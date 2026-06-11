import requests
import json
import pandas as pd
from datetime import datetime
import time
import threading
from core.broker import BaseBroker
from core.config import KABUCOM_API_PASSWORD, HISTORY_FILE, EXECUTION_LOG_FILE
from core.log_setup import send_discord_notify
from core.file_io import atomic_write_json, atomic_write_csv, safe_read_csv, append_csv_rows
from core.order_journal import append_order_journal
from core.kabucom_order_state import (
    OrderProcessState,
    OrderTerminalReason,
    SubmissionStatus,
    classify_submission_response,
    parse_kabucom_order,
)
from core.kabucom_quote import parse_board_quote

class KabucomBroker(BaseBroker):
    """
    auカブコム証券（kabuステーションAPI）と通信するBrokerクラス。
    is_production = False の場合は検証環境（ポート18081）を使用し、
    True の場合は本番環境（ポート18080）を使用してリアルマネーで売買を行う。
    """
    
    def __init__(self, is_production=False):
        self.is_production = is_production
        self.port = 18080 if is_production else 18081
        self.base_url = f"http://localhost:{self.port}/kabusapi"
        self.password = KABUCOM_API_PASSWORD
        self.token = None
        # [Professional Audit] マルチスレッド環境での認証競合を防ぐためのロック
        self._auth_lock = threading.Lock()
        # [Professional Audit] Sessionを永続化し、HTTP Keep-Aliveを有効にして遅延を最小化する
        self.session = requests.Session()
        # [Professional Audit] API予算管理 (1時間5000回を上限の目安とする)
        self.request_count = 0
        self.last_reset_time = time.time()
        
        env_name = "【本番API】" if is_production else "【検証API】"
        if not self.password:
            print(f"⚠️ {env_name} パスワード(KABUCOM_API_PASSWORD)が.envに設定されていません。")
        else:
            self._authenticate()

    def _authenticate(self):
        """ kabuステーションAPIからトークンを取得する """
        with self._auth_lock:
            url = f"{self.base_url}/token"
            headers = {'Content-Type': 'application/json'}
            data = {'APIPassword': self.password}
            
            try:
                res = self.session.post(url, headers=headers, json=data, timeout=10)
                if res.status_code == 200:
                    self.token = res.json().get('Token')
                    print(f"✅ auカブコムAPI 認証成功 (Port:{self.port})")
                else:
                    print(f"⚠️ 認証失敗: {res.status_code} {res.text}")
            except Exception as e:
                env_name = "本番" if self.is_production else "検証用"
                print(f"⚠️ kabuステーション({env_name})に接続できません。アプリが起動し、APIが有効化されているか確認してください。({e})")

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
        allow_transient_retry = method == "GET"
        # [Professional Audit] API予算管理と自動スロットリング
        now = time.time()
        if now - self.last_reset_time > 3600:
            self.request_count = 0
            self.last_reset_time = now
        self.request_count += 1
        if self.request_count > 4800:
            print(f"⚠️ API Request Budget Alert: {self.request_count} requests/hr. Throttling...")
            time.sleep(0.5)

        for retry in [False, True]:
            headers = self._get_headers(force_refresh=retry)
            # [Professional Audit] GET のみ指数バックオフを許可する。POST/PUT の無条件再送は重複注文を招くため禁止。
            delays = [0, 1, 2, 4] if allow_transient_retry else [0]
            for delay in delays:
                if delay > 0: time.sleep(delay)
                try:
                    res = self.session.request(method, url, headers=headers, **kwargs)
                    if res.status_code == 200:
                        return res
                    elif res.status_code == 401 and not retry:
                        break # 内側のループを抜けて、認証をリフレッシュしてリトライ
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
            res = self._api_request("GET", "symbol/7203@1", timeout=5)
            if res and res.status_code == 200:
                # サーバーの現在時刻はレスポンスの 'TradingDate' ではなく、本来はAPIのリファレンスから
                # 明示的な「サーバー時刻」エンドポイントを叩くべきだが、多くのAPIではレスポンスヘッダや
                # 時価情報の更新時刻が基準となる。ここでは簡易的にトヨタの時価時刻を基準とする。
                # 実際の KabuステーションAPI には /common/servertime のようなものがないため。
                time_str = res.json().get('CurrentPriceTime', "")
                if time_str:
                    # 時刻のみ(HH:mm:ss)の場合は当日の日付を付加
                    today = datetime.now(JST).date()
                    full_time_str = f"{today} {time_str}"
                    return datetime.strptime(full_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=JST)
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
                if not isinstance(orders, list):
                    return None
                active = []
                has_unknown = False
                unresolved_order_ids = []
                for order in orders:
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
        if not self.is_production:
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

        return {
            "cash": 0.0,
            "stock_buying_power": stock_buying_power if cash_ok else 0.0,
            "margin_buying_power": margin_buying_power if margin_ok else 0.0,
            "configured_risk_capital": 0.0,
            "realized_pnl_today": 0.0,
            "unrealized_pnl": 0.0,
            "gross_position_notional": 0.0,
            "net_position_notional": 0.0,
            "broker_position_count": 0,
            "wallet_snapshot_incomplete": not (cash_ok and margin_ok),
            "wallet_cash_ok": cash_ok,
            "wallet_margin_ok": margin_ok,
        }

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

        # 2. ローカルデータマージ (中身は以前と同じ)
        from core.config import PORTFOLIO_FILE
        local_data = {}
        managed_execution_ids = set()
        df_local = safe_read_csv(PORTFOLIO_FILE)
        if not df_local.empty:
            for _, row in df_local.iterrows():
                row_data = row.to_dict()
                local_data[str(row['code'])] = row_data
                execution_id = str(row_data.get("execution_id") or "").strip()
                if execution_id:
                    managed_execution_ids.add(execution_id)

        final_positions = []
        for p in api_positions:
            if p.get('LeavesQty', 0) == 0: continue
            code_sym = str(p['Symbol'])
            current_price = float(p['CurrentPrice']) if p.get('CurrentPrice') is not None else 0.0
            leaves_qty = int(p.get('LeavesQty', 0) or 0)
            hold_qty = int(p.get('HoldQty', 0) or 0)
            available_qty = max(0, leaves_qty - hold_qty)
            execution_id = str(p.get('ExecutionID') or "").strip() or None
            
            if code_sym in local_data:
                hist = local_data[code_sym]
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
            elif code_sym in local_data:
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
                "hold_qty": hold_qty if p.get('HoldQty') is not None else None,
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

    def _build_close_positions_for_symbol(self, code: str, requested_qty: int) -> dict | None:
        """信用返済用に、同一銘柄・同一Exchange・同一MarginTradeTypeの建玉へ数量を安全に割り当てる。"""
        if requested_qty <= 0:
            return {"close_positions": [], "exchange": None, "margin_trade_type": None}
        try:
            positions = self.get_positions()
        except Exception as exc:
            print(f"⚠️ 返済建玉の再取得に失敗しました: {exc}")
            return None

        matches = [p for p in positions if p.get("code") == str(code) and p.get("hold_id")]
        if not matches:
            return None

        candidate_exchange = None
        candidate_margin_trade_type = None
        for position in matches:
            exchange = position.get("exchange")
            margin_trade_type = position.get("margin_trade_type")
            if exchange is None or margin_trade_type is None:
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
                leaves_qty = int(position.get("leaves_qty", position.get("shares", 0)) or 0)
                hold_qty = int(position.get("hold_qty", 0) or 0)
                available_qty = max(0, leaves_qty - hold_qty)
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

    def execute_market_order(self, code: str, shares: int, side: str, price: float = 0, close_positions: list = None, exchange: int | None = None, margin_trade_type: int | None = None) -> str:
        """
        現物・信用の成行・指値注文を発注する。
        side: "1" (売), "2" (買)
        close_positions: [{"HoldID": "...", "Qty": 100}, ...] (信用返済時)
        """
        if not self.token: return None
        import os
        intent_id = f"market-{time.time_ns()}"
        
        cash_margin = 2 if side == "2" else 3
        # 買付余力(2) または 信用売(3)
        if margin_trade_type is None:
            margin_trade_type = 3 if side == "2" else None
        if exchange is None:
            if side == "2":
                try:
                    exchange = int(os.environ.get("KABUCOM_ORDER_EXCHANGE", 1))
                except (TypeError, ValueError):
                    exchange = 1
            else:
                exchange = None
        if side == "1" and (exchange is None or margin_trade_type is None):
            print(f"⚠️ 返済注文のExchange/MarginTradeTypeが未確定のため発注を中止します: {code}")
            return None
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
            "Password": self.password,
            "Symbol": code,
            "Exchange": int(exchange),
            "SecurityType": 1,  # 1: 株式
            "Side": side,       # 1: 売, 2: 買
            "CashMargin": cash_margin,
            "MarginTradeType": margin_trade_type,
            "DelivType": 0 if cash_margin == 2 else 2,
            "AccountType": int(os.environ.get("KABUCOM_ACCOUNT_TYPE", 4)),
            "Qty": shares,
            "FrontOrderType": front_order_type,
            "Price": float(normalized_price) if front_order_type == 20 else 0,
            "ExpireDay": 0
        }

        # 信用返済(CashMargin=3)の場合は ClosePositions を付与
        if cash_margin == 3 and close_positions:
            data["ClosePositions"] = close_positions
        elif cash_margin == 3:
            print(f"⚠️ 信用返済の返済建玉IDが取得できないため、発注を中止します: {code}")
            return None

        res = self._api_request("POST", "sendorder", json=data, timeout=10)
        submission = classify_submission_response(
            intent_id=intent_id,
            symbol=str(code),
            side=side,
            qty=shares,
            price=float(normalized_price) if front_order_type == 20 else 0.0,
            response=res,
        )
        self._last_submission_result = submission
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
            return order_id
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
            return None
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
        return None

    def cancel_order(self, order_id: str) -> bool:
        """ API経由で注文を取り消す (オートキャンセル機構用) """
        if not self.token: return False
        cancel_data = {"OrderId": order_id, "Password": self.password}
        append_order_journal({
            "event": "CANCEL_REQUESTED",
            "order_id": order_id,
            "is_production": bool(self.is_production),
        })
        
        res = self._api_request("PUT", "cancelorder", json=cancel_data, timeout=10)
        submission = classify_submission_response(
            intent_id=f"cancel-{time.time_ns()}",
            symbol="",
            side="",
            qty=0,
            price=None,
            response=res,
            allow_missing_order_id=True,
        )
        if submission.status == SubmissionStatus.ACCEPTED:
            confirmed = self._confirm_terminal_order_state(order_id, timeout_sec=5)
            append_order_journal({
                "event": "CANCELLED" if confirmed else "UNKNOWN",
                "order_id": order_id,
                "http_status": submission.http_status,
                "result": submission.result_code,
                "is_production": bool(self.is_production),
                "confirmed": bool(confirmed),
            })
            return bool(confirmed)
        if submission.status == SubmissionStatus.REJECTED:
            append_order_journal({
                "event": "REJECTED",
                "order_id": order_id,
                "http_status": submission.http_status,
                "rejection_reason": submission.rejection_reason,
                "is_production": bool(self.is_production),
            })
            return False
        append_order_journal({
            "event": "UNKNOWN",
            "order_id": order_id,
            "http_status": submission.http_status,
            "response_text": submission.response_text,
            "rejection_reason": submission.rejection_reason,
            "is_production": bool(self.is_production),
        })
        return False

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

    def get_order_details(self, order_id: str) -> dict:
        """ 注文詳細（ステータス・約定単価等）を取得する """
        if not self.token or not order_id: return None
        res = self._api_request("GET", f"orders?id={order_id}", timeout=10)
        if res and res.status_code == 200:
            orders = res.json()
            if orders and len(orders) > 0:
                return orders[0]
        return None

    # --- [New] リアルタイム監視用の銘柄登録・解除・板情報取得 ---
    def register_symbols(self, symbols: list):
        """ 
        kabuステーションAPI側に銘柄を監視登録する。
        仕様上1回あたり50銘柄までのため、チャンク分割して実行する。
        """
        if not self.token: return False
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
        res = self._api_request("PUT", "unregister/all", timeout=10)
        if res and res.status_code == 200:
             print("🧹 [API] 全銘柄の監視登録を解除しました。")
             return True
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

    def execute_chase_order(self, code: str, shares: int, side: str, atr: float = 0) -> dict:
        """
        指値を最良気配に追従（Chase）させながら発注し、一定時間で強制執行するOMS機能。
        [Professional Audit] 1. 部分約定の合算(VWAP), 2. 待機時間の短縮, 3. 決済指定(HoldID)
        """
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

            order_id = self.execute_market_order(
                code,
                remaining_shares,
                side,
                price=limit_price,
                close_positions=close_pos_list,
                exchange=None if close_route is None else close_route.get("exchange"),
                margin_trade_type=None if close_route is None else close_route.get("margin_trade_type"),
            )
            last_submission = getattr(self, "_last_submission_result", None)
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
                                "execution_ids": tuple(total_execution_ids),
                                "execution_id": total_execution_ids[0] if total_execution_ids else None,
                            }
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
                    break

            if terminal_details:
                parsed = parse_kabucom_order(terminal_details)
                last_terminal_reason = parsed.terminal_reason
                if parsed.process_state == OrderProcessState.UNKNOWN:
                    unresolved = True
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
            return {
                "order_id": last_order_id,
                "submission_status": None if last_submission is None else last_submission.status.value,
                "process_state": OrderProcessState.UNKNOWN.value,
                "terminal_reason": None,
                "Qty": total_filled_qty,
                "filled_qty": total_filled_qty,
                "Price": avg_price,
                "average_price": avg_price if total_filled_qty > 0 else None,
                "remaining_qty": max(0, shares - total_filled_qty),
                "Symbol": code,
                "has_partial_fill": total_filled_qty > 0 and total_filled_qty < shares,
                "execution_ids": tuple(total_execution_ids),
                "execution_id": total_execution_ids[0] if total_execution_ids else None,
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
                    return {
                        "order_id": last_order_id,
                        "submission_status": None if last_submission is None else last_submission.status.value,
                        "process_state": OrderProcessState.UNKNOWN.value,
                        "terminal_reason": None,
                        "Qty": total_filled_qty,
                        "filled_qty": total_filled_qty,
                        "Price": total_filled_value / total_filled_qty if total_filled_qty > 0 else 0.0,
                        "average_price": total_filled_value / total_filled_qty if total_filled_qty > 0 else None,
                        "remaining_qty": remaining_shares,
                        "Symbol": code,
                        "has_partial_fill": total_filled_qty > 0 and total_filled_qty < shares,
                        "rejection_reason": "close_positions_unavailable",
                        "unresolved": True,
                    }
                close_pos_list = close_route["close_positions"]

            order_id = self.execute_market_order(
                code,
                remaining_shares,
                side,
                price=force_price,
                close_positions=close_pos_list,
                exchange=None if close_route is None else close_route.get("exchange"),
                margin_trade_type=None if close_route is None else close_route.get("margin_trade_type"),
            )
            last_order_id = order_id or last_order_id
            last_submission = getattr(self, "_last_submission_result", last_submission)
            if order_id:
                f_details = self.wait_for_execution(order_id, timeout_sec=20)
                if f_details:
                    parsed = parse_kabucom_order(f_details)
                    if parsed.process_state == OrderProcessState.UNKNOWN:
                        unresolved = True
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

        avg_price = total_filled_value / total_filled_qty if total_filled_qty > 0 else 0.0
        terminal_reason = None if last_terminal_reason is None else last_terminal_reason.value
        process_state = OrderProcessState.UNKNOWN.value if unresolved else (
            OrderProcessState.TERMINAL.value if total_filled_qty > 0 or terminal_reason is not None else OrderProcessState.UNKNOWN.value
        )
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
            "execution_ids": tuple(total_execution_ids),
            "execution_id": total_execution_ids[0] if total_execution_ids else None,
        }

    def execute_stop_order(self, code: str, shares: int, side: str, trigger_price: float, hold_id: str = None, exchange: int | None = None, margin_trade_type: int | None = None) -> str:
        """
        逆指値（ストップロス）注文を発注する。
        side: "1" (売), "2" (買)
        trigger_price: トリガー価格
        """
        if not self.token: return None
        import os
        intent_id = f"stop-{time.time_ns()}"

        # ストップロス売り(1) または ストップロス買い(2)
        cash_margin = 2 if side == "2" else 3
        if margin_trade_type is None:
            margin_trade_type = 3 if side == "2" else None
        if exchange is None:
            if side == "2":
                try:
                    exchange = int(os.environ.get("KABUCOM_ORDER_EXCHANGE", 1))
                except (TypeError, ValueError):
                    exchange = 1
            elif hold_id:
                route = self._resolve_hold_route(hold_id)
                if route:
                    exchange = route["exchange"]
                    margin_trade_type = route["margin_trade_type"]
        if side == "1" and (exchange is None or margin_trade_type is None):
            print(f"⚠️ 逆指値の返済建玉ルートが不明なため、発注を中止します: {code}")
            return None
        if margin_trade_type is None:
            margin_trade_type = 3
        
        # 逆指値の設定
        # 公式仕様の UnderOver に合わせる。
        # 1: 以下, 2: 以上
        # 売り（損切り）の場合は現在値が trigger_price 以下になったら成行
        under_over = 1 if side == "1" else 2
        from core.logic import normalize_tick_size
        normalized_trigger_price = normalize_tick_size(trigger_price, is_buy=(side == "2"))

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
            "Password": self.password,
            "Symbol": code,
            "Exchange": int(exchange),
            "SecurityType": 1,
            "Side": side,
            "CashMargin": cash_margin,
            "MarginTradeType": margin_trade_type,
            "DelivType": 0 if cash_margin == 2 else 2,
            "AccountType": int(os.environ.get("KABUCOM_ACCOUNT_TYPE", 4)),
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

        if cash_margin == 3 and hold_id:
            data["ClosePositions"] = [{"HoldID": hold_id, "Qty": shares}]
        elif cash_margin == 3:
            print(f"⚠️ 逆指値の返済建玉IDが取得できないため、発注を中止します: {code}")
            return None

        res = self._api_request("POST", "sendorder", json=data, timeout=10)
        submission = classify_submission_response(
            intent_id=intent_id,
            symbol=str(code),
            side=side,
            qty=shares,
            price=float(normalized_trigger_price),
            response=res,
        )
        self._last_submission_result = submission
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
                "exchange": None if exchange is None else int(exchange),
                "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
                "is_production": bool(self.is_production),
            })
            print(f"🛑 逆指値注文（ストップロス）を設定しました (ID: {order_id}) - {code} {shares}株 Trigger: {trigger_price}")
            return order_id
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
                "exchange": None if exchange is None else int(exchange),
                "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
                "is_production": bool(self.is_production),
            })
            print(f"⚠️ 逆指値注文エラー: {submission.rejection_reason}")
            return None
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
            "exchange": None if exchange is None else int(exchange),
            "margin_trade_type": None if margin_trade_type is None else int(margin_trade_type),
            "is_production": bool(self.is_production),
        })
        return None

    def wait_for_execution(self, order_id: str, timeout_sec: int = 30) -> dict:
        """ 注文が約定（または失敗）するまで待機する """
        print(f"⏳ 注文 ID: {order_id} の約定を待機中...")
        start_time = time.time()
        last_details = None
        while time.time() - start_time < timeout_sec:
            details = self.get_order_details(order_id)
            if details:
                parsed = parse_kabucom_order(details)
                last_details = dict(details)
                last_details["__parsed_process_state__"] = parsed.process_state.value
                last_details["__parsed_terminal_reason__"] = None if parsed.terminal_reason is None else parsed.terminal_reason.value
                last_details["__parsed_cumulative_qty__"] = parsed.cumulative_qty
                last_details["__parsed_order_qty__"] = parsed.order_qty
                last_details["__parsed_average_fill_price__"] = parsed.average_fill_price
                last_details["__parsed_has_partial_fill__"] = parsed.has_partial_fill
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
                    return last_details
                if parsed.process_state == OrderProcessState.UNKNOWN:
                    print(f"⚠️ 注文 ID: {order_id} の状態が不明です。")
                    return last_details
            time.sleep(2)
        print(f"⚠️ 注文 ID: {order_id} の約定確認がタイムアウトしました。ゾンビ処理化を防ぐため取消要求を送信します。")
        if self.cancel_order(order_id):
            print("✅ タイムアウト注文の強制取消要求を送信しました。")
        else:
            print(f"⚠️ 取消要求の送信に失敗しました（手動で約定状況を確認してください）")
        terminal_details = self._confirm_terminal_order_state(order_id, timeout_sec=5)
        if terminal_details:
            parsed = parse_kabucom_order(terminal_details)
            if parsed.cumulative_qty > 0:
                terminal_details["Qty"] = parsed.cumulative_qty
                terminal_details["Price"] = parsed.average_fill_price if parsed.average_fill_price is not None else terminal_details.get("Price")
            print(f"✅ 注文 ID: {order_id} の終端状態を確認しました ({parsed.terminal_reason.value if parsed.terminal_reason else 'unknown'})。")
            return terminal_details
        print(f"⚠️ 注文 ID: {order_id} の取消完了が規定時間内に確認できませんでした。ゾンビポジションに注意してください。")
        return last_details

    # ---------------------------------------------------------
    # インターフェース互換性のためのファイル保存・ログ機能
    # (API運用でも履歴CSVやダッシュボード観測用ログは残す)
    # ---------------------------------------------------------
    def save_positions(self, portfolio: list):
        """ リアルAPIでは自動でポジションが残るが、ダッシュボード互換性のためにファイルにも書き出す """
        from core.config import PORTFOLIO_FILE
        df = pd.DataFrame(portfolio)
        atomic_write_csv(PORTFOLIO_FILE, df)

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
        
        # [Professional Audit] 実行ログの肥大化防止（ローテーション）
        from core.file_io import rotate_csv_if_large
        rotate_csv_if_large(EXECUTION_LOG_FILE, max_size_mb=5)
