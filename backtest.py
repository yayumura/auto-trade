import pandas as pd
import numpy as np

def run_backtest_v16_production(univ_indices, bundle_np, timeline, breadth_ratio,
                                 initial_cash=10000000, max_pos=10, 
                                 sl_mult=5.0, tp_mult=15.0, leverage_rate=2.0, breadth_threshold=0.4,
                                 slippage=0.001, use_sma_exit=True, exit_buffer=0.985, 
                                 verbose=False):
    """
    V22.2 Market Neutral Absolute Return Model
    - Simultaneous L5:S5 Selection (RS Lead/Lag)
    - Risk Parity Sizing: (Equity * 0.5%) / ATR
    - 2-Day Unrealized Loss Time Stop
    - 3*ATR Profit Protection (Break-even Stop)
    """
    T = len(timeline)
    cash = float(initial_cash)
    portfolio = []
    trade_count = 0
    monthly_assets = {}
    trade_ledger = []
    
    close_np = bundle_np['Close']
    open_np, high_np, low_np = bundle_np['Open'], bundle_np['High'], bundle_np['Low']
    sma5_np = bundle_np['SMA5']
    sma20_np = bundle_np['SMA20']
    sma100_np = bundle_np['SMA100']
    atr_np = bundle_np['ATR']
    
    idx_1321 = bundle_np['tickers'].index('1321.T') if '1321.T' in bundle_np['tickers'] else None
    
    for i in range(100, T):
        curr_time = timeline[i]
        is_diag = False
        y, m = curr_time.year, curr_time.month
        if (y == 2021 and m == 12) or (y == 2022 and m == 1) or (y == 2023 and (10 <= m <= 12)):
            is_diag = True

        current_profits = 0.0
        for p in portfolio:
            cp = np.nan_to_num(close_np[i, p['s_idx']])
            if cp <= 0: cp = p['buy_price']
            current_profits += (cp - p['buy_price']) * p['shares'] if p['direction'] == 'LONG' else (p['buy_price'] - cp) * p['shares']
        
        total_equity = cash + current_profits
        if i % 20 == 0:
            monthly_assets[curr_time.strftime('%Y-%m')] = total_equity

        # 1. Management Loop
        new_portfolio = []
        for p in portfolio:
            tidx = p['s_idx']
            direction = p['direction']
            ticker = bundle_np['tickers'][tidx]
            today_open = open_np[i, tidx]
            today_high = high_np[i, tidx]
            today_low = low_np[i, tidx]
            atr = atr_np[i, tidx]
            
            if np.isnan(today_open) or np.isnan(today_high) or np.isnan(today_low):
                p['held_days'] += 1
                new_portfolio.append(p)
                continue
            
            # [V22.2] 3*ATR Profit Protection
            if direction == 'LONG':
                p['sl_price'] = max(p['sl_price'], today_high - (p['entry_atr'] * sl_mult))
                if today_low >= p['buy_price'] + (p['entry_atr'] * 3.0):
                    p['sl_price'] = max(p['sl_price'], p['buy_price'] * 1.001)
            else: # SHORT
                p['sl_price'] = min(p['sl_price'], today_low + (p['entry_atr'] * sl_mult))
                if today_high <= p['buy_price'] - (p['entry_atr'] * 3.0):
                    p['sl_price'] = min(p['sl_price'], p['buy_price'] * 0.999)
            
            exit_p = None
            exit_reason = ""
            
            if use_sma_exit and p.get('exit_next_open', False):
                exit_p, exit_reason = today_open, "SMA20 Breach / Stagnation"
            
            if exit_p is None:
                if direction == 'LONG':
                    if today_open <= p['sl_price']: exit_p, exit_reason = today_open, "SL (Gap)"
                    elif today_low <= p['sl_price']: exit_p, exit_reason = p['sl_price'], "SL"
                    elif today_high >= p['tp_price']: exit_p, exit_reason = p['tp_price'], "TP"
                    # [V22.2] 2-Day Unrealized Loss Stop
                    elif p['held_days'] >= 2 and today_open < p['buy_price']:
                        exit_p, exit_reason = today_open, "Fast Loss Stop (2d)"
                    elif p['held_days'] >= 60: exit_p, exit_reason = today_open, "Time Stop (60d)"
                else: # SHORT
                    if today_open >= p['sl_price']: exit_p, exit_reason = today_open, "SL (Gap)"
                    elif today_high >= p['sl_price']: exit_p, exit_reason = p['sl_price'], "SL"
                    elif today_low <= p['tp_price']: exit_p, exit_reason = p['tp_price'], "TP"
                    # [V22.2] 2-Day Unrealized Loss Stop
                    elif p['held_days'] >= 2 and today_open > p['buy_price']:
                        exit_p, exit_reason = today_open, "Fast Loss Stop (2d)"
                    elif p['held_days'] >= 60: exit_p, exit_reason = today_open, "Time Stop (60d)"
            
            if exit_p is not None:
                curr_slippage = slippage if direction == 'LONG' else 0.002
                if direction == 'LONG':
                    real_exit = exit_p * (1.0 - curr_slippage)
                    profit = (real_exit - p['buy_price']) * p['shares']
                else: # SHORT
                    real_exit = exit_p * (1.0 + curr_slippage)
                    profit = (p['buy_price'] - real_exit) * p['shares']
                
                trade_record = {
                    "ticker": ticker, "direction": direction, "entry_date": p['entry_date'],
                    "exit_date": curr_time.strftime('%Y-%m-%d'), "entry_price": p['buy_price'],
                    "exit_price": real_exit, "profit": profit,
                    "profit_pct": (real_exit / p['buy_price'] - 1) * 100 if direction == 'LONG' else (p['buy_price'] / real_exit - 1) * 100,
                    "reason": exit_reason, "entry_breadth": p['entry_breadth']
                }
                trade_ledger.append(trade_record)
                if is_diag and profit < 0:
                    print(f"💀 [Loss] {curr_time.strftime('%Y-%m-%d')} | {ticker:10} | {direction:5} | {exit_reason:20} | PnL: {profit:,.0f}")
                cash += profit
                trade_count += 1
            else:
                p['held_days'] += 1
                today_close = close_np[i, tidx]
                today_sma20 = sma20_np[i, tidx]
                if not np.isnan(today_close):
                    # Keep SMA20 breach logic as secondary check
                    if direction == 'LONG' and today_close < today_sma20 * exit_buffer: p['exit_next_open'] = True
                    elif direction == 'SHORT' and today_close > today_sma20 * (2.0 - exit_buffer): p['exit_next_open'] = True
                new_portfolio.append(p)
        portfolio = new_portfolio

        # 2. Entry Loop (Market Neutral L5:S5)
        if i + 1 >= T: continue
        br = breadth_ratio[i]
        
        # [V22.2] No macro filter. Always scan for both directions.
        c_u, s5_u, s20_u, s100_u = close_np[i, univ_indices], sma5_np[i, univ_indices], sma20_np[i, univ_indices], sma100_np[i, univ_indices]
        h_u, l_u, atr_u = high_np[i, univ_indices], low_np[i, univ_indices], atr_np[i, univ_indices]
        rs_u = s5_u / (s100_u + 1e-9)
        
        valid_longs = []
        valid_shorts = []
        
        # Long candidates (Strong RS & s20 pullback)
        mask_l = (s5_u > s20_u) & (s20_u > s100_u) & (c_u < s20_u * 1.05) & (c_u > s20_u * 0.95)
        if mask_l.any():
            valid_longs = [(rs_u[m], idx, 'LONG') for m, idx in zip(np.where(mask_l)[0], univ_indices[mask_l])]
            
        # Short candidates (Weak RS & s20 pullback)
        mask_s = (s5_u < s20_u) & (s20_u < s100_u) & (c_u < s20_u * 1.05) & (c_u > s20_u * 0.95)
        if mask_s.any():
            valid_shorts = [(rs_u[m], idx, 'SHORT') for m, idx in zip(np.where(mask_s)[0], univ_indices[mask_s])]
            
        best_longs = sorted(valid_longs, key=lambda x: x[0], reverse=True)[:5]
        best_shorts = sorted(valid_shorts, key=lambda x: x[0], reverse=False)[:5]
        
        candidates = best_longs + best_shorts
        for score, s_idx, direction in candidates:
            if len(portfolio) >= max_pos: break
            if s_idx in [p['s_idx'] for p in portfolio]: continue
            
            buy_v = open_np[i+1, s_idx]
            if not np.isnan(buy_v) and buy_v > 0:
                entry_p = buy_v * (1.0 + slippage if direction == 'LONG' else 1.0 - 0.002)
                entry_atr = max(1.0, np.nan_to_num(atr_np[i, s_idx]))
                
                # [V22.2 Tuning] Aggressive Risk Parity Sizing
                # Risk allowance: 2.0% of Total Equity per 1*ATR move.
                target_risk_amount = total_equity * 0.02 
                shares_by_risk = target_risk_amount / entry_atr
                
                # Allocation Cap: (TotalEquity * Leverage) / MaxPositions
                max_alloc_yen = (total_equity * leverage_rate) / max_pos
                shares_by_cap = max_alloc_yen / entry_p
                
                sh = (int(min(shares_by_risk, shares_by_cap)) // 100) * 100
                
                if sh >= 100:
                    p_item = {
                        "s_idx": s_idx, "buy_price": entry_p, "shares": sh, "held_days": 0,
                        "entry_atr": entry_atr, "direction": direction,
                        "entry_date": curr_time.strftime('%Y-%m-%d'), "entry_breadth": br
                    }
                    if direction == 'LONG':
                        p_item.update({"sl_price": entry_p - (entry_atr * sl_mult), "tp_price": entry_p + (entry_atr * tp_mult)})
                    else:
                        p_item.update({"sl_price": entry_p + (entry_atr * sl_mult), "tp_price": entry_p - (entry_atr * tp_mult)})
                    portfolio.append(p_item)
                    cash -= 0 # In margin trading simulated here, we track cash as 'Free Margin' if needed, but simplicity wins.
                    # Wait, in this sim, cash = equity - total_position_value? No, cash is cumulative PnL.
                    # Let's keep the existing logic where profit is added to cash.

    if trade_ledger:
        import os
        os.makedirs("data/simulation", exist_ok=True)
        pd.DataFrame(trade_ledger).to_csv("data/simulation/trade_ledger.csv", index=False, encoding="utf-8-sig")

    final_equity = cash + sum((np.nan_to_num(close_np[-1, p['s_idx']]) - p['buy_price']) * p['shares'] if p['direction'] == 'LONG' else (p['buy_price'] - np.nan_to_num(close_np[-1, p['s_idx']])) * p['shares'] for p in portfolio)
    return float(final_equity), trade_count, monthly_assets, [t['profit'] for t in trade_ledger]
