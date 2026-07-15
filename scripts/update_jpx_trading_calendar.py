from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from hashlib import sha256
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.config import JST
from core.file_io import atomic_write_json
from core.jpx_calendar import JPX_CALENDAR_SOURCE_URL, JPX_TRADING_CALENDAR_PATH


_YEAR_TABLE_PATTERN = re.compile(
    r"<h3\b[^>]*>.*?<span>\s*(\d{4})年\s*</span>.*?</h3>.*?<table\b[^>]*>(.*?)</table>",
    flags=re.IGNORECASE | re.DOTALL,
)
_DATE_PATTERN = re.compile(r"(\d{4})/(\d{2})/(\d{2})")
_MIN_SOURCE_CLOSED_DATES_PER_YEAR = 15


class JPXCalendarSourceError(RuntimeError):
    pass


def extract_jpx_closed_dates(
    source_text: str,
    *,
    start_year: int,
    end_year: int,
) -> dict[int, tuple[date, ...]]:
    if start_year > end_year:
        raise ValueError("start_year must be less than or equal to end_year")

    parsed_by_year: dict[int, tuple[date, ...]] = {}
    for match in _YEAR_TABLE_PATTERN.finditer(source_text):
        table_year = int(match.group(1))
        if not start_year <= table_year <= end_year:
            continue
        parsed_dates: set[date] = set()
        for date_match in _DATE_PATTERN.finditer(match.group(2)):
            parsed = date(*(int(date_match.group(index)) for index in range(1, 4)))
            if parsed.year != table_year:
                raise JPXCalendarSourceError(
                    f"JPX source table {table_year} contains cross-year date {parsed.isoformat()}"
                )
            parsed_dates.add(parsed)
        if len(parsed_dates) < _MIN_SOURCE_CLOSED_DATES_PER_YEAR:
            raise JPXCalendarSourceError(
                f"JPX source table {table_year} has only {len(parsed_dates)} closed dates"
            )
        parsed_by_year[table_year] = tuple(sorted(parsed_dates))

    missing_years = [year for year in range(start_year, end_year + 1) if year not in parsed_by_year]
    if missing_years:
        raise JPXCalendarSourceError(
            "JPX source is missing requested calendar years: "
            + ",".join(str(year) for year in missing_years)
        )
    return parsed_by_year


def _iter_dates(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def build_jpx_trading_calendar_payload(
    source_bytes: bytes,
    *,
    generated_at: datetime,
    start_year: int,
    end_year: int,
    source_url: str = JPX_CALENDAR_SOURCE_URL,
) -> dict[str, object]:
    try:
        source_text = source_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise JPXCalendarSourceError("JPX source is not valid UTF-8") from exc

    source_closed_by_year = extract_jpx_closed_dates(
        source_text,
        start_year=start_year,
        end_year=end_year,
    )
    coverage_start = date(start_year, 1, 1)
    coverage_end = date(end_year, 12, 31)
    source_closed = {
        item
        for values in source_closed_by_year.values()
        for item in values
    }
    closed_dates: list[str] = []
    trading_dates: list[str] = []
    for current in _iter_dates(coverage_start, coverage_end):
        if current.weekday() >= 5 or current in source_closed:
            closed_dates.append(current.isoformat())
        else:
            trading_dates.append(current.isoformat())

    generated = generated_at if generated_at.tzinfo is not None else generated_at.replace(tzinfo=JST)
    generated = generated.astimezone(JST)
    return {
        "schema_version": 1,
        "source_url": source_url,
        "source": source_url,
        "source_hash": f"sha256:{sha256(source_bytes).hexdigest()}",
        "generated_at": generated.isoformat(timespec="seconds"),
        "coverage_start": coverage_start.isoformat(),
        "coverage_end": coverage_end.isoformat(),
        "closed_dates": closed_dates,
        "trading_dates": trading_dates,
        "half_day_dates": [],
    }


def download_jpx_calendar_source(source_url: str, *, timeout_seconds: float) -> bytes:
    request = Request(
        source_url,
        headers={"User-Agent": "auto-trade-jpx-calendar/1.0"},
        method="GET",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        status = int(getattr(response, "status", 200) or 200)
        if status != 200:
            raise JPXCalendarSourceError(f"JPX source returned HTTP {status}")
        payload = response.read()
    if not payload:
        raise JPXCalendarSourceError("JPX source returned an empty response")
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    current_year = datetime.now(JST).year
    parser = argparse.ArgumentParser(
        description="Build an explicit JPX trading-day contract from the official JPX closure tables."
    )
    parser.add_argument("--source-url", default=JPX_CALENDAR_SOURCE_URL)
    parser.add_argument("--source-file", help="Optional previously downloaded official HTML source.")
    parser.add_argument("--start-year", type=int, default=current_year)
    parser.add_argument("--end-year", type=int, default=current_year + 1)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--output", default=str(JPX_TRADING_CALENDAR_PATH))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.start_year > args.end_year:
        raise SystemExit("--start-year must be less than or equal to --end-year")
    if args.source_file:
        source_bytes = Path(args.source_file).expanduser().read_bytes()
    else:
        source_bytes = download_jpx_calendar_source(
            str(args.source_url),
            timeout_seconds=float(args.timeout_seconds),
        )
    payload = build_jpx_trading_calendar_payload(
        source_bytes,
        generated_at=datetime.now(JST),
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        source_url=str(args.source_url),
    )
    output_path = Path(args.output).expanduser().resolve(strict=False)
    atomic_write_json(str(output_path), payload)
    print(f"JPX CALENDAR: {output_path}")
    print(f"COVERAGE: {payload['coverage_start']}..{payload['coverage_end']}")
    print(f"TRADING DATES: {len(payload['trading_dates'])}")
    print(f"CLOSED DATES: {len(payload['closed_dates'])}")
    print(f"SOURCE HASH: {payload['source_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
