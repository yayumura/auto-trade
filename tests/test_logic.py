import unittest
import pandas as pd
import numpy as np
from core.logic import (
    RealtimeBuffer,
    calculate_all_technicals_v12,
    calculate_lot_size,
    compute_daytrade_rebound_trigger,
    evaluate_daytrade_open_setup,
    get_daytrade_week_key,
    has_daytrade_rebound_confirmation,
    is_daytrade_monthly_risk_blocked,
    is_daytrade_market_allowed,
    resolve_daytrade_intraday_stop_mult,
    resolve_daytrade_intraday_target_mult,
    resolve_daytrade_buying_power,
    resolve_daytrade_weekly_leverage,
)

class TestLogic(unittest.TestCase):
    def test_calculate_all_technicals_v12_mean_reversion(self):
        # Create a mock dataframe
        dates = pd.date_range("2024-01-01", periods=30)
        tickers = ["1000.T", "1321.T"]
        
        # MultiIndex columns setup similar to application
        columns = pd.MultiIndex.from_tuples(
            [(t, f) for t in tickers for f in ["Close", "High", "Low", "Open", "Volume"]]
        )
        data = np.random.randn(30, len(columns)) * 5 + 100
        df = pd.DataFrame(data, index=dates, columns=columns)
        
        bundle = calculate_all_technicals_v12(df)
        
        # Assert indicators exist
        self.assertIn('RSI2', bundle)
        self.assertIn('BB_LOWER_2', bundle)
        
        # Verify RSI calculation values (values between 0 and 100)
        rsi_vals = bundle['RSI2'].values
        valid_rsi = rsi_vals[~np.isnan(rsi_vals)]
        if len(valid_rsi) > 0:
            self.assertTrue(np.all((valid_rsi >= 0) & (valid_rsi <= 100)))

        # Verify Bollinger Bands calculations
        valid_bb = bundle['BB_LOWER_2'].values[~np.isnan(bundle['BB_LOWER_2'].values)]
        self.assertTrue(len(valid_bb) > 0)

    def test_realtime_buffer_tracks_session_levels(self):
        buffer = RealtimeBuffer("1000")
        ts = pd.Timestamp("2026-04-21 09:05:00")
        buffer.update(100.0, 1_000, ts, open_price=99.5, high_price=100.0, low_price=99.4)
        buffer.update(101.0, 2_000, ts, open_price=99.5, high_price=101.0, low_price=99.4)
        buffer.update(100.5, 3_000, ts, open_price=99.5, high_price=101.0, low_price=99.2)

        self.assertEqual(buffer.get_session_open(), 99.5)
        self.assertEqual(buffer.get_session_high(), 101.0)
        self.assertEqual(buffer.get_session_low(), 99.2)

    def test_rebound_trigger_helper(self):
        trigger = compute_daytrade_rebound_trigger(100.0, 5.0, confirm_atr=0.2)
        self.assertAlmostEqual(trigger, 101.0)
        self.assertTrue(has_daytrade_rebound_confirmation(101.5, 100.0, 5.0, confirm_atr=0.2))
        self.assertFalse(has_daytrade_rebound_confirmation(100.8, 100.0, 5.0, confirm_atr=0.2))

    def test_daytrade_market_filter_allows_trend_or_strong_breadth(self):
        self.assertFalse(is_daytrade_market_allowed(0.422, market_open=110.0, prev_market_sma_trend=100.0))
        self.assertTrue(is_daytrade_market_allowed(0.423, market_open=110.0, prev_market_sma_trend=100.0))
        self.assertFalse(is_daytrade_market_allowed(0.423, market_open=95.0, prev_market_sma_trend=100.0))
        self.assertTrue(is_daytrade_market_allowed(0.60, market_open=95.0, prev_market_sma_trend=100.0))

    def test_daytrade_weekly_leverage_catches_up_until_target(self):
        self.assertEqual(get_daytrade_week_key(pd.Timestamp("2026-04-24")), "2026-W17")
        self.assertAlmostEqual(resolve_daytrade_weekly_leverage(1.0, 1_000_000, 1_000_000), 20.0)
        self.assertAlmostEqual(resolve_daytrade_weekly_leverage(1.0, 1_000_000, 1_005_000), 1.0)
        self.assertAlmostEqual(resolve_daytrade_weekly_leverage(1.0, 1_000_000, 1_010_000), 1.0)
        self.assertEqual(resolve_daytrade_weekly_leverage(0.0, 1_000_000, 990_000), 0.0)

    def test_daytrade_shared_risk_helpers(self):
        self.assertFalse(is_daytrade_monthly_risk_blocked(1_000_000, 251_000))
        self.assertTrue(is_daytrade_monthly_risk_blocked(1_000_000, 250_000))
        self.assertAlmostEqual(resolve_daytrade_intraday_stop_mult(3.35), 0.67)
        self.assertAlmostEqual(resolve_daytrade_intraday_target_mult(40.0), 2.0)
        self.assertAlmostEqual(resolve_daytrade_buying_power(1_000_000, 1_000_000, 2.3), 2_300_000)

    def test_lot_size_uses_dynamic_leverage(self):
        self.assertEqual(
            calculate_lot_size(
                current_equity=1_000_000,
                atr=10.0,
                sl_mult=3.0,
                price=1_000.0,
                dynamic_leverage=1.2,
                max_positions=1,
                buying_power=2_000_000,
            ),
            1_200,
        )
        self.assertEqual(
            calculate_lot_size(
                current_equity=1_000_000,
                atr=10.0,
                sl_mult=3.0,
                price=1_000.0,
                dynamic_leverage=0.0,
                max_positions=1,
                buying_power=2_000_000,
            ),
            0,
        )

    def test_daytrade_open_setup_accepts_small_prior_pullback(self):
        accepted = evaluate_daytrade_open_setup(
            open_p=100.2,
            prev_close=100.0,
            sma_med=98.0,
            breadth_val=0.55,
            prev_open=100.4,
            prev_atr=2.0,
            prev_low=99.2,
            prev_rsi2=50.0,
            rs_alpha=20.0,
            prev_prev_close=100.4,
        )
        rejected = evaluate_daytrade_open_setup(
            open_p=100.2,
            prev_close=100.0,
            sma_med=98.0,
            breadth_val=0.55,
            prev_open=102.0,
            prev_atr=2.0,
            prev_low=99.2,
            prev_rsi2=50.0,
            rs_alpha=20.0,
            prev_prev_close=101.0,
        )

        self.assertIsNotNone(accepted)
        self.assertIsNone(rejected)

if __name__ == '__main__':
    unittest.main()
