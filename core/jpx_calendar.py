from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Any, Mapping
from urllib.parse import urlparse

import jpholiday

from core.config import JST


JPX_TRADING_CALENDAR_PATH = Path(__file__).resolve().parents[1] / "contracts" / "jpx_trading_calendar.json"
JPX_CALENDAR_MAX_AGE_DAYS = 370
JPX_CALENDAR_SOURCE_URL = "https://www.jpx.co.jp/corporate/about-jpx/calendar/index.html"
_JPX_SOURCE_HASH_PATTERN = re.compile(r"sha256:[0-9a-fA-F]{64}")
_JPX_SOURCE_PATH = "/corporate/about-jpx/calendar/index.html"


@dataclass(frozen=True)
class JPXTradingDayStatus:
    trading_day: bool
    source_ready: bool
    source_reason: str
    source_path: str
    source_present: bool
    source_valid: bool
    trading_date: str
    half_day: bool
    used_fallback: bool


@dataclass(frozen=True)
class _JPXTradingCalendarLoadResult:
    calendar: dict[str, Any] | None
    source_present: bool
    source_valid: bool
    source_reason: str
    source_url_explicit: bool
    generated_at: datetime | None
    coverage_start: date | None
    coverage_end: date | None


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


def _normalize_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _is_authoritative_jpx_source_url(value: Any) -> bool:
    source_url = _normalize_text(value)
    if source_url is None:
        return False
    try:
        parsed = urlparse(source_url)
        port = parsed.port
    except ValueError:
        return False
    return bool(
        parsed.scheme.lower() == "https"
        and (parsed.hostname or "").lower() in {"jpx.co.jp", "www.jpx.co.jp"}
        and port in {None, 443}
        and parsed.username is None
        and parsed.password is None
        and parsed.path.rstrip("/") == _JPX_SOURCE_PATH.rstrip("/")
        and not parsed.query
        and not parsed.fragment
    )


def _parse_calendar_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _normalize_text(value)
    if text is None:
        return None
    text = text.replace("Z", "+00:00")
    try:
        parsed_datetime = datetime.fromisoformat(text)
    except ValueError:
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
    return parsed_datetime.date()


def _parse_calendar_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min, tzinfo=JST)
    else:
        text = _normalize_text(value)
        if text is None:
            return None
        text = text.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            try:
                parsed_date = date.fromisoformat(text)
            except ValueError:
                return None
            parsed = datetime.combine(parsed_date, time.min, tzinfo=JST)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=JST)
    else:
        parsed = parsed.astimezone(JST)
    return parsed


def _normalize_date_sequence(values: Any) -> tuple[str, ...] | None:
    if values is None:
        return None
    if isinstance(values, (str, bytes)):
        values = [values]
    if not isinstance(values, (list, tuple, set)):
        return None
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        parsed = _parse_calendar_date(value)
        if parsed is None:
            return None
        text = parsed.isoformat()
        if text in seen:
            return None
        seen.add(text)
        normalized.append(text)
    return tuple(sorted(normalized))


