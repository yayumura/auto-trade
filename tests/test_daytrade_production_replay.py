import csv
import json
from hashlib import sha256
from datetime import datetime
from types import SimpleNamespace

from core.config import JST
from core.daytrade_production_replay import (
    append_daytrade_production_snapshot,
    DAYTRADE_OBSERVATION_POLICY_ROTATING_196,
    build_daytrade_production_snapshot,
    canonical_daytrade_digest,
    find_first_daytrade_production_snapshot,
    load_daytrade_production_snapshots,
    replay_daytrade_production_snapshot,
)
from jp_production_replay import (
    _actual_cost_evidence_reasons,
    _actual_net_evidence_reasons,
    _build_lifecycle_summary,
    _operational_evidence_reasons,
    run_production_replay,
    _entry_quote_evidence_reasons,
    _entry_risk_evidence_reasons,
    _entry_fill_evidence_reasons,
    _entry_order_risk_reasons,
    _opened_entry_risk_reasons,
    _protective_stop_risk_reasons,
    _exit_lifecycle_evidence_reasons,
)


def _symbol(
    code,
    open_today,
    *,
    opening_time="2026-07-13T09:00:00+09:00",
    previous_close_time="2026-07-10T00:00:00+09:00",
):
    offset = 10.0 if code == "1321" else 0.0
    return {
        "code": code,
        "opening_price_timestamp": opening_time,
        "previous_close_timestamp": previous_close_time,
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
        "board_batch_started_at": datetime(2026, 7, 13, 9, 29, 50, tzinfo=JST),
        "board_batch_completed_at": datetime(2026, 7, 13, 9, 30, tzinfo=JST),
        "trade_mode": "KABUCOM_LIVE",
        "is_simulation": False,
        "server_clock_evidence": {
            "schema_version": 1,
            "verified": True,
            "source": "wallet_cash_date_header",
            "reason": "verified",
            "server_time": "2026-07-13T09:29:49+09:00",
            "received_at": "2026-07-13T09:29:49+09:00",
            "fallback_time": "2026-07-13T09:29:49+09:00",
            "drift_seconds": 0.0,
            "max_abs_drift_seconds": 30.0,
        },
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


def _rotating_snapshot(*, mutate_evidence=None):
    codes = [str(2000 + index) for index in range(196)]
    started_at = datetime(2026, 7, 13, 9, 29, 35, tzinfo=JST)
    completed_at = datetime(2026, 7, 13, 9, 29, 50, tzinfo=JST)
    protected_started = datetime(2026, 7, 13, 9, 29, 36, tzinfo=JST)
    protected_completed = datetime(2026, 7, 13, 9, 29, 37, tzinfo=JST)
    batches = []
    for batch_index in range(4):
        requested = codes[batch_index * 49:(batch_index + 1) * 49]
        batch_started = datetime(
            2026, 7, 13, 9, 29, 38 + batch_index * 2, tzinfo=JST
        )
        batch_completed = datetime(
            2026, 7, 13, 9, 29, 40 + batch_index * 2, tzinfo=JST
        )
        batches.append({
            "batch_index": batch_index,
            "requested": requested,
            "register_ok": True,
            "board_requested": requested,
            "observed": sorted(requested),
            "failures": [],
            "unregister_ok": True,
            "started_at": batch_started.isoformat(),
            "completed_at": batch_completed.isoformat(),
        })
    evidence = {
        "requested": codes,
        "observed": sorted([*codes, "1321"]),
        "failures": [],
        "protected_board": {
            "requested": ["1321"],
            "board_requested": ["1321"],
            "observed": ["1321"],
            "failures": [],
            "started_at": protected_started.isoformat(),
            "completed_at": protected_completed.isoformat(),
        },
        "batches": batches,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "max_span_seconds": 30.0,
        "registry_clean": True,
        "final_registered_codes": ["1321"],
        "rejection_reasons": [],
    }
    if mutate_evidence is not None:
        mutate_evidence(evidence)
    return _snapshot(
        board_batch_started_at=started_at,
        board_batch_completed_at=completed_at,
        requested_codes=[*codes, "1321"],
        symbol_inputs=[
            *(_symbol(code, 100.5) for code in codes),
            _symbol("1321", 100.0),
        ],
        observation_policy=DAYTRADE_OBSERVATION_POLICY_ROTATING_196,
        opening_discovery_evidence=evidence,
    )


def _selected_snapshot():
    opening_time = "2026-07-15T09:00:00+09:00"
    previous_close_time = "2026-07-14T00:00:00+09:00"
    symbol = _symbol(
        "1000",
        99.0,
        opening_time=opening_time,
        previous_close_time=previous_close_time,
    )
    symbol["close_prev2"] = 103.0
    symbol["rsi2_prev"] = 0.0
    market = _symbol(
        "1321",
        100.0,
        opening_time=opening_time,
        previous_close_time=previous_close_time,
    )
    return _snapshot(
        trade_date="2026-07-15",
        feature_asof="2026-07-14",
        open_asof="2026-07-15",
        captured_at=datetime(2026, 7, 15, 9, 30, tzinfo=JST),
        board_batch_started_at=datetime(2026, 7, 15, 9, 29, 50, tzinfo=JST),
        board_batch_completed_at=datetime(2026, 7, 15, 9, 30, tzinfo=JST),
        server_clock_evidence={
            "schema_version": 1,
            "verified": True,
            "source": "wallet_cash_date_header",
            "reason": "verified",
            "server_time": "2026-07-15T09:29:49+09:00",
            "received_at": "2026-07-15T09:29:49+09:00",
            "fallback_time": "2026-07-15T09:29:49+09:00",
            "drift_seconds": 0.0,
            "max_abs_drift_seconds": 30.0,
        },
        symbol_inputs=[symbol, market],
    )


def _entry_quote_row(code, *, decision="entry_quote_refresh_passed"):
    return {
        "decision": decision,
        "reason": "" if decision == "entry_quote_refresh_passed" else "transport",
        "code": str(code),
        "entry_quote_evidence_schema_version": 1,
        "entry_quote_status": (
            "fresh" if decision == "entry_quote_refresh_passed" else "rejected"
        ),
        "entry_quote_code": str(code),
        "entry_quote_batch_started_at": "2026-07-15T09:30:00+09:00",
        "entry_quote_batch_completed_at": "2026-07-15T09:30:01+09:00",
        "entry_quote_batch_span_seconds": 1.0,
        "entry_quote_max_batch_span_seconds": 5,
        "entry_quote_price_timestamp_source": "bid_timestamp",
        "entry_quote_price_timestamp": "2026-07-15T09:29:55+09:00",
        "entry_quote_received_at": "2026-07-15T09:30:00.500000+09:00",
        "entry_quote_age_seconds": 6.0,
        "entry_quote_transport_age_seconds": 0.5,
        "entry_quote_max_age_seconds": 30,
        "entry_quote_current_price": 100.0,
        "entry_quote_best_sell_price": 101.0,
        "entry_quote_best_sell_qty": 300,
        "entry_quote_reason": (
            "" if decision == "entry_quote_refresh_passed" else "transport"
        ),
    }


def _entry_risk_row(code):
    return {
        "decision": "entry_risk_resolved",
        "reason": "",
        "code": str(code),
        "entry_risk_evidence_schema_version": 1,
        "entry_risk_status": "approved",
        "entry_risk_reason": "",
        "entry_risk_code": str(code),
        "entry_risk_current_equity": 1_000_000,
        "entry_risk_theoretical_buying_power": 5_000_000,
        "entry_risk_wallet_margin_buying_power": 5_000_000,
        "entry_risk_buying_power": 5_000_000,
        "entry_risk_dynamic_leverage": 1.0,
        "entry_risk_quote_price": 101.0,
        "entry_risk_sizing_price": 101.0,
        "entry_risk_stop_price": 90.0,
        "entry_risk_turnover": 1_000_000_000,
        "entry_risk_max_positions": 1,
        "entry_risk_raw_shares": 9_900,
        "entry_risk_shares": 7_400,
        "entry_risk_max_entry_price": 101.0,
        "entry_risk_notional_pct": 0.15,
        "entry_risk_equity_notional_pct": "",
        "entry_risk_risk_budget_pct": 0.10,
        "entry_risk_size_multiplier": 1.0,
    }


def test_production_snapshot_replays_with_exact_candidate_and_selector_parity():
    snapshot = _snapshot()
    replay = replay_daytrade_production_snapshot(snapshot)

    assert snapshot["decision_allowed"] is True
    assert snapshot["eligible_for_decision_clean_holdout"] is True
    assert replay.replayable is True
    assert replay.parity is True
    assert replay.candidate_digest == snapshot["recorded"]["candidate_digest"]
    assert replay.selected_digest == snapshot["recorded"]["selected_digest"]


def test_rotating_discovery_snapshot_requires_complete_batch_and_registry_evidence():
    snapshot = _rotating_snapshot()
    replay = replay_daytrade_production_snapshot(snapshot)

    assert snapshot["schema_version"] == 4
    assert snapshot["decision_allowed"] is True
    assert replay.replayable is True
    assert replay.parity is True


def test_rotating_discovery_snapshot_fails_closed_on_incomplete_observation_batch():
    def remove_observation(evidence):
        evidence["batches"][2]["observed"].pop()

    snapshot = _rotating_snapshot(mutate_evidence=remove_observation)
    replay = replay_daytrade_production_snapshot(snapshot)

    assert snapshot["decision_allowed"] is False
    assert (
        "opening_discovery_batch_2_observed_mismatch"
        in snapshot["rejection_reasons"]
    )
    assert replay.replayable is False
    assert replay.parity is True


def test_rotating_discovery_snapshot_fails_closed_on_dirty_registry_or_time_overlap():
    def corrupt_registry_and_time(evidence):
        evidence["registry_clean"] = False
        evidence["batches"][1]["started_at"] = evidence["batches"][0]["started_at"]

    snapshot = _rotating_snapshot(mutate_evidence=corrupt_registry_and_time)

    assert snapshot["decision_allowed"] is False
    assert "opening_discovery_registry_dirty" in snapshot["rejection_reasons"]
    assert "opening_discovery_batch_1_time_overlap" in snapshot["rejection_reasons"]



def test_rotating_discovery_snapshot_rejects_duplicate_or_protected_discovery_codes():
    def duplicate_observation(evidence):
        evidence["batches"][0]["observed"].append(
            evidence["batches"][0]["observed"][0]
        )

    duplicate = _rotating_snapshot(mutate_evidence=duplicate_observation)

    def include_protected(evidence):
        evidence["requested"][-1] = "1321"

    protected = _rotating_snapshot(mutate_evidence=include_protected)

    assert duplicate["decision_allowed"] is False
    assert (
        "opening_discovery_batch_0_observed_mismatch"
        in duplicate["rejection_reasons"]
    )
    assert protected["decision_allowed"] is False
    assert (
        "opening_discovery_requested_codes_invalid"
        in protected["rejection_reasons"]
    )


def test_rotating_discovery_snapshot_malformed_nested_evidence_fails_closed():
    def corrupt_nested_types(evidence):
        evidence["protected_board"] = 7
        evidence["batches"] = "not-a-batch-list"
        evidence["started_at"] = "2026-07-13T09:29:35"

    snapshot = _rotating_snapshot(mutate_evidence=corrupt_nested_types)
    replay = replay_daytrade_production_snapshot(snapshot)

    assert snapshot["decision_allowed"] is False
    assert (
        "opening_discovery_protected_evidence_invalid"
        in snapshot["rejection_reasons"]
    )
    assert "opening_discovery_batches_invalid" in snapshot["rejection_reasons"]
    assert "opening_discovery_timezone_not_jst" in snapshot["rejection_reasons"]
    assert replay.replayable is False
    assert replay.parity is True


def test_snapshot_mixed_timezone_batch_evidence_fails_closed_without_exception():
    snapshot = _snapshot(
        board_batch_started_at="2026-07-13T09:29:50",
    )

    assert snapshot["decision_allowed"] is False
    assert "board_batch_timezone_not_jst" in snapshot["rejection_reasons"]


def test_snapshot_server_clock_evidence_is_required_and_fail_closed():
    missing = _snapshot(server_clock_evidence={})
    unverified = _snapshot(
        server_clock_evidence={
            "schema_version": 1,
            "verified": False,
            "source": "local_clock_fallback",
            "reason": "wallet_cash_date_header_missing",
            "server_time": "2026-07-13T09:29:49+09:00",
            "received_at": "2026-07-13T09:29:49+09:00",
            "fallback_time": "2026-07-13T09:29:49+09:00",
            "drift_seconds": 0.0,
            "max_abs_drift_seconds": 30.0,
        }
    )
    stale_evidence = dict(_snapshot()["inputs"]["server_clock"])
    stale_evidence["received_at"] = "2026-07-13T09:30:20+09:00"
    stale_evidence["drift_seconds"] = -31.0
    stale = _snapshot(server_clock_evidence=stale_evidence)

    assert missing["decision_allowed"] is False
    assert "server_clock_unverified" in missing["rejection_reasons"]
    assert "server_clock_source_invalid" in missing["rejection_reasons"]
    assert unverified["decision_allowed"] is False
    assert "server_clock_unverified" in unverified["rejection_reasons"]
    assert "server_clock_source_invalid" in unverified["rejection_reasons"]
    assert stale["decision_allowed"] is False
    assert "server_clock_drift_exceeded" in stale["rejection_reasons"]
    assert "server_clock_received_after_snapshot" in stale["rejection_reasons"]


def test_replay_malformed_selector_input_fails_closed_without_exception():
    snapshot = _snapshot()
    snapshot["inputs"]["selector"] = 7
    decision_identity = {
        key: value
        for key, value in snapshot["inputs"].items()
        if key not in {"captured_at", "execution_quotes"}
    }
    snapshot["snapshot_id"] = canonical_daytrade_digest(decision_identity)[:32]

    replay = replay_daytrade_production_snapshot(snapshot)

    assert replay.replayable is False
    assert replay.parity is False
    assert "selector_input_invalid" in replay.rejection_reasons

def test_snapshot_rejects_unrequested_or_duplicate_symbol_inputs():
    unrequested = _snapshot(
        symbol_inputs=[
            _symbol("1000", 100.5),
            _symbol("1321", 100.0),
            _symbol("9999", 100.5),
        ]
    )
    duplicate = _snapshot(
        symbol_inputs=[
            _symbol("1000", 100.5),
            _symbol("1000", 100.5),
            _symbol("1321", 100.0),
        ]
    )

    assert unrequested["decision_allowed"] is False
    assert (
        "unrequested_symbol_inputs_present:9999"
        in unrequested["rejection_reasons"]
    )
    assert duplicate["decision_allowed"] is False
    assert "symbol_inputs_duplicate" in duplicate["rejection_reasons"]


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


def test_snapshot_fails_closed_on_batch_span_and_previous_close_date_mismatch():
    symbols = [_symbol("1000", 100.5), _symbol("1321", 100.0)]
    symbols[0]["previous_close_timestamp"] = "2026-07-09T00:00:00+09:00"
    snapshot = _snapshot(
        board_batch_started_at=datetime(2026, 7, 13, 9, 29, tzinfo=JST),
        board_batch_completed_at=datetime(2026, 7, 13, 9, 30, tzinfo=JST),
        captured_at=datetime(2026, 7, 13, 9, 29, 59, tzinfo=JST),
        symbol_inputs=symbols,
    )
    replay = replay_daytrade_production_snapshot(snapshot)

    assert snapshot["decision_allowed"] is False
    assert "board_batch_span_exceeded" in snapshot["rejection_reasons"]
    assert "snapshot_captured_before_batch_completed" in snapshot["rejection_reasons"]
    assert "1000:previous_close_timestamp_not_feature_asof" in snapshot["rejection_reasons"]
    assert replay.replayable is False
    assert replay.parity is True



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
    assert summary["linked_net_actual_exits"] == 0
    assert summary["net_cost_incomplete_exits"] == 1
    assert summary["observed_net_pnl"] is None


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
    assert summary["linked_net_actual_exits"] == 0
    assert summary["observed_net_pnl"] is None


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

def test_production_replay_strict_lifecycle_requires_linked_decision_and_orders(tmp_path):
    snapshot_path = tmp_path / "snapshots.jsonl"
    exit_path = tmp_path / "exits.csv"
    snapshot = _selected_snapshot()
    append_daytrade_production_snapshot(snapshot_path, snapshot)

    code, summary = run_production_replay(
        snapshots_file=snapshot_path,
        exit_log=exit_path,
        decision_log=tmp_path / "missing-decisions.csv",
        order_journal=tmp_path / "missing-journal.jsonl",
        trade_mode="KABUCOM_LIVE",
        min_snapshots=1,
        require_complete_lifecycle=True,
        expected_code_commit_sha="test-sha",
        expected_runtime_config_hash="test-config",
    )

    assert replay_daytrade_production_snapshot(snapshot).selected_codes
    assert code == 4
    assert summary["lifecycle_incomplete_snapshots"] == 1
    assert "missing_linked_decision:1" in summary["lifecycle_incomplete_reasons"]


def test_strict_lifecycle_requires_entry_quote_evidence_before_sizing():
    result = SimpleNamespace(
        parity=True,
        replayable=True,
        snapshot_id="snapshot-1",
        selected_codes=("1000",),
    )
    summary = _build_lifecycle_summary(
        [result],
        [
            {
                "decision_snapshot_id": "snapshot-1",
                "decision": "selected_for_sizing",
                "code": "1000",
            }
        ],
        [],
        [],
    )

    assert summary["lifecycle_incomplete_snapshots"] == 1
    assert (
        "missing_entry_quote_evidence:1"
        in summary["lifecycle_incomplete_reasons"]
    )


def test_production_replay_strict_lifecycle_accepts_flat_linked_actual_exit(tmp_path):
    snapshot_path = tmp_path / "snapshots.jsonl"
    decision_path = tmp_path / "decisions.csv"
    journal_path = tmp_path / "order_journal.jsonl"
    exit_path = tmp_path / "exits.csv"
    snapshot = _selected_snapshot()
    snapshot_id = snapshot["snapshot_id"]
    append_daytrade_production_snapshot(snapshot_path, snapshot)

    selected_code = replay_daytrade_production_snapshot(snapshot).selected_codes[0]
    empty_hash = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    decision_rows = [
        {
            "decision_snapshot_id": snapshot_id,
            "is_simulation": False,
            "trade_mode": "KABUCOM_LIVE",
            "decision": "operational_review_passed",
            "reason": "no_recent_news",
            "code": selected_code,
            "operational_evidence_schema_version": 1,
            "news_fetch_status": "no_news",
            "news_query_url": "https://example.test/news",
            "news_text": "",
            "news_sha256": empty_hash,
            "news_error": "",
            "ai_outcome": "not_requested_no_news",
            "ai_provider": "",
            "ai_model": "",
            "ai_prompt": "",
            "ai_prompt_sha256": empty_hash,
            "ai_raw_response": "",
            "ai_raw_response_sha256": empty_hash,
            "ai_error": "",
        },
        {
            "decision_snapshot_id": snapshot_id,
            "is_simulation": False,
            "trade_mode": "KABUCOM_LIVE",
            **_entry_quote_row(selected_code),
        },
        {
            "decision_snapshot_id": snapshot_id,
            "is_simulation": False,
            "trade_mode": "KABUCOM_LIVE",
            **_entry_risk_row(selected_code),
        },
        {
            "decision_snapshot_id": snapshot_id,
            "is_simulation": False,
            "trade_mode": "KABUCOM_LIVE",
            "decision": "opened_live",
            "code": selected_code,
            "shares": 7_400,
            "entry_price": 101.0,
        },
    ]
    fieldnames = tuple(
        dict.fromkeys(
            key
            for row in decision_rows
            for key in row
        )
    )
    with decision_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(decision_rows)

    journal_events = [
        {
            "decision_snapshot_id": snapshot_id,
            "lifecycle_stage": "entry",
            "event": "PLANNED",
            "intent_id": "entry-1",
            "symbol": selected_code,
            "side": "2",
            "price": 101.0,
            "qty": 7_400,
            "entry_risk_evidence_schema_version": 1,
            "entry_sizing_price": 101.0,
            "entry_price_ceiling": 101.0,
            "entry_sizing_shares": 7_400,
        },
        {
            "decision_snapshot_id": snapshot_id,
            "lifecycle_stage": "entry",
            "event": "ACCEPTED",
            "intent_id": "entry-1",
            "order_id": "ENTRY-1",
            "symbol": selected_code,
            "side": "2",
            "price": 101.0,
            "qty": 7_400,
            "entry_risk_evidence_schema_version": 1,
            "entry_sizing_price": 101.0,
            "entry_price_ceiling": 101.0,
            "entry_sizing_shares": 7_400,
        },
        {
            "decision_snapshot_id": snapshot_id,
            "lifecycle_stage": "entry",
            "event": "FILLED",
            "intent_id": "entry-1",
            "order_id": "ENTRY-1",
            "symbol": selected_code,
            "side": "2",
            "order_ids": ["ENTRY-1"],
            "execution_ids": ["ENTRY-EX-1"],
            "execution_id": "ENTRY-EX-1",
            "execution_evidence_schema_version": 1,
            "aggregate_execution": True,
            "requested_qty": 7_400,
            "qty": 7_400,
            "filled_qty": 7_400,
            "remaining_qty": 0,
            "average_price": 101.0,
            "average_fill_price": 101.0,
            "process_state": "terminal",
            "terminal_reason": "filled",
            "submission_status": "accepted",
        },
        {
            "decision_snapshot_id": snapshot_id,
            "lifecycle_stage": "protective_stop",
            "event": "ACCEPTED",
            "intent_id": "stop-1",
            "order_id": "STOP-1",
            "kind": "stop",
            "symbol": selected_code,
            "side": "1",
            "qty": 7_400,
            "trigger_price": 90.0,
            "confirmed": True,
            "confirmation_reason": "orders_api_confirmed",
            "confirmation_evidence_schema_version": 1,
            "exchange": 1,
            "margin_trade_type": 3,
            "expected_close_positions": [{"HoldID": "HOLD-1", "Qty": 7_400}],
            "confirmation_details": {
                "response_shape_version": 2,
                "requested_order_id": "STOP-1",
                "order_id": "STOP-1",
                "symbol": selected_code,
                "details_present": True,
                "process_state": "active",
                "terminal_reason": None,
                "order_qty": 7_400,
                "cumulative_qty": 0,
                "remaining_qty": 7_400,
                "side": "1",
                "cash_margin": 3,
                "deliv_type": 2,
                "exchange": 1,
                "margin_trade_type": 3,
                "trigger_price": 90.0,
                "expected_qty": 7_400,
                "expected_trigger_price": 90.0,
                "close_positions": [{"HoldID": "HOLD-1", "Qty": 7_400}],
                "close_positions_match": True,
                "reverse_limit": {
                    "TriggerSec": 1, "TriggerPrice": 90.0, "UnderOver": 1,
                    "AfterHitOrderType": 1, "AfterHitPrice": 0,
                },
                "has_partial_fill": False,
                "is_consistent": True,
                "mismatch_reason": "confirmed",
            },
        },
        {
            "decision_snapshot_id": snapshot_id,
            "lifecycle_stage": "exit",
            "event": "ACCEPTED",
            "intent_id": "exit-1",
            "order_id": "EXIT-1",
            "symbol": selected_code,
            "side": "1",
            "qty": 7_400,
        },
        {
            "decision_snapshot_id": snapshot_id,
            "lifecycle_stage": "exit",
            "event": "FILLED",
            "intent_id": "exit-1",
            "order_id": "EXIT-1",
            "order_ids": ["EXIT-1"],
            "symbol": selected_code,
            "side": "1",
            "execution_ids": ["EXIT-EX-1"],
            "execution_id": "EXIT-EX-1",
            "execution_evidence_schema_version": 1,
            "aggregate_execution": True,
            "requested_qty": 7_400,
            "qty": 7_400,
            "filled_qty": 7_400,
            "remaining_qty": 0,
            "average_price": 101.1,
            "average_fill_price": 101.1,
            "process_state": "terminal",
            "terminal_reason": "filled",
        },
    ]
    journal_path.write_text(
        "".join(json.dumps(event) + "\n" for event in journal_events),
        encoding="utf-8",
    )

    with exit_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "decision_snapshot_id",
                "is_simulation",
                "code",
                "observed_price",
                "buy_price",
                "held_shares",
                "filled_shares",
                "is_partial_fill",
                "entry_execution_ids",
                "exit_order_id",
                "exit_execution_ids",
                "observed_pnl",
                "observed_gross_pnl",
                "observed_execution_net_pnl",
                "observed_net_pnl",
                "remaining_shares",
                "actual_cost_evidence_schema_version",
                "actual_cost_evidence_complete",
                "actual_cost_evidence_reason",
                "capital_gains_tax",
                "capital_gains_tax_evidence_complete",
                "actual_net_pnl_evidence_complete",
                "entry_commission",
                "entry_commission_tax",
                "position_expenses",
                "exit_commission",
                "exit_commission_tax",
                "actual_total_cost",
            ),
        )
        writer.writeheader()
        writer.writerow({
            "decision_snapshot_id": snapshot_id,
            "is_simulation": False,
            "code": selected_code,
            "observed_price": 101.1,
            "buy_price": 101.0,
            "held_shares": 7_400,
            "filled_shares": 7_400,
            "is_partial_fill": False,
            "entry_execution_ids": ["ENTRY-EX-1"],
            "exit_order_id": "EXIT-1",
            "exit_execution_ids": ["EXIT-EX-1"],
            "observed_pnl": 740.0,
            "observed_gross_pnl": 740.0,
            "observed_execution_net_pnl": 735.0,
            "observed_net_pnl": 635.0,
            "remaining_shares": 0,
            "actual_cost_evidence_schema_version": 1,
            "actual_cost_evidence_complete": True,
            "actual_cost_evidence_reason": "",
            "capital_gains_tax": 100.0,
            "capital_gains_tax_evidence_complete": True,
            "actual_net_pnl_evidence_complete": True,
            "entry_commission": 2.0,
            "entry_commission_tax": 0.2,
            "position_expenses": 1.0,
            "exit_commission": 1.5,
            "exit_commission_tax": 0.3,
            "actual_total_cost": 5.0,
        })

    code, summary = run_production_replay(
        snapshots_file=snapshot_path,
        exit_log=exit_path,
        decision_log=decision_path,
        order_journal=journal_path,
        trade_mode="KABUCOM_LIVE",
        min_snapshots=1,
        require_complete_lifecycle=True,
        expected_code_commit_sha="test-sha",
        expected_runtime_config_hash="test-config",
    )

    assert code == 0
    assert summary["linked_decision_events"] == 4
    assert summary["linked_order_events"] == 6
    assert summary["lifecycle_complete_snapshots"] == 1
    assert summary["lifecycle_incomplete_snapshots"] == 0
    assert summary["linked_net_actual_exits"] == 1
    assert summary["net_cost_incomplete_exits"] == 0
    assert summary["observed_execution_net_pnl"] == 735.0
    assert summary["linked_execution_net_actual_exits"] == 1
    assert summary["observed_net_pnl"] == 635.0
    assert summary["observed_net_profit_factor"] == float("inf")


