"""Backend i18n module - provides translations for technical analysis and wheel strategy."""

# Signal indicator names
SIGNAL_NAMES = {
    "zh": {
        "candlestick": "K线",
        "ma": "均线",
        "macd": "MACD",
        "rsi": "RSI",
        "kdj": "KDJ",
        "bollinger": "布林带",
        "adx": "ADX",
    },
    "en": {
        "candlestick": "Candlestick",
        "ma": "Moving Avg",
        "macd": "MACD",
        "rsi": "RSI",
        "kdj": "KDJ",
        "bollinger": "Bollinger",
        "adx": "ADX",
    },
}

# Signal values
SIGNALS = {
    "zh": {
        "neutral": "中性",
        # MA
        "ma_bullish": "看多（多头排列）",
        "ma_bearish": "看空（空头排列）",
        "ma_slightly_bullish": "偏多（价格站上短期均线）",
        "ma_slightly_bearish": "偏空（价格跌破短期均线）",
        # MACD
        "macd_bullish": "看多（零轴上金叉）",
        "macd_bearish": "看空（零轴下死叉）",
        "macd_slightly_bullish": "偏多（零轴下金叉）",
        "macd_slightly_bearish": "偏空（零轴上死叉）",
        # RSI
        "rsi_bullish": "看多（超卖）",
        "rsi_bearish": "看空（超买）",
        "rsi_slightly_bullish": "偏多（接近超卖）",
        "rsi_slightly_bearish": "偏空（接近超买）",
        # KDJ
        "kdj_bullish": "看多（超卖金叉）",
        "kdj_bearish": "看空（超买死叉）",
        "kdj_slightly_bullish": "偏多（金叉）",
        "kdj_slightly_bearish": "偏空（死叉）",
        # Bollinger
        "bb_bullish": "看多（触及下轨）",
        "bb_bearish": "看空（触及上轨）",
        "bb_slightly_bullish": "偏多（下轨附近）",
        "bb_slightly_bearish": "偏空（上轨附近）",
        # ADX
        "adx_bullish": "看多（强趋势 ADX={adx:.1f}）",
        "adx_bearish": "看空（强趋势 ADX={adx:.1f}）",
        "adx_slightly_bullish": "偏多（趋势形成 ADX={adx:.1f}）",
        "adx_slightly_bearish": "偏空（趋势形成 ADX={adx:.1f}）",
        "adx_oscillating": "震荡（无明显趋势 ADX={adx:.1f}）",
        # Candlestick simple
        "k_slightly_bullish": "偏多（超跌支撑）",
        "k_slightly_bearish": "偏空（超买压力）",
    },
    "en": {
        "neutral": "Neutral",
        # MA
        "ma_bullish": "Bullish (Bull Alignment)",
        "ma_bearish": "Bearish (Bear Alignment)",
        "ma_slightly_bullish": "Slightly Bullish (Above Short MA)",
        "ma_slightly_bearish": "Slightly Bearish (Below Short MA)",
        # MACD
        "macd_bullish": "Bullish (Golden Cross Above 0)",
        "macd_bearish": "Bearish (Dead Cross Below 0)",
        "macd_slightly_bullish": "Slightly Bullish (Golden Cross Below 0)",
        "macd_slightly_bearish": "Slightly Bearish (Dead Cross Above 0)",
        # RSI
        "rsi_bullish": "Bullish (Oversold)",
        "rsi_bearish": "Bearish (Overbought)",
        "rsi_slightly_bullish": "Slightly Bullish (Near Oversold)",
        "rsi_slightly_bearish": "Slightly Bearish (Near Overbought)",
        # KDJ
        "kdj_bullish": "Bullish (Oversold Golden Cross)",
        "kdj_bearish": "Bearish (Overbought Dead Cross)",
        "kdj_slightly_bullish": "Slightly Bullish (Golden Cross)",
        "kdj_slightly_bearish": "Slightly Bearish (Dead Cross)",
        # Bollinger
        "bb_bullish": "Bullish (Touch Lower Band)",
        "bb_bearish": "Bearish (Touch Upper Band)",
        "bb_slightly_bullish": "Slightly Bullish (Near Lower Band)",
        "bb_slightly_bearish": "Slightly Bearish (Near Upper Band)",
        # ADX
        "adx_bullish": "Bullish (Strong Trend ADX={adx:.1f})",
        "adx_bearish": "Bearish (Strong Trend ADX={adx:.1f})",
        "adx_slightly_bullish": "Slightly Bullish (Trend Forming ADX={adx:.1f})",
        "adx_slightly_bearish": "Slightly Bearish (Trend Forming ADX={adx:.1f})",
        "adx_oscillating": "Ranging (No Clear Trend ADX={adx:.1f})",
        # Candlestick simple
        "k_slightly_bullish": "Slightly Bullish (Oversold Support)",
        "k_slightly_bearish": "Slightly Bearish (Overbought Pressure)",
    },
}

