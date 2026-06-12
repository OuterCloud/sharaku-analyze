"""
Monte Carlo Predictor for Stock Price Analysis

Uses geometric Brownian motion (GBM) with vectorized simulations.
"""

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .base_predictor import BasePredictor
from .data_utils import DataUtils


class MonteCarloPredictor(BasePredictor):
    """
    Monte Carlo stock price predictor using geometric Brownian motion.
    """

    TRADING_DAYS_PER_YEAR = 252

    def __init__(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ):
        super().__init__(ticker, start_date, end_date)

        self.mu_daily: Optional[float] = None
        self.sigma_daily: Optional[float] = None
        self.current_price: Optional[float] = None

        self.data_utils = DataUtils()

    def fit(self, data: Optional[pd.DataFrame] = None) -> "MonteCarloPredictor":
        if data is not None:
            self.validate_data(data)
            prepared_data = self._prepare_data_from_df(data)
        else:
            prepared_data = self.data_utils.prepare_model_data(
                self.ticker, self.start_date, self.end_date
            )

        self.data = prepared_data["raw_data"]
        self.close_prices = prepared_data["close_prices"]
        self.returns = prepared_data["log_returns"]

        self.mu_daily = float(self.returns.mean())
        self.sigma_daily = float(self.returns.std())
        self.current_price = float(self.close_prices.iloc[-1])

        self.is_fitted = True
        return self

    def predict(
        self, days: int, n_paths: int = 10000, seed: int = 42
    ) -> Dict[str, np.ndarray]:
        if not self.is_fitted:
            raise ValueError("Model must be fitted before making predictions")

        price_paths = self._simulate_price_paths(n_paths, days, seed)

        return {
            "price_paths": price_paths,
            "final_prices": price_paths[:, -1],
            "n_paths": n_paths,
            "n_days": days,
            "current_price": self.current_price,
        }

    def analyze_risk(
        self, predictions: Dict, confidence_levels: List[float] = None
    ) -> Dict[str, float]:
        if confidence_levels is None:
            confidence_levels = [0.05, 0.25, 0.5, 0.75, 0.95]

        final_prices = predictions["final_prices"]
        current_price = predictions["current_price"]

        returns_pct = (final_prices / current_price - 1) * 100

        results = {
            "mean_price": float(np.mean(final_prices)),
            "median_price": float(np.median(final_prices)),
            "std_price": float(np.std(final_prices)),
            "min_price": float(np.min(final_prices)),
            "max_price": float(np.max(final_prices)),
            "mean_return": float(np.mean(returns_pct)),
            "median_return": float(np.median(returns_pct)),
            "std_return": float(np.std(returns_pct)),
            "min_return": float(np.min(returns_pct)),
            "max_return": float(np.max(returns_pct)),
        }

        for level in confidence_levels:
            price_percentile = np.percentile(final_prices, level * 100)
            return_percentile = np.percentile(returns_pct, level * 100)
            results[f"price_percentile_{int(level * 100)}"] = float(price_percentile)
            results[f"return_percentile_{int(level * 100)}"] = float(return_percentile)

        # VaR and CVaR
        var_95 = np.percentile(returns_pct, 5)
        cvar_95 = np.mean(returns_pct[returns_pct <= var_95])

        results["VaR_95"] = float(var_95)
        results["CVaR_95"] = float(cvar_95)

        return results

    def get_model_summary(self) -> Dict:
        if not self.is_fitted:
            return {"error": "Model not fitted"}

        return {
            "model_info": self.get_model_info(),
            "parameters": {
                "mu_daily": self.mu_daily,
                "sigma_daily": self.sigma_daily,
                "mu_annual": self.mu_daily * self.TRADING_DAYS_PER_YEAR,
                "sigma_annual": self.sigma_daily * np.sqrt(self.TRADING_DAYS_PER_YEAR),
                "current_price": self.current_price,
            },
            "data_info": {
                "data_points": len(self.close_prices),
                "date_range": f"{self.close_prices.index[0].strftime('%Y-%m-%d')} to {self.close_prices.index[-1].strftime('%Y-%m-%d')}",
            },
        }

    def _simulate_price_paths(self, n_paths: int, n_days: int, seed: int) -> np.ndarray:
        np.random.seed(seed)

        mu_annual = self.mu_daily * self.TRADING_DAYS_PER_YEAR
        sigma_annual = self.sigma_daily * np.sqrt(self.TRADING_DAYS_PER_YEAR)
        dt = 1.0 / self.TRADING_DAYS_PER_YEAR

        Z = np.random.standard_normal((n_paths, n_days))

        dlnS = (mu_annual - 0.5 * sigma_annual**2) * dt + sigma_annual * np.sqrt(dt) * Z

        lnS_paths = np.cumsum(dlnS, axis=1)
        lnS_paths = np.column_stack([np.zeros(n_paths), lnS_paths]) + np.log(
            self.current_price
        )
        price_paths = np.exp(lnS_paths)

        price_floor = max(0.10, self.current_price * 0.05)
        price_paths = np.maximum(price_paths, price_floor)

        return price_paths

    def _prepare_data_from_df(self, data: pd.DataFrame) -> Dict:
        close_prices = self.data_utils.extract_close_prices(data)
        log_returns = self.data_utils.calculate_returns(close_prices, "log")
        statistics = self.data_utils.get_basic_statistics(close_prices, log_returns)

        return {
            "raw_data": data,
            "close_prices": close_prices,
            "log_returns": log_returns,
            "statistics": statistics,
            "ticker": self.ticker,
        }
