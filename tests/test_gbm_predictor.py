"""Tests for GBMPredictor"""

import numpy as np
import pandas as pd
import pytest

from sharaku.lib.gbm_predictor import GBMPredictor


def make_stock_data(n=252, start_price=100.0):
    """Generate synthetic stock data for testing."""
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    returns = np.random.normal(0.0005, 0.02, n)
    prices = start_price * np.exp(np.cumsum(returns))
    return pd.DataFrame(
        {"Close": prices, "Open": prices * 0.99, "High": prices * 1.01, "Low": prices * 0.98},
        index=dates,
    )


class TestGBMPredictor:
    def test_init(self):
        p = GBMPredictor("AAPL")
        assert p.ticker == "AAPL"
        assert p.is_fitted is False

    def test_fit(self):
        data = make_stock_data()
        p = GBMPredictor("AAPL")
        p.fit(data)

        assert p.is_fitted is True
        assert p.current_price is not None
        assert p.mu_annual is not None
        assert p.sigma_annual is not None
        assert p.sigma_robust is not None

    def test_predict_not_fitted(self):
        p = GBMPredictor("AAPL")
        with pytest.raises(ValueError, match="must be fitted"):
            p.predict("2025-12-31")

    def test_predict(self):
        data = make_stock_data()
        p = GBMPredictor("AAPL")
        p.fit(data)

        from datetime import datetime, timedelta
        future_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
        result = p.predict(future_date, n_simulations=1000)

        assert "final_prices" in result
        assert len(result["final_prices"]) == 1000
        assert result["current_price"] > 0
        assert result["trading_days"] > 0
        assert all(result["final_prices"] > 0)

    def test_analyze_risk(self):
        data = make_stock_data()
        p = GBMPredictor("AAPL")
        p.fit(data)

        from datetime import datetime, timedelta
        future_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
        predictions = p.predict(future_date, n_simulations=1000)
        risk = p.analyze_risk(predictions)

        assert "mean_price" in risk
        assert "median_price" in risk
        assert "mean_return" in risk
        assert "price_percentile_5" in risk
        assert "price_percentile_95" in risk
        assert risk["price_percentile_5"] < risk["price_percentile_95"]

    def test_scenario_analysis(self):
        from datetime import datetime, timedelta

        data = make_stock_data()
        p = GBMPredictor("AAPL")
        p.fit(data)
        future_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
        scenarios = p.scenario_analysis(future_date, n_simulations=1000)

        assert len(scenarios) == 3  # 基线, 乐观, 保守
        assert "scenario" in scenarios.columns
        assert "mean_price" in scenarios.columns

    def test_get_model_summary_not_fitted(self):
        p = GBMPredictor("AAPL")
        summary = p.get_model_summary()
        assert "error" in summary

    def test_get_model_summary_fitted(self):
        data = make_stock_data()
        p = GBMPredictor("AAPL")
        p.fit(data)
        summary = p.get_model_summary()

        assert "model_info" in summary
        assert "parameters" in summary
        assert "data_info" in summary