# Advice
ADVICE = {
    "zh": {
        "strong_bullish": "看多（多指标共振看多, 建议持仓或轻仓试多）",
        "bullish": "偏多（部分指标看多, 可小仓位试探）",
        "strong_bearish": "看空（多指标共振看空, 可考虑减仓, 空仓者勿追高）",
        "bearish": "偏空（部分指标看空, 建议谨慎观望）",
        "neutral": "观望（信号混乱, 等待明确方向）",
    },
    "en": {
        "strong_bullish": "Bullish (Multiple indicators align bullish, hold or add position)",
        "bullish": "Slightly Bullish (Some indicators bullish, try small position)",
        "strong_bearish": "Bearish (Multiple indicators align bearish, consider reducing position)",
        "bearish": "Slightly Bearish (Some indicators bearish, stay cautious)",
        "neutral": "Wait and See (Mixed signals, wait for clear direction)",
    },
}

# Warning
WARNING = {
    "zh": "本分析基于历史数据，不构成投资建议。",
    "en": "This analysis is based on historical data and does not constitute investment advice.",
}

# Candlestick pattern names
PATTERN_NAMES = {
    "zh": {
        "doji": "十字星",
        "hammer": "锤子线",
        "inverted_hammer": "倒锤子线",
        "hanging_man": "上吊线",
        "shooting_star": "射击之星",
        "bullish_engulfing": "看涨吞没",
        "bearish_engulfing": "看跌吞没",
        "morning_star": "启明星",
        "evening_star": "黄昏星",
        "three_black_crows": "三只乌鸦",
        "three_white_soldiers": "三个白武士",
        "dark_cloud_cover": "乌云盖顶",
        "piercing": "刺透形态",
        "harami": "孕线",
        "tweezers_bottom": "平底",
        "tweezers_top": "平顶",
    },
    "en": {
        "doji": "Doji",
        "hammer": "Hammer",
        "inverted_hammer": "Inverted Hammer",
        "hanging_man": "Hanging Man",
        "shooting_star": "Shooting Star",
        "bullish_engulfing": "Bullish Engulfing",
        "bearish_engulfing": "Bearish Engulfing",
        "morning_star": "Morning Star",
        "evening_star": "Evening Star",
        "three_black_crows": "Three Black Crows",
        "three_white_soldiers": "Three White Soldiers",
        "dark_cloud_cover": "Dark Cloud Cover",
        "piercing": "Piercing Pattern",
        "harami": "Harami",
        "tweezers_bottom": "Tweezers Bottom",
        "tweezers_top": "Tweezers Top",
    },
}

# Candlestick pattern signals
PATTERN_SIGNALS = {
    "zh": {
        "doji_bullish": "看多（十字星-底部反转）",
        "doji_bearish": "看空（十字星-顶部反转）",
        "doji_neutral": "中性（十字星-变盘）",
        "hammer_bullish": "看多（锤子线-反转）",
        "inverted_hammer_bullish": "看多（倒锤子-反转）",
        "hanging_man_bearish": "看空（上吊线-反转）",
        "shooting_star_bearish": "看空（射击之星-反转）",
        "bullish_engulfing": "看多（看涨吞没）",
        "bearish_engulfing": "看空（看跌吞没）",
        "morning_star_bullish": "看多（启明星-反转）",
        "evening_star_bearish": "看空（黄昏星-反转）",
        "three_black_crows": "看空（三只乌鸦）",
        "three_white_soldiers": "看多（三个白武士）",
        "dark_cloud_cover": "看空（乌云盖顶-反转）",
        "piercing_bullish": "看多（刺透形态-反转）",
        "harami_bullish": "看多（孕线-底部反转）",
        "harami_bearish": "看空（孕线-顶部反转）",
        "harami_neutral": "中性（孕线-变盘）",
        "tweezers_bullish": "看多（平底-支撑确认）",
        "tweezers_bearish": "看空（平顶-阻力确认）",
    },
    "en": {
        "doji_bullish": "Bullish (Doji - Bottom Reversal)",
        "doji_bearish": "Bearish (Doji - Top Reversal)",
        "doji_neutral": "Neutral (Doji - Potential Reversal)",
        "hammer_bullish": "Bullish (Hammer - Reversal)",
        "inverted_hammer_bullish": "Bullish (Inverted Hammer - Reversal)",
        "hanging_man_bearish": "Bearish (Hanging Man - Reversal)",
        "shooting_star_bearish": "Bearish (Shooting Star - Reversal)",
        "bullish_engulfing": "Bullish (Bullish Engulfing)",
        "bearish_engulfing": "Bearish (Bearish Engulfing)",
        "morning_star_bullish": "Bullish (Morning Star - Reversal)",
        "evening_star_bearish": "Bearish (Evening Star - Reversal)",
        "three_black_crows": "Bearish (Three Black Crows)",
        "three_white_soldiers": "Bullish (Three White Soldiers)",
        "dark_cloud_cover": "Bearish (Dark Cloud Cover - Reversal)",
        "piercing_bullish": "Bullish (Piercing Pattern - Reversal)",
        "harami_bullish": "Bullish (Harami - Bottom Reversal)",
        "harami_bearish": "Bearish (Harami - Top Reversal)",
        "harami_neutral": "Neutral (Harami - Potential Reversal)",
        "tweezers_bullish": "Bullish (Tweezers Bottom - Support)",
        "tweezers_bearish": "Bearish (Tweezers Top - Resistance)",
    },
}

