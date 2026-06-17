from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.order_journal import OrderJournalReplaySummary

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
    active_orders_unknown_count: int
    wallet_snapshot_incomplete: bool
    needs_manual_review: bool
    blocking_reasons: tuple[str, ...]


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
        if stop_status == "armed" and not stop_order_id and not stop_unconfirmed_order_id:
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

    active_orders_unknown_count = 0
    if active_orders_info is None:
        active_orders_unknown_count = 1
    else:
        active_orders_unknown_count = len(active_orders_info.get("unresolved_order_ids", []))
        if active_orders_info.get("has_unknown"):
            active_orders_unknown_count += 1

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
        active_orders_unknown_count=active_orders_unknown_count,
        wallet_snapshot_incomplete=bool(wallet_snapshot_incomplete),
        needs_manual_review=bool(blocking_reasons),
        blocking_reasons=tuple(blocking_reasons),
    )
