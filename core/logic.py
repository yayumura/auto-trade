import pandas as pd
import numpy as np
import time
import os
import json
import datetime
from datetime import datetime as dt
from .config import BREAKOUT_PERIOD, MAX_POSITIONS, JST, TARGET_PROFIT, STOP_LOSS_RATE, EXIT_PERIOD, MIN_PRICE, MAX_PRICE

# ==========================================
# 1. V12.0 Growth Monster Logic (Backtest & Live)
# ==========================================

def calculate_all_technicals_v12(full_data, breakout_p=5):
    """
    V12.0 高頻度・爆発力重視のテクニカル計算
    """
    if full_data is None or full_data.empty: return None
    close, high, low, volume, open_p = [full_data.xs(k, axis=1, level=1) for k in ["Close", "High", "Low", "Volume", "Open"]]
    
    # トレンド判定 (短期・中期)
    sma20 = close.rolling(20).mean()
    sma20_vol = volume.rolling(20).mean()
    
    # 勢い判定 (Ret3: 3日間の騰落率)
    ret3 = (close / close.shift(3) - 1) * 100
    
    # ブレイクアウト判定 (直近高値)
    ht = high.rolling(breakout_p).max().shift(1)
    
    # ATR (ボラティリティ)
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = np.maximum(np.maximum(tr1, tr2), tr3)
    atr = tr.rolling(14).mean()

    return {
        "Close": close, "High": high, "Low": low, "Volume": volume, "Open": open_p,
        "SMA20": sma20, "SMA20_Vol": sma20_vol, "Ret3": ret3, "HT": ht, "ATR": atr,
        "SMA200": close.rolling(200).mean() # For Regime check
    }

def manage_positions_v12(portfolio, current_time, bundle, tp=TARGET_PROFIT, sl=STOP_LOSS_RATE, time_limit=EXIT_PERIOD):
    """
    V12.0 高頻度利確・損切りロジック
    """
    trade_logs, remaining = [], []
    for p in portfolio:
        code = str(p['code']); ticker = f"{code}.T"
        try:
            # データの取得
            row_high = bundle["High"].at[current_time, ticker]
            row_low = bundle["Low"].at[current_time, ticker]
            row_close = bundle["Close"].at[current_time, ticker]
            
            if 'held_days' not in p: p['held_days'] = 0
            p['held_days'] += 1

            exit_p = 0; reason = None; timing = "immediate"
            
            # --- エグジット判定 ---
            # 1. 利確 (当日高値が指値に到達)
            if row_high >= p['buy_price'] * (1.0 + tp):
                reason = "Target Profit"; exit_p = p['buy_price'] * (1.0 + tp)
            # 2. 損切り (当日安値が損切りラインに到達)
            elif row_low <= p['buy_price'] * (1.0 - sl):
                reason = "Stop Loss"; exit_p = p['buy_price'] * (1.0 - sl)
            # 3. タイムアップ (数日経っても伸びない) -> 翌朝の寄付きで売る
            elif p['held_days'] >= time_limit:
                reason = "Time Limit"; exit_p = row_close; timing = "next_open"
            
            if reason:
                trade_logs.append({
                    "code": code, "reason": reason, "price": exit_p, 
                    "shares": p['shares'], "buy_price": p['buy_price'], "buy_time": p.get('buy_time', str(current_time)),
                    "timing": timing 
                })
            else:
                remaining.append(p)
        except: remaining.append(p)
    return remaining, trade_logs

def select_candidates_v12(current_time, bundle, target_codes, max_count=10):
    """
    V12.0 爆発力重視の銘柄選定
    optimizer.py と完全同一のフィルター条件を使用
    """
    candidates = []
    # 終値基準のデータを一括取得
    c, v, s20, sv20, r3, ht = [bundle[k].loc[current_time] for k in ["Close", "Volume", "SMA20", "SMA20_Vol", "Ret3", "HT"]]
    
    for code in target_codes:
        ticker = f"{code}.T"
        if ticker not in c.index: continue
        cp = c[ticker]
        # optimizer.py と同一: MIN_PRICE <= cp <= MAX_PRICE
        if pd.isna(cp) or cp < MIN_PRICE or cp > MAX_PRICE: continue
        
        # 爆発フィルタ: optimizer.py と完全一致
        # SMA20上, Ret3 > 5%, 出来高1.5倍, ブレイクアウト
        if cp > s20[ticker] and r3[ticker] > 5 and v[ticker] > sv20[ticker] * 1.5 and cp > ht[ticker]:
            candidates.append({
                "code": code, 
                "score": float(r3[ticker]), # 勢いが強い順に並べる
                "price": cp
            })
            
    return sorted(candidates, key=lambda x: x['score'], reverse=True)