# Candlestick pattern descriptions
PATTERN_DESCRIPTIONS = {
    "zh": {
        "doji_bottom": "实体极小的K线，出现在低位可能是底部反转信号",
        "doji_top": "实体极小的K线，出现在高位可能是顶部反转信号",
        "doji_neutral": "实体极小的K线，表示多空力量平衡，可能出现变盘",
        "hammer": "下影线长、上影线短的阳线，出现在下跌后是强烈的底部反转信号",
        "inverted_hammer": "上影线长、下影线短的阳线，出现在下跌后暗示买方试探性反攻",
        "hanging_man": "下影线长的阴线，出现在上涨后的高位，是顶部反转警告信号",
        "shooting_star": "上影线长的阴线，出现在高位表示上方抛压沉重，可能反转下跌",
        "bullish_engulfing": "大阳线完全吞没前一根阴线，是强烈的底部反转信号",
        "bearish_engulfing": "大阴线完全吞没前一根阳线，是强烈的顶部反转信号",
        "morning_star": "三根K线组合：大阴线+小实体+大阳线，是经典的底部反转形态",
        "evening_star": "三根K线组合：大阳线+小实体+大阴线，是经典的顶部反转形态",
        "three_black_crows": "连续三根大阴线且逐步走低，是强烈的下跌趋势延续信号",
        "three_white_soldiers": "连续三根大阳线且逐步走高，是强烈的上涨趋势延续信号",
        "dark_cloud_cover": "阴线深入前一根阳线50%以上，出现在高位是顶部反转信号",
        "piercing": "阳线深入前一根阴线50%以上，出现在低位是底部反转信号",
        "harami_bottom": "小K线被前一根大K线完全包含，出现在低位可能反转上涨",
        "harami_top": "小K线被前一根大K线完全包含，出现在高位可能反转下跌",
        "harami_neutral": "小K线被前一根大K线完全包含，表示趋势减弱，可能变盘",
        "tweezers_bottom": "两根K线最低价相同，表示该价位有强支撑，可能反弹",
        "tweezers_top": "两根K线最高价相同，表示该价位有强阻力，可能回落",
    },
    "en": {
        "doji_bottom": "Very small body candle at low levels - potential bottom reversal signal",
        "doji_top": "Very small body candle at high levels - potential top reversal signal",
        "doji_neutral": "Very small body candle indicating balance between bulls and bears - potential reversal",
        "hammer": "Long lower shadow, short upper shadow bullish candle after a decline - strong bottom reversal",
        "inverted_hammer": "Long upper shadow, short lower shadow bullish candle after decline - buyers testing",
        "hanging_man": "Long lower shadow bearish candle at highs after uptrend - top reversal warning",
        "shooting_star": "Long upper shadow bearish candle at highs - heavy selling pressure, possible reversal",
        "bullish_engulfing": "Large bullish candle fully engulfs prior bearish candle - strong bottom reversal",
        "bearish_engulfing": "Large bearish candle fully engulfs prior bullish candle - strong top reversal",
        "morning_star": "Three-candle pattern: large bearish + small body + large bullish - classic bottom reversal",
        "evening_star": "Three-candle pattern: large bullish + small body + large bearish - classic top reversal",
        "three_black_crows": "Three consecutive large bearish candles trending lower - strong downtrend continuation",
        "three_white_soldiers": "Three consecutive large bullish candles trending higher - strong uptrend continuation",
        "dark_cloud_cover": "Bearish candle penetrates 50%+ of prior bullish candle at highs - top reversal",
        "piercing": "Bullish candle penetrates 50%+ of prior bearish candle at lows - bottom reversal",
        "harami_bottom": "Small candle contained within prior large candle at lows - potential bullish reversal",
        "harami_top": "Small candle contained within prior large candle at highs - potential bearish reversal",
        "harami_neutral": "Small candle contained within prior large candle - trend weakening, potential reversal",
        "tweezers_bottom": "Two candles with same low price - strong support at this level, possible bounce",
        "tweezers_top": "Two candles with same high price - strong resistance at this level, possible pullback",
    },
}