@lru_cache(maxsize=4)
def _load_jpx_trading_calendar_payload(path: str | Path = JPX_TRADING_CALENDAR_PATH) -> _JPXTradingCalendarLoadResult:
    calendar_path = Path(path).expanduser().resolve(strict=False)
    if not calendar_path.exists():
        return _JPXTradingCalendarLoadResult(
            calendar=None,
            source_present=False,
            source_valid=False,
            source_reason="jpx_calendar_missing",
            source_url_explicit=False,
            generated_at=None,
            coverage_start=None,
            coverage_end=None,
        )
    try:
        raw = json.loads(calendar_path.read_text(encoding="utf-8"))
    except Exception:
        return _JPXTradingCalendarLoadResult(
            calendar=None,
            source_present=True,
            source_valid=False,
            source_reason="jpx_calendar_invalid",
            source_url_explicit=False,
            generated_at=None,
            coverage_start=None,
            coverage_end=None,
        )
    if not isinstance(raw, Mapping):
        return _JPXTradingCalendarLoadResult(
            calendar=None,
            source_present=True,
            source_valid=False,
            source_reason="jpx_calendar_invalid",
            source_url_explicit=False,
            generated_at=None,
            coverage_start=None,
            coverage_end=None,
        )

    schema_version_raw = raw.get("schema_version")
    try:
        schema_version = int(schema_version_raw)
    except (TypeError, ValueError):
        return _JPXTradingCalendarLoadResult(
            calendar=None,
            source_present=True,
            source_valid=False,
            source_reason="jpx_calendar_invalid",
            source_url_explicit=False,
            generated_at=None,
            coverage_start=None,
            coverage_end=None,
        )
    if schema_version != 1:
        return _JPXTradingCalendarLoadResult(
            calendar=None,
            source_present=True,
            source_valid=False,
            source_reason="jpx_calendar_invalid",
            source_url_explicit=False,
            generated_at=None,
            coverage_start=None,
            coverage_end=None,
        )

    explicit_source_url = _normalize_text(raw.get("source_url"))
    legacy_source = _normalize_text(raw.get("source"))
    source_url = explicit_source_url or legacy_source
    source_hash = _normalize_text(raw.get("source_hash"))
    generated_at_text = _normalize_text(raw.get("generated_at"))
    coverage_start_text = _normalize_text(raw.get("coverage_start"))
    coverage_end_text = _normalize_text(raw.get("coverage_end"))

    if source_url is None or source_hash is None or generated_at_text is None or coverage_start_text is None or coverage_end_text is None:
        return _JPXTradingCalendarLoadResult(
            calendar=None,
            source_present=True,
            source_valid=False,
            source_reason="jpx_calendar_invalid",
            source_url_explicit=bool(explicit_source_url),
            generated_at=None,
            coverage_start=None,
            coverage_end=None,
        )

    generated_at = _parse_calendar_datetime(generated_at_text)
    coverage_start = _parse_calendar_date(coverage_start_text)
    coverage_end = _parse_calendar_date(coverage_end_text)
    if generated_at is None or coverage_start is None or coverage_end is None or coverage_start > coverage_end:
        return _JPXTradingCalendarLoadResult(
            calendar=None,
            source_present=True,
            source_valid=False,
            source_reason="jpx_calendar_invalid",
            source_url_explicit=bool(explicit_source_url),
            generated_at=generated_at,
            coverage_start=coverage_start,
            coverage_end=coverage_end,
        )

    closed_dates = _normalize_date_sequence(raw.get("closed_dates"))
    trading_dates = _normalize_date_sequence(raw.get("trading_dates"))
    half_day_dates = _normalize_date_sequence(raw.get("half_day_dates"))
    if closed_dates is None or trading_dates is None or half_day_dates is None:
        return _JPXTradingCalendarLoadResult(
            calendar=None,
            source_present=True,
            source_valid=False,
            source_reason="jpx_calendar_invalid",
            source_url_explicit=bool(explicit_source_url),
            generated_at=generated_at,
            coverage_start=coverage_start,
            coverage_end=coverage_end,
        )

    closed_set = set(closed_dates)
    trading_set = set(trading_dates)
    half_day_set = set(half_day_dates)
    if (closed_set & trading_set) or (closed_set & half_day_set) or (trading_set & half_day_set):
        return _JPXTradingCalendarLoadResult(
            calendar=None,
            source_present=True,
            source_valid=False,
            source_reason="jpx_calendar_invalid",
            source_url_explicit=bool(explicit_source_url),
            generated_at=generated_at,
            coverage_start=coverage_start,
            coverage_end=coverage_end,
        )

    return _JPXTradingCalendarLoadResult(
        calendar={
            "schema_version": schema_version,
            "source_url": source_url,
            "source": legacy_source or source_url,
            "source_url_explicit": bool(explicit_source_url),
            "source_hash": source_hash,
            "generated_at": generated_at_text,
            "coverage_start": coverage_start.isoformat(),
            "coverage_end": coverage_end.isoformat(),
            "closed_dates": closed_dates,
            "trading_dates": trading_dates,
            "half_day_dates": half_day_dates,
        },
        source_present=True,
        source_valid=True,
        source_reason="jpx_calendar_valid",
        source_url_explicit=bool(explicit_source_url),
        generated_at=generated_at,
        coverage_start=coverage_start,
        coverage_end=coverage_end,
    )


def load_jpx_trading_calendar(path: str | Path = JPX_TRADING_CALENDAR_PATH) -> dict[str, Any] | None:
    payload = _load_jpx_trading_calendar_payload(path)
    if payload.calendar is None:
        return None
    return dict(payload.calendar)


