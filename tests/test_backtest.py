import numpy as np
import pandas as pd
from unittest.mock import patch

from backtest import run_backtest_v16_production, run_backtest_v19_monthly_rotation
from core.config import SLIPPAGE
from core.monthly_rotation_strategy import get_prod_monthly_rotation_backtest_params
from core.logic import normalize_tick_size


def _build_daytrade_bundle(exit_mode="close"):
    T = 110
    dates = pd.date_range("2024-01-07", periods=T)

    close_data = np.full((T, 1), 100.0)
    open_data = np.full((T, 1), 100.0)
    high_data = np.full((T, 1), 101.0)
    low_data = np.full((T, 1), 99.0)
    rsi2_data = np.full((T, 1), 20.0)
    sma20_data = np.full((T, 1), 95.0)
    sma100_data = np.full((T, 1), 90.0)
    atr_data = np.full((T, 1), 2.0)

    # Prior two sessions create a valid short-term momentum setup.
    close_data[100, 0] = 100.0
    open_data[100, 0] = 99.0
    high_data[100, 0] = 100.5
    low_data[100, 0] = 98.5

    close_data[101, 0] = 104.0
    open_data[101, 0] = 102.0
    high_data[101, 0] = 104.5
    low_data[101, 0] = 101.5
    rsi2_data[101, 0] = 60.0

    # Entry day: controlled continuation gap from 104 to 105.0 (~+0.96%)
    open_data[102, 0] = 105.0
    sma20_data[101, 0] = 100.0
    sma20_data[102, 0] = 100.0

    if exit_mode == "close":
        close_data[102, 0] = 108.5
        high_data[102, 0] = 108.8
        low_data[102, 0] = 104.8
    elif exit_mode == "stop":
        close_data[102, 0] = 103.0
        high_data[102, 0] = 105.1
        low_data[102, 0] = 102.8
    elif exit_mode == "target":
        close_data[102, 0] = 108.5
        high_data[102, 0] = 109.2
        low_data[102, 0] = 104.8
    elif exit_mode == "failed_runup":
        close_data[102, 0] = 104.8
        high_data[102, 0] = 107.6
        low_data[102, 0] = 104.6
    else:
        raise ValueError(f"Unknown exit_mode: {exit_mode}")

    bundle_np = {
        "Close": close_data,
        "Open": open_data,
        "High": high_data,
        "Low": low_data,
        "SMA5": np.full((T, 1), 90.0),
        "SMA20": sma20_data,
        "SMA100": sma100_data,
        "SMA200": np.full((T, 1), 90.0),
        "ATR": atr_data,
        "RSI2": rsi2_data,
        "RS_Alpha": np.full((T, 1), 30.0),
        "Turnover": np.full((T, 1), 1_000_000_000.0),
        "BB_LOWER_2": np.full((T, 1), 80.0),
        "tickers": ["1000.T"],
    }

    return dates, bundle_np


def _build_low_breadth_tuesday_catchup_bundle(start_date="2024-01-05"):
    T = 110
    dates = pd.date_range(start_date, periods=T)
    tickers = ["1000.T", "1321.T"]

    close_data = np.full((T, 2), [100.0, 100.0])
    open_data = np.full((T, 2), [100.0, 100.0])
    high_data = np.full((T, 2), [101.0, 101.0])
    low_data = np.full((T, 2), [99.0, 99.0])
    rsi2_data = np.full((T, 2), [55.0, 50.0])
    sma20_data = np.full((T, 2), [100.0, 100.0])
    sma100_data = np.full((T, 2), [95.0, 100.0])
    atr_data = np.full((T, 2), [2.0, 1.0])

    close_data[100] = [100.0, 100.0]
    open_data[100] = [99.0, 100.0]
    low_data[100] = [98.5, 99.5]

    close_data[101] = [104.0, 100.0]
    open_data[101] = [102.0, 100.0]
    high_data[101] = [104.5, 100.5]
    low_data[101] = [101.5, 99.5]
    rsi2_data[101] = [60.0, 50.0]

    open_data[102] = [105.0, 100.0]
    close_data[102] = [106.5, 100.2]
    high_data[102] = [106.8, 100.4]
    low_data[102] = [104.8, 99.8]

    bundle_np = {
        "Close": close_data,
        "Open": open_data,
        "High": high_data,
        "Low": low_data,
        "SMA5": np.full((T, 2), [99.0, 100.0]),
        "SMA20": sma20_data,
        "SMA100": sma100_data,
        "SMA200": np.full((T, 2), [90.0, 100.0]),
        "ATR": atr_data,
        "RSI2": rsi2_data,
        "RS_Alpha": np.full((T, 2), [30.0, 0.0]),
        "Turnover": np.full((T, 2), 1_000_000_000.0),
        "BB_LOWER_2": np.full((T, 2), [80.0, 95.0]),
        "tickers": tickers,
    }

    return dates, bundle_np


def _run_single_trade_backtest(exit_mode, return_trade_log=False, sl_mult=5.0, tp_mult=20.0):
    dates, bundle_np = _build_daytrade_bundle(exit_mode=exit_mode)
    return run_backtest_v16_production(
        univ_indices=np.arange(1),
        bundle_np=bundle_np,
        timeline=dates,
        breadth_ratio=np.ones(len(dates)) * 0.8,
        initial_cash=10_000_000,
        max_pos=1,
        sl_mult=sl_mult,
        tp_mult=tp_mult,
        leverage_rate=1.0,
        breadth_threshold=0.3,
        max_hold_days=1,
        return_trade_log=return_trade_log,
    )


