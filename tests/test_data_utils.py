"""Tests for DataUtils"""

import numpy as np
import pandas as pd
import pytest

from sharaku.lib.data_utils import DataUtils


class TestDataUtils:
    def test_init(self, tmp_path):
        cache_dir = str(tmp_path / "cache")
        du = DataUtils(cache_dir=cache_dir)
        assert du.cache_dir == cache_dir

    def test_get_cache_path(self, tmp_path):
        du = DataUtils(cache_dir=str(tmp_path))
        path = du.get_cache_path("AAPL", "2023-01-01", "2024-01-01")
        assert "AAPL_2023-01-01_2024-01-01.pkl" in path

    def test_extract_close_prices_simple(self):
        du = DataUtils()
        df = pd.DataFrame(
            {"Close": [100.0, 101.0, 102.0]},
            index=pd.date_range("2024-01-01", periods=3),
        )
        prices = du.extract_close_prices(df)
        assert len(prices) == 3
        assert prices.iloc[0] == 100.0

    def test_extract_close_prices_multiindex(self):
        du = DataUtils()
        arrays = [["Close", "Open"], ["AAPL", "AAPL"]]
        tuples = list(zip(*arrays))
        index = pd.MultiIndex.from_tuples(tuples)
        df = pd.DataFrame(
            [[100.0, 99.0], [101.0, 100.0]],
            columns=index,
            index=pd.date_range("2024-01-01", periods=2),
        )
        prices = du.extract_close_prices(df)
        assert len(prices) == 2

    def test_extract_close_prices_no_close(self):
        du = DataUtils()
        df = pd.DataFrame(
            {"Volume": [1000, 2000]},
            index=pd.date_range("2024-01-01", periods=2),
        )
        with pytest.raises(ValueError, match="无法找到收盘价"):
            du.extract_close_prices(df)

    def test_calculate_returns_log(self):
        du = DataUtils()
        prices = pd.Series([100.0, 110.0, 121.0])
        returns = du.calculate_returns(prices, "log")
        assert len(returns) == 2
        assert returns.iloc[0] > 0

    def test_calculate_returns_simple(self):
        du = DataUtils()
        prices = pd.Series([100.0, 110.0, 121.0])
        returns = du.calculate_returns(prices, "simple")
        assert abs(returns.iloc[0] - 0.1) < 1e-10

    def test_calculate_returns_invalid(self):
        du = DataUtils()
        with pytest.raises(ValueError):
            du.calculate_returns(pd.Series([1, 2]), "unknown")

    def test_get_basic_statistics(self):
        du = DataUtils()
        index = pd.date_range("2024-01-01", periods=100)
        prices = pd.Series(np.random.uniform(95, 105, 100), index=index)
        returns = du.calculate_returns(prices, "log")
        stats = du.get_basic_statistics(prices, returns)

        assert "current_price" in stats
        assert "volatility_annual" in stats
        assert "data_points" in stats
        assert stats["data_points"] == 100
