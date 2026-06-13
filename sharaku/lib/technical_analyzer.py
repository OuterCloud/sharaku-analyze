"""技术分析模块 - 计算技术指标并生成交易信号"""

import pandas as pd
import yfinance as yf
from loguru import logger
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, ADXIndicator, SMAIndicator
from ta.volatility import BollingerBands

# K线形态检测清单
CANDLESTICK_PATTERNS_CHECKED = [
    "十字星（Doji）",
    "锤子线（Hammer）",
    "倒锤子线（Inverted Hammer）",
    "上吊线（Hanging Man）",
    "射击之星（Shooting Star）",
    "看涨吞没（Bullish Engulfing）",
    "看跌吞没（Bearish Engulfing）",
    "启明星（Morning Star）",
    "黄昏星（Evening Star）",
    "三只乌鸦（Three Black Crows）",
    "三个白武士（Three White Soldiers）",
    "乌云盖顶（Dark Cloud Cover）",
    "刺透形态（Piercing Pattern）",
    "孕线形态（Harami）",
    "平底/平顶（Tweezers）",
]


class TechnicalAnalyzer:
    """技术分析器 - 计算7大指标并给出综合评分(0-100)"""

    def __init__(self, ticker: str, period: str = "6mo"):
        self.ticker = ticker.upper()
        self.period = period

    def analyze(self) -> dict:
        """执行技术分析，返回结果字典"""
        logger.info(f"正在技术分析: {self.ticker}")

        data = yf.download(self.ticker, period=self.period, progress=False)
        if data.empty:
            return {
                "success": False,
                "error": f"未获取到数据，请检查股票代码是否正确: {self.ticker}",
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
            return {"success": False, "error": f"计算技术指标失败: {e}"}

        # ===== 信号判断 =====
        signals = {
            "K线": "中性",
            "均线": "中性",
            "MACD": "中性",
            "RSI": "中性",
            "KDJ": "中性",
            "布林带": "中性",
            "ADX": "中性",
        }
        score = 0

        # --- K线形态 ---
        k_signal, k_score, pattern_name, pattern_desc = self._identify_candlestick(
            df, price, bb_lower, bb_upper, ma60
        )
        signals["K线"] = k_signal
        score += k_score

        # --- 均线系统 ---
        if ma5 > ma10 > ma20 and price > ma5:
            signals["均线"] = "看多（多头排列）"
            score += 1.5
        elif ma5 < ma10 < ma20 and price < ma5:
            signals["均线"] = "看空（空头排列）"
            score -= 1.5
        elif price > ma5 > ma10 and price > ma20:
            signals["均线"] = "偏多（价格站上短期均线）"
            score += 0.5
        elif price < ma5 < ma10 and price < ma20:
            signals["均线"] = "偏空（价格跌破短期均线）"
            score -= 0.5

        # --- MACD ---
        if macd_val > macd_signal and macd_val > 0:
            signals["MACD"] = "看多（零轴上金叉）"
            score += 1.5
        elif macd_val < macd_signal and macd_val < 0:
            signals["MACD"] = "看空（零轴下死叉）"
            score -= 1.5
        elif macd_val > macd_signal and macd_val < 0:
            signals["MACD"] = "偏多（零轴下金叉）"
            score += 0.5
        elif macd_val < macd_signal and macd_val > 0:
            signals["MACD"] = "偏空（零轴上死叉）"
            score -= 0.5

        # --- RSI ---
        if rsi < 30:
            signals["RSI"] = "看多（超卖）"
            score += 1
        elif rsi > 70:
            signals["RSI"] = "看空（超买）"
            score -= 1
        elif 30 <= rsi <= 40:
            signals["RSI"] = "偏多（接近超卖）"
            score += 0.5
        elif 60 <= rsi <= 70:
            signals["RSI"] = "偏空（接近超买）"
            score -= 0.5

        # --- KDJ ---
        if k_val < 20 and k_val > d_val:
            signals["KDJ"] = "看多（超卖金叉）"
            score += 1
        elif k_val > 80 and k_val < d_val:
            signals["KDJ"] = "看空（超买死叉）"
            score -= 1
        elif 20 <= k_val <= 30 and k_val > d_val:
            signals["KDJ"] = "偏多（金叉）"
            score += 0.5
        elif 70 <= k_val <= 80 and k_val < d_val:
            signals["KDJ"] = "偏空（死叉）"
            score -= 0.5

        # --- 布林带 ---
        bb_width = bb_upper - bb_lower
        bb_position = (price - bb_lower) / bb_width if bb_width > 0 else 0.5
        if bb_position <= 0.1:
            signals["布林带"] = "看多（触及下轨）"
            score += 1
        elif bb_position >= 0.9:
            signals["布林带"] = "看空（触及上轨）"
            score -= 1
        elif 0.1 < bb_position <= 0.3:
            signals["布林带"] = "偏多（下轨附近）"
            score += 0.5
        elif 0.7 <= bb_position < 0.9:
            signals["布林带"] = "偏空（上轨附近）"
            score -= 0.5

        # --- ADX ---
        if not pd.isna(adx_val) and not pd.isna(di_plus) and not pd.isna(di_minus):
            if adx_val >= 25:
                if di_plus > di_minus:
                    signals["ADX"] = f"看多（强趋势 ADX={adx_val:.1f}）"
                    score += 1.5
                else:
                    signals["ADX"] = f"看空（强趋势 ADX={adx_val:.1f}）"
                    score -= 1.5
            elif adx_val >= 20:
                if di_plus > di_minus:
                    signals["ADX"] = f"偏多（趋势形成 ADX={adx_val:.1f}）"
                    score += 0.5
                else:
                    signals["ADX"] = f"偏空（趋势形成 ADX={adx_val:.1f}）"
                    score -= 0.5
            else:
                signals["ADX"] = f"震荡（无明显趋势 ADX={adx_val:.1f}）"

        # ===== 归一化分数 (0-100) =====
        normalized_score = max(0, min(100, (score + 12) * 100 / 24))

        ret = {
            "success": True,
            "ticker": self.ticker,
            "current_price": price,
            "score": normalized_score,
            "signals": signals,
            "advice": "",
            "warning": "本分析基于历史数据，不构成投资建议。",
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
            ret["patterns_checked"] = CANDLESTICK_PATTERNS_CHECKED

        # 建议
        if normalized_score >= 65:
            ret["advice"] = "看多（多指标共振看多, 建议持仓或轻仓试多）"
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
            ret["advice"] = "偏多（部分指标看多, 可小仓位试探）"
        elif normalized_score <= 35:
            ret["advice"] = "看空（多指标共振看空, 可考虑减仓, 空仓者勿追高）"
        elif normalized_score <= 45:
            ret["advice"] = "偏空（部分指标看空, 建议谨慎观望）"
        else:
            ret["advice"] = "观望（信号混乱, 等待明确方向）"

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
            return "中性", 0, None, None

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

        # 1. 十字星
        if body_1 <= total_range_1 * 0.1 and total_range_1 > 0:
            near_support = price <= bb_lower * 1.02 or (
                not pd.isna(ma60) and price <= ma60 * 1.02
            )
            near_resistance = price >= bb_upper * 0.98
            if near_support:
                return "看多（十字星-底部反转）", 1.5, "十字星", "实体极小的K线，出现在低位可能是底部反转信号"
            elif near_resistance:
                return "看空（十字星-顶部反转）", -1.5, "十字星", "实体极小的K线，出现在高位可能是顶部反转信号"
            else:
                return "中性（十字星-变盘）", 0, "十字星", "实体极小的K线，表示多空力量平衡，可能出现变盘"

        # 2. 锤子线
        if (
            is_bullish_1
            and lower_shadow_1 >= body_1 * 2
            and upper_shadow_1 <= body_1 * 0.3
        ):
            if is_bearish_2 and price <= bb_lower * 1.05:
                return "看多（锤子线-反转）", 2.0, "锤子线", "下影线长、上影线短的阳线，出现在下跌后是强烈的底部反转信号"

        # 3. 倒锤子线
        if (
            is_bullish_1
            and upper_shadow_1 >= body_1 * 2
            and lower_shadow_1 <= body_1 * 0.3
        ):
            if is_bearish_2 and price <= bb_lower * 1.05:
                return "看多（倒锤子-反转）", 1.5, "倒锤子线", "上影线长、下影线短的阳线，出现在下跌后暗示买方试探性反攻"

        # 4. 上吊线
        if (
            is_bearish_1
            and lower_shadow_1 >= body_1 * 2
            and upper_shadow_1 <= body_1 * 0.3
        ):
            if is_bullish_2 and price >= bb_upper * 0.95:
                return "看空（上吊线-反转）", -2.0, "上吊线", "下影线长的阴线，出现在上涨后的高位，是顶部反转警告信号"

        # 5. 射击之星
        if (
            is_bearish_1
            and upper_shadow_1 >= body_1 * 2
            and lower_shadow_1 <= body_1 * 0.3
        ):
            if is_bullish_2 and price >= bb_upper * 0.95:
                return "看空（射击之星-反转）", -1.5, "射击之星", "上影线长的阴线，出现在高位表示上方抛压沉重，可能反转下跌"

        # 6. 看涨吞没
        if is_bullish_1 and is_bearish_2:
            if close_1 > open_2 and open_1 < close_2 and body_1 > body_2 * 1.2:
                return "看多（看涨吞没）", 2.5, "看涨吞没", "大阳线完全吞没前一根阴线，是强烈的底部反转信号"

        # 7. 看跌吞没
        if is_bearish_1 and is_bullish_2:
            if close_1 < open_2 and open_1 > close_2 and body_1 > body_2 * 1.2:
                return "看空（看跌吞没）", -2.5, "看跌吞没", "大阴线完全吞没前一根阳线，是强烈的顶部反转信号"

        # 8. 启明星
        if is_bearish_3 and body_2 < body_3 * 0.3 and is_bullish_1:
            if close_1 > (open_3 + close_3) / 2 and price <= bb_lower * 1.1:
                return "看多（启明星-反转）", 2.5, "启明星", "三根K线组合：大阴线+小实体+大阳线，是经典的底部反转形态"

        # 9. 黄昏星
        if is_bullish_3 and body_2 < body_3 * 0.3 and is_bearish_1:
            if close_1 < (open_3 + close_3) / 2 and price >= bb_upper * 0.9:
                return "看空（黄昏星-反转）", -2.5, "黄昏星", "三根K线组合：大阳线+小实体+大阴线，是经典的顶部反转形态"

        # 10. 三只乌鸦
        if is_bearish_1 and is_bearish_2 and is_bearish_3:
            if close_1 < close_2 < close_3 and body_1 > total_range_1 * 0.6:
                return "看空（三只乌鸦）", -2.0, "三只乌鸦", "连续三根大阴线且逐步走低，是强烈的下跌趋势延续信号"

        # 11. 三个白武士
        if is_bullish_1 and is_bullish_2 and is_bullish_3:
            if close_1 > close_2 > close_3 and body_1 > total_range_1 * 0.6:
                return "看多（三个白武士）", 2.0, "三个白武士", "连续三根大阳线且逐步走高，是强烈的上涨趋势延续信号"

        # 12. 乌云盖顶
        if is_bearish_1 and is_bullish_2:
            if (
                open_1 > close_2
                and close_1 < (open_2 + close_2) / 2
                and close_1 > open_2
                and price >= bb_upper * 0.92
            ):
                return "看空（乌云盖顶-反转）", -2.0, "乌云盖顶", "阴线深入前一根阳线50%以上，出现在高位是顶部反转信号"

        # 13. 刺透形态
        if is_bullish_1 and is_bearish_2:
            if (
                open_1 < close_2
                and close_1 > (open_2 + close_2) / 2
                and close_1 < open_2
                and price <= bb_lower * 1.08
            ):
                return "看多（刺透形态-反转）", 2.0, "刺透形态", "阳线深入前一根阴线50%以上，出现在低位是底部反转信号"

        # 14. 孕线形态
        if body_1 <= body_2 * 0.3 and body_1 > 0:
            if max(open_1, close_1) <= max(open_2, close_2) and min(
                open_1, close_1
            ) >= min(open_2, close_2):
                near_support = price <= bb_lower * 1.05
                near_resistance = price >= bb_upper * 0.95
                if near_support and is_bullish_2:
                    return "看多（孕线-底部反转）", 1.5, "孕线", "小K线被前一根大K线完全包含，出现在低位可能反转上涨"
                elif near_resistance and is_bearish_2:
                    return "看空（孕线-顶部反转）", -1.5, "孕线", "小K线被前一根大K线完全包含，出现在高位可能反转下跌"
                else:
                    return "中性（孕线-变盘）", 0, "孕线", "小K线被前一根大K线完全包含，表示趋势减弱，可能变盘"

        # 15. 平底/平顶
        if len(df) >= 2:
            low_diff = abs(low_1 - low_2) / low_1 if low_1 > 0 else 1
            high_diff = abs(high_1 - high_2) / high_1 if high_1 > 0 else 1

            if low_diff <= 0.002 and is_bearish_2 and is_bullish_1:
                if price <= bb_lower * 1.05:
                    return "看多（平底-支撑确认）", 1.5, "平底", "两根K线最低价相同，表示该价位有强支撑，可能反弹"

            if high_diff <= 0.002 and is_bullish_2 and is_bearish_1:
                if price >= bb_upper * 0.95:
                    return "看空（平顶-阻力确认）", -1.5, "平顶", "两根K线最高价相同，表示该价位有强阻力，可能回落"

        # 简单趋势判断
        recent_change = (close_1 - close_3) / close_3
        near_support = price <= bb_lower * 1.02 or (
            not pd.isna(ma60) and price <= ma60 * 1.02
        )
        near_resistance = price >= bb_upper * 0.98

        if recent_change < -0.08 and near_support:
            return "偏多（超跌支撑）", 0.5, None, None
        elif recent_change > 0.08 and near_resistance:
            return "偏空（超买压力）", -0.5, None, None

        return "中性", 0, None, None
