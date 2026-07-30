import unittest
from unittest.mock import patch

import pandas as pd

from providers import markets_sh_provider, stock_analysis_provider
from repositories import stock_data_repository as repository


class StockDataRepositoryTests(unittest.TestCase):
    def setUp(self):
        repository.clear_all_caches()

    def test_all_repository_and_provider_caches_use_one_hour(self):
        self.assertEqual(repository.CACHE_TTL_SECONDS, 60 * 60)
        self.assertEqual(markets_sh_provider.CACHE_TTL_SECONDS, 60 * 60)
        self.assertEqual(stock_analysis_provider.CACHE_TTL_SECONDS, 60 * 60)

    @patch("repositories.stock_data_repository.yahoo.get_ticker_info")
    def test_ticker_info_normalizes_before_cache_lookup(self, loader):
        loader.return_value = {"symbol": "V"}

        first = repository.get_ticker_info("v")
        second = repository.get_ticker_info(" V ")

        self.assertEqual(first, second)
        loader.assert_called_once_with("V")

    @patch("repositories.stock_data_repository.yahoo.get_price_history")
    def test_price_history_is_loaded_once_and_always_requests_twenty_years(self, loader):
        loader.return_value = pd.DataFrame(
            {"Adjusted Close": [100.0]},
            index=[pd.Timestamp("2026-01-01")],
        )

        repository.get_price_history("v")
        repository.get_price_history("V")

        loader.assert_called_once_with("V", years=20)

    @patch("repositories.stock_data_repository.markets_sh.get_annual_fundamentals")
    def test_annual_fundamentals_are_loaded_once_per_ticker(self, loader):
        frame = pd.DataFrame({"Date": list(range(2007, 2027)), "Revenue": [1] * 20})
        frame.attrs["source"] = "markets.sh"
        loader.return_value = frame

        first = repository.get_annual_fundamentals("v", "token")
        second = repository.get_annual_fundamentals("V", "token")

        self.assertEqual(len(first), 20)
        self.assertEqual(len(second), 20)
        loader.assert_called_once_with("V", "token", 20)


if __name__ == "__main__":
    unittest.main()
