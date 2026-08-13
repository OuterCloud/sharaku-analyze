"""
Stock Screener - S&P 500 量化选股模块

基于多维量化因子自动筛选标普 500 成分股中符合条件的投资标的。
支持自定义筛选参数，默认策略为低估值+高质量成长股。
"""

import concurrent.futures
from typing import Optional

import pandas as pd
import yfinance as yf
from loguru import logger


# --- 默认筛选参数 ---

DEFAULT_PARAMS = {
    "min_market_cap": 10_000_000_000,  # 最低市值 $10B
    "sectors": ["Healthcare", "Technology", "Financial Services", "Industrials", "Energy"],
    "peg_max": 1.0,  # PEG 上限
    "peg_min": 0.0,  # PEG 下限（排除负值）
    "roe_min": 0.12,  # ROE 最低 12%
    "fcf_positive": True,  # 要求正自由现金流
    "de_max": 100.0,  # D/E 最大 100%
    "max_workers": 20,  # 并发线程数
}


# --- 内置核心标的列表（S&P 500 权重前 100，网络不可用时作为 fallback） ---

_FALLBACK_SP500_CORE = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "GOOG", "BRK-B", "LLY", "AVGO",
    "JPM", "TSLA", "UNH", "XOM", "V", "PG", "JNJ", "MA", "COST", "HD",
    "MRK", "ABBV", "CRM", "AMD", "NFLX", "CVX", "BAC", "KO", "PEP", "WMT",
    "LIN", "TMO", "ADBE", "ACN", "MCD", "CSCO", "ABT", "ORCL", "DHR", "WFC",
    "CMCSA", "PM", "TXN", "INTC", "VZ", "NEE", "IBM", "INTU", "RTX", "AMGN",
    "QCOM", "HON", "UNP", "AMAT", "GE", "CAT", "ISRG", "SPGI", "LOW", "PFE",
    "NOW", "BA", "GS", "T", "ELV", "BLK", "BKNG", "AXP", "SYK", "MDT",
    "SBUX", "MDLZ", "ADI", "LMT", "DE", "GILD", "MMC", "TJX", "VRTX", "ADP",
    "CI", "CB", "ETN", "LRCX", "REGN", "MO", "ZTS", "TMUS", "SO", "BDX",
    "FI", "DUK", "BSX", "CL", "CME", "SCHW", "PLD", "PGR", "SLB", "NOC",
]


def _fetch_via_yahoo_screener(min_market_cap: int = 10_000_000_000) -> list[str]:
    """通过 Yahoo Finance Screener API 获取美股大盘股列表（无需翻墙）"""
    import requests

    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"
    session.get("https://fc.yahoo.com", timeout=5)
    crumb = session.get("https://query2.finance.yahoo.com/v1/test/getcrumb", timeout=5).text

    all_symbols = []
    # Yahoo screener 单次最多 250 条，分页获取
    for offset in range(0, 750, 250):
        url = f"https://query2.finance.yahoo.com/v1/finance/screener?crumb={crumb}"
        body = {
            "size": 250,
            "offset": offset,
            "sortField": "intradaymarketcap",
            "sortType": "DESC",
            "quoteType": "EQUITY",
            "query": {
                "operator": "AND",
                "operands": [
                    {"operator": "eq", "operands": ["region", "us"]},
                    {"operator": "btwn", "operands": ["intradaymarketcap", min_market_cap, 100_000_000_000_000]},
                ],
            },
        }
        resp = session.post(url, json=body, timeout=15)
        if resp.status_code != 200:
            break
        data = resp.json()
        quotes = data.get("finance", {}).get("result", [{}])[0].get("quotes", [])
        if not quotes:
            break
        for q in quotes:
            symbol = q.get("symbol", "")
            # 过滤掉非普通股（如 BRK-A 这类超高价股保留，但排除 warrants/units）
            if symbol and "." not in symbol and "-W" not in symbol and "-U" not in symbol:
                all_symbols.append(symbol)

    return all_symbols


def get_sp500_tickers() -> list[str]:
    """
    获取美股大盘股列表用于选股扫描。

    优先级：
    1. Yahoo Finance Screener API（直接获取美股 $10B+ 市值股票，国内可访问）
    2. Wikipedia S&P 500 列表
    3. GitHub datahub CSV
    """
    # 方案 1：Yahoo Finance Screener（最可靠，国内直连）
    try:
        tickers = _fetch_via_yahoo_screener()
        if len(tickers) >= 100:
            logger.info(f"从 Yahoo Screener 获取到 {len(tickers)} 只美股大盘股")
            return tickers
    except Exception as e:
        logger.warning(f"Yahoo Screener 获取失败: {e}")

    # 方案 2：Wikipedia
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        tables = pd.read_html(url, attrs={"id": "constituents"})
        df = tables[0]
        tickers = df["Symbol"].str.replace(".", "-", regex=False).tolist()
        logger.info(f"从 Wikipedia 获取到 {len(tickers)} 只 S&P 500 成分股")
        return tickers
    except Exception as e:
        logger.warning(f"Wikipedia 获取失败: {e}")

    # 方案 3：GitHub datahub
    try:
        import requests
        csv_url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
        resp = requests.get(csv_url, timeout=10)
        resp.raise_for_status()
        from io import StringIO
        df = pd.read_csv(StringIO(resp.text))
        tickers = df["Symbol"].str.replace(".", "-", regex=False).tolist()
        logger.info(f"从 GitHub datahub 获取到 {len(tickers)} 只 S&P 500 成分股")
        return tickers
    except Exception as e:
        logger.error(f"所有数据源均失败: {e}")
        return []