def get_jpx_trading_day_status(
    trading_date: date | datetime | None = None,
    *,
    calendar_path: str | Path = JPX_TRADING_CALENDAR_PATH,
    require_source: bool = False,
) -> JPXTradingDayStatus:
    resolved_date = _coerce_date(trading_date)
    calendar_path = Path(calendar_path).expanduser().resolve(strict=False)
    payload = _load_jpx_trading_calendar_payload(calendar_path)
    trading_date_text = resolved_date.isoformat()

    if payload.calendar is None:
        source_reason = payload.source_reason
        if require_source:
            return JPXTradingDayStatus(
                trading_day=False,
                source_ready=False,
                source_reason=source_reason,
                source_path=str(calendar_path),
                source_present=payload.source_present,
                source_valid=False,
                trading_date=trading_date_text,
                half_day=False,
                used_fallback=False,
            )
        return JPXTradingDayStatus(
            trading_day=_fallback_business_day(resolved_date),
            source_ready=False,
            source_reason="fallback_jpholiday",
            source_path=str(calendar_path),
            source_present=payload.source_present,
            source_valid=False,
            trading_date=trading_date_text,
            half_day=False,
            used_fallback=True,
        )

    if require_source and (
        not payload.source_url_explicit
        or not _is_authoritative_jpx_source_url(payload.calendar.get("source_url"))
        or _JPX_SOURCE_HASH_PATTERN.fullmatch(str(payload.calendar.get("source_hash") or "")) is None
    ):
        return JPXTradingDayStatus(
            trading_day=False,
            source_ready=False,
            source_reason="jpx_calendar_invalid",
            source_path=str(calendar_path),
            source_present=True,
            source_valid=False,
            trading_date=trading_date_text,
            half_day=False,
            used_fallback=False,
        )

    now = datetime.now(JST)
    if payload.generated_at is not None:
        if payload.generated_at > now:
            if require_source:
                return JPXTradingDayStatus(
                    trading_day=False,
                    source_ready=False,
                    source_reason="jpx_calendar_invalid",
                    source_path=str(calendar_path),
                    source_present=True,
                    source_valid=False,
                    trading_date=trading_date_text,
                    half_day=False,
                    used_fallback=False,
                )
            return JPXTradingDayStatus(
                trading_day=_fallback_business_day(resolved_date),
                source_ready=False,
                source_reason="fallback_jpholiday",
                source_path=str(calendar_path),
                source_present=True,
                source_valid=False,
                trading_date=trading_date_text,
                half_day=False,
                used_fallback=True,
            )
        if now - payload.generated_at > timedelta(days=JPX_CALENDAR_MAX_AGE_DAYS):
            if require_source:
                return JPXTradingDayStatus(
                    trading_day=False,
                    source_ready=False,
                    source_reason="jpx_calendar_stale",
                    source_path=str(calendar_path),
                    source_present=True,
                    source_valid=False,
                    trading_date=trading_date_text,
                    half_day=False,
                    used_fallback=False,
                )
            return JPXTradingDayStatus(
                trading_day=_fallback_business_day(resolved_date),
                source_ready=False,
                source_reason="fallback_jpholiday",
                source_path=str(calendar_path),
                source_present=True,
                source_valid=False,
                trading_date=trading_date_text,
                half_day=False,
                used_fallback=True,
            )

    closed_dates = set(payload.calendar.get("closed_dates") or ())
    trading_dates = set(payload.calendar.get("trading_dates") or ())
    half_day_dates = set(payload.calendar.get("half_day_dates") or ())

    if require_source and payload.coverage_start is not None and payload.coverage_end is not None:
        if not (payload.coverage_start <= resolved_date <= payload.coverage_end):
            return JPXTradingDayStatus(
                trading_day=False,
                source_ready=False,
                source_reason="jpx_calendar_coverage_gap",
                source_path=str(calendar_path),
                source_present=True,
                source_valid=True,
                trading_date=trading_date_text,
                half_day=False,
                used_fallback=False,
            )

    if trading_date_text in closed_dates:
        return JPXTradingDayStatus(
            trading_day=False,
            source_ready=True,
            source_reason="calendar_closed_date",
            source_path=str(calendar_path),
            source_present=True,
            source_valid=True,
            trading_date=trading_date_text,
            half_day=False,
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
            half_day=False,
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
            half_day=True,
            used_fallback=False,
        )

    if not require_source and payload.source_valid:
        return JPXTradingDayStatus(
            trading_day=_fallback_business_day(resolved_date),
            source_ready=True,
            source_reason="calendar_fallback",
            source_path=str(calendar_path),
            source_present=True,
            source_valid=True,
            trading_date=trading_date_text,
            half_day=False,
            used_fallback=True,
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
            half_day=False,
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
        half_day=False,
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
