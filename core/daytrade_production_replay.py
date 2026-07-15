from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

from core.daytrade_candidate_engine import (
    DaytradeOpenArrayView,
    generate_daytrade_candidate_groups,
)
from core.file_io import append_jsonl, ensure_absolute_path
from core.daytrade_opening_discovery import DAYTRADE_DISCOVERY_MAX_SPAN_SECONDS
from core.daytrade_observation_universe import (
    DAYTRADE_DISCOVERY_BATCH_COUNT,
    DAYTRADE_DISCOVERY_BATCH_SIZE,
    DAYTRADE_DISCOVERY_MAX_SYMBOLS,
)
from core.logic import (
    build_daytrade_open_market_context,
    select_daytrade_candidates,
)


DAYTRADE_PRODUCTION_SNAPSHOT_SCHEMA_VERSION = 4
DAYTRADE_MAX_BOARD_BATCH_SPAN_SECONDS = 30.0
DAYTRADE_SERVER_CLOCK_MAX_ABS_DRIFT_SECONDS = 30.0
DAYTRADE_PRODUCTION_STRATEGY_PATH = "observed_open_shared_engine_v1"
DAYTRADE_OBSERVATION_POLICY_FIXED_49 = "production_fixed_49_v1"
DAYTRADE_OBSERVATION_POLICY_ROTATING_196 = "rotating_discovery_196_v1"
_GROUP_NAMES = (
    "primary",
    "strong_oversold",
    "fallback",
    "catchup",
    "inverse",
    "bull_etf",
)


@dataclass(frozen=True, slots=True)
class DaytradeProductionReplayResult:
    snapshot_id: str
    replayable: bool
    parity: bool
    rejection_reasons: tuple[str, ...]
    selected_codes: tuple[str, ...]
    candidate_digest: str
    selected_digest: str


