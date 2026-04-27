import numpy as np
import pandas as pd

from backtest import run_backtest_v16_production, run_backtest_v19_monthly_rotation
from core.monthly_rotation_strategy import get_prod_monthly_rotation_backtest_params


def _build_daytrade_bundle(exit_mode="close"):
    T = 110
    dates = pd.date_range("2024-01-01", periods=T)

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
        close_data[102, 0] = 106.5
        high_data[102, 0] = 106.8
        low_data[102, 0] = 104.8
    elif exit_mode == "stop":
        close_data[102, 0] = 103.0
        high_data[102, 0] = 105.1
        low_data[102, 0] = 102.8
    elif exit_mode == "target":
        close_data[102, 0] = 108.5
        high_data[102, 0] = 109.2
        low_data[102, 0] = 104.8
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


def _run_single_trade_backtest(exit_mode):
    dates, bundle_np = _build_daytrade_bundle(exit_mode=exit_mode)
    return run_backtest_v16_production(
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
    )


def _run_single_trade_backtest_with_costs(exit_mode, **kwargs):
    dates, bundle_np = _build_daytrade_bundle(exit_mode=exit_mode)
    return run_backtest_v16_production(
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
    assert "2024-04-12" in daily_stats
    assert daily_stats["2024-04-12"]["day_pnl"] > 0
    assert daily_stats["2024-04-12"]["trade_count"] == 1


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