def test_actual_cost_evidence_rejects_tampered_net_pnl():
    row = {
        "actual_cost_evidence_schema_version": 1,
        "actual_cost_evidence_complete": True,
        "actual_cost_evidence_reason": "",
        "buy_price": 100.0,
        "observed_price": 105.0,
        "held_shares": 100,
        "filled_shares": 100,
        "remaining_shares": 0,
        "is_partial_fill": False,
        "observed_gross_pnl": 500.0,
        "observed_execution_net_pnl": 495.0,
        "capital_gains_tax": 100.0,
        "capital_gains_tax_evidence_complete": True,
        "actual_net_pnl_evidence_complete": True,
        "observed_net_pnl": 395.0,
        "entry_commission": 2.0,
        "entry_commission_tax": 0.2,
        "position_expenses": 1.0,
        "exit_commission": 1.5,
        "exit_commission_tax": 0.3,
        "actual_total_cost": 5.0,
    }

    assert _actual_cost_evidence_reasons(row) == []
    assert _actual_net_evidence_reasons(row) == []
    row["observed_execution_net_pnl"] = 496.0
    assert "observed_execution_net_pnl_mismatch" in _actual_cost_evidence_reasons(row)
    row["observed_execution_net_pnl"] = 495.0
    row["observed_net_pnl"] = 396.0
    assert "observed_net_pnl_mismatch" in _actual_net_evidence_reasons(row)
    row["observed_net_pnl"] = 395.0
    row["entry_commission"] = -1.0
    assert "entry_commission_invalid" in _actual_cost_evidence_reasons(row)


