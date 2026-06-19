from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Mapping

import jpholiday

from core.config import JST


JPX_TRADING_CALENDAR_PATH = Path(__file__).resolve().parents[1] / "contracts" / "jpx_trading_calendar.json"


@dataclass(frozen=True)
class JPXTradingDayStatus:
    trading_day: bool
    source_ready: bool
    source_reason: str
    source_path: str
    source_present: bool
    source_valid: bool
    trading_date: str
    used_fallback: bool


def _coerce_date(value: date | datetime | None) -> date:
    if value is None:
        return datetime.now(JST).date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if hasattr(value, "date"):
        try:
            candidate = value.date()
        except Exception as exc:  # pragma: no cover - defensive fallback
            raise TypeError(f"Unsupported date value: {value!r}") from exc
        if isinstance(candidate, date):
            return candidate
    raise TypeError(f"Unsupported date value: {value!r}")


def _fallback_business_day(trading_date: date) -> bool:
    if trading_date.weekday() >= 5:
        return False
    if jpholiday.is_holiday(trading_date):
        return False
    if (trading_date.month == 12 and trading_date.day == 31) or (trading_date.month == 1 and trading_date.day in {1, 2, 3}):
        return False
    return True


def _normalize_date_sequence(values: Any) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes)):
        values = [values]
    if not isinstance(values, list):
        return ()
    normalized: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text:
            normalized.append(text)
    return tuple(sorted(dict.fromkeys(normalized)))


@lru_cache(maxsize=4)
def load_jpx_trading_calendar(path: str | Path = JPX_TRADING_CALENDAR_PATH) -> dict[str, Any] | None:
    calendar_path = Path(path)
    if not calendar_path.exists():
        return None
    try:
        raw = json.loads(calendar_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(raw, Mapping):
        return None
    schema_version = raw.get("schema_version")
    if schema_version is not None:
        try:
            if int(schema_version) != 1:
                return None
        except (TypeError, ValueError):
            return None
    closed_dates = _normalize_date_sequence(raw.get("closed_dates"))
    trading_dates = _normalize_date_sequence(raw.get("trading_dates"))
    half_day_dates = _normalize_date_sequence(raw.get("half_day_dates"))
    if raw.get("closed_dates") is not None and not closed_dates and raw.get("closed_dates") != []:
        return None
    if raw.get("trading_dates") is not None and not trading_dates and raw.get("trading_dates") != []:
        return None
    if raw.get("half_day_dates") is not None and not half_day_dates and raw.get("half_day_dates") != []:
        return None
    return {
        "schema_version": 1 if schema_version is None else int(schema_version),
        "source": str(raw.get("source") or "").strip() or None,
        "generated_at": str(raw.get("generated_at") or "").strip() or None,
        "closed_dates": closed_dates,
        "trading_dates": trading_dates,
        "half_day_dates": half_day_dates,
    }


def get_jpx_trading_day_status(
    trading_date: date | datetime | None = None,
    *,
    calendar_path: str | Path = JPX_TRADING_CALENDAR_PATH,
    require_source: bool = False,
) -> JPXTradingDayStatus:
    resolved_date = _coerce_date(trading_date)
    calendar_path = Path(calendar_path)
    calendar = load_jpx_trading_calendar(calendar_path)
    trading_date_text = resolved_date.isoformat()

    if calendar is None:
        source_present = calendar_path.exists()
        source_reason = "jpx_calendar_invalid" if source_present else "jpx_calendar_missing"
        if require_source:
            return JPXTradingDayStatus(
                trading_day=False,
                source_ready=False,
                source_reason=source_reason,
                source_path=str(calendar_path),
                source_present=source_present,
                source_valid=False,
                trading_date=trading_date_text,
                used_fallback=False,
            )
        return JPXTradingDayStatus(
            trading_day=_fallback_business_day(resolved_date),
            source_ready=False,
            source_reason="fallback_jpholiday",
            source_path=str(calendar_path),
            source_present=source_present,
            source_valid=False,
            trading_date=trading_date_text,
            used_fallback=True,
        )

    closed_dates = set(calendar.get("closed_dates") or ())
    trading_dates = set(calendar.get("trading_dates") or ())
    half_day_dates = set(calendar.get("half_day_dates") or ())

    if trading_date_text in closed_dates:
        return JPXTradingDayStatus(
            trading_day=False,
            source_ready=True,
            source_reason="calendar_closed_date",
            source_path=str(calendar_path),
            source_present=True,
            source_valid=True,
            trading_date=trading_date_text,
            used_fallback=False,
        )
    if trading_date_text in trading_dates:
        return JPXTradingDayStatus(
            trading_day=True,
            source_ready=True,
            source_reason="calendar_trading_date",
            source_path=str(calendar_path),
            source_present=True,
            source_valid=True,
            trading_date=trading_date_text,
            used_fallback=False,
        )
    if trading_date_text in half_day_dates:
        return JPXTradingDayStatus(
            trading_day=True,
            source_ready=True,
            source_reason="calendar_half_day",
            source_path=str(calendar_path),
            source_present=True,
            source_valid=True,
            trading_date=trading_date_text,
            used_fallback=False,
        )

    if require_source:
        # LIVE ではカレンダーの未列挙日を fallback で埋めず、coverage gap として fail closed にする。
        return JPXTradingDayStatus(
            trading_day=False,
            source_ready=False,
            source_reason="jpx_calendar_coverage_gap",
            source_path=str(calendar_path),
            source_present=True,
            source_valid=True,
            trading_date=trading_date_text,
            used_fallback=False,
        )

    return JPXTradingDayStatus(
        trading_day=_fallback_business_day(resolved_date),
        source_ready=True,
        source_reason="calendar_fallback",
        source_path=str(calendar_path),
        source_present=True,
        source_valid=True,
        trading_date=trading_date_text,
        used_fallback=True,
    )


def is_jpx_business_day(
    trading_date: date | datetime | None = None,
    *,
    calendar_path: str | Path = JPX_TRADING_CALENDAR_PATH,
    require_source: bool = False,
) -> bool:
    return get_jpx_trading_day_status(
        trading_date,
        calendar_path=calendar_path,
        require_source=require_source,
    ).trading_day
