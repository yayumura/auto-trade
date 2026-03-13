import requests
import json
import pandas as pd
from datetime import datetime
import time
from core.broker import BaseBroker
from core.config import KABUCOM_API_PASSWORD, HISTORY_FILE, EXECUTION_LOG_FILE
from core.log_setup import send_discord_notify

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
            res = requests.post(url, headers=headers, json=data, timeout=5)
            if res.status_code == 200:
                self.token = res.json().get('Token')
                print(f"✅ auカブコムAPI 認証成功 (Port:{self.port})")
            else:
                print(f"⚠️ 認証失敗: {res.status_code} {res.text}")
        except Exception as e:
            env_name = "本番" if self.is_production else "検証用"
            print(f"⚠️ kabuステーション({env_name})に接続できません。アプリが起動し、APIが有効化されているか確認してください。({e})")

    def _get_headers(self):
        if not self.token:
            self._authenticate()
        return {
            'Content-Type': 'application/json',
            'X-API-KEY': self.token
        }

    def get_account_balance(self) -> dict:
        """ 現金残高（買付余力）の取得 """
        if not self.token: return {"cash": 0}
        
        url = f"{self.base_url}/wallet/cash"
        try:
            res = requests.get(url, headers=self._get_headers(), timeout=5)
            if res.status_code == 200:
                data = res.json()
                # 買付余力 (StockAccountWallet) を現金残高とする
                cash = data.get('StockAccountWallet', 0)
                return {"cash": float(cash)}
            else:
                print(f"⚠️ 余力取得エラー: {res.text}")
                return {"cash": 0}
        except Exception as e:
            print(f"⚠️ 余力取得通信エラー: {e}")
            return {"cash": 0}

    def get_positions(self) -> list:
        """ 
        現在保有中の現物ポジション一覧を取得し、シミュレーションBOTと同じ辞書リスト形式に変換する。
        （※kabuステーション側で買値（AverageCost）等も管理されている）
        """
        if not self.token: return []
        
        url = f"{self.base_url}/positions?product=0" # 0: 現物
        positions = []
        try:
            res = requests.get(url, headers=self._get_headers(), timeout=5)
            if res.status_code == 200:
                data = res.json()
                for p in data:
                    if p['LeavesQty'] == 0: continue # 売却済残存データ等をパージ
                    # kabuステーションのレスポンスをBOT共通フォーマットにマッピング
                    code_sym = p['Symbol']
                    positions.append({
                        "code": code_sym,
                        "name": p['SymbolName'],
                        "shares": p['LeavesQty'],         # 保有数量
                        "buy_price": p['Price'],          # 平均取得単価
                        "current_price": p['CurrentPrice'],
                        "highest_price": p['CurrentPrice'], # 取引時間中に現在値=最高値として扱う(暫定)
                        "buy_time": "Real API Position"
                    })
                return positions
            else:
                print(f"⚠️ ポジション取得エラー: {res.text}")
                return []
        except Exception as e:
            print(f"⚠️ ポジション取得通信エラー: {e}")
            return []

    def execute_market_order(self, code: str, shares: int, side: str) -> bool:
        """
        現物の成行注文（買い/売り）を発注する純粋APIラッパー。
        side: "1" (売), "2" (買)
        """
        if not self.token: return False
        
        url = f"{self.base_url}/sendorder"
        data = {
            "Password": self.password,
            "Symbol": code,
            "Exchange": 1,      # 1: 東証
            "SecurityType": 1,  # 1: 株式
            "Side": side,       # 1: 売, 2: 買
            "CashMargin": 1,    # 1: 新規（現物買）or 返済（現物売）
            "MarginTradeType": 1, # 1: 制度信用（現物の場合はダミー）
            "DelivType": 2,     # 2: お預り金（現物買の場合必須）
            "AccountType": 4,   # 4: 特定口座
            "Qty": shares,
            "FrontOrderType": 10, # 10: 成行
            "Price": 0,         # 成行なので0
            "ExpireDay": 0      # 当日限り
        }
        
        try:
            res = requests.post(url, headers=self._get_headers(), json=data, timeout=5)
            if res.status_code == 200:
                order_res = res.json()
                if order_res.get('Result') == 0:
                    order_id = order_res.get('OrderId')
                    env = "【本番】" if self.is_production else "【検証API】"
                    act = "買い" if side == "2" else "売り"
                    print(f"✅ {env} 注文受付完了 (ID: {order_id}) - {code} {shares}株 {act}")
                    return True
                else:
                    print(f"⚠️ 注文拒否: {order_res}")
                    return False
            else:
                print(f"⚠️ 注文HTTPエラー: {res.status_code} {res.text}")
                return False
        except Exception as e:
            print(f"⚠️ 注文通信エラー: {e}")
            return False

    # ---------------------------------------------------------
    # インターフェース互換性のためのファイル保存・ログ機能
    # (API運用でも履歴CSVやダッシュボード観測用ログは残す)
    # ---------------------------------------------------------
    def save_positions(self, portfolio: list):
        """ リアルAPIでは自動でポジションが残るが、ダッシュボード互換性のためにファイルにも書き出す """
        import pandas as pd
        from core.config import PORTFOLIO_FILE
        df = pd.DataFrame(portfolio)
        df.to_csv(PORTFOLIO_FILE, index=False, encoding='utf-8-sig')

    def save_account(self, account: dict):
        """ 同上 """
        import json
        from core.config import ACCOUNT_FILE
        with open(ACCOUNT_FILE, 'w', encoding='utf-8') as f:
            json.dump(account, f, indent=4)

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
