"""
Base Predictor Class

Abstract base class for all stock price prediction models.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Union

import numpy as np
import pandas as pd


class BasePredictor(ABC):
    """
    Abstract base class for stock price prediction models.

    This class defines the common interface that all prediction models should implement.
    """

    def __init__(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ):
        self.ticker = ticker.upper()
        self.start_date = start_date
        self.end_date = end_date

        # Data storage
        self.data: Optional[pd.DataFrame] = None
        self.close_prices: Optional[pd.Series] = None
        self.returns: Optional[pd.Series] = None

        # Model parameters
        self.is_fitted = False

    @abstractmethod
    def fit(self, data: Optional[pd.DataFrame] = None) -> "BasePredictor":
        pass

    @abstractmethod
    def predict(self, days: int, **kwargs) -> Dict[str, Union[float, np.ndarray]]:
        pass

    @abstractmethod
    def analyze_risk(self, predictions: Dict) -> Dict[str, float]:
        pass

    def get_model_info(self) -> Dict[str, Union[str, bool]]:
        return {
            "model_type": self.__class__.__name__,
            "ticker": self.ticker,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "is_fitted": self.is_fitted,
        }

    def validate_data(self, data: pd.DataFrame) -> bool:
        if data.empty:
            raise ValueError("输入数据为空")

        if len(data) < 10:
            raise ValueError(
                f"数据点不足: 当前只有 {len(data)} 个数据点，需要至少 10 个。\n"
                f"该股票可能是新上市的，历史数据较少。\n"
                f"建议选择上市时间较长的股票进行预测。"
            )

        return True

    def __str__(self) -> str:
        status = "fitted" if self.is_fitted else "not fitted"
        return f"{self.__class__.__name__}(ticker={self.ticker}, {status})"

    def calculate_returns(self, prices: pd.Series, method: str = "log") -> pd.Series:
        if method == "log":
            return np.log(prices / prices.shift(1)).dropna()
        elif method == "simple":
            return (prices / prices.shift(1) - 1).dropna()
        else:
            raise ValueError("Method must be 'log' or 'simple'")

    def _get_basic_stats(self) -> Dict[str, float]:
        if self.returns is None:
            raise ValueError("No returns data available. Please fit the model first.")

        return {
            "mean_return": float(self.returns.mean()),
            "std_return": float(self.returns.std()),
            "min_return": float(self.returns.min()),
            "max_return": float(self.returns.max()),
            "current_price": float(self.close_prices.iloc[-1])
            if self.close_prices is not None
            else None,
        }
