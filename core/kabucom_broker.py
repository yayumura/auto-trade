import requests
import json
import pandas as pd
from datetime import datetime
import time
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
        
        env_name = "【本番API】" if is_production else "【検証API】"
        if not self.password:
            print(f"⚠️ {env_name} パスワード(KABUCOM_API_PASSWORD)が.envに設定されていません。")
        else:
            self._authenticate()

    def _authenticate(self):
        """ kabuステーションAPIからトークンを取得する """
        url = f"{self.base_url}/token"
        headers = {'Content-Type': 'application/json'}
        data = {'APIPassword': self.password}
        
        try:
            res = requests.post(url, headers=headers, json=data, timeout=10)
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

    def get_server_time(self) -> datetime:
        """ 取引所（証券会社側）の現在時刻を取得する """
        from core.config import JST
        fallback = datetime.now(JST)  # H-6: JST aware datetimeを常に返すよう修正
        if not self.token: return fallback
        url = f"{self.base_url}/symbol/7203@1" # トヨタの時価情報から時刻を拝借
        try:
            res = requests.get(url, headers=self._get_headers(), timeout=5)
            if res.status_code == 200:
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
        url = f"{self.base_url}/orders"
        try:
            res = requests.get(url, headers=self._get_headers(), timeout=10)
            if res.status_code == 200:
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
        
        url = f"{self.base_url}/wallet/cash"
        for retry in [False, True]: # 401時のリトライ用
            try:
                res = requests.get(url, headers=self._get_headers(force_refresh=retry), timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    cash = data.get('StockAccountWallet', 0)
                    return {"cash": float(cash)}
                elif res.status_code == 401 and not retry:
                    continue
                else:
                    print(f"⚠️ 余力取得エラー: {res.text}")
                    return {"cash": 0}
            except Exception as e:
                print(f"⚠️ 余力取得通信エラー: {e}")
                return {"cash": 0}
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

        api_positions = None
        for retry in [False, True]:
            try:
                res = requests.get(url, headers=self._get_headers(force_refresh=retry), timeout=10)
                if res.status_code == 200:
                    api_positions = res.json()
                    break
                elif res.status_code == 401 and not retry:
                    continue
                else:
                    raise Exception(f"API Error: {res.status_code} {res.text}")
            except Exception as e:
                if retry: raise e # リトライ後も失敗なら上位へ投げる
                continue

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
                "partial_sold": partial_sold
            })
        return final_positions

    def execute_market_order(self, code: str, shares: int, side: str, price: float = 0) -> str:
        """
        現物の成行・指値注文（買い/売り）を発注する純粋APIラッパー。
        成功時は OrderId を返し、失敗時は None を返すようにシグネチャを変更。
        side: "1" (売), "2" (買)
        """
        if not self.token: return None
        
        cash_margin = 2 if side == "2" else 3
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
            "AccountType": 4,   # 4: 特定口座
            "Qty": shares,
            "FrontOrderType": front_order_type,
            "Price": int(price),
            "ExpireDay": 0      # 当日限り
        }

        url = f"{self.base_url}/sendorder"
        
        for retry in [False, True]:
            try:
                res = requests.post(url, headers=self._get_headers(force_refresh=retry), json=data, timeout=10)
                if res.status_code == 200:
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
                elif res.status_code == 401 and not retry:
                    print("🔄 [API] トークン期限切れ(401)を検知。再認証して注文をリトライします...")
                    continue
                else:
                    print(f"⚠️ 注文HTTPエラー: {res.status_code} {res.text}")
                    return None
            except Exception as e:
                print(f"⚠️ 注文通信エラー: {e}")
                return None
        return None

    def cancel_order(self, order_id: str) -> bool:
        """ API経由で注文を取り消す (オートキャンセル機構用) """
        if not self.token: return False
        cancel_url = f"{self.base_url}/cancelorder"
        cancel_data = {"OrderId": order_id, "Password": self.password}
        
        for retry in [False, True]:
            try:
                res = requests.put(cancel_url, headers=self._get_headers(force_refresh=retry), json=cancel_data, timeout=10)
                if res.status_code == 200:
                    order_res = res.json()
                    if order_res.get('Result') == 0:
                        return True
                    else:
                        print(f"⚠️ 取消要求失敗: {order_res}")
                        return False
                elif res.status_code == 401 and not retry:
                    continue
                else:
                    return False
            except Exception as e:
                print(f"⚠️ 取消要求通信エラー: {e}")
                return False
        return False

    def get_order_details(self, order_id: str) -> dict:
        """ 注文詳細（ステータス・約定単価等）を取得する """
        if not self.token or not order_id: return None
        url = f"{self.base_url}/orders?id={order_id}"
        try:
            res = requests.get(url, headers=self._get_headers(), timeout=10)
            if res.status_code == 200:
                orders = res.json()
                if orders and len(orders) > 0:
                    return orders[0]
            return None
        except Exception:
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
        codes = [str(s).replace(".T", "") for s in symbols]
        
        chunk_size = 50
        for i in range(0, len(codes), chunk_size):
            chunk = codes[i:i + chunk_size]
            reg_list = [{"Symbol": c, "Exchange": 1} for c in chunk]
            data = {"Symbols": reg_list}
            try:
                res = requests.put(url, headers=self._get_headers(), json=data, timeout=10)
                if res.status_code == 200:
                    print(f"✅ API銘柄登録完了 ({i+1}〜{i+len(chunk)}銘柄目)")
                else:
                    print(f"⚠️ 銘柄登録エラー ({i+1}〜): {res.text}")
            except Exception as e:
                print(f"⚠️ 銘柄登録通信エラー: {e}")
                return False
        return True

    def unregister_all(self):
        """ 登録済みの全銘柄を解除する（上限管理のため） """
        if not self.token: return False
        url = f"{self.base_url}/unregister/all"
        try:
            res = requests.put(url, headers=self._get_headers(), timeout=10)
            return res.status_code == 200
        except:
            return False

    def get_board_data(self, symbols: list) -> dict:
        """ 
        登録済み銘柄の時価情報（board）を取得する。
        戻り値: { "7203": {"price": 1234, "status": "気配"}, ... }
        """
        results = {}
        if not self.token: return results
        
        for s in symbols:
            code = str(s).replace(".T", "")
            url = f"{self.base_url}/board/{code}@1"
            try:
                res = requests.get(url, headers=self._get_headers(), timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    results[code] = {
                        "price": data.get('CurrentPrice'),
                        "prev_close": data.get('PreviousClose'), # [Expert Refinement] 前日終値を追加
                        "status": data.get('CurrentPriceStatus'),
                        "bid": data.get('BidPrice'),
                        "ask": data.get('AskPrice')
                    }
            except Exception:
                continue
        return results

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
        df_log = pd.DataFrame([{
            "time": summary_record['time'], 
            "actions": actions_str, 
            "portfolio_count": len(summary_record['portfolio']), 
            "stock_value_yen": summary_record['stock_value_yen'], 
            "cash_yen": summary_record['cash_yen'], 
            "total_assets_yen": total_assets
        }])
        df_log.to_csv(EXECUTION_LOG_FILE, mode='a', header=write_header, index=False, encoding='utf-8-sig')
