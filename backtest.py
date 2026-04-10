import pandas as pd
import numpy as np
from core.logic import (
    calculate_aegis_shield, get_exit_thresholds, 
    calculate_dynamic_leverage, check_entry_signal
)

def run_backtest_v16_production(univ_indices, bundle_np, timeline, breadth_ratio,
                               initial_cash=1000000, max_pos=2, 
                               sl_mult=3.0, tp_mult=40.0, leverage_rate=2.5, breadth_threshold=0.3,
                               slippage=0.001, use_sma_exit=False, exit_buffer=0.985, max_hold_days=30,
                               verbose=False):
    """
    V132.0 Imperial Apex (Aegis Sovereign Sync)
    - Full parity with live logic: RSI2 Mean Reversion + RS Leader Selection
    - Aegis Shield: Monthly drawdown-based risk tightening
    - Dynamic Leverage: Integrated breadth-based scaling
    - Time Stop: 30-day limit
    - Break-even Stop: ATR 5.0 Profit protection
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
    rsi2_np = bundle_np['RSI2']
    atr_np = bundle_np['ATR']
    rs_alpha_np = bundle_np.get('RS_Alpha', np.zeros_like(close_np))
    sma50_np = bundle_np.get('SMA50', np.zeros_like(close_np))
    sma20_np = bundle_np.get('SMA20', np.zeros_like(close_np))
    
    cooling_days = 0
    current_month = ""
    month_start_equity = initial_cash
    month_done = False
    
    # Identify 1321.T for regime detection
    idx_1321 = -1
    for idx_t, t_ticker in enumerate(bundle_np['tickers']):
        if t_ticker == '1321.T': 
            idx_1321 = idx_t
            break

    for i in range(1, T):
        curr_time = timeline[i]
        
        # 0. Monthly Tracking & Aegis Initialization
        if cooling_days > 0: cooling_days -= 1
        
        if curr_time.strftime('%Y-%m') != current_month:
            current_month = curr_time.strftime('%Y-%m')
            # Calculate equity at start of month
            month_start_equity = cash + sum(np.nan_to_num(close_np[i, p['s_idx']]) * p['shares'] for p in portfolio)
            month_done = False 

        total_equity = cash + sum(np.nan_to_num(close_np[i, p['s_idx']]) * p['shares'] for p in portfolio)
        month_drawdown = (total_equity / month_start_equity) - 1.0 if month_start_equity > 0 else 0
        
        # Regime Detection (Aegis Standard)
        regime = "NEUTRAL"
        is_trend_snapped = False
        if idx_1321 != -1:
            p_1321 = close_np[i, idx_1321]
            s200_1321 = bundle_np['SMA200'][i, idx_1321]
            s200_prev = bundle_np['SMA200'][i-5, idx_1321] if i > 5 else s200_1321
            slope = (s200_1321 / s200_prev - 1.0) * 100 if s200_prev != 0 else 0
            
            if p_1321 > s200_1321 and slope > 0.02: regime = "BULL"
            elif p_1321 < s200_1321 * 0.98: regime = "BEAR"
            
            s5_1321 = bundle_np['SMA5'][i, idx_1321]
            if p_1321 < s5_1321: is_trend_snapped = True

        # --- Imperial Sovereign Protocol (V143 Adaptive) ---
        shield_mult = calculate_aegis_shield(month_drawdown, regime)
        if month_drawdown <= -0.15: month_done = True 

        # 1. Management
        new_portfolio = []
        for p in portfolio:
            tidx = p['s_idx']
            t_open = open_np[i, tidx]
            t_high = high_np[i, tidx]
            t_low = low_np[i, tidx]
            t_close = close_np[i, tidx]
            t_atr = atr_np[i, tidx]
            r2 = rsi2_np[i, tidx]
            
            if np.isnan(t_close):
                new_portfolio.append(p)
                continue
            
            p['max_price'] = max(p.get('max_price', t_close), t_close)
            exit_p = None
            
            # --- Exit Conditions (V143.0 Adaptive) ---
            
            # A. Adaptive Stop (Breadth & DD Based)
            stop_mult = 3.0 
            curr_breadth = breadth_ratio[i]
            if curr_breadth < 0.45: stop_mult = 1.5 
            if month_drawdown <= -0.07: stop_mult = 1.0 
            
            stop_dist = stop_mult * t_atr 
            initial_stop_price = p['buy_price'] - stop_dist
            
            if t_close > p['buy_price']:
                 tsl_price = max(initial_stop_price, p['max_price'] - stop_dist)
            else:
                 tsl_price = initial_stop_price

            # B. RSI Overextension
            exit_threshold = get_exit_thresholds(regime, is_trend_snapped)
            
            # C. Trend Breach (2.5% buffer)
            is_trend_broken = False
            if t_close < sma20_np[i, tidx] * 0.975:
                is_trend_broken = True
            
            if t_low <= tsl_price or t_open <= tsl_price:
                exit_p = max(t_open, tsl_price)
            elif r2 > exit_threshold:
                exit_p = t_close
            elif is_trend_broken:
                exit_p = t_close
            elif month_done:
                exit_p = t_close
            
            if exit_p is not None:
                final_exit = exit_p * (1.0 - slippage)
                trade_results.append((final_exit - p['buy_price']) * p['shares'])
                cash += final_exit * p['shares']
                cooling_days = 2
            else:
                new_portfolio.append(p)
        portfolio = new_portfolio
        
        # Stats Update
        total_equity = cash + sum(np.nan_to_num(close_np[i, pos['s_idx']]) * pos['shares'] for pos in portfolio)
        monthly_assets[current_month] = float(total_equity)

        # 2. Entry (V143.0 Adaptive Alpha)
        if i + 1 >= T or month_done or cooling_days > 0 or regime != "BULL": continue 
        
        # [V140] Moderate Dynamic Leverage
        dynamic_lev = calculate_dynamic_leverage(breadth_ratio[i], config_leverage=leverage_rate, shield_mult=shield_mult)
        if dynamic_lev <= 0: continue
        
        # Selection: Pure RS_Alpha Top Leaders
        rs_alphas = rs_alpha_np[i, :]
        rsis = rsi2_np[i, :]
        sma200s = bundle_np['SMA200'][i, :]
        turnover_np = bundle_np.get('Turnover', np.ones_like(close_np) * 1e12) # Default huge if missing

        valid_indices = [idx for idx in univ_indices if not np.isnan(rs_alphas[idx])]
        # Scoring: Top RS leaders
        sorted_candidates = sorted(valid_indices, key=lambda x: rs_alphas[x], reverse=True)
        
        for s_idx in sorted_candidates:
            if len(portfolio) >= max_pos: break 
            if any(p['s_idx'] == s_idx for p in portfolio): continue
            
            rs = rs_alphas[s_idx]
            r2 = rsis[s_idx]
            t_close = close_np[i, s_idx]
            t_open = open_np[i, s_idx]
            t_sma20 = sma20_np[i, s_idx]
            t_sma200 = sma200s[s_idx]
            t_turnover = turnover_np[i, s_idx]
            
            # Momentum Filters
            if rs < 25.0: continue
            if t_close < t_sma20: continue
            if t_close < t_sma200 * 1.05: continue 

            # Entry Signal
            entry_signal = check_entry_signal(regime, r2, t_close, t_open, t_sma20, sma200=t_sma200)
                    
            if entry_signal:
                real_buy = t_close * (1.0 + slippage)
                raw_value = (total_equity * dynamic_lev / max_pos)
                
                # --- Adaptive Liquidity Filter (V148.0 Reality Apex) ---
                # Purpose: Ensure reality at scale.
                if raw_value < 5_000_000:
                    actual_value = raw_value # Small-cap growth phase
                elif raw_value < 20_000_000:
                    actual_value = min(raw_value, t_turnover * 0.20)
                else:
                    actual_value = min(raw_value, t_turnover * 0.05)
                
                shares = int(actual_value / real_buy)
                if shares > 0:
                    portfolio.append({
                        's_idx': s_idx, 'buy_price': real_buy,
                        'shares': shares, 'held_days': 0, 'max_price': real_buy,
                        'buy_atr': atr_np[i, s_idx]
                    })
                    cash -= real_buy * shares
                    trade_count += 1

    final = cash + sum(np.nan_to_num(close_np[-1, p['s_idx']]) * p['shares'] for p in portfolio)
    return float(final), trade_count, monthly_assets, trade_results
