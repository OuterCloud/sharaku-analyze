#!/usr/bin/env python3
"""
Sharaku Analyze - 股票智能预测分析 Web 服务
"""

import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import uvicorn
from diskcache import Cache
from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from sharaku import DataUtils, GBMPredictor, MonteCarloPredictor, ProphetPredictor, StockDatabase, TechnicalAnalyzer, analyze_wheel_strategy
from sharaku.config import Path as SharakuPath
from sharaku.lib.advisor import InvestmentAdvisor
from sharaku.lib.market_session import fetch_us_market_movers, fetch_us_market_movers_by_tickers, get_us_market_session
from sharaku.lib.screener import run_screener
from sharaku.lib.visualization import (
    generate_batch_chart,
    generate_cumulative_returns_chart,
    generate_monte_carlo_paths_chart,
    generate_prediction_chart,
    generate_prophet_chart,
)

# override=True：项目内的 .env 是本项目配置的唯一权威来源。
# 默认的 override=False 会让 shell 中残留的同名变量（如旧的 LLM_API_KEY）
# 静默覆盖 .env，导致改了配置却不生效、且报错指向一个你以为已经换掉的值。
load_dotenv(override=True)

# Disable matplotlib warnings
warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")

# --- Disk cache with TTL ---
_cache_dir = Path(__file__).parent / ".cache" / "predictions"
_cache = Cache(str(_cache_dir))
CACHE_TTL = 3600  # 1 hour


def _cache_get(key: str) -> Optional[dict]:
    return _cache.get(key)


def _cache_set(key: str, data: dict):
    _cache.set(key, data, expire=CACHE_TTL)


# --- Market detection ---
_EXCHANGE_TO_MARKET = {
    "NYQ": "US", "NMS": "US", "NGM": "US", "PCX": "US", "BTS": "US",  # 美国
    "HKG": "HK", "HKSE": "HK",  # 香港
    "SHH": "CN", "SHZ": "CN",  # A股
    "JPX": "JP", "TYO": "JP",  # 日本
    "TAI": "TW", "TWO": "TW",  # 台湾
    "KSC": "KR", "KOE": "KR",  # 韩国
    "LSE": "UK", "IOB": "UK",  # 英国
    "FRA": "DE", "GER": "DE",  # 德国
    "PAR": "FR", "ENX": "FR",  # 法国
    "SGX": "SG",  # 新加坡
    "ASX": "AU",  # 澳洲
    "TSX": "CA", "CNQ": "CA",  # 加拿大
}

_SUFFIX_TO_MARKET = {
    ".HK": "HK", ".SS": "CN", ".SZ": "CN",
    ".T": "JP", ".TW": "TW", ".TWO": "TW",
    ".KS": "KR", ".KQ": "KR",
    ".L": "UK", ".F": "DE", ".PA": "FR",
    ".SI": "SG", ".AX": "AU", ".TO": "CA",
}


def _detect_market(ticker: str, exchange: str) -> str:
    """根据交易所代码和 ticker 后缀判断市场"""
    if exchange in _EXCHANGE_TO_MARKET:
        return _EXCHANGE_TO_MARKET[exchange]
    for suffix, market in _SUFFIX_TO_MARKET.items():
        if ticker.endswith(suffix):
            return market
    return "US"


# --- Helpers ---

MAX_BATCH_TICKERS = 20


def _validate_target_date(target_date: str) -> datetime:
    """校验并解析目标日期，非法格式抛 HTTPException"""
    try:
        dt = datetime.strptime(target_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail=f"日期格式错误，需要 YYYY-MM-DD: {target_date}")
    if dt.date() <= datetime.now().date():
        raise HTTPException(status_code=400, detail="目标日期必须是未来日期")
    return dt


def _calc_trading_days(target_date: str, prepared_data: dict) -> int:
    """从 prepared_data 计算到目标日期的交易天数"""
    target_dt = _validate_target_date(target_date)
    last_date = prepared_data["close_prices"].index[-1]
    if hasattr(last_date, "date"):
        last_date = last_date.date()
    else:
        last_date = pd.to_datetime(last_date).date()
    return (target_dt.date() - last_date).days


