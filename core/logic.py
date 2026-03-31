import pandas as pd
import numpy as np
import os
import json
from datetime import datetime
import yfinance as yf
from core.config import EXCLUSION_CACHE_FILE, JST

# ==========================================
# V10.7 真・聖杯復元エンジン (The Restoration)
# コミット 740f63 の +200% ロジックを完全再現
# ==========================================

# --- 補助関数 (Production用) ---
def load_invalid_tickers():
    if os.path.exists(EXCLUSION_CACHE_FILE):
        try:
            with open(EXCLUSION_CACHE_FILE, 'r') as f: return set(json.load(f))
        except: pass
    return set()

def save_invalid_tickers(invalid_set):
    try:
        with open(EXCLUSION_CACHE_FILE, 'w') as f: json.dump(list(invalid_set), f)
    except: pass

def normalize_tick_size(price: float, is_buy: bool) -> int:
    p = float(price)
    tick = 1.0 if p <= 3000 else 5.0 if p <= 5000 else 10.0 if p <= 10000 else 50.0
    return int((p + tick - 0.0001) // tick * tick) if is_buy else int(p // tick * tick)

class RealtimeBuffer:
    def __init__(self, code, history_df, interval_mins=15):
        self.code = code
        self.df = history_df.copy() if not history_df.empty else pd.DataFrame()
        self.interval = interval_mins
    def update(self, price, total_volume, timestamp, current_time_override=None):
        if price is None or price <= 0 or self.df.empty: return
        last_idx = self.df.index[-1]
        self.df.at[last_idx, 'Close'] = price
        if total_volume > 0: self.df.at[last_idx, 'Volume'] = total_volume

# --- 地合いレジーム判定 ---
def detect_market_regime(broker=None, buffer=None, current_time_override=None, verbose=True):
    try:
        if buffer and not buffer.df.empty:
            df = buffer.df
        else:
            if broker is None: return "BULL" # バックテスト時はフィルタ無効
            df = yf.download('1321.T', period='1y', interval='1d', progress=False)
        if df.empty: return "BULL"
        cl = df['Close'].iloc[-1]
        s200 = df['Close'].rolling(200).mean().iloc[-1]
        if cl < s200:
            if verbose: print(f"  [Regime] 🚨 市場弱気 (NK < SMA200) -> 制限中")
            return "BEAR"
        return "BULL"
    except: return "RANGE"

# --- 1. 【核心】テクニカル計算 (740f63 完全再現) ---
def calculate_all_technicals_v10(full_data, breakout_p=25, exit_p=10):
    if full_data is None or full_data.empty: return None
    
    if isinstance(full_data.columns, pd.MultiIndex):
        close = full_data.xs('Close', axis=1, level=1)
        high = full_data.xs('High', axis=1, level=1)
        low = full_data.xs('Low', axis=1, level=1)
        volume = full_data.xs('Volume', axis=1, level=1)
        open_p = full_data.xs('Open', axis=1, level=1)
    else:
        close, high, low, volume, open_p = full_data['Close'], full_data['High'], full_data['Low'], full_data['Volume'], full_data['Open']
    
    sma200 = close.rolling(200).mean()
    sma200_slope = (sma200 - sma200.shift(20)) / 20
    ht = high.rolling(breakout_p).max().shift(1)
    le = low.rolling(exit_p).min().shift(1)
    vol_confirm = volume > volume.shift(1)
    
    tr1, tr2, tr3 = high-low, (high-close.shift()).abs(), (low-close.shift()).abs()
    tr = np.maximum(tr1, np.maximum(tr2, tr3))
    atr = tr.rolling(14).mean().fillna(close * 0.02).clip(lower=1.0)
    
    return {
        "Close": close, "Open": open_p, "High": high, "Low": low, "Volume": volume,
        "SMA200": sma200, "SMA200_Slope": sma200_slope,
        "HT": ht, "LE": le, "Vol_Confirm": vol_confirm, "ATR": atr
    }

# --- 2. 【核心】スキャンエンジン (740f63 完全再現) ---
def select_candidates_v10(current_time, bundle, target_codes, max_count=3):
    candidates = []
    c, s200, slope, ht, v_conf, v, atr = [bundle[k].loc[current_time] for k in ["Close", "SMA200", "SMA200_Slope", "HT", "Vol_Confirm", "Volume", "ATR"]]
    
    for code in target_codes:
        ticker = f"{code}.T"
        if ticker not in c.index: continue
        cp = c[ticker]
        if pd.isna(cp) or cp < 100: continue
        
        # 伝説の4重フィルタ
        if slope[ticker] > 0 and cp > s200[ticker] and cp > ht[ticker] and v_conf[ticker]:
            candidates.append({"code": code, "score": v[ticker], "price": cp, "atr": atr[ticker]})
            
    return sorted(candidates, key=lambda x: x['score'], reverse=True)[:max_count]

# --- 3. 【核心】ポジション管理 (740f63 完全再現) ---
def manage_positions_v10(portfolio, current_time, bundle, stop_mult=3.0):
    trade_logs, remaining = [], []
    for p in portfolio:
        if p.get('pending_buy'): remaining.append(p); continue
        ticker = f"{p['code']}.T"
        try:
            op, lp, le, atr = [bundle[k].at[current_time, ticker] for k in ["Open", "Low", "LE", "ATR"]]
            buy_p = p['buy_price']
            stop_p = buy_p - (p['atr'] * stop_mult)
            
            sell_reason = None
            if op <= stop_p: sell_reason = "Final Stop (Gap)"; exec_p = op
            elif lp <= stop_p: sell_reason = "Final Stop"; exec_p = stop_p
            elif lp < le: sell_reason = "Final Exit"; exec_p = le
            
            if sell_reason:
                trade_logs.append({
                    "code": p['code'], "reason": sell_reason, "price": exec_p, 
                    "shares": p['shares'], "buy_price": buy_p, "buy_time": p['buy_time'], "atr": p['atr']
                })
            else: remaining.append(p)
        except: remaining.append(p)
    return remaining, trade_logs

# --- auto_trade.py 用エイリアス ---
def select_best_candidates(data_df, targets, df_symbols=None, regime="RANGE", realtime_buffers=None, verbose=True):
    if regime == "BEAR": return []
    bundle = calculate_all_technicals_v10(data_df)
    if not bundle: return []
    res = select_candidates_v10(data_df.index[-1], bundle, targets, max_count=5)
    # 本番用に関数内情報の付加が必要ならここで変換
    for r in res:
        if df_symbols is not None:
            r['name'] = df_symbols[df_symbols['コード'].astype(str) == str(r['code'])]['銘柄名'].values[0]
        else: r['name'] = str(r['code'])
        r['reason'] = "Standard Breakout"
    return res

def manage_positions(portfolio, account, broker, regime="RANGE", is_simulation=True, realtime_buffers=None):
    """本番運用用の鉄壁ポジション管理 (V10.7復元版)"""
    trade_logs, remaining, actions = [], [], []
    stop_mult = 3.0 # 設定値
    
    for p in portfolio:
        if p.get('pending_buy'): remaining.append(p); continue
        code = str(p['code'])
        
        try:
            # リアルタイムバッファから最新状態を取得
            buffer = realtime_buffers.get(code) if realtime_buffers else None
            # バッファがない場合は yfinance 等で補完する想定（基本はあるはず）
            if buffer and not buffer.df.empty:
                df_tech = calculate_all_technicals_v10(buffer.df, breakout_p=20, exit_p=10)
                latest = df_tech["Close"].index[-1]
                op, lp, le, atr = df_tech["Open"].iloc[-1], df_tech["Low"].iloc[-1], df_tech["LE"].iloc[-1], df_tech["ATR"].iloc[-1]
                cp = df_tech["Close"].iloc[-1] 
            else:
                # バッファがない場合の緊急措置 (現状維持)
                remaining.append(p); continue
                
            buy_p = p['buy_price']
            stop_p = buy_p - (p['atr'] * stop_mult)
            
            sell_reason = None
            exec_p = cp
            
            # +200% ロジックの3段階エグジット
            if op <= stop_p: sell_reason = "Final Stop (Gap)"; exec_p = op
            elif lp <= stop_p: sell_reason = "Final Stop"; exec_p = stop_p
            elif lp < le: sell_reason = "Final Exit (LowBreak)"; exec_p = le
            
            if sell_reason:
                print(f"  [EXEC] {code} SELL: {sell_reason} at {exec_p:.1f}")
                actions.append({"code": code, "type": "SELL", "price": exec_p, "shares": p['shares'], "reason": sell_reason})
                trade_logs.append({
                    "code": code, "profit": (exec_p - buy_p) * p['shares'], "reason": sell_reason
                })
            else:
                remaining.append(p)
        except Exception as e:
            print(f"  [Error] manage_positions ({code}): {e}")
            remaining.append(p)
            
    return remaining, account, actions, trade_logs