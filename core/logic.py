import pandas as pd
import numpy as np
import os
import json
from datetime import datetime
import yfinance as yf
from core.config import EXCLUSION_CACHE_FILE, JST, BREAKOUT_PERIOD, EXIT_PERIOD

# ==========================================
# V10.7.1 FINAL PRODUCTION (The Golden Path)
# 迷いを断ち切り、検証済みの最強アルゴリズムへ
# ==========================================

def normalize_tick_size(price: float, is_buy: bool) -> int:
    p = float(price)
    tick = 1.0 if p <= 3000 else 5.0 if p <= 5000 else 10.0 if p <= 10000 else 50.0
    return int((p + tick - 0.0001) // tick * tick) if is_buy else int(p // tick * tick)

def load_invalid_tickers():
    if os.path.exists(EXCLUSION_CACHE_FILE):
        try:
            with open(EXCLUSION_CACHE_FILE, 'r') as f:
                return set(json.load(f))
        except: return set()
    return set()

def save_invalid_tickers(invalid_tickers):
    try:
        with open(EXCLUSION_CACHE_FILE, 'w') as f:
            json.dump(list(invalid_tickers), f)
    except: pass

class RealtimeBuffer:
    def __init__(self, code, history_df, interval_mins=15):
        self.code = code
        self.df = history_df.copy() if not history_df.empty else pd.DataFrame()
    def update(self, price, total_volume, timestamp, current_time_override=None):
        if price is None or price <= 0 or self.df.empty: return
        last_idx = self.df.index[-1]
        self.df.at[last_idx, 'Close'] = price
        if total_volume > 0: self.df.at[last_idx, 'Volume'] = total_volume

def detect_market_regime(broker=None, buffer=None, current_time_override=None, verbose=True):
    try:
        if buffer and not buffer.df.empty:
            df = buffer.df
        else:
            if broker is None: return "BULL"
            # 指数データの取得 (1321: 日経225ETF)
            df = yf.download('1321.T', period='2y', interval='1d', progress=False)
            
        if df is None or df.empty:
            if verbose: print("⚠️ [Regime] Index data could not be acquired. Defaulting to RANGE.")
            return "RANGE"

        # yfinanceのデータ形式(MultiIndex等)に依存せず、'Close'列の最後の値を取り出す
        if 'Close' in df.columns:
            # MultiIndex (Ticker, Column) のケースを考慮
            close_data = df['Close']
            if isinstance(close_data, pd.DataFrame):
                close_data = close_data.iloc[:, 0]
            
            if len(close_data) < 200:
                if verbose: print(f"⚠️ [Regime] Data volume is insufficient ({len(close_data)}). Defaulting to RANGE.")
                return "RANGE"

            cl = float(close_data.iloc[-1])
            s200 = float(close_data.rolling(200).mean().iloc[-1])
            
            if pd.isna(s200):
                if verbose: print("⚠️ [Regime] SMA200 calculation resulted in NaN. Defaulting to RANGE.")
                return "RANGE"
                
            return "BEAR" if cl < s200 else "BULL"
        else:
            if verbose: print("⚠️ [Regime] 'Close' column not found in data.")
            return "RANGE"
    except Exception as e:
        if verbose: print(f"⚠️ [Regime] Error occurred: {e}. Defaulting to RANGE.")
        return "RANGE"

def calculate_all_technicals_v10(full_data, breakout_p=BREAKOUT_PERIOD, exit_p=EXIT_PERIOD):
    if full_data is None or full_data.empty: return None
    if isinstance(full_data.columns, pd.MultiIndex):
        close, high, low, volume, open_p = full_data.xs('Close', axis=1, level=1), full_data.xs('High', axis=1, level=1), full_data.xs('Low', axis=1, level=1), full_data.xs('Volume', axis=1, level=1), full_data.xs('Open', axis=1, level=1)
    else:
        close, high, low, volume, open_p = full_data['Close'], full_data['High'], full_data['Low'], full_data['Volume'], full_data['Open']
    
    sma200 = close.rolling(200).mean()
    slope = (sma200 - sma200.shift(20)) / 20
    ht, le = high.rolling(breakout_p).max().shift(1), low.rolling(exit_p).min().shift(1)
    vol_confirm = volume > volume.shift(1)
    tr = np.maximum(high-low, np.maximum((high-close.shift()).abs(), (low-close.shift()).abs()))
    atr = tr.rolling(14).mean().fillna(close * 0.02).clip(lower=1.0)
    
    return {
        "Close": close, "Open": open_p, "High": high, "Low": low, "Volume": volume,
        "SMA200": sma200, "SMA200_Slope": slope, "HT": ht, "LE": le, "Vol_Confirm": vol_confirm, "ATR": atr
    }

def select_candidates_v10(current_time, bundle, target_codes, max_count=3):
    candidates = []
    c, s200, slope, ht, v_conf, v, atr = [bundle[k].loc[current_time] for k in ["Close", "SMA200", "SMA200_Slope", "HT", "Vol_Confirm", "Volume", "ATR"]]
    for code in target_codes:
        ticker = f"{code}.T"
        if ticker not in c.index: continue
        cp = c[ticker]
        if pd.isna(cp) or cp < 100: continue
        
        # 最強の4重フィルタ (200日線上、傾きプラス、高値ブレイク、出来高増加)
        if slope[ticker] > 0 and cp > s200[ticker] and cp > ht[ticker] and v_conf[ticker]:
            candidates.append({"code": code, "score": float(v[ticker]), "price": cp, "atr": atr[ticker]})
    return sorted(candidates, key=lambda x: x['score'], reverse=True)[:max_count]

def manage_positions_v10(portfolio, current_time, bundle, stop_mult=3.0):
    trade_logs, remaining = [], []
    for p in portfolio:
        if p.get('pending_buy'): remaining.append(p); continue
        code = str(p['code']); ticker = f"{code}.T"
        try:
            op, lp, le, atr = [bundle[k].at[current_time, ticker] for k in ["Open", "Low", "LE", "ATR"]]
            bp, stop_p = p['buy_price'], p['buy_price'] - (p['atr'] * stop_mult)
            sell_reason, exec_p = None, 0
            if op <= stop_p: sell_reason = "Final Stop (Gap)"; exec_p = op
            elif lp <= stop_p: sell_reason = "Final Stop"; exec_p = stop_p
            elif lp < le: sell_reason = "Final Exit"; exec_p = le
            if sell_reason:
                trade_logs.append({"code": code, "reason": sell_reason, "price": exec_p, "shares": p['shares'], "buy_price": bp, "buy_time": p['buy_time'], "atr": p['atr']})
            else: remaining.append(p)
        except: remaining.append(p)
    return remaining, trade_logs

def select_best_candidates(data_df, targets, df_symbols=None, regime="RANGE", realtime_buffers=None, verbose=True):
    if regime == "BEAR": return []
    bundle = calculate_all_technicals_v10(data_df)
    if not bundle: return []
    res = select_candidates_v10(data_df.index[-1], bundle, targets, max_count=5)
    for r in res:
        r['name'] = df_symbols[df_symbols['コード'].astype(str) == str(r['code'])]['銘柄名'].values[0] if df_symbols is not None else str(r['code'])
        r['reason'] = "Standard Breakout"
    return res

def manage_positions(portfolio, account, broker, regime="RANGE", is_simulation=True, realtime_buffers=None):
    trade_logs, remaining, actions = [], [], []
    for p in portfolio:
        if p.get('pending_buy'): remaining.append(p); continue
        code = str(p['code'])
        try:
            buffer = realtime_buffers.get(code)
            if buffer and not buffer.df.empty:
                df_tech = calculate_all_technicals_v10(buffer.df, breakout_p=BREAKOUT_PERIOD, exit_p=EXIT_PERIOD)
                op, lp, le, atr = df_tech["Open"].iloc[-1], df_tech["Low"].iloc[-1], df_tech["LE"].iloc[-1], df_tech["ATR"].iloc[-1]
                bp, stop_p = p['buy_price'], p['buy_price'] - (p['atr'] * 3.0)
                sell_reason, exec_p = None, df_tech["Close"].iloc[-1]
                if op <= stop_p: sell_reason = "Final Stop (Gap)"; exec_p = op
                elif lp <= stop_p: sell_reason = "Final Stop"; exec_p = stop_p
                elif lp < le: sell_reason = "Final Exit"; exec_p = le
                if sell_reason:
                    actions.append({"code": code, "type": "SELL", "price": exec_p, "shares": p['shares'], "reason": sell_reason})
                    # 現金残高を更新 (シミュレーションおよび検証モード用)
                    gross = exec_p * p['shares']
                    profit = (exec_p - bp) * p['shares']
                    # 簡易的な税金計算 (利益の20.315%)
                    tax = max(0, int(profit * 0.20315)) if profit > 0 else 0
                    account['cash'] += (gross - tax)
                    
                    trade_logs.append({"code": code, "profit": profit - tax, "reason": sell_reason})
                else: remaining.append(p)
            else: remaining.append(p)
        except: remaining.append(p)
    return remaining, account, actions, trade_logs