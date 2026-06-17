from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from core.kabucom_contracts import (
    TEST_CONTRACT_FIXTURE_PATH,
    load_contract_fixture,
    validate_test_contract_fixture,
)

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
class LiveFinancialWriteGateStatus:
    allowed: bool
    reason: str
    base_gate_status: LiveOrderGateStatus
    test_fixture_path: str
    test_fixture_present: bool
    test_fixture_valid: bool
    test_fixture_captured_from_kabucom_test: bool
    ci_green_attested: bool


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


def _coerce_env_bool(*names: str) -> bool | None:
    for name in names:
        raw = os.getenv(name)
        if raw is None:
            continue
        text = raw.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
    return None


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


def get_kabucom_live_financial_write_gate_status(
    *,
    base_gate_status: LiveOrderGateStatus | None = None,
    test_fixture_path: str | Path | None = None,
    ci_green_attested: bool | None = None,
) -> LiveFinancialWriteGateStatus:
    """KABUCOM_LIVE の financial write を開けてよいかを総合判定する。

    既存の live order gate に加えて、KABUCOM_TEST fixture の provenance と
    CI green attestation も fail closed で要求する。
    """
    base_gate_status = get_live_order_gate_status() if base_gate_status is None else base_gate_status
    fixture_path = TEST_CONTRACT_FIXTURE_PATH if test_fixture_path is None else Path(test_fixture_path)
    fixture_path_text = str(fixture_path)
    if ci_green_attested is None:
        ci_green_attested = _coerce_env_bool("KABUCOM_LIVE_CI_GREEN", "CI_GREEN") is True
    resolved_ci_green_attested = bool(ci_green_attested)

    if not bool(getattr(base_gate_status, "allowed", False)):
        return LiveFinancialWriteGateStatus(
            allowed=False,
            reason=str(getattr(base_gate_status, "reason", "live_order_gate_blocked")),
            base_gate_status=base_gate_status,
            test_fixture_path=fixture_path_text,
            test_fixture_present=False,
            test_fixture_valid=False,
            test_fixture_captured_from_kabucom_test=False,
            ci_green_attested=resolved_ci_green_attested,
        )

    if str(getattr(base_gate_status, "reason", "")) == "non_live_mode":
        return LiveFinancialWriteGateStatus(
            allowed=True,
            reason="non_live_mode",
            base_gate_status=base_gate_status,
            test_fixture_path=fixture_path_text,
            test_fixture_present=False,
            test_fixture_valid=False,
            test_fixture_captured_from_kabucom_test=False,
            ci_green_attested=resolved_ci_green_attested,
        )

    fixture = load_contract_fixture(fixture_path)
    if fixture is None:
        return LiveFinancialWriteGateStatus(
            allowed=False,
            reason="test_contract_fixture_missing",
            base_gate_status=base_gate_status,
            test_fixture_path=fixture_path_text,
            test_fixture_present=False,
            test_fixture_valid=False,
            test_fixture_captured_from_kabucom_test=False,
            ci_green_attested=resolved_ci_green_attested,
        )

    validation = validate_test_contract_fixture(fixture)
    if not validation.valid:
        return LiveFinancialWriteGateStatus(
            allowed=False,
            reason=f"test_contract_fixture_invalid:{validation.reason}",
            base_gate_status=base_gate_status,
            test_fixture_path=fixture_path_text,
            test_fixture_present=True,
            test_fixture_valid=False,
            test_fixture_captured_from_kabucom_test=False,
            ci_green_attested=resolved_ci_green_attested,
        )

    captured_from_test = bool(fixture.get("captured_from_kabucom_test"))
    if not captured_from_test:
        return LiveFinancialWriteGateStatus(
            allowed=False,
            reason="test_contract_fixture_not_captured_from_kabucom_test",
            base_gate_status=base_gate_status,
            test_fixture_path=fixture_path_text,
            test_fixture_present=True,
            test_fixture_valid=True,
            test_fixture_captured_from_kabucom_test=False,
            ci_green_attested=resolved_ci_green_attested,
        )

    if not resolved_ci_green_attested:
        return LiveFinancialWriteGateStatus(
            allowed=False,
            reason="ci_green_attestation_missing",
            base_gate_status=base_gate_status,
            test_fixture_path=fixture_path_text,
            test_fixture_present=True,
            test_fixture_valid=True,
            test_fixture_captured_from_kabucom_test=True,
            ci_green_attested=resolved_ci_green_attested,
        )

    return LiveFinancialWriteGateStatus(
        allowed=True,
        reason="ready",
        base_gate_status=base_gate_status,
        test_fixture_path=fixture_path_text,
        test_fixture_present=True,
        test_fixture_valid=True,
        test_fixture_captured_from_kabucom_test=True,
        ci_green_attested=resolved_ci_green_attested,
    )


def can_enable_kabucom_live_financial_write(
    *,
    base_gate_status: LiveOrderGateStatus | None = None,
    test_fixture_path: str | Path | None = None,
    ci_green_attested: bool | None = None,
) -> bool:
    return get_kabucom_live_financial_write_gate_status(
        base_gate_status=base_gate_status,
        test_fixture_path=test_fixture_path,
        ci_green_attested=ci_green_attested,
    ).allowed


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
    return can_enable_kabucom_live_financial_write()
