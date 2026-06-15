from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


OFFICIAL_CONTRACT_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "contracts" / "kabucom_contract_fixture.json"
TEST_CONTRACT_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "contracts" / "kabucom_test_contract_fixture.json"
CONTRACT_FIXTURE_PATH = OFFICIAL_CONTRACT_FIXTURE_PATH


@dataclass(frozen=True)
class ContractValidationResult:
    valid: bool
    reason: str
    normalized_payload: Any | None = None


def _normalize_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize_json_value(item) for key, item in sorted(value.items(), key=lambda entry: str(entry[0]))}
    if isinstance(value, list):
        return [_normalize_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_json_value(item) for item in value]
    if isinstance(value, set):
        return [_normalize_json_value(item) for item in sorted(value, key=lambda item: repr(item))]
    if isinstance(value, Path):
        return str(value)
    return value


def load_contract_fixture(path: str | Path = CONTRACT_FIXTURE_PATH) -> dict[str, Any] | None:
    fixture_path = Path(path)
    if not fixture_path.exists():
        return None
    try:
        raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    return raw


def hash_contract_fixture(path: str | Path = CONTRACT_FIXTURE_PATH) -> str | None:
    fixture = load_contract_fixture(path)
    if fixture is None:
        return None
    raw = json.dumps(_normalize_json_value(fixture), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _validation_failure(reason: str) -> ContractValidationResult:
    return ContractValidationResult(valid=False, reason=reason, normalized_payload=None)


def _validation_success(reason: str, payload: Any) -> ContractValidationResult:
    return ContractValidationResult(valid=True, reason=reason, normalized_payload=payload)


def _require_mapping(payload: Any, context: str) -> Mapping[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    return payload


def _require_list(payload: Any, context: str) -> list[Any] | None:
    if not isinstance(payload, list):
        return None
    return payload


def _coerce_non_negative_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return number


def _extract_order_id(payload: Mapping[str, Any]) -> str | None:
    for key in ("OrderId", "OrderID", "ID", "Id"):
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _validate_common_sendorder_fields(mapping: Mapping[str, Any], *, context: str) -> ContractValidationResult:
    required_keys = (
        "Password",
        "Symbol",
        "Exchange",
        "SecurityType",
        "Side",
        "CashMargin",
        "MarginTradeType",
        "DelivType",
        "AccountType",
        "Qty",
        "FrontOrderType",
        "Price",
        "ExpireDay",
    )
    missing = [key for key in required_keys if key not in mapping]
    if missing:
        return _validation_failure(f"{context}_missing:{','.join(missing)}")
    if not str(mapping.get("Password") or "").strip():
        return _validation_failure(f"{context}_password_missing")
    if not str(mapping.get("Symbol") or "").strip():
        return _validation_failure(f"{context}_symbol_missing")
    qty = _coerce_non_negative_number(mapping.get("Qty"))
    if qty is None or qty <= 0:
        return _validation_failure(f"{context}_qty_invalid")
    return _validation_success(f"{context}_ok", dict(mapping))


def validate_wallet_balance_response(payload: Any, *, required_key: str) -> ContractValidationResult:
    mapping = _require_mapping(payload, "wallet_balance")
    if mapping is None:
        return _validation_failure("wallet_balance_not_mapping")
    if required_key not in mapping:
        return _validation_failure(f"wallet_balance_missing:{required_key}")
    number = _coerce_non_negative_number(mapping.get(required_key))
    if number is None:
        return _validation_failure(f"wallet_balance_invalid:{required_key}")
    return _validation_success("wallet_balance_ok", {required_key: number})


def validate_orders_list_response(payload: Any) -> ContractValidationResult:
    orders = _require_list(payload, "orders")
    if orders is None:
        return _validation_failure("orders_response_not_list")

    normalized: list[dict[str, Any]] = []
    for index, order in enumerate(orders):
        if not isinstance(order, Mapping):
            return _validation_failure(f"orders_response_item_not_mapping:{index}")
        order_id = _extract_order_id(order)
        if not order_id:
            return _validation_failure(f"orders_response_missing_order_id:{index}")
        if order.get("State") is None:
            return _validation_failure(f"orders_response_missing_state:{index}")
        if order.get("OrderQty") is None:
            return _validation_failure(f"orders_response_missing_order_qty:{index}")
        if order.get("CumQty") is None:
            return _validation_failure(f"orders_response_missing_cum_qty:{index}")
        details = order.get("Details")
        if details is not None and not isinstance(details, list):
            return _validation_failure(f"orders_response_details_not_list:{index}")
        normalized.append(dict(order))
    return _validation_success("orders_response_ok", normalized)


def validate_order_detail_response(payload: Any) -> ContractValidationResult:
    response = validate_orders_list_response(payload)
    if not response.valid:
        return response
    normalized = response.normalized_payload or []
    if not normalized:
        return _validation_failure("order_detail_response_empty")
    return _validation_success("order_detail_response_ok", normalized)


def validate_market_order_request_payload(payload: Any) -> ContractValidationResult:
    mapping = _require_mapping(payload, "market_order_request")
    if mapping is None:
        return _validation_failure("market_order_request_not_mapping")
    common = _validate_common_sendorder_fields(mapping, context="market_order_request")
    if not common.valid:
        return common
    front_order_type = int(mapping.get("FrontOrderType") or 0)
    if front_order_type not in (10, 20):
        return _validation_failure("market_order_request_front_order_type_invalid")
    cash_margin = int(mapping.get("CashMargin") or 0)
    if cash_margin == 3:
        close_positions = mapping.get("ClosePositions")
        if not isinstance(close_positions, list) or not close_positions:
            return _validation_failure("market_order_request_close_positions_missing")
    return _validation_success("market_order_request_ok", dict(mapping))


def validate_stop_order_request_payload(payload: Any) -> ContractValidationResult:
    mapping = _require_mapping(payload, "stop_order_request")
    if mapping is None:
        return _validation_failure("stop_order_request_not_mapping")

    common = _validate_common_sendorder_fields(mapping, context="stop_order_request")
    if not common.valid:
        return common
    if int(mapping.get("FrontOrderType") or 0) != 30:
        return _validation_failure("stop_order_request_front_order_type_invalid")
    reverse_limit = mapping.get("ReverseLimitOrder")
    if not isinstance(reverse_limit, Mapping):
        return _validation_failure("stop_order_request_reverse_limit_missing")
    required_reverse_keys = (
        "TriggerSec",
        "TriggerPrice",
        "UnderOver",
        "AfterHitOrderType",
        "AfterHitPrice",
    )
    missing_reverse = [key for key in required_reverse_keys if key not in reverse_limit]
    if missing_reverse:
        return _validation_failure(f"stop_order_request_reverse_limit_missing:{','.join(missing_reverse)}")
    return _validation_success("stop_order_request_ok", dict(mapping))


def validate_cancel_order_request_payload(payload: Any) -> ContractValidationResult:
    mapping = _require_mapping(payload, "cancel_order_request")
    if mapping is None:
        return _validation_failure("cancel_order_request_not_mapping")
    if not str(mapping.get("OrderID") or "").strip():
        return _validation_failure("cancel_order_request_order_id_missing")
    if not str(mapping.get("Password") or "").strip():
        return _validation_failure("cancel_order_request_password_missing")
    return _validation_success("cancel_order_request_ok", dict(mapping))
