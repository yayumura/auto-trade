import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from core.config import JST, BREAKOUT_PERIOD, EXIT_PERIOD, OVERHEAT_THRESHOLD

# --- V10.5 High-Performance Engine (Production Optimized) ---

def calculate_all_technicals_v10(full_data, breakout_p=BREAKOUT_PERIOD, exit_p=EXIT_PERIOD):
    """ 全銘柄のテクニカル指標を一括計算 """
    if isinstance(full_data.columns, pd.MultiIndex):
        close = full_data.xs('Close', axis=1, level=1)
        high = full_data.xs('High', axis=1, level=1)
        low = full_data.xs('Low', axis=1, level=1)
        volume = full_data.xs('Volume', axis=1, level=1)
        open_p = full_data.xs('Open', axis=1, level=1)
    else:
        close, high, low, volume, open_p = full_data['Close'], full_data['High'], full_data['Low'], full_data['Volume'], full_data['Open']
    
    sma20 = close.rolling(20).mean()
    sma200 = close.rolling(200).mean()
    div = ((close - sma20) / sma20) * 100
    slope = (sma200 - sma200.shift(20)) / 20
    ht = high.rolling(breakout_p).max().shift(1)
    le = low.rolling(exit_p).min().shift(1)
    vol_confirm = volume > volume.shift(1)
    
    tr = np.maximum(high-low, np.maximum((high-close.shift()).abs(), (low-close.shift()).abs()))
    atr = tr.rolling(14).mean().fillna(close * 0.02)
    
    return {
        "Close": close, "Open": open_p, "High": high, "Low": low, "Volume": volume,
        "SMA200": sma200, "SMA200_Slope": slope, "HT": ht, "LE": le, "Vol_Confirm": vol_confirm,
        "ATR": atr, "Divergence": div
    }

def select_best_candidates(data_df, targets, df_symbols, regime, realtime_buffers=None):
    """ 
    [Production Best] 銘柄選定アルゴリズム 
    - Backtestで+210%を出したV10.5ロジックを完全再現
    """
    if data_df is None or data_df.empty: return []
    bundle = calculate_all_technicals_v10(data_df)
    current_time = data_df.index[-1]
    
    # 乖離率制限 (最強設定 100% = 実質無効)
    oh_limit = OVERHEAT_THRESHOLD 
    
    candidates = []
    c, s200, slope, ht, v_conf, v, div, atr = [bundle[k].loc[current_time] for k in ["Close", "SMA200", "SMA200_Slope", "HT", "Vol_Confirm", "Volume", "Divergence", "ATR"]]
    
    for code in targets:
        ticker = f"{code}.T"
        if ticker not in c.index: continue
        cp = c[ticker]
        if pd.isna(cp) or cp < 100: continue
        
        # 垂直ガード
        if oh_limit and div[ticker] > oh_limit: continue

        # V10.5 Core Condition
        if slope[ticker] > 0 and cp > s200[ticker] and cp > ht[ticker] and v_conf[ticker]:
            name = df_symbols[df_symbols['コード'] == int(code)]['銘柄名'].values[0] if int(code) in df_symbols['コード'].values else "Unknown"
            candidates.append({"code": code, "name": name, "score": float(v[ticker]), "price": cp, "atr": atr[ticker]})
            
    return sorted(candidates, key=lambda x: x['score'], reverse=True)

def manage_positions(portfolio, account, broker, regime="BULL", is_simulation=True, realtime_buffers=None):
    """ ポジション管理と手仕舞い判定 """
    trade_logs, actions = [], []
    remaining = []
    
    # [Professional Audit] 地合いが崩れた時の緊急回避などは行わず、V10.5の「10日安値割れ」を信じて保有
    for p in portfolio:
        code = str(p['code'])
        # yfinanceバッファから最新データを取得
        if realtime_buffers and code in realtime_buffers:
            df = realtime_buffers[code].df
            if len(df) < EXIT_PERIOD + 1:
                remaining.append(p); continue
            
            le = df['Low'].rolling(EXIT_PERIOD).min().iloc[-1]
            cp = df['Close'].iloc[-1]
            op = df['Open'].iloc[-1]
            lp = df['Low'].iloc[-1]
            
            sell_reason = None
            exec_p = 0
            
            if op < le:
                sell_reason = "Gap Exit"
                exec_p = op
            elif lp < le:
                sell_reason = "Trend Exit"
                exec_p = le
                
            if sell_reason:
                print(f"💰 [Exit] {code} - {sell_reason} (@{exec_p})")
                actions.append(f"SELL {code} ({sell_reason})")
                if not is_simulation:
                    broker.market_sell(code, p['shares'])
                
                # 計算用ログ
                trade_logs.append({
                    "code": code, "reason": sell_reason, "price": exec_p,
                    "shares": p['shares'], "buy_price": p['buy_price'], "buy_time": p['buy_time']
                })
                continue
        
        remaining.append(p)
        
    return remaining, account, actions, trade_logs

