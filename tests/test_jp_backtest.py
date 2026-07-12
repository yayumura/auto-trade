import pickle
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import jp_refresh_validate
from jp_backtest import _resolve_holdout_start_date, _summarize_window, run_jp_broad_backtest


class TestJpBacktestWindowing(unittest.TestCase):
    def setUp(self):
        self.timeline = pd.to_datetime(
            [
                "2026-03-02",
                "2026-03-03",
                "2026-03-04",
                "2026-03-05",
                "2026-03-06",
                "2026-03-09",
                "2026-03-10",
                "2026-03-11",
                "2026-03-12",
                "2026-03-13",
                "2026-04-03",
            ]
        )
        self.daily_stats = {
            "2026-03-02": {"equity": 100.0, "day_pnl": 0.0, "trade_count": 0},
            "2026-03-03": {"equity": 100.0, "day_pnl": 0.0, "trade_count": 0},
            "2026-03-04": {"equity": 101.0, "day_pnl": 1.0, "trade_count": 1},
            "2026-03-05": {"equity": 100.0, "day_pnl": -1.0, "trade_count": 1},
            "2026-03-06": {"equity": 100.0, "day_pnl": 0.0, "trade_count": 0},
            "2026-03-09": {"equity": 101.0, "day_pnl": 1.0, "trade_count": 1},
            "2026-03-10": {"equity": 102.0, "day_pnl": 1.0, "trade_count": 1},
            "2026-03-11": {"equity": 103.0, "day_pnl": 1.0, "trade_count": 1},
            "2026-03-12": {"equity": 104.0, "day_pnl": 1.0, "trade_count": 1},
            "2026-03-13": {"equity": 105.0, "day_pnl": 1.0, "trade_count": 1},
            "2026-04-03": {"equity": 106.0, "day_pnl": 1.0, "trade_count": 1},
        }
        self.trade_log = [
            {"day_key": "2026-03-04", "net_pnl": 1.0},
            {"day_key": "2026-03-05", "net_pnl": -1.0},
            {"day_key": "2026-03-09", "net_pnl": 1.0},
            {"day_key": "2026-03-10", "net_pnl": 1.0},
            {"day_key": "2026-03-11", "net_pnl": 1.0},
            {"day_key": "2026-03-12", "net_pnl": 1.0},
            {"day_key": "2026-03-13", "net_pnl": 1.0},
            {"day_key": "2026-04-03", "net_pnl": 1.0},
        ]

    def test_resolve_holdout_start_date_uses_trailing_month_span(self):
        self.assertEqual(
            _resolve_holdout_start_date(self.timeline, 1),
            "2026-03-04",
        )

    def test_segmented_summary_uses_only_full_iso_weeks_inside_window(self):
        summary = _summarize_window(
            daily_stats=self.daily_stats,
            trade_log=self.trade_log,
            label="HOLDOUT",
            start_date="2026-03-04",
            end_date="2026-03-13",
            warmup_start="2026-01-01",
        )

        self.assertIsNotNone(summary)
        self.assertEqual(summary["start_date"], "2026-03-04")
        self.assertEqual(summary["end_date"], "2026-03-13")
        self.assertAlmostEqual(summary["start_equity"], 100.0)
        self.assertAlmostEqual(summary["final_equity"], 105.0)
        self.assertAlmostEqual(summary["total_return_pct"], 5.0)
        self.assertEqual(summary["trade_count"], 7)
        self.assertAlmostEqual(summary["win_rate"], (6 / 7) * 100.0)
        self.assertEqual(summary["week_count"], 1)
        self.assertEqual(summary["plus_1pct_weeks"], 1)
        self.assertEqual(summary["positive_weeks"], 1)
        self.assertEqual(summary["full_month_rates"], [])
        self.assertEqual(summary["full_month_returns"], [])
        self.assertEqual(summary["months_ge_20pct"], 0)

    def test_segmented_summary_reports_full_month_twenty_percent_target(self):
        daily_stats = {
            "2026-03-02": {"equity": 100.0, "day_pnl": 0.0, "trade_count": 0},
            "2026-03-31": {"equity": 120.0, "day_pnl": 20.0, "trade_count": 1},
        }
        summary = _summarize_window(
            daily_stats=daily_stats,
            trade_log=[{"day_key": "2026-03-31", "net_pnl": 20.0}],
            label="TRAIN",
            start_date="2026-03-02",
            end_date="2026-03-31",
            warmup_start="2026-01-01",
            global_day_keys=["2026-02-27", "2026-03-02", "2026-03-31", "2026-04-01"],
        )

        self.assertEqual(summary["full_month_returns"], [0.20])
        self.assertEqual(summary["months_ge_20pct"], 1)