def _run_single_trade_backtest_with_costs(exit_mode, sl_mult=5.0, tp_mult=20.0, **kwargs):
    dates, bundle_np = _build_daytrade_bundle(exit_mode=exit_mode)
    return run_backtest_v16_production(
        univ_indices=np.arange(1),
        bundle_np=bundle_np,
        timeline=dates,
        breadth_ratio=np.ones(len(dates)) * 0.8,
        initial_cash=10_000_000,
        max_pos=1,
        sl_mult=sl_mult,
        tp_mult=tp_mult,
        leverage_rate=1.0,
        breadth_threshold=0.3,
        max_hold_days=1,
        **kwargs,
    )


def test_daytrade_executes_one_trade_with_close_exit():
    final_assets, trade_count, monthly, results = _run_single_trade_backtest("close")

    assert trade_count == 1, f"Expected 1 trade, got {trade_count}"
    assert len(results) == 1
    assert results[0] > 0
    assert final_assets > 10_000_000


def test_daytrade_intraday_stop_caps_loss():
    final_assets, trade_count, monthly, results = _run_single_trade_backtest("stop")

    assert trade_count == 1, f"Expected 1 trade, got {trade_count}"
    assert len(results) == 1
    assert results[0] < 0
    assert final_assets < 10_000_000


def test_daytrade_intraday_target_locks_gain():
    final_assets, trade_count, monthly, results = _run_single_trade_backtest("target")

    assert trade_count == 1, f"Expected 1 trade, got {trade_count}"
    assert len(results) == 1
    assert results[0] > 0
    assert final_assets > 10_000_000


def test_daytrade_intraday_failed_runup_exits_near_break_even():
    final_assets, trade_count, monthly, results, trade_log = _run_single_trade_backtest(
        "failed_runup",
        return_trade_log=True,
        tp_mult=40.0,
    )

    assert trade_count == 1, f"Expected 1 trade, got {trade_count}"
    assert len(results) == 1
    assert trade_log[0]["exit_reason"] == "intraday_failed_runup"
    assert trade_log[0]["modeled_exit_price"] == trade_log[0]["entry_price"]
    assert trade_log[0]["exit_price"] <= trade_log[0]["entry_price"]
    assert results[0] <= 0


def test_daytrade_explicit_cost_reduces_equity():
    no_cost_assets, *_ = _run_single_trade_backtest_with_costs(
        "close",
        slippage=0.0,
        explicit_trade_cost=0.0,
    )
    with_cost_assets, *_ = _run_single_trade_backtest_with_costs(
        "close",
        slippage=0.0,
        explicit_trade_cost=5_000.0,
    )

    assert with_cost_assets < no_cost_assets


def test_daytrade_supports_asymmetric_execution_slippage():
    symmetric_assets, *_ = _run_single_trade_backtest_with_costs(
        "close",
        slippage=0.001,
    )
    asymmetric_assets, *_ = _run_single_trade_backtest_with_costs(
        "close",
        slippage=0.001,
        entry_slippage=0.0,
        exit_slippage=0.002,
    )

    assert asymmetric_assets != symmetric_assets


def test_daytrade_execution_uses_directional_tick_rounding():
    _, trade_count, _, _, trade_log = _run_single_trade_backtest(
        "close",
        return_trade_log=True,
    )

    assert trade_count == 1
    assert trade_log[0]["entry_price"] == normalize_tick_size(
        105.0 * 1.002,
        is_buy=True,
    )
    assert trade_log[0]["exit_reason"] == "intraday_target"
    assert trade_log[0]["exit_price"] == normalize_tick_size(
        trade_log[0]["modeled_exit_price"] * (1.0 - SLIPPAGE),
        is_buy=False,
    )
    assert trade_log[0]["entry_price"] == 106.0
    assert trade_log[0]["exit_price"] == 107.0


def test_daytrade_can_return_daily_stats():
    dates, bundle_np = _build_daytrade_bundle(exit_mode="close")
    final_assets, trade_count, monthly, results, daily_stats = run_backtest_v16_production(
        univ_indices=np.arange(1),
        bundle_np=bundle_np,
        timeline=dates,
        breadth_ratio=np.ones(len(dates)) * 0.8,
        initial_cash=10_000_000,
        max_pos=1,
        sl_mult=5.0,
        tp_mult=20.0,
        leverage_rate=1.0,
        breadth_threshold=0.3,
        max_hold_days=1,
        return_daily_stats=True,
    )

    assert trade_count == 1
    assert final_assets > 10_000_000
    assert isinstance(daily_stats, dict)
    assert "2024-04-18" in daily_stats
    assert daily_stats["2024-04-18"]["day_pnl"] > 0
    assert daily_stats["2024-04-18"]["trade_count"] == 1

