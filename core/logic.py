import json
import pandas as pd
import numpy as np
from datetime import datetime as dt
from core.config import (
    ATR_STOP_LOSS, TARGET_PROFIT_MULT, JST, BREADTH_THRESHOLD,
    MAX_POSITIONS, MAX_ALLOCATION_PCT,
    MAX_ALLOCATION_AMOUNT, LIQUIDITY_LIMIT_RATE, MIN_ALLOCATION_AMOUNT,
    EXCLUSION_CACHE_FILE, SMA20_EXIT_BUFFER, MAX_HOLD_DAYS,
    SMA_SHORT_PERIOD, SMA_MEDIUM_PERIOD, SMA_LONG_PERIOD, SMA_TREND_PERIOD,
    BULL_GAP_LIMIT, RS_THRESHOLD,
    USE_COMPOUNDING, INITIAL_CASH
)

def calculate_position_stops(buy_price, buy_atr, max_price, current_price,
                             sl_mult, tp_mult):
    """
    V17.0 Golden Exit Calculator.
    - Trailing Stop based on max_price (NOT fixed at entry).
    - Fixed Take Profit based on Entry.
    - Simple, robust, trend-following capture.
    """
    # 損切り (Trailing Stop using max_price)
    # これにより、利益が乗るほど損切りラインが上がり、利益を保護します。
    tsl_price = max_price - (buy_atr * sl_mult)
    
    # 利確ターゲット (Fixed TP)
    target_price = buy_price + (buy_atr * tp_mult)
    
    return tsl_price, target_price

def manage_positions_live(portfolio, broker=None, is_simulation=True, realtime_buffers=None, sma_med_map=None):
    """
    V17.0 Golden Manager:
    - Fixed ATR TP/SL.
    - SMA20 Trend Breach protection.
    - Time-based Exit (MAX_HOLD_DAYS).
    """
    remaining = []
    sell_actions = []
    
    for p in portfolio:
        code = str(p['code'])
        # 1. Price Acquisition
        if realtime_buffers and code in realtime_buffers:
            current_price = realtime_buffers[code].get_latest_price()
        else:
            current_price = float(p.get('current_price', p['buy_price']))
            
        buy_price = float(p['buy_price'])
        atr = float(p.get('buy_atr', 0))
        highest_price = float(p.get('highest_price', 0))
        
        # 2. Shared Stop/Target Calculation
        tsl_price, target_price = calculate_position_stops(
            buy_price, atr, highest_price, current_price,
            ATR_STOP_LOSS, TARGET_PROFIT_MULT
        )

        # 3. Technical Trend Exit (SMA20)
        is_trend_broken = False
        if sma_med_map and code in sma_med_map:
            # Buffer for optimized endurance (Synced with config)
            if current_price < float(sma_med_map[code]) * SMA20_EXIT_BUFFER: 
                is_trend_broken = True

        # 4. Sell Decision
        exit_reason = None

        if current_price <= tsl_price:
            exit_reason = f"Stop Loss ({ATR_STOP_LOSS} ATR)"
        elif current_price >= target_price:
            exit_reason = f"Take Profit ({TARGET_PROFIT_MULT} ATR)"
        elif is_trend_broken:
            exit_reason = "Trend Breach (SMA20)"
            
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

def calculate_dynamic_leverage(breadth_val, config_leverage=1.5):
    """V17.0 Fixed Breadth Scaling: On if >= Threshold, else Off."""
    if breadth_val >= BREADTH_THRESHOLD:
        return config_leverage
    return 0.0