def test_entry_quote_evidence_rejects_tampered_age_price_and_status():
    row = _entry_quote_row("1000")

    assert _entry_quote_evidence_reasons(row) == []

    row["entry_quote_age_seconds"] = 5.0
    assert "entry_quote_age_mismatch" in _entry_quote_evidence_reasons(row)
    row["entry_quote_age_seconds"] = 6.0

    row["entry_quote_best_sell_price"] = 0
    assert (
        "entry_quote_best_sell_price_invalid"
        in _entry_quote_evidence_reasons(row)
    )
    row["entry_quote_best_sell_price"] = 101.0

    row["entry_quote_status"] = "rejected"
    assert (
        "entry_quote_pass_status_mismatch"
        in _entry_quote_evidence_reasons(row)
    )


def test_blocked_entry_quote_evidence_requires_rejected_status_and_reason():
    row = _entry_quote_row(
        "1000",
        decision="blocked_entry_quote_refresh",
    )
    assert _entry_quote_evidence_reasons(row) == []

    row["entry_quote_reason"] = ""
    assert (
        "entry_quote_block_reason_missing"
        in _entry_quote_evidence_reasons(row)
    )


def test_entry_risk_evidence_recomputes_wallet_quote_and_price_ceiling():
    row = _entry_risk_row("1000")
    quote_rows = {"1000": _entry_quote_row("1000")}

    assert _entry_risk_evidence_reasons(row, quote_rows) == []

    tampered_wallet = dict(row)
    tampered_wallet["entry_risk_wallet_margin_buying_power"] = 4_000_000
    assert (
        "entry_risk_wallet_cap_mismatch"
        in _entry_risk_evidence_reasons(tampered_wallet, quote_rows)
    )

    tampered_quote = dict(row)
    tampered_quote["entry_risk_quote_price"] = 100.0
    assert (
        "entry_risk_quote_price_mismatch"
        in _entry_risk_evidence_reasons(tampered_quote, quote_rows)
    )

    tampered_ceiling = dict(row)
    tampered_ceiling["entry_risk_max_entry_price"] = 102.0
    assert (
        "entry_risk_price_ceiling_mismatch"
        in _entry_risk_evidence_reasons(tampered_ceiling, quote_rows)
    )


