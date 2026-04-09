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

def manage_positions_live(portfolio, account, broker=None, regime="BULL", is_simulation=True, realtime_buffers=None, today_ohlc=None, sma20_map=None, month_drawdown=0.0, is_trend_snapped=False):
    """
    V131.1 Aegis Sovereign Position Manager:
    - Dynamic Risk Shield: Adjusts ATR multiplier based on monthly performance.
    - RSI Profit Take: Exits when mean reversion is complete.
    """
    remaining = []
    sell_actions = []
    
    # --- Aegis Sovereign Protocol Sync ---
    atr_shield_mult = calculate_aegis_shield(month_drawdown, regime)
    exit_threshold = get_exit_thresholds(regime, is_trend_snapped)

    for p in portfolio:
        code = str(p['code'])
        # 1. 価格取得
        if realtime_buffers and code in realtime_buffers:
            current_price = realtime_buffers[code].get_latest_price()
            # RSI2 is needed for exit
            rsi2 = realtime_buffers[code].get_current_rsi2() if hasattr(realtime_buffers[code], 'get_current_rsi2') else 50
        else:
            current_price = float(p.get('current_price', p['buy_price']))
            rsi2 = 50 # Fallback
            
        buy_price = float(p['buy_price'])
        atr = float(p.get('buy_atr', 0))
        highest_price = float(p.get('highest_price', 0))
        
        # 2. 逆指値 (Stop Loss) 計算: Dynamic Trailing Stop
        # Use ATR_STOP_LOSS from config, but scaled by Aegis Shield
        current_sl_dist = ATR_STOP_LOSS * atr * atr_shield_mult
        initial_stop = buy_price - current_sl_dist
        
        # [V18.1] Break-even Stop (5.0 ATR Profit Protection)
        if highest_price >= buy_price + (atr * 5.0):
            initial_stop = max(initial_stop, buy_price * 1.002)
            
        if ATR_TRAIL and highest_price > 0:
            stop_price = max(initial_stop, highest_price - current_sl_dist)
        else:
            stop_price = initial_stop
            
        # 3. タイムリミット (Aegis Standard: 30日強制決済)
        is_timeout = False
        buy_time_str = p.get('buy_time')
        if buy_time_str:
            try:
                buy_dt = dt.strptime(buy_time_str, '%Y-%m-%d %H:%M:%S')
                days_held = (dt.now().replace(tzinfo=None) - buy_dt.replace(tzinfo=None)).days
                if days_held >= 30: # [V132] Optimized from 60 to 30
                    is_timeout = True
            except: pass
        
        # 4. Technical Exit: SMA20割れ判定 (Optional, secondary to RSI)
        is_sma_breach = False
        if EXIT_ON_SMA20_BREACH and sma20_map and code in sma20_map:
            if current_price < float(sma20_map[code]) * SMA20_EXIT_BUFFER:
                is_sma_breach = True

        # 5. 売却判定
        exit_reason = None
        if current_price <= stop_price:
            exit_reason = "Stop Loss (Aegis Shield)" if stop_price < buy_price else "Break-even Stop"
        elif rsi2 > exit_threshold:
            exit_reason = f"RSI Profit Target ({rsi2:.1f} > {exit_threshold})"
        elif month_drawdown <= -0.12:
            exit_reason = "Aegis Critical Safeguard (Month Done)"
        elif is_timeout:
            exit_reason = "Time Limit Reached (30 Days)"
        elif is_sma_breach:
            exit_reason = "SMA20 Breach (Technical Exit)"

        if exit_reason:
            sell_actions.append(f"SELL {code} - {exit_reason} (@{current_price:,.1f})")
            if not is_simulation and broker:
                try: broker.execute_chase_order(code, p['shares'], side="1")
                except: pass
            continue
            
        # 建玉情報の更新
        p['current_price'] = round(current_price, 1)
        if current_price > float(p.get('highest_price', 0)):
            p['highest_price'] = round(current_price, 1)
            
        remaining.append(p)

    return remaining, sell_actions

# --- Common Decision Core (Parity Logic) ---

def calculate_aegis_shield(month_drawdown, regime="BULL"):
    """V132.0 Shared Risk Scaling Logic"""
    atr_shield_mult = 1.0
    if month_drawdown <= -0.05: atr_shield_mult = 0.66
    if month_drawdown <= -0.10: atr_shield_mult = 0.33
    if regime != "BULL": atr_shield_mult = 0.8 # [V131.1 Sync]
    return atr_shield_mult

def get_exit_thresholds(regime, is_trend_snapped):
    """V132.0 Shared RSI Exit Thresholds"""
    exit_threshold = 85 if not is_trend_snapped else 55
    if regime != "BULL": exit_threshold = 60
    return exit_threshold

def calculate_dynamic_leverage(breadth_val, config_leverage=2.5):
    """V132.0 Shared Leverage Scaling"""
    if breadth_val >= 0.50: dynamic_lev = 3.0
    elif breadth_val >= 0.40: dynamic_lev = 2.0
    elif breadth_val >= 0.30: dynamic_lev = 1.0
    else: dynamic_lev = 0.0
    return min(dynamic_lev, config_leverage) if dynamic_lev > 0 else 0

def check_entry_signal(regime, rsi2, price, open_p, sma50):
    """V132.0 Shared Entry Signal Logic"""
    rsi_limit = 12.0
    if regime == "BULL": rsi_limit = 30.0
    if regime == "BEAR": rsi_limit = 8.0
    
    if regime == "BULL":
        # Bullish Mean Reversion: Oversold but above long-term trend
        if rsi2 < rsi_limit and price > sma50 and price > open_p:
            return True
    else:
        # Neutral/Bear Reversion: Deeper oversold, rebound confirmation
        if rsi2 < rsi_limit and price > open_p:
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
    V131.1 Aegis Sovereign Selection:
    - Filters by RSI2 (Mean Reversion)
    - Sorts by RS_Alpha (Relative Strength Leaders)
    """
    bundle = calculate_all_technicals_v12(data_df)
    
    close = bundle['Close'].iloc[-1]
    open_p = bundle['Open'].iloc[-1]
    rsi2 = bundle['RSI2'].iloc[-1]
    sma50 = bundle['SMA50'].iloc[-1]
    atr = bundle['ATR'].iloc[-1]
    rs_alpha = bundle['RS_Alpha'].iloc[-1]
    
    # Entry thresholds based on regime
    rsi_limit = 12.0
    if regime == "BULL": rsi_limit = 30.0
    if regime == "BEAR": rsi_limit = 8.0
    
    candidates = []
    for t_with_t in [f"{t}.T" for t in targets]:
        if t_with_t not in close.index: continue
        
        p = close[t_with_t]
        o = open_p[t_with_t]
        r2 = rsi2[t_with_t]
        s50 = sma50[t_with_t]
        rs = rs_alpha[t_with_t]
        
        if pd.isna(p) or p <= 0 or pd.isna(r2): continue
        
        entry_signal = check_entry_signal(regime, r2, p, o, s50)
                
        # Inverse ETF Safeguard (If 1357.T is in targets and it's a BEAR market)
        if "1357" in t_with_t and regime == "BEAR" and r2 > 70:
            entry_signal = True

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
                "score": rs # High RS leaders preferred
            })

    # Sort by RS_Alpha descending
    candidates = sorted(candidates, key=lambda x: x['rs'], reverse=True)
    return candidates # Return all, not just top 10, for better backtest coverage

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