def check_entry_signal(regime, rsi2, price, open_p, sma_med, sma_trend=0):
    """
    V17.0 Golden Entry Logic.
    - Pure Momentum/Trend Follower.
    - High RS leaders in BULL regime.
    """
    if regime != "BULL": return False 
    
    # Selectionで上位RSに絞られているため、ここではregimeチェックのみで充分
    return True

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
    bundle[f'SMA{SMA_SHORT_PERIOD}'] = close.rolling(SMA_SHORT_PERIOD).mean()
    bundle[f'SMA{SMA_MEDIUM_PERIOD}'] = close.rolling(SMA_MEDIUM_PERIOD).mean()
    bundle[f'SMA{SMA_LONG_PERIOD}'] = close.rolling(SMA_LONG_PERIOD).mean()
    bundle[f'SMA{SMA_TREND_PERIOD}'] = close.rolling(SMA_TREND_PERIOD).mean()
    # Ensure specific SMAs for optimization
    for p in [50, 100, 200]:
        if f'SMA{p}' not in bundle:
            bundle[f'SMA{p}'] = close.rolling(p).mean()
    
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
    V168.0 Strict Market Regime Filter:
    - BULL: 価格が長期SMA200を上回り、かつ長期SMAが上昇傾向
    - BEAR: 価格が長期SMA200を下回っている（この間は全エントリー停止）
    """
    regime = "NEUTRAL"
    is_trend_snapped = False
    
    if data_df is not None:
        try:
            close_all = data_df.xs('Close', axis=1, level=1)
            if '1321.T' in close_all.columns:
                c_1321 = close_all['1321.T']
                sma_trend = c_1321.rolling(SMA_TREND_PERIOD).mean()
                sma_short = c_1321.rolling(SMA_SHORT_PERIOD).mean()
                
                curr_p = c_1321.iloc[-1]
                curr_sma_trend = sma_trend.iloc[-1]
                prev_sma_trend = sma_trend.iloc[-10] # 2 weeks ago
                slope = (curr_sma_trend / prev_sma_trend - 1.0) * 100
                
                # ベア判定を厳格化: SMA200を下回ったら即座にBEAR（ブロック）
                if curr_p < curr_sma_trend:
                    regime = "BEAR"
                elif slope > 0.01: # 緩やかな上昇トレンド
                    regime = "BULL"
                
                if curr_p < sma_short.iloc[-1]:
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
    prev_close = bundle['Close'].iloc[-2]  # 前日終値（ギャップ計算用）
    open_p = bundle['Open'].iloc[-1]
    rsi2 = bundle['RSI2'].iloc[-1]
    sma_med = bundle[f'SMA{SMA_MEDIUM_PERIOD}'].iloc[-1]
    sma_trend = bundle[f'SMA{SMA_TREND_PERIOD}'].iloc[-1]
    atr = bundle['ATR'].iloc[-1]
    rs_alpha = bundle['RS_Alpha'].iloc[-1]
    turnover = bundle['Turnover'].iloc[-1] if 'Turnover' in bundle else None
    
    candidates = []
    for t_with_t in [f"{t}.T" for t in targets]:
        if t_with_t not in close.index: continue
        
        p = close[t_with_t]
        o = open_p[t_with_t]
        r2 = rsi2[t_with_t]
        s_med = sma_med[t_with_t]
        s_trend = sma_trend[t_with_t]
        rs = rs_alpha[t_with_t]
        
        if pd.isna(p) or p <= 0 or pd.isna(rs): continue
        if rs < RS_THRESHOLD: continue # Momentum requirement

        # [V150.2 Gap Filter Parity] バックテストと同一ギャップフィルター
        p_prev = prev_close[t_with_t] if t_with_t in prev_close.index else None
        if p_prev is not None and not pd.isna(p_prev) and p_prev > 0:
            gap_pct = (o / p_prev - 1.0)
            if (regime == "BULL" and gap_pct < -0.02) or (abs(gap_pct) > BULL_GAP_LIMIT):
                continue

        entry_signal = check_entry_signal(regime, r2, p, o, s_med, s_trend)
                
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
                "adv_yen": turnover[t_with_t] if turnover is not None else 0,
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

def calculate_lot_size(current_equity, atr, sl_mult, price, dynamic_leverage, 
                       max_positions, buying_power=None, turnover=None):
    """
    V167.5 Imperial Sizing Logic (Simple Equity Allocation)
    1. 資産ベースの決定（複利 vs 単利）
    2. 1銘柄あたりの割当資金の計算 (Target Allocation)
    3. 割当額を価格で割り、100株単位に切り捨てる
    4. 購買力および流動性による安全制約
    """
    # 資産ベースの決定（複利 = 現在資産, 単利 = 初期資金）
    base_equity = current_equity if USE_COMPOUNDING else INITIAL_CASH
    
    # 1銘柄あたりの割当資金 = (資産 * レバレッジ) / 最大ポジション数
    # これにより、常に資金を最大数で等分して運用する
    target_allocation = (base_equity * dynamic_leverage) / max_positions
    
    # 流動性制約 (直近出来高等の 2.5% を上限とする)
    if turnover and turnover > 0:
        target_allocation = min(target_allocation, turnover * LIQUIDITY_LIMIT_RATE)
    
    # 割当額に基づく株数
    shares_alloc = int(target_allocation // price)
    
    # 全体購買力による制約 (実際の注文可能額を超えないようにする)
    shares_bp = 1e9
    if buying_power is not None:
        shares_bp = int((buying_power * 0.98) // price) # 余裕を持って 98%
        
    # 最小値の採用と100株単位への丸め (単元株制度への適合)
    final_shares = min(shares_alloc, shares_bp)
    final_shares = (final_shares // 100) * 100
    
    return max(final_shares, 0)

