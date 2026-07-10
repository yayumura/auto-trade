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
    resolve_daytrade_strong_oversold_equity_notional_pct,
    resolve_daytrade_strong_oversold_risk_budget_pct,
    resolve_daytrade_strong_oversold_notional_pct,
    resolve_daytrade_strong_oversold_size_multiplier,
    resolve_daytrade_primary_notional_pct,
    resolve_daytrade_primary_risk_budget_pct,
    resolve_daytrade_primary_size_multiplier,
    score_daytrade_inverse_open_setup,
    extend_daytrade_targets_with_inverse_codes,
    should_replace_primary_with_preferred_etf,
    get_daytrade_week_key,
    has_daytrade_rebound_confirmation,
    is_daytrade_catchup_market_allowed,
    is_daytrade_catchup_rs_high_breadth_filtered,
    is_daytrade_catchup_rs_wednesday_mid_breadth_low_gap_hot_open_filtered,
    is_daytrade_catchup_rs_wednesday_low_breadth_weak_market_low_open_filtered,
    is_daytrade_catchup_rs_wednesday_mid_breadth_negative_open_extreme_rs_filtered,
    is_daytrade_catchup_rs_monday_low_breadth_deep_gap_stretched_open_filtered,
    is_daytrade_catchup_rs_monday_low_breadth_low_open_filtered,
    is_daytrade_catchup_rs_tuesday_low_breadth_low_open_filtered,
    is_daytrade_catchup_rs_low_breadth_high_market_ratio_filtered,
    is_daytrade_catchup_rs_tuesday_low_breadth_very_hot_market_filtered,
    is_daytrade_catchup_rs_friday_low_breadth_filtered,
    is_daytrade_catchup_rs_friday_hot_market_low_breadth_filtered,
    is_daytrade_catchup_rs_monday_low_score_filtered,
    is_daytrade_catchup_rs_monday_low_breadth_weak_market_stretched_open_high_rsi_filtered,
    is_daytrade_catchup_rs_monday_mid_breadth_stretched_open_filtered,
    is_daytrade_catchup_rs_tuesday_low_breadth_weak_market_filtered,
    is_daytrade_catchup_rs_tuesday_low_breadth_moderate_market_filtered,
    is_daytrade_catchup_rs_tuesday_low_breadth_high_market_stretched_open_filtered,
    is_daytrade_catchup_rs_monday_low_breadth_hot_gap_low_open_filtered,
    is_daytrade_fallback_market_allowed,
    is_daytrade_fallback_hot_market_filtered,
    is_daytrade_fallback_low_breadth_hot_market_mid_open_filtered,
    is_daytrade_fallback_low_breadth_hot_market_high_open_filtered,
    is_daytrade_fallback_low_breadth_strong_prev_return_filtered,
    is_daytrade_fallback_tuesday_weak_market_high_open_filtered,
    is_daytrade_fallback_tuesday_friday_mid_market_filtered,
    is_daytrade_fallback_wednesday_low_breadth_high_open_filtered,
    is_daytrade_primary_friday_low_open_filtered,
    is_daytrade_inverse_market_allowed,
    is_daytrade_inverse_pullback_market_allowed,
    is_daytrade_inverse_rebreak_context,
    is_daytrade_monthly_risk_blocked,
    is_daytrade_market_allowed,
    is_daytrade_strong_oversold_market_allowed,
    is_daytrade_strong_oversold_tuesday_stretched_open_filtered,
    is_daytrade_strong_oversold_thursday_mid_breadth_filtered,
    is_daytrade_strong_oversold_monday_low_breadth_hot_market_filtered,
    is_daytrade_weekly_profit_guard_active,
    is_daytrade_bull_etf_price_allowed,
    resolve_daytrade_intraday_stop_mult,
    resolve_daytrade_intraday_target_mult,
    is_daytrade_primary_failed_runup_exit,
    normalize_tick_size,
    resolve_daytrade_live_exit_decision,
    resolve_daytrade_breadth_exposure_scale,
    resolve_daytrade_buying_power,
    resolve_daytrade_inverse_buying_power,
    resolve_daytrade_selected_leverage,
    resolve_daytrade_selected_inverse_buying_power_leverage,
    resolve_daytrade_scan_min_turnover,
    resolve_daytrade_inverse_min_turnover,
    DAYTRADE_PRIMARY_HOT_CONTINUATION_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_LOW_RS_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_STRETCHED_STALL_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_FRAGILE_HOT_MARKET_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_HEATED_CONTINUATION_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_HIGH_BREADTH_MID_HOT_MARKET_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_MAX_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_LOW_SCORE_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_LOW_SCORE_HOT_MARKET_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_MID_BREADTH_HOT_MARKET_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_WEDNESDAY_HOT_GAP_BELOW_SMA_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_HOT_MARKET_MID_BREADTH_MID_SCORE_MODERATE_PREV_RETURN_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_WEDNESDAY_HIGH_MARKET_MID_BREADTH_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_WEDNESDAY_LOW_BREADTH_HIGH_GAP_HIGH_SCORE_STRONG_OPEN_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_TUESDAY_HIGH_MARKET_MID_BREADTH_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_TUESDAY_HIGH_BREADTH_HIGH_SCORE_STRETCHED_OPEN_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_MONDAY_BROAD_MID_SCORE_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_TEPID_MARKET_STRONG_PRIOR_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_TEPID_LOW_BREADTH_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_TEPID_LOW_BREADTH_HIGH_GAP_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_TUESDAY_OVERHEATED_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_LOW_BREADTH_WEAK_MARKET_SCORE6_8_POS_GAP_LOW_PREV_RETURN_EQUITY_NOTIONAL_PCT,
    resolve_daytrade_primary_equity_notional_pct,
    resolve_daytrade_fallback_notional_pct,
    resolve_daytrade_fallback_equity_notional_pct,
    resolve_daytrade_catchup_equity_notional_pct,
    resolve_daytrade_catchup_notional_pct,
    resolve_daytrade_catchup_size_multiplier,
    resolve_daytrade_weekly_leverage,
    select_daytrade_candidates,
    DAYTRADE_BULL_ETF_LOW_BREADTH_REBOUND_LEVERAGE,
    DAYTRADE_BULL_ETF_LOW_BREADTH_REBOUND_NOTIONAL_PCT,
    DAYTRADE_CATCHUP_GAPDOWN_EQUITY_NOTIONAL_PCT,
    DAYTRADE_CATCHUP_GAPDOWN_NOTIONAL_PCT,
    DAYTRADE_CATCHUP_RS_EQUITY_NOTIONAL_PCT,
    DAYTRADE_CATCHUP_RS_NOTIONAL_PCT,
    DAYTRADE_CATCHUP_RS_HOT_PREV_RETURN_EQUITY_NOTIONAL_PCT,
    DAYTRADE_CATCHUP_RS_STRONG_CONTINUATION_EQUITY_NOTIONAL_PCT,
    DAYTRADE_CATCHUP_RS_STRONG_CONTINUATION_RISK_BUDGET_PCT,
    DAYTRADE_SELECTED_CATCHUP_RS_STRONG_CONTINUATION_MAX_LEVERAGE,
    DAYTRADE_CATCHUP_GAPDOWN_LOW_BREADTH_PROBE_LEVERAGE,
    DAYTRADE_CATCHUP_RS_TUESDAY_LOW_BREADTH_PROBE_LEVERAGE,
    DAYTRADE_FALLBACK_MAX_NOTIONAL_PCT,
    DAYTRADE_FALLBACK_EQUITY_NOTIONAL_PCT,
    DAYTRADE_FALLBACK_HIGH_BREADTH_EXTENDED_EQUITY_NOTIONAL_PCT,
    DAYTRADE_FALLBACK_MONDAY_MID_BREADTH_NEUTRAL_MARKET_SIZEUP_NOTIONAL_PCT,
    DAYTRADE_FALLBACK_LOW_BREADTH_CONTINUATION_EQUITY_NOTIONAL_PCT,
    DAYTRADE_FALLBACK_TUESDAY_FRIDAY_WEAK_MARKET_EQUITY_NOTIONAL_PCT,
    DAYTRADE_INVERSE_BUYING_POWER_LEVERAGE,
    DAYTRADE_SELECTED_FRAGILE_HOT_MARKET_MAX_LEVERAGE,
    DAYTRADE_SELECTED_HEATED_POSITIVE_GAP_MAX_LEVERAGE,
    DAYTRADE_SELECTED_TUESDAY_STRONG_OVERSOLD_HOT_MARKET_MAX_LEVERAGE,
    DAYTRADE_SELECTED_TUESDAY_STRONG_OVERSOLD_LOSSY_HOT_MARKET_MAX_LEVERAGE,
    DAYTRADE_SELECTED_TUESDAY_STRONG_OVERSOLD_NEAR_SMA_MAX_LEVERAGE,
    DAYTRADE_SELECTED_LATE_WEEK_HIGH_SCORE_HOT_MARKET_MAX_LEVERAGE,
    DAYTRADE_SELECTED_LOW_SCORE_OVERHEATED_NO_TRADE_MAX_LEVERAGE,
    DAYTRADE_SELECTED_LOW_SCORE_HOT_GAP_MAX_LEVERAGE,
    DAYTRADE_SELECTED_OVERHEATED_LOW_BREADTH_MAX_LEVERAGE,
    DAYTRADE_SELECTED_WEDNESDAY_NONPOSITIVE_GAP_NO_TRADE_MAX_LEVERAGE,
)
class TestLogic(unittest.TestCase):
    def _board_lot_candidate(
        self,
        code,
        score,
        setup_type,
        *,
        open_price,
        gap_pct=0.01,
        atr=100.0,
        stop_mult=0.8,
        notional_pct=1.0,
        equity_notional_pct=1.0,
        turnover=1_000_000_000.0,
    ):
        return {
            "code": code,
            "score": score,
            "setup_type": setup_type,
            "open": open_price,
            "price": open_price,
            "atr": atr,
            "gap_pct": gap_pct,
            "stop_mult": stop_mult,
            "notional_pct": notional_pct,
            "equity_notional_pct": equity_notional_pct,
            "turnover": turnover,
        }
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
    def test_realtime_buffer_previous_close_is_separate_from_session_open(self):
        buffer = RealtimeBuffer("1000")
        buffer.set_previous_close(98.0)
        self.assertEqual(buffer.get_previous_close(), 98.0)
        ts = pd.Timestamp("2026-04-21 09:05:00")
        buffer.update(100.0, 1_000, ts)
        self.assertEqual(buffer.get_session_open(), 100.0)
        self.assertEqual(buffer.get_previous_close(), 98.0)
        self.assertNotEqual(buffer.get_session_open(), buffer.get_previous_close())
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
    def test_daytrade_catchup_rs_tuesday_low_breadth_high_rs_size_multiplier(self):
        self.assertEqual(
            resolve_daytrade_catchup_size_multiplier(
                setup_type="catchup_rs",
                breadth_val=0.482715,
                gap_pct=0.007150,
                market_ratio=1.030712,
                score=8.297658,
                rs_alpha=52.968750,
                open_vs_sma_atr=1.051775,
                trade_date=pd.Timestamp("2022-12-13"),
            ),
            2.5,
        )
        self.assertEqual(
            resolve_daytrade_catchup_size_multiplier(
                setup_type="catchup_rs",
                breadth_val=0.409177,
                gap_pct=0.017699,
                market_ratio=1.013924,
                score=12.885431,
                rs_alpha=83.243243,
                open_vs_sma_atr=0.854260,
                trade_date=pd.Timestamp("2024-10-01"),
            ),
            2.5,
        )
        self.assertEqual(
            resolve_daytrade_catchup_size_multiplier(
                setup_type="catchup_rs",
                breadth_val=0.326210,
                gap_pct=0.004695,
                market_ratio=1.004794,
                score=10.357805,
                rs_alpha=35.324015,
                open_vs_sma_atr=2.198216,
                trade_date=pd.Timestamp("2024-10-29"),
            ),
            1.0,
        )

    def test_daytrade_catchup_rs_caps_hot_prev_return(self):
        eligible = evaluate_daytrade_catchup_open_setups(
            102.0,
            100.0,
            99.0,
            0.40,
            prev_atr=2.0,
            prev_low=98.0,
            prev_rsi2=60.0,
            rs_alpha=30.0,
            prev_prev_close=92.593,
            prev_sma_trend=90.0,
        )
        self.assertTrue(any(item["setup_type"] == "catchup_rs" for item in eligible))
        capped = evaluate_daytrade_catchup_open_setups(
            102.0,
            100.0,
            99.0,
            0.40,
            prev_atr=2.0,
            prev_low=98.0,
            prev_rsi2=60.0,
            rs_alpha=30.0,
            prev_prev_close=91.743,
            prev_sma_trend=90.0,
        )
        self.assertFalse(any(item["setup_type"] == "catchup_rs" for item in capped))
    def test_daytrade_weekly_leverage_catches_up_until_target(self):
        self.assertEqual(get_daytrade_week_key(pd.Timestamp("2026-04-24")), "2026-W17")
        self.assertEqual(get_daytrade_week_key(pd.Timestamp("2026-04-20")), "2026-W17")
        self.assertAlmostEqual(resolve_daytrade_weekly_leverage(1.0, 1_000_000, 1_000_000), 30.0)
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
            30.0,
        )
        self.assertAlmostEqual(resolve_daytrade_weekly_leverage(1.0, 1_000_000, 1_004_999), 30.0)
        self.assertAlmostEqual(resolve_daytrade_weekly_leverage(1.0, 1_000_000, 1_005_000), 30.0)
        self.assertAlmostEqual(resolve_daytrade_weekly_leverage(1.0, 1_000_000, 1_009_999), 30.0)
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
        self.assertFalse(
            is_daytrade_weekly_profit_guard_active(
                1_000_000,
                1_009_000,
                current_time=pd.Timestamp("2026-04-23"),
            )
        )
        self.assertTrue(
            is_daytrade_weekly_profit_guard_active(
                1_000_000,
                1_010_000,
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
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                0.0,
                [{"setup_type": "catchup_rs", "score": 10.0, "gap_pct": 0.009}],
                0.30,
                trade_weekday=1,
            ),
            0.25,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.5,
                [{"setup_type": "catchup_rs", "score": 10.0, "gap_pct": 0.009}],
                0.30,
                trade_weekday=1,
            ),
            1.5,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "primary", "score": 9.0, "gap_pct": 0.004}],
                0.50,
                market_ratio=1.16,
                trade_weekday=4,
            ),
            DAYTRADE_SELECTED_FRAGILE_HOT_MARKET_MAX_LEVERAGE,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "primary", "score": 7.5, "gap_pct": 0.004}],
                0.59,
                market_ratio=1.18,
                trade_weekday=0,
            ),
            DAYTRADE_SELECTED_LOW_SCORE_HOT_GAP_MAX_LEVERAGE,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "primary", "score": 7.5, "gap_pct": 0.004}],
                0.59,
                market_ratio=1.20,
                trade_weekday=0,
            ),
            DAYTRADE_SELECTED_LOW_SCORE_OVERHEATED_NO_TRADE_MAX_LEVERAGE,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "primary", "score": 7.5, "gap_pct": -0.004}],
                0.59,
                market_ratio=1.18,
                trade_weekday=0,
            ),
            1.25,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "primary", "score": 7.5, "gap_pct": 0.004}],
                0.50,
                market_ratio=1.18,
                trade_weekday=0,
            ),
            DAYTRADE_SELECTED_LOW_SCORE_HOT_GAP_MAX_LEVERAGE,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "primary", "score": 11.5, "gap_pct": 0.004}],
                0.59,
                market_ratio=1.18,
                trade_weekday=1,
            ),
            DAYTRADE_SELECTED_HEATED_POSITIVE_GAP_MAX_LEVERAGE,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "primary", "score": 9.0, "gap_pct": 0.004}],
                0.70,
                market_ratio=1.18,
                trade_weekday=1,
            ),
            0.10,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "strong_oversold", "score": 18.0, "prev_return": -0.01, "open_vs_sma_atr": 0.2}],
                0.60,
                market_ratio=1.15,
                trade_weekday=1,
            ),
            DAYTRADE_SELECTED_TUESDAY_STRONG_OVERSOLD_NEAR_SMA_MAX_LEVERAGE,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "strong_oversold", "score": 17.670299, "prev_return": -0.026398, "open_vs_sma_atr": 1.455014}],
                0.566939,
                market_ratio=1.030775,
                trade_weekday=1,
            ),
            DAYTRADE_SELECTED_TUESDAY_STRONG_OVERSOLD_LOSSY_HOT_MARKET_MAX_LEVERAGE,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "strong_oversold", "score": 18.0, "prev_return": -0.01, "open_vs_sma_atr": 0.3}],
                0.60,
                market_ratio=1.15,
                trade_weekday=1,
            ),
            DAYTRADE_SELECTED_TUESDAY_STRONG_OVERSOLD_HOT_MARKET_MAX_LEVERAGE,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "strong_oversold", "score": 18.0, "prev_return": -0.01, "open_vs_sma_atr": 1.2}],
                0.60,
                market_ratio=1.10,
                trade_weekday=1,
            ),
            DAYTRADE_SELECTED_TUESDAY_STRONG_OVERSOLD_HOT_MARKET_MAX_LEVERAGE,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "strong_oversold", "score": 18.0, "prev_return": -0.01, "open_vs_sma_atr": 1.2}],
                0.60,
                market_ratio=1.01,
                trade_weekday=1,
            ),
            1.25,
        )
        self.assertEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "strong_oversold", "score": 17.858066, "open_vs_sma_atr": 8.653726}],
                0.64,
                market_ratio=1.141145,
                trade_weekday=3,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "strong_oversold", "score": 18.948339, "open_vs_sma_atr": 6.753719}],
                0.72,
                market_ratio=1.121681,
                trade_weekday=2,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "primary", "score": 10.0, "gap_pct": 0.012}],
                0.68,
                market_ratio=1.10,
                trade_weekday=2,
            ),
            0.10,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "primary", "score": 8.5, "gap_pct": 0.0}],
                0.70,
                market_ratio=1.12,
                trade_weekday=2,
            ),
            DAYTRADE_SELECTED_WEDNESDAY_NONPOSITIVE_GAP_NO_TRADE_MAX_LEVERAGE,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "primary", "score": 8.5, "gap_pct": 0.0}],
                0.64,
                market_ratio=1.12,
                trade_weekday=2,
            ),
            1.25,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "primary", "score": 10.5, "gap_pct": 0.0}],
                0.59,
                market_ratio=1.12,
                trade_weekday=2,
            ),
            1.25,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "primary", "score": 11.5, "gap_pct": 0.004}],
                0.59,
                market_ratio=1.18,
                trade_weekday=2,
            ),
            DAYTRADE_SELECTED_LATE_WEEK_HIGH_SCORE_HOT_MARKET_MAX_LEVERAGE,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "primary", "score": 11.5, "gap_pct": 0.004}],
                0.59,
                market_ratio=1.22,
                trade_weekday=2,
            ),
            DAYTRADE_SELECTED_LATE_WEEK_HIGH_SCORE_HOT_MARKET_MAX_LEVERAGE,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "primary", "score": 11.5, "gap_pct": 0.0}],
                0.59,
                market_ratio=1.18,
                trade_weekday=2,
            ),
            DAYTRADE_SELECTED_LATE_WEEK_HIGH_SCORE_HOT_MARKET_MAX_LEVERAGE,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "primary", "score": 10.0, "gap_pct": 0.004}],
                0.50,
                market_ratio=1.10,
                trade_weekday=0,
            ),
            1.25,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "inverse", "score": 10.0, "gap_pct": 0.004}],
                0.50,
                market_ratio=1.16,
                trade_weekday=0,
            ),
            1.25,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "primary", "score": 11.5, "gap_pct": -0.004}],
                0.59,
                market_ratio=1.22,
                trade_weekday=2,
            ),
            DAYTRADE_SELECTED_LATE_WEEK_HIGH_SCORE_HOT_MARKET_MAX_LEVERAGE,
        )
        self.assertEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "primary", "score": 5.952687, "gap_pct": 0.018349}],
                0.689503,
                market_ratio=1.10739,
                trade_weekday=0,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "primary", "score": 4.222628, "gap_pct": 0.015979}],
                0.725959,
                market_ratio=1.13799,
                trade_weekday=0,
            ),
            1.25,
        )
        self.assertEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "primary", "score": 5.227397, "gap_pct": 0.000856}],
                0.587052,
                market_ratio=1.115841,
                trade_weekday=2,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "primary", "score": 5.645373, "gap_pct": 0.00196}],
                0.605908,
                market_ratio=1.135153,
                trade_weekday=2,
            ),
            1.25,
        )
        self.assertEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "primary", "score": 3.826079, "gap_pct": 0.014671, "prev_rsi2": 65.0}],
                0.604023,
                market_ratio=1.018327,
                trade_weekday=3,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "primary", "score": 5.10499, "gap_pct": 0.012685, "prev_rsi2": 38.461538}],
                0.632307,
                market_ratio=1.004259,
                trade_weekday=3,
            ),
            1.25,
        )
        self.assertEqual(
            resolve_daytrade_selected_leverage(
                0.0,
                [{"setup_type": "catchup_rs", "score": 12.0, "gap_pct": 0.009}],
                0.30,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{
                    "setup_type": "catchup_rs",
                    "score": 18.903164,
                    "prev_return": 0.071082,
                    "open_vs_sma_atr": -0.2773,
                }],
                0.422376,
                market_ratio=1.31693,
                trade_weekday=1,
            ),
            DAYTRADE_SELECTED_CATCHUP_RS_STRONG_CONTINUATION_MAX_LEVERAGE,
        )
        self.assertEqual(
            resolve_daytrade_selected_leverage(
                0.0,
                [{"setup_type": "catchup_rs", "score": 10.0, "gap_pct": 0.011}],
                0.30,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                0.0,
                [{"setup_type": "catchup_gapdown", "score": 7.0, "gap_pct": -0.012}],
                0.30,
                market_ratio=1.08,
                trade_weekday=2,
            ),
            DAYTRADE_CATCHUP_GAPDOWN_LOW_BREADTH_PROBE_LEVERAGE,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                0.0,
                [{"setup_type": "catchup_rs", "score": 8.5, "gap_pct": 0.007}],
                0.30,
                trade_weekday=1,
            ),
            DAYTRADE_CATCHUP_RS_TUESDAY_LOW_BREADTH_PROBE_LEVERAGE,
        )
        self.assertEqual(
            resolve_daytrade_selected_leverage(
                0.0,
                [{"setup_type": "catchup_gapdown", "score": 7.0, "gap_pct": -0.012}],
                0.30,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_selected_leverage(
                0.0,
                [{"setup_type": "catchup_gapdown", "score": 8.0, "gap_pct": -0.012}],
                0.30,
                trade_weekday=2,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                0.0,
                [{
                    "setup_type": "bull_etf_rebound",
                    "score": 8.5,
                    "gap_pct": 0.034,
                    "prev_return": 0.017,
                    "prev_rsi2": 46.2,
                    "open_vs_sma_atr": -2.9,
                    "code": "1570",
                }],
                0.15,
            ),
            DAYTRADE_BULL_ETF_LOW_BREADTH_REBOUND_LEVERAGE,
        )
        self.assertEqual(
            resolve_daytrade_selected_leverage(
                0.0,
                [{
                    "setup_type": "bull_etf_rebound",
                    "score": 8.5,
                    "gap_pct": 0.034,
                    "prev_return": 0.017,
                    "prev_rsi2": 46.2,
                    "open_vs_sma_atr": -2.9,
                    "code": "1570",
                }],
                0.25,
            ),
            0.0,
        )
        self.assertAlmostEqual(DAYTRADE_BULL_ETF_LOW_BREADTH_REBOUND_NOTIONAL_PCT, 1.0)
        self.assertTrue(is_daytrade_bull_etf_price_allowed(22_795.5, "1570.T", 0.15))
        self.assertFalse(is_daytrade_bull_etf_price_allowed(22_795.5, "7203.T", 0.15))
        self.assertFalse(is_daytrade_bull_etf_price_allowed(22_795.5, "1570.T", 0.25))
        self.assertAlmostEqual(resolve_daytrade_scan_min_turnover("1368", 0.09), 125_000_000.0)
        self.assertAlmostEqual(resolve_daytrade_scan_min_turnover("1368", 0.10), 300_000_000.0)
        self.assertAlmostEqual(resolve_daytrade_scan_min_turnover("7203", 0.09), 300_000_000.0)
        self.assertAlmostEqual(resolve_daytrade_inverse_min_turnover(0.09), 125_000_000.0)
        self.assertAlmostEqual(resolve_daytrade_inverse_min_turnover(0.10), 300_000_000.0)
        self.assertAlmostEqual(
            resolve_daytrade_selected_inverse_buying_power_leverage(
                [{"setup_type": "inverse", "turnover": 140_000_000.0}],
                0.09,
            ),
            0.60,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_inverse_buying_power_leverage(
                [{"setup_type": "inverse", "adv_yen": 140_000_000.0}],
                0.09,
            ),
            0.60,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_inverse_buying_power_leverage(
                [{"setup_type": "inverse", "turnover": 400_000_000.0}],
                0.09,
            ),
            DAYTRADE_INVERSE_BUYING_POWER_LEVERAGE,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_inverse_buying_power_leverage(
                [{"setup_type": "inverse", "turnover": 140_000_000.0}],
                0.12,
            ),
            DAYTRADE_INVERSE_BUYING_POWER_LEVERAGE,
        )
        self.assertAlmostEqual(resolve_daytrade_breadth_exposure_scale(0.49), 0.35)
        self.assertAlmostEqual(resolve_daytrade_breadth_exposure_scale(0.50), 1.0)
        self.assertAlmostEqual(DAYTRADE_FALLBACK_EQUITY_NOTIONAL_PCT, 1.20)
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.65,
                gap_pct=0.008,
                open_vs_sma_atr=0.4,
                trade_weekday=1,
            ),
            0.50,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.65,
                gap_pct=0.0,
                open_vs_sma_atr=0.4,
                trade_weekday=1,
            ),
            0.75,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.72,
                gap_pct=0.008,
                open_vs_sma_atr=3.4,
                trade_weekday=0,
            ),
            0.50,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.72,
                gap_pct=0.015,
                open_vs_sma_atr=3.4,
                trade_weekday=0,
            ),
            DAYTRADE_PRIMARY_MAX_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.52,
                gap_pct=0.028,
                open_vs_sma_atr=0.4,
                trade_weekday=0,
            ),
            1.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.52,
                gap_pct=0.028,
                open_vs_sma_atr=1.2,
                trade_weekday=0,
            ),
            DAYTRADE_PRIMARY_MAX_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.72,
                gap_pct=0.020,
                open_vs_sma_atr=-0.2,
                trade_weekday=2,
            ),
            0.50,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.72,
                gap_pct=0.020,
                open_vs_sma_atr=0.2,
                trade_weekday=2,
            ),
            DAYTRADE_PRIMARY_MAX_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.650534,
                gap_pct=-0.000454,
                open_vs_sma_atr=2.498551,
                market_ratio=1.167908,
                primary_score=4.880015,
                rs_alpha=47.015672,
                trade_weekday=2,
                prev_return=0.018010,
                prev_rsi2=76.470588,
            ),
            3.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.749214,
                gap_pct=0.0,
                open_vs_sma_atr=2.031484,
                market_ratio=1.189645,
                primary_score=7.528062,
                rs_alpha=84.95212,
                trade_weekday=2,
                prev_return=0.011976,
                prev_rsi2=72.727273,
            ),
            6.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.806411,
                gap_pct=0.021277,
                open_vs_sma_atr=-0.166773,
                market_ratio=1.149692,
                primary_score=10.846057,
                rs_alpha=76.502146,
                trade_weekday=1,
                prev_return=0.032643,
                prev_rsi2=47.706422,
            ),
            3.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.70,
                gap_pct=0.024,
                market_ratio=1.10,
                open_vs_sma_atr=1.8,
                primary_score=9.0,
                rs_alpha=75.0,
                trade_weekday=2,
            ),
            DAYTRADE_PRIMARY_WEDNESDAY_HIGH_MARKET_MID_BREADTH_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.685732,
                gap_pct=0.000276,
                open_vs_sma_atr=1.622298,
                market_ratio=1.152172,
                primary_score=5.241099,
                prev_return=0.024852,
                prev_rsi2=79.279279,
                trade_weekday=3,
            ),
            3.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.652420,
                gap_pct=0.010324,
                open_vs_sma_atr=2.032328,
                market_ratio=1.168685,
                primary_score=4.003971,
                trade_weekday=3,
            ),
            2.5,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.759899,
                gap_pct=0.029155,
                market_ratio=1.269486,
                open_vs_sma_atr=3.736419,
                primary_score=13.909204,
                trade_weekday=2,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.874293,
                gap_pct=0.026664,
                market_ratio=1.114357,
                open_vs_sma_atr=3.803930,
                primary_score=4.706037,
                trade_weekday=2,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.68,
                gap_pct=0.008,
                open_vs_sma_atr=3.0,
                market_ratio=1.12,
                primary_score=7.5,
                trade_weekday=0,
            ),
            0.25,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.68,
                gap_pct=0.008,
                open_vs_sma_atr=3.0,
                market_ratio=1.12,
                primary_score=7.5,
                trade_weekday=1,
            ),
            0.25,
        )
        # Tuesday low-open / mid-breadth / hot-market pocket that was loss-only
        # in train across several score regimes.
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.6863607793840352,
                gap_pct=-0.0038026618633043574,
                open_vs_sma_atr=0.37455460071264035,
                market_ratio=1.1519086775102514,
                primary_score=3.365181318578275,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.6216216216216216,
                gap_pct=0.0,
                open_vs_sma_atr=-0.44680030840400964,
                market_ratio=1.2699288787489131,
                primary_score=12.494224265711345,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.6637335009428033,
                gap_pct=0.02682506227246595,
                open_vs_sma_atr=0.7929659173314022,
                market_ratio=1.2226795933422674,
                primary_score=5.342074867666413,
                trade_weekday=1,
            ),
            0.0,
        )
        # Tuesday's low-score / stretched-open / hot-market pocket was loss-only in train.
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.559397,
                gap_pct=-0.001188,
                open_vs_sma_atr=2.323431,
                market_ratio=1.130825,
                primary_score=3.396698,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.502828,
                gap_pct=-0.000589,
                open_vs_sma_atr=1.801257,
                market_ratio=1.103130,
                primary_score=6.487512,
                trade_weekday=1,
            ),
            0.0,
        )
        # Tuesday's stretched-open / mid-breadth / hot-market pocket only stays
        # out when RSI2 is still weak; stronger RSI2 should remain tradable.
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.6216216216216216,
                gap_pct=-0.000999,
                open_vs_sma_atr=2.549284,
                market_ratio=1.2699288787489131,
                prev_rsi2=70.921986,
                primary_score=5.984792,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.6253928346951603,
                gap_pct=-0.0037570444583594487,
                open_vs_sma_atr=2.2033573141486795,
                market_ratio=1.218975925631562,
                prev_rsi2=71.24999999940626,
                primary_score=4.678518073725999,
                trade_weekday=1,
            ),
            0.0,
        )
        # Wednesday's mid-breadth / hot-market pocket only stays out when the
        # previous return is still weak; slightly stronger follow-through should
        # remain tradable.
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.6964173475801383,
                gap_pct=-0.0026189436927106513,
                open_vs_sma_atr=0.384737678855323,
                market_ratio=1.237121892963642,
                prev_return=0.006590509666080768,
                primary_score=5.429713248169915,
                trade_weekday=2,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.6612193588937775,
                gap_pct=-0.001285897985426443,
                open_vs_sma_atr=1.251111111111115,
                market_ratio=1.2671894465073452,
                prev_return=0.012147505422993587,
                primary_score=5.745171403442753,
                trade_weekday=2,
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.6115650534255186,
                gap_pct=0.0009590792838873874,
                open_vs_sma_atr=0.7016248153618907,
                market_ratio=1.2230871015060332,
                prev_return=0.016905071521456483,
                primary_score=5.602020862010071,
                trade_weekday=2,
            ),
            0.0,
        )
        # Wednesday's hot-gap / below-SMA pocket keeps a small size for the
        # lower-score cases, but the high-score tail was loss-only in train.
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.512256,
                gap_pct=0.015928,
                open_vs_sma_atr=-0.689298,
                market_ratio=1.013408,
                primary_score=6.552053,
                trade_weekday=2,
            ),
            DAYTRADE_PRIMARY_WEDNESDAY_HOT_GAP_BELOW_SMA_EQUITY_NOTIONAL_PCT,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.4600879949717159,
                gap_pct=0.015341701534170138,
                open_vs_sma_atr=-0.38246505717916135,
                market_ratio=1.0688199217184948,
                primary_score=12.713391074956975,
                trade_weekday=2,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.71024512884978,
                gap_pct=0.020883777239709467,
                open_vs_sma_atr=-0.1873278236914588,
                market_ratio=1.0312084190153623,
                primary_score=9.233136360956749,
                trade_weekday=2,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.6222501571338781,
                gap_pct=0.01985461646956721,
                open_vs_sma_atr=-1.1656991696671317,
                market_ratio=1.2007569482199816,
                primary_score=25.145531883126964,
                trade_weekday=2,
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.6442489000628535,
                gap_pct=0.026252983293556076,
                open_vs_sma_atr=-0.3231925554760207,
                market_ratio=1.1079838372579072,
                primary_score=7.3120456262886,
                trade_weekday=2,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.70,
                gap_pct=0.024,
                market_ratio=1.10,
                open_vs_sma_atr=1.2,
                primary_score=9.0,
                rs_alpha=75.0,
                trade_weekday=2,
            ),
            DAYTRADE_PRIMARY_MAX_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.75,
                gap_pct=0.018,
                open_vs_sma_atr=1.2,
                trade_weekday=2,
                prev_return=0.06,
                prev_rsi2=62.0,
            ),
            DAYTRADE_PRIMARY_HOT_CONTINUATION_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.75,
                gap_pct=0.018,
                open_vs_sma_atr=1.2,
                trade_weekday=2,
                prev_return=0.06,
                prev_rsi2=55.0,
            ),
            DAYTRADE_PRIMARY_MAX_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.72,
                gap_pct=0.002,
                open_vs_sma_atr=1.8,
                trade_weekday=0,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.65,
                gap_pct=-0.001,
                open_vs_sma_atr=1.8,
                trade_weekday=1,
            ),
            0.25,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.72,
                gap_pct=0.008,
                open_vs_sma_atr=1.8,
                trade_weekday=1,
            ),
            0.75,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.58,
                gap_pct=0.005,
                open_vs_sma_atr=2.2,
                trade_weekday=3,
            ),
            3.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.52,
                gap_pct=0.005,
                open_vs_sma_atr=2.2,
                trade_weekday=3,
            ),
            1.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.58,
                gap_pct=0.005,
                open_vs_sma_atr=0.8,
                trade_weekday=3,
            ),
            DAYTRADE_PRIMARY_MAX_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.618479,
                gap_pct=0.009074,
                market_ratio=1.15821,
                open_vs_sma_atr=2.167539,
                primary_score=9.72879,
                prev_return=0.031835,
                rs_alpha=81.5486,
                trade_weekday=3,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.618479,
                gap_pct=0.009074,
                market_ratio=1.15821,
                open_vs_sma_atr=2.167539,
                primary_score=9.72879,
                prev_return=0.031835,
                rs_alpha=81.5486,
                trade_weekday=2,
            ),
            DAYTRADE_PRIMARY_MAX_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.685732,
                gap_pct=0.028163,
                market_ratio=1.171012,
                open_vs_sma_atr=1.481463,
                primary_score=9.32145,
                prev_return=0.031827,
                rs_alpha=52.644149,
                trade_weekday=2,
            ),
            DAYTRADE_PRIMARY_HOT_MARKET_MID_BREADTH_MID_SCORE_MODERATE_PREV_RETURN_EQUITY_NOTIONAL_PCT,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.703331,
                gap_pct=0.028163,
                market_ratio=1.171012,
                open_vs_sma_atr=0.481463,
                primary_score=9.32145,
                prev_return=0.031827,
                rs_alpha=52.644149,
                trade_weekday=2,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.619736,
                gap_pct=-0.001676,
                market_ratio=1.194038,
                open_vs_sma_atr=-1.912983,
                primary_score=9.350689,
                prev_return=0.066922,
                rs_alpha=45.590798,
                trade_weekday=2,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.641735,
                gap_pct=0.022026,
                market_ratio=1.125264,
                open_vs_sma_atr=1.502942,
                primary_score=9.196425,
                prev_return=0.047048,
                rs_alpha=41.081417,
                trade_weekday=2,
            ),
            DAYTRADE_PRIMARY_WEDNESDAY_LOW_BREADTH_HIGH_GAP_HIGH_SCORE_STRONG_OPEN_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.641735,
                gap_pct=0.022026,
                market_ratio=1.125264,
                open_vs_sma_atr=0.902942,
                primary_score=9.196425,
                prev_return=0.047048,
                rs_alpha=41.081417,
                trade_weekday=2,
            ),
            DAYTRADE_PRIMARY_MAX_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.715732,
                gap_pct=0.028163,
                market_ratio=1.171012,
                open_vs_sma_atr=0.481463,
                primary_score=9.32145,
                prev_return=0.031827,
                rs_alpha=52.644149,
                trade_weekday=2,
            ),
            DAYTRADE_PRIMARY_MAX_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.72,
                gap_pct=0.007,
                open_vs_sma_atr=1.1,
                market_ratio=1.07,
                primary_score=11.0,
                trade_weekday=2,
            ),
            0.75,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.65,
                gap_pct=0.007,
                open_vs_sma_atr=1.1,
                market_ratio=1.02,
                primary_score=11.0,
                prev_return=0.03,
                trade_weekday=0,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.65,
                gap_pct=0.007,
                open_vs_sma_atr=1.1,
                market_ratio=1.12,
                primary_score=11.0,
                trade_weekday=2,
            ),
            DAYTRADE_PRIMARY_MAX_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.65,
                gap_pct=0.007,
                open_vs_sma_atr=1.1,
                market_ratio=1.02,
                primary_score=11.0,
                prev_return=0.03,
                trade_weekday=1,
            ),
            DAYTRADE_PRIMARY_TEPID_MARKET_STRONG_PRIOR_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.72,
                gap_pct=0.0,
                open_vs_sma_atr=1.1,
                market_ratio=1.20,
                primary_score=11.0,
                trade_weekday=1,
            ),
            DAYTRADE_PRIMARY_TUESDAY_OVERHEATED_EQUITY_NOTIONAL_PCT,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.737901,
                gap_pct=0.002619,
                open_vs_sma_atr=1.096432,
                market_ratio=1.119219,
                primary_score=8.3232,
                trade_weekday=4,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.745443,
                gap_pct=0.016726,
                open_vs_sma_atr=1.079632,
                market_ratio=1.221709,
                primary_score=8.054856,
                trade_weekday=3,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.676304,
                gap_pct=0.0,
                open_vs_sma_atr=-1.468652,
                market_ratio=1.220428,
                primary_score=8.460589,
                trade_weekday=4,
            ),
            DAYTRADE_PRIMARY_MAX_EQUITY_NOTIONAL_PCT,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.436204,
                gap_pct=-0.002725,
                open_vs_sma_atr=-0.338223,
                market_ratio=1.00354,
                primary_score=3.560024,
                trade_weekday=0,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.710874,
                gap_pct=0.00974,
                open_vs_sma_atr=2.73,
                market_ratio=1.096044,
                primary_score=6.483152,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.706474,
                gap_pct=0.0,
                open_vs_sma_atr=2.788099,
                market_ratio=1.088991,
                primary_score=6.343471,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.651163,
                gap_pct=0.0,
                open_vs_sma_atr=0.9,
                market_ratio=1.127503,
                primary_score=4.72867,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.625393,
                gap_pct=-0.003757,
                open_vs_sma_atr=1.0,
                market_ratio=1.218976,
                primary_score=4.678518,
                trade_weekday=1,
            ),
            0.75,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.706474,
                gap_pct=0.0,
                open_vs_sma_atr=2.788099,
                market_ratio=1.088991,
                primary_score=6.6,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.64,
                gap_pct=0.007,
                open_vs_sma_atr=1.2,
                market_ratio=1.20,
                primary_score=8.5,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.80,
                gap_pct=0.012,
                open_vs_sma_atr=0.0,
                market_ratio=1.20,
                primary_score=7.0,
                trade_weekday=3,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.80,
                gap_pct=0.012,
                open_vs_sma_atr=0.0,
                market_ratio=1.20,
                primary_score=13.0,
                trade_weekday=3,
            ),
            DAYTRADE_PRIMARY_MAX_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.65,
                gap_pct=0.007,
                open_vs_sma_atr=1.1,
                market_ratio=1.02,
                primary_score=11.0,
                prev_return=0.03,
                trade_weekday=3,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.65,
                gap_pct=0.007,
                open_vs_sma_atr=1.1,
                market_ratio=1.02,
                primary_score=11.0,
                prev_return=0.03,
                trade_weekday=4,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.60,
                gap_pct=0.012,
                open_vs_sma_atr=0.8,
                market_ratio=1.10,
                primary_score=9.0,
                prev_return=0.01,
                trade_weekday=0,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.80,
                gap_pct=0.012,
                open_vs_sma_atr=0.0,
                market_ratio=1.20,
                primary_score=7.0,
                prev_return=0.0,
                trade_weekday=3,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.80,
                gap_pct=0.012,
                open_vs_sma_atr=0.0,
                market_ratio=1.20,
                primary_score=13.0,
                prev_return=0.0,
                trade_weekday=3,
            ),
            DAYTRADE_PRIMARY_MAX_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.86,
                gap_pct=0.021,
                open_vs_sma_atr=1.4,
                market_ratio=1.09,
                primary_score=13.0,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.49,
                gap_pct=0.0048,
                open_vs_sma_atr=1.3,
                market_ratio=1.10,
                primary_score=11.6,
                trade_weekday=4,
            ),
            0.0,
        )
        # Wednesday's low-breadth / weak-market / small-gap pocket was pure-loss
        # in train, so keep that slice out entirely.
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.466373,
                gap_pct=0.001280,
                open_vs_sma_atr=0.963585,
                market_ratio=1.009799,
                primary_score=7.765902,
                trade_weekday=2,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.494657,
                gap_pct=0.000570,
                open_vs_sma_atr=1.009495,
                market_ratio=1.015792,
                primary_score=3.571537,
                trade_weekday=2,
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.446260,
                gap_pct=0.002808,
                open_vs_sma_atr=0.784160,
                market_ratio=1.037716,
                primary_score=6.141977,
                trade_weekday=2,
            ),
            0.0,
        )
        # Wednesday's mid-breadth / weak-market / score 6-8 / small-gap pocket
        # was pure-loss in train, so keep that slice out entirely.
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.584538,
                gap_pct=0.0,
                open_vs_sma_atr=3.314129,
                market_ratio=1.022231,
                primary_score=7.421015,
                trade_weekday=2,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.583281,
                gap_pct=0.000143,
                open_vs_sma_atr=0.362017,
                market_ratio=1.032903,
                primary_score=7.905598,
                trade_weekday=2,
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.555625,
                gap_pct=0.0,
                open_vs_sma_atr=1.740519,
                market_ratio=1.029993,
                primary_score=3.537512,
                trade_weekday=2,
            ),
            0.0,
        )
        # Monday's mid-high breadth / hot-market / non-positive-gap pocket was
        # pure-loss in train, so keep that slice out entirely.
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.662476,
                gap_pct=0.0,
                open_vs_sma_atr=2.641911,
                market_ratio=1.130061,
                primary_score=8.273642,
                trade_weekday=0,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.675676,
                gap_pct=-0.001883,
                open_vs_sma_atr=4.381857,
                market_ratio=1.144642,
                primary_score=4.422353,
                trade_weekday=0,
            ),
            0.0,
        )
        # Friday's low-breadth / near-neutral-market / small-positive-gap pocket
        # was pure-loss in train, so keep that slice out entirely.
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.493400,
                gap_pct=0.002353,
                open_vs_sma_atr=3.196532,
                market_ratio=1.036024,
                primary_score=6.063944,
                trade_weekday=4,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.458831,
                gap_pct=0.002099,
                open_vs_sma_atr=2.428530,
                market_ratio=1.035770,
                primary_score=7.134368,
                trade_weekday=4,
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.523570,
                gap_pct=0.0,
                open_vs_sma_atr=2.208649,
                market_ratio=1.038010,
                primary_score=6.901111,
                trade_weekday=4,
            ),
            0.0,
        )
        # Friday's mid-breadth / near-neutral-market / low-score / stretched-open
        # pocket was pure-loss in train, so keep that slice out entirely.
        # Friday's mid-breadth / near-neutral-market / low-score / stretched-open
        # pocket was pure-loss in train, so keep that slice out entirely.
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.5820238843494657,
                gap_pct=0.020160310905999568,
                open_vs_sma_atr=1.9253094323516873,
                market_ratio=1.0232750790973422,
                primary_score=4.700684399456394,
                trade_weekday=4,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.6411062225015713,
                gap_pct=0.0035826242722794,
                open_vs_sma_atr=3.132219705549259,
                market_ratio=1.0720878879286655,
                primary_score=4.969202658137443,
                trade_weekday=4,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.5876807039597737,
                gap_pct=0.0,
                open_vs_sma_atr=2.2526483050847466,
                market_ratio=1.0271939495831857,
                primary_score=4.729619066968815,
                trade_weekday=4,
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.562539283469516,
                gap_pct=0.0,
                open_vs_sma_atr=3.0618202633085296,
                market_ratio=1.0006648217756462,
                primary_score=5.025264879945478,
                trade_weekday=4,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.66,
                gap_pct=0.018,
                open_vs_sma_atr=0.8,
                market_ratio=1.10,
                primary_score=11.5,
                prev_return=0.040,
                trade_weekday=0,
            ),
            DAYTRADE_PRIMARY_HEATED_CONTINUATION_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.66,
                gap_pct=0.018,
                open_vs_sma_atr=0.8,
                market_ratio=1.10,
                primary_score=11.5,
                prev_return=0.030,
                trade_weekday=0,
            ),
            DAYTRADE_PRIMARY_MAX_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.52,
                gap_pct=0.012,
                open_vs_sma_atr=0.8,
                market_ratio=1.12,
                primary_score=7.5,
                trade_weekday=0,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.60,
                gap_pct=0.006,
                open_vs_sma_atr=1.2,
                market_ratio=1.08,
                primary_score=7.5,
                trade_weekday=4,
            ),
            3.75,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.48,
                gap_pct=0.015,
                open_vs_sma_atr=1.1,
                market_ratio=1.08,
                primary_score=7.0,
                trade_weekday=3,
            ),
            0.10,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.44,
                gap_pct=0.0,
                open_vs_sma_atr=1.5,
                market_ratio=1.08,
                primary_score=7.5,
                trade_weekday=1,
            ),
            DAYTRADE_PRIMARY_LOW_SCORE_HOT_MARKET_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.68,
                gap_pct=0.007,
                open_vs_sma_atr=0.3,
                market_ratio=1.08,
                primary_score=5.5,
                trade_weekday=2,
            ),
            DAYTRADE_PRIMARY_MID_BREADTH_HOT_MARKET_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.68,
                gap_pct=0.007,
                open_vs_sma_atr=0.1,
                market_ratio=1.08,
                primary_score=5.5,
                trade_weekday=2,
            ),
            DAYTRADE_PRIMARY_LOW_SCORE_HOT_MARKET_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.7008170961659334,
                gap_pct=-0.0002322981744421905,
                market_ratio=1.2525188679245284,
                open_vs_sma_atr=0.2138238095238095,
                primary_score=4.817377839419318,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.81,
                gap_pct=0.001235448913536401,
                market_ratio=1.19,
                open_vs_sma_atr=0.6,
                primary_score=6.380008399301425,
                trade_weekday=1,
            ),
            DAYTRADE_PRIMARY_LOW_SCORE_HOT_MARKET_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.95,
                gap_pct=0.020,
                open_vs_sma_atr=1.2,
                market_ratio=0.90,
                primary_score=5.5,
                trade_weekday=4,
            ),
            DAYTRADE_PRIMARY_LOW_SCORE_EQUITY_NOTIONAL_PCT,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.6222501571338781,
                gap_pct=0.019342,
                open_vs_sma_atr=1.069282,
                market_ratio=1.2007569482199816,
                primary_score=10.635328140222146,
                trade_weekday=2,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.71,
                gap_pct=0.004,
                open_vs_sma_atr=1.5,
                market_ratio=1.18,
                primary_score=8.0,
                rs_alpha=35.0,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.71,
                gap_pct=0.004,
                open_vs_sma_atr=1.5,
                market_ratio=1.18,
                primary_score=11.5,
                rs_alpha=35.0,
                trade_weekday=1,
            ),
            DAYTRADE_PRIMARY_MAX_EQUITY_NOTIONAL_PCT,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.71,
                gap_pct=0.015,
                open_vs_sma_atr=2.0,
                market_ratio=1.20,
                primary_score=8.0,
                rs_alpha=40.0,
                trade_weekday=0,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.71,
                gap_pct=0.021,
                open_vs_sma_atr=2.1,
                market_ratio=1.20,
                primary_score=13.5,
                rs_alpha=120.0,
                trade_weekday=0,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.71,
                gap_pct=0.021,
                open_vs_sma_atr=2.1,
                market_ratio=1.20,
                primary_score=13.5,
                rs_alpha=90.0,
                trade_weekday=0,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.71,
                gap_pct=0.015,
                open_vs_sma_atr=3.5,
                market_ratio=1.20,
                primary_score=8.0,
                rs_alpha=40.0,
                trade_weekday=0,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.72,
                gap_pct=0.011,
                open_vs_sma_atr=3.3,
                market_ratio=1.25,
                primary_score=5.5,
                rs_alpha=36.5,
                trade_weekday=0,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.74,
                gap_pct=0.011,
                open_vs_sma_atr=3.8,
                market_ratio=1.22,
                primary_score=5.8,
                rs_alpha=30.4,
                trade_weekday=0,
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.68,
                gap_pct=0.017,
                open_vs_sma_atr=4.4,
                market_ratio=1.18,
                primary_score=8.6,
                rs_alpha=40.1,
                trade_weekday=0,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.874293,
                gap_pct=0.001439,
                open_vs_sma_atr=3.78123,
                market_ratio=1.124722,
                primary_score=12.818952,
                rs_alpha=91.259463,
                trade_weekday=1,
            ),
            DAYTRADE_PRIMARY_TUESDAY_HIGH_BREADTH_HIGH_SCORE_STRETCHED_OPEN_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.740415,
                gap_pct=0.021398,
                open_vs_sma_atr=3.110114,
                market_ratio=1.146066,
                primary_score=24.523883,
                trade_weekday=1,
            ),
            4.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_notional_pct(
                breadth_val=0.740415,
                gap_pct=0.021398,
                open_vs_sma_atr=3.110114,
                market_ratio=1.146066,
                primary_score=24.523883,
                trade_weekday=1,
            ),
            0.20,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_notional_pct(
                breadth_val=0.67819,
                gap_pct=0.021772939346811793,
                open_vs_sma_atr=2.049350649350648,
                market_ratio=1.108313263929358,
                primary_score=11.1042440606069,
                trade_weekday=1,
            ),
            0.20,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_notional_pct(
                breadth_val=0.6807039597737272,
                gap_pct=-0.0009794319294809,
                open_vs_sma_atr=-0.4999999999999997,
                market_ratio=1.1945217234524736,
                primary_score=11.129107151338568,
                prev_return=0.01896207584830334,
                trade_weekday=3,
            ),
            0.25,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_notional_pct(
                breadth_val=0.623507228158391,
                gap_pct=0.0021299254526092,
                open_vs_sma_atr=2.65057915057915,
                market_ratio=1.218805626330669,
                primary_score=7.221845877029052,
                prev_return=0.03528114663726578,
                trade_weekday=4,
            ),
            0.25,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_notional_pct(
                breadth_val=0.6882463859208046,
                gap_pct=-0.0048622366288493,
                open_vs_sma_atr=2.33178209690665,
                market_ratio=1.1981878608620915,
                primary_score=5.574530120432707,
                trade_weekday=2,
            ),
            0.20,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_notional_pct(
                breadth_val=0.5292269013199246,
                gap_pct=0.024793388429751984,
                open_vs_sma_atr=2.3483110761979553,
                market_ratio=1.0100065463387262,
                primary_score=8.3133156223285,
                trade_weekday=1,
            ),
            0.15,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_risk_budget_pct(
                breadth_val=0.740415,
                gap_pct=0.021398,
                open_vs_sma_atr=3.110114,
                market_ratio=1.146066,
                primary_score=24.523883,
                primary_equity_notional_pct=4.0,
                trade_weekday=1,
            ),
            0.25,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_risk_budget_pct(
                breadth_val=0.67819,
                gap_pct=0.021772939346811793,
                open_vs_sma_atr=2.049350649350648,
                market_ratio=1.108313263929358,
                primary_score=11.1042440606069,
                trade_weekday=1,
            ),
            0.10,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_risk_budget_pct(
                breadth_val=0.67819,
                gap_pct=0.021772939346811793,
                open_vs_sma_atr=2.049350649350648,
                market_ratio=1.108313263929358,
                primary_score=11.1042440606069,
                primary_equity_notional_pct=3.0,
                trade_weekday=1,
            ),
            0.25,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_risk_budget_pct(
                breadth_val=0.67819,
                gap_pct=0.021772939346811793,
                open_vs_sma_atr=2.049350649350648,
                market_ratio=1.108313263929358,
                primary_score=11.1042440606069,
                primary_equity_notional_pct=3.0,
                trade_weekday=0,
            ),
            0.10,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.67819,
                gap_pct=0.021772939346811793,
                open_vs_sma_atr=2.049350649350648,
                market_ratio=1.108313263929358,
                primary_score=11.1042440606069,
                trade_weekday=1,
            ),
            3.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.890635,
                gap_pct=0.0,
                open_vs_sma_atr=3.203636,
                market_ratio=1.14814,
                primary_score=11.124408,
                rs_alpha=70.588235,
                trade_weekday=1,
            ),
            DAYTRADE_PRIMARY_MAX_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.72,
                gap_pct=0.007,
                open_vs_sma_atr=1.1,
                market_ratio=1.10,
                primary_score=9.0,
                trade_weekday=0,
            ),
            DAYTRADE_PRIMARY_MONDAY_BROAD_MID_SCORE_EQUITY_NOTIONAL_PCT,
        )
        # Monday's near-SMA / low-score / hot-market pocket was loss-only in train.
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.658705,
                gap_pct=0.019492,
                open_vs_sma_atr=0.100809,
                market_ratio=1.149836,
                prev_return=0.038013,
                primary_score=5.636248,
                rs_alpha=8.178914,
                trade_weekday=0,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.689503,
                gap_pct=0.018349,
                open_vs_sma_atr=0.946535,
                market_ratio=1.107390,
                prev_return=0.039195,
                primary_score=5.952687,
                rs_alpha=14.602804,
                trade_weekday=0,
            ),
            DAYTRADE_PRIMARY_MID_BREADTH_HOT_MARKET_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.62,
                gap_pct=0.004,
                open_vs_sma_atr=1.2,
                market_ratio=1.03,
                primary_score=6.5,
                trade_weekday=2,
            ),
            DAYTRADE_PRIMARY_TEPID_LOW_BREADTH_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.62,
                gap_pct=0.024,
                open_vs_sma_atr=1.2,
                market_ratio=1.03,
                primary_score=6.5,
                trade_weekday=2,
            ),
            DAYTRADE_PRIMARY_TEPID_LOW_BREADTH_HIGH_GAP_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.80,
                gap_pct=0.004,
                open_vs_sma_atr=1.2,
                market_ratio=1.25,
                primary_score=6.5,
                trade_weekday=2,
            ),
            DAYTRADE_PRIMARY_MAX_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.52,
                gap_pct=0.012,
                open_vs_sma_atr=1.2,
                market_ratio=1.08,
                primary_score=9.5,
                trade_weekday=0,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.52,
                gap_pct=0.012,
                open_vs_sma_atr=1.2,
                market_ratio=1.12,
                primary_score=7.5,
                trade_weekday=0,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.62,
                gap_pct=0.004,
                open_vs_sma_atr=1.2,
                market_ratio=1.04,
                primary_score=9.5,
                prev_return=0.05,
                rs_alpha=60.0,
                trade_weekday=1,
            ),
            DAYTRADE_PRIMARY_TEPID_MARKET_STRONG_PRIOR_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.62,
                gap_pct=0.004,
                open_vs_sma_atr=1.2,
                market_ratio=1.06,
                primary_score=8.0,
                prev_return=0.05,
                rs_alpha=60.0,
                trade_weekday=1,
            ),
            DAYTRADE_PRIMARY_LOW_SCORE_HOT_MARKET_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.70,
                gap_pct=0.004,
                open_vs_sma_atr=0.3,
                market_ratio=1.12,
                primary_score=7.0,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.675676,
                gap_pct=0.020588,
                open_vs_sma_atr=0.729358,
                market_ratio=1.010961,
                primary_score=7.463999,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.651791,
                gap_pct=0.007423,
                open_vs_sma_atr=3.886825,
                market_ratio=1.009709,
                primary_score=3.827046,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.661848,
                gap_pct=0.005109,
                open_vs_sma_atr=3.618905,
                market_ratio=1.011353,
                primary_score=5.056725,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.68,
                gap_pct=0.004,
                open_vs_sma_atr=0.3,
                market_ratio=1.06,
                primary_score=7.0,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.70,
                gap_pct=0.004,
                open_vs_sma_atr=1.0,
                market_ratio=1.08,
                primary_score=7.0,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.80,
                gap_pct=0.004,
                open_vs_sma_atr=1.2,
                market_ratio=1.10,
                primary_score=11.0,
                trade_weekday=0,
            ),
            DAYTRADE_PRIMARY_HIGH_BREADTH_MID_HOT_MARKET_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.80,
                gap_pct=0.004,
                open_vs_sma_atr=1.2,
                market_ratio=1.10,
                primary_score=11.0,
                trade_weekday=1,
            ),
            DAYTRADE_PRIMARY_MAX_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.80,
                gap_pct=0.004,
                open_vs_sma_atr=1.2,
                market_ratio=1.16,
                primary_score=12.0,
                trade_weekday=0,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.80,
                gap_pct=0.004,
                open_vs_sma_atr=1.2,
                market_ratio=1.16,
                primary_score=12.0,
                trade_weekday=3,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.80,
                gap_pct=0.004,
                open_vs_sma_atr=1.2,
                market_ratio=1.16,
                primary_score=12.1,
                trade_weekday=0,
            ),
            DAYTRADE_PRIMARY_HIGH_BREADTH_MID_HOT_MARKET_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.58,
                gap_pct=0.015,
                open_vs_sma_atr=1.2,
                rs_alpha=8.0,
                trade_weekday=0,
            ),
            DAYTRADE_PRIMARY_LOW_RS_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.72,
                gap_pct=0.007,
                open_vs_sma_atr=1.1,
                market_ratio=1.07,
                primary_score=11.0,
                rs_alpha=8.0,
                trade_weekday=2,
            ),
            0.75,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.65,
                gap_pct=0.015,
                open_vs_sma_atr=4.4,
                rs_alpha=40.0,
                trade_weekday=0,
            ),
            DAYTRADE_PRIMARY_STRETCHED_STALL_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.65,
                gap_pct=0.015,
                open_vs_sma_atr=5.1,
                rs_alpha=40.0,
                trade_weekday=0,
            ),
            DAYTRADE_PRIMARY_MAX_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_fallback_equity_notional_pct(
                gap_pct=0.006,
                breadth_val=0.55,
                trade_weekday=1,
            ),
            0.75,
        )
        self.assertAlmostEqual(
            resolve_daytrade_fallback_equity_notional_pct(
                gap_pct=0.006,
                breadth_val=0.55,
                trade_weekday=3,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_fallback_equity_notional_pct(
                gap_pct=0.004,
                breadth_val=0.55,
                trade_weekday=2,
            ),
            DAYTRADE_FALLBACK_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_fallback_equity_notional_pct(
                gap_pct=0.006,
                breadth_val=0.52,
                market_ratio=1.03,
                trade_weekday=1,
            ),
            DAYTRADE_FALLBACK_TUESDAY_FRIDAY_WEAK_MARKET_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_fallback_equity_notional_pct(
                gap_pct=0.006,
                breadth_val=0.52,
                market_ratio=1.03,
                trade_weekday=0,
            ),
            DAYTRADE_FALLBACK_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_fallback_equity_notional_pct(
                gap_pct=-0.001,
                breadth_val=0.52,
                market_ratio=1.03,
                trade_weekday=1,
            ),
            DAYTRADE_FALLBACK_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_fallback_equity_notional_pct(
                gap_pct=0.006929,
                breadth_val=0.578801,
                prev_return=0.051866,
                open_vs_sma_atr=4.132314,
                trade_weekday=0,
            ),
            DAYTRADE_FALLBACK_HIGH_BREADTH_EXTENDED_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_fallback_equity_notional_pct(
                gap_pct=0.008621,
                breadth_val=0.569735,
                prev_return=-0.004766,
                open_vs_sma_atr=3.787703,
                trade_weekday=0,
            ),
            DAYTRADE_FALLBACK_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_fallback_equity_notional_pct(
                gap_pct=0.006,
                breadth_val=0.80,
                trade_weekday=2,
            ),
            0.30,
        )
        self.assertAlmostEqual(
            resolve_daytrade_fallback_equity_notional_pct(
                gap_pct=0.006,
                breadth_val=0.44,
                score=3.5,
                trade_weekday=2,
            ),
            0.30,
        )
        self.assertAlmostEqual(
            resolve_daytrade_fallback_equity_notional_pct(
                gap_pct=0.006,
                breadth_val=0.48,
                score=4.5,
                trade_weekday=2,
            ),
            0.50,
        )
        self.assertAlmostEqual(
            resolve_daytrade_fallback_notional_pct(
                breadth_val=0.534255,
                market_ratio=1.003756,
                prev_return=0.021557,
                score=5.809731,
                trade_weekday=0,
            ),
            DAYTRADE_FALLBACK_MONDAY_MID_BREADTH_NEUTRAL_MARKET_SIZEUP_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_fallback_notional_pct(
                breadth_val=0.534255,
                market_ratio=1.003756,
                prev_return=0.021557,
                score=5.809731,
                trade_weekday=1,
            ),
            DAYTRADE_FALLBACK_MAX_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_fallback_equity_notional_pct(
                gap_pct=0.0,
                breadth_val=0.5084852294154619,
                market_ratio=0.9945078640943172,
                open_vs_sma_atr=2.6388644366197163,
                score=4.963572716619428,
                trade_weekday=0,
            ),
            2.5,
        )
        self.assertAlmostEqual(
            resolve_daytrade_fallback_notional_pct(
                breadth_val=0.5084852294154619,
                market_ratio=0.9945078640943172,
                prev_return=0.0,
                score=4.963572716619428,
                trade_weekday=0,
            ),
            DAYTRADE_FALLBACK_MONDAY_MID_BREADTH_NEUTRAL_MARKET_SIZEUP_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_fallback_equity_notional_pct(
                gap_pct=0.0,
                breadth_val=0.534255,
                market_ratio=1.003756,
                open_vs_sma_atr=2.013643,
                prev_return=0.021557,
                score=5.809731,
                trade_weekday=0,
            ),
            3.75,
        )
        self.assertAlmostEqual(
            resolve_daytrade_fallback_equity_notional_pct(
                gap_pct=0.0,
                breadth_val=0.534255,
                market_ratio=1.003756,
                open_vs_sma_atr=2.013643,
                prev_return=0.021557,
                score=5.809731,
                trade_weekday=1,
            ),
            DAYTRADE_FALLBACK_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_fallback_notional_pct(
                breadth_val=0.492772,
                market_ratio=1.030534,
                prev_return=0.054892,
                score=7.093739,
                trade_weekday=2,
                open_vs_sma_atr=3.786542,
            ),
            0.25,
        )
        self.assertAlmostEqual(
            resolve_daytrade_fallback_equity_notional_pct(
                gap_pct=0.0,
                breadth_val=0.492772,
                market_ratio=1.030534,
                open_vs_sma_atr=3.786542,
                prev_return=0.054892,
                score=7.093739,
                trade_weekday=2,
            ),
            2.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_fallback_equity_notional_pct(
                gap_pct=0.002,
                breadth_val=0.42,
                prev_return=0.03,
                open_vs_sma_atr=0.8,
                trade_weekday=4,
            ),
            DAYTRADE_FALLBACK_LOW_BREADTH_CONTINUATION_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_fallback_equity_notional_pct(
                gap_pct=0.002,
                breadth_val=0.42,
                prev_return=0.03,
                open_vs_sma_atr=1.3,
                trade_weekday=4,
            ),
            DAYTRADE_FALLBACK_EQUITY_NOTIONAL_PCT,
        )
        fallback_low_breadth_loss_candidate = {
            "breadth_val": 0.488372,
            "market_ratio": 1.086902,
            "score": 5.527594,
            "prev_return": 0.016815,
            "open_vs_sma_atr": 2.093725,
            "trade_weekday": 0,
        }
        fallback_low_breadth_second_loss_candidate = {
            "breadth_val": 0.465116,
            "market_ratio": 1.084507,
            "score": 6.361869,
            "prev_return": 0.006568,
            "open_vs_sma_atr": 0.294039,
            "trade_weekday": 1,
        }
        fallback_low_breadth_survivor_candidate = {
            "breadth_val": 0.453803,
            "market_ratio": 1.091328,
            "score": 6.480642,
            "prev_return": 0.046185,
            "open_vs_sma_atr": 1.894243,
            "trade_weekday": 2,
        }
        for candidate in (fallback_low_breadth_loss_candidate, fallback_low_breadth_second_loss_candidate):
            self.assertAlmostEqual(resolve_daytrade_fallback_equity_notional_pct(gap_pct=0.0, **candidate), 0.0)
        self.assertGreater(
            resolve_daytrade_fallback_equity_notional_pct(gap_pct=0.0, **fallback_low_breadth_survivor_candidate),
            0.0,
        )
        fallback_neutral_mid_loss_candidate = {
            "breadth_val": 0.595223,
            "market_ratio": 0.985849,
            "score": 5.975586,
            "prev_return": 0.020322,
            "open_vs_sma_atr": 2.129749,
            "trade_weekday": 2,
        }
        fallback_neutral_mid_second_loss_candidate = {
            "breadth_val": 0.571339,
            "market_ratio": 0.994572,
            "score": 7.143986,
            "prev_return": 0.05,
            "open_vs_sma_atr": 2.880342,
            "trade_weekday": 2,
        }
        fallback_hot_high_score_loss_candidate = {
            "breadth_val": 0.488372,
            "market_ratio": 1.098270,
            "score": 9.112519,
            "prev_return": 0.052323,
            "open_vs_sma_atr": 2.328951,
            "trade_weekday": 4,
        }
        fallback_tuesday_mid_loss_candidate = {
            "breadth_val": 0.469516,
            "market_ratio": 0.987399,
            "score": 6.210937,
            "prev_return": 0.025771,
            "open_vs_sma_atr": 2.258600,
            "trade_weekday": 1,
        }
        fallback_tuesday_high_score_loss_candidate = {
            "breadth_val": 0.445632,
            "market_ratio": 0.997919,
            "score": 8.109433,
            "prev_return": 0.009662,
            "open_vs_sma_atr": 1.915862,
            "trade_weekday": 1,
        }
        for candidate in (
            fallback_neutral_mid_loss_candidate,
            fallback_neutral_mid_second_loss_candidate,
            fallback_hot_high_score_loss_candidate,
            fallback_tuesday_mid_loss_candidate,
            fallback_tuesday_high_score_loss_candidate,
        ):
            self.assertAlmostEqual(resolve_daytrade_fallback_equity_notional_pct(gap_pct=0.0, **candidate), 0.0)
        fallback_wednesday_low_open_loss_candidate = {
            "breadth_val": 0.5713387806411062,
            "market_ratio": 0.9945721640176608,
            "score": 5.6043780805075665,
            "prev_return": 0.02087682672233826,
            "open_vs_sma_atr": -0.9492924528301887,
            "trade_weekday": 2,
        }
        fallback_wednesday_low_open_survivor_candidate = {
            "breadth_val": 0.5713387806411062,
            "market_ratio": 0.9945721640176608,
            "score": 5.4,
            "prev_return": 0.02087682672233826,
            "open_vs_sma_atr": -0.5,
            "trade_weekday": 2,
        }
        fallback_friday_high_open_loss_candidate = {
            "breadth_val": 0.595223130106851,
            "market_ratio": 0.9858490106528727,
            "score": 3.3249395233785277,
            "prev_return": 0.005875440658049458,
            "open_vs_sma_atr": 3.3876651982378863,
            "trade_weekday": 4,
        }
        fallback_friday_high_open_survivor_candidate = {
            "breadth_val": 0.595223130106851,
            "market_ratio": 0.9858490106528727,
            "score": 4.1,
            "prev_return": 0.005875440658049458,
            "open_vs_sma_atr": 3.3876651982378863,
            "trade_weekday": 4,
        }
        fallback_friday_low_breadth_sub_neutral_market_loss_candidate = {
            "breadth_val": 0.42111879321181644,
            "market_ratio": 0.9891406575477792,
            "score": 4.386547500528413,
            "prev_return": 0.030897709520087846,
            "open_vs_sma_atr": 1.6926867219917008,
            "trade_weekday": 4,
        }
        fallback_friday_low_breadth_sub_neutral_market_second_loss_candidate = {
            "breadth_val": 0.42111879321181644,
            "market_ratio": 0.9891406575477792,
            "score": 2.765199839445165,
            "prev_return": 0.01696638702373648,
            "open_vs_sma_atr": 2.201535225149457,
            "trade_weekday": 4,
        }
        self.assertAlmostEqual(
            resolve_daytrade_fallback_equity_notional_pct(
                gap_pct=0.0,
                **fallback_friday_low_breadth_sub_neutral_market_second_loss_candidate,
            ),
            0.0,
        )
        fallback_friday_low_breadth_sub_neutral_market_survivor_candidate = {
            "breadth_val": 0.42111879321181644,
            "market_ratio": 0.9891406575477792,
            "score": 4.6,
            "prev_return": 0.030897709520087846,
            "open_vs_sma_atr": 1.6926867219917008,
            "trade_weekday": 2,
        }
        self.assertAlmostEqual(
            resolve_daytrade_fallback_equity_notional_pct(
                gap_pct=0.0,
                **fallback_friday_low_breadth_sub_neutral_market_loss_candidate,
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_fallback_equity_notional_pct(
                gap_pct=0.0,
                **fallback_friday_low_breadth_sub_neutral_market_survivor_candidate,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_fallback_equity_notional_pct(gap_pct=0.0, **fallback_wednesday_low_open_loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_fallback_equity_notional_pct(gap_pct=0.0, **fallback_wednesday_low_open_survivor_candidate),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_fallback_equity_notional_pct(gap_pct=0.0, **fallback_friday_high_open_loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_fallback_equity_notional_pct(gap_pct=0.0, **fallback_friday_high_open_survivor_candidate),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_catchup_equity_notional_pct(
                setup_type="catchup_rs",
                breadth_val=0.44,
                gap_pct=0.012,
                open_vs_sma_atr=1.6,
                trade_weekday=0,
            ),
            0.75,
        )
        self.assertAlmostEqual(
            resolve_daytrade_catchup_equity_notional_pct(
                setup_type="catchup_rs",
                breadth_val=0.44,
                gap_pct=0.012,
                open_vs_sma_atr=1.4,
                trade_weekday=0,
            ),
            DAYTRADE_CATCHUP_RS_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_catchup_equity_notional_pct(
                setup_type="catchup_rs",
                breadth_val=0.48,
                gap_pct=0.002,
                prev_return=0.081858,
                open_vs_sma_atr=3.9,
                trade_weekday=2,
            ),
            DAYTRADE_CATCHUP_RS_HOT_PREV_RETURN_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_catchup_equity_notional_pct(
                setup_type="catchup_rs",
                breadth_val=0.422376,
                gap_pct=0.011061,
                prev_return=0.071082,
                open_vs_sma_atr=-0.2773,
                score=18.903164,
                trade_weekday=1,
            ),
            DAYTRADE_CATCHUP_RS_STRONG_CONTINUATION_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_catchup_equity_notional_pct(
                setup_type="catchup_rs",
                breadth_val=0.60,
                gap_pct=0.017,
                prev_return=0.084663,
                open_vs_sma_atr=3.26,
                trade_weekday=1,
            ),
            DAYTRADE_CATCHUP_RS_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_catchup_equity_notional_pct(
                setup_type="catchup_rs",
                breadth_val=0.44,
                gap_pct=0.012,
                open_vs_sma_atr=2.1,
                trade_weekday=4,
            ),
            0.35,
        )
        self.assertAlmostEqual(
            resolve_daytrade_catchup_equity_notional_pct(
                setup_type="catchup_rs",
                breadth_val=0.44,
                gap_pct=0.012,
                open_vs_sma_atr=2.1,
                trade_weekday=3,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_catchup_equity_notional_pct(
                setup_type="catchup_rs",
                breadth_val=0.44,
                gap_pct=0.012,
                open_vs_sma_atr=1.9,
                trade_weekday=4,
            ),
            0.75,
        )
        self.assertAlmostEqual(
            resolve_daytrade_catchup_equity_notional_pct(
                setup_type="catchup_gapdown",
                breadth_val=0.40,
                gap_pct=-0.018,
                open_vs_sma_atr=-1.2,
                trade_weekday=0,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_catchup_equity_notional_pct(
                setup_type="catchup_gapdown",
                breadth_val=0.40,
                gap_pct=-0.018,
                open_vs_sma_atr=-0.8,
                trade_weekday=0,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_catchup_equity_notional_pct(
                setup_type="catchup_gapdown",
                breadth_val=0.30,
                gap_pct=-0.010,
                open_vs_sma_atr=0.3,
                trade_weekday=4,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_catchup_equity_notional_pct(
                setup_type="catchup_gapdown",
                breadth_val=0.40,
                gap_pct=-0.015,
                score=6.5,
                trade_weekday=4,
            ),
            0.25,
        )
        self.assertAlmostEqual(
            resolve_daytrade_catchup_equity_notional_pct(
                setup_type="catchup_gapdown",
                breadth_val=0.40,
                gap_pct=-0.009,
                score=6.5,
                trade_weekday=4,
            ),
            DAYTRADE_CATCHUP_GAPDOWN_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_catchup_equity_notional_pct(
                setup_type="catchup_gapdown",
                breadth_val=0.40,
                gap_pct=-0.009,
                open_vs_sma_atr=0.3,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_catchup_equity_notional_pct(
                setup_type="catchup_gapdown",
                breadth_val=0.40,
                gap_pct=-0.009,
                open_vs_sma_atr=0.8,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_catchup_equity_notional_pct(
                setup_type="catchup_gapdown",
                breadth_val=0.40,
                gap_pct=-0.009,
                open_vs_sma_atr=2.1,
                trade_weekday=1,
            ),
            0.25,
        )
        self.assertAlmostEqual(
            resolve_daytrade_catchup_equity_notional_pct(
                setup_type="catchup_gapdown",
                breadth_val=0.30,
                gap_pct=-0.010,
                trade_weekday=4,
            ),
            DAYTRADE_CATCHUP_GAPDOWN_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_catchup_equity_notional_pct(
                setup_type="catchup_gapdown",
                breadth_val=0.40,
                gap_pct=-0.009,
                trade_weekday=1,
            ),
            0.25,
        )
        self.assertAlmostEqual(
            resolve_daytrade_catchup_notional_pct(
                setup_type="catchup_gapdown",
                breadth_val=0.55,
                market_ratio=1.06,
            ),
            DAYTRADE_CATCHUP_GAPDOWN_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_catchup_notional_pct(
                setup_type="catchup_rs",
                breadth_val=0.54,
                market_ratio=1.06,
            ),
            DAYTRADE_CATCHUP_RS_NOTIONAL_PCT,
        )
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
        self.assertEqual(
            cap_daytrade_position_size(
                raw_shares=5_000,
                current_equity=1_000_000,
                buying_power=5_000_000,
                entry_price=1_000.0,
                stop_price=900.0,
                notional_pct=1.0,
                equity_notional_pct=2.0,
                risk_budget_pct=0.12,
                size_multiplier=1.5,
            ),
            1_800,
        )
        self.assertEqual(
            cap_daytrade_position_size(
                raw_shares=10_000,
                current_equity=1_000_000,
                buying_power=10_000_000,
                entry_price=1_000.0,
                stop_price=900.0,
                notional_pct=1.0,
                equity_notional_pct=DAYTRADE_CATCHUP_RS_STRONG_CONTINUATION_EQUITY_NOTIONAL_PCT,
                risk_budget_pct=DAYTRADE_CATCHUP_RS_STRONG_CONTINUATION_RISK_BUDGET_PCT,
            ),
            3_000,
        )
    def test_daytrade_primary_train_replay_size_multiplier_matches_shared_families(self):
        self.assertEqual(
            resolve_daytrade_primary_size_multiplier(
                breadth_val=0.666248,
                gap_pct=0.022026,
                open_vs_sma_atr=1.502942,
                market_ratio=1.125264,
                primary_score=9.196425,
                trade_date=pd.Timestamp("2023-07-12"),
                prev_return=0.047048,
                prev_rsi2=76.691729,
            ),
            1.5,
        )
        self.assertEqual(
            resolve_daytrade_primary_size_multiplier(
                breadth_val=0.720302,
                gap_pct=0.000744,
                open_vs_sma_atr=2.425004,
                market_ratio=1.203315,
                primary_score=6.185709,
                trade_date=pd.Timestamp("2023-06-16"),
                prev_return=0.017913,
                prev_rsi2=76.756757,
            ),
            1.5,
        )
        self.assertEqual(
            resolve_daytrade_primary_size_multiplier(
                breadth_val=0.5,
                gap_pct=0.01,
                open_vs_sma_atr=1.0,
                market_ratio=1.03,
                primary_score=7.5,
                trade_date=pd.Timestamp("2024-01-08"),
                prev_return=0.0,
                prev_rsi2=40.0,
            ),
            1.0,
        )

    def test_daytrade_strong_oversold_train_replay_size_multiplier_splits_pockets(self):
        self.assertEqual(
            resolve_daytrade_strong_oversold_size_multiplier(
                breadth_val=0.551226,
                gap_pct=-0.005758,
                market_ratio=1.011402,
                score=18.252726,
                open_vs_trend_atr=2.070657,
                trade_date=pd.Timestamp("2025-06-16"),
            ),
            2.5,
        )
        self.assertEqual(
            resolve_daytrade_strong_oversold_size_multiplier(
                breadth_val=0.589566,
                gap_pct=-0.005535,
                market_ratio=1.188889,
                score=19.021604,
                open_vs_trend_atr=4.646289,
                trade_date=pd.Timestamp("2025-10-15"),
            ),
            1.3,
        )
        self.assertEqual(
            resolve_daytrade_strong_oversold_size_multiplier(
                breadth_val=0.695789,
                gap_pct=-0.014571,
                market_ratio=1.039355,
                score=20.379097,
                open_vs_trend_atr=6.261748,
                trade_date=pd.Timestamp("2023-04-05"),
            ),
            2.0,
        )
        self.assertEqual(
            resolve_daytrade_strong_oversold_size_multiplier(
                breadth_val=0.6593337523570082,
                gap_pct=-0.014444444444444482,
                market_ratio=1.001554166381899,
                score=18.608284393090123,
                open_vs_trend_atr=1.439776357827475,
                trade_date=pd.Timestamp("2023-02-22"),
            ),
            2.5,
        )
        self.assertEqual(
            resolve_daytrade_strong_oversold_size_multiplier(
                breadth_val=0.654934,
                gap_pct=-0.005059,
                market_ratio=0.996104,
                score=18.802731,
                open_vs_trend_atr=0.335467,
                trade_date=pd.Timestamp("2022-08-03"),
            ),
            1.0,
        )
        self.assertEqual(
            resolve_daytrade_strong_oversold_size_multiplier(
                breadth_val=0.761785,
                gap_pct=-0.015427,
                market_ratio=1.004472,
                score=19.278605,
                open_vs_trend_atr=5.263553,
                trade_date=pd.Timestamp("2022-08-29"),
            ),
            1.0,
        )

    def test_daytrade_primary_monday_mid_breadth_moderate_extension_no_trade(self):
        loss_candidate = {
            "breadth_val": 0.68259,
            "gap_pct": 0.007989,
            "market_ratio": 1.128167,
            "open_vs_sma_atr": 3.200377,
            "prev_return": 0.025956,
            "primary_score": 7.012557,
            "trade_weekday": 0,
        }
        slightly_safer_candidate = dict(loss_candidate, open_vs_sma_atr=2.9)
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(**loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**slightly_safer_candidate),
            0.0,
        )
    def test_daytrade_primary_monday_high_market_high_breadth_lower_score_low_open_no_trade(self):
        loss_candidate = {
            "breadth_val": 0.724073,
            "gap_pct": 0.009312,
            "market_ratio": 1.196148,
            "open_vs_sma_atr": 2.623105,
            "primary_score": 11.410560,
            "rs_alpha": 55.098468,
            "trade_weekday": 0,
        }
        stronger_open_candidate = dict(loss_candidate, open_vs_sma_atr=4.430155)
        negative_gap_loss_candidate = dict(
            loss_candidate,
            gap_pct=-0.003509,
            open_vs_sma_atr=2.323136,
            primary_score=9.332015,
            rs_alpha=32.712456,
        )
        stronger_score_candidate = {
            **loss_candidate,
            "breadth_val": 0.781270,
            "gap_pct": 0.015607,
            "market_ratio": 1.210922,
            "open_vs_sma_atr": 1.744136,
            "primary_score": 19.161923,
            "rs_alpha": 142.636746,
        }
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**loss_candidate),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**negative_gap_loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**stronger_open_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**stronger_score_candidate),
            0.0,
        )
    def test_daytrade_primary_tuesday_mid_breadth_tepid_market_score9_no_trade(self):
        loss_candidate = {
            "breadth_val": 0.662476,
            "gap_pct": 0.015928,
            "market_ratio": 1.070339,
            "open_vs_sma_atr": 0.72933,
            "prev_return": 0.060606,
            "primary_score": 9.027171,
            "trade_weekday": 1,
        }
        slightly_safer_candidate = dict(loss_candidate, primary_score=9.6)
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(**loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**slightly_safer_candidate),
            0.0,
        )
    def test_daytrade_primary_thursday_mid_breadth_hot_market_stretched_open_no_trade(self):
        loss_candidate = {
            "breadth_val": 0.639849,
            "gap_pct": 0.007989,
            "market_ratio": 1.178443,
            "open_vs_sma_atr": 2.072373,
            "prev_return": 0.022535,
            "primary_score": 6.982952,
            "rs_alpha": 57.5179,
            "trade_weekday": 3,
        }
        slightly_safer_candidate = dict(loss_candidate, open_vs_sma_atr=1.9)
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(**loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**slightly_safer_candidate),
            0.0,
        )
    def test_daytrade_primary_tuesday_low_open_mid_breadth_hot_market_no_trade(self):
        loss_candidate = {
            "breadth_val": 0.603394,
            "gap_pct": 0.0,
            "market_ratio": 1.219570,
            "open_vs_sma_atr": 0.276668,
            "prev_return": 0.042587,
            "primary_score": 5.912435,
            "rs_alpha": 28.051143,
            "trade_weekday": 1,
        }
        slightly_safer_candidate = dict(loss_candidate, open_vs_sma_atr=2.0)
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(**loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**slightly_safer_candidate),
            0.0,
        )
    def test_daytrade_primary_tuesday_low_score_hot_market_no_trade(self):
        loss_candidate = {
            "breadth_val": 0.668762,
            "gap_pct": 0.007334,
            "market_ratio": 1.052975,
            "open_vs_sma_atr": 1.357409,
            "prev_return": 0.030411,
            "primary_score": 5.061363,
            "trade_weekday": 1,
        }
        slightly_safer_candidate = dict(loss_candidate, market_ratio=1.10, open_vs_sma_atr=1.1)
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(**loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**slightly_safer_candidate),
            0.0,
        )
    def test_daytrade_primary_tuesday_mid_breadth_low_score_small_positive_gap_no_trade(self):
        loss_candidate = {
            "breadth_val": 0.605280,
            "gap_pct": 0.002951,
            "market_ratio": 1.106340,
            "open_vs_sma_atr": 0.544920,
            "primary_score": 4.659033,
            "trade_weekday": 1,
        }
        slightly_safer_candidate = dict(loss_candidate, primary_score=6.1)
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(**loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**slightly_safer_candidate),
            0.0,
        )
    def test_daytrade_primary_wednesday_hot_market_low_score_mid_open_probe(self):
        loss_candidate = {
            "breadth_val": 0.7033312382149591,
            "gap_pct": -0.0010631001387706174,
            "market_ratio": 1.1710117720226947,
            "open_vs_sma_atr": 1.7061688311688297,
            "primary_score": 5.34852483657811,
            "trade_weekday": 2,
        }
        slightly_safer_candidate = dict(loss_candidate, open_vs_sma_atr=2.1)
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(**loss_candidate),
            0.10,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**slightly_safer_candidate),
            0.10,
        )
    def test_daytrade_primary_wednesday_high_breadth_low_score_high_open_no_trade(self):
        loss_candidates = [
            {
                "breadth_val": 0.7774984286612193,
                "gap_pct": -0.004313443565780006,
                "market_ratio": 1.0555880190759834,
                "open_vs_sma_atr": 3.163884673748103,
                "primary_score": 5.086844334425752,
                "trade_weekday": 2,
            },
            {
                "breadth_val": 0.8705216844751729,
                "gap_pct": 0.017473118279569988,
                "market_ratio": 1.0931647881665723,
                "open_vs_sma_atr": 2.0689655172413794,
                "primary_score": 3.140205312583127,
                "trade_weekday": 2,
            },
        ]
        for candidate in loss_candidates:
            self.assertAlmostEqual(
                resolve_daytrade_primary_equity_notional_pct(**candidate),
                0.0,
            )
        safe_candidate = {
            "breadth_val": 0.6442489000628535,
            "gap_pct": 0.026252983293556076,
            "market_ratio": 1.1079838372579072,
            "open_vs_sma_atr": -0.3231925554760207,
            "primary_score": 7.3120456262886,
            "trade_weekday": 2,
        }
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**safe_candidate),
            0.10,
        )
    def test_daytrade_primary_wednesday_hot_gap_mid_breadth_exact_loss_pocket_no_trade(self):
        loss_candidate = {
            "breadth_val": 0.6059082338152105,
            "gap_pct": 0.015928,
            "market_ratio": 1.13515308494388,
            "open_vs_sma_atr": -0.4221698113207542,
            "primary_score": 7.655992566987266,
            "trade_weekday": 2,
        }
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**loss_candidate),
            0.0,
        )
    def test_daytrade_primary_wednesday_low_breadth_high_score_mod_open_no_trade(self):
        loss_candidates = [
            {
                "breadth_val": 0.5449402891263356,
                "gap_pct": 0.022189349112426093,
                "market_ratio": 1.0201625525514664,
                "open_vs_sma_atr": 0.9027008310249299,
                "primary_score": 9.58051924765054,
                "trade_weekday": 2,
            },
            {
                "breadth_val": 0.4663733500942803,
                "gap_pct": -0.0011061946902655162,
                "market_ratio": 1.0097985642745393,
                "open_vs_sma_atr": 1.4096170970614426,
                "primary_score": 10.24891938584346,
                "trade_weekday": 2,
            },
        ]
        for candidate in loss_candidates:
            self.assertAlmostEqual(
                resolve_daytrade_primary_equity_notional_pct(**candidate),
                0.0,
            )
        safe_candidate = {
            "breadth_val": 0.5593966059082338,
            "gap_pct": 0.02499209111040801,
            "market_ratio": 1.0054279366969747,
            "open_vs_sma_atr": 2.164944191814799,
            "primary_score": 4.683633263705239,
            "trade_weekday": 2,
        }
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**safe_candidate),
            0.10,
        )
    def test_daytrade_primary_tuesday_high_breadth_hot_market_low_score_probe(self):
        loss_candidate = {
            "breadth_val": 0.751100,
            "gap_pct": 0.009852,
            "market_ratio": 1.257739,
            "open_vs_sma_atr": 1.304388,
            "prev_return": 0.013733,
            "primary_score": 3.046980,
            "trade_weekday": 1,
        }
        slightly_safer_candidate = dict(loss_candidate, primary_score=8.2, gap_pct=0.011)
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(**loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**slightly_safer_candidate),
            0.10,
        )
    def test_daytrade_primary_tuesday_high_breadth_hot_market_low_score_low_open_probe(self):
        loss_candidate = {
            "breadth_val": 0.7014456316781899,
            "gap_pct": 0.010204081632652962,
            "market_ratio": 1.2275689064176813,
            "open_vs_sma_atr": 0.3600867678958785,
            "primary_score": 5.906728240839433,
            "trade_weekday": 1,
        }
        slightly_safer_candidate = dict(loss_candidate, open_vs_sma_atr=0.6)
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(**loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**slightly_safer_candidate),
            0.10,
        )
    def test_daytrade_primary_low_score_hot_market_fragile_core_no_trade(self):
        loss_candidate = {
            "breadth_val": 0.575110,
            "gap_pct": 0.000616,
            "market_ratio": 1.001321,
            "open_vs_sma_atr": 1.083489,
            "prev_return": 0.039028,
            "primary_score": 4.549075,
            "trade_weekday": 3,
        }
        slightly_safer_candidate = dict(loss_candidate, primary_score=6.5)
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(**loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**slightly_safer_candidate),
            0.0,
        )
    def test_daytrade_primary_low_breadth_mid_hot_low_score_no_trade(self):
        loss_candidates = [
            {
                "breadth_val": 0.460088,
                "gap_pct": 0.016420,
                "market_ratio": 1.068820,
                "open_vs_sma_atr": -0.175662,
                "primary_score": 4.076108,
                "trade_weekday": 2,
            },
            {
                "breadth_val": 0.514771,
                "gap_pct": 0.001017,
                "market_ratio": 1.086073,
                "open_vs_sma_atr": 2.472313,
                "primary_score": 5.618059,
                "trade_weekday": 0,
            },
            {
                "breadth_val": 0.538655,
                "gap_pct": 0.015928,
                "market_ratio": 1.098480,
                "open_vs_sma_atr": 1.570342,
                "primary_score": 4.935794,
                "trade_weekday": 2,
            },
            {
                "breadth_val": 0.528598,
                "gap_pct": -0.003086,
                "market_ratio": 1.086403,
                "open_vs_sma_atr": 2.784214,
                "primary_score": 4.609204,
                "trade_weekday": 2,
            },
            {
                "breadth_val": 0.548712,
                "gap_pct": -0.001745,
                "market_ratio": 1.088565,
                "open_vs_sma_atr": 0.036683,
                "primary_score": 3.499505,
                "trade_weekday": 1,
            },
        ]
        safe_candidate = {
            "breadth_val": 0.529855,
            "gap_pct": -0.004646,
            "market_ratio": 1.102576,
            "open_vs_sma_atr": 2.518521,
            "primary_score": 6.072058,
            "trade_weekday": 1,
        }
        for candidate in loss_candidates:
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**safe_candidate), 0.0)
    def test_daytrade_primary_friday_low_breadth_near_neutral_market_low_score_no_trade(self):
        loss_candidates = [
            {
                "breadth_val": 0.46825895663104966,
                "market_ratio": 1.035393926023235,
                "gap_pct": 0.0,
                "open_vs_sma_atr": 0.0,
                "primary_score": 5.560352587280899,
                "trade_weekday": 4,
            },
            {
                "breadth_val": 0.4764299182903834,
                "market_ratio": 1.0174014773875482,
                "gap_pct": 0.0,
                "open_vs_sma_atr": 0.0,
                "primary_score": 4.395681712279935,
                "trade_weekday": 4,
            },
        ]
        safe_candidate = {
            "breadth_val": 0.6725329981143935,
            "market_ratio": 1.0747053240421511,
                "gap_pct": 0.0,
                "open_vs_sma_atr": 0.0,
            "primary_score": 4.097058844464297,
            "trade_weekday": 4,
        }
        for candidate in loss_candidates:
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**safe_candidate), 0.0)
    def test_daytrade_primary_thursday_low_score_hot_market_stretched_open_no_trade(self):
        loss_candidate = {
            "breadth_val": 0.575110,
            "gap_pct": 0.004597,
            "market_ratio": 1.001321,
            "open_vs_sma_atr": 1.503759,
            "prev_return": 0.042027,
            "primary_score": 3.962894,
            "trade_weekday": 3,
        }
        slightly_safer_candidate = dict(loss_candidate, market_ratio=1.04, open_vs_sma_atr=1.55)
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(**loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**slightly_safer_candidate),
            0.0,
        )
    def test_daytrade_primary_thursday_mid_breadth_medium_gap_low_score_no_trade(self):
        loss_candidate = {
            "breadth_val": 0.594595,
            "gap_pct": 0.013912,
            "market_ratio": 1.045730,
            "open_vs_sma_atr": 1.610698,
            "primary_score": 6.944239,
            "trade_weekday": 3,
        }
        slightly_safer_candidate = dict(loss_candidate, primary_score=8.1)
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(**loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**slightly_safer_candidate),
            0.0,
        )
    def test_daytrade_primary_friday_low_score_hot_market_stretched_open_no_trade(self):
        loss_candidate = {
            "breadth_val": 0.672533,
            "gap_pct": -0.000139,
            "market_ratio": 1.074705,
            "open_vs_sma_atr": 3.849165,
            "prev_return": 0.050707,
            "primary_score": 6.669561,
            "trade_weekday": 4,
        }
        slightly_safer_candidate = dict(loss_candidate, open_vs_sma_atr=2.4)
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(**loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**slightly_safer_candidate),
            0.0,
        )
    def test_daytrade_primary_tuesday_low_score_hot_market_open_band_split(self):
        mid_open_loss_candidate = {
            "breadth_val": 0.707102,
            "gap_pct": 0.005668,
            "market_ratio": 1.180933,
            "open_vs_sma_atr": 0.964669,
            "primary_score": 3.572352,
            "trade_weekday": 1,
        }
        strong_open_candidate = {
            "breadth_val": 0.693903,
            "gap_pct": 0.005221,
            "market_ratio": 1.179655,
            "open_vs_sma_atr": 2.527284,
            "primary_score": 4.369317,
            "trade_weekday": 1,
        }
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**mid_open_loss_candidate),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**strong_open_candidate),
            0.75,
        )
    def test_daytrade_primary_monday_thursday_friday_low_score_hot_market_no_trade(self):
        loss_candidate = {
            "breadth_val": 0.609051,
            "gap_pct": -0.002500,
            "market_ratio": 1.105121,
            "open_vs_sma_atr": 0.669960,
            "prev_return": 0.017488,
            "primary_score": 4.720600,
            "trade_weekday": 0,
        }
        slightly_safer_candidate = dict(loss_candidate, primary_score=6.6)
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(**loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**slightly_safer_candidate),
            0.0,
        )
    def test_daytrade_primary_monday_tuesday_friday_low_score_stretched_open_large_gap_no_trade(self):
        monday_loss_candidate = {
            "breadth_val": 0.651163,
            "gap_pct": 0.018051,
            "market_ratio": 1.092293,
            "open_vs_sma_atr": 2.633787,
            "primary_score": 4.820711,
            "trade_weekday": 0,
        }
        tuesday_loss_candidate = {
            "breadth_val": 0.700817,
            "gap_pct": 0.024976,
            "market_ratio": 1.166610,
            "open_vs_sma_atr": 2.875949,
            "primary_score": 4.967275,
            "trade_weekday": 1,
        }
        friday_loss_candidate = {
            "breadth_val": 0.476430,
            "gap_pct": 0.029855,
            "market_ratio": 1.017401,
            "open_vs_sma_atr": 2.735172,
            "primary_score": 4.694918,
            "trade_weekday": 4,
        }
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**monday_loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                **dict(monday_loss_candidate, open_vs_sma_atr=2.4)
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**tuesday_loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                **dict(tuesday_loss_candidate, market_ratio=1.04, open_vs_sma_atr=2.4)
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**friday_loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.6725329981143935,
                gap_pct=0.0,
                market_ratio=1.0747053240421511,
                open_vs_sma_atr=0.0,
                primary_score=4.097058844464297,
                trade_weekday=4,
            ),
            0.0,
        )
    def test_daytrade_primary_monday_mid_breadth_mild_hot_market_tight_gap_no_trade(self):
        loss_candidate = {
            "breadth_val": 0.624764,
            "gap_pct": 0.004597,
            "market_ratio": 1.084117,
            "open_vs_sma_atr": -0.843570,
            "primary_score": 6.229129,
            "trade_weekday": 0,
        }
        survivor_candidate = {
            "breadth_val": 0.637335,
            "gap_pct": 0.021266,
            "market_ratio": 1.080330,
            "open_vs_sma_atr": 1.842980,
            "primary_score": 3.772276,
            "trade_weekday": 0,
        }
        self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**loss_candidate), 0.0)
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**survivor_candidate), 0.0)
    def test_daytrade_primary_monday_mid_breadth_mild_hot_market_mid_score_low_open_no_trade(self):
        loss_candidate = self._board_lot_candidate(
            "9997",
            9.121165,
            "primary",
            open_price=50000.0,
            gap_pct=-0.000747,
        )
        loss_candidate.update(
            {
                "breadth_val": 0.469516,
                "market_ratio": 1.063452,
                "open_vs_sma_atr": 0.908560,
                "primary_score": 9.121165,
                "trade_weekday": 0,
            }
        )
        survivor_candidate = self._board_lot_candidate(
            "9998",
            9.121165,
            "primary",
            open_price=50000.0,
            gap_pct=-0.000747,
        )
        survivor_candidate.update(
            {
                "breadth_val": 0.469516,
                "market_ratio": 1.063452,
                "open_vs_sma_atr": 1.1,
                "primary_score": 9.121165,
                "trade_weekday": 0,
            }
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=loss_candidate["breadth_val"],
                gap_pct=loss_candidate["gap_pct"],
                open_vs_sma_atr=loss_candidate["open_vs_sma_atr"],
                market_ratio=loss_candidate["market_ratio"],
                primary_score=loss_candidate["primary_score"],
                trade_weekday=loss_candidate["trade_weekday"],
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=survivor_candidate["breadth_val"],
                gap_pct=survivor_candidate["gap_pct"],
                open_vs_sma_atr=survivor_candidate["open_vs_sma_atr"],
                market_ratio=survivor_candidate["market_ratio"],
                primary_score=survivor_candidate["primary_score"],
                trade_weekday=survivor_candidate["trade_weekday"],
            ),
            0.0,
        )
        loss_equity_notional_pct = resolve_daytrade_primary_equity_notional_pct(
            breadth_val=loss_candidate["breadth_val"],
            gap_pct=loss_candidate["gap_pct"],
            open_vs_sma_atr=loss_candidate["open_vs_sma_atr"],
            market_ratio=loss_candidate["market_ratio"],
            primary_score=loss_candidate["primary_score"],
            trade_weekday=loss_candidate["trade_weekday"],
        )
        survivor_equity_notional_pct = resolve_daytrade_primary_equity_notional_pct(
            breadth_val=survivor_candidate["breadth_val"],
            gap_pct=survivor_candidate["gap_pct"],
            open_vs_sma_atr=survivor_candidate["open_vs_sma_atr"],
            market_ratio=survivor_candidate["market_ratio"],
            primary_score=survivor_candidate["primary_score"],
            trade_weekday=survivor_candidate["trade_weekday"],
        )
        self.assertEqual(
            cap_daytrade_position_size(
                raw_shares=10_000,
                current_equity=1_000_000,
                buying_power=1_000_000,
                entry_price=1_000.0,
                stop_price=920.0,
                notional_pct=loss_candidate["notional_pct"],
                equity_notional_pct=loss_equity_notional_pct,
                risk_budget_pct=0.12,
            ),
            0,
        )
        self.assertGreater(
            cap_daytrade_position_size(
                raw_shares=10_000,
                current_equity=1_000_000,
                buying_power=1_000_000,
                entry_price=1_000.0,
                stop_price=920.0,
                notional_pct=survivor_candidate["notional_pct"],
                equity_notional_pct=survivor_equity_notional_pct,
                risk_budget_pct=0.12,
            ),
            0,
        )
    def test_daytrade_primary_monday_mid_breadth_neutral_market_low_score_tight_gap_no_trade(self):
        loss_candidates = [
            {
                "breadth_val": 0.473287,
                "gap_pct": -0.002413,
                "market_ratio": 1.016038,
                "open_vs_sma_atr": 2.485703,
                "primary_score": 3.638857,
                "trade_weekday": 0,
            },
            {
                "breadth_val": 0.519170,
                "gap_pct": -0.001676,
                "market_ratio": 1.021425,
                "open_vs_sma_atr": 2.550031,
                "primary_score": 3.456664,
                "trade_weekday": 0,
            },
            {
                "breadth_val": 0.539283,
                "gap_pct": 0.001491,
                "market_ratio": 1.029490,
                "open_vs_sma_atr": 2.114565,
                "primary_score": 3.114581,
                "trade_weekday": 0,
            },
            {
                "breadth_val": 0.451917,
                "gap_pct": 0.004705,
                "market_ratio": 1.037822,
                "open_vs_sma_atr": 2.303116,
                "primary_score": 4.726512,
                "trade_weekday": 0,
            },
            {
                "breadth_val": 0.541798,
                "gap_pct": 0.0,
                "market_ratio": 1.012050,
                "open_vs_sma_atr": 2.033292,
                "primary_score": 4.687752,
                "trade_weekday": 0,
            },
        ]
        for candidate in loss_candidates:
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        survivor_candidate = {
            "breadth_val": 0.465116,
            "gap_pct": -0.001832,
            "market_ratio": 1.040209,
            "open_vs_sma_atr": 1.940660,
            "primary_score": 5.160957,
            "trade_weekday": 0,
        }
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**survivor_candidate), 0.0)
    def test_daytrade_primary_monday_mid_breadth_neutral_market_low_score_high_gap_no_trade(self):
        loss_candidates = [
            {
                "breadth_val": 0.451917,
                "gap_pct": 0.019608,
                "market_ratio": 1.037822,
                "open_vs_sma_atr": 1.717473,
                "primary_score": 4.149227,
                "trade_weekday": 0,
            },
            {
                "breadth_val": 0.467630,
                "gap_pct": 0.017820,
                "market_ratio": 1.043263,
                "open_vs_sma_atr": 1.040654,
                "primary_score": 4.173553,
                "trade_weekday": 0,
            },
        ]
        for candidate in loss_candidates:
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        survivor_candidate = {
            "breadth_val": 0.517913,
            "gap_pct": 0.003521,
            "market_ratio": 1.022852,
            "open_vs_sma_atr": 1.819444,
            "primary_score": 4.077229,
            "trade_weekday": 0,
        }
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**survivor_candidate), 0.0)
    def test_daytrade_primary_wednesday_high_score_mid_open_no_trade(self):
        wednesday_loss_candidates = [
            {
                "breadth_val": 0.654305,
                "gap_pct": 0.002291,
                "market_ratio": 1.039748,
                "open_vs_sma_atr": 1.552964,
                "primary_score": 10.855253,
                "trade_weekday": 2,
            },
            {
                "breadth_val": 0.703331,
                "gap_pct": 0.023940,
                "market_ratio": 1.171012,
                "open_vs_sma_atr": 1.871570,
                "primary_score": 9.838009,
                "trade_weekday": 2,
            },
            {
                "breadth_val": 0.721559,
                "gap_pct": 0.019039,
                "market_ratio": 1.024193,
                "open_vs_sma_atr": 1.390038,
                "primary_score": 15.594371,
                "trade_weekday": 2,
            },
        ]
        win_candidate = {
            "breadth_val": 0.432432,
            "gap_pct": 0.016997,
            "market_ratio": 1.032355,
            "open_vs_sma_atr": 2.484211,
            "primary_score": 7.657448,
            "trade_weekday": 2,
        }
        for candidate in wednesday_loss_candidates:
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**win_candidate), 0.0)
    def test_daytrade_primary_wednesday_stretched_from_prev_low_no_trade(self):
        loss_candidate = {
            "breadth_val": 0.587052,
            "gap_pct": 0.025586,
            "market_ratio": 1.115841,
            "open_from_prev_low_atr": 1.851064,
            "open_vs_sma_atr": 2.920213,
            "primary_score": 10.378423,
            "rs_alpha": 22.774869,
            "trade_weekday": 2,
        }
        breadth_survivor_candidate = {
            "breadth_val": 0.432432,
            "gap_pct": 0.016997,
            "market_ratio": 1.032355,
            "open_from_prev_low_atr": 1.894737,
            "open_vs_sma_atr": 2.484211,
            "primary_score": 7.657448,
            "rs_alpha": 41.2,
            "trade_weekday": 2,
        }
        open_survivor_candidate = {
            "breadth_val": 0.611565,
            "gap_pct": 0.000959,
            "market_ratio": 1.223087,
            "open_from_prev_low_atr": 0.597407,
            "open_vs_sma_atr": 0.701625,
            "primary_score": 5.602021,
            "rs_alpha": 52.177086,
            "trade_weekday": 2,
        }
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**breadth_survivor_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**open_survivor_candidate),
            0.0,
        )
    def test_daytrade_primary_tuesday_wednesday_high_breadth_mid_score_high_rsi_no_trade(self):
        loss_candidate = {
            "breadth_val": 0.703331,
            "gap_pct": -0.004082,
            "market_ratio": 1.171012,
            "open_vs_sma_atr": 1.569846,
            "primary_score": 6.409240,
            "prev_rsi2": 57.8125,
            "trade_weekday": 2,
        }
        second_loss_candidate = {
            "breadth_val": 0.700817,
            "gap_pct": 0.009250,
            "market_ratio": 1.252519,
            "open_vs_sma_atr": 0.111441,
            "primary_score": 7.281098,
            "prev_rsi2": 73.333333,
            "trade_weekday": 1,
        }
        survivor_candidate = {
            "breadth_val": 0.706474,
            "gap_pct": 0.009653,
            "market_ratio": 1.204034,
            "open_vs_sma_atr": 1.684324,
            "primary_score": 6.858091,
            "prev_rsi2": 38.709677,
            "trade_weekday": 1,
        }
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**loss_candidate),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**second_loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**survivor_candidate),
            0.0,
        )
    def test_daytrade_primary_failed_runup_exit_is_primary_only(self):
        self.assertTrue(
            is_daytrade_primary_failed_runup_exit(
                "primary",
                buy_price=100.0,
                current_price=99.8,
                session_high=102.0,
            )
        )
        self.assertFalse(
            is_daytrade_primary_failed_runup_exit(
                "fallback",
                buy_price=100.0,
                current_price=99.8,
                session_high=102.0,
            )
        )
        self.assertFalse(
            is_daytrade_primary_failed_runup_exit(
                "primary",
                buy_price=100.0,
                current_price=100.1,
                session_high=102.5,
            )
        )
        self.assertFalse(
            is_daytrade_primary_failed_runup_exit(
                "primary",
                buy_price=100.0,
                current_price=99.8,
                session_high=101.9,
            )
        )
    def test_daytrade_live_exit_helper_prioritizes_stop_and_target_before_failed_runup(self):
        stop_exit = resolve_daytrade_live_exit_decision(
            setup_type="primary",
            buy_price=100.0,
            open_price=100.4,
            high_price=102.6,
            low_price=97.8,
            current_price=99.8,
            stop_price=98.0,
            target_price=120.0,
            session_high=102.6,
        )
        target_exit = resolve_daytrade_live_exit_decision(
            setup_type="primary",
            buy_price=100.0,
            open_price=100.4,
            high_price=120.4,
            low_price=99.4,
            current_price=99.8,
            stop_price=98.0,
            target_price=120.0,
            session_high=120.4,
        )
        fade_exit = resolve_daytrade_live_exit_decision(
            setup_type="primary",
            buy_price=100.0,
            open_price=100.4,
            high_price=102.6,
            low_price=99.4,
            current_price=99.8,
            stop_price=98.0,
            target_price=120.0,
            session_high=102.6,
            allow_close_exit=False,
        )
        self.assertEqual(stop_exit, (98.0, "intraday_stop"))
        self.assertEqual(target_exit, (120.0, "intraday_target"))
        self.assertEqual(fade_exit, (100.0, "intraday_failed_runup"))
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
    def test_daytrade_primary_setup_avoids_friday_low_open(self):
        blocked_open = evaluate_daytrade_open_setup(
            open_p=100.2,
            prev_close=100.0,
            sma_med=99.2,
            breadth_val=0.62,
            prev_open=99.1,
            prev_atr=2.0,
            prev_low=98.7,
            prev_rsi2=54.0,
            rs_alpha=24.0,
            prev_prev_close=99.5,
            trade_weekday=4,
        )
        allowed_open = evaluate_daytrade_open_setup(
            open_p=100.2,
            prev_close=100.0,
            sma_med=98.8,
            breadth_val=0.62,
            prev_open=99.1,
            prev_atr=2.0,
            prev_low=98.7,
            prev_rsi2=54.0,
            rs_alpha=24.0,
            prev_prev_close=99.5,
            trade_weekday=0,
        )
        blocked_live = evaluate_daytrade_setup(
            price=100.6,
            open_p=100.2,
            prev_close=100.0,
            sma_med=99.2,
            breadth_val=0.62,
            prev_open=99.1,
            prev_atr=2.0,
            prev_low=98.7,
            rs_alpha=24.0,
            rsi2=54.0,
            prev_prev_close=99.5,
            trade_weekday=4,
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
            open_p=107.3,
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
            open_p=107.3,
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
            open_p=107.8,
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
            open_p=107.8,
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
    def test_daytrade_primary_setup_avoids_tuesday_index_gap_mid_breadth(self):
        blocked_open = evaluate_daytrade_open_setup(
            open_p=100.4,
            prev_close=100.0,
            sma_med=98.0,
            breadth_val=0.55,
            prev_open=96.5,
            prev_atr=2.0,
            prev_low=98.5,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=96.0,
            trade_weekday=1,
            market_open=101.2,
            prev_market_close=100.0,
        )
        allowed_lower_index_gap = evaluate_daytrade_open_setup(
            open_p=100.4,
            prev_close=100.0,
            sma_med=98.0,
            breadth_val=0.55,
            prev_open=96.5,
            prev_atr=2.0,
            prev_low=98.5,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=96.0,
            trade_weekday=1,
            market_open=100.8,
            prev_market_close=100.0,
        )
        allowed_other_breadth = evaluate_daytrade_open_setup(
            open_p=100.4,
            prev_close=100.0,
            sma_med=98.0,
            breadth_val=0.62,
            prev_open=96.5,
            prev_atr=2.0,
            prev_low=98.5,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=96.0,
            trade_weekday=1,
            market_open=101.2,
            prev_market_close=100.0,
        )
        blocked_live = evaluate_daytrade_setup(
            price=100.5,
            open_p=100.4,
            prev_close=100.0,
            sma_med=98.0,
            breadth_val=0.55,
            prev_open=96.5,
            prev_atr=2.0,
            prev_low=98.5,
            rs_alpha=40.0,
            rsi2=55.0,
            prev_prev_close=96.0,
            trade_weekday=1,
            market_open=101.2,
            prev_market_close=100.0,
        )
        self.assertIsNone(blocked_open)
        self.assertIsNotNone(allowed_lower_index_gap)
        self.assertIsNotNone(allowed_other_breadth)
        self.assertIsNone(blocked_live)
    def test_daytrade_primary_setup_avoids_tuesday_stall_gap(self):
        blocked_open = evaluate_daytrade_open_setup(
            open_p=109.62,
            prev_close=108.0,
            sma_med=104.0,
            breadth_val=0.72,
            prev_open=106.5,
            prev_atr=2.0,
            prev_low=106.0,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=104.0,
            trade_weekday=1,
        )
        allowed_open_lower_gap = evaluate_daytrade_open_setup(
            open_p=109.1,
            prev_close=108.0,
            sma_med=104.0,
            breadth_val=0.72,
            prev_open=106.5,
            prev_atr=2.0,
            prev_low=106.0,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=104.0,
            trade_weekday=1,
        )
        allowed_open_other_day = evaluate_daytrade_open_setup(
            open_p=109.62,
            prev_close=108.0,
            sma_med=104.0,
            breadth_val=0.72,
            prev_open=106.5,
            prev_atr=2.0,
            prev_low=106.0,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=104.0,
            trade_weekday=2,
        )
        blocked_live = evaluate_daytrade_setup(
            price=109.8,
            open_p=109.62,
            prev_close=108.0,
            sma_med=104.0,
            breadth_val=0.72,
            prev_open=106.5,
            prev_atr=2.0,
            prev_low=106.0,
            rs_alpha=40.0,
            rsi2=55.0,
            prev_prev_close=104.0,
            trade_weekday=1,
        )
        self.assertIsNone(blocked_open)
        self.assertIsNotNone(allowed_open_lower_gap)
        self.assertIsNotNone(allowed_open_other_day)
        self.assertIsNone(blocked_live)
    def test_daytrade_primary_setup_avoids_tuesday_far_trend_extension(self):
        blocked_open = evaluate_daytrade_open_setup(
            open_p=108.2,
            prev_close=108.0,
            sma_med=100.0,
            breadth_val=0.72,
            prev_open=106.5,
            prev_atr=2.0,
            prev_low=106.0,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=104.0,
            trade_weekday=1,
        )
        allowed_open_below_threshold = evaluate_daytrade_open_setup(
            open_p=108.2,
            prev_close=108.0,
            sma_med=100.1,
            breadth_val=0.72,
            prev_open=106.5,
            prev_atr=2.0,
            prev_low=106.0,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=104.0,
            trade_weekday=1,
        )
        allowed_open_other_day = evaluate_daytrade_open_setup(
            open_p=108.2,
            prev_close=108.0,
            sma_med=100.0,
            breadth_val=0.72,
            prev_open=106.5,
            prev_atr=2.0,
            prev_low=106.0,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=104.0,
            trade_weekday=4,
        )
        blocked_live = evaluate_daytrade_setup(
            price=108.4,
            open_p=108.2,
            prev_close=108.0,
            sma_med=100.0,
            breadth_val=0.72,
            prev_open=106.5,
            prev_atr=2.0,
            prev_low=106.0,
            rs_alpha=40.0,
            rsi2=55.0,
            prev_prev_close=104.0,
            trade_weekday=1,
        )
        self.assertIsNone(blocked_open)
        self.assertIsNotNone(allowed_open_below_threshold)
        self.assertIsNotNone(allowed_open_other_day)
        self.assertIsNone(blocked_live)
    def test_daytrade_primary_setup_avoids_wednesday_stall_gap_and_far_trend(self):
        blocked_gap_open = evaluate_daytrade_open_setup(
            open_p=108.864,
            prev_close=108.0,
            sma_med=104.0,
            breadth_val=0.72,
            prev_open=106.5,
            prev_atr=2.0,
            prev_low=106.0,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=104.0,
            trade_weekday=2,
        )
        allowed_gap_other_day = evaluate_daytrade_open_setup(
            open_p=108.864,
            prev_close=108.0,
            sma_med=104.0,
            breadth_val=0.72,
            prev_open=106.5,
            prev_atr=2.0,
            prev_low=106.0,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=104.0,
            trade_weekday=3,
        )
        blocked_far_trend_open = evaluate_daytrade_open_setup(
            open_p=110.3,
            prev_close=108.0,
            sma_med=99.5,
            breadth_val=0.72,
            prev_open=106.5,
            prev_atr=2.0,
            prev_low=106.0,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=104.0,
            trade_weekday=2,
        )
        allowed_far_trend_below_threshold = evaluate_daytrade_open_setup(
            open_p=110.3,
            prev_close=108.0,
            sma_med=100.2,
            breadth_val=0.72,
            prev_open=106.5,
            prev_atr=2.0,
            prev_low=106.0,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=104.0,
            trade_weekday=2,
        )
        blocked_live = evaluate_daytrade_setup(
            price=110.5,
            open_p=110.3,
            prev_close=108.0,
            sma_med=99.5,
            breadth_val=0.72,
            prev_open=106.5,
            prev_atr=2.0,
            prev_low=106.0,
            rs_alpha=40.0,
            rsi2=55.0,
            prev_prev_close=104.0,
            trade_weekday=2,
        )
        self.assertIsNone(blocked_gap_open)
        self.assertIsNotNone(allowed_gap_other_day)
        self.assertIsNone(blocked_far_trend_open)
        self.assertIsNotNone(allowed_far_trend_below_threshold)
        self.assertIsNone(blocked_live)
    def test_daytrade_primary_setup_avoids_tuesday_crowded_mid_high_breadth(self):
        blocked_open = evaluate_daytrade_open_setup(
            open_p=100.9,
            prev_close=100.0,
            sma_med=96.0,
            breadth_val=0.65,
            prev_open=99.0,
            prev_atr=2.0,
            prev_low=98.8,
            prev_rsi2=55.0,
            rs_alpha=60.0,
            prev_prev_close=97.0,
            trade_weekday=1,
        )
        allowed_higher_gap = evaluate_daytrade_open_setup(
            open_p=101.1,
            prev_close=100.0,
            sma_med=96.0,
            breadth_val=0.65,
            prev_open=99.0,
            prev_atr=2.0,
            prev_low=98.8,
            prev_rsi2=55.0,
            rs_alpha=60.0,
            prev_prev_close=97.0,
            trade_weekday=1,
        )
        allowed_lower_rs = evaluate_daytrade_open_setup(
            open_p=100.9,
            prev_close=100.0,
            sma_med=96.0,
            breadth_val=0.65,
            prev_open=99.0,
            prev_atr=2.0,
            prev_low=98.8,
            prev_rsi2=55.0,
            rs_alpha=50.0,
            prev_prev_close=97.0,
            trade_weekday=1,
        )
        allowed_other_day = evaluate_daytrade_open_setup(
            open_p=100.9,
            prev_close=100.0,
            sma_med=96.0,
            breadth_val=0.65,
            prev_open=99.0,
            prev_atr=2.0,
            prev_low=98.8,
            prev_rsi2=55.0,
            rs_alpha=60.0,
            prev_prev_close=97.0,
            trade_weekday=3,
        )
        blocked_live = evaluate_daytrade_setup(
            price=101.2,
            open_p=100.9,
            prev_close=100.0,
            sma_med=96.0,
            breadth_val=0.65,
            prev_open=99.0,
            prev_atr=2.0,
            prev_low=98.8,
            rs_alpha=60.0,
            rsi2=55.0,
            prev_prev_close=97.0,
            trade_weekday=1,
        )
        self.assertIsNone(blocked_open)
        self.assertIsNotNone(allowed_higher_gap)
        self.assertIsNotNone(allowed_lower_rs)
        self.assertIsNotNone(allowed_other_day)
        self.assertIsNone(blocked_live)
    def test_daytrade_primary_setup_avoids_wednesday_small_gap(self):
        blocked_open = evaluate_daytrade_open_setup(
            open_p=108.54,
            prev_close=108.0,
            sma_med=104.0,
            breadth_val=0.72,
            prev_open=106.5,
            prev_atr=2.0,
            prev_low=106.0,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=104.0,
            trade_weekday=2,
        )
        allowed_boundary_gap = evaluate_daytrade_open_setup(
            open_p=108.324,
            prev_close=108.0,
            sma_med=104.0,
            breadth_val=0.72,
            prev_open=106.5,
            prev_atr=2.0,
            prev_low=106.0,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=104.0,
            trade_weekday=2,
        )
        allowed_other_day = evaluate_daytrade_open_setup(
            open_p=108.54,
            prev_close=108.0,
            sma_med=104.0,
            breadth_val=0.72,
            prev_open=106.5,
            prev_atr=2.0,
            prev_low=106.0,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=104.0,
            trade_weekday=1,
        )
        blocked_live = evaluate_daytrade_setup(
            price=108.7,
            open_p=108.54,
            prev_close=108.0,
            sma_med=104.0,
            breadth_val=0.72,
            prev_open=106.5,
            prev_atr=2.0,
            prev_low=106.0,
            rs_alpha=40.0,
            rsi2=55.0,
            prev_prev_close=104.0,
            trade_weekday=2,
        )
        self.assertIsNone(blocked_open)
        self.assertIsNotNone(allowed_boundary_gap)
        self.assertIsNotNone(allowed_other_day)
        self.assertIsNone(blocked_live)
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
            trade_weekday=4,
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
            sma_med=98.5,
            breadth_val=0.55,
            prev_open=100.5,
            prev_atr=2.0,
            prev_low=100.3,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=96.0,
            trade_weekday=3,
        )
        self.assertIsNone(blocked_open)
        self.assertIsNotNone(allowed_open)
    def test_daytrade_primary_setup_avoids_thursday_broad_late_week_extension(self):
        blocked_open = evaluate_daytrade_open_setup(
            open_p=107.0,
            prev_close=106.6,
            sma_med=102.0,
            breadth_val=0.72,
            prev_open=105.5,
            prev_atr=2.0,
            prev_low=105.0,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=100.0,
            trade_weekday=3,
        )
        allowed_open = evaluate_daytrade_open_setup(
            open_p=107.0,
            prev_close=106.6,
            sma_med=102.0,
            breadth_val=0.72,
            prev_open=105.5,
            prev_atr=2.0,
            prev_low=105.0,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=100.0,
            trade_weekday=4,
        )
        blocked_live = evaluate_daytrade_setup(
            price=107.5,
            open_p=107.0,
            prev_close=106.6,
            sma_med=102.0,
            breadth_val=0.72,
            prev_open=105.5,
            prev_atr=2.0,
            prev_low=105.0,
            rs_alpha=40.0,
            rsi2=55.0,
            prev_prev_close=100.0,
            trade_weekday=3,
        )
        self.assertIsNone(blocked_open)
        self.assertIsNotNone(allowed_open)
        self.assertIsNone(blocked_live)
    def test_daytrade_primary_setup_avoids_thursday_neutral_trend_stall(self):
        blocked_open = evaluate_daytrade_open_setup(
            open_p=105.0,
            prev_close=104.0,
            sma_med=103.0,
            breadth_val=0.72,
            prev_open=102.0,
            prev_atr=2.0,
            prev_low=101.0,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=100.0,
            trade_weekday=3,
        )
        allowed_open = evaluate_daytrade_open_setup(
            open_p=105.0,
            prev_close=104.0,
            sma_med=103.0,
            breadth_val=0.72,
            prev_open=102.0,
            prev_atr=2.0,
            prev_low=101.0,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=100.0,
            trade_weekday=4,
        )
        blocked_live = evaluate_daytrade_setup(
            price=105.5,
            open_p=105.0,
            prev_close=104.0,
            sma_med=103.0,
            breadth_val=0.72,
            prev_open=102.0,
            prev_atr=2.0,
            prev_low=101.0,
            rs_alpha=40.0,
            rsi2=55.0,
            prev_prev_close=100.0,
            trade_weekday=3,
        )
        self.assertIsNone(blocked_open)
        self.assertIsNotNone(allowed_open)
        self.assertIsNone(blocked_live)
    def test_daytrade_primary_setup_avoids_thursday_stall_trend_extension(self):
        blocked_open = evaluate_daytrade_open_setup(
            open_p=108.0,
            prev_close=107.0,
            sma_med=100.0,
            breadth_val=0.72,
            prev_open=105.5,
            prev_atr=2.0,
            prev_low=105.0,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=103.0,
            trade_weekday=3,
        )
        allowed_open_below_threshold = evaluate_daytrade_open_setup(
            open_p=108.0,
            prev_close=107.0,
            sma_med=101.2,
            breadth_val=0.72,
            prev_open=105.5,
            prev_atr=2.0,
            prev_low=105.0,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=103.0,
            trade_weekday=3,
        )
        allowed_open_other_day = evaluate_daytrade_open_setup(
            open_p=108.0,
            prev_close=107.0,
            sma_med=100.0,
            breadth_val=0.72,
            prev_open=105.5,
            prev_atr=2.0,
            prev_low=105.0,
            prev_rsi2=55.0,
            rs_alpha=40.0,
            prev_prev_close=103.0,
            trade_weekday=4,
        )
        blocked_live = evaluate_daytrade_setup(
            price=108.3,
            open_p=108.0,
            prev_close=107.0,
            sma_med=100.0,
            breadth_val=0.72,
            prev_open=105.5,
            prev_atr=2.0,
            prev_low=105.0,
            rs_alpha=40.0,
            rsi2=55.0,
            prev_prev_close=103.0,
            trade_weekday=3,
        )
        self.assertIsNone(blocked_open)
        self.assertIsNotNone(allowed_open_below_threshold)
        self.assertIsNotNone(allowed_open_other_day)
        self.assertIsNone(blocked_live)
    def test_daytrade_primary_setup_avoids_friday_flat_gap_weak_rs(self):
        blocked_open = evaluate_daytrade_open_setup(
            open_p=105.6,
            prev_close=105.2,
            sma_med=102.0,
            breadth_val=0.65,
            prev_open=104.5,
            prev_atr=2.0,
            prev_low=104.0,
            prev_rsi2=55.0,
            rs_alpha=8.0,
            prev_prev_close=100.0,
            trade_weekday=4,
        )
        allowed_open = evaluate_daytrade_open_setup(
            open_p=105.6,
            prev_close=105.2,
            sma_med=102.0,
            breadth_val=0.65,
            prev_open=104.5,
            prev_atr=2.0,
            prev_low=104.0,
            prev_rsi2=55.0,
            rs_alpha=12.0,
            prev_prev_close=100.0,
            trade_weekday=4,
        )
        blocked_live = evaluate_daytrade_setup(
            price=106.1,
            open_p=105.6,
            prev_close=105.2,
            sma_med=102.0,
            breadth_val=0.65,
            prev_open=104.5,
            prev_atr=2.0,
            prev_low=104.0,
            rs_alpha=8.0,
            rsi2=55.0,
            prev_prev_close=100.0,
            trade_weekday=4,
        )
        self.assertIsNone(blocked_open)
        self.assertIsNotNone(allowed_open)
        self.assertIsNone(blocked_live)
    def test_daytrade_fallback_open_setup_is_bounded(self):
        accepted = evaluate_daytrade_fallback_open_setup(
            open_p=101.1,
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
            open_p=101.3,
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
    def test_daytrade_fallback_open_setup_avoids_low_breadth_flat_gap(self):
        blocked = evaluate_daytrade_fallback_open_setup(
            open_p=100.25,
            prev_close=100.0,
            sma_med=98.0,
            breadth_val=0.39,
            prev_atr=2.0,
            prev_low=99.2,
            prev_rsi2=55.0,
            rs_alpha=15.0,
            prev_prev_close=99.5,
        )
        allowed_by_breadth = evaluate_daytrade_fallback_open_setup(
            open_p=100.25,
            prev_close=100.0,
            sma_med=98.0,
            breadth_val=0.40,
            prev_atr=2.0,
            prev_low=99.2,
            prev_rsi2=55.0,
            rs_alpha=15.0,
            prev_prev_close=99.5,
        )
        allowed_by_gap = evaluate_daytrade_fallback_open_setup(
            open_p=100.5,
            prev_close=100.0,
            sma_med=98.0,
            breadth_val=0.39,
            prev_atr=2.0,
            prev_low=99.2,
            prev_rsi2=55.0,
            rs_alpha=15.0,
            prev_prev_close=99.5,
        )
        self.assertIsNone(blocked)
        self.assertIsNotNone(allowed_by_breadth)
        self.assertIsNotNone(allowed_by_gap)
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
    def test_daytrade_fallback_score_prefers_structural_room_over_compression(self):
        compressed = {
            "gap_pct": 0.007,
            "prev_return": 0.022,
            "open_from_prev_low_atr": 0.75,
            "open_vs_sma_atr": 0.46,
            "rs_alpha": 40.0,
        }
        structured = {
            "gap_pct": 0.007,
            "prev_return": 0.020,
            "open_from_prev_low_atr": 1.20,
            "open_vs_sma_atr": 4.00,
            "rs_alpha": 33.0,
        }
        self.assertGreater(
            score_daytrade_fallback_open_setup(structured, prev_rsi2=60.0, rs_alpha=33.0),
            score_daytrade_fallback_open_setup(compressed, prev_rsi2=60.0, rs_alpha=40.0),
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
        self.assertAlmostEqual(DAYTRADE_CATCHUP_GAPDOWN_EQUITY_NOTIONAL_PCT, 0.50)
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
    def test_daytrade_inverse_open_setup_supports_panic_rebreak(self):
        accepted = evaluate_daytrade_inverse_open_setup(
            open_p=104.9,
            prev_close=100.0,
            breadth_val=0.12,
            prev_atr=2.0,
            prev_prev_close=112.0,
            market_open=84.5,
            prev_market_close=87.0,
            prev_market_sma_trend=100.0,
        )
        rejected_shallow_market = evaluate_daytrade_inverse_open_setup(
            open_p=104.9,
            prev_close=100.0,
            breadth_val=0.12,
            prev_atr=2.0,
            prev_prev_close=112.0,
            market_open=90.0,
            prev_market_close=92.0,
            prev_market_sma_trend=100.0,
        )
        rejected_first_panic_day = evaluate_daytrade_inverse_open_setup(
            open_p=104.9,
            prev_close=100.0,
            breadth_val=0.12,
            prev_atr=2.0,
            prev_prev_close=96.0,
            market_open=84.5,
            prev_market_close=87.0,
            prev_market_sma_trend=100.0,
        )
        self.assertTrue(
            is_daytrade_inverse_rebreak_context(
                0.12,
                market_open=84.5,
                prev_market_close=87.0,
                prev_market_sma_trend=100.0,
            )
        )
        self.assertIsNotNone(accepted)
        self.assertEqual(accepted["setup_type"], "inverse_rebreak")
        self.assertGreater(accepted["gap_pct"], 0.03)
        self.assertLess(accepted["prev_return"], 0.0)
        self.assertGreater(score_daytrade_inverse_open_setup(accepted, rs_alpha=10.0), 3.0)
        self.assertIsNone(rejected_shallow_market)
        self.assertIsNone(rejected_first_panic_day)
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
        self.assertTrue(
            is_daytrade_strong_oversold_tuesday_stretched_open_filtered(
                2.1,
                trade_weekday=1,
            )
        )
        self.assertFalse(
            is_daytrade_strong_oversold_tuesday_stretched_open_filtered(
                1.9,
                trade_weekday=1,
            )
        )
        self.assertFalse(
            is_daytrade_strong_oversold_tuesday_stretched_open_filtered(
                2.1,
                trade_weekday=0,
            )
        )
    def test_daytrade_strong_oversold_pure_win_size_up(self):
        wednesday_sizeup_candidate = {
            "breadth_val": 0.695789,
            "gap_pct": -0.014571,
            "market_ratio": 1.039355,
            "score": 20.379097,
            "trade_weekday": 2,
        }
        thursday_sizeup_candidate = {
            "breadth_val": 0.687618,
            "gap_pct": -0.012005,
            "market_ratio": 1.049552,
            "score": 18.612141,
            "trade_weekday": 3,
        }
        hot_market_sizeup_candidate = {
            "breadth_val": 0.578,
            "gap_pct": 0.002,
            "market_ratio": 1.117,
            "score": 17.471,
            "open_vs_trend_atr": 1.141,
            "trade_weekday": 1,
        }
        stable_market_sizeup_candidate = {
            "breadth_val": 0.551,
            "gap_pct": -0.006,
            "market_ratio": 1.011,
            "score": 18.253,
            "open_vs_trend_atr": 2.071,
            "trade_weekday": 0,
        }
        holdout_near_miss_candidate = {
            "breadth_val": 0.684,
            "gap_pct": -0.013,
            "market_ratio": 1.128,
            "score": 18.013,
            "open_vs_trend_atr": 0.775,
            "trade_weekday": 0,
        }
        wednesday_loss_candidate = {
            "breadth_val": 0.654934,
            "gap_pct": -0.005059,
            "market_ratio": 0.996104,
            "score": 18.802731,
            "trade_weekday": 2,
        }
        self.assertEqual(
            resolve_daytrade_strong_oversold_notional_pct(**wednesday_sizeup_candidate),
            0.105,
        )
        self.assertEqual(
            resolve_daytrade_strong_oversold_notional_pct(**thursday_sizeup_candidate),
            0.105,
        )
        self.assertEqual(
            resolve_daytrade_strong_oversold_notional_pct(**hot_market_sizeup_candidate),
            0.105,
        )
        self.assertEqual(
            resolve_daytrade_strong_oversold_notional_pct(**stable_market_sizeup_candidate),
            0.105,
        )
        self.assertEqual(
            resolve_daytrade_strong_oversold_notional_pct(**holdout_near_miss_candidate),
            0.04,
        )
        self.assertEqual(
            resolve_daytrade_strong_oversold_notional_pct(**wednesday_loss_candidate),
            0.04,
        )
        self.assertEqual(
            resolve_daytrade_strong_oversold_equity_notional_pct(**wednesday_sizeup_candidate),
            4.0,
        )
        self.assertEqual(
            resolve_daytrade_strong_oversold_equity_notional_pct(**thursday_sizeup_candidate),
            4.0,
        )
        self.assertEqual(
            resolve_daytrade_strong_oversold_equity_notional_pct(**hot_market_sizeup_candidate),
            4.0,
        )
        self.assertEqual(
            resolve_daytrade_strong_oversold_equity_notional_pct(**stable_market_sizeup_candidate),
            4.0,
        )
        self.assertEqual(
            resolve_daytrade_strong_oversold_equity_notional_pct(**holdout_near_miss_candidate),
            1.0,
        )
        self.assertEqual(
            resolve_daytrade_strong_oversold_equity_notional_pct(**wednesday_loss_candidate),
            1.0,
        )
        self.assertEqual(
            resolve_daytrade_strong_oversold_risk_budget_pct(**wednesday_sizeup_candidate),
            0.125,
        )
        self.assertEqual(
            resolve_daytrade_strong_oversold_risk_budget_pct(**thursday_sizeup_candidate),
            0.125,
        )
        self.assertEqual(
            resolve_daytrade_strong_oversold_risk_budget_pct(**hot_market_sizeup_candidate),
            0.125,
        )
        self.assertEqual(
            resolve_daytrade_strong_oversold_risk_budget_pct(**stable_market_sizeup_candidate),
            0.125,
        )
        self.assertEqual(
            resolve_daytrade_strong_oversold_risk_budget_pct(**holdout_near_miss_candidate),
            0.10,
        )
        self.assertEqual(
            resolve_daytrade_strong_oversold_risk_budget_pct(**wednesday_loss_candidate),
            0.10,
        )
    def test_daytrade_candidate_selection_filters_monday_low_breadth_hot_market_strong_oversold(self):
        strong_oversold = [{"code": "3696", "score": 22.367028, "setup_type": "strong_oversold"}]
        self.assertTrue(
            is_daytrade_strong_oversold_monday_low_breadth_hot_market_filtered(
                strong_oversold[0],
                0.628536,
                1.042601,
                trade_weekday=0,
            )
        )
        self.assertTrue(
            is_daytrade_strong_oversold_monday_low_breadth_hot_market_filtered(
                strong_oversold[0],
                0.618479,
                1.031988,
                trade_weekday=0,
            )
        )
        self.assertTrue(
            is_daytrade_strong_oversold_monday_low_breadth_hot_market_filtered(
                strong_oversold[0],
                0.730358,
                1.023806,
                trade_weekday=0,
            )
        )
        self.assertFalse(
            is_daytrade_strong_oversold_monday_low_breadth_hot_market_filtered(
                strong_oversold[0],
                0.551226,
                1.011402,
                trade_weekday=0,
            )
        )
        self.assertFalse(
            is_daytrade_strong_oversold_monday_low_breadth_hot_market_filtered(
                strong_oversold[0],
                0.684475,
                1.127905,
                trade_weekday=0,
            )
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                strong_oversold,
                [],
                [],
                breadth_val=0.628536,
                market_ratio=1.042601,
                trade_weekday=0,
                max_count=1,
            ),
            [],
        )
    def test_daytrade_candidate_selection_filters_thursday_mid_breadth_strong_oversold(self):
        loss_candidate = {
            "code": "7649",
            "score": 18.475765,
            "setup_type": "strong_oversold",
            "gap_pct": -0.008053,
            "open_vs_sma_atr": 2.740808,
        }
        survivor_candidate = {
            "code": "9999",
            "score": 16.0,
            "setup_type": "strong_oversold",
            "gap_pct": -0.004,
            "open_vs_sma_atr": 1.8,
        }
        self.assertTrue(
            is_daytrade_strong_oversold_thursday_mid_breadth_filtered(
                loss_candidate,
                0.559397,
                1.048115,
                -0.008053,
                2.740808,
                trade_weekday=3,
            )
        )
        self.assertFalse(
            is_daytrade_strong_oversold_thursday_mid_breadth_filtered(
                survivor_candidate,
                0.559397,
                1.048115,
                -0.008053,
                1.8,
                trade_weekday=3,
            )
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [loss_candidate, survivor_candidate],
                [],
                breadth_val=0.559397,
                market_ratio=1.048115,
                trade_weekday=3,
                max_count=1,
            )[0]["code"],
            "9999",
        )
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
    def test_daytrade_candidate_selection_swaps_to_executable_raw_catchup_when_hot_market_fallback_cannot_build_board_lot(self):
        fallback = [
            self._board_lot_candidate("2000", 8.0, "fallback", open_price=50000.0, gap_pct=0.009),
        ]
        catchup = [
            self._board_lot_candidate("2500", 15.0, "catchup_rs", open_price=8000.0, gap_pct=0.010),
            self._board_lot_candidate("2501", 9.2, "catchup_gapdown", open_price=8500.0, gap_pct=-0.012),
        ]
        selected = select_daytrade_candidates(
            [],
            [],
            fallback,
            catchup,
            breadth_val=0.54,
            market_ratio=1.16,
            trade_date=pd.Timestamp("2026-06-05"),
            trade_weekday=4,
            current_equity=1_005_000.0,
            week_start_equity=1_000_000.0,
            current_time=pd.Timestamp("2026-06-05"),
            account_cash=1_005_000.0,
            base_leverage=1.25,
            max_count=1,
        )
        self.assertEqual(selected[0]["code"], "2500")
        self.assertEqual(selected[0]["setup_type"], "catchup_rs")
    def test_daytrade_candidate_selection_filters_hot_market_fallback_even_when_catchup_gap_is_small(self):
        fallback = [
            self._board_lot_candidate("2000", 8.0, "fallback", open_price=50000.0, gap_pct=0.009),
        ]
        catchup = [
            self._board_lot_candidate("2500", 13.0, "catchup_rs", open_price=8000.0, gap_pct=0.010),
        ]
        selected = select_daytrade_candidates(
            [],
            [],
            fallback,
            catchup,
            breadth_val=0.54,
            market_ratio=1.16,
            trade_date=pd.Timestamp("2026-06-05"),
            trade_weekday=4,
            current_equity=1_005_000.0,
            week_start_equity=1_000_000.0,
            current_time=pd.Timestamp("2026-06-05"),
            account_cash=1_005_000.0,
            base_leverage=1.25,
            max_count=1,
        )
        self.assertEqual(selected[0]["code"], "2500")
        self.assertEqual(selected[0]["setup_type"], "catchup_rs")
    def test_daytrade_candidate_selection_can_recover_catchup_gapdown_low_breadth(self):
        fallback = [
            self._board_lot_candidate("2000", 6.0, "fallback", open_price=50000.0, gap_pct=0.009),
        ]
        catchup = [
            self._board_lot_candidate("2600", 7.8, "catchup_gapdown", open_price=8000.0, gap_pct=-0.012),
        ]
        selected = select_daytrade_candidates(
            [],
            [],
            fallback,
            catchup,
            breadth_val=0.30,
            market_ratio=1.16,
            trade_date=pd.Timestamp("2026-06-05"),
            trade_weekday=2,
            current_equity=1_005_000.0,
            week_start_equity=1_000_000.0,
            current_time=pd.Timestamp("2026-06-05"),
            account_cash=1_005_000.0,
            base_leverage=1.25,
            max_count=1,
        )
        self.assertEqual(selected[0]["code"], "2600")
        self.assertEqual(selected[0]["setup_type"], "catchup_gapdown")
    def test_daytrade_candidate_selection_filters_tuesday_weak_market_high_open_fallback(self):
        fallback = [
            {"code": "2384", "score": 4.0, "setup_type": "fallback", "prev_return": 0.03, "open_vs_sma_atr": 5.2},
        ]
        catchup = [{"code": "2500", "score": 7.0, "setup_type": "catchup_rs", "gap_pct": 0.009}]
        self.assertTrue(
            is_daytrade_fallback_tuesday_weak_market_high_open_filtered(
                fallback[0],
                0.46,
                1.02,
                trade_weekday=1,
            )
        )
        self.assertFalse(
            is_daytrade_fallback_tuesday_weak_market_high_open_filtered(
                fallback[0],
                0.46,
                1.08,
                trade_weekday=1,
            )
        )
        selected = select_daytrade_candidates(
            [],
            [],
            fallback,
            catchup,
            breadth_val=0.46,
            market_ratio=1.02,
            trade_weekday=1,
            max_count=1,
        )
        self.assertEqual(selected[0]["setup_type"], "catchup_rs")
    def test_daytrade_candidate_selection_filters_tuesday_friday_mid_market_fallback(self):
        fallback = [
            {"code": "2384", "score": 5.5, "setup_type": "fallback"},
        ]
        self.assertTrue(
            is_daytrade_fallback_tuesday_friday_mid_market_filtered(
                fallback[0],
                1.03,
                trade_weekday=1,
            )
        )
        self.assertTrue(
            is_daytrade_fallback_tuesday_friday_mid_market_filtered(
                fallback[0],
                1.03,
                trade_weekday=4,
            )
        )
        self.assertFalse(
            is_daytrade_fallback_tuesday_friday_mid_market_filtered(
                fallback[0],
                1.07,
                trade_weekday=1,
            )
        )
        self.assertFalse(
            is_daytrade_fallback_tuesday_friday_mid_market_filtered(
                fallback[0],
                1.03,
                trade_weekday=0,
            )
        )
        selected = select_daytrade_candidates(
            [],
            [],
            fallback,
            [],
            breadth_val=0.46,
            market_ratio=1.03,
            trade_weekday=1,
            max_count=1,
        )
        self.assertEqual(selected, [])
    def test_daytrade_candidate_selection_filters_wednesday_low_breadth_high_open_fallback(self):
        loss_candidate = self._board_lot_candidate(
            "4194",
            5.981567,
            "fallback",
            open_price=4500.0,
            gap_pct=0.0,
        )
        loss_candidate.update({
            "prev_return": 0.053012,
            "open_vs_sma_atr": 2.627566,
        })
        survivor_candidate = self._board_lot_candidate(
            "1719",
            3.091724,
            "fallback",
            open_price=3000.0,
            gap_pct=0.0,
        )
        survivor_candidate.update({
            "prev_return": 0.038574,
            "open_vs_sma_atr": 0.237235,
        })
        self.assertTrue(
            is_daytrade_fallback_wednesday_low_breadth_high_open_filtered(
                loss_candidate,
                0.373979,
                1.005738,
                trade_weekday=2,
            )
        )
        self.assertFalse(
            is_daytrade_fallback_wednesday_low_breadth_high_open_filtered(
                survivor_candidate,
                0.406034,
                1.121076,
                trade_weekday=2,
            )
        )
        selected = select_daytrade_candidates(
            [],
            [],
            [loss_candidate, survivor_candidate],
            [],
            breadth_val=0.373979,
            market_ratio=1.005738,
            trade_weekday=2,
            max_count=1,
        )
        self.assertEqual(selected[0]["code"], "1719")
    def test_daytrade_candidate_selection_preserves_primary_no_trade_pocket(self):
        primary = [
            self._board_lot_candidate("3000", 8.0, "primary", open_price=50000.0, gap_pct=0.0),
        ]
        catchup = [
            self._board_lot_candidate("2500", 12.0, "catchup_rs", open_price=8000.0, gap_pct=0.010),
        ]
        selected = select_daytrade_candidates(
            primary,
            [],
            [],
            catchup,
            breadth_val=0.58,
            market_ratio=1.20,
            trade_date=pd.Timestamp("2026-06-05"),
            trade_weekday=4,
            current_equity=1_005_000.0,
            week_start_equity=1_000_000.0,
            current_time=pd.Timestamp("2026-06-05"),
            account_cash=1_005_000.0,
            base_leverage=1.25,
            max_count=1,
        )
        self.assertEqual(selected[0]["code"], "3000")
        self.assertEqual(selected[0]["setup_type"], "primary")
    def test_daytrade_candidate_selection_prefers_bull_etf_over_low_breadth_non_primary(self):
        catchup = [
            {"code": "7979", "score": 11.9, "setup_type": "catchup_rs", "gap_pct": 0.0149},
            {"code": "7011", "score": 7.3, "setup_type": "catchup_rs", "gap_pct": 0.0173},
        ]
        bull_etf = [{"code": "1570", "score": 8.4, "setup_type": "bull_etf_rebound"}]
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                catchup,
                [],
                bull_etf,
                breadth_val=0.216,
                trade_weekday=1,
                max_count=1,
            )[0]["code"],
            "1570",
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                catchup,
                [],
                [],
                breadth_val=0.216,
                trade_weekday=1,
                max_count=1,
            )[0]["code"],
            "7979",
        )
    def test_daytrade_candidate_selection_replaces_primary_on_high_ratio_crowding(self):
        primary = [
            {"code": f"{3000 + idx}", "score": 10.0 - (idx * 0.05), "setup_type": "primary"}
            for idx in range(20)
        ]
        catchup = [
            {"code": "9000", "score": 11.2, "setup_type": "catchup_rs"},
            {"code": "9001", "score": 9.8, "setup_type": "catchup_rs"},
        ]
        replaced = select_daytrade_candidates(
            primary,
            [],
            [],
            catchup,
            market_ratio=1.10,
            max_count=1,
        )
        self.assertEqual(replaced[0]["code"], "9000")
        self.assertEqual(
            select_daytrade_candidates(
                primary,
                [],
                [],
                catchup,
                market_ratio=1.09,
                max_count=1,
            )[0]["code"],
            "3000",
        )
        self.assertEqual(
            select_daytrade_candidates(
                primary[:19],
                [],
                [],
                catchup,
                market_ratio=1.10,
                max_count=1,
            )[0]["code"],
            "3000",
        )
    def test_daytrade_candidate_selection_replaces_fallback_with_hot_market_catchup_rs(self):
        fallback = [{"code": "2282", "score": 3.8, "setup_type": "fallback"}]
        catchup = [{"code": "7940", "score": 14.4, "setup_type": "catchup_rs", "gap_pct": 0.011}]
        replaced = select_daytrade_candidates(
            [],
            [],
            fallback,
            catchup,
            breadth_val=0.54,
            market_ratio=1.11,
            max_count=1,
        )
        self.assertEqual(replaced[0]["code"], "7940")
        self.assertEqual(replaced[0]["setup_type"], "catchup_rs")
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                fallback,
                catchup,
                breadth_val=0.56,
                market_ratio=1.11,
                max_count=1,
            )[0]["code"],
            "7940",
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                fallback,
                catchup,
                breadth_val=0.54,
                market_ratio=1.09,
                max_count=1,
            )[0]["code"],
            "7940",
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                fallback,
                [{"code": "7940", "score": 14.4, "setup_type": "catchup_rs", "gap_pct": 0.013}],
                breadth_val=0.54,
                market_ratio=1.11,
                max_count=1,
            )[0]["code"],
            "7940",
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                fallback,
                [{"code": "7940", "score": 9.7, "setup_type": "catchup_rs", "gap_pct": 0.011}],
                breadth_val=0.54,
                market_ratio=1.11,
                max_count=1,
            )[0]["code"],
            "7940",
        )
    def test_daytrade_candidate_selection_filters_wednesday_low_breadth_catchup_rs(self):
        catchup = [{"code": "3687", "score": 11.6, "setup_type": "catchup_rs", "gap_pct": 0.012}]
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                catchup,
                breadth_val=0.40,
                trade_weekday=2,
                max_count=1,
            ),
            [],
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                catchup,
                breadth_val=0.46,
                trade_weekday=2,
                max_count=1,
            )[0]["code"],
            "3687",
        )
    def test_daytrade_candidate_selection_filters_wednesday_catchup_rs_pockets(self):
        mid_gap_loss_candidate = {
            "code": "6508",
            "score": 4.486012266314807,
            "setup_type": "catchup_rs",
            "gap_pct": 0.0034364261168384758,
            "open_vs_sma_atr": 2.163511187607573,
            "prev_rsi2": 83.33333332777778,
        }
        mid_gap_survivor_candidate = {
            "code": "8706",
            "score": 7.14,
            "setup_type": "catchup_rs",
            "gap_pct": 0.0025,
            "open_vs_sma_atr": 1.123,
            "prev_rsi2": 75.0,
        }
        weak_open_loss_candidate = {
            "code": "2607",
            "score": 6.914306984279813,
            "setup_type": "catchup_rs",
            "gap_pct": 0.006752608962553808,
            "open_vs_sma_atr": 1.6197021764032073,
            "prev_rsi2": 76.23762376086658,
        }
        weak_open_survivor_candidate = {
            "code": "2432",
            "score": 7.82,
            "setup_type": "catchup_rs",
            "gap_pct": 0.007,
            "open_vs_sma_atr": 1.467,
            "prev_rsi2": 76.6,
        }
        self.assertTrue(
            is_daytrade_catchup_rs_wednesday_mid_breadth_low_gap_hot_open_filtered(
                mid_gap_loss_candidate,
                0.5273412947831553,
                1.0128991435446986,
                trade_weekday=2,
            )
        )
        self.assertFalse(
            is_daytrade_catchup_rs_wednesday_mid_breadth_low_gap_hot_open_filtered(
                mid_gap_survivor_candidate,
                0.5273412947831553,
                1.0128991435446986,
                trade_weekday=2,
            )
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                [mid_gap_loss_candidate],
                breadth_val=0.5273412947831553,
                market_ratio=1.0128991435446986,
                trade_weekday=2,
                max_count=1,
            ),
            [],
        )
        self.assertTrue(
            is_daytrade_catchup_rs_wednesday_low_breadth_weak_market_low_open_filtered(
                weak_open_loss_candidate,
                0.47203016970458833,
                0.991090482699679,
                trade_weekday=2,
            )
        )
        self.assertFalse(
            is_daytrade_catchup_rs_wednesday_low_breadth_weak_market_low_open_filtered(
                weak_open_survivor_candidate,
                0.47203016970458833,
                0.991090482699679,
                trade_weekday=2,
            )
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                [weak_open_loss_candidate],
                breadth_val=0.47203016970458833,
                market_ratio=0.991090482699679,
                trade_weekday=2,
                max_count=1,
            ),
            [],
        )
        negative_open_loss_candidate = {
            "code": "5535",
            "score": 16.705137677477644,
            "setup_type": "catchup_rs",
            "gap_pct": 0.0015282730514518672,
            "open_vs_sma_atr": -1.6246246246246243,
            "rs_alpha": 147.2292191435768,
        }
        negative_open_survivor_candidate = {
            "code": "2432",
            "score": 7.82,
            "setup_type": "catchup_rs",
            "gap_pct": 0.007,
            "open_vs_sma_atr": 1.467,
            "rs_alpha": 37.62,
        }
        self.assertTrue(
            is_daytrade_catchup_rs_wednesday_mid_breadth_negative_open_extreme_rs_filtered(
                negative_open_loss_candidate,
                0.502828409805154,
                0.9524392055433709,
                trade_weekday=2,
            )
        )
        self.assertFalse(
            is_daytrade_catchup_rs_wednesday_mid_breadth_negative_open_extreme_rs_filtered(
                negative_open_survivor_candidate,
                0.502828409805154,
                0.9524392055433709,
                trade_weekday=2,
            )
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                [negative_open_loss_candidate],
                breadth_val=0.502828409805154,
                market_ratio=0.9524392055433709,
                trade_weekday=2,
                max_count=1,
            ),
            [],
        )
    def test_daytrade_candidate_selection_filters_remaining_monday_tuesday_catchup_rs_pockets(self):
        monday_deep_gap_loss_candidate = {
            "code": "7013",
            "score": 10.0,
            "setup_type": "catchup_rs",
            "gap_pct": 0.0289,
            "open_vs_sma_atr": 2.506,
            "prev_rsi2": 73.1,
        }
        monday_low_open_loss_candidate = {
            "code": "8002",
            "score": 6.95,
            "setup_type": "catchup_rs",
            "gap_pct": 0.0032,
            "open_vs_sma_atr": 0.181,
            "prev_rsi2": 70.5,
        }
        tuesday_low_open_loss_candidate = {
            "code": "7532",
            "score": 4.32,
            "setup_type": "catchup_rs",
            "gap_pct": 0.0,
            "open_vs_sma_atr": 0.53,
            "prev_rsi2": 46.9,
        }
        self.assertTrue(
            is_daytrade_catchup_rs_monday_low_breadth_deep_gap_stretched_open_filtered(
                monday_deep_gap_loss_candidate,
                0.4,
                0.98,
                trade_weekday=0,
            )
        )
        self.assertTrue(
            is_daytrade_catchup_rs_monday_low_breadth_low_open_filtered(
                monday_low_open_loss_candidate,
                0.374,
                0.961,
                trade_weekday=0,
            )
        )
        self.assertTrue(
            is_daytrade_catchup_rs_tuesday_low_breadth_low_open_filtered(
                tuesday_low_open_loss_candidate,
                0.417,
                0.962,
                trade_weekday=1,
            )
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                [monday_deep_gap_loss_candidate],
                breadth_val=0.4,
                market_ratio=0.98,
                trade_weekday=0,
                max_count=1,
            ),
            [],
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                [monday_low_open_loss_candidate],
                breadth_val=0.374,
                market_ratio=0.961,
                trade_weekday=0,
                max_count=1,
            ),
            [],
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                [tuesday_low_open_loss_candidate],
                breadth_val=0.417,
                market_ratio=0.962,
                trade_weekday=1,
                max_count=1,
            ),
            [],
        )
    def test_daytrade_candidate_selection_filters_monday_low_score_catchup_rs(self):
        loss_candidate = {"code": "2501", "score": 5.672569, "setup_type": "catchup_rs"}
        survivor_candidate = {"code": "6454", "score": 6.077388, "setup_type": "catchup_rs"}
        self.assertTrue(
            is_daytrade_catchup_rs_monday_low_score_filtered(
                loss_candidate,
                trade_weekday=0,
            )
        )
        self.assertFalse(
            is_daytrade_catchup_rs_monday_low_score_filtered(
                survivor_candidate,
                trade_weekday=0,
            )
        )
        self.assertFalse(
            is_daytrade_catchup_rs_monday_low_score_filtered(
                loss_candidate,
                trade_weekday=1,
            )
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                [loss_candidate, survivor_candidate],
                breadth_val=0.43,
                trade_weekday=0,
                max_count=1,
            )[0]["code"],
            "6454",
        )
    def test_daytrade_candidate_selection_filters_monday_weak_market_catchup_rs(self):
        catchup = [
            {"code": "6101", "score": 11.2, "setup_type": "catchup_rs", "gap_pct": 0.008},
            {"code": "7011", "score": 10.4, "setup_type": "catchup_rs", "gap_pct": 0.011},
        ]
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                catchup,
                breadth_val=0.48,
                market_ratio=0.96,
                trade_weekday=0,
                max_count=1,
            )[0]["code"],
            "7011",
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                [catchup[0]],
                breadth_val=0.48,
                market_ratio=0.96,
                trade_weekday=0,
                max_count=1,
            ),
            [],
        )
    def test_daytrade_candidate_selection_filters_monday_low_breadth_weak_market_stretched_open_high_rsi_catchup_rs(self):
        loss_candidate = {
            "code": "2726",
            "score": 13.0,
            "setup_type": "catchup_rs",
            "gap_pct": 0.017027863777089758,
            "open_vs_sma_atr": 2.256913021618902,
            "prev_rsi2": 87.4999999978125,
        }
        second_loss_candidate = {
            "code": "5727",
            "score": 12.5,
            "setup_type": "catchup_rs",
            "gap_pct": 0.019854721549636745,
            "open_vs_sma_atr": 2.929530201342282,
            "prev_rsi2": 84.74576270899166,
        }
        survivor_candidate = {
            "code": "9107",
            "score": 12.0,
            "setup_type": "catchup_rs",
            "gap_pct": 0.018,
            "open_vs_sma_atr": 3.217,
            "prev_rsi2": 60.0,
        }
        second_survivor_candidate = {
            "code": "9501",
            "score": 11.0,
            "setup_type": "catchup_rs",
            "gap_pct": 0.0155,
            "open_vs_sma_atr": 3.247,
            "prev_rsi2": 50.0,
        }
        self.assertTrue(
            is_daytrade_catchup_rs_monday_low_breadth_weak_market_stretched_open_high_rsi_filtered(
                loss_candidate,
                0.4186046511627907,
                0.988377893056664,
                trade_weekday=0,
            )
        )
        self.assertTrue(
            is_daytrade_catchup_rs_monday_low_breadth_weak_market_stretched_open_high_rsi_filtered(
                second_loss_candidate,
                0.4186046511627907,
                0.988377893056664,
                trade_weekday=0,
            )
        )
        self.assertFalse(
            is_daytrade_catchup_rs_monday_low_breadth_weak_market_stretched_open_high_rsi_filtered(
                survivor_candidate,
                0.4186046511627907,
                0.988377893056664,
                trade_weekday=0,
            )
        )
        self.assertFalse(
            is_daytrade_catchup_rs_monday_low_breadth_weak_market_stretched_open_high_rsi_filtered(
                second_survivor_candidate,
                0.4186046511627907,
                0.988377893056664,
                trade_weekday=0,
            )
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                [loss_candidate, second_loss_candidate, survivor_candidate, second_survivor_candidate],
                breadth_val=0.4186046511627907,
                market_ratio=0.988377893056664,
                trade_weekday=0,
                max_count=1,
            )[0]["code"],
            "9107",
        )
    def test_daytrade_candidate_selection_filters_monday_mid_breadth_catchup_rs(self):
        loss_candidate = {
            "code": "9501",
            "score": 9.184777848560607,
            "setup_type": "catchup_rs",
            "gap_pct": 0.03392568659127626,
            "open_vs_sma_atr": 2.9129662522202486,
        }
        survivor_candidate = {
            "code": "9501X",
            "score": 10.184777848560607,
            "setup_type": "catchup_rs",
            "gap_pct": 0.03392568659127626,
            "open_vs_sma_atr": 2.9129662522202486,
        }
        self.assertTrue(
            is_daytrade_catchup_rs_monday_mid_breadth_stretched_open_filtered(
                loss_candidate,
                0.5059710873664363,
                trade_weekday=0,
            )
        )
        self.assertFalse(
            is_daytrade_catchup_rs_monday_mid_breadth_stretched_open_filtered(
                survivor_candidate,
                0.5059710873664363,
                trade_weekday=0,
            )
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                [loss_candidate, survivor_candidate],
                breadth_val=0.5059710873664363,
                trade_weekday=0,
                max_count=1,
            )[0]["code"],
            "9501X",
        )
    def test_daytrade_candidate_selection_filters_monday_low_breadth_hot_gap_low_open_catchup_rs(self):
        catchup = [
            {
                "code": "6101",
                "score": 11.2,
                "setup_type": "catchup_rs",
                "gap_pct": 0.012,
                "open_vs_sma_atr": 0.5,
            },
            {
                "code": "7011",
                "score": 10.4,
                "setup_type": "catchup_rs",
                "gap_pct": 0.012,
                "open_vs_sma_atr": 1.2,
            },
        ]
        self.assertTrue(
            is_daytrade_catchup_rs_monday_low_breadth_hot_gap_low_open_filtered(
                catchup[0],
                0.48,
                trade_weekday=0,
            )
        )
        self.assertFalse(
            is_daytrade_catchup_rs_monday_low_breadth_hot_gap_low_open_filtered(
                catchup[0],
                0.48,
                trade_weekday=2,
            )
        )
        self.assertFalse(
            is_daytrade_catchup_rs_monday_low_breadth_hot_gap_low_open_filtered(
                catchup[0],
                0.56,
                trade_weekday=0,
            )
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                catchup,
                breadth_val=0.48,
                market_ratio=0.98,
                trade_weekday=0,
                max_count=1,
            )[0]["code"],
            "7011",
        )
    def test_daytrade_candidate_selection_filters_high_breadth_catchup_rs(self):
        catchup = [
            {"code": "6101", "score": 11.2, "setup_type": "catchup_rs", "gap_pct": 0.008},
            {"code": "2501", "score": 9.6, "setup_type": "catchup_gapdown", "gap_pct": -0.012},
        ]
        self.assertTrue(
            is_daytrade_catchup_rs_high_breadth_filtered(catchup[0], 0.56, trade_weekday=0)
        )
        self.assertTrue(
            is_daytrade_catchup_rs_high_breadth_filtered(catchup[0], 0.56, trade_weekday=4)
        )
        self.assertFalse(
            is_daytrade_catchup_rs_high_breadth_filtered(catchup[0], 0.56, trade_weekday=2)
        )
        self.assertFalse(
            is_daytrade_catchup_rs_high_breadth_filtered(catchup[0], 0.54, trade_weekday=0)
        )
        selected = select_daytrade_candidates(
            [],
            [],
            [],
            catchup,
            breadth_val=0.56,
            market_ratio=0.99,
            trade_weekday=0,
            max_count=1,
        )
        self.assertEqual(selected[0]["setup_type"], "catchup_gapdown")
    def test_daytrade_candidate_selection_filters_low_breadth_high_market_ratio_catchup_rs(self):
        catchup = [{"code": "1963", "score": 6.1, "setup_type": "catchup_rs", "gap_pct": -0.000272}]
        self.assertTrue(
            is_daytrade_catchup_rs_low_breadth_high_market_ratio_filtered(catchup[0], 0.538655, 1.195596, trade_weekday=2)
        )
        self.assertTrue(
            is_daytrade_catchup_rs_low_breadth_high_market_ratio_filtered(catchup[0], 0.546826, 1.160304, trade_weekday=1)
        )
        self.assertFalse(
            is_daytrade_catchup_rs_low_breadth_high_market_ratio_filtered(catchup[0], 0.546826, 1.200304, trade_weekday=4)
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                catchup,
                breadth_val=0.538655,
                market_ratio=1.195596,
                trade_weekday=2,
                max_count=1,
            ),
            [],
        )
    def test_daytrade_candidate_selection_filters_tuesday_very_hot_low_breadth_catchup_rs(self):
        loss_candidate = {"code": "7717", "score": 10.986723, "setup_type": "catchup_rs", "gap_pct": 0.00361}
        survivor_candidate = {"code": "6480", "score": 18.903164, "setup_type": "catchup_rs", "gap_pct": 0.011061}
        self.assertTrue(
            is_daytrade_catchup_rs_tuesday_low_breadth_very_hot_market_filtered(
                loss_candidate,
                0.407291,
                1.22013,
                trade_weekday=1,
            )
        )
        self.assertFalse(
            is_daytrade_catchup_rs_tuesday_low_breadth_very_hot_market_filtered(
                survivor_candidate,
                0.422376,
                1.31693,
                trade_weekday=1,
            )
        )
        selected = select_daytrade_candidates(
            [],
            [],
            [],
            [loss_candidate, survivor_candidate],
            breadth_val=0.407291,
            market_ratio=1.22013,
            trade_weekday=1,
            max_count=1,
        )
        self.assertEqual(selected[0]["code"], "6480")
    def test_daytrade_candidate_selection_filters_friday_low_breadth_catchup_rs(self):
        catchup = [{"code": "6101", "score": 11.2, "setup_type": "catchup_rs", "gap_pct": 0.008}]
        self.assertTrue(
            is_daytrade_catchup_rs_friday_low_breadth_filtered(
                catchup[0],
                0.54,
                1.04,
                trade_weekday=4,
            )
        )
        self.assertFalse(
            is_daytrade_catchup_rs_friday_low_breadth_filtered(
                catchup[0],
                0.56,
                1.04,
                trade_weekday=4,
            )
        )
        self.assertFalse(
            is_daytrade_catchup_rs_friday_low_breadth_filtered(
                catchup[0],
                0.54,
                1.16,
                trade_weekday=4,
            )
        )
        self.assertFalse(
            is_daytrade_catchup_rs_friday_low_breadth_filtered(
                catchup[0],
                0.54,
                1.04,
                trade_weekday=2,
            )
        )
        hot_market_loss = [{"code": "5074", "score": 13.9, "setup_type": "catchup_rs"}]
        self.assertTrue(
            is_daytrade_catchup_rs_friday_hot_market_low_breadth_filtered(
                hot_market_loss[0],
                0.386549,
                1.216463,
                trade_weekday=4,
            )
        )
        self.assertFalse(
            is_daytrade_catchup_rs_friday_hot_market_low_breadth_filtered(
                dict(hot_market_loss[0], score=11.9),
                0.386549,
                1.216463,
                trade_weekday=4,
            )
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                catchup,
                breadth_val=0.54,
                market_ratio=1.04,
                trade_weekday=4,
                max_count=1,
            ),
            [],
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                hot_market_loss,
                breadth_val=0.386549,
                market_ratio=1.216463,
                trade_weekday=4,
                max_count=1,
            ),
            [],
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                catchup,
                breadth_val=0.54,
                market_ratio=1.16,
                trade_weekday=4,
                max_count=1,
            )[0]["code"],
            "6101",
        )
    def test_daytrade_candidate_selection_filters_wednesday_negative_trend_catchup_gapdown(self):
        catchup = [
            {
                "code": "5838",
                "score": 8.0,
                "setup_type": "catchup_gapdown",
                "gap_pct": -0.015,
                "open_vs_sma_atr": -0.986,
            },
            {
                "code": "4506",
                "score": 7.2,
                "setup_type": "catchup_gapdown",
                "gap_pct": -0.015,
                "open_vs_sma_atr": 0.5,
            },
        ]
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                catchup,
                breadth_val=0.42,
                trade_weekday=2,
                max_count=1,
            )[0]["code"],
            "4506",
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                [catchup[0]],
                breadth_val=0.42,
                trade_weekday=2,
                max_count=1,
            ),
            [],
        )
    def test_daytrade_candidate_selection_filters_hot_market_fallback(self):
        fallback = [
            {"code": "9509", "score": 18.0, "setup_type": "fallback", "gap_pct": 0.004},
            {"code": "2501", "score": 9.6, "setup_type": "catchup_gapdown", "gap_pct": -0.012},
        ]
        self.assertTrue(
            is_daytrade_fallback_hot_market_filtered(
                fallback[0],
                0.50,
                1.02,
            )
        )
        self.assertFalse(
            is_daytrade_fallback_hot_market_filtered(
                fallback[0],
                0.49,
                1.02,
            )
        )
        selected = select_daytrade_candidates(
            [],
            [],
            fallback,
            [],
            breadth_val=0.50,
            market_ratio=1.02,
            trade_weekday=0,
            max_count=1,
        )
        self.assertEqual(selected[0]["setup_type"], "catchup_gapdown")
    def test_daytrade_candidate_selection_filters_fallback_low_breadth_hot_market_mid_open(self):
        loss_candidate = {
            "code": "4047",
            "score": 17.197135,
            "setup_type": "fallback",
            "open_vs_sma_atr": 0.631191,
        }
        survivor_candidate = {
            "code": "5208",
            "score": 3.182786,
            "setup_type": "fallback",
            "open_vs_sma_atr": -2.452149,
        }
        self.assertTrue(
            is_daytrade_fallback_low_breadth_hot_market_mid_open_filtered(
                loss_candidate,
                0.406662,
                1.33687,
            )
        )
        self.assertFalse(
            is_daytrade_fallback_low_breadth_hot_market_mid_open_filtered(
                survivor_candidate,
                0.406662,
                1.33687,
            )
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [loss_candidate, survivor_candidate],
                [],
                breadth_val=0.406662,
                market_ratio=1.33687,
                trade_weekday=0,
                max_count=1,
            )[0]["code"],
            "5208",
        )

    def test_daytrade_candidate_selection_filters_fallback_low_breadth_hot_market_high_open(self):
        loss_candidate = {
            "code": "3480",
            "score": 6.625283,
            "setup_type": "fallback",
            "open_vs_sma_atr": 4.690021,
        }
        survivor_candidate = {
            "code": "6480",
            "score": 12.678824,
            "setup_type": "fallback",
            "open_vs_sma_atr": 4.392505,
        }
        self.assertTrue(
            is_daytrade_fallback_low_breadth_hot_market_high_open_filtered(
                loss_candidate,
                0.405405,
                1.282682,
            )
        )
        self.assertFalse(
            is_daytrade_fallback_low_breadth_hot_market_high_open_filtered(
                survivor_candidate,
                0.405405,
                1.282682,
            )
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [loss_candidate, survivor_candidate],
                [],
                breadth_val=0.405405,
                market_ratio=1.282682,
                trade_weekday=4,
                max_count=1,
            )[0]["code"],
            "6480",
        )

    def test_daytrade_candidate_selection_filters_fallback_low_breadth_strong_prev_return(self):
        loss_candidate = {
            "code": "7383",
            "score": 8.868914,
            "setup_type": "fallback",
            "prev_return": 0.058824,
        }
        survivor_candidate = {
            "code": "6406",
            "score": 6.1,
            "setup_type": "fallback",
            "prev_return": 0.01,
        }
        self.assertTrue(
            is_daytrade_fallback_low_breadth_strong_prev_return_filtered(
                loss_candidate,
                0.418605,
                trade_weekday=0,
            )
        )
        self.assertFalse(
            is_daytrade_fallback_low_breadth_strong_prev_return_filtered(
                survivor_candidate,
                0.418605,
                trade_weekday=0,
            )
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [loss_candidate, survivor_candidate],
                breadth_val=0.418605,
                trade_weekday=0,
                max_count=1,
            )[0]["code"],
            "6406",
        )
    def test_daytrade_candidate_selection_filters_friday_countertrend_setups(self):
        strong_oversold = [{"code": "1579", "score": 11.0, "setup_type": "strong_oversold"}]
        inverse = [
            {"code": "1459", "score": 20.0, "setup_type": "inverse_pullback"},
            {"code": "1368", "score": 4.0, "setup_type": "inverse"},
        ]
        catchup = [{"code": "2500", "score": 7.0, "setup_type": "catchup_rs"}]
        self.assertEqual(
            select_daytrade_candidates(
                [],
                strong_oversold,
                [],
                catchup,
                inverse,
                trade_weekday=4,
                max_count=1,
            )[0]["code"],
            "2500",
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                strong_oversold,
                [],
                [],
                inverse,
                trade_weekday=4,
                max_count=1,
            )[0]["code"],
            "1368",
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                strong_oversold,
                [],
                [],
                [{"code": "1459", "score": 20.0, "setup_type": "inverse_pullback"}],
                trade_weekday=4,
            ),
            [],
        )
    def test_daytrade_candidate_selection_prefers_moderate_tuesday_low_breadth_catchup_rs(self):
        catchup = [
            {"code": "2586", "score": 25.0, "setup_type": "catchup_rs", "gap_pct": 0.009},
            {"code": "8136", "score": 9.6, "setup_type": "catchup_rs", "gap_pct": 0.003},
            {"code": "6516", "score": 6.1, "setup_type": "catchup_rs", "gap_pct": 0.000},
        ]
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                catchup,
                breadth_val=0.30,
                trade_weekday=1,
                max_count=1,
            )[0]["code"],
            "8136",
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                catchup,
                breadth_val=0.30,
                trade_weekday=2,
                max_count=1,
            ),
            [],
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                catchup,
                breadth_val=0.40,
                trade_weekday=1,
                max_count=1,
            )[0]["code"],
            "2586",
        )
    def test_daytrade_candidate_selection_filters_tuesday_low_breadth_weak_market_catchup_rs(self):
        loss_candidate = {
            "code": "6779",
            "score": 12.068123996588456,
            "setup_type": "catchup_rs",
            "gap_pct": 0.011060507482107962,
            "open_vs_sma_atr": 0.9896907216494846,
        }
        survivor_candidate = {
            "code": "3038",
            "score": 8.68082232361268,
            "setup_type": "catchup_rs",
            "gap_pct": 0.00603486812695575,
            "open_vs_sma_atr": 2.119266055045872,
        }
        self.assertTrue(
            is_daytrade_catchup_rs_tuesday_low_breadth_weak_market_filtered(
                loss_candidate,
                0.41734758013827783,
                0.962000537094882,
                trade_weekday=1,
            )
        )
        self.assertFalse(
            is_daytrade_catchup_rs_tuesday_low_breadth_weak_market_filtered(
                survivor_candidate,
                0.31615336266499056,
                0.9672854813528141,
                trade_weekday=1,
            )
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                [loss_candidate, survivor_candidate],
                breadth_val=0.41734758013827783,
                market_ratio=0.962000537094882,
                trade_weekday=1,
                max_count=1,
            )[0]["code"],
            "3038",
        )
    def test_daytrade_candidate_selection_filters_tuesday_low_breadth_moderate_market_catchup_rs(self):
        lower_score_loss_candidate = {
            "code": "6857",
            "score": 6.751721,
            "setup_type": "catchup_rs",
            "gap_pct": 0.005501,
            "open_vs_sma_atr": 3.143705,
        }
        loss_candidate = {
            "code": "3064",
            "score": 8.889436,
            "setup_type": "catchup_rs",
            "gap_pct": 0.015928,
            "open_vs_sma_atr": 0.635367,
        }
        survivor_candidate = {
            "code": "7383",
            "score": 12.885431,
            "setup_type": "catchup_rs",
            "gap_pct": 0.017699,
            "open_vs_sma_atr": 0.85426,
        }
        self.assertTrue(
            is_daytrade_catchup_rs_tuesday_low_breadth_moderate_market_filtered(
                lower_score_loss_candidate,
                0.409805,
                1.020335,
                trade_weekday=1,
            )
        )
        self.assertTrue(
            is_daytrade_catchup_rs_tuesday_low_breadth_moderate_market_filtered(
                loss_candidate,
                0.409805,
                1.020335,
                trade_weekday=1,
            )
        )
        self.assertFalse(
            is_daytrade_catchup_rs_tuesday_low_breadth_moderate_market_filtered(
                survivor_candidate,
                0.409177,
                1.013924,
                trade_weekday=1,
            )
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                [lower_score_loss_candidate, loss_candidate, survivor_candidate],
                breadth_val=0.409805,
                market_ratio=1.020335,
                trade_weekday=1,
                max_count=1,
            )[0]["code"],
            "7383",
        )
    def test_daytrade_candidate_selection_filters_tuesday_low_breadth_high_market_stretched_open_catchup_rs(self):
        first_loss_candidate = {
            "code": "6779",
            "score": 18.846391,
            "setup_type": "catchup_rs",
            "gap_pct": 0.021349,
            "open_vs_sma_atr": 1.893434,
        }
        second_loss_candidate = {
            "code": "3445",
            "score": 14.749416,
            "setup_type": "catchup_rs",
            "gap_pct": 0.010101,
            "open_vs_sma_atr": 1.610948,
        }
        third_loss_candidate = {
            "code": "6752",
            "score": 11.457673,
            "setup_type": "catchup_rs",
            "gap_pct": 0.015928,
            "open_vs_sma_atr": 2.031885,
        }
        survivor_candidate = {
            "code": "6480",
            "score": 18.903164,
            "setup_type": "catchup_rs",
            "gap_pct": 0.011061,
            "open_vs_sma_atr": -0.277300,
        }
        self.assertTrue(
            is_daytrade_catchup_rs_tuesday_low_breadth_high_market_stretched_open_filtered(
                first_loss_candidate,
                0.407291,
                1.220130,
                trade_weekday=1,
            )
        )
        self.assertTrue(
            is_daytrade_catchup_rs_tuesday_low_breadth_high_market_stretched_open_filtered(
                second_loss_candidate,
                0.410434,
                1.285558,
                trade_weekday=1,
            )
        )
        self.assertTrue(
            is_daytrade_catchup_rs_tuesday_low_breadth_high_market_stretched_open_filtered(
                third_loss_candidate,
                0.358265,
                1.230841,
                trade_weekday=1,
            )
        )
        self.assertFalse(
            is_daytrade_catchup_rs_tuesday_low_breadth_high_market_stretched_open_filtered(
                survivor_candidate,
                0.422376,
                1.316930,
                trade_weekday=1,
            )
        )
        self.assertEqual(
            select_daytrade_candidates(
                [],
                [],
                [],
                [first_loss_candidate, second_loss_candidate, third_loss_candidate, survivor_candidate],
                breadth_val=0.407291,
                market_ratio=1.220130,
                trade_weekday=1,
                max_count=1,
            )[0]["code"],
            "6480",
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
    def test_daytrade_primary_residual_weekday_pockets_no_trade(self):
        # Monday residual pocket: low-breadth, low-score, modest-gap continuation.
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.581395,
                gap_pct=0.007034,
                market_ratio=1.012145,
                open_vs_sma_atr=3.307479,
                primary_score=6.521778,
                trade_weekday=0,
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.66,
                gap_pct=0.007034,
                market_ratio=1.06,
                open_vs_sma_atr=1.5,
                primary_score=6.521778,
                trade_weekday=0,
            ),
            0.0,
        )
        # Monday residual pocket: mid-breadth, low-score, low-gap hot-market.
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.720930,
                gap_pct=0.0,
                market_ratio=1.098173,
                open_vs_sma_atr=2.894536,
                primary_score=5.420800,
                trade_weekday=0,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.651163,
                gap_pct=-0.001919,
                market_ratio=1.092293,
                open_vs_sma_atr=1.303506,
                primary_score=4.454268,
                trade_weekday=0,
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.82,
                gap_pct=0.007389,
                market_ratio=1.12,
                open_vs_sma_atr=1.5,
                primary_score=8.2,
                trade_weekday=0,
            ),
            0.0,
        )
        # Monday high-rs pocket: same low-score mid-breadth regime stayed loss-only in train.
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.720930,
                gap_pct=0.009554,
                market_ratio=1.098173,
                open_vs_sma_atr=0.437151,
                primary_score=4.316883,
                rs_alpha=29.021749,
                trade_weekday=0,
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.658077,
                gap_pct=0.007952,
                market_ratio=1.053443,
                open_vs_sma_atr=0.491296,
                primary_score=3.953431,
                rs_alpha=24.968944,
                trade_weekday=0,
            ),
            0.0,
        )
        # Monday mid-high breadth / hot-market / mid-gap pocket lost when the
        # open stayed weak, but the higher-open slice survived.
        monday_mid_high_hot_market_loss_candidates = [
            {
                "breadth_val": 0.682590,
                "gap_pct": 0.005754,
                "market_ratio": 1.128167,
                "open_vs_sma_atr": 0.660131,
                "primary_score": 5.722336,
                "rs_alpha": 34.833204,
                "trade_weekday": 0,
            },
            {
                "breadth_val": 0.677561,
                "gap_pct": 0.007384,
                "market_ratio": 1.139788,
                "open_vs_sma_atr": 0.536364,
                "primary_score": 6.810162,
                "rs_alpha": 20.764331,
                "trade_weekday": 0,
            },
        ]
        monday_mid_high_hot_market_survivor_candidates = [
            {
                "breadth_val": 0.745443,
                "gap_pct": 0.006799,
                "market_ratio": 1.105531,
                "open_vs_sma_atr": 2.262165,
                "primary_score": 3.988394,
                "rs_alpha": 35.275081,
                "trade_weekday": 0,
            },
            {
                "breadth_val": 0.742300,
                "gap_pct": 0.007185,
                "market_ratio": 1.128691,
                "open_vs_sma_atr": 2.209155,
                "primary_score": 7.612355,
                "rs_alpha": 33.829210,
                "trade_weekday": 0,
            },
        ]
        for candidate in monday_mid_high_hot_market_loss_candidates:
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        for candidate in monday_mid_high_hot_market_survivor_candidates:
            self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        # Tuesday residual pocket: slightly hotter mid-breadth / low-score
        # continuation stayed loss-only even after the quarter-size cap.
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.700817,
                gap_pct=0.007389,
                market_ratio=1.166610,
                open_vs_sma_atr=1.5,
                primary_score=5.501665,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.82,
                gap_pct=0.007389,
                market_ratio=1.12,
                open_vs_sma_atr=1.5,
                primary_score=8.2,
                rs_alpha=40.0,
                trade_weekday=1,
            ),
            0.0,
        )
        # Tuesday high-breadth / hot-market / very-low-score probe tail.
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.754243,
                gap_pct=0.002780,
                market_ratio=1.259412,
                open_vs_sma_atr=0.848115,
                primary_score=3.255980,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.751100,
                gap_pct=0.002824,
                market_ratio=1.257739,
                open_vs_sma_atr=2.320958,
                primary_score=3.060805,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.744186,
                gap_pct=-0.003501,
                market_ratio=1.261023,
                open_vs_sma_atr=1.537265,
                primary_score=6.761726,
                trade_weekday=1,
            ),
            0.0,
        )
        # Friday residual pocket: mid-breadth / low-score / small-gap
        # continuation was loss-only in train and never showed up in holdout.
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.712131,
                gap_pct=0.007204,
                market_ratio=1.040149,
                open_vs_sma_atr=1.5,
                primary_score=8.270753,
                trade_weekday=4,
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.712131,
                gap_pct=0.004204,
                market_ratio=1.06,
                open_vs_sma_atr=1.5,
                primary_score=8.270753,
                prev_return=0.01,
                trade_weekday=4,
            ),
            0.0,
        )
    def test_daytrade_primary_monday_tuesday_thursday_near_neutral_market_low_score_small_gap_cap(self):
        monday_loss_candidate = {
            "breadth_val": 0.581395,
            "gap_pct": 0.003767,
            "market_ratio": 1.012145,
            "open_vs_sma_atr": 1.5964,
            "primary_score": 5.426526,
            "trade_weekday": 0,
        }
        tuesday_loss_candidate = {
            "breadth_val": 0.432432,
            "gap_pct": 0.002694,
            "market_ratio": 1.027932,
            "open_vs_sma_atr": 1.021063,
            "primary_score": 4.502359,
            "trade_weekday": 1,
        }
        thursday_loss_candidate = {
            "breadth_val": 0.694532,
            "gap_pct": 0.0,
            "market_ratio": 1.035647,
            "open_vs_sma_atr": 1.387443,
            "primary_score": 4.444887,
            "trade_weekday": 3,
        }
        friday_survivor = {
            "breadth_val": 0.562539,
            "gap_pct": 0.0,
            "market_ratio": 1.000665,
            "open_vs_sma_atr": 3.06182,
            "primary_score": 5.025265,
            "trade_weekday": 4,
        }
        for candidate in (monday_loss_candidate, tuesday_loss_candidate, thursday_loss_candidate):
            self.assertAlmostEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.03)
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**friday_survivor), 0.0)

    def test_daytrade_primary_train_loss_pockets_no_trade(self):
        high_gap_loss_candidate = {
            "breadth_val": 0.767442,
            "gap_pct": 0.02583,
            "market_ratio": 1.082356,
            "open_vs_sma_atr": 1.557081,
            "primary_score": 9.596041,
            "rs_alpha": 27.619496,
            "trade_weekday": 3,
        }
        high_gap_second_loss_candidate = {
            "breadth_val": 0.727844,
            "gap_pct": 0.025152,
            "market_ratio": 1.093094,
            "open_vs_sma_atr": 2.503968,
            "primary_score": 6.616306,
            "rs_alpha": 5.665848,
            "trade_weekday": 2,
        }
        high_gap_survivor_candidate = {
            "breadth_val": 0.717788,
            "gap_pct": 0.016058,
            "market_ratio": 1.081314,
            "open_vs_sma_atr": 1.570642,
            "primary_score": 7.029637,
            "rs_alpha": 22.321429,
            "trade_weekday": 0,
        }
        for candidate in (high_gap_loss_candidate, high_gap_second_loss_candidate):
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**high_gap_survivor_candidate),
            0.0,
        )
        thursday_low_gap_loss_candidate = {
            "breadth_val": 0.65242,
            "gap_pct": -0.001449,
            "market_ratio": 1.168685,
            "open_vs_sma_atr": 2.270175,
            "primary_score": 4.723216,
            "rs_alpha": 28.109915,
            "trade_weekday": 3,
        }
        thursday_low_gap_second_loss_candidate = {
            "breadth_val": 0.65682,
            "gap_pct": 0.006478,
            "market_ratio": 1.154693,
            "open_vs_sma_atr": 1.171105,
            "primary_score": 3.966279,
            "rs_alpha": 36.553432,
            "trade_weekday": 3,
        }
        thursday_low_gap_survivor_candidate = {
            "breadth_val": 0.641106,
            "gap_pct": 0.003202,
            "market_ratio": 1.160149,
            "open_vs_sma_atr": 0.211604,
            "primary_score": 4.160656,
            "rs_alpha": 45.046440,
            "trade_weekday": 0,
        }
        for candidate in (thursday_low_gap_loss_candidate, thursday_low_gap_second_loss_candidate):
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**thursday_low_gap_survivor_candidate),
            0.0,
        )
        low_breadth_loss_candidate = {
            "breadth_val": 0.588938,
            "gap_pct": 0.000652,
            "market_ratio": 1.13107,
            "open_vs_sma_atr": -0.530585,
            "primary_score": 13.347665,
            "rs_alpha": 96.163683,
            "trade_weekday": 2,
        }
        low_breadth_second_loss_candidate = {
            "breadth_val": 0.582024,
            "gap_pct": 0.015075,
            "market_ratio": 1.215438,
            "open_vs_sma_atr": 1.262685,
            "primary_score": 8.328645,
            "rs_alpha": 56.282723,
            "trade_weekday": 2,
        }
        low_breadth_survivor_candidate = {
            "breadth_val": 0.650534,
            "gap_pct": -0.000454,
            "market_ratio": 1.167908,
            "open_vs_sma_atr": 2.498551,
            "primary_score": 4.880015,
            "rs_alpha": 47.015672,
            "trade_weekday": 2,
        }
        for candidate in (low_breadth_loss_candidate, low_breadth_second_loss_candidate):
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**low_breadth_survivor_candidate),
            0.0,
        )
    def test_daytrade_primary_low_breadth_weak_market_score6_8_low_prev_return_cap(self):
        positive_gap_loss_candidate = {
            "breadth_val": 0.494657,
            "gap_pct": 0.002374,
            "market_ratio": 1.015792,
            "open_vs_sma_atr": 2.309172,
            "primary_score": 6.179385,
            "prev_return": 0.042062,
            "trade_weekday": 2,
        }
        zero_gap_loss_candidate = {
            "breadth_val": 0.499686,
            "gap_pct": 0.0,
            "market_ratio": 1.017694,
            "open_vs_sma_atr": 1.391418,
            "primary_score": 6.176655,
            "prev_return": 0.013919,
            "trade_weekday": 1,
        }
        survivor_candidate = {
            "breadth_val": 0.512256,
            "gap_pct": 0.015928,
            "market_ratio": 1.013408,
            "open_vs_sma_atr": -0.689298,
            "primary_score": 6.552053,
            "prev_return": 0.047340,
            "trade_weekday": 2,
        }
        for candidate in (positive_gap_loss_candidate, zero_gap_loss_candidate):
            self.assertAlmostEqual(
                resolve_daytrade_primary_equity_notional_pct(**candidate),
                DAYTRADE_PRIMARY_LOW_BREADTH_WEAK_MARKET_SCORE6_8_POS_GAP_LOW_PREV_RETURN_EQUITY_NOTIONAL_PCT,
            )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**survivor_candidate),
            DAYTRADE_PRIMARY_LOW_BREADTH_WEAK_MARKET_SCORE6_8_POS_GAP_LOW_PREV_RETURN_EQUITY_NOTIONAL_PCT,
        )
    def test_daytrade_primary_tuesday_low_breadth_weak_market_low_score_low_prev_return_no_trade(self):
        loss_candidates = [
            {
                "breadth_val": 0.499686,
                "gap_pct": 0.003814,
                "market_ratio": 1.017694,
                "open_vs_sma_atr": 1.113758,
                "primary_score": 3.345381,
                "prev_return": 0.01989,
                "trade_weekday": 1,
            },
            {
                "breadth_val": 0.522313,
                "gap_pct": 0.002185,
                "market_ratio": 1.022140,
                "open_vs_sma_atr": 0.542384,
                "primary_score": 3.471140,
                "prev_return": 0.01369,
                "trade_weekday": 1,
            },
        ]
        survivor_candidates = [
            {
                "breadth_val": 0.499686,
                "gap_pct": 0.003814,
                "market_ratio": 1.017694,
                "open_vs_sma_atr": 0.983333,
                "primary_score": 3.345381,
                "prev_return": 0.031122,
                "trade_weekday": 1,
            },
            {
                "breadth_val": 0.522313,
                "gap_pct": 0.002185,
                "market_ratio": 1.022140,
                "open_vs_sma_atr": 1.203579,
                "primary_score": 3.471140,
                "prev_return": 0.029683,
                "trade_weekday": 1,
            },
        ]
        for candidate in loss_candidates:
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        for candidate in survivor_candidates:
            self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)

    def test_daytrade_primary_tuesday_mid_breadth_near_neutral_market_low_score_non_negative_open_no_trade(self):
        loss_candidates = [
            {
                "breadth_val": 0.5248271527341295,
                "gap_pct": 0.0020408163265306367,
                "market_ratio": 1.0155166674676877,
                "open_vs_sma_atr": 0.06498194945848416,
                "primary_score": 7.367936450942483,
                "trade_weekday": 1,
            },
            {
                "breadth_val": 0.5103708359522313,
                "gap_pct": 0.001765225066195919,
                "market_ratio": 1.027608883057041,
                "open_vs_sma_atr": 0.02154848408920161,
                "primary_score": 7.0059154718961105,
                "trade_weekday": 1,
            },
            {
                "breadth_val": 0.5864236329352609,
                "gap_pct": 0.008983451536642928,
                "market_ratio": 1.0182647589971272,
                "open_vs_sma_atr": 0.8252873563218386,
                "primary_score": 6.922374396555077,
                "trade_weekday": 1,
            },
        ]
        for candidate in loss_candidates:
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        negative_open_survivor = {
            "breadth_val": 0.6329352608422376,
            "gap_pct": 0.0,
            "market_ratio": 1.0283646727677918,
            "open_vs_sma_atr": -0.703909590714725,
            "primary_score": 6.046059610192571,
            "trade_weekday": 1,
        }
        low_score_survivor = {
            "breadth_val": 0.524198617221873,
            "gap_pct": 0.0033333333333334103,
            "market_ratio": 1.0140902680006634,
            "open_vs_sma_atr": 2.168880455407973,
            "primary_score": 4.271763589903312,
            "trade_weekday": 1,
        }
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**negative_open_survivor), 0.0)
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**low_score_survivor), 0.0)
    def test_daytrade_primary_hot_market_low_score_small_gap_mid_rsi_no_trade(self):
        loss_candidates = [
            {
                "breadth_val": 0.7460723981900452,
                "gap_pct": 0.0,
                "market_ratio": 1.1413172267331078,
                "open_vs_sma_atr": 3.5205156136525046,
                "prev_rsi2": 59.380863039399624,
                "primary_score": 5.743145739698769,
                "trade_weekday": 1,
            },
            {
                "breadth_val": 0.666247642991829,
                "gap_pct": 0.0011703280680436608,
                "market_ratio": 1.1252643685748598,
                "open_vs_sma_atr": 2.2642569256000004,
                "prev_rsi2": 51.21951219512195,
                "primary_score": 3.73045586106555,
                "trade_weekday": 2,
            },
            {
                "breadth_val": 0.548083466483675,
                "gap_pct": 0.0015289611894871345,
                "market_ratio": 1.1187422969187672,
                "open_vs_sma_atr": -1.406821548821549,
                "prev_rsi2": 57.14285714285714,
                "primary_score": 3.4958655483784035,
                "trade_weekday": 3,
            },
            {
                "breadth_val": 0.5593971240883804,
                "gap_pct": 0.0,
                "market_ratio": 1.1308245415521775,
                "open_vs_sma_atr": 0.5150891632373114,
                "prev_rsi2": 59.12806539509537,
                "primary_score": 5.272334152334469,
                "trade_weekday": 1,
            },
        ]
        for candidate in loss_candidates:
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        score_survivor = {
            "breadth_val": 0.5103708359522313,
            "gap_pct": 0.003619303002168279,
            "market_ratio": 1.1058899365750526,
            "open_vs_sma_atr": -0.527891156462585,
            "prev_rsi2": 57.00737588652482,
            "primary_score": 7.104473286245175,
            "trade_weekday": 0,
        }
        gap_survivor = {
            "breadth_val": 0.5612816608000001,
            "gap_pct": 0.007474576271186552,
            "market_ratio": 1.1346886157096796,
            "open_vs_sma_atr": 0.4574594267496105,
            "prev_rsi2": 55.99999999999999,
            "primary_score": 4.456129447452521,
            "trade_weekday": 1,
        }
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**score_survivor), 0.0)
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**gap_survivor), 0.0)
    def test_daytrade_primary_near_neutral_market_mid_score_mid_open_mid_rsi_no_trade(self):
        loss_candidates = [
            {
                "breadth_val": 0.5487124660164589,
                "gap_pct": 0.004645760742870291,
                "market_ratio": 1.037798149056255,
                "open_vs_sma_atr": 1.7551322335966776,
                "prev_rsi2": 61.857142857142854,
                "primary_score": 6.201150455991111,
                "trade_weekday": 0,
            },
            {
                "breadth_val": 0.426146694214876,
                "gap_pct": -0.003588726512542683,
                "market_ratio": 1.031564462925466,
                "open_vs_sma_atr": 1.9393280632411068,
                "prev_rsi2": 65.12455516014235,
                "primary_score": 6.695821724303482,
                "trade_weekday": 1,
            },
            {
                "breadth_val": 0.4362040195378542,
                "gap_pct": 0.0026167810680740424,
                "market_ratio": 1.0035401743998044,
                "open_vs_sma_atr": 1.4745804261090824,
                "prev_rsi2": 69.55671447087606,
                "primary_score": 6.713706104394246,
                "trade_weekday": 0,
            },
            {
                "breadth_val": 0.6945318578214356,
                "gap_pct": 0.01548821548821549,
                "market_ratio": 1.035647279581417,
                "open_vs_sma_atr": 1.560925846116169,
                "prev_rsi2": 70.0,
                "primary_score": 7.855242887217898,
                "trade_weekday": 3,
            },
        ]
        for candidate in loss_candidates:
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        market_survivor = {
            "breadth_val": 0.6329352608422376,
            "gap_pct": 0.0,
            "market_ratio": 1.1286910262793503,
            "open_vs_sma_atr": 2.2091552257207706,
            "prev_rsi2": 59.0448627946101,
            "primary_score": 7.612354626691787,
            "trade_weekday": 0,
        }
        rsi_survivor = {
            "breadth_val": 0.6731621937521773,
            "gap_pct": 0.008000000000000007,
            "market_ratio": 1.1336060486080875,
            "open_vs_sma_atr": 1.8662213564213566,
            "prev_rsi2": 54.3859649122807,
            "primary_score": 3.237900882966744,
            "trade_weekday": 1,
        }
        high_score_survivor = {
            "breadth_val": 0.5191703894701276,
            "gap_pct": -0.004651162790697701,
            "market_ratio": 1.1129261941191365,
            "open_vs_sma_atr": 1.0365893641025641,
            "prev_rsi2": 60.0,
            "primary_score": 10.390264716694042,
            "trade_weekday": 4,
        }
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**market_survivor), 0.0)
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**rsi_survivor), 0.0)
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**high_score_survivor), 0.0)
    def test_daytrade_primary_tuesday_and_friday_low_score_negative_gap_exact_pockets_no_trade(self):
        low_score_high_open_loss_candidates = [
            {
                "breadth_val": 0.676933,
                "gap_pct": 0.0,
                "market_ratio": 1.007958,
                "open_vs_sma_atr": 4.322581,
                "primary_score": 3.132217,
                "trade_weekday": 0,
            },
            {
                "breadth_val": 0.700817,
                "gap_pct": -0.003523,
                "market_ratio": 1.166610,
                "open_vs_sma_atr": 3.061186,
                "primary_score": 3.190866,
                "trade_weekday": 1,
            },
            {
                "breadth_val": 0.761785,
                "gap_pct": 0.008696,
                "market_ratio": 1.105218,
                "open_vs_sma_atr": 3.374869,
                "primary_score": 3.709625,
                "trade_weekday": 4,
            },
        ]
        for candidate in low_score_high_open_loss_candidates:
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        low_score_high_open_survivor = dict(low_score_high_open_loss_candidates[0], open_vs_sma_atr=2.99)
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**low_score_high_open_survivor), 0.0)
        near_neutral_high_breadth_loss_candidates = [
            {
                "breadth_val": 0.781270,
                "gap_pct": 0.003824,
                "market_ratio": 1.040435,
                "open_vs_sma_atr": 2.675362,
                "primary_score": 4.293877,
                "trade_weekday": 3,
            },
            {
                "breadth_val": 0.764928,
                "gap_pct": 0.022287,
                "market_ratio": 1.031636,
                "open_vs_sma_atr": 1.321595,
                "primary_score": 4.553403,
                "trade_weekday": 4,
            },
            {
                "breadth_val": 0.842238,
                "gap_pct": -0.001908,
                "market_ratio": 1.030493,
                "open_vs_sma_atr": 9.023499,
                "primary_score": 4.678080,
                "trade_weekday": 0,
            },
        ]
        for candidate in near_neutral_high_breadth_loss_candidates:
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        near_neutral_high_breadth_survivor = dict(near_neutral_high_breadth_loss_candidates[0], open_vs_sma_atr=0.99)
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**near_neutral_high_breadth_survivor), 0.0)
        tuesday_loss_candidates = [
            {
                "breadth_val": 0.5593971240883804,
                "gap_pct": -0.0006478342749553985,
                "market_ratio": 1.1308245415521775,
                "open_vs_sma_atr": 1.3619889041394325,
                "primary_score": 3.939877932198034,
                "trade_weekday": 1,
            },
            {
                "breadth_val": 0.4996862780390022,
                "gap_pct": -0.004704887687035955,
                "market_ratio": 1.0176940134760165,
                "open_vs_sma_atr": 1.7290979955456576,
                "primary_score": 3.5176417043111844,
                "trade_weekday": 1,
            },
            {
                "breadth_val": 0.7190454339622642,
                "gap_pct": -0.002798192055177447,
                "market_ratio": 1.1864721139273931,
                "open_vs_sma_atr": 1.8191809917127072,
                "primary_score": 4.327418560887294,
                "trade_weekday": 1,
            },
        ]
        for candidate in tuesday_loss_candidates:
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        tuesday_survivor = dict(tuesday_loss_candidates[0], gap_pct=0.001)
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**tuesday_survivor), 0.0)
        friday_loss_candidates = [
            {
                "breadth_val": 0.6184794358057516,
                "gap_pct": -0.004351014040561382,
                "market_ratio": 1.015544041450776,
                "open_vs_sma_atr": 3.21505376344086,
                "primary_score": 5.821773797138964,
                "trade_weekday": 4,
            },
            {
                "breadth_val": 0.5876805775597951,
                "gap_pct": -0.0016812905360809143,
                "market_ratio": 1.0271938775510204,
                "open_vs_sma_atr": 2.8829159663865544,
                "primary_score": 5.036592960678715,
                "trade_weekday": 4,
            },
            {
                "breadth_val": 0.7121311679055794,
                "gap_pct": -0.003699685739321917,
                "market_ratio": 1.0401492510401492,
                "open_vs_sma_atr": -0.17441340782122905,
                "primary_score": 4.760326486263173,
                "trade_weekday": 4,
            },
        ]
        for candidate in friday_loss_candidates:
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        friday_survivor = {
            "breadth_val": 0.7404146730462512,
            "gap_pct": 0.015427599611273208,
            "market_ratio": 1.0455377111946425,
            "open_vs_sma_atr": 1.2232142857142858,
            "primary_score": 4.349498231907086,
            "trade_weekday": 4,
        }
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**friday_survivor), 0.0)
    def test_daytrade_primary_train_only_exact_primary_pockets_no_trade(self):
        low_breadth_loss_candidates = [
            {
                "breadth_val": 0.522313,
                "gap_pct": 0.002411,
                "market_ratio": 1.022140,
                "open_vs_sma_atr": 0.789541,
                "primary_score": 4.121639,
                "trade_weekday": 1,
            },
            {
                "breadth_val": 0.480830,
                "gap_pct": 0.004121,
                "market_ratio": 1.009151,
                "open_vs_sma_atr": 0.057692,
                "primary_score": 4.516975,
                "trade_weekday": 0,
            },
            {
                "breadth_val": 0.532998,
                "gap_pct": 0.0,
                "market_ratio": 1.014349,
                "open_vs_sma_atr": 0.739409,
                "primary_score": 4.642462,
                "trade_weekday": 1,
            },
        ]
        for candidate in low_breadth_loss_candidates:
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        low_breadth_survivor = dict(low_breadth_loss_candidates[0], gap_pct=-0.001)
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**low_breadth_survivor), 0.0)
        tuesday_loss_candidates = [
            {
                "breadth_val": 0.604651,
                "gap_pct": -0.004587,
                "market_ratio": 0.951948,
                "open_vs_sma_atr": -0.566586,
                "primary_score": 6.619833,
                "trade_weekday": 1,
            },
            {
                "breadth_val": 0.524827,
                "gap_pct": -0.001037,
                "market_ratio": 1.015517,
                "open_vs_sma_atr": -0.491456,
                "primary_score": 7.326504,
                "trade_weekday": 1,
            },
            {
                "breadth_val": 0.693903,
                "gap_pct": -0.002533,
                "market_ratio": 1.042640,
                "open_vs_sma_atr": -0.508041,
                "primary_score": 6.965364,
                "trade_weekday": 1,
            },
        ]
        for candidate in tuesday_loss_candidates:
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        tuesday_survivor = dict(tuesday_loss_candidates[0], open_vs_sma_atr=0.0)
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**tuesday_survivor), 0.0)
        wednesday_loss_candidates = [
            {
                "breadth_val": 0.746072,
                "gap_pct": 0.0,
                "market_ratio": 1.036026,
                "open_vs_sma_atr": 1.034483,
                "primary_score": 3.863375,
                "trade_weekday": 2,
            },
            {
                "breadth_val": 0.639221,
                "gap_pct": 0.0,
                "market_ratio": 1.048046,
                "open_vs_sma_atr": 1.967332,
                "primary_score": 3.963863,
                "trade_weekday": 2,
            },
            {
                "breadth_val": 0.710245,
                "gap_pct": -0.001911,
                "market_ratio": 1.031208,
                "open_vs_sma_atr": 1.306816,
                "primary_score": 5.795580,
                "trade_weekday": 2,
            },
        ]
        for candidate in wednesday_loss_candidates:
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        wednesday_survivor = dict(wednesday_loss_candidates[0], gap_pct=0.001)
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**wednesday_survivor), 0.0)
    def test_daytrade_primary_additional_train_only_exact_pockets_no_trade(self):
        tuesday_loss_candidates = [
            {
                "breadth_val": 0.494657,
                "gap_pct": 0.025324,
                "market_ratio": 1.114576,
                "open_vs_sma_atr": 1.570297,
                "primary_score": 6.660821,
                "trade_weekday": 1,
            },
            {
                "breadth_val": 0.531113,
                "gap_pct": 0.002451,
                "market_ratio": 1.110695,
                "open_vs_sma_atr": 1.327045,
                "primary_score": 7.211545,
                "trade_weekday": 1,
            },
        ]
        for candidate in tuesday_loss_candidates:
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        tuesday_survivor = dict(tuesday_loss_candidates[0], gap_pct=-0.001)
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**tuesday_survivor), 0.0)
        thursday_loss_candidates = [
            {
                "breadth_val": 0.612194,
                "gap_pct": -0.002395,
                "market_ratio": 1.103996,
                "open_vs_sma_atr": 2.101695,
                "primary_score": 6.760961,
                "trade_weekday": 3,
            },
            {
                "breadth_val": 0.595852,
                "gap_pct": 0.009174,
                "market_ratio": 1.044002,
                "open_vs_sma_atr": 2.362093,
                "primary_score": 6.646276,
                "trade_weekday": 3,
            },
            {
                "breadth_val": 0.604023,
                "gap_pct": 0.007883,
                "market_ratio": 1.018327,
                "open_vs_sma_atr": 2.507829,
                "primary_score": 7.109946,
                "trade_weekday": 3,
            },
        ]
        for candidate in thursday_loss_candidates:
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        thursday_survivor = dict(thursday_loss_candidates[0], open_vs_sma_atr=1.0)
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**thursday_survivor), 0.0)
        friday_hot_market_loss_candidates = [
            {
                "breadth_val": 0.732872,
                "gap_pct": 0.029412,
                "market_ratio": 1.127880,
                "open_vs_sma_atr": 5.272025,
                "primary_score": 7.232793,
                "trade_weekday": 4,
            },
            {
                "breadth_val": 0.689503,
                "gap_pct": 0.008389,
                "market_ratio": 1.126878,
                "open_vs_sma_atr": 5.576157,
                "primary_score": 7.404354,
                "trade_weekday": 4,
            },
            {
                "breadth_val": 0.578253,
                "gap_pct": 0.007265,
                "market_ratio": 1.100773,
                "open_vs_sma_atr": 0.640724,
                "primary_score": 6.918856,
                "trade_weekday": 4,
            },
        ]
        for candidate in friday_hot_market_loss_candidates:
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        friday_hot_market_survivor = dict(friday_hot_market_loss_candidates[0], gap_pct=-0.001)
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**friday_hot_market_survivor), 0.0)
        monday_loss_candidates = [
            {
                "breadth_val": 0.676933,
                "gap_pct": 0.004016,
                "market_ratio": 1.007958,
                "open_vs_sma_atr": -0.252941,
                "primary_score": 3.884382,
                "trade_weekday": 0,
            },
            {
                "breadth_val": 0.473287,
                "gap_pct": -0.003300,
                "market_ratio": 1.001188,
                "open_vs_sma_atr": -1.158575,
                "primary_score": 4.198238,
                "trade_weekday": 0,
            },
            {
                "breadth_val": 0.658705,
                "gap_pct": 0.008736,
                "market_ratio": 0.982683,
                "open_vs_sma_atr": -1.209367,
                "primary_score": 4.019593,
                "trade_weekday": 0,
            },
        ]
        for candidate in monday_loss_candidates:
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        monday_survivor = dict(monday_loss_candidates[0], open_vs_sma_atr=0.0)
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**monday_survivor), 0.0)
    def test_daytrade_primary_wednesday_and_friday_hot_market_negative_gap_loss_pockets_no_trade(self):
        wednesday_loss_candidates = [
            {
                "breadth_val": 0.666247642991829,
                "gap_pct": -0.0034138519629648423,
                "market_ratio": 1.1252643685748598,
                "open_vs_sma_atr": -0.5663525857728564,
                "prev_return": 0.015762097409762088,
                "primary_score": 6.174756572089737,
                "trade_weekday": 2,
            },
            {
                "breadth_val": 0.61659333752357,
                "gap_pct": -0.0017881090746534323,
                "market_ratio": 1.1226853299208146,
                "open_vs_sma_atr": -0.7035633055344979,
                "prev_return": 0.027560863573725225,
                "primary_score": 5.231321250474383,
                "trade_weekday": 2,
            },
            {
                "breadth_val": 0.6033940917661847,
                "gap_pct": -0.003197291705849259,
                "market_ratio": 1.122284972203406,
                "open_vs_sma_atr": 0.08761479275254908,
                "prev_return": 0.023090244371752888,
                "primary_score": 4.9682346926175995,
                "trade_weekday": 2,
            },
        ]
        for candidate in wednesday_loss_candidates:
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        wednesday_survivor_candidate = dict(wednesday_loss_candidates[0], gap_pct=0.001)
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**wednesday_survivor_candidate), 0.0)
        friday_loss_candidate = {
            "breadth_val": 0.6725329981143935,
            "gap_pct": -0.0009661835748792091,
            "market_ratio": 1.1328402680097402,
            "open_vs_sma_atr": -0.3925619834710744,
            "prev_return": 0.015701668302257055,
            "primary_score": 3.585536369324725,
            "trade_weekday": 4,
        }
        self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**friday_loss_candidate), 0.0)
        friday_survivor_candidate = dict(friday_loss_candidate, gap_pct=0.001)
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**friday_survivor_candidate), 0.0)
    def test_daytrade_primary_wednesday_high_open_low_score_tight_gap_no_trade(self):
        loss_candidates = [
            {
                "breadth_val": 0.433690,
                "gap_pct": 0.001744,
                "market_ratio": 1.022109,
                "open_vs_sma_atr": 2.709016,
                "primary_score": 6.654636,
                "trade_weekday": 2,
            },
            {
                "breadth_val": 0.681961,
                "gap_pct": -0.003225,
                "market_ratio": 1.073463,
                "open_vs_sma_atr": 3.710183,
                "primary_score": 4.640105,
                "trade_weekday": 2,
            },
            {
                "breadth_val": 0.721559,
                "gap_pct": 0.002251,
                "market_ratio": 1.024193,
                "open_vs_sma_atr": 3.214961,
                "primary_score": 6.093790,
                "trade_weekday": 2,
            },
            {
                "breadth_val": 0.633564,
                "gap_pct": -0.001765,
                "market_ratio": 1.026311,
                "open_vs_sma_atr": 2.110840,
                "primary_score": 3.228285,
                "trade_weekday": 2,
            },
            {
                "breadth_val": 0.500943,
                "gap_pct": -0.004196,
                "market_ratio": 1.017077,
                "open_vs_sma_atr": 3.038908,
                "primary_score": 5.080973,
                "trade_weekday": 2,
            },
        ]
        for candidate in loss_candidates:
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        survivor_candidate = {
            "breadth_val": 0.727844,
            "gap_pct": 0.001171,
            "market_ratio": 1.093094,
            "open_vs_sma_atr": 2.505499,
            "primary_score": 5.147249,
            "trade_weekday": 2,
        }
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**survivor_candidate), 0.0)
    def test_daytrade_primary_wednesday_low_breadth_weak_market_sub6_positive_gap_no_trade(self):
        loss_candidates = [
            {
                "breadth_val": 0.4663733500942803,
                "gap_pct": 0.015724381625441763,
                "market_ratio": 1.0097985642745393,
                "open_vs_sma_atr": -0.25051845707175296,
                "primary_score": 5.979682260310932,
                "prev_return": 0.04254927242586115,
                "trade_weekday": 2,
            },
            {
                "breadth_val": 0.5009428032683847,
                "gap_pct": 0.0008035355564481872,
                "market_ratio": 1.0170770803934293,
                "open_vs_sma_atr": 0.7794237343317616,
                "primary_score": 5.415410982373237,
                "prev_return": -0.004798080767692836,
                "trade_weekday": 2,
            },
            {
                "breadth_val": 0.4443746298686241,
                "gap_pct": 0.02455692440630138,
                "market_ratio": 1.0025466234023108,
                "open_vs_sma_atr": -2.1053181818181816,
                "primary_score": 3.3777268559501565,
                "prev_return": 0.011857707509881423,
                "trade_weekday": 2,
            },
            {
                "breadth_val": 0.6819610307982401,
                "gap_pct": 0.024060150375939893,
                "market_ratio": 1.0734629251635794,
                "open_vs_sma_atr": -2.434567901234568,
                "primary_score": 5.315853348649405,
                "prev_return": 0.0390625,
                "trade_weekday": 2,
            },
        ]
        for candidate in loss_candidates:
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        survivor_candidate = dict(
            loss_candidates[0],
            market_ratio=1.06,
            open_vs_sma_atr=0.8,
            primary_score=6.1,
        )
        self.assertGreater(resolve_daytrade_primary_equity_notional_pct(**survivor_candidate), 0.0)
    def test_daytrade_primary_residual_hot_market_loss_pockets_no_trade(self):
        monday_thursday_loss_candidate = {
            "breadth_val": 0.877436,
            "gap_pct": 0.007064,
            "market_ratio": 1.154834,
            "open_vs_sma_atr": 1.989703,
            "primary_score": 4.748541,
            "rs_alpha": 32.846715,
            "trade_weekday": 0,
        }
        monday_thursday_second_loss_candidate = {
            "breadth_val": 0.786298,
            "gap_pct": 0.003279,
            "market_ratio": 1.114605,
            "open_vs_sma_atr": 2.210999,
            "primary_score": 4.616065,
            "rs_alpha": 53.451399,
            "trade_weekday": 3,
        }
        monday_thursday_survivor_candidate = {
            "breadth_val": 0.854808,
            "gap_pct": 0.005429,
            "market_ratio": 1.152553,
            "open_vs_sma_atr": 1.520231,
            "primary_score": 6.616835,
            "rs_alpha": 58.247423,
            "trade_weekday": 0,
        }
        friday_loss_candidate = {
            "breadth_val": 0.582024,
            "gap_pct": 0.008595,
            "market_ratio": 1.215438,
            "open_vs_sma_atr": 1.469905,
            "primary_score": 3.194121,
            "rs_alpha": 33.859303,
            "trade_weekday": 4,
        }
        friday_survivor_candidate = {
            "breadth_val": 0.563796,
            "gap_pct": 0.015928,
            "market_ratio": 1.186830,
            "open_vs_sma_atr": 1.407159,
            "primary_score": 4.562845,
            "rs_alpha": 41.677898,
            "trade_weekday": 4,
        }
        wednesday_loss_candidate = {
            "breadth_val": 0.727844,
            "gap_pct": 0.000551,
            "market_ratio": 1.093094,
            "open_vs_sma_atr": 2.717842,
            "primary_score": 6.492279,
            "rs_alpha": 29.478944,
            "trade_weekday": 2,
        }
        for candidate in (
            monday_thursday_loss_candidate,
            monday_thursday_second_loss_candidate,
            friday_loss_candidate,
            wednesday_loss_candidate,
        ):
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**monday_thursday_survivor_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**friday_survivor_candidate),
            0.0,
        )
    def test_daytrade_primary_friday_low_score_near_neutral_market_small_positive_gap_no_trade(self):
        loss_candidate = {
            "breadth_val": 0.680075354258,
            "gap_pct": 0.003119993523,
            "market_ratio": 1.037535853947,
            "open_vs_sma_atr": 1.89760824437,
            "primary_score": 4.63933003046,
            "trade_weekday": 4,
        }
        second_loss_candidate = {
            "breadth_val": 0.732244144913,
            "gap_pct": 0.003790284611,
            "market_ratio": 1.00341622138,
            "open_vs_sma_atr": 1.08367583321,
            "primary_score": 4.64246168225,
            "trade_weekday": 4,
        }
        survivor_candidate = {
            "breadth_val": 0.512256,
            "gap_pct": 0.015928,
            "market_ratio": 1.013408,
            "open_vs_sma_atr": -0.689298,
            "primary_score": 6.552053,
            "prev_return": 0.047340,
            "trade_weekday": 2,
        }
        for candidate in (loss_candidate, second_loss_candidate):
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**survivor_candidate),
            0.0,
        )
    def test_daytrade_primary_tuesday_high_market_mid_breadth_high_open_no_trade(self):
        loss_candidate = {
            "breadth_val": 0.7008170961659334,
            "gap_pct": 0.0101271031168062,
            "market_ratio": 1.2525188679245284,
            "open_vs_sma_atr": 1.9495354435064308,
            "primary_score": 6.547751751585202,
            "trade_weekday": 1,
        }
        second_loss_candidate = {
            "breadth_val": 0.7542428327443726,
            "gap_pct": 0.015928,
            "market_ratio": 1.2594117647058824,
            "open_vs_sma_atr": 1.9794869278346422,
            "primary_score": 6.477606876805,
            "trade_weekday": 1,
        }
        third_loss_candidate = {
            "breadth_val": 0.7441860465116279,
            "gap_pct": -0.0035594237823653,
            "market_ratio": 1.2610232783379028,
            "open_vs_sma_atr": 3.261939060256383,
            "primary_score": 7.834030398097213,
            "trade_weekday": 1,
        }
        survivor_candidate = {
            "breadth_val": 0.706473901,
            "gap_pct": 0.0096531303022769,
            "market_ratio": 1.2040340425719117,
            "open_vs_sma_atr": 1.6843240038567493,
            "primary_score": 6.858091432390938,
            "trade_weekday": 1,
        }
        negative_open_survivor = {
            "breadth_val": 0.7932123873208732,
            "gap_pct": 0.0101907706954327,
            "market_ratio": 1.2357258832642513,
            "open_vs_sma_atr": -1.338813852806067,
            "primary_score": 6.849258166055425,
            "trade_weekday": 1,
        }
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**loss_candidate),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**second_loss_candidate),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**third_loss_candidate),
            0.0,
        )
        fourth_loss_candidate = {
            "breadth_val": 0.7542428327443726,
            "gap_pct": -0.0009399679473381,
            "market_ratio": 1.2594117647058824,
            "open_vs_sma_atr": 1.9941603848014134,
            "primary_score": 5.465566106484,
            "trade_weekday": 1,
        }
        fifth_loss_candidate = {
            "breadth_val": 0.7542428327443726,
            "gap_pct": 0.0046892223294649,
            "market_ratio": 1.2594117647058824,
            "open_vs_sma_atr": 1.4416111223187864,
            "primary_score": 4.073456044004355,
            "trade_weekday": 1,
        }
        sixth_loss_candidate = {
            "breadth_val": 0.7008170961659334,
            "gap_pct": 0.0113894009478585,
            "market_ratio": 1.2525188679245284,
            "open_vs_sma_atr": 0.6218221391650097,
            "primary_score": 4.997580576764944,
            "trade_weekday": 1,
        }
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**fourth_loss_candidate),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**fifth_loss_candidate),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**sixth_loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**survivor_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**negative_open_survivor),
            0.0,
        )
    def test_daytrade_primary_tuesday_high_market_mid_breadth_positive_gap_high_ratio_no_trade(self):
        loss_candidate = {
            "breadth_val": 0.7008170961659334,
            "gap_pct": 0.0104797184380651,
            "market_ratio": 1.2525188679245284,
            "open_vs_sma_atr": 1.0903225806451614,
            "primary_score": 6.265771636279091,
            "trade_weekday": 1,
        }
        low_score_loss_candidate = {
            "breadth_val": 0.7542428327443726,
            "gap_pct": 0.0038012505105168,
            "market_ratio": 1.2594117647058824,
            "open_vs_sma_atr": 0.4732670107334527,
            "primary_score": 3.587628038524018,
            "trade_weekday": 1,
        }
        very_low_score_loss_candidate = {
            "breadth_val": 0.7008170961659334,
            "gap_pct": 0.0060938452163315,
            "market_ratio": 1.2525188679245284,
            "open_vs_sma_atr": 0.5991352686843731,
            "primary_score": 3.9771443893279086,
            "trade_weekday": 1,
        }
        mid_open_loss_candidate = {
            "breadth_val": 0.7008170961659334,
            "gap_pct": 0.0088620157028917,
            "market_ratio": 1.2525188679245284,
            "open_vs_sma_atr": 1.4268633459191842,
            "primary_score": 3.855013409099258,
            "trade_weekday": 1,
        }
        high_open_loss_candidate = {
            "breadth_val": 0.7008170961659334,
            "gap_pct": 0.0078218127159497,
            "market_ratio": 1.2525188679245284,
            "open_vs_sma_atr": 2.244837818453329,
            "primary_score": 3.616286401267922,
            "trade_weekday": 1,
        }
        second_loss_candidate = {
            "breadth_val": 0.7542428327443726,
            "gap_pct": 0.0051739130434783,
            "market_ratio": 1.2594117647058824,
            "open_vs_sma_atr": 0.9504496181046678,
            "primary_score": 4.934510390839158,
            "trade_weekday": 1,
        }
        third_loss_candidate = {
            "breadth_val": 0.7511001823956475,
            "gap_pct": 0.0021670270966142,
            "market_ratio": 1.25773916833735,
            "open_vs_sma_atr": 0.4199520171894169,
            "primary_score": 4.995915227963812,
            "trade_weekday": 1,
        }
        survivor_candidate = {
            "breadth_val": 0.7441860465116279,
            "gap_pct": -0.0035010938844764,
            "market_ratio": 1.2610232783379028,
            "open_vs_sma_atr": 1.5372651837866997,
            "primary_score": 6.76172618283092,
            "trade_weekday": 1,
        }
        low_score_survivor_candidate = {
            "breadth_val": 0.7460723694390719,
            "gap_pct": 0.0011933851887831,
            "market_ratio": 1.2453677645376778,
            "open_vs_sma_atr": 2.217687074829932,
            "primary_score": 3.343086210356489,
            "trade_weekday": 1,
        }
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**loss_candidate),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**low_score_loss_candidate),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**very_low_score_loss_candidate),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**mid_open_loss_candidate),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**high_open_loss_candidate),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**second_loss_candidate),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**third_loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**survivor_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**low_score_survivor_candidate),
            0.0,
        )
    def test_daytrade_primary_monday_weak_market_stretched_open_no_trade(self):
        loss_candidate = {
            "breadth_val": 0.6631054682589566,
            "gap_pct": 0.002408419861353,
            "market_ratio": 1.0356419607817244,
            "open_vs_sma_atr": 2.0400337754194745,
            "primary_score": 6.078410227661177,
            "trade_weekday": 0,
        }
        second_loss_candidate = {
            "breadth_val": 0.7177877385866153,
            "gap_pct": -0.002236133787281,
            "market_ratio": 1.0245223045359312,
            "open_vs_sma_atr": 1.8336234496353858,
            "primary_score": 6.272141593581529,
            "trade_weekday": 0,
        }
        stronger_open_candidate = {
            "breadth_val": 0.6838470110879027,
            "gap_pct": 0.0232108598951173,
            "market_ratio": 0.9990746971815555,
            "open_vs_sma_atr": 2.996447530864198,
            "primary_score": 5.813756802200919,
            "trade_weekday": 0,
        }
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**loss_candidate),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**second_loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**stronger_open_candidate),
            0.0,
        )
    def test_daytrade_primary_monday_tuesday_very_low_breadth_weak_market_high_score_low_open_no_trade(self):
        loss_candidate = {
            "breadth_val": 0.4676304211187932,
            "gap_pct": 0.0019762845849802257,
            "market_ratio": 1.0207537860435345,
            "open_vs_sma_atr": 0.4510204081632658,
            "primary_score": 6.505250491816056,
            "trade_weekday": 0,
        }
        second_loss_candidate = {
            "breadth_val": 0.46511627906976744,
            "gap_pct": -0.004282655246252709,
            "market_ratio": 1.0402092888120766,
            "open_vs_sma_atr": 0.04070556309362279,
            "primary_score": 7.070826327993852,
            "trade_weekday": 0,
        }
        survivor_candidate = {
            "breadth_val": 0.6731624620623398,
            "gap_pct": 0.008000000000000007,
            "market_ratio": 1.133606117910525,
            "open_vs_sma_atr": 1.866221056161243,
            "primary_score": 3.237901045457442,
            "trade_weekday": 1,
        }
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**loss_candidate),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**second_loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**survivor_candidate),
            0.0,
        )
    def test_daytrade_primary_additional_train_loss_pockets_no_trade(self):
        # Tuesday mid-breadth / hot-market / high-score / sub-half-ATR open.
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.6304211187932118,
                gap_pct=0.021324354657688,
                market_ratio=1.2071223510435942,
                open_vs_sma_atr=0.371711711711712,
                primary_score=7.40804154363878,
                rs_alpha=54.06340057636887,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.625393,
                gap_pct=0.009653,
                market_ratio=1.218976,
                open_vs_sma_atr=1.0,
                primary_score=4.678518,
                rs_alpha=52.054795,
                trade_weekday=1,
            ),
            0.0,
        )
    def test_daytrade_primary_tuesday_high_market_mid_breadth_negative_open_low_score_no_trade(self):
        loss_candidate = {
            "breadth_val": 0.7008170961659334,
            "gap_pct": 0.006380008204938934,
            "market_ratio": 1.2525188679245284,
            "open_vs_sma_atr": -0.7057136912950613,
            "primary_score": 3.2154490922452064,
            "trade_weekday": 1,
        }
        survivor_candidate = {
            "breadth_val": 0.6637337606837607,
            "gap_pct": 0.026825127334465953,
            "market_ratio": 1.222680412371134,
            "open_vs_sma_atr": 0.792965657746335,
            "primary_score": 5.342074879696522,
            "trade_weekday": 1,
        }
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**survivor_candidate),
            0.0,
        )
    def test_daytrade_primary_tuesday_high_breadth_hot_market_very_low_score_no_trade(self):
        loss_candidate = {
            "breadth_val": 0.754242614707731,
            "gap_pct": 0.0056118143459915615,
            "market_ratio": 1.2594124509491993,
            "open_vs_sma_atr": 2.425111308993756,
            "primary_score": 3.1882119508539564,
            "trade_weekday": 1,
        }
        second_loss_candidate = {
            "breadth_val": 0.7510999371464487,
            "gap_pct": 0.009852216748768461,
            "market_ratio": 1.2577386111588889,
            "open_vs_sma_atr": 1.3043884220354793,
            "primary_score": 3.0469803122803927,
            "trade_weekday": 1,
        }
        survivor_candidate = {
            "breadth_val": 0.7460716530483973,
            "gap_pct": 0.0011933174224343368,
            "market_ratio": 1.2453679419279515,
            "open_vs_sma_atr": 2.2176870748299318,
            "primary_score": 3.343086224754765,
            "trade_weekday": 1,
        }
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**loss_candidate),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**second_loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**survivor_candidate),
            0.0,
        )
    def test_daytrade_primary_tuesday_wednesday_high_breadth_near_neutral_market_mid_open_no_trade(self):
        loss_candidate = {
            "breadth_val": 0.7278441231929604,
            "gap_pct": -0.004491017964071808,
            "market_ratio": 1.0266106972229576,
            "open_vs_sma_atr": 1.5547169811320756,
            "primary_score": 10.59829355940634,
            "trade_weekday": 1,
        }
        second_loss_candidate = {
            "breadth_val": 0.71024512884978,
            "gap_pct": -0.0034825870646766344,
            "market_ratio": 1.0312084190153623,
            "open_vs_sma_atr": 1.1726656233698498,
            "primary_score": 8.497688544637,
            "trade_weekday": 2,
        }
        third_loss_candidate = {
            "breadth_val": 0.7278441231929604,
            "gap_pct": -0.0003745318352059712,
            "market_ratio": 1.0266106972229576,
            "open_vs_sma_atr": -0.1768377253814147,
            "primary_score": 9.95644671676978,
            "trade_weekday": 1,
        }
        survivor_candidate = {
            "breadth_val": 0.6913890634820867,
            "gap_pct": 0.01921317474839901,
            "market_ratio": 1.0484568301361483,
            "open_vs_sma_atr": 2.2481139983235545,
            "primary_score": 9.734284614870738,
            "trade_weekday": 2,
        }
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**loss_candidate),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**second_loss_candidate),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**third_loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**survivor_candidate),
            0.0,
        )
    def test_daytrade_primary_tuesday_mid_breadth_hot_market_stretched_open_low_score_no_trade(self):
        loss_candidate = {
            "breadth_val": 0.630421,
            "gap_pct": -0.000380,
            "market_ratio": 1.207122,
            "open_vs_sma_atr": 3.275348,
            "primary_score": 6.876616,
            "rs_alpha": 17.215302,
            "trade_weekday": 1,
        }
        safer_neighbor = {
            "breadth_val": 0.660591,
            "gap_pct": -0.002764,
            "market_ratio": 1.197680,
            "open_vs_sma_atr": 2.339387,
            "primary_score": 8.483330,
            "rs_alpha": 28.158205,
            "trade_weekday": 1,
        }
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(**loss_candidate),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**safer_neighbor),
            0.0,
        )
        # Tuesday high-breadth / mid-gap / mid-score / low-open.
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.700817,
                gap_pct=0.010309,
                market_ratio=1.252519,
                open_vs_sma_atr=0.909836,
                primary_score=7.539108,
                rs_alpha=64.009662,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.706474,
                gap_pct=0.009653,
                market_ratio=1.204034,
                open_vs_sma_atr=1.684324,
                primary_score=6.858091,
                rs_alpha=52.054795,
                trade_weekday=1,
            ),
            0.0,
        )
        # Tuesday high-breadth / high-score / mid-open.
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.750471,
                gap_pct=0.0,
                market_ratio=1.131439,
                open_vs_sma_atr=1.781321,
                primary_score=14.035739,
                rs_alpha=149.52381,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.757385,
                gap_pct=0.024648,
                market_ratio=1.1264,
                open_vs_sma_atr=1.968047,
                primary_score=12.485364,
                rs_alpha=91.805493,
                trade_weekday=1,
            ),
            0.0,
        )
        # Friday mid-breadth / hot-market / high-score / mid-open.
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.624764,
                gap_pct=0.027422,
                market_ratio=1.18501,
                open_vs_sma_atr=1.932015,
                primary_score=8.271928,
                rs_alpha=29.639889,
                trade_weekday=4,
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.637964,
                gap_pct=0.008152,
                market_ratio=1.156066,
                open_vs_sma_atr=2.295341,
                primary_score=6.993222,
                rs_alpha=49.715216,
                trade_weekday=4,
            ),
            0.0,
        )
        # Thursday holdout veto pocket: this was the current worst day and is
        # still absent from train and standalone.
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.639849,
                gap_pct=0.0,
                market_ratio=1.178443,
                open_vs_sma_atr=1.012083,
                primary_score=6.832076,
                rs_alpha=20.762517,
                trade_weekday=3,
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.646763,
                gap_pct=0.022989,
                market_ratio=1.181362,
                open_vs_sma_atr=-0.638821,
                primary_score=6.39803,
                rs_alpha=22.881356,
                trade_weekday=3,
            ),
            0.0,
        )
    def test_daytrade_primary_thursday_near_neutral_mid_open_low_score_no_trade(self):
        loss_candidate = {
            "breadth_val": 0.6316781898177247,
            "gap_pct": 0.02127659574468077,
            "market_ratio": 1.010428654583587,
            "open_vs_sma_atr": 1.0008417508417509,
            "primary_score": 7.243355117761603,
            "rs_alpha": 37.74912075029309,
            "trade_weekday": 3,
        }
        second_loss_candidate = {
            "breadth_val": 0.6040226272784412,
            "gap_pct": 0.02269043760129663,
            "market_ratio": 1.0183270956991417,
            "open_vs_sma_atr": 1.949444657219456,
            "primary_score": 6.679185391796499,
            "rs_alpha": 37.294170004450386,
            "trade_weekday": 3,
        }
        survivor_candidate = {
            "breadth_val": 0.661219,
            "gap_pct": -0.002299,
            "market_ratio": 1.028257,
            "open_vs_sma_atr": -0.720896,
            "primary_score": 6.079457,
            "trade_weekday": 3,
        }
        for candidate in (loss_candidate, second_loss_candidate):
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**survivor_candidate),
            0.0,
        )
    def test_daytrade_primary_wednesday_low_breadth_near_neutral_negative_gap_low_score_no_trade(self):
        loss_candidate = {
            "breadth_val": 0.4632306725329981,
            "gap_pct": -0.0016275284817484081,
            "market_ratio": 1.021915737527678,
            "open_vs_sma_atr": 0.5484624367458141,
            "primary_score": 3.7076526387313242,
            "rs_alpha": 20.916502670789995,
            "trade_weekday": 2,
        }
        second_loss_candidate = {
            "breadth_val": 0.49465744814582024,
            "gap_pct": -0.0037149611617697254,
            "market_ratio": 1.0157915072351775,
            "open_vs_sma_atr": 0.1710108073744414,
            "primary_score": 3.6745837595157624,
            "rs_alpha": 29.527559055118104,
            "trade_weekday": 2,
        }
        survivor_candidate = {
            "breadth_val": 0.487744,
            "gap_pct": 0.017173,
            "market_ratio": 1.006597,
            "open_vs_sma_atr": 0.890909,
            "primary_score": 3.193656,
            "trade_weekday": 2,
        }
        for candidate in (loss_candidate, second_loss_candidate):
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 0.0)
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(**survivor_candidate),
            0.0,
        )
    def test_daytrade_primary_residual_train_only_pockets_no_trade(self):
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.672533,
                gap_pct=0.027361,
                market_ratio=1.132840,
                open_vs_sma_atr=2.449807,
                primary_score=3.795966,
                trade_weekday=4,
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.740415,
                gap_pct=0.015428,
                market_ratio=1.045538,
                open_vs_sma_atr=1.223214,
                primary_score=4.349498,
                trade_weekday=4,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.712131,
                gap_pct=0.018663,
                market_ratio=1.040149,
                open_vs_sma_atr=0.915903,
                primary_score=4.13511,
                prev_rsi2=51.923077,
                trade_weekday=4,
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.672533,
                gap_pct=-0.004251,
                market_ratio=1.074705,
                open_vs_sma_atr=0.614118,
                primary_score=4.097059,
                prev_rsi2=65.625,
                trade_weekday=4,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.756757,
                market_ratio=0.999204,
                gap_pct=-0.000344,
                primary_score=13.752608,
                open_vs_sma_atr=0.129385,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.694532,
                market_ratio=0.992497,
                gap_pct=-0.000694,
                primary_score=3.193918,
                open_vs_sma_atr=0.185185,
                trade_weekday=1,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.700189,

                market_ratio=1.005715,
                gap_pct=0.021834,
                primary_score=5.601648,
                open_vs_sma_atr=2.992547,
                trade_weekday=3,
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.513514,

                market_ratio=1.030644,
                gap_pct=0.018175,
                primary_score=4.733015,
                open_vs_sma_atr=1.435959,
                trade_weekday=3,
            ),
            0.0,
        )
        self.assertEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.767442,

                market_ratio=1.082356,
                gap_pct=0.0,
                prev_return=0.006502,
                primary_score=7.291774,
                open_vs_sma_atr=1.29989,
                trade_weekday=3,
            ),
            0.0,
        )
        self.assertGreater(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.580767,

                market_ratio=1.036796,
                gap_pct=0.007714,
                prev_return=0.018254,
                primary_score=3.14097,
                open_vs_sma_atr=1.785153,
                trade_weekday=3,
            ),
            0.0,
        )
    def test_daytrade_primary_friday_high_breadth_hot_market_stable_gap_sizeup(self):
        win_candidates = (
            {
                "breadth_val": 0.720302,
                "gap_pct": 0.000744,
                "market_ratio": 1.203315,
                "open_vs_sma_atr": 2.425004,
                "prev_return": 0.017913,
                "prev_rsi2": 76.756757,
                "primary_score": 6.185709,
                "trade_weekday": 4,
            },
            {
                "breadth_val": 0.624764,
                "gap_pct": 0.001511,
                "market_ratio": 1.185010,
                "open_vs_sma_atr": 0.883550,
                "prev_return": 0.063907,
                "prev_rsi2": 74.647887,
                "primary_score": 6.608166,
                "trade_weekday": 4,
            },
            {
                "breadth_val": 0.747957,
                "gap_pct": 0.002179,
                "market_ratio": 1.232131,
                "open_vs_sma_atr": 0.625761,
                "prev_return": 0.013693,
                "prev_rsi2": 53.448276,
                "primary_score": 6.136192,
                "trade_weekday": 4,
            },
            {
                "breadth_val": 0.623507,
                "gap_pct": 0.002130,
                "market_ratio": 1.218806,
                "open_vs_sma_atr": 2.650579,
                "prev_return": 0.035281,
                "prev_rsi2": 62.745098,
                "primary_score": 7.221846,
                "trade_weekday": 4,
            },
        )
        for candidate in win_candidates:
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 10.5)
            self.assertAlmostEqual(resolve_daytrade_primary_risk_budget_pct(**candidate), 0.375)
    def test_daytrade_primary_thursday_friday_moderate_open_sizeup(self):
        win_candidates = (
            {
                "breadth_val": 0.620993,
                "gap_pct": 0.005195,
                "market_ratio": 1.114173,
                "open_vs_sma_atr": 1.079547,
                "primary_score": 8.292804,
                "trade_weekday": 4,
            },
            {
                "breadth_val": 0.428033,
                "gap_pct": 0.000462,
                "market_ratio": 1.088532,
                "open_vs_sma_atr": 2.488424,
                "primary_score": 4.795007,
                "trade_weekday": 3,
            },
            {
                "breadth_val": 0.626021,
                "gap_pct": 0.00693,
                "market_ratio": 1.134371,
                "open_vs_sma_atr": 2.080664,
                "primary_score": 10.065864,
                "trade_weekday": 3,
            },
            {
                "breadth_val": 0.647392,
                "gap_pct": -0.003096,
                "market_ratio": 1.125252,
                "open_vs_sma_atr": 1.171338,
                "primary_score": 7.603948,
                "trade_weekday": 4,
            },
        )
        for candidate in win_candidates:
            self.assertAlmostEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 3.75)
            self.assertAlmostEqual(resolve_daytrade_primary_risk_budget_pct(**candidate), 0.15)

    def test_daytrade_primary_broader_hot_market_stable_gap_sizeup(self):
        win_candidates = (
            {
                "breadth_val": 0.680704,
                "gap_pct": -0.000979,
                "market_ratio": 1.194522,
                "open_vs_sma_atr": -0.5,
                "prev_return": 0.018962,
                "primary_score": 11.129107,
                "trade_weekday": 3,
            },
            {
                "breadth_val": 0.761785,
                "gap_pct": -0.002660,
                "market_ratio": 1.176980,
                "open_vs_sma_atr": 0.747666,
                "prev_return": 0.074286,
                "primary_score": 9.673022,
                "trade_weekday": 1,
            },
            {
                "breadth_val": 0.749214,
                "gap_pct": 0.0,
                "market_ratio": 1.189645,
                "open_vs_sma_atr": 2.031484,
                "prev_return": 0.011976,
                "primary_score": 7.528062,
                "trade_weekday": 2,
            },
        )
        for candidate in win_candidates:
            self.assertEqual(resolve_daytrade_primary_equity_notional_pct(**candidate), 6.0)

        loss_candidate = {
            "breadth_val": 0.735387,
            "gap_pct": 0.0,
            "market_ratio": 1.225086,
            "open_vs_sma_atr": -0.455204,
            "prev_return": 0.017347,
            "primary_score": 6.979769,
            "trade_weekday": 2,
        }
        self.assertLess(
            resolve_daytrade_primary_equity_notional_pct(**loss_candidate),
            6.0,
        )

    def test_tick_normalization_rounds_buy_up_and_sell_down_to_jpx_ticks(self):
        self.assertEqual(normalize_tick_size(1234.2, is_buy=True), 1235.0)
        self.assertEqual(normalize_tick_size(1234.2, is_buy=False), 1234.0)
        self.assertEqual(normalize_tick_size(3001.0, is_buy=True), 3005.0)
        self.assertEqual(normalize_tick_size(3001.0, is_buy=False), 3000.0)
        self.assertEqual(normalize_tick_size(0, is_buy=True), 0.0)
if __name__ == '__main__':
    unittest.main()