def test_daytrade_can_return_candidate_log():
    dates, bundle_np = _build_daytrade_bundle(exit_mode="close")
    final_assets, trade_count, monthly, results, daily_stats, trade_log, candidate_log = run_backtest_v16_production(
        univ_indices=np.arange(1),
        bundle_np=bundle_np,
        timeline=dates,
        breadth_ratio=np.ones(len(dates)) * 0.8,
        initial_cash=10_000_000,
        max_pos=1,
        sl_mult=5.0,
        tp_mult=20.0,
        leverage_rate=1.0,
        breadth_threshold=0.3,
        max_hold_days=1,
        return_daily_stats=True,
        return_trade_log=True,
        return_candidate_log=True,
    )

    assert trade_count == 1
    assert final_assets > 10_000_000
    assert isinstance(candidate_log, dict)
    assert candidate_log["days"]
    assert candidate_log["candidates"]

    opened_days = [row for row in candidate_log["days"] if row["reason"] == "opened"]
    assert opened_days
    assert opened_days[0]["selected_count"] == 1
    assert opened_days[0]["opened_count"] == 1
    assert opened_days[0]["scan_universe"] == 1
    assert opened_days[0]["scan_passed_scan"] == 1
    assert "setup_no_setup_candidate_after_scan" in opened_days[0]

    opened_candidates = [row for row in candidate_log["candidates"] if row["opened"]]
    assert len(opened_candidates) == 1
    opened_candidate = opened_candidates[0]
    assert opened_candidate["execution_status"] == "opened"
    assert opened_candidate["selection_rank"] == 1
    assert opened_candidate["modeled_exit_reason"] == trade_log[0]["exit_reason"]
    assert opened_candidate["net_pnl"] == results[0]

def test_daytrade_backtest_generates_catchup_gapdown_candidates():
    dates, bundle_np = _build_daytrade_bundle(exit_mode="close")

    def _gapdown_only(open_p, *_args, **_kwargs):
        if not np.isclose(float(open_p), 105.0):
            return []
        return [{
            "setup_type": "catchup_gapdown",
            "gap_pct": -0.01,
            "prev_return": -0.02,
            "prev_rsi2": 20.0,
            "open_from_prev_low_atr": 0.5,
            "open_vs_sma_atr": 1.0,
            "rs_alpha": 30.0,
            "symbol_trend_ratio": 1.05,
        }]

    def _select_catchup(_primary, _strong, _fallback, catchup, _inverse, _bull, **_kwargs):
        return catchup[:1]

    with patch("core.logic.is_daytrade_catchup_market_allowed", return_value=True), patch(
        "core.daytrade_candidate_engine.evaluate_daytrade_open_setup", return_value=None
    ), patch(
        "core.daytrade_candidate_engine.evaluate_daytrade_strong_oversold_open_setup", return_value=None
    ), patch(
        "core.daytrade_candidate_engine.evaluate_daytrade_fallback_open_setup", return_value=None
    ), patch(
        "core.daytrade_candidate_engine.evaluate_daytrade_catchup_open_setups", side_effect=_gapdown_only
    ), patch(
        "core.daytrade_candidate_engine.score_daytrade_catchup_open_setup", return_value=10.0
    ), patch(
        "backtest.select_daytrade_candidates", side_effect=_select_catchup
    ), patch(
        "backtest.cap_daytrade_position_size", return_value=100
    ):
        _, trade_count, _, _, _, trade_log, candidate_log = run_backtest_v16_production(
            univ_indices=np.arange(1),
            bundle_np=bundle_np,
            timeline=dates,
            breadth_ratio=np.ones(len(dates)) * 0.8,
            initial_cash=10_000_000,
            max_pos=1,
            leverage_rate=1.0,
            return_daily_stats=True,
            return_trade_log=True,
            return_candidate_log=True,
        )

    assert trade_count == 1
    assert trade_log[0]["setup_type"] == "catchup_gapdown"
    assert any(
        row["setup_type"] == "catchup_gapdown" and row["opened"]
        for row in candidate_log["candidates"]
    )

def test_daytrade_open_entry_does_not_use_same_day_breadth():
    dates, bundle_np = _build_daytrade_bundle(exit_mode="close")
    breadth_ratio = np.full(len(dates), 0.20)
    breadth_ratio[102] = 0.80

    final_assets, trade_count, monthly, results = run_backtest_v16_production(
        univ_indices=np.arange(1),
        bundle_np=bundle_np,
        timeline=dates,
        breadth_ratio=breadth_ratio,
        initial_cash=10_000_000,
        max_pos=1,
        sl_mult=5.0,
        tp_mult=20.0,
        leverage_rate=1.0,
        breadth_threshold=0.3,
        max_hold_days=1,
    )

    assert trade_count == 0
    assert len(results) == 0
    assert final_assets == 10_000_000


def test_daytrade_allows_low_breadth_tuesday_catchup_rs_probe():
    dates, bundle_np = _build_low_breadth_tuesday_catchup_bundle()

    def _select_first_available(primary, strong, fallback, catchup, inverse, bull, **kwargs):
        return catchup[:1] or fallback[:1] or strong[:1] or primary[:1] or inverse[:1] or bull[:1]

    with patch("backtest.select_daytrade_candidates", side_effect=_select_first_available), patch(
        "backtest.cap_daytrade_position_size", return_value=100
    ):
        final_assets, trade_count, monthly, results = run_backtest_v16_production(
            univ_indices=np.arange(1),
            bundle_np=bundle_np,
            timeline=dates,
            breadth_ratio=np.ones(len(dates)) * 0.30,
            initial_cash=10_000_000,
            max_pos=1,
            sl_mult=5.0,
            tp_mult=20.0,
            slippage=0.0,
            leverage_rate=1.0,
            breadth_threshold=0.3,
            max_hold_days=1,
        )

    assert trade_count == 1
    assert len(results) == 1
    assert results[0] > 0
    assert final_assets > 10_000_000.0


