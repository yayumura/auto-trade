import json
import pandas as pd
import numpy as np
from datetime import datetime as dt
from core.config import (
    ATR_STOP_LOSS, TARGET_PROFIT_MULT, JST, BREADTH_THRESHOLD,
    MAX_POSITIONS, MAX_RISK_PER_TRADE, MAX_ALLOCATION_PCT,
    MAX_ALLOCATION_AMOUNT, LIQUIDITY_LIMIT_RATE, MIN_ALLOCATION_AMOUNT,
    EXCLUSION_CACHE_FILE, PROJECT_ROOT, DATA_ROOT, ATR_TRAIL, EXIT_ON_SMA20_BREACH,
    SMA20_EXIT_BUFFER
)

def manage_positions_live(portfolio, account, broker=None, regime="BULL", is_simulation=True, realtime_buffers=None, today_ohlc=None, sma20_map=None):
    """
    V29.0 The Absolute Apex Position Manager:
    - Pure LONG + Pullback (V21 based)
    - Corrected Buffer: 0.94 (SMA20 Exit)
    - Trailing stop update from High
    """
    remaining = []
    sell_actions = []
    
    for p in portfolio:
        code = str(p['code'])
        
        # 1. Price Acquisition
        if realtime_buffers and code in realtime_buffers:
            current_price = realtime_buffers[code].get_latest_price()
            today_high = realtime_buffers[code].get_day_high() 
        else:
            current_price = float(p.get('current_price', p['buy_price']))
            today_high = current_price # Fallback
            
        buy_price = float(p['buy_price'])
        atr = float(p.get('buy_atr', 0))
        
        # 2. Stop Loss / Trailing Stop (V21: Trail from High)
        sl_mult = ATR_STOP_LOSS
        tp_mult = TARGET_PROFIT_MULT
        sl_price = float(p.get('sl_price', 0))
        
        # [RESTORED] Trailing stop update from High
        sl_price = max(sl_price, today_high - (atr * sl_mult))
            
        p['sl_price'] = sl_price
        target_price = buy_price + (atr * tp_mult)
        
        # 3. Exit Conditions
        is_stop = (current_price <= sl_price)
        is_tp = (current_price >= target_price)

        # 4. Time Limit (60d forced exit)
        is_timeout = False
        is_stagnated = False
        buy_time_str = p.get('buy_time')
        if buy_time_str:
            try:
                buy_dt = dt.strptime(buy_time_str, '%Y-%m-%d %H:%M:%S')
                days_held = (dt.now() - buy_dt).days
                if days_held >= 60:
                    is_timeout = True
                elif days_held >= 20: 
                    if current_price <= buy_price:
                        is_stagnated = True
            except: pass
        
        # 5. Gap Simulation (Gap Open Breach)
        is_gap_down = False
        exit_price = current_price
        if is_simulation and today_ohlc and code in today_ohlc:
            o_price = today_ohlc[code].get('Open', 0)
            if o_price > 0 and o_price <= sl_price:
                is_gap_down, exit_price = True, o_price
        
        # 6. Technical Exit: SMA20 Breach (LONG)
        is_sma_breach = False
        if EXIT_ON_SMA20_BREACH and sma20_map and code in sma20_map:
            s20 = float(sma20_map[code])
            if current_price < s20 * SMA20_EXIT_BUFFER:
                is_sma_breach = True

        # 7. Execution Decision
        if is_gap_down:
            sell_actions.append(f"SELL {code} - Gap Exit (@{exit_price:,.1f})")
            if not is_simulation and broker:
                try: broker.execute_chase_order(code, p['shares'], side="1")
                except: pass
            continue
        elif is_sma_breach:
            sell_actions.append(f"SELL {code} - SMA20 Breach (@{current_price:,.1f})")
            if not is_simulation and broker:
                try: broker.execute_chase_order(code, p['shares'], side="1")
                except: pass
            continue
        elif is_stop:
            reason = "Stop Loss" if current_price < buy_price else "Trailing Stop"
            sell_actions.append(f"SELL {code} - {reason} (@{current_price:,.1f})")
            if not is_simulation and broker:
                try: broker.execute_chase_order(code, p['shares'], side="1")
                except: pass
            continue
        elif is_stagnated:
            sell_actions.append(f"SELL {code} - Stagnation Stop (@{current_price:,.1f})")
            if not is_simulation and broker:
                try: broker.execute_chase_order(code, p['shares'], side="1")
                except: pass
            continue
        elif is_timeout:
            sell_actions.append(f"SELL {code} - Time Limit (60d)")
            if not is_simulation and broker:
                try: broker.execute_chase_order(code, p['shares'], side="1")
                except: pass
            continue
        elif is_tp:
            sell_actions.append(f"SELL {code} - Profit Target (@{current_price:,.1f})")
            if not is_simulation and broker:
                try: broker.execute_chase_order(code, p['shares'], side="1")
                except: pass
            continue
            
        # 8. Update Stats
        p['current_price'] = round(current_price, 1)
        remaining.append(p)

    return remaining, sell_actions

