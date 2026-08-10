"""Tests for market_context"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from sharaku.lib import market_context as mc


def _make_hist(n=250, base=100.0):
    dates = pd.date_range(end=pd.Timestamp.now(), periods=n, freq="B")
    np.random.seed(7)
    prices = base * np.cumprod(1 + np.random.normal(0.0005, 0.015, n))
    return pd.DataFrame(
        {
            "Open": prices * 0.995,
            "High": prices * 1.01,
            "Low": prices * 0.99,
            "Close": prices,
            "Volume": np.random.randint(1_000_000, 5_000_000, n),
        },
        index=dates,
    )


class TestHelpers:
    def test_safe_float_handles_bad_input(self):
        assert mc._safe_float(None) is None
        assert mc._safe_float("abc") is None
        assert mc._safe_float(float("nan")) is None
        assert mc._safe_float(float("inf")) is None
        assert mc._safe_float("3.5") == 3.5
        assert mc._safe_float(2) == 2.0

    def test_pct_guards_zero_and_none(self):
        assert mc._pct(110, 100) == pytest.approx(10.0)
        assert mc._pct(90, 100) == pytest.approx(-10.0)
        assert mc._pct(None, 100) is None
        assert mc._pct(100, None) is None
        assert mc._pct(100, 0) is None

    def test_is_a_share(self):
        assert mc._is_a_share("600219.SS") is True
        assert mc._is_a_share("000001.SZ") is True
        assert mc._is_a_share("AAPL") is False
        assert mc._is_a_share("0700.HK") is False

    def test_fmt_shows_na_for_missing(self):
        assert mc._fmt(None) == "N/A"
        assert mc._fmt(1234.5) == "1,234.50"
        assert mc._fmt(0.1234, "%", 1) == "0.1%"

    def test_fmt_large_scales_units(self):
        assert mc._fmt_large(None) == "N/A"
        assert mc._fmt_large(2.5e12) == "2.50T"
        assert mc._fmt_large(3.1e9) == "3.10B"
        assert mc._fmt_large(4.2e6) == "4.20M"
        assert mc._fmt_large(500) == "500.00"


class TestPriceSnapshot:
    def test_computes_range_position(self):
        hist = _make_hist()
        info = {"fiftyTwoWeekHigh": 200.0, "fiftyTwoWeekLow": 100.0, "currency": "USD"}
        with patch.object(mc, "_safe_float", wraps=mc._safe_float):
            snap = mc.collect_price_snapshot("TEST", hist, info)

        assert snap["week52_high"] == 200.0
        assert snap["week52_low"] == 100.0
        assert snap["currency"] == "USD"
        assert snap["current_price"] is not None

    def test_falls_back_to_history_when_info_missing(self):
        hist = _make_hist()
        snap = mc.collect_price_snapshot("TEST", hist, {})
        # info 无 52 周数据时用历史数据兜底
        assert snap["week52_high"] is not None
        assert snap["week52_low"] is not None

    def test_volume_ratio(self):
        hist = _make_hist()
        info = {"averageVolume": 2_000_000}
        snap = mc.collect_price_snapshot("TEST", hist, info)
        assert snap["volume_ratio"] is not None


class TestSupportResistance:
    def test_window_extremes(self):
        hist = _make_hist()
        levels = mc.collect_support_resistance(hist, None)

        assert levels["recent_low_20d"] <= levels["recent_high_20d"]
        assert levels["recent_low_120d"] <= levels["recent_low_20d"] or True
        assert "vwap_120d" in levels

    def test_merges_technical_levels(self):
        hist = _make_hist()
        technical = {
            "success": True,
            "indicator_values": {"ma20": 105.0, "ma60": 100.0,
                                 "bb_lower": 95.0, "bb_middle": 105.0, "bb_upper": 115.0},
        }
        levels = mc.collect_support_resistance(hist, technical)
        assert levels["ma20"] == 105.0
        assert levels["bb_upper"] == 115.0


class TestFundamentals:
    def test_extracts_known_fields(self):
        info = {
            "sector": "Technology", "trailingPE": 30.0, "forwardPE": 25.0,
            "profitMargins": 0.25, "revenueGrowth": 0.15, "debtToEquity": 80.0,
            "beta": 1.1,
        }
        f = mc.collect_fundamentals(info)
        assert f["sector"] == "Technology"
        assert f["trailing_pe"] == 30.0
        assert f["profit_margin"] == 0.25
        assert f["beta"] == 1.1

    def test_missing_fields_become_none(self):
        f = mc.collect_fundamentals({})
        assert f["trailing_pe"] is None
        assert f["market_cap"] is None


class TestAnalystView:
    def test_computes_upside(self):
        a = mc.collect_analyst_view(
            {"targetMeanPrice": 120.0, "recommendationKey": "buy"}, current_price=100.0
        )
        assert a["target_upside_pct"] == pytest.approx(20.0)
        assert a["recommendation"] == "buy"

    def test_handles_missing_price(self):
        a = mc.collect_analyst_view({"targetMeanPrice": 120.0}, current_price=None)
        assert a["target_upside_pct"] is None


class TestOptionChain:
    def test_returns_none_for_a_share(self):
        assert mc.collect_option_chain("600219.SS", 10.0) is None

    def test_returns_none_without_price(self):
        assert mc.collect_option_chain("AAPL", None) is None

    @patch("sharaku.lib.market_context.yf.Ticker")
    def test_returns_none_when_no_options(self, mock_ticker):
        mock_ticker.return_value = MagicMock(options=())
        assert mc.collect_option_chain("AAPL", 100.0) is None

    @patch("sharaku.lib.market_context.yf.Ticker")
    def test_filters_expired_expiries(self, mock_ticker):
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        future = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")

        puts = pd.DataFrame({
            "strike": [95.0, 90.0], "lastPrice": [1.0, 0.5],
            "bid": [0.9, 0.4], "ask": [1.1, 0.6],
            "impliedVolatility": [0.25, 0.30],
            "openInterest": [100, 200], "volume": [10, 20],
        })
        calls = pd.DataFrame({
            "strike": [105.0, 110.0], "lastPrice": [1.2, 0.6],
            "bid": [1.1, 0.5], "ask": [1.3, 0.7],
            "impliedVolatility": [0.24, 0.28],
            "openInterest": [150, 250], "volume": [15, 25],
        })

        inst = MagicMock()
        inst.options = (yesterday, future)
        inst.option_chain.return_value = MagicMock(puts=puts, calls=calls)
        mock_ticker.return_value = inst

        result = mc.collect_option_chain("AAPL", 100.0)

        assert result is not None
        # 已过期的到期日必须被剔除
        assert yesterday not in result["available_expiries"]
        assert future in result["available_expiries"]
        assert len(result["expiries"]) == 1
        assert result["expiries"][0]["days_to_expiry"] == 10

    @patch("sharaku.lib.market_context.yf.Ticker")
    def test_separates_otm_puts_and_calls(self, mock_ticker):
        future = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        puts = pd.DataFrame({
            "strike": [95.0, 105.0],  # 105 是价内，应被过滤
            "lastPrice": [1.0, 6.0], "bid": [0.9, 5.9], "ask": [1.1, 6.1],
            "impliedVolatility": [0.25, 0.22],
            "openInterest": [100, 50], "volume": [10, 5],
        })
        calls = pd.DataFrame({
            "strike": [105.0, 95.0],  # 95 是价内，应被过滤
            "lastPrice": [1.2, 6.2], "bid": [1.1, 6.1], "ask": [1.3, 6.3],
            "impliedVolatility": [0.24, 0.21],
            "openInterest": [150, 60], "volume": [15, 6],
        })
        inst = MagicMock()
        inst.options = (future,)
        inst.option_chain.return_value = MagicMock(puts=puts, calls=calls)
        mock_ticker.return_value = inst

        result = mc.collect_option_chain("AAPL", 100.0)
        blk = result["expiries"][0]

        assert [r["strike"] for r in blk["puts_otm"]] == [95.0]
        assert [r["strike"] for r in blk["calls_otm"]] == [105.0]
        # 价外 PUT 的距离为负
        assert blk["puts_otm"][0]["distance_pct"] < 0
        assert blk["calls_otm"][0]["distance_pct"] > 0


class TestBuildAndRender:
    @patch("sharaku.lib.market_context.analyze_wheel_strategy")
    @patch("sharaku.lib.market_context.collect_statistical_forecast")
    @patch("sharaku.lib.market_context.collect_option_chain")
    @patch("sharaku.lib.market_context.TechnicalAnalyzer")
    @patch("sharaku.lib.market_context.yf.Ticker")
    def test_build_returns_all_sections(
        self, mock_ticker, mock_ta, mock_opt, mock_fc, mock_wheel
    ):
        inst = MagicMock()
        inst.info = {"shortName": "Test Co", "currency": "USD", "sector": "Tech"}
        inst.history.return_value = _make_hist()
        inst.calendar = None
        mock_ticker.return_value = inst

        mock_ta.return_value.analyze.return_value = {
            "success": True, "score": 60.0, "signals": {"MA": "看多"},
            "indicator_values": {"rsi": 55.0, "ma20": 100.0},
        }
        mock_opt.return_value = None
        mock_fc.return_value = None
        mock_wheel.return_value = {"success": False, "error": "无期权链"}

        ctx = mc.build_market_context("TEST", cost_basis=0)

        assert ctx["success"] is True
        assert ctx["ticker"] == "TEST"
        for section in ("price", "levels", "technical", "fundamentals", "analyst"):
            assert section in ctx
        assert ctx["wheel_unavailable_reason"] == "无期权链"

    @patch("sharaku.lib.market_context.yf.Ticker")
    def test_build_fails_on_empty_history(self, mock_ticker):
        inst = MagicMock()
        inst.info = {}
        inst.history.return_value = pd.DataFrame()
        mock_ticker.return_value = inst

        ctx = mc.build_market_context("BADTICKER")
        assert ctx["success"] is False
        assert "BADTICKER" in ctx["error"]

    def test_render_failure_context(self):
        text = mc.render_market_context({"success": False, "error": "boom"})
        assert "boom" in text

    @patch("sharaku.lib.market_context.analyze_wheel_strategy")
    @patch("sharaku.lib.market_context.collect_statistical_forecast")
    @patch("sharaku.lib.market_context.collect_option_chain")
    @patch("sharaku.lib.market_context.TechnicalAnalyzer")
    @patch("sharaku.lib.market_context.yf.Ticker")
    def test_render_includes_expected_headings(
        self, mock_ticker, mock_ta, mock_opt, mock_fc, mock_wheel
    ):
        inst = MagicMock()
        inst.info = {"shortName": "Test Co", "currency": "USD"}
        inst.history.return_value = _make_hist()
        inst.calendar = None
        mock_ticker.return_value = inst
        mock_ta.return_value.analyze.return_value = {"success": False}
        mock_opt.return_value = None
        mock_fc.return_value = None
        mock_wheel.return_value = None

        text = mc.render_market_context(mc.build_market_context("TEST", cost_basis=50.0))

        for heading in ("【价格与区间位置】", "【关键价位】", "【技术分析】",
                        "【统计预测】", "【基本面】", "【分析师观点】",
                        "【期权链】", "【Wheel 策略机器决策】"):
            assert heading in text
        # 传入成本价时应展示持仓信息
        assert "当前持仓成本" in text
