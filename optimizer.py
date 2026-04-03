import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime

sys.path.append(os.getcwd())
from core.config import DATA_FILE, JST, TAX_RATE, MIN_PRICE, MAX_PRICE, MAX_ALLOCATION_AMOUNT, LIQUIDITY_LIMIT_RATE
from core.logic import calculate_all_technicals_v12

def run_numpy_backtest_v12(univ_indices, bundle_np, timeline, initial_cash=1000000, max_pos=5, tp=0.07, sl=0.03, time_limit=3, max_allocation=5000000, liquidity_rate=0.01):
    cash_net, cash_gross = float(initial_cash), float(initial_cash)
    port_net, port_gross = [], []
    t_net, t_gross = 0, 0
    annual_profit_net, tax_paid_this_year, current_year = 0, 0, timeline[0].year
    TAX_RATE = 0.20315
    open_np, close_np = bundle_np['Open'], bundle_np['Close']
    high_np, low_np = bundle_np['High'], bundle_np['Low']
    sma20_np, ret3_np = bundle_np['SMA20'], bundle_np['Ret3']
    volume_np, sma20_vol_np = bundle_np['Volume'], bundle_np['SMA20_Vol']
    ht_np = bundle_np['HT']
    adv_np = bundle_np['ADV']
    warmup, T = 25, len(timeline)
    
    for i in range(warmup, T):
        curr_time = timeline[i]
        
        if curr_time.year != current_year:
            annual_profit_net = 0; tax_paid_this_year = 0; current_year = curr_time.year

        # 1. Manage Positions (NET)
        nxt_net = []
        pending_cash_net = 0
        for p in port_net:
            p['held_days'] += 1
            ticker_idx = p['s_idx']
            
            # Management logic remains same, but timing of cash recovery changes
            if high_np[i, ticker_idx] >= p['buy_price'] * (1 + tp):
                # Immediate exit (Intraday)
                exit_p = p['buy_price'] * (1 + tp)
                realized = (exit_p - p['buy_price']) * p['shares']
                annual_profit_net += realized
                new_tax = max(0, int(annual_profit_net * TAX_RATE))
                tax_diff = new_tax - tax_paid_this_year
                tax_paid_this_year = new_tax
                cash_net += (exit_p * p['shares']) - tax_diff
                t_net += 1
            elif low_np[i, ticker_idx] <= p['buy_price'] * (1 - sl):
                # Immediate exit (Intraday)
                exit_p = p['buy_price'] * (1 - sl)
                realized = (exit_p - p['buy_price']) * p['shares']
                annual_profit_net += realized
                new_tax = max(0, int(annual_profit_net * TAX_RATE))
                tax_diff = new_tax - tax_paid_this_year
                tax_paid_this_year = new_tax
                cash_net += (exit_p * p['shares']) - tax_diff
                t_net += 1
            elif p['held_days'] >= time_limit:
                # Time limit exit (Next Open)
                # Matches backtest's logic of exiting at Open[i+1]
                if i + 1 < T:
                    exit_p = open_np[i + 1, ticker_idx]
                    if np.isnan(exit_p): exit_p = close_np[i, ticker_idx]
                else: 
                    exit_p = close_np[i, ticker_idx]
                
                realized = (exit_p - p['buy_price']) * p['shares']
                annual_profit_net += realized
                new_tax = max(0, int(annual_profit_net * TAX_RATE))
                tax_diff = new_tax - tax_paid_this_year
                tax_paid_this_year = new_tax
                # IMPORTANT: Cash is recovered BUT cannot be used for today's scan/buy
                # To simplify: we'll add it AFTER the buying loop
                pending_cash_net += (exit_p * p['shares']) - tax_diff
                t_net += 1
            else:
                nxt_net.append(p)
        port_net = nxt_net

        # 2. Manage Positions (GROSS) - Same logic
        nxt_gross = []
        pending_cash_gross = 0
        for p in port_gross:
            p['held_days'] += 1
            ticker_idx = p['s_idx']
            if high_np[i, ticker_idx] >= p['buy_price'] * (1 + tp):
                cash_gross += (p['buy_price'] * (1 + tp) * p['shares'])
                t_gross += 1
            elif low_np[i, ticker_idx] <= p['buy_price'] * (1 - sl):
                cash_gross += (p['buy_price'] * (1 - sl) * p['shares'])
                t_gross += 1
            elif p['held_days'] >= time_limit:
                if i + 1 < T:
                    exit_p = open_np[i + 1, ticker_idx]
                    if np.isnan(exit_p): exit_p = close_np[i, ticker_idx]
                else: exit_p = close_np[i, ticker_idx]
                pending_cash_gross += (exit_p * p['shares'])
                t_gross += 1
            else:
                nxt_gross.append(p)
        port_gross = nxt_gross

        # 2. Scanning & Buying (Sync with current day indicators)
        if i + 1 < T:
            idx_scan = i
            cp_u = close_np[idx_scan, univ_indices]
            # BUG FIX: Added Ret3 > 5 filter to match core/logic.py
            valid_mask = (cp_u >= MIN_PRICE) & (cp_u <= MAX_PRICE) & \
                        (cp_u > sma20_np[idx_scan, univ_indices]) & \
                        (ret3_np[idx_scan, univ_indices] > 5) & \
                        (volume_np[idx_scan, univ_indices] > sma20_vol_np[idx_scan, univ_indices] * 1.5) & \
                        (cp_u > ht_np[idx_scan, univ_indices])
            valid_can_idx = univ_indices[valid_mask]
            
            if len(valid_can_idx) > 0:
                # 2a. NET Buy
                if len(port_net) < max_pos:
                    sorted_can_idx = valid_can_idx[np.argsort(ret3_np[idx_scan, valid_can_idx])[::-1]]
                    for s_idx in sorted_can_idx:
                        if len(port_net) >= max_pos: break
                        if s_idx in [pw['s_idx'] for pw in port_net]: continue
                        
                        total_eq_net = cash_net + sum(close_np[i, p['s_idx']] * p['shares'] for p in port_net)
                        max_cap = min(total_eq_net / max_pos, max_allocation)
                        
                        # Dynamic Liquidity Cap
                        adv_yen = adv_np[i, s_idx]
                        if adv_yen > 0:
                            max_cap = min(max_cap, adv_yen * liquidity_rate)

                        buy_p = open_np[i+1, s_idx]
                        if not np.isnan(buy_p):
                            sh = int(min(cash_net // buy_p, max_cap // buy_p))
                            sh = (sh // 100) * 100
                            if sh >= 100:
                                port_net.append({"s_idx": s_idx, "buy_price": buy_p, "shares": sh, "held_days": 0})
                                cash_net -= float(buy_p * sh)
                
                # 2b. GROSS Buy
                if len(port_gross) < max_pos:
                    sorted_can_idx = valid_can_idx[np.argsort(ret3_np[idx_scan, valid_can_idx])[::-1]]
                    for s_idx in sorted_can_idx:
                        if len(port_gross) >= max_pos: break
                        if s_idx in [pw['s_idx'] for pw in port_gross]: continue
                        
                        total_eq_gross = cash_gross + sum(close_np[i, p['s_idx']] * p['shares'] for p in port_gross)
                        max_cap = min(total_eq_gross / max_pos, max_allocation)
                        
                        # Dynamic Liquidity Cap
                        adv_yen = adv_np[i, s_idx]
                        if adv_yen > 0:
                            max_cap = min(max_cap, adv_yen * liquidity_rate)

                        buy_p = open_np[i+1, s_idx]
                        if not np.isnan(buy_p):
                            sh = int(min(cash_gross // buy_p, max_cap // buy_p))
                            sh = (sh // 100) * 100
                            if sh >= 100:
                                port_gross.append({"s_idx": s_idx, "buy_price": buy_p, "shares": sh, "held_days": 0})
                                cash_gross -= float(buy_p * sh)
        
        # 3. Post-Buy Cash Recovery (Cash from time-limit exits becomes available for tomorrow)
        cash_net += pending_cash_net
        cash_gross += pending_cash_gross

    val_net = cash_net + sum(close_np[-1, p['s_idx']] * p['shares'] for p in port_net)
    val_gross = cash_gross + sum(close_np[-1, p['s_idx']] * p['shares'] for p in port_gross)
    return (val_net-initial_cash)/initial_cash*100, (val_gross-initial_cash)/initial_cash*100, t_net

if __name__ == "__main__":
    from core.config import TARGET_MARKETS, INITIAL_CASH
    df_sym = pd.read_csv(DATA_FILE)
    univ_codes = [str(c) for i, c in enumerate(df_sym['コード']) if df_sym.iloc[i]['市場・商品区分'] in TARGET_MARKETS]
    
    # Matching backtest.py EXACTLY: Load 3616 cache and filter down
    univ_cache = os.path.join("data_cache", "hist_3616stocks_2021-01-01_2026-03-29_None_1d_v4.pkl")
    if not os.path.exists(univ_cache):
        print(f"Error: Cache not found at {univ_cache}")
        sys.exit(1)
        
    print(f"Loading base cache: {univ_cache}")
    all_data_full = pd.read_pickle(univ_cache)
    
    # Filtering loop logic from backtest.py 
    target_tickers = [f"{code}.T" for code in univ_codes]
    valid_tickers = [t for t in target_tickers if t in all_data_full.columns.get_level_values(0).unique()]
    all_data = all_data_full.loc[:, (valid_tickers, slice(None))]
    all_data.index = all_data.index.tz_localize('UTC').tz_convert(JST)
    
    print(f"Universe Size: {len(valid_tickers)} stocks (Filtered from {len(univ_codes)} initial codes)")
    bundle_static = calculate_all_technicals_v12(all_data) 
    # --- ADV (Turnover) 5-day average calculation ---
    turnover = (bundle_static['Volume'] * bundle_static['Close']).rolling(5).mean()
    bundle_static['ADV'] = turnover

    tickers = bundle_static['Close'].columns.tolist()
    timeline = bundle_static["Close"].index.unique().sort_values()
    univ_indices = np.array([tickers.index(t) for t in valid_tickers])
    bundle_np = {k: bundle_static[k].to_numpy() for k in bundle_static}
    
    results = []
    tp_list, sl_list, pos_list, time_list = [0.03, 0.05, 0.07, 0.10, 0.15], [0.03, 0.05], [5, 10, 20], [3, 5, 10]
    
    print(f"Starting V12.0 HYPER-OPTIMIZATION (Growth Market)...")
    
    for tp in tp_list:
        for sl in sl_list:
            for p in pos_list:
                for t in time_list:
                    p_net, p_gross, t_cnt = run_numpy_backtest_v12(univ_indices, bundle_np, timeline, max_pos=p, tp=tp, sl=sl, time_limit=t, max_allocation=MAX_ALLOCATION_AMOUNT, liquidity_rate=LIQUIDITY_LIMIT_RATE)
                    results.append({"tp":tp, "sl":sl, "p":p, "t":t, "p_net":p_net, "p_gross":p_gross, "trades":t_cnt})
                    print(f"Tested: TP:{tp*100:>2.0f}% SL:{sl*100:>2.0f}% POS:{p:<2} T:{t:<2} -> NET:{p_net:>+10.2f}% | GROSS:{p_gross:>+10.2f}% | TRADES:{t_cnt}", flush=True)

    print("\n" + "="*95)
    print(" V12.0 GROWTH MONSTER RANKING (SYNCHRONIZED)")
    print("="*95)
    print(" RANK | TP%  | SL%  | POS | TIME | NET PROFIT | GROSS PROFIT | TRADES")
    print(" ---  + ---- + ---- + --- + ---- + ---------- + ------------ + ------")
    
    results.sort(key=lambda x: x['p_net'], reverse=True)
    report = ""
    for i, res in enumerate(results[:10], 1):
        line = f" #{i:<2}  | {res['tp']*100:>2.0f}% | {res['sl']*100:>2.0f}% | {res['p']:<3} | {res['t']:<4} | {res['p_net']:>+10.2f}% | {res['p_gross']:>+12.2f}% | {res['trades']}"
        print(line)
        report += line + "\n"
    print("="*95)
    with open("opt_v12_ranking.txt", "w", encoding="utf-8") as f: f.write(report)
