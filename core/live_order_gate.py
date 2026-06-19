from __future__ import annotations

import json
import os
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.kabucom_contracts import (
    compute_contract_fixture_manifest_hash,
    TEST_CONTRACT_FIXTURE_PATH,
    hash_contract_fixture,
    load_contract_fixture,
    validate_test_contract_fixture,
)

from core.config import (
    APPROVED_CONFIG_HASH,
    DEBUG_MODE,
    ENABLE_LIVE_ORDER,
    JST,
    RUNTIME_LIVE_ORDER_CONFIG_HASH,
    TRADE_MODE,
)
from core.github_actions_artifact_source import (
    GitHubArtifactSourceVerificationResult,
    verify_live_write_attestation_artifact_source,
)
from core.live_approval_manifest import compute_live_approval_manifest_hash
from core.live_approval_manifest import read_git_commit_sha
from core.jpx_calendar import get_jpx_trading_day_status
from core.live_write_attestation import (
    compute_live_write_attestation_hash,
    LIVE_WRITE_ATTESTATION_TEST_COMMAND,
    load_live_write_attestation,
    load_live_write_attestation_digest,
    read_git_remote_repository_full_name,
    validate_live_write_attestation,
)


LIVE_WRITE_ATTESTATION_PATH = Path(__file__).resolve().parents[1] / "contracts" / "kabucom_live_write_attestation.json"


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
    blocking_reasons: tuple[str, ...]
    base_gate_status: LiveOrderGateStatus
    test_fixture_path: str
    test_fixture_present: bool
    test_fixture_valid: bool
    test_fixture_captured_from_kabucom_test: bool
    ci_artifact_attested: bool
    operator_acknowledged: bool
    live_write_attestation_path: str
    live_write_attestation_present: bool
    live_write_attestation_valid: bool
    live_write_attestation_captured_from_kabucom_test: bool
    live_write_attestation_digest_present: bool
    live_write_attestation_digest_valid: bool
    github_artifact_source_required: bool
    github_artifact_source_verified: bool
    github_artifact_source_reason: str
    operator_ack_source: str
    operator_ack_reason: str
    jpx_calendar_ready: bool
    jpx_calendar_trading_day: bool
    jpx_calendar_reason: str


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
    live_readiness_allowed: bool = True
    live_readiness_reason: str = "ready"


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


def _parse_ack_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=JST)
    return parsed.astimezone(JST)


def _load_operator_ack_context() -> tuple[dict[str, Any] | None, str | None]:
    raw = os.getenv("KABUCOM_LIVE_OPERATOR_ACK_CONTEXT")
    if raw is None or not raw.strip():
        return None, None
    try:
        payload = json.loads(raw)
    except Exception:
        return None, "operator_ack_context_invalid_json"
    if not isinstance(payload, dict):
        return None, "operator_ack_context_not_mapping"
    return payload, None