def _date_text(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()
    if not text:
        raise ValueError("date value is required")
    return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()


def _datetime_text(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value or "").strip()
    if not text:
        raise ValueError("datetime value is required")
    return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()


def _parse_datetime(value: Any) -> datetime:
    return datetime.fromisoformat(_datetime_text(value).replace("Z", "+00:00"))


def _is_jst_aware(value: datetime) -> bool:
    return value.utcoffset() == timedelta(hours=9)


def _float_or_none(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _decode_float(value: Any) -> float:
    result = _float_or_none(value)
    return np.nan if result is None else result


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _json_safe(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_daytrade_digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_code(value: Any) -> str:
    code = str(value or "").strip().upper()
    return code[:-2] if code.endswith(".T") else code



def _code_tuple(values: Any) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes)) or not isinstance(
        values, (list, tuple, set, frozenset)
    ):
        values = (values,)
    return tuple(_normalize_code(value) for value in values)


def _validate_rotating_discovery_evidence(
    inputs: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> tuple[str, ...]:
    reasons: list[str] = []
    requested = _code_tuple(evidence.get("requested"))
    protected = ("1321",)
    expected_all = set(requested) | set(protected)
    input_requested = _code_tuple(inputs.get("requested_codes"))

    if len(requested) != DAYTRADE_DISCOVERY_MAX_SYMBOLS:
        reasons.append("opening_discovery_requested_count_invalid")
    if (
        len(set(requested)) != len(requested)
        or any(not code for code in requested)
        or any(code in protected for code in requested)
    ):
        reasons.append("opening_discovery_requested_codes_invalid")
    if set(input_requested) != expected_all or len(input_requested) != len(expected_all):
        reasons.append("opening_discovery_snapshot_request_mismatch")
    observed = _code_tuple(evidence.get("observed"))
    if set(observed) != expected_all or len(observed) != len(expected_all):
        reasons.append("opening_discovery_observed_codes_mismatch")
    if _code_tuple(evidence.get("failures")):
        reasons.append("opening_discovery_failures_present")
    if evidence.get("registry_clean") is not True:
        reasons.append("opening_discovery_registry_dirty")
    if _code_tuple(evidence.get("final_registered_codes")) != protected:
        reasons.append("opening_discovery_registry_not_restored")
    if evidence.get("rejection_reasons"):
        reasons.append("opening_discovery_rejection_present")
    if _float_or_none(evidence.get("max_span_seconds")) != DAYTRADE_DISCOVERY_MAX_SPAN_SECONDS:
        reasons.append("opening_discovery_max_span_mismatch")

    protected_raw = evidence.get("protected_board")
    if isinstance(protected_raw, Mapping):
        protected_board = dict(protected_raw)
    else:
        protected_board = {}
        reasons.append("opening_discovery_protected_evidence_invalid")
    for field in ("requested", "board_requested", "observed"):
        if _code_tuple(protected_board.get(field)) != protected:
            reasons.append(f"opening_discovery_protected_{field}_mismatch")
    if _code_tuple(protected_board.get("failures")):
        reasons.append("opening_discovery_protected_failures_present")

    raw_batches = evidence.get("batches")
    if isinstance(raw_batches, (list, tuple)):
        batches = list(raw_batches)
    else:
        batches = []
        reasons.append("opening_discovery_batches_invalid")
    if len(batches) != DAYTRADE_DISCOVERY_BATCH_COUNT:
        reasons.append("opening_discovery_batch_count_invalid")
    flattened: list[str] = []
    normalized_batches: list[dict[str, Any]] = []
    for position, raw_batch in enumerate(batches):
        if isinstance(raw_batch, Mapping):
            batch = dict(raw_batch)
        else:
            batch = {}
            reasons.append(f"opening_discovery_batch_{position}_evidence_invalid")
        normalized_batches.append(batch)
        try:
            batch_index = int(batch.get("batch_index"))
        except (TypeError, ValueError):
            batch_index = -1
        if batch_index != position:
            reasons.append(f"opening_discovery_batch_{position}_index_invalid")
        batch_requested = _code_tuple(batch.get("requested"))
        flattened.extend(batch_requested)
        if len(batch_requested) != DAYTRADE_DISCOVERY_BATCH_SIZE:
            reasons.append(f"opening_discovery_batch_{position}_size_invalid")
        if _code_tuple(batch.get("board_requested")) != batch_requested:
            reasons.append(f"opening_discovery_batch_{position}_request_mismatch")
        batch_observed = _code_tuple(batch.get("observed"))
        if (
            set(batch_observed) != set(batch_requested)
            or len(batch_observed) != len(batch_requested)
        ):
            reasons.append(f"opening_discovery_batch_{position}_observed_mismatch")
        if _code_tuple(batch.get("failures")):
            reasons.append(f"opening_discovery_batch_{position}_failures_present")
        if batch.get("register_ok") is not True:
            reasons.append(f"opening_discovery_batch_{position}_register_failed")
        if batch.get("unregister_ok") is not True:
            reasons.append(f"opening_discovery_batch_{position}_unregister_failed")
    if tuple(flattened) != requested:
        reasons.append("opening_discovery_batch_order_mismatch")

    board_batch_raw = inputs.get("board_batch")
    if not isinstance(board_batch_raw, Mapping):
        reasons.append("opening_discovery_board_batch_invalid")
        return tuple(dict.fromkeys(reasons))
    board_batch = dict(board_batch_raw)
    try:
        trade_date = _date_text(inputs.get("trade_date"))
        top_started = _parse_datetime(board_batch.get("started_at"))
        top_completed = _parse_datetime(board_batch.get("completed_at"))
        discovery_started = _parse_datetime(evidence.get("started_at"))
        discovery_completed = _parse_datetime(evidence.get("completed_at"))
    except (TypeError, ValueError):
        reasons.append("opening_discovery_timestamps_invalid")
        return tuple(dict.fromkeys(reasons))

    if not _is_jst_aware(discovery_started) or not _is_jst_aware(discovery_completed):
        reasons.append("opening_discovery_timezone_not_jst")
        return tuple(dict.fromkeys(reasons))
    if discovery_started != top_started or discovery_completed != top_completed:
        reasons.append("opening_discovery_snapshot_span_mismatch")
    if (discovery_completed - discovery_started).total_seconds() > DAYTRADE_DISCOVERY_MAX_SPAN_SECONDS:
        reasons.append("opening_discovery_span_exceeded")

    timeline = [("protected", protected_board)]
    timeline.extend(
        (f"batch_{position}", batch)
        for position, batch in enumerate(normalized_batches)
    )
    previous_completed = discovery_started
    for label, item in timeline:
        try:
            started_at = _parse_datetime(item.get("started_at"))
            completed_at = _parse_datetime(item.get("completed_at"))
        except (TypeError, ValueError):
            reasons.append(f"opening_discovery_{label}_timestamps_invalid")
            continue
        if not _is_jst_aware(started_at) or not _is_jst_aware(completed_at):
            reasons.append(f"opening_discovery_{label}_timezone_not_jst")
            continue
        if started_at > completed_at:
            reasons.append(f"opening_discovery_{label}_time_reversed")
        if _date_text(started_at) != trade_date or _date_text(completed_at) != trade_date:
            reasons.append(f"opening_discovery_{label}_cross_day")
        if started_at < previous_completed:
            reasons.append(f"opening_discovery_{label}_time_overlap")
        if started_at < discovery_started or completed_at > discovery_completed:
            reasons.append(f"opening_discovery_{label}_outside_span")
        previous_completed = max(previous_completed, completed_at)
    return tuple(dict.fromkeys(reasons))

def _validate_snapshot_inputs(inputs: Mapping[str, Any]) -> tuple[str, ...]:
    reasons: list[str] = []
    try:
        trade_date = _date_text(inputs.get("trade_date"))
        feature_asof = _date_text(inputs.get("feature_asof"))
        open_asof = _date_text(inputs.get("open_asof"))
    except (TypeError, ValueError):
        return ("invalid_snapshot_dates",)
    if str(inputs.get("strategy_path") or "") != DAYTRADE_PRODUCTION_STRATEGY_PATH:
        reasons.append("strategy_path_mismatch")

    if feature_asof >= trade_date:
        reasons.append("feature_asof_not_before_trade_date")
    if open_asof != trade_date:
        reasons.append("open_asof_not_trade_date")

    server_clock_raw = inputs.get("server_clock")
    if isinstance(server_clock_raw, Mapping):
        server_clock = dict(server_clock_raw)
    else:
        server_clock = {}
        reasons.append("server_clock_evidence_invalid")
    if server_clock.get("schema_version") != 1:
        reasons.append("server_clock_schema_invalid")
    if server_clock.get("verified") is not True:
        reasons.append("server_clock_unverified")
    expected_clock_source = (
        "simulation_clock"
        if bool(inputs.get("is_simulation"))
        else "wallet_cash_date_header"
    )
    expected_clock_reason = (
        "simulation"
        if bool(inputs.get("is_simulation"))
        else "verified"
    )
    if str(server_clock.get("source") or "") != expected_clock_source:
        reasons.append("server_clock_source_invalid")
    if str(server_clock.get("reason") or "") != expected_clock_reason:
        reasons.append("server_clock_reason_invalid")
    configured_clock_drift = _float_or_none(
        server_clock.get("max_abs_drift_seconds")
    )
    if configured_clock_drift != DAYTRADE_SERVER_CLOCK_MAX_ABS_DRIFT_SECONDS:
        reasons.append("server_clock_max_drift_mismatch")
    reported_clock_drift = _float_or_none(server_clock.get("drift_seconds"))
    try:
        server_time = _parse_datetime(server_clock.get("server_time"))
        clock_received_at = _parse_datetime(server_clock.get("received_at"))
        fallback_time = _parse_datetime(server_clock.get("fallback_time"))
        captured_clock_at = _parse_datetime(inputs.get("captured_at"))
    except (TypeError, ValueError):
        reasons.append("server_clock_timestamps_invalid")
    else:
        clock_timestamps = (
            server_time,
            clock_received_at,
            fallback_time,
            captured_clock_at,
        )
        if not all(_is_jst_aware(value) for value in clock_timestamps):
            reasons.append("server_clock_timezone_not_jst")
        else:
            computed_clock_drift = (
                server_time - clock_received_at
            ).total_seconds()
            if (
                reported_clock_drift is None
                or abs(reported_clock_drift - computed_clock_drift) > 0.02
            ):
                reasons.append("server_clock_drift_mismatch")
            elif abs(reported_clock_drift) > DAYTRADE_SERVER_CLOCK_MAX_ABS_DRIFT_SECONDS:
                reasons.append("server_clock_drift_exceeded")
            if _date_text(server_time) != trade_date:
                reasons.append("server_clock_cross_day")
            if clock_received_at > captured_clock_at:
                reasons.append("server_clock_received_after_snapshot")

    board_batch_raw = inputs.get("board_batch")
    if isinstance(board_batch_raw, Mapping):
        board_batch = dict(board_batch_raw)
    else:
        board_batch = {}
        reasons.append("board_batch_invalid")
    try:
        batch_started_at = _parse_datetime(board_batch.get("started_at"))
        batch_completed_at = _parse_datetime(board_batch.get("completed_at"))
        captured_at = _parse_datetime(inputs.get("captured_at"))
    except (TypeError, ValueError):
        reasons.append("board_batch_timestamps_invalid")
    else:
        timestamps = (batch_started_at, batch_completed_at, captured_at)
        if not all(_is_jst_aware(value) for value in timestamps):
            reasons.append("board_batch_timezone_not_jst")
        else:
            if batch_started_at > batch_completed_at:
                reasons.append("board_batch_time_reversed")
            if (
                _date_text(batch_started_at) != trade_date
                or _date_text(batch_completed_at) != trade_date
            ):
                reasons.append("board_batch_cross_day")
            batch_span_seconds = (
                batch_completed_at - batch_started_at
            ).total_seconds()
            if batch_span_seconds > DAYTRADE_MAX_BOARD_BATCH_SPAN_SECONDS:
                reasons.append("board_batch_span_exceeded")
            if captured_at < batch_completed_at:
                reasons.append("snapshot_captured_before_batch_completed")
    configured_span = _float_or_none(board_batch.get("max_span_seconds"))
    if (
        configured_span is None
        or configured_span != DAYTRADE_MAX_BOARD_BATCH_SPAN_SECONDS
    ):
        reasons.append("board_batch_max_span_mismatch")
    requested_codes = _code_tuple(inputs.get("requested_codes"))
    observation_policy = str(inputs.get("observation_policy") or "").strip()
    opening_discovery = inputs.get("opening_discovery")
    if observation_policy == DAYTRADE_OBSERVATION_POLICY_FIXED_49:
        if opening_discovery:
            reasons.append("opening_discovery_unexpected_for_fixed_policy")
        non_market_codes = [code for code in requested_codes if code != "1321"]
        if len(non_market_codes) > DAYTRADE_DISCOVERY_BATCH_SIZE:
            reasons.append("fixed_observation_policy_capacity_exceeded")
    elif observation_policy == DAYTRADE_OBSERVATION_POLICY_ROTATING_196:
        if not isinstance(opening_discovery, Mapping):
            reasons.append("opening_discovery_evidence_missing")
        else:
            reasons.extend(
                _validate_rotating_discovery_evidence(inputs, opening_discovery)
            )
    else:
        reasons.append("observation_policy_unsupported")
    raw_symbols = inputs.get("symbols")
    if isinstance(raw_symbols, (list, tuple)):
        symbol_values = list(raw_symbols)
    else:
        symbol_values = []
        reasons.append("symbol_inputs_invalid")
    symbols: list[dict[str, Any]] = []
    for position, raw_symbol in enumerate(symbol_values):
        if isinstance(raw_symbol, Mapping):
            symbols.append(dict(raw_symbol))
        else:
            symbols.append({})
            reasons.append(f"symbol_input_{position}_invalid")
    if not symbols:
        reasons.append("symbol_inputs_missing")
    observed_code_list = tuple(_normalize_code(item.get("code")) for item in symbols)
    observed_codes = set(observed_code_list)
    if len(set(requested_codes)) != len(requested_codes):
        reasons.append("requested_symbol_codes_duplicate")
    if len(observed_codes) != len(observed_code_list):
        reasons.append("symbol_inputs_duplicate")
    missing = sorted(set(requested_codes) - observed_codes)
    if missing:
        reasons.append("requested_symbol_inputs_missing:" + ",".join(missing))
    unrequested = sorted(observed_codes - set(requested_codes))
    if unrequested:
        reasons.append("unrequested_symbol_inputs_present:" + ",".join(unrequested))

    market_raw = inputs.get("market")
    if isinstance(market_raw, Mapping):
        market = dict(market_raw)
    else:
        market = {}
        reasons.append("market_input_invalid")
    market_code = _normalize_code(market.get("code", "1321"))
    if market_code not in observed_codes:
        reasons.append("market_symbol_input_missing")

    for field in ("breadth", "open_today", "close_prev", "sma_trend_prev"):
        if _float_or_none(market.get(field)) is None:
            reasons.append(f"market_{field}_invalid")

    selector_raw = inputs.get("selector")
    if isinstance(selector_raw, Mapping):
        selector = dict(selector_raw)
    else:
        selector = {}
        reasons.append("selector_input_invalid")
    for field in (
        "current_equity",
        "week_start_equity",
        "account_cash",
        "base_leverage",
    ):
        if _float_or_none(selector.get(field)) is None:
            reasons.append(f"selector_{field}_invalid")

    strategy_raw = inputs.get("strategy")
    if isinstance(strategy_raw, Mapping):
        strategy = dict(strategy_raw)
    else:
        strategy = {}
        reasons.append("strategy_input_invalid")
    for field in ("liquidity_limit", "bull_gap_limit", "rsi_threshold"):
        if _float_or_none(strategy.get(field)) is None:
            reasons.append(f"strategy_{field}_invalid")
    for item in symbols:
        code = _normalize_code(item.get("code"))
        if not code:
            reasons.append("empty_symbol_code")
            continue
        opening_timestamp = item.get("opening_price_timestamp")
        try:
            if _date_text(opening_timestamp) != trade_date:
                reasons.append(f"{code}:opening_timestamp_cross_day")
        except (TypeError, ValueError):
            reasons.append(f"{code}:opening_timestamp_missing")
        previous_close_timestamp = item.get("previous_close_timestamp")
        try:
            if _date_text(previous_close_timestamp) != feature_asof:
                reasons.append(f"{code}:previous_close_timestamp_not_feature_asof")
        except (TypeError, ValueError):
            reasons.append(f"{code}:previous_close_timestamp_missing")

        required = (
            "open_today",
            "close_prev",
            "close_prev2",
            "open_prev",
            "low_prev",
            "atr_prev",
            "turnover_prev",
            "rsi2_prev",
            "rs_alpha_prev",
            "sma_med_prev",
            "sma_trend_prev",
        )
        if any(_float_or_none(item.get(field)) is None for field in required):
            reasons.append(f"{code}:required_feature_missing")

    raw_failures = inputs.get("board_failures")
    if not isinstance(raw_failures, (list, tuple)):
        raw_failures = ()
        reasons.append("board_failures_invalid")
    for position, raw_failure in enumerate(raw_failures):
        if not isinstance(raw_failure, Mapping):
            reasons.append(f"board_failure_{position}_invalid")
            continue
        failure = dict(raw_failure)
        code = _normalize_code(failure.get("code"))
        reason = str(failure.get("reason") or "unknown")
        reasons.append(f"{code}:board_{reason}")
    operational_reasons = inputs.get("operational_reasons")
    if isinstance(operational_reasons, (list, tuple)):
        for operational_reason in operational_reasons:
            reasons.append(str(operational_reason))
    else:
        reasons.append("operational_reasons_invalid")
    return tuple(dict.fromkeys(reasons))


def _evaluate_inputs(
    inputs: Mapping[str, Any],
    *,
    snapshot_id: str,
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], tuple[str, ...]]:
    reasons = _validate_snapshot_inputs(inputs)
    if reasons:
        return {name: [] for name in _GROUP_NAMES}, [], reasons

    symbols = list(inputs["symbols"])
    tickers = [
        f"{_normalize_code(item['code'])}.T"
        for item in symbols
    ]

    def array(field: str):
        return np.asarray([_decode_float(item.get(field)) for item in symbols], dtype=float)

    market_input = dict(inputs["market"])
    market_context = build_daytrade_open_market_context(
        trade_date=inputs["trade_date"],
        feature_asof=inputs["feature_asof"],
        open_asof=inputs["open_asof"],
        breadth_val=market_input["breadth"],
        market_open=market_input["open_today"],
        prev_market_close=market_input["close_prev"],
        prev_market_sma_trend=market_input["sma_trend_prev"],
    )
    strategy = dict(inputs["strategy"])
    groups = generate_daytrade_candidate_groups(
        DaytradeOpenArrayView(
            tickers=tickers,
            universe_indices=np.arange(len(tickers), dtype=int),
            open_today=array("open_today"),
            close_prev=array("close_prev"),
            close_prev2=array("close_prev2"),
            open_prev=array("open_prev"),
            low_prev=array("low_prev"),
            atr_prev=array("atr_prev"),
            turnover_prev=array("turnover_prev"),
            rsi2_prev=array("rsi2_prev"),
            rs_alpha_prev=array("rs_alpha_prev"),
            sma_med_prev=array("sma_med_prev"),
            sma_trend_prev=array("sma_trend_prev"),
        ),
        market_context,
        liquidity_limit=float(strategy["liquidity_limit"]),
        bull_gap_limit=float(strategy["bull_gap_limit"]),
        rsi_threshold=float(strategy["rsi_threshold"]),
    )
    raw_groups = {
        name: [dict(item) for item in getattr(groups, name)]
        for name in _GROUP_NAMES
    }
    selector = dict(inputs["selector"])
    selected = select_daytrade_candidates(
        raw_groups["primary"],
        raw_groups["strong_oversold"],
        raw_groups["fallback"],
        raw_groups["catchup"],
        raw_groups["inverse"],
        raw_groups["bull_etf"],
        breadth_val=market_context.breadth_val,
        market_ratio=market_context.market_ratio,
        trade_date=inputs["trade_date"],
        current_equity=float(selector["current_equity"]),
        week_start_equity=float(selector["week_start_equity"]),
        current_time=datetime.fromisoformat(
            str(inputs["captured_at"]).replace("Z", "+00:00")
        ),
        account_cash=float(selector["account_cash"]),
        base_leverage=float(selector["base_leverage"]),
    )
    selected_output = []
    for rank, item in enumerate(selected or (), start=1):
        output = dict(item)
        output["decision_snapshot_id"] = snapshot_id
        output["candidate_rank"] = rank
        selected_output.append(output)
    return (
        {
            name: [_json_safe(item) for item in raw_groups[name]]
            for name in _GROUP_NAMES
        },
        [_json_safe(item) for item in selected_output],
        (),
    )


def build_daytrade_production_snapshot(
    *,
    trade_date: Any,
    feature_asof: Any,
    open_asof: Any,
    captured_at: Any,
    trade_mode: str,
    is_simulation: bool,
    requested_codes: Iterable[Any],
    symbol_inputs: Iterable[Mapping[str, Any]],
    market_input: Mapping[str, Any],
    selector_context: Mapping[str, Any],
    board_batch_started_at: Any,
    board_batch_completed_at: Any,
    strategy_context: Mapping[str, Any],
    server_clock_evidence: Mapping[str, Any],
    observation_policy: str = DAYTRADE_OBSERVATION_POLICY_FIXED_49,
    opening_discovery_evidence: Mapping[str, Any] | None = None,
    board_failures: Iterable[Mapping[str, Any]] = (),
    operational_reasons: Iterable[str] = (),
    execution_quotes: Iterable[Mapping[str, Any]] = (),
    code_commit_sha: str | None = None,
    runtime_config_hash: str | None = None,
) -> dict[str, Any]:
    inputs = {
        "strategy_path": DAYTRADE_PRODUCTION_STRATEGY_PATH,
        "trade_date": _date_text(trade_date),
        "feature_asof": _date_text(feature_asof),
        "open_asof": _date_text(open_asof),
        "captured_at": _datetime_text(captured_at),
        "trade_mode": str(trade_mode or "").strip().upper(),
        "is_simulation": bool(is_simulation),
        "requested_codes": [_normalize_code(code) for code in requested_codes],
        "observation_policy": str(observation_policy or "").strip(),
        "opening_discovery": (
            None
            if opening_discovery_evidence is None
            else _json_safe(dict(opening_discovery_evidence))
        ),
        "symbols": [_json_safe(dict(item)) for item in symbol_inputs],
        "market": _json_safe(dict(market_input)),
        "selector": _json_safe(dict(selector_context)),
        "strategy": _json_safe(dict(strategy_context)),
        "server_clock": _json_safe(dict(server_clock_evidence)),
        "board_batch": {
            "started_at": _datetime_text(board_batch_started_at),
            "completed_at": _datetime_text(board_batch_completed_at),
            "max_span_seconds": DAYTRADE_MAX_BOARD_BATCH_SPAN_SECONDS,
        },
        "board_failures": [_json_safe(dict(item)) for item in board_failures],
        "operational_reasons": [str(reason) for reason in operational_reasons],
        # Current price, bid/ask, high, low and volume are execution evidence.
        # They are intentionally outside the signal arrays.
        "execution_quotes": [_json_safe(dict(item)) for item in execution_quotes],
        "code_commit_sha": str(code_commit_sha or ""),
        "runtime_config_hash": str(runtime_config_hash or ""),
    }
    decision_identity = {
        key: value
        for key, value in inputs.items()
        if key not in {"captured_at", "execution_quotes"}
    }
    snapshot_id = canonical_daytrade_digest(decision_identity)[:32]
    candidate_groups, selected, reasons = _evaluate_inputs(
        inputs,
        snapshot_id=snapshot_id,
    )
    candidate_digest = canonical_daytrade_digest(candidate_groups)
    selected_digest = canonical_daytrade_digest(selected)
    live_mode = inputs["trade_mode"] == "KABUCOM_LIVE" and not inputs["is_simulation"]
    return {
        "schema_version": DAYTRADE_PRODUCTION_SNAPSHOT_SCHEMA_VERSION,
        "snapshot_id": snapshot_id,
        "captured_at": inputs["captured_at"],
        "trade_date": inputs["trade_date"],
        "trade_mode": inputs["trade_mode"],
        "is_simulation": inputs["is_simulation"],
        "strategy_path": DAYTRADE_PRODUCTION_STRATEGY_PATH,
        "decision_allowed": not reasons,
        "eligible_for_decision_clean_holdout": bool(live_mode and not reasons),
        "rejection_reasons": list(reasons),
        "inputs": inputs,
        "recorded": {
            "candidate_groups": candidate_groups,
            "selected_candidates": selected,
            "candidate_digest": candidate_digest,
            "selected_digest": selected_digest,
        },
    }


def replay_daytrade_production_snapshot(
    snapshot: Mapping[str, Any],
    *,
    expected_code_commit_sha: str | None = None,
    expected_runtime_config_hash: str | None = None,
) -> DaytradeProductionReplayResult:
    snapshot_id = str(snapshot.get("snapshot_id") or "")
    if int(snapshot.get("schema_version") or 0) != DAYTRADE_PRODUCTION_SNAPSHOT_SCHEMA_VERSION:
        return DaytradeProductionReplayResult(
            snapshot_id=snapshot_id,
            replayable=False,
            parity=False,
            rejection_reasons=("unsupported_schema_version",),
            selected_codes=(),
            candidate_digest="",
            selected_digest="",
        )
    inputs = dict(snapshot.get("inputs") or {})
    environment_reasons = []
    if (
        expected_code_commit_sha is not None
        and str(inputs.get("code_commit_sha") or "") != str(expected_code_commit_sha)
    ):
        environment_reasons.append("code_commit_sha_mismatch")
    if (
        expected_runtime_config_hash is not None
        and str(inputs.get("runtime_config_hash") or "")
        != str(expected_runtime_config_hash)
    ):
        environment_reasons.append("runtime_config_hash_mismatch")
    if environment_reasons:
        return DaytradeProductionReplayResult(
            snapshot_id=snapshot_id,
            replayable=False,
            parity=False,
            rejection_reasons=tuple(environment_reasons),
            selected_codes=(),
            candidate_digest="",
            selected_digest="",
        )
    expected_identity = {
        key: value
        for key, value in inputs.items()
        if key not in {"captured_at", "execution_quotes"}
    }
    expected_snapshot_id = canonical_daytrade_digest(expected_identity)[:32]
    if snapshot_id != expected_snapshot_id:
        return DaytradeProductionReplayResult(
            snapshot_id=snapshot_id,
            replayable=False,
            parity=False,
            rejection_reasons=("snapshot_identity_mismatch",),
            selected_codes=(),
            candidate_digest="",
            selected_digest="",
        )

    candidate_groups, selected, reasons = _evaluate_inputs(
        inputs,
        snapshot_id=snapshot_id,
    )
    candidate_digest = canonical_daytrade_digest(candidate_groups)
    selected_digest = canonical_daytrade_digest(selected)
    recorded = dict(snapshot.get("recorded") or {})
    recorded_reasons = tuple(str(reason) for reason in snapshot.get("rejection_reasons") or ())
    parity = (
        candidate_digest == str(recorded.get("candidate_digest") or "")
        and selected_digest == str(recorded.get("selected_digest") or "")
        and tuple(reasons) == recorded_reasons
    )
    selected_codes = tuple(
        _normalize_code(item.get("code"))
        for item in selected
    )
    return DaytradeProductionReplayResult(
        snapshot_id=snapshot_id,
        replayable=not reasons,
        parity=parity,
        rejection_reasons=tuple(reasons),
        selected_codes=selected_codes,
        candidate_digest=candidate_digest,
        selected_digest=selected_digest,
    )


def append_daytrade_production_snapshot(
    path: str | Path,
    snapshot: Mapping[str, Any],
) -> None:
    append_jsonl(str(path), _json_safe(dict(snapshot)))


def load_daytrade_production_snapshots(
    path: str | Path,
) -> list[dict[str, Any]]:
    resolved = Path(ensure_absolute_path(path))
    if not resolved.exists():
        return []
    snapshots: list[dict[str, Any]] = []
    with resolved.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                value = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid production snapshot JSONL at line {line_number}"
                ) from exc
            if not isinstance(value, dict):
                raise ValueError(
                    f"production snapshot line {line_number} is not an object"
                )
            snapshots.append(value)
    return snapshots


def find_first_daytrade_production_snapshot(
    path: str | Path,
    *,
    trade_date: Any,
    trade_mode: str,
) -> dict[str, Any] | None:
    wanted_date = _date_text(trade_date)
    wanted_mode = str(trade_mode or "").strip().upper()
    for snapshot in load_daytrade_production_snapshots(path):
        if (
            str(snapshot.get("trade_date") or "") == wanted_date
            and str(snapshot.get("trade_mode") or "").upper() == wanted_mode
        ):
            return snapshot
    return None
