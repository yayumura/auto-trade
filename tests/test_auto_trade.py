import numpy as np
import pandas as pd
from unittest.mock import patch

from auto_trade import build_daytrade_position_record, compute_daytrade_snapshot, is_inverse_only_candidate_set
from core.logic import RealtimeBuffer, resolve_daytrade_live_exit_decision


def _build_snapshot_df():
    dates = pd.date_range("2024-01-01", periods=30)
    tickers = ["1000.T", "1321.T"]
    fields = ["Open", "High", "Low", "Close", "Volume"]
    columns = pd.MultiIndex.from_tuples((ticker, field) for ticker in tickers for field in fields)

    rows = []
    for idx in range(len(dates)):
        row = []
        for ticker_offset in (0.0, 10.0):
            base = 100.0 + ticker_offset + idx
            row.extend([base - 0.5, base + 1.0, base - 1.0, base, 1_000_000.0])
        rows.append(row)
    return pd.DataFrame(rows, index=dates, columns=columns)


def test_compute_daytrade_snapshot_calculates_breadth_without_name_error():
    data_df = _build_snapshot_df()
    symbols_df = pd.DataFrame({"コード": ["1000", "1321"], "銘柄名": ["Foo", "Bar"]})

    with patch("auto_trade.SMA_LONG_PERIOD", 5), \
         patch("auto_trade.get_prime_tickers", return_value=["1000.T", "1321.T"]), \
         patch("auto_trade.select_best_candidates", return_value=[{"code": "1000", "price": 120.0}]):
        snapshot = compute_daytrade_snapshot(
            data_df=data_df,
            symbols_df=symbols_df,
            targets=["1000", "1321"],
            regime="bull",
        )

    assert snapshot["top_candidates"][0]["code"] == "1000"
    assert snapshot["breadth"] == 1.0
    assert snapshot["latest_close_map"]["1000"] > 0


def test_inverse_only_candidate_set_accepts_inverse_pullback():
    assert is_inverse_only_candidate_set([{"setup_type": "inverse_pullback"}])
    assert is_inverse_only_candidate_set(
        [{"setup_type": "inverse"}, {"setup_type": "inverse_pullback"}]
    )
    assert not is_inverse_only_candidate_set([{"setup_type": "inverse_pullback"}, {"setup_type": "fallback"}])
    assert not is_inverse_only_candidate_set([])


def test_build_daytrade_position_record_preserves_setup_and_risk_context():
    record = build_daytrade_position_record(
        {
            "code": "1000",
            "name": "Foo",
            "setup_type": "primary",
            "atr": 2.0,
            "stop_mult": 1.0,
            "target_mult": 1.5,
            "candidate_rank": 3,
            "breadth": 0.62,
            "market_ratio": 1.05,
            "gap_pct": 0.004,
            "prev_return": 0.03,
            "open_vs_sma_atr": 1.2,
            "score": 8.4,
            "rs_alpha": 42.0,
            "prev_rsi2": 63.0,
        },
        executed_price=105.0,
        shares=300,
        buy_time="2026-04-21 09:03:00",
    )

    assert record["setup_type"] == "primary"
    assert record["entry_stop_price"] == 103.0
    assert record["entry_target_price"] == 108.0
    assert record["entry_candidate_rank"] == 3
    assert record["buy_rs"] == 42.0
    assert record["buy_rsi2"] == 63.0


def test_daytrade_primary_failed_runup_exit_uses_live_session_high():
    record = build_daytrade_position_record(
        {
            "code": "1000",
            "setup_type": "primary",
            "atr": 2.0,
            "stop_mult": 1.0,
            "target_mult": 1.5,
        },
        executed_price=105.0,
        shares=300,
        buy_time="2026-04-21 09:03:00",
    )

    buffer = RealtimeBuffer("1000")
    buffer.update(
        104.8,
        1_000,
        pd.Timestamp("2026-04-21 10:00:00"),
        open_price=105.0,
        high_price=107.6,
        low_price=104.6,
    )

    exit_price, exit_reason = resolve_daytrade_live_exit_decision(
        setup_type=record["setup_type"],
        buy_price=record["buy_price"],
        open_price=buffer.get_session_open(),
        high_price=buffer.get_session_high(),
        low_price=buffer.get_session_low(),
        current_price=buffer.get_latest_price(),
        stop_price=record["entry_stop_price"],
        target_price=record["entry_target_price"],
        session_high=buffer.get_session_high(),
        allow_close_exit=False,
    )

    assert exit_reason == "intraday_failed_runup"
    assert exit_price == record["buy_price"]
