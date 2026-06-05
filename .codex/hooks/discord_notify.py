#!/usr/bin/env python3
"""Send a Discord notification when a Codex session ends."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

WEBHOOK_ENV = "DISCORD_WEBHOOK_URL"
REQUEST_PHRASES = (
    "ご確認ください",
    "確認してください",
    "教えてください",
    "送ってください",
    "入力してください",
    "選んでください",
    "選択してください",
    "実行してください",
    "対応してください",
    "要対応",
    "対応が必要",
    "必要です",
    "必要があります",
    "見せてください",
    "進めてください",
    "決めてください",
    "お願いします",
    "ください",
    "教えて",
    "let me know",
    "please",
    "could you",
    "can you",
    "what would you like",
    "do you want",
)
FAILURE_PHRASES = (
    "失敗",
    "できない",
    "できません",
    "cannot",
    "can't",
    "unable",
    "blocked",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_local_env() -> None:
    """Load DISCORD_WEBHOOK_URL from the repo's .env if it exists."""

    if WEBHOOK_ENV in os.environ:
        return

    env_path = repo_root() / ".env"
    if not env_path.exists():
        return

    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):].strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() != WEBHOOK_ENV:
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            if value:
                os.environ[WEBHOOK_ENV] = value
                return
    except Exception:
        return


def read_input() -> dict:
    try:
        raw = sys.stdin.read().strip()
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


def normalize_text(text: str) -> str:
    return " ".join(text.split()).strip()


def needs_user_action(message: str) -> bool:
    text = normalize_text(message)
    if not text:
        return False

    lowered = text.lower()
    if "?" in text or "？" in text:
        return True
    if any(phrase in text for phrase in REQUEST_PHRASES):
        return True
    if any(phrase in lowered for phrase in FAILURE_PHRASES):
        return True
    return False


def build_message(payload: dict) -> str:
    last_assistant_message = str(payload.get("last_assistant_message") or "").strip()

    if needs_user_action(last_assistant_message):
        return "Codex: 要対応 / あなたの対応が必要"
    return "Codex: 完了 / あなたの対応は不要"


def send_webhook(url: str, message: str) -> None:
    body = json.dumps({"content": message}, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "codex-discord-hook/1.0",
        },
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        response.read()


def main() -> int:
    load_local_env()
    webhook_url = os.environ.get(WEBHOOK_ENV, "").strip()
    if not webhook_url:
        return 0

    payload = read_input()
    message = build_message(payload)

    try:
        send_webhook(webhook_url, message)
    except HTTPError as exc:
        print(f"Discord webhook failed: HTTP {exc.code} {exc.reason}", file=sys.stderr)
    except URLError as exc:
        print(f"Discord webhook failed: {exc.reason}", file=sys.stderr)
    except Exception as exc:
        print(f"Discord webhook failed: {exc}", file=sys.stderr)

    print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
