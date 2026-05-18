import unittest

import pandas as pd

from jp_walkforward import _aggregate_holdout_summaries, _build_walkforward_windows


class TestJpWalkforwardWindowing(unittest.TestCase):
    def test_build_walkforward_windows_returns_chronological_expanding_train_windows(self):
        timeline = pd.bdate_range("2026-01-05", "2026-05-29")

        windows = _build_walkforward_windows(
            timeline=timeline,
            holdout_months=1,
            step_months=1,
            min_train_months=2,
            max_windows=2,
            warmup_start="2026-01-05",
        )

        self.assertEqual(
            windows,
            [
                {
                    "window_id": 1,
                    "train_start": "2026-01-05",
                    "train_end": "2026-03-27",
                    "holdout_start": "2026-03-30",
                    "holdout_end": "2026-04-29",
                },
                {
                    "window_id": 2,
                    "train_start": "2026-01-05",
                    "train_end": "2026-04-29",
                    "holdout_start": "2026-04-30",
                    "holdout_end": "2026-05-29",
                },
            ],
        )

    def test_aggregate_holdout_summaries_rolls_up_window_level_metrics(self):
        window_results = [
            {
                "window_id": 1,
                "train_summary": {"end_date": "2026-03-27", "plus_1pct_weeks": 8, "week_count": 10},
                "holdout_summary": {
                    "start_date": "2026-03-30",
                    "end_date": "2026-04-29",
                    "total_return_pct": 5.0,
                    "profit_factor": 2.0,
                    "trade_count": 4,
                    "worst_day": -100.0,
                    "plus_1pct_weeks": 2,
                    "week_count": 2,
                    "positive_weeks": 2,
                },
            },
            {
                "window_id": 2,
                "train_summary": {"end_date": "2026-04-29", "plus_1pct_weeks": 9, "week_count": 12},
                "holdout_summary": {
                    "start_date": "2026-04-30",
                    "end_date": "2026-05-29",
                    "total_return_pct": -1.0,
                    "profit_factor": 0.5,
                    "trade_count": 3,
                    "worst_day": -250.0,
                    "plus_1pct_weeks": 1,
                    "week_count": 2,
                    "positive_weeks": 1,
                },
            },
        ]

        summary = _aggregate_holdout_summaries(window_results)

        self.assertIsNotNone(summary)
        self.assertEqual(summary["window_count"], 2)
        self.assertEqual(summary["positive_windows"], 1)
        self.assertEqual(summary["windows_all_weeks_hit"], 1)
        self.assertEqual(summary["total_holdout_trades"], 7)
        self.assertEqual(summary["total_holdout_weeks"], 4)
        self.assertEqual(summary["total_plus_1pct_weeks"], 3)
        self.assertEqual(summary["total_positive_weeks"], 3)
        self.assertAlmostEqual(summary["avg_holdout_return_pct"], 2.0)
        self.assertAlmostEqual(summary["median_holdout_return_pct"], 2.0)
        self.assertAlmostEqual(summary["min_holdout_return_pct"], -1.0)
        self.assertAlmostEqual(summary["max_holdout_return_pct"], 5.0)
        self.assertAlmostEqual(summary["avg_holdout_pf"], 1.25)
        self.assertAlmostEqual(summary["median_holdout_pf"], 1.25)
        self.assertEqual(summary["best_window"]["start_date"], "2026-03-30")
        self.assertEqual(summary["worst_window"]["start_date"], "2026-04-30")


if __name__ == "__main__":
    unittest.main()
