from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass
from hashlib import sha256
import re
import urllib.parse

import feedparser
from google import genai
import requests

from core.config import GEMINI_API_KEY, GEMINI_MODEL, GROQ_API_KEY, GROQ_MODEL


AI_OPERATIONAL_EVIDENCE_SCHEMA_VERSION = 1


def _sha256_text(value: str) -> str:
    return f"sha256:{sha256(str(value or '').encode('utf-8')).hexdigest()}"


def clean_text_for_ai(text):
    if not isinstance(text, str):
        return ""
    text = re.sub(r"[\r\n\t]+", " ", text)
    return re.sub(
        r"[^\x20-\x7E\u3000-\u303F\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]",
        "",
        text,
    ).strip()


@dataclass(frozen=True)
class NewsFetchResult:
    status: str
    code: str
    name: str
    query_url: str
    titles: tuple[str, ...]
    news_text: str
    news_sha256: str
    error: str | None = None

    def to_evidence(self) -> dict[str, object]:
        return {
            "operational_evidence_schema_version": AI_OPERATIONAL_EVIDENCE_SCHEMA_VERSION,
            "news_fetch_status": self.status,
            "news_query_url": self.query_url,
            "news_text": self.news_text,
            "news_sha256": self.news_sha256,
            "news_error": self.error or "",
        }


@dataclass(frozen=True)
class AIQualitativeFilterResult:
    allowed: bool
    outcome: str
    reason: str
    provider: str
    model: str
    prompt: str
    prompt_sha256: str
    raw_response: str
    raw_response_sha256: str
    error: str | None = None

    def to_evidence(self) -> dict[str, object]:
        return {
            "ai_outcome": self.outcome,
            "ai_provider": self.provider,
            "ai_model": self.model,
            "ai_prompt": self.prompt,
            "ai_prompt_sha256": self.prompt_sha256,
            "ai_raw_response": self.raw_response,
            "ai_raw_response_sha256": self.raw_response_sha256,
            "ai_error": self.error or "",
        }


if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
else:
    gemini_client = None

groq_client = None
if GROQ_API_KEY:
    try:
        from groq import Groq

        groq_client = Groq(api_key=GROQ_API_KEY)
    except ImportError:
        print("[Safety Warning] 'groq' library not found. AI failover is unavailable.")

ai_executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)


def get_recent_news_evidence(code, name, timeout=5) -> NewsFetchResult:
    """Fetch point-in-time news evidence without conflating failure with no news."""
    code_text = str(code or "").strip()
    clean_name = re.sub(r"\s+", " ", str(name or "")).strip()
    query = urllib.parse.quote(f"{code_text} {clean_name}")
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
    try:
        response = requests.get(rss_url, timeout=timeout)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        entries = list(getattr(feed, "entries", ()) or ())
        if bool(getattr(feed, "bozo", False)) and not entries:
            raise ValueError(f"rss_parse_error:{getattr(feed, 'bozo_exception', 'unknown')}")
        titles = tuple(
            str(getattr(entry, "title", "") or "").strip()
            for entry in entries[:5]
            if str(getattr(entry, "title", "") or "").strip()
        )
        news_text = " | ".join(titles)
        return NewsFetchResult(
            status="ok" if titles else "no_news",
            code=code_text,
            name=clean_name,
            query_url=rss_url,
            titles=titles,
            news_text=news_text,
            news_sha256=_sha256_text(news_text),
        )
    except Exception as exc:
        return NewsFetchResult(
            status="error",
            code=code_text,
            name=clean_name,
            query_url=rss_url,
            titles=(),
            news_text="",
            news_sha256=_sha256_text(""),
            error=f"{type(exc).__name__}:{exc}",
        )


def get_recent_news(code, name, timeout=5):
    """Backward-compatible text wrapper; failures remain distinguishable."""
    result = get_recent_news_evidence(code, name, timeout=timeout)
    if result.status == "ok":
        return result.news_text
    if result.status == "no_news":
        return "ニュースなし"
    return "ニュース取得失敗"


def _build_ai_prompt(code, name, news_text) -> str:
    safe_name = clean_text_for_ai(name)
    safe_news = clean_text_for_ai(news_text)
    return (
        f"対象銘柄: {safe_name} ({code})\n"
        f"最新ニュース: {safe_news}\n\n"
        "あなたは機関投資家のコンプライアンス・リスク管理者です。\n"
        "この銘柄のニュースの中に、直近で「下方修正」「粉飾決算」"
        "「不祥事・スキャンダル」「第三者割当増資(希薄化)」"
        "「上場廃止懸念」などの致命的・突発的な悪材料が含まれるか判定してください。\n\n"
        "出力ルール:\n"
        "1行目: YES または NO (悪材料があればYES、特になければNO)\n"
        "2行目: 理由(短く)"
    )


def _parse_ai_response(raw_response: str) -> str | None:
    lines = [line.strip().upper() for line in str(raw_response or "").splitlines() if line.strip()]
    if not lines:
        return None
    first_token = lines[0].split(maxsplit=1)[0].rstrip(":：")
    if first_token in {"YES", "NO"}:
        return first_token
    return None


