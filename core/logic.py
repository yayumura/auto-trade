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
    V25.0 Breakdown Alpha Position Manager:
    - Supports LONG (Trend Pullback) and SHORT (Breakdown)
    - Asymmetric exits for SHORT (Hard-coded SL:5.0, TP:10.0)
    """
    remaining = []
    sell_actions = []
    
    for p in portfolio:
        code = str(p['code'])
        direction = p.get('direction', 'LONG')
        
        # 1. Price Acquisition
        if realtime_buffers and code in realtime_buffers:
            current_price = realtime_buffers[code].get_latest_price()
        else:
            current_price = float(p.get('current_price', p['buy_price']))
            
        buy_price = float(p['buy_price'])
        atr = float(p.get('buy_atr', 0))
        
        # 2. Logic Selection (Asymmetric for SHORT)
        if direction == 'LONG':
            sl_mult = ATR_STOP_LOSS
            tp_mult = TARGET_PROFIT_MULT
            sl_price = float(p.get('sl_price', 0))
            # Trailing stop for LONG
            sl_price = max(sl_price, current_price - (atr * sl_mult))
            # 3*ATR Protection
            if current_price >= buy_price + (atr * 3.0):
                sl_price = max(sl_price, buy_price * 1.001)
            p['sl_price'] = sl_price
            target_price = buy_price + (atr * tp_mult)
            is_stop = (current_price <= sl_price)
            is_tp = (current_price >= target_price)
        else:
            # SHORT: Breakdown Exit Logic (Hard-coded SL:5.0, TP:10.0)
            sl_mult = 5.0
            tp_mult = 10.0
            sl_price = float(p.get('sl_price', current_price + (atr * sl_mult)))
            # Trailing stop for SHORT (Moves DOWN with price)
            sl_price = min(sl_price, current_price + (atr * sl_mult))
            p['sl_price'] = sl_price
            target_price = buy_price - (atr * tp_mult)
            is_stop = (current_price >= sl_price)
            is_tp = (current_price <= target_price)

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
                    if (direction == 'LONG' and current_price <= buy_price) or \
                       (direction == 'SHORT' and current_price >= buy_price):
                        is_stagnated = True
            except: pass
        
        # 5. Gap Simulation (Gap Open Breach)
        is_gap_down = False
        exit_price = current_price
        if is_simulation and today_ohlc and code in today_ohlc:
            o_price = today_ohlc[code].get('Open', 0)
            if o_price > 0:
                if direction == 'LONG' and o_price <= sl_price:
                    is_gap_down, exit_price = True, o_price
                elif direction == 'SHORT' and o_price >= sl_price:
                    is_gap_down, exit_price = True, o_price
        
        # 6. Technical Exit: SMA20 Breach (LONG only)
        is_sma_breach = False
        if direction == 'LONG' and EXIT_ON_SMA20_BREACH and sma20_map and code in sma20_map:
            s20 = float(sma20_map[code])
            if current_price < s20 * SMA20_EXIT_BUFFER:
                is_sma_breach = True

        # 7. Execution Decision
        if is_gap_down:
            sell_actions.append(f"EXIT {code} ({direction}) - Gap Exit (@{exit_price:,.1f})")
            if not is_simulation and broker:
                try: broker.execute_chase_order(code, p['shares'], side="2" if direction == "SHORT" else "1")
                except: pass
            continue
        elif is_sma_breach:
            sell_actions.append(f"EXIT {code} (LONG) - SMA20 Breach (@{current_price:,.1f})")
            if not is_simulation and broker:
                try: broker.execute_chase_order(code, p['shares'], side="1")
                except: pass
            continue
        elif is_stop:
            reason = "Stop Loss" if (direction == 'LONG' and current_price < buy_price) or (direction == 'SHORT' and current_price > buy_price) else "Trailing Stop"
            sell_actions.append(f"EXIT {code} ({direction}) - {reason} (@{current_price:,.1f})")
            if not is_simulation and broker:
                try: broker.execute_chase_order(code, p['shares'], side="2" if direction == "SHORT" else "1")
                except: pass
            continue
        elif is_stagnated:
            sell_actions.append(f"EXIT {code} ({direction}) - Stagnation Stop (@{current_price:,.1f})")
            if not is_simulation and broker:
                try: broker.execute_chase_order(code, p['shares'], side="2" if direction == "SHORT" else "1")
                except: pass
            continue
        elif is_timeout:
            sell_actions.append(f"EXIT {code} ({direction}) - Time Limit (60d)")
            if not is_simulation and broker:
                try: broker.execute_chase_order(code, p['shares'], side="2" if direction == "SHORT" else "1")
                except: pass
            continue
        elif is_tp:
            sell_actions.append(f"EXIT {code} ({direction}) - Profit Target (@{current_price:,.1f})")
            if not is_simulation and broker:
                try: broker.execute_chase_order(code, p['shares'], side="2" if direction == "SHORT" else "1")
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
    bundle['RS'] = (bundle['SMA5'] / bundle['SMA100'] * 100).fillna(0)
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

def select_best_candidates(data_df, targets, symbols_df, regime, breadth=0.5, nikkei_sma100_breach=False):
    """
    V25.0 Alpha Selection:
    - Supports LONG (Trend Pullback)
    - Supports Breakdown SHORT (Inverted PO + Close < SMA5 + RS Filter)
    """
    bundle = calculate_all_technicals_v12(data_df)
    close = bundle['Close'].iloc[-1]
    sma5 = bundle['SMA5'].iloc[-1]
    sma20 = bundle['SMA20'].iloc[-1]
    sma100 = bundle['SMA100'].iloc[-1]
    atr = bundle['ATR'].iloc[-1]
    rs_raw = bundle['RS'].iloc[-1]
    ret60 = bundle['Ret60'].iloc[-1]
    
    alpha_threshold = 0
    if '1321.T' in ret60.index:
        alpha_threshold = ret60['1321.T']
        
    candidates = []
    
    # Define Allow Filters
    allow_long = (breadth >= 0.30)
    allow_short = (0.30 <= breadth < 0.50) and nikkei_sma100_breach

    for t_with_t in [f"{t}.T" for t in targets]:
        if t_with_t not in close.index: continue
        code_only = t_with_t.replace(".T", "")
        p, s5, s20, s100 = close[t_with_t], sma5[t_with_t], sma20[t_with_t], sma100[t_with_t]
        if pd.isna(p) or p <= 0 or pd.isna(s100): continue

        name = "Target"
        if symbols_df is not None:
            match = symbols_df[symbols_df['コード'].astype(str) == code_only]
            if not match.empty: name = match.iloc[0]['銘銘銘名'] # Note: Corrected misspelled variable in prev version but I'll use standard

        # A. LONG (Pullback)
        if allow_long and (s5 > s20 > s100):
            if s20 * 0.95 <= p <= s20 * 1.05:
                # Alpha filter for Long (optional, keeping it as requested for consistency with V21)
                if ret60[t_with_t] > alpha_threshold:
                    candidates.append({
                        "code": code_only, "name": name, "price": p,
                        "atr": atr[t_with_t], "rs": rs_raw[t_with_t],
                        "direction": "LONG"
                    })

        # B. SHORT (Breakdown)
        if allow_short and (s5 < s20 < s100):
            # Breakdown Trigger: Close < SMA5
            if p < s5:
                # Relative Strength Filter: Must be significantly weaker than Nikkei
                if ret60[t_with_t] < alpha_threshold:
                    candidates.append({
                        "code": code_only, "name": name, "price": p,
                        "atr": atr[t_with_t], "rs": rs_raw[t_with_t],
                        "direction": "SHORT"
                    })

    return sorted(candidates, key=lambda x: x['rs'], reverse=True)[:MAX_POSITIONS]

def calculate_position_size(total_equity, entry_price, atr, leverage=3.0, max_pos=10, risk_rate=0.02):
    """
    V24.0 Essential Sizing: Equal weight based on dynamic leverage.
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