# Patterns checked list
PATTERNS_CHECKED = {
    "zh": [
        "十字星（Doji）", "锤子线（Hammer）", "倒锤子线（Inverted Hammer）",
        "上吊线（Hanging Man）", "射击之星（Shooting Star）",
        "看涨吞没（Bullish Engulfing）", "看跌吞没（Bearish Engulfing）",
        "启明星（Morning Star）", "黄昏星（Evening Star）",
        "三只乌鸦（Three Black Crows）", "三个白武士（Three White Soldiers）",
        "乌云盖顶（Dark Cloud Cover）", "刺透形态（Piercing Pattern）",
        "孕线形态（Harami）", "平底/平顶（Tweezers）",
    ],
    "en": [
        "Doji", "Hammer", "Inverted Hammer",
        "Hanging Man", "Shooting Star",
        "Bullish Engulfing", "Bearish Engulfing",
        "Morning Star", "Evening Star",
        "Three Black Crows", "Three White Soldiers",
        "Dark Cloud Cover", "Piercing Pattern",
        "Harami", "Tweezers",
    ],
}

# Error messages
ERRORS = {
    "zh": {
        "no_data": "未获取到数据，请检查股票代码是否正确: {ticker}",
        "calc_failed": "计算技术指标失败: {error}",
        "a_share_no_options": "A股（沪深）不支持期权Wheel策略",
        "no_options": "{ticker} 没有可交易的期权，无法执行Wheel策略",
        "no_ticker_data": "无法获取 {ticker} 数据，请检查代码或网络连接",
    },
    "en": {
        "no_data": "No data found. Please check the ticker symbol: {ticker}",
        "calc_failed": "Failed to calculate technical indicators: {error}",
        "a_share_no_options": "A-shares (Shanghai/Shenzhen) do not support options Wheel strategy",
        "no_options": "{ticker} has no tradeable options for Wheel strategy",
        "no_ticker_data": "Cannot fetch data for {ticker}. Please check the ticker or network connection",
    },
}

# Wheel strategy - Sell Put
WHEEL_PUT = {
    "zh": {
        "danger_label": "危险：下降趋势 (Falling Knife)",
        "danger_reason": "20日EMA近5天下跌{ema_trend:.1f}%，处于下降趋势中，此时卖Put容易被assign后继续亏损，应等趋势企稳。",
        "caution_label": "谨慎观望 (Caution)",
        "caution_reason": "EMA走平偏弱，股价偏离EMA达{price_vs_ema:.1f}%，不排除趋势转弱的可能，如需卖Put建议极低strike小仓位试探。",
        "great_label": "极佳建仓期 (Great Opportunity)",
        "great_reason_pullback": "{ticker} 处于上升趋势中的回调（EMA仍在走高+{ema_trend:.1f}%），股价短暂跌破EMA，恐慌推高Put权利金，正是卖Put的黄金窗口！",
        "great_reason_washout": "{ticker} 上升趋势中遭遇日内剧烈洗盘(>{intra_drop:.1f}%)，IV飙升，时间价值极肥！",
        "acceptable_label": "可考虑建仓 (Acceptable)",
        "acceptable_reason": "股价接近EMA且有一定回调，趋势尚未走坏，可小仓位试探性卖Put。",
        "wait_label": "观望等待 (Wait for Dip)",
        "wait_reason": "当前远离支撑位或趋势不明朗，建议等回调到EMA附近再卖Put。",
    },
    "en": {
        "danger_label": "Danger: Falling Knife",
        "danger_reason": "20-day EMA down {ema_trend:.1f}% over 5 days, in a downtrend. Selling puts risks assignment and further losses. Wait for stabilization.",
        "caution_label": "Caution: Wait and Watch",
        "caution_reason": "EMA flat/weak, price deviates {price_vs_ema:.1f}% from EMA. Trend may be weakening. If selling puts, use very low strike with small position.",
        "great_label": "Great Opportunity",
        "great_reason_pullback": "{ticker} pulling back in an uptrend (EMA still rising +{ema_trend:.1f}%). Price briefly below EMA, panic inflating put premium - golden window for selling puts!",
        "great_reason_washout": "{ticker} experienced sharp intraday washout (>{intra_drop:.1f}%) in uptrend. IV spiking, rich time value!",
        "acceptable_label": "Acceptable Entry",
        "acceptable_reason": "Price near EMA with some pullback, trend still intact. Can try selling puts with small position.",
        "wait_label": "Wait for Dip",
        "wait_reason": "Currently far from support or unclear trend direction. Wait for pullback to EMA before selling puts.",
    },
}