import json

# --- Database ---
stock_db = StockDatabase()

# --- Investment Advisor (LLM) ---
advisor = InvestmentAdvisor(knowledge_dir=SharakuPath.knowledge_dir())


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Sharaku Analyze starting...")
    # 输出顾问模块的生效配置（key 仅掩码显示），避免配置未生效时难以排查
    if advisor.is_configured():
        key = advisor.api_key
        masked = f"{key[:7]}...{key[-4:]}" if len(key) > 12 else "***"
        logger.info(f"Advisor: model={advisor.model} key={masked} base_url={advisor.base_url or 'default'}")
        logger.info(f"Advisor: knowledge_dir={advisor.knowledge_base.root_dir} "
                    f"docs={advisor.knowledge_stats()['doc_count']}")
    else:
        logger.warning("Advisor: LLM_API_KEY 未配置，投资顾问模块不可用")
    yield
    logger.info("Sharaku Analyze shutting down.")


app = FastAPI(title="Sharaku Analyze", version="0.1.0", lifespan=lifespan)

# Serve frontend build
frontend_dist = Path(__file__).parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")


# ==================== Health ====================


@app.get("/health")
async def health_check():
    return JSONResponse(content={
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "0.1.0",
    })


# ==================== Stock Management ====================


@app.get("/api/stocks")
async def get_stocks(enabled_only: bool = True, stock_type: str = None):
    """获取所有已缓存的股票（用户曾搜索/使用过的标的）"""
    try:
        stocks = stock_db.get_all_stocks(enabled_only, stock_type)
        return JSONResponse(content={"success": True, "stocks": stocks})
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)


