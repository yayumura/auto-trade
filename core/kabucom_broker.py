import os
import requests
import json
import pandas as pd
from decimal import Decimal
from datetime import datetime
import time
import threading
from dataclasses import dataclass
from enum import Enum
from email.utils import parsedate_to_datetime
from core.broker import BaseBroker
from core.config import (
    DEBUG_MODE,
    HISTORY_FILE,
    EXECUTION_LOG_FILE,
    EXECUTION_AUDIT_LOG_FILE,
    JST,
    KABUCOM_API_PASSWORD,
    KABUCOM_ORDER_PASSWORD,
    KABUCOM_PORT_LIVE,
    KABUCOM_PORT_TEST,
    TRADE_MODE,
)
from core.log_setup import send_discord_notify
from core.file_io import atomic_write_json, append_csv_rows, append_jsonl
from core.kabucom_contracts import (
    validate_cancel_order_request_payload,
    validate_market_order_request_payload,
    validate_order_detail_response,
    validate_orders_list_response,
    validate_stop_order_request_payload,
    validate_wallet_balance_response,
)
from core.order_journal import append_order_journal
from core.portfolio_state import load_portfolio_positions, write_portfolio_state
from core.kabucom_order_state import (
    CancelResult,
    CancelStatus,
    CancelTerminalStatus,
    ExecutionFill,
    ExecutionWaitResult,
    OrderProcessState,
    OrderTerminalReason,
    OrderSubmissionResult,
    SubmissionResult,
    SubmissionStatus,
    StockOrderAction,
    resolve_stock_order_action_context,
    classify_submission_response,
    classify_cancel_response,
    parse_kabucom_order,
    resolve_stock_order_action,
    resolve_cancel_terminal_status,
)
from core.live_order_gate import get_live_order_gate_status
from core.live_order_gate import get_kabucom_live_financial_write_gate_status
from core.kabucom_quote import parse_board_quote


class BrokerEnvironment(Enum):
    LIVE = "live"
    TEST = "test"


class BrokerOperationClass(Enum):
    READ_ONLY = "read_only"
    NEW_EXPOSURE = "new_exposure"
    REDUCE_EXPOSURE = "reduce_exposure"
    CANCEL_MANAGED_ORDER = "cancel_managed_order"
    REGISTRY_MUTATION = "registry_mutation"


class RequestBudgetBucket(Enum):
    AUTH = "auth"
    WALLET = "wallet"
    ORDERS = "orders"
    MARKET_DATA = "market_data"
    REGISTRY = "registry"
    OTHER = "other"


REQUEST_BUDGET_LIMITS = {
    RequestBudgetBucket.AUTH: 120,
    RequestBudgetBucket.WALLET: 1200,
    RequestBudgetBucket.ORDERS: 1200,
    RequestBudgetBucket.MARKET_DATA: 3600,
    RequestBudgetBucket.REGISTRY: 3000,
    RequestBudgetBucket.OTHER: 1200,
}


@dataclass(frozen=True)
class BrokerEndpointConfig:
    environment: BrokerEnvironment
    port: int
    base_url: str | None = None

    @classmethod
    def live(cls, base_url: str | None = None) -> "BrokerEndpointConfig":
        return cls(BrokerEnvironment.LIVE, KABUCOM_PORT_LIVE, base_url)

    @classmethod
    def test(cls, base_url: str | None = None) -> "BrokerEndpointConfig":
        return cls(BrokerEnvironment.TEST, KABUCOM_PORT_TEST, base_url)

    @classmethod
    def from_trade_mode(cls, trade_mode: str | None = None) -> "BrokerEndpointConfig":
        mode = TRADE_MODE if trade_mode is None else str(trade_mode).strip().upper()
        if mode == "KABUCOM_LIVE":
            return cls.live()
        if mode == "KABUCOM_TEST":
            return cls.test()
        raise ValueError(f"Unsupported kabucom trade mode: {mode!r}")

    def validate(self) -> "BrokerEndpointConfig":
        if not isinstance(self.environment, BrokerEnvironment):
            raise ValueError(f"Unsupported broker environment: {self.environment!r}")
        expected_port = KABUCOM_PORT_LIVE if self.environment == BrokerEnvironment.LIVE else KABUCOM_PORT_TEST
        if int(self.port) != expected_port:
            raise ValueError(
                f"Broker endpoint port mismatch for {self.environment.value}: "
                f"expected {expected_port}, got {self.port}"
            )
        expected_base_url = f"http://localhost:{expected_port}/kabusapi"
        if self.base_url is None:
            return BrokerEndpointConfig(self.environment, expected_port, expected_base_url)
        normalized_base_url = str(self.base_url).rstrip("/")
        if normalized_base_url != expected_base_url:
            raise ValueError(
                f"Broker endpoint base_url mismatch for {self.environment.value}: "
                f"expected {expected_base_url!r}, got {self.base_url!r}"
            )
        return BrokerEndpointConfig(self.environment, expected_port, normalized_base_url)

