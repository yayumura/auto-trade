import json
import pandas as pd
import numpy as np
from datetime import datetime as dt
from core.config import (
    ATR_STOP_LOSS, TARGET_PROFIT_MULT, JST, BREADTH_THRESHOLD,
    MAX_POSITIONS, MAX_RISK_PER_TRADE, MAX_ALLOCATION_PCT,
    MAX_ALLOCATION_AMOUNT, LIQUIDITY_LIMIT_RATE, MIN_ALLOCATION_AMOUNT,
    EXCLUSION_CACHE_FILE, PROJECT_ROOT, DATA_ROOT, ATR_TRAIL, EXIT_ON_SMA20_BREACH,
    SMA20_EXIT_BUFFER, MAX_HOLD_DAYS
)

def manage_positions_live(portfolio, account, broker=None, regime="BULL", is_simulation=True, realtime_buffers=None, today_ohlc=None, sma20_map=None, month_drawdown=0.0, is_trend_snapped=False, market_breadth=0.5):
    """
    V143.0 Adaptive Alpha Manager:
    - Growth Focus: 3.0 ATR base trail.
    - Market Shield: Tightens to 1.5 ATR if Breadth < 0.45.
    - Safe Mode: Tightens to 1.0 ATR if Month DD > 7%.
    """
    remaining = []
    sell_actions = []
    
    exit_threshold = get_exit_thresholds(regime, is_trend_snapped)

    for p in portfolio:
        code = str(p['code'])
        # 1. Price Acquisition
        if realtime_buffers and code in realtime_buffers:
            current_price = realtime_buffers[code].get_latest_price()
            rsi2 = realtime_buffers[code].get_current_rsi2() if hasattr(realtime_buffers[code], 'get_current_rsi2') else 50
        else:
            current_price = float(p.get('current_price', p['buy_price']))
            rsi2 = 50 
            
        buy_price = float(p['buy_price'])
        atr = float(p.get('buy_atr', 0))
        highest_price = float(p.get('highest_price', 0))
        
        # 2. Adaptive Stop Multiplier
        stop_mult = 3.0 # Base (High performance)
        
        # Protective triggers
        if market_breadth < BREADTH_THRESHOLD: stop_mult = 1.5 # Market rotation protection
        if month_drawdown <= -0.07: stop_mult = 1.0 # Emergency lockdown
        
        stop_dist = stop_mult * atr 
        initial_stop = buy_price - stop_dist
        
        # Trailing
        if current_price > buy_price:
             tsl_price = max(initial_stop, highest_price - stop_dist)
        else:
             tsl_price = initial_stop
            
        # 3. Technical Trend Exit
        is_trend_broken = False
        if sma20_map and code in sma20_map:
            # Buffer for optimized endurance (Synced with config)
            if current_price < float(sma20_map[code]) * SMA20_EXIT_BUFFER: 
                is_trend_broken = True

        # 4. Sell Decision
        exit_reason = None
        if current_price <= tsl_price:
            exit_reason = f"Trail Stop ({stop_mult:.1f} ATR)"
        elif rsi2 > exit_threshold:
            exit_reason = f"Profit Peak ({rsi2:.1f})"
        elif is_trend_broken:
            exit_reason = "Trend Breach (SMA20)"
        elif month_drawdown <= -0.15: # Doomsday
            exit_reason = "System Circuit Breaker"
            
        # 5. Time Stop (V17.0 Parity)
        buy_time_str = p.get('buy_time')
        if buy_time_str:
            try:
                bt = dt.strptime(buy_time_str, '%Y-%m-%d %H:%M:%S')
                days_held = (dt.now() - bt).days
                if days_held >= MAX_HOLD_DAYS:
                    exit_reason = f"Time Stop ({days_held} days)"
            except: pass

        if exit_reason:
            sell_actions.append(f"SELL {code} - {exit_reason} (@{current_price:,.1f})")
            if not is_simulation and broker:
                try: broker.execute_chase_order(code, p['shares'], side="1")
                except: pass
            continue
            
        p['current_price'] = round(current_price, 1)
        if current_price > float(p.get('highest_price', 0)):
            p['highest_price'] = round(current_price, 1)
        remaining.append(p)

    return remaining, sell_actions