def _result_from_response(*, provider, model, prompt, raw_response):
    parsed = _parse_ai_response(raw_response)
    if parsed == "YES":
        return AIQualitativeFilterResult(
            allowed=False,
            outcome="blocked_adverse_news",
            reason=f"{provider} detected adverse news",
            provider=provider,
            model=model,
            prompt=prompt,
            prompt_sha256=_sha256_text(prompt),
            raw_response=str(raw_response or ""),
            raw_response_sha256=_sha256_text(str(raw_response or "")),
        )
    if parsed == "NO":
        return AIQualitativeFilterResult(
            allowed=True,
            outcome="approved",
            reason=f"{provider} found no fatal adverse news",
            provider=provider,
            model=model,
            prompt=prompt,
            prompt_sha256=_sha256_text(prompt),
            raw_response=str(raw_response or ""),
            raw_response_sha256=_sha256_text(str(raw_response or "")),
        )
    return None


def _blocked_ai_result(*, outcome, reason, prompt, provider, model, raw_response="", error=None):
    return AIQualitativeFilterResult(
        allowed=False,
        outcome=outcome,
        reason=reason,
        provider=provider,
        model=model,
        prompt=prompt,
        prompt_sha256=_sha256_text(prompt),
        raw_response=str(raw_response or ""),
        raw_response_sha256=_sha256_text(str(raw_response or "")),
        error=error,
    )


def _evaluate_ai_qualitative_filter_core(code, name, news_text):
    """Operational news veto. Unknown or malformed states always fail closed."""
    prompt = _build_ai_prompt(code, name, news_text)
    errors = []
    last_provider = "none"
    last_model = f"gemini:{GEMINI_MODEL}|groq:{GROQ_MODEL}"
    last_response = ""

    if gemini_client is not None:
        last_provider = "gemini"
        last_model = GEMINI_MODEL
        try:
            response = gemini_client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
            last_response = str(getattr(response, "text", "") or "")
            result = _result_from_response(
                provider="gemini",
                model=GEMINI_MODEL,
                prompt=prompt,
                raw_response=last_response,
            )
            if result is not None:
                return result
            errors.append("gemini:invalid_response")
        except Exception as exc:
            errors.append(f"gemini:{type(exc).__name__}:{exc}")

    if groq_client is not None:
        last_provider = "groq"
        last_model = GROQ_MODEL
        try:
            response = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            last_response = str(response.choices[0].message.content or "")
            result = _result_from_response(
                provider="groq",
                model=GROQ_MODEL,
                prompt=prompt,
                raw_response=last_response,
            )
            if result is not None:
                return result
            errors.append("groq:invalid_response")
        except Exception as exc:
            errors.append(f"groq:{type(exc).__name__}:{exc}")

    if gemini_client is None and groq_client is None:
        errors.append("no_ai_provider_configured")
    error_text = " | ".join(errors)
    outcome = "blocked_ai_invalid_response" if last_response else "blocked_ai_unavailable"
    return _blocked_ai_result(
        outcome=outcome,
        reason="AI evidence unavailable; entry blocked",
        prompt=prompt,
        provider=last_provider,
        model=last_model,
        raw_response=last_response,
        error=error_text,
    )


def evaluate_ai_qualitative_filter(code, name, news_text, timeout=10):
    """Bound AI latency and fail closed when the result is unavailable."""
    prompt = _build_ai_prompt(code, name, news_text)
    try:
        future = ai_executor.submit(
            _evaluate_ai_qualitative_filter_core,
            code,
            name,
            news_text,
        )
        return future.result(timeout=timeout)
    except Exception as exc:
        return _blocked_ai_result(
            outcome="blocked_ai_timeout",
            reason="AI review timed out; entry blocked",
            prompt=prompt,
            provider="timeout",
            model=f"gemini:{GEMINI_MODEL}|groq:{GROQ_MODEL}",
            error=f"{type(exc).__name__}:{exc}",
        )


def build_operational_review_evidence(
    news_result: NewsFetchResult,
    ai_result: AIQualitativeFilterResult | None = None,
) -> dict[str, object]:
    evidence = news_result.to_evidence()
    if ai_result is not None:
        evidence.update(ai_result.to_evidence())
        return evidence
    if news_result.status == "no_news":
        outcome = "not_requested_no_news"
    else:
        outcome = "not_requested_news_fetch_failed"
    evidence.update(
        {
            "ai_outcome": outcome,
            "ai_provider": "",
            "ai_model": "",
            "ai_prompt": "",
            "ai_prompt_sha256": _sha256_text(""),
            "ai_raw_response": "",
            "ai_raw_response_sha256": _sha256_text(""),
            "ai_error": "",
        }
    )
    return evidence


def ai_qualitative_filter(code, name, news_text, timeout=10):
    """Backward-compatible tuple wrapper with fail-closed semantics."""
    result = evaluate_ai_qualitative_filter(code, name, news_text, timeout=timeout)
    return result.allowed, result.reason
