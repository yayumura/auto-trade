from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Mapping

from core.config import JST, RUNTIME_LIVE_ORDER_CONFIG_HASH
from core.live_approval_manifest import compute_live_approval_manifest_hash, read_git_commit_sha
from core.order_journal import OrderJournalReplaySummary
from core.startup_recovery import StartupRecoveryReport

try:
    from core.kabucom_broker import REQUEST_BUDGET_LIMITS, RequestBudgetBucket
except Exception:  # pragma: no cover - import cycle guard for partial imports
    REQUEST_BUDGET_LIMITS = {}
    RequestBudgetBucket = None  # type: ignore[assignment]


LIVE_READINESS_STATUS_READY = "ready"
LIVE_READINESS_STATUS_BLOCKED = "blocked"
LIVE_READINESS_STATUS_NOT_VERIFIED = "not_verified"
LIVE_RISK_REVIEW_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class LiveReadinessItem:
    name: str
    status: str
    reason: str
    evidence: tuple[str, ...]
    checked_at: str

    @property
    def is_ready(self) -> bool:
        return self.status == LIVE_READINESS_STATUS_READY


@dataclass(frozen=True)
class LiveReadinessReport:
    schema_version: int
    checked_at: str
    allowed: bool
    reason: str
    items: tuple[LiveReadinessItem, ...]

    @property
    def blocking_items(self) -> tuple[LiveReadinessItem, ...]:
        return tuple(item for item in self.items if item.status != LIVE_READINESS_STATUS_READY)

    @property
    def blocking_reasons(self) -> tuple[str, ...]:
        return tuple(item.reason for item in self.blocking_items)

    @property
    def not_verified_items(self) -> tuple[LiveReadinessItem, ...]:
        return tuple(item for item in self.items if item.status == LIVE_READINESS_STATUS_NOT_VERIFIED)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "checked_at": self.checked_at,
            "allowed": self.allowed,
            "reason": self.reason,
            "items": [
                {
                    "name": item.name,
                    "status": item.status,
                    "reason": item.reason,
                    "evidence": list(item.evidence),
                    "checked_at": item.checked_at,
                }
                for item in self.items
            ],
        }

    def format_compact(self) -> str:
        if self.allowed:
            return f"allowed=True reason={self.reason}"
        blocked = " | ".join(
            f"{item.name}:{item.status}:{item.reason}"
            for item in self.blocking_items
        )
        return f"allowed=False reason={self.reason} blocked={blocked}"


def _now_checked_at(checked_at: datetime | None = None) -> str:
    if checked_at is None:
        checked_at = datetime.now(JST)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=JST)
    else:
        checked_at = checked_at.astimezone(JST)
    return checked_at.isoformat()


