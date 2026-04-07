import pandas as pd
import numpy as np

def run_backtest_v16_production(univ_indices, bundle_np, timeline, breadth_ratio,
                               initial_cash=10000000, max_pos=10, 
                               sl_mult=1.5, tp_mult=3.0, leverage_rate=2.0, breadth_threshold=0.4,
                               slippage=0.001, use_sma_exit=False, exit_buffer=0.985, max_hold_days=4,
                               verbose=False):
    """
    Mean Reversion / Short Swing System
    - Extreme Oversold: RSI(2) < 10 & Close < BB -2σ
    - Long-term Trend: Close > SMA100
    - Fast Exits: max_hold_days (Default 4), tight SL/TP
    """
    T = len(timeline)
    cash = float(initial_cash)
    portfolio = []
    trade_count = 0
    monthly_assets = {}
    trade_results = []
    
    close_np = bundle_np['Close']
    open_np, high_np, low_np = bundle_np['Open'], bundle_np['High'], bundle_np['Low']
    sma5_np = bundle_np['SMA5']
    sma20_np = bundle_np['SMA20']
    sma100_np = bundle_np['SMA100']
    atr_np = bundle_np['ATR']
    rsi2_np = bundle_np['RSI2']
    bb_lower_2_np = bundle_np['BB_LOWER_2']
    
    idx_1321 = bundle_np['tickers'].index('1321.T') if '1321.T' in bundle_np['tickers'] else None
    
    for i in range(100, T):
        curr_time = timeline[i]
        held_value = sum(np.nan_to_num(close_np[i, p['s_idx']]) * p['shares'] for p in portfolio)
        total_equity = cash + held_value
        
        if i % 20 == 0:
            monthly_assets[curr_time.strftime('%Y-%m')] = total_equity

        # 1. Management
        pending_cash = 0.0
        new_portfolio = []
        for p in portfolio:
            tidx = p['s_idx']
            today_open, today_high, today_low = open_np[i, tidx], high_np[i, tidx], low_np[i, tidx]
            
            # --- NaN Check ---
            if np.isnan(today_open) or np.isnan(today_high) or np.isnan(today_low):
                p['held_days'] += 1
                new_portfolio.append(p)
                continue
            
            exit_p = None
            if p.get('exit_next_open', False):
                exit_p = today_open
            
            if exit_p is None:
                if today_open <= p['sl_price']: exit_p = today_open
                elif today_low <= p['sl_price']: exit_p = p['sl_price']
                elif today_high >= p['tp_price']: exit_p = p['tp_price']
            
            if exit_p is not None:
                real_exit = exit_p * (1.0 - slippage)
                profit = (real_exit - p['buy_price']) * p['shares']
                trade_results.append(profit)
                pending_cash += real_exit * p['shares']
                trade_count += 1
            else:
                p['held_days'] += 1
                
                # --- 動的利確判定 (Dynamic Reversion Exit) ---
                today_close = close_np[i, tidx]
                today_sma5 = sma5_np[i, tidx]
                today_rsi2 = rsi2_np[i, tidx]
                
                # 平均回帰（SMA5上抜け）または過熱（RSI2 > 70）で翌日決済
                is_reverted = (not np.isnan(today_close) and today_close > today_sma5)
                is_overbought = (not np.isnan(today_rsi2) and today_rsi2 > 70)
                
                if is_reverted or is_overbought:
                    p['exit_next_open'] = True
                # --- 既存のタイムストップ処理 ---
                elif p['held_days'] >= max_hold_days:
                    p['exit_next_open'] = True
                        
                new_portfolio.append(p)
        portfolio, cash = new_portfolio, float(cash + pending_cash)

        # 2. Entry
        if i + 1 >= T: continue
        br = breadth_ratio[i]
        if br < breadth_threshold: continue
        
        current_leverage = leverage_rate
        
        if idx_1321 is not None:
             if close_np[i, idx_1321] < sma100_np[i, idx_1321]:
                  continue
        
        if len(portfolio) < max_pos:
            held_value = sum(np.nan_to_num(close_np[i, p['s_idx']]) * p['shares'] for p in portfolio)
            total_equity = cash + held_value
            buying_power = (total_equity * current_leverage) - held_value
            
            c_u = close_np[i, univ_indices]
            o_u = open_np[i, univ_indices]
            h_u = high_np[i, univ_indices]
            l_u = low_np[i, univ_indices]
            s100_u = sma100_np[i, univ_indices]
            rsi2_u = rsi2_np[i, univ_indices]
            bb_lower_2_u = bb_lower_2_np[i, univ_indices]
            
            # Reversion Entry Rules
            is_long_uptrend = (c_u > s100_u)
            is_panic_sold = (rsi2_u < 10) & (c_u < bb_lower_2_u)
            
            # --- V18.1 追加: スナイパー・エントリー（日中反発サイン） ---
            # 条件1: 終値が当日の変動幅（高値 - 安値）の半分より上で引けている（長い下ヒゲ、反発の証拠）
            is_rebound = (c_u - l_u) / (h_u - l_u + 1e-9) >= 0.5
            # 条件2: 陽線（終値 > 始値）
            is_white_candle = (c_u > o_u)
            
            # どちらかの反発サインが出ていること
            is_strong_close = is_rebound | is_white_candle
            
            valid_mask = is_long_uptrend & is_panic_sold & is_strong_close
            valid_idx = univ_indices[valid_mask]
            
            if len(valid_idx) > 0:
                # Prioritize strictly by lowest RSI2
                rsi_vals = rsi2_u[valid_mask]
                sorted_idx = valid_idx[np.argsort(rsi_vals)]
                
                for s_idx in sorted_idx:
                    if len(portfolio) >= max_pos: break
                    if s_idx in [p['s_idx'] for p in portfolio]: continue
                    
                    buy_v = open_np[i+1, s_idx]
                    if not np.isnan(buy_v) and buy_v > 0:
                        entry_p = buy_v * (1.0 + slippage)
                        entry_atr = max(1.0, np.nan_to_num(atr_np[i, s_idx]))
                        
                        allocation = (total_equity * current_leverage) / max_pos
                        actual_ma = min(allocation, buying_power)
                        
                        sh = (int(actual_ma / entry_p) // 100) * 100
                        
                        if sh >= 100:
                            portfolio.append({
                                "s_idx": s_idx, "buy_price": entry_p, "shares": sh, "held_days": 0,
                                "entry_atr": entry_atr,
                                "sl_price": entry_p - (entry_atr * sl_mult),
                                "tp_price": entry_p + (entry_atr * tp_mult)
                            })
                            cash -= entry_p * sh
                            buying_power -= entry_p * sh

    final = cash + sum(np.nan_to_num(close_np[-1, p['s_idx']]) * p['shares'] for p in portfolio)
    return float(final), trade_count, monthly_assets, trade_results
