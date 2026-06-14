from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.order_journal import OrderJournalReplaySummary


@dataclass(frozen=True)
class StartupRecoveryReport:
    managed_position_count: int
    ambiguous_position_count: int
    unmanaged_position_count: int
    entry_unresolved_count: int
    exit_unresolved_count: int
    journal_unresolved_count: int
    active_orders_unknown_count: int
    wallet_snapshot_incomplete: bool
    needs_manual_review: bool
    blocking_reasons: tuple[str, ...]


def _count_positions(portfolio: list[dict[str, Any]] | None) -> dict[str, int]:
    managed = ambiguous = unmanaged = entry_unresolved = exit_unresolved = 0
    for position in portfolio or []:
        ownership = str(position.get("ownership") or "").upper()
        if ownership == "MANAGED_BY_BOT":
            managed += 1
        elif ownership == "AMBIGUOUS":
            ambiguous += 1
        else:
            unmanaged += 1
        if position.get("entry_order_unresolved"):
            entry_unresolved += 1
        if position.get("exit_order_unresolved"):
            exit_unresolved += 1
    return {
        "managed": managed,
        "ambiguous": ambiguous,
        "unmanaged": unmanaged,
        "entry_unresolved": entry_unresolved,
        "exit_unresolved": exit_unresolved,
    }


def build_startup_recovery_report(
    *,
    portfolio: list[dict[str, Any]] | None,
    active_orders_info: Mapping[str, Any] | None,
    order_journal_summary: OrderJournalReplaySummary | None,
    wallet_snapshot_incomplete: bool,
) -> StartupRecoveryReport:
    counts = _count_positions(portfolio)
    journal_unresolved_count = 0 if order_journal_summary is None else order_journal_summary.unresolved_count

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
    if counts["ambiguous"] > 0:
        blocking_reasons.append(f"ambiguous_positions:{counts['ambiguous']}")
    if journal_unresolved_count > 0:
        blocking_reasons.append(f"journal_unresolved:{journal_unresolved_count}")
    if active_orders_unknown_count > 0:
        blocking_reasons.append(f"active_orders_unknown:{active_orders_unknown_count}")

    return StartupRecoveryReport(
        managed_position_count=counts["managed"],
        ambiguous_position_count=counts["ambiguous"],
        unmanaged_position_count=counts["unmanaged"],
        entry_unresolved_count=counts["entry_unresolved"],
        exit_unresolved_count=counts["exit_unresolved"],
        journal_unresolved_count=journal_unresolved_count,
        active_orders_unknown_count=active_orders_unknown_count,
        wallet_snapshot_incomplete=bool(wallet_snapshot_incomplete),
        needs_manual_review=bool(blocking_reasons),
        blocking_reasons=tuple(blocking_reasons),
    )