def _make_item(
    name: str,
    status: str,
    reason: str,
    evidence: tuple[str, ...],
    checked_at: str,
) -> LiveReadinessItem:
    return LiveReadinessItem(
        name=name,
        status=status,
        reason=reason,
        evidence=tuple(str(entry) for entry in evidence if str(entry or "").strip()),
        checked_at=checked_at,
    )


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _read_json_payload(path: str | Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    target = Path(path)
    if not target.exists():
        return None
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    return raw


def _normalize_request_budget_counts(request_budget_counts: Mapping[Any, Any] | None) -> dict[str, int]:
    normalized: dict[str, int] = {}
    if not isinstance(request_budget_counts, Mapping):
        return normalized
    for bucket in REQUEST_BUDGET_LIMITS:
        bucket_value = getattr(bucket, "value", str(bucket))
        count = 0
        if bucket in request_budget_counts:
            count = request_budget_counts[bucket]
        elif bucket_value in request_budget_counts:
            count = request_budget_counts[bucket_value]
        else:
            bucket_name = getattr(bucket, "name", bucket_value)
            if bucket_name in request_budget_counts:
                count = request_budget_counts[bucket_name]
        try:
            normalized[bucket_value] = max(0, int(count))
        except (TypeError, ValueError):
            normalized[bucket_value] = 0
    return normalized


def _portfolio_execution_id_truth(
    portfolio: list[dict[str, Any]] | None,
) -> tuple[str, str, tuple[str, ...]]:
    if portfolio is None:
        return LIVE_READINESS_STATUS_NOT_VERIFIED, "portfolio_missing", ()

    managed_positions: list[dict[str, Any]] = []
    for position in portfolio:
        if not isinstance(position, Mapping):
            continue
        if _as_text(position.get("ownership")).upper() == "MANAGED_BY_BOT":
            managed_positions.append(dict(position))

    if not managed_positions:
        return LIVE_READINESS_STATUS_READY, "managed_positions_empty", ("managed_positions=0",)

    review_needed: list[str] = []
    evidence: list[str] = []
    for position in managed_positions:
        code = _as_text(position.get("code")) or _as_text(position.get("symbol")) or "unknown"
        source = _as_text(position.get("position_lot_key_source"))
        needs_review = bool(position.get("position_lot_key_needs_review"))
        if source:
            evidence.append(f"{code}:{source}")
        else:
            evidence.append(f"{code}:missing")
        if needs_review or source not in {"execution_id", "execution_ids"}:
            review_needed.append(code)

    if review_needed:
        return (
            LIVE_READINESS_STATUS_BLOCKED,
            f"execution_id_truth_needs_review:{','.join(review_needed[:10])}",
            tuple(evidence),
        )
    return LIVE_READINESS_STATUS_READY, "execution_id_truth_verified", tuple(evidence)


def _build_protective_stop_item(
    startup_recovery_report: StartupRecoveryReport | None,
    checked_at: str,
) -> LiveReadinessItem:
    name = "protective_stop_lifecycle"
    if startup_recovery_report is None:
        return _make_item(name, LIVE_READINESS_STATUS_NOT_VERIFIED, "startup_recovery_missing", (), checked_at)

    evidence = (
        f"pending={startup_recovery_report.protective_stop_pending_count}",
        f"orphan={startup_recovery_report.protective_stop_orphan_count}",
        f"missing={startup_recovery_report.protective_stop_missing_count}",
        f"manual_review={startup_recovery_report.needs_manual_review}",
    )
    if (
        startup_recovery_report.protective_stop_pending_count > 0
        or startup_recovery_report.protective_stop_orphan_count > 0
        or startup_recovery_report.protective_stop_missing_count > 0
    ):
        reason = "protective_stop_reconciliation_pending"
        return _make_item(name, LIVE_READINESS_STATUS_BLOCKED, reason, evidence, checked_at)
    if startup_recovery_report.needs_manual_review:
        reason = "startup_recovery_manual_review_required"
        return _make_item(name, LIVE_READINESS_STATUS_BLOCKED, reason, evidence, checked_at)
    return _make_item(name, LIVE_READINESS_STATUS_READY, "protective_stop_lifecycle_clear", evidence, checked_at)


def _build_partial_fill_item(
    startup_recovery_report: StartupRecoveryReport | None,
    checked_at: str,
) -> LiveReadinessItem:
    name = "partial_fill_unresolved"
    if startup_recovery_report is None:
        return _make_item(name, LIVE_READINESS_STATUS_NOT_VERIFIED, "startup_recovery_missing", (), checked_at)

    evidence = (
        f"entry_unresolved={startup_recovery_report.entry_unresolved_count}",
        f"exit_unresolved={startup_recovery_report.exit_unresolved_count}",
    )
    if startup_recovery_report.entry_unresolved_count > 0 or startup_recovery_report.exit_unresolved_count > 0:
        return _make_item(name, LIVE_READINESS_STATUS_BLOCKED, "unresolved_entry_or_exit_state", evidence, checked_at)
    return _make_item(name, LIVE_READINESS_STATUS_READY, "no_unresolved_partial_fills", evidence, checked_at)


def _build_execution_id_item(
    portfolio: list[dict[str, Any]] | None,
    checked_at: str,
) -> LiveReadinessItem:
    name = "execution_id_truth"
    status, reason, evidence = _portfolio_execution_id_truth(portfolio)
    return _make_item(name, status, reason, evidence, checked_at)


def _build_quote_freshness_item(
    quote_fresh: bool | None,
    checked_at: str,
) -> LiveReadinessItem:
    name = "quote_freshness"
    if quote_fresh is None:
        return _make_item(name, LIVE_READINESS_STATUS_NOT_VERIFIED, "quote_freshness_missing", (), checked_at)
    evidence = (f"quote_fresh={bool(quote_fresh)}",)
    if quote_fresh:
        return _make_item(name, LIVE_READINESS_STATUS_READY, "quote_snapshot_fresh", evidence, checked_at)
    return _make_item(name, LIVE_READINESS_STATUS_BLOCKED, "quote_snapshot_stale", evidence, checked_at)


def _build_journal_reconciliation_item(
    startup_recovery_report: StartupRecoveryReport | None,
    order_journal_summary: OrderJournalReplaySummary | None,
    checked_at: str,
) -> LiveReadinessItem:
    name = "journal_reconciliation"
    if startup_recovery_report is None or order_journal_summary is None:
        return _make_item(name, LIVE_READINESS_STATUS_NOT_VERIFIED, "journal_evidence_missing", (), checked_at)

    evidence = (
        f"journal_unresolved={order_journal_summary.unresolved_count}",
        f"journal_corrupt_lines={order_journal_summary.corrupt_lines}",
        f"active_orders_unknown={startup_recovery_report.active_orders_unknown_count}",
    )
    if (
        order_journal_summary.unresolved_count > 0
        or order_journal_summary.corrupt_lines > 0
        or startup_recovery_report.active_orders_unknown_count > 0
    ):
        return _make_item(name, LIVE_READINESS_STATUS_BLOCKED, "journal_or_active_order_reconciliation_pending", evidence, checked_at)
    return _make_item(name, LIVE_READINESS_STATUS_READY, "journal_reconciliation_clear", evidence, checked_at)


def _build_request_budget_item(
    request_budget_counts: Mapping[Any, Any] | None,
    checked_at: str,
) -> LiveReadinessItem:
    name = "request_budget"
    if not isinstance(request_budget_counts, Mapping):
        return _make_item(name, LIVE_READINESS_STATUS_NOT_VERIFIED, "request_budget_snapshot_missing", (), checked_at)

    counts = _normalize_request_budget_counts(request_budget_counts)
    if not counts:
        return _make_item(name, LIVE_READINESS_STATUS_NOT_VERIFIED, "request_budget_snapshot_empty", (), checked_at)

    over_limit: list[str] = []
    evidence: list[str] = []
    for bucket_value, limit in sorted(REQUEST_BUDGET_LIMITS.items(), key=lambda item: getattr(item[0], "value", str(item[0]))):
        bucket_name = getattr(bucket_value, "value", str(bucket_value))
        count = counts.get(bucket_name, 0)
        evidence.append(f"{bucket_name}={count}/{int(limit)}")
        if count > int(limit):
            over_limit.append(f"{bucket_name}:{count}>{int(limit)}")
    if over_limit:
        return _make_item(
            name,
            LIVE_READINESS_STATUS_BLOCKED,
            f"request_budget_exceeded:{','.join(over_limit[:10])}",
            tuple(evidence),
            checked_at,
        )
    return _make_item(name, LIVE_READINESS_STATUS_READY, "request_budget_within_limits", tuple(evidence), checked_at)


def _normalize_evidence_value(value: Any) -> str:
    if isinstance(value, Mapping):
        return json.dumps({str(k): _normalize_evidence_value(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}, ensure_ascii=False, sort_keys=True)
    if isinstance(value, (list, tuple, set)):
        return json.dumps([_normalize_evidence_value(item) for item in value], ensure_ascii=False)
    return _as_text(value)


def _build_risk_review_item(
    risk_review_path: str | Path | None,
    checked_at: str,
    *,
    expected_code_commit_sha: str | None,
    expected_runtime_config_hash: str | None,
    expected_approval_manifest_hash: str | None,
) -> tuple[LiveReadinessItem, dict[str, Any] | None]:
    name = "risk_readiness"
    payload = _read_json_payload(risk_review_path)
    if payload is None:
        return _make_item(name, LIVE_READINESS_STATUS_NOT_VERIFIED, "risk_review_missing", (), checked_at), None

    evidence = [f"risk_review_path={Path(risk_review_path).as_posix() if risk_review_path is not None else ''}"]
    missing: list[str] = []
    schema_version = payload.get("schema_version")
    try:
        schema_version_int = int(schema_version)
    except (TypeError, ValueError):
        schema_version_int = 0
    if schema_version_int < LIVE_RISK_REVIEW_SCHEMA_VERSION:
        missing.append("schema_version")

    status = _as_text(payload.get("status")).lower()
    if not status:
        missing.append("status")
    elif status != "ready":
        return _make_item(
            name,
            LIVE_READINESS_STATUS_BLOCKED,
            f"risk_review_status_not_ready:{status}",
            tuple(evidence + [f"status={status}"]),
            checked_at,
        ), payload

    reviewed_at = _as_text(payload.get("reviewed_at"))
    reviewer = _as_text(payload.get("reviewer"))
    if not reviewed_at:
        missing.append("reviewed_at")
    if not reviewer:
        missing.append("reviewer")

    code_commit_sha = _as_text(payload.get("code_commit_sha"))
    if not code_commit_sha:
        missing.append("code_commit_sha")
    elif expected_code_commit_sha is not None and code_commit_sha != expected_code_commit_sha:
        return _make_item(
            name,
            LIVE_READINESS_STATUS_BLOCKED,
            "risk_review_code_commit_sha_mismatch",
            tuple(evidence + [f"code_commit_sha={code_commit_sha}", f"expected={expected_code_commit_sha}"]),
            checked_at,
        ), payload

    runtime_config_hash = _as_text(payload.get("runtime_config_hash"))
    if not runtime_config_hash:
        missing.append("runtime_config_hash")
    elif expected_runtime_config_hash is not None and runtime_config_hash != expected_runtime_config_hash:
        return _make_item(
            name,
            LIVE_READINESS_STATUS_BLOCKED,
            "risk_review_runtime_config_hash_mismatch",
            tuple(evidence + [f"runtime_config_hash={runtime_config_hash}", f"expected={expected_runtime_config_hash}"]),
            checked_at,
        ), payload

    approval_manifest_hash = _as_text(payload.get("approval_manifest_hash"))
    if not approval_manifest_hash:
        missing.append("approval_manifest_hash")
    elif expected_approval_manifest_hash is not None and approval_manifest_hash != expected_approval_manifest_hash:
        return _make_item(
            name,
            LIVE_READINESS_STATUS_BLOCKED,
            "risk_review_approval_manifest_hash_mismatch",
            tuple(evidence + [f"approval_manifest_hash={approval_manifest_hash}", f"expected={expected_approval_manifest_hash}"]),
            checked_at,
        ), payload

    required_sections = (
        "train_holdout_review",
        "walk_forward_review",
        "transaction_cost_stress",
        "slippage_stress",
        "capacity_liquidity_stress",
        "rule_complexity_report",
    )
    for section_name in required_sections:
        section_value = payload.get(section_name)
        if section_value in (None, "", [], {}):
            missing.append(section_name)
            continue
        evidence.append(f"{section_name}={_normalize_evidence_value(section_value)}")

    no_lookahead_audit_hash = _as_text(payload.get("no_lookahead_audit_hash"))
    if not no_lookahead_audit_hash:
        missing.append("no_lookahead_audit_hash")
    else:
        evidence.append(f"no_lookahead_audit_hash={no_lookahead_audit_hash}")

    if missing:
        return _make_item(
            name,
            LIVE_READINESS_STATUS_BLOCKED,
            f"risk_review_missing_fields:{','.join(sorted(set(missing)))}",
            tuple(evidence + [f"reviewed_at={reviewed_at}", f"reviewer={reviewer}"]),
            checked_at,
        ), payload

    evidence.extend(
        [
            f"schema_version={schema_version_int}",
            f"reviewed_at={reviewed_at}",
            f"reviewer={reviewer}",
            f"code_commit_sha={code_commit_sha}",
            f"runtime_config_hash={runtime_config_hash}",
            f"approval_manifest_hash={approval_manifest_hash}",
        ]
    )
    return _make_item(
        name,
        LIVE_READINESS_STATUS_READY,
        "risk_review_ready",
        tuple(evidence),
        checked_at,
    ), payload


def _build_no_lookahead_item(
    risk_review_item: LiveReadinessItem,
    risk_review_payload: dict[str, Any] | None,
    checked_at: str,
) -> LiveReadinessItem:
    name = "no_lookahead_audit"
    if risk_review_payload is None:
        if risk_review_item.status == LIVE_READINESS_STATUS_NOT_VERIFIED:
            return _make_item(name, LIVE_READINESS_STATUS_NOT_VERIFIED, "risk_review_missing", (), checked_at)
        return _make_item(name, LIVE_READINESS_STATUS_BLOCKED, "risk_review_unavailable_for_audit", (), checked_at)

    no_lookahead_audit_hash = _as_text(risk_review_payload.get("no_lookahead_audit_hash"))
    if not no_lookahead_audit_hash:
        return _make_item(name, LIVE_READINESS_STATUS_BLOCKED, "no_lookahead_audit_hash_missing", risk_review_item.evidence, checked_at)
    return _make_item(
        name,
        LIVE_READINESS_STATUS_READY,
        "no_lookahead_audit_ready",
        tuple(list(risk_review_item.evidence) + [f"no_lookahead_audit_hash={no_lookahead_audit_hash}"]),
        checked_at,
    )


def build_live_readiness_report(
    *,
    portfolio: list[dict[str, Any]] | None = None,
    startup_recovery_report: StartupRecoveryReport | None = None,
    order_journal_summary: OrderJournalReplaySummary | None = None,
    request_budget_counts: Mapping[Any, Any] | None = None,
    quote_fresh: bool | None = None,
    risk_review_path: str | Path | None = None,
    expected_code_commit_sha: str | None = None,
    expected_runtime_config_hash: str | None = None,
    expected_approval_manifest_hash: str | None = None,
    checked_at: datetime | None = None,
) -> LiveReadinessReport:
    checked_at_text = _now_checked_at(checked_at)
    expected_code_commit_sha = expected_code_commit_sha or read_git_commit_sha()
    expected_runtime_config_hash = expected_runtime_config_hash or RUNTIME_LIVE_ORDER_CONFIG_HASH
    expected_approval_manifest_hash = expected_approval_manifest_hash or compute_live_approval_manifest_hash()

    protective_stop_item = _build_protective_stop_item(startup_recovery_report, checked_at_text)
    partial_fill_item = _build_partial_fill_item(startup_recovery_report, checked_at_text)
    execution_id_item = _build_execution_id_item(portfolio, checked_at_text)
    quote_freshness_item = _build_quote_freshness_item(quote_fresh, checked_at_text)
    journal_item = _build_journal_reconciliation_item(startup_recovery_report, order_journal_summary, checked_at_text)
    request_budget_item = _build_request_budget_item(request_budget_counts, checked_at_text)
    risk_item, risk_payload = _build_risk_review_item(
        risk_review_path,
        checked_at_text,
        expected_code_commit_sha=expected_code_commit_sha,
        expected_runtime_config_hash=expected_runtime_config_hash,
        expected_approval_manifest_hash=expected_approval_manifest_hash,
    )
    no_lookahead_item = _build_no_lookahead_item(risk_item, risk_payload, checked_at_text)

    items = (
        protective_stop_item,
        partial_fill_item,
        execution_id_item,
        quote_freshness_item,
        journal_item,
        request_budget_item,
        risk_item,
        no_lookahead_item,
    )
    blocking_items = tuple(item for item in items if item.status != LIVE_READINESS_STATUS_READY)
    allowed = not blocking_items
    if allowed:
        reason = "ready"
    else:
        reason = " | ".join(
            f"{item.name}:{item.status}:{item.reason}"
            for item in blocking_items
        )
    return LiveReadinessReport(
        schema_version=1,
        checked_at=checked_at_text,
        allowed=allowed,
        reason=reason,
        items=items,
    )
