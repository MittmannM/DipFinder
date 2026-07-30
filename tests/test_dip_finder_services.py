import unittest

import pandas as pd

from services.dcf_calculator_service import (
    build_dcf_inputs,
    calculate_dcf_projection,
    calculate_dcf_scenario,
    calculate_historical_dcf_benchmarks,
)
from services.dip_finder_service import (
    calculate_52_week_metrics,
    calculate_period_returns,
    determine_dip_status,
)
from services.fundamental_analysis_service import (
    calculate_average_growth_rates,
    calculate_valuation_metrics,
    calculate_yoy_growth_rates,
)
from services.valuation_service import calculate_valuation_percentile


class DipFinderServiceTests(unittest.TestCase):
    def setUp(self):
        index = pd.date_range("2024-01-01", "2025-01-01", freq="D")
        self.prices = pd.DataFrame(
            {"Adjusted Close": [100 + position for position in range(len(index))]},
            index=index,
        )

    def test_period_returns_use_adjusted_close(self):
        returns = calculate_period_returns(self.prices)
        current = float(self.prices["Adjusted Close"].iloc[-1])

        self.assertAlmostEqual(returns["1W"], current / self.prices.at[pd.Timestamp("2024-12-25"), "Adjusted Close"] - 1)
        self.assertAlmostEqual(returns["1M"], current / self.prices.at[pd.Timestamp("2024-12-01"), "Adjusted Close"] - 1)
        self.assertAlmostEqual(returns["1Y"], current / 100 - 1)

    def test_52_week_metrics(self):
        metrics = calculate_52_week_metrics(self.prices)

        self.assertEqual(metrics["high_52w"], 466)
        self.assertEqual(metrics["low_52w"], 100)
        self.assertEqual(metrics["drawdown_52w"], 0)
        self.assertEqual(metrics["range_position_52w"], 1)

    def test_zero_range_does_not_divide_by_zero(self):
        flat = self.prices.copy()
        flat["Adjusted Close"] = 100

        metrics = calculate_52_week_metrics(flat)

        self.assertIsNone(metrics["range_position_52w"])

    def test_valuation_percentile_ignores_invalid_multiples(self):
        percentile = calculate_valuation_percentile(15, [-2, 0, None, 10, 15, 20])

        self.assertEqual(percentile, 1 / 3)

    def test_dip_status_rules(self):
        base = {
            "period_returns": {"1M": -0.09},
            "drawdown_52w": -0.10,
            "pe_percentile": 0.50,
            "pfcf_percentile": 0.50,
        }

        self.assertEqual(determine_dip_status({**base, "pe_percentile": 0.35}), "ATTRACTIVE_DIP")
        self.assertEqual(
            determine_dip_status({**base, "pe_percentile": 0.66, "pfcf_percentile": 0.66}),
            "DIP_BUT_EXPENSIVE",
        )
        self.assertEqual(determine_dip_status(base), "DIP")
        self.assertEqual(
            determine_dip_status({**base, "period_returns": {"1M": -0.01}, "drawdown_52w": -0.19}),
            "NO_DIP",
        )
        self.assertEqual(determine_dip_status({**base, "pfcf_percentile": None}), "INSUFFICIENT_DATA")

