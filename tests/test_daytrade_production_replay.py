import csv
from datetime import datetime

from core.config import JST
from core.daytrade_production_replay import (
    append_daytrade_production_snapshot,
    build_daytrade_production_snapshot,
    canonical_daytrade_digest,
    find_first_daytrade_production_snapshot,
    load_daytrade_production_snapshots,
    replay_daytrade_production_snapshot,
)
from jp_production_replay import run_production_replay


def _symbol(code, open_today, *, opening_time="2026-07-13T09:00:00+09:00"):
    offset = 10.0 if code == "1321" else 0.0
    return {
        "code": code,
        "opening_price_timestamp": opening_time,
        "open_today": open_today + offset,
        "close_prev": 100.0 + offset,
        "close_prev2": 99.0 + offset,
        "open_prev": 99.5 + offset,
        "low_prev": 98.0 + offset,
        "atr_prev": 2.0,
        "turnover_prev": 1_000_000_000.0,
        "rsi2_prev": 50.0,
        "rs_alpha_prev": 20.0,
        "sma_med_prev": 95.0 + offset,
        "sma_trend_prev": 90.0 + offset,
    }


def _snapshot(**overrides):
    values = {
        "trade_date": "2026-07-13",
        "feature_asof": "2026-07-10",
        "open_asof": "2026-07-13",
        "captured_at": datetime(2026, 7, 13, 9, 30, tzinfo=JST),
        "trade_mode": "KABUCOM_LIVE",
        "is_simulation": False,
        "requested_codes": ["1000", "1321"],
        "symbol_inputs": [_symbol("1000", 100.5), _symbol("1321", 100.0)],
        "market_input": {
            "code": "1321",
            "breadth": 0.60,
            "open_today": 110.0,
            "close_prev": 110.0,
            "sma_trend_prev": 100.0,
            "market_ratio": 1.10,
        },
        "selector_context": {
            "current_equity": 1_000_000.0,
            "week_start_equity": 1_000_000.0,
            "account_cash": 1_000_000.0,
            "base_leverage": 1.25,
        },
        "strategy_context": {
            "liquidity_limit": 0.025,
            "bull_gap_limit": 0.03,
            "rsi_threshold": 100.0,
        },
        "execution_quotes": [
            {
                "code": "1000",
                "current_price": 101.0,
                "best_sell_price": 101.1,
                "session_high": 102.0,
                "session_low": 99.0,
                "volume": 100_000,
            }
        ],
        "code_commit_sha": "test-sha",
        "runtime_config_hash": "test-config",
    }
    values.update(overrides)
    return build_daytrade_production_snapshot(**values)


def test_production_snapshot_replays_with_exact_candidate_and_selector_parity():
    snapshot = _snapshot()
    replay = replay_daytrade_production_snapshot(snapshot)

    assert snapshot["decision_allowed"] is True
    assert snapshot["eligible_for_decision_clean_holdout"] is True
    assert replay.replayable is True
    assert replay.parity is True
    assert replay.candidate_digest == snapshot["recorded"]["candidate_digest"]
    assert replay.selected_digest == snapshot["recorded"]["selected_digest"]


def test_execution_quote_fields_do_not_change_signal_identity_or_output():
    first = _snapshot()
    second = _snapshot(
        execution_quotes=[
            {
                "code": "1000",
                "current_price": 300.0,
                "best_sell_price": 301.0,
                "session_high": 350.0,
                "session_low": 50.0,
                "volume": 9_999_999,
            }
        ]
    )

    assert first["snapshot_id"] == second["snapshot_id"]
    assert first["recorded"]["candidate_digest"] == second["recorded"]["candidate_digest"]
    assert first["recorded"]["selected_digest"] == second["recorded"]["selected_digest"]


def test_open_signal_change_changes_snapshot_identity():
    first = _snapshot()
    changed_symbols = [_symbol("1000", 102.0), _symbol("1321", 100.0)]
    second = _snapshot(symbol_inputs=changed_symbols)

    assert first["snapshot_id"] != second["snapshot_id"]


