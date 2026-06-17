from __future__ import annotations

from dataclasses import asdict, dataclass
import difflib
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


CONTRACT_MANIFEST_PATH = Path(__file__).resolve().parents[1] / "contracts" / "kabucom_contract_manifest.json"
OFFICIAL_CONTRACT_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "contracts" / "kabucom_contract_fixture.json"
TEST_CONTRACT_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "contracts" / "kabucom_test_contract_fixture.json"
CONTRACT_FIXTURE_PATH = OFFICIAL_CONTRACT_FIXTURE_PATH
OFFICIAL_CONTRACT_FIXTURE_KIND = "OFFICIAL_OPENAPI"
TEST_CONTRACT_FIXTURE_KIND = "KABUCOM_TEST"
TEST_CONTRACT_PASSWORD_POLICY = "api_password_fallback_allowed"
SANITIZED_PASSWORD_PLACEHOLDER = "<redacted>"


@dataclass(frozen=True)
class ContractFixtureManifest:
    schema_version: int
    official_fixture_kind: str | None
    test_fixture_kind: str | None
    official_fixture_hash: str | None
    test_fixture_hash: str | None
    password_policy: str | None
    diff_document_hash: str | None
    api_spec_version: str | None
    api_spec_commit_sha: str | None
    api_spec_acquired_at: str | None
    generated_at: str | None = None


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


def _hash_text(text: str) -> str:
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def _build_fixture_diff_text(official_fixture: Mapping[str, Any], test_fixture: Mapping[str, Any]) -> str:
    official_lines = json.dumps(
        _normalize_json_value(official_fixture),
        sort_keys=True,
        ensure_ascii=False,
        indent=2,
    ).splitlines()
    test_lines = json.dumps(
        _normalize_json_value(test_fixture),
        sort_keys=True,
        ensure_ascii=False,
        indent=2,
    ).splitlines()
    return "\n".join(
        difflib.unified_diff(
            official_lines,
            test_lines,
            fromfile="official_contract_fixture",
            tofile="test_contract_fixture",
            lineterm="",
        )
    )


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
    if "Password" in mapping and not str(mapping.get("Password") or "").strip():
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
    if "Password" in mapping and not str(mapping.get("Password") or "").strip():
        return _validation_failure("cancel_order_request_password_missing")
    return _validation_success("cancel_order_request_ok", dict(mapping))


def _validate_fixture_password_policy(mapping: Mapping[str, Any], *, expected_kind: str, expected_password_policy: str | None = None) -> ContractValidationResult:
    fixture_kind = str(mapping.get("fixture_kind") or "").strip()
    if fixture_kind != expected_kind:
        return _validation_failure(f"contract_fixture_kind_mismatch:{fixture_kind or 'missing'}")

    password_policy = mapping.get("password_policy")
    if expected_password_policy is None:
        if password_policy is not None:
            return _validation_failure("contract_fixture_password_policy_forbidden")
    else:
        if str(password_policy or "").strip() != expected_password_policy:
            return _validation_failure("contract_fixture_password_policy_invalid")
    return _validation_success("contract_fixture_policy_ok", dict(mapping))


def _validate_test_fixture_provenance(mapping: Mapping[str, Any]) -> ContractValidationResult:
    required_keys = ("captured_from_kabucom_test", "captured_at", "sanitized_fields", "redaction_policy", "provenance_note")
    missing = [key for key in required_keys if key not in mapping]
    if missing:
        return _validation_failure(f"test_contract_fixture_provenance_missing:{','.join(missing)}")

    if not isinstance(mapping.get("captured_from_kabucom_test"), bool):
        return _validation_failure("test_contract_fixture_provenance_capture_flag_invalid")

    captured_at = str(mapping.get("captured_at") or "").strip()
    if not captured_at:
        return _validation_failure("test_contract_fixture_provenance_captured_at_missing")

    sanitized_fields = mapping.get("sanitized_fields")
    if not isinstance(sanitized_fields, list) or not sanitized_fields:
        return _validation_failure("test_contract_fixture_provenance_sanitized_fields_invalid")
    if any(not str(item or "").strip() for item in sanitized_fields):
        return _validation_failure("test_contract_fixture_provenance_sanitized_fields_invalid")

    redaction_policy = str(mapping.get("redaction_policy") or "").strip()
    if not redaction_policy:
        return _validation_failure("test_contract_fixture_provenance_redaction_policy_missing")

    provenance_note = str(mapping.get("provenance_note") or "").strip()
    if not provenance_note:
        return _validation_failure("test_contract_fixture_provenance_note_missing")

    return _validation_success("test_contract_fixture_provenance_ok", dict(mapping))


