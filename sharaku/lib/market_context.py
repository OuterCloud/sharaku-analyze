"""
市场上下文采集模块 - 为投资顾问汇总一只标的的多维度事实数据

汇总内容：
- 价格与区间位置（52周高低、距高低点幅度、成交量）
- 技术指标（复用 TechnicalAnalyzer 的 7 大指标与 K 线形态）
- 支撑/阻力位（近期波段高低点 + 布林带 + 均线）
- 统计预测（GBM / 蒙特卡洛分位数）
- 基本面（估值、盈利能力、成长性、财务健康度）
- 分析师目标价与评级
- 期权链概况（近月到期、IV、可选行权价及权利金）
- Wheel 策略机器决策（复用 wheel_monitor）

所有数据均为"事实层"，不做主观判断，判断交由 LLM 结合知识库完成。
"""

import warnings
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf
from loguru import logger

from sharaku.lib.data_utils import DataUtils
from sharaku.lib.gbm_predictor import GBMPredictor
from sharaku.lib.monte_carlo_predictor import MonteCarloPredictor
from sharaku.lib.technical_analyzer import TechnicalAnalyzer
from sharaku.lib.wheel_monitor import analyze_wheel_strategy

# 顾问模块用较少的模拟次数，保证响应速度
ADVISOR_N_SIMULATIONS = 20000

# 期权链最多分析的到期日数量
MAX_OPTION_EXPIRIES = 4

# 每个到期日展示的候选行权价数量（价外方向）
OPTION_STRIKES_PER_SIDE = 6


def _safe_float(val: Any) -> Optional[float]:
    """安全转 float，NaN/None/异常一律返回 None"""
    if val is None:
        return None
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    if np.isnan(f) or np.isinf(f):
        return None
    return f


