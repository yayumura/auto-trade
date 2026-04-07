import pandas as pd
import numpy as np

def run_backtest_v16_production(univ_indices, bundle_np, timeline, breadth_ratio,
                                 initial_cash=10000000, max_pos=10, 
                                 sl_mult=5.0, tp_mult=15.0, leverage_rate=3.0, breadth_threshold=0.20,
                                 slippage=0.001, use_sma_exit=True, exit_buffer=0.985, 
                                 verbose=False):
    """
    V27.0 [THE HOLY GRAIL] - Pure Alpha Long-Only Trend-Follow
    - Fixed RS Formula Error (Uses SMA5/SMA100 for authentic trend selection)
    - Fixed Trailing Stop Choke Error (Uses Close instead of High)
    - Dynamic Leverage: 0.5+ (3x), 0.4+ (2x), 0.2+ (1x), <0.2 (Stop)
    - Pure LONG Strategy (SHORT logic completely removed)
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
    # Nikkei 225 index for relative strength comparison
    nik_idx = -1
    if '1321.T' in tickers:
        nik_idx = list(tickers).index('1321.T')
    
    for i in range(100, T):
        curr_time = timeline[i]
        
        # 1. Management & Equity Calculation
        current_profits = 0.0
        for p in portfolio:
            cp = np.nan_to_num(close_np[i, p['s_idx']])
            if cp <= 0: cp = p['buy_price']
            current_profits += (cp - p['buy_price']) * p['shares']
        
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
            today_close = close_np[i, tidx]
            
            if np.isnan(today_open):
                p['held_days'] += 1
                new_portfolio.append(p)
                continue
            
            # [V27.0 Fix] Trailing stop update (Uses CLOSE to allow "breathing room")
            p['sl_price'] = max(p['sl_price'], today_close - (p['entry_atr'] * sl_mult))
            # 3*ATR break-even protection
            if today_low >= p['buy_price'] + (p['entry_atr'] * 3.0):
                p['sl_price'] = max(p['sl_price'], p['buy_price'] * 1.001)

            exit_p = None
            exit_reason = ""
            
            # Time Stop (60d)
            if p['held_days'] >= 60:
                exit_p, exit_reason = today_open, "Time Stop (60d)"
            
            # Technical Exit (SMA20 Breach)
            if exit_p is None and use_sma_exit and p.get('exit_next_open', False):
                exit_p, exit_reason = today_open, "SMA20 Breach"
            
            # Risk Stops
            if exit_p is None:
                if today_open <= p['sl_price']: exit_p, exit_reason = today_open, "SL (Gap)"
                elif today_low <= p['sl_price']: exit_p, exit_reason = p['sl_price'], "SL"
                elif today_high >= p['tp_price']: exit_p, exit_reason = p['tp_price'], "TP"
            
            if exit_p is not None:
                # Execution with slippage
                real_exit = exit_p * (1.0 - slippage)
                profit = (real_exit - p['buy_price']) * p['shares']
                
                trade_record = {
                    "ticker": ticker, "direction": "LONG", "entry_date": p['entry_date'],
                    "exit_date": curr_time.strftime('%Y-%m-%d'), "entry_price": p['buy_price'],
                    "exit_price": real_exit, "profit": profit,
                    "profit_pct": (profit / (p['buy_price'] * p['shares'])) * 100,
                    "reason": exit_reason, "entry_breadth": p['entry_breadth']
                }
                trade_ledger.append(trade_record)
                cash += profit
                trade_count += 1
            else:
                p['held_days'] += 1
                today_close_val = close_np[i, tidx]
                today_sma20 = sma20_np[i, tidx]
                if not np.isnan(today_close_val) and today_close_val < today_sma20 * exit_buffer: 
                    p['exit_next_open'] = True
                new_portfolio.append(p)
        portfolio = new_portfolio

        # 2. Entry Logic
        if i + 1 >= T: continue
        br = breadth_ratio[i]
        
        # [V27.0] Dynamic Leverage
        curr_lev = 0.0
        if br >= 0.50: curr_lev = 3.0
        elif br >= 0.40: curr_lev = 2.0
        elif br >= breadth_threshold: curr_lev = 1.0 # default to 0.20
        
        if curr_lev <= 0: continue
        if len(portfolio) >= max_pos: continue
        
        nik_ret60 = ret60_np[i, nik_idx] if nik_idx != -1 else 0
        
        c_u, s5_u, s20_u, s100_u = close_np[i, univ_indices], sma5_np[i, univ_indices], sma20_np[i, univ_indices], sma100_np[i, univ_indices]
        ret60_u = ret60_np[i, univ_indices]
        
        # [V27.0 Fix] Authentic Relative Strength (SMA5/SMA100)
        atr_u, rs_u = atr_np[i, univ_indices], (s5_u/s100_u*100)
        
        # V21 Perfect Order Pullback Logic
        mask = (s5_u > s20_u) & (s20_u > s100_u) & (c_u < s20_u * 1.05) & (c_u > s20_u * 0.95) & (ret60_u > nik_ret60)
        
        if mask.any():
            candidates = sorted([(rs_u[idx], univ_indices[idx]) for idx, m in enumerate(mask) if m], 
                                key=lambda x: x[0], reverse=True)[:5]
            
            for score, s_idx in candidates:
                if len(portfolio) >= max_pos: break
                if s_idx in [pos['s_idx'] for pos in portfolio]: continue
                
                buy_v = open_np[i+1, s_idx]
                if not np.isnan(buy_v) and buy_v > 0:
                    entry_p = buy_v * (1.0 + slippage)
                    # Sizing based on Dynamic Leverage and Max positions
                    sh = ((total_equity * curr_lev / max_pos) / entry_p // 100) * 100
                    
                    if sh >= 100:
                        entry_atr = max(1.0, np.nan_to_num(atr_np[i, s_idx]))
                        portfolio.append({
                            "s_idx": s_idx, "buy_price": entry_p, "shares": sh, "held_days": 0,
                            "entry_atr": entry_atr, "sl_price": entry_p - (entry_atr * sl_mult),
                            "tp_price": entry_p + (entry_atr * tp_mult), "direction": "LONG",
                            "entry_date": curr_time.strftime('%Y-%m-%d'), "entry_breadth": br
                        })

    final_portfolio_value = sum((np.nan_to_num(close_np[-1, p['s_idx']]) - p['buy_price']) * p['shares'] for p in portfolio)
    final_equity = cash + final_portfolio_value
    return float(final_equity), trade_count, monthly_assets, trade_ledger
