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
        if not portfolio:
            df = pd.DataFrame(columns=[
                'code', 'name', 'buy_time', 'buy_price', 
                'highest_price', 'current_price', 'shares'
            ])
        else:
            df = pd.DataFrame(portfolio)
        atomic_write_csv(PORTFOLIO_FILE, df)

    def save_portfolio(self, portfolio: list):
        """auto_trade.py との互換性のためのエイリアス（M-3修正）"""
        self.save_positions(portfolio)

    def execute_market_order(self, code: str, shares: int, side: str, price: float = 0) -> str:
        """ 
        シミュレーションでは常に即時成功とみなし、ダミーIDを返す。
        V18.1: スリッページを反映した実行価格のシミュレーション。
        """
        from core.config import SLIPPAGE_RATE
        exec_price = price
        if price > 0:
            if side == "1": # Buy
                exec_price = price * (1.0 + SLIPPAGE_RATE)
            else: # Sell
                exec_price = price * (1.0 - SLIPPAGE_RATE)
                
            if os.getenv("DEBUG_MODE", "false").lower() == "true":
                print(f"[SIM_EXEC] {code} {side} @ {exec_price:,.1f} (Slipped from {price:,.1f})")

        import time
        return f"SIM-{int(time.time())}"

    def execute_chase_order(self, code: str, shares: int, side: str, atr: float = 0) -> str:
        """ シミュレーションでは追従せず、成行注文として即時決済する(互換性維持) """
        # 成行注文としてスリッページを適用
        return self.execute_market_order(code, shares, side)

    def execute_stop_order(self, code: str, shares: int, side: str, trigger_price: float, current_open: float = None) -> dict:
        """ 
        [V18.2 Strictness] 逆指値（ストップロス）のシミュレーション実行。
        - 始値がトリガー価格を下回っている（ギャップダウン）場合、始値で約定させる。
        """
        from core.config import SLIPPAGE_RATE
        exec_price = trigger_price
        
        # 始値がすでにストップ価格を割り込んでいた場合（ギャップダウン）
        if current_open is not None and side == "1": # Sell Stop (Stop Loss)
            if current_open <= trigger_price:
                exec_price = current_open # より不利な始値で約定
        
        # スリッページ適用
        if side == "1": # Sell
            final_price = exec_price * (1.0 - SLIPPAGE_RATE)
        else: # Buy (Stop Buy)
            final_price = exec_price * (1.0 + SLIPPAGE_RATE)
            
        import time
        return {
            "ID": f"SIM-STOP-{int(time.time())}",
            "State": 7, # Simulated Execution
            "Price": final_price,
            "Qty": shares
        }

    def cancel_order(self, order_id: str) -> bool:
        """ シミュレーションでは即キャンセル成功とする """
        return True

    def log_trade(self, trade_record: dict):
        df = pd.DataFrame([trade_record])
        atomic_write_csv(HISTORY_FILE, df)

    def log_execution_summary(self, summary_record: dict):
        # UI表示用のコンソール出力
        total_assets = summary_record['total_assets_yen']
        actions = summary_record['actions']
        
        print("\n" + "="*50)
        print(f" [Summary] 実行サマリー (レジーム: {summary_record['regime']})")
        print("="*50)
        print("\n【今回のアクション】")
        
        if actions:
            for act in actions:
                print(f" * {act}")
        else:
            print(" - アクションなし (保有維持 / 新規見送り)")
            
        print("\n【現在の保有株式】")
        if summary_record['portfolio']:
            for p in summary_record['portfolio']:
                cp = float(p.get('current_price', p['buy_price']))
                val = cp * int(p['shares'])
                profit_pct = (cp - float(p['buy_price'])) / float(p['buy_price']) * 100 if float(p['buy_price']) > 0 else 0
                print(f" - {p['code']} {p['name']}\n    数量: {p['shares']}株 | 現在値: {cp:,.1f}円 | 評価額: {val:,.0f}円 | 損益: {profit_pct:+.2f}%")
        else:
            print(" - 保有なし")
            
        print("\n【口座ステータス】")
        print(f" [Cash] 現金残高:   {summary_record['cash_yen']:>10,.0f}円")
        print(f" [Stocks] 株式評価額: {summary_record['stock_value_yen']:>10,.0f}円")
        print(f" [Total] 合計資産額: {total_assets:>10,.0f}円")
        print("="*50 + "\n")
        
        actions_str = " | ".join(actions) if actions else "アクションなし"
        df_log = pd.DataFrame([{
            "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
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