# Wheel strategy - Covered Call
WHEEL_CALL = {
    "zh": {
        "underwater_label": "深度套牢，不建议卖Call (Deep Underwater)",
        "underwater_reason": "当前价 ${price:.2f} 低于成本 ${cost:.2f} 达 {pct:.1f}%，套牢过深，卖Call权利金微薄且会锁死反弹空间，建议等待大幅反弹后再考虑。",
        "moderate_underwater_label": "轻度套牢但可收租 (Sell Above Cost)",
        "moderate_underwater_reason": "当前价 ${price:.2f} 低于成本 {pct:.1f}%，但股价站上EMA且有反弹动能，可在成本之上 ${strike} 卖Call——即使被行权也不亏损，还赚权利金。",
        "caution_underwater_label": "轻度套牢，谨慎卖Call (Caution)",
        "caution_underwater_reason": "当前价 ${price:.2f} 低于成本 {pct:.1f}%，可小仓位在成本之上 ${strike} 卖Call收时间价值，但注意不要锁死反弹空间，建议卖远期或少量合约。",
        "hold_label": "暂时忍耐 (Hold Shares)",
        "hold_reason_pullback": "股价低于20日EMA（偏离{deviation:.1f}%），正处于回调阶段，此时卖Call会锁死反弹空间，应等待股价重回EMA上方再考虑。",
        "great_label": "绝佳收租期 (High Premium)",
        "great_reason_v": "{ticker} 强势V型反转且站稳EMA上方，IV拉升，Call权利金丰厚！",
        "great_reason_surge": "{ticker} 单日暴涨 {change:.1f}%，高于EMA，适合高位卖出Covered Call！",
        "moderate_label": "可以收租 (Moderate Premium)",
        "moderate_reason": "股价站上EMA且有涨幅，Call权利金尚可，可适量卖出。",
        "hold_reason_no_spike": "当前未出现明显冲高，或股价尚未站稳EMA上方，卖Call时机不成熟。",
    },
    "en": {
        "underwater_label": "Deep Underwater - Do Not Sell Calls",
        "underwater_reason": "Price ${price:.2f} is {pct:.1f}% below cost ${cost:.2f}. Too deep underwater, call premium too thin and locks upside. Wait for significant recovery.",
        "moderate_underwater_label": "Lightly Underwater - Sell Above Cost",
        "moderate_underwater_reason": "Price ${price:.2f} is {pct:.1f}% below cost, but above EMA with bounce momentum. Sell call at ${strike} above cost - even if assigned, no loss plus premium earned.",
        "caution_underwater_label": "Lightly Underwater - Cautious",
        "caution_underwater_reason": "Price ${price:.2f} is {pct:.1f}% below cost. Can sell small call position at ${strike} above cost for time value, but avoid locking upside. Consider far-dated or few contracts.",
        "hold_label": "Hold Shares - Wait",
        "hold_reason_pullback": "Price below 20-day EMA (deviation {deviation:.1f}%), in pullback phase. Selling calls now locks recovery upside. Wait for price above EMA.",
        "great_label": "Great Premium Collection Period",
        "great_reason_v": "{ticker} strong V-shaped reversal and stable above EMA. IV elevated, rich call premium!",
        "great_reason_surge": "{ticker} surged {change:.1f}% today, above EMA. Ideal for selling covered calls at high levels!",
        "moderate_label": "Moderate Premium - Can Collect",
        "moderate_reason": "Price above EMA with gains. Call premium acceptable, can sell moderate amount.",
        "hold_reason_no_spike": "No significant spike or price not stable above EMA. Timing not ideal for selling calls.",
    },
}
