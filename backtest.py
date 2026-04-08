import pandas as pd
import numpy as np

def run_backtest_v16_production(univ_indices, bundle_np, timeline, breadth_ratio,
                               initial_cash=1000000, max_pos=2, 
                               sl_mult=5.0, tp_mult=10.0, leverage_rate=2.2, breadth_threshold=0.3,
                               slippage=0.001, use_sma_exit=False, exit_buffer=0.985, max_hold_days=30,
                               verbose=False):
    """
    V38.0 Imperial Apex Reborn (Optimized Mean Reversion)
    - Strong Rebound Confirmation: White Candle + Close > Prev Close.
    - RS Filtering: RS > 102 (Only above average strength).
    - High Turnover: Rapid Reversion Exit (Close > SMA5).
    - Goal: Target 5% Monthly via 3.0x Leverage and High Win-Rate.
    """
    T = len(timeline)
    cash = float(initial_cash)
    portfolio = []
    trade_count = 0
    monthly_assets = {}
    trade_results = []
    
    close_np = bundle_np['Close']
    open_np = bundle_np['Open']
    high_np = bundle_np['High']
    low_np = bundle_np['Low']
    sma5_np = bundle_np['SMA5']
    sma100_np = bundle_np['SMA100']
    rsi2_np = bundle_np['RSI2']
    atr_np = bundle_np['ATR']
    rs_np = bundle_np.get('RS', np.ones_like(close_np) * 100)
    cooling_days = 0
    current_month = ""
    month_start_equity = initial_cash
    month_done = False
    
    # --- V131.1 Aegis Sovereign Restoration ---
    for i in range(1, T):
        curr_time = timeline[i]
        
        # 0. Essential State
        if cooling_days > 0:
            cooling_days -= 1
            
        if curr_time.strftime('%Y-%m') != current_month:
            current_month = curr_time.strftime('%Y-%m')
            month_start_equity = cash + sum(np.nan_to_num(close_np[i, p['s_idx']]) * p['shares'] for p in portfolio)
            month_done = False 

        total_equity = cash + sum(np.nan_to_num(close_np[i, p['s_idx']]) * p['shares'] for p in portfolio)
        
        # Global Regime
        idx_1321 = -1
        for idx_t, t_ticker in enumerate(bundle_np['tickers']):
            if t_ticker == '1321.T': 
                idx_1321 = idx_t
                break
        
        sma200_val = bundle_np['SMA200'][i, idx_1321] if idx_1321 != -1 else 0
        sma50_val = bundle_np['SMA50'][i, idx_1321] if idx_1321 != -1 else 0
        price_1321 = close_np[i, idx_1321]
        sma200_prev = bundle_np['SMA200'][i-5, idx_1321] if (idx_1321 != -1 and i > 5) else sma200_val
        slope_pct = (sma200_val / sma200_prev - 1.0) * 100 if sma200_prev != 0 else 0
        
        is_overheated = (price_1321 > sma50_val * 1.10)
        
        engine_mode = "NEUTRAL"
        if price_1321 > sma200_val and slope_pct > 0.02:
            engine_mode = "BULL"
        elif price_1321 < (sma200_val * 0.98):
            engine_mode = "BEAR"
        
        # --- V131.0 Aegis Sovereign Restoration ---
        month_drawdown = (total_equity / month_start_equity) - 1.0
        is_caution_zone = (month_drawdown <= -0.05)
        is_danger_zone = (month_drawdown <= -0.10)
        
        if not month_done and month_drawdown <= -0.12: 
            month_done = True 
            
        # Index Trend Health
        idx_sma5 = bundle_np['SMA5'][i, idx_1321] if idx_1321 != -1 else 0
        is_trend_snapped = (price_1321 < idx_sma5)
        
        # 1. Management (Aegis Sovereign Protocol)
        new_portfolio = []
        for p in portfolio:
            tidx = p['s_idx']
            t_open = open_np[i, tidx]
            t_high = high_np[i, tidx]
            t_low = low_np[i, tidx]
            t_close = close_np[i, tidx]
            t_atr = atr_np[i, tidx]
            if np.isnan(t_close):
                new_portfolio.append(p)
                continue
            
            p['max_price'] = max(p.get('max_price', t_close), t_close)
            exit_p = None
            
            # Dynamic Risk Shield
            atr_mult = 1.5
            if is_caution_zone: atr_mult = 1.0
            if is_danger_zone: atr_mult = 0.5
            if engine_mode != "BULL": atr_mult = 1.0
            
            tsl_price = p['max_price'] - (atr_mult * t_atr)
            
            # Dynamic Exit Threshold
            rsi_val = rsi2_np[i, tidx]
            exit_threshold = 85 if not is_trend_snapped else 55
            if engine_mode != "BULL": exit_threshold = 60
            
            if t_open <= tsl_price or t_low <= tsl_price:
                exit_p = max(t_open, tsl_price)
            elif rsi_val > exit_threshold:
                exit_p = t_close
            elif is_danger_zone: 
                exit_p = t_close
            
            if exit_p is not None:
                final_exit = exit_p * (1.0 - slippage)
                trade_results.append((final_exit - p['buy_price']) * p['shares'])
                cash += final_exit * p['shares']
                cooling_days = 2
            else:
                p['held_days'] = p.get('held_days', 0) + 1
                new_portfolio.append(p)
        portfolio = new_portfolio
        
        # Stats Update
        total_equity = cash + sum(np.nan_to_num(close_np[i, pos['s_idx']]) * pos['shares'] for pos in portfolio)
        monthly_assets[current_month] = float(total_equity)

        # 2. Entry
        if i + 1 >= T or month_done or cooling_days > 0: continue 
        
        per_slot_size = (leverage_rate / max_pos)
        rs_alphas = bundle_np.get('RS_Alpha', np.zeros_like(close_np))[i, :]
        valid_indices = [idx for idx in univ_indices if not np.isnan(rs_alphas[idx])]
        top_indices = sorted(valid_indices, key=lambda x: rs_alphas[x], reverse=True)[:max_pos]
        
        for s_idx in top_indices:
            if len(portfolio) >= max_pos: break 
            if any(p['s_idx'] == s_idx for p in portfolio): continue
            
            rsi_val = rsi2_np[i, s_idx]
            t_close = close_np[i, s_idx]
            t_open = open_np[i, s_idx]
            t_sma50 = bundle_np['SMA50'][i, s_idx]
            
            current_slot_size = per_slot_size * (0.5 if is_overheated else 1.0)
            entry_signal = False
            if engine_mode == "BULL":
                if rsi_val < 30.0 and t_close > t_sma50 and t_close > t_open:
                    entry_signal = True
            elif engine_mode == "NEUTRAL":
                if rsi_val < 12.0 and t_close > t_open:
                    entry_signal = True
            elif engine_mode == "BEAR":
                if rsi_val < 8.0 and t_close > t_open:
                    entry_signal = True
                elif bundle_np['tickers'][s_idx] == '1357.T' and rsi_val > 70:
                    entry_signal = True
            
            if entry_signal:
                real_buy = t_close * (1.0 + slippage)
                shares = int((total_equity * current_slot_size) / real_buy)
                if shares > 0:
                    t_atr = atr_np[i, s_idx]
                    portfolio.append({
                        's_idx': s_idx, 'buy_price': real_buy,
                        'sl_price': real_buy - (2.2 * t_atr), 
                        'shares': shares, 'held_days': 0, 'max_price': real_buy
                    })
                    cash -= real_buy * shares
                    trade_count += 1







    final = cash + sum(np.nan_to_num(close_np[-1, p['s_idx']]) * p['shares'] for p in portfolio)
    return float(final), trade_count, monthly_assets, trade_results