def test_entry_order_risk_evidence_rejects_price_above_ceiling():
    risk_row = _entry_risk_row("1000")
    event = {
        "symbol": "1000",
        "side": "2",
        "price": 101.0,
        "qty": 7_400,
        "entry_risk_evidence_schema_version": 1,
        "entry_sizing_price": 101.0,
        "entry_price_ceiling": 101.0,
        "entry_sizing_shares": 7_400,
    }

    assert _entry_order_risk_reasons(event, {"1000": risk_row}) == []
    event["price"] = 102.0
    assert (
        "entry_order_price_ceiling_exceeded"
        in _entry_order_risk_reasons(event, {"1000": risk_row})
    )


def test_entry_order_and_opened_decision_reject_quantity_or_fill_over_risk():
    risk_row = _entry_risk_row("1000")
    event = {
        "symbol": "1000",
        "side": "2",
        "price": 101.0,
        "qty": 7_500,
        "entry_risk_evidence_schema_version": 1,
        "entry_sizing_price": 101.0,
        "entry_price_ceiling": 101.0,
        "entry_sizing_shares": 7_400,
    }
    assert (
        "entry_order_qty_exceeds_sizing_shares"
        in _entry_order_risk_reasons(event, {"1000": risk_row})
    )

    opened = {
        "code": "1000",
        "shares": 7_500,
        "entry_price": 102.0,
    }
    reasons = _opened_entry_risk_reasons(opened, {"1000": risk_row})
    assert "opened_entry_shares_exceed_risk_envelope" in reasons
    assert "opened_entry_price_exceeds_risk_envelope" in reasons


