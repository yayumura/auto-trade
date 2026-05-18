import unittest

import pandas as pd

from jp_backtest import _resolve_holdout_start_date, _summarize_window


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


if __name__ == "__main__":
    unittest.main()