def calculate_aegis_shield(month_drawdown, regime="BULL"):
    """V140.0 Adaptive Exposure"""
    if month_drawdown <= -0.05: return 0.5
    if month_drawdown <= -0.10: return 0.0 # Shutdown entry
    return 1.0

def get_exit_thresholds(regime, is_trend_snapped):
    """V140.0 Profit Locking (Ride to 90+ in Bulls)"""
    if regime == "BULL": return 92
    return 80

def calculate_dynamic_leverage(breadth_val, config_leverage=1.5, shield_mult=1.0):
    """V140.0 Breadth Scaling"""
    if breadth_val >= 0.60: base = 2.0
    elif breadth_val >= 0.40: base = 1.0
    else: base = 0.0
    return min(base, config_leverage) * shield_mult

def check_entry_signal(regime, rsi2, price, open_p, sma20, sma200=0):
    """V140.0 Momentum Entry: Buy Strength"""
    if regime != "BULL": return False # Strictly Bull only for momentum
    
    # Perfect Order Confirmation: Price > SMA20 > SMA200
    if price < sma20: return False
    if sma200 > 0 and price < sma200 * 1.05: return False 
    
    # Entry on strength (RSI2 indicates buying pressure, not oversold)
    if rsi2 > 40 and price > open_p:
        return True
    return False

def calculate_all_technicals_v12(data_df):
    """
    V131.1 Aegis Technical Bundle:
    - Added RS_Alpha (Absolute 60-day) for leader selection
    - Added RSI2 for mean reversion entry/exit
    """
    bundle = {}
    close = data_df.xs('Close', axis=1, level=1)
    high = data_df.xs('High', axis=1, level=1)
    low = data_df.xs('Low', axis=1, level=1)
    open_v = data_df.xs('Open', axis=1, level=1)
    vol = data_df.xs('Volume', axis=1, level=1)
    
    bundle['Close'] = close
    bundle['Open'] = open_v
    bundle['Volume'] = vol
    bundle['SMA5'] = close.rolling(5).mean()
    bundle['SMA20'] = close.rolling(20).mean()
    bundle['SMA50'] = close.rolling(50).mean()
    bundle['SMA100'] = close.rolling(100).mean()
    bundle['SMA200'] = close.rolling(200).mean()
    
    # RSI (2) Vectorized
    delta = close.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    # Wilder's smoothing equivalent via rolling
    ma_up = up.rolling(2).mean()
    ma_down = down.rolling(2).mean()
    rs_rsi = ma_up / (ma_down + 1e-9)
    bundle['RSI2'] = 100 - (100 / (1 + rs_rsi))
    
    # ATR (20) Vectorized
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1)
    bundle['ATR'] = (high - low).rolling(20).mean() # Simple approximation for speed, or properly calculate TR
    # Proper TR calculation:
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.DataFrame(np.maximum(np.maximum(tr1.values, tr2.values), tr3.values), index=close.index, columns=close.columns)
    bundle['ATR'] = tr.rolling(20).mean()
    
    # RS_Alpha (Absolute Momentum: 3-month performance ratio)
    bundle['RS_Alpha'] = (close / close.shift(60) - 1.0) * 100

    # Turnover (Value) calculation for liquidity filtering
    if vol is not None:
        turnover = close * vol
        bundle['Turnover'] = turnover.rolling(5).median() # 5-day median turnover
    
    return bundle