def test_entry_fill_evidence_matches_opened_qty_price_and_execution_ids():
    risk_row = _entry_risk_row("1000")
    opened = {"code": "1000", "shares": 7_400, "entry_price": 101.0}
    fill = {
        "event": "FILLED",
        "symbol": "1000",
        "side": "2",
        "order_id": "ENTRY-2",
        "order_ids": ("ENTRY-1", "ENTRY-2"),
        "qty": 7_400,
        "filled_qty": 7_400,
        "requested_qty": 7_400,
        "remaining_qty": 0,
        "average_price": 101.0,
        "average_fill_price": 101.0,
        "execution_ids": ("ENTRY-EX-1", "ENTRY-EX-2"),
        "execution_id": "ENTRY-EX-1",
        "execution_evidence_schema_version": 1,
        "aggregate_execution": True,
        "process_state": "terminal",
        "terminal_reason": "filled",
        "submission_status": "accepted",
    }
    accepted = [
        {"event": "ACCEPTED", "symbol": "1000", "side": "2",
         "order_id": "ENTRY-1"},
        {"event": "ACCEPTED", "symbol": "1000", "side": "2",
         "order_id": "ENTRY-2"},
    ]
    entry_events = [*accepted, fill]


    assert _entry_fill_evidence_reasons(
        opened, entry_events, {"1000": risk_row}
    ) == []

    tampered_fill = dict(fill)
    tampered_fill["filled_qty"] = 7_300
    tampered_fill["average_fill_price"] = 100.0
    reasons = _entry_fill_evidence_reasons(
        opened, [*accepted, tampered_fill], {"1000": risk_row}
    )
    assert "entry_execution_qty_mismatch" in reasons
    assert "entry_execution_price_mismatch" in reasons

    missing_aggregate = dict(fill)
    missing_aggregate["aggregate_execution"] = False
    assert _entry_fill_evidence_reasons(
        opened, [*accepted, missing_aggregate], {"1000": risk_row}
    ) == ["entry_aggregate_fill_count_invalid"]

    invalid_primary = dict(fill)
    invalid_primary["execution_id"] = "OTHER"
    assert (
        "entry_execution_primary_id_invalid"
        in _entry_fill_evidence_reasons(
            opened, [*accepted, invalid_primary], {"1000": risk_row}
        )
    )


    assert (
        "entry_execution_order_ids_mismatch"
        in _entry_fill_evidence_reasons(
            opened, [accepted[0], fill], {"1000": risk_row}
        )
    )

