import numpy as np
import pandas as pd
import pytest

from core.daytrade_observation_universe import (
    DAYTRADE_DISCOVERY_MAX_SYMBOLS,
    build_daytrade_production_observation_indices_by_day,
    build_daytrade_rotating_discovery_indices_by_day,
    normalize_daytrade_observation_code,
    select_daytrade_rotating_discovery_codes,
    select_daytrade_production_observation_codes,
)


def test_production_observation_selection_reserves_etfs_and_filters_fail_closed():
    observations = [
        {
            "ticker": "1000.T",
            "is_prime": True,
            "close": 100.0,
            "atr": 2.0,
            "turnover": 1_000_000_000.0,
        },
        {
            "ticker": "1570.T",
            "is_prime": False,
            "close": 10_000.0,
            "atr": 100.0,
            "turnover": 500_000_000.0,
        },
        {
            "ticker": "2000.T",
            "is_prime": False,
            "close": 100.0,
            "atr": 2.0,
            "turnover": 2_000_000_000.0,
        },
        {
            "ticker": "1321.T",
            "is_prime": True,
            "close": 30_000.0,
            "atr": 100.0,
            "turnover": 2_000_000_000.0,
        },
        {
            "ticker": "3000.T",
            "is_prime": True,
            "close": np.nan,
            "atr": 2.0,
            "turnover": 2_000_000_000.0,
        },
    ]

    selected = select_daytrade_production_observation_codes(
        observations,
        breadth=0.5,
        max_symbols=2,
        min_turnover_resolver=lambda _ticker, _breadth: 0.0,
    )

    assert selected == ["1570", "1000"]


def _build_observation_bundle():
    timeline = pd.date_range("2026-01-05", periods=4, freq="B")
    tickers = ["1000.T", "1570.T", "2000.T", "1321.T"]
    close = np.full((4, 4), [100.0, 10_000.0, 200.0, 30_000.0])
    return timeline, {
        "tickers": tickers,
        "Close": close,
        "Open": close.copy(),
        "Low": close * 0.99,
        "ATR": np.full((4, 4), [2.0, 100.0, 4.0, 200.0]),
        "Turnover": np.full((4, 4), 2_000_000_000.0),
        "RSI2": np.full((4, 4), 60.0),
        "RS_Alpha": np.full((4, 4), 30.0),
        "SMA20": close * 0.95,
        "SMA100": np.full((4, 4), [90.0, 9_000.0, 190.0, 29_000.0]),
        "SMA200": close * 0.90,
    }


def test_production_observation_mapping_uses_only_prior_day_features():
    timeline, bundle = _build_observation_bundle()
    baseline = build_daytrade_production_observation_indices_by_day(
        bundle_np=bundle,
        timeline=timeline,
        prime_tickers=("1000.T", "2000.T", "1321.T"),
        max_symbols=3,
    )

    same_day_changed = {
        key: (value.copy() if isinstance(value, np.ndarray) else value)
        for key, value in bundle.items()
    }
    same_day_changed["Close"][2] = np.nan
    same_day_changed["ATR"][2] = np.nan
    same_day_changed["Turnover"][2] = np.nan
    replay = build_daytrade_production_observation_indices_by_day(
        bundle_np=same_day_changed,
        timeline=timeline,
        prime_tickers=("1000.T", "2000.T", "1321.T"),
        max_symbols=3,
    )

    trade_day = str(timeline[2].date())
    assert baseline[trade_day] == replay[trade_day]
    assert baseline[trade_day][0] == 1
    assert 3 not in baseline[trade_day]


def test_production_observation_mapping_rejects_misaligned_arrays():
    timeline, bundle = _build_observation_bundle()
    bundle["ATR"] = bundle["ATR"][:-1]

    with pytest.raises(ValueError, match="identical shapes"):
        build_daytrade_production_observation_indices_by_day(
            bundle_np=bundle,
            timeline=timeline,
            prime_tickers=("1000.T",),
        )