def test_invalid_point_in_time_snapshot_is_recorded_but_fail_closed():
    snapshot = _snapshot(
        feature_asof="2026-07-13",
        board_failures=[{"code": "1000", "reason": "transport"}],
    )
    replay = replay_daytrade_production_snapshot(snapshot)

    assert snapshot["decision_allowed"] is False
    assert snapshot["eligible_for_decision_clean_holdout"] is False
    assert "feature_asof_not_before_trade_date" in snapshot["rejection_reasons"]
    assert "1000:board_transport" in snapshot["rejection_reasons"]
    assert replay.replayable is False
    assert replay.parity is True
    assert replay.selected_codes == ()


def test_tampered_recorded_output_fails_parity():
    snapshot = _snapshot()
    snapshot["recorded"]["selected_digest"] = canonical_daytrade_digest(["tampered"])

    replay = replay_daytrade_production_snapshot(snapshot)

    assert replay.parity is False


def test_replay_rejects_code_or_runtime_config_mismatch():
    snapshot = _snapshot()

    replay = replay_daytrade_production_snapshot(
        snapshot,
        expected_code_commit_sha="different-sha",
        expected_runtime_config_hash="different-config",
    )

    assert replay.replayable is False
    assert replay.parity is False
    assert replay.rejection_reasons == (
        "code_commit_sha_mismatch",
        "runtime_config_hash_mismatch",
    )


def test_jsonl_round_trip_and_first_snapshot_lookup(tmp_path):
    path = tmp_path / "snapshots.jsonl"
    snapshot = _snapshot()
    append_daytrade_production_snapshot(path, snapshot)

    loaded = load_daytrade_production_snapshots(path)
    found = find_first_daytrade_production_snapshot(
        path,
        trade_date="2026-07-13",
        trade_mode="KABUCOM_LIVE",
    )

    assert loaded == [snapshot]
    assert found == snapshot


def test_production_replay_cli_summary_links_actual_exit(tmp_path):
    snapshot_path = tmp_path / "snapshots.jsonl"
    exit_path = tmp_path / "exits.csv"
    snapshot = _snapshot()
    append_daytrade_production_snapshot(snapshot_path, snapshot)
    with exit_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("decision_snapshot_id", "is_simulation", "observed_pnl"),
        )
        writer.writeheader()
        writer.writerow({
            "decision_snapshot_id": snapshot["snapshot_id"],
            "is_simulation": False,
            "observed_pnl": 1234.0,
        })

    code, summary = run_production_replay(
        snapshots_file=snapshot_path,
        exit_log=exit_path,
        trade_mode="KABUCOM_LIVE",
        min_snapshots=1,
        expected_code_commit_sha="test-sha",
        expected_runtime_config_hash="test-config",
    )

    assert code == 0
    assert summary["snapshots"] == 1
    assert summary["parity"] == 1
    assert summary["linked_actual_exits"] == 1
    assert summary["observed_pnl"] == 1234.0
    assert summary["observed_gross_pnl"] == 1234.0


def test_kabucom_test_replay_links_execution_without_claiming_clean_holdout(tmp_path):
    snapshot_path = tmp_path / "snapshots.jsonl"
    exit_path = tmp_path / "exits.csv"
    snapshot = _snapshot(trade_mode="KABUCOM_TEST")
    append_daytrade_production_snapshot(snapshot_path, snapshot)
    with exit_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("decision_snapshot_id", "is_simulation", "observed_pnl"),
        )
        writer.writeheader()
        writer.writerow({
            "decision_snapshot_id": snapshot["snapshot_id"],
            "is_simulation": False,
            "observed_pnl": -250.0,
        })

    code, summary = run_production_replay(
        snapshots_file=snapshot_path,
        exit_log=exit_path,
        trade_mode="KABUCOM_TEST",
        min_snapshots=1,
        expected_code_commit_sha="test-sha",
        expected_runtime_config_hash="test-config",
    )

    assert code == 0
    assert summary["eligible_execution_replay"] == 1
    assert summary["eligible_decision_clean_holdout"] == 0
    assert summary["linked_actual_exits"] == 1
    assert summary["observed_gross_pnl"] == -250.0


def test_production_replay_requires_minimum_snapshot_count(tmp_path):
    code, summary = run_production_replay(
        snapshots_file=tmp_path / "missing.jsonl",
        exit_log=tmp_path / "missing.csv",
        trade_mode="KABUCOM_LIVE",
        min_snapshots=1,
        expected_code_commit_sha="test-sha",
        expected_runtime_config_hash="test-config",
    )

    assert code == 2
    assert summary["snapshots"] == 0
