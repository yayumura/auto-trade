import os
import json
import pandas as pd
from datetime import datetime
from core.broker import BaseBroker
from core.config import ACCOUNT_FILE, PORTFOLIO_FILE, HISTORY_FILE, EXECUTION_LOG_FILE, INITIAL_CASH
from core.file_io import atomic_write_json, atomic_write_csv, safe_read_json, safe_read_csv

class SimulationBroker(BaseBroker):
    """
    CSV/JSONファイルを使用して仮想売買を行うシミュレーション用Broker。
    既存の auto_trade.py からファイル入出力部分のみを抽出して実装されています。
    """
    
    def get_account_balance(self) -> dict:
        account = safe_read_json(ACCOUNT_FILE)
        return account if account is not None else {"cash": INITIAL_CASH}

    def save_account(self, account_data: dict):
        atomic_write_json(ACCOUNT_FILE, account_data)

    def get_positions(self) -> list:
        df = safe_read_csv(PORTFOLIO_FILE)
        return df.to_dict('records') if not df.empty else []

    def save_positions(self, portfolio: list):
        df = pd.DataFrame(portfolio)
        atomic_write_csv(PORTFOLIO_FILE, df)

    def save_portfolio(self, portfolio: list):
        """auto_trade.py との互換性のためのエイリアス（M-3修正）"""
        self.save_positions(portfolio)

    def execute_market_order(self, code: str, shares: int, side: str) -> str:
        """ シミュレーションでは常に即時成功とみなし、ダミーIDを返す """
        import time
        return f"SIM-{int(time.time())}"

    def log_trade(self, trade_record: dict):
        write_header = not os.path.exists(HISTORY_FILE) or os.path.getsize(HISTORY_FILE) == 0
        df = pd.DataFrame([trade_record])
        df.to_csv(HISTORY_FILE, mode='a', header=write_header, index=False, encoding='utf-8-sig')

    def log_execution_summary(self, summary_record: dict):
        # UI表示用のコンソール出力
        total_assets = summary_record['total_assets_yen']
        actions = summary_record['actions']
        
        print("\n" + "="*50)
        print(f" 📊 実行サマリー (レジーム: {summary_record['regime']})")
        print("="*50)
        print("\n【今回のアクション】")
        
        if actions:
            for act in actions:
                print(f" ✔ {act}")
        else:
            print(" - アクションなし (保有維持 / 新規見送り)")
            
        print("\n【現在の保有株式】")
        if summary_record['portfolio']:
            for p in summary_record['portfolio']:
                cp = float(p.get('current_price', p['buy_price']))
                val = cp * int(p['shares'])
                profit_pct = (cp - float(p['buy_price'])) / float(p['buy_price']) * 100
                print(f" 🔹 {p['code']} {p['name']}\n    数量: {p['shares']}株 | 現在値: {cp:,.1f}円 | 評価額: {val:,.0f}円 | 損益: {profit_pct:+.2f}%")
        else:
            print(" - 保有なし")
            
        print("\n【口座ステータス】")
        print(f" 💰 現金残高:   {summary_record['cash_yen']:>10,.0f}円")
        print(f" 📈 株式評価額: {summary_record['stock_value_yen']:>10,.0f}円")
        print(f" 👑 合計資産額: {total_assets:>10,.0f}円")
        print("="*50 + "\n")
        
        # CSVへの記録作成
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
