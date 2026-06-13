"""Tests for TechnicalAnalyzer"""

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from sharaku.lib.technical_analyzer import TechnicalAnalyzer


def _make_mock_data(n=120, base_price=150.0):
    """Generate realistic OHLCV data for testing."""
    dates = pd.date_range(end=pd.Timestamp.now(), periods=n, freq="B")
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.02, n)
    prices = base_price * np.cumprod(1 + returns)

    df = pd.DataFrame(
        {
            "Open": prices * (1 + np.random.uniform(-0.005, 0.005, n)),
            "High": prices * (1 + np.random.uniform(0.005, 0.02, n)),
            "Low": prices * (1 - np.random.uniform(0.005, 0.02, n)),
            "Close": prices,
            "Adj Close": prices,
            "Volume": np.random.randint(1_000_000, 50_000_000, n),
        },
        index=dates,
    )
    return df


class TestTechnicalAnalyzer:
    @patch("sharaku.lib.technical_analyzer.yf.download")
    def test_successful_analysis_returns_score(self, mock_download):
        mock_download.return_value = _make_mock_data()
        analyzer = TechnicalAnalyzer("AAPL")
        result = analyzer.analyze()

        assert result["success"] is True
        assert 0 <= result["score"] <= 100
        assert result["ticker"] == "AAPL"
        assert isinstance(result["current_price"], float)

    @patch("sharaku.lib.technical_analyzer.yf.download")
    def test_returns_seven_signals(self, mock_download):
        mock_download.return_value = _make_mock_data()
        analyzer = TechnicalAnalyzer("MSFT")
        result = analyzer.analyze()

        assert result["success"] is True
        signals = result["signals"]
        assert len(signals) == 7
        expected_keys = {"K线", "均线", "MACD", "RSI", "KDJ", "布林带", "ADX"}
        assert set(signals.keys()) == expected_keys

    @patch("sharaku.lib.technical_analyzer.yf.download")
    def test_empty_data_returns_failure(self, mock_download):
        mock_download.return_value = pd.DataFrame()
        analyzer = TechnicalAnalyzer("INVALID")
        result = analyzer.analyze()

        assert result["success"] is False
        assert "error" in result

    @patch("sharaku.lib.technical_analyzer.yf.download")
    def test_multi_market_tickers(self, mock_download):
        mock_download.return_value = _make_mock_data()

        for ticker in ["0700.HK", "7203.T", "005930.KS"]:
            analyzer = TechnicalAnalyzer(ticker)
            result = analyzer.analyze()
            assert result["success"] is True
            assert result["ticker"] == ticker.upper()

    @patch("sharaku.lib.technical_analyzer.yf.download")
    def test_indicator_values_keys(self, mock_download):
        mock_download.return_value = _make_mock_data()
        analyzer = TechnicalAnalyzer("AAPL")
        result = analyzer.analyze()

        assert "indicator_values" in result
        iv = result["indicator_values"]
        expected_keys = {
            "ma5", "ma10", "ma20", "ma60",
            "macd", "macd_signal", "macd_hist",
            "rsi", "k", "d",
            "bb_upper", "bb_middle", "bb_lower",
            "adx", "di_plus", "di_minus",
        }
        assert set(iv.keys()) == expected_keys
        # All values should be numeric
        for key, val in iv.items():
            assert isinstance(val, (int, float)), f"{key} is not numeric: {type(val)}"

    @patch("sharaku.lib.technical_analyzer.yf.download")
    def test_advice_field_present(self, mock_download):
        mock_download.return_value = _make_mock_data()
        analyzer = TechnicalAnalyzer("GOOGL")
        result = analyzer.analyze()

        assert result["success"] is True
        assert "advice" in result
        assert len(result["advice"]) > 0

    @patch("sharaku.lib.technical_analyzer.yf.download")
    def test_candlestick_pattern_or_checked(self, mock_download):
        mock_download.return_value = _make_mock_data()
        analyzer = TechnicalAnalyzer("AAPL")
        result = analyzer.analyze()

        # Either a pattern is detected or patterns_checked list is present
        if result["candlestick_pattern"] is None:
            assert "patterns_checked" in result
            assert len(result["patterns_checked"]) == 15
        else:
            pattern = result["candlestick_pattern"]
            assert "name" in pattern
            assert "description" in pattern
            assert "score" in pattern

    @patch("sharaku.lib.technical_analyzer.yf.download")
    def test_custom_period(self, mock_download):
        mock_download.return_value = _make_mock_data(n=250)
        analyzer = TechnicalAnalyzer("AAPL", period="1y")
        result = analyzer.analyze()

        assert result["success"] is True
        mock_download.assert_called_once_with("AAPL", period="1y", progress=False)