@app.get("/api/stocks/search")
async def search_stocks(q: str = "", enabled_only: bool = True):
    """搜索股票 - 先查本地库，再通过 Yahoo Finance 动态搜索"""
    try:
        if not q.strip():
            # 空查询返回本地已缓存的股票
            stocks = stock_db.get_all_stocks(enabled_only)
            return JSONResponse(content={"success": True, "stocks": stocks})

        # 先从本地数据库搜
        local_stocks = stock_db.search_stocks(q, enabled_only)
        # 如果本地结果都有完整名称（非自动入库的），直接返回
        if local_stocks and all(s["name"] != s["ticker"] for s in local_stocks):
            return JSONResponse(content={"success": True, "stocks": local_stocks})

        # 本地没有结果，通过 Yahoo Finance 搜索
        import requests
        resp = requests.get(
            "https://query2.finance.yahoo.com/v1/finance/search",
            params={"q": q, "quotesCount": 30, "newsCount": 0, "enableFuzzyQuery": True},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            quotes = data.get("quotes", [])
            results = []
            for quote in quotes:
                # 只保留股票和ETF
                qtype = quote.get("quoteType", "")
                if qtype in ("EQUITY", "ETF"):
                    ticker = quote.get("symbol", "")
                    name = quote.get("shortname") or quote.get("longname") or ticker
                    exchange = quote.get("exchange", "")
                    # 根据 exchange 和 ticker 后缀判断市场
                    stock_type = _detect_market(ticker, exchange)
                    results.append({"ticker": ticker, "name": name, "stock_type": stock_type})
            return JSONResponse(content={"success": True, "stocks": results})

        return JSONResponse(content={"success": True, "stocks": local_stocks})
    except Exception as e:
        # fallback to local
        local_stocks = stock_db.search_stocks(q, enabled_only)
        return JSONResponse(content={"success": True, "stocks": local_stocks})




# ==================== Prediction ====================


@app.post("/api/predict/single")
async def predict_single_stock(
    ticker: str = Form(...),
    target_date: str = Form(...),
):
    """单个股票预测 API"""
    try:
        ticker = ticker.upper()
        _validate_target_date(target_date)

        # Check cache
        cache_key = f"single:{ticker}:{target_date}"
        cached = _cache_get(cache_key)
        if cached:
            return JSONResponse(content=cached)

        # Verify stock exists, auto-add if not in DB
        stock_info = stock_db.get_stock_by_ticker(ticker)
        if not stock_info or not stock_info["enabled"]:
            # 尝试自动添加
            stock_db.add_stock(ticker, ticker, "", _detect_market(ticker, ""))
            stock_info = stock_db.get_stock_by_ticker(ticker)
            if not stock_info:
                raise HTTPException(status_code=400, detail="股票不存在或未启用")

        # Date range: past 2 years
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")

        # Data preparation
        data_utils = DataUtils()
        prepared_data = data_utils.prepare_model_data(ticker, start_date, end_date)

        # Get latest price
        latest_prices = data_utils.get_latest_price_info(ticker)
        current_price = (
            latest_prices["current_price"]
            or prepared_data["statistics"]["current_price"]
        )

        # Calculate trading days
        trading_days = _calc_trading_days(target_date, prepared_data)

        # GBM prediction
        gbm = GBMPredictor(ticker)
        gbm.fit(prepared_data["raw_data"])
        gbm_predictions = gbm.predict(target_date, n_simulations=200000)
        gbm_risk = gbm.analyze_risk(gbm_predictions)

        # Monte Carlo prediction
        mc = MonteCarloPredictor(ticker)
        mc.fit(prepared_data["raw_data"])
        mc_predictions = mc.predict(days=trading_days, n_paths=200000)
        mc_risk = mc.analyze_risk(mc_predictions)

        # Prophet prediction (optional)
        prophet_result = None
        prophet_chart_base64 = ""
        try:
            prophet = ProphetPredictor(ticker)
            prophet.fit(prepared_data["raw_data"])
            prophet_predictions = prophet.predict(days=trading_days, return_full_forecast=True)
            prophet_risk = prophet.analyze_risk(prophet_predictions)
            prophet_trend = prophet.get_trend_analysis(days=trading_days)

            prophet_result = {
                "mean_price": float(prophet_predictions["prediction"]),
                "return": float(prophet_predictions["expected_return"]),
                "lower_bound": float(prophet_predictions["lower_bound"]),
                "upper_bound": float(prophet_predictions["upper_bound"]),
                "uncertainty": float(prophet_risk["uncertainty"]),
                "risk_level": prophet_risk["risk_level"],
                "trend_change": float(prophet_trend.get("trend_change_pct", 0)),
            }

            # Generate Prophet forecast chart
            prophet_chart_base64 = generate_prophet_chart(
                ticker, prophet_predictions, float(current_price)
            )
        except Exception as prophet_error:
            logger.debug(f"Prophet prediction skipped: {prophet_error}")

        # Generate charts
        chart_base64, stats_data = generate_prediction_chart(
            ticker, current_price,
            gbm_predictions["final_prices"],
            mc_predictions["final_prices"],
            target_date,
            prophet_result=prophet_result,
        )

        mc_paths_chart_base64 = generate_monte_carlo_paths_chart(
            ticker, current_price, mc_predictions, target_date,
        )

        mc_cumulative_returns_chart_base64 = generate_cumulative_returns_chart(
            ticker, current_price, mc_predictions, target_date,
        )

        result = {
            "success": True,
            "ticker": ticker,
            "name": stock_info["name"],
            "current_price": float(current_price),
            "target_date": target_date,
            "trading_days": trading_days,
            "gbm": {
                "mean_price": float(gbm_risk["mean_price"]),
                "median_price": float(gbm_risk["median_price"]),
                "return": float(gbm_risk["mean_return"]),
                "percentile_5": float(gbm_risk.get("price_percentile_5", 0)),
                "percentile_95": float(gbm_risk.get("price_percentile_95", 0)),
            },
            "mc": {
                "mean_price": float(mc_risk["mean_price"]),
                "median_price": float(mc_risk["median_price"]),
                "return": float(mc_risk["mean_return"]),
                "percentile_5": float(mc_risk.get("price_percentile_5", 0)),
                "percentile_95": float(mc_risk.get("price_percentile_95", 0)),
            },
            "prophet": prophet_result,
            "volatility": float(prepared_data["statistics"].get("volatility_annual", 0)),
            "chart": chart_base64,
            "mc_paths_chart": mc_paths_chart_base64,
            "mc_cumulative_returns_chart": mc_cumulative_returns_chart_base64,
            "prophet_chart": prophet_chart_base64,
            "stats_summary": stats_data,
        }

        _cache_set(cache_key, result)
        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Single prediction failed: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)


