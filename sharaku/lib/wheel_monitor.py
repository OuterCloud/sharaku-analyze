"""
Wheel期权策略盯盘分析模块
基于20日EMA、历史波动率和盘面特征，给出Sell Put和Covered Call的决策建议
"""

import numpy as np
import yfinance as yf


def analyze_wheel_strategy(ticker: str, cost_basis: float) -> dict:
    """
    分析Wheel期权策略，返回结构化结果。

    Args:
        ticker: 股票代码
        cost_basis: 正股持仓成本价（用于Covered Call决策）

    Returns:
        dict with analysis results
    """
    stock = yf.Ticker(ticker)

    # 获取实时价格
    try:
        current_price = stock.fast_info["lastPrice"]
    except (KeyError, TypeError):
        current_price = None

    # 获取近3个月历史K线
    hist = stock.history(period="3mo")
    if hist.empty:
        return {"success": False, "error": f"无法获取 {ticker} 数据，请检查代码或网络连接"}

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
        put_label = "危险：下降趋势 (Falling Knife)"
        put_reason = (
            f"20日EMA近5天下跌{ema_trend * 100:.1f}%，处于下降趋势中，"
            "此时卖Put容易被assign后继续亏损，应等趋势企稳。"
        )
    elif ema_trend < 0 and price_vs_ema < -0.05:
        put_status = "caution"
        put_label = "谨慎观望 (Caution)"
        put_reason = (
            f"EMA走平偏弱，股价偏离EMA达{price_vs_ema * 100:.1f}%，"
            "不排除趋势转弱的可能，如需卖Put建议极低strike小仓位试探。"
        )
    elif price_vs_ema < 0 and ema_trend >= 0:
        put_status = "great"
        put_label = "极佳建仓期 (Great Opportunity)"
        put_reason = (
            f"{ticker} 处于上升趋势中的回调（EMA仍在走高+{ema_trend * 100:.1f}%），"
            "股价短暂跌破EMA，恐慌推高Put权利金，正是卖Put的黄金窗口！"
        )
    elif price_vs_ema < 0.02 and intra_drop < -5.0 and ema_trend >= 0:
        put_status = "great"
        put_label = "极佳建仓期 (Great Opportunity)"
        put_reason = f"{ticker} 上升趋势中遭遇日内剧烈洗盘(>{abs(intra_drop):.1f}%)，IV飙升，时间价值极肥！"
    elif price_vs_ema < 0.05 and intra_drop < -3.0 and ema_trend >= -0.01:
        put_status = "acceptable"
        put_label = "可考虑建仓 (Acceptable)"
        put_reason = "股价接近EMA且有一定回调，趋势尚未走坏，可小仓位试探性卖Put。"
    else:
        put_status = "wait"
        put_label = "观望等待 (Wait for Dip)"
        put_reason = "当前远离支撑位或趋势不明朗，建议等回调到EMA附近再卖Put。"

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

    if current_price < cost_basis * 0.95:
        call_status = "underwater"
        call_label = "不建议卖Call (Underwater)"
        call_reason = (
            f"当前价 ${current_price:.2f} 远低于成本 ${cost_basis:.2f}，"
            "卖Call会锁定亏损上限，等待反弹到成本附近再考虑。"
        )
    else:
        recommended_call_strike = round(current_price * (1 + 0.67 * std_5day))
        if recommended_call_strike <= cost_basis:
            recommended_call_strike = round(cost_basis * 1.05)

        if price_vs_ema < 0:
            call_status = "hold"
            call_label = "暂时忍耐 (Hold Shares)"
            call_reason = (
                f"股价低于20日EMA（偏离{price_vs_ema * 100:.1f}%），正处于回调阶段，"
                "此时卖Call会锁死反弹空间，应等待股价重回EMA上方再考虑。"
            )
        elif (gap_and_change > 5.0 or is_v_shape) and price_vs_ema > 0.02:
            call_status = "great"
            call_label = "绝佳收租期 (High Premium)"
            if is_v_shape:
                call_reason = f"{ticker} 强势V型反转且站稳EMA上方，IV拉升，Call权利金丰厚！"
            else:
                call_reason = f"{ticker} 单日暴涨 {gap_and_change:.1f}%，高于EMA，适合高位卖出Covered Call！"
        elif gap_and_change > 3.0 and price_vs_ema > 0:
            call_status = "moderate"
            call_label = "可以收租 (Moderate Premium)"
            call_reason = "股价站上EMA且有涨幅，Call权利金尚可，可适量卖出。"
        else:
            call_status = "hold"
            call_label = "暂时忍耐 (Hold Shares)"
            call_reason = "当前未出现明显冲高，或股价尚未站稳EMA上方，卖Call时机不成熟。"

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