def test_daytrade_filters_low_breadth_friday_catchup_rs_probe():
    dates, bundle_np = _build_low_breadth_tuesday_catchup_bundle(start_date="2024-01-01")
    final_assets, trade_count, monthly, results = run_backtest_v16_production(
        univ_indices=np.arange(1),
        bundle_np=bundle_np,
        timeline=dates,
        breadth_ratio=np.ones(len(dates)) * 0.30,
        initial_cash=10_000_000,
        max_pos=1,
        sl_mult=5.0,
        tp_mult=20.0,
        slippage=0.0,
        leverage_rate=1.0,
        breadth_threshold=0.3,
        max_hold_days=1,
    )

    assert trade_count == 0
    assert len(results) == 0
    assert final_assets == 10_000_000.0


def test_daytrade_catchup_rs_strong_continuation_forwards_risk_budget_pct():
    dates, bundle_np = _build_low_breadth_tuesday_catchup_bundle()
    captured = {}

    def _select_first_available(primary, strong, fallback, catchup, inverse, bull, **kwargs):
        return catchup[:1] or fallback[:1] or strong[:1] or primary[:1] or inverse[:1] or bull[:1]

    def _capture_cap_daytrade_position_size(*args, **kwargs):
        captured["risk_budget_pct"] = kwargs.get("risk_budget_pct")
        return 100

    with patch("backtest.select_daytrade_candidates", side_effect=_select_first_available), patch(
        "core.daytrade_candidate_engine.resolve_daytrade_catchup_notional_pct", return_value=1.0
    ), patch("core.daytrade_candidate_engine.resolve_daytrade_catchup_equity_notional_pct", return_value=2.0), patch(
        "backtest.cap_daytrade_position_size", side_effect=_capture_cap_daytrade_position_size
    ):
        final_assets, trade_count, monthly, results = run_backtest_v16_production(
            univ_indices=np.arange(1),
            bundle_np=bundle_np,
            timeline=dates,
            breadth_ratio=np.ones(len(dates)) * 0.30,
            initial_cash=10_000_000,
            max_pos=1,
            sl_mult=5.0,
            tp_mult=20.0,
            slippage=0.0,
            leverage_rate=1.0,
            breadth_threshold=0.3,
            max_hold_days=1,
        )

    assert trade_count == 1
    assert len(results) == 1
    assert results[0] > 0
    assert captured["risk_budget_pct"] == 0.3
    assert final_assets > 10_000_000.0


def test_daytrade_tries_next_candidate_when_top_is_too_large():
    T = 104
    dates = pd.date_range("2024-01-07", periods=T)
    captured = {}
    close_data = np.full((T, 2), [8_500.0, 1_000.0])
    open_data = close_data.copy()
    high_data = close_data * 1.01
    low_data = close_data * 0.99
    atr_data = np.zeros((T, 2))

    close_data[100] = [8_400.0, 980.0]
    open_data[100] = [8_300.0, 970.0]
    low_data[100] = [8_250.0, 965.0]
    close_data[101] = [8_800.0, 1_000.0]
    open_data[101] = [8_500.0, 990.0]
    atr_data[101] = [80.0, 10.0]
    open_data[102] = [9_000.0, 1_010.0]
    close_data[102] = [9_050.0, 1_025.0]
    high_data[102] = [9_080.0, 1_030.0]
    low_data[102] = [8_990.0, 1_005.0]

    bundle_np = {
        "Close": close_data,
        "Open": open_data,
        "High": high_data,
        "Low": low_data,
        "SMA5": np.full((T, 2), 900.0),
        "SMA20": np.full((T, 2), [8_000.0, 950.0]),
        "SMA100": np.full((T, 2), [7_500.0, 900.0]),
        "SMA200": np.full((T, 2), [7_000.0, 850.0]),
        "ATR": atr_data,
        "RSI2": np.full((T, 2), 60.0),
        "RS_Alpha": np.full((T, 2), [100.0, 20.0]),
        "Turnover": np.full((T, 2), 2_000_000_000.0),
        "BB_LOWER_2": np.full((T, 2), 800.0),
        "tickers": ["9000.T", "1000.T"],
    }

    top_candidate = {
        "code": "9000.T",
        "setup_type": "primary",
        "score": 10.0,
        "open": 8_500.0,
        "close": 8_800.0,
        "high": 8_900.0,
        "low": 8_400.0,
        "atr": 80.0,
        "turnover": 2_000_000_000.0,
        "notional_pct": 0.20,
        "equity_notional_pct": 3.0,
        "risk_budget_pct": 0.30,
        "size_multiplier": 1.5,
    }
    next_candidate = {
        "code": "1000.T",
        "setup_type": "primary",
        "score": 9.0,
        "open": 1_000.0,
        "close": 1_025.0,
        "high": 1_030.0,
        "low": 995.0,
        "atr": 10.0,
        "turnover": 2_000_000_000.0,
        "notional_pct": 0.15,
        "equity_notional_pct": 1.0,
        "risk_budget_pct": 0.10,
        "size_multiplier": 1.0,
    }

    def _select_two_candidates(primary, strong, fallback, catchup, inverse, bull, **kwargs):
        return [top_candidate, next_candidate]

    def _skip_too_large_candidate(*args, **kwargs):
        entry_price = kwargs.get("entry_price", 0.0)
        if entry_price >= 5_000.0:
            captured["size_multiplier"] = kwargs.get("size_multiplier")
        return 0 if entry_price >= 5_000.0 else 100

    with patch("backtest.select_daytrade_candidates", side_effect=_select_two_candidates), patch(
        "backtest.cap_daytrade_position_size", side_effect=_skip_too_large_candidate
    ):
        final_assets, trade_count, monthly, results = run_backtest_v16_production(
            univ_indices=np.arange(2),
            bundle_np=bundle_np,
            timeline=dates,
            breadth_ratio=np.ones(len(dates)) * 0.8,
            initial_cash=1_000_000,
            max_pos=1,
            slippage=0.0,
            leverage_rate=1.0,
            breadth_threshold=0.3,
        )

    assert trade_count == 1
    assert final_assets > 1_000_000
    assert len(results) == 1
    assert captured["size_multiplier"] == 1.5


