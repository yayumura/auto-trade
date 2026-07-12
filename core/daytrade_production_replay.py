from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
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
from core.logic import (
    build_daytrade_open_market_context,
    select_daytrade_candidates,
)


DAYTRADE_PRODUCTION_SNAPSHOT_SCHEMA_VERSION = 1
DAYTRADE_PRODUCTION_STRATEGY_PATH = "observed_open_shared_engine_v1"
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


def _validate_snapshot_inputs(inputs: Mapping[str, Any]) -> tuple[str, ...]:
    reasons: list[str] = []
    try:
        trade_date = _date_text(inputs.get("trade_date"))
        feature_asof = _date_text(inputs.get("feature_asof"))
        open_asof = _date_text(inputs.get("open_asof"))
    except (TypeError, ValueError):
        return ("invalid_snapshot_dates",)

    if feature_asof >= trade_date:
        reasons.append("feature_asof_not_before_trade_date")
    if open_asof != trade_date:
        reasons.append("open_asof_not_trade_date")

    symbols = list(inputs.get("symbols") or [])
    if not symbols:
        reasons.append("symbol_inputs_missing")
    requested_codes = tuple(_normalize_code(code) for code in inputs.get("requested_codes") or ())
    observed_codes = {_normalize_code(item.get("code")) for item in symbols}
    missing = sorted(set(requested_codes) - observed_codes)
    if missing:
        reasons.append("requested_symbol_inputs_missing:" + ",".join(missing))

    market = dict(inputs.get("market") or {})
    market_code = _normalize_code(market.get("code", "1321"))
    if market_code not in observed_codes:
        reasons.append("market_symbol_input_missing")

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

    for failure in inputs.get("board_failures") or ():
        code = _normalize_code(failure.get("code"))
        reason = str(failure.get("reason") or "unknown")
        reasons.append(f"{code}:board_{reason}")
    for operational_reason in inputs.get("operational_reasons") or ():
        reasons.append(str(operational_reason))
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
    strategy_context: Mapping[str, Any],
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
        "symbols": [_json_safe(dict(item)) for item in symbol_inputs],
        "market": _json_safe(dict(market_input)),
        "selector": _json_safe(dict(selector_context)),
        "strategy": _json_safe(dict(strategy_context)),
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