def calculate_all_technicals_v12(data_df):
    bundle = {}
    close = data_df.xs('Close', axis=1, level=1)
    high = data_df.xs('High', axis=1, level=1)
    low = data_df.xs('Low', axis=1, level=1)
    
    bundle['Close'] = close
    bundle['SMA5'] = close.rolling(5).mean()
    bundle['SMA20'] = close.rolling(20).mean()
    bundle['SMA100'] = close.rolling(100).mean()
    
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.DataFrame(np.maximum(np.maximum(tr1.values, tr2.values), tr3.values), index=close.index, columns=close.columns)
    bundle['ATR'] = tr.rolling(20).mean()
    bundle['RS'] = (bundle['SMA5'] / bundle['SMA20'] * 100).fillna(0)
    bundle['High'] = high
    bundle['Low'] = low
    bundle['Open'] = data_df.xs('Open', axis=1, level=1)
    
    # 60-day Return (Vectorized)
    bundle['Ret60'] = (close / close.shift(60) - 1).fillna(0)
    
    return bundle

def detect_market_regime(data_df=None, buffer=None):
    if data_df is not None:
        try:
            close_all = data_df.xs('Close', axis=1, level=1)
            if '1321.T' in close_all.columns:
                close_1321 = close_all['1321.T']
                sma100_1321 = close_1321.rolling(100).mean().iloc[-1]
                current_1321 = close_1321.iloc[-1]
                if current_1321 < sma100_1321: return "BEAR"
        except: pass
    return "BULL"

def select_best_candidates(data_df, targets, symbols_df, regime, breadth=0.5):
    """
    V30.0 [The Real V21 Clone] Selection:
    - [RESTORED V21] Pullback (0.96-1.04) + Reversal + Strong Close
    - Dynamic Leverage: 1x to 3x based on Breadth
    """
    if breadth < 0.30: return []
    
    bundle = calculate_all_technicals_v12(data_df)
    close = bundle['Close'].iloc[-1]
    sma5 = bundle['SMA5'].iloc[-1]
    sma20 = bundle['SMA20'].iloc[-1]
    sma100 = bundle['SMA100'].iloc[-1]
    atr = bundle['ATR'].iloc[-1]
    rs_raw = bundle['RS'].iloc[-1]
    ret60 = bundle['Ret60'].iloc[-1]
    
    # [RESTORED V21] Previous close for reversal check
    prev_close = bundle['Close'].iloc[-2]
    
    alpha_threshold = 0
    if '1321.T' in ret60.index:
        alpha_threshold = ret60['1321.T']
        
    candidates = []
    
    for t_with_t in [f"{t}.T" for t in targets]:
        if t_with_t not in close.index: continue
        code_only = t_with_t.replace(".T", "")
        p, s5, s20, s100 = close[t_with_t], sma5[t_with_t], sma20[t_with_t], sma100[t_with_t]
        if pd.isna(p) or p <= 0 or pd.isna(s100): continue

        name = "Target"
        if symbols_df is not None:
            match = symbols_df[symbols_df['コード'].astype(str) == code_only]
            if not match.empty: name = match.iloc[0]['銘柄名']

        # [RESTORED V21] Pure Perfect Order + Tight Pullback + Reversal Confirmation
        if (s5 > s20 > s100):
            # 1. Pullback Check (0.96-1.04)
            if s20 * 0.96 <= p <= s20 * 1.04:
                # 2. Strong Close & Reversal Check
                today_h = bundle['High'].iloc[-1][t_with_t]
                today_l = bundle['Low'].iloc[-1][t_with_t]
                today_o = bundle['Open'].iloc[-1][t_with_t]
                prev_c  = prev_close[t_with_t]
                
                is_strong = (p - today_l) / (today_h - today_l + 1e-9) >= 0.5
                is_reversal = ((p > prev_c) or (p > today_o)) and is_strong
                
                if is_reversal:
                    # Alpha filter (Relative Strength > Nikkei)
                    if ret60[t_with_t] > alpha_threshold:
                        candidates.append({
                            "code": code_only, "name": name, "price": p,
                            "atr": atr[t_with_t], "rs": rs_raw[t_with_t],
                            "direction": "LONG"
                        })

    return sorted(candidates, key=lambda x: x['rs'], reverse=True)[:MAX_POSITIONS]

def calculate_position_size(total_equity, entry_price, atr, leverage=1.0, max_pos=7):
    """
    V29.0 Sizing: Dynamic leverage based on Breadth.
    """
    if entry_price <= 0: return 0
    allocation_yen = (total_equity * leverage) / max_pos
    shares = allocation_yen / entry_price
    return (int(shares) // 100) * 100

def normalize_tick_size(price, is_buy=True):
    return round(price, 1)

def get_prime_tickers():
    import os
    import pandas as pd
    from core.config import DATA_FILE
    if not os.path.exists(DATA_FILE): return []
    df = pd.read_csv(DATA_FILE)
    if '市場・商品区分' in df.columns:
        prime = df[df['市場・商品区分'].str.contains('プライム', na=False)]
        return [f"{str(code)}.T" for code in prime['コード']]
    return []