def test_daytrade_can_trade_inverse_on_riskoff_day():
    T = 104
    dates = pd.date_range("2024-01-01", periods=T)
    tickers = ["1368.T", "1321.T"]

    close_data = np.full((T, 2), [100.0, 100.0])
    open_data = np.full((T, 2), [100.0, 100.0])
    high_data = np.full((T, 2), [101.0, 101.0])
    low_data = np.full((T, 2), [99.0, 99.0])
    atr_data = np.full((T, 2), 1.0)
    rsi2_data = np.full((T, 2), 60.0)
    rs_alpha_data = np.full((T, 2), [10.0, 0.0])

    close_data[100] = [98.0, 100.0]
    open_data[100] = [97.5, 101.0]
    low_data[100] = [97.0, 99.5]

    close_data[101] = [100.0, 97.0]
    open_data[101] = [99.0, 98.0]
    high_data[101] = [100.5, 98.2]
    low_data[101] = [98.8, 96.5]
    rsi2_data[101] = [100.0, 40.0]
    rs_alpha_data[101] = [12.0, -5.0]

    open_data[102] = [101.0, 97.0]
    close_data[102] = [102.0, 96.5]
    high_data[102] = [103.5, 97.2]
    low_data[102] = [100.8, 96.0]

    bundle_np = {
        "Close": close_data,
        "Open": open_data,
        "High": high_data,
        "Low": low_data,
        "SMA5": np.full((T, 2), [99.0, 99.0]),
        "SMA20": np.full((T, 2), [99.0, 99.0]),
        "SMA100": np.full((T, 2), [99.0, 99.0]),
        "SMA200": np.full((T, 2), [99.0, 100.0]),
        "ATR": atr_data,
        "RSI2": rsi2_data,
        "RS_Alpha": rs_alpha_data,
        "Turnover": np.full((T, 2), 2_000_000_000.0),
        "BB_LOWER_2": np.full((T, 2), [95.0, 95.0]),
        "tickers": tickers,
    }

    final_assets, trade_count, monthly, results = run_backtest_v16_production(
        univ_indices=np.array([0]),
        bundle_np=bundle_np,
        timeline=dates,
        breadth_ratio=np.ones(len(dates)) * 0.30,
        initial_cash=1_000_000,
        max_pos=1,
        slippage=0.0,
        leverage_rate=1.0,
        breadth_threshold=0.3,
    )

    assert trade_count == 1
    assert final_assets > 1_000_000
    assert results[0] > 0


def test_daytrade_can_trade_low_turnover_inverse_in_panic_breadth():
    T = 104
    dates = pd.date_range("2024-01-01", periods=T)
    tickers = ["1368.T", "1321.T"]

    close_data = np.full((T, 2), [100.0, 100.0])
    open_data = np.full((T, 2), [100.0, 100.0])
    high_data = np.full((T, 2), [101.0, 101.0])
    low_data = np.full((T, 2), [99.0, 99.0])
    atr_data = np.full((T, 2), 1.0)
    rsi2_data = np.full((T, 2), 60.0)
    rs_alpha_data = np.full((T, 2), [10.0, 0.0])
    turnover_data = np.full((T, 2), [150_000_000.0, 2_000_000_000.0])

    close_data[100] = [98.0, 100.0]
    open_data[100] = [97.5, 101.0]
    low_data[100] = [97.0, 99.5]

    close_data[101] = [100.0, 97.0]
    open_data[101] = [99.0, 98.0]
    high_data[101] = [100.5, 98.2]
    low_data[101] = [98.8, 96.5]
    rsi2_data[101] = [100.0, 40.0]
    rs_alpha_data[101] = [12.0, -5.0]

    open_data[102] = [101.0, 97.0]
    close_data[102] = [102.0, 96.5]
    high_data[102] = [103.5, 97.2]
    low_data[102] = [100.8, 96.0]

    bundle_np = {
        "Close": close_data,
        "Open": open_data,
        "High": high_data,
        "Low": low_data,
        "SMA5": np.full((T, 2), [99.0, 99.0]),
        "SMA20": np.full((T, 2), [99.0, 99.0]),
        "SMA100": np.full((T, 2), [99.0, 99.0]),
        "SMA200": np.full((T, 2), [99.0, 100.0]),
        "ATR": atr_data,
        "RSI2": rsi2_data,
        "RS_Alpha": rs_alpha_data,
        "Turnover": turnover_data,
        "BB_LOWER_2": np.full((T, 2), [95.0, 95.0]),
        "tickers": tickers,
    }

    final_assets, trade_count, monthly, results = run_backtest_v16_production(
        univ_indices=np.array([0]),
        bundle_np=bundle_np,
        timeline=dates,
        breadth_ratio=np.ones(len(dates)) * 0.09,
        initial_cash=1_000_000,
        max_pos=1,
        slippage=0.0,
        leverage_rate=1.0,
        breadth_threshold=0.3,
    )

    assert trade_count == 1
    assert final_assets > 1_000_000
    assert results[0] > 0


