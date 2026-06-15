from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from core.order_journal import append_order_journal, build_order_journal_replay_summary
from core.startup_recovery import build_startup_recovery_report


def test_append_order_journal_adds_schema_event_id_sequence_and_pid(tmp_path: Path):
    journal_path = tmp_path / "order_journal.jsonl"

    first = append_order_journal({"event": "PLANNED"}, path=str(journal_path))
    second = append_order_journal({"event": "ACCEPTED"}, path=str(journal_path))

    assert first["schema_version"] == 1
    assert first["event_id"]
    assert second["event_id"]
    assert first["event_id"] != second["event_id"]
    assert second["sequence"] == first["sequence"] + 1
    assert first["process_id"] == second["process_id"]
    assert journal_path.exists()

    lines = journal_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    payloads = [json.loads(line) for line in lines]
    assert payloads[0]["schema_version"] == 1
    assert payloads[0]["event"] == "PLANNED"
    assert payloads[1]["event"] == "ACCEPTED"


def test_build_order_journal_replay_summary_marks_planned_and_accepted_as_unresolved(tmp_path: Path):
    journal_path = tmp_path / "order_journal.jsonl"
    append_order_journal({"event": "PLANNED", "intent_id": "intent-1"}, path=str(journal_path))
    append_order_journal({"event": "ACCEPTED", "intent_id": "intent-1", "order_id": "ORDER-1"}, path=str(journal_path))
    append_order_journal({"event": "CANCEL_REQUESTED", "order_id": "ORDER-2"}, path=str(journal_path))
    append_order_journal({"event": "CANCELLED", "order_id": "ORDER-2"}, path=str(journal_path))
    append_order_journal({"event": "REJECTED", "intent_id": "intent-3"}, path=str(journal_path))
    append_order_journal({"event": "PLANNED", "intent_id": "intent-4"}, path=str(journal_path))
    append_order_journal({"event": "FILLED_BEFORE_CANCEL", "intent_id": "intent-4", "order_id": "ORDER-4"}, path=str(journal_path))

    summary = build_order_journal_replay_summary(str(journal_path))

    assert summary.total_lines == 7
    assert summary.parsed_lines == 7
    assert summary.corrupt_lines == 0
    assert summary.has_unresolved is True
    assert summary.unresolved_count == 1
    unresolved_keys = {intent.tracking_key for intent in summary.unresolved_intents}
    assert "intent:intent-1" in unresolved_keys
    resolved_keys = {intent.tracking_key for intent in summary.resolved_intents}
    assert "order:ORDER-2" in resolved_keys
    assert "intent:intent-3" in resolved_keys
    assert "intent:intent-4" in resolved_keys


def test_build_order_journal_replay_summary_treats_filled_as_terminal(tmp_path: Path):
    journal_path = tmp_path / "order_journal.jsonl"
    append_order_journal({"event": "PLANNED", "intent_id": "intent-1"}, path=str(journal_path))
    append_order_journal({"event": "ACCEPTED", "intent_id": "intent-1", "order_id": "ORDER-1"}, path=str(journal_path))
    append_order_journal({"event": "FILLED", "intent_id": "intent-1", "order_id": "ORDER-1", "filled_qty": 100}, path=str(journal_path))

    summary = build_order_journal_replay_summary(str(journal_path))

    assert summary.has_unresolved is False
    assert summary.unresolved_count == 0
    resolved_keys = {intent.tracking_key for intent in summary.resolved_intents}
    assert "intent:intent-1" in resolved_keys


def test_build_startup_recovery_report_blocks_on_corrupt_journal_lines(tmp_path: Path):
    journal_path = tmp_path / "order_journal.jsonl"
    append_order_journal({"event": "ACCEPTED", "intent_id": "intent-1", "order_id": "ORDER-1"}, path=str(journal_path))
    with journal_path.open("a", encoding="utf-8") as f:
        f.write("{not-json}\n")

    summary = build_order_journal_replay_summary(str(journal_path))
    report = build_startup_recovery_report(
        portfolio=[],
        active_orders_info={"orders": [], "has_unknown": False, "unresolved_order_ids": []},
        order_journal_summary=summary,
        wallet_snapshot_incomplete=False,
    )

    assert summary.corrupt_lines == 1
    assert report.needs_manual_review is True
    assert "journal_corrupt_lines:1" in report.blocking_reasons


def test_build_startup_recovery_report_blocks_on_unresolved_active_orders():
    report = build_startup_recovery_report(
        portfolio=[],
        active_orders_info={
            "orders": [],
            "has_unknown": True,
            "unresolved_order_ids": ["ORDER-1"],
        },
        order_journal_summary=None,
        wallet_snapshot_incomplete=False,
    )

    assert report.active_orders_unknown_count == 2
    assert report.needs_manual_review is True
    assert "active_orders_unknown:2" in report.blocking_reasons


def test_append_order_journal_raises_when_fsync_fails(tmp_path: Path):
    journal_path = tmp_path / "order_journal.jsonl"

    with patch("core.order_journal.os.fsync", side_effect=OSError("fsync failed")):
        try:
            append_order_journal({"event": "PLANNED"}, path=str(journal_path))
        except OSError as exc:
            assert "fsync failed" in str(exc)
        else:
            raise AssertionError("append_order_journal should raise when fsync fails")
