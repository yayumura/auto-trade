import itertools
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core.config import JST, ORDER_JOURNAL_FILE
from core.file_io import ensure_absolute_path

ORDER_JOURNAL_SCHEMA_VERSION = 1
_ORDER_JOURNAL_SEQUENCE = itertools.count(1)

_TERMINAL_EVENTS = {"REJECTED", "CANCELLED", "FILLED", "FILLED_BEFORE_CANCEL", "EXPIRED"}
_UNRESOLVED_EVENTS = {"PLANNED", "ACCEPTED", "CANCEL_REQUESTED", "UNKNOWN"}


@dataclass(frozen=True)
class OrderJournalIntentReplay:
    tracking_key: str
    intent_id: str | None
    order_id: str | None
    kind: str | None
    latest_event: str
    unresolved: bool
    unresolved_reason: str | None
    event_count: int
    latest_sequence: int | None
    latest_logged_at: str | None
    latest_payload: dict[str, Any]


@dataclass(frozen=True)
class OrderJournalReplaySummary:
    total_lines: int
    parsed_lines: int
    corrupt_lines: int
    intents: tuple[OrderJournalIntentReplay, ...]
    corrupt_final_line_count: int = 0
    corrupt_middle_line_count: int = 0

    @property
    def unresolved_intents(self) -> tuple[OrderJournalIntentReplay, ...]:
        return tuple(intent for intent in self.intents if intent.unresolved)

    @property
    def resolved_intents(self) -> tuple[OrderJournalIntentReplay, ...]:
        return tuple(intent for intent in self.intents if not intent.unresolved)

    @property
    def unresolved_count(self) -> int:
        return len(self.unresolved_intents)

    @property
    def has_unresolved(self) -> bool:
        return self.unresolved_count > 0


def append_order_journal(event: dict, path: str = ORDER_JOURNAL_FILE) -> dict:
    """Append a single order event as JSONL."""
    payload = dict(event or {})
    payload.setdefault("schema_version", ORDER_JOURNAL_SCHEMA_VERSION)
    payload.setdefault("event_id", uuid.uuid4().hex)
    payload.setdefault("sequence", next(_ORDER_JOURNAL_SEQUENCE))
    payload.setdefault("process_id", os.getpid())
    payload.setdefault("logged_at", datetime.now(JST).isoformat())
    journal_path = Path(ensure_absolute_path(path))
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    with journal_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            raise
    return payload


def _journal_tracking_key(payload: dict[str, Any], line_number: int) -> str:
    intent_id = str(payload.get("intent_id") or "").strip()
    if intent_id:
        return f"intent:{intent_id}"
    order_id = str(payload.get("order_id") or "").strip()
    if order_id:
        return f"order:{order_id}"
    event_name = str(payload.get("event") or "event").strip() or "event"
    kind = str(payload.get("kind") or "").strip()
    symbol = str(payload.get("symbol") or "").strip()
    return f"line:{line_number}:{event_name}:{kind}:{symbol}"


def _count_corrupt_line_categories(total_lines: int, parsed_line_numbers: set[int]) -> tuple[int, int]:
    if total_lines <= 0:
        return 0, 0
    missing_line_numbers = sorted(set(range(1, total_lines + 1)) - set(parsed_line_numbers))
    if not missing_line_numbers:
        return 0, 0
    corrupt_final_line_count = 1 if total_lines in missing_line_numbers else 0
    corrupt_middle_line_count = max(0, len(missing_line_numbers) - corrupt_final_line_count)
    return corrupt_final_line_count, corrupt_middle_line_count


def _journal_unresolved_reason(event_name: str) -> str | None:
    if event_name == "PLANNED":
        return "planned_not_accepted"
    if event_name == "ACCEPTED":
        return "accepted_not_terminal"
    if event_name == "CANCEL_REQUESTED":
        return "cancel_pending"
    if event_name == "UNKNOWN":
        return "unknown_state"
    return None


def load_order_journal_events(path: str = ORDER_JOURNAL_FILE) -> tuple[dict[str, Any], ...]:
    journal_path = Path(ensure_absolute_path(path))
    if not journal_path.exists() or journal_path.stat().st_size == 0:
        return ()

    events: list[dict[str, Any]] = []
    with journal_path.open("r", encoding="utf-8") as f:
        for line_number, raw_line in enumerate(f, start=1):
            text = raw_line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                payload["__line_number__"] = line_number
                events.append(payload)
    return tuple(events)


