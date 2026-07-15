from datetime import datetime
from hashlib import sha256

import pytest

from core.config import JST
from core.jpx_calendar import JPX_CALENDAR_SOURCE_URL
from scripts.update_jpx_trading_calendar import (
    JPXCalendarSourceError,
    build_jpx_trading_calendar_payload,
    extract_jpx_closed_dates,
)


def _build_source_html(*years: int) -> bytes:
    sections = []
    for year in years:
        rows = []
        for month in range(1, 13):
            rows.append(f"<tr><td>{year}/{month:02d}/01（月）</td><td>休業日</td></tr>")
        rows.extend(
            [
                f"<tr><td>{year}/01/02（火）</td><td>休業日</td></tr>",
                f"<tr><td>{year}/01/03（水）</td><td>休業日</td></tr>",
                f"<tr><td>{year}/12/31（木）</td><td>休業日</td></tr>",
            ]
        )
        sections.append(
            f"<h3><span>{year}年</span></h3><div><table>{''.join(rows)}</table></div>"
        )
    return "".join(sections).encode("utf-8")


def test_build_payload_explicitly_partitions_trading_and_closed_dates():
    source_bytes = _build_source_html(2026, 2027)
    payload = build_jpx_trading_calendar_payload(
        source_bytes,
        generated_at=datetime(2026, 7, 15, 9, 30, tzinfo=JST),
        start_year=2026,
        end_year=2027,
    )

    closed_dates = set(payload["closed_dates"])
    trading_dates = set(payload["trading_dates"])
    assert payload["source_url"] == JPX_CALENDAR_SOURCE_URL
    assert payload["source_hash"] == f"sha256:{sha256(source_bytes).hexdigest()}"
    assert payload["coverage_start"] == "2026-01-01"
    assert payload["coverage_end"] == "2027-12-31"
    assert "2026-01-01" in closed_dates
    assert "2026-01-03" in closed_dates
    assert "2026-01-05" in trading_dates
    assert not (closed_dates & trading_dates)
    assert len(closed_dates) + len(trading_dates) == 730
    assert payload["half_day_dates"] == []


def test_extract_closed_dates_requires_every_requested_year():
    source_text = _build_source_html(2026).decode("utf-8")

    with pytest.raises(JPXCalendarSourceError, match="missing requested calendar years: 2027"):
        extract_jpx_closed_dates(source_text, start_year=2026, end_year=2027)


def test_extract_closed_dates_rejects_truncated_year_table():
    source_text = (
        "<h3><span>2026年</span></h3>"
        "<table><tr><td>2026/01/01（木）</td><td>元日</td></tr></table>"
    )

    with pytest.raises(JPXCalendarSourceError, match="only 1 closed dates"):
        extract_jpx_closed_dates(source_text, start_year=2026, end_year=2026)