def _resolve_operator_acknowledgement(
    *,
    expected_code_commit_sha: str | None,
    expected_approved_config_hash: str | None,
    expected_runtime_config_hash: str | None,
    expected_repository_full_name: str | None,
    expected_test_fixture_hash: str | None,
    expected_live_write_attestation_hash: str | None,
    allow_legacy_boolean: bool = True,
) -> tuple[bool, str, str]:
    context, context_error = _load_operator_ack_context()
    if context_error is not None:
        return False, "structured_context", context_error

    if context is not None:
        required_keys = {
            "operator_id",
            "acknowledged_at",
            "expires_at",
            "code_commit_sha",
            "approved_config_hash",
            "runtime_config_hash",
            "repository_full_name",
            "test_fixture_hash",
            "live_write_attestation_hash",
        }
        missing = sorted(key for key in required_keys if key not in context)
        if missing:
            return False, "structured_context", f"operator_ack_context_missing:{','.join(missing)}"

        operator_id = str(context.get("operator_id") or "").strip()
        if not operator_id:
            return False, "structured_context", "operator_ack_context_operator_id_missing"

        acknowledged_at = _parse_ack_datetime(context.get("acknowledged_at"))
        if acknowledged_at is None:
            return False, "structured_context", "operator_ack_context_acknowledged_at_invalid"
        expires_at = _parse_ack_datetime(context.get("expires_at"))
        if expires_at is None:
            return False, "structured_context", "operator_ack_context_expires_at_invalid"
        if expires_at <= datetime.now(JST):
            return False, "structured_context", "operator_ack_context_expired"
        if acknowledged_at > expires_at:
            return False, "structured_context", "operator_ack_context_acknowledged_at_after_expiry"

        actual_code_commit_sha = str(context.get("code_commit_sha") or "").strip()
        actual_approved_config_hash = str(context.get("approved_config_hash") or "").strip()
        actual_runtime_config_hash = str(context.get("runtime_config_hash") or "").strip()
        actual_repository_full_name = str(context.get("repository_full_name") or "").strip()
        actual_test_fixture_hash = str(context.get("test_fixture_hash") or "").strip()
        actual_live_write_attestation_hash = str(context.get("live_write_attestation_hash") or "").strip()

        if expected_code_commit_sha is not None and actual_code_commit_sha != str(expected_code_commit_sha).strip():
            return False, "structured_context", "operator_ack_context_code_commit_sha_mismatch"
        if expected_approved_config_hash is not None and actual_approved_config_hash != str(expected_approved_config_hash).strip():
            return False, "structured_context", "operator_ack_context_approved_config_hash_mismatch"
        if expected_runtime_config_hash is not None and actual_runtime_config_hash != str(expected_runtime_config_hash).strip():
            return False, "structured_context", "operator_ack_context_runtime_config_hash_mismatch"
        if expected_repository_full_name is not None and actual_repository_full_name != str(expected_repository_full_name).strip():
            return False, "structured_context", "operator_ack_context_repository_full_name_mismatch"
        if expected_test_fixture_hash is not None and actual_test_fixture_hash != str(expected_test_fixture_hash).strip():
            return False, "structured_context", "operator_ack_context_test_fixture_hash_mismatch"
        if expected_live_write_attestation_hash is not None and actual_live_write_attestation_hash != str(expected_live_write_attestation_hash).strip():
            return False, "structured_context", "operator_ack_context_live_write_attestation_hash_mismatch"

        return True, "structured_context", "operator_ack_context_ok"

    if not allow_legacy_boolean:
        return False, "structured_context", "operator_ack_context_missing"

    resolved_operator_acknowledged = _coerce_env_bool("KABUCOM_LIVE_OPERATOR_ACK", "LIVE_WRITE_OPERATOR_ACK") is True
    if resolved_operator_acknowledged:
        return True, "legacy_bool", "legacy_boolean_true"
    return False, "legacy_bool", "legacy_boolean_false"


