import yfinance as yf
import pandas as pd
from datetime import datetime
import os
import sys
import argparse
import time

sys.path.append(os.getcwd())

from core.logic import (
    calculate_all_technicals_v10, manage_positions_v10, select_candidates_v10
)
from core.config import (
    INITIAL_CASH, DATA_FILE, JST, TAX_RATE
)

def get_historical_data(target_codes):
    univ_cache = os.path.join("data_cache", "hist_3616stocks_2021-01-01_2026-03-29_None_1d_v4.pkl")
    if os.path.exists(univ_cache):
        all_data = pd.read_pickle(univ_cache)
        tickers = [f"{code}.T" for code in target_codes] + ["1321.T"]
        valid_tickers = [t for t in tickers if t in all_data.columns.get_level_values(0).unique()]
        return all_data.loc[:, (valid_tickers, slice(None))]
    return None

def run_truth_session(target_codes, bundle, timeline, initial_cash_val=1000000, max_pos=3, show_trades=False):
    account = {"cash": float(initial_cash_val)}
    portfolio, trade_history, pending_exits = [], [], []
    
    for i in range(len(timeline)):
        current_time = timeline[i]
        
        # 1. 決済執行 (Open)
        if pending_exits:
            still_pending = []
            for pe in pending_exits:
                ticker = f"{pe['code']}.T"
                try:
                    open_p = bundle["Open"].at[current_time, ticker]
                    if not pd.isna(open_p):
                        exec_p = max(bundle["Low"].at[current_time, ticker], open_p)
                        gross = (exec_p - pe['buy_price']) * pe['shares']
                        tax = max(0, int(gross * TAX_RATE)) if gross > 0 else 0
                        account['cash'] += (exec_p * pe['shares']) - tax
                        trade_history.append({"code": pe['code'], "profit": gross-tax})
                        if show_trades: print(f"    [{current_time.date()}] SELL: {pe['code']} @ {exec_p:.1f} ({pe['reason']})")
                    else: still_pending.append(pe)
                except: still_pending.append(pe)
            pending_exits = still_pending

        # 2. 判定 (Close)
        if portfolio:
            held = [p for p in portfolio if not p.get('pending_buy')]
            remaining, logs = manage_positions_v10(held, current_time, bundle)
            for log in logs:
                pending_exits.append(log)
                portfolio = [p for p in portfolio if str(p['code']) != str(log['code'])]

        # 3. 買付予約執行
        for p in portfolio:
            if p.get('pending_buy') and p.get('buy_time') == current_time:
                ticker = f"{p['code']}.T"
                try:
                    buy_p = bundle["Open"].at[current_time, ticker]
                    if not pd.isna(buy_p):
                        curr_v = sum(bundle["Close"].at[current_time, f"{p_['code']}.T"] * p_['shares'] for p_ in portfolio if not p_.get('pending_buy'))
                        total_equity = account['cash'] + curr_v
                        
                        # 3ポジション集中: 資産の1/3投入
                        alloc = total_equity / max_pos
                        shares = int( (alloc * 0.95) // buy_p ) # 5%余裕
                        shares = (shares // 100) * 100
                        
                        if shares >= 100:
                            p.update({"buy_price": buy_p, "shares": shares, "pending_buy": False})
                            account['cash'] -= float(buy_p * shares)
                            if show_trades: print(f"    [{current_time.date()}] BUY:  {p['code']} @ {buy_p:.1f}")
                        else: p['ignore'] = True
                    else: p['ignore'] = True
                except: p['ignore'] = True
        portfolio = [p for p in portfolio if not p.get('ignore')]
        
        # 4. 新規スキャン
        held_count = len([p for p in portfolio if not p.get('pending_buy')])
        if held_count < max_pos and i + 1 < len(timeline):
            candidates = select_candidates_v10(current_time, bundle, target_codes, max_count=max_pos-held_count)
            for best in candidates:
                if held_count >= max_pos: break
                if not any(str(p['code']) == str(best['code']) for p in portfolio):
                    portfolio.append({"code": best['code'], "buy_price": 0, "shares": 0, "buy_time": timeline[i+1], "atr": best['atr'], "pending_buy": True})
                    held_count += 1

    last_dt = timeline[-1]
    final_stock_val = sum(bundle["Close"].get(f"{p['code']}.T", pd.Series([0])).at[last_dt] * p['shares'] for p in portfolio if not p.get('pending_buy'))
    total_assets = account['cash'] + final_stock_val
    return {"profit_pct": (total_assets - initial_cash_val) / initial_cash_val * 100, "trade_count": len(trade_history)}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--stocks', type=str, default='prime')
    parser.add_argument('--breakout', type=int, default=25)
    parser.add_argument('--exit', type=int, default=10)
    parser.add_argument('--max_pos', type=int, default=3)
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    df_sym = pd.read_csv(DATA_FILE)
    univ = [str(c) for i, c in enumerate(df_sym['コード']) if df_sym.iloc[i]['市場・商品区分'] == 'プライム（内国株式）']
        
    all_data = get_historical_data(univ)
    if all_data.index.tzinfo is None: all_data.index = all_data.index.tz_localize('UTC').tz_convert(JST)
    else: all_data.index = all_data.index.tz_convert(JST)
    
    bundle = calculate_all_technicals_v10(all_data, breakout_p=args.breakout, exit_p=args.exit)
    timeline = bundle["Close"].index.unique().sort_values()
    
    res = run_truth_session(univ, bundle, timeline, max_pos=args.max_pos, show_trades=args.verbose)
    print(f"\nFINAL VERIFIED RESULT: Market:PRIME B:{args.breakout} E:{args.exit} Pos:{args.max_pos} | Profit:{res['profit_pct']:+.2f}% Trades:{res['trade_count']}")