def test_protective_stop_requires_orders_api_confirmation_and_exact_risk_qty():
    risk_row = _entry_risk_row("1000")
    opened = {
        "code": "1000",
        "shares": 7_400,
        "entry_price": 101.0,
    }
    valid_stop = {
        "event": "ACCEPTED",
        "kind": "stop",
        "symbol": "1000",
        "side": "1",
        "qty": 7_400,
        "trigger_price": 90.0,
        "order_id": "STOP-1",
        "confirmed": True,
        "confirmation_reason": "orders_api_confirmed",
        "confirmation_evidence_schema_version": 1,
        "exchange": 1,
        "margin_trade_type": 3,
        "expected_close_positions": [{"HoldID": "HOLD-1", "Qty": 7_400}],
        "confirmation_details": {
            "response_shape_version": 2,
            "requested_order_id": "STOP-1",
            "order_id": "STOP-1",
            "symbol": "1000",
            "details_present": True,
            "process_state": "active",
            "terminal_reason": None,
            "order_qty": 7_400,
            "cumulative_qty": 0,
            "remaining_qty": 7_400,
            "side": "1",
            "cash_margin": 3,
            "deliv_type": 2,
            "exchange": 1,
            "margin_trade_type": 3,
            "trigger_price": 90.0,
            "expected_qty": 7_400,
            "expected_trigger_price": 90.0,
            "close_positions": [{"HoldID": "HOLD-1", "Qty": 7_400}],
            "close_positions_match": True,
            "reverse_limit": {
                "TriggerSec": 1, "TriggerPrice": 90.0, "UnderOver": 1,
                "AfterHitOrderType": 1, "AfterHitPrice": 0,
            },
            "has_partial_fill": False,
            "is_consistent": True,
            "mismatch_reason": "confirmed",
        },
    }

    assert _protective_stop_risk_reasons(
        opened,
        [valid_stop],
        {"1000": risk_row},
    ) == []

    unconfirmed = dict(valid_stop)
    unconfirmed["confirmed"] = False
    assert _protective_stop_risk_reasons(
        opened,
        [unconfirmed],
        {"1000": risk_row},
    ) == ["missing_confirmed_protective_stop"]

    boolean_only = dict(valid_stop)
    boolean_only.pop("confirmation_evidence_schema_version")
    boolean_only.pop("confirmation_details")
    reasons = _protective_stop_risk_reasons(
        opened,
        [boolean_only],
        {"1000": risk_row},
    )
    assert "protective_stop_confirmation_schema_invalid" in reasons
    assert "protective_stop_confirmation_evidence_missing" in reasons

    tampered_confirmation = dict(valid_stop)
    tampered_confirmation["confirmation_details"] = dict(
        valid_stop["confirmation_details"]
    )
    tampered_confirmation["confirmation_details"]["order_id"] = "OTHER"
    tampered_confirmation["confirmation_details"]["order_qty"] = 7_300
    tampered_confirmation["confirmation_details"]["trigger_price"] = 89.0
    reasons = _protective_stop_risk_reasons(
        opened,
        [tampered_confirmation],
        {"1000": risk_row},
    )
    assert "protective_stop_confirmation_order_id_mismatch" in reasons
    assert "protective_stop_confirmation_qty_mismatch" in reasons
    assert "protective_stop_confirmation_trigger_mismatch" in reasons

    wrong_qty_and_trigger = dict(valid_stop)
    wrong_qty_and_trigger["qty"] = 7_300
    wrong_qty_and_trigger["trigger_price"] = 89.0
    reasons = _protective_stop_risk_reasons(
        opened,
        [wrong_qty_and_trigger],
        {"1000": risk_row},
    )
    assert "protective_stop_qty_mismatch" in reasons
    assert "protective_stop_trigger_mismatch" in reasons