class DcfCalculatorServiceTests(unittest.TestCase):
    def test_dcf_inputs_use_supplied_snapshot_and_shared_history(self):
        years = list(range(2015, 2026))
        history = pd.DataFrame(
            {
                "Date": years,
                "EPS Diluted": [1.1**index for index in range(len(years))],
                "Free Cash Flow": [100 * 1.1**index for index in range(len(years))],
                "Shares Outstanding": [10] * len(years),
                "PE Ratio": [20] * len(years),
                "P/FCF Ratio": [20] * len(years),
            }
        )

        ticker_info = {
            "currentPrice": 100,
            "trailingEps": 5,
            "trailingPE": 20,
            "marketCap": 1000,
            "sharesOutstanding": 10,
            "freeCashflow": 50,
            "earningsGrowth": 0.12,
            "currency": "USD",
        }

        result = build_dcf_inputs(
            "TEST",
            fundamental_history=history,
            ticker_info=ticker_info,
        )

        self.assertAlmostEqual(result["eps_growth"], 0.12)
        self.assertAlmostEqual(result["fcf_growth_5y"], 0.10)
        self.assertAlmostEqual(result["fcf_per_share"], 5)

    def test_historical_dcf_benchmarks_use_full_five_and_ten_year_periods(self):
        years = list(range(2015, 2026))
        history = pd.DataFrame(
            {
                "Date": years,
                "EPS Diluted": [1.1**index for index in range(len(years))],
                "Free Cash Flow": [100 * 1.2**index for index in range(len(years))],
                "Shares Outstanding": [10] * len(years),
                "PE Ratio": list(range(10, 21)),
                "P/FCF Ratio": [10] * len(years),
            }
        )

        result = calculate_historical_dcf_benchmarks(history)

        self.assertAlmostEqual(result["eps_growth_5y"], 0.10)
        self.assertAlmostEqual(result["eps_growth_10y"], 0.10)
        self.assertAlmostEqual(result["fcf_growth_5y"], 0.20)
        self.assertAlmostEqual(result["fcf_growth_10y"], 0.20)
        self.assertAlmostEqual(result["pe_average_5y"], 18)
        self.assertAlmostEqual(result["pe_average_10y"], 15.5)
        self.assertAlmostEqual(result["fcf_yield_average_10y"], 0.10)

    def test_historical_dcf_benchmarks_do_not_label_short_history_as_ten_year(self):
        history = pd.DataFrame(
            {
                "Date": list(range(2020, 2026)),
                "EPS Diluted": [1, 2, 3, 4, 5, 6],
                "PE Ratio": [10, 11, 12, 13, 14, 15],
            }
        )

        result = calculate_historical_dcf_benchmarks(history)

        self.assertIsNotNone(result["eps_growth_5y"])
        self.assertIsNone(result["eps_growth_10y"])
        self.assertIsNone(result["pe_average_10y"])

    def test_eps_projection_interpolates_valuation(self):
        projection = calculate_dcf_projection(
            current_price=100,
            current_metric_per_share=5,
            annual_growth_rate=0.10,
            current_assumption=20,
            terminal_assumption=25,
            basis="EPS",
        )

        self.assertEqual(len(projection), 6)
        self.assertEqual(projection[0]["projected_price"], 100)
        self.assertAlmostEqual(projection[1]["valuation_assumption"], 21)
        self.assertAlmostEqual(projection[5]["projected_price"], 5 * 1.10**5 * 25)

    def test_fcf_projection_interpolates_yield(self):
        projection = calculate_dcf_projection(
            current_price=100,
            current_metric_per_share=5,
            annual_growth_rate=0.10,
            current_assumption=0.05,
            terminal_assumption=0.04,
            basis="FCF",
        )

        self.assertEqual(projection[0]["projected_price"], 100)
        self.assertAlmostEqual(projection[5]["projected_price"], 5 * 1.10**5 / 0.04)

    def test_eps_scenario(self):
        result = calculate_dcf_scenario(
            current_price=100,
            current_metric_per_share=5,
            annual_growth_rate=0.10,
            terminal_assumption=20,
            desired_annual_return=0.15,
            basis="EPS",
        )

        future_eps = 5 * 1.10**5
        future_price = future_eps * 20
        self.assertAlmostEqual(result["future_metric_per_share"], future_eps)
        self.assertAlmostEqual(result["future_price"], future_price)
        self.assertAlmostEqual(result["multiple"], future_price / 100)
        self.assertAlmostEqual(result["maximum_purchase_price"], future_price / 1.15**5)

    def test_fcf_yield_scenario(self):
        result = calculate_dcf_scenario(
            current_price=80,
            current_metric_per_share=4,
            annual_growth_rate=0.05,
            terminal_assumption=0.05,
            desired_annual_return=0.10,
            basis="FCF",
        )

        future_fcf = 4 * 1.05**5
        self.assertAlmostEqual(result["future_price"], future_fcf / 0.05)
        self.assertAlmostEqual(result["annual_return"], (result["future_price"] / 80) ** (1 / 5) - 1)

    def test_non_positive_starting_metric_is_rejected(self):
        with self.assertRaises(ValueError):
            calculate_dcf_scenario(
                current_price=100,
                current_metric_per_share=-1,
                annual_growth_rate=0.10,
                terminal_assumption=20,
                desired_annual_return=0.15,
                basis="EPS",
            )


class FundamentalAnalysisServiceTests(unittest.TestCase):
    def test_growth_helpers_keep_the_existing_period_logic(self):
        growth = calculate_yoy_growth_rates([100, 110, 121])

        self.assertAlmostEqual(growth[0], 0.10)
        self.assertAlmostEqual(growth[1], 0.10)
        self.assertEqual(
            calculate_average_growth_rates(growth),
            (10.0, 10.0, 10.0, 10.0),
        )

    def test_valuation_metrics_calculate_ev_to_ebitda_fallback(self):
        result = calculate_valuation_metrics(
            {
                "marketCap": 1_000,
                "enterpriseValue": 1_200,
                "ebitda": 100,
                "freeCashflow": 50,
                "totalCash": 300,
                "totalDebt": 200,
            }
        )

        self.assertEqual(result["enterprise_to_ebitda"], 12)
        self.assertEqual(result["fcf_yield"], 5)
        self.assertEqual(result["net"], 0)


if __name__ == "__main__":
    unittest.main()
