import pandas as pd
import numpy as np

def run_backtest_v16_production(univ_indices, bundle_np, timeline, breadth_ratio,
                               initial_cash=10000000, max_pos=5, 
                               sl_mult=5.0, tp_mult=20.0, breadth_threshold=0.4,
                               slippage=0.001):
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
    
    close_np = bundle_np['Close']
    open_np, high_np, low_np = bundle_np['Open'], bundle_np['High'], bundle_np['Low']
    sma5_np = bundle_np['SMA5']
    sma20_np = bundle_np['SMA20']
    sma100_np = bundle_np['SMA100']
    atr_np = bundle_np['ATR']
    
    for i in range(100, T):
        curr_time = timeline[i]
        if i % 20 == 0:
            held_v = sum(np.nan_to_num(close_np[i, p['s_idx']]) * p['shares'] for p in portfolio)
            monthly_assets[curr_time.strftime('%Y-%m')] = cash + held_v

        # 1. Management
        nxt, pending_cash = [], 0.0
        for p in portfolio:
            tidx = p['s_idx']
            today_open, today_high, today_low = open_np[i, tidx], high_np[i, tidx], low_np[i, tidx]
            
            # --- NaN Check: Skip if data is missing (trading suspension) ---
            if np.isnan(today_open) or np.isnan(today_high) or np.isnan(today_low):
                p['held_days'] += 1
                nxt.append(p)
                continue
            
            p['sl_price'] = max(p['sl_price'], today_high - (p['entry_atr'] * sl_mult))
            
            exit_p = None
            if today_open <= p['sl_price']: exit_p = today_open
            elif today_low <= p['sl_price']: exit_p = p['sl_price']
            elif today_high >= p['tp_price']: exit_p = p['tp_price']
            elif p['held_days'] >= 60: exit_p = today_open
            
            if exit_p is not None:
                pending_cash += exit_p * (1.0 - slippage) * p['shares']
                trade_count += 1
            else:
                p['held_days'] += 1
                nxt.append(p)
        portfolio, cash = nxt, float(cash + pending_cash)

        # 2. Entry
        if i + 1 >= T: continue
        if breadth_ratio[i] < breadth_threshold: continue
        
        if len(portfolio) < max_pos:
            c_u, s5_u, s20_u, s100_u = close_np[i, univ_indices], sma5_np[i, univ_indices], sma20_np[i, univ_indices], sma100_np[i, univ_indices]
            
            # The V16.2 Winner Logic
            is_perfect = (s5_u > s20_u) & (s20_u > s100_u)
            is_pullback = (c_u < s20_u * 1.02) & (c_u > s20_u * 0.98) 
            
            valid_mask = is_perfect & is_pullback
            valid_idx = univ_indices[valid_mask]
            
            if len(valid_idx) > 0:
                # ALPHA SORT: SMA5 / SMA100 Ratio (Trend Momentum)
                strength = s5_u[valid_mask] / s100_u[valid_mask]
                sorted_idx = valid_idx[np.argsort(strength)][::-1]
                
                for s_idx in sorted_idx:
                    if len(portfolio) >= max_pos: break
                    if s_idx in [p['s_idx'] for p in portfolio]: continue
                    
                    buy_v = open_np[i+1, s_idx]
                    if not np.isnan(buy_v) and buy_v > 0:
                        entry_p = buy_v * (1.0 + slippage)
                        entry_atr = max(1.0, np.nan_to_num(atr_np[i, s_idx]))
                        sh = (int((cash / (max_pos - len(portfolio))) / entry_p) // 100) * 100
                        if sh >= 100:
                            portfolio.append({
                                "s_idx": s_idx, "buy_price": entry_p, "shares": sh, "held_days": 0,
                                "entry_atr": entry_atr,
                                "sl_price": entry_p - (entry_atr * sl_mult),
                                "tp_price": entry_p + (entry_atr * tp_mult)
                            })
                            cash -= entry_p * sh

    final = cash + sum(np.nan_to_num(close_np[-1, p['s_idx']]) * p['shares'] for p in portfolio)
    return float(final), trade_count, monthly_assets