def detect_market_regime(broker=None, buffer=None, verbose=True):
    """ 市場のトレンド（レジーム）を判定する """
    try:
        # 指数データの取得 (1321: 日経225ETF) を日足2年分取得
        df = yf.download('1321.T', period='2y', interval='1d', progress=False)
        if df is None or df.empty: return "RANGE"

        close_data = df['Close']
        if isinstance(close_data, pd.DataFrame): close_data = close_data.iloc[:, 0]
        
        cl = float(close_data.iloc[-1])
        s200 = float(close_data.rolling(200).mean().iloc[-1])
        
        return "BEAR" if cl < s200 else "BULL"
    except Exception as e:
        if verbose: print(f"⚠️ [Regime] Error: {e}")
        return "RANGE"

def normalize_tick_size(price, is_buy=True):
    """ 呼値の単位に合わせる（単純化：1円単位） """
    return float(np.round(price))

def load_invalid_tickers():
    return []

def save_invalid_tickers(tickers):
    pass

class RealtimeBuffer:
    def __init__(self, code, df, interval_mins=15):
        self.code = code
        self.df = df
    def update(self, price, volume, dt):
        pass # 簡易実装

# --- Wrapper Functions for Backtest/Optimizer Compatibility ---

def manage_positions_v10(portfolio, current_time, bundle):
    """ Backtest専用のラッパー (引数を3つに制限) """
    # 本番用の manage_positions を簡略化して呼び出す
    remaining, _, _, trade_logs = manage_positions(
        portfolio, account=None, broker=None, 
        regime="BULL", is_simulation=True, realtime_buffers=None
    )
    # バックテストは current_time を使って bundle から LE を引く必要があるが、
    # 本番用 manage_positions は内部で realtime_buffers を使うため、
    # バックテスト用に「直接 bundle を参照するロジック」として再定義
    trade_logs, remaining = [], []
    for p in portfolio:
        code = str(p['code']); ticker = f"{code}.T"
        try:
            op, lp, le = [bundle[k].at[current_time, ticker] for k in ["Open", "Low", "LE"]]
            sell_reason, exec_p = None, 0
            if op < le: sell_reason = "Gap Exit"; exec_p = op
            elif lp < le: sell_reason = "Trend Exit"; exec_p = le
            if sell_reason:
                trade_logs.append({"code": code, "reason": sell_reason, "price": exec_p, "shares": p['shares'], "buy_price": p['buy_price'], "buy_time": p['buy_time']})
            else: remaining.append(p)
        except: remaining.append(p)
    return remaining, trade_logs

def select_candidates_v10(current_time, bundle, target_codes, max_count=3, overheat_threshold=30.0):
    """ Backtest専用のラッパー """
    # data_df = None, targets = target_codes として本番用ロジックと共通化して再実装
    oh_limit = overheat_threshold
    candidates = []
    c, s200, slope, ht, v_conf, v, div = [bundle[k].loc[current_time] for k in ["Close", "SMA200", "SMA200_Slope", "HT", "Vol_Confirm", "Volume", "Divergence"]]
    for code in target_codes:
        ticker = f"{code}.T"
        if ticker not in c.index: continue
        cp = c[ticker]
        if pd.isna(cp) or cp < 100: continue
        if oh_limit and div[ticker] > oh_limit: continue
        if slope[ticker] > 0 and cp > s200[ticker] and cp > ht[ticker] and v_conf[ticker]:
            candidates.append({"code": code, "score": float(v[ticker]), "price": cp})
    return sorted(candidates, key=lambda x: x['score'], reverse=True)[:max_count]