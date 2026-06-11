import json
from datetime import datetime
from pathlib import Path

from core.config import JST, ORDER_JOURNAL_FILE
from core.file_io import ensure_absolute_path


def append_order_journal(event: dict, path: str = ORDER_JOURNAL_FILE) -> dict:
    """Append a single order event as JSONL."""
    payload = dict(event or {})
    payload.setdefault("logged_at", datetime.now(JST).isoformat())
    journal_path = Path(ensure_absolute_path(path))
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    with journal_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    return payload