def validate_official_contract_fixture(fixture: Any) -> ContractValidationResult:
    mapping = _require_mapping(fixture, "official_contract_fixture")
    if mapping is None:
        return _validation_failure("official_contract_fixture_not_mapping")

    policy = _validate_fixture_password_policy(mapping, expected_kind=OFFICIAL_CONTRACT_FIXTURE_KIND, expected_password_policy=None)
    if not policy.valid:
        return policy

    requests = mapping.get("requests")
    if not isinstance(requests, Mapping):
        return _validation_failure("official_contract_fixture_missing_requests")
    responses = mapping.get("responses")
    if not isinstance(responses, Mapping):
        return _validation_failure("official_contract_fixture_missing_responses")

    request_validators = (
        ("market_order", validate_market_order_request_payload),
        ("stop_order", validate_stop_order_request_payload),
        ("cancel_order", validate_cancel_order_request_payload),
    )
    for request_name, validator in request_validators:
        request_payload = requests.get(request_name)
        request_validation = validator(request_payload)
        if not request_validation.valid:
            return _validation_failure(f"official_contract_fixture_request_invalid:{request_name}:{request_validation.reason}")
        if isinstance(request_payload, Mapping) and "Password" in request_payload:
            return _validation_failure(f"official_contract_fixture_password_field_present:{request_name}")

    wallet_cash = validate_wallet_balance_response(responses.get("wallet_cash"), required_key="StockAccountWallet")
    if not wallet_cash.valid:
        return _validation_failure(f"official_contract_fixture_wallet_cash_invalid:{wallet_cash.reason}")
    wallet_margin = validate_wallet_balance_response(responses.get("wallet_margin"), required_key="MarginAccountWallet")
    if not wallet_margin.valid:
        return _validation_failure(f"official_contract_fixture_wallet_margin_invalid:{wallet_margin.reason}")
    orders = validate_orders_list_response(responses.get("orders"))
    if not orders.valid:
        return _validation_failure(f"official_contract_fixture_orders_invalid:{orders.reason}")
    return _validation_success("official_contract_fixture_ok", dict(mapping))


def validate_test_contract_fixture(fixture: Any) -> ContractValidationResult:
    mapping = _require_mapping(fixture, "test_contract_fixture")
    if mapping is None:
        return _validation_failure("test_contract_fixture_not_mapping")

    policy = _validate_fixture_password_policy(mapping, expected_kind=TEST_CONTRACT_FIXTURE_KIND, expected_password_policy=TEST_CONTRACT_PASSWORD_POLICY)
    if not policy.valid:
        return policy

    provenance = _validate_test_fixture_provenance(mapping)
    if not provenance.valid:
        return provenance

    requests = mapping.get("requests")
    if not isinstance(requests, Mapping):
        return _validation_failure("test_contract_fixture_missing_requests")
    responses = mapping.get("responses")
    if not isinstance(responses, Mapping):
        return _validation_failure("test_contract_fixture_missing_responses")

    request_validators = (
        ("market_order", validate_market_order_request_payload),
        ("stop_order", validate_stop_order_request_payload),
        ("cancel_order", validate_cancel_order_request_payload),
    )
    for request_name, validator in request_validators:
        request_payload = requests.get(request_name)
        request_validation = validator(request_payload)
        if not request_validation.valid:
            return _validation_failure(f"test_contract_fixture_request_invalid:{request_name}:{request_validation.reason}")
        if not isinstance(request_payload, Mapping):
            return _validation_failure(f"test_contract_fixture_request_not_mapping:{request_name}")
        if request_payload.get("Password") != SANITIZED_PASSWORD_PLACEHOLDER:
            return _validation_failure(f"test_contract_fixture_password_not_sanitized:{request_name}")

    wallet_cash = validate_wallet_balance_response(responses.get("wallet_cash"), required_key="StockAccountWallet")
    if not wallet_cash.valid:
        return _validation_failure(f"test_contract_fixture_wallet_cash_invalid:{wallet_cash.reason}")
    wallet_margin = validate_wallet_balance_response(responses.get("wallet_margin"), required_key="MarginAccountWallet")
    if not wallet_margin.valid:
        return _validation_failure(f"test_contract_fixture_wallet_margin_invalid:{wallet_margin.reason}")
    orders = validate_orders_list_response(responses.get("orders"))
    if not orders.valid:
        return _validation_failure(f"test_contract_fixture_orders_invalid:{orders.reason}")
    return _validation_success("test_contract_fixture_ok", dict(mapping))