def test_daytrade_can_trade_inverse_pullback_in_bear_market():
    T = 104
    dates = pd.date_range("2023-12-31", periods=T)
    tickers = ["1368.T", "1321.T"]

    close_data = np.full((T, 2), [100.0, 100.0])
    open_data = np.full((T, 2), [100.0, 100.0])
    high_data = np.full((T, 2), [101.0, 101.0])
    low_data = np.full((T, 2), [99.0, 99.0])
    atr_data = np.full((T, 2), 1.0)
    rsi2_data = np.full((T, 2), [60.0, 40.0])
    rs_alpha_data = np.full((T, 2), [10.0, -5.0])

    close_data[100] = [100.0, 100.0]
    open_data[100] = [100.0, 99.0]

    close_data[101] = [104.0, 99.0]
    open_data[101] = [103.0, 98.5]
    high_data[101] = [104.5, 99.2]
    low_data[101] = [102.8, 98.0]

    open_data[102] = [103.0, 98.0]
    close_data[102] = [104.0, 99.0]
    high_data[102] = [105.0, 100.0]
    low_data[102] = [102.5, 98.0]

    bundle_np = {
        "Close": close_data,
        "Open": open_data,
        "High": high_data,
        "Low": low_data,
        "SMA5": np.full((T, 2), [110.0, 100.0]),
        "SMA20": np.full((T, 2), [110.0, 100.0]),
        "SMA100": np.full((T, 2), [110.0, 100.0]),
        "SMA200": np.full((T, 2), [110.0, 100.0]),
        "ATR": atr_data,
        "RSI2": rsi2_data,
        "RS_Alpha": rs_alpha_data,
        "Turnover": np.full((T, 2), 2_000_000_000.0),
        "BB_LOWER_2": np.full((T, 2), [95.0, 95.0]),
        "tickers": tickers,
    }

    breadth_ratio = np.ones(len(dates)) * 0.30
    final_assets, trade_count, monthly, results = run_backtest_v16_production(
        univ_indices=np.array([0]),
        bundle_np=bundle_np,
        timeline=dates,
        breadth_ratio=breadth_ratio,
        initial_cash=1_000_000,
        max_pos=1,
        slippage=0.0,
        leverage_rate=1.0,
        breadth_threshold=0.3,
    )

    assert trade_count == 1
    assert final_assets > 1_000_000
    assert results[0] > 0


def test_daytrade_can_trade_inverse_rebreak_after_failed_rebound():
    T = 104
    dates = pd.date_range("2024-01-01", periods=T)
    tickers = ["1360.T", "1321.T"]

    close_data = np.full((T, 2), [100.0, 100.0])
    open_data = np.full((T, 2), [100.0, 100.0])
    high_data = np.full((T, 2), [101.0, 101.0])
    low_data = np.full((T, 2), [99.0, 99.0])
    atr_data = np.full((T, 2), [2.0, 1.0])
    rsi2_data = np.full((T, 2), [60.0, 40.0])
    rs_alpha_data = np.full((T, 2), [10.0, -5.0])

    close_data[100] = [112.0, 90.0]
    open_data[100] = [111.0, 91.0]

    close_data[101] = [100.0, 87.0]
    open_data[101] = [101.0, 89.0]
    high_data[101] = [102.0, 90.0]
    low_data[101] = [99.0, 86.0]

    open_data[102] = [104.9, 84.5]
    close_data[102] = [106.0, 84.0]
    high_data[102] = [108.0, 85.0]
    low_data[102] = [104.5, 83.5]

    bundle_np = {
        "Close": close_data,
        "Open": open_data,
        "High": high_data,
        "Low": low_data,
        "SMA5": np.full((T, 2), [110.0, 100.0]),
        "SMA20": np.full((T, 2), [110.0, 100.0]),
        "SMA100": np.full((T, 2), [110.0, 100.0]),
        "SMA200": np.full((T, 2), [110.0, 100.0]),
        "ATR": atr_data,
        "RSI2": rsi2_data,
        "RS_Alpha": rs_alpha_data,
        "Turnover": np.full((T, 2), 2_000_000_000.0),
        "BB_LOWER_2": np.full((T, 2), [95.0, 95.0]),
        "tickers": tickers,
    }

    final_assets, trade_count, monthly, results, trade_log = run_backtest_v16_production(
        univ_indices=np.array([0]),
        bundle_np=bundle_np,
        timeline=dates,
        breadth_ratio=np.ones(len(dates)) * 0.12,
        initial_cash=1_000_000,
        max_pos=1,
        slippage=0.0,
        leverage_rate=1.0,
        breadth_threshold=0.3,
        return_trade_log=True,
    )

    assert trade_count == 1
    assert final_assets > 1_000_000
    assert results[0] > 0
    assert trade_log[0]["setup_type"] == "inverse_rebreak"


