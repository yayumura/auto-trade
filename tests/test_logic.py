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
    is_daytrade_inverse_rebreak_context,
    is_daytrade_monthly_risk_blocked,
    is_daytrade_market_allowed,
    is_daytrade_strong_oversold_market_allowed,
    is_daytrade_weekly_profit_guard_active,
    is_daytrade_bull_etf_price_allowed,
    resolve_daytrade_intraday_stop_mult,
    resolve_daytrade_intraday_target_mult,
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
    DAYTRADE_PRIMARY_LOW_SCORE_HOT_MARKET_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_MID_BREADTH_HOT_MARKET_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_WEDNESDAY_HIGH_MARKET_MID_BREADTH_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_TUESDAY_HIGH_MARKET_MID_BREADTH_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_MONDAY_BROAD_MID_SCORE_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_TEPID_MARKET_STRONG_PRIOR_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_TEPID_LOW_BREADTH_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_TEPID_LOW_BREADTH_HIGH_GAP_EQUITY_NOTIONAL_PCT,
    DAYTRADE_PRIMARY_TUESDAY_OVERHEATED_EQUITY_NOTIONAL_PCT,
    resolve_daytrade_primary_equity_notional_pct,
    resolve_daytrade_fallback_equity_notional_pct,
    resolve_daytrade_catchup_equity_notional_pct,
    resolve_daytrade_catchup_notional_pct,
    resolve_daytrade_weekly_leverage,
    select_daytrade_candidates,
    DAYTRADE_BULL_ETF_LOW_BREADTH_REBOUND_LEVERAGE,
    DAYTRADE_BULL_ETF_LOW_BREADTH_REBOUND_NOTIONAL_PCT,
    DAYTRADE_CATCHUP_GAPDOWN_EQUITY_NOTIONAL_PCT,
    DAYTRADE_CATCHUP_GAPDOWN_NOTIONAL_PCT,
    DAYTRADE_CATCHUP_RS_EQUITY_NOTIONAL_PCT,
    DAYTRADE_CATCHUP_RS_NOTIONAL_PCT,
    DAYTRADE_CATCHUP_RS_HOT_PREV_RETURN_EQUITY_NOTIONAL_PCT,
    DAYTRADE_CATCHUP_GAPDOWN_LOW_BREADTH_PROBE_LEVERAGE,
    DAYTRADE_FALLBACK_EQUITY_NOTIONAL_PCT,
    DAYTRADE_FALLBACK_HIGH_BREADTH_EXTENDED_EQUITY_NOTIONAL_PCT,
    DAYTRADE_FALLBACK_LOW_BREADTH_CONTINUATION_EQUITY_NOTIONAL_PCT,
    DAYTRADE_INVERSE_BUYING_POWER_LEVERAGE,
    DAYTRADE_SELECTED_FRAGILE_HOT_MARKET_MAX_LEVERAGE,
    DAYTRADE_SELECTED_HEATED_POSITIVE_GAP_MAX_LEVERAGE,
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
            0.20,
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
                trade_weekday=0,
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
                [{"setup_type": "primary", "score": 9.5, "gap_pct": 0.0}],
                0.70,
                market_ratio=1.12,
                trade_weekday=2,
            ),
            DAYTRADE_SELECTED_WEDNESDAY_NONPOSITIVE_GAP_NO_TRADE_MAX_LEVERAGE,
        )
        self.assertAlmostEqual(
            resolve_daytrade_selected_leverage(
                1.25,
                [{"setup_type": "primary", "score": 9.5, "gap_pct": 0.0}],
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
                0.70,
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
                0.0,
                [{"setup_type": "catchup_rs", "score": 12.0, "gap_pct": 0.009}],
                0.30,
                trade_weekday=1,
            ),
            0.0,
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
            2.0,
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
            2.0,
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
            2.0,
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
            2.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.72,
                gap_pct=0.002,
                open_vs_sma_atr=1.8,
                trade_weekday=0,
            ),
            1.0,
        )
        self.assertAlmostEqual(
            resolve_daytrade_primary_equity_notional_pct(
                breadth_val=0.65,
                gap_pct=-0.001,
                open_vs_sma_atr=1.8,
                trade_weekday=1,
            ),
            0.75,
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
            0.90,
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
            2.0,
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
            2.0,
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
                gap_pct=0.007,
                open_vs_sma_atr=1.1,
                market_ratio=1.20,
                primary_score=11.0,
                trade_weekday=1,
            ),
            DAYTRADE_PRIMARY_TUESDAY_OVERHEATED_EQUITY_NOTIONAL_PCT,
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
            2.0,
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
            2.0,
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
            0.10,
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
                breadth_val=0.71,
                gap_pct=0.004,
                open_vs_sma_atr=1.5,
                market_ratio=1.18,
                primary_score=8.0,
                rs_alpha=35.0,
                trade_weekday=1,
            ),
            DAYTRADE_PRIMARY_TUESDAY_HIGH_MARKET_MID_BREADTH_EQUITY_NOTIONAL_PCT,
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
            DAYTRADE_PRIMARY_MAX_EQUITY_NOTIONAL_PCT,
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
            2.0,
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
            2.0,
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
            2.0,
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
            0.25,
        )
        self.assertAlmostEqual(
            resolve_daytrade_catchup_equity_notional_pct(
                setup_type="catchup_gapdown",
                breadth_val=0.40,
                gap_pct=-0.018,
                open_vs_sma_atr=-0.8,
                trade_weekday=0,
            ),
            DAYTRADE_CATCHUP_GAPDOWN_EQUITY_NOTIONAL_PCT,
        )
        self.assertAlmostEqual(
            resolve_daytrade_catchup_equity_notional_pct(
                setup_type="catchup_gapdown",
                breadth_val=0.30,
                gap_pct=-0.010,
                open_vs_sma_atr=0.3,
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
            0.10,
        )
        self.assertAlmostEqual(
            resolve_daytrade_catchup_equity_notional_pct(
                setup_type="catchup_gapdown",
                breadth_val=0.40,
                gap_pct=-0.009,
                open_vs_sma_atr=0.8,
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

    def test_daytrade_candidate_selection_keeps_non_executable_top_when_hot_market_score_gap_is_too_small(self):
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

        self.assertEqual(selected[0]["code"], "2000")
        self.assertEqual(selected[0]["setup_type"], "fallback")

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
            "2282",
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
            "2282",
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
            "2282",
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
            "2282",
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