# ==========================================
# 2. 本番用・バックテスト共通インターフェース
# ==========================================

class RealtimeBuffer:
    def __init__(self, code, historical_df, interval_mins=15):
        self.code = code
        self.data = historical_df.copy()
        self.interval_mins = interval_mins

    def update(self, price, volume, current_time):
        if price is None or price <= 0: return
        ticker = f"{self.code}.T"
        if ticker in self.data.columns.get_level_values(0):
            self.data.loc[current_time, (ticker, "Close")] = price
            self.data.loc[current_time, (ticker, "High")] = max(price, self.data.loc[current_time, (ticker, "High")] if (current_time in self.data.index and not pd.isna(self.data.loc[current_time, (ticker, "High")])) else price)
            self.data.loc[current_time, (ticker, "Low")] = min(price, self.data.loc[current_time, (ticker, "Low")] if (current_time in self.data.index and not pd.isna(self.data.loc[current_time, (ticker, "Low")])) else price)
            if volume: self.data.loc[current_time, (ticker, "Volume")] = volume

def calculate_all_technicals(full_data, breakout_p=5):
    return calculate_all_technicals_v12(full_data, breakout_p=breakout_p)

# Live versions of V12 selection and management
def select_best_candidates(data_df, targets, df_symbols, regime, realtime_buffers=None):
    # V12 logic specifically for live bot usage
    bundle = calculate_all_technicals_v12(data_df)
    if bundle is None: return []
    current_time = data_df.index[-1]
    candidates = select_candidates_v12(current_time, bundle, targets, max_count=MAX_POSITIONS)
    # Convert to expected dictionaries for auto_trade.py
    results = []
    for c in candidates:
        name = df_symbols[df_symbols['コード'].astype(str) == str(c['code'])]['銘柄名'].values[0] if not df_symbols.empty else "Unknown"
        results.append({
            "code": c['code'], "name": name, "price": c['price'], "score": c['score'], "atr": bundle["ATR"].at[current_time, f"{c['code']}.T"]
        })
    return results

def manage_positions_live(
    portfolio, account, broker=None, regime="BULL",
    is_simulation=False, realtime_buffers=None,
    tp=TARGET_PROFIT, sl=STOP_LOSS_RATE, time_limit=EXIT_PERIOD
):
    """
    V12.0 Live Position Manager
    - auto_trade.py の呼び出し規約に完全準拠
    - held_days は buy_time からの経過日数で正確計算（ループ毎インクリメントではない）
    - Time Limit 到達時は timing='next_open' で翌朝フラグを立て、即時売却しない
    - 翌朝 (9:30以前) に pending_time_exit=True のポジションを成行売却

    Returns: (portfolio_remaining, account, sell_actions, trade_logs)
    """
    trade_logs, remaining, sell_actions = [], [], []
    now = dt.now(JST)
    is_morning = now.time() <= datetime.time(9, 30)  # 寄付き直後かどうか

    for p in portfolio:
        code = str(p['code'])
        ticker = f"{code}.T"
        try:
            # --- 現在価格の取得 ---
            cp = float(p.get('current_price', p['buy_price']))
            hp = cp
            lp = cp
            if not is_simulation and broker is not None:
                try:
                    board = broker.get_board_data([code])
                    b = board.get(str(code), {})
                    cp = float(b.get('price') or cp)
                    hp = float(b.get('high') or cp)
                    lp = float(b.get('low') or cp)
                except Exception:
                    pass
            elif realtime_buffers and code in realtime_buffers:
                try:
                    buf_df = realtime_buffers[code].data
                    if not buf_df.empty:
                        last = buf_df.iloc[-1]
                        if isinstance(buf_df.columns, pd.MultiIndex):
                            cp = float(last.get((ticker, 'Close'), cp))
                            hp = float(last.get((ticker, 'High'), cp))
                            lp = float(last.get((ticker, 'Low'), cp))
                        else:
                            cp = float(last.get('Close', cp))
                            hp = float(last.get('High', cp))
                            lp = float(last.get('Low', cp))
                except Exception:
                    pass
            p['current_price'] = cp

            # --- held_days: buy_time からの経過日数で計算 ---
            try:
                buy_date = dt.strptime(str(p['buy_time'])[:10], '%Y-%m-%d').date()
                held_days = (now.date() - buy_date).days
            except Exception:
                held_days = p.get('held_days', 0)
            p['held_days'] = held_days

            # --- 翌日始値売却の実行（寄付き時） ---
            if p.get('pending_time_exit'):
                if is_morning:
                    # 寄付き価格（cp）で売却実行
                    log = {
                        "code": code, "name": p.get('name', ''),
                        "reason": "Time Limit (morning exec)",
                        "price": cp, "shares": p['shares'],
                        "buy_price": p['buy_price'],
                        "buy_time": p.get('buy_time', ''),
                        "timing": "immediate"
                    }
                    trade_logs.append(log)
                    sell_actions.append(f"SELL {code}: TimeLimit@morning {cp:.0f}")
                else:
                    # 翌朝になるまで保有継続
                    remaining.append(p)
                continue

            # --- 通常エグジット判定 ---
            reason = None
            exit_p = 0
            timing = "immediate"

            if hp >= p['buy_price'] * (1.0 + tp):
                reason = "Target Profit"
                exit_p = p['buy_price'] * (1.0 + tp)
            elif lp <= p['buy_price'] * (1.0 - sl):
                reason = "Stop Loss"
                exit_p = p['buy_price'] * (1.0 - sl)
            elif held_days >= time_limit:
                # 翌朝始値売却: ポジションは保有継続 + フラグON
                p['pending_time_exit'] = True
                remaining.append(p)
                trade_logs.append({
                    "code": code, "name": p.get('name', ''),
                    "reason": "Time Limit",
                    "price": cp, "shares": p['shares'],
                    "buy_price": p['buy_price'],
                    "buy_time": p.get('buy_time', ''),
                    "timing": "next_open"  # 即時執行しない
                })
                sell_actions.append(f"DEFER {code}: TimeLimit → 翌朝始値売却予定")
                continue

            if reason:
                trade_logs.append({
                    "code": code, "name": p.get('name', ''),
                    "reason": reason, "price": exit_p,
                    "shares": p['shares'], "buy_price": p['buy_price'],
                    "buy_time": p.get('buy_time', ''),
                    "timing": timing
                })
                sell_actions.append(f"SELL {code}: {reason} @ {exit_p:.0f}")
            else:
                remaining.append(p)

        except Exception as e:
            print(f"[WARNING] manage_positions_live: {code} エラー: {e}")
            remaining.append(p)

    return remaining, account, sell_actions, trade_logs


