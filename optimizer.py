import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime

sys.path.append(os.getcwd())
try:
    from core.logic import calculate_all_technicals_v10
except ImportError:
    from core.logic import calculate_all_technicals_v10

from core.config import DATA_FILE, JST, TAX_RATE

def run_numpy_backtest(univ_indices, bundle_np, timeline, initial_cash=1000000, max_pos=3, overheat=30.0, score_mode="turnover"):
    # Net Account (Production)
    cash_n = float(initial_cash)
    portfolio_n = []
    pending_exits_n = []
    annual_profit_n = 0
    tax_paid_this_year_n = 0
    current_year_n = timeline[0].year

    # Gross Account (Tax-Free)
    cash_g = float(initial_cash)
    portfolio_g = []
    pending_exits_g = []

    close_np = bundle_np['Close']
    open_np = bundle_np['Open']
    low_np = bundle_np['Low']
    high_np = bundle_np['High']
    sma200_np = bundle_np['SMA200']
    sma200_slope_np = bundle_np['SMA200_Slope']
    vol_confirm_np = bundle_np['Vol_Confirm']
    volume_np = bundle_np['Volume']
    divergence_np = bundle_np['Divergence']
    atr_np = bundle_np['ATR']
    ht_np = bundle_np['HT']
    le_np = bundle_np['LE']
    etf_idx = bundle_np['etf_idx']

    for i in range(len(timeline)):
        if timeline[i].year != current_year_n:
            annual_profit_n = 0; tax_paid_this_year_n = 0; current_year_n = timeline[i].year

        # 1. Exit Exec
        if pending_exits_n:
            for pe in pending_exits_n:
                curr_op = open_np[i, pe['s_idx']]
                if not np.isnan(curr_op):
                    realized = (curr_op - pe['buy_price']) * pe['shares']
                    annual_profit_n += realized
                    new_tax = max(0, int(annual_profit_n * TAX_RATE))
                    tax_diff = new_tax - tax_paid_this_year_n
                    tax_paid_this_year_n = new_tax
                    cash_n += (curr_op * pe['shares']) - tax_diff
            pending_exits_n = []
        if pending_exits_g:
            for pe in pending_exits_g:
                curr_op = open_np[i, pe['s_idx']]
                if not np.isnan(curr_op):
                    cash_g += curr_op * pe['shares']
            pending_exits_g = []

        # 2. Position Management
        prev_i = max(0, i-1)
        is_bear = (close_np[prev_i, etf_idx] < sma200_np[prev_i, etf_idx]) if i > 0 else False

        def manage(portfolio, cash, is_bear, i, ann_prof=None, tax_paid=None):
            new_port, p_exits = [], []
            t_paid = tax_paid; a_prof = ann_prof
            for p in portfolio:
                if p.get('pending_buy'):
                    new_port.append(p); continue
                s_idx = p['s_idx']
                op, cp, lp, hp, le_std = open_np[i, s_idx], close_np[i, s_idx], low_np[i, s_idx], high_np[i, s_idx], le_np[i, s_idx]
                atr = atr_np[i, s_idx]
                if hp > p['max_p']: p['max_p'] = hp
                p['held_days'] += 1
                le = le_std
                if (p['max_p'] - p['buy_price']) > (1.5 * atr): le = max(le, p['buy_price'])
                
                exit_p = 0; reason = None; timing = "immediate"
                if is_bear: reason = "Shield"; exit_p = op; timing = "immediate"
                elif op < le: reason = "Gap"; exit_p = op; timing = "immediate"
                elif lp < le: reason = "Trend"; exit_p = le; timing = "immediate"
                elif p['held_days'] >= 10 and (cp - p['buy_price']) < (0.5 * atr):
                    reason = "Time"; timing = "next_open"

                if reason:
                    if timing == "immediate":
                        realized = (exit_p - p['buy_price']) * p['shares']
                        if a_prof is not None:
                            a_prof += realized
                            new_t = max(0, int(a_prof * TAX_RATE)); tax_diff = new_t - t_paid; t_paid = new_t
                            cash += (exit_p * p['shares']) - tax_diff
                        else: cash += (exit_p * p['shares'])
                    else: p_exits.append({"s_idx": s_idx, "buy_price": p['buy_price'], "shares": p['shares']})
                else: new_port.append(p)
            return new_port, cash, p_exits, a_prof, t_paid

        portfolio_n, cash_n, exits_n, annual_profit_n, tax_paid_this_year_n = manage(portfolio_n, cash_n, is_bear, i, annual_profit_n, tax_paid_this_year_n)
        portfolio_g, cash_g, exits_g, _, _ = manage(portfolio_g, cash_g, is_bear, i)
        pending_exits_n.extend(exits_n); pending_exits_g.extend(exits_g)

        # 3. Buy Exec
        def execute_buys(portfolio, cash, i):
            for p in portfolio:
                if p.get('pending_buy') and p.get('buy_time_idx') == i:
                    s_idx = p['s_idx']
                    buy_p = open_np[i, s_idx]
                    if not np.isnan(buy_p):
                        prev_idx = max(0, i-1)
                        curr_v = sum(close_np[prev_idx, p_['s_idx']] * p_['shares'] for p_ in portfolio if not p_.get('pending_buy'))
                        equity = cash + curr_v
                        # [STRICT FIX] 買付余力を現金残高以下に制限
                        max_pos_cap = equity / max_pos
                        shares = int(min(cash, max_pos_cap) // buy_p)
                        shares = (shares // 100) * 100
                        if shares >= 100:
                            p.update({"buy_price": buy_p, "shares": shares, "pending_buy": False, "max_p": buy_p, "held_days": 0})
                            cash -= float(buy_p * shares)
                            p['valid'] = True
                        else: p['valid'] = False
                    else: p['valid'] = False
            return [p for p in portfolio if not p.get('pending_buy') or p.get('valid')], cash

        portfolio_n, cash_n = execute_buys(portfolio_n, cash_n, i)
        portfolio_g, cash_g = execute_buys(portfolio_g, cash_g, i)

        # 4. Scan
        held_cnt_n = len([p for p in portfolio_n if not p.get('pending_buy')])
        held_cnt_g = len([p for p in portfolio_g if not p.get('pending_buy')])
        if (held_cnt_n < max_pos or held_cnt_g < max_pos) and i + 1 < len(timeline):
            if close_np[i, etf_idx] < sma200_np[i, etf_idx]: continue
            cp_u = close_np[i, univ_indices]
            valid_mask = (cp_u >= 100) & (divergence_np[i, univ_indices] <= overheat) & \
                        (sma200_slope_np[i, univ_indices] > 0) & (cp_u > sma200_np[i, univ_indices]) & \
                        (cp_u > ht_np[i, univ_indices]) & (vol_confirm_np[i, univ_indices] > 0)
            if np.any(valid_mask):
                valid_can_idx = univ_indices[valid_mask]
                if score_mode == "turnover": scores = volume_np[i, valid_can_idx] * cp_u[valid_mask]
                elif score_mode == "momentum": scores = cp_u[valid_mask] / close_np[max(0,i-1), valid_can_idx]
                else: scores = volume_np[i, valid_can_idx]
                t_idx = np.argsort(scores)[::-1]
                for idx_v in t_idx:
                    s_idx = valid_can_idx[idx_v]
                    if held_cnt_n < max_pos and not any(p['s_idx'] == s_idx for p in portfolio_n):
                        portfolio_n.append({"s_idx": s_idx, "buy_time_idx": i+1, "pending_buy": True}); held_cnt_n += 1
                    if held_cnt_g < max_pos and not any(p['s_idx'] == s_idx for p in portfolio_g):
                        portfolio_g.append({"s_idx": s_idx, "buy_time_idx": i+1, "pending_buy": True}); held_cnt_g += 1

    final_v_n = sum(close_np[-1, p['s_idx']] * p['shares'] for p in portfolio_n if not p.get('pending_buy'))
    final_v_g = sum(close_np[-1, p['s_idx']] * p['shares'] for p in portfolio_g if not p.get('pending_buy'))
    return (cash_n + final_v_n - initial_cash) / initial_cash * 100, (cash_g + final_v_g - initial_cash) / initial_cash * 100

if __name__ == "__main__":
    df_sym = pd.read_csv(DATA_FILE)
    univ_codes = [str(c) for i, c in enumerate(df_sym['コード']) if df_sym.iloc[i]['市場・商品区分'] == 'プライム（内国株式）']
    univ_cache = os.path.join("data_cache", "hist_3616stocks_2021-01-01_2026-03-29_None_1d_v4.pkl")
    all_data = pd.read_pickle(univ_cache)
    all_data.index = all_data.index.tz_localize('UTC').tz_convert(JST)
    bundle_static = calculate_all_technicals_v10(all_data) 
    tickers = bundle_static['Close'].columns.tolist()
    timeline = bundle_static["Close"].index.unique().sort_values()
    univ_indices = np.array([tickers.index(f"{c}.T") for c in univ_codes if f"{c}.T" in tickers])
    common_np = {k: bundle_static[k].to_numpy() for k in ["Open", "High", "Low", "Close", "SMA200", "SMA200_Slope", "Vol_Confirm", "Volume", "Divergence", "ATR"]}
    common_np['etf_idx'] = tickers.index("1321.T")
    results = []
    b_range = [10, 15, 20, 25, 30, 40, 50, 60]
    e_range = [5, 10, 15, 20, 25, 30]
    p_range = [1, 2, 3, 4, 5]
    oh_range = [15.0, 25.0, 35.0]
    s_range = ["volume", "turnover", "momentum"]
    print(f"Starting FINAL SYNC MASK OPTIMIZATION (Strict Cash-Only)...")
    high_df = bundle_static['High']; low_df = bundle_static['Low']
    for b in b_range:
        ht_np = high_df.rolling(b).max().shift(1).to_numpy()
        for e in e_range:
            if e >= b: continue
            le_np = low_df.rolling(e).min().shift(1).to_numpy()
            bundle_local = common_np.copy(); bundle_local['HT'] = ht_np; bundle_local['LE'] = le_np
            for p in p_range:
                for oh in oh_range:
                    for s in s_range:
                        p_net, p_gross = run_numpy_backtest(univ_indices, bundle_local, timeline, max_pos=p, overheat=oh, score_mode=s)
                        results.append({"b":b, "e":e, "p":p, "oh":oh, "s":s, "p_net":p_net, "p_gross":p_gross})

    top_10 = sorted(results, key=lambda x: x['p_net'], reverse=True)[:10]
    report = "\n" + "="*70 + "\n FINAL SYNC RANKING \n" + "="*70 + "\n"
    report += " RANK | B  | E  | P | OH%  | SCORE    | NET PROFIT  | GROSS PROFIT\n"
    report += " ---  + -- + -- + - + ---- + -------- + ----------- + ------------\n"
    for i, res in enumerate(top_10):
        report += f" #{i+1:<2} | {res['b']:<2} | {res['e']:<2} | {res['p']:<1} | {res['oh']:<4.1f} | {res['s']:<8} | {res['p_net']:>+11.2f}% | {res['p_gross']:>+11.2f}%\n"
    report += "="*70 + "\n"
    best = top_10[0]
    report += f"\n[Ultimate Champion] B:{best['b']} E:{best['e']} Pos:{best['p']} OH:{best['oh']} Score:{best['s']} \n -> NET: {best['p_net']:+.2f}% | GROSS: {best['p_gross']:+.2f}%\n"
    print(report)
    with open("opt_final_ranking.txt", "w", encoding="utf-8") as f: f.write(report)