def test_actual_exit_recomputes_gross_and_links_order_execution_ids():
    opened = {
        "code": "1000",
        "shares": 100,
        "entry_price": 100.0,
    }
    exit_row = {
        "code": "1000",
        "held_shares": 100,
        "filled_shares": 100,
        "remaining_shares": 0,
        "buy_price": 100.0,
        "entry_execution_ids": "('ENTRY-EX-1',)",
        "observed_price": 105.0,
        "exit_order_id": "EXIT-1",
        "exit_execution_ids": "('EXIT-EX-1',)",
    }
    fill = {
        "event": "FILLED",
        "symbol": "1000",
        "side": "1",
        "order_id": "EXIT-1",
        "order_ids": ("EXIT-1",),
        "execution_ids": ("EXIT-EX-1",),
        "execution_id": "EXIT-EX-1",
        "execution_evidence_schema_version": 1,
        "aggregate_execution": True,
        "requested_qty": 100,
        "qty": 100,
        "filled_qty": 100,
        "remaining_qty": 0,
        "average_price": 105.0,
        "average_fill_price": 105.0,
        "process_state": "terminal",
        "terminal_reason": "filled",
    }
    entry_fill = {
        "event": "FILLED",
        "symbol": "1000",
        "side": "2",
        "order_id": "ENTRY-1",
        "execution_ids": ("ENTRY-EX-1",),
        "execution_id": "ENTRY-EX-1",
        "execution_evidence_schema_version": 1,
        "aggregate_execution": True,
    }
    exit_accept = {
        "event": "ACCEPTED", "symbol": "1000", "side": "1",
        "order_id": "EXIT-1",
    }
    fill_events = [exit_accept, fill]

    assert _exit_lifecycle_evidence_reasons(
        opened,
        exit_row,
        [entry_fill],
        fill_events,
    ) == []

    wrong_qty = dict(exit_row)
    wrong_qty["filled_shares"] = 200
    assert (
        "actual_exit_filled_shares_mismatch"
        in _exit_lifecycle_evidence_reasons(opened, wrong_qty, [entry_fill], fill_events)
    )

    wrong_execution = dict(exit_row)
    wrong_execution["exit_execution_ids"] = "('OTHER-EX',)"
    assert (
        "actual_exit_execution_ids_mismatch"
        in _exit_lifecycle_evidence_reasons(
            opened,
            wrong_execution,
            [entry_fill],
            fill_events,
        )
    )

    tampered_fill = dict(fill)
    tampered_fill["average_fill_price"] = 104.0
    assert (
        "actual_exit_execution_price_mismatch"
        in _exit_lifecycle_evidence_reasons(
            opened, exit_row, [entry_fill], [exit_accept, tampered_fill]
        )
    )


    assert (
        "actual_exit_execution_order_ids_mismatch"
        in _exit_lifecycle_evidence_reasons(
            opened, exit_row, [entry_fill], [fill]
        )
    )