@app.post("/api/predict/batch")
async def predict_batch_stocks(
    tickers: str = Form(...),
    target_date: str = Form(...),
):
    """批量股票预测 API"""
    try:
        _validate_target_date(target_date)
        ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
        if len(ticker_list) > MAX_BATCH_TICKERS:
            raise HTTPException(status_code=400, detail=f"批量预测最多 {MAX_BATCH_TICKERS} 只股票")

        # Check cache
        cache_key = f"batch:{'_'.join(sorted(ticker_list))}:{target_date}"
        cached = _cache_get(cache_key)
        if cached:
            return JSONResponse(content=cached)

        # Auto-add missing tickers to DB
        available_stocks = stock_db.get_stocks_dict()
        for t in ticker_list:
            if t not in available_stocks:
                stock_db.add_stock(t, t, "", _detect_market(t, ""))
        available_stocks = stock_db.get_stocks_dict()

        # Date range
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")

        results = []

        for ticker in ticker_list:
            try:
                data_utils = DataUtils()
                prepared_data = data_utils.prepare_model_data(ticker, start_date, end_date)

                latest_prices = data_utils.get_latest_price_info(ticker)
                current_price = (
                    latest_prices["current_price"]
                    or prepared_data["statistics"]["current_price"]
                )

                trading_days = _calc_trading_days(target_date, prepared_data)

                # GBM
                gbm = GBMPredictor(ticker)
                gbm.fit(prepared_data["raw_data"])
                gbm_predictions = gbm.predict(target_date, n_simulations=200000)
                gbm_risk = gbm.analyze_risk(gbm_predictions)

                # MC
                mc = MonteCarloPredictor(ticker)
                mc.fit(prepared_data["raw_data"])
                mc_predictions = mc.predict(days=trading_days, n_paths=200000)
                mc_risk = mc.analyze_risk(mc_predictions)

                result = {
                    "ticker": ticker,
                    "name": available_stocks[ticker],
                    "current_price": float(current_price),
                    "gbm_mean_price": float(gbm_risk["mean_price"]),
                    "gbm_return": float(gbm_risk["mean_return"]),
                    "mc_mean_price": float(mc_risk["mean_price"]),
                    "mc_return": float(mc_risk["mean_return"]),
                    "price_5th": float(gbm_risk.get("price_percentile_5", 0)),
                    "price_95th": float(gbm_risk.get("price_percentile_95", 0)),
                    "volatility": float(prepared_data["statistics"].get("volatility_annual", 0)),
                }
                results.append(result)

            except Exception as e:
                logger.error(f"{ticker} prediction failed: {e}")
                continue

        # Sort by return
        results.sort(key=lambda x: x["gbm_return"], reverse=True)

        # Generate chart
        chart_base64 = generate_batch_chart(results, target_date)

        batch_result = {
            "success": True,
            "target_date": target_date,
            "results": results,
            "chart": chart_base64,
        }

        _cache_set(cache_key, batch_result)
        return JSONResponse(content=batch_result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch prediction failed: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)


# ==================== Quick Batch Prediction ====================

# Detect Prophet availability once at startup
_PROPHET_AVAILABLE = False
try:
    import prophet as _prophet_mod  # noqa: F401
    _PROPHET_AVAILABLE = True
except ImportError:
    pass

_quick_executor = ThreadPoolExecutor(max_workers=8)