def _analyze_single_ticker(symbol: str, params: dict) -> Optional[dict]:
    """对单只股票执行量化筛选，返回 dict 或 None（不通过）"""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info

        # 提取核心指标
        market_cap = info.get("marketCap", 0)
        peg = info.get("pegRatio")
        forward_pe = info.get("forwardPE")
        trailing_pe = info.get("trailingPE")
        roe = info.get("returnOnEquity")
        fcf = info.get("freeCashflow")
        debt_to_equity = info.get("debtToEquity")  # 百分比形式
        sector = info.get("sector", "")
        name = info.get("shortName", symbol)
        dividend_yield = info.get("dividendYield")
        revenue_growth = info.get("revenueGrowth")
        profit_margin = info.get("profitMargins")

        # 价格位置指标
        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        week52_high = info.get("fiftyTwoWeekHigh")
        week52_low = info.get("fiftyTwoWeekLow")

        # --- 筛选规则 ---

        # 规则 1：市值门槛
        min_cap = params.get("min_market_cap", DEFAULT_PARAMS["min_market_cap"])
        if not market_cap or market_cap < min_cap:
            return None

        # 规则 2：板块过滤
        sectors = params.get("sectors", DEFAULT_PARAMS["sectors"])
        if sectors and sector not in sectors:
            return None

        # 规则 3：PEG 估值匹配
        peg_min = params.get("peg_min", DEFAULT_PARAMS["peg_min"])
        peg_max = params.get("peg_max", DEFAULT_PARAMS["peg_max"])
        if peg is None or not (peg_min < peg <= peg_max):
            return None

        # 规则 4：ROE 资本效率
        roe_min = params.get("roe_min", DEFAULT_PARAMS["roe_min"])
        if roe is None or roe < roe_min:
            return None

        # 规则 5：自由现金流
        if params.get("fcf_positive", DEFAULT_PARAMS["fcf_positive"]):
            if fcf is None or fcf <= 0:
                return None

        # 规则 6：债务管控
        de_max = params.get("de_max", DEFAULT_PARAMS["de_max"])
        if debt_to_equity is not None and debt_to_equity > de_max:
            return None

        # 计算 52 周价格位置百分位 (0%=52周最低, 100%=52周最高)
        price_position = None
        if current_price and week52_high and week52_low and week52_high > week52_low:
            price_position = round((current_price - week52_low) / (week52_high - week52_low) * 100, 1)

        return {
            "symbol": symbol,
            "name": name,
            "sector": sector,
            "market_cap_b": round(market_cap / 1e9, 2),
            "peg": round(peg, 2),
            "forward_pe": round(forward_pe, 2) if forward_pe else None,
            "trailing_pe": round(trailing_pe, 2) if trailing_pe else None,
            "roe_pct": round(roe * 100, 2),
            "fcf_m": round(fcf / 1e6, 2) if fcf else None,
            "de_pct": round(debt_to_equity, 2) if debt_to_equity is not None else None,
            "dividend_yield_pct": round(dividend_yield * 100, 2) if dividend_yield else None,
            "revenue_growth_pct": round(revenue_growth * 100, 2) if revenue_growth else None,
            "profit_margin_pct": round(profit_margin * 100, 2) if profit_margin else None,
            "current_price": round(current_price, 2) if current_price else None,
            "week52_high": round(week52_high, 2) if week52_high else None,
            "week52_low": round(week52_low, 2) if week52_low else None,
            "price_position_pct": price_position,
        }
    except Exception as e:
        logger.debug(f"Screener: {symbol} 分析跳过: {e}")
        return None


def run_screener(params: Optional[dict] = None) -> dict:
    """
    执行选股筛选。

    Args:
        params: 筛选参数（可选），未提供则使用默认策略。

    Returns:
        {
            "success": True/False,
            "total_scanned": int,
            "results": [...],
            "params_used": {...},
            "error": str (仅失败时)
        }
    """
    if params is None:
        params = {}

    # 合并默认参数
    effective_params = {**DEFAULT_PARAMS, **params}

    # 获取 S&P 500 列表
    tickers = get_sp500_tickers()
    if not tickers:
        return {
            "success": False,
            "error": "无法获取 S&P 500 成分股列表",
            "total_scanned": 0,
            "results": [],
            "params_used": effective_params,
        }

    max_workers = effective_params.get("max_workers", 20)
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_analyze_single_ticker, ticker, effective_params): ticker
            for ticker in tickers
        }
        for future in concurrent.futures.as_completed(futures):
            try:
                res = future.result(timeout=15)
                if res:
                    results.append(res)
            except Exception:
                pass

    # 按 PEG 升序排列
    results.sort(key=lambda x: x["peg"])

    logger.info(f"Screener 完成: 扫描 {len(tickers)} 只，命中 {len(results)} 只")

    return {
        "success": True,
        "total_scanned": len(tickers),
        "results": results,
        "params_used": {
            "min_market_cap": effective_params["min_market_cap"],
            "sectors": effective_params["sectors"],
            "peg_range": f"{effective_params.get('peg_min', 0)}-{effective_params['peg_max']}",
            "roe_min": effective_params["roe_min"],
            "fcf_positive": effective_params["fcf_positive"],
            "de_max": effective_params["de_max"],
        },
    }
