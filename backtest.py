import pandas as pd
import numpy as np

def run_backtest_v16_production(univ_indices, bundle_np, timeline, breadth_ratio,
                                 initial_cash=10000000, max_pos=7, 
                                 sl_mult=10.0, tp_mult=30.0, leverage_rate=3.0, breadth_threshold=0.30,
                                 slippage=0.001, use_sma_exit=True, exit_buffer=0.94, 
                                 verbose=False):
    """
    V29.0 [The Absolute Apex] - Ultimate Trend-Follower
    - Corrected Buffer: 0.94 (SMA20 Exit) to prevent self-whipsaw
    - [RESTORED] Dynamic Leverage (All-Weather defense): 1x, 2x, 3x based on Breadth
    - Reverted to RS Formula: SMA5 / SMA20
    - Reverted to High-based Trailing Stop
    - Normalized Cash/Inventory Calculation
    """
    T = len(timeline)
    cash = float(initial_cash)
    portfolio = []
    trade_count = 0
    monthly_assets = {}
    trade_ledger = []
    
    close_np, open_np = bundle_np['Close'], bundle_np['Open']
    high_np, low_np = bundle_np['High'], bundle_np['Low']
    sma5_np, sma20_np, sma100_np = bundle_np['SMA5'], bundle_np['SMA20'], bundle_np['SMA100']
    atr_np = bundle_np['ATR']
    tickers = bundle_np['tickers']
    
    for i in range(100, T):
        curr_time = timeline[i]
        
        # 1. Portfolio Management
        held_value = 0.0
        for p in portfolio:
            cp = np.nan_to_num(close_np[i, p['s_idx']])
            if cp <= 0: cp = p['buy_price']
            held_value += cp * p['shares']
        
        total_equity = cash + held_value
        if i % 20 == 0:
            monthly_assets[curr_time.strftime('%Y-%m-%d')] = total_equity

        new_portfolio = []
        for p in portfolio:
            tidx = p['s_idx']
            ticker = tickers[tidx]
            today_open, today_high = open_np[i, tidx], high_np[i, tidx]
            today_low, today_close = low_np[i, tidx], close_np[i, tidx]
            
            if np.isnan(today_open) or np.isnan(today_close):
                p['held_days'] += 1
                new_portfolio.append(p)
                continue
            
            # [RESTORED] Trail from High (Tighter protection for massive profits)
            p['sl_price'] = max(p['sl_price'], today_high - (p['entry_atr'] * sl_mult))

            exit_p, exit_reason = None, ""
            
            # SMA20 Breach Execution
            if exit_p is None and use_sma_exit and p.get('exit_next_open', False):
                exit_p, exit_reason = today_open, "SMA20 Breach / Stagnation"
            
            # Risk Stops
            if exit_p is None:
                if today_open <= p['sl_price']: exit_p, exit_reason = today_open, "SL (Gap)"
                elif today_low <= p['sl_price']: exit_p, exit_reason = p['sl_price'], "SL"
                elif today_high >= p['tp_price']: exit_p, exit_reason = p['tp_price'], "TP"
            
            if exit_p is not None:
                real_exit = exit_p * (1.0 - slippage)
                revenue = real_exit * p['shares']
                profit = (real_exit - p['buy_price']) * p['shares']
                
                trade_ledger.append({
                    "ticker": ticker, "direction": "LONG", "entry_date": p['entry_date'],
                    "exit_date": curr_time.strftime('%Y-%m-%d'), "entry_price": p['buy_price'],
                    "exit_price": real_exit, "profit": profit,
                    "profit_pct": (real_exit / p['buy_price'] - 1) * 100,
                    "reason": exit_reason, "entry_breadth": p['entry_breadth']
                })
                # Inventory to Cash
                cash += revenue
                trade_count += 1
            else:
                p['held_days'] += 1
                if today_close < sma20_np[i, tidx] * exit_buffer: 
                    p['exit_next_open'] = True
                new_portfolio.append(p)
                
        portfolio = new_portfolio

        # 2. Entry Logic
        if i + 1 >= T: continue
        br = breadth_ratio[i]
        
        # Dynamic Leverage (All-Weather defense)
        curr_lev = 0.0
        if br >= 0.50: curr_lev = 3.0
        elif br >= 0.40: curr_lev = 2.0
        elif br >= breadth_threshold: curr_lev = 1.0
        
        if curr_lev <= 0: continue
        if len(portfolio) >= max_pos: continue
        
        c_u, s5_u, s20_u = close_np[i, univ_indices], sma5_np[i, univ_indices], sma20_np[i, univ_indices]
        s100_u, atr_u = sma100_np[i, univ_indices], atr_np[i, univ_indices]
        
        # [RESTORED] Short-term momentum relative strength
        rs_u = s5_u / s20_u * 100 
        
        # Pure Perfect Order Pullback
        mask = (s5_u > s20_u) & (s20_u > s100_u) & (c_u < s20_u * 1.05) & (c_u > s20_u * 0.95)
        
        if mask.any():
            candidates = sorted([(rs_u[idx], univ_indices[idx]) for idx, m in enumerate(mask) if m], 
                                key=lambda x: x[0], reverse=True)[:max_pos]
            
            for score, s_idx in candidates:
                if len(portfolio) >= max_pos: break
                if s_idx in [pos['s_idx'] for pos in portfolio]: continue
                
                buy_v = open_np[i+1, s_idx]
                if not np.isnan(buy_v) and buy_v > 0:
                    entry_p = buy_v * (1.0 + slippage)
                    # 購入株数の算出に curr_lev を使用する
                    sh = ((total_equity * curr_lev / max_pos) / entry_p // 100) * 100
                    
                    if sh >= 100:
                        entry_atr = max(1.0, np.nan_to_num(atr_np[i, s_idx]))
                        # Cash to Inventory
                        cash -= entry_p * sh
                        portfolio.append({
                            "s_idx": s_idx, "buy_price": entry_p, "shares": sh, "held_days": 0,
                            "entry_atr": entry_atr, "sl_price": entry_p - (entry_atr * sl_mult),
                            "tp_price": entry_p + (entry_atr * tp_mult), "direction": "LONG",
                            "entry_date": curr_time.strftime('%Y-%m-%d'), "entry_breadth": br
                        })

    # Final Inventory evaluation
    final_equity = cash + sum(np.nan_to_num(close_np[-1, p['s_idx']]) * p['shares'] for p in portfolio)
    return float(final_equity), trade_count, monthly_assets, trade_ledger