def _quick_predict_one(ticker: str, target_date: str, include_prophet: bool = False) -> Optional[dict]:
    """预测单只股票的 GBM/MC（可选 Prophet），带 per-ticker 缓存"""
    suffix = ":p" if include_prophet else ""
    cache_key = f"qp:{ticker}:{target_date}{suffix}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")

    data_utils = DataUtils()
    prepared_data = data_utils.prepare_model_data(ticker, start_date, end_date)

    latest_prices = data_utils.get_latest_price_info(ticker)
    current_price = (
        latest_prices["current_price"]
        or prepared_data["statistics"]["current_price"]
    )

    try:
        trading_days = _calc_trading_days(target_date, prepared_data)
    except HTTPException:
        return None

    if trading_days <= 0:
        return None

    cur = float(current_price)

    # GBM with 10k simulations (sufficient for quick overview)
    gbm = GBMPredictor(ticker)
    gbm.fit(prepared_data["raw_data"])
    gbm_predictions = gbm.predict(target_date, n_simulations=10000)
    gbm_risk = gbm.analyze_risk(gbm_predictions)
    gbm_price = float(gbm_risk["mean_price"])

    # Monte Carlo with 10k paths
    mc = MonteCarloPredictor(ticker)
    mc.fit(prepared_data["raw_data"])
    mc_predictions = mc.predict(days=trading_days, n_paths=10000)
    mc_risk = mc.analyze_risk(mc_predictions)
    mc_price = float(mc_risk["mean_price"])

    # Prophet (only when explicitly requested)
    prophet_price = None
    prophet_ret = None
    if include_prophet and _PROPHET_AVAILABLE:
        try:
            p = ProphetPredictor(ticker)
            p.fit(prepared_data["raw_data"])
            prophet_predictions = p.predict(days=trading_days)
            prophet_price = float(prophet_predictions["prediction"])
            prophet_ret = (prophet_price - cur) / cur if cur > 0 else None
        except Exception as prophet_err:
            logger.debug(f"Quick Prophet {ticker} skipped: {prophet_err}")

    # Compute returns relative to live current price
    result = {
        "ticker": ticker,
        "current_price": cur,
        "gbm_mean_price": gbm_price,
        "gbm_return": (gbm_price - cur) / cur if cur > 0 else 0.0,
        "mc_mean_price": mc_price,
        "mc_return": (mc_price - cur) / cur if cur > 0 else 0.0,
        "prophet_mean_price": prophet_price,
        "prophet_return": prophet_ret,
    }
    _cache_set(cache_key, result)
    return result


@app.get("/api/predict/quick-batch")
async def predict_quick_batch(
    tickers: str = "",
    target_date: str = "",
    prophet: str = "0",
):
    """轻量批量预测 - 并行跑 GBM/MC（可选 Prophet），用于行情表异步加载"""
    try:
        if not tickers.strip() or not target_date.strip():
            return JSONResponse(content={"success": False, "error": "Missing tickers or target_date"}, status_code=400)

        ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
        if not ticker_list:
            return JSONResponse(content={"success": True, "results": []})

        include_prophet = prophet == "1"

        # Submit all tickers to thread pool for parallel execution
        futures = {
            _quick_executor.submit(_quick_predict_one, ticker, target_date, include_prophet): ticker
            for ticker in ticker_list
        }

        results = []
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                item = future.result(timeout=30)
                if item:
                    results.append(item)
            except Exception as e:
                logger.debug(f"Quick predict {ticker} skipped: {e}")

        return JSONResponse(content={"success": True, "results": results})

    except Exception as e:
        logger.error(f"Quick batch prediction failed: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)


# ==================== Technical Analysis ====================


@app.post("/api/technical/analyze")
async def technical_analyze(
    ticker: str = Form(...),
    lang: str = Form("zh"),
):
    """技术分析 API"""
    try:
        ticker = ticker.upper()
        lang = lang if lang in ("zh", "en") else "zh"

        # Check cache
        cache_key = f"technical:{ticker}:{lang}"
        cached = _cache_get(cache_key)
        if cached:
            return JSONResponse(content=cached)

        # Auto-add ticker to DB if not present
        stock_info = stock_db.get_stock_by_ticker(ticker)
        if not stock_info:
            stock_db.add_stock(ticker, ticker, "", _detect_market(ticker, ""))

        analyzer = TechnicalAnalyzer(ticker, lang=lang)
        result = analyzer.analyze()

        if result.get("success"):
            _cache_set(cache_key, result)

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Technical analysis failed: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)