def build_order_journal_replay_summary(path: str = ORDER_JOURNAL_FILE) -> OrderJournalReplaySummary:
    events = load_order_journal_events(path)
    journal_path = Path(ensure_absolute_path(path))
    total_lines = 0
    if journal_path.exists():
        with journal_path.open("r", encoding="utf-8") as f:
            total_lines = sum(1 for _ in f)

    parsed_line_numbers = {
        int(event.get("__line_number__") or 0)
        for event in events
        if int(event.get("__line_number__") or 0) > 0
    }

    grouped: dict[str, dict[str, Any]] = {}
    for event in events:
        line_number = int(event.get("__line_number__") or 0)
        tracking_key = _journal_tracking_key(event, line_number)
        entry = grouped.setdefault(
            tracking_key,
            {
                "tracking_key": tracking_key,
                "intent_id": None,
                "order_id": None,
                "kind": None,
                "latest_event": None,
                "unresolved": False,
                "unresolved_reason": None,
                "event_count": 0,
                "latest_sequence": None,
                "latest_logged_at": None,
                "latest_payload": {},
            },
        )
        entry["event_count"] += 1
        entry["intent_id"] = entry["intent_id"] or str(event.get("intent_id") or "").strip() or None
        entry["order_id"] = entry["order_id"] or str(event.get("order_id") or "").strip() or None
        entry["kind"] = entry["kind"] or str(event.get("kind") or "").strip() or None
        event_name = str(event.get("event") or "").strip() or "UNKNOWN"
        sequence = event.get("sequence")
        try:
            sequence = int(sequence) if sequence is not None else None
        except (TypeError, ValueError):
            sequence = None
        entry["latest_event"] = event_name
        entry["latest_sequence"] = sequence if sequence is not None else entry["latest_sequence"]
        logged_at = event.get("logged_at")
        if logged_at is not None:
            entry["latest_logged_at"] = str(logged_at)
        entry["latest_payload"] = dict(event)
        if event_name in _TERMINAL_EVENTS:
            entry["unresolved"] = False
            entry["unresolved_reason"] = None
        elif event_name in _UNRESOLVED_EVENTS:
            entry["unresolved"] = True
            entry["unresolved_reason"] = _journal_unresolved_reason(event_name)
        elif entry["latest_event"] is None:
            entry["unresolved"] = True
            entry["unresolved_reason"] = "unknown_event"

    intents = []
    for entry in grouped.values():
        latest_event = str(entry["latest_event"] or "UNKNOWN")
        if latest_event in _TERMINAL_EVENTS:
            unresolved = False
            unresolved_reason = None
        elif latest_event in _UNRESOLVED_EVENTS:
            unresolved = True
            unresolved_reason = _journal_unresolved_reason(latest_event)
        else:
            unresolved = False
            unresolved_reason = None
        intents.append(
            OrderJournalIntentReplay(
                tracking_key=str(entry["tracking_key"]),
                intent_id=entry["intent_id"],
                order_id=entry["order_id"],
                kind=entry["kind"],
                latest_event=latest_event,
                unresolved=unresolved,
                unresolved_reason=unresolved_reason,
                event_count=int(entry["event_count"]),
                latest_sequence=entry["latest_sequence"],
                latest_logged_at=entry["latest_logged_at"],
                latest_payload=dict(entry["latest_payload"]),
            )
        )

    intents.sort(key=lambda item: (
        item.latest_sequence is None,
        item.latest_sequence if item.latest_sequence is not None else 0,
        item.tracking_key,
    ))
    corrupt_final_line_count, corrupt_middle_line_count = _count_corrupt_line_categories(
        total_lines,
        parsed_line_numbers,
    )
    return OrderJournalReplaySummary(
        total_lines=total_lines,
        parsed_lines=len(events),
        corrupt_lines=max(0, total_lines - len(events)),
        intents=tuple(intents),
        corrupt_final_line_count=corrupt_final_line_count,
        corrupt_middle_line_count=corrupt_middle_line_count,
    )
