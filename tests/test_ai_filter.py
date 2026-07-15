from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

from core import ai_filter


def _hash(value):
    return f"sha256:{sha256(str(value or '').encode('utf-8')).hexdigest()}"


def test_ai_filter_blocks_when_no_provider_is_available():
    with patch.object(ai_filter, "gemini_client", None), patch.object(
        ai_filter,
        "groq_client",
        None,
    ):
        result = ai_filter._evaluate_ai_qualitative_filter_core(
            "1000",
            "Example",
            "material news",
        )

    assert result.allowed is False
    assert result.outcome == "blocked_ai_unavailable"
    assert result.prompt_sha256 == _hash(result.prompt)
    assert result.raw_response_sha256 == _hash("")
    assert "no_ai_provider_configured" in result.error


def test_ai_filter_accepts_only_explicit_no_and_blocks_explicit_yes():
    client = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=Mock(
                side_effect=[
                    SimpleNamespace(text="NO\n問題なし"),
                    SimpleNamespace(text="YES\n下方修正"),
                ]
            )
        )
    )
    with patch.object(ai_filter, "gemini_client", client), patch.object(
        ai_filter,
        "groq_client",
        None,
    ):
        approved = ai_filter._evaluate_ai_qualitative_filter_core(
            "1000",
            "Example",
            "news",
        )
        blocked = ai_filter._evaluate_ai_qualitative_filter_core(
            "1000",
            "Example",
            "news",
        )

    assert approved.allowed is True
    assert approved.outcome == "approved"
    assert blocked.allowed is False
    assert blocked.outcome == "blocked_adverse_news"
    assert approved.raw_response_sha256 == _hash(approved.raw_response)
    assert blocked.raw_response_sha256 == _hash(blocked.raw_response)


def test_ai_filter_blocks_malformed_response_instead_of_auto_approving():
    client = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=Mock(
                return_value=SimpleNamespace(text="おそらく問題ありません")
            )
        )
    )
    with patch.object(ai_filter, "gemini_client", client), patch.object(
        ai_filter,
        "groq_client",
        None,
    ):
        result = ai_filter._evaluate_ai_qualitative_filter_core(
            "1000",
            "Example",
            "news",
        )

    assert result.allowed is False
    assert result.outcome == "blocked_ai_invalid_response"
    assert result.raw_response == "おそらく問題ありません"
    assert "invalid_response" in result.error


def test_ai_filter_timeout_fails_closed():
    future = Mock()
    future.result.side_effect = TimeoutError("slow")
    executor = Mock()
    executor.submit.return_value = future
    with patch.object(ai_filter, "ai_executor", executor):
        result = ai_filter.evaluate_ai_qualitative_filter(
            "1000",
            "Example",
            "news",
            timeout=0.01,
        )

    assert result.allowed is False
    assert result.outcome == "blocked_ai_timeout"
    assert result.prompt_sha256 == _hash(result.prompt)
    assert "TimeoutError" in result.error


def test_news_fetch_failure_is_distinct_from_no_news():
    with patch.object(
        ai_filter.requests,
        "get",
        side_effect=requests.Timeout("network unavailable"),
    ):
        result = ai_filter.get_recent_news_evidence("1000", "Example")
        legacy = ai_filter.get_recent_news("1000", "Example")

    assert result.status == "error"
    assert result.news_text == ""
    assert result.news_sha256 == _hash("")
    assert "Timeout" in result.error
    assert legacy == "ニュース取得失敗"


def test_news_fetch_no_entries_records_no_news_evidence():
    response = Mock()
    response.content = b"<rss />"
    response.raise_for_status.return_value = None
    parsed = SimpleNamespace(entries=[], bozo=False)
    with patch.object(ai_filter.requests, "get", return_value=response), patch.object(
        ai_filter.feedparser,
        "parse",
        return_value=parsed,
    ):
        result = ai_filter.get_recent_news_evidence("1000", "Example")

    evidence = ai_filter.build_operational_review_evidence(result)
    assert result.status == "no_news"
    assert evidence["ai_outcome"] == "not_requested_no_news"
    assert evidence["news_sha256"] == _hash("")
    assert evidence["ai_prompt_sha256"] == _hash("")
    assert evidence["ai_raw_response_sha256"] == _hash("")