class KabucomBroker(BaseBroker):
    """
    auカブコム証券（kabuステーションAPI）と通信するBrokerクラス。
    endpoint_config で実行環境と port を明示し、環境不一致を constructor で拒否する。
    """
    
    def __init__(self, endpoint_config: BrokerEndpointConfig):
        if not isinstance(endpoint_config, BrokerEndpointConfig):
            raise TypeError("endpoint_config must be a BrokerEndpointConfig")
        self.endpoint_config = endpoint_config.validate()
        self._environment = self.endpoint_config.environment
        self.port = int(self.endpoint_config.port)
        self.base_url = self.endpoint_config.base_url or f"http://localhost:{self.port}/kabusapi"
        self.password = KABUCOM_API_PASSWORD
        self.order_password = KABUCOM_ORDER_PASSWORD or (self.password if self.environment == BrokerEnvironment.TEST else None)
        self.token = None
        # [Professional Audit] マルチスレッド環境での認証競合を防ぐためのロック
        self._auth_lock = threading.Lock()
        # [Professional Audit] Sessionを永続化し、HTTP Keep-Aliveを有効にして遅延を最小化する
        self.session = requests.Session()
        # [Professional Audit] API予算管理 (1時間5000回を上限の目安とする)
        self.request_count = 0
        self.last_reset_time = time.time()
        self.request_budget_counts = {bucket: 0 for bucket in RequestBudgetBucket}
        self.request_budget_last_reset_time = self.last_reset_time
        
        env_name = "【本番API】" if self.is_production else "【検証API】"
        if not self.password:
            print(f"⚠️ {env_name} パスワード(KABUCOM_API_PASSWORD)が.envに設定されていません。")
        else:
            self._authenticate()
        if self.environment == BrokerEnvironment.LIVE and not self.order_password:
            print("⚠️ LIVE では注文用パスワード(KABUCOM_ORDER_PASSWORD)の明示設定が必要です。")

    @classmethod
    def from_trade_mode(cls, trade_mode: str | None = None) -> "KabucomBroker":
        return cls(BrokerEndpointConfig.from_trade_mode(trade_mode))

    @property
    def environment(self) -> BrokerEnvironment:
        env = getattr(self, "_environment", None)
        if isinstance(env, BrokerEnvironment):
            return env
        legacy = getattr(self, "_legacy_is_production", None)
        if legacy is None:
            return BrokerEnvironment.TEST
        return BrokerEnvironment.LIVE if bool(legacy) else BrokerEnvironment.TEST

    @property
    def is_production(self) -> bool:
        return self.environment == BrokerEnvironment.LIVE

    @is_production.setter
    def is_production(self, value: bool):
        if hasattr(self, "endpoint_config"):
            raise AttributeError("is_production is derived from endpoint_config and cannot be reassigned")
        self._legacy_is_production = bool(value)
        self._environment = BrokerEnvironment.LIVE if bool(value) else BrokerEnvironment.TEST

    def _authenticate(self):
        """ kabuステーションAPIからトークンを取得する """
        with self._auth_lock:
            url = f"{self.base_url}/token"
            headers = {'Content-Type': 'application/json'}
            data = {'APIPassword': self.password}
            
            try:
                self._record_request_budget(RequestBudgetBucket.AUTH)
                res = self.session.post(url, headers=headers, json=data, timeout=10)
                if res.status_code == 200:
                    self.token = res.json().get('Token')
                    print(f"✅ auカブコムAPI 認証成功 (Port:{self.port})")
                else:
                    print(f"⚠️ 認証失敗: {res.status_code} {res.text}")
            except Exception as e:
                env_name = "本番" if self.is_production else "検証用"
                print(f"⚠️ kabuステーション({env_name})に接続できません。アプリが起動し、APIが有効化されているか確認してください。({e})")

    def _classify_request_bucket(self, method: str, endpoint: str) -> RequestBudgetBucket:
        endpoint_text = str(endpoint or "").lower()
        method_text = str(method or "").upper()
        if endpoint_text.startswith("token") or endpoint_text.endswith("/token"):
            return RequestBudgetBucket.AUTH
        if endpoint_text.startswith("wallet/"):
            return RequestBudgetBucket.WALLET
        if endpoint_text.startswith("orders") or endpoint_text.startswith("sendorder") or endpoint_text.startswith("cancelorder"):
            return RequestBudgetBucket.ORDERS
        if endpoint_text.startswith("board/") or endpoint_text.startswith("symbol/"):
            return RequestBudgetBucket.MARKET_DATA
        if endpoint_text.startswith("register") or endpoint_text.startswith("unregister"):
            return RequestBudgetBucket.REGISTRY
        if method_text == "POST" and endpoint_text.endswith("/token"):
            return RequestBudgetBucket.AUTH
        return RequestBudgetBucket.OTHER

    def _resolve_buy_exchange(self) -> int | None:
        raw_exchange = os.environ.get("KABUCOM_ORDER_EXCHANGE")
        if raw_exchange is None or not str(raw_exchange).strip():
            return None
        try:
            return int(raw_exchange)
        except (TypeError, ValueError):
            return None

    def _resolve_account_type(self) -> int | None:
        raw_account_type = os.environ.get("KABUCOM_ACCOUNT_TYPE")
        if raw_account_type is None or not str(raw_account_type).strip():
            return None
        try:
            return int(raw_account_type)
        except (TypeError, ValueError):
            return None

    def _resolve_operation_class_for_action(self, action: StockOrderAction) -> BrokerOperationClass:
        if action in {StockOrderAction.MARGIN_NEW_LONG, StockOrderAction.MARGIN_NEW_SHORT}:
            return BrokerOperationClass.NEW_EXPOSURE
        if action in {StockOrderAction.MARGIN_CLOSE_LONG, StockOrderAction.MARGIN_CLOSE_SHORT}:
            return BrokerOperationClass.REDUCE_EXPOSURE
        raise ValueError(f"Unsupported stock order action: {action!r}")

    def _record_request_budget(self, bucket: RequestBudgetBucket):
        now = time.time()
        request_budget_last_reset_time = getattr(self, "request_budget_last_reset_time", None)
        if request_budget_last_reset_time is None:
            request_budget_last_reset_time = now
            self.request_budget_last_reset_time = request_budget_last_reset_time
        request_budget_counts = getattr(self, "request_budget_counts", None)
        if not isinstance(request_budget_counts, dict):
            request_budget_counts = {bucket_key: 0 for bucket_key in RequestBudgetBucket}
            self.request_budget_counts = request_budget_counts
        if now - request_budget_last_reset_time > 3600:
            request_budget_counts = {bucket_key: 0 for bucket_key in RequestBudgetBucket}
            self.request_budget_counts = request_budget_counts
            self.request_budget_last_reset_time = now
        request_budget_counts[bucket] = int(request_budget_counts.get(bucket, 0)) + 1
        self.request_count = int(getattr(self, "request_count", 0)) + 1
        if self.request_count > 4800:
            print(f"⚠️ API Request Budget Alert: {self.request_count} requests/hr. Throttling...")
            time.sleep(0.5)
        bucket_limit = REQUEST_BUDGET_LIMITS[bucket]
        if request_budget_counts[bucket] > bucket_limit:
            print(
                f"⚠️ API Request Budget Alert [{bucket.value}]: "
                f"{request_budget_counts[bucket]} requests/hr (limit {bucket_limit}). Throttling..."
            )
            time.sleep(0.5)

    def _resolve_retry_after_seconds(self, response) -> float | None:
        headers = getattr(response, "headers", None)
        if not headers or not hasattr(headers, "get"):
            return None
        retry_after = headers.get("Retry-After")
        if retry_after is None:
            return None
        text = str(retry_after).strip()
        if not text:
            return None
        try:
            seconds = float(text)
            if seconds >= 0:
                return seconds
        except (TypeError, ValueError):
            pass
        try:
            retry_at = parsedate_to_datetime(text)
        except Exception:
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=JST)
        else:
            retry_at = retry_at.astimezone(JST)
        return max(0.0, (retry_at - datetime.now(JST)).total_seconds())

    def _get_headers(self, force_refresh=False):
        if not self.token or force_refresh:
            self._authenticate()
        return {
            'Content-Type': 'application/json',
            'X-API-KEY': self.token
        }

    def _api_request(self, method, endpoint, **kwargs):
        """
        [Professional Audit] APIリクエストの共通ラッパー。
        認証切れ(401)時の自動リトライ機能を備え、DRY原則に基づき通信処理を一元化する。
        """
        url = f"{self.base_url}/{endpoint}" if not endpoint.startswith("http") else endpoint
        method = method.upper()
        bucket = self._classify_request_bucket(method, endpoint)
        allow_transient_retry = method == "GET"
        # [Professional Audit] API予算管理と自動スロットリング
        retry_attempts = [False, True] if allow_transient_retry else [False]
        for retry in retry_attempts:
            headers = self._get_headers(force_refresh=retry)
            # [Professional Audit] GET のみ指数バックオフを許可する。POST/PUT の無条件再送は重複注文を招くため禁止。
            delays = [0, 1, 2, 4] if allow_transient_retry else [0]
            for delay in delays:
                if delay > 0: time.sleep(delay)
                try:
                    self._record_request_budget(bucket)
                    res = self.session.request(method, url, headers=headers, **kwargs)
                    if res.status_code == 200:
                        return res
                    elif res.status_code == 401 and not retry:
                        if allow_transient_retry:
                            break # 内側のループを抜けて、認証をリフレッシュしてリトライ
                        return res
                    elif res.status_code == 429:
                        if allow_transient_retry:
                            retry_after = self._resolve_retry_after_seconds(res)
                            if retry_after is None:
                                retry_after = delay * 2 if delay > 0 else 1.0
                            print(f"⚠️ API Rate Limited (429). Retrying in {float(retry_after):.1f}s...")
                            time.sleep(max(0.0, float(retry_after)))
                            continue
                        return res
                    elif res.status_code in [500, 502, 503, 504]:
                        if allow_transient_retry:
                            print(f"⚠️ API Server Error ({res.status_code}). Retrying in {delay*2 if delay>0 else 1}s...")
                            continue
                        return res
                    else:
                        return res
                except Exception as e:
                    if not allow_transient_retry:
                        print(f"❌ API Request Fatal Error: {method} {url} | Error: {e}")
                        return None
                    if delay == delays[-1]:
                        # [Professional Audit] ログ出力時に機密情報をマスクする
                        masked_headers = {k: ('********' if k.upper() == 'X-API-KEY' else v) for k, v in headers.items()}
                        print(f"❌ API Request Fatal Error: {method} {url} | Headers: {masked_headers} | Error: {e}")
                        raise e
                    continue
        return None

    def get_server_time(self) -> datetime:
        """ 取引所（証券会社側）の現在時刻を取得する """
        from core.config import JST
        fallback = datetime.now(JST)  # H-6: JST aware datetimeを常に返すよう修正
        if not self.token: return fallback
        try:
            # [Professional Audit] 共通ラッパーを使用して認証・リトライの恩恵を受ける
            res = self._api_request("GET", "wallet/cash", timeout=5)
            if res and res.status_code == 200:
                date_header = None
                if hasattr(res, "headers"):
                    date_header = res.headers.get("Date")
                if date_header:
                    try:
                        parsed_date = parsedate_to_datetime(date_header)
                        if parsed_date.tzinfo is None:
                            parsed_date = parsed_date.replace(tzinfo=JST)
                        return parsed_date.astimezone(JST)
                    except Exception:
                        pass
            return fallback
        except Exception:
            return fallback

    def get_active_orders(self) -> dict | None:
        """ 現在執行中（未約定・待機中等）の注文一覧を取得する """
        if not self.token: return None
        try:
            # [Professional Audit] 共通ラッパーを使用して認証・リトライの恩恵を受ける
            res = self._api_request("GET", "orders", timeout=10)
            if res is None:
                return None
            if res.status_code == 200:
                orders = res.json()
                validation = validate_orders_list_response(orders)
                if not validation.valid:
                    print(f"⚠️ 注文一覧レスポンス契約違反: {validation.reason}")
                    return None
                if not isinstance(orders, list):
                    return None
                active = []
                has_unknown = False
                unresolved_order_ids = []
                for order in validation.normalized_payload or []:
                    if not isinstance(order, dict):
                        continue
                    parsed = parse_kabucom_order(order)
                    if parsed.process_state == OrderProcessState.ACTIVE:
                        enriched = dict(order)
                        enriched["__parsed_process_state__"] = parsed.process_state.value
                        enriched["__parsed_terminal_reason__"] = None if parsed.terminal_reason is None else parsed.terminal_reason.value
                        enriched["__parsed_cumulative_qty__"] = parsed.cumulative_qty
                        enriched["__parsed_order_qty__"] = parsed.order_qty
                        enriched["__parsed_has_partial_fill__"] = parsed.has_partial_fill
                        active.append(enriched)
                    elif parsed.process_state == OrderProcessState.UNKNOWN:
                        has_unknown = True
                        unresolved_order_ids.append(parsed.order_id or "")
                return {
                    "orders": active,
                    "has_unknown": has_unknown,
                    "unresolved_order_ids": [order_id for order_id in unresolved_order_ids if order_id],
                }
            return None
        except Exception as e:
            print(f"⚠️ 注文一覧取得エラー: {e}")
            return None

    def get_account_balance(self) -> dict:
        """ 
        [Professional Audit] モードに応じた残高取得。
        - 本番モード: APIから本物の資産情報を取得。
        - 検証モード: APIの固定値を無視し、ローカルファイル(account.json)で仮想資金を管理。
        """
        if not self.token: return {"cash": 0}
        
        # 検証モード(TEST)の場合はローカルファイルを優先
        if self.environment == BrokerEnvironment.TEST:
            from core.config import ACCOUNT_FILE, INITIAL_CASH
            from core.file_io import safe_read_json, atomic_write_json
            account = safe_read_json(ACCOUNT_FILE)
            # state 不在時のみ INITIAL_CASH で初期化する。0以下は異常値として保持する。
            if not account:
                print(f"💰 [Account] 仮想資金を初期化します: {INITIAL_CASH:,.0f}円")
                account = {"cash": float(INITIAL_CASH)}
                atomic_write_json(ACCOUNT_FILE, account)
            elif account.get('cash') is None:
                print(f"💰 [Account] cash 欄が欠落しているため初期化します: {INITIAL_CASH:,.0f}円")
                account = {"cash": float(INITIAL_CASH)}
                atomic_write_json(ACCOUNT_FILE, account)
            return account

        # 本番モード(LIVE)の場合はAPIから取得
        cash_res = self._api_request("GET", "wallet/cash", timeout=10)
        margin_res = self._api_request("GET", "wallet/margin", timeout=10)
        cash_ok = bool(cash_res and cash_res.status_code == 200)
        margin_ok = bool(margin_res and margin_res.status_code == 200)

        stock_buying_power = 0.0
        margin_buying_power = 0.0
        if cash_ok:
            try:
                cash_data = cash_res.json()
                stock_buying_power = float(cash_data.get("StockAccountWallet") or 0.0)
            except Exception:
                cash_ok = False
        if margin_ok:
            try:
                margin_data = margin_res.json()
                margin_buying_power = float(margin_data.get("MarginAccountWallet") or 0.0)
            except Exception:
                margin_ok = False

        if not cash_ok or not margin_ok:
            print(
                "⚠️ 口座余力取得エラー: "
                f"cash={'ok' if cash_ok else (cash_res.text if cash_res else 'No Response')}, "
                f"margin={'ok' if margin_ok else (margin_res.text if margin_res else 'No Response')}"
            )

        cash_validation = validate_wallet_balance_response(
            cash_res.json() if cash_ok and cash_res else None,
            required_key="StockAccountWallet",
        )
        margin_validation = validate_wallet_balance_response(
            margin_res.json() if margin_ok and margin_res else None,
            required_key="MarginAccountWallet",
        )
        if not cash_validation.valid or not margin_validation.valid:
            print(
                "⚠️ 口座余力レスポンス契約違反: "
                f"cash={cash_validation.reason if not cash_validation.valid else 'ok'}, "
                f"margin={margin_validation.reason if not margin_validation.valid else 'ok'}"
            )
            cash_ok = cash_ok and cash_validation.valid
            margin_ok = margin_ok and margin_validation.valid
            if cash_validation.valid and cash_validation.normalized_payload is not None:
                stock_buying_power = float(cash_validation.normalized_payload.get("StockAccountWallet") or stock_buying_power)
            if margin_validation.valid and margin_validation.normalized_payload is not None:
                margin_buying_power = float(margin_validation.normalized_payload.get("MarginAccountWallet") or margin_buying_power)

        return {
            "cash": 0.0,
            "stock_buying_power": stock_buying_power if cash_ok else 0.0,
            "margin_buying_power": margin_buying_power if margin_ok else 0.0,
            "unrealized_pnl": 0.0,
            "gross_position_notional": 0.0,
            "net_position_notional": 0.0,
            "broker_position_count": 0,
            "wallet_snapshot_incomplete": not (cash_ok and margin_ok),
            "wallet_cash_ok": cash_ok,
            "wallet_margin_ok": margin_ok,
        }

    def _authorize_operation(self, operation_class: BrokerOperationClass) -> tuple[bool, str]:
        """Mutating endpoint を centralized に認可する。"""
        if not hasattr(self, "endpoint_config"):
            return True, "legacy_test_double"

        if operation_class == BrokerOperationClass.READ_ONLY:
            return True, "read_only"

        if self.environment == BrokerEnvironment.TEST:
            if TRADE_MODE != "KABUCOM_TEST":
                return False, "test_endpoint_requires_kabucom_test_mode"
            return True, "test_endpoint_allowed"

        if self.environment != BrokerEnvironment.LIVE:
            return False, "unknown_broker_environment"

        if TRADE_MODE != "KABUCOM_LIVE":
            return False, "live_endpoint_write_blocked_by_trade_mode"

        if operation_class == BrokerOperationClass.NEW_EXPOSURE:
            if DEBUG_MODE:
                return False, "debug_mode_enabled"
            if not self.order_password:
                return False, "order_password_missing"
            gate_status = get_kabucom_live_financial_write_gate_status(
                base_gate_status=get_live_order_gate_status(),
            )
            if not gate_status.allowed:
                return False, f"live_new_order_disabled:{gate_status.reason}"
            return True, "live_new_exposure_allowed"

        if operation_class in {
            BrokerOperationClass.REDUCE_EXPOSURE,
            BrokerOperationClass.CANCEL_MANAGED_ORDER,
            BrokerOperationClass.REGISTRY_MUTATION,
        }:
            return True, "live_reduction_or_registry_allowed"

        return False, "unsupported_operation_class"

    @staticmethod
    def _normalize_submission_rejection_reason(reason: str) -> str:
        if reason == "order_password_missing":
            return "missing_order_password"
        return reason

    def _infer_request_sent(self, submission: SubmissionResult) -> bool:
        preflight_reasons = {
            "no_token",
            "missing_close_route",
            "close_positions_unavailable",
            "missing_buy_exchange",
            "missing_account_type",
            "missing_order_password",
            "order_password_missing",
            "live_endpoint_write_blocked_by_trade_mode",
            "debug_mode_enabled",
            "test_endpoint_requires_kabucom_test_mode",
        }
        if submission.status == SubmissionStatus.UNKNOWN:
            return submission.rejection_reason not in preflight_reasons
        if submission.rejection_reason in preflight_reasons and submission.http_status is None:
            return False
        return True

    def _wrap_submission_result(
        self,
        submission: SubmissionResult,
        *,
        side: str,
        cash_margin: int,
        request_sent: bool,
        limit_price: float | None = None,
        trigger_price: float | None = None,
        confirmed: bool = False,
        confirmation_reason: str | None = None,
    ) -> OrderSubmissionResult:
        return OrderSubmissionResult.from_submission(
            submission,
            action=resolve_stock_order_action(side, cash_margin, allow_short=False),
            request_sent=request_sent,
            side=side,
            limit_price=limit_price,
            trigger_price=trigger_price,
            confirmed=confirmed,
            confirmation_reason=confirmation_reason,
        )

    def _extract_execution_fills(self, details: dict | None, parsed) -> tuple[ExecutionFill, ...]:
        if not details:
            return ()
        raw_details = details.get("Details")
        if not isinstance(raw_details, list):
            raw_details = []
        fills: list[ExecutionFill] = []
        for detail in raw_details:
            if not isinstance(detail, dict):
                continue
            if int(detail.get("RecType", 0) or 0) != 8:
                continue
            execution_id = str(detail.get("ExecutionID") or "").strip()
            if not execution_id:
                continue
            qty_value = detail.get("Qty")
            if qty_value is None:
                qty_value = detail.get("CumQty")
            try:
                qty = int(qty_value or 0)
            except (TypeError, ValueError):
                qty = 0
            try:
                price = float(detail.get("Price") or 0.0)
            except (TypeError, ValueError):
                price = 0.0
            executed_at = detail.get("ExecutionDateTime") or detail.get("ExecTime")
            if isinstance(executed_at, str):
                try:
                    executed_at = datetime.fromisoformat(executed_at.replace("Z", "+00:00"))
                except Exception:
                    executed_at = None
            elif not isinstance(executed_at, datetime):
                executed_at = None
            fills.append(
                ExecutionFill(
                    execution_id=execution_id,
                    qty=max(0, qty),
                    price=price,
                    executed_at=executed_at,
                    commission=None,
                    commission_tax=None,
                )
            )
        if fills:
            return tuple(fills)
        if parsed.cumulative_qty > 0:
            fallback_price = parsed.average_fill_price
            if fallback_price is None and details is not None:
                try:
                    fallback_price = float(details.get("Price") or 0.0)
                except (TypeError, ValueError):
                    fallback_price = 0.0
            return (
                ExecutionFill(
                    execution_id=parsed.execution_ids[0] if parsed.execution_ids else "",
                    qty=parsed.cumulative_qty,
                    price=float(fallback_price or 0.0),
                    executed_at=None,
                    commission=None,
                    commission_tax=None,
                ),
            )
        return ()

    def _build_wait_result(
        self,
        details: dict | None,
        *,
        order_id: str,
        unresolved: bool = False,
        unresolved_reason: str | None = None,
        submission_status: SubmissionStatus | None = None,
    ) -> ExecutionWaitResult:
        enriched = self._enrich_order_details_with_parse(details, unresolved=unresolved, unresolved_reason=unresolved_reason)
        parsed = parse_kabucom_order(enriched)
        fills = self._extract_execution_fills(enriched, parsed)
        process_state = parsed.process_state
        terminal_reason = parsed.terminal_reason
        if unresolved:
            process_state = OrderProcessState.UNKNOWN
            terminal_reason = None
        return ExecutionWaitResult(
            process_state=process_state,
            terminal_reason=terminal_reason,
            fills=fills,
            cumulative_qty=parsed.cumulative_qty,
            remaining_qty=parsed.unfilled_qty,
            unresolved=bool(unresolved),
            unresolved_reason=unresolved_reason,
            order_id=order_id,
            submission_status=submission_status,
            raw_details=enriched,
        )

    def _normalize_close_positions_payload(self, close_positions: list | None) -> tuple[tuple[str, int], ...] | None:
        if close_positions is None:
            return None
        if not isinstance(close_positions, list):
            return None
        normalized: list[tuple[str, int]] = []
        for item in close_positions:
            if not isinstance(item, dict):
                return None
            hold_id = str(item.get("HoldID") or item.get("hold_id") or "").strip()
            qty_value = item.get("Qty")
            try:
                qty = int(qty_value or 0)
            except (TypeError, ValueError):
                return None
            if not hold_id or qty <= 0:
                return None
            normalized.append((hold_id, qty))
        return tuple(normalized)

    def _confirm_stop_order_submission(
        self,
        *,
        order_id: str,
        expected_qty: int,
        expected_trigger_price: float,
        expected_close_positions: list | None,
        side: str,
        exchange: int | None,
        margin_trade_type: int | None,
    ) -> tuple[bool, str | None, dict | None]:
        details = self.get_order_details(order_id)
        expected_close_positions_payload = self._normalize_close_positions_payload(expected_close_positions)
        expected_cash_margin = 3 if str(side) == "1" else 2
        expected_deliv_type = 0 if expected_cash_margin == 2 else 2

        def _close_positions_summary(close_positions_payload: list | None) -> list[dict[str, int | str]] | None:
            normalized = self._normalize_close_positions_payload(close_positions_payload)
            if normalized is None:
                return None
            return [{"HoldID": hold_id, "Qty": qty} for hold_id, qty in normalized]

        def _reverse_limit_summary(details_payload: dict | None) -> dict[str, object] | None:
            if not isinstance(details_payload, dict):
                return None
            reverse_limit = details_payload.get("ReverseLimitOrder")
            if not isinstance(reverse_limit, dict):
                return None
            summary: dict[str, object] = {}
            for key in ("TriggerSec", "TriggerPrice", "UnderOver", "AfterHitOrderType", "AfterHitPrice"):
                if key in reverse_limit:
                    summary[key] = reverse_limit.get(key)
            return summary or None

        def _limit_summary(summary: dict[str, object]) -> dict[str, object]:
            serialized = json.dumps(summary, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            if len(serialized) <= 4096:
                return summary
            return {
                "response_shape_version": summary.get("response_shape_version"),
                "order_id": summary.get("order_id"),
                "details_present": summary.get("details_present"),
                "process_state": summary.get("process_state"),
                "terminal_reason": summary.get("terminal_reason"),
                "order_qty": summary.get("order_qty"),
                "cumulative_qty": summary.get("cumulative_qty"),
                "remaining_qty": summary.get("remaining_qty"),
                "side": summary.get("side"),
                "cash_margin": summary.get("cash_margin"),
                "deliv_type": summary.get("deliv_type"),
                "exchange": summary.get("exchange"),
                "margin_trade_type": summary.get("margin_trade_type"),
                "trigger_price": summary.get("trigger_price"),
                "expected_qty": summary.get("expected_qty"),
                "expected_trigger_price": summary.get("expected_trigger_price"),
                "close_positions_count": summary.get("close_positions_count"),
                "expected_close_positions_count": summary.get("expected_close_positions_count"),
                "close_positions_match": summary.get("close_positions_match"),
                "mismatch_reason": summary.get("mismatch_reason"),
                "summary_truncated": True,
                "summary_size_chars": len(serialized),
            }

        def _build_confirmation_details(mismatch_reason: str, *, details_payload: dict | None = None, parsed_order=None) -> dict[str, object]:
            close_positions_summary = _close_positions_summary(None if details_payload is None else details_payload.get("ClosePositions"))
            reverse_limit_summary = _reverse_limit_summary(details_payload)
            summary = {
                "response_shape_version": 1,
                "order_id": order_id,
                "details_present": bool(details_payload),
                "process_state": None if parsed_order is None else parsed_order.process_state.value,
                "terminal_reason": None if parsed_order is None or parsed_order.terminal_reason is None else parsed_order.terminal_reason.value,
                "order_qty": None if parsed_order is None else parsed_order.order_qty,
                "cumulative_qty": None if parsed_order is None else parsed_order.cumulative_qty,
                "remaining_qty": None if parsed_order is None else parsed_order.unfilled_qty,
                "side": side,
                "cash_margin": details_payload.get("CashMargin") if isinstance(details_payload, dict) and "CashMargin" in details_payload else expected_cash_margin,
                "deliv_type": details_payload.get("DelivType") if isinstance(details_payload, dict) and "DelivType" in details_payload else expected_deliv_type,
                "exchange": details_payload.get("Exchange") if isinstance(details_payload, dict) and "Exchange" in details_payload else exchange,
                "margin_trade_type": details_payload.get("MarginTradeType") if isinstance(details_payload, dict) and "MarginTradeType" in details_payload else margin_trade_type,
                "trigger_price": None if reverse_limit_summary is None else reverse_limit_summary.get("TriggerPrice"),
                "expected_qty": int(expected_qty),
                "expected_trigger_price": float(expected_trigger_price),
                "close_positions": close_positions_summary,
                "close_positions_count": 0 if close_positions_summary is None else len(close_positions_summary),
                "expected_close_positions": None if expected_close_positions_payload is None else [
                    {"HoldID": hold_id, "Qty": qty}
                    for hold_id, qty in expected_close_positions_payload
                ],
                "expected_close_positions_count": 0 if expected_close_positions_payload is None else len(expected_close_positions_payload),
                "close_positions_match": None if expected_close_positions_payload is None else self._normalize_close_positions_payload(None if details_payload is None else details_payload.get("ClosePositions")) == expected_close_positions_payload,
                "reverse_limit": reverse_limit_summary,
                "detail_count": None if parsed_order is None else parsed_order.detail_count,
                "raw_state": None if parsed_order is None else parsed_order.raw_state,
                "raw_order_state": None if parsed_order is None else parsed_order.raw_order_state,
                "latest_detail_rec_type": None if parsed_order is None else parsed_order.latest_detail_rec_type,
                "has_partial_fill": None if parsed_order is None else parsed_order.has_partial_fill,
                "is_consistent": None if parsed_order is None else parsed_order.is_consistent,
                "mismatch_reason": mismatch_reason,
            }
            return _limit_summary(summary)

        if not isinstance(details, dict) or not details:
            return False, "stop_order_not_found", _build_confirmation_details("stop_order_not_found")

        parsed = parse_kabucom_order(details)
        if parsed.process_state == OrderProcessState.UNKNOWN:
            return False, "stop_order_state_unknown", _build_confirmation_details("stop_order_state_unknown", details_payload=details, parsed_order=parsed)
        if parsed.process_state != OrderProcessState.ACTIVE:
            mismatch_reason = f"stop_order_state_{parsed.process_state.value}"
            return False, mismatch_reason, _build_confirmation_details(mismatch_reason, details_payload=details, parsed_order=parsed)
        if parsed.order_qty != int(expected_qty):
            return False, "stop_order_qty_mismatch", _build_confirmation_details("stop_order_qty_mismatch", details_payload=details, parsed_order=parsed)
        if parsed.cumulative_qty != 0:
            return False, "stop_order_already_filled", _build_confirmation_details("stop_order_already_filled", details_payload=details, parsed_order=parsed)

        actual_side = str(details.get("Side") or "").strip()
        if actual_side and actual_side != str(side):
            return False, "stop_order_side_mismatch", _build_confirmation_details("stop_order_side_mismatch", details_payload=details, parsed_order=parsed)

        actual_cash_margin = None
        if "CashMargin" in details:
            try:
                actual_cash_margin = int(details.get("CashMargin") or 0)
            except (TypeError, ValueError):
                actual_cash_margin = None
        if actual_cash_margin is not None and actual_cash_margin != expected_cash_margin:
            return False, "stop_order_cash_margin_mismatch", _build_confirmation_details("stop_order_cash_margin_mismatch", details_payload=details, parsed_order=parsed)

        actual_deliv_type = None
        if "DelivType" in details:
            try:
                actual_deliv_type = int(details.get("DelivType") or 0)
            except (TypeError, ValueError):
                actual_deliv_type = None
        if actual_deliv_type is not None and actual_deliv_type != expected_deliv_type:
            return False, "stop_order_deliv_type_mismatch", _build_confirmation_details("stop_order_deliv_type_mismatch", details_payload=details, parsed_order=parsed)

        actual_exchange = None
        if "Exchange" in details:
            try:
                actual_exchange = int(details.get("Exchange") or 0)
            except (TypeError, ValueError):
                actual_exchange = None
        if exchange is not None and actual_exchange is not None and actual_exchange != int(exchange):
            return False, "stop_order_exchange_mismatch", _build_confirmation_details("stop_order_exchange_mismatch", details_payload=details, parsed_order=parsed)

        actual_margin_trade_type = None
        if "MarginTradeType" in details:
            try:
                actual_margin_trade_type = int(details.get("MarginTradeType") or 0)
            except (TypeError, ValueError):
                actual_margin_trade_type = None
        if margin_trade_type is not None and actual_margin_trade_type is not None and actual_margin_trade_type != int(margin_trade_type):
            return False, "stop_order_margin_trade_type_mismatch", _build_confirmation_details("stop_order_margin_trade_type_mismatch", details_payload=details, parsed_order=parsed)

        reverse_limit = details.get("ReverseLimitOrder")
        if not isinstance(reverse_limit, dict):
            return False, "stop_order_reverse_limit_missing", _build_confirmation_details("stop_order_reverse_limit_missing", details_payload=details, parsed_order=parsed)
        actual_trigger_price = reverse_limit.get("TriggerPrice")
        if actual_trigger_price is None:
            return False, "stop_order_trigger_price_missing", _build_confirmation_details("stop_order_trigger_price_missing", details_payload=details, parsed_order=parsed)
        try:
            if Decimal(str(actual_trigger_price)) != Decimal(str(expected_trigger_price)):
                return False, "stop_order_trigger_price_mismatch", _build_confirmation_details("stop_order_trigger_price_mismatch", details_payload=details, parsed_order=parsed)
        except Exception:
            return False, "stop_order_trigger_price_mismatch", _build_confirmation_details("stop_order_trigger_price_mismatch", details_payload=details, parsed_order=parsed)

        actual_under_over = None
        if "UnderOver" in reverse_limit:
            try:
                actual_under_over = int(reverse_limit.get("UnderOver") or 0)
            except (TypeError, ValueError):
                actual_under_over = None
        expected_under_over = 1 if str(side) == "1" else 2
        if actual_under_over is not None and actual_under_over != expected_under_over:
            return False, "stop_order_under_over_mismatch", _build_confirmation_details("stop_order_under_over_mismatch", details_payload=details, parsed_order=parsed)

        actual_after_hit_order_type = None
        if "AfterHitOrderType" in reverse_limit:
            try:
                actual_after_hit_order_type = int(reverse_limit.get("AfterHitOrderType") or 0)
            except (TypeError, ValueError):
                actual_after_hit_order_type = None
        if actual_after_hit_order_type is not None and actual_after_hit_order_type != 1:
            return False, "stop_order_after_hit_order_type_mismatch", _build_confirmation_details("stop_order_after_hit_order_type_mismatch", details_payload=details, parsed_order=parsed)

        if expected_close_positions_payload is not None:
            actual_close_positions_payload = self._normalize_close_positions_payload(details.get("ClosePositions"))
            if actual_close_positions_payload != expected_close_positions_payload:
                return False, "stop_order_close_positions_mismatch", _build_confirmation_details("stop_order_close_positions_mismatch", details_payload=details, parsed_order=parsed)

        return True, None, None

    def get_positions(self) -> list:
        """ 
        現在保有中の現物ポジション一覧を取得し、シミュレーションBOTと同じ辞書リスト形式に変換する。
        さらに、既存のファイルから highest_price 等の継続データを復元する。
        """
        if not self.token: 
            raise ConnectionError("認証トークンがないためポジションを取得できません")
        
        # 1. APIから最新の信用ポジションを取得 (デイトレード信用対応)
        url = f"{self.base_url}/positions?product=2" # 2: 信用

        res = self._api_request("GET", f"positions?product=2", timeout=10)
        if res and res.status_code == 200:
            api_positions = res.json()
        else:
            raise Exception(f"API Error: {res.status_code if res else 'No Response'}")

        # 2. ローカルデータマージ
        from core.config import PORTFOLIO_FILE
        local_data_by_execution_id: dict[str, dict] = {}
        local_data_by_code: dict[str, list[dict]] = {}
        managed_execution_ids = set()
        for row_data in load_portfolio_positions(PORTFOLIO_FILE):
            code_key = str(row_data.get("code") or "").strip()
            if not code_key:
                continue
            local_data_by_code.setdefault(code_key, []).append(row_data)
            execution_id = str(row_data.get("execution_id") or "").strip()
            if execution_id:
                managed_execution_ids.add(execution_id)
                local_data_by_execution_id[execution_id] = row_data
            execution_ids = row_data.get("execution_ids") or []
            if isinstance(execution_ids, str):
                execution_ids = [execution_ids]
            for extra_execution_id in execution_ids:
                execution_text = str(extra_execution_id or "").strip()
                if execution_text:
                    managed_execution_ids.add(execution_text)
                    local_data_by_execution_id[execution_text] = row_data

        final_positions = []
        for p in api_positions:
            if p.get('LeavesQty', 0) == 0: continue
            code_sym = str(p['Symbol'])
            current_price = float(p['CurrentPrice']) if p.get('CurrentPrice') is not None else 0.0
            leaves_qty = int(p.get('LeavesQty', 0) or 0)
            raw_hold_qty = p.get('HoldQty')
            hold_qty = None
            available_qty = None
            if raw_hold_qty is not None:
                try:
                    hold_qty = max(0, int(raw_hold_qty or 0))
                except (TypeError, ValueError):
                    hold_qty = None
                if hold_qty is not None:
                    available_qty = max(0, leaves_qty - hold_qty)
            execution_id = str(p.get('ExecutionID') or "").strip() or None
            
            hist = None
            if execution_id and execution_id in local_data_by_execution_id:
                hist = local_data_by_execution_id[execution_id]
            if hist is not None:
                # --- [Phase 10] 株式分割・併合ロジック（削除済み） ---
                highest_price = float(hist.get('highest_price', current_price))
                highest_price = max(highest_price, current_price)
                buy_time = hist.get('buy_time', "Real API Position")
                partial_sold = hist.get('partial_sold', False)
            else:
                highest_price = current_price
                buy_time = "Real API Position"
                partial_sold = False

            if execution_id and execution_id in managed_execution_ids:
                ownership = "MANAGED_BY_BOT"
                ownership_reason = "matched_execution_id"
            elif local_data_by_code.get(code_sym):
                ownership = "AMBIGUOUS"
                ownership_reason = "symbol_match_only"
            else:
                ownership = "UNMANAGED"
                ownership_reason = "no_local_match"

            final_positions.append({
                "code": code_sym, 
                "name": p.get('SymbolName', ''), 
                "shares": leaves_qty,
                "leaves_qty": leaves_qty,
                "hold_qty": hold_qty,
                "available_qty": available_qty,
                "buy_price": float(p['Price']) if p.get('Price') is not None else 0.0, 
                "current_price": current_price,
                "highest_price": round(highest_price, 1),
                "buy_time": buy_time,
                "partial_sold": partial_sold,
                "hold_id": p.get('ExecutionID'), # 信用返済用に保持
                "execution_id": p.get('ExecutionID'),
                "exchange": p.get('Exchange'),
                "margin_trade_type": p.get('MarginTradeType'),
                "ownership": ownership,
                "ownership_reason": ownership_reason,
            })
        return final_positions

    def _build_close_positions_for_symbol(
        self,
        code: str,
        requested_qty: int,
        managed_execution_ids: set[str] | None = None,
    ) -> dict | None:
        """信用返済用に、同一銘柄・同一Exchange・同一MarginTradeTypeの建玉へ数量を安全に割り当てる。"""
        if requested_qty <= 0:
            return {"close_positions": [], "exchange": None, "margin_trade_type": None}
        normalized_execution_ids = {
            str(item or "").strip()
            for item in (managed_execution_ids or set())
            if str(item or "").strip()
        }
        try:
            positions = self.get_positions()
        except Exception as exc:
            print(f"⚠️ 返済建玉の再取得に失敗しました: {exc}")
            return None

        matches = [
            p
            for p in positions
            if p.get("code") == str(code)
            and p.get("hold_id")
            and str(p.get("ownership") or "").upper() == "MANAGED_BY_BOT"
            and (
                not normalized_execution_ids
                or str(p.get("execution_id") or "").strip() in normalized_execution_ids
            )
        ]
        if not matches:
            return None

        candidate_exchange = None
        candidate_margin_trade_type = None
        for position in matches:
            exchange = position.get("exchange")
            margin_trade_type = position.get("margin_trade_type")
            hold_qty = position.get("hold_qty")
            available_qty = position.get("available_qty")
            if exchange is None or margin_trade_type is None or hold_qty is None or available_qty is None:
                return None
            if candidate_exchange is None:
                candidate_exchange = int(exchange)
                candidate_margin_trade_type = int(margin_trade_type)
            elif candidate_exchange != int(exchange) or candidate_margin_trade_type != int(margin_trade_type):
                print(
                    f"⚠️ 返済対象建玉のExchange/MarginTradeTypeが混在しています: "
                    f"{code} exchange={candidate_exchange}/{exchange} margin={candidate_margin_trade_type}/{margin_trade_type}"
                )
                return None

        remaining_qty = int(requested_qty)
        close_positions = []
        for position in sorted(
            matches,
            key=lambda item: (
                str(item.get("buy_time", "")),
                str(item.get("execution_id", "")),
                str(item.get("hold_id", "")),
            ),
        ):
            available_qty = position.get("available_qty")
            if available_qty is None:
                print(f"⚠️ 返済対象建玉の数量が不明です: {code} hold_id={position.get('hold_id')}")
                return None
            available_qty = max(0, int(available_qty))
            if available_qty <= 0:
                continue

            take_qty = min(remaining_qty, available_qty)
            if take_qty > 0:
                close_positions.append({
                    "HoldID": position["hold_id"],
                    "Qty": take_qty,
                })
                remaining_qty -= take_qty
            if remaining_qty <= 0:
                break

        if remaining_qty > 0:
            print(f"⚠️ 返済可能数量が不足しています: {code} requested={requested_qty} available={requested_qty - remaining_qty}")
            return None
        return {
            "close_positions": close_positions,
            "exchange": candidate_exchange,
            "margin_trade_type": candidate_margin_trade_type,
        }

    def _resolve_hold_route(self, hold_id: str) -> dict | None:
        """hold_id に紐づく建玉の Exchange / MarginTradeType を特定する。"""
        if not hold_id:
            return None
        try:
            positions = self.get_positions()
        except Exception as exc:
            print(f"⚠️ 返済建玉の再取得に失敗しました: {exc}")
            return None

        matches = [p for p in positions if p.get("hold_id") == hold_id]
        if not matches:
            return None

        exchange = matches[0].get("exchange")
        margin_trade_type = matches[0].get("margin_trade_type")
        if exchange is None or margin_trade_type is None:
            return None

        for position in matches[1:]:
            if position.get("exchange") != exchange or position.get("margin_trade_type") != margin_trade_type:
                return None

        return {
            "exchange": int(exchange),
            "margin_trade_type": int(margin_trade_type),
        }

    def _submit_market_order(
        self,
        code: str,
        shares: int,
        side: str,
        price: float = 0,
        close_positions: list = None,
        exchange: int | None = None,
        margin_trade_type: int | None = None,
        operation_class: BrokerOperationClass | None = None,
    ) -> SubmissionResult:
        """
        現物・信用の成行・指値注文を発注し、SubmissionResult を返す。
        side: "1" (売), "2" (買)
        close_positions: [{"HoldID": "...", "Qty": 100}, ...] (信用返済時)
        """
        if not self.token:
            return SubmissionResult(
                status=SubmissionStatus.UNKNOWN,
                intent_id=f"market-{time.time_ns()}",
                broker_order_id=None,
                symbol=str(code),
                side=side,
                qty=int(shares),
                price=float(price) if price is not None else None,
                http_status=None,
                rejection_reason="no_token",
            )
        intent_id = f"market-{time.time_ns()}"
        
        cash_margin = 2 if side == "2" else 3
        # 買付余力(2) または 信用売(3)
        if margin_trade_type is None:
            margin_trade_type = 3 if side == "2" else None
        if exchange is None:
            if side == "2":
                exchange = self._resolve_buy_exchange()
                if exchange is None:
                    print(f"⚠️ 新規買い注文のExchangeが未設定のため、発注を中止します: {code}")
                    submission = SubmissionResult(
                        status=SubmissionStatus.REJECTED,
                        intent_id=intent_id,
                        broker_order_id=None,
                        symbol=str(code),
                        side=side,
                        qty=int(shares),
                        price=float(price) if price is not None else None,
                        http_status=None,
                        rejection_reason="missing_buy_exchange",
                    )
                    append_order_journal({
                        "event": "REJECTED",
                        "intent_id": intent_id,
                        "kind": "market",
                        "symbol": str(code),
                        "side": side,
                        "qty": int(shares),
                        "price": float(price) if price is not None else 0.0,
                        "http_status": None,
                        "result": None,
                        "rejection_reason": "missing_buy_exchange",
                        "exchange": None,
                        "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
                        "is_production": bool(self.is_production),
                    })
                    return self._wrap_submission_result(
                        submission,
                        side=side,
                        cash_margin=cash_margin,
                        request_sent=False,
                        limit_price=float(price) if price is not None and price > 0 else None,
                    )
            else:
                exchange = None
        if side == "1" and (exchange is None or margin_trade_type is None):
            print(f"⚠️ 返済注文のExchange/MarginTradeTypeが未確定のため発注を中止します: {code}")
            submission = SubmissionResult(
                status=SubmissionStatus.REJECTED,
                intent_id=intent_id,
                broker_order_id=None,
                symbol=str(code),
                side=side,
                qty=int(shares),
                price=float(price) if price is not None else None,
                http_status=None,
                rejection_reason="missing_close_route",
            )
            append_order_journal({
                "event": "REJECTED",
                "intent_id": intent_id,
                "kind": "market",
                "symbol": str(code),
                "side": side,
                "qty": int(shares),
                "price": float(price) if price > 0 else 0.0,
                "http_status": None,
                "result": None,
                "rejection_reason": submission.rejection_reason,
                "exchange": None if exchange is None else int(exchange),
                "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
                "is_production": bool(self.is_production),
            })
            return submission
        if hasattr(self, "endpoint_config"):
            if self.environment == BrokerEnvironment.LIVE and TRADE_MODE != "KABUCOM_LIVE":
                submission = SubmissionResult(
                    status=SubmissionStatus.REJECTED,
                    intent_id=intent_id,
                    broker_order_id=None,
                    symbol=str(code),
                    side=side,
                    qty=int(shares),
                    price=float(price) if price is not None else None,
                    http_status=None,
                    rejection_reason="live_endpoint_write_blocked_by_trade_mode",
                )
                append_order_journal({
                    "event": "REJECTED",
                    "intent_id": intent_id,
                    "kind": "market",
                    "symbol": str(code),
                    "side": side,
                    "qty": int(shares),
                    "price": float(price) if price is not None and price > 0 else 0.0,
                    "rejection_reason": submission.rejection_reason,
                    "is_production": bool(self.is_production),
                })
                return submission
            if self.environment == BrokerEnvironment.TEST and TRADE_MODE != "KABUCOM_TEST":
                submission = SubmissionResult(
                    status=SubmissionStatus.REJECTED,
                    intent_id=intent_id,
                    broker_order_id=None,
                    symbol=str(code),
                    side=side,
                    qty=int(shares),
                    price=float(price) if price is not None else None,
                    http_status=None,
                    rejection_reason="test_endpoint_requires_kabucom_test_mode",
                )
                append_order_journal({
                    "event": "REJECTED",
                    "intent_id": intent_id,
                    "kind": "market",
                    "symbol": str(code),
                    "side": side,
                    "qty": int(shares),
                    "price": float(price) if price is not None and price > 0 else 0.0,
                    "rejection_reason": submission.rejection_reason,
                    "is_production": bool(self.is_production),
                })
                return submission
        operation_class = operation_class or (
            BrokerOperationClass.NEW_EXPOSURE if side == "2" else BrokerOperationClass.REDUCE_EXPOSURE
        )
        allowed, reason = self._authorize_operation(operation_class)
        if not allowed:
            normalized_reason = self._normalize_submission_rejection_reason(reason)
            print(f"🛑 {code} の注文をコード側で停止しました。reason={reason}")
            submission = SubmissionResult(
                status=SubmissionStatus.REJECTED,
                intent_id=intent_id,
                broker_order_id=None,
                symbol=str(code),
                side=side,
                qty=int(shares),
                price=float(price) if price is not None else None,
                http_status=None,
                rejection_reason=normalized_reason,
            )
            append_order_journal({
                "event": "REJECTED",
                "intent_id": intent_id,
                "kind": "market",
                "symbol": str(code),
                "side": side,
                "qty": int(shares),
                "price": float(price) if price > 0 else 0.0,
                "http_status": None,
                "result": None,
                "rejection_reason": normalized_reason,
                "is_production": bool(self.is_production),
            })
            return submission
        if not self.order_password:
            submission = SubmissionResult(
                status=SubmissionStatus.REJECTED,
                intent_id=intent_id,
                broker_order_id=None,
                symbol=str(code),
                side=side,
                qty=int(shares),
                price=float(price) if price is not None else None,
                http_status=None,
                rejection_reason="missing_order_password",
            )
            append_order_journal({
                "event": "REJECTED",
                "intent_id": intent_id,
                "kind": "market",
                "symbol": str(code),
                "side": side,
                "qty": int(shares),
                "price": float(price) if price is not None and price > 0 else 0.0,
                "rejection_reason": submission.rejection_reason,
                "is_production": bool(self.is_production),
            })
            return submission
        account_type = self._resolve_account_type()
        if account_type is None:
            print(f"⚠️ 注文のAccountTypeが未設定のため、発注を中止します: {code}")
            submission = SubmissionResult(
                status=SubmissionStatus.REJECTED,
                intent_id=intent_id,
                broker_order_id=None,
                symbol=str(code),
                side=side,
                qty=int(shares),
                price=float(price) if price is not None else None,
                http_status=None,
                rejection_reason="missing_account_type",
            )
            append_order_journal({
                "event": "REJECTED",
                "intent_id": intent_id,
                "kind": "market",
                "symbol": str(code),
                "side": side,
                "qty": int(shares),
                "price": float(price) if price > 0 else 0.0,
                "http_status": None,
                "result": None,
                "rejection_reason": submission.rejection_reason,
                "exchange": None if exchange is None else int(exchange),
                "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
                "is_production": bool(self.is_production),
            })
            return self._wrap_submission_result(
                submission,
                side=side,
                cash_margin=cash_margin,
                request_sent=False,
                limit_price=float(price) if price is not None and price > 0 else None,
            )
        if margin_trade_type is None:
            margin_trade_type = 3

        front_order_type = 20 if price > 0 else 10  # 20:指値 10:成行
        normalized_price = 0.0
        if price > 0:
            from core.logic import normalize_tick_size
            normalized_price = normalize_tick_size(price, is_buy=(side == "2"))

        append_order_journal({
            "event": "PLANNED",
            "intent_id": intent_id,
            "kind": "market",
            "symbol": str(code),
            "side": side,
            "qty": int(shares),
            "price": float(normalized_price) if front_order_type == 20 else 0.0,
            "cash_margin": cash_margin,
            "front_order_type": front_order_type,
            "exchange": None if exchange is None else int(exchange),
            "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
            "is_production": bool(self.is_production),
        })

        data = {
            "Password": self.order_password,
            "Symbol": code,
            "Exchange": int(exchange),
            "SecurityType": 1,  # 1: 株式
            "Side": side,       # 1: 売, 2: 買
            "CashMargin": cash_margin,
            "MarginTradeType": margin_trade_type,
            "DelivType": 0 if cash_margin == 2 else 2,
            "AccountType": account_type,
            "Qty": shares,
            "FrontOrderType": front_order_type,
            "Price": float(normalized_price) if front_order_type == 20 else 0,
            "ExpireDay": 0
        }

        # 信用返済(CashMargin=3)の場合は ClosePositions を付与
        if cash_margin == 3:
            if close_positions is not None:
                if not isinstance(close_positions, list) or not close_positions:
                    print(f"⚠️ 信用返済の返済建玉リストが不正なため、発注を中止します: {code}")
                    submission = SubmissionResult(
                        status=SubmissionStatus.REJECTED,
                        intent_id=intent_id,
                        broker_order_id=None,
                        symbol=str(code),
                        side=side,
                        qty=int(shares),
                        price=float(normalized_price) if front_order_type == 20 else 0.0,
                        http_status=None,
                        rejection_reason="close_positions_unavailable",
                    )
                    append_order_journal({
                        "event": "REJECTED",
                        "intent_id": intent_id,
                        "kind": "market",
                        "symbol": str(code),
                        "side": side,
                        "qty": int(shares),
                        "price": float(normalized_price) if front_order_type == 20 else 0.0,
                        "http_status": None,
                        "result": None,
                        "rejection_reason": submission.rejection_reason,
                        "exchange": None if exchange is None else int(exchange),
                        "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
                        "is_production": bool(self.is_production),
                    })
                    return submission
                data["ClosePositions"] = close_positions
            else:
                print(f"⚠️ 信用返済の返済建玉IDが取得できないため、発注を中止します: {code}")
                submission = SubmissionResult(
                    status=SubmissionStatus.REJECTED,
                    intent_id=intent_id,
                    broker_order_id=None,
                    symbol=str(code),
                    side=side,
                    qty=int(shares),
                    price=float(normalized_price) if front_order_type == 20 else 0.0,
                    http_status=None,
                    rejection_reason="close_positions_unavailable",
                )
                append_order_journal({
                    "event": "REJECTED",
                    "intent_id": intent_id,
                    "kind": "market",
                    "symbol": str(code),
                    "side": side,
                    "qty": int(shares),
                    "price": float(normalized_price) if front_order_type == 20 else 0.0,
                    "http_status": None,
                    "result": None,
                    "rejection_reason": submission.rejection_reason,
                    "exchange": None if exchange is None else int(exchange),
                    "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
                    "is_production": bool(self.is_production),
                })
                return submission

        payload_validation = validate_market_order_request_payload(data)
        if not payload_validation.valid:
            print(f"🛑 market order payload をコード側で停止しました。reason={payload_validation.reason}")
            submission = SubmissionResult(
                status=SubmissionStatus.REJECTED,
                intent_id=intent_id,
                broker_order_id=None,
                symbol=str(code),
                side=side,
                qty=int(shares),
                price=float(normalized_price) if front_order_type == 20 else 0.0,
                http_status=None,
                rejection_reason=payload_validation.reason,
            )
            append_order_journal({
                "event": "REJECTED",
                "intent_id": intent_id,
                "kind": "market",
                "symbol": str(code),
                "side": side,
                "qty": int(shares),
                "price": float(normalized_price) if front_order_type == 20 else 0.0,
                "http_status": None,
                "result": None,
                "rejection_reason": payload_validation.reason,
                "exchange": None if exchange is None else int(exchange),
                "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
                "is_production": bool(self.is_production),
            })
            return submission

        res = self._api_request("POST", "sendorder", json=data, timeout=10)
        submission = classify_submission_response(
            intent_id=intent_id,
            symbol=str(code),
            side=side,
            qty=shares,
            price=float(normalized_price) if front_order_type == 20 else 0.0,
            response=res,
        )
        if submission.status == SubmissionStatus.ACCEPTED:
            order_id = submission.broker_order_id
            env = "【本番】" if self.is_production else "【検証API】"
            act = "買い" if side == "2" else "売り"
            otype = "指値" if price > 0 else "成行"
            append_order_journal({
                "event": "ACCEPTED",
                "intent_id": intent_id,
                "kind": "market",
                "symbol": str(code),
                "side": side,
                "qty": int(shares),
                "price": float(normalized_price) if front_order_type == 20 else 0.0,
                "order_id": order_id,
                "http_status": submission.http_status,
                "result": submission.result_code,
                "exchange": None if exchange is None else int(exchange),
                "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
                "is_production": bool(self.is_production),
            })
            print(f"✅ {env} 注文受付完了 (ID: {order_id}) - {code} {shares}株 {act} ({otype})")
            return submission
        if submission.status == SubmissionStatus.REJECTED:
            append_order_journal({
                "event": "REJECTED",
                "intent_id": intent_id,
                "kind": "market",
                "symbol": str(code),
                "side": side,
                "qty": int(shares),
                "price": float(normalized_price) if front_order_type == 20 else 0.0,
                "http_status": submission.http_status,
                "result": submission.result_code,
                "rejection_reason": submission.rejection_reason,
                "exchange": None if exchange is None else int(exchange),
                "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
                "is_production": bool(self.is_production),
            })
            print(f"⚠️ 注文拒否: {submission.rejection_reason}")
            return submission
        append_order_journal({
            "event": "UNKNOWN",
            "intent_id": intent_id,
            "kind": "market",
            "symbol": str(code),
            "side": side,
            "qty": int(shares),
            "price": float(normalized_price) if front_order_type == 20 else 0.0,
            "http_status": submission.http_status,
            "response_text": submission.response_text,
            "rejection_reason": submission.rejection_reason,
            "exchange": None if exchange is None else int(exchange),
            "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
            "is_production": bool(self.is_production),
        })
        return submission

    def execute_market_order(self, code: str, shares: int, action: StockOrderAction, price: float = 0, close_positions: list = None, exchange: int | None = None, margin_trade_type: int | None = None) -> OrderSubmissionResult:
        context = resolve_stock_order_action_context(action, allow_short=True)
        side = context.side
        cash_margin = context.cash_margin
        operation_class = self._resolve_operation_class_for_action(action)
        if action in (StockOrderAction.MARGIN_NEW_SHORT, StockOrderAction.MARGIN_CLOSE_SHORT):
            intent_id = f"market-{time.time_ns()}"
            submission = SubmissionResult(
                status=SubmissionStatus.REJECTED,
                intent_id=intent_id,
                broker_order_id=None,
                symbol=str(code),
                side=side,
                qty=int(shares),
                price=float(price) if price is not None else None,
                http_status=None,
                rejection_reason="unsupported_stock_order_action",
            )
            append_order_journal({
                "event": "REJECTED",
                "intent_id": intent_id,
                "kind": "market",
                "symbol": str(code),
                "side": side,
                "qty": int(shares),
                "price": float(price) if price is not None and price > 0 else 0.0,
                "rejection_reason": submission.rejection_reason,
                "order_action": action.value,
                "cash_margin": cash_margin,
                "exchange": None if exchange is None else int(exchange),
                "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
                "is_production": bool(self.is_production),
            })
            print(f"🛑 {code} の注文をコード側で停止しました。reason=unsupported_stock_order_action action={action.value}")
            return OrderSubmissionResult.from_submission(
                submission,
                action=action,
                request_sent=False,
                side=side,
                limit_price=float(price) if price is not None and price > 0 else None,
            )
        submission = self._submit_market_order(
            code,
            shares,
            side,
            price=price,
            close_positions=close_positions,
            exchange=exchange,
            margin_trade_type=margin_trade_type,
            operation_class=operation_class,
        )
        request_sent = self._infer_request_sent(submission)
        limit_price = getattr(submission, "limit_price", None)
        if limit_price is None:
            limit_price = getattr(submission, "price", None)
        if limit_price is not None and float(limit_price) <= 0:
            limit_price = None
        return self._wrap_submission_result(
            submission,
            side=side,
            cash_margin=cash_margin,
            request_sent=request_sent,
            limit_price=limit_price,
        )

    def cancel_order(self, order_id: str) -> CancelResult:
        """ API経由で注文を取り消す (オートキャンセル機構用) """
        if not self.token:
            return CancelResult(
                status=CancelStatus.UNKNOWN,
                order_id=order_id,
                parsed_order=None,
                cumulative_qty=0,
                remaining_qty=0,
                request_sent=False,
                rejection_reason="no_token",
            )
        allowed, reason = self._authorize_operation(BrokerOperationClass.CANCEL_MANAGED_ORDER)
        if not allowed:
            print(f"🛑 cancelorder をコード側で停止しました。reason={reason}")
            append_order_journal({
                "event": "REJECTED",
                "order_id": order_id,
                "rejection_reason": reason,
                "is_production": bool(self.is_production),
            })
            return CancelResult(
                status=CancelStatus.REJECTED,
                order_id=order_id,
                parsed_order=None,
                cumulative_qty=0,
                remaining_qty=0,
                request_sent=False,
                rejection_reason=reason,
            )
        if not self.order_password:
            append_order_journal({
                "event": "REJECTED",
                "order_id": order_id,
                "rejection_reason": "missing_order_password",
                "is_production": bool(self.is_production),
            })
            return CancelResult(
                status=CancelStatus.REJECTED,
                order_id=order_id,
                parsed_order=None,
                cumulative_qty=0,
                remaining_qty=0,
                request_sent=False,
                rejection_reason="missing_order_password",
            )
        cancel_data = {"OrderID": order_id, "Password": self.order_password}
        cancel_validation = validate_cancel_order_request_payload(cancel_data)
        if not cancel_validation.valid:
            print(f"🛑 cancelorder payload をコード側で停止しました。reason={cancel_validation.reason}")
            append_order_journal({
                "event": "REJECTED",
                "order_id": order_id,
                "rejection_reason": cancel_validation.reason,
                "is_production": bool(self.is_production),
            })
            return CancelResult(
                status=CancelStatus.REJECTED,
                order_id=order_id,
                parsed_order=None,
                cumulative_qty=0,
                remaining_qty=0,
                request_sent=False,
                rejection_reason=cancel_validation.reason,
            )
        append_order_journal({
            "event": "CANCEL_REQUESTED",
            "order_id": order_id,
            "is_production": bool(self.is_production),
        })
        
        res = self._api_request("PUT", "cancelorder", json=cancel_data, timeout=10)
        submission = classify_cancel_response(
            intent_id=f"cancel-{time.time_ns()}",
            response=res,
        )
        if submission.status == SubmissionStatus.ACCEPTED:
            confirmed = self._confirm_terminal_order_state(order_id, timeout_sec=5)
            parsed_order = None
            cumulative_qty = 0
            remaining_qty = 0
            terminal_status: CancelTerminalStatus | None = None
            terminal_reason = None
            journal_event = "UNKNOWN"
            if confirmed:
                parsed = parse_kabucom_order(confirmed)
                parsed_order = parsed
                cumulative_qty = parsed.cumulative_qty
                remaining_qty = parsed.unfilled_qty
                terminal_reason = parsed.terminal_reason
                terminal_status = resolve_cancel_terminal_status(parsed)
                if terminal_status == CancelTerminalStatus.CANCELLED:
                    journal_event = "CANCELLED"
                elif terminal_status == CancelTerminalStatus.FILLED_BEFORE_CANCEL:
                    journal_event = "FILLED_BEFORE_CANCEL"
                elif terminal_status == CancelTerminalStatus.EXPIRED:
                    journal_event = "EXPIRED"
                elif terminal_status == CancelTerminalStatus.REJECTED:
                    journal_event = "REJECTED"
                else:
                    journal_event = "UNKNOWN"
            else:
                terminal_status = CancelTerminalStatus.UNKNOWN
            append_order_journal({
                "event": journal_event,
                "order_id": order_id,
                "http_status": submission.http_status,
                "result": submission.result_code,
                "is_production": bool(self.is_production),
                "confirmed": bool(confirmed),
                "terminal_reason": None if terminal_reason is None else terminal_reason.value,
                "terminal_status": None if terminal_status is None else terminal_status.value,
            })
            if terminal_status is None:
                terminal_status = CancelTerminalStatus.UNKNOWN
            if terminal_status == CancelTerminalStatus.CANCELLED:
                rejection_reason = None
            elif terminal_status == CancelTerminalStatus.UNKNOWN and not confirmed:
                rejection_reason = "cancel_not_confirmed"
            else:
                rejection_reason = terminal_status.value
            return CancelResult(
                status=CancelStatus.ACCEPTED if confirmed else CancelStatus.UNKNOWN,
                order_id=order_id,
                parsed_order=parsed_order,
                cumulative_qty=cumulative_qty,
                remaining_qty=remaining_qty,
                request_sent=True,
                terminal_status=terminal_status,
                terminal_reason=terminal_reason,
                http_status=submission.http_status,
                result_code=submission.result_code,
                rejection_reason=rejection_reason,
                response_text=submission.response_text,
                confirmed=bool(confirmed),
            )
        if submission.status == SubmissionStatus.REJECTED:
            append_order_journal({
                "event": "REJECTED",
                "order_id": order_id,
                "http_status": submission.http_status,
                "rejection_reason": submission.rejection_reason,
                "is_production": bool(self.is_production),
            })
            return CancelResult(
                status=CancelStatus.REJECTED,
                order_id=order_id,
                parsed_order=None,
                cumulative_qty=0,
                remaining_qty=0,
                request_sent=True,
                http_status=submission.http_status,
                result_code=submission.result_code,
                rejection_reason=submission.rejection_reason,
                response_text=submission.response_text,
                confirmed=False,
            )
        append_order_journal({
            "event": "UNKNOWN",
            "order_id": order_id,
            "http_status": submission.http_status,
            "response_text": submission.response_text,
            "rejection_reason": submission.rejection_reason,
            "is_production": bool(self.is_production),
        })
        return CancelResult(
            status=CancelStatus.UNKNOWN,
            order_id=order_id,
            parsed_order=None,
            cumulative_qty=0,
            remaining_qty=0,
            request_sent=True,
            http_status=submission.http_status,
            result_code=submission.result_code,
            rejection_reason=submission.rejection_reason,
            response_text=submission.response_text,
            confirmed=False,
        )

    def _confirm_terminal_order_state(self, order_id: str, timeout_sec: int = 5) -> dict | None:
        """Cancel request or timeout後に、終端状態を確認する。"""
        start_time = time.time()
        while time.time() - start_time < timeout_sec:
            details = self.get_order_details(order_id)
            if not details:
                time.sleep(1)
                continue
            parsed = parse_kabucom_order(details)
            if parsed.process_state != OrderProcessState.TERMINAL:
                time.sleep(1)
                continue
            enriched = dict(details)
            enriched["__parsed_process_state__"] = parsed.process_state.value
            enriched["__parsed_terminal_reason__"] = None if parsed.terminal_reason is None else parsed.terminal_reason.value
            enriched["__parsed_cumulative_qty__"] = parsed.cumulative_qty
            enriched["__parsed_order_qty__"] = parsed.order_qty
            enriched["__parsed_average_fill_price__"] = parsed.average_fill_price
            enriched["__parsed_has_partial_fill__"] = parsed.has_partial_fill
            return enriched
        return None

    def _enrich_order_details_with_parse(self, details: dict | None, *, unresolved: bool = False, unresolved_reason: str | None = None) -> dict:
        """注文詳細にパース結果を付与し、未解決フラグを安全に引き回せるようにする。"""
        enriched = dict(details or {})
        parsed = parse_kabucom_order(enriched)
        enriched["__parsed_process_state__"] = parsed.process_state.value
        enriched["__parsed_terminal_reason__"] = None if parsed.terminal_reason is None else parsed.terminal_reason.value
        enriched["__parsed_cumulative_qty__"] = parsed.cumulative_qty
        enriched["__parsed_order_qty__"] = parsed.order_qty
        enriched["__parsed_average_fill_price__"] = parsed.average_fill_price
        enriched["__parsed_has_partial_fill__"] = parsed.has_partial_fill
        enriched["unresolved"] = bool(unresolved)
        if unresolved_reason:
            enriched["unresolved_reason"] = str(unresolved_reason)
        if parsed.cumulative_qty > 0:
            enriched["Qty"] = parsed.cumulative_qty
            if parsed.average_fill_price is not None:
                enriched["Price"] = parsed.average_fill_price
        return enriched

    def get_order_details(self, order_id: str) -> dict:
        """ 注文詳細（ステータス・約定単価等）を取得する """
        if not self.token or not order_id: return None
        res = self._api_request("GET", f"orders?id={order_id}", timeout=10)
        if res and res.status_code == 200:
            orders = res.json()
            validation = validate_order_detail_response(orders)
            if not validation.valid:
                print(f"⚠️ 注文詳細レスポンス契約違反: {validation.reason}")
                return None
            normalized_orders = validation.normalized_payload or []
            if normalized_orders:
                return normalized_orders[0]
        return None

    # --- [New] リアルタイム監視用の銘柄登録・解除・板情報取得 ---
    def register_symbols(self, symbols: list):
        """ 
        kabuステーションAPI側に銘柄を監視登録する。
        仕様上1回あたり50銘柄までのため、チャンク分割して実行する。
        """
        if not self.token: return False
        allowed, reason = self._authorize_operation(BrokerOperationClass.REGISTRY_MUTATION)
        if not allowed:
            print(f"🛑 register をコード側で停止しました。reason={reason}")
            return False
        url = f"{self.base_url}/register"
        
        # yfinance形式 (7203.T) -> カブコム形式 (7203)
        # [Professional Audit] 重複登録を排除してAPIの負荷とエラーを防ぐ
        codes = sorted(list(set(str(s).replace(".T", "") for s in symbols)))
        
        chunk_size = 50
        for i in range(0, len(codes), chunk_size):
            chunk = codes[i:i + chunk_size]
            reg_list = [{"Symbol": c, "Exchange": 1} for c in chunk]
            data = {"Symbols": reg_list}
            res = self._api_request("PUT", "register", json=data, timeout=10)
            if res and res.status_code == 200:
                print(f"✅ API銘柄登録完了 ({i+1}〜{i+len(chunk)}銘柄目)")
            else:
                print(f"⚠️ 銘柄登録エラー ({i+1}〜): {res.text if res else 'No Response'}")
                return False
        return True

    def unregister_symbols(self, symbols: list):
        """ 監視対象から外れた銘柄を解除する（2000銘柄の上限管理） """
        if not self.token or not symbols: return False
        allowed, reason = self._authorize_operation(BrokerOperationClass.REGISTRY_MUTATION)
        if not allowed:
            print(f"🛑 unregister をコード側で停止しました。reason={reason}")
            return False
        url = f"{self.base_url}/unregister"
        
        # [Professional Audit] 重複解除を排除してリソースを最適化
        codes = sorted(list(set(str(s).replace(".T", "") for s in symbols)))
        chunk_size = 50
        for i in range(0, len(codes), chunk_size):
            chunk = codes[i:i + chunk_size]
            unreg_list = [{"Symbol": c, "Exchange": 1} for c in chunk]
            data = {"Symbols": unreg_list}
            res = self._api_request("PUT", "unregister", json=data, timeout=10)
            if res and res.status_code == 200:
                print(f"✅ API銘柄登録解除完了 ({i+1}〜{i+len(chunk)}銘柄目)")
            else:
                print(f"⚠️ 銘柄解除エラー: {res.text if res else 'No Response'}")
                return False
        return True

    def unregister_all(self):
        """ 登録済みの全銘柄を解除する（上限管理のため） """
        if not self.token: return False
        print("🛑 unregister/all は安全上の理由で無効化されています。")
        return False

    def get_board_data(self, symbols: list) -> dict:
        """ [Professional Audit] 制限値幅を含めた板時価情報を取得する """
        results = {}
        if not self.token: return results
        
        for s in symbols:
            code = str(s).replace(".T", "")
            res = self._api_request("GET", f"board/{code}@1", timeout=5)
            # [Professional Audit] 連続リクエストによる API サーバーへの瞬間負荷 (Burst) を抑制する
            time.sleep(0.1)
            if res and res.status_code == 200:
                data = res.json()
                quote = parse_board_quote(code, data)
                if not quote.is_valid:
                    print(f"⚠️ 板情報スキップ: {code} ({quote.rejection_reason})")
                    continue
                received_at = datetime.now(JST)
                results[code] = {
                    "symbol": quote.symbol,
                    "price": quote.current_price,
                    "current_price": quote.current_price,
                    "best_sell_price": quote.best_sell_price,
                    "best_sell_qty": quote.best_sell_qty,
                    "best_buy_price": quote.best_buy_price,
                    "best_buy_qty": quote.best_buy_qty,
                    "quote_timestamp": quote.quote_timestamp,
                    "current_price_timestamp": quote.current_price_timestamp,
                    "bid_timestamp": quote.bid_timestamp,
                    "ask_timestamp": quote.ask_timestamp,
                    "opening_price_timestamp": quote.opening_price_timestamp,
                    "received_at": quote.received_at or received_at,
                    "bid_sign_raw": quote.bid_sign_raw,
                    "ask_sign_raw": quote.ask_sign_raw,
                    "current_price_status": quote.current_price_status,
                    "open": data.get('OpeningPrice'),
                    "high": data.get('HighPrice'),
                    "low": data.get('LowPrice'),
                    "volume": data.get('TradingVolume'),
                    "prev_close": data.get('PreviousClose'),
                    "upper_limit": quote.upper_limit,
                    "lower_limit": quote.lower_limit,
                    "is_valid": quote.is_valid,
                }
        return results

    def execute_chase_order(self, code: str, shares: int, action: StockOrderAction, atr: float = 0) -> dict:
        """
        指値を最良気配に追従（Chase）させながら発注し、一定時間で強制執行するOMS機能。
        [Professional Audit] 1. 部分約定の合算(VWAP), 2. 待機時間の短縮, 3. 決済指定(HoldID)
        """
        context = resolve_stock_order_action_context(action, allow_short=True)
        side = context.side
        operation_class = self._resolve_operation_class_for_action(action)
        if action in (StockOrderAction.MARGIN_NEW_SHORT, StockOrderAction.MARGIN_CLOSE_SHORT):
            print(f"🛑 追従発注をコード側で停止しました。reason=unsupported_stock_order_action action={action.value}")
            return {
                "order_id": None,
                "submission_status": SubmissionStatus.REJECTED.value,
                "process_state": OrderProcessState.UNKNOWN.value,
                "terminal_reason": None,
                "Qty": 0,
                "filled_qty": 0,
                "Price": 0.0,
                "average_price": None,
                "remaining_qty": int(shares),
                "Symbol": code,
                "has_partial_fill": False,
                "unresolved": True,
                "unresolved_reason": "unsupported_stock_order_action",
                "execution_ids": (),
                "execution_id": None,
                "side": side,
                "action": action.value,
            }
        print(f"🚀 【追従発注開始】{code} {shares}株 (Side:{side})")
        
        remaining_shares = shares
        total_filled_qty = 0
        total_filled_value = 0.0
        total_execution_ids: list[str] = []
        unresolved = False
        last_order_id = None
        last_submission = None
        last_terminal_reason = None
        last_process_state = OrderProcessState.UNKNOWN
        unresolved_reason = None
        last_execution_status = None
        last_entry_execution_status = None
        last_exit_execution_status = None

        def _log_unresolved_order_event(
            *,
            reason: str,
            order_id: str | None,
            filled_qty: int,
            remaining_qty: int,
            terminal_reason: OrderTerminalReason | None,
            submission_status: SubmissionStatus | None,
        ) -> None:
            append_order_journal({
                "event": "UNKNOWN",
                "intent_id": None if last_submission is None else last_submission.intent_id,
                "kind": "market",
                "symbol": str(code),
                "side": side,
                "qty": int(shares),
                "order_id": order_id,
                "filled_qty": int(filled_qty),
                "remaining_qty": int(remaining_qty),
                "process_state": OrderProcessState.UNKNOWN.value,
                "terminal_reason": None if terminal_reason is None else terminal_reason.value,
                "unresolved_reason": reason,
                "submission_status": None if submission_status is None else submission_status.value,
                "is_production": bool(self.is_production),
            })

        filled_order_ids: set[str] = set()

        def _log_filled_order_event(
            *,
            order_id: str | None,
            filled_qty: int,
            remaining_qty: int,
            terminal_reason: OrderTerminalReason | None,
            submission_status: SubmissionStatus | None,
        ) -> None:
            order_key = str(order_id or "").strip()
            if not order_key or order_key in filled_order_ids:
                return
            filled_order_ids.add(order_key)
            append_order_journal({
                "event": "FILLED",
                "intent_id": None if last_submission is None else last_submission.intent_id,
                "kind": "market",
                "symbol": str(code),
                "side": side,
                "qty": int(filled_qty),
                "order_id": order_id,
                "filled_qty": int(filled_qty),
                "remaining_qty": int(max(0, remaining_qty)),
                "process_state": OrderProcessState.TERMINAL.value,
                "terminal_reason": None if terminal_reason is None else terminal_reason.value,
                "submission_status": None if submission_status is None else submission_status.value,
                "is_production": bool(self.is_production),
            })

        from core.logic import normalize_tick_size
        for attempt in range(1, 4):
            if remaining_shares <= 0:
                break
            time.sleep(0.2)

            board = self.get_board_data([code])
            b_info = board.get(str(code).replace(".T", ""))
            if not b_info:
                break

            c_price = float(b_info.get("current_price") or b_info.get("price") or 0.0)
            if side == "2" and c_price >= float(b_info.get("upper_limit", 999999) or 999999):
                print(f"🚨 {code} はストップ高に達しているため、買い注文を中止します。")
                break
            if side == "1" and c_price <= float(b_info.get("lower_limit", 0) or 0):
                print(f"🚨 {code} はストップ安に達しているため、売り注文を中止します。")
                break

            if side == "2":
                limit_price = b_info.get("best_sell_price") or b_info.get("price") or c_price
                limit_price = normalize_tick_size(limit_price, is_buy=True)
            else:
                limit_price = b_info.get("best_buy_price") or b_info.get("price") or c_price
                limit_price = normalize_tick_size(limit_price, is_buy=False)

            if not limit_price or limit_price <= 0:
                print(f"⚠️ {code} の有効な価格が取得できないため、追従を中断します。")
                break

            close_pos_list = None
            close_route = None
            if side == "1":
                close_route = self._build_close_positions_for_symbol(code, remaining_shares)
                if close_route is None:
                    print(f"⚠️ {code} の返済建玉を正しく特定できないため、追従を中止します。")
                    unresolved = True
                    break
                close_pos_list = close_route["close_positions"]

            submission = self._submit_market_order(
                code,
                remaining_shares,
                side,
                price=limit_price,
                close_positions=close_pos_list,
                exchange=None if close_route is None else close_route.get("exchange"),
                margin_trade_type=None if close_route is None else close_route.get("margin_trade_type"),
                operation_class=operation_class,
            )
            order_id = submission.broker_order_id
            last_submission = submission
            last_order_id = order_id
            if not order_id:
                if last_submission and last_submission.status == SubmissionStatus.REJECTED:
                    rejection_reason = last_submission.rejection_reason or "rejected"
                    return {
                        "order_id": None,
                        "submission_status": last_submission.status.value,
                        "process_state": OrderProcessState.UNKNOWN.value,
                        "terminal_reason": OrderTerminalReason.REJECTED.value,
                        "Qty": total_filled_qty,
                        "filled_qty": total_filled_qty,
                        "Price": total_filled_value / total_filled_qty if total_filled_qty > 0 else 0.0,
                        "average_price": total_filled_value / total_filled_qty if total_filled_qty > 0 else None,
                        "remaining_qty": remaining_shares,
                        "Symbol": code,
                        "has_partial_fill": total_filled_qty > 0 and total_filled_qty < shares,
                        "rejection_reason": rejection_reason,
                        "unresolved": False,
                    }
                if last_submission and last_submission.status == SubmissionStatus.UNKNOWN:
                    unresolved = True
                    unresolved_reason = "submission_unknown"
                break

            print(f"⏳ 追従試行 {attempt}/3: 価格 {limit_price:.1f} で {remaining_shares}株 待機中...")
            start_wait = time.time()
            terminal_details = None

            while time.time() - start_wait < 30:
                details = self.get_order_details(order_id)
                if details:
                    parsed = parse_kabucom_order(details)
                    if parsed.process_state == OrderProcessState.UNKNOWN:
                        print(f"⚠️ 注文 ID: {order_id} の状態が不明です。再注文は行わず終了します。")
                        unresolved = True
                        unresolved_reason = "unknown_state"
                        terminal_details = details
                        last_process_state = parsed.process_state
                        last_terminal_reason = parsed.terminal_reason
                        break
                    if parsed.process_state == OrderProcessState.TERMINAL:
                        for execution_id in parsed.execution_ids:
                            if execution_id not in total_execution_ids:
                                total_execution_ids.append(execution_id)
                        terminal_details = dict(details)
                        terminal_details["__parsed_process_state__"] = parsed.process_state.value
                        terminal_details["__parsed_terminal_reason__"] = None if parsed.terminal_reason is None else parsed.terminal_reason.value
                        terminal_details["__parsed_cumulative_qty__"] = parsed.cumulative_qty
                        terminal_details["__parsed_average_fill_price__"] = parsed.average_fill_price
                        terminal_details["__parsed_has_partial_fill__"] = parsed.has_partial_fill
                        last_process_state = parsed.process_state
                        last_terminal_reason = parsed.terminal_reason
                        if parsed.terminal_reason == OrderTerminalReason.REJECTED and parsed.cumulative_qty <= 0:
                            return {
                                "order_id": order_id,
                                "submission_status": None if last_submission is None else last_submission.status.value,
                                "process_state": OrderProcessState.UNKNOWN.value,
                                "terminal_reason": OrderTerminalReason.REJECTED.value,
                                "Qty": 0,
                                "filled_qty": 0,
                                "Price": 0.0,
                                "average_price": None,
                                "remaining_qty": shares,
                                "Symbol": code,
                                "has_partial_fill": False,
                                "rejection_reason": "broker_rejected",
                                "unresolved": False,
                                "execution_status": "rejected",
                                "entry_execution_status": "rejected",
                                "exit_execution_status": "rejected",
                                "execution_ids": tuple(total_execution_ids),
                                "execution_id": total_execution_ids[0] if total_execution_ids else None,
                            }
                        if parsed.terminal_reason == OrderTerminalReason.FILLED and parsed.cumulative_qty > 0:
                            _log_filled_order_event(
                                order_id=order_id,
                                filled_qty=parsed.cumulative_qty,
                                remaining_qty=0,
                                terminal_reason=parsed.terminal_reason,
                                submission_status=last_submission.status if last_submission is not None else None,
                            )
                        break
                time.sleep(1)

            if terminal_details is None and not unresolved:
                print(f"⏰ 待機時間終了。注文 ID: {order_id} を一度取り消して残数を確認します。")
                cancel_confirmed = self.cancel_order(order_id)
                if cancel_confirmed:
                    terminal_details = self._confirm_terminal_order_state(order_id, timeout_sec=5)
                else:
                    terminal_details = self._confirm_terminal_order_state(order_id, timeout_sec=5)
                if terminal_details is None:
                    print("⛔ 取消完了が確認できないため、新規再発注は行わず終了します。")
                    unresolved = True
                    unresolved_reason = "cancel_unconfirmed"
                    break

            if terminal_details:
                parsed = parse_kabucom_order(terminal_details)
                last_terminal_reason = parsed.terminal_reason
                if parsed.process_state == OrderProcessState.UNKNOWN:
                    unresolved = True
                    unresolved_reason = "unknown_state"
                    break
                if parsed.cumulative_qty > 0:
                    for execution_id in parsed.execution_ids:
                        if execution_id not in total_execution_ids:
                            total_execution_ids.append(execution_id)
                    fill_qty = parsed.cumulative_qty
                    fill_price = parsed.average_fill_price
                    if fill_price is None:
                        raw_price = terminal_details.get("Price", limit_price)
                        fill_price = float(raw_price if raw_price not in (None, 0) else limit_price)
                    total_filled_qty += fill_qty
                    total_filled_value += float(fill_price) * fill_qty
                    remaining_shares = max(0, shares - total_filled_qty)
                    print(
                        f"⚠️ 注文 ID: {order_id} は {fill_qty}株 約定済みです"
                        + (" (部分約定)" if remaining_shares > 0 else "")
                    )
                if parsed.terminal_reason == OrderTerminalReason.FILLED or remaining_shares <= 0:
                    break
                continue

        if unresolved:
            avg_price = total_filled_value / total_filled_qty if total_filled_qty > 0 else 0.0
            terminal_reason = None if last_terminal_reason is None else last_terminal_reason.value
            _log_unresolved_order_event(
                reason=unresolved_reason or "unresolved",
                order_id=last_order_id,
                filled_qty=total_filled_qty,
                remaining_qty=max(0, shares - total_filled_qty),
                terminal_reason=last_terminal_reason,
                submission_status=None if last_submission is None else last_submission.status,
            )
            return {
                "order_id": last_order_id,
                "submission_status": None if last_submission is None else last_submission.status.value,
                "process_state": OrderProcessState.UNKNOWN.value,
                "terminal_reason": terminal_reason,
                "Qty": total_filled_qty,
                "filled_qty": total_filled_qty,
                "Price": avg_price,
                "average_price": avg_price if total_filled_qty > 0 else None,
                "remaining_qty": max(0, shares - total_filled_qty),
                "Symbol": code,
                "has_partial_fill": total_filled_qty > 0 and total_filled_qty < shares,
                "unresolved_reason": unresolved_reason or (None if last_terminal_reason is None else last_terminal_reason.value),
                "execution_status": last_execution_status,
                "entry_execution_status": last_entry_execution_status,
                "exit_execution_status": last_exit_execution_status,
                "execution_ids": tuple(total_execution_ids),
                "execution_id": total_execution_ids[0] if total_execution_ids else None,
                "unresolved": True,
            }

        if remaining_shares > 0:
            print(f"🔥 【強制執行】残数 {remaining_shares}株 をマージン付の価格で即時約定させます。")
            board = self.get_board_data([code])
            b_info = board.get(str(code).replace(".T", ""))
            current_price = float(b_info.get("current_price") or b_info.get("price") or 0.0)

            if side == "2":
                force_price = normalize_tick_size(current_price + (atr * 0.2 if atr > 0 else current_price * 0.01), is_buy=True)
            else:
                force_price = normalize_tick_size(current_price - (atr * 0.2 if atr > 0 else current_price * 0.01), is_buy=False)

            close_pos_list = None
            close_route = None
            if side == "1":
                close_route = self._build_close_positions_for_symbol(code, remaining_shares)
                if close_route is None:
                    print(f"⚠️ {code} の返済建玉を正しく特定できないため、強制執行を中止します。")
                    _log_unresolved_order_event(
                        reason="close_route_unavailable",
                        order_id=last_order_id,
                        filled_qty=total_filled_qty,
                        remaining_qty=remaining_shares,
                        terminal_reason=last_terminal_reason,
                        submission_status=None if last_submission is None else last_submission.status,
                    )
                    return {
                        "order_id": last_order_id,
                        "submission_status": None if last_submission is None else last_submission.status.value,
                        "process_state": OrderProcessState.UNKNOWN.value,
                        "terminal_reason": None if last_terminal_reason is None else last_terminal_reason.value,
                        "Qty": total_filled_qty,
                        "filled_qty": total_filled_qty,
                        "Price": total_filled_value / total_filled_qty if total_filled_qty > 0 else 0.0,
                        "average_price": total_filled_value / total_filled_qty if total_filled_qty > 0 else None,
                        "remaining_qty": remaining_shares,
                        "Symbol": code,
                        "has_partial_fill": total_filled_qty > 0 and total_filled_qty < shares,
                        "rejection_reason": "close_positions_unavailable",
                        "unresolved_reason": "close_route_unavailable",
                        "unresolved": True,
                        "execution_status": last_execution_status,
                        "entry_execution_status": last_entry_execution_status,
                        "exit_execution_status": last_exit_execution_status,
                    }
                close_pos_list = close_route["close_positions"]

            submission = self._submit_market_order(
                code,
                remaining_shares,
                side,
                price=force_price,
                close_positions=close_pos_list,
                exchange=None if close_route is None else close_route.get("exchange"),
                margin_trade_type=None if close_route is None else close_route.get("margin_trade_type"),
                operation_class=operation_class,
            )
            order_id = submission.broker_order_id
            last_order_id = order_id or last_order_id
            last_submission = submission
            if order_id:
                execution_kind = "exit" if action == StockOrderAction.MARGIN_CLOSE_LONG else "entry"
                f_details = self.wait_for_execution(order_id, timeout_sec=20).to_legacy_dict(symbol=code, side=side, execution_kind=execution_kind)
                last_execution_status = f_details.get("execution_status")
                last_entry_execution_status = f_details.get("entry_execution_status")
                last_exit_execution_status = f_details.get("exit_execution_status")
                if f_details:
                    if f_details.get("unresolved"):
                        parsed = parse_kabucom_order(f_details)
                        last_terminal_reason = parsed.terminal_reason or last_terminal_reason
                        if parsed.cumulative_qty > 0:
                            for execution_id in parsed.execution_ids:
                                if execution_id not in total_execution_ids:
                                    total_execution_ids.append(execution_id)
                            fill_qty = parsed.cumulative_qty
                            fill_price = parsed.average_fill_price
                            if fill_price is None:
                                raw_price = f_details.get("Price", force_price)
                                fill_price = float(raw_price if raw_price not in (None, 0) else force_price)
                            total_filled_qty += fill_qty
                            total_filled_value += float(fill_price) * fill_qty
                            remaining_shares = max(0, shares - total_filled_qty)
                        _log_unresolved_order_event(
                            reason="wait_for_execution_unresolved",
                            order_id=last_order_id,
                            filled_qty=total_filled_qty,
                            remaining_qty=max(0, shares - total_filled_qty),
                            terminal_reason=parsed.terminal_reason or last_terminal_reason,
                            submission_status=None if last_submission is None else last_submission.status,
                        )
                        avg_price = total_filled_value / total_filled_qty if total_filled_qty > 0 else 0.0
                        return {
                            "order_id": last_order_id,
                            "submission_status": None if last_submission is None else last_submission.status.value,
                            "process_state": OrderProcessState.UNKNOWN.value,
                            "terminal_reason": None if parsed.terminal_reason is None else parsed.terminal_reason.value,
                            "Qty": total_filled_qty,
                            "filled_qty": total_filled_qty,
                            "Price": avg_price,
                            "average_price": avg_price if total_filled_qty > 0 else None,
                            "remaining_qty": max(0, shares - total_filled_qty),
                            "Symbol": code,
                            "has_partial_fill": total_filled_qty > 0 and total_filled_qty < shares,
                            "unresolved_reason": f_details.get("unresolved_reason") or "wait_for_execution_unresolved",
                            "unresolved": True,
                            "execution_status": last_execution_status,
                            "entry_execution_status": last_entry_execution_status,
                            "exit_execution_status": last_exit_execution_status,
                            "execution_ids": tuple(total_execution_ids),
                            "execution_id": total_execution_ids[0] if total_execution_ids else None,
                        }
                    parsed = parse_kabucom_order(f_details)
                    if parsed.process_state == OrderProcessState.UNKNOWN:
                        if parsed.cumulative_qty > 0:
                            for execution_id in parsed.execution_ids:
                                if execution_id not in total_execution_ids:
                                    total_execution_ids.append(execution_id)
                            fill_qty = parsed.cumulative_qty
                            fill_price = parsed.average_fill_price
                            if fill_price is None:
                                raw_price = f_details.get("Price", force_price)
                                fill_price = float(raw_price if raw_price not in (None, 0) else force_price)
                            total_filled_qty += fill_qty
                            total_filled_value += float(fill_price) * fill_qty
                            remaining_shares = max(0, shares - total_filled_qty)
                        _log_unresolved_order_event(
                            reason="force_fill_unknown_state",
                            order_id=last_order_id,
                            filled_qty=total_filled_qty,
                            remaining_qty=max(0, shares - total_filled_qty),
                            terminal_reason=parsed.terminal_reason or last_terminal_reason,
                            submission_status=None if last_submission is None else last_submission.status,
                        )
                        avg_price = total_filled_value / total_filled_qty if total_filled_qty > 0 else 0.0
                        return {
                            "order_id": last_order_id,
                            "submission_status": None if last_submission is None else last_submission.status.value,
                            "process_state": OrderProcessState.UNKNOWN.value,
                            "terminal_reason": None if parsed.terminal_reason is None else parsed.terminal_reason.value,
                            "Qty": total_filled_qty,
                            "filled_qty": total_filled_qty,
                            "Price": avg_price,
                            "average_price": avg_price if total_filled_qty > 0 else None,
                            "remaining_qty": max(0, shares - total_filled_qty),
                            "Symbol": code,
                            "has_partial_fill": total_filled_qty > 0 and total_filled_qty < shares,
                            "unresolved_reason": "force_fill_unknown_state",
                            "unresolved": True,
                            "execution_status": last_execution_status,
                            "entry_execution_status": last_entry_execution_status,
                            "exit_execution_status": last_exit_execution_status,
                            "execution_ids": tuple(total_execution_ids),
                            "execution_id": total_execution_ids[0] if total_execution_ids else None,
                        }
                    elif parsed.cumulative_qty > 0:
                        last_terminal_reason = parsed.terminal_reason or last_terminal_reason
                        for execution_id in parsed.execution_ids:
                            if execution_id not in total_execution_ids:
                                total_execution_ids.append(execution_id)
                        fill_qty = parsed.cumulative_qty
                        fill_price = parsed.average_fill_price
                        if fill_price is None:
                            raw_price = f_details.get("Price", force_price)
                            fill_price = float(raw_price if raw_price not in (None, 0) else force_price)
                        total_filled_qty += fill_qty
                        total_filled_value += float(fill_price) * fill_qty
                        remaining_shares = max(0, shares - total_filled_qty)
                        if parsed.terminal_reason == OrderTerminalReason.FILLED:
                            _log_filled_order_event(
                                order_id=order_id,
                                filled_qty=parsed.cumulative_qty,
                                remaining_qty=0,
                                terminal_reason=parsed.terminal_reason,
                                submission_status=last_submission.status if last_submission is not None else None,
                            )

        avg_price = total_filled_value / total_filled_qty if total_filled_qty > 0 else 0.0
        terminal_reason = None if last_terminal_reason is None else last_terminal_reason.value
        process_state = OrderProcessState.UNKNOWN.value if unresolved else (
            OrderProcessState.TERMINAL.value if total_filled_qty > 0 or terminal_reason is not None else OrderProcessState.UNKNOWN.value
        )
        if (
            not unresolved
            and total_filled_qty > 0
            and last_order_id
            and str(last_order_id).strip() not in filled_order_ids
            and (
                remaining_shares <= 0
                or last_terminal_reason == OrderTerminalReason.FILLED
            )
        ):
            _log_filled_order_event(
                order_id=last_order_id,
                filled_qty=total_filled_qty,
                remaining_qty=remaining_shares,
                terminal_reason=last_terminal_reason,
                submission_status=last_submission.status if last_submission is not None else None,
            )
        if last_execution_status is None:
            if total_filled_qty > 0:
                last_execution_status = "completed"
                if action == StockOrderAction.MARGIN_CLOSE_LONG:
                    last_exit_execution_status = "completed"
                else:
                    last_entry_execution_status = "completed"
            elif last_terminal_reason == OrderTerminalReason.REJECTED:
                last_execution_status = "rejected"
                if action == StockOrderAction.MARGIN_CLOSE_LONG:
                    last_exit_execution_status = "rejected"
                else:
                    last_entry_execution_status = "rejected"
        return {
            "order_id": last_order_id,
            "submission_status": None if last_submission is None else last_submission.status.value,
            "process_state": process_state,
            "terminal_reason": terminal_reason,
            "Qty": total_filled_qty,
            "filled_qty": total_filled_qty,
            "Price": avg_price,
            "average_price": avg_price if total_filled_qty > 0 else None,
            "remaining_qty": max(0, shares - total_filled_qty),
            "Symbol": code,
            "has_partial_fill": total_filled_qty > 0 and total_filled_qty < shares,
            "unresolved": unresolved,
            "execution_status": last_execution_status,
            "entry_execution_status": last_entry_execution_status,
            "exit_execution_status": last_exit_execution_status,
            "execution_ids": tuple(total_execution_ids),
            "execution_id": total_execution_ids[0] if total_execution_ids else None,
        }

    def execute_stop_order(
        self,
        code: str,
        shares: int,
        action: StockOrderAction,
        trigger_price: float,
        hold_id: str = None,
        close_positions: list | None = None,
        exchange: int | None = None,
        margin_trade_type: int | None = None,
    ) -> OrderSubmissionResult:
        """
        逆指値（ストップロス）注文を発注する。
        trigger_price: トリガー価格
        """
        context = resolve_stock_order_action_context(action, allow_short=True)
        side = context.side
        cash_margin = context.cash_margin
        if action in (StockOrderAction.MARGIN_NEW_SHORT, StockOrderAction.MARGIN_CLOSE_SHORT):
            intent_id = f"stop-{time.time_ns()}"
            normalized_trigger_price = float(trigger_price)
            submission = SubmissionResult(
                status=SubmissionStatus.REJECTED,
                intent_id=intent_id,
                broker_order_id=None,
                symbol=str(code),
                side=side,
                qty=int(shares),
                price=float(normalized_trigger_price),
                http_status=None,
                rejection_reason="unsupported_stock_order_action",
            )
            append_order_journal({
                "event": "REJECTED",
                "intent_id": intent_id,
                "kind": "stop",
                "symbol": str(code),
                "side": side,
                "qty": int(shares),
                "trigger_price": float(normalized_trigger_price),
                "rejection_reason": submission.rejection_reason,
                "order_action": action.value,
                "exchange": None if exchange is None else int(exchange),
                "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
                "is_production": bool(self.is_production),
            })
            print(f"🛑 逆指値注文をコード側で停止しました。reason=unsupported_stock_order_action action={action.value}")
            return OrderSubmissionResult.from_submission(
                submission,
                action=action,
                request_sent=False,
                side=side,
                trigger_price=float(normalized_trigger_price),
            )
        if not self.token:
            submission = SubmissionResult(
                status=SubmissionStatus.UNKNOWN,
                intent_id=f"stop-{time.time_ns()}",
                broker_order_id=None,
                symbol=str(code),
                side=side,
                qty=int(shares),
                price=float(trigger_price),
                http_status=None,
                rejection_reason="no_token",
            )
            return self._wrap_submission_result(
                submission,
                side=side,
                cash_margin=cash_margin,
                request_sent=False,
                trigger_price=float(trigger_price),
            )
        intent_id = f"stop-{time.time_ns()}"

        if margin_trade_type is None:
            margin_trade_type = 3 if side == "2" else None
        from core.logic import normalize_tick_size
        normalized_trigger_price = normalize_tick_size(trigger_price, is_buy=(side == "2"))
        if exchange is None:
            if side == "2":
                exchange = self._resolve_buy_exchange()
                if exchange is None:
                    print(f"⚠️ 逆指値の新規買い注文に必要なExchangeが未設定のため、発注を中止します: {code}")
                    submission = SubmissionResult(
                        status=SubmissionStatus.REJECTED,
                        intent_id=intent_id,
                        broker_order_id=None,
                        symbol=str(code),
                        side=side,
                        qty=int(shares),
                        price=float(normalized_trigger_price),
                        http_status=None,
                        rejection_reason="missing_buy_exchange",
                    )
                    append_order_journal({
                        "event": "REJECTED",
                        "intent_id": intent_id,
                        "kind": "stop",
                        "symbol": str(code),
                        "side": side,
                        "qty": int(shares),
                        "trigger_price": float(normalized_trigger_price),
                        "hold_id": hold_id,
                        "http_status": None,
                        "result": None,
                        "rejection_reason": "missing_buy_exchange",
                        "exchange": None,
                        "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
                        "is_production": bool(self.is_production),
                    })
                    return self._wrap_submission_result(
                        submission,
                        side=side,
                        cash_margin=cash_margin,
                        request_sent=False,
                        trigger_price=float(normalized_trigger_price),
                    )
            elif hold_id:
                route = self._resolve_hold_route(hold_id)
                if route:
                    exchange = route["exchange"]
                    margin_trade_type = route["margin_trade_type"]
        if side == "1" and (exchange is None or margin_trade_type is None):
            print(f"⚠️ 逆指値の返済建玉ルートが不明なため、発注を中止します: {code}")
            submission = SubmissionResult(
                status=SubmissionStatus.REJECTED,
                intent_id=intent_id,
                broker_order_id=None,
                symbol=str(code),
                side=side,
                qty=int(shares),
                price=float(normalized_trigger_price),
                http_status=None,
                rejection_reason="missing_close_route",
            )
            append_order_journal({
                "event": "REJECTED",
                "intent_id": intent_id,
                "kind": "stop",
                "symbol": str(code),
                "side": side,
                "qty": int(shares),
                "trigger_price": float(normalized_trigger_price),
                "hold_id": hold_id,
                "close_positions": None,
                "expected_close_positions": None,
                "hold_ids": [],
                "trigger_price_normalized": float(normalized_trigger_price),
                "order_action": getattr(action, "value", str(action)),
                "cash_margin": int(cash_margin),
                "deliv_type": 0 if cash_margin == 2 else 2,
                "route_resolution_stage": "pre_resolution",
                "route_resolution_reason": "missing_close_route",
                "http_status": None,
                "result": None,
                "rejection_reason": "missing_close_route",
                "exchange": None if exchange is None else int(exchange),
                "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
                "is_production": bool(self.is_production),
            })
            return self._wrap_submission_result(
                submission,
                side=side,
                cash_margin=cash_margin,
                request_sent=False,
                trigger_price=float(normalized_trigger_price),
            )
        if hasattr(self, "endpoint_config"):
            if self.environment == BrokerEnvironment.LIVE and TRADE_MODE != "KABUCOM_LIVE":
                submission = SubmissionResult(
                    status=SubmissionStatus.REJECTED,
                    intent_id=intent_id,
                    broker_order_id=None,
                    symbol=str(code),
                    side=side,
                    qty=int(shares),
                    price=float(normalized_trigger_price),
                    http_status=None,
                    rejection_reason="live_endpoint_write_blocked_by_trade_mode",
                )
                append_order_journal({
                    "event": "REJECTED",
                    "intent_id": intent_id,
                    "kind": "stop",
                    "symbol": str(code),
                    "side": side,
                    "qty": int(shares),
                    "trigger_price": float(normalized_trigger_price),
                    "rejection_reason": submission.rejection_reason,
                    "is_production": bool(self.is_production),
                })
                return self._wrap_submission_result(
                    submission,
                    side=side,
                    cash_margin=cash_margin,
                    request_sent=False,
                    trigger_price=float(normalized_trigger_price),
                )
            if self.environment == BrokerEnvironment.TEST and TRADE_MODE != "KABUCOM_TEST":
                submission = SubmissionResult(
                    status=SubmissionStatus.REJECTED,
                    intent_id=intent_id,
                    broker_order_id=None,
                    symbol=str(code),
                    side=side,
                    qty=int(shares),
                    price=float(normalized_trigger_price),
                    http_status=None,
                    rejection_reason="test_endpoint_requires_kabucom_test_mode",
                )
                append_order_journal({
                    "event": "REJECTED",
                    "intent_id": intent_id,
                    "kind": "stop",
                    "symbol": str(code),
                    "side": side,
                    "qty": int(shares),
                    "trigger_price": float(normalized_trigger_price),
                    "rejection_reason": submission.rejection_reason,
                    "is_production": bool(self.is_production),
                })
                return self._wrap_submission_result(
                    submission,
                    side=side,
                    cash_margin=cash_margin,
                    request_sent=False,
                    trigger_price=float(normalized_trigger_price),
                )
        operation_class = self._resolve_operation_class_for_action(action)
        allowed, reason = self._authorize_operation(operation_class)
        if not allowed:
            normalized_reason = self._normalize_submission_rejection_reason(reason)
            print(f"🛑 逆指値注文をコード側で停止しました。reason={reason}")
            submission = SubmissionResult(
                status=SubmissionStatus.REJECTED,
                intent_id=intent_id,
                broker_order_id=None,
                symbol=str(code),
                side=side,
                qty=int(shares),
                price=float(normalized_trigger_price),
                http_status=None,
                rejection_reason=normalized_reason,
            )
            append_order_journal({
                "event": "REJECTED",
                "intent_id": intent_id,
                "kind": "stop",
                "symbol": str(code),
                "side": side,
                "qty": int(shares),
                "trigger_price": float(normalized_trigger_price),
                "hold_id": hold_id,
                "http_status": None,
                "result": None,
                "rejection_reason": normalized_reason,
                "exchange": None if exchange is None else int(exchange),
                "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
                "is_production": bool(self.is_production),
            })
            return self._wrap_submission_result(
                submission,
                side=side,
                cash_margin=cash_margin,
                request_sent=False,
                trigger_price=float(normalized_trigger_price),
            )
        if not self.order_password:
            submission = SubmissionResult(
                status=SubmissionStatus.REJECTED,
                intent_id=intent_id,
                broker_order_id=None,
                symbol=str(code),
                side=side,
                qty=int(shares),
                price=float(normalized_trigger_price),
                http_status=None,
                rejection_reason="missing_order_password",
            )
            append_order_journal({
                "event": "REJECTED",
                "intent_id": intent_id,
                "kind": "stop",
                "symbol": str(code),
                "side": side,
                "qty": int(shares),
                "trigger_price": float(normalized_trigger_price),
                "rejection_reason": submission.rejection_reason,
                "is_production": bool(self.is_production),
            })
            return self._wrap_submission_result(
                submission,
                side=side,
                cash_margin=cash_margin,
                request_sent=False,
                trigger_price=float(normalized_trigger_price),
            )
        account_type = self._resolve_account_type()
        if account_type is None:
            print(f"⚠️ 逆指値注文のAccountTypeが未設定のため、発注を中止します: {code}")
            submission = SubmissionResult(
                status=SubmissionStatus.REJECTED,
                intent_id=intent_id,
                broker_order_id=None,
                symbol=str(code),
                side=side,
                qty=int(shares),
                price=float(normalized_trigger_price),
                http_status=None,
                rejection_reason="missing_account_type",
            )
            append_order_journal({
                "event": "REJECTED",
                "intent_id": intent_id,
                "kind": "stop",
                "symbol": str(code),
                "side": side,
                "qty": int(shares),
                "trigger_price": float(normalized_trigger_price),
                "hold_id": hold_id,
                "http_status": None,
                "result": None,
                "rejection_reason": submission.rejection_reason,
                "exchange": None if exchange is None else int(exchange),
                "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
                "is_production": bool(self.is_production),
            })
            return self._wrap_submission_result(
                submission,
                side=side,
                cash_margin=cash_margin,
                request_sent=False,
                trigger_price=float(normalized_trigger_price),
            )
        if margin_trade_type is None:
            margin_trade_type = 3

        # 逆指値の設定
        # 公式仕様の UnderOver に合わせる。
        # 1: 以下, 2: 以上
        # 売り（損切り）の場合は現在値が trigger_price 以下になったら成行
        under_over = 1 if side == "1" else 2

        append_order_journal({
            "event": "PLANNED",
            "intent_id": intent_id,
            "kind": "stop",
            "symbol": str(code),
            "side": side,
            "qty": int(shares),
            "trigger_price": float(normalized_trigger_price),
            "hold_id": hold_id,
            "exchange": None if exchange is None else int(exchange),
            "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
            "is_production": bool(self.is_production),
        })

        data = {
            "Password": self.order_password,
            "Symbol": code,
            "Exchange": int(exchange),
            "SecurityType": 1,
            "Side": side,
            "CashMargin": cash_margin,
            "MarginTradeType": margin_trade_type,
            "DelivType": 0 if cash_margin == 2 else 2,
            "AccountType": account_type,
            "Qty": shares,
            "FrontOrderType": 30,  # 逆指値
            "Price": 0,
            "ExpireDay": 0,
            "ReverseLimitOrder": {
                "TriggerSec": 1,
                "TriggerPrice": float(normalized_trigger_price),
                "UnderOver": under_over,
                "AfterHitOrderType": 1, # 1: 成行
                "AfterHitPrice": 0
            }
        }

        route_resolution_stage_hint = None
        route_resolution_reason_hint = None

        def _build_stop_route_journal_fields(*, route_resolution_stage: str | None = None, route_resolution_reason: str | None = None) -> dict[str, object]:
            resolved_close_positions = data.get("ClosePositions")
            normalized_close_positions = None
            hold_ids: list[str] = []
            if route_resolution_stage is None:
                route_resolution_stage = route_resolution_stage_hint
                if route_resolution_stage is None:
                    route_resolution_stage = "resolved" if context.requires_close_positions else "not_required"
            if route_resolution_reason is None:
                route_resolution_reason = route_resolution_reason_hint
            if isinstance(resolved_close_positions, list):
                normalized_close_positions = []
                for item in resolved_close_positions:
                    if not isinstance(item, dict):
                        normalized_close_positions = None
                        hold_ids = []
                        break
                    copied_item = dict(item)
                    normalized_close_positions.append(copied_item)
                    hold_id_text = str(copied_item.get("HoldID") or copied_item.get("hold_id") or "").strip()
                    if hold_id_text:
                        hold_ids.append(hold_id_text)
            if route_resolution_stage == "pre_resolution":
                normalized_close_positions = None
                hold_ids = []
            return {
                "close_positions": normalized_close_positions,
                "expected_close_positions": normalized_close_positions,
                "hold_ids": hold_ids,
                "trigger_price_normalized": float(normalized_trigger_price),
                "order_action": getattr(action, "value", str(action)),
                "cash_margin": int(cash_margin),
                "deliv_type": int(data["DelivType"]),
                "exchange": None if exchange is None else int(exchange),
                "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
                "route_resolution_stage": route_resolution_stage,
                "route_resolution_reason": route_resolution_reason,
            }

        if context.requires_close_positions:
            if close_positions is not None:
                if not isinstance(close_positions, list) or not close_positions:
                    print(f"⚠️ 逆指値の返済建玉リストが不正なため、発注を中止します: {code}")
                    submission = SubmissionResult(
                        status=SubmissionStatus.REJECTED,
                        intent_id=intent_id,
                        broker_order_id=None,
                        symbol=str(code),
                        side=side,
                        qty=int(shares),
                        price=float(normalized_trigger_price),
                        http_status=None,
                        rejection_reason="close_positions_invalid",
                    )
                    append_order_journal({
                        "event": "REJECTED",
                        "intent_id": intent_id,
                        "kind": "stop",
                        "symbol": str(code),
                        "side": side,
                        "qty": int(shares),
                        "trigger_price": float(normalized_trigger_price),
                        "hold_id": hold_id,
                        **_build_stop_route_journal_fields(route_resolution_stage="pre_resolution", route_resolution_reason="close_positions_invalid"),
                        "http_status": None,
                        "result": None,
                        "rejection_reason": "close_positions_invalid",
                        "exchange": None if exchange is None else int(exchange),
                        "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
                        "is_production": bool(self.is_production),
                    })
                    return self._wrap_submission_result(
                        submission,
                        side=side,
                        cash_margin=cash_margin,
                        request_sent=False,
                        trigger_price=float(normalized_trigger_price),
                    )
                data["ClosePositions"] = close_positions
            elif hold_id:
                route_resolution_stage_hint = "fallback_single_hold"
                route_resolution_reason_hint = "single_hold_fallback"
                data["ClosePositions"] = [{"HoldID": hold_id, "Qty": shares}]
            else:
                print(f"⚠️ 逆指値の返済建玉IDが取得できないため、発注を中止します: {code}")
                submission = SubmissionResult(
                    status=SubmissionStatus.REJECTED,
                    intent_id=intent_id,
                    broker_order_id=None,
                    symbol=str(code),
                    side=side,
                    qty=int(shares),
                    price=float(normalized_trigger_price),
                    http_status=None,
                    rejection_reason="hold_id_missing",
                )
                append_order_journal({
                    "event": "REJECTED",
                    "intent_id": intent_id,
                    "kind": "stop",
                    "symbol": str(code),
                    "side": side,
                    "qty": int(shares),
                    "trigger_price": float(normalized_trigger_price),
                    "hold_id": hold_id,
                    **_build_stop_route_journal_fields(route_resolution_stage="pre_resolution", route_resolution_reason="hold_id_missing"),
                    "http_status": None,
                    "result": None,
                    "rejection_reason": "hold_id_missing",
                    "exchange": None if exchange is None else int(exchange),
                    "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
                    "is_production": bool(self.is_production),
                })
                return self._wrap_submission_result(
                    submission,
                    side=side,
                    cash_margin=cash_margin,
                    request_sent=False,
                    trigger_price=float(normalized_trigger_price),
                )

        append_order_journal({
            "event": "ROUTE_RESOLVED",
            "intent_id": intent_id,
            "kind": "stop",
            "symbol": str(code),
            "side": side,
            "qty": int(shares),
            "trigger_price": float(normalized_trigger_price),
            "hold_id": hold_id,
            **_build_stop_route_journal_fields(),
            "is_production": bool(self.is_production),
        })

        payload_validation = validate_stop_order_request_payload(data)
        if not payload_validation.valid:
            print(f"🛑 stop order payload をコード側で停止しました。reason={payload_validation.reason}")
            submission = SubmissionResult(
                status=SubmissionStatus.REJECTED,
                intent_id=intent_id,
                broker_order_id=None,
                symbol=str(code),
                side=side,
                qty=int(shares),
                price=float(normalized_trigger_price),
                http_status=None,
                rejection_reason=payload_validation.reason,
            )
            append_order_journal({
                "event": "REJECTED",
                "intent_id": intent_id,
                "kind": "stop",
                "symbol": str(code),
                "side": side,
                "qty": int(shares),
                "trigger_price": float(normalized_trigger_price),
                "hold_id": hold_id,
                "http_status": None,
                "result": None,
                "rejection_reason": payload_validation.reason,
                **_build_stop_route_journal_fields(),
                "exchange": None if exchange is None else int(exchange),
                "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
                "is_production": bool(self.is_production),
            })
            return self._wrap_submission_result(
                submission,
                side=side,
                cash_margin=cash_margin,
                request_sent=False,
                trigger_price=float(normalized_trigger_price),
            )

        expected_close_positions = data.get("ClosePositions")
        res = self._api_request("POST", "sendorder", json=data, timeout=10)
        submission = classify_submission_response(
            intent_id=intent_id,
            symbol=str(code),
            side=side,
            qty=shares,
            price=float(normalized_trigger_price),
            response=res,
        )
        if submission.status == SubmissionStatus.ACCEPTED:
            order_id = submission.broker_order_id
            append_order_journal({
                "event": "ACCEPTED",
                "intent_id": intent_id,
                "kind": "stop",
                "symbol": str(code),
                "side": side,
                "qty": int(shares),
                "trigger_price": float(normalized_trigger_price),
                "hold_id": hold_id,
                "order_id": order_id,
                "http_status": submission.http_status,
                "result": submission.result_code,
                **_build_stop_route_journal_fields(),
                "exchange": None if exchange is None else int(exchange),
                "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
                "is_production": bool(self.is_production),
            })
            confirmed = False
            confirmation_reason = None
            confirmation_details = None
            if order_id:
                confirmed, confirmation_reason, confirmation_details = self._confirm_stop_order_submission(
                    order_id=order_id,
                    expected_qty=int(shares),
                    expected_trigger_price=float(normalized_trigger_price),
                    expected_close_positions=expected_close_positions,
                    side=side,
                    exchange=exchange,
                    margin_trade_type=margin_trade_type,
                )
            if confirmed:
                print(f"🛑 逆指値注文（ストップロス）を設定しました (ID: {order_id}) - {code} {shares}株 Trigger: {trigger_price}")
                return self._wrap_submission_result(
                    submission,
                    side=side,
                    cash_margin=cash_margin,
                    request_sent=True,
                    trigger_price=float(normalized_trigger_price),
                    confirmed=True,
                )

            confirmation_reason = confirmation_reason or "stop_order_confirmation_unavailable"
            append_order_journal({
                "event": "UNKNOWN",
                "intent_id": intent_id,
                "kind": "stop",
                "symbol": str(code),
                "side": side,
                "qty": int(shares),
                "trigger_price": float(normalized_trigger_price),
                "hold_id": hold_id,
                "order_id": order_id,
                "http_status": submission.http_status,
                "result": submission.result_code,
                "confirmation_reason": confirmation_reason,
                "confirmation_details": confirmation_details,
                **_build_stop_route_journal_fields(),
                "exchange": None if exchange is None else int(exchange),
                "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
                "is_production": bool(self.is_production),
            })
            print(
                "⚠️ 逆指値注文は sendorder で受理されましたが、orders API の確認に失敗したため "
                f"armed にしませんでした: {confirmation_reason}"
            )
            return self._wrap_submission_result(
                submission,
                side=side,
                cash_margin=cash_margin,
                request_sent=True,
                trigger_price=float(normalized_trigger_price),
                confirmed=False,
                confirmation_reason=confirmation_reason,
            )
        if submission.status == SubmissionStatus.REJECTED:
            append_order_journal({
                "event": "REJECTED",
                "intent_id": intent_id,
                "kind": "stop",
                "symbol": str(code),
                "side": side,
                "qty": int(shares),
                "trigger_price": float(normalized_trigger_price),
                "hold_id": hold_id,
                "http_status": submission.http_status,
                "rejection_reason": submission.rejection_reason,
                "result": submission.result_code,
                **_build_stop_route_journal_fields(),
                "exchange": None if exchange is None else int(exchange),
                "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
                "is_production": bool(self.is_production),
            })
            print(f"⚠️ 逆指値注文エラー: {submission.rejection_reason}")
            return self._wrap_submission_result(
                submission,
                side=side,
                cash_margin=cash_margin,
                request_sent=True,
                trigger_price=float(normalized_trigger_price),
            )
        append_order_journal({
            "event": "UNKNOWN",
            "intent_id": intent_id,
            "kind": "stop",
            "symbol": str(code),
            "side": side,
            "qty": int(shares),
            "trigger_price": float(normalized_trigger_price),
            "hold_id": hold_id,
            "http_status": submission.http_status,
            "response_text": submission.response_text,
            "rejection_reason": submission.rejection_reason,
            **_build_stop_route_journal_fields(),
            "exchange": None if exchange is None else int(exchange),
            "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
            "is_production": bool(self.is_production),
        })
        return self._wrap_submission_result(
            submission,
            side=side,
            cash_margin=cash_margin,
            request_sent=True,
            trigger_price=float(normalized_trigger_price),
        )

    def wait_for_execution(self, order_id: str, timeout_sec: int = 30) -> ExecutionWaitResult:
        """ 注文が約定（または失敗）するまで待機する """
        print(f"⏳ 注文 ID: {order_id} の約定を待機中...")
        start_time = time.time()
        last_details = None
        while time.time() - start_time < timeout_sec:
            details = self.get_order_details(order_id)
            if details:
                last_details = self._enrich_order_details_with_parse(details)
                parsed = parse_kabucom_order(last_details)
                if parsed.process_state == OrderProcessState.TERMINAL:
                    if parsed.cumulative_qty > 0:
                        last_details["Qty"] = parsed.cumulative_qty
                        last_details["Price"] = parsed.average_fill_price if parsed.average_fill_price is not None else details.get("Price")
                    if parsed.terminal_reason == OrderTerminalReason.FILLED:
                        print(f"✨ 注文 ID: {order_id} 全部約定しました。")
                    elif parsed.terminal_reason == OrderTerminalReason.CANCELLED:
                        print(f"⚠️ 注文 ID: {order_id} は取消完了です。")
                    elif parsed.terminal_reason == OrderTerminalReason.EXPIRED:
                        print(f"❌ 注文 ID: {order_id} は失効しました。")
                    elif parsed.terminal_reason == OrderTerminalReason.REJECTED:
                        print(f"❌ 注文 ID: {order_id} は発注エラーで終了しました。")
                    return self._build_wait_result(last_details, order_id=order_id)
                if parsed.process_state == OrderProcessState.UNKNOWN:
                    print(f"⚠️ 注文 ID: {order_id} の状態が不明です。")
                    return self._build_wait_result(
                        last_details,
                        order_id=order_id,
                        unresolved=True,
                        unresolved_reason="unknown_state",
                    )
            time.sleep(2)
        print(f"⚠️ 注文 ID: {order_id} の約定確認がタイムアウトしました。ゾンビ処理化を防ぐため取消要求を送信します。")
        cancel_result = self.cancel_order(order_id)
        if isinstance(cancel_result, CancelResult):
            if bool(cancel_result):
                print("✅ タイムアウト注文の強制取消要求を送信しました。")
            elif cancel_result.terminal_status == CancelTerminalStatus.FILLED_BEFORE_CANCEL:
                print(f"⚠️ 注文 ID: {order_id} は取消要求より先に約定していました。")
            else:
                print(f"⚠️ 取消要求の送信に失敗しました（手動で約定状況を確認してください）")
        elif cancel_result:
            print("✅ タイムアウト注文の強制取消要求を送信しました。")
        else:
            print(f"⚠️ 取消要求の送信に失敗しました（手動で約定状況を確認してください）")
        terminal_details = self._confirm_terminal_order_state(order_id, timeout_sec=5)
        if terminal_details:
            terminal_details = self._enrich_order_details_with_parse(terminal_details)
            parsed = parse_kabucom_order(terminal_details)
            print(f"✅ 注文 ID: {order_id} の終端状態を確認しました ({parsed.terminal_reason.value if parsed.terminal_reason else 'unknown'})。")
            return self._build_wait_result(terminal_details, order_id=order_id)
        print(f"⚠️ 注文 ID: {order_id} の取消完了が規定時間内に確認できませんでした。ゾンビポジションに注意してください。")
        return self._build_wait_result(
            last_details,
            order_id=order_id,
            unresolved=True,
            unresolved_reason="timeout_unconfirmed",
        )

    # ---------------------------------------------------------
    # インターフェース互換性のためのファイル保存・ログ機能
    # (API運用でも履歴CSVやダッシュボード観測用ログは残す)
    # ---------------------------------------------------------
    def save_positions(self, portfolio: list):
        """ リアルAPIでは自動でポジションが残るが、ダッシュボード互換性のためにファイルにも書き出す """
        from core.config import PORTFOLIO_FILE
        environment = getattr(self, "environment", None)
        broker_environment = getattr(environment, "value", None)
        if not broker_environment:
            broker_environment = "live" if getattr(self, "is_production", False) else "test"
        write_portfolio_state(
            PORTFOLIO_FILE,
            portfolio,
            metadata={
                "source": "kabucom_broker",
                "broker_environment": broker_environment,
                "broker_account_type": self._resolve_account_type(),
                "broker_product": "margin",
            },
        )

    def save_portfolio(self, portfolio: list):
        """auto_trade.py との互換性のためのエイリアス（M-4修正）"""
        self.save_positions(portfolio)

    def save_account(self, account: dict):
        """ 同上 """
        from core.config import ACCOUNT_FILE
        atomic_write_json(ACCOUNT_FILE, account)

    def log_trade(self, trade_record: dict):
        append_csv_rows(HISTORY_FILE, [trade_record])

    def log_execution_summary(self, summary_record: dict):
        import os
        total_assets = summary_record['total_assets_yen']
        actions = summary_record['actions']
        
        print("\n" + "="*50)
        env_label = "[REAL API]" if self.is_production else "[TEST API]"
        print(f" 📊 実行サマリー {env_label} (レジーム: {summary_record['regime']})")
        print("="*50)
        print("\n【今回のアクション】")
        
        if actions:
            for act in actions: print(f" ✔ {act}")
        else:
            print(" - アクションなし (保有維持 / 新規見送り)")
            
        print("\n【現在の保有株式 (API同期値)】")
        portfolio = summary_record.get('portfolio', [])
        if portfolio:
            for p in portfolio:
                cp = float(p.get('current_price', p['buy_price']))
                bp = float(p['buy_price'])
                val = cp * int(p['shares'])
                profit_pct = (cp - bp) / bp * 100 if bp > 0 else 0
                print(f" 🔹 {p['code']} {p['name']}\n    数量: {p['shares']}株 | 現在値: {cp:,.1f}円 | 評価額: {val:,.0f}円 | 損益: {profit_pct:+.2f}%")
        else:
            print(" - 保有なし")

        if any(key in summary_record for key in ("equity_yen", "margin_buying_power_yen", "stock_buying_power_yen")):
            print("\n【口座ステータス (Broker Snapshot)】")
            if summary_record.get("equity_yen") is not None:
                print(f" 👑 推定純資産: {summary_record['equity_yen']:>10,.0f}円")
            if summary_record.get("margin_buying_power_yen") is not None:
                print(f" 💳 信用余力:   {summary_record['margin_buying_power_yen']:>10,.0f}円")
            if summary_record.get("stock_buying_power_yen") is not None:
                print(f" 💰 現物余力:   {summary_record['stock_buying_power_yen']:>10,.0f}円")
            print(f" 📈 保有評価額: {summary_record['stock_value_yen']:>10,.0f}円")
            print(f" 🧮 合計資産額: {total_assets:>10,.0f}円")
        else:
            print("\n【口座ステータス (API取得値)】")
            print(f" 💰 現金残高:   {summary_record['cash_yen']:>10,.0f}円")
            print(f" 📈 株式評価額: {summary_record['stock_value_yen']:>10,.0f}円")
            print(f" 👑 合計資産額: {total_assets:>10,.0f}円")
        print("="*50 + "\n")
        
        actions_str = " | ".join(actions) if actions else "アクションなし"
        df_log = pd.DataFrame([{
            "time": summary_record.get('time', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            "regime": summary_record.get('regime', 'UNKNOWN'),
            "total_assets": total_assets,
            "cash": summary_record.get('cash_yen', 0),
            "stock_value": summary_record.get('stock_value_yen', 0),
            "actions": actions_str
        }])
        atomic_write_csv(EXECUTION_LOG_FILE, df_log)
        append_jsonl(EXECUTION_AUDIT_LOG_FILE, {
            "event_type": "execution_summary",
            "source": "kabucom_broker",
            "logged_at": datetime.now().isoformat(),
            "regime": summary_record.get('regime', 'UNKNOWN'),
            "total_assets": total_assets,
            "cash": summary_record.get('cash_yen', 0),
            "stock_value": summary_record.get('stock_value_yen', 0),
            "actions": actions,
            "portfolio": summary_record.get('portfolio', []),
        })
        
        # [Professional Audit] 実行ログの肥大化防止（ローテーション）
        from core.file_io import rotate_csv_if_large
        rotate_csv_if_large(EXECUTION_LOG_FILE, max_size_mb=5)
        rotate_csv_if_large(EXECUTION_AUDIT_LOG_FILE, max_size_mb=5)