def detect_market_regime(data_df=None, buffer=None):
    """
    V131.1 Aegis Regime Detection:
    - BULL: Price > SMA200 and SMA200 Slope > 0.02%
    - BEAR: Price < SMA200 * 0.98
    - NEUTRAL: Else
    """
    regime = "NEUTRAL"
    is_trend_snapped = False
    
    if data_df is not None:
        try:
            close_all = data_df.xs('Close', axis=1, level=1)
            if '1321.T' in close_all.columns:
                c_1321 = close_all['1321.T']
                sma200 = c_1321.rolling(200).mean()
                sma5 = c_1321.rolling(5).mean()
                
                curr_p = c_1321.iloc[-1]
                curr_sma200 = sma200.iloc[-1]
                prev_sma200 = sma200.iloc[-5] # 1 week ago
                slope = (curr_sma200 / prev_sma200 - 1.0) * 100
                
                if curr_p > curr_sma200 and slope > 0.02:
                    regime = "BULL"
                elif curr_p < curr_sma200 * 0.98:
                    regime = "BEAR"
                
                if curr_p < sma5.iloc[-1]:
                    is_trend_snapped = True
        except: pass

    return regime, is_trend_snapped

def select_best_candidates(data_df, targets, symbols_df, regime, realtime_buffers=None):
    """
    V140.0 Momentum Leader Selection:
    - Universe: Stocks with RS_Alpha > 25.
    - Sorting: RS_Alpha Descending.
    """
    bundle = calculate_all_technicals_v12(data_df)
    
    close = bundle['Close'].iloc[-1]
    open_p = bundle['Open'].iloc[-1]
    rsi2 = bundle['RSI2'].iloc[-1]
    sma20 = bundle['SMA20'].iloc[-1]
    sma200 = bundle['SMA200'].iloc[-1]
    atr = bundle['ATR'].iloc[-1]
    rs_alpha = bundle['RS_Alpha'].iloc[-1]
    
    candidates = []
    for t_with_t in [f"{t}.T" for t in targets]:
        if t_with_t not in close.index: continue
        
        p = close[t_with_t]
        o = open_p[t_with_t]
        r2 = rsi2[t_with_t]
        s20 = sma20[t_with_t]
        s200 = sma200[t_with_t]
        rs = rs_alpha[t_with_t]
        
        if pd.isna(p) or p <= 0 or pd.isna(rs): continue
        if rs < 25.0: continue # Momentum requirement
        
        entry_signal = check_entry_signal(regime, r2, p, o, s20, s200)
                
        if entry_signal:
            code_only = t_with_t.replace(".T", "")
            name = "Target"
            if symbols_df is not None:
                match = symbols_df[symbols_df['コード'].astype(str) == code_only]
                if not match.empty: name = match.iloc[0]['銘柄名']
            
            candidates.append({
                "code": code_only,
                "name": name,
                "price": p,
                "atr": atr[t_with_t],
                "rs": rs,
                "rsi2": r2,
                "score": rs # Pure momentum score
            })

    candidates = sorted(candidates, key=lambda x: x['rs'], reverse=True)
    return candidates 

class RealtimeBuffer:
    def __init__(self, code, initial_df=None, interval_mins=15):
        self.code = code
        self.latest_price = 0
        self.latest_volume = 0
        self.prices = [] # Simplified history for RSI2
        
    def update(self, price, volume, server_time):
        if price and price > 0:
            if self.latest_price != price:
                self.prices.append(price)
            self.latest_price = price
            self.latest_volume = volume
            if len(self.prices) > 20: self.prices = self.prices[-20:]
            
    def get_latest_price(self):
        return self.latest_price

    def get_current_rsi2(self):
        if len(self.prices) < 3: return 50
        diffs = np.diff(self.prices[-3:])
        ups = [d if d > 0 else 0 for d in diffs]
        downs = [abs(d) if d < 0 else 0 for d in diffs]
        avg_up = np.mean(ups)
        avg_down = np.mean(downs)
        if avg_down == 0: return 100
        rs = avg_up / avg_down
        return 100 - (100 / (1 + rs))

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
    from core.config import DATA_FILE
    import os
    if not os.path.exists(DATA_FILE): return []
    df = pd.read_csv(DATA_FILE)
    if '市場・商品区分' in df.columns:
        prime = df[df['市場・商品区分'].str.contains('プライム', na=False)]
        return [f"{str(code)}.T" for code in prime['コード']]
    return []