class TestJpBacktestHarness(unittest.TestCase):
    def test_run_jp_broad_backtest_uses_prepared_univ_indices(self):
        cache_path = None
        try:
            with tempfile.NamedTemporaryFile("wb", suffix=".pkl", delete=False) as handle:
                pickle.dump({"ignored": True}, handle)
                cache_path = handle.name

            bundle = {"Close": pd.DataFrame(columns=["1000.T", "1321.T", "2000.T"])}
            prepared = {
                "bundle": bundle,
                "bundle_np": {"tickers": ["1000.T", "1321.T", "2000.T"]},
                "timeline": pd.to_datetime(["2026-01-06"]),
                "breadth_series": np.array([0.50], dtype=float),
                "univ_indices": np.array([0, 2], dtype=int),
            }

            with patch("jp_backtest.build_rotation_backtest_inputs_from_cache", return_value=prepared), \
                patch("jp_backtest._summarize_window", return_value={"start_date": "2026-01-06", "end_date": "2026-01-06"}), \
                patch("jp_backtest._print_report"), \
                patch(
                    "jp_backtest.run_backtest_v16_production",
                    return_value=(1_000_000.0, 0, {}, [], {}, []),
                ) as mock_run:
                result = run_jp_broad_backtest(cache_path=cache_path, holdout_months=0, standalone_latest_months=0)

            self.assertEqual(result, 0)
            self.assertTrue(mock_run.called)
            self.assertTrue(np.array_equal(mock_run.call_args.kwargs["univ_indices"], prepared["univ_indices"]))
        finally:
            if cache_path is not None:
                Path(cache_path).unlink(missing_ok=True)

    def test_refresh_validate_uses_tax_rate_for_full_and_standalone(self):
        prepared = {
            "bundle": {"Close": pd.DataFrame(columns=["1000.T", "1321.T", "2000.T"])},
            "bundle_np": {"tickers": ["1000.T", "1321.T", "2000.T"]},
            "timeline": pd.to_datetime(["2026-05-01", "2026-05-02", "2026-05-06"]),
            "breadth_series": np.array([0.45, 0.46, 0.47], dtype=float),
            "univ_indices": np.array([0, 2], dtype=int),
        }

        sliced_inputs = (
            prepared["bundle_np"],
            prepared["timeline"],
            prepared["breadth_series"],
            "2026-05-01",
        )

        def summarize_side_effect(*, label, start_date=None, end_date=None, **_kwargs):
            return {"label": label, "start_date": start_date, "end_date": end_date}

        with patch.object(jp_refresh_validate, "_load_cache", return_value={"ignored": True}), \
            patch.object(
                jp_refresh_validate,
                "build_rotation_backtest_inputs_from_cache",
                return_value=prepared,
            ), \
            patch.object(
                jp_refresh_validate,
                "_slice_backtest_inputs_for_window",
                return_value=sliced_inputs,
            ), \
            patch.object(
                jp_refresh_validate,
                "_summarize_window",
                side_effect=summarize_side_effect,
            ), \
            patch.object(
                jp_refresh_validate,
                "run_backtest_v16_production",
                return_value=(1_000_000.0, 0, {}, [], {}, []),
            ) as mock_run:
            (
                full_summary,
                train_summary,
                holdout_summary,
                standalone_summary,
                *_rest,
            ) = jp_refresh_validate._build_full_validation_report(
                cache_path="dummy.pkl",
                holdout_months=1,
                standalone_latest_months=1,
                standalone_initial_cash=1_000_000.0,
            )

        self.assertIsNotNone(full_summary)
        self.assertIsNotNone(train_summary)
        self.assertIsNotNone(holdout_summary)
        self.assertIsNotNone(standalone_summary)
        self.assertEqual(len(mock_run.call_args_list), 2)
        for call in mock_run.call_args_list:
            self.assertTrue(np.array_equal(call.kwargs["univ_indices"], prepared["univ_indices"]))
            self.assertAlmostEqual(call.kwargs["profit_tax_rate"], jp_refresh_validate.TAX_RATE)
            self.assertAlmostEqual(call.kwargs["slippage"], jp_refresh_validate.SLIPPAGE_RATE)
            self.assertAlmostEqual(
                call.kwargs["explicit_trade_cost"],
                jp_refresh_validate.DAYTRADE_API_EXPLICIT_TRADE_COST,
            )


if __name__ == "__main__":
    unittest.main()