def test_daytrade_can_trade_strong_oversold_in_bull_market():
    T = 104
    dates = pd.date_range("2023-12-31", periods=T)
    tickers = ["9000.T", "1321.T"]

    close_data = np.full((T, 2), [100.0, 100.0])
    open_data = np.full((T, 2), [100.0, 100.0])
    high_data = np.full((T, 2), [101.0, 101.0])
    low_data = np.full((T, 2), [99.0, 99.0])
    atr_data = np.full((T, 2), 2.0)
    rsi2_data = np.full((T, 2), [20.0, 50.0])
    rs_alpha_data = np.full((T, 2), [15.0, 0.0])

    close_data[100] = [103.5, 100.0]
    open_data[100] = [103.0, 100.0]
    high_data[100] = [103.8, 101.0]
    low_data[100] = [102.8, 99.5]

    close_data[101] = [103.0, 101.0]
    open_data[101] = [103.2, 101.0]
    high_data[101] = [103.4, 101.5]
    low_data[101] = [102.9, 100.8]
    rsi2_data[101] = [1.5, 50.0]

    open_data[102] = [100.0, 101.5]
    close_data[102] = [102.8, 102.0]
    high_data[102] = [103.2, 102.2]
    low_data[102] = [99.8, 101.2]

    bundle_np = {
        "Close": close_data,
        "Open": open_data,
        "High": high_data,
        "Low": low_data,
        "SMA5": np.full((T, 2), [99.0, 100.0]),
        "SMA20": np.full((T, 2), [98.0, 100.0]),
        "SMA100": np.full((T, 2), [96.0, 100.0]),
        "SMA200": np.full((T, 2), [95.0, 100.0]),
        "ATR": atr_data,
        "RSI2": rsi2_data,
        "RS_Alpha": rs_alpha_data,
        "Turnover": np.full((T, 2), 2_000_000_000.0),
        "BB_LOWER_2": np.full((T, 2), [94.0, 95.0]),
        "tickers": tickers,
    }

    final_assets, trade_count, monthly, results = run_backtest_v16_production(
        univ_indices=np.array([0]),
        bundle_np=bundle_np,
        timeline=dates,
        breadth_ratio=np.ones(len(dates)) * 0.8,
        initial_cash=1_000_000,
        max_pos=1,
        slippage=0.0,
        leverage_rate=1.0,
        breadth_threshold=0.3,
    )

    assert trade_count == 1
    assert final_assets > 1_000_000
    assert results[0] > 0


def test_daytrade_strong_oversold_tuesday_stretched_open_is_filtered_in_backtest():
    T = 104
    dates = pd.date_range("2024-01-05", periods=T, freq="B")
    tickers = ["9000.T", "1321.T"]

    close_data = np.full((T, 2), [100.0, 100.0])
    open_data = np.full((T, 2), [100.0, 100.0])
    high_data = np.full((T, 2), [101.0, 101.0])
    low_data = np.full((T, 2), [99.0, 99.0])
    atr_data = np.full((T, 2), 2.0)
    rsi2_data = np.full((T, 2), [20.0, 50.0])
    rs_alpha_data = np.full((T, 2), [15.0, 0.0])

    close_data[100] = [103.5, 100.0]
    open_data[100] = [103.0, 100.0]
    high_data[100] = [103.8, 101.0]
    low_data[100] = [102.8, 99.5]

    close_data[101] = [103.0, 101.0]
    open_data[101] = [103.2, 101.0]
    high_data[101] = [103.4, 101.5]
    low_data[101] = [102.9, 100.8]
    rsi2_data[101] = [1.5, 50.0]

    open_data[102] = [100.0, 101.5]
    close_data[102] = [102.8, 102.0]
    high_data[102] = [103.2, 102.2]
    low_data[102] = [99.8, 101.2]

    bundle_np = {
        "Close": close_data,
        "Open": open_data,
        "High": high_data,
        "Low": low_data,
        "SMA5": np.full((T, 2), [99.0, 100.0]),
        "SMA20": np.full((T, 2), [98.0, 100.0]),
        "SMA100": np.full((T, 2), [96.0, 100.0]),
        "SMA200": np.full((T, 2), [95.0, 100.0]),
        "ATR": atr_data,
        "RSI2": rsi2_data,
        "RS_Alpha": rs_alpha_data,
        "Turnover": np.full((T, 2), 2_000_000_000.0),
        "BB_LOWER_2": np.full((T, 2), [94.0, 95.0]),
        "tickers": tickers,
    }

    final_assets, trade_count, monthly, results = run_backtest_v16_production(
        univ_indices=np.array([0]),
        bundle_np=bundle_np,
        timeline=dates,
        breadth_ratio=np.ones(len(dates)) * 0.8,
        initial_cash=1_000_000,
        max_pos=1,
        slippage=0.0,
        leverage_rate=1.0,
        breadth_threshold=0.3,
    )

    assert trade_count == 0
    assert final_assets == 1_000_000
    assert results == []


def test_monthly_rotation_can_hold_a_winner():
    T = 260
    dates = pd.date_range("2024-01-01", periods=T, freq="B")
    tickers = ["AAA.T", "BBB.T", "CCC.T", "1321.T"]

    close_data = np.column_stack([
        np.linspace(100, 220, T),  # strongest trend
        np.linspace(100, 140, T),
        np.linspace(100, 110, T),
        np.linspace(100, 180, T),  # market proxy
    ])

    bundle_np = {
        "Close": close_data,
        "RS_Alpha": np.column_stack([
            np.full(T, 80.0),
            np.full(T, 40.0),
            np.full(T, 20.0),
            np.full(T, 0.0),
        ]),
        "Turnover": np.full((T, len(tickers)), 2_000_000_000.0),
        "ATR": np.full((T, len(tickers)), 2.0),
        "SMA100": close_data * 0.9,
        "SMA200": close_data * 0.85,
        "tickers": tickers,
    }

    final_assets, trade_count, monthly, results = run_backtest_v19_monthly_rotation(
        univ_indices=np.array([0, 1, 2]),
        bundle_np=bundle_np,
        timeline=dates,
        breadth_ratio=np.ones(T),
        initial_cash=1_000_000,
        max_pos=1,
        leverage_rate=1.0,
        breadth_threshold=0.4,
        slippage=0.0,
        min_turnover=1_000_000_000.0,
        rs_min=0.0,
        annual_margin_interest_rate=0.0,
    )

    assert trade_count > 0
    assert final_assets > 1_000_000


