"""
Wheel期权策略盯盘分析模块
基于20日EMA、历史波动率和盘面特征，给出Sell Put和Covered Call的决策建议
"""

import numpy as np
import yfinance as yf

from sharaku.i18n import ERRORS, WHEEL_CALL, WHEEL_PUT


def analyze_wheel_strategy(ticker: str, cost_basis: float, lang: str = "zh") -> dict:
    """
    分析Wheel期权策略，返回结构化结果。

    Args:
        ticker: 股票代码
        cost_basis: 正股持仓成本价（用于Covered Call决策）
        lang: 语言 "zh" 或 "en"

    Returns:
        dict with analysis results
    """
    if lang not in ("zh", "en"):
        lang = "zh"

    t_put = WHEEL_PUT[lang]
    t_call = WHEEL_CALL[lang]
    t_err = ERRORS[lang]

    # A股不支持Wheel策略
    if ticker.endswith(".SS") or ticker.endswith(".SZ"):
        return {"success": False, "error": t_err["a_share_no_options"]}

    stock = yf.Ticker(ticker)

    # 检查是否有期权链
    try:
        options_dates = stock.options
        if not options_dates:
            return {"success": False, "error": t_err["no_options"].format(ticker=ticker)}
    except Exception:
        return {"success": False, "error": t_err["no_options"].format(ticker=ticker)}

    # 获取实时价格
    try:
        current_price = stock.fast_info["lastPrice"]
    except (KeyError, TypeError):
        current_price = None

    # 获取近3个月历史K线
    hist = stock.history(period="3mo")
    if hist.empty:
        return {"success": False, "error": t_err["no_ticker_data"].format(ticker=ticker)}

    if current_price is None:
        current_price = hist["Close"].iloc[-1]

    today_open = float(hist["Open"].iloc[-1])
    today_high = float(hist["High"].iloc[-1])
    today_low = float(hist["Low"].iloc[-1])
    prev_close = float(hist["Close"].iloc[-2])

    # 20日指数移动平均线
    hist["20_EMA"] = hist["Close"].ewm(span=20, adjust=False).mean()
    ema_20 = float(hist["20_EMA"].iloc[-1])

    # 20日历史波动率
    log_returns = np.log(hist["Close"] / hist["Close"].shift(1))
    volatility = float(log_returns.rolling(window=20).std().iloc[-1] * np.sqrt(252))

    # 盘面特征
    intra_drop = (
        ((today_low - today_open) / today_open) * 100
        if today_open > 0
        else 0
    )
    intra_change = (
        ((current_price - today_open) / today_open) * 100
        if today_open > 0
        else 0
    )
    gap_and_change = ((current_price - prev_close) / prev_close) * 100

    # V型反转判定
    drop_depth = today_open - today_low
    recovery = current_price - today_low
    is_v_shape = (
        drop_depth / today_open > 0.03
        and recovery / drop_depth > 0.7
        if drop_depth > 0
        else False
    )

    # 周度标准差（5个交易日）
    std_5day = volatility * np.sqrt(5 / 252)

    # EMA趋势方向
    price_vs_ema = (current_price - ema_20) / ema_20
    ema_5d_ago = float(hist["20_EMA"].iloc[-6]) if len(hist) >= 6 else float(hist["20_EMA"].iloc[0])
    ema_trend = (ema_20 - ema_5d_ago) / ema_5d_ago

    # ========== SELL PUT 决策 ==========
    if ema_trend < -0.02:
        put_status = "danger"
        put_label = t_put["danger_label"]
        put_reason = t_put["danger_reason"].format(ema_trend=ema_trend * 100)
    elif ema_trend < 0 and price_vs_ema < -0.05:
        put_status = "caution"
        put_label = t_put["caution_label"]
        put_reason = t_put["caution_reason"].format(price_vs_ema=price_vs_ema * 100)
    elif price_vs_ema < 0 and ema_trend >= 0:
        put_status = "great"
        put_label = t_put["great_label"]
        put_reason = t_put["great_reason_pullback"].format(ticker=ticker, ema_trend=ema_trend * 100)
    elif price_vs_ema < 0.02 and intra_drop < -5.0 and ema_trend >= 0:
        put_status = "great"
        put_label = t_put["great_label"]
        put_reason = t_put["great_reason_washout"].format(ticker=ticker, intra_drop=abs(intra_drop))
    elif price_vs_ema < 0.05 and intra_drop < -3.0 and ema_trend >= -0.01:
        put_status = "acceptable"
        put_label = t_put["acceptable_label"]
        put_reason = t_put["acceptable_reason"]
    else:
        put_status = "wait"
        put_label = t_put["wait_label"]
        put_reason = t_put["wait_reason"]

    # Put strike 推荐
    raw_put_strike = current_price * (1 - 1.04 * std_5day)
    ema_cap = ema_20 * 0.95
    floor = current_price * 0.70
    recommended_put_strike = round(min(raw_put_strike, ema_cap))
    if recommended_put_strike < floor:
        recommended_put_strike = round(floor)

    # ========== COVERED CALL 决策 ==========
    call_status = ""
    call_label = ""
    call_reason = ""
    recommended_call_strike = None

    underwater_pct = (cost_basis - current_price) / cost_basis * 100 if cost_basis > 0 else 0

    if current_price < cost_basis * 0.85:
        # 深度套牢（>15%），不建议卖Call
        call_status = "underwater"
        call_label = t_call["underwater_label"]
        call_reason = t_call["underwater_reason"].format(
            price=current_price, cost=cost_basis, pct=underwater_pct
        )
    elif current_price < cost_basis:
        # 轻度套牢（<15%），可在成本价之上卖Call收租
        recommended_call_strike = round(cost_basis * 1.02)

        if price_vs_ema >= 0 and (gap_and_change > 3.0 or is_v_shape):
            call_status = "moderate"
            call_label = t_call["moderate_underwater_label"]
            call_reason = t_call["moderate_underwater_reason"].format(
                price=current_price, pct=underwater_pct, strike=recommended_call_strike
            )
        else:
            call_status = "caution"
            call_label = t_call["caution_underwater_label"]
            call_reason = t_call["caution_underwater_reason"].format(
                price=current_price, pct=underwater_pct, strike=recommended_call_strike
            )
    else:
        # 浮盈状态
        recommended_call_strike = round(current_price * (1 + 0.67 * std_5day))
        if recommended_call_strike <= cost_basis:
            recommended_call_strike = round(cost_basis * 1.05)

        if price_vs_ema < 0:
            call_status = "hold"
            call_label = t_call["hold_label"]
            call_reason = t_call["hold_reason_pullback"].format(deviation=price_vs_ema * 100)
        elif (gap_and_change > 5.0 or is_v_shape) and price_vs_ema > 0.02:
            call_status = "great"
            call_label = t_call["great_label"]
            if is_v_shape:
                call_reason = t_call["great_reason_v"].format(ticker=ticker)
            else:
                call_reason = t_call["great_reason_surge"].format(ticker=ticker, change=gap_and_change)
        elif gap_and_change > 3.0 and price_vs_ema > 0:
            call_status = "moderate"
            call_label = t_call["moderate_label"]
            call_reason = t_call["moderate_reason"]
        else:
            call_status = "hold"
            call_label = t_call["hold_label"]
            call_reason = t_call["hold_reason_no_spike"]

    return {
        "success": True,
        "ticker": ticker,
        "current_price": float(current_price),
        "ema_20": ema_20,
        "ema_deviation": price_vs_ema * 100,
        "ema_trend": ema_trend * 100,
        "volatility": volatility * 100,
        "intra_drop": intra_drop,
        "intra_change": intra_change,
        "gap_and_change": gap_and_change,
        "is_v_shape": is_v_shape,
        "today_open": today_open,
        "today_high": today_high,
        "today_low": today_low,
        "prev_close": prev_close,
        "sell_put": {
            "status": put_status,
            "label": put_label,
            "reason": put_reason,
            "recommended_strike": recommended_put_strike,
            "strike_distance_pct": ((recommended_put_strike - current_price) / current_price) * 100,
            "cash_required": recommended_put_strike * 100,
        },
        "covered_call": {
            "status": call_status,
            "label": call_label,
            "reason": call_reason,
            "recommended_strike": recommended_call_strike,
            "strike_distance_pct": (
                ((recommended_call_strike - current_price) / current_price) * 100
                if recommended_call_strike
                else None
            ),
            "cost_basis": cost_basis,
        },
    }
