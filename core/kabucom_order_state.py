from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class OrderProcessState(Enum):
    ACTIVE = "active"
    TERMINAL = "terminal"
    UNKNOWN = "unknown"


class OrderTerminalReason(Enum):
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"


class SubmissionStatus(Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ParsedOrder:
    order_id: str | None
    process_state: OrderProcessState
    terminal_reason: OrderTerminalReason | None
    order_qty: int
    cumulative_qty: int
    unfilled_qty: int
    working_qty: int
    average_fill_price: float | None
    execution_ids: tuple[str, ...]
    raw_state: int | None
    raw_order_state: int | None
    latest_detail_rec_type: int | None
    has_partial_fill: bool
    detail_count: int
    is_consistent: bool


@dataclass(frozen=True)
class SubmissionResult:
    status: SubmissionStatus
    intent_id: str
    broker_order_id: str | None
    symbol: str
    side: str
    qty: int
    price: float | None
    http_status: int | None
    result_code: int | None = None
    rejection_reason: str | None = None
    response_text: str | None = None


_ACTIVE_RAW_STATES = {1, 2, 3, 4}


def _coerce_int(value: Any, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        if isinstance(value, bool):
            return int(value)
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_order_id(raw: Mapping[str, Any]) -> str | None:
    for key in ("OrderId", "OrderID", "ID", "Id"):
        value = raw.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _extract_details(raw: Mapping[str, Any]) -> list[dict[str, Any]]:
    details = raw.get("Details")
    if not isinstance(details, list):
        return []
    normalized: list[dict[str, Any]] = []
    for detail in details:
        if isinstance(detail, Mapping):
            normalized.append(dict(detail))
    return normalized


def _sort_details_by_seqnum(details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """SeqNum がある場合はそれを優先し、配列順への依存を減らす。"""
    indexed_details: list[tuple[bool, int, int, dict[str, Any]]] = []
    for index, detail in enumerate(details):
        seq_num = _coerce_int(detail.get("SeqNum"))
        indexed_details.append((seq_num is None, seq_num if seq_num is not None else index, index, detail))
    indexed_details.sort(key=lambda item: (item[0], item[1], item[2]))
    return [item[3] for item in indexed_details]


def parse_kabucom_order(raw: Mapping[str, Any] | None) -> ParsedOrder:
    payload = dict(raw or {})
    details = _sort_details_by_seqnum(_extract_details(payload))
    raw_state = _coerce_int(payload.get("State"))
    raw_order_state = _coerce_int(payload.get("OrderState"))
    state_for_classification = raw_state if raw_state is not None else raw_order_state
    order_qty = _coerce_int(payload.get("OrderQty"), default=None)
    if order_qty is None:
        order_qty = _coerce_int(payload.get("Qty"), default=0) or 0
    cumulative_qty = _coerce_int(payload.get("CumQty"), default=0) or 0
    if cumulative_qty < 0:
        cumulative_qty = 0

    fill_qty_sum = 0
    fill_value_sum = 0.0
    execution_ids: list[str] = []
    seen_execution_ids: set[str] = set()
    seen_seq_nums: set[int] = set()
    is_consistent = True
    cancel_like_detail = False
    expire_like_detail = False
    reject_like_detail = False
    detail_error_like = False
    latest_detail_rec_type = None

    for detail in details:
        rec_type = _coerce_int(detail.get("RecType"))
        seq_num = _coerce_int(detail.get("SeqNum"))
        if seq_num is not None:
            if seq_num in seen_seq_nums:
                is_consistent = False
            else:
                seen_seq_nums.add(seq_num)
        if rec_type is not None:
            latest_detail_rec_type = rec_type
        state = _coerce_int(detail.get("State"))
        if state is not None:
            if state == 4:
                detail_error_like = True
        qty = _coerce_int(detail.get("Qty"))
        if qty is None:
            qty = _coerce_int(detail.get("CumQty"), default=0) or 0
        price = _coerce_float(detail.get("Price"))
        execution_id = detail.get("ExecutionID")
        if execution_id is not None and rec_type == 8:
            execution_text = str(execution_id).strip()
            if execution_text:
                if execution_text in seen_execution_ids:
                    is_consistent = False
                else:
                    seen_execution_ids.add(execution_text)
                execution_ids.append(execution_text)

        if rec_type == 8:
            fill_qty_sum += max(0, int(qty or 0))
            if price is not None:
                fill_value_sum += float(price) * max(0, int(qty or 0))
        elif rec_type == 6:
            cancel_like_detail = True
        elif rec_type in {3, 7}:
            expire_like_detail = True

        if state is not None and state not in {1, 2, 3, 4, 5}:
            reject_like_detail = True

    order_qty = max(0, int(order_qty or 0))
    cumulative_qty = max(0, int(cumulative_qty or 0))
    unfilled_qty = max(order_qty - cumulative_qty, 0)
    has_partial_fill = order_qty > 0 and 0 < cumulative_qty < order_qty
    average_fill_price = None
    if fill_qty_sum > 0:
        average_fill_price = fill_value_sum / fill_qty_sum

    if order_qty > 0 and cumulative_qty > order_qty:
        is_consistent = False
    if fill_qty_sum > 0 and cumulative_qty > 0 and fill_qty_sum != cumulative_qty:
        is_consistent = False
    if has_partial_fill and not details and raw_state == 5:
        is_consistent = False
    if raw_state is not None and raw_order_state is not None and raw_state != raw_order_state:
        is_consistent = False

    process_state = OrderProcessState.UNKNOWN
    terminal_reason: OrderTerminalReason | None = None

    if state_for_classification in _ACTIVE_RAW_STATES:
        process_state = OrderProcessState.ACTIVE
        if not is_consistent or detail_error_like:
            process_state = OrderProcessState.UNKNOWN
    elif state_for_classification == 5:
        if order_qty > 0 and cumulative_qty >= order_qty and (fill_qty_sum in {0, cumulative_qty}):
            process_state = OrderProcessState.TERMINAL
            terminal_reason = OrderTerminalReason.FILLED
        elif details:
            if cancel_like_detail:
                process_state = OrderProcessState.TERMINAL
                terminal_reason = OrderTerminalReason.CANCELLED
            elif expire_like_detail:
                process_state = OrderProcessState.TERMINAL
                terminal_reason = OrderTerminalReason.EXPIRED
            elif (detail_error_like or reject_like_detail) and cumulative_qty == 0:
                process_state = OrderProcessState.TERMINAL
                terminal_reason = OrderTerminalReason.REJECTED
            elif cumulative_qty > 0:
                process_state = OrderProcessState.UNKNOWN
            else:
                process_state = OrderProcessState.UNKNOWN
        else:
            process_state = OrderProcessState.UNKNOWN
    else:
        process_state = OrderProcessState.UNKNOWN

    if not is_consistent:
        process_state = OrderProcessState.UNKNOWN
        terminal_reason = None

    working_qty = unfilled_qty if process_state == OrderProcessState.ACTIVE else 0
    if process_state == OrderProcessState.TERMINAL and terminal_reason is None:
        process_state = OrderProcessState.UNKNOWN

    return ParsedOrder(
        order_id=_normalize_order_id(payload),
        process_state=process_state,
        terminal_reason=terminal_reason,
        order_qty=order_qty,
        cumulative_qty=cumulative_qty,
        unfilled_qty=unfilled_qty,
        working_qty=working_qty,
        average_fill_price=average_fill_price,
        execution_ids=tuple(execution_ids),
        raw_state=raw_state,
        raw_order_state=raw_order_state,
        latest_detail_rec_type=latest_detail_rec_type,
        has_partial_fill=has_partial_fill,
        detail_count=len(details),
        is_consistent=is_consistent,
    )


def classify_submission_response(
    *,
    intent_id: str,
    symbol: str,
    side: str,
    qty: int,
    price: float | None,
    response: Any,
    allow_missing_order_id: bool = False,
) -> SubmissionResult:
    http_status = None if response is None else getattr(response, "status_code", None)
    response_text = None if response is None else getattr(response, "text", None)

    if response is None:
        return SubmissionResult(
            status=SubmissionStatus.UNKNOWN,
            intent_id=intent_id,
            broker_order_id=None,
            symbol=symbol,
            side=side,
            qty=int(qty),
            price=price,
            http_status=None,
            rejection_reason="no_response",
            response_text=None,
        )

    if http_status == 200:
        try:
            payload = response.json()
        except Exception:
            return SubmissionResult(
                status=SubmissionStatus.UNKNOWN,
                intent_id=intent_id,
                broker_order_id=None,
                symbol=symbol,
                side=side,
                qty=int(qty),
                price=price,
                http_status=http_status,
                rejection_reason="malformed_200_response",
                response_text=response_text,
            )
        if not isinstance(payload, Mapping):
            return SubmissionResult(
                status=SubmissionStatus.UNKNOWN,
                intent_id=intent_id,
                broker_order_id=None,
                symbol=symbol,
                side=side,
                qty=int(qty),
                price=price,
                http_status=http_status,
                rejection_reason="schema_invalid",
                response_text=response_text,
            )
        result_code = _coerce_int(payload.get("Result"))
        order_id = _normalize_order_id(payload)
        if result_code == 0 and order_id:
            return SubmissionResult(
                status=SubmissionStatus.ACCEPTED,
                intent_id=intent_id,
                broker_order_id=order_id,
                symbol=symbol,
                side=side,
                qty=int(qty),
                price=price,
                http_status=http_status,
                result_code=result_code,
                response_text=response_text,
            )
        if result_code == 0 and allow_missing_order_id:
            return SubmissionResult(
                status=SubmissionStatus.ACCEPTED,
                intent_id=intent_id,
                broker_order_id=order_id,
                symbol=symbol,
                side=side,
                qty=int(qty),
                price=price,
                http_status=http_status,
                result_code=result_code,
                rejection_reason="missing_order_id_but_allowed",
                response_text=response_text,
            )
        if result_code is None:
            return SubmissionResult(
                status=SubmissionStatus.UNKNOWN,
                intent_id=intent_id,
                broker_order_id=order_id,
                symbol=symbol,
                side=side,
                qty=int(qty),
                price=price,
                http_status=http_status,
                rejection_reason="missing_result_code",
                response_text=response_text,
            )
        if result_code == 0 and not order_id:
            return SubmissionResult(
                status=SubmissionStatus.UNKNOWN,
                intent_id=intent_id,
                broker_order_id=None,
                symbol=symbol,
                side=side,
                qty=int(qty),
                price=price,
                http_status=http_status,
                result_code=result_code,
                rejection_reason="missing_order_id",
                response_text=response_text,
            )
        return SubmissionResult(
            status=SubmissionStatus.REJECTED,
            intent_id=intent_id,
            broker_order_id=order_id,
            symbol=symbol,
            side=side,
            qty=int(qty),
            price=price,
            http_status=http_status,
            result_code=result_code,
            rejection_reason="result_non_zero",
            response_text=response_text,
        )

    if http_status in {400, 401, 403, 404, 405, 413, 415, 429}:
        return SubmissionResult(
            status=SubmissionStatus.REJECTED,
            intent_id=intent_id,
            broker_order_id=None,
            symbol=symbol,
            side=side,
            qty=int(qty),
            price=price,
            http_status=http_status,
            rejection_reason=f"http_{http_status}",
            response_text=response_text,
        )

    if http_status is not None and http_status >= 500:
        return SubmissionResult(
            status=SubmissionStatus.UNKNOWN,
            intent_id=intent_id,
            broker_order_id=None,
            symbol=symbol,
            side=side,
            qty=int(qty),
            price=price,
            http_status=http_status,
            rejection_reason=f"http_{http_status}",
            response_text=response_text,
        )

    return SubmissionResult(
        status=SubmissionStatus.UNKNOWN,
        intent_id=intent_id,
        broker_order_id=None,
        symbol=symbol,
        side=side,
        qty=int(qty),
        price=price,
        http_status=http_status,
        rejection_reason="unclassified_response",
        response_text=response_text,
    )
