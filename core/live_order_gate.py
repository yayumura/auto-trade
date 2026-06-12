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


def is_live_new_entry_allowed() -> bool:
    """KABUCOM_LIVE の新規 entry が許可されるかだけを返す。"""
    return get_live_order_gate_status().allowed