def _pct(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    """计算百分比变化，分母为 0 或缺失时返回 None"""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return (numerator - denominator) / denominator * 100


def _is_a_share(ticker: str) -> bool:
    return ticker.endswith(".SS") or ticker.endswith(".SZ")


# ==================== 各维度采集 ====================


def collect_price_snapshot(ticker: str, hist: pd.DataFrame, info: dict) -> dict:
    """价格快照与区间位置"""
    close = hist["Close"].dropna()
    current = _safe_float(close.iloc[-1]) if len(close) else None

    week52_high = _safe_float(info.get("fiftyTwoWeekHigh"))
    week52_low = _safe_float(info.get("fiftyTwoWeekLow"))
    # info 缺失时用历史数据兜底
    if week52_high is None and len(close):
        week52_high = _safe_float(close.tail(252).max())
    if week52_low is None and len(close):
        week52_low = _safe_float(close.tail(252).min())

    range_position = None
    if current is not None and week52_high and week52_low and week52_high > week52_low:
        range_position = (current - week52_low) / (week52_high - week52_low) * 100

    def change_over(days: int) -> Optional[float]:
        if len(close) <= days:
            return None
        return _pct(current, _safe_float(close.iloc[-days - 1]))

    volume = _safe_float(hist["Volume"].iloc[-1]) if "Volume" in hist and len(hist) else None
    avg_volume = _safe_float(info.get("averageVolume"))

    return {
        "current_price": current,
        "currency": info.get("currency"),
        "week52_high": week52_high,
        "week52_low": week52_low,
        "pct_from_52w_high": _pct(current, week52_high),
        "pct_above_52w_low": _pct(current, week52_low),
        "range_position_pct": range_position,
        "change_1d_pct": change_over(1),
        "change_5d_pct": change_over(5),
        "change_20d_pct": change_over(20),
        "change_60d_pct": change_over(60),
        "volume": volume,
        "avg_volume": avg_volume,
        "volume_ratio": (volume / avg_volume) if volume and avg_volume else None,
    }


def collect_support_resistance(hist: pd.DataFrame, technical: Optional[dict]) -> dict:
    """支撑/阻力位：近期波段高低点 + 技术指标位"""
    close = hist["Close"].dropna()
    high = hist["High"].dropna()
    low = hist["Low"].dropna()

    def window_low(days: int) -> Optional[float]:
        return _safe_float(low.tail(days).min()) if len(low) else None

    def window_high(days: int) -> Optional[float]:
        return _safe_float(high.tail(days).max()) if len(high) else None

    result = {
        "recent_low_20d": window_low(20),
        "recent_high_20d": window_high(20),
        "recent_low_60d": window_low(60),
        "recent_high_60d": window_high(60),
        "recent_low_120d": window_low(120),
        "recent_high_120d": window_high(120),
    }

    if technical and technical.get("success"):
        iv = technical.get("indicator_values", {})
        result.update({
            "ma20": _safe_float(iv.get("ma20")),
            "ma60": _safe_float(iv.get("ma60")),
            "bb_lower": _safe_float(iv.get("bb_lower")),
            "bb_middle": _safe_float(iv.get("bb_middle")),
            "bb_upper": _safe_float(iv.get("bb_upper")),
        })

    # 年内成交量加权均价（近似筹码成本）
    if "Volume" in hist:
        recent = hist.tail(120).dropna(subset=["Close", "Volume"])
        vol_sum = _safe_float(recent["Volume"].sum())
        if vol_sum and vol_sum > 0:
            vwap = float((recent["Close"] * recent["Volume"]).sum() / vol_sum)
            result["vwap_120d"] = vwap

    return result


def collect_fundamentals(info: dict) -> dict:
    """基本面：估值、盈利能力、成长性、财务健康度"""
    dividend_yield = _safe_float(info.get("dividendYield"))
    return {
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "market_cap": _safe_float(info.get("marketCap")),
        # 估值
        "trailing_pe": _safe_float(info.get("trailingPE")),
        "forward_pe": _safe_float(info.get("forwardPE")),
        "peg_ratio": _safe_float(info.get("pegRatio")),
        "price_to_book": _safe_float(info.get("priceToBook")),
        "ev_to_ebitda": _safe_float(info.get("enterpriseToEbitda")),
        # 盈利能力
        "profit_margin": _safe_float(info.get("profitMargins")),
        "return_on_equity": _safe_float(info.get("returnOnEquity")),
        "trailing_eps": _safe_float(info.get("trailingEps")),
        "forward_eps": _safe_float(info.get("forwardEps")),
        # 成长性
        "revenue_growth": _safe_float(info.get("revenueGrowth")),
        "earnings_growth": _safe_float(info.get("earningsGrowth")),
        # 财务健康度
        "debt_to_equity": _safe_float(info.get("debtToEquity")),
        "current_ratio": _safe_float(info.get("currentRatio")),
        "free_cashflow": _safe_float(info.get("freeCashflow")),
        "total_cash_per_share": _safe_float(info.get("totalCashPerShare")),
        "book_value_per_share": _safe_float(info.get("bookValue")),
        # 其他
        "beta": _safe_float(info.get("beta")),
        "dividend_yield_pct": dividend_yield,
    }


def collect_analyst_view(info: dict, current_price: Optional[float]) -> dict:
    """分析师目标价与评级"""
    target_mean = _safe_float(info.get("targetMeanPrice"))
    return {
        "recommendation": info.get("recommendationKey"),
        "analyst_count": _safe_float(info.get("numberOfAnalystOpinions")),
        "target_mean": target_mean,
        "target_high": _safe_float(info.get("targetHighPrice")),
        "target_low": _safe_float(info.get("targetLowPrice")),
        "target_upside_pct": _pct(target_mean, current_price),
    }


def collect_statistical_forecast(ticker: str, horizon_days: int = 30) -> Optional[dict]:
    """GBM / 蒙特卡洛统计预测（分位数区间）"""
    try:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
        data_utils = DataUtils()
        prepared = data_utils.prepare_model_data(ticker, start_date, end_date)

        target_date = (datetime.now() + timedelta(days=horizon_days)).strftime("%Y-%m-%d")

        gbm = GBMPredictor(ticker)
        gbm.fit(prepared["raw_data"])
        gbm_pred = gbm.predict(target_date, n_simulations=ADVISOR_N_SIMULATIONS)
        gbm_risk = gbm.analyze_risk(gbm_pred)

        mc = MonteCarloPredictor(ticker)
        mc.fit(prepared["raw_data"])
        mc_pred = mc.predict(days=horizon_days, n_paths=ADVISOR_N_SIMULATIONS)
        mc_risk = mc.analyze_risk(mc_pred)

        stats = prepared["statistics"]
        return {
            "horizon_days": horizon_days,
            "target_date": target_date,
            "annual_volatility_pct": _safe_float(stats.get("volatility_annual", 0) * 100),
            "annual_drift_pct": _safe_float(stats.get("mean_return_annual", 0) * 100),
            "gbm": {
                "mean_price": _safe_float(gbm_risk.get("mean_price")),
                "median_price": _safe_float(gbm_risk.get("median_price")),
                "percentile_5": _safe_float(gbm_risk.get("price_percentile_5")),
                "percentile_95": _safe_float(gbm_risk.get("price_percentile_95")),
                "expected_return_pct": _safe_float(gbm_risk.get("mean_return")),
            },
            "monte_carlo": {
                "mean_price": _safe_float(mc_risk.get("mean_price")),
                "median_price": _safe_float(mc_risk.get("median_price")),
                "percentile_5": _safe_float(mc_risk.get("price_percentile_5")),
                "percentile_95": _safe_float(mc_risk.get("price_percentile_95")),
                "expected_return_pct": _safe_float(mc_risk.get("mean_return")),
                "var_95": _safe_float(mc_risk.get("var_95")),
                "cvar_95": _safe_float(mc_risk.get("cvar_95")),
            },
        }
    except Exception as e:
        logger.debug(f"统计预测采集失败 {ticker}: {e}")
        return None


def collect_option_chain(ticker: str, current_price: Optional[float]) -> Optional[dict]:
    """期权链概况：近月到期日、IV、价外可选行权价与权利金"""
    if _is_a_share(ticker) or current_price is None:
        return None

    try:
        stock = yf.Ticker(ticker)
        expiries = stock.options
        if not expiries:
            return None
    except Exception as e:
        logger.debug(f"期权链获取失败 {ticker}: {e}")
        return None

    def summarize_side(df: pd.DataFrame, side: str) -> List[dict]:
        """提取价外方向的候选行权价"""
        if df is None or df.empty:
            return []
        cols = ["strike", "lastPrice", "bid", "ask", "impliedVolatility", "openInterest", "volume"]
        available = [c for c in cols if c in df.columns]
        sub = df[available].dropna(subset=["strike"]).copy()

        if side == "put":
            # Sell Put 关注价外（strike < 现价），按接近现价排序
            sub = sub[sub["strike"] < current_price].sort_values("strike", ascending=False)
        else:
            # Covered Call 关注价外（strike > 现价）
            sub = sub[sub["strike"] > current_price].sort_values("strike", ascending=True)

        sub = sub.head(OPTION_STRIKES_PER_SIDE)

        rows = []
        for _, r in sub.iterrows():
            strike = _safe_float(r.get("strike"))
            bid = _safe_float(r.get("bid"))
            ask = _safe_float(r.get("ask"))
            mid = (bid + ask) / 2 if bid is not None and ask is not None and (bid or ask) else _safe_float(r.get("lastPrice"))
            rows.append({
                "strike": strike,
                "distance_pct": _pct(strike, current_price),
                "bid": bid,
                "ask": ask,
                "mid_premium": mid,
                "premium_yield_pct": (mid / strike * 100) if mid and strike else None,
                "implied_volatility_pct": (
                    _safe_float(r.get("impliedVolatility")) * 100
                    if _safe_float(r.get("impliedVolatility")) is not None
                    else None
                ),
                "open_interest": _safe_float(r.get("openInterest")),
                "volume": _safe_float(r.get("volume")),
            })
        return rows

    today = datetime.now().date()

    # 过滤掉已过期/当日到期的合约（流动性与定价均不可用）
    valid_expiries = []
    for exp in expiries:
        try:
            if (datetime.strptime(exp, "%Y-%m-%d").date() - today).days >= 1:
                valid_expiries.append(exp)
        except ValueError:
            continue

    if not valid_expiries:
        return None

    expiry_blocks = []
    atm_ivs: List[float] = []

    for exp in valid_expiries[:MAX_OPTION_EXPIRIES]:
        try:
            chain = stock.option_chain(exp)
        except Exception:
            continue

        try:
            days_to_exp = (datetime.strptime(exp, "%Y-%m-%d").date() - today).days
        except ValueError:
            days_to_exp = None

        puts = summarize_side(chain.puts, "put")
        calls = summarize_side(chain.calls, "call")

        # 取最接近现价的合约 IV 作为该到期日的 ATM IV
        for rows in (puts, calls):
            if rows and rows[0].get("implied_volatility_pct") is not None:
                atm_ivs.append(rows[0]["implied_volatility_pct"])

        expiry_blocks.append({
            "expiry": exp,
            "days_to_expiry": days_to_exp,
            "puts_otm": puts,
            "calls_otm": calls,
        })

    if not expiry_blocks:
        return None

    return {
        "available_expiries": valid_expiries[:12],
        "atm_implied_volatility_pct": float(np.mean(atm_ivs)) if atm_ivs else None,
        "expiries": expiry_blocks,
    }


def collect_earnings_calendar(ticker: str) -> Optional[dict]:
    """财报日期（临近财报是重要的期权风险因素）"""
    try:
        stock = yf.Ticker(ticker)
        cal = stock.calendar
        if not cal:
            return None
        earnings_dates = cal.get("Earnings Date") if isinstance(cal, dict) else None
        if not earnings_dates:
            return None
        if not isinstance(earnings_dates, list):
            earnings_dates = [earnings_dates]
        formatted = [str(d) for d in earnings_dates if d]
        if not formatted:
            return None

        days_until = None
        try:
            first = pd.to_datetime(formatted[0]).date()
            days_until = (first - datetime.now().date()).days
        except (ValueError, TypeError):
            pass

        return {"next_earnings_dates": formatted, "days_until_earnings": days_until}
    except Exception as e:
        logger.debug(f"财报日期获取失败 {ticker}: {e}")
        return None


# ==================== 汇总入口 ====================


def build_market_context(
    ticker: str,
    cost_basis: float = 0,
    lang: str = "zh",
    horizon_days: int = 30,
) -> dict:
    """
    汇总一只标的的全维度事实数据。

    Args:
        ticker: 股票代码
        cost_basis: 持仓成本价（0 表示未持仓）
        lang: 技术分析/Wheel 文案语言
        horizon_days: 统计预测的时间跨度

    Returns:
        dict: 结构化上下文；失败字段为 None，不抛异常
    """
    ticker = ticker.upper()
    logger.info(f"采集市场上下文: {ticker}")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        stock = yf.Ticker(ticker)
        try:
            info = stock.info or {}
        except Exception as e:
            logger.warning(f"基本面信息获取失败 {ticker}: {e}")
            info = {}

        try:
            hist = stock.history(period="1y")
        except Exception as e:
            logger.warning(f"历史数据获取失败 {ticker}: {e}")
            hist = pd.DataFrame()

    if hist.empty:
        return {"success": False, "error": f"未找到 {ticker} 的历史数据", "ticker": ticker}

    # 技术分析
    technical = None
    try:
        technical = TechnicalAnalyzer(ticker, lang=lang).analyze()
    except Exception as e:
        logger.debug(f"技术分析失败 {ticker}: {e}")

    price = collect_price_snapshot(ticker, hist, info)
    current_price = price.get("current_price")

    # Wheel 策略（A股/无期权链会返回 success=False，属预期情况）
    wheel = None
    try:
        wheel = analyze_wheel_strategy(ticker, cost_basis, lang=lang)
    except Exception as e:
        logger.debug(f"Wheel 分析失败 {ticker}: {e}")

    return {
        "success": True,
        "ticker": ticker,
        "name": info.get("shortName") or info.get("longName") or ticker,
        "as_of": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "position": {
            "cost_basis": cost_basis if cost_basis > 0 else None,
            "unrealized_pnl_pct": _pct(current_price, cost_basis) if cost_basis > 0 else None,
        },
        "price": price,
        "levels": collect_support_resistance(hist, technical),
        "technical": technical if technical and technical.get("success") else None,
        "fundamentals": collect_fundamentals(info),
        "analyst": collect_analyst_view(info, current_price),
        "forecast": collect_statistical_forecast(ticker, horizon_days),
        "options": collect_option_chain(ticker, current_price),
        "earnings": collect_earnings_calendar(ticker),
        "wheel": wheel if wheel and wheel.get("success") else None,
        "wheel_unavailable_reason": (
            wheel.get("error") if wheel and not wheel.get("success") else None
        ),
    }


# ==================== 渲染为提示词文本 ====================


def _fmt(val: Optional[float], suffix: str = "", digits: int = 2) -> str:
    """格式化数值，缺失显示 N/A"""
    if val is None:
        return "N/A"
    return f"{val:,.{digits}f}{suffix}"


def _fmt_large(val: Optional[float]) -> str:
    """格式化大额数字（市值、现金流）"""
    if val is None:
        return "N/A"
    for unit, div in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(val) >= div:
            return f"{val / div:,.2f}{unit}"
    return f"{val:,.2f}"


def render_market_context(ctx: dict) -> str:
    """把结构化上下文渲染为紧凑的文本块，供 LLM 阅读"""
    if not ctx.get("success"):
        return f"数据采集失败：{ctx.get('error', '未知错误')}"

    lines: List[str] = []
    add = lines.append

    add(f"标的: {ctx['ticker']} ({ctx.get('name')})")
    add(f"数据时间: {ctx.get('as_of')}")

    pos = ctx.get("position") or {}
    if pos.get("cost_basis"):
        add(f"当前持仓成本: {_fmt(pos['cost_basis'])}，浮动盈亏: {_fmt(pos.get('unrealized_pnl_pct'), '%')}")
    else:
        add("当前持仓: 未持仓（空仓待入场）")

    # --- 价格 ---
    p = ctx.get("price") or {}
    add("\n【价格与区间位置】")
    add(f"现价: {_fmt(p.get('current_price'))} {p.get('currency') or ''}")
    add(f"52周区间: {_fmt(p.get('week52_low'))} ~ {_fmt(p.get('week52_high'))}"
        f"（当前处于区间 {_fmt(p.get('range_position_pct'), '%', 1)} 位置）")
    add(f"距52周高点: {_fmt(p.get('pct_from_52w_high'), '%')}，"
        f"高于52周低点: {_fmt(p.get('pct_above_52w_low'), '%')}")
    add(f"涨跌幅: 1日 {_fmt(p.get('change_1d_pct'), '%')} | 5日 {_fmt(p.get('change_5d_pct'), '%')} | "
        f"20日 {_fmt(p.get('change_20d_pct'), '%')} | 60日 {_fmt(p.get('change_60d_pct'), '%')}")
    add(f"成交量: {_fmt_large(p.get('volume'))}（相对均量 {_fmt(p.get('volume_ratio'), 'x')}）")

    # --- 关键价位 ---
    lv = ctx.get("levels") or {}
    add("\n【关键价位】")
    add(f"20日高/低: {_fmt(lv.get('recent_high_20d'))} / {_fmt(lv.get('recent_low_20d'))}")
    add(f"60日高/低: {_fmt(lv.get('recent_high_60d'))} / {_fmt(lv.get('recent_low_60d'))}")
    add(f"120日高/低: {_fmt(lv.get('recent_high_120d'))} / {_fmt(lv.get('recent_low_120d'))}")
    if lv.get("ma20") is not None:
        add(f"均线: MA20 {_fmt(lv.get('ma20'))} | MA60 {_fmt(lv.get('ma60'))}")
    if lv.get("bb_lower") is not None:
        add(f"布林带: 下轨 {_fmt(lv.get('bb_lower'))} | 中轨 {_fmt(lv.get('bb_middle'))} | 上轨 {_fmt(lv.get('bb_upper'))}")
    if lv.get("vwap_120d") is not None:
        add(f"120日成交量加权均价(近似筹码成本): {_fmt(lv.get('vwap_120d'))}")

    # --- 技术分析 ---
    tech = ctx.get("technical")
    add("\n【技术分析】")
    if tech:
        add(f"综合评分: {_fmt(tech.get('score'), '', 1)}/100（>65偏多, <35偏空）")
        signals = tech.get("signals") or {}
        add("各指标信号: " + " | ".join(f"{k}={v}" for k, v in signals.items()))
        iv = tech.get("indicator_values") or {}
        add(f"RSI(14): {_fmt(iv.get('rsi'), '', 1)} | KDJ: K={_fmt(iv.get('k'), '', 1)} D={_fmt(iv.get('d'), '', 1)}")
        add(f"MACD: {_fmt(iv.get('macd'), '', 3)} | Signal: {_fmt(iv.get('macd_signal'), '', 3)} | 柱: {_fmt(iv.get('macd_hist'), '', 3)}")
        add(f"ADX: {_fmt(iv.get('adx'), '', 1)} | DI+: {_fmt(iv.get('di_plus'), '', 1)} | DI-: {_fmt(iv.get('di_minus'), '', 1)}")
        pattern = tech.get("candlestick_pattern")
        if pattern:
            add(f"K线形态: {pattern.get('name')} — {pattern.get('description')}")
        if tech.get("stop_loss") is not None:
            add(f"机器建议止损/目标: {_fmt(tech.get('stop_loss'))} / {_fmt(tech.get('target'))}")
    else:
        add("技术分析数据不可用")

    # --- 统计预测 ---
    fc = ctx.get("forecast")
    add("\n【统计预测】")
    if fc:
        add(f"预测跨度: {fc.get('horizon_days')} 天（至 {fc.get('target_date')}）")
        add(f"年化波动率: {_fmt(fc.get('annual_volatility_pct'), '%')} | 年化漂移: {_fmt(fc.get('annual_drift_pct'), '%')}")
        g = fc.get("gbm") or {}
        add(f"GBM: 均值 {_fmt(g.get('mean_price'))} | 中位数 {_fmt(g.get('median_price'))} | "
            f"90%区间 [{_fmt(g.get('percentile_5'))}, {_fmt(g.get('percentile_95'))}] | "
            f"期望收益 {_fmt(g.get('expected_return_pct'), '%')}")
        m = fc.get("monte_carlo") or {}
        add(f"蒙特卡洛: 均值 {_fmt(m.get('mean_price'))} | 中位数 {_fmt(m.get('median_price'))} | "
            f"90%区间 [{_fmt(m.get('percentile_5'))}, {_fmt(m.get('percentile_95'))}] | "
            f"期望收益 {_fmt(m.get('expected_return_pct'), '%')}")
        if m.get("var_95") is not None:
            add(f"风险度量: VaR(95%) {_fmt(m.get('var_95'), '%')} | CVaR(95%) {_fmt(m.get('cvar_95'), '%')}")
    else:
        add("统计预测不可用")

    # --- 基本面 ---
    f = ctx.get("fundamentals") or {}
    add("\n【基本面】")
    add(f"行业: {f.get('sector') or 'N/A'} / {f.get('industry') or 'N/A'} | 市值: {_fmt_large(f.get('market_cap'))}")
    add(f"估值: TTM PE {_fmt(f.get('trailing_pe'))} | 前瞻 PE {_fmt(f.get('forward_pe'))} | "
        f"PEG {_fmt(f.get('peg_ratio'))} | PB {_fmt(f.get('price_to_book'))} | EV/EBITDA {_fmt(f.get('ev_to_ebitda'))}")
    add(f"盈利: 净利率 {_fmt((f.get('profit_margin') or 0) * 100 if f.get('profit_margin') is not None else None, '%')} | "
        f"ROE {_fmt((f.get('return_on_equity') or 0) * 100 if f.get('return_on_equity') is not None else None, '%')} | "
        f"TTM EPS {_fmt(f.get('trailing_eps'))} | 前瞻 EPS {_fmt(f.get('forward_eps'))}")
    add(f"成长: 营收增速 {_fmt((f.get('revenue_growth') or 0) * 100 if f.get('revenue_growth') is not None else None, '%')} | "
        f"盈利增速 {_fmt((f.get('earnings_growth') or 0) * 100 if f.get('earnings_growth') is not None else None, '%')}")
    add(f"财务: 负债权益比 {_fmt(f.get('debt_to_equity'))} | 流动比率 {_fmt(f.get('current_ratio'))} | "
        f"自由现金流 {_fmt_large(f.get('free_cashflow'))} | 每股现金 {_fmt(f.get('total_cash_per_share'))}")
    add(f"Beta: {_fmt(f.get('beta'))} | 股息率: {_fmt(f.get('dividend_yield_pct'), '%')}")

    # --- 分析师 ---
    a = ctx.get("analyst") or {}
    add("\n【分析师观点】")
    add(f"评级: {a.get('recommendation') or 'N/A'}（{_fmt(a.get('analyst_count'), '', 0)} 位分析师）")
    add(f"目标价: 均值 {_fmt(a.get('target_mean'))} | 区间 [{_fmt(a.get('target_low'))}, {_fmt(a.get('target_high'))}] | "
        f"相对现价空间 {_fmt(a.get('target_upside_pct'), '%')}")

    # --- 财报 ---
    e = ctx.get("earnings")
    if e:
        add("\n【财报日历】")
        add(f"下次财报: {', '.join(e.get('next_earnings_dates', []))}"
            + (f"（距今 {e['days_until_earnings']} 天）" if e.get("days_until_earnings") is not None else ""))

    # --- 期权链 ---
    opt = ctx.get("options")
    add("\n【期权链】")
    if opt:
        add(f"ATM 隐含波动率: {_fmt(opt.get('atm_implied_volatility_pct'), '%')}")
        add(f"可选到期日: {', '.join(opt.get('available_expiries', [])[:8])}")
        for blk in opt.get("expiries", []):
            add(f"\n到期 {blk['expiry']}（{blk.get('days_to_expiry')} 天）:")
            if blk.get("puts_otm"):
                add("  价外 PUT（Sell Put 候选）:")
                for r in blk["puts_otm"]:
                    add(f"    行权价 {_fmt(r['strike'])}（{_fmt(r['distance_pct'], '%', 1)}）"
                        f" 权利金中值 {_fmt(r['mid_premium'])}"
                        f" 收益率 {_fmt(r['premium_yield_pct'], '%')}"
                        f" IV {_fmt(r['implied_volatility_pct'], '%', 1)}"
                        f" 未平仓 {_fmt(r['open_interest'], '', 0)}")
            if blk.get("calls_otm"):
                add("  价外 CALL（Covered Call 候选）:")
                for r in blk["calls_otm"]:
                    add(f"    行权价 {_fmt(r['strike'])}（{_fmt(r['distance_pct'], '%', 1)}）"
                        f" 权利金中值 {_fmt(r['mid_premium'])}"
                        f" 收益率 {_fmt(r['premium_yield_pct'], '%')}"
                        f" IV {_fmt(r['implied_volatility_pct'], '%', 1)}"
                        f" 未平仓 {_fmt(r['open_interest'], '', 0)}")
    else:
        add("该标的无期权链数据（A股或无期权品种）")

    # --- Wheel 机器决策 ---
    w = ctx.get("wheel")
    add("\n【Wheel 策略机器决策】")
    if w:
        add(f"20日EMA: {_fmt(w.get('ema_20'))} | 价格偏离EMA: {_fmt(w.get('ema_deviation'), '%')} | "
            f"EMA趋势(5日): {_fmt(w.get('ema_trend'), '%')}")
        add(f"历史波动率: {_fmt(w.get('volatility'), '%')} | 日内最大回撤: {_fmt(w.get('intra_drop'), '%')} | "
            f"跳空+涨跌: {_fmt(w.get('gap_and_change'), '%')} | V型反转: {w.get('is_v_shape')}")
        sp = w.get("sell_put") or {}
        add(f"Sell Put: [{sp.get('status')}] {sp.get('label')} — {sp.get('reason')}")
        if sp.get("recommended_strike"):
            add(f"  机器推荐行权价 {_fmt(sp.get('recommended_strike'))}"
                f"（距现价 {_fmt(sp.get('strike_distance_pct'), '%', 1)}）"
                f" 需备资金 {_fmt(sp.get('cash_required'))}")
        cc = w.get("covered_call") or {}
        if cc.get("status") and cc.get("status") != "no_position":
            add(f"Covered Call: [{cc.get('status')}] {cc.get('label')} — {cc.get('reason')}")
            if cc.get("recommended_strike"):
                add(f"  机器推荐行权价 {_fmt(cc.get('recommended_strike'))}"
                    f"（距现价 {_fmt(cc.get('strike_distance_pct'), '%', 1)}）")
    else:
        reason = ctx.get("wheel_unavailable_reason")
        add(f"不可用{f'：{reason}' if reason else ''}")

    return "\n".join(lines)
