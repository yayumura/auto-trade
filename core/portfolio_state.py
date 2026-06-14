from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import shutil
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from core.config import JST
from core.file_io import atomic_write_json, ensure_absolute_path, safe_read_csv, safe_read_json

PORTFOLIO_STATE_SCHEMA_VERSION = 1
PORTFOLIO_STATE_FORMAT = "schema_versioned_json"
PORTFOLIO_STRING_FIELDS = {
    "code",
    "symbol",
    "execution_id",
    "hold_id",
    "ownership",
    "ownership_reason",
    "setup_type",
    "buy_time",
    "sell_time",
}


@dataclass(frozen=True)
class PortfolioState:
    schema_version: int
    positions: list[dict[str, Any]]
    metadata: dict[str, Any]
    source_format: str
    needs_migration: bool


def _normalize_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize_json_value(item) for key, item in sorted(value.items(), key=lambda entry: str(entry[0]))}
    if isinstance(value, list):
        return [_normalize_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_json_value(item) for item in value]
    if isinstance(value, set):
        return [_normalize_json_value(item) for item in sorted(value, key=lambda item: repr(item))]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "item") and callable(getattr(value, "item")):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def _normalize_record(record: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in dict(record or {}).items():
        normalized_key = str(key)
        normalized_value = _normalize_json_value(value)
        if normalized_key in PORTFOLIO_STRING_FIELDS and normalized_value is not None:
            normalized_value = str(normalized_value)
        normalized[normalized_key] = normalized_value
    return normalized


def _normalize_positions(portfolio: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    positions = []
    for record in portfolio or []:
        if isinstance(record, Mapping):
            positions.append(_normalize_record(record))
    return positions


def _backup_legacy_portfolio_file(path: str) -> Path | None:
    absolute_path = Path(ensure_absolute_path(path))
    if not absolute_path.exists() or absolute_path.stat().st_size == 0:
        return None

    archive_dir = absolute_path.parent / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
    suffix = absolute_path.suffix or ".json"
    backup_path = archive_dir / f"{absolute_path.stem}_legacy_{timestamp}{suffix}"
    counter = 1
    while backup_path.exists():
        backup_path = archive_dir / f"{absolute_path.stem}_legacy_{timestamp}_{counter}{suffix}"
        counter += 1
    shutil.copy2(absolute_path, backup_path)
    return backup_path


def build_portfolio_state_payload(
    portfolio: list[dict[str, Any]] | None,
    *,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_positions = _normalize_positions(portfolio)
    normalized_metadata = _normalize_record(metadata or {})
    normalized_metadata.setdefault("position_count", len(normalized_positions))
    normalized_metadata.setdefault("updated_at", datetime.now(JST).isoformat())
    return {
        "schema_version": PORTFOLIO_STATE_SCHEMA_VERSION,
        "format": PORTFOLIO_STATE_FORMAT,
        "positions": normalized_positions,
        "metadata": normalized_metadata,
    }


def load_portfolio_state(path: str) -> PortfolioState | None:
    absolute_path = ensure_absolute_path(path)
    path_obj = Path(absolute_path)
    if not path_obj.exists() or path_obj.stat().st_size == 0:
        return None

    raw_json = safe_read_json(absolute_path, default=None)
    if isinstance(raw_json, dict) and "positions" in raw_json:
        positions = raw_json.get("positions") or []
        metadata = raw_json.get("metadata") or {}
        schema_version = int(raw_json.get("schema_version") or 0)
        needs_migration = schema_version != PORTFOLIO_STATE_SCHEMA_VERSION or raw_json.get("format") != PORTFOLIO_STATE_FORMAT
        return PortfolioState(
            schema_version=schema_version,
            positions=_normalize_positions(positions),
            metadata=_normalize_record(metadata),
            source_format=str(raw_json.get("format") or "json"),
            needs_migration=needs_migration,
        )

    if isinstance(raw_json, list):
        return PortfolioState(
            schema_version=0,
            positions=_normalize_positions(raw_json),
            metadata={},
            source_format="legacy_json_list",
            needs_migration=True,
        )

    df = safe_read_csv(absolute_path)
    if df.empty:
        return None
    positions = df.to_dict(orient="records")
    return PortfolioState(
        schema_version=0,
        positions=_normalize_positions(positions),
        metadata={},
        source_format="legacy_csv",
        needs_migration=True,
    )


def load_portfolio_positions(path: str) -> list[dict[str, Any]]:
    state = load_portfolio_state(path)
    if state is None:
        return []
    return list(state.positions)


def write_portfolio_state(
    path: str,
    portfolio: list[dict[str, Any]] | None,
    *,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    existing_state = load_portfolio_state(path)
    if existing_state is not None and existing_state.needs_migration:
        _backup_legacy_portfolio_file(path)

    payload = build_portfolio_state_payload(portfolio, metadata=metadata)
    atomic_write_json(path, payload)
    return payload
