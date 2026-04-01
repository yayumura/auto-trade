import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime

sys.path.append(os.getcwd())
try:
    from core.logic import calculate_all_technicals_v10
except ImportError:
    # Handle direct execution
    from core.logic import calculate_all_technicals_v10

from core.config import DATA_FILE, JST, TAX_RATE

def run_numpy_backtest(univ_indices, bundle_np, timeline, initial_cash=1000000, max_pos=3, overheat=30.0, score_mode="volume", apply_tax=True):
    cash = float(initial_cash)
    portfolio, trade_history, pending_exits = [], [], []
    annual_profit = 0; tax_paid_this_year = 0; current_year = timeline[0].year
    etf_idx = bundle_np['etf_idx']

    for i in range(len(timeline)):
        current_year_val = timeline[i].year
        if current_year_val != current_year:
            annual_profit = 0; tax_paid_this_year = 0; current_year = current_year_val

        if pending_exits:
            for pe in pending_exits:
                realized = (pe['price'] - pe['buy_price']) * pe['shares']
                if apply_tax:
                    annual_profit += realized
                    new_total_tax = max(0, int(annual_profit * TAX_RATE))
                    tax_diff = new_total_tax - tax_paid_this_year
                    tax_paid_this_year = new_total_tax
                    cash += (pe['price'] * pe['shares']) - tax_diff
                else:
                    cash += (pe['price'] * pe['shares'])
                trade_history.append(pe)
            pending_exits = []

        if portfolio:
            new_portfolio = []
            is_panic = bundle_np['Close'][i, etf_idx] < bundle_np['SMA200'][i, etf_idx]
            for p in portfolio:
                if p.get('pending_buy'):
                    new_portfolio.append(p); continue
                s_idx = p['s_idx']
                cp, lp, hp, le_std = bundle_np['Close'][i, s_idx], bundle_np['Low'][i, s_idx], bundle_np['High'][i, s_idx], bundle_np['LE'][i, s_idx]
                atr = bundle_np['ATR'][i, s_idx]
                if hp > p['max_p']: p['max_p'] = hp
                p['held_days'] += 1
                le = le_std
                if (p['max_p'] - p['buy_price']) > (1.5 * atr): le = max(le, p['buy_price'])
                exit_p = 0; reason = None
                if p['held_days'] >= 10 and (cp - p['buy_price']) < (0.5 * atr):
                    reason = "Time Stop"; exit_p = bundle_np['Open'][i+1, s_idx] if i+1 < len(timeline) else cp
                elif is_panic:
                    reason = "Shield"; exit_p = bundle_np['Open'][i, s_idx]
                elif bundle_np['Open'][i, s_idx] < le:
                    reason = "Gap Down"; exit_p = bundle_np['Open'][i, s_idx]
                elif lp < le:
                    reason = "Trend Exit"; exit_p = le
                if reason:
                    pending_exits.append({"code": p['code'], "price": exit_p, "buy_price": p['buy_price'], "shares": p['shares']})
                else:
                    new_portfolio.append(p)
            portfolio = new_portfolio

        for p in portfolio:
            if p.get('pending_buy') and p.get('buy_time_idx') == i:
                s_idx = p['s_idx']
                buy_p = bundle_np['Open'][i, s_idx]
                if not np.isnan(buy_p):
                    prev_i = max(0, i-1)
                    curr_v = sum(bundle_np['Close'][prev_i, p_['s_idx']] * p_['shares'] for p_ in portfolio if not p_.get('pending_buy'))
                    equity = cash + curr_v
                    shares = int((equity / max_pos) // buy_p)
                    shares = (shares // 100) * 100
                    if shares >= 100:
                        p.update({"buy_price": buy_p, "shares": shares, "pending_buy": False, "max_p": buy_p, "held_days": 0})
                        cash -= float(buy_p * shares)
                        p['valid'] = True
                    else: p['valid'] = False
                else: p['valid'] = False
        portfolio = [p for p in portfolio if not p.get('pending_buy') or p.get('valid')]
        
        held_cnt = len([p for p in portfolio if not p.get('pending_buy')])
        if held_cnt < max_pos and i + 1 < len(timeline):
            if bundle_np['Close'][i, etf_idx] < bundle_np['SMA200'][i, etf_idx]: continue
            candidates = []
            for s_idx in univ_indices:
                cp = bundle_np['Close'][i, s_idx]
                if np.isnan(cp) or cp < 100: continue
                if bundle_np['Divergence'][i, s_idx] > overheat: continue
                if (bundle_np['SMA200_Slope'][i, s_idx] > 0 and cp > bundle_np['SMA200'][i, s_idx] and cp > bundle_np['HT'][i, s_idx] and bundle_np['Vol_Confirm'][i, s_idx] > 0):
                    score = float(bundle_np['Volume'][i, s_idx] * cp) if score_mode == "turnover" else float(bundle_np['Volume'][i, s_idx])
                    candidates.append({"s_idx": s_idx, "score": score, "code": bundle_np['tickers'][s_idx].replace('.T','')})
            
            best_list = sorted(candidates, key=lambda x: x['score'], reverse=True)[:max_pos-held_cnt]
            for best in best_list:
                if held_cnt >= max_pos: break
                if not any(p['s_idx'] == best['s_idx'] for p in portfolio):
                    portfolio.append({"s_idx": best['s_idx'], "code": best['code'], "buy_time_idx": i+1, "pending_buy": True})
                    held_cnt += 1

    final_v = sum(bundle_np['Close'][-1, p['s_idx']] * p['shares'] for p in portfolio if not p.get('pending_buy'))
    return (cash + final_v - initial_cash) / initial_cash * 100, len(trade_history)

if __name__ == "__main__":
    df_sym = pd.read_csv(DATA_FILE)
    univ_codes = [str(c) for i, c in enumerate(df_sym['コード']) if df_sym.iloc[i]['市場・商品区分'] == 'プライム（内国株式）']
    univ_cache = os.path.join("data_cache", "hist_3616stocks_2021-01-01_2026-03-29_None_1d_v4.pkl")
    all_data = pd.read_pickle(univ_cache)
    all_data.index = all_data.index.tz_localize('UTC').tz_convert(JST)

    results = []
    b_range = [20, 25, 30, 35]
    e_range = [10, 15, 20]
    p_range = [1, 2, 3]
    oh_range = [25.0, 30.0, 40.0]
    s_range = ["volume", "turnover"]

    print(f"Starting FAST SUPER OPTIMIZATION (NUMPY) ({len(b_range)*len(e_range)*len(p_range)*len(oh_range)*len(s_range)} patterns)...")

    for b in b_range:
        for e in e_range:
            print(f"\n[PHASE] Calibrating Bundle B:{b} E:{e} ...")
            bundle = calculate_all_technicals_v10(all_data, breakout_p=b, exit_p=e)
            tickers = bundle['Close'].columns.tolist()
            bundle_np = {k: bundle[k].to_numpy() for k in ["Open", "High", "Low", "Close", "SMA200", "SMA200_Slope", "HT", "Vol_Confirm", "Volume", "Divergence", "ATR", "LE"]}
            bundle_np['tickers'] = tickers
            bundle_np['etf_idx'] = tickers.index("1321.T")
            univ_indices = [tickers.index(f"{c}.T") for c in univ_codes if f"{c}.T" in tickers]
            timeline = bundle["Close"].index.unique().sort_values()

            for p in p_range:
                for oh in oh_range:
                    for s in s_range:
                        p_net, t_net = run_numpy_backtest(univ_indices, bundle_np, timeline, max_pos=p, overheat=oh, score_mode=s)
                        results.append({"b":b, "e":e, "p":p, "oh":oh, "s":s, "p_net":p_net, "trades":t_net})
                        if p_net > 500:
                            print(f"  !!! B:{b} E:{e} Pos:{p} OH:{oh}% Score:{s} | NET: {p_net:+.2f}% !!!")

    best = sorted(results, key=lambda x: x['p_net'], reverse=True)[0]
    print(f"\n" + "="*50)
    print(f" SUPER OPTIMIZER WINNER FOUND ")
    print(f"="*50)
    print(f" Breakout (B): {best['b']}")
    print(f" Exit (E):     {best['e']}")
    print(f" Positions:    {best['p']}")
    print(f" Overheat:     {best['oh']}%")
    print(f" Scoring:      {best['s']}")
    print(f" MAX REAL NET PROFIT: {best['p_net']:+.2f}%")
    print(f"="*50)
