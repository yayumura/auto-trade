import unittest
import pandas as pd
import numpy as np
from core.logic import (
    RealtimeBuffer,
    cap_daytrade_position_size,
    calculate_all_technicals_v12,
    calculate_lot_size,
    compute_daytrade_rebound_trigger,
    evaluate_daytrade_setup,
    evaluate_daytrade_open_setup,
    evaluate_daytrade_catchup_open_setups,
    evaluate_daytrade_fallback_open_setup,
    evaluate_daytrade_strong_oversold_open_setup,
    evaluate_daytrade_inverse_open_setup,
    score_daytrade_catchup_open_setup,
    score_daytrade_fallback_open_setup,
    score_daytrade_strong_oversold_open_setup,
    score_daytrade_inverse_open_setup,
    extend_daytrade_targets_with_inverse_codes,
    should_replace_primary_with_preferred_etf,
    get_daytrade_week_key,
    has_daytrade_rebound_confirmation,
    is_daytrade_catchup_market_allowed,
    is_daytrade_fallback_market_allowed,
    is_daytrade_inverse_market_allowed,
    is_daytrade_inverse_pullback_market_allowed,
    is_daytrade_monthly_risk_blocked,
    is_daytrade_market_allowed,
    is_daytrade_strong_oversold_market_allowed,
    is_daytrade_weekly_profit_guard_active,
    resolve_daytrade_intraday_stop_mult,
    resolve_daytrade_intraday_target_mult,
    resolve_daytrade_breadth_exposure_scale,
    resolve_daytrade_buying_power,
    resolve_daytrade_inverse_buying_power,
    resolve_daytrade_weekly_leverage,
    select_daytrade_candidates,
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
        self.assertTrue(is_daytrade_fallback_market_allowed(0.36, market_open=99.0, prev_market_sma_trend=100.0))
        self.assertFalse(is_daytrade_fallback_market_allowed(0.359, market_open=110.0, prev_market_sma_trend=100.0))
        self.assertTrue(is_daytrade_catchup_market_allowed(0.36, market_open=95.0, prev_market_sma_trend=100.0))
        self.assertFalse(is_daytrade_catchup_market_allowed(0.179, market_open=110.0, prev_market_sma_trend=100.0))
        self.assertTrue(
            is_daytrade_inverse_market_allowed(
                0.30,
                market_open=97.0,
                prev_market_sma_trend=100.0,
                prev_market_close=100.0,
            )
        )
        self.assertFalse(
            is_daytrade_inverse_market_allowed(
                0.40,
                market_open=97.0,
                prev_market_sma_trend=100.0,
                prev_market_close=100.0,
            )
        )
        self.assertTrue(
            is_daytrade_inverse_pullback_market_allowed(
                0.45,
                market_open=98.0,
                prev_market_sma_trend=100.0,
                prev_market_close=100.0,
            )
        )
        self.assertFalse(
            is_daytrade_inverse_pullback_market_allowed(
                0.55,
                market_open=98.0,
                prev_market_sma_trend=100.0,
                prev_market_close=100.0,
            )
        )

    def test_daytrade_weekly_leverage_catches_up_until_target(self):
        self.assertEqual(get_daytrade_week_key(pd.Timestamp("2026-04-24")), "2026-W17")
        self.assertAlmostEqual(resolve_daytrade_weekly_leverage(1.0, 1_000_000, 1_000_000), 20.0)
        self.assertAlmostEqual(
            resolve_daytrade_weekly_leverage(
                1.0,
                1_000_000,
                1_000_000,
                current_time=pd.Timestamp("2026-04-20"),
            ),
            60.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_weekly_leverage(
                1.0,
                1_000_000,
                1_000_000,
                current_time=pd.Timestamp("2026-04-22"),
            ),
            60.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_weekly_leverage(
                1.0,
                1_000_000,
                1_000_000,
                current_time=pd.Timestamp("2026-04-23"),
            ),
            20.0,
        )
        self.assertAlmostEqual(resolve_daytrade_weekly_leverage(1.0, 1_000_000, 1_004_999), 20.0)
        self.assertAlmostEqual(resolve_daytrade_weekly_leverage(1.0, 1_000_000, 1_005_000), 20.0)
        self.assertAlmostEqual(resolve_daytrade_weekly_leverage(1.0, 1_000_000, 1_009_999), 20.0)
        self.assertAlmostEqual(
            resolve_daytrade_weekly_leverage(
                1.0,
                1_000_000,
                1_010_000,
                current_time=pd.Timestamp("2026-04-20"),
            ),
            0.0,
        )
        self.assertEqual(resolve_daytrade_weekly_leverage(0.0, 1_000_000, 990_000), 0.0)
        self.assertFalse(
            is_daytrade_weekly_profit_guard_active(
                1_000_000,
                1_006_000,
                current_time=pd.Timestamp("2026-04-22"),
            )
        )
        self.assertTrue(
            is_daytrade_weekly_profit_guard_active(
                1_000_000,
                1_005_000,
                current_time=pd.Timestamp("2026-04-23"),
            )
        )
        self.assertTrue(
            is_daytrade_weekly_profit_guard_active(
                1_000_000,
                1_009_000,
                current_time=pd.Timestamp("2026-04-24"),
            )
        )

    def test_daytrade_shared_risk_helpers(self):
        self.assertFalse(is_daytrade_monthly_risk_blocked(1_000_000, 371_000))
        self.assertTrue(is_daytrade_monthly_risk_blocked(1_000_000, 370_000))
        self.assertAlmostEqual(resolve_daytrade_intraday_stop_mult(3.35), 0.67)
        self.assertAlmostEqual(resolve_daytrade_intraday_target_mult(40.0), 2.0)
        self.assertAlmostEqual(resolve_daytrade_buying_power(1_000_000, 1_000_000, 2.3), 2_300_000)
        self.assertAlmostEqual(resolve_daytrade_inverse_buying_power(1_000_000, 1_000_000), 1_000_000)
        self.assertAlmostEqual(resolve_daytrade_breadth_exposure_scale(0.49), 0.35)
        self.assertAlmostEqual(resolve_daytrade_breadth_exposure_scale(0.50), 1.0)
        self.assertEqual(
            cap_daytrade_position_size(
                raw_shares=5_000,
                current_equity=1_000_000,
                buying_power=5_000_000,
                entry_price=1_000.0,
                stop_price=950.0,
                notional_pct=1.0,
                equity_notional_pct=0.3,
            ),
            300,
        )

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

    def test_daytrade_primary_setup_avoids_mid_breadth_gap_chase(self):
        blocked_open = evaluate_daytrade_open_setup(
            open_p=101.0,
            prev_close=100.0,
            sma_med=98.0,
            breadth_val=0.55,
            prev_open=99.0,
            prev_atr=2.0,
            prev_low=98.5,
            prev_rsi2=55.0,
            rs_alpha=20.0,
            prev_prev_close=99.5,
        )
        allowed_open = evaluate_daytrade_open_setup(
            open_p=101.0,
            prev_close=100.0,
            sma_med=98.0,
            breadth_val=0.60,
            prev_open=99.0,
            prev_atr=2.0,
            prev_low=98.5,
            prev_rsi2=55.0,
            rs_alpha=20.0,
            prev_prev_close=99.5,
        )
        blocked_live = evaluate_daytrade_setup(
            price=101.5,
            open_p=101.0,
            prev_close=100.0,
            sma_med=98.0,
            breadth_val=0.55,
            prev_open=99.0,
            prev_atr=2.0,
            prev_low=98.5,
            rs_alpha=20.0,
            rsi2=55.0,
            prev_prev_close=99.5,
        )

        self.assertIsNone(blocked_open)
        self.assertIsNotNone(allowed_open)
        self.assertIsNone(blocked_live)

    def test_daytrade_primary_setup_avoids_moderate_breadth_overextension(self):
        blocked_open = evaluate_daytrade_open_setup(
            open_p=107.4,
            prev_close=107.0,
            sma_med=100.0,
            breadth_val=0.60,
            prev_open=106.0,
            prev_atr=2.0,
            prev_low=105.8,
            prev_rsi2=58.0,
            rs_alpha=24.0,
            prev_prev_close=106.0,
        )
        allowed_open = evaluate_daytrade_open_setup(
            open_p=107.4,
            prev_close=107.0,
            sma_med=100.0,
            breadth_val=0.64,
            prev_open=106.0,
            prev_atr=2.0,
            prev_low=105.8,
            prev_rsi2=58.0,
            rs_alpha=24.0,
            prev_prev_close=106.0,
        )
        blocked_live = evaluate_daytrade_setup(
            price=107.9,
            open_p=107.4,
            prev_close=107.0,
            sma_med=100.0,
            breadth_val=0.60,
            prev_open=106.0,
            prev_atr=2.0,
            prev_low=105.8,
            rs_alpha=24.0,
            rsi2=58.0,
            prev_prev_close=106.0,
        )

        self.assertIsNone(blocked_open)
        self.assertIsNotNone(allowed_open)
        self.assertIsNone(blocked_live)

    def test_daytrade_primary_setup_avoids_mid_rsi_overextension(self):
        blocked_open = evaluate_daytrade_open_setup(
            open_p=104.2,
            prev_close=104.0,
            sma_med=100.0,
            breadth_val=0.62,
            prev_open=103.0,
            prev_atr=2.0,
            prev_low=102.8,
            prev_rsi2=45.0,
            rs_alpha=24.0,
            prev_prev_close=103.0,
        )
        allowed_open = evaluate_daytrade_open_setup(
            open_p=104.2,
            prev_close=104.0,
            sma_med=100.0,
            breadth_val=0.63,
            prev_open=103.0,
            prev_atr=2.0,
            prev_low=102.8,
            prev_rsi2=45.0,
            rs_alpha=24.0,
            prev_prev_close=103.0,
        )
        blocked_live = evaluate_daytrade_setup(
            price=104.7,
            open_p=104.2,
            prev_close=104.0,
            sma_med=100.0,
            breadth_val=0.62,
            prev_open=103.0,
            prev_atr=2.0,
            prev_low=102.8,
            rs_alpha=24.0,
            rsi2=45.0,
            prev_prev_close=103.0,
        )

        self.assertIsNone(blocked_open)
        self.assertIsNotNone(allowed_open)
        self.assertIsNone(blocked_live)

    def test_daytrade_primary_setup_avoids_monday_hot_continuation(self):
        blocked_open = evaluate_daytrade_open_setup(
            open_p=106.5,
            prev_close=104.0,
            sma_med=100.0,
            breadth_val=0.72,
            prev_open=103.0,
            prev_atr=2.0,
            prev_low=102.5,
            prev_rsi2=55.0,
            rs_alpha=30.0,
            prev_prev_close=99.0,
            trade_weekday=0,
        )
        allowed_open = evaluate_daytrade_open_setup(
            open_p=106.5,
            prev_close=104.0,
            sma_med=100.0,
            breadth_val=0.72,
            prev_open=103.0,
            prev_atr=2.0,
            prev_low=102.5,
            prev_rsi2=55.0,
            rs_alpha=30.0,
            prev_prev_close=99.0,
            trade_weekday=1,
        )
        blocked_live = evaluate_daytrade_setup(
            price=107.0,
            open_p=106.5,
            prev_close=104.0,
            sma_med=100.0,
            breadth_val=0.72,
            prev_open=103.0,
            prev_atr=2.0,
            prev_low=102.5,
            rs_alpha=30.0,
            rsi2=55.0,
            prev_prev_close=99.0,
            trade_weekday=0,
        )

        self.assertIsNone(blocked_open)
        self.assertIsNotNone(allowed_open)
        self.assertIsNone(blocked_live)

    def test_daytrade_primary_setup_avoids_tuesday_mid_breadth_hot_gap_without_followthrough(self):
        blocked_open = evaluate_daytrade_open_setup(
            open_p=104.7,
            prev_close=102.0,
            sma_med=100.0,
            breadth_val=0.55,
            prev_open=101.0,
            prev_atr=2.0,
            prev_low=100.8,
            prev_rsi2=50.0,
            rs_alpha=40.0,
            prev_prev_close=100.0,
            trade_weekday=1,
        )
        allowed_open = evaluate_daytrade_open_setup(
            open_p=104.7,
            prev_close=102.0,
            sma_med=100.0,
            breadth_val=0.55,
            prev_open=101.0,
            prev_atr=2.0,
            prev_low=100.8,
            prev_rsi2=50.0,
            rs_alpha=40.0,
            prev_prev_close=100.0,
            trade_weekday=2,
        )

        self.assertIsNone(blocked_open)
        self.assertIsNotNone(allowed_open)

    def test_daytrade_primary_setup_avoids_tuesday_mid_breadth_weak_rs_extension(self):
        blocked_open = evaluate_daytrade_open_setup(
            open_p=106.8,
            prev_close=105.0,
            sma_med=102.0,
            breadth_val=0.55,
            prev_open=104.0,
            prev_atr=2.0,
            prev_low=103.6,
            prev_rsi2=60.0,
            rs_alpha=20.0,
            prev_prev_close=100.0,
            trade_weekday=1,
        )
        allowed_open = evaluate_daytrade_open_setup(
            open_p=106.8,
            prev_close=105.0,
            sma_med=102.0,
            breadth_val=0.55,
            prev_open=104.0,
            prev_atr=2.0,
            prev_low=103.6,
            prev_rsi2=60.0,
            rs_alpha=30.0,
            prev_prev_close=100.0,
            trade_weekday=1,
        )

        self.assertIsNone(blocked_open)
        self.assertIsNotNone(allowed_open)

    def test_daytrade_primary_setup_avoids_tuesday_high_breadth_weak_rs_extension(self):
        blocked_open = evaluate_daytrade_open_setup(
            open_p=107.0,
            prev_close=105.5,
            sma_med=102.0,
            breadth_val=0.72,
            prev_open=104.0,
            prev_atr=2.0,
            prev_low=104.0,
            prev_rsi2=60.0,
            rs_alpha=20.0,
            prev_prev_close=100.0,
            trade_weekday=1,
        )
        allowed_open = evaluate_daytrade_open_setup(
            open_p=107.0,
            prev_close=105.5,
            sma_med=102.0,
            breadth_val=0.72,
            prev_open=104.0,
            prev_atr=2.0,
            prev_low=104.0,
            prev_rsi2=60.0,
            rs_alpha=30.0,
            prev_prev_close=100.0,
            trade_weekday=1,
        )

        self.assertIsNone(blocked_open)
        self.assertIsNotNone(allowed_open)

    def test_daytrade_primary_setup_avoids_thursday_mid_breadth_low_gap_without_followthrough(self):
        blocked_open = evaluate_daytrade_open_setup(
            open_p=100.5,
            prev_close=100.0,
            sma_med=98.0,
            breadth_val=0.55,
            prev_open=99.5,
            prev_atr=2.0,
            prev_low=99.0,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=97.5,
            trade_weekday=3,
        )
        allowed_open = evaluate_daytrade_open_setup(
            open_p=100.5,
            prev_close=100.0,
            sma_med=98.0,
            breadth_val=0.55,
            prev_open=99.5,
            prev_atr=2.0,
            prev_low=99.0,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=97.5,
            trade_weekday=2,
        )

        self.assertIsNone(blocked_open)
        self.assertIsNotNone(allowed_open)

    def test_daytrade_primary_setup_avoids_thursday_mid_breadth_late_extension_stall(self):
        blocked_open = evaluate_daytrade_open_setup(
            open_p=101.5,
            prev_close=101.0,
            sma_med=99.0,
            breadth_val=0.55,
            prev_open=100.5,
            prev_atr=2.0,
            prev_low=100.3,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=94.0,
            trade_weekday=3,
        )
        allowed_open = evaluate_daytrade_open_setup(
            open_p=102.8,
            prev_close=101.0,
            sma_med=99.0,
            breadth_val=0.55,
            prev_open=100.5,
            prev_atr=2.0,
            prev_low=100.3,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=94.0,
            trade_weekday=3,
        )

        self.assertIsNone(blocked_open)
        self.assertIsNotNone(allowed_open)

    def test_daytrade_fallback_open_setup_is_bounded(self):
        accepted = evaluate_daytrade_fallback_open_setup(
            open_p=100.2,
            prev_close=100.0,
            sma_med=98.0,
            breadth_val=0.40,
            prev_atr=2.0,
            prev_low=99.2,
            prev_rsi2=55.0,
            rs_alpha=15.0,
            prev_prev_close=99.5,
        )
        rejected = evaluate_daytrade_fallback_open_setup(
            open_p=103.0,
            prev_close=100.0,
            sma_med=98.0,
            breadth_val=0.40,
            prev_atr=2.0,
            prev_low=99.2,
            prev_rsi2=55.0,
            rs_alpha=15.0,
            prev_prev_close=99.5,
        )

        self.assertIsNotNone(accepted)
        self.assertIsNone(rejected)

    def test_daytrade_fallback_open_setup_accepts_moderately_hot_rsi(self):
        accepted = evaluate_daytrade_fallback_open_setup(
            open_p=100.4,
            prev_close=100.0,
            sma_med=98.0,
            breadth_val=0.40,
            prev_atr=2.0,
            prev_low=99.2,
            prev_rsi2=79.5,
            rs_alpha=15.0,
            prev_prev_close=99.5,
        )
        rejected = evaluate_daytrade_fallback_open_setup(
            open_p=100.4,
            prev_close=100.0,
            sma_med=98.0,
            breadth_val=0.40,
            prev_atr=2.0,
            prev_low=99.2,
            prev_rsi2=80.5,
            rs_alpha=15.0,
            prev_prev_close=99.5,
        )

        self.assertIsNotNone(accepted)
        self.assertIsNone(rejected)

    def test_daytrade_fallback_score_prefers_moderate_gap(self):
        preferred = {
            "gap_pct": 0.007,
            "prev_return": 0.02,
            "open_from_prev_low_atr": 0.8,
            "open_vs_sma_atr": 0.0,
            "rs_alpha": 30.0,
        }
        stretched = dict(preferred, gap_pct=0.012)

        self.assertGreater(
            score_daytrade_fallback_open_setup(preferred, prev_rsi2=60.0, rs_alpha=30.0),
            score_daytrade_fallback_open_setup(stretched, prev_rsi2=60.0, rs_alpha=30.0),
        )

    def test_daytrade_catchup_setups_cover_gapdown_and_strong_rs(self):
        gapdown = evaluate_daytrade_catchup_open_setups(
            open_p=97.1,
            prev_close=100.0,
            sma_med=99.0,
            breadth_val=0.40,
            prev_atr=2.0,
            prev_low=96.5,
            prev_rsi2=32.0,
            rs_alpha=12.0,
            prev_prev_close=101.0,
            prev_sma_trend=99.0,
        )
        strong_rs = evaluate_daytrade_catchup_open_setups(
            open_p=101.0,
            prev_close=100.0,
            sma_med=98.0,
            breadth_val=0.40,
            prev_atr=2.0,
            prev_low=99.0,
            prev_rsi2=70.0,
            rs_alpha=35.0,
            prev_prev_close=98.0,
            prev_sma_trend=95.0,
        )
        shallow_gap = evaluate_daytrade_catchup_open_setups(
            open_p=99.5,
            prev_close=100.0,
            sma_med=99.0,
            breadth_val=0.40,
            prev_atr=2.0,
            prev_low=98.8,
            prev_rsi2=55.0,
            rs_alpha=25.0,
            prev_prev_close=99.0,
            prev_sma_trend=98.0,
        )

        self.assertEqual(gapdown[0]["setup_type"], "catchup_gapdown")
        self.assertEqual(strong_rs[0]["setup_type"], "catchup_rs")
        self.assertFalse(any(item["setup_type"] == "catchup_gapdown" for item in shallow_gap))
        self.assertGreater(score_daytrade_catchup_open_setup(gapdown[0]), 4.0)
        self.assertGreater(score_daytrade_catchup_open_setup(strong_rs[0]), 4.0)

    def test_daytrade_inverse_open_setup_is_riskoff_only(self):
        accepted = evaluate_daytrade_inverse_open_setup(
            open_p=101.0,
            prev_close=100.0,
            breadth_val=0.30,
            prev_atr=2.0,
            prev_prev_close=98.0,
            market_open=97.0,
            prev_market_close=100.0,
            prev_market_sma_trend=100.0,
        )
        rejected = evaluate_daytrade_inverse_open_setup(
            open_p=101.0,
            prev_close=100.0,
            breadth_val=0.45,
            prev_atr=2.0,
            prev_prev_close=98.0,
            market_open=101.0,
            prev_market_close=100.0,
            prev_market_sma_trend=100.0,
        )

        self.assertIsNotNone(accepted)
        self.assertIsNone(rejected)
        self.assertGreater(score_daytrade_inverse_open_setup(accepted, rs_alpha=10.0), 3.0)
        self.assertEqual(accepted["setup_type"], "inverse")

    def test_daytrade_inverse_open_setup_supports_pullback_in_bear_market(self):
        accepted = evaluate_daytrade_inverse_open_setup(
            open_p=103.5,
            prev_close=105.0,
            breadth_val=0.45,
            prev_atr=2.0,
            prev_prev_close=100.0,
            market_open=98.0,
            prev_market_close=100.0,
            prev_market_sma_trend=100.0,
        )
        rejected = evaluate_daytrade_inverse_open_setup(
            open_p=103.5,
            prev_close=105.0,
            breadth_val=0.55,
            prev_atr=2.0,
            prev_prev_close=100.0,
            market_open=98.0,
            prev_market_close=100.0,
            prev_market_sma_trend=100.0,
        )

        self.assertIsNotNone(accepted)
        self.assertEqual(accepted["setup_type"], "inverse_pullback")
        self.assertLess(accepted["gap_pct"], 0.0)
        self.assertGreater(score_daytrade_inverse_open_setup(accepted, rs_alpha=10.0), 3.0)
        self.assertIsNone(rejected)

    def test_daytrade_strong_oversold_open_setup_targets_strong_market_dips(self):
        self.assertTrue(
            is_daytrade_strong_oversold_market_allowed(
                0.62,
                market_open=101.0,
                prev_market_sma_trend=100.0,
            )
        )
        accepted = evaluate_daytrade_strong_oversold_open_setup(
            open_p=100.0,
            prev_close=103.0,
            breadth_val=0.62,
            prev_atr=2.0,
            prev_rsi2=1.5,
            rs_alpha=15.0,
            prev_prev_close=103.5,
            prev_sma_trend=95.0,
        )
        rejected = evaluate_daytrade_strong_oversold_open_setup(
            open_p=105.0,
            prev_close=103.0,
            breadth_val=0.62,
            prev_atr=2.0,
            prev_rsi2=6.0,
            rs_alpha=15.0,
            prev_prev_close=103.5,
            prev_sma_trend=95.0,
        )

        self.assertIsNotNone(accepted)
        self.assertIsNone(rejected)
        self.assertGreater(score_daytrade_strong_oversold_open_setup(accepted, rs_alpha=15.0), 5.0)

    def test_daytrade_candidate_selection_can_replace_weak_primary(self):
        primary = [{"code": "1000", "score": 5.0, "setup_type": "primary"}]
        medium_primary = [{"code": "1100", "score": 6.5, "setup_type": "primary"}]
        strong_oversold = [
            {"code": "1500", "score": 10.0, "setup_type": "strong_oversold"},
            {"code": "1579", "score": 8.0, "setup_type": "strong_oversold"},
        ]
        fallback = [{"code": "2000", "score": 9.1, "setup_type": "fallback"}]
        catchup = [{"code": "2500", "score": 20.0, "setup_type": "catchup_rs"}]
        inverse = [{"code": "1459", "score": 4.5, "setup_type": "inverse"}]
        strong_primary = [{"code": "3000", "score": 8.0, "setup_type": "primary"}]

        self.assertEqual(select_daytrade_candidates([], strong_oversold, fallback, max_count=1)[0]["code"], "1579")
        self.assertEqual(select_daytrade_candidates(primary, strong_oversold, fallback, max_count=1)[0]["code"], "2000")
        self.assertEqual(select_daytrade_candidates(medium_primary, strong_oversold, fallback, max_count=1)[0]["code"], "2000")
        self.assertEqual(select_daytrade_candidates(strong_primary, strong_oversold, fallback, max_count=1)[0]["code"], "3000")
        self.assertEqual(select_daytrade_candidates([], [], [], catchup, max_count=1)[0]["code"], "2500")
        self.assertEqual(select_daytrade_candidates(strong_primary, [], [], catchup, max_count=1)[0]["code"], "3000")
        self.assertEqual(select_daytrade_candidates([], [], [], [], inverse, max_count=1)[0]["code"], "1459")
        self.assertIn("1459", extend_daytrade_targets_with_inverse_codes(["1000"]))
        self.assertTrue(should_replace_primary_with_preferred_etf(10.0, 11.1, 0.65))
        self.assertFalse(should_replace_primary_with_preferred_etf(10.1, 11.5, 0.70))
        self.assertFalse(should_replace_primary_with_preferred_etf(9.0, 9.9, 0.70))
        self.assertFalse(should_replace_primary_with_preferred_etf(9.0, 11.5, 0.64))

    def test_daytrade_candidate_selection_can_prefer_bull_etf_over_marginal_primary(self):
        primary = [{"code": "3000", "score": 9.5, "setup_type": "primary"}]
        strong_oversold = [{"code": "1579", "score": 11.0, "setup_type": "strong_oversold"}]
        catchup = [{"code": "1306", "score": 10.8, "setup_type": "catchup_rs"}]

        self.assertEqual(
            select_daytrade_candidates(
                primary,
                strong_oversold,
                [],
                catchup,
                breadth_val=0.70,
                max_count=1,
            )[0]["code"],
            "1579",
        )
        self.assertEqual(
            select_daytrade_candidates(
                primary,
                strong_oversold,
                [],
                catchup,
                breadth_val=0.60,
                max_count=1,
            )[0]["code"],
            "3000",
        )

    def test_daytrade_candidate_selection_can_replace_tuesday_mid_breadth_primary_with_fallback(self):
        primary = [{"code": "3000", "score": 7.0, "setup_type": "primary"}]
        fallback = [{"code": "4000", "score": 7.7, "setup_type": "fallback"}]

        self.assertEqual(
            select_daytrade_candidates(
                primary,
                [],
                fallback,
                breadth_val=0.55,
                trade_weekday=1,
                max_count=1,
            )[0]["code"],
            "4000",
        )
        self.assertEqual(
            select_daytrade_candidates(
                primary,
                [],
                fallback,
                breadth_val=0.55,
                trade_weekday=2,
                max_count=1,
            )[0]["code"],
            "3000",
        )

if __name__ == '__main__':
    unittest.main()
