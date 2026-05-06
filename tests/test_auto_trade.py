import numpy as np
import pandas as pd
from unittest.mock import patch

from auto_trade import compute_daytrade_snapshot, is_inverse_only_candidate_set


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