def test_operational_evidence_hash_tampering_is_rejected():
    empty_hash = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    row = {
        "decision": "operational_review_passed",
        "reason": "no_recent_news",
        "operational_evidence_schema_version": "1",
        "news_fetch_status": "no_news",
        "news_query_url": "https://example.test/news",
        "news_text": "",
        "news_sha256": empty_hash,
        "news_error": "",
        "ai_outcome": "not_requested_no_news",
        "ai_provider": "",
        "ai_model": "",
        "ai_prompt": "",
        "ai_prompt_sha256": empty_hash,
        "ai_raw_response": "",
        "ai_raw_response_sha256": empty_hash,
        "ai_error": "",
    }

    assert _operational_evidence_reasons(row) == []
    row["news_sha256"] = "sha256:tampered"
    assert "news_hash_mismatch" in _operational_evidence_reasons(row)


def test_ai_operational_evidence_requires_prompt_and_raw_response_integrity():
    digest = lambda value: f"sha256:{sha256(value.encode('utf-8')).hexdigest()}"
    row = {
        "decision": "operational_review_passed",
        "reason": "ai_filter:approved",
        "operational_evidence_schema_version": "1",
        "news_fetch_status": "ok",
        "news_query_url": "https://example.test/news",
        "news_text": "material news",
        "news_sha256": digest("material news"),
        "news_error": "",
        "ai_outcome": "approved",
        "ai_provider": "gemini",
        "ai_model": "test-model",
        "ai_prompt": "review prompt",
        "ai_prompt_sha256": digest("review prompt"),
        "ai_raw_response": "NO\n問題なし",
        "ai_raw_response_sha256": digest("NO\n問題なし"),
        "ai_error": "",
    }

    assert _operational_evidence_reasons(row) == []
    row["ai_raw_response"] = "YES\n悪材料あり"
    reasons = _operational_evidence_reasons(row)
    assert "ai_raw_response_hash_mismatch" in reasons
    assert "ai_outcome_raw_response_mismatch" in reasons
