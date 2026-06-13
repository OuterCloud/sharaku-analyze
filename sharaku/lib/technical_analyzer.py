"""技术分析模块 - 计算技术指标并生成交易信号"""

import pandas as pd
import yfinance as yf
from loguru import logger
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, ADXIndicator, SMAIndicator
from ta.volatility import BollingerBands

from sharaku.i18n import (
    ADVICE,
    ERRORS,
    PATTERN_DESCRIPTIONS,
    PATTERN_NAMES,
    PATTERN_SIGNALS,
    PATTERNS_CHECKED,
    SIGNAL_NAMES,
    SIGNALS,
    WARNING,
)


class TechnicalAnalyzer:
    """技术分析器 - 计算7大指标并给出综合评分(0-100)"""

    def __init__(self, ticker: str, period: str = "6mo", lang: str = "zh"):
        self.ticker = ticker.upper()
        self.period = period
        self.lang = lang if lang in ("zh", "en") else "zh"

    def _t_signal(self, key: str, **kwargs) -> str:
        s = SIGNALS[self.lang][key]
        return s.format(**kwargs) if kwargs else s

    def _t_name(self, key: str) -> str:
        return SIGNAL_NAMES[self.lang][key]

    def analyze(self) -> dict:
        """执行技术分析，返回结果字典"""
        logger.info(f"正在技术分析: {self.ticker}")

        data = yf.download(self.ticker, period=self.period, progress=False)
        if data.empty:
            return {
                "success": False,
                "error": ERRORS[self.lang]["no_data"].format(ticker=self.ticker),
            }

        df = data.copy()
        close = df["Close"].squeeze()
        high = df["High"].squeeze()
        low = df["Low"].squeeze()

        # ===== 计算技术指标 =====
        df["MA5"] = SMAIndicator(close, window=5).sma_indicator()
        df["MA10"] = SMAIndicator(close, window=10).sma_indicator()
        df["MA20"] = SMAIndicator(close, window=20).sma_indicator()
        df["MA60"] = SMAIndicator(close, window=60).sma_indicator()

        macd = MACD(close)
        df["MACD"] = macd.macd()
        df["MACD_signal"] = macd.macd_signal()
        df["MACD_hist"] = macd.macd_diff()

        df["RSI"] = RSIIndicator(close, window=14).rsi()

        stoch = StochasticOscillator(high, low, close, window=9, smooth_window=3)
        df["K"] = stoch.stoch()
        df["D"] = stoch.stoch_signal()
        df["J"] = 3 * df["K"] - 2 * df["D"]

        bb = BollingerBands(close, window=20, window_dev=2)
        df["BB_upper"] = bb.bollinger_hband()
        df["BB_middle"] = bb.bollinger_mavg()
        df["BB_lower"] = bb.bollinger_lband()

        adx_ind = ADXIndicator(high, low, close, window=14)
        df["ADX"] = adx_ind.adx()
        df["DI_plus"] = adx_ind.adx_pos()
        df["DI_minus"] = adx_ind.adx_neg()

        # 提取最新值
        try:
            price = self._scalar(df["Close"].iloc[-1])
            bb_lower = self._scalar(df["BB_lower"].iloc[-1])
            bb_upper = self._scalar(df["BB_upper"].iloc[-1])
            bb_middle = self._scalar(df["BB_middle"].iloc[-1])
            ma5 = self._scalar(df["MA5"].iloc[-1])
            ma10 = self._scalar(df["MA10"].iloc[-1])
            ma20 = self._scalar(df["MA20"].iloc[-1])
            ma60 = self._scalar(df["MA60"].iloc[-1])
            macd_val = self._scalar(df["MACD"].iloc[-1])
            macd_signal = self._scalar(df["MACD_signal"].iloc[-1])
            macd_hist = self._scalar(df["MACD_hist"].iloc[-1])
            rsi = self._scalar(df["RSI"].iloc[-1])
            k_val = self._scalar(df["K"].iloc[-1])
            d_val = self._scalar(df["D"].iloc[-1])
            adx_val = self._scalar(df["ADX"].iloc[-1])
            di_plus = self._scalar(df["DI_plus"].iloc[-1])
            di_minus = self._scalar(df["DI_minus"].iloc[-1])
        except Exception as e:
            return {"success": False, "error": ERRORS[self.lang]["calc_failed"].format(error=e)}

        # ===== 信号判断 =====
        neutral = self._t_signal("neutral")
        signals = {
            self._t_name("candlestick"): neutral,
            self._t_name("ma"): neutral,
            self._t_name("macd"): neutral,
            self._t_name("rsi"): neutral,
            self._t_name("kdj"): neutral,
            self._t_name("bollinger"): neutral,
            self._t_name("adx"): neutral,
        }
        score = 0

        # --- K线形态 ---
        k_signal, k_score, pattern_name, pattern_desc = self._identify_candlestick(
            df, price, bb_lower, bb_upper, ma60
        )
        signals[self._t_name("candlestick")] = k_signal
        score += k_score

        # --- 均线系统 ---
        if ma5 > ma10 > ma20 and price > ma5:
            signals[self._t_name("ma")] = self._t_signal("ma_bullish")
            score += 1.5
        elif ma5 < ma10 < ma20 and price < ma5:
            signals[self._t_name("ma")] = self._t_signal("ma_bearish")
            score -= 1.5
        elif price > ma5 > ma10 and price > ma20:
            signals[self._t_name("ma")] = self._t_signal("ma_slightly_bullish")
            score += 0.5
        elif price < ma5 < ma10 and price < ma20:
            signals[self._t_name("ma")] = self._t_signal("ma_slightly_bearish")
            score -= 0.5

        # --- MACD ---
        if macd_val > macd_signal and macd_val > 0:
            signals[self._t_name("macd")] = self._t_signal("macd_bullish")
            score += 1.5
        elif macd_val < macd_signal and macd_val < 0:
            signals[self._t_name("macd")] = self._t_signal("macd_bearish")
            score -= 1.5
        elif macd_val > macd_signal and macd_val < 0:
            signals[self._t_name("macd")] = self._t_signal("macd_slightly_bullish")
            score += 0.5
        elif macd_val < macd_signal and macd_val > 0:
            signals[self._t_name("macd")] = self._t_signal("macd_slightly_bearish")
            score -= 0.5

        # --- RSI ---
        if rsi < 30:
            signals[self._t_name("rsi")] = self._t_signal("rsi_bullish")
            score += 1
        elif rsi > 70:
            signals[self._t_name("rsi")] = self._t_signal("rsi_bearish")
            score -= 1
        elif 30 <= rsi <= 40:
            signals[self._t_name("rsi")] = self._t_signal("rsi_slightly_bullish")
            score += 0.5
        elif 60 <= rsi <= 70:
            signals[self._t_name("rsi")] = self._t_signal("rsi_slightly_bearish")
            score -= 0.5

        # --- KDJ ---
        if k_val < 20 and k_val > d_val:
            signals[self._t_name("kdj")] = self._t_signal("kdj_bullish")
            score += 1
        elif k_val > 80 and k_val < d_val:
            signals[self._t_name("kdj")] = self._t_signal("kdj_bearish")
            score -= 1
        elif 20 <= k_val <= 30 and k_val > d_val:
            signals[self._t_name("kdj")] = self._t_signal("kdj_slightly_bullish")
            score += 0.5
        elif 70 <= k_val <= 80 and k_val < d_val:
            signals[self._t_name("kdj")] = self._t_signal("kdj_slightly_bearish")
            score -= 0.5

        # --- 布林带 ---
        bb_width = bb_upper - bb_lower
        bb_position = (price - bb_lower) / bb_width if bb_width > 0 else 0.5
        if bb_position <= 0.1:
            signals[self._t_name("bollinger")] = self._t_signal("bb_bullish")
            score += 1
        elif bb_position >= 0.9:
            signals[self._t_name("bollinger")] = self._t_signal("bb_bearish")
            score -= 1
        elif 0.1 < bb_position <= 0.3:
            signals[self._t_name("bollinger")] = self._t_signal("bb_slightly_bullish")
            score += 0.5
        elif 0.7 <= bb_position < 0.9:
            signals[self._t_name("bollinger")] = self._t_signal("bb_slightly_bearish")
            score -= 0.5

        # --- ADX ---
        if not pd.isna(adx_val) and not pd.isna(di_plus) and not pd.isna(di_minus):
            if adx_val >= 25:
                if di_plus > di_minus:
                    signals[self._t_name("adx")] = self._t_signal("adx_bullish", adx=adx_val)
                    score += 1.5
                else:
                    signals[self._t_name("adx")] = self._t_signal("adx_bearish", adx=adx_val)
                    score -= 1.5
            elif adx_val >= 20:
                if di_plus > di_minus:
                    signals[self._t_name("adx")] = self._t_signal("adx_slightly_bullish", adx=adx_val)
                    score += 0.5
                else:
                    signals[self._t_name("adx")] = self._t_signal("adx_slightly_bearish", adx=adx_val)
                    score -= 0.5
            else:
                signals[self._t_name("adx")] = self._t_signal("adx_oscillating", adx=adx_val)

        # ===== 归一化分数 (0-100) =====
        normalized_score = max(0, min(100, (score + 12) * 100 / 24))

        ret = {
            "success": True,
            "ticker": self.ticker,
            "current_price": price,
            "score": normalized_score,
            "signals": signals,
            "advice": "",
            "warning": WARNING[self.lang],
            "indicator_values": {
                "ma5": ma5,
                "ma10": ma10,
                "ma20": ma20,
                "ma60": ma60,
                "macd": macd_val,
                "macd_signal": macd_signal,
                "macd_hist": macd_hist,
                "rsi": rsi,
                "k": k_val,
                "d": d_val,
                "bb_upper": bb_upper,
                "bb_middle": bb_middle,
                "bb_lower": bb_lower,
                "adx": adx_val,
                "di_plus": di_plus,
                "di_minus": di_minus,
            },
        }

        # K线形态
        if pattern_name:
            ret["candlestick_pattern"] = {
                "name": pattern_name,
                "description": pattern_desc,
                "score": k_score,
                "signal": k_signal,
            }
        else:
            ret["candlestick_pattern"] = None
            ret["patterns_checked"] = PATTERNS_CHECKED[self.lang]

        # 建议
        if normalized_score >= 65:
            ret["advice"] = ADVICE[self.lang]["strong_bullish"]
            recent_low = df["Low"].iloc[-5:].min()
            if pd.isna(recent_low):
                recent_low = price * 0.95
            else:
                recent_low = self._scalar(recent_low)
            stop_loss = min(bb_lower, recent_low) * 0.98
            target = price * 1.08
            ret["stop_loss"] = stop_loss
            ret["target"] = target
        elif normalized_score >= 55:
            ret["advice"] = ADVICE[self.lang]["bullish"]
        elif normalized_score <= 35:
            ret["advice"] = ADVICE[self.lang]["strong_bearish"]
        elif normalized_score <= 45:
            ret["advice"] = ADVICE[self.lang]["bearish"]
        else:
            ret["advice"] = ADVICE[self.lang]["neutral"]

        return ret

    @staticmethod
    def _scalar(val):
        """将 pandas/numpy 值转为 Python 标量"""
        if hasattr(val, "item"):
            return val.item()
        return float(val)

    def _identify_candlestick(self, df, price, bb_lower, bb_upper, ma60):
        """识别K线形态，返回 (信号, 得分, 形态名, 描述)"""
        if len(df) < 3:
            return self._t_signal("neutral"), 0, None, None

        open_1 = self._scalar(df["Open"].iloc[-1])
        high_1 = self._scalar(df["High"].iloc[-1])
        low_1 = self._scalar(df["Low"].iloc[-1])
        close_1 = self._scalar(df["Close"].iloc[-1])

        open_2 = self._scalar(df["Open"].iloc[-2])
        high_2 = self._scalar(df["High"].iloc[-2])
        low_2 = self._scalar(df["Low"].iloc[-2])
        close_2 = self._scalar(df["Close"].iloc[-2])

        open_3 = self._scalar(df["Open"].iloc[-3])
        close_3 = self._scalar(df["Close"].iloc[-3])

        body_1 = abs(close_1 - open_1)
        upper_shadow_1 = high_1 - max(open_1, close_1)
        lower_shadow_1 = min(open_1, close_1) - low_1
        total_range_1 = high_1 - low_1

        body_2 = abs(close_2 - open_2)
        body_3 = abs(close_3 - open_3)

        is_bullish_1 = close_1 > open_1
        is_bearish_1 = close_1 < open_1
        is_bullish_2 = close_2 > open_2
        is_bearish_2 = close_2 < open_2
        is_bullish_3 = close_3 > open_3
        is_bearish_3 = close_3 < open_3

        lang = self.lang
        ps = PATTERN_SIGNALS[lang]
        pn = PATTERN_NAMES[lang]
        pd_desc = PATTERN_DESCRIPTIONS[lang]

        # 1. 十字星
        if body_1 <= total_range_1 * 0.1 and total_range_1 > 0:
            near_support = price <= bb_lower * 1.02 or (
                not pd.isna(ma60) and price <= ma60 * 1.02
            )
            near_resistance = price >= bb_upper * 0.98
            if near_support:
                return ps["doji_bullish"], 1.5, pn["doji"], pd_desc["doji_bottom"]
            elif near_resistance:
                return ps["doji_bearish"], -1.5, pn["doji"], pd_desc["doji_top"]
            else:
                return ps["doji_neutral"], 0, pn["doji"], pd_desc["doji_neutral"]

        # 2. 锤子线
        if (
            is_bullish_1
            and lower_shadow_1 >= body_1 * 2
            and upper_shadow_1 <= body_1 * 0.3
        ):
            if is_bearish_2 and price <= bb_lower * 1.05:
                return ps["hammer_bullish"], 2.0, pn["hammer"], pd_desc["hammer"]

        # 3. 倒锤子线
        if (
            is_bullish_1
            and upper_shadow_1 >= body_1 * 2
            and lower_shadow_1 <= body_1 * 0.3
        ):
            if is_bearish_2 and price <= bb_lower * 1.05:
                return ps["inverted_hammer_bullish"], 1.5, pn["inverted_hammer"], pd_desc["inverted_hammer"]

        # 4. 上吊线
        if (
            is_bearish_1
            and lower_shadow_1 >= body_1 * 2
            and upper_shadow_1 <= body_1 * 0.3
        ):
            if is_bullish_2 and price >= bb_upper * 0.95:
                return ps["hanging_man_bearish"], -2.0, pn["hanging_man"], pd_desc["hanging_man"]

        # 5. 射击之星
        if (
            is_bearish_1
            and upper_shadow_1 >= body_1 * 2
            and lower_shadow_1 <= body_1 * 0.3
        ):
            if is_bullish_2 and price >= bb_upper * 0.95:
                return ps["shooting_star_bearish"], -1.5, pn["shooting_star"], pd_desc["shooting_star"]

        # 6. 看涨吞没
        if is_bullish_1 and is_bearish_2:
            if close_1 > open_2 and open_1 < close_2 and body_1 > body_2 * 1.2:
                return ps["bullish_engulfing"], 2.5, pn["bullish_engulfing"], pd_desc["bullish_engulfing"]

        # 7. 看跌吞没
        if is_bearish_1 and is_bullish_2:
            if close_1 < open_2 and open_1 > close_2 and body_1 > body_2 * 1.2:
                return ps["bearish_engulfing"], -2.5, pn["bearish_engulfing"], pd_desc["bearish_engulfing"]

        # 8. 启明星
        if is_bearish_3 and body_2 < body_3 * 0.3 and is_bullish_1:
            if close_1 > (open_3 + close_3) / 2 and price <= bb_lower * 1.1:
                return ps["morning_star_bullish"], 2.5, pn["morning_star"], pd_desc["morning_star"]

        # 9. 黄昏星
        if is_bullish_3 and body_2 < body_3 * 0.3 and is_bearish_1:
            if close_1 < (open_3 + close_3) / 2 and price >= bb_upper * 0.9:
                return ps["evening_star_bearish"], -2.5, pn["evening_star"], pd_desc["evening_star"]

        # 10. 三只乌鸦
        if is_bearish_1 and is_bearish_2 and is_bearish_3:
            if close_1 < close_2 < close_3 and body_1 > total_range_1 * 0.6:
                return ps["three_black_crows"], -2.0, pn["three_black_crows"], pd_desc["three_black_crows"]

        # 11. 三个白武士
        if is_bullish_1 and is_bullish_2 and is_bullish_3:
            if close_1 > close_2 > close_3 and body_1 > total_range_1 * 0.6:
                return ps["three_white_soldiers"], 2.0, pn["three_white_soldiers"], pd_desc["three_white_soldiers"]

        # 12. 乌云盖顶
        if is_bearish_1 and is_bullish_2:
            if (
                open_1 > close_2
                and close_1 < (open_2 + close_2) / 2
                and close_1 > open_2
                and price >= bb_upper * 0.92
            ):
                return ps["dark_cloud_cover"], -2.0, pn["dark_cloud_cover"], pd_desc["dark_cloud_cover"]

        # 13. 刺透形态
        if is_bullish_1 and is_bearish_2:
            if (
                open_1 < close_2
                and close_1 > (open_2 + close_2) / 2
                and close_1 < open_2
                and price <= bb_lower * 1.08
            ):
                return ps["piercing_bullish"], 2.0, pn["piercing"], pd_desc["piercing"]

        # 14. 孕线形态
        if body_1 <= body_2 * 0.3 and body_1 > 0:
            if max(open_1, close_1) <= max(open_2, close_2) and min(
                open_1, close_1
            ) >= min(open_2, close_2):
                near_support = price <= bb_lower * 1.05
                near_resistance = price >= bb_upper * 0.95
                if near_support and is_bullish_2:
                    return ps["harami_bullish"], 1.5, pn["harami"], pd_desc["harami_bottom"]
                elif near_resistance and is_bearish_2:
                    return ps["harami_bearish"], -1.5, pn["harami"], pd_desc["harami_top"]
                else:
                    return ps["harami_neutral"], 0, pn["harami"], pd_desc["harami_neutral"]

        # 15. 平底/平顶
        if len(df) >= 2:
            low_diff = abs(low_1 - low_2) / low_1 if low_1 > 0 else 1
            high_diff = abs(high_1 - high_2) / high_1 if high_1 > 0 else 1

            if low_diff <= 0.002 and is_bearish_2 and is_bullish_1:
                if price <= bb_lower * 1.05:
                    return ps["tweezers_bullish"], 1.5, pn["tweezers_bottom"], pd_desc["tweezers_bottom"]

            if high_diff <= 0.002 and is_bullish_2 and is_bearish_1:
                if price >= bb_upper * 0.95:
                    return ps["tweezers_bearish"], -1.5, pn["tweezers_top"], pd_desc["tweezers_top"]

        # 简单趋势判断
        recent_change = (close_1 - close_3) / close_3
        near_support = price <= bb_lower * 1.02 or (
            not pd.isna(ma60) and price <= ma60 * 1.02
        )
        near_resistance = price >= bb_upper * 0.98

        if recent_change < -0.08 and near_support:
            return self._t_signal("k_slightly_bullish"), 0.5, None, None
        elif recent_change > 0.08 and near_resistance:
            return self._t_signal("k_slightly_bearish"), -0.5, None, None

        return self._t_signal("neutral"), 0, None, None
