"""Tests for MonteCarloPredictor"""

import numpy as np
import pandas as pd
import pytest

from sharaku.lib.monte_carlo_predictor import MonteCarloPredictor


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


class TestMonteCarloPredictor:
    def test_init(self):
        p = MonteCarloPredictor("TSLA")
        assert p.ticker == "TSLA"
        assert p.is_fitted is False

    def test_fit(self):
        data = make_stock_data()
        p = MonteCarloPredictor("TSLA")
        p.fit(data)

        assert p.is_fitted is True
        assert p.current_price is not None
        assert p.mu_daily is not None
        assert p.sigma_daily is not None

    def test_predict_not_fitted(self):
        p = MonteCarloPredictor("TSLA")
        with pytest.raises(ValueError, match="must be fitted"):
            p.predict(30)

    def test_predict(self):
        data = make_stock_data()
        p = MonteCarloPredictor("TSLA")
        p.fit(data)

        result = p.predict(days=30, n_paths=500)

        assert "price_paths" in result
        assert "final_prices" in result
        assert result["price_paths"].shape == (500, 31)  # n_paths x (days + 1)
        assert len(result["final_prices"]) == 500
        assert result["n_paths"] == 500
        assert result["n_days"] == 30
        assert all(result["final_prices"] > 0)

    def test_predict_reproducibility(self):
        data = make_stock_data()
        p = MonteCarloPredictor("TSLA")
        p.fit(data)

        r1 = p.predict(days=10, n_paths=100, seed=42)
        r2 = p.predict(days=10, n_paths=100, seed=42)

        np.testing.assert_array_equal(r1["final_prices"], r2["final_prices"])

    def test_analyze_risk(self):
        data = make_stock_data()
        p = MonteCarloPredictor("TSLA")
        p.fit(data)
        predictions = p.predict(days=30, n_paths=1000)
        risk = p.analyze_risk(predictions)

        assert "mean_price" in risk
        assert "median_price" in risk
        assert "VaR_95" in risk
        assert "CVaR_95" in risk
        assert risk["VaR_95"] < 0  # VaR should typically be negative
        assert risk["CVaR_95"] <= risk["VaR_95"]  # CVaR <= VaR
        assert risk["price_percentile_5"] < risk["price_percentile_95"]

    def test_price_floor(self):
        data = make_stock_data()
        p = MonteCarloPredictor("TSLA")
        p.fit(data)

        # Even with extreme simulation, prices should not go below floor
        result = p.predict(days=252, n_paths=100)
        price_floor = max(0.10, p.current_price * 0.05)
        assert all(result["price_paths"].flatten() >= price_floor)

    def test_get_model_summary(self):
        data = make_stock_data()
        p = MonteCarloPredictor("TSLA")
        p.fit(data)
        summary = p.get_model_summary()

        assert "model_info" in summary
        assert "parameters" in summary
        assert summary["parameters"]["mu_daily"] is not None
        assert summary["parameters"]["sigma_daily"] is not None
