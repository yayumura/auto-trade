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
    V17.0 Imperial Position Manager:
    - Returns: [portfolio, sell_actions]
    """
    sl_mult = ATR_STOP_LOSS
    tp_mult = TARGET_PROFIT_MULT
    
    remaining = []
    sell_actions = []
    
    for p in portfolio:
        code = str(p['code'])
        # 1. 価格取得
        if realtime_buffers and code in realtime_buffers:
            current_price = realtime_buffers[code].get_latest_price()
        else:
            current_price = float(p.get('current_price', p['buy_price']))
            
        buy_price = float(p['buy_price'])
        atr = float(p.get('buy_atr', 0))
        highest_price = float(p.get('highest_price', 0))
        
        # 2. 逆指値 (Stop Loss) 計算
        initial_stop = buy_price - (atr * sl_mult)
        
        # [V18.1] Break-even Stop (5.0 ATR Profit Protection)
        if highest_price >= buy_price + (atr * 5.0):
            initial_stop = max(initial_stop, buy_price * 1.002)
            
        if ATR_TRAIL and highest_price > 0:
            stop_price = max(initial_stop, highest_price - (atr * sl_mult))
        else:
            stop_price = initial_stop
            
        # 3. 利確 (Profit Target) 計算
        target_price = buy_price + (atr * tp_mult)
        
        # 4. タイムリミット (保有10日以上で停滞判定、60日以上で強制決済)
        is_timeout = False
        is_stagnated = False
        buy_time_str = p.get('buy_time')
        if buy_time_str:
            try:
                buy_dt = dt.strptime(buy_time_str, '%Y-%m-%d %H:%M:%S')
                days_held = (dt.now() - buy_dt).days
                if days_held >= 5:
                    is_timeout = True
                elif days_held >= 2 and current_price <= buy_price:
                    is_stagnated = True
            except: pass
        
        # 5. 窓開け暴落（ギャップダウン）対応 (シミュレーション用)
        # 始値がストップロスを既に下回っている場合、始値で決済
        is_gap_down = False
        exit_price = current_price
        
        if is_simulation and today_ohlc and code in today_ohlc:
            o_price = today_ohlc[code].get('Open', 0)
            if o_price > 0 and o_price <= stop_price:
                is_gap_down = True
                exit_price = o_price
        
        # 6. Technical Exit: SMA20割れ判定
        is_sma_breach = False
        if EXIT_ON_SMA20_BREACH and sma20_map and code in sma20_map:
            if current_price < float(sma20_map[code]) * SMA20_EXIT_BUFFER:
                is_sma_breach = True

        # 7. 売却判定
        if is_gap_down:
            sell_actions.append(f"SELL {code} - Gap Down Stop Loss Triggered (@{exit_price:,.1f})")
            if not is_simulation and broker:
                try: broker.execute_chase_order(code, p['shares'], side="1")
                except: pass
            continue
        elif is_sma_breach:
            sell_actions.append(f"SELL {code} - SMA20 Breach Triggered (@{current_price:,.1f})")
            if not is_simulation and broker:
                try: broker.execute_chase_order(code, p['shares'], side="1")
                except: pass
            continue
        elif current_price <= stop_price:
            reason = "Stop Loss" if stop_price < buy_price else "Break-even Stop"
            sell_actions.append(f"SELL {code} - {reason} Triggered (@{current_price:,.1f})")
            if not is_simulation and broker:
                try: broker.execute_chase_order(code, p['shares'], side="1")
                except: pass
            continue
        elif is_stagnated:
            sell_actions.append(f"SELL {code} - Time Stop (Stagnation) (@{current_price:,.1f})")
            if not is_simulation and broker:
                try: broker.execute_chase_order(code, p['shares'], side="1")
                except: pass
            continue
        elif is_timeout:
            sell_actions.append(f"SELL {code} - Time Limit Reached (5 Days)")
            if not is_simulation and broker:
                try: broker.execute_chase_order(code, p['shares'], side="1")
                except: pass
            continue
        elif current_price >= target_price:
            sell_actions.append(f"SELL {code} - Profit Target Reached (@{current_price:,.1f})")
            if not is_simulation and broker:
                try: broker.execute_chase_order(code, p['shares'], side="1")
                except: pass
            continue
            
        # 7. 評価額と高値の更新
        p['current_price'] = round(current_price, 1)
        if current_price > float(p.get('highest_price', 0)):
            p['highest_price'] = round(current_price, 1)
            
        remaining.append(p)

    return remaining, sell_actions

def calculate_all_technicals_v12(data_df):
    """
    V17.0 Imperial Technical Bundle:
    - SMA5, SMA20, SMA100
    - ATR (20)
    - RS (Normalized Strength)
    """
    bundle = {}
    
    # xs for metric
    close = data_df.xs('Close', axis=1, level=1)
    high = data_df.xs('High', axis=1, level=1)
    low = data_df.xs('Low', axis=1, level=1)
    
    bundle['Close'] = close
    bundle['SMA5'] = close.rolling(5).mean()
    bundle['SMA20'] = close.rolling(20).mean()
    bundle['SMA100'] = close.rolling(100).mean()
    
    # ATR (20) Vectorized
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    
    # Vectorized element-wise max for true range
    tr = pd.DataFrame(
        np.maximum(np.maximum(tr1.values, tr2.values), tr3.values),
        index=close.index,
        columns=close.columns
    )
    bundle['ATR'] = tr.rolling(20).mean()
    
    # RS (Momentum Strength: SMA5 / SMA100 Ratio)
    bundle['RS'] = (bundle['SMA5'] / bundle['SMA100'] * 100).fillna(0)
    
    # Store Open for reversal check
    bundle['Open'] = data_df.xs('Open', axis=1, level=1)
    
    return bundle

def detect_market_regime(data_df=None, buffer=None):
    """
    V17.2 Imperial Regime Filter:
    - Checks if Nikkei 225 (1321.T) is above its SMA100.
    - If below, returns BEAR to suppress new entries.
    """
    if data_df is not None:
        try:
            # 1321.T SMA100 Check
            close_all = data_df.xs('Close', axis=1, level=1)
            if '1321.T' in close_all.columns:
                close_1321 = close_all['1321.T']
                sma100_1321 = close_1321.rolling(100).mean().iloc[-1]
                current_1321 = close_1321.iloc[-1]
                if current_1321 < sma100_1321:
                    return "BEAR"
        except:
            pass

    # Fallback to buffer check if available
    if buffer and '1321' in buffer:
        price = buffer['1321'].get_latest_price()
        if price > 0: return "BULL"
        
    return "BULL"

def select_best_candidates(data_df, targets, symbols_df, regime, realtime_buffers=None):
    """
    V17.0 Imperial Selection Engine:
    - Filters targets based on SMA alignment and RS.
    - Requires: SMA5 > SMA20 > SMA100 (Perfect Power Order)
    """
    bundle = calculate_all_technicals_v12(data_df)
    
    close = bundle['Close'].iloc[-1]
    sma5 = bundle['SMA5'].iloc[-1]
    sma20 = bundle['SMA20'].iloc[-1]
    sma100 = bundle['SMA100'].iloc[-1]
    atr = bundle['ATR'].iloc[-1]
    rs = bundle['RS'].iloc[-1]
    
    candidates = []
    
    for t_with_t in [f"{t}.T" for t in targets]:
        if t_with_t not in close.index: 
            # In data_df, columns are tickers.
            if t_with_t not in bundle['Close'].columns: continue
        
        code_only = t_with_t.replace(".T", "")
        p = close[t_with_t]
        s5, s20, s100 = sma5[t_with_t], sma20[t_with_t], sma100[t_with_t]
        
        if pd.isna(p) or p <= 0: continue
        
        # Imperial Trend: 5 > 20 > 100
        if s5 > s20 > s100:
            # Entry Signal 1: Pullback (Price strictly between SMA20 * 0.98 and SMA20 * 1.02)
            if s20 * 0.98 <= p < s20 * 1.02:
                # Entry Signal 2: Reversal Confirmation (Close > Prev Close OR Close > Open)
                prev_p = bundle['Close'].iloc[-2][t_with_t]
                open_p = bundle['Open'].iloc[-1][t_with_t]
                h_p = bundle['High'].iloc[-1][t_with_t]
                l_p = bundle['Low'].iloc[-1][t_with_t]
                
                # [V19.0 Momentum Sync] +1.5% Gain Constraint
                is_momentum = p >= prev_p * 1.015

                if ((p > prev_p) or (p > open_p)) and is_strong and is_momentum:
                    # Name lookup
                    name = "Target"
                if symbols_df is not None:
                    match = symbols_df[symbols_df['コード'].astype(str) == code_only]
                    if not match.empty: name = match.iloc[0]['銘柄名']
                
                candidates.append({
                    "code": code_only,
                    "name": name,
                    "price": p,
                    "atr": atr[t_with_t],
                    "rs": rs[t_with_t],
                    "score": rs[t_with_t]
                })

    # Sort by RS descending
    candidates = sorted(candidates, key=lambda x: x['rs'], reverse=True)
    return candidates[:10]

class RealtimeBuffer:
    def __init__(self, code, initial_df=None, interval_mins=15):
        self.code = code
        self.latest_price = 0
        self.latest_volume = 0
        
    def update(self, price, volume, server_time):
        if price and price > 0:
            self.latest_price = price
            self.latest_volume = volume
            
    def get_latest_price(self):
        return self.latest_price

def load_invalid_tickers():
    try:
        with open(EXCLUSION_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_invalid_tickers(invalid_map):
    try:
        with open(EXCLUSION_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(invalid_map, f, indent=4)
    except:
        pass

def normalize_tick_size(price, is_buy=True):
    return round(price, 1)

def get_prime_tickers():
    import os
    import pandas as pd
    from core.config import DATA_FILE
    if not os.path.exists(DATA_FILE):
        return []
    df = pd.read_csv(DATA_FILE)
    if '市場・商品区分' in df.columns:
        prime = df[df['市場・商品区分'].str.contains('プライム', na=False)]
        return [f"{str(code)}.T" for code in prime['コード']]
    return []
