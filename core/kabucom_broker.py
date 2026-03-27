import requests
import json
import pandas as pd
from datetime import datetime
import time
import threading
from core.broker import BaseBroker
from core.config import KABUCOM_API_PASSWORD, HISTORY_FILE, EXECUTION_LOG_FILE
from core.log_setup import send_discord_notify
from core.file_io import atomic_write_json, atomic_write_csv, safe_read_csv

class KabucomBroker(BaseBroker):
    """
    auカブコム証券（kabuステーションAPI）と通信するBrokerクラス。
    is_production = False の場合は検証環境（ポート8081）を使用し、
    True の場合は本番環境（ポート8080）を使用してリアルマネーで売買を行う。
    """
    
    def __init__(self, is_production=False):
        self.is_production = is_production
        self.port = 8080 if is_production else 8081
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
            # [Professional Audit] 指数バックオフによるサーバー側エラー(5xx)への耐性強化
            for delay in [0, 1, 2, 4]:
                if delay > 0: time.sleep(delay)
                try:
                    res = self.session.request(method, url, headers=headers, **kwargs)
                    if res.status_code == 200:
                        return res
                    elif res.status_code == 401 and not retry:
                        break # 内側のループを抜けて、認証をリフレッシュしてリトライ
                    elif res.status_code in [500, 502, 503, 504]:
                        print(f"⚠️ API Server Error ({res.status_code}). Retrying in {delay*2 if delay>0 else 1}s...")
                        continue
                    else:
                        return res
                except Exception as e:
                    if delay == 4:
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

    def get_active_orders(self) -> list:
        """ 現在執行中（未約定・待機中等）の注文一覧を取得する """
        if not self.token: return []
        try:
            # [Professional Audit] 共通ラッパーを使用して認証・リトライの恩恵を受ける
            res = self._api_request("GET", "orders", timeout=10)
            if res and res.status_code == 200:
                orders = res.json()
                # State 3:受付, 4:受付済, 5:執行中 のものを抽出
                active = [o for o in orders if o.get('State') in [3, 4, 5]]
                return active
            return []
        except:
            return []

    def get_account_balance(self) -> dict:
        """ 現金残高（買付余力）の取得 """
        if not self.token: return {"cash": 0}
        
        res = self._api_request("GET", "wallet/cash", timeout=10)
        if res and res.status_code == 200:
            data = res.json()
            cash = data.get('StockAccountWallet', 0)
            return {"cash": float(cash)}
        
        print(f"⚠️ 余力取得エラー: {res.text if res else 'No Response'}")
        return {"cash": 0}

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
        df_local = safe_read_csv(PORTFOLIO_FILE)
        if not df_local.empty:
            for _, row in df_local.iterrows():
                local_data[str(row['code'])] = row.to_dict()

        final_positions = []
        for p in api_positions:
            if p['LeavesQty'] == 0: continue
            code_sym = str(p['Symbol'])
            current_price = float(p['CurrentPrice'])
            
            if code_sym in local_data:
                hist = local_data[code_sym]
                local_buy_price = float(hist.get('buy_price', 0))
                api_buy_price = float(p['Price'])
                
                # --- [Phase 10] 株式分割・併合の自動検知同期 ---
                # APIの取得単価とローカルの取得単価に5%以上の乖離がある場合、分割等があったとみなす
                if local_buy_price > 0 and abs(1 - (api_buy_price / local_buy_price)) > 0.05:
                    adj_ratio = api_buy_price / local_buy_price
                    print(f"🔄 [Split Sync] {code_sym} の価格乖離({local_buy_price} -> {api_buy_price})を検知。記録を係数 {adj_ratio:.4f} で調整します。")
                    highest_price = float(hist.get('highest_price', current_price)) * adj_ratio
                else:
                    highest_price = float(hist.get('highest_price', current_price))
                
                highest_price = max(highest_price, current_price)
                buy_time = hist.get('buy_time', "Real API Position")
                # 【新規】分割利確済みフラグの復元
                partial_sold = hist.get('partial_sold', False)
            else:
                highest_price = current_price
                buy_time = "Real API Position"
                partial_sold = False

            final_positions.append({
                "code": code_sym, "name": p['SymbolName'], "shares": int(p['LeavesQty']),
                "buy_price": float(p['Price']), "current_price": current_price,
                "highest_price": round(highest_price, 1),
                "buy_time": buy_time,
                "partial_sold": partial_sold,
                "hold_id": p.get('ExecutionID') # 決済時に必須となる建玉ID
            })
        return final_positions

    def execute_market_order(self, code: str, shares: int, side: str, price: float = 0, hold_ids: list = None) -> str:
        """
        現物・信用の成行・指値注文を発注する。
        side: "1" (売), "2" (買)
        hold_ids: 決済時に指定する建玉IDのリスト (side="1" の時に指定)
        """
        if not self.token: return None
        
        cash_margin = 2 if side == "2" else 3
        # 買付余力(2) または 信用売(3)
        # [Professional Audit] 信用取引の決済(Close)を明示する
        
        front_order_type = 20 if price > 0 else 10  # 20:指値 10:成行
        
        data = {
            "Password": self.password,
            "Symbol": code,
            "Exchange": 1,      # 1: 東証
            "SecurityType": 1,  # 1: 株式
            "Side": side,       # 1: 売, 2: 買
            "CashMargin": cash_margin,
            "MarginTradeType": 3,
            "DelivType": 0,
            "AccountType": int(os.environ.get("KABUCOM_ACCOUNT_TYPE", 4)),
            "Qty": shares,
            "FrontOrderType": front_order_type,
            "Price": int(price),
            "ExpireDay": 0
        }

        if side == "1" and hold_ids:
            # [Professional Audit] 決済指定漏れによる両建て増殖バグの修正
            # 建玉を指定して返済（決済）注文を投げる
            data["ClosePositionOrder"] = [{"HoldID": h_id, "Qty": shares} for h_id in hold_ids]
            # ※ 単一の決済なら shares で良いが、複数に跨る場合は各々指定が必要。
            # 今回は単純化のため、上位で1建玉ごとに呼ぶか、同じ数量を割り当てる想定。

        res = self._api_request("POST", "sendorder", json=data, timeout=10)
        if res and res.status_code == 200:
            order_res = res.json()
            if order_res.get('Result') == 0:
                order_id = order_res.get('OrderId')
                env = "【本番】" if self.is_production else "【検証API】"
                act = "買い" if side == "2" else "売り"
                otype = "指値" if price > 0 else "成行"
                print(f"✅ {env} 注文受付完了 (ID: {order_id}) - {code} {shares}株 {act} ({otype})")
                return order_id
            else:
                print(f"⚠️ 注文拒否: {order_res}")
        return None

    def cancel_order(self, order_id: str) -> bool:
        """ API経由で注文を取り消す (オートキャンセル機構用) """
        if not self.token: return False
        cancel_url = f"{self.base_url}/cancelorder"
        cancel_data = {"OrderId": order_id, "Password": self.password}
        
        res = self._api_request("PUT", "cancelorder", json=cancel_data, timeout=10)
        if res and res.status_code == 200:
            order_res = res.json()
            return order_res.get('Result') == 0
        return False

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
                results[code] = {
                    "price": data.get('CurrentPrice'),
                    "prev_close": data.get('PreviousClose'),
                    "status": data.get('CurrentPriceStatus'),
                    "bid": data.get('BidPrice'),
                    "ask": data.get('AskPrice'),
                    "upper_limit": data.get('UpperLimit'),
                    "lower_limit": data.get('LowerLimit')
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
        total_filled_value = 0
        
        # [Professional Audit] 決済時の建玉特定
        hold_ids = []
        if side == "1":
            try:
                all_pos = self.get_positions()
                target_pos = [p for p in all_pos if str(p['code']) == str(code)]
                hold_ids = [p['hold_id'] for p in target_pos if p.get('hold_id')]
            except Exception as e:
                print(f"⚠️ 決済用建玉IDの取得に失敗しました: {e}")

        for attempt in range(1, 4):
            if remaining_shares <= 0: break
            time.sleep(0.2)
            
            board = self.get_board_data([code])
            b_info = board.get(str(code).replace(".T", ""))
            if not b_info: break
            
            c_price = b_info.get('price', 0)
            if side == "2" and c_price >= b_info.get('upper_limit', 999999):
                print(f"🚨 {code} はストップ高に達しているため、買い注文を中止します。")
                break
            if side == "1" and c_price <= b_info.get('lower_limit', 0):
                print(f"🚨 {code} はストップ安に達しているため、売り注文を中止します。")
                break

            if side == "2":
                limit_price = b_info.get('bid') or ((b_info.get('ask', 0) + b_info.get('price', 0))/2)
                limit_price = normalize_tick_size(limit_price, is_buy=True)
            else:
                limit_price = b_info.get('ask') or ((b_info.get('bid', 0) + b_info.get('price', 0))/2)
                limit_price = normalize_tick_size(limit_price, is_buy=False)
            
            if not limit_price or limit_price <= 0:
                 limit_price = b_info.get('price', 0)
            
            if not limit_price or limit_price <= 0:
                print(f"⚠️ {code} の有効な価格が取得できないため、追従を中断します。")
                break

            # 注文発注（売却時は建玉IDを指定）
            order_id = self.execute_market_order(code, remaining_shares, side, price=limit_price, hold_ids=hold_ids if side == "1" else None)
            if not order_id: break
            
            print(f"⏳ 追従試行 {attempt}/3: 価格 {limit_price:.1f} で {remaining_shares}株 待機中...")
            start_wait = time.time()
            current_order_filled = False
            
            # [Professional Audit] 待機時間を10秒から3秒に短縮（逆選択回避）
            while time.time() - start_wait < 3:
                details = self.get_order_details(order_id)
                if details:
                    state = details.get('State')
                    if state == 6: # 全部約定
                        print(f"✨ 注文 ID: {order_id} が全部約定しました。")
                        qty = int(details.get('CumQty', remaining_shares))
                        total_filled_qty += qty
                        total_filled_value += (float(details.get('Price', limit_price)) * qty)
                        remaining_shares = 0
                        current_order_filled = True
                        break
                time.sleep(1)
            
            if current_order_filled: break
            
            print(f"⏰ 待機時間終了。注文 ID: {order_id} を一度取り消して残数を確認します。")
            if self.cancel_order(order_id):
                time.sleep(0.5)
                for _ in range(5):
                    d = self.get_order_details(order_id)
                    if d and d.get('State') in [8, 9, 10, 6]:
                        cum_qty = int(d.get('CumQty', 0))
                        if cum_qty > 0:
                            print(f"⚠️ 注文 ID: {order_id} は一部約定（{cum_qty}株）していました。")
                            total_filled_qty += cum_qty
                            total_filled_value += (float(d.get('Price', limit_price)) * cum_qty)
                        remaining_shares -= cum_qty
                        break
                    time.sleep(1)
            else:
                d = self.get_order_details(order_id)
                if d and d.get('State') == 6:
                    print(f"✨ 注文 ID: {order_id} の取消には失敗しましたが、既に全約定していました。")
                    qty = int(d.get('CumQty', remaining_shares))
                    total_filled_qty += qty
                    total_filled_value += (float(d.get('Price', limit_price)) * qty)
                    remaining_shares = 0
                    break
                else:
                    print(f"⛔ キャセル失敗かつ約定不明のため、安全のため追従を中断します。")
                    break

        # --- 最終手段: 強制執行 (Marketable Limit Order) ---
        if remaining_shares > 0:
            print(f"🔥 【強制執行】残数 {remaining_shares}株 をマージン付の価格で即時約定させます。")
            board = self.get_board_data([code])
            b_info = board.get(str(code).replace(".T", ""))
            current_price = b_info.get('price') or b_info.get('bid', 0)
            
            from core.logic import normalize_tick_size
            if side == "2":
                force_price = normalize_tick_size(current_price + (atr * 0.2 if atr > 0 else current_price * 0.01), is_buy=True)
            else:
                force_price = normalize_tick_size(current_price - (atr * 0.2 if atr > 0 else current_price * 0.01), is_buy=False)
                
            order_id = self.execute_market_order(code, remaining_shares, side, price=force_price, hold_ids=hold_ids if side == "1" else None)
            if order_id:
                f_details = self.wait_for_execution(order_id, timeout_sec=20)
                if f_details:
                    qty = int(f_details.get('CumQty', remaining_shares))
                    total_filled_qty += qty
                    total_filled_value += (float(f_details.get('Price', force_price)) * qty)
                    remaining_shares -= qty

        # [Professional Audit] 合算した結果（VWAP）を返却
        avg_price = total_filled_value / total_filled_qty if total_filled_qty > 0 else 0
        return {
            "State": 6 if total_filled_qty >= shares else 7,
            "Qty": total_filled_qty,
            "Price": avg_price,
            "Symbol": code
        }

    def wait_for_execution(self, order_id: str, timeout_sec: int = 30) -> dict:
        """ 注文が約定（または失敗）するまで待機する """
        print(f"⏳ 注文 ID: {order_id} の約定を待機中...")
        start_time = time.time()
        while time.time() - start_time < timeout_sec:
            details = self.get_order_details(order_id)
            if details:
                state = details.get('State')
                # 5: 執行中, 3: 受付(現物), 4: 受付済
                # 6: 全部約定, 7: 一部約定, 8: 取消済, 9: 失効, 10: 出来ず
                if state == 6:
                    print(f"✨ 注文 ID: {order_id} 全部約定しました。")
                    return details
                elif state == 7:
                    # H-5: 一部約定を検出。残りの注文を取消して約定分のみを返す。
                    cum_qty = details.get('CumQty', 0)
                    leaves_qty = details.get('LeavesQty', 0)
                    print(f"⚠️ 注文 ID: {order_id} 一部約定 ({cum_qty}株約定, 残{leaves_qty}株)。残りの注文を取消します。")
                    # 残りの注文をキャンセルする
                    if not self.cancel_order(order_id):
                        print(f"⚠️ 残注文の取消に失敗（手動確認要）")
                    # 一部約定を全部約定たこととしてdetailsを返すが、Phase上位に一部約定であることを通知
                    details['_partial'] = True
                    details['State'] = 6  # 上位の約定チェックが State==6 を期待するため
                    details['Qty'] = cum_qty  # 実際に約定した株数で上書き
                    return details
                elif state in [8, 9, 10]:
                    print(f"❌ 注文 ID: {order_id} は約定しませんでした (State: {state})。")
                    return details
            time.sleep(2)
        print(f"⚠️ 注文 ID: {order_id} の約定確認がタイムアウトしました。ゾンビ処理化を防ぐため取消要求を送信します。")
        if self.cancel_order(order_id):
            print("✅ タイムアウト注文の強制取消要求を送信しました。")
        else:
            print(f"⚠️ 取消要求の送信に失敗しました（手動で約定状況を確認してください）")
            
        # --- [V2-C2] 取消完了の確認ポーリングを追加 ---
        print(f"⏳ 注文 ID: {order_id} の取消完了を待機中...")
        cancel_start = time.time()
        while time.time() - cancel_start < 15:
            details = self.get_order_details(order_id)
            if details and details.get('State') == 8: # 8: 取消済
                print(f"✅ 注文 ID: {order_id} の取消が完了しました。")
                return details
            time.sleep(2)
        print(f"⚠️ 注文 ID: {order_id} の取消完了が規定時間内に確認できませんでした（State: {details.get('State') if details else 'Unknown'}）。ゾンビポジションに注意してください。")
        return None

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
        """ 決済履歴をCSVに追記する（ダッシュボード用） """
        import os
        write_header = not os.path.exists(HISTORY_FILE) or os.path.getsize(HISTORY_FILE) == 0
        df = pd.DataFrame([trade_record])
        df.to_csv(HISTORY_FILE, mode='a', header=write_header, index=False, encoding='utf-8-sig')

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
            
        print("\n【口座ステータス (API取得値)】")
        print(f" 💰 現金残高:   {summary_record['cash_yen']:>10,.0f}円")
        print(f" 📈 株式評価額: {summary_record['stock_value_yen']:>10,.0f}円")
        print(f" 👑 合計資産額: {total_assets:>10,.0f}円")
        print("="*50 + "\n")
        
        write_header = not os.path.exists(EXECUTION_LOG_FILE) or os.path.getsize(EXECUTION_LOG_FILE) == 0
        actions_str = " | ".join(actions) if actions else "アクションなし"
        
        # [Professional Audit] ログ出力用のデータフレームを作成
        df_log = pd.DataFrame([{
            "time": summary_record.get('time', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            "regime": summary_record.get('regime', 'UNKNOWN'),
            "total_assets": total_assets,
            "cash": summary_record.get('cash_yen', 0),
            "stock_value": summary_record.get('stock_value_yen', 0),
            "actions": actions_str
        }])
        
        df_log.to_csv(EXECUTION_LOG_FILE, mode='a', header=write_header, index=False, encoding='utf-8-sig')
        
        # [Professional Audit] 実行ログの肥大化防止（ローテーション）
        from core.file_io import rotate_csv_if_large
        rotate_csv_if_large(EXECUTION_LOG_FILE, max_size_mb=5)
