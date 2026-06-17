from __future__ import annotations

from dataclasses import dataclass

from core.config import (
    APPROVED_CONFIG_HASH,
    DEBUG_MODE,
    ENABLE_LIVE_ORDER,
    RUNTIME_LIVE_ORDER_CONFIG_HASH,
    TRADE_MODE,
)


@dataclass(frozen=True)
class LiveOrderGateStatus:
    allowed: bool
    reason: str
    trade_mode: str
    debug_mode: bool
    enable_live_order: bool
    approved_config_hash: str
    runtime_config_hash: str


@dataclass(frozen=True)
class EntryAuthorizationContext:
    production_endpoint: bool
    approved_manifest_valid: bool
    reconciliation_clean: bool
    unresolved_order_count: int
    ambiguous_position_count: int
    wallet_snapshot_fresh: bool
    positions_snapshot_fresh: bool
    orders_snapshot_fresh: bool
    quote_fresh: bool
    registry_ready: bool
    critical_state_valid: bool
    session_allows_entry: bool
    clock_healthy: bool
    shutdown_requested: bool
    protective_stop_pending_count: int = 0
    protective_stop_orphan_count: int = 0


@dataclass(frozen=True)
class EntryAuthorizationStatus:
    allowed: bool
    reason: str
    blocking_reasons: tuple[str, ...]


def _coerce_bool(value: bool | str | None) -> bool:
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)


def get_live_order_gate_status(
    *,
    trade_mode: str | None = None,
    debug_mode: bool | None = None,
    enable_live_order: bool | None = None,
    approved_config_hash: str | None = None,
    runtime_config_hash: str | None = None,
) -> LiveOrderGateStatus:
    """KABUCOM_LIVE の新規注文許可状況を判定する。"""
    trade_mode = TRADE_MODE if trade_mode is None else str(trade_mode).strip().upper()
    debug_mode = DEBUG_MODE if debug_mode is None else _coerce_bool(debug_mode)
    enable_live_order = ENABLE_LIVE_ORDER if enable_live_order is None else _coerce_bool(enable_live_order)
    approved_config_hash = (
        APPROVED_CONFIG_HASH if approved_config_hash is None else str(approved_config_hash).strip()
    )
    runtime_config_hash = (
        RUNTIME_LIVE_ORDER_CONFIG_HASH if runtime_config_hash is None else str(runtime_config_hash).strip()
    )

    if trade_mode != "KABUCOM_LIVE":
        return LiveOrderGateStatus(
            allowed=True,
            reason="non_live_mode",
            trade_mode=trade_mode,
            debug_mode=debug_mode,
            enable_live_order=enable_live_order,
            approved_config_hash=approved_config_hash,
            runtime_config_hash=runtime_config_hash,
        )
    if debug_mode:
        return LiveOrderGateStatus(
            allowed=False,
            reason="debug_mode_enabled",
            trade_mode=trade_mode,
            debug_mode=debug_mode,
            enable_live_order=enable_live_order,
            approved_config_hash=approved_config_hash,
            runtime_config_hash=runtime_config_hash,
        )
    if not enable_live_order:
        return LiveOrderGateStatus(
            allowed=False,
            reason="enable_live_order_missing",
            trade_mode=trade_mode,
            debug_mode=debug_mode,
            enable_live_order=enable_live_order,
            approved_config_hash=approved_config_hash,
            runtime_config_hash=runtime_config_hash,
        )
    if not approved_config_hash:
        return LiveOrderGateStatus(
            allowed=False,
            reason="approved_config_hash_missing",
            trade_mode=trade_mode,
            debug_mode=debug_mode,
            enable_live_order=enable_live_order,
            approved_config_hash=approved_config_hash,
            runtime_config_hash=runtime_config_hash,
        )
    if approved_config_hash != runtime_config_hash:
        return LiveOrderGateStatus(
            allowed=False,
            reason="config_hash_mismatch",
            trade_mode=trade_mode,
            debug_mode=debug_mode,
            enable_live_order=enable_live_order,
            approved_config_hash=approved_config_hash,
            runtime_config_hash=runtime_config_hash,
        )
    return LiveOrderGateStatus(
        allowed=True,
        reason="ready",
        trade_mode=trade_mode,
        debug_mode=debug_mode,
        enable_live_order=enable_live_order,
        approved_config_hash=approved_config_hash,
        runtime_config_hash=runtime_config_hash,
    )


def evaluate_entry_authorization(context: EntryAuthorizationContext) -> EntryAuthorizationStatus:
    """ライブ新規 entry の実行時認可を判定する。"""
    if not context.production_endpoint:
        return EntryAuthorizationStatus(
            allowed=True,
            reason="non_production_endpoint",
            blocking_reasons=(),
        )

    blocking_reasons: list[str] = []
    if not context.approved_manifest_valid:
        blocking_reasons.append("approved_manifest_invalid")
    if not context.reconciliation_clean:
        blocking_reasons.append("reconciliation_dirty")
    if context.unresolved_order_count > 0:
        blocking_reasons.append(f"unresolved_orders:{int(context.unresolved_order_count)}")
    if context.ambiguous_position_count > 0:
        blocking_reasons.append(f"ambiguous_positions:{int(context.ambiguous_position_count)}")
    if context.protective_stop_pending_count > 0:
        blocking_reasons.append(f"protective_stop_pending:{int(context.protective_stop_pending_count)}")
    if context.protective_stop_orphan_count > 0:
        blocking_reasons.append(f"protective_stop_orphan:{int(context.protective_stop_orphan_count)}")
    if not context.wallet_snapshot_fresh:
        blocking_reasons.append("wallet_snapshot_stale")
    if not context.positions_snapshot_fresh:
        blocking_reasons.append("positions_snapshot_stale")
    if not context.orders_snapshot_fresh:
        blocking_reasons.append("orders_snapshot_stale")
    if not context.quote_fresh:
        blocking_reasons.append("quote_stale")
    if not context.registry_ready:
        blocking_reasons.append("registry_not_ready")
    if not context.critical_state_valid:
        blocking_reasons.append("critical_state_invalid")
    if not context.session_allows_entry:
        blocking_reasons.append("session_disallows_entry")
    if not context.clock_healthy:
        blocking_reasons.append("clock_unhealthy")
    if context.shutdown_requested:
        blocking_reasons.append("shutdown_requested")

    if blocking_reasons:
        return EntryAuthorizationStatus(
            allowed=False,
            reason=" | ".join(blocking_reasons),
            blocking_reasons=tuple(blocking_reasons),
        )

    return EntryAuthorizationStatus(
        allowed=True,
        reason="ready",
        blocking_reasons=(),
    )


def is_live_new_entry_allowed() -> bool:
    """KABUCOM_LIVE の新規 entry が許可されるかだけを返す。"""
    return get_live_order_gate_status().allowed
