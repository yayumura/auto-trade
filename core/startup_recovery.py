from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.order_journal import OrderJournalIntentReplay, OrderJournalReplaySummary

_UNRESOLVED_EXECUTION_STATUSES = {"partial_unresolved", "zero_fill_unresolved"}


@dataclass(frozen=True)
class StartupRecoveryReport:
    managed_position_count: int
    ambiguous_position_count: int
    unmanaged_position_count: int
    entry_unresolved_count: int
    exit_unresolved_count: int
    protective_stop_pending_count: int
    protective_stop_orphan_count: int
    protective_stop_missing_count: int
    journal_unresolved_count: int
    journal_corrupt_line_count: int
    journal_corrupt_final_line_count: int
    journal_corrupt_middle_line_count: int
    accepted_order_missing_at_broker_count: int
    broker_position_without_journal_count: int
    journal_filled_without_position_count: int
    unconfirmed_stop_replay_count: int
    active_orders_unknown_count: int
    wallet_snapshot_incomplete: bool
    needs_manual_review: bool
    blocking_reasons: tuple[str, ...]


def _first_text(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _normalize_execution_ids(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        raw_values = [value]
    elif isinstance(value, (list, tuple, set)):
        raw_values = list(value)
    else:
        raw_values = [value]

    normalized: list[str] = []
    for item in raw_values:
        text = _first_text(item)
        if text and text not in normalized:
            normalized.append(text)
    return tuple(normalized)


def _extract_active_order_ids(active_orders_info: Mapping[str, Any] | None) -> set[str]:
    if not isinstance(active_orders_info, Mapping):
        return set()
    order_ids: set[str] = set()
    for order in active_orders_info.get("orders", []):
        if not isinstance(order, Mapping):
            continue
        for key in ("ID", "OrderId", "OrderID"):
            value = str(order.get(key) or "").strip()
            if value:
                order_ids.add(value)
                break
    return order_ids


def _extract_journal_identifiers(intent: OrderJournalIntentReplay) -> tuple[str | None, set[str], str]:
    payload = intent.latest_payload if isinstance(intent.latest_payload, Mapping) else {}
    order_id = _first_text(payload.get("order_id"), payload.get("OrderId"), payload.get("OrderID"))
    execution_ids: set[str] = set(_normalize_execution_ids(payload.get("execution_ids")))
    execution_id = _first_text(payload.get("execution_id"), payload.get("ExecutionID"))
    if execution_id:
        execution_ids.add(execution_id)
    kind = _first_text(intent.kind, payload.get("kind")) or ""
    return order_id, execution_ids, kind.lower()


def _extract_position_reconciliation_ids(position: Mapping[str, Any]) -> set[str]:
    identifiers: set[str] = set()
    for key in ("entry_order_id", "order_id", "execution_id", "hold_id"):
        text = _first_text(position.get(key))
        if text:
            identifiers.add(text)
    identifiers.update(_normalize_execution_ids(position.get("execution_ids")))
    return identifiers


def _count_positions(portfolio: list[dict[str, Any]] | None, active_orders_info: Mapping[str, Any] | None = None) -> dict[str, int]:
    managed = ambiguous = unmanaged = entry_unresolved = exit_unresolved = protective_stop_pending = protective_stop_orphan = protective_stop_missing = 0
    active_order_ids = _extract_active_order_ids(active_orders_info)
    can_check_active_orders = active_orders_info is not None
    for position in portfolio or []:
        ownership = str(position.get("ownership") or "").upper()
        if ownership == "MANAGED_BY_BOT":
            managed += 1
        elif ownership == "AMBIGUOUS":
            ambiguous += 1
        else:
            unmanaged += 1
        entry_unresolved_flag = bool(position.get("entry_order_unresolved"))
        exit_unresolved_flag = bool(position.get("exit_order_unresolved"))
        entry_execution_status = str(position.get("entry_order_execution_status") or "").lower()
        exit_execution_status = str(position.get("exit_order_execution_status") or "").lower()
        if entry_unresolved_flag or entry_execution_status in _UNRESOLVED_EXECUTION_STATUSES:
            entry_unresolved += 1
        if exit_unresolved_flag or exit_execution_status in _UNRESOLVED_EXECUTION_STATUSES:
            exit_unresolved += 1
        stop_status = str(position.get("protective_stop_status") or "").lower()
        stop_order_id = str(position.get("protective_stop_order_id") or "").strip()
        stop_unconfirmed_order_id = str(position.get("protective_stop_unconfirmed_order_id") or "").strip()
        if stop_unconfirmed_order_id:
            protective_stop_pending += 1
        if stop_status in {"armed", "failed"} and not stop_order_id and not stop_unconfirmed_order_id:
            protective_stop_orphan += 1
        if (
            can_check_active_orders
            and stop_status == "armed"
            and stop_order_id
            and stop_order_id not in active_order_ids
            and not stop_unconfirmed_order_id
        ):
            protective_stop_missing += 1
    return {
        "managed": managed,
        "ambiguous": ambiguous,
        "unmanaged": unmanaged,
        "entry_unresolved": entry_unresolved,
        "exit_unresolved": exit_unresolved,
        "protective_stop_pending": protective_stop_pending,
        "protective_stop_orphan": protective_stop_orphan,
        "protective_stop_missing": protective_stop_missing,
    }


def build_startup_recovery_report(
    *,
    portfolio: list[dict[str, Any]] | None,
    active_orders_info: Mapping[str, Any] | None,
    order_journal_summary: OrderJournalReplaySummary | None,
    wallet_snapshot_incomplete: bool,
) -> StartupRecoveryReport:
    counts = _count_positions(portfolio, active_orders_info)
    journal_unresolved_count = 0 if order_journal_summary is None else order_journal_summary.unresolved_count
    journal_corrupt_line_count = 0 if order_journal_summary is None else order_journal_summary.corrupt_lines
    journal_corrupt_final_line_count = 0 if order_journal_summary is None else order_journal_summary.corrupt_final_line_count
    journal_corrupt_middle_line_count = 0 if order_journal_summary is None else order_journal_summary.corrupt_middle_line_count

    active_orders_unknown_count = 0
    if active_orders_info is None:
        active_orders_unknown_count = 1
    else:
        active_orders_unknown_count = len(active_orders_info.get("unresolved_order_ids", []))
        if active_orders_info.get("has_unknown"):
            active_orders_unknown_count += 1

    active_order_ids = _extract_active_order_ids(active_orders_info)
    journal_order_ids: set[str] = set()
    journal_execution_ids: set[str] = set()
    accepted_order_missing_at_broker_count = 0
    journal_filled_without_position_count = 0
    unconfirmed_stop_replay_count = 0

    managed_positions = [
        dict(position)
        for position in portfolio or []
        if isinstance(position, Mapping) and str(position.get("ownership") or "").upper() == "MANAGED_BY_BOT"
    ]
    managed_position_identifiers = [_extract_position_reconciliation_ids(position) for position in managed_positions]
    managed_position_identifier_union = set().union(*managed_position_identifiers) if managed_position_identifiers else set()

    if order_journal_summary is not None:
        for intent in order_journal_summary.intents:
            order_id, execution_ids, kind = _extract_journal_identifiers(intent)
            if order_id:
                journal_order_ids.add(order_id)
            journal_execution_ids.update(execution_ids)
            latest_event = str(intent.latest_event or "").strip().upper()

            if latest_event == "ACCEPTED" and order_id and active_orders_info is not None and order_id not in active_order_ids:
                accepted_order_missing_at_broker_count += 1

            if latest_event in {"FILLED", "FILLED_BEFORE_CANCEL"}:
                journal_ids = set()
                if order_id:
                    journal_ids.add(order_id)
                journal_ids.update(execution_ids)
                if not journal_ids or not (journal_ids & managed_position_identifier_union):
                    journal_filled_without_position_count += 1

            if kind == "stop" and intent.unresolved:
                unconfirmed_stop_replay_count += 1

    broker_position_without_journal_count = 0
    journal_reconciliation_union = journal_order_ids | journal_execution_ids
    for _position, position_identifiers in zip(managed_positions, managed_position_identifiers):
        if not position_identifiers:
            broker_position_without_journal_count += 1
            continue
        if not (position_identifiers & journal_reconciliation_union):
            broker_position_without_journal_count += 1

    blocking_reasons: list[str] = []
    if wallet_snapshot_incomplete:
        blocking_reasons.append("wallet_snapshot_incomplete")
    if counts["entry_unresolved"] > 0:
        blocking_reasons.append(f"entry_unresolved:{counts['entry_unresolved']}")
    if counts["exit_unresolved"] > 0:
        blocking_reasons.append(f"exit_unresolved:{counts['exit_unresolved']}")
    if counts["protective_stop_pending"] > 0:
        blocking_reasons.append(f"protective_stop_pending:{counts['protective_stop_pending']}")
    if counts["protective_stop_orphan"] > 0:
        blocking_reasons.append(f"protective_stop_orphan:{counts['protective_stop_orphan']}")
    if counts["protective_stop_missing"] > 0:
        blocking_reasons.append(f"protective_stop_missing:{counts['protective_stop_missing']}")
    if counts["ambiguous"] > 0:
        blocking_reasons.append(f"ambiguous_positions:{counts['ambiguous']}")
    if journal_unresolved_count > 0:
        blocking_reasons.append(f"journal_unresolved:{journal_unresolved_count}")
    if journal_corrupt_line_count > 0:
        blocking_reasons.append(f"journal_corrupt_lines:{journal_corrupt_line_count}")
    if journal_corrupt_final_line_count > 0:
        blocking_reasons.append(f"journal_corrupt_final_lines:{journal_corrupt_final_line_count}")
    if journal_corrupt_middle_line_count > 0:
        blocking_reasons.append(f"journal_corrupt_middle_lines:{journal_corrupt_middle_line_count}")
    if accepted_order_missing_at_broker_count > 0:
        blocking_reasons.append(f"accepted_order_missing_at_broker:{accepted_order_missing_at_broker_count}")
    if broker_position_without_journal_count > 0:
        blocking_reasons.append(f"broker_position_without_journal:{broker_position_without_journal_count}")
    if journal_filled_without_position_count > 0:
        blocking_reasons.append(f"journal_filled_without_position:{journal_filled_without_position_count}")
    if unconfirmed_stop_replay_count > 0:
        blocking_reasons.append(f"unconfirmed_stop_replay:{unconfirmed_stop_replay_count}")
    if active_orders_unknown_count > 0:
        blocking_reasons.append(f"active_orders_unknown:{active_orders_unknown_count}")

    return StartupRecoveryReport(
        managed_position_count=counts["managed"],
        ambiguous_position_count=counts["ambiguous"],
        unmanaged_position_count=counts["unmanaged"],
        entry_unresolved_count=counts["entry_unresolved"],
        exit_unresolved_count=counts["exit_unresolved"],
        protective_stop_pending_count=counts["protective_stop_pending"],
        protective_stop_orphan_count=counts["protective_stop_orphan"],
        protective_stop_missing_count=counts["protective_stop_missing"],
        journal_unresolved_count=journal_unresolved_count,
        journal_corrupt_line_count=journal_corrupt_line_count,
        journal_corrupt_final_line_count=journal_corrupt_final_line_count,
        journal_corrupt_middle_line_count=journal_corrupt_middle_line_count,
        accepted_order_missing_at_broker_count=accepted_order_missing_at_broker_count,
        broker_position_without_journal_count=broker_position_without_journal_count,
        journal_filled_without_position_count=journal_filled_without_position_count,
        unconfirmed_stop_replay_count=unconfirmed_stop_replay_count,
        active_orders_unknown_count=active_orders_unknown_count,
        wallet_snapshot_incomplete=bool(wallet_snapshot_incomplete),
        needs_manual_review=bool(blocking_reasons),
        blocking_reasons=tuple(blocking_reasons),
    )
