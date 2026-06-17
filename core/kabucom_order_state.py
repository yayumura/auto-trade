from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import re
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


class StockOrderAction(Enum):
    MARGIN_NEW_LONG = "margin_new_long"
    MARGIN_CLOSE_LONG = "margin_close_long"
    MARGIN_NEW_SHORT = "margin_new_short"
    MARGIN_CLOSE_SHORT = "margin_close_short"


@dataclass(frozen=True)
class StockOrderActionContext:
    side: str
    cash_margin: int
    deliv_type: int
    requires_close_positions: bool


class EntryExecutionStatus(Enum):
    COMPLETED = "completed"
    PARTIAL_UNRESOLVED = "partial_unresolved"
    ZERO_FILL_UNRESOLVED = "zero_fill_unresolved"
    REJECTED = "rejected"


class ExitExecutionStatus(Enum):
    COMPLETED = "completed"
    PARTIAL_UNRESOLVED = "partial_unresolved"
    ZERO_FILL_UNRESOLVED = "zero_fill_unresolved"
    REJECTED = "rejected"


class CancelStatus(Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


class CancelTerminalStatus(Enum):
    CANCELLED = "cancelled"
    FILLED_BEFORE_CANCEL = "filled_before_cancel"
    EXPIRED = "expired"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


MAX_RESPONSE_TEXT_CHARS = 2048
_SECRET_VALUE_PATTERN = re.compile(
    r'(?i)(?P<prefix>"?(?:APIPassword|Password|Token)"?\s*[:=]\s*"?)'
    r'(?P<secret>[^\s,"\'};]+)'
)


def _sanitize_response_text(text: Any) -> str | None:
    if text is None:
        return None
    sanitized = str(text)
    sanitized = _SECRET_VALUE_PATTERN.sub(lambda match: f"{match.group('prefix')}***REDACTED***", sanitized)
    if len(sanitized) > MAX_RESPONSE_TEXT_CHARS:
        sanitized = sanitized[:MAX_RESPONSE_TEXT_CHARS] + "...[truncated]"
    return sanitized


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


@dataclass(frozen=True)
class OrderSubmissionResult:
    status: SubmissionStatus
    intent_id: str
    broker_order_id: str | None
    request_sent: bool
    action: StockOrderAction
    symbol: str
    qty: int
    side: str
    limit_price: float | None = None
    trigger_price: float | None = None
    http_status: int | None = None
    result_code: int | None = None
    rejection_reason: str | None = None
    response_text: str | None = None
    confirmed: bool = False
    confirmation_reason: str | None = None

    @property
    def is_accepted(self) -> bool:
        return self.status == SubmissionStatus.ACCEPTED and bool(self.broker_order_id)

    @property
    def is_confirmed(self) -> bool:
        return self.is_accepted and self.confirmed

    @property
    def is_protective_stop_armed(self) -> bool:
        return self.is_confirmed

    def __bool__(self) -> bool:
        """Accepted submission with a broker order id.

        This intentionally does not mean the order has been confirmed by the
        follow-up orders API read.
        """
        return self.is_accepted

    @classmethod
    def from_submission(
        cls,
        submission: SubmissionResult,
        *,
        action: StockOrderAction,
        request_sent: bool,
        side: str,
        limit_price: float | None = None,
        trigger_price: float | None = None,
        confirmed: bool = False,
        confirmation_reason: str | None = None,
    ) -> "OrderSubmissionResult":
        return cls(
            status=submission.status,
            intent_id=submission.intent_id,
            broker_order_id=submission.broker_order_id,
            request_sent=bool(request_sent),
            action=action,
            symbol=submission.symbol,
            qty=int(submission.qty),
            side=side,
            limit_price=limit_price,
            trigger_price=trigger_price,
            http_status=submission.http_status,
            result_code=submission.result_code,
            rejection_reason=submission.rejection_reason,
            response_text=submission.response_text,
            confirmed=bool(confirmed),
            confirmation_reason=confirmation_reason,
        )


@dataclass(frozen=True)
class ExecutionFill:
    execution_id: str
    qty: int
    price: float
    executed_at: datetime | None = None
    commission: float | None = None
    commission_tax: float | None = None


@dataclass(frozen=True)
class ExecutionWaitResult:
    process_state: OrderProcessState
    terminal_reason: OrderTerminalReason | None
    fills: tuple[ExecutionFill, ...]
    cumulative_qty: int
    remaining_qty: int
    unresolved: bool
    unresolved_reason: str | None
    order_id: str | None = None
    submission_status: SubmissionStatus | None = None
    raw_details: dict[str, Any] | None = None

    def __bool__(self) -> bool:
        return not self.unresolved or self.cumulative_qty > 0

    @property
    def average_price(self) -> float | None:
        qty_sum = sum(max(0, int(fill.qty)) for fill in self.fills)
        if qty_sum <= 0:
            return None
        value_sum = sum(max(0, int(fill.qty)) * float(fill.price) for fill in self.fills)
        return value_sum / qty_sum

    @property
    def execution_ids(self) -> tuple[str, ...]:
        return tuple(fill.execution_id for fill in self.fills if fill.execution_id)

    @property
    def entry_execution_status(self) -> EntryExecutionStatus:
        return classify_entry_execution_status(
            unresolved=self.unresolved,
            cumulative_qty=self.cumulative_qty,
            terminal_reason=self.terminal_reason,
        )

    @property
    def exit_execution_status(self) -> ExitExecutionStatus:
        return classify_exit_execution_status(
            unresolved=self.unresolved,
            cumulative_qty=self.cumulative_qty,
            terminal_reason=self.terminal_reason,
        )

    def to_legacy_dict(self, *, symbol: str | None = None, side: str | None = None, execution_kind: str = "entry") -> dict[str, Any]:
        average_price = self.average_price
        order_qty = self.cumulative_qty + max(0, int(self.remaining_qty))
        detail_state = 10 if self.unresolved else (5 if self.process_state == OrderProcessState.TERMINAL else 3)
        if str(execution_kind).strip().lower() == "exit":
            execution_status = self.exit_execution_status.value
            execution_status_key = "exit_execution_status"
        else:
            execution_status = self.entry_execution_status.value
            execution_status_key = "entry_execution_status"
        details = [
            {
                "RecType": 8,
                "SeqNum": idx + 1,
                "State": detail_state,
                "Qty": int(fill.qty),
                "Price": float(fill.price),
                "ExecutionID": fill.execution_id,
            }
            for idx, fill in enumerate(self.fills)
        ]
        return {
            "OrderId": self.order_id,
            "OrderQty": order_qty,
            "CumQty": self.cumulative_qty,
            "State": detail_state,
            "OrderState": detail_state,
            "Details": details,
            "unresolved": self.unresolved,
            "unresolved_reason": self.unresolved_reason,
            "submission_status": None if self.submission_status is None else self.submission_status.value,
            "process_state": self.process_state.value,
            "terminal_reason": None if self.terminal_reason is None else self.terminal_reason.value,
            "Qty": self.cumulative_qty,
            "filled_qty": self.cumulative_qty,
            "Price": average_price if average_price is not None else 0.0,
            "average_price": average_price,
            "remaining_qty": max(0, int(self.remaining_qty)),
            "Symbol": symbol,
            "side": side,
            "has_partial_fill": self.cumulative_qty > 0 and self.remaining_qty > 0,
            "execution_ids": self.execution_ids,
            "execution_id": self.execution_ids[0] if self.execution_ids else None,
            "execution_status": execution_status,
            execution_status_key: execution_status,
            "__parsed_process_state__": self.process_state.value,
            "__parsed_terminal_reason__": None if self.terminal_reason is None else self.terminal_reason.value,
            "__parsed_cumulative_qty__": self.cumulative_qty,
            "__parsed_order_qty__": order_qty,
            "__parsed_average_fill_price__": average_price,
            "__parsed_has_partial_fill__": self.cumulative_qty > 0 and self.remaining_qty > 0,
        }


@dataclass(frozen=True)
class CancelResult:
    status: CancelStatus
    order_id: str | None
    parsed_order: ParsedOrder | None
    cumulative_qty: int
    remaining_qty: int
    request_sent: bool
    confirmed: bool = False
    terminal_status: CancelTerminalStatus | None = None
    terminal_reason: OrderTerminalReason | None = None
    http_status: int | None = None
    result_code: int | None = None
    rejection_reason: str | None = None
    response_text: str | None = None

    def __bool__(self) -> bool:
        if self.terminal_status is None:
            return self.confirmed and self.status == CancelStatus.ACCEPTED
        return (
            self.confirmed
            and self.status == CancelStatus.ACCEPTED
            and self.terminal_status == CancelTerminalStatus.CANCELLED
        )


def resolve_cancel_terminal_status(parsed_order: ParsedOrder | None) -> CancelTerminalStatus | None:
    if parsed_order is None:
        return None
    if parsed_order.terminal_reason == OrderTerminalReason.CANCELLED:
        return CancelTerminalStatus.CANCELLED
    if parsed_order.terminal_reason == OrderTerminalReason.FILLED:
        return CancelTerminalStatus.FILLED_BEFORE_CANCEL
    if parsed_order.terminal_reason == OrderTerminalReason.EXPIRED:
        return CancelTerminalStatus.EXPIRED
    if parsed_order.terminal_reason == OrderTerminalReason.REJECTED:
        return CancelTerminalStatus.REJECTED
    if parsed_order.process_state == OrderProcessState.TERMINAL:
        return CancelTerminalStatus.UNKNOWN
    return None


def resolve_stock_order_action(side: str, cash_margin: int | None = None, *, allow_short: bool = False) -> StockOrderAction:
    side_text = str(side or "").strip()
    if side_text == "2":
        if cash_margin == 3:
            if not allow_short:
                raise ValueError("Unsupported stock order action: MARGIN_CLOSE_SHORT")
            return StockOrderAction.MARGIN_CLOSE_SHORT
        return StockOrderAction.MARGIN_NEW_LONG
    if side_text == "1":
        if cash_margin == 2:
            if not allow_short:
                raise ValueError("Unsupported stock order action: MARGIN_NEW_SHORT")
            return StockOrderAction.MARGIN_NEW_SHORT
        return StockOrderAction.MARGIN_CLOSE_LONG
    raise ValueError(f"Unsupported stock order side: {side!r}")


def resolve_stock_order_action_context(
    action: StockOrderAction,
    *,
    allow_short: bool = False,
) -> StockOrderActionContext:
    if action == StockOrderAction.MARGIN_NEW_LONG:
        return StockOrderActionContext(
            side="2",
            cash_margin=2,
            deliv_type=0,
            requires_close_positions=False,
        )
    if action == StockOrderAction.MARGIN_CLOSE_LONG:
        return StockOrderActionContext(
            side="1",
            cash_margin=3,
            deliv_type=2,
            requires_close_positions=True,
        )
    if action == StockOrderAction.MARGIN_NEW_SHORT:
        if not allow_short:
            raise ValueError("Unsupported stock order action: MARGIN_NEW_SHORT")
        return StockOrderActionContext(
            side="1",
            cash_margin=2,
            deliv_type=0,
            requires_close_positions=False,
        )
    if action == StockOrderAction.MARGIN_CLOSE_SHORT:
        if not allow_short:
            raise ValueError("Unsupported stock order action: MARGIN_CLOSE_SHORT")
        return StockOrderActionContext(
            side="2",
            cash_margin=3,
            deliv_type=2,
            requires_close_positions=True,
        )
    raise ValueError(f"Unsupported stock order action: {action!r}")


def _classify_execution_status(
    *,
    unresolved: bool,
    cumulative_qty: int,
    terminal_reason: OrderTerminalReason | None,
    status_enum: type[EntryExecutionStatus] | type[ExitExecutionStatus],
):
    if unresolved:
        if cumulative_qty > 0:
            return status_enum.PARTIAL_UNRESOLVED
        return status_enum.ZERO_FILL_UNRESOLVED
    if cumulative_qty > 0:
        return status_enum.COMPLETED
    return status_enum.REJECTED


def classify_entry_execution_status(
    *,
    unresolved: bool,
    cumulative_qty: int,
    terminal_reason: OrderTerminalReason | None,
) -> EntryExecutionStatus:
    return _classify_execution_status(
        unresolved=bool(unresolved),
        cumulative_qty=int(cumulative_qty),
        terminal_reason=terminal_reason,
        status_enum=EntryExecutionStatus,
    )


def classify_exit_execution_status(
    *,
    unresolved: bool,
    cumulative_qty: int,
    terminal_reason: OrderTerminalReason | None,
) -> ExitExecutionStatus:
    return _classify_execution_status(
        unresolved=bool(unresolved),
        cumulative_qty=int(cumulative_qty),
        terminal_reason=terminal_reason,
        status_enum=ExitExecutionStatus,
    )


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
) -> SubmissionResult:
    http_status = None if response is None else getattr(response, "status_code", None)
    response_text = None if response is None else _sanitize_response_text(getattr(response, "text", None))

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


