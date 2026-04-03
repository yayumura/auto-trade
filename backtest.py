import yfinance as yf
import pandas as pd
from datetime import datetime
import os
import sys
import argparse
import numpy as np

sys.path.append(os.getcwd())
from core.logic import (
    calculate_all_technicals_v10, manage_positions_v10, select_candidates_v10
)
from core.config import (
    INITIAL_CASH, DATA_FILE, JST, TAX_RATE,
    STOCKS_TYPE, BREAKOUT_PERIOD, EXIT_PERIOD, MAX_POSITIONS, OVERHEAT_THRESHOLD
)

def get_historical_data(target_codes):
    univ_cache = os.path.join("data_cache", "hist_3616stocks_2021-01-01_2026-03-29_None_1d_v4.pkl")
    if os.path.exists(univ_cache):
        all_data = pd.read_pickle(univ_cache)
        tickers = [f"{code}.T" for code in target_codes] + ["1321.T"]
        valid_tickers = [t for t in tickers if t in all_data.columns.get_level_values(0).unique()]
        return all_data.loc[:, (valid_tickers, slice(None))]
    return None

def run_dual_session(target_codes, bundle, timeline, initial_cash_val=1000000, max_pos=3, overheat=30.0, apply_tax=True):
    account = {"cash": float(initial_cash_val)}
    portfolio, trade_history, pending_exits = [], [], []
    monthly_assets = {}
    
    annual_profit = 0
    tax_paid_this_year = 0
    current_year = timeline[0].year

    for i in range(len(timeline)):
        current_time = timeline[i]
        
        if current_time.year != current_year:
            annual_profit = 0
            tax_paid_this_year = 0
            current_year = current_time.year

        # 1. Exit Exec
        if pending_exits:
            still_pending = []
            for pe in pending_exits:
                ticker = f"{pe['code']}.T"
                try:
                    open_p = bundle["Open"].at[current_time, ticker]
                    if not pd.isna(open_p):
                        exec_p = open_p
                        realized_profit = (exec_p - pe['buy_price']) * pe['shares']
                        if apply_tax:
                            annual_profit += realized_profit
                            new_total_tax = max(0, int(annual_profit * TAX_RATE))
                            tax_diff = new_total_tax - tax_paid_this_year
                            tax_paid_this_year = new_total_tax
                            account['cash'] += (exec_p * pe['shares']) - tax_diff
                        else:
                            account['cash'] += (exec_p * pe['shares'])
                        trade_history.append({"code": pe['code'], "profit": realized_profit})
                    else: still_pending.append(pe)
                except: still_pending.append(pe)
            pending_exits = still_pending

        # 2. Position Check
        if portfolio:
            held = [p for p in portfolio if not p.get('pending_buy')]
            remaining, logs = manage_positions_v10(held, current_time, bundle)
            for log in logs:
                if log.get('timing') == "immediate":
                    exec_p = log['price']
                    realized_profit = (exec_p - log['buy_price']) * log['shares']
                    if apply_tax:
                        annual_profit += realized_profit
                        new_total_tax = max(0, int(annual_profit * TAX_RATE))
                        tax_diff = new_total_tax - tax_paid_this_year
                        tax_paid_this_year = new_total_tax
                        account['cash'] += (exec_p * log['shares']) - tax_diff
                    else:
                        account['cash'] += (exec_p * log['shares'])
                    trade_history.append({"code": log['code'], "profit": realized_profit})
                else:
                    pending_exits.append(log)
            portfolio = [p for p in portfolio if str(p['code']) in [str(r['code']) for r in remaining] or p.get('pending_buy')]

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
                        
                        max_buy_cap = total_equity / max_pos
                        # 現金残高以下に制限
                        shares = int( min(account['cash'], max_buy_cap) // buy_p )
                        shares = (shares // 100) * 100
                        
                        if shares >= 100:
                            p.update({"buy_price": buy_p, "shares": shares, "pending_buy": False, "max_p": buy_p, "held_days": 0})
                            account['cash'] -= float(buy_p * shares)
                        else: p['ignore'] = True
                    else: p['ignore'] = True
                except: p['ignore'] = True
        portfolio = [p for p in portfolio if not p.get('ignore')]
        
        # 4. Scan
        held_count = len([p for p in portfolio if not p.get('pending_buy')])
        if held_count < max_pos and i + 1 < len(timeline):
            candidates = select_candidates_v10(current_time, bundle, target_codes, max_count=max_pos-held_count, overheat_threshold=overheat)
            for best in candidates:
                if held_count >= max_pos: break
                if not any(str(p['code']) == str(best['code']) for p in portfolio):
                    portfolio.append({"code": best['code'], "buy_price": 0, "shares": 0, "buy_time": timeline[i+1], "pending_buy": True})
                    held_count += 1

        if i == len(timeline) - 1 or timeline[i].month != timeline[i+1].month:
            curr_v_close = sum(bundle["Close"].at[current_time, f"{p_['code']}.T"] * p_['shares'] for p_ in portfolio if not p_.get('pending_buy'))
            monthly_assets[current_time.strftime("%Y-%m")] = account['cash'] + curr_v_close

    last_close = bundle["Close"].iloc[-1]
    total_assets = account['cash'] + sum(last_close.get(f"{p['code']}.T", 0) * p['shares'] for p in portfolio if not p.get('pending_buy'))
    m_returns = []
    prev_val = initial_cash_val
    for k in sorted(monthly_assets.keys()):
        curr_val = monthly_assets[k]
        m_returns.append((curr_val - prev_val) / prev_val)
        prev_val = curr_val
    return {"profit_pct": (total_assets - initial_cash_val) / initial_cash_val * 100, "trade_count": len(trade_history), "monthly_win_rate": (len([r for r in m_returns if r > 0]) / len(m_returns) * 100) if m_returns else 0, "m_returns": m_returns, "monthly_assets": monthly_assets, "final_assets": total_assets}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--stocks', type=str, default=STOCKS_TYPE)
    parser.add_argument('--breakout', type=int, default=BREAKOUT_PERIOD)
    parser.add_argument('--exit', type=int, default=EXIT_PERIOD)
    parser.add_argument('--max_pos', type=int, default=MAX_POSITIONS)
    parser.add_argument('--overheat', type=float, default=OVERHEAT_THRESHOLD)
    args = parser.parse_args()

    df_sym = pd.read_csv(DATA_FILE)
    univ = [str(c) for i, c in enumerate(df_sym['コード']) if df_sym.iloc[i]['市場・商品区分'] == 'プライム（内国株式）']
    all_data = get_historical_data(univ)
    all_data.index = all_data.index.tz_localize('UTC').tz_convert(JST)
    bundle = calculate_all_technicals_v10(all_data, breakout_p=args.breakout, exit_p=args.exit)
    timeline = bundle["Close"].index.unique().sort_values()
    
    res_net = run_dual_session(univ, bundle, timeline, max_pos=args.max_pos, overheat=args.overheat, apply_tax=True)
    res_gross = run_dual_session(univ, bundle, timeline, max_pos=args.max_pos, overheat=args.overheat, apply_tax=False)
    
    print(f"\n" + "="*80)
    print(f" FINAL PERFORMANCE SUMMARY (COMPARISON MODE) ")
    print(f"="*80)
    print(f" {'METRIC':<20} | {'GROSS (TAX-FREE)':>25} | {'NET (PRODUCTION)':>25}")
    print(f" {'-'*20} + {'-'*25} + {'-'*25}")
    print(f" {'Total Profit (%)':<20} | {res_gross['profit_pct']:>+24.2f}% | {res_net['profit_pct']:>+24.2f}%")
    print(f" {'Final Assets (JPY)':<20} | {int(res_gross['final_assets']):>25,d} | {int(res_net['final_assets']):>25,d}")
    print(f" {'Total Trades':<20} | {res_gross['trade_count']:>25} | {res_net['trade_count']:>25}")
    print(f"="*80)

    print("\nMONTHLY ASSET COMPARISON (NET vs GROSS)")
    print("-" * 80)
    print(f" {'MONTH':<10} | {'NET ASSET (JPY)':>20} | {'GROSS ASSET (JPY)':>20} | {'DIFF (NET-GROSS)':>22}")
    print("-" * 80)
    sorted_months = sorted(res_net['monthly_assets'].keys())
    for month in sorted_months:
        na = res_net['monthly_assets'][month]
        ga = res_gross['monthly_assets'][month]
        diff = na - ga
        print(f" {month:<10} | {int(na):>20,d} | {int(ga):>20,d} | {int(diff):>+22,d}")
    print("-" * 80 + "\n")
