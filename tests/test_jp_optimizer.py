import unittest

import numpy as np
import pandas as pd

from jp_optimizer import (
    _build_robustness_windows,
    _resolve_optimizer_split,
    _score_train_robustness,
    _slice_backtest_inputs,
    _validate_train_timeline_or_raise,
)


class TestJpOptimizerWindowing(unittest.TestCase):
    def test_resolve_optimizer_split_matches_trailing_holdout_cut(self):
        timeline = pd.to_datetime(
            [
                "2026-03-02",
                "2026-03-03",
                "2026-03-04",
                "2026-03-05",
                "2026-04-03",
            ]
        )

        split_plan = _resolve_optimizer_split(timeline, 1)

        self.assertEqual(
            split_plan,
            {
                "holdout_start": "2026-03-04",
                "train_end": "2026-03-03",
            },
        )

    def test_slice_backtest_inputs_truncates_time_based_arrays_only(self):
        timeline = pd.to_datetime(
            [
                "2026-03-02",
                "2026-03-03",
                "2026-03-04",
                "2026-03-05",
            ]
        )
        breadth = np.array([0.1, 0.2, 0.3, 0.4], dtype=float)
        bundle_np = {
            "Open": np.array([[1.0], [2.0], [3.0], [4.0]]),
            "Close": np.array([[10.0], [20.0], [30.0], [40.0]]),
            "RS_Alpha": np.array([[100.0], [101.0], [102.0], [103.0]]),
            "tickers": ["7203.T"],
        }

        sliced_bundle_np, sliced_timeline, sliced_breadth = _slice_backtest_inputs(
            bundle_np=bundle_np,
            timeline=timeline,
            breadth_ratio=breadth,
            end_date="2026-03-03",
        )

        self.assertEqual(list(sliced_timeline.strftime("%Y-%m-%d")), ["2026-03-02", "2026-03-03"])
        np.testing.assert_array_equal(sliced_breadth, np.array([0.1, 0.2], dtype=float))
        np.testing.assert_array_equal(sliced_bundle_np["Open"], np.array([[1.0], [2.0]]))
        np.testing.assert_array_equal(sliced_bundle_np["Close"], np.array([[10.0], [20.0]]))
        np.testing.assert_array_equal(sliced_bundle_np["RS_Alpha"], np.array([[100.0], [101.0]]))
        self.assertEqual(sliced_bundle_np["tickers"], ["7203.T"])

    def test_validate_train_timeline_requires_meaningful_history_by_default(self):
        short_train = pd.bdate_range("2026-03-27", "2026-04-15")

        with self.assertRaisesRegex(ValueError, "force-full-refresh"):
            _validate_train_timeline_or_raise(short_train, min_train_months=24)

    def test_build_robustness_windows_returns_chronological_train_subwindows(self):
        timeline = pd.bdate_range("2026-01-05", "2026-05-29")

        windows = _build_robustness_windows(
            timeline=timeline,
            window_months=1,
            step_months=1,
            warmup_start="2026-01-05",
        )

        self.assertEqual(
            windows,
            [
                {"window_id": 1, "start_date": "2026-01-05", "end_date": "2026-01-29"},
                {"window_id": 2, "start_date": "2026-01-28", "end_date": "2026-02-27"},
                {"window_id": 3, "start_date": "2026-03-02", "end_date": "2026-03-27"},
                {"window_id": 4, "start_date": "2026-03-30", "end_date": "2026-04-29"},
                {"window_id": 5, "start_date": "2026-04-30", "end_date": "2026-05-29"},
            ],
        )

    def test_score_train_robustness_prefers_consistent_candidates(self):
        consistent = {
            "trade_count": 240,
            "week_count": 60,
            "window_count": 12,
            "pf": 1.80,
            "plus_1pct_week_rate": 0.82,
            "positive_week_rate": 0.90,
            "positive_window_rate": 0.92,
            "median_window_return_pct": 3.2,
            "worst_window_return_pct": 0.4,
            "median_window_pf": 1.70,
            "avg_month_active_rate": 0.56,
            "mdd": 8.0,
            "worst_day_pct": 1.8,
            "months_3q_active": 2,
        }
        fragile = {
            "trade_count": 240,
            "week_count": 60,
            "window_count": 12,
            "pf": 1.45,
            "plus_1pct_week_rate": 0.63,
            "positive_week_rate": 0.76,
            "positive_window_rate": 0.58,
            "median_window_return_pct": 1.2,
            "worst_window_return_pct": -6.0,
            "median_window_pf": 1.20,
            "avg_month_active_rate": 0.48,
            "mdd": 17.0,
            "worst_day_pct": 4.5,
            "months_3q_active": 0,
        }

        consistent_score = _score_train_robustness(consistent)
        fragile_score = _score_train_robustness(fragile)

        self.assertTrue(consistent_score["eligible"])
        self.assertTrue(fragile_score["eligible"])
        self.assertGreater(consistent_score["score"], fragile_score["score"])


if __name__ == "__main__":
    unittest.main()
