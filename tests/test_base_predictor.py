"""Tests for BasePredictor"""

import numpy as np
import pandas as pd
import pytest

from sharaku.lib.base_predictor import BasePredictor


class ConcretePredictor(BasePredictor):
    """Concrete implementation for testing."""

    def fit(self, data=None):
        self.is_fitted = True
        return self

    def predict(self, days, **kwargs):
        return {"prices": np.array([100.0] * days)}

    def analyze_risk(self, predictions):
        return {"risk": 0.5}


class TestBasePredictor:
    def test_init(self):
        p = ConcretePredictor("aapl", "2023-01-01", "2024-01-01")
        assert p.ticker == "AAPL"
        assert p.start_date == "2023-01-01"
        assert p.end_date == "2024-01-01"
        assert p.is_fitted is False

    def test_str(self):
        p = ConcretePredictor("TSLA")
        assert "not fitted" in str(p)
        p.fit()
        assert "fitted" in str(p)

    def test_get_model_info(self):
        p = ConcretePredictor("NVDA")
        info = p.get_model_info()
        assert info["ticker"] == "NVDA"
        assert info["model_type"] == "ConcretePredictor"
        assert info["is_fitted"] is False

    def test_validate_data_empty(self):
        p = ConcretePredictor("AAPL")
        with pytest.raises(ValueError, match="输入数据为空"):
            p.validate_data(pd.DataFrame())

    def test_validate_data_too_few(self):
        p = ConcretePredictor("AAPL")
        df = pd.DataFrame({"Close": [1, 2, 3]})
        with pytest.raises(ValueError, match="数据点不足"):
            p.validate_data(df)

    def test_validate_data_ok(self):
        p = ConcretePredictor("AAPL")
        df = pd.DataFrame({"Close": range(20)})
        assert p.validate_data(df) is True

    def test_calculate_returns_log(self):
        p = ConcretePredictor("AAPL")
        prices = pd.Series([100.0, 110.0, 121.0])
        returns = p.calculate_returns(prices, "log")
        assert len(returns) == 2
        assert abs(returns.iloc[0] - np.log(1.1)) < 1e-10

    def test_calculate_returns_simple(self):
        p = ConcretePredictor("AAPL")
        prices = pd.Series([100.0, 110.0, 121.0])
        returns = p.calculate_returns(prices, "simple")
        assert len(returns) == 2
        assert abs(returns.iloc[0] - 0.1) < 1e-10

    def test_calculate_returns_invalid_method(self):
        p = ConcretePredictor("AAPL")
        prices = pd.Series([100.0, 110.0])
        with pytest.raises(ValueError, match="Method must be"):
            p.calculate_returns(prices, "invalid")
