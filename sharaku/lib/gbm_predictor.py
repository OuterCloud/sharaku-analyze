"""
Geometric Brownian Motion (GBM) Predictor for Stock Price Analysis
"""

from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .base_predictor import BasePredictor
from .data_utils import DataUtils


class GBMPredictor(BasePredictor):
    """
    Geometric Brownian Motion stock price predictor.
    """

    def __init__(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ):
        super().__init__(ticker, start_date, end_date)

        self.mu_annual: Optional[float] = None
        self.sigma_annual: Optional[float] = None
        self.sigma_robust: Optional[float] = None
        self.current_price: Optional[float] = None

        self.data_utils = DataUtils()

    def fit(self, data: Optional[pd.DataFrame] = None) -> "GBMPredictor":
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

        mu_daily = float(self.returns.mean())
        sigma_daily = float(self.returns.std())

        self.mu_annual = mu_daily * 252
        self.sigma_annual = sigma_daily * np.sqrt(252)
        self.current_price = float(self.close_prices.iloc[-1])

        # Calculate robust volatility estimate
        returns_clean = self.returns[
            (self.returns > self.returns.quantile(0.025))
            & (self.returns < self.returns.quantile(0.975))
        ]
        sigma_robust_daily = float(returns_clean.std())
        self.sigma_robust = sigma_robust_daily * np.sqrt(252)

        self.is_fitted = True
        return self

    def predict(
        self,
        target_date: str,
        n_simulations: int = 100000,
        use_robust_volatility: bool = True,
        seed: int = 42,
        **kwargs,
    ) -> Dict[str, np.ndarray]:
        if not self.is_fitted:
            raise ValueError("Model must be fitted before making predictions")

        trading_days = self._calculate_trading_days(target_date)
        if trading_days <= 0:
            raise ValueError("Target date must be in the future")

        effective_sigma = (
            self.sigma_robust
            if (use_robust_volatility and self.sigma_annual > 2.0)
            else self.sigma_annual
        )

        final_prices = self._simulate_gbm_endpoints(
            n_simulations, trading_days, effective_sigma, seed
        )

        return {
            "final_prices": final_prices,
            "target_date": target_date,
            "trading_days": trading_days,
            "n_simulations": n_simulations,
            "current_price": self.current_price,
            "effective_sigma": effective_sigma,
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

        return results

    def scenario_analysis(
        self,
        target_date: str,
        scenarios: Optional[Dict[str, tuple]] = None,
        n_simulations: int = 100000,
    ) -> pd.DataFrame:
        if not self.is_fitted:
            raise ValueError("Model must be fitted before scenario analysis")

        if scenarios is None:
            scenarios = {
                "基线": (self.mu_annual, self.sigma_annual),
                "乐观": (self.mu_annual + 0.10, self.sigma_annual * 0.9),
                "保守": (self.mu_annual - 0.15, self.sigma_annual * 1.2),
            }

        trading_days = self._calculate_trading_days(target_date)
        T = trading_days / 252.0

        results = []

        for scenario_name, (mu_scenario, sigma_scenario) in scenarios.items():
            np.random.seed(42)
            Z = np.random.normal(size=n_simulations)

            ln_ST = (
                np.log(self.current_price)
                + (mu_scenario - 0.5 * sigma_scenario**2) * T
                + sigma_scenario * np.sqrt(T) * Z
            )
            ST = np.exp(ln_ST)

            result = {
                "scenario": scenario_name,
                "mu_annual": mu_scenario,
                "sigma_annual": sigma_scenario,
                "mean_price": np.mean(ST),
                "median_price": np.median(ST),
                "price_5th": np.percentile(ST, 5),
                "price_95th": np.percentile(ST, 95),
                "mean_return": (np.mean(ST) / self.current_price - 1) * 100,
                "return_5th": np.percentile((ST / self.current_price - 1) * 100, 5),
                "return_95th": np.percentile((ST / self.current_price - 1) * 100, 95),
            }
            results.append(result)

        return pd.DataFrame(results)

    def get_model_summary(self) -> Dict:
        if not self.is_fitted:
            return {"error": "Model not fitted"}

        return {
            "model_info": self.get_model_info(),
            "parameters": {
                "mu_annual": self.mu_annual,
                "sigma_annual": self.sigma_annual,
                "sigma_robust": self.sigma_robust,
                "current_price": self.current_price,
            },
            "data_info": {
                "data_points": len(self.close_prices),
                "date_range": f"{self.close_prices.index[0].strftime('%Y-%m-%d')} to {self.close_prices.index[-1].strftime('%Y-%m-%d')}",
            },
        }

    def _calculate_trading_days(self, target_date: str) -> int:
        today = datetime.now().date()
        target = datetime.strptime(target_date, "%Y-%m-%d").date()

        try:
            trading_days = int(np.busday_count(today, target))
        except AttributeError:
            days_diff = (target - today).days
            years = days_diff / 365.25
            trading_days = int(years * 252)

        return trading_days

    def _simulate_gbm_endpoints(
        self, n_simulations: int, trading_days: int, sigma: float, seed: int
    ) -> np.ndarray:
        np.random.seed(seed)
        T = trading_days / 252.0

        Z = np.random.standard_normal(n_simulations)

        ln_ST = (
            np.log(self.current_price)
            + (self.mu_annual - 0.5 * sigma**2) * T
            + sigma * np.sqrt(T) * Z
        )

        final_prices = np.exp(ln_ST)

        price_floor = max(0.10, self.current_price * 0.05)
        final_prices = np.maximum(final_prices, price_floor)

        return final_prices

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
