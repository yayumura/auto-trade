from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Mapping


def _coerce_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        if isinstance(value, bool):
            return int(value)
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _parse_time_like(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    for candidate in (text, text.replace("T", " ")):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


@dataclass(frozen=True)
class BoardQuote:
    symbol: str
    current_price: float | None
    best_sell_price: float | None
    best_sell_qty: int | None
    best_buy_price: float | None
    best_buy_qty: int | None
    quote_timestamp: datetime | None
    current_price_timestamp: datetime | None
    bid_timestamp: datetime | None
    ask_timestamp: datetime | None
    opening_price_timestamp: datetime | None
    received_at: datetime | None
    bid_sign_raw: str | None
    ask_sign_raw: str | None
    current_price_status: int | None
    upper_limit: float | None
    lower_limit: float | None
    is_valid: bool
    rejection_reason: str | None

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if payload.get("quote_timestamp") is not None:
            payload["quote_timestamp"] = payload["quote_timestamp"].isoformat()
        if payload.get("current_price_timestamp") is not None:
            payload["current_price_timestamp"] = payload["current_price_timestamp"].isoformat()
        if payload.get("bid_timestamp") is not None:
            payload["bid_timestamp"] = payload["bid_timestamp"].isoformat()
        if payload.get("ask_timestamp") is not None:
            payload["ask_timestamp"] = payload["ask_timestamp"].isoformat()
        if payload.get("opening_price_timestamp") is not None:
            payload["opening_price_timestamp"] = payload["opening_price_timestamp"].isoformat()
        if payload.get("received_at") is not None:
            payload["received_at"] = payload["received_at"].isoformat()
        return payload


def parse_board_quote(symbol: str, raw: Mapping[str, Any]) -> BoardQuote:
    current_price = _coerce_float(raw.get("CurrentPrice"))
    best_sell_price = _coerce_float(raw.get("BidPrice"))
    best_buy_price = _coerce_float(raw.get("AskPrice"))
    best_sell_qty = _coerce_int(raw.get("BidQty"))
    best_buy_qty = _coerce_int(raw.get("AskQty"))
    current_price_status = _coerce_int(raw.get("CurrentPriceStatus"))
    upper_limit = _coerce_float(raw.get("UpperLimit"))
    lower_limit = _coerce_float(raw.get("LowerLimit"))
    current_price_timestamp = _parse_time_like(raw.get("CurrentPriceTime"))
    quote_timestamp = _parse_time_like(raw.get("QuoteTime")) or current_price_timestamp
    received_at = _parse_time_like(raw.get("received_at") or raw.get("ReceivedAt"))
    if quote_timestamp is None:
        quote_timestamp = received_at
    bid_timestamp = _parse_time_like(raw.get("BidTime"))
    ask_timestamp = _parse_time_like(raw.get("AskTime"))
    opening_price_timestamp = _parse_time_like(raw.get("OpeningPriceTime"))
    bid_sign_raw = raw.get("BidSign")
    ask_sign_raw = raw.get("AskSign")

    rejection_reason = None
    if current_price is None or current_price <= 0:
        rejection_reason = "missing_current_price"
    elif best_sell_price is None or best_sell_price <= 0:
        rejection_reason = "missing_best_sell_price"
    elif best_buy_price is None or best_buy_price <= 0:
        rejection_reason = "missing_best_buy_price"
    elif current_price_status is not None and current_price_status not in {0, 1, 2}:
        rejection_reason = f"special_quote_status_{current_price_status}"
    elif best_buy_price > best_sell_price:
        rejection_reason = "inverted_spread"

    return BoardQuote(
        symbol=str(symbol),
        current_price=current_price,
        best_sell_price=best_sell_price,
        best_sell_qty=best_sell_qty,
        best_buy_price=best_buy_price,
        best_buy_qty=best_buy_qty,
        quote_timestamp=quote_timestamp,
        current_price_timestamp=current_price_timestamp,
        bid_timestamp=bid_timestamp,
        ask_timestamp=ask_timestamp,
        opening_price_timestamp=opening_price_timestamp,
        received_at=received_at,
        bid_sign_raw=str(bid_sign_raw) if bid_sign_raw is not None else None,
        ask_sign_raw=str(ask_sign_raw) if ask_sign_raw is not None else None,
        current_price_status=current_price_status,
        upper_limit=upper_limit,
        lower_limit=lower_limit,
        is_valid=rejection_reason is None,
        rejection_reason=rejection_reason,
    )
