from dataclasses import fields

import numpy as np
import pytest

from core.daytrade_candidate_engine import (
    DaytradeOpenArrayView,
    generate_daytrade_candidate_groups,
)
from core.logic import build_daytrade_open_market_context


def _open_view(values):
    base = np.asarray(values, dtype=float)
    return DaytradeOpenArrayView(
        tickers=["1000.T"],
        universe_indices=np.array([0], dtype=int),
        open_today=base[:1],
        close_prev=base[1:2],
        close_prev2=base[2:3],
        open_prev=base[3:4],
        low_prev=base[4:5],
        atr_prev=base[5:6],
        turnover_prev=base[6:7],
        rsi2_prev=base[7:8],
        rs_alpha_prev=base[8:9],
        sma_med_prev=base[9:10],
        sma_trend_prev=base[10:11],
    )


def test_daytrade_open_array_view_excludes_same_day_future_fields_and_keeps_views():
    field_names = {field.name for field in fields(DaytradeOpenArrayView)}
    assert {"close_today", "high_today", "low_today", "volume_today"}.isdisjoint(field_names)

    source = np.arange(11.0)
    snapshot = _open_view(source)
    assert np.shares_memory(snapshot.open_today, source)
    assert np.shares_memory(snapshot.sma_trend_prev, source)


def test_daytrade_open_array_view_rejects_non_point_in_time_shapes():
    source = np.arange(11.0)
    kwargs = {
        field.name: getattr(_open_view(source), field.name)
        for field in fields(DaytradeOpenArrayView)
    }
    kwargs["open_today"] = np.ones((1, 1))

    with pytest.raises(ValueError, match="one-dimensional"):
        DaytradeOpenArrayView(**kwargs)


def test_candidate_engine_accepts_prior_features_and_today_open_only():
    snapshot = _open_view(
        [
            np.nan,
            100.0,
            99.0,
            99.5,
            98.5,
            2.0,
            1_000_000_000.0,
            50.0,
            20.0,
            95.0,
            90.0,
        ]
    )
    market = build_daytrade_open_market_context(
        trade_date="2026-07-13",
        feature_asof="2026-07-10",
        open_asof="2026-07-13",
        breadth_val=0.60,
        market_open=2_800.0,
        prev_market_close=2_790.0,
        prev_market_sma_trend=2_700.0,
    )

    result = generate_daytrade_candidate_groups(
        snapshot,
        market,
        liquidity_limit=0.025,
        bull_gap_limit=0.03,
        rsi_threshold=100.0,
    )

    assert result.scan_stats["universe"] == 1
    assert result.scan_stats["raw_nan"] == 1
    assert not any(
        (
            result.primary,
            result.strong_oversold,
            result.fallback,
            result.catchup,
            result.inverse,
            result.bull_etf,
        )
    )