def validate_contract_fixture(fixture: Any) -> ContractValidationResult:
    mapping = _require_mapping(fixture, "contract_fixture")
    if mapping is None:
        return _validation_failure("contract_fixture_not_mapping")
    fixture_kind = str(mapping.get("fixture_kind") or "").strip()
    if fixture_kind == OFFICIAL_CONTRACT_FIXTURE_KIND:
        return validate_official_contract_fixture(mapping)
    if fixture_kind == TEST_CONTRACT_FIXTURE_KIND:
        return validate_test_contract_fixture(mapping)
    return _validation_failure("contract_fixture_kind_unknown")


def build_contract_fixture_manifest(
    *,
    official_path: str | Path = OFFICIAL_CONTRACT_FIXTURE_PATH,
    test_path: str | Path = TEST_CONTRACT_FIXTURE_PATH,
    generated_at: str | None = None,
) -> ContractFixtureManifest:
    official_fixture = load_contract_fixture(official_path)
    test_fixture = load_contract_fixture(test_path)
    official_hash = hash_contract_fixture(official_path)
    test_hash = hash_contract_fixture(test_path)

    api_spec_version = None
    api_spec_commit_sha = None
    api_spec_acquired_at = None
    password_policy = None
    official_kind = None
    test_kind = None
    diff_document_hash = None

    if isinstance(official_fixture, Mapping):
        official_kind = str(official_fixture.get("fixture_kind") or "").strip() or None
        api_spec_version = official_fixture.get("api_spec_version")
        api_spec_commit_sha = official_fixture.get("api_spec_commit_sha")
        api_spec_acquired_at = official_fixture.get("api_spec_acquired_at")
    if isinstance(test_fixture, Mapping):
        test_kind = str(test_fixture.get("fixture_kind") or "").strip() or None
        password_policy = str(test_fixture.get("password_policy") or "").strip() or None
        api_spec_version = api_spec_version or test_fixture.get("api_spec_version")
        api_spec_commit_sha = api_spec_commit_sha or test_fixture.get("api_spec_commit_sha")
        api_spec_acquired_at = api_spec_acquired_at or test_fixture.get("api_spec_acquired_at")

    if isinstance(official_fixture, Mapping) and isinstance(test_fixture, Mapping):
        diff_document_hash = _hash_text(_build_fixture_diff_text(official_fixture, test_fixture))

    return ContractFixtureManifest(
        schema_version=1,
        official_fixture_kind=official_kind,
        test_fixture_kind=test_kind,
        official_fixture_hash=official_hash,
        test_fixture_hash=test_hash,
        password_policy=password_policy,
        diff_document_hash=diff_document_hash,
        api_spec_version=None if api_spec_version is None else str(api_spec_version),
        api_spec_commit_sha=None if api_spec_commit_sha is None else str(api_spec_commit_sha),
        api_spec_acquired_at=None if api_spec_acquired_at is None else str(api_spec_acquired_at),
        generated_at=generated_at,
    )


def manifest_to_canonical_payload(manifest: ContractFixtureManifest | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(manifest, ContractFixtureManifest):
        payload = asdict(manifest)
    else:
        payload = dict(manifest)
    payload.pop("generated_at", None)
    return _normalize_json_value(payload)


def compute_contract_fixture_manifest_hash(
    manifest: ContractFixtureManifest | Mapping[str, Any] | None = None,
) -> str:
    if manifest is None:
        manifest = build_contract_fixture_manifest()
    payload = manifest_to_canonical_payload(manifest)
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def write_contract_fixture_manifest(path: str | Path, manifest: ContractFixtureManifest | None = None) -> Path:
    manifest = build_contract_fixture_manifest() if manifest is None else manifest
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(_normalize_json_value(asdict(manifest)), sort_keys=True, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target


def load_contract_fixture_manifest(path: str | Path) -> ContractFixtureManifest:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return ContractFixtureManifest(
        schema_version=int(raw["schema_version"]),
        official_fixture_kind=raw.get("official_fixture_kind"),
        test_fixture_kind=raw.get("test_fixture_kind"),
        official_fixture_hash=raw.get("official_fixture_hash"),
        test_fixture_hash=raw.get("test_fixture_hash"),
        password_policy=raw.get("password_policy"),
        diff_document_hash=raw.get("diff_document_hash"),
        api_spec_version=raw.get("api_spec_version"),
        api_spec_commit_sha=raw.get("api_spec_commit_sha"),
        api_spec_acquired_at=raw.get("api_spec_acquired_at"),
        generated_at=raw.get("generated_at"),
    )