def test_rotating_discovery_mapping_does_not_read_same_day_outcomes():
    timeline, bundle = _build_observation_bundle()
    baseline = build_daytrade_rotating_discovery_indices_by_day(
        bundle_np=bundle,
        timeline=timeline,
        prime_tickers=("1000.T", "2000.T"),
    )

    same_day_changed = {
        key: (value.copy() if isinstance(value, np.ndarray) else value)
        for key, value in bundle.items()
    }
    for field in (
        "Close",
        "Open",
        "Low",
        "ATR",
        "Turnover",
        "RSI2",
        "RS_Alpha",
        "SMA20",
        "SMA100",
        "SMA200",
    ):
        same_day_changed[field][2] = np.nan
    replay = build_daytrade_rotating_discovery_indices_by_day(
        bundle_np=same_day_changed,
        timeline=timeline,
        prime_tickers=("1000.T", "2000.T"),
    )

    trade_day = str(timeline[2].date())
    assert baseline[trade_day] == replay[trade_day]
    assert baseline[trade_day][0] == 1
    assert 3 not in baseline[trade_day]


def test_rotating_discovery_history_replay_delegates_to_one_day_selector():
    timeline, bundle = _build_observation_bundle()
    day_index = 2
    feature_index = day_index - 1
    selected = select_daytrade_rotating_discovery_codes(
        tickers=bundle["tickers"],
        trade_date=timeline[day_index],
        feature_asof=timeline[feature_index],
        close_prev=bundle["Close"][feature_index],
        close_prev2=bundle["Close"][day_index - 2],
        open_prev=bundle["Open"][feature_index],
        low_prev=bundle["Low"][feature_index],
        atr_prev=bundle["ATR"][feature_index],
        turnover_prev=bundle["Turnover"][feature_index],
        rsi2_prev=bundle["RSI2"][feature_index],
        rs_alpha_prev=bundle["RS_Alpha"][feature_index],
        sma_med_prev=bundle["SMA20"][feature_index],
        sma_long_prev=bundle["SMA100"][feature_index],
        sma_trend_prev=bundle["SMA200"][feature_index],
        prime_tickers=("1000.T", "2000.T"),
    )
    replay = build_daytrade_rotating_discovery_indices_by_day(
        bundle_np=bundle,
        timeline=timeline,
        prime_tickers=("1000.T", "2000.T"),
    )
    replay_codes = [
        normalize_daytrade_observation_code(bundle["tickers"][index])
        for index in replay[str(timeline[day_index].date())]
    ]

    assert replay_codes == selected


def test_one_day_rotating_discovery_rejects_misaligned_or_duplicate_features():
    timeline, bundle = _build_observation_bundle()
    kwargs = {
        "tickers": bundle["tickers"],
        "trade_date": timeline[2],
        "feature_asof": timeline[1],
        "close_prev": bundle["Close"][1],
        "close_prev2": bundle["Close"][0],
        "open_prev": bundle["Open"][1],
        "low_prev": bundle["Low"][1],
        "atr_prev": bundle["ATR"][1],
        "turnover_prev": bundle["Turnover"][1],
        "rsi2_prev": bundle["RSI2"][1],
        "rs_alpha_prev": bundle["RS_Alpha"][1],
        "sma_med_prev": bundle["SMA20"][1],
        "sma_long_prev": bundle["SMA100"][1],
        "sma_trend_prev": bundle["SMA200"][1],
        "prime_tickers": ("1000.T", "2000.T"),
    }
    with pytest.raises(ValueError, match="align with tickers"):
        select_daytrade_rotating_discovery_codes(**{**kwargs, "atr_prev": [1.0]})
    with pytest.raises(ValueError, match="unique after normalization"):
        select_daytrade_rotating_discovery_codes(
            **{**kwargs, "tickers": ["1000.T", "1000", "2000.T", "1321.T"]}
        )
    assert select_daytrade_rotating_discovery_codes(
        **{**kwargs, "trade_date": timeline[1]}
    ) == []


def test_rotating_discovery_policy_capacity_and_scenarios_are_not_tunable():
    timeline, bundle = _build_observation_bundle()

    with pytest.raises(ValueError, match="fixed by four 49-symbol"):
        build_daytrade_rotating_discovery_indices_by_day(
            bundle_np=bundle,
            timeline=timeline,
            prime_tickers=("1000.T",),
            max_symbols=DAYTRADE_DISCOVERY_MAX_SYMBOLS - 1,
        )
    with pytest.raises(ValueError, match="opening scenarios are fixed"):
        build_daytrade_rotating_discovery_indices_by_day(
            bundle_np=bundle,
            timeline=timeline,
            prime_tickers=("1000.T",),
            open_scenarios=(0.0,),
        )
