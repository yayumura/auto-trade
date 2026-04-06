import pandas as pd
import numpy as np

def run_backtest_v16_production(univ_indices, bundle_np, timeline, breadth_ratio,
                               initial_cash=10000000, max_pos=10, 
                               sl_mult=5.0, tp_mult=15.0, leverage_rate=2.0, breadth_threshold=0.4,
                               slippage=0.001, use_sma_exit=True, exit_buffer=0.985, 
                               verbose=False):
    """
    V17.0 THE IMPERIAL ORACLE - PEAK ALPHA SYNC
    - Perfect Order: SMA5 > SMA20 > SMA100
    - Pullback: Buying @ SMA20 support (98% to 102%)
    - Sorting: S5/S100 Ratio (Trend Strength) - DISCOVERED ALPHA
    """
    T = len(timeline)
    cash = float(initial_cash)
    portfolio = []
    trade_count = 0
    monthly_assets = {}
    trade_results = [] # [V17.5] Detailed Trade Tracker
    
    close_np = bundle_np['Close']
    open_np, high_np, low_np = bundle_np['Open'], bundle_np['High'], bundle_np['Low']
    sma5_np = bundle_np['SMA5']
    sma20_np = bundle_np['SMA20']
    sma100_np = bundle_np['SMA100']
    atr_np = bundle_np['ATR']
    
    # [V17.2 Enhancement] Pre-locate 1321.T (Global Market Proxy)
    idx_1321 = bundle_np['tickers'].index('1321.T') if '1321.T' in bundle_np['tickers'] else None
    
    for i in range(100, T):
        curr_time = timeline[i]
        
        # held_value calculation for Long/Short
        # For Short, value is technically negative or we can track absolute exposure.
        # Here we use held_value as "current market value of positions" for total_equity calculation.
        # Short position value = -current_price * shares? No, let's use the standard accounting:
        # Equity = Cash + sum(MarketValue of Longs) - sum(MarketValue of Shorts)
        # Wait, in Margin trading, Equity = Cash + sum(Profit/Loss).
        
        long_mv = sum(np.nan_to_num(close_np[i, p['s_idx']]) * p['shares'] for p in portfolio if p.get('direction', 'LONG') == 'LONG')
        short_mv = sum(np.nan_to_num(close_np[i, p['s_idx']]) * p['shares'] for p in portfolio if p.get('direction') == 'SHORT')
        # Simple equity: Cash + (MarketValue if Long)
        # But for Short, if price goes up, equity goes down.
        # Equity = Cash + sum((Current - Entry) * Shares if Long) + sum((Entry - Current) * Shares if Short)
        # This is equivalent to: Equity = InitialCash + total_profits.
        # Let's use a more robust way:
        current_profits = 0.0
        for p in portfolio:
            cp = np.nan_to_num(close_np[i, p['s_idx']])
            if cp <= 0: cp = p['buy_price'] # Fallback
            if p.get('direction', 'LONG') == 'LONG':
                current_profits += (cp - p['buy_price']) * p['shares']
            else:
                current_profits += (p['buy_price'] - cp) * p['shares']
        
        total_equity = cash + current_profits
        
        if i % 20 == 0:
            monthly_assets[curr_time.strftime('%Y-%m')] = total_equity

        # 1. Management
        pending_cash_delta = 0.0
        new_portfolio = []
        for p in portfolio:
            tidx = p['s_idx']
            direction = p.get('direction', 'LONG')
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
                p['sl_price'] = min(p['sl_price'], today_low + (p['entry_atr'] * sl_mult))
                if today_low <= p['buy_price'] - (p['entry_atr'] * 5.0):
                    p['sl_price'] = min(p['sl_price'], p['buy_price'] * 0.998)
            
            exit_p = None
            if use_sma_exit and p.get('exit_next_open', False):
                exit_p = today_open
            
            if exit_p is None:
                if direction == 'LONG':
                    if today_open <= p['sl_price']: exit_p = today_open
                    elif today_low <= p['sl_price']: exit_p = p['sl_price']
                    elif today_high >= p['tp_price']: exit_p = p['tp_price']
                    elif p['held_days'] >= 60: exit_p = today_open
                else: # SHORT
                    if today_open >= p['sl_price']: exit_p = today_open
                    elif today_high >= p['sl_price']: exit_p = p['sl_price']
                    elif today_low <= p['tp_price']: exit_p = p['tp_price']
                    elif p['held_days'] >= 60: exit_p = today_open
            
            if exit_p is not None:
                if direction == 'LONG':
                    real_exit = exit_p * (1.0 - slippage)
                    profit = (real_exit - p['buy_price']) * p['shares']
                else: # SHORT
                    real_exit = exit_p * (1.0 + slippage) # Short covering: pay more to buy back
                    profit = (p['buy_price'] - real_exit) * p['shares']
                
                trade_results.append(profit)
                cash += profit # In margin, we just add the profit to cash
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
        
        # [V21 Breadth Logic]
        allow_long = br >= 0.30
        allow_short = br < 0.40
        
        # --- [V21 Dynamic Leverage Sync] ---
        current_leverage = 1.0 # Default
        if br >= 0.50: current_leverage = 3.0
        elif br >= 0.40: current_leverage = 2.0
        elif br >= 0.30: current_leverage = 1.0
        else: current_leverage = 1.0 # Keep 1x for short-only phase or suppress? Request implies pursuing absolute return.
        
        if idx_1321 is not None and br >= 0.30: # Only filter LONG entries by Nikkei SMA100
             if close_np[i, idx_1321] < sma100_np[i, idx_1321]:
                  allow_long = False
        
        if len(portfolio) < max_pos and (allow_long or allow_short):
            # Calculate Buying Power
            current_exposure = sum(p['buy_price'] * p['shares'] for p in portfolio)
            # Simple margin buying power: (Equity * Leverage) - Exposure
            buying_power = (total_equity * current_leverage) - current_exposure
            
            c_u, s5_u, s20_u, s100_u = close_np[i, univ_indices], sma5_np[i, univ_indices], sma20_np[i, univ_indices], sma100_np[i, univ_indices]
            h_u, l_u = high_np[i, univ_indices], low_np[i, univ_indices]
            atr_u = atr_np[i, univ_indices]
            
            # --- LONG Candidates ---
            valid_long_idx = []
            if allow_long:
                is_perfect_l = (s5_u > s20_u) & (s20_u > s100_u)
                is_pullback_l = (c_u < s20_u * 1.04) & (c_u > s20_u * 0.96) 
                is_strong_close = (c_u - l_u) / (h_u - l_u + 1e-9) >= 0.5
                is_reversal_l = ((c_u > close_np[i-1, univ_indices]) | (c_u > open_np[i, univ_indices])) & is_strong_close
                mask_l = is_perfect_l & is_pullback_l & is_reversal_l
                if mask_l.any():
                    strength_l = s5_u[mask_l] / s100_u[mask_l]
                    v_idx_l = univ_indices[mask_l]
                    # Format: (score, s_idx, direction)
                    valid_long_idx = [(s, idx, 'LONG') for s, idx in zip(strength_l, v_idx_l)]

            # --- SHORT Candidates ---
            valid_short_idx = []
            if allow_short:
                is_perfect_s = (s5_u < s20_u) & (s20_u < s100_u)
                is_pullback_s = (c_u < s20_u * 1.02) & (c_u > s20_u * 0.98)
                is_weak_close = (h_u - c_u) / (h_u - l_u + 1e-9) >= 0.5
                is_reversal_s = ((c_u < close_np[i-1, univ_indices]) | (c_u < open_np[i, univ_indices])) & is_weak_close
                mask_s = is_perfect_s & is_pullback_s & is_reversal_s
                if mask_s.any():
                    strength_s = s100_u[mask_s] / s5_u[mask_s]
                    v_idx_s = univ_indices[mask_s]
                    valid_short_idx = [(s, idx, 'SHORT') for s, idx in zip(strength_s, v_idx_s)]

            all_candidates = sorted(valid_long_idx + valid_short_idx, key=lambda x: x[0], reverse=True)
            
            for score, s_idx, direction in all_candidates:
                if len(portfolio) >= max_pos: break
                if s_idx in [p['s_idx'] for p in portfolio]: continue
                
                buy_v = open_np[i+1, s_idx]
                if not np.isnan(buy_v) and buy_v > 0:
                    entry_p = buy_v * (1.0 + slippage if direction == 'LONG' else 1.0 - slippage)
                    entry_atr = max(1.0, np.nan_to_num(atr_np[i, s_idx]))
                    
                    allocation = (total_equity * current_leverage) / max_pos
                    actual_ma = min(allocation, buying_power)
                    sh = (int(actual_ma / entry_p) // 100) * 100
                    
                    if sh >= 100:
                        if direction == 'LONG':
                            p_item = {
                                "s_idx": s_idx, "buy_price": entry_p, "shares": sh, "held_days": 0,
                                "entry_atr": entry_atr, "direction": "LONG",
                                "sl_price": entry_p - (entry_atr * sl_mult),
                                "tp_price": entry_p + (entry_atr * tp_mult)
                            }
                        else:
                            p_item = {
                                "s_idx": s_idx, "buy_price": entry_p, "shares": sh, "held_days": 0,
                                "entry_atr": entry_atr, "direction": "SHORT",
                                "sl_price": entry_p + (entry_atr * sl_mult),
                                "tp_price": entry_p - (entry_atr * tp_mult)
                            }
                        portfolio.append(p_item)
                        buying_power -= entry_p * sh
                    elif verbose:
                        print(f"⏭️ [BT Skip] {bundle_np['tickers'][s_idx]} skipped: Low budget.")

    # Final equity calculation
    current_profits = 0.0
    for p in portfolio:
        cp = np.nan_to_num(close_np[-1, p['s_idx']])
        if cp <= 0: cp = p['buy_price']
        if p.get('direction', 'LONG') == 'LONG':
            current_profits += (cp - p['buy_price']) * p['shares']
        else:
            current_profits += (p['buy_price'] - cp) * p['shares']
            
    final = cash + current_profits
    return float(final), trade_count, monthly_assets, trade_results