def classify_cancel_response(*, intent_id: str, response: Any) -> SubmissionResult:
    """cancelorder の応答を、OrderId 欠損を許容する専用ルールで分類する。"""
    http_status = None if response is None else getattr(response, "status_code", None)
    response_text = None if response is None else _sanitize_response_text(getattr(response, "text", None))

    if response is None:
        return SubmissionResult(
            status=SubmissionStatus.UNKNOWN,
            intent_id=intent_id,
            broker_order_id=None,
            symbol="",
            side="",
            qty=0,
            price=None,
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
                symbol="",
                side="",
                qty=0,
                price=None,
                http_status=http_status,
                rejection_reason="malformed_200_response",
                response_text=response_text,
            )
        if not isinstance(payload, Mapping):
            return SubmissionResult(
                status=SubmissionStatus.UNKNOWN,
                intent_id=intent_id,
                broker_order_id=None,
                symbol="",
                side="",
                qty=0,
                price=None,
                http_status=http_status,
                rejection_reason="schema_invalid",
                response_text=response_text,
            )
        result_code = _coerce_int(payload.get("Result"))
        order_id = _normalize_order_id(payload)
        if result_code == 0:
            return SubmissionResult(
                status=SubmissionStatus.ACCEPTED,
                intent_id=intent_id,
                broker_order_id=order_id,
                symbol="",
                side="",
                qty=0,
                price=None,
                http_status=http_status,
                result_code=result_code,
                response_text=response_text,
            )
        if result_code is None:
            return SubmissionResult(
                status=SubmissionStatus.UNKNOWN,
                intent_id=intent_id,
                broker_order_id=order_id,
                symbol="",
                side="",
                qty=0,
                price=None,
                http_status=http_status,
                rejection_reason="missing_result_code",
                response_text=response_text,
            )
        return SubmissionResult(
            status=SubmissionStatus.REJECTED,
            intent_id=intent_id,
            broker_order_id=order_id,
            symbol="",
            side="",
            qty=0,
            price=None,
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
            symbol="",
            side="",
            qty=0,
            price=None,
            http_status=http_status,
            rejection_reason=f"http_{http_status}",
            response_text=response_text,
        )

    if http_status is not None and http_status >= 500:
        return SubmissionResult(
            status=SubmissionStatus.UNKNOWN,
            intent_id=intent_id,
            broker_order_id=None,
            symbol="",
            side="",
            qty=0,
            price=None,
            http_status=http_status,
            rejection_reason=f"http_{http_status}",
            response_text=response_text,
        )

    return SubmissionResult(
        status=SubmissionStatus.UNKNOWN,
        intent_id=intent_id,
        broker_order_id=None,
        symbol="",
        side="",
        qty=0,
        price=None,
        http_status=http_status,
        rejection_reason="unclassified_response",
        response_text=response_text,
    )
