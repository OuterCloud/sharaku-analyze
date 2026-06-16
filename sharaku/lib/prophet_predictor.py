"""
Prophet Predictor - Facebook Prophet 时间序列预测模型

Prophet 为可选依赖，未安装时优雅降级。
"""

import os
import warnings
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union

import numpy as np
import pandas as pd
from loguru import logger

from .base_predictor import BasePredictor

warnings.filterwarnings("ignore")


class ProphetPredictor(BasePredictor):
    """
    使用 Facebook Prophet 进行股价预测的预测器类。
    """

    def __init__(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        growth: str = "linear",
        yearly_seasonality: bool = True,
        weekly_seasonality: bool = True,
        daily_seasonality: bool = False,
        interval_width: float = 0.95,
        changepoint_prior_scale: float = 0.05,
        seasonality_prior_scale: float = 10.0,
    ):
        super().__init__(ticker, start_date, end_date)

        self.growth = growth
        self.yearly_seasonality = yearly_seasonality
        self.weekly_seasonality = weekly_seasonality
        self.daily_seasonality = daily_seasonality
        self.interval_width = interval_width
        self.changepoint_prior_scale = changepoint_prior_scale
        self.seasonality_prior_scale = seasonality_prior_scale

        self.model = None
        self.prophet_data = None

        self._check_prophet_installation()

    def _check_prophet_installation(self):
        """检查 Prophet 是否已安装"""
        try:
            import prophet  # noqa: F401

            self.prophet_available = True
        except ImportError:
            self.prophet_available = False
            logger.warning("Prophet 未安装，部分功能不可用。请运行: pip install prophet")

    def _prepare_prophet_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """准备 Prophet 模型所需的数据格式。"""
        close_data = None

        if "Close" in df.columns:
            close_data = df["Close"]
        elif isinstance(df.columns, pd.MultiIndex):
            close_cols = [col for col in df.columns if "Close" in str(col)]
            if close_cols:
                close_data = df[close_cols[0]]
        elif len(df.columns) == 1:
            close_data = df.iloc[:, 0]
        elif len(df.columns) >= 4:
            close_data = df.iloc[:, 3]

        if close_data is None:
            raise ValueError(
                f"无法从 DataFrame 中找到 Close 列。可用列: {df.columns.tolist()}"
            )

        if hasattr(close_data, "iloc") and len(close_data.shape) > 1:
            close_data = close_data.iloc[:, 0]

        prophet_df = pd.DataFrame(
            {"ds": df.index.to_list(), "y": close_data.values.flatten()}
        )
        prophet_df["ds"] = pd.to_datetime(prophet_df["ds"])
        prophet_df = prophet_df.reset_index(drop=True)

        return prophet_df

    def fit(self, data: Optional[pd.DataFrame] = None) -> "ProphetPredictor":
        if not self.prophet_available:
            raise ImportError("Prophet 未安装，请运行: pip install prophet")

        from prophet import Prophet

        if data is None:
            from .data_utils import DataUtils

            if self.start_date is None:
                self.start_date = (datetime.now() - timedelta(days=730)).strftime(
                    "%Y-%m-%d"
                )
            if self.end_date is None:
                self.end_date = datetime.now().strftime("%Y-%m-%d")

            data_utils = DataUtils()
            data = data_utils.download_stock_data(
                ticker=self.ticker,
                start_date=self.start_date,
                end_date=self.end_date,
                use_cache=True,
            )

        self.data = data
        self.prophet_data = self._prepare_prophet_data(data)

        if len(self.prophet_data) < 30:
            raise ValueError("数据点数太少，至少需要 30 个数据点")

        self.model = Prophet(
            growth=self.growth,
            yearly_seasonality=self.yearly_seasonality,
            weekly_seasonality=self.weekly_seasonality,
            daily_seasonality=self.daily_seasonality,
            interval_width=self.interval_width,
            changepoint_prior_scale=self.changepoint_prior_scale,
            seasonality_prior_scale=self.seasonality_prior_scale,
        )

        logger.info(f"开始训练 Prophet 模型 ({self.ticker})...")
        self.model.fit(self.prophet_data)
        self.is_fitted = True
        logger.info("Prophet 模型训练完成!")

        return self

    def predict(
        self, days: int = 30, return_full_forecast: bool = False
    ) -> Dict[str, Union[float, np.ndarray, pd.DataFrame]]:
        if not self.is_fitted or self.model is None:
            raise RuntimeError("模型未训练，请先调用 fit() 方法")

        future = self.model.make_future_dataframe(periods=days)
        forecast = self.model.predict(future)

        last_prediction = forecast.iloc[-1]
        current_price = self.prophet_data["y"].iloc[-1]

        prediction_price = last_prediction["yhat"]
        lower_bound = last_prediction["yhat_lower"]
        upper_bound = last_prediction["yhat_upper"]

        price_floor = max(0.10, current_price * 0.05)
        prediction_price = max(prediction_price, price_floor)
        lower_bound = max(lower_bound, price_floor)
        upper_bound = max(upper_bound, price_floor)

        if "yhat" in forecast.columns:
            forecast["yhat"] = forecast["yhat"].clip(lower=price_floor)
            forecast["yhat_lower"] = forecast["yhat_lower"].clip(lower=price_floor)
            forecast["yhat_upper"] = forecast["yhat_upper"].clip(lower=price_floor)

        expected_return = (prediction_price - current_price) / current_price * 100

        result = {
            "prediction": float(prediction_price),
            "lower_bound": float(lower_bound),
            "upper_bound": float(upper_bound),
            "current_price": float(current_price),
            "expected_return": float(expected_return),
            "days": days,
        }

        if return_full_forecast:
            result["forecast_df"] = forecast

        return result

    def analyze_risk(
        self, predictions: Dict = None, days: int = 30
    ) -> Dict[str, float]:
        if predictions is None:
            predictions = self.predict(days=days)

        pred_price = predictions["prediction"]
        lower = predictions["lower_bound"]
        upper = predictions["upper_bound"]

        uncertainty = (upper - lower) / pred_price * 100
        confidence_width = upper - lower

        if "forecast_df" in predictions:
            forecast_df = predictions["forecast_df"]
            volatility = forecast_df["yhat"].std()
        else:
            volatility = confidence_width / 4

        if uncertainty < 20:
            risk_level = "low"
        elif uncertainty < 40:
            risk_level = "medium"
        else:
            risk_level = "high"

        return {
            "uncertainty": float(uncertainty),
            "risk_level": risk_level,
            "volatility": float(volatility),
            "confidence_width": float(confidence_width),
            "lower_bound": float(lower),
            "upper_bound": float(upper),
        }

    def get_trend_analysis(self, days: int = 30) -> Dict[str, Any]:
        if not self.is_fitted:
            raise RuntimeError("模型未训练，请先调用 fit() 方法")

        future = self.model.make_future_dataframe(periods=days)
        forecast = self.model.predict(future)

        recent_trend = forecast["trend"].iloc[-days:].mean()
        current_trend = forecast["trend"].iloc[-1]
        trend_change = (current_trend - recent_trend) / recent_trend * 100

        result = {
            "current_trend": float(current_trend),
            "recent_trend": float(recent_trend),
            "trend_change_pct": float(trend_change),
        }

        if "yearly" in forecast.columns:
            result["yearly_effect"] = float(forecast["yearly"].iloc[-1])
        if "weekly" in forecast.columns:
            result["weekly_effect"] = float(forecast["weekly"].iloc[-1])

        return result

    def get_model_summary(self) -> Dict[str, Any]:
        summary = {
            "model_type": "Prophet",
            "ticker": self.ticker,
            "is_fitted": self.is_fitted,
            "data_points": len(self.prophet_data)
            if self.prophet_data is not None
            else 0,
            "parameters": {
                "growth": self.growth,
                "yearly_seasonality": self.yearly_seasonality,
                "weekly_seasonality": self.weekly_seasonality,
                "daily_seasonality": self.daily_seasonality,
                "interval_width": self.interval_width,
                "changepoint_prior_scale": self.changepoint_prior_scale,
                "seasonality_prior_scale": self.seasonality_prior_scale,
            },
        }

        if self.is_fitted and self.prophet_data is not None:
            summary["date_range"] = {
                "start": str(self.prophet_data["ds"].min()),
                "end": str(self.prophet_data["ds"].max()),
            }
            summary["current_price"] = float(self.prophet_data["y"].iloc[-1])

        return summary
