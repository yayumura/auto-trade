import pandas as pd
import numpy as np

def run_backtest_v16_production(univ_indices, bundle_np, timeline, breadth_ratio,
                                 initial_cash=10000000, max_pos=10, 
                                 sl_mult=5.0, tp_mult=15.0, leverage_rate=3.0, breadth_threshold=0.30,
                                 slippage=0.001, use_sma_exit=True, exit_buffer=0.985, 
                                 verbose=False):
    """
    V25.0 Hybrid Alpha Backtest:
    - Supports Pullback LONG and Breakdown SHORT.
    - SHORT Macro: 0.30 <= Breadth < 0.50 AND Nikkei < SMA100.
    - SHORT Exit: Asymmetric (Hard-coded SL:5.0, TP:10.0).
    - SHORT Sizing: 0.5x of LONG allocation.
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
    ret60_np = bundle_np.get('Ret60', np.zeros_like(close_np))
    
    tickers = bundle_np['tickers']
    # Identify Nikkei 225 (1321.T) index for macro/alpha filtering
    nikkei_idx = -1
    if '1321.T' in tickers:
        nikkei_idx = list(tickers).index('1321.T')
    
    for i in range(100, T):
        curr_time = timeline[i]
        
        # 1. Management & Equity Calculation
        current_profits = 0.0
        for p in portfolio:
            cp = np.nan_to_num(close_np[i, p['s_idx']])
            if cp <= 0: cp = p['buy_price']
            if p['direction'] == 'LONG':
                current_profits += (cp - p['buy_price']) * p['shares']
            else:
                current_profits += (p['buy_price'] - cp) * p['shares']
        
        total_equity = cash + current_profits
        if i % 20 == 0:
            monthly_assets[curr_time.strftime('%Y-%m-%d')] = total_equity

        new_portfolio = []
        for p in portfolio:
            tidx = p['s_idx']
            ticker = tickers[tidx]
            today_open = open_np[i, tidx]
            today_high = high_np[i, tidx]
            today_low = low_np[i, tidx]
            direction = p['direction']
            
            if np.isnan(today_open):
                p['held_days'] += 1
                new_portfolio.append(p)
                continue
            
            # Trailing stop update (Direction-dependent)
            if direction == 'LONG':
                p['sl_price'] = max(p['sl_price'], today_high - (p['entry_atr'] * sl_mult))
                if today_low >= p['buy_price'] + (p['entry_atr'] * 3.0):
                    p['sl_price'] = max(p['sl_price'], p['buy_price'] * 1.001)
            else:
                # SHORT: Trailing stop moves DOWN with price
                p['sl_price'] = min(p['sl_price'], today_low + (p['entry_atr'] * 5.0))

            exit_p = None
            exit_reason = ""
            
            # Time Stop (60d)
            if p['held_days'] >= 60:
                exit_p, exit_reason = today_open, "Time Stop (60d)"
            
            # Technical Exit (SMA20 Breach - LONG only)
            if direction == 'LONG' and exit_p is None and use_sma_exit and p.get('exit_next_open', False):
                exit_p, exit_reason = today_open, "SMA20 Breach"
            
            # Risk Stops
            if exit_p is None:
                if direction == 'LONG':
                    if today_open <= p['sl_price']: exit_p, exit_reason = today_open, "SL (Gap)"
                    elif today_low <= p['sl_price']: exit_p, exit_reason = p['sl_price'], "SL"
                    elif today_high >= p['tp_price']: exit_p, exit_reason = p['tp_price'], "TP"
                else:
                    # SHORT Exit Logic
                    if today_open >= p['sl_price']: exit_p, exit_reason = today_open, "SL (Gap)"
                    elif today_high >= p['sl_price']: exit_p, exit_reason = p['sl_price'], "SL"
                    elif today_low <= p['tp_price']: exit_p, exit_reason = p['tp_price'], "TP"
            
            if exit_p is not None:
                # Execution with slippage
                if direction == 'LONG': real_exit = exit_p * (1.0 - slippage)
                else: real_exit = exit_p * (1.0 + slippage)
                
                profit = (real_exit - p['buy_price']) * p['shares'] if direction == 'LONG' else (p['buy_price'] - real_exit) * p['shares']
                
                trade_record = {
                    "ticker": ticker, "direction": direction, "entry_date": p['entry_date'],
                    "exit_date": curr_time.strftime('%Y-%m-%d'), "entry_price": p['buy_price'],
                    "exit_price": real_exit, "profit": profit,
                    "profit_pct": (profit / (p['buy_price'] * p['shares'] if direction == 'LONG' else p['buy_price'] * p['shares'])) * 100,
                    "reason": exit_reason, "entry_breadth": p['entry_breadth']
                }
                trade_ledger.append(trade_record)
                cash += profit
                trade_count += 1
            else:
                p['held_days'] += 1
                if direction == 'LONG':
                    today_close = close_np[i, tidx]
                    today_sma20 = sma20_np[i, tidx]
                    if not np.isnan(today_close) and today_close < today_sma20 * exit_buffer: 
                        p['exit_next_open'] = True
                new_portfolio.append(p)
        portfolio = new_portfolio

        # 2. Entry Logic
        if i + 1 >= T: continue
        br = breadth_ratio[i]
        
        # Dynamic Leverage
        curr_lev = 0.0
        if br >= 0.50: curr_lev = 3.0
        elif br >= 0.40: curr_lev = 2.0
        elif br >= breadth_threshold: curr_lev = 1.0
        if curr_lev <= 0: continue
        if len(portfolio) >= max_pos: continue
        
        # Macro Check for SHORT
        if nikkei_idx != -1:
            nik_c = close_np[i, nikkei_idx]
            nik_s100 = sma100_np[i, nikkei_idx]
            nik_ret60 = ret60_np[i, nikkei_idx]
        else:
            nik_c, nik_s100, nik_ret60 = 0, 0, 0
        
        allow_short = (0.30 <= br < 0.50) and (nik_c < nik_s100)
        allow_long = (br >= 0.30) or (br < 0.30) # Always allow Loading for Long in V25 logic

        c_u, s5_u, s20_u, s100_u = close_np[i, univ_indices], sma5_np[i, univ_indices], sma20_np[i, univ_indices], sma100_np[i, univ_indices]
        ret60_u = ret60_np[i, univ_indices]
        atr_u, rs_u = atr_np[i, univ_indices], (s5_u/s20_u*100)
        
        # Signals
        m_long = allow_long & (s5_u > s20_u) & (s20_u > s100_u) & (c_u < s20_u * 1.05) & (c_u > s20_u * 0.95) & (ret60_u > nik_ret60)
        m_short = allow_short & (s5_u < s20_u) & (s20_u < s100_u) & (c_u < s5_u) & (ret60_u < nik_ret60)
        
        candidates = []
        for idx in range(len(univ_indices)):
            if m_long[idx]: candidates.append((rs_u[idx], univ_indices[idx], 'LONG'))
            if m_short[idx]: candidates.append((200 - rs_u[idx], univ_indices[idx], 'SHORT')) # Invert RS for Short rank
            
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            for _, s_idx, dir in candidates[:5]:
                if len(portfolio) >= max_pos: break
                if s_idx in [pos['s_idx'] for pos in portfolio]: continue
                
                buy_v = open_np[i+1, s_idx]
                if not np.isnan(buy_v) and buy_v > 0:
                    # Entry Execution
                    e_p = buy_v * (1.0 + slippage) if dir == 'LONG' else buy_v * (1.0 - slippage)
                    
                    # Sizing: SHORT is 0.5x weight
                    weight = 1.0 if dir == 'LONG' else 0.5
                    sh = ((total_equity * curr_lev * weight / max_pos) / e_p // 100) * 100
                    
                    if sh >= 100:
                        atr_val = max(1.0, np.nan_to_num(atr_np[i, s_idx]))
                        if dir == 'LONG':
                            sl_p, tp_p = e_p - (atr_val * sl_mult), e_p + (atr_val * tp_mult)
                        else:
                            sl_p, tp_p = e_p + (atr_val * 5.0), e_p - (atr_val * 10.0)
                            
                        portfolio.append({
                            "s_idx": s_idx, "buy_price": e_p, "shares": sh, "held_days": 0,
                            "entry_atr": atr_val, "sl_price": sl_p, "tp_price": tp_p, "direction": dir,
                            "entry_date": curr_time.strftime('%Y-%m-%d'), "entry_breadth": br
                        })

    final_portfolio_value = 0.0
    for p in portfolio:
        cp = np.nan_to_num(close_np[-1, p['s_idx']])
        if cp <= 0: cp = p['buy_price']
        if p['direction'] == 'LONG':
            final_portfolio_value += (cp - p['buy_price']) * p['shares']
        else:
            final_portfolio_value += (p['buy_price'] - cp) * p['shares']
            
    final_equity = cash + final_portfolio_value
    return float(final_equity), trade_count, monthly_assets, trade_ledger