# ==================== Wheel Strategy ====================


@app.post("/api/wheel/analyze")
async def wheel_analyze(
    ticker: str = Form(...),
    cost_basis: float = Form(0),
    lang: str = Form("zh"),
):
    """Wheel期权策略分析 API"""
    try:
        ticker = ticker.upper()
        lang = lang if lang in ("zh", "en") else "zh"

        # Check cache
        cache_key = f"wheel:{ticker}:{cost_basis}:{lang}"
        cached = _cache_get(cache_key)
        if cached:
            return JSONResponse(content=cached)

        result = analyze_wheel_strategy(ticker, cost_basis, lang=lang)

        if result.get("success"):
            _cache_set(cache_key, result)

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Wheel analysis failed: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)


# ==================== Market Session & Movers ====================


@app.get("/api/market/session")
async def market_session():
    """获取当前美股交易时段"""
    try:
        session = get_us_market_session()
        return JSONResponse(content={"success": True, **session})
    except Exception as e:
        logger.error(f"Market session detection failed: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)


@app.get("/api/market/movers")
async def market_movers(category: str = "all", tickers: str = ""):
    """
    获取美股涨跌幅排行。
    category: gainers / losers / actives / all（动态获取 Yahoo Finance 实时榜单）
    tickers: 可选，逗号分隔的自选股票代码列表
    """
    try:
        logger.info(f"Market movers request: category={category}")
        session_info = get_us_market_session()

        if tickers.strip():
            # 自选模式：按用户指定的 tickers 查询
            ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
            movers = fetch_us_market_movers_by_tickers(ticker_list[:50])
            return JSONResponse(content={
                "success": True,
                "session": session_info,
                "data": {"custom": movers},
                "mode": "custom",
            })

        # 动态获取 Yahoo Finance 实时榜单（并行 + 缓存）
        data = fetch_us_market_movers(category=category, count=30)

        logger.info(f"Market movers done: {', '.join(f'{k}={len(v)}' for k, v in data.items())}")
        return JSONResponse(content={
            "success": True,
            "session": session_info,
            "data": data,
            "mode": "screener",
        })

    except Exception as e:
        logger.error(f"Market movers failed: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)


# ==================== Stock Screener ====================

SCREENER_CACHE_TTL = 1800  # 30 minutes for screener results


@app.post("/api/screener/run")
async def screener_run(
    peg_max: float = Form(1.0),
    roe_min: float = Form(0.12),
    min_market_cap: float = Form(10_000_000_000),
    de_max: float = Form(100.0),
    fcf_positive: str = Form("1"),
    sectors: str = Form(""),
):
    """
    执行 S&P 500 量化选股。

    Form 参数：
        peg_max: PEG 上限（默认 1.0）
        roe_min: ROE 最低要求（默认 0.12 即 12%）
        min_market_cap: 最低市值（默认 $10B）
        de_max: D/E 最大值（默认 100%）
        fcf_positive: 是否要求正 FCF（"1" 或 "0"）
        sectors: 板块过滤，逗号分隔（空则使用默认板块列表）
    """
    try:
        # 构建参数
        params = {
            "peg_max": peg_max,
            "roe_min": roe_min,
            "min_market_cap": min_market_cap,
            "de_max": de_max,
            "fcf_positive": fcf_positive == "1",
        }

        if sectors.strip():
            params["sectors"] = [s.strip() for s in sectors.split(",") if s.strip()]

        # 检查缓存
        cache_key = f"screener:{peg_max}:{roe_min}:{min_market_cap}:{de_max}:{fcf_positive}:{sectors}"
        cached = _cache_get(cache_key)
        if cached:
            return JSONResponse(content=cached)

        # 执行筛选（耗时操作，约 30-60s）
        result = run_screener(params)

        if result["success"]:
            _cache.set(cache_key, result, expire=SCREENER_CACHE_TTL)

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Screener failed: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)


# ==================== Investment Advisor (LLM) ====================

# 市场上下文缓存 TTL（同一标的追问时复用，避免重复采集数据）
ADVISOR_CONTEXT_TTL = 300


@app.get("/api/advisor/status")
async def advisor_status():
    """顾问模块状态：LLM 是否已配置、知识库概况"""
    try:
        stats = advisor.knowledge_stats()
        return JSONResponse(content={
            "success": True,
            "configured": advisor.is_configured(),
            "model": advisor.model,
            "knowledge": stats,
        })
    except Exception as e:
        logger.error(f"Advisor status failed: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)


@app.post("/api/advisor/chat")
async def advisor_chat(
    ticker: str = Form(...),
    question: str = Form(...),
    cost_basis: float = Form(0),
    horizon_days: int = Form(30),
    history: str = Form("[]"),
    use_cached_context: str = Form("1"),
):
    """
    投资顾问对话（SSE 流式输出）。

    Form 参数：
        ticker: 股票代码
        question: 用户提问
        cost_basis: 持仓成本（0 表示未持仓）
        horizon_days: 统计预测跨度
        history: JSON 数组，形如 [{"role":"user","content":"..."}]
        use_cached_context: "1" 时复用缓存的市场上下文（追问场景）
    """
    ticker = ticker.upper().strip()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker 不能为空")
    if not question.strip():
        raise HTTPException(status_code=400, detail="question 不能为空")

    try:
        parsed_history = json.loads(history) if history else []
        if not isinstance(parsed_history, list):
            parsed_history = []
        # 只保留合法的 role/content 结构
        parsed_history = [
            {"role": m["role"], "content": m["content"]}
            for m in parsed_history
            if isinstance(m, dict)
            and m.get("role") in ("user", "assistant")
            and isinstance(m.get("content"), str)
            and m["content"].strip()
        ]
    except (json.JSONDecodeError, TypeError, KeyError):
        parsed_history = []

    # 自动入库
    if not stock_db.get_stock_by_ticker(ticker):
        stock_db.add_stock(ticker, ticker, "", _detect_market(ticker, ""))

    # 复用市场上下文（同一标的的追问不必重新采集全量数据）
    ctx_cache_key = f"advisor_ctx:{ticker}:{cost_basis}:{horizon_days}"
    cached_context = None
    if use_cached_context == "1":
        cached_context = _cache.get(ctx_cache_key)

    def event_stream():
        def cache_context(ctx: dict):
            _cache.set(ctx_cache_key, ctx, expire=ADVISOR_CONTEXT_TTL)

        try:
            for event in advisor.stream_chat(
                ticker=ticker,
                question=question,
                cost_basis=cost_basis,
                horizon_days=horizon_days,
                history=parsed_history,
                cached_context=cached_context,
                on_context=cache_context,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"Advisor stream failed: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲，保证流式实时性
        },
    )


# ==================== SPA Fallback ====================


@app.get("/{path:path}")
async def serve_spa(path: str):
    """Serve the SPA index.html for all non-API routes"""
    index_file = frontend_dist / "index.html"
    if index_file.exists():
        from fastapi.responses import FileResponse
        return FileResponse(str(index_file))
    return JSONResponse(
        content={"message": "Frontend not built. Run: cd frontend && npm run build"},
        status_code=404,
    )


if __name__ == "__main__":
    import os

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    log_level = os.getenv("LOG_LEVEL", "info")

    uvicorn.run("app:app", host=host, port=port, log_level=log_level, reload=True)
