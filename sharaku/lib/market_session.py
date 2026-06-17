"""
美股交易时段判断 & 涨跌幅排行（动态获取）
"""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, List

import pytz
import requests
from loguru import logger

_movers_executor = ThreadPoolExecutor(max_workers=3)

# 美股交易时段（美东时间）
US_EASTERN = pytz.timezone("US/Eastern")


def get_us_market_session() -> Dict:
    """
    判断当前美股所处的交易时段
    返回: {"session": "pre_market"|"regular"|"after_hours"|"overnight"|"closed",
           "label_zh": "...", "label_en": "...",
           "is_trading": bool, "eastern_time": "HH:MM"}
    """
    now_et = datetime.now(US_EASTERN)
    hour, minute = now_et.hour, now_et.minute
    time_val = hour * 60 + minute
    weekday = now_et.weekday()  # 0=Mon, 6=Sun

    # 周末
    if weekday >= 5:
        return {
            "session": "closed",
            "label_zh": "休市（周末）",
            "label_en": "Closed (Weekend)",
            "is_trading": False,
            "eastern_time": now_et.strftime("%H:%M"),
            "date": now_et.strftime("%Y-%m-%d"),
        }

    if 4 * 60 <= time_val < 9 * 60 + 30:
        session = "pre_market"
        label_zh = "盘前交易"
        label_en = "Pre-Market"
        is_trading = True
    elif 9 * 60 + 30 <= time_val < 16 * 60:
        session = "regular"
        label_zh = "盘中交易"
        label_en = "Regular Hours"
        is_trading = True
    elif 16 * 60 <= time_val < 20 * 60:
        session = "after_hours"
        label_zh = "盘后交易"
        label_en = "After-Hours"
        is_trading = True
    else:
        session = "overnight"
        label_zh = "夜盘（休市）"
        label_en = "Overnight (Closed)"
        is_trading = False

    return {
        "session": session,
        "label_zh": label_zh,
        "label_en": label_en,
        "is_trading": is_trading,
        "eastern_time": now_et.strftime("%H:%M"),
        "date": now_et.strftime("%Y-%m-%d"),
    }