def test_monthly_rotation_keeps_same_leader_without_monthly_churn():
    T = 260
    dates = pd.date_range("2024-01-01", periods=T, freq="B")
    tickers = ["AAA.T", "1321.T"]

    close_data = np.column_stack([
        np.linspace(100, 240, T),
        np.linspace(100, 180, T),
    ])

    bundle_np = {
        "Close": close_data,
        "RS_Alpha": np.column_stack([
            np.full(T, 80.0),
            np.zeros(T),
        ]),
        "Turnover": np.full((T, len(tickers)), 2_000_000_000.0),
        "ATR": np.full((T, len(tickers)), 2.0),
        "SMA20": close_data * 0.98,
        "SMA100": close_data * 0.9,
        "SMA200": close_data * 0.85,
        "tickers": tickers,
    }

    final_assets, trade_count, monthly, results = run_backtest_v19_monthly_rotation(
        univ_indices=np.array([0]),
        bundle_np=bundle_np,
        timeline=dates,
        breadth_ratio=np.ones(T),
        initial_cash=1_000_000,
        max_pos=1,
        leverage_rate=1.0,
        breadth_threshold=0.4,
        slippage=0.0,
        min_turnover=1_000_000_000.0,
        rs_min=0.0,
        annual_margin_interest_rate=0.0,
    )

    assert final_assets > 1_000_000
    assert trade_count == 1
    assert len(results) == 1


def test_monthly_rotation_prod_config_runs_on_synthetic_data():
    T = 260
    dates = pd.date_range("2024-01-01", periods=T, freq="B")
    tickers = ["AAA.T", "BBB.T", "CCC.T", "1321.T"]

    close_data = np.column_stack([
        np.linspace(100, 240, T),
        np.linspace(100, 170, T),
        np.linspace(100, 130, T),
        np.linspace(100, 180, T),
    ])

    bundle_np = {
        "Close": close_data,
        "RS_Alpha": np.column_stack([
            np.full(T, 80.0),
            np.full(T, 45.0),
            np.full(T, 20.0),
            np.zeros(T),
        ]),
        "Turnover": np.full((T, len(tickers)), 2_000_000_000.0),
        "ATR": np.full((T, len(tickers)), 2.0),
        "SMA20": close_data * 0.98,
        "SMA100": close_data * 0.9,
        "SMA200": close_data * 0.85,
        "tickers": tickers,
    }

    params = get_prod_monthly_rotation_backtest_params()
    final_assets, trade_count, monthly, results = run_backtest_v19_monthly_rotation(
        univ_indices=np.array([0, 1, 2]),
        bundle_np=bundle_np,
        timeline=dates,
        breadth_ratio=np.ones(T),
        initial_cash=1_000_000,
        slippage=0.0,
        annual_margin_interest_rate=0.0,
        **params,
    )

    assert trade_count > 0
    assert final_assets > 1_000_000


def test_monthly_rotation_margin_interest_reduces_equity():
    T = 260
    dates = pd.date_range("2024-01-01", periods=T, freq="B")
    tickers = ["AAA.T", "1321.T"]

    close_data = np.column_stack([
        np.linspace(100, 200, T),
        np.linspace(100, 150, T),
    ])
    open_data = close_data.copy()

    bundle_np = {
        "Open": open_data,
        "Close": close_data,
        "RS_Alpha": np.column_stack([
            np.full(T, 80.0),
            np.zeros(T),
        ]),
        "Turnover": np.full((T, len(tickers)), 2_000_000_000.0),
        "ATR": np.full((T, len(tickers)), 2.0),
        "SMA20": close_data * 0.98,
        "SMA100": close_data * 0.9,
        "SMA200": close_data * 0.85,
        "tickers": tickers,
    }

    no_interest, *_ = run_backtest_v19_monthly_rotation(
        univ_indices=np.array([0]),
        bundle_np=bundle_np,
        timeline=dates,
        breadth_ratio=np.ones(T),
        initial_cash=1_000_000,
        max_pos=1,
        leverage_rate=1.0,
        breadth_threshold=0.4,
        slippage=0.0,
        min_turnover=1_000_000_000.0,
        rs_min=0.0,
        tax_rate=0.0,
        annual_margin_interest_rate=0.0,
    )

    with_interest, *_ = run_backtest_v19_monthly_rotation(
        univ_indices=np.array([0]),
        bundle_np=bundle_np,
        timeline=dates,
        breadth_ratio=np.ones(T),
        initial_cash=1_000_000,
        max_pos=1,
        leverage_rate=1.0,
        breadth_threshold=0.4,
        slippage=0.0,
        min_turnover=1_000_000_000.0,
        rs_min=0.0,
        tax_rate=0.0,
        annual_margin_interest_rate=0.0279,
    )

    assert with_interest < no_interest
