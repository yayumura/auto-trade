import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime

sys.path.append(os.getcwd())
from core.logic import (
    calculate_all_technicals_v10, manage_positions_v10, select_candidates_v10
)
from core.config import (
    DATA_FILE, JST, INITIAL_CASH, TAX_RATE
)

def get_historical_data(target_codes):
    univ_cache = os.path.join("data_cache", "hist_3616stocks_2021-01-01_2026-03-29_None_1d_v4.pkl")
    if os.path.exists(univ_cache):
        all_data = pd.read_pickle(univ_cache)
        tickers = [f"{code}.T" for code in target_codes] + ["1321.T"]
        valid_tickers = [t for t in tickers if t in all_data.columns.get_level_values(0).unique()]
        return all_data.loc[:, (valid_tickers, slice(None))]
    return None

def run_fast_backtest(univ, bundle, timeline, initial_cash=1000000, max_pos=3, overheat=30.0, apply_tax=True):
    account = {"cash": float(initial_cash)}
    portfolio, trade_history, pending_exits = [], [], []
    
    annual_profit = 0
    tax_paid_this_year = 0
    current_year = timeline[0].year

    for i in range(len(timeline)):
        current_time = timeline[i]
        
        if current_time.year != current_year:
            annual_profit = 0; tax_paid_this_year = 0; current_year = current_time.year

        # 1. Exit Exec
        if pending_exits:
            for pe in pending_exits:
                realized_profit = (pe['price'] - pe['buy_price']) * pe['shares']
                if apply_tax:
                    annual_profit += realized_profit
                    new_total_tax = max(0, int(annual_profit * TAX_RATE))
                    tax_diff = new_total_tax - tax_paid_this_year
                    tax_paid_this_year = new_total_tax
                    account['cash'] += (pe['price'] * pe['shares']) - tax_diff
                else:
                    account['cash'] += (pe['price'] * pe['shares'])
                trade_history.append(pe)
            pending_exits = []

        # 2. Position Check
        if portfolio:
            held = [p for p in portfolio if not p.get('pending_buy')]
            # Production settings: Shield:ON, Guard:OFF
            remaining, logs = manage_positions_v10(held, current_time, bundle, use_shield=True, use_profit_guard=False)
            pending_exits.extend(logs)
            portfolio = [p for p in portfolio if str(p['code']) not in [str(l['code']) for l in logs]]

        # 3. Buy Exec
        for p in portfolio:
            if p.get('pending_buy') and p.get('buy_time') == current_time:
                ticker = f"{p['code']}.T"
                try:
                    buy_p = bundle["Open"].at[current_time, ticker]
                    if not pd.isna(buy_p):
                        prev_time = timeline[max(0, i-1)]
                        curr_v = sum(bundle["Close"].at[prev_time, f"{p_['code']}.T"] * p_['shares'] for p_ in portfolio if not p_.get('pending_buy'))
                        total_equity = account['cash'] + curr_v
                        shares = int((total_equity / max_pos) // buy_p)
                        shares = (shares // 100) * 100
                        if shares >= 100:
                            p.update({"buy_price": buy_p, "shares": shares, "pending_buy": False})
                            account['cash'] -= float(buy_p * shares)
                        else: p['ignore'] = True
                    else: p['ignore'] = True
                except: p['ignore'] = True
        portfolio = [p for p in portfolio if not p.get('ignore')]
        
        # 4. Scanning
        held_count = len([p for p in portfolio if not p.get('pending_buy')])
        if held_count < max_pos and i + 1 < len(timeline):
            candidates = select_candidates_v10(current_time, bundle, univ, max_count=max_pos-held_count, overheat_threshold=overheat, use_shield=True)
            for best in candidates:
                if held_count >= max_pos: break
                if not any(str(p['code']) == str(best['code']) for p in portfolio):
                    portfolio.append({"code": best['code'], "buy_price": 0, "shares": 0, "buy_time": timeline[i+1], "pending_buy": True})
                    held_count += 1

    final_portfolio_v = sum(bundle["Close"].get(f"{p['code']}.T", pd.Series([0])).iloc[-1] * p['shares'] for p in portfolio if not p.get('pending_buy'))
    total_assets = account['cash'] + final_portfolio_v
    return (total_assets - initial_cash) / initial_cash * 100, len(trade_history)

if __name__ == "__main__":
    print("Starting ULTIMATE Full-Grid Optimization (72 patterns)...")
    
    df_sym = pd.read_csv(DATA_FILE)
    univ = [str(c) for i, c in enumerate(df_sym['コード']) if df_sym.iloc[i]['市場・商品区分'] == 'プライム（内国株式）']
    all_data = get_historical_data(univ)
    all_data.index = all_data.index.tz_localize('UTC').tz_convert(JST)
    
    results = []
    # FULL SEARCH
    for b in [15, 20, 25]:
        for e in [10, 15, 20]:
            print(f"\n[PHASE] Calibrating Bundle B:{b} E:{e} ...")
            bundle = calculate_all_technicals_v10(all_data, breakout_p=b, exit_p=e)
            timeline = bundle["Close"].index.unique().sort_values()
            
            for p in [3, 5]:
                for oh in [25.0, 30.0, 40.0, 100.0]:
                    # Run Net (This is the primary goal)
                    p_net, t_net = run_fast_backtest(univ, bundle, timeline, max_pos=p, overheat=oh, apply_tax=True)
                    # Run Gross (Implicitly calculated to show potential)
                    p_gross, t_gross = run_fast_backtest(univ, bundle, timeline, max_pos=p, overheat=oh, apply_tax=False)
                    
                    print(f"  > Pos:{p} OH:{oh}% | Net:{p_net:>+8.2f}% (Gross:{p_gross:>+8.2f}%) | Trades:{t_net}")
                    results.append({"b":b, "e":e, "p":p, "oh":oh, "p_net":p_net, "p_gross":p_gross})
    
    best = sorted(results, key=lambda x: x['p_net'], reverse=True)[0]
    print(f"\n" + "="*50)
    print(f" ULTIMATE WINNER FOUND ")
    print(f"="*50)
    print(f" Breakout (B): {best['b']}")
    print(f" Exit (E):     {best['e']}")
    print(f" Positions:    {best['p']}")
    print(f" Overheat:     {best['oh']}%")
    print(f"-"*50)
    print(f" FINAL REAL NET PROFIT: {best['p_net']:+.2f}%")
    print(f" (Potential Gross):     {best['p_gross']:+.2f}%")
    print(f"="*50)
