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
    
    # 納税管理
    annual_profit = 0
    tax_paid_this_year = 0
    current_year = timeline[0].year

    for i in range(len(timeline)):
        current_time = timeline[i]
        
        # 年が変わったら納税実績をリセット
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
                        exec_p = pe['price']
                        realized_profit = (exec_p - pe['buy_price']) * pe['shares']
                        
                        if apply_tax:
                            # 特定口座（源泉徴収あり）のロジック:
                            # 1. 通算利益加算
                            old_annual_profit = annual_profit
                            annual_profit += realized_profit
                            
                            # 2. 新しい累積納税額を計算 (マイナスの場合は0)
                            new_total_tax = max(0, int(annual_profit * TAX_RATE))
                            
                            # 3. 今回の徴収額（または還付額）を計算
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
                        shares = int( (total_equity / max_pos) // buy_p )
                        shares = (shares // 100) * 100
                        if shares >= 100:
                            p.update({"buy_price": buy_p, "shares": shares, "pending_buy": False})
                            account['cash'] -= float(buy_p * shares)
                        else: p['ignore'] = True
                    else: p['ignore'] = True
                except: p['ignore'] = True
        portfolio = [p for p in portfolio if not p.get('ignore')]
        
        # 4. Scan
        held_count = len([p for p in portfolio if not p.get('pending_buy')])
        if held_count < max_pos and i + 1 < len(timeline):
            candidates = select_candidates_v10(current_time, bundle, univ, max_count=max_pos-held_count, overheat_threshold=overheat)
            for best in candidates:
                if held_count >= max_pos: break
                if not any(str(p['code']) == str(best['code']) for p in portfolio):
                    portfolio.append({"code": best['code'], "buy_price": 0, "shares": 0, "buy_time": timeline[i+1], "pending_buy": True})
                    held_count += 1

        if i == len(timeline) - 1 or timeline[i].month != timeline[i+1].month:
            curr_v_close = sum(bundle["Close"].at[current_time, f"{p_['code']}.T"] * p_['shares'] for p_ in portfolio if not p_.get('pending_buy'))
            monthly_assets[current_time.strftime("%Y-%m")] = account['cash'] + curr_v_close

    total_assets = account['cash'] + sum(bundle["Close"].get(f"{p['code']}.T", pd.Series([0])).iloc[-1] * p['shares'] for p in portfolio if not p.get('pending_buy'))
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

    print(f"\n[Launcher] Starting Proper Taxation Backtest...")
    print(f"  [Config] Market:{args.stocks.upper()} | B:{args.breakout} | E:{args.exit} | Pos:{args.max_pos}")

    df_sym = pd.read_csv(DATA_FILE)
    univ = [str(c) for i, c in enumerate(df_sym['コード']) if df_sym.iloc[i]['市場・商品区分'] == 'プライム（内国株式）']
    all_data = get_historical_data(univ)
    all_data.index = all_data.index.tz_localize('UTC').tz_convert(JST)
    
    bundle = calculate_all_technicals_v10(all_data, breakout_p=args.breakout, exit_p=args.exit)
    timeline = bundle["Close"].index.unique().sort_values()
    
    print("  Calculating REAL Net Results (With Annual Profit Loss Offset)...")
    res_net = run_dual_session(univ, bundle, timeline, max_pos=args.max_pos, overheat=args.overheat, apply_tax=True)
    print("  Calculating Gross Results (Tax-Free)...")
    res_gross = run_dual_session(univ, bundle, timeline, max_pos=args.max_pos, overheat=args.overheat, apply_tax=False)
    
    # 指標計算 (Net)
    m_avg = sum(res_net['m_returns']) / len(res_net['m_returns']) if res_net['m_returns'] else 0
    m_std = np.std(res_net['m_returns']) if res_net['m_returns'] else 1
    m_sharpe = m_avg / m_std if m_std > 0 else 0

    print(f"\n" + "="*50)
    print(f" FINAL PERFORMANCE SUMMARY (CORRECTED) ")
    print(f"="*50)
    print(f" {'METRIC':<20} | {'TAX-FREE (GROSS)':>12} | {'PRODUCTION (NET)':>12}")
    print(f" {'-'*20} + {'-'*12} + {'-'*12}")
    print(f" {'Total Profit (%)':<20} | {res_gross['profit_pct']:>+11.2f}% | {res_net['profit_pct']:>+11.2f}%")
    print(f" {'Final Assets (JPY)':<20} | {int(res_gross['final_assets']):>11,d} | {int(res_net['final_assets']):>11,d}")
    print(f" {'Total Trades':<20} | {res_gross['trade_count']:>11} | {res_net['trade_count']:>11}")
    print(f" {'Monthly Win Rate':<20} | {res_gross['monthly_win_rate']:>11.1f}% | {res_net['monthly_win_rate']:>11.1f}%")
    print(f" {'Sharpe Ratio':<20} | {'-':>11} | {m_sharpe:>11.3f}")
    print(f"="*50 + "\n")
