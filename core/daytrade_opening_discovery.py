from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Iterable

from core.config import JST
from core.daytrade_observation_universe import (
    DAYTRADE_DISCOVERY_BATCH_SIZE,
    DAYTRADE_DISCOVERY_MAX_SYMBOLS,
    normalize_daytrade_observation_code,
)


DAYTRADE_DISCOVERY_MAX_SPAN_SECONDS = 30.0


@dataclass(frozen=True)
class DaytradeDiscoveryBatchEvidence:
    batch_index: int
    requested: tuple[str, ...]
    register_ok: bool
    board_requested: tuple[str, ...]
    observed: tuple[str, ...]
    failures: tuple[str, ...]
    unregister_ok: bool
    started_at: datetime
    completed_at: datetime


@dataclass(frozen=True)
class DaytradeProtectedBoardEvidence:
    requested: tuple[str, ...]
    board_requested: tuple[str, ...]
    observed: tuple[str, ...]
    failures: tuple[str, ...]
    started_at: datetime
    completed_at: datetime


@dataclass(frozen=True)
class DaytradeOpeningDiscoveryResult:
    requested: tuple[str, ...]
    observations: dict[str, dict[str, Any]]
    failures: dict[str, str]
    protected_board: DaytradeProtectedBoardEvidence
    batches: tuple[DaytradeDiscoveryBatchEvidence, ...]
    started_at: datetime
    completed_at: datetime
    registry_clean: bool
    final_registered_codes: tuple[str, ...]
    rejection_reasons: tuple[str, ...]

    @property
    def span_seconds(self) -> float:
        return max(0.0, (self.completed_at - self.started_at).total_seconds())

    @property
    def success(self) -> bool:
        return not self.rejection_reasons



def serialize_daytrade_opening_discovery_result(
    result: DaytradeOpeningDiscoveryResult,
) -> dict[str, Any]:
    """Serialize registry/Board evidence without duplicating quote payloads."""
    protected = result.protected_board
    return {
        "requested": list(result.requested),
        "observed": sorted(result.observations),
        "failures": sorted(result.failures),
        "protected_board": {
            "requested": list(protected.requested),
            "board_requested": list(protected.board_requested),
            "observed": list(protected.observed),
            "failures": list(protected.failures),
            "started_at": protected.started_at.isoformat(),
            "completed_at": protected.completed_at.isoformat(),
        },
        "batches": [
            {
                "batch_index": batch.batch_index,
                "requested": list(batch.requested),
                "register_ok": batch.register_ok,
                "board_requested": list(batch.board_requested),
                "observed": list(batch.observed),
                "failures": list(batch.failures),
                "unregister_ok": batch.unregister_ok,
                "started_at": batch.started_at.isoformat(),
                "completed_at": batch.completed_at.isoformat(),
            }
            for batch in result.batches
        ],
        "started_at": result.started_at.isoformat(),
        "completed_at": result.completed_at.isoformat(),
        "max_span_seconds": DAYTRADE_DISCOVERY_MAX_SPAN_SECONDS,
        "registry_clean": result.registry_clean,
        "final_registered_codes": list(result.final_registered_codes),
        "rejection_reasons": list(result.rejection_reasons),
    }

def plan_daytrade_discovery_batches(
    symbols: Iterable[Any],
    *,
    batch_size: int = DAYTRADE_DISCOVERY_BATCH_SIZE,
    max_symbols: int = DAYTRADE_DISCOVERY_MAX_SYMBOLS,
    protected_codes: Iterable[Any] = ("1321",),
) -> tuple[tuple[str, ...], ...]:
    if int(batch_size) != DAYTRADE_DISCOVERY_BATCH_SIZE:
        raise ValueError("daytrade discovery batch size is fixed at 49")
    if int(max_symbols) != DAYTRADE_DISCOVERY_MAX_SYMBOLS:
        raise ValueError("daytrade discovery capacity is fixed at four 49-symbol batches")
    protected = {
        normalize_daytrade_observation_code(code)
        for code in protected_codes
    }
    ordered = []
    seen = set()
    for value in symbols:
        code = normalize_daytrade_observation_code(value)
        if not code or code in protected or code in seen:
            continue
        seen.add(code)
        ordered.append(code)
    if len(ordered) > DAYTRADE_DISCOVERY_MAX_SYMBOLS:
        raise ValueError(
            f"daytrade discovery requested {len(ordered)} symbols; "
            f"maximum is {DAYTRADE_DISCOVERY_MAX_SYMBOLS}"
        )
    return tuple(
        tuple(ordered[offset:offset + DAYTRADE_DISCOVERY_BATCH_SIZE])
        for offset in range(0, len(ordered), DAYTRADE_DISCOVERY_BATCH_SIZE)
    )


