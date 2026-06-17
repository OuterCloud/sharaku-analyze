"""
Data Utilities for Stock Price Prediction

Uses yfinance as the sole data source.
"""

import os
import time
import warnings
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf
from loguru import logger


class DataUtils:
    """
    Utility class for stock data operations including download, cache, and preprocessing.
    """

    # 类级别的请求频率控制（所有实例共享）
    _last_request_time: float = 0
    _request_interval: float = 1.0

    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def _rate_limit_request(self):
        """控制请求频率，避免触发API限制（类级别共享）"""
        current_time = time.time()
        time_since_last = current_time - DataUtils._last_request_time

        if time_since_last < DataUtils._request_interval:
            sleep_time = DataUtils._request_interval - time_since_last
            logger.debug(f"请求频率控制，等待 {sleep_time:.1f} 秒...")
            time.sleep(sleep_time)

        DataUtils._last_request_time = time.time()

    def get_cache_path(self, ticker: str, start_date: str, end_date: str) -> str:
        filename = f"{ticker}_{start_date}_{end_date}.pkl"
        return os.path.join(self.cache_dir, filename)

    def download_stock_data(
        self,
        ticker: str,
        start_date: str,
        end_date: Optional[str] = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Download stock data with caching support.

        Args:
            ticker: Stock ticker symbol
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            use_cache: Whether to use cached data if available

        Returns:
            pd.DataFrame: Stock price data

        Raises:
            RuntimeError: If data download fails
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")

        cache_path = self.get_cache_path(ticker, start_date, end_date)

        # Try to load from cache
        if use_cache and os.path.exists(cache_path):
            try:
                cached_data = pd.read_pickle(cache_path)
                logger.info(f"从缓存加载 {ticker} 数据成功")
                return cached_data
            except Exception as e:
                logger.info(f"缓存文件损坏，重新下载: {e}")

        # Download fresh data
        logger.info(f"通过 yfinance 下载 {ticker} 历史数据...")

        try:
            self._rate_limit_request()

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                data = yf.download(
                    ticker,
                    start=start_date,
                    end=end_date,
                    progress=False,
                    auto_adjust=True,
                )

            if data.empty:
                raise ValueError(f"未找到 {ticker} 的数据")

            # Save to cache
            if use_cache:
                pd.to_pickle(data, cache_path)
                logger.info(f"数据已缓存至: {cache_path}")

            return data

        except Exception as e:
            raise RuntimeError(f"下载数据失败: {e}")

    def extract_close_prices(self, data: pd.DataFrame) -> pd.Series:
        """
        Extract close prices from stock data, handling MultiIndex columns.
        """
        # Handle MultiIndex columns
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = ["_".join(col).strip() for col in data.columns.values]

        # Try different close price column names
        close_candidates = [
            col
            for col in data.columns
            if "close" in col.lower() or "adj" in col.lower()
        ]

        if close_candidates:
            close_prices = data[close_candidates[0]].dropna()
        elif "Adj Close" in data.columns:
            close_prices = data["Adj Close"].dropna()
        elif "Close" in data.columns:
            close_prices = data["Close"].dropna()
        else:
            raise ValueError("无法找到收盘价数据列")

        return close_prices

    def calculate_returns(self, prices: pd.Series, method: str = "log") -> pd.Series:
        """Calculate returns from price series."""
        if method == "log":
            return (
                (prices / prices.shift(1))
                .apply(lambda x: 0 if x <= 0 else np.log(x))
                .dropna()
            )
        elif method == "simple":
            return (prices / prices.shift(1) - 1).dropna()
        else:
            raise ValueError("Method must be 'log' or 'simple'")

    def get_basic_statistics(
        self, prices: pd.Series, returns: pd.Series
    ) -> Dict[str, float]:
        """Calculate basic statistics for price and return data."""
        stats = {
            "current_price": float(prices.iloc[-1].item()),
            "price_min": float(prices.min()),
            "price_max": float(prices.max()),
            "price_mean": float(prices.mean()),
            "mean_return_daily": float(returns.mean()),
            "std_return_daily": float(returns.std()),
            "min_return_daily": float(returns.min()),
            "max_return_daily": float(returns.max()),
            "mean_return_annual": float(returns.mean() * 252),
            "volatility_annual": float(returns.std() * (252**0.5)),
            "data_points": len(prices),
            "date_range_days": (prices.index[-1] - prices.index[0]).days,
        }

        return stats

    def prepare_model_data(
        self, ticker: str, start_date: str, end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Complete data preparation pipeline for modeling."""
        raw_data = self.download_stock_data(ticker, start_date, end_date)
        close_prices = self.extract_close_prices(raw_data)
        log_returns = self.calculate_returns(close_prices, "log")
        stats = self.get_basic_statistics(close_prices, log_returns)

        return {
            "raw_data": raw_data,
            "close_prices": close_prices,
            "log_returns": log_returns,
            "statistics": stats,
            "ticker": ticker,
        }

    def get_latest_price_info(self, ticker: str) -> Dict[str, Optional[float]]:
        """获取股票的最新价格信息。"""
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                stock = yf.Ticker(ticker)
                info = stock.info

                current_price = info.get("regularMarketPrice") or info.get(
                    "currentPrice"
                )

                if current_price is None:
                    recent_data = yf.download(
                        ticker, period="2d", progress=False, auto_adjust=True
                    )
                    if not recent_data.empty:
                        current_price = float(
                            recent_data["Close"].iloc[-1].item()
                        )

                return {
                    "current_price": float(current_price) if current_price else None
                }

        except Exception as e:
            logger.info(f"获取 {ticker} 最新价格信息失败: {e}")
            # 尝试使用缓存的历史数据作为fallback
            try:
                cache_files = [
                    f
                    for f in os.listdir(self.cache_dir)
                    if f.startswith(f"{ticker}_") and f.endswith(".pkl")
                ]
                if cache_files:
                    latest_cache = max(
                        cache_files,
                        key=lambda x: os.path.getmtime(
                            os.path.join(self.cache_dir, x)
                        ),
                    )
                    cache_path = os.path.join(self.cache_dir, latest_cache)
                    cached_data = pd.read_pickle(cache_path)
                    if not cached_data.empty and "Close" in cached_data.columns:
                        fallback_price = float(cached_data["Close"].iloc[-1].item())
                        return {"current_price": fallback_price}
            except Exception:
                pass

            return {"current_price": None}