def _build_live_financial_write_gate_status(
    *,
    allowed: bool,
    reason: str,
    blocking_reasons: tuple[str, ...],
    base_gate_status: LiveOrderGateStatus,
    test_fixture_path: str,
    test_fixture_present: bool,
    test_fixture_valid: bool,
    test_fixture_captured_from_kabucom_test: bool,
    ci_artifact_attested: bool,
    operator_acknowledged: bool,
    live_write_attestation_path: str,
    live_write_attestation_present: bool,
    live_write_attestation_valid: bool,
    live_write_attestation_captured_from_kabucom_test: bool,
    live_write_attestation_digest_present: bool,
    live_write_attestation_digest_valid: bool,
    github_artifact_source_required: bool,
    github_artifact_source_verified: bool,
    github_artifact_source_reason: str,
    operator_ack_source: str,
    operator_ack_reason: str,
    jpx_calendar_ready: bool,
    jpx_calendar_trading_day: bool,
    jpx_calendar_reason: str,
) -> LiveFinancialWriteGateStatus:
    return LiveFinancialWriteGateStatus(
        allowed=allowed,
        reason=reason,
        blocking_reasons=blocking_reasons,
        base_gate_status=base_gate_status,
        test_fixture_path=test_fixture_path,
        test_fixture_present=test_fixture_present,
        test_fixture_valid=test_fixture_valid,
        test_fixture_captured_from_kabucom_test=test_fixture_captured_from_kabucom_test,
        ci_artifact_attested=ci_artifact_attested,
        operator_acknowledged=operator_acknowledged,
        live_write_attestation_path=live_write_attestation_path,
        live_write_attestation_present=live_write_attestation_present,
        live_write_attestation_valid=live_write_attestation_valid,
        live_write_attestation_captured_from_kabucom_test=live_write_attestation_captured_from_kabucom_test,
        live_write_attestation_digest_present=live_write_attestation_digest_present,
        live_write_attestation_digest_valid=live_write_attestation_digest_valid,
        github_artifact_source_required=github_artifact_source_required,
        github_artifact_source_verified=github_artifact_source_verified,
        github_artifact_source_reason=github_artifact_source_reason,
        operator_ack_source=operator_ack_source,
        operator_ack_reason=operator_ack_reason,
        jpx_calendar_ready=jpx_calendar_ready,
        jpx_calendar_trading_day=jpx_calendar_trading_day,
        jpx_calendar_reason=jpx_calendar_reason,
    )


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
    live_write_attestation_path: str | Path | None = None,
    require_github_artifact_source: bool = False,
    operator_acknowledged: bool | None = None,
) -> LiveFinancialWriteGateStatus:
    """KABUCOM_LIVE の financial write を開けてよいかを総合判定する。

    既存の live order gate に加えて、KABUCOM_TEST fixture の provenance、
    CI artifact attestation bundle、digest sidecar、JPX calendar source、
    operator acknowledgement も fail closed で要求する。
    KABUCOM_LIVE では structured operator ack context が必須で、
    legacy boolean や explicit 引数だけでは開けない。
    """
    base_gate_status = get_live_order_gate_status() if base_gate_status is None else base_gate_status
    fixture_path = TEST_CONTRACT_FIXTURE_PATH if test_fixture_path is None else Path(test_fixture_path)
    fixture_path_text = str(fixture_path)
    attestation_path = LIVE_WRITE_ATTESTATION_PATH if live_write_attestation_path is None else Path(live_write_attestation_path)
    attestation_path_text = str(attestation_path)
    resolved_operator_acknowledged = bool(operator_acknowledged) if operator_acknowledged is not None else False
    operator_ack_source = "explicit_argument" if operator_acknowledged is not None else "not_checked"
    operator_ack_reason = (
        "explicit_argument_true"
        if operator_acknowledged is True
        else "explicit_argument_false" if operator_acknowledged is False
        else "not_checked"
    )

    if not bool(getattr(base_gate_status, "allowed", False)):
        reason = str(getattr(base_gate_status, "reason", "live_order_gate_blocked"))
        return _build_live_financial_write_gate_status(
            allowed=False,
            reason=reason,
            blocking_reasons=(reason,),
            base_gate_status=base_gate_status,
            test_fixture_path=fixture_path_text,
            test_fixture_present=False,
            test_fixture_valid=False,
            test_fixture_captured_from_kabucom_test=False,
            ci_artifact_attested=False,
            operator_acknowledged=resolved_operator_acknowledged,
            live_write_attestation_path=attestation_path_text,
            live_write_attestation_present=False,
            live_write_attestation_valid=False,
            live_write_attestation_captured_from_kabucom_test=False,
            live_write_attestation_digest_present=False,
            live_write_attestation_digest_valid=False,
            github_artifact_source_required=require_github_artifact_source,
            github_artifact_source_verified=False,
            github_artifact_source_reason="not_checked",
            operator_ack_source=operator_ack_source,
            operator_ack_reason=operator_ack_reason,
            jpx_calendar_ready=False,
            jpx_calendar_trading_day=False,
            jpx_calendar_reason="not_checked",
        )

    if str(getattr(base_gate_status, "reason", "")) == "non_live_mode":
        return _build_live_financial_write_gate_status(
            allowed=True,
            reason="non_live_mode",
            blocking_reasons=(),
            base_gate_status=base_gate_status,
            test_fixture_path=fixture_path_text,
            test_fixture_present=False,
            test_fixture_valid=False,
            test_fixture_captured_from_kabucom_test=False,
            ci_artifact_attested=False,
            operator_acknowledged=resolved_operator_acknowledged,
            live_write_attestation_path=attestation_path_text,
            live_write_attestation_present=False,
            live_write_attestation_valid=False,
            live_write_attestation_captured_from_kabucom_test=False,
            live_write_attestation_digest_present=False,
            live_write_attestation_digest_valid=False,
            github_artifact_source_required=require_github_artifact_source,
            github_artifact_source_verified=False,
            github_artifact_source_reason="not_checked",
            operator_ack_source="not_checked",
            operator_ack_reason="non_live_mode",
            jpx_calendar_ready=False,
            jpx_calendar_trading_day=False,
            jpx_calendar_reason="not_checked",
        )

    blocking_reasons: list[str] = []

    fixture = load_contract_fixture(fixture_path)
    fixture_present = fixture is not None
    fixture_valid = False
    fixture_captured_from_test = False
    fixture_captured_at: str | None = None
    fixture_sanitized_fields: tuple[str, ...] = ()
    fixture_redaction_policy: str | None = None
    fixture_hash = hash_contract_fixture(fixture_path)
    contract_manifest_hash = compute_contract_fixture_manifest_hash()
    code_commit_sha = read_git_commit_sha()
    repository_full_name = read_git_remote_repository_full_name()
    attestation_present = False
    attestation_valid = False
    attestation_captured_from_test = False
    attestation_digest_present = False
    attestation_digest_valid = False
    ci_artifact_attested = False
    github_artifact_source_verified = False
    github_artifact_source_reason = "not_checked"
    trade_mode = str(TRADE_MODE).strip().upper()
    is_live_mode = trade_mode == "KABUCOM_LIVE"
    jpx_calendar_status = get_jpx_trading_day_status(require_source=trade_mode == "KABUCOM_LIVE")
    jpx_calendar_ready = bool(jpx_calendar_status.source_ready)
    jpx_calendar_trading_day = bool(jpx_calendar_status.trading_day)
    jpx_calendar_reason = str(jpx_calendar_status.source_reason)

    if code_commit_sha is None:
        blocking_reasons.append("code_commit_sha_unavailable")
    if repository_full_name is None:
        blocking_reasons.append("repository_full_name_unavailable")

    if fixture is None:
        blocking_reasons.append("test_contract_fixture_missing")
    else:
        validation = validate_test_contract_fixture(fixture)
        fixture_valid = bool(validation.valid)
        if not fixture_valid:
            blocking_reasons.append(f"test_contract_fixture_invalid:{validation.reason}")
        else:
            fixture_captured_from_test = bool(fixture.get("captured_from_kabucom_test"))
            fixture_captured_at = str(fixture.get("captured_at") or "").strip() or None
            sanitized_fields_value = fixture.get("sanitized_fields")
            if isinstance(sanitized_fields_value, list):
                fixture_sanitized_fields = tuple(sorted(str(item).strip() for item in sanitized_fields_value if str(item or "").strip()))
            fixture_redaction_policy = str(fixture.get("redaction_policy") or "").strip() or None
            if not fixture_captured_from_test:
                blocking_reasons.append("test_contract_fixture_not_captured_from_kabucom_test")

    attestation = load_live_write_attestation(attestation_path)
    if attestation is None:
        blocking_reasons.append("live_write_attestation_missing")
        attestation_hash = None
    else:
        attestation_present = True
        attestation_hash = compute_live_write_attestation_hash(attestation)
        attestation_digest = load_live_write_attestation_digest(attestation_path)
        if attestation_digest is None:
            blocking_reasons.append("live_write_attestation_digest_missing")
        else:
            attestation_digest_present = True
            if attestation_digest != attestation_hash:
                blocking_reasons.append("live_write_attestation_digest_mismatch")
            else:
                attestation_digest_valid = True
        expected_runtime_config_hash = str(getattr(base_gate_status, "runtime_config_hash", "") or "").strip() or None
        expected_approved_config_hash = str(getattr(base_gate_status, "approved_config_hash", "") or "").strip() or None
        expected_approval_manifest_hash = compute_live_approval_manifest_hash()
        expected_code_commit_sha = code_commit_sha
        expected_repository_full_name = repository_full_name
        attestation_validation = validate_live_write_attestation(
            attestation,
            expected_runtime_config_hash=expected_runtime_config_hash,
            expected_approved_config_hash=expected_approved_config_hash,
            expected_approval_manifest_hash=expected_approval_manifest_hash,
            expected_code_commit_sha=expected_code_commit_sha,
            expected_contract_fixture_manifest_hash=contract_manifest_hash,
            expected_test_fixture_hash=fixture_hash,
            expected_repository_full_name=expected_repository_full_name,
            expected_test_command=LIVE_WRITE_ATTESTATION_TEST_COMMAND,
            expected_captured_from_kabucom_test=True if fixture_captured_from_test else False,
            expected_captured_at=fixture_captured_at,
            expected_sanitized_fields=fixture_sanitized_fields,
            expected_redaction_policy=fixture_redaction_policy,
        )
        attestation_valid = bool(attestation_validation.valid)
        if not attestation_valid:
            blocking_reasons.append(f"live_write_attestation_invalid:{attestation_validation.reason}")
        else:
            attestation_captured_from_test = bool(attestation.get("test_fixture_captured_from_kabucom_test"))
            ci_artifact_attested = bool(fixture_captured_from_test and attestation_captured_from_test)

    if fixture_captured_from_test and not ci_artifact_attested:
        blocking_reasons.append("ci_artifact_attestation_missing")

    if require_github_artifact_source:
        if not attestation_present or not attestation_valid:
            github_artifact_source_reason = "live_write_attestation_unavailable_for_source_verification"
        else:
            github_result: GitHubArtifactSourceVerificationResult = verify_live_write_attestation_artifact_source(
                repository_full_name=repository_full_name or "",
                workflow_run_id=str(attestation.get("ci_run_id") or "").strip(),
                head_sha=str(attestation.get("ci_head_sha") or "").strip(),
                local_attestation_path=attestation_path,
            )
            github_artifact_source_verified = bool(github_result.valid)
            github_artifact_source_reason = str(github_result.reason)
            if not github_result.valid:
                blocking_reasons.append(f"github_attestation_source_unverified:{github_result.reason}")

    if operator_acknowledged is None or is_live_mode:
        resolved_operator_acknowledged, operator_ack_source, operator_ack_reason = _resolve_operator_acknowledgement(
            expected_code_commit_sha=code_commit_sha,
            expected_approved_config_hash=expected_approved_config_hash,
            expected_runtime_config_hash=expected_runtime_config_hash,
            expected_repository_full_name=repository_full_name,
            expected_test_fixture_hash=fixture_hash,
            expected_live_write_attestation_hash=attestation_hash,
            allow_legacy_boolean=not is_live_mode,
        )
    else:
        resolved_operator_acknowledged = bool(operator_acknowledged)
        operator_ack_source = "explicit_argument"
        operator_ack_reason = "explicit_argument_true" if resolved_operator_acknowledged else "explicit_argument_false"

    if is_live_mode:
        if not jpx_calendar_ready:
            blocking_reasons.append(jpx_calendar_reason)
        elif not jpx_calendar_trading_day:
            blocking_reasons.append("jpx_calendar_non_trading_day")

    if not resolved_operator_acknowledged:
        if operator_ack_source == "structured_context" and operator_ack_reason != "operator_ack_context_ok":
            blocking_reasons.append(operator_ack_reason)
        else:
            blocking_reasons.append("operator_ack_missing")

    allowed = not blocking_reasons
    reason = "ready" if allowed else " | ".join(blocking_reasons)
    return _build_live_financial_write_gate_status(
        allowed=allowed,
        reason=reason,
        blocking_reasons=tuple(blocking_reasons),
        base_gate_status=base_gate_status,
        test_fixture_path=fixture_path_text,
        test_fixture_present=fixture_present,
        test_fixture_valid=fixture_valid,
        test_fixture_captured_from_kabucom_test=fixture_captured_from_test,
        ci_artifact_attested=ci_artifact_attested,
        operator_acknowledged=resolved_operator_acknowledged,
        live_write_attestation_path=attestation_path_text,
        live_write_attestation_present=attestation_present,
        live_write_attestation_valid=attestation_valid,
        live_write_attestation_captured_from_kabucom_test=attestation_captured_from_test,
        live_write_attestation_digest_present=attestation_digest_present,
        live_write_attestation_digest_valid=attestation_digest_valid,
        github_artifact_source_required=require_github_artifact_source,
        github_artifact_source_verified=github_artifact_source_verified,
        github_artifact_source_reason=github_artifact_source_reason,
        operator_ack_source=operator_ack_source,
        operator_ack_reason=operator_ack_reason,
        jpx_calendar_ready=jpx_calendar_ready,
        jpx_calendar_trading_day=jpx_calendar_trading_day,
        jpx_calendar_reason=jpx_calendar_reason,
    )


def can_enable_kabucom_live_financial_write(
    *,
    base_gate_status: LiveOrderGateStatus | None = None,
    test_fixture_path: str | Path | None = None,
    live_write_attestation_path: str | Path | None = None,
    require_github_artifact_source: bool = False,
    operator_acknowledged: bool | None = None,
) -> bool:
    return get_kabucom_live_financial_write_gate_status(
        base_gate_status=base_gate_status,
        test_fixture_path=test_fixture_path,
        live_write_attestation_path=live_write_attestation_path,
        require_github_artifact_source=require_github_artifact_source,
        operator_acknowledged=operator_acknowledged,
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
    if not context.live_readiness_allowed:
        readiness_reason = str(context.live_readiness_reason or "").strip() or "not_ready"
        blocking_reasons.append(f"live_readiness_report_unready:{readiness_reason}")

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
    return can_enable_kabucom_live_financial_write(
        require_github_artifact_source=str(TRADE_MODE).strip().upper() == "KABUCOM_LIVE",
    )