def _call_registry_mutation(broker: Any, method_name: str, codes: list[str]) -> bool:
    try:
        method = getattr(broker, method_name)
        return bool(method(codes))
    except Exception:
        # The caller still attempts the complementary cleanup operation.
        return False


def collect_daytrade_opening_discovery(
    broker: Any,
    symbols: Iterable[Any],
    *,
    initial_registered_codes: Iterable[Any],
    protected_codes: Iterable[Any] = ("1321",),
    clock: Callable[[], datetime] | None = None,
) -> DaytradeOpeningDiscoveryResult:
    """Rotate explicit registry batches and collect immutable official opens fail closed."""
    now = clock or (lambda: datetime.now(JST))
    started_at = now()
    protected = {
        normalize_daytrade_observation_code(code)
        for code in protected_codes
        if normalize_daytrade_observation_code(code)
    }
    registered = {
        normalize_daytrade_observation_code(code)
        for code in initial_registered_codes
        if normalize_daytrade_observation_code(code)
    }
    observations: dict[str, dict[str, Any]] = {}
    failures: dict[str, str] = {}
    evidence: list[DaytradeDiscoveryBatchEvidence] = []
    rejection_reasons: list[str] = []
    registry_clean = True
    empty_protected_evidence = DaytradeProtectedBoardEvidence(
        requested=tuple(sorted(protected)),
        board_requested=(),
        observed=(),
        failures=(),
        started_at=started_at,
        completed_at=started_at,
    )

    try:
        batches = plan_daytrade_discovery_batches(
            symbols,
            protected_codes=protected,
        )
    except ValueError as exc:
        completed_at = now()
        return DaytradeOpeningDiscoveryResult(
            requested=(),
            observations={},
            failures={},
            protected_board=empty_protected_evidence,
            batches=(),
            started_at=started_at,
            completed_at=completed_at,
            registry_clean=False,
            final_registered_codes=tuple(sorted(registered)),
            rejection_reasons=(f"discovery_plan_invalid:{exc}",),
        )

    requested = tuple(code for batch in batches for code in batch)
    cleanup_codes = sorted(registered - protected)
    if cleanup_codes:
        cleanup_ok = _call_registry_mutation(broker, "unregister_symbols", cleanup_codes)
        if cleanup_ok:
            registered.difference_update(cleanup_codes)
        else:
            registry_clean = False
            rejection_reasons.append("initial_registry_cleanup_failed")

    missing_protected = sorted(protected - registered)
    if registry_clean and missing_protected:
        protected_ok = _call_registry_mutation(broker, "register_symbols", missing_protected)
        if protected_ok:
            registered.update(missing_protected)
        else:
            registry_clean = False
            rejection_reasons.append("protected_registry_registration_failed")

    protected_evidence = empty_protected_evidence
    if registry_clean:
        protected_requested = tuple(sorted(protected))
        protected_started_at = now()
        protected_board_requested: tuple[str, ...] = ()
        protected_observed: tuple[str, ...] = ()
        protected_failures: tuple[str, ...] = ()
        try:
            board_result = broker.get_board_snapshot_batch(list(protected_requested))
        except Exception:
            board_result = None
            protected_failures = protected_requested
            for code in protected_requested:
                failures[code] = "board_exception"
            rejection_reasons.append("protected_board_exception")
        if board_result is not None:
            protected_board_requested = tuple(
                normalize_daytrade_observation_code(code)
                for code in getattr(board_result, "requested", ())
            )
            protected_observations = {
                normalize_daytrade_observation_code(code): dict(value)
                for code, value in dict(
                    getattr(board_result, "observations", {}) or {}
                ).items()
            }
            normalized_protected_failures = {
                normalize_daytrade_observation_code(code): failure
                for code, failure in dict(
                    getattr(board_result, "failures", {}) or {}
                ).items()
            }
            if protected_board_requested != protected_requested:
                rejection_reasons.append("protected_board_request_mismatch")
            protected_returned = (
                set(protected_observations) | set(normalized_protected_failures)
            )
            if (
                protected_returned != set(protected_requested)
                or set(protected_observations).intersection(
                    normalized_protected_failures
                )
            ):
                rejection_reasons.append("protected_board_result_mismatch")
            observations.update(protected_observations)
            for normalized, failure in normalized_protected_failures.items():
                reason = str(getattr(failure, "reason", None) or "unknown")
                failures[normalized] = reason
            protected_observed = tuple(sorted(protected_observations))
            protected_failures = tuple(sorted(normalized_protected_failures))
            if protected_failures:
                rejection_reasons.append("protected_board_failures")
        protected_completed_at = now()
        protected_evidence = DaytradeProtectedBoardEvidence(
            requested=protected_requested,
            board_requested=protected_board_requested,
            observed=protected_observed,
            failures=protected_failures,
            started_at=protected_started_at,
            completed_at=protected_completed_at,
        )

    if registry_clean and not rejection_reasons:
        for batch_index, batch in enumerate(batches):
            batch_started_at = now()
            register_ok = _call_registry_mutation(broker, "register_symbols", list(batch))
            if register_ok:
                registered.update(batch)

            board_requested: tuple[str, ...] = ()
            observed_codes: tuple[str, ...] = ()
            failure_codes: tuple[str, ...] = ()
            if register_ok:
                try:
                    board_result = broker.get_board_snapshot_batch(list(batch))
                except Exception:
                    board_result = None
                    failure_codes = tuple(sorted(batch))
                    for code in batch:
                        failures[code] = "board_exception"
                    rejection_reasons.append(f"batch_{batch_index}:board_exception")
                if board_result is not None:
                    board_requested = tuple(
                        normalize_daytrade_observation_code(code)
                        for code in getattr(board_result, "requested", ())
                    )
                    batch_observations = {
                        normalize_daytrade_observation_code(code): dict(value)
                        for code, value in dict(
                            getattr(board_result, "observations", {}) or {}
                        ).items()
                    }
                    batch_failures = dict(getattr(board_result, "failures", {}) or {})
                    normalized_failures = {
                        normalize_daytrade_observation_code(code): failure
                        for code, failure in batch_failures.items()
                    }
                    if tuple(sorted(board_requested)) != tuple(sorted(batch)):
                        rejection_reasons.append(f"batch_{batch_index}:board_request_mismatch")
                    returned_codes = set(batch_observations) | set(normalized_failures)
                    if (
                        returned_codes != set(batch)
                        or set(batch_observations).intersection(normalized_failures)
                    ):
                        rejection_reasons.append(f"batch_{batch_index}:board_result_mismatch")
                    observations.update(batch_observations)
                    for normalized, failure in normalized_failures.items():
                        reason = str(getattr(failure, "reason", None) or "unknown")
                        failures[normalized] = reason
                    observed_codes = tuple(sorted(batch_observations))
                    failure_codes = tuple(sorted(normalized_failures))
            else:
                for code in batch:
                    failures[code] = "register_failed"

            unregister_ok = _call_registry_mutation(
                broker,
                "unregister_symbols",
                list(batch),
            )
            if unregister_ok:
                registered.difference_update(batch)
            else:
                registry_clean = False
                rejection_reasons.append(f"batch_{batch_index}:unregister_failed")

            batch_completed_at = now()
            evidence.append(
                DaytradeDiscoveryBatchEvidence(
                    batch_index=batch_index,
                    requested=batch,
                    register_ok=register_ok,
                    board_requested=board_requested,
                    observed=observed_codes,
                    failures=failure_codes,
                    unregister_ok=unregister_ok,
                    started_at=batch_started_at,
                    completed_at=batch_completed_at,
                )
            )
            if not register_ok:
                rejection_reasons.append(f"batch_{batch_index}:register_failed")
            if not register_ok or not unregister_ok:
                break

    completed_at = now()
    missing = sorted(set(requested) - set(observations))
    if missing:
        rejection_reasons.append("discovery_observations_missing:" + ",".join(missing))
    if failures:
        rejection_reasons.append("discovery_board_failures")
    missing_protected_observations = sorted(protected - set(observations))
    if missing_protected_observations:
        rejection_reasons.append(
            "protected_observations_missing:"
            + ",".join(missing_protected_observations)
        )
    if registered != protected:
        registry_clean = False
        rejection_reasons.append("discovery_registry_not_restored")
    span_seconds = max(0.0, (completed_at - started_at).total_seconds())
    if span_seconds > DAYTRADE_DISCOVERY_MAX_SPAN_SECONDS:
        rejection_reasons.append("discovery_span_exceeded")
    if not registry_clean:
        rejection_reasons.append("discovery_registry_dirty")

    return DaytradeOpeningDiscoveryResult(
        requested=requested,
        observations=observations,
        failures=failures,
        protected_board=protected_evidence,
        batches=tuple(evidence),
        started_at=started_at,
        completed_at=completed_at,
        registry_clean=registry_clean,
        final_registered_codes=tuple(sorted(registered)),
        rejection_reasons=tuple(dict.fromkeys(rejection_reasons)),
    )
