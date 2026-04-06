import pandas as pd
import numpy as np

def run_backtest_v16_production(univ_indices, bundle_np, timeline, breadth_ratio,
                                 initial_cash=10000000, max_pos=10, 
                                 sl_mult=5.0, tp_mult=15.0, leverage_rate=2.0, breadth_threshold=0.4,
                                 slippage=0.001, use_sma_exit=True, exit_buffer=0.985, 
                                 verbose=False):
    """
    V22 Diagnostic Mode - THE IMPERIAL ORACLE
    - All-Weather L/S Logic with strict short-selling constraints.
    - Captures detailed trade ledger for failure pattern analysis.
    """
    T = len(timeline)
    cash = float(initial_cash)
    portfolio = []
    trade_count = 0
    monthly_assets = {}
    trade_ledger = [] # [V22] Diagnostic Ledger
    
    close_np = bundle_np['Close']
    open_np, high_np, low_np = bundle_np['Open'], bundle_np['High'], bundle_np['Low']
    sma5_np = bundle_np['SMA5']
    sma20_np = bundle_np['SMA20']
    sma100_np = bundle_np['SMA100']
    atr_np = bundle_np['ATR']
    
    idx_1321 = bundle_np['tickers'].index('1321.T') if '1321.T' in bundle_np['tickers'] else None
    
    for i in range(100, T):
        curr_time = timeline[i]
        
        # [V22] Diagnostic Logging Period Check
        is_diag = False
        y, m = curr_time.year, curr_time.month
        if (y == 2021 and m == 12) or (y == 2022 and m == 1) or (y == 2023 and (10 <= m <= 12)):
            is_diag = True

        current_profits = 0.0
        for p in portfolio:
            cp = np.nan_to_num(close_np[i, p['s_idx']])
            if cp <= 0: cp = p['buy_price']
            if p.get('direction', 'LONG') == 'LONG':
                current_profits += (cp - p['buy_price']) * p['shares']
            else:
                current_profits += (p['buy_price'] - cp) * p['shares']
        
        total_equity = cash + current_profits
        if i % 20 == 0:
            monthly_assets[curr_time.strftime('%Y-%m')] = total_equity

        # 1. Management
        new_portfolio = []
        for p in portfolio:
            tidx = p['s_idx']
            direction = p.get('direction', 'LONG')
            ticker = bundle_np['tickers'][tidx]
            today_open, today_high, today_low = open_np[i, tidx], high_np[i, tidx], low_np[i, tidx]
            
            if np.isnan(today_open) or np.isnan(today_high) or np.isnan(today_low):
                p['held_days'] += 1
                new_portfolio.append(p)
                continue
            
            # SL/TP Update (Trailing)
            if direction == 'LONG':
                p['sl_price'] = max(p['sl_price'], today_high - (p['entry_atr'] * sl_mult))
                if today_high >= p['buy_price'] + (p['entry_atr'] * 5.0):
                    p['sl_price'] = max(p['sl_price'], p['buy_price'] * 1.002)
            else: # SHORT
                p['sl_price'] = min(p['sl_price'], today_low + (p['entry_atr'] * sl_mult * 0.5))
                if today_low <= p['buy_price'] - (p['entry_atr'] * 5.0):
                    p['sl_price'] = min(p['sl_price'], p['buy_price'] * 0.998)
            
            exit_p = None
            exit_reason = ""
            
            if use_sma_exit and p.get('exit_next_open', False):
                exit_p = today_open
                exit_reason = "SMA20 Breach / Stagnation"
            
            if exit_p is None:
                if direction == 'LONG':
                    if today_open <= p['sl_price']: exit_p, exit_reason = today_open, "SL (Gap)"
                    elif today_low <= p['sl_price']: exit_p, exit_reason = p['sl_price'], "SL"
                    elif today_high >= p['tp_price']: exit_p, exit_reason = p['tp_price'], "TP"
                    elif p['held_days'] >= 60: exit_p, exit_reason = today_open, "Time Stop (60d)"
                else: # SHORT
                    if today_open >= p['sl_price']: exit_p, exit_reason = today_open, "SL (Gap)"
                    elif today_high >= p['sl_price']: exit_p, exit_reason = p['sl_price'], "SL"
                    elif today_low <= p['tp_price']: exit_p, exit_reason = p['tp_price'], "TP"
                    # [V22] Short specific time-stop: 5 days
                    elif p['held_days'] >= 5: exit_p, exit_reason = today_open, "Short Time Stop (5d)"
            
            if exit_p is not None:
                # [V22] Asymmetric Slippage for Short
                curr_slippage = slippage if direction == 'LONG' else 0.002
                
                if direction == 'LONG':
                    real_exit = exit_p * (1.0 - curr_slippage)
                    profit = (real_exit - p['buy_price']) * p['shares']
                else: # SHORT
                    real_exit = exit_p * (1.0 + curr_slippage)
                    profit = (p['buy_price'] - real_exit) * p['shares']
                
                trade_record = {
                    "ticker": ticker,
                    "direction": direction,
                    "entry_date": p['entry_date'],
                    "exit_date": curr_time.strftime('%Y-%m-%d'),
                    "entry_price": p['buy_price'],
                    "exit_price": real_exit,
                    "profit": profit,
                    "profit_pct": (real_exit / p['buy_price'] - 1) * 100 if direction == 'LONG' else (p['buy_price'] / real_exit - 1) * 100,
                    "reason": exit_reason,
                    "entry_breadth": p['entry_breadth']
                }
                trade_ledger.append(trade_record)
                
                if is_diag and profit < 0:
                    print(f"💀 [Loss] {curr_time.strftime('%Y-%m-%d')} | {ticker:10} | {direction:5} | {exit_reason:20} | PnL: {profit:,.0f} ({trade_record['profit_pct']:.1f}%)")

                cash += profit
                trade_count += 1
            else:
                p['held_days'] += 1
                today_close = close_np[i, tidx]
                today_sma20 = sma20_np[i, tidx]
                if not np.isnan(today_close):
                    if direction == 'LONG':
                        if today_close < today_sma20 * exit_buffer: p['exit_next_open'] = True
                        if p['held_days'] >= 20 and today_close <= p['buy_price']: p['exit_next_open'] = True
                    else: # SHORT
                        if today_close > today_sma20 * (2.0 - exit_buffer): p['exit_next_open'] = True
                        if p['held_days'] >= 20 and today_close >= p['buy_price']: p['exit_next_open'] = True
                        
                new_portfolio.append(p)
        portfolio = new_portfolio

        # 2. Entry
        if i + 1 >= T: continue
        br = breadth_ratio[i]
        allow_long = br >= 0.25
        allow_short = br < 0.25
        
        if idx_1321 is not None:
             is_bull_macro = close_np[i, idx_1321] >= sma100_np[i, idx_1321]
             if not is_bull_macro: allow_long = False
             if is_bull_macro: allow_short = False
        
        current_leverage = 1.0 
        if br >= 0.50: current_leverage = 3.0
        elif br >= 0.40: current_leverage = 2.0
        elif br >= 0.25: current_leverage = 1.0 
        else: current_leverage = 1.0 
        
        if len(portfolio) < max_pos and (allow_long or allow_short):
            current_exposure = sum(p['buy_price'] * p['shares'] for p in portfolio)
            buying_power = (total_equity * current_leverage) - current_exposure
            
            c_u, s5_u, s20_u, s100_u = close_np[i, univ_indices], sma5_np[i, univ_indices], sma20_np[i, univ_indices], sma100_np[i, univ_indices]
            h_u, l_u = high_np[i, univ_indices], low_np[i, univ_indices]
            atr_u = atr_np[i, univ_indices]
            
            valid_long_idx = []
            if allow_long:
                mask_l = (s5_u > s20_u) & (s20_u > s100_u) & (c_u < s20_u * 1.04) & (c_u > s20_u * 0.96) & \
                         (((c_u > close_np[i-1, univ_indices]) | (c_u > open_np[i, univ_indices])) & ((c_u - l_u) / (h_u - l_u + 1e-9) >= 0.5))
                if mask_l.any():
                    strength_l = s5_u[mask_l] / s100_u[mask_l]
                    valid_long_idx = [(s, idx, 'LONG') for s, idx in zip(strength_l, univ_indices[mask_l])]

            valid_short_idx = []
            if allow_short:
                mask_s = (s5_u < s20_u) & (s20_u < s100_u) & (c_u < s20_u * 1.02) & (c_u > s20_u * 0.98) & \
                         (((c_u < close_np[i-1, univ_indices]) | (c_u < open_np[i, univ_indices])) & ((h_u - c_u) / (h_u - l_u + 1e-9) >= 0.5))
                if mask_s.any():
                    strength_s = s100_u[mask_s] / s5_u[mask_s]
                    valid_short_idx = [(s, idx, 'SHORT') for s, idx in zip(strength_s, univ_indices[mask_s])]

            all_candidates = sorted(valid_long_idx + valid_short_idx, key=lambda x: x[0], reverse=True)
            for score, s_idx, direction in all_candidates:
                if len(portfolio) >= max_pos: break
                if s_idx in [p['s_idx'] for p in portfolio]: continue
                
                buy_v = open_np[i+1, s_idx]
                if not np.isnan(buy_v) and buy_v > 0:
                    entry_p = buy_v * (1.0 + slippage if direction == 'LONG' else 1.0 - 0.002)
                    entry_atr = max(1.0, np.nan_to_num(atr_np[i, s_idx]))
                    actual_ma = min((total_equity * current_leverage) / max_pos, buying_power)
                    sh = (int(actual_ma / entry_p) // 100) * 100
                    
                    if sh >= 100:
                        p_item = {
                            "s_idx": s_idx, "buy_price": entry_p, "shares": sh, "held_days": 0,
                            "entry_atr": entry_atr, "direction": direction,
                            "entry_date": timeline[i+1].strftime('%Y-%m-%d'),
                            "entry_breadth": br
                        }
                        if direction == 'LONG':
                            p_item.update({"sl_price": entry_p - (entry_atr * sl_mult), "tp_price": entry_p + (entry_atr * tp_mult)})
                        else:
                            p_item.update({"sl_price": entry_p + (entry_atr * sl_mult * 0.5), "tp_price": entry_p - (entry_atr * tp_mult * 0.5)})
                        portfolio.append(p_item)
                        buying_power -= entry_p * sh

    # Output Ledger to CSV
    if trade_ledger:
        import os
        os.makedirs("data/simulation", exist_ok=True)
        pd.DataFrame(trade_ledger).to_csv("data/simulation/trade_ledger.csv", index=False, encoding="utf-8-sig")
        print(f"📊 [Diagnostic] Trade Ledger saved to data/simulation/trade_ledger.csv ({len(trade_ledger)} trades)")

    current_profits = 0.0
    for p in portfolio:
        cp = np.nan_to_num(close_np[-1, p['s_idx']])
        if cp <= 0: cp = p['buy_price']
        current_profits += (cp - p['buy_price']) * p['shares'] if p.get('direction', 'LONG') == 'LONG' else (p['buy_price'] - cp) * p['shares']
            
    final = cash + current_profits
    return float(final), trade_count, monthly_assets, [t['profit'] for t in trade_ledger]

