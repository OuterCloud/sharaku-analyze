#!/usr/bin/env python3
"""
Sharaku Analyze - 港美股智能预测分析 Web 服务
"""

import time
import warnings
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from sharaku import DataUtils, GBMPredictor, MonteCarloPredictor, ProphetPredictor, StockDatabase, analyze_wheel_strategy
from sharaku.lib.visualization import (
    generate_batch_chart,
    generate_cumulative_returns_chart,
    generate_monte_carlo_paths_chart,
    generate_prediction_chart,
)

load_dotenv()

# Disable matplotlib warnings
warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")

# --- In-memory cache with TTL ---
_cache: Dict[str, dict] = {}
CACHE_TTL = 3600  # 1 hour


def _cache_get(key: str) -> Optional[dict]:
    entry = _cache.get(key)
    if entry and time.time() - entry["ts"] < CACHE_TTL:
        return entry["data"]
    if entry:
        del _cache[key]
    return None


def _cache_set(key: str, data: dict):
    _cache[key] = {"data": data, "ts": time.time()}


# --- Database ---
stock_db = StockDatabase()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Sharaku Analyze starting...")
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
        if local_stocks:
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
                    # 根据 exchange 或 ticker 后缀判断市场
                    if ticker.endswith(".HK") or exchange in ("HKG", "HKSE"):
                        stock_type = "HK"
                    elif ticker.endswith(".SS") or ticker.endswith(".SZ"):
                        stock_type = "CN"
                    else:
                        stock_type = "US"
                    results.append({"ticker": ticker, "name": name, "stock_type": stock_type})
            return JSONResponse(content={"success": True, "stocks": results})

        return JSONResponse(content={"success": True, "stocks": local_stocks})
    except Exception as e:
        # fallback to local
        local_stocks = stock_db.search_stocks(q, enabled_only)
        return JSONResponse(content={"success": True, "stocks": local_stocks})


@app.post("/api/stocks")
async def add_stock(
    ticker: str = Form(...),
    name: str = Form(...),
    sector: str = Form(""),
    stock_type: str = Form("US"),
):
    """添加新股票"""
    try:
        if not ticker or not name:
            raise HTTPException(status_code=400, detail="股票代码和名称不能为空")

        success = stock_db.add_stock(ticker, name, sector, stock_type)
        if success:
            return JSONResponse(content={"success": True, "message": "股票添加成功"})
        else:
            return JSONResponse(
                content={"success": False, "error": "股票代码已存在"}, status_code=400
            )
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)


@app.get("/api/stocks/validate")
async def validate_ticker(ticker: str):
    """验证并添加任意美股标的"""
    import yfinance as yf

    ticker = ticker.upper().strip()
    # 先查本地数据库
    existing = stock_db.get_stock_by_ticker(ticker)
    if existing:
        return JSONResponse(content={
            "success": True,
            "stock": {"ticker": existing["ticker"], "name": existing["name"]},
        })

    # 通过 yfinance 验证
    try:
        info = yf.Ticker(ticker).fast_info
        if info and info.get("lastPrice"):
            name = ticker  # fast_info 没有 name，用 ticker 代替
            try:
                full_info = yf.Ticker(ticker).info
                name = full_info.get("shortName") or full_info.get("longName") or ticker
            except Exception:
                pass
            # 自动添加到数据库
            stock_db.add_stock(ticker, name, "", "US")
            return JSONResponse(content={
                "success": True,
                "stock": {"ticker": ticker, "name": name},
            })
    except Exception:
        pass

    return JSONResponse(content={"success": False, "error": f"无法识别标的: {ticker}"})


# ==================== Prediction ====================


@app.post("/api/predict/single")
async def predict_single_stock(
    ticker: str = Form(...),
    target_date: str = Form(...),
):
    """单个股票预测 API"""
    try:
        ticker = ticker.upper()

        # Check cache
        cache_key = f"single:{ticker}:{target_date}"
        cached = _cache_get(cache_key)
        if cached:
            return JSONResponse(content=cached)

        # Verify stock exists, auto-add if not in DB
        stock_info = stock_db.get_stock_by_ticker(ticker)
        if not stock_info or not stock_info["enabled"]:
            # 尝试自动添加
            stock_db.add_stock(ticker, ticker, "", "US")
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
        target_dt = datetime.strptime(target_date, "%Y-%m-%d")
        last_date = prepared_data["close_prices"].index[-1]
        if hasattr(last_date, "date"):
            last_date = last_date.date()
        else:
            last_date = pd.to_datetime(last_date).date()
        trading_days = (target_dt.date() - last_date).days

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
        except Exception as prophet_error:
            logger.debug(f"Prophet prediction skipped: {prophet_error}")

        # Generate charts
        chart_base64, stats_data = generate_prediction_chart(
            ticker, current_price,
            gbm_predictions["final_prices"],
            mc_predictions["final_prices"],
            target_date,
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
        ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]

        # Check cache
        cache_key = f"batch:{'_'.join(sorted(ticker_list))}:{target_date}"
        cached = _cache_get(cache_key)
        if cached:
            return JSONResponse(content=cached)

        # Auto-add missing tickers to DB
        available_stocks = stock_db.get_stocks_dict()
        for t in ticker_list:
            if t not in available_stocks:
                stock_db.add_stock(t, t, "", "US")
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

                target_dt = datetime.strptime(target_date, "%Y-%m-%d")
                last_date = prepared_data["close_prices"].index[-1]
                if hasattr(last_date, "date"):
                    last_date = last_date.date()
                else:
                    last_date = pd.to_datetime(last_date).date()
                trading_days = (target_dt.date() - last_date).days

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


# ==================== Wheel Strategy ====================


@app.post("/api/wheel/analyze")
async def wheel_analyze(
    ticker: str = Form(...),
    cost_basis: float = Form(...),
):
    """Wheel期权策略分析 API"""
    try:
        ticker = ticker.upper()

        # Check cache
        cache_key = f"wheel:{ticker}:{cost_basis}"
        cached = _cache_get(cache_key)
        if cached:
            return JSONResponse(content=cached)

        result = analyze_wheel_strategy(ticker, cost_basis)

        if result.get("success"):
            _cache_set(cache_key, result)

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Wheel analysis failed: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)


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