# ==========================================
# 3. ユーティリティ関数 (auto_trade.py 依存)
# ==========================================

def detect_market_regime(broker=None, buffer=None):
    """
    日経225 ETF (1321.T) のトレンドからレジームを判定。
    Returns: 'BULL' | 'RANGE' | 'BEAR'
    """
    try:
        import yfinance as yf
        df = yf.download("1321.T", period="1y", interval="1d",
                         progress=False, threads=False, auto_adjust=False)
        if df is None or df.empty or len(df) < 50:
            return "RANGE"
        close = df['Close'].squeeze()
        sma50  = close.rolling(50).mean().iloc[-1]
        sma200 = close.rolling(min(200, len(close))).mean().iloc[-1]
        latest = close.iloc[-1]
        if latest > sma50 and sma50 > sma200:
            return "BULL"
        elif latest < sma50 and sma50 < sma200:
            return "BEAR"
        else:
            return "RANGE"
    except Exception as e:
        print(f"[WARNING] detect_market_regime: {e}")
        return "RANGE"


_INVALID_TICKERS_FILE = "invalid_tickers.json"

def load_invalid_tickers():
    """データ取得不可だった銘柄コードのセットを読み込む"""
    try:
        with open(_INVALID_TICKERS_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f).get("codes", []))
    except Exception:
        return set()


def save_invalid_tickers(codes):
    """データ取得不可だった銘柄コードのセットを保存する"""
    try:
        existing = load_invalid_tickers()
        updated = list(existing | set(str(c) for c in codes))
        with open(_INVALID_TICKERS_FILE, "w", encoding="utf-8") as f:
            json.dump({"codes": updated}, f, ensure_ascii=False)
    except Exception as e:
        print(f"[WARNING] save_invalid_tickers: {e}")


def normalize_tick_size(price, is_buy=True):
    """
    東証の呼値単位に価格を丸める。
    is_buy=True のとき切り上げ（買い注文）、False のとき切り捨て（売り注文）。
    """
    import math
    if price < 200:    tick = 1
    elif price < 500:   tick = 1
    elif price < 1000:  tick = 1
    elif price < 2000:  tick = 1
    elif price < 3000:  tick = 1
    elif price < 5000:  tick = 5
    elif price < 10000: tick = 10
    elif price < 30000: tick = 10
    elif price < 50000: tick = 50
    else:               tick = 100
    if is_buy:
        return math.ceil(price / tick) * tick
    else:
        return math.floor(price / tick) * tick