def _fetch_screener_tickers(scr_id: str, count: int = 25) -> List[str]:
    """
    通过 Yahoo Finance screener API 获取榜单股票代码列表。
    scr_id: day_gainers / day_losers / most_actives
    """
    try:
        resp = requests.get(
            "https://query2.finance.yahoo.com/v1/finance/screener/predefined/saved",
            params={"scrIds": scr_id, "count": count},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        quotes = (
            data.get("finance", {})
            .get("result", [{}])[0]
            .get("quotes", [])
        )
        return [q["symbol"] for q in quotes if q.get("symbol")]
    except Exception as e:
        logger.warning(f"Screener {scr_id} failed: {e}")
        return []


def _fetch_quotes_batch(tickers: List[str]) -> List[Dict]:
    """
    通过 yfinance 内部认证 session 批量获取实时行情（含盘前/盘后最新价格）。
    如果 yfinance 方式失败，返回空列表。
    """
    if not tickers:
        return []
    try:
        import yfinance as yf
        from yfinance.data import YfData

        yfdata = YfData(session=None)
        symbols = ",".join(tickers)
        params = {"symbols": symbols}
        url = "https://query2.finance.yahoo.com/v7/finance/quote"
        response = yfdata.get(url=url, params=params)
        data = response.json()
        return data.get("quoteResponse", {}).get("result", [])
    except Exception as e:
        logger.debug(f"yfinance authenticated quote failed: {e}")
        return []



def _quote_to_mover(q: Dict, session: str) -> Dict:
    """将 Yahoo Finance quote 数据转为统一的 mover 格式"""
    ticker = q.get("symbol", "")
    name = q.get("shortName") or q.get("longName") or ticker
    regular_price = q.get("regularMarketPrice", 0)
    prev_close = q.get("regularMarketPreviousClose", 0)

    if session == "pre_market":
        price = q.get("preMarketPrice") or regular_price
        change = q.get("preMarketChange") or (price - prev_close if prev_close else 0)
        change_pct = q.get("preMarketChangePercent") or (change / prev_close * 100 if prev_close else 0)
        ref_label_zh = "盘前价 vs 前收盘"
        ref_label_en = "Pre-Market vs Prev Close"
    elif session == "after_hours":
        post_price = q.get("postMarketPrice")
        if post_price:
            price = post_price
            change = q.get("postMarketChange") or (price - regular_price if regular_price else 0)
            change_pct = q.get("postMarketChangePercent") or (change / regular_price * 100 if regular_price else 0)
            ref_label_zh = "盘后价 vs 收盘价"
            ref_label_en = "After-Hours vs Close"
        else:
            price = regular_price
            change = q.get("regularMarketChange", 0)
            change_pct = q.get("regularMarketChangePercent", 0)
            ref_label_zh = "收盘价 vs 前收盘"
            ref_label_en = "Close vs Prev Close"
    elif session in ("overnight", "closed"):
        # 夜盘/休市：Yahoo 无夜盘数据，展示盘后最终价 vs 收盘价
        post_price = q.get("postMarketPrice")
        if post_price:
            price = post_price
            change = q.get("postMarketChange") or (price - regular_price if regular_price else 0)
            change_pct = q.get("postMarketChangePercent") or (change / regular_price * 100 if regular_price else 0)
            ref_label_zh = "盘后收盘价 vs 日内收盘价"
            ref_label_en = "AH Close vs Regular Close"
        else:
            price = regular_price
            change = q.get("regularMarketChange", 0)
            change_pct = q.get("regularMarketChangePercent", 0)
            ref_label_zh = "收盘价 vs 前收盘"
            ref_label_en = "Close vs Prev Close"
    else:
        # regular session
        price = regular_price
        change = q.get("regularMarketChange", 0)
        change_pct = q.get("regularMarketChangePercent", 0)
        ref_label_zh = "当前价 vs 前收盘"
        ref_label_en = "Current vs Prev Close"

    return {
        "ticker": ticker,
        "name": name,
        "price": float(price) if price else 0,
        "change": float(change) if change else 0,
        "change_pct": float(change_pct) if change_pct else 0,
        "prev_close": float(prev_close) if prev_close else 0,
        "volume": q.get("regularMarketVolume", 0),
        "market_cap": q.get("marketCap", 0),
        "ref_label_zh": ref_label_zh,
        "ref_label_en": ref_label_en,
    }


def _get_quotes_for_category(scr_id: str, count: int, session: str) -> List[Dict]:
    """
    获取某个分类的实时行情：
    1. 先从 screener 获取股票列表
    2. 用 yfinance 认证 session 获取实时价格（含盘后最新）
    3. 如果 yfinance 失败则回退到 screener 自带的快照数据
    """
    tickers = _fetch_screener_tickers(scr_id, count)
    if not tickers:
        return []

    # 尝试通过 yfinance 认证获取实时数据
    quotes = _fetch_quotes_batch(tickers)
    if quotes:
        return [_quote_to_mover(q, session) for q in quotes]

    # fallback: 直接用 screener 返回的快照数据（可能有几分钟延迟）
    logger.info(f"Using screener snapshot for {scr_id}")
    try:
        resp = requests.get(
            "https://query2.finance.yahoo.com/v1/finance/screener/predefined/saved",
            params={"scrIds": scr_id, "count": count},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        quotes = (
            data.get("finance", {})
            .get("result", [{}])[0]
            .get("quotes", [])
        )
        return [_quote_to_mover(q, session) for q in quotes]
    except Exception as e:
        logger.warning(f"Screener fallback for {scr_id} also failed: {e}")
        return []


# Simple in-memory cache for movers (avoid repeated Yahoo scrapes)
_movers_cache: Dict[str, dict] = {}
_MOVERS_CACHE_TTL = 60  # seconds


def fetch_us_market_movers(category: str = "all", count: int = 30) -> Dict:
    """
    动态获取美股涨跌幅排行，无需预设列表。
    优先使用 yfinance 认证接口获取实时价格，screener 作为 fallback。
    三个分类并行获取以减少等待时间。
    category: "gainers" | "losers" | "actives" | "all"
    返回: {"gainers": [...], "losers": [...], "actives": [...]}
    """
    cache_key = f"{category}:{count}"
    cached = _movers_cache.get(cache_key)
    if cached and time.time() - cached["ts"] < _MOVERS_CACHE_TTL:
        return cached["data"]

    session_info = get_us_market_session()
    session = session_info["session"]

    categories_to_fetch = []
    if category in ("gainers", "all"):
        categories_to_fetch.append(("gainers", "day_gainers"))
    if category in ("losers", "all"):
        categories_to_fetch.append(("losers", "day_losers"))
    if category in ("actives", "all"):
        categories_to_fetch.append(("actives", "most_actives"))

    # Fetch all categories in parallel
    futures = {
        _movers_executor.submit(_get_quotes_for_category, scr_id, count, session): name
        for name, scr_id in categories_to_fetch
    }

    result = {}
    for future in futures:
        name = futures[future]
        try:
            items = future.result(timeout=15)
        except Exception as e:
            logger.warning(f"Movers {name} failed: {e}")
            items = []

        if name == "gainers":
            items.sort(key=lambda x: x["change_pct"], reverse=True)
        elif name == "losers":
            items.sort(key=lambda x: x["change_pct"])
        elif name == "actives":
            items.sort(key=lambda x: x["volume"] or 0, reverse=True)
        result[name] = items

    _movers_cache[cache_key] = {"data": result, "ts": time.time()}
    return result


def fetch_us_market_movers_by_tickers(tickers: List[str]) -> List[Dict]:
    """
    按指定 tickers 批量获取行情（用于用户自选列表场景）。
    """
    if not tickers:
        return []

    session_info = get_us_market_session()
    session = session_info["session"]

    symbols = ",".join(tickers)
    try:
        resp = requests.get(
            "https://query2.finance.yahoo.com/v7/finance/quote",
            params={"symbols": symbols},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        resp.raise_for_status()
        quotes = resp.json().get("quoteResponse", {}).get("result", [])
    except Exception as e:
        logger.error(f"Quote API failed: {e}")
        return []

    results = [_quote_to_mover(q, session) for q in quotes]
    results.sort(key=lambda x: x["change_pct"], reverse=True)
    return results
