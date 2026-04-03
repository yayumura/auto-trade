import pandas as pd
import numpy as np
import time
import os
import json
import datetime
from datetime import datetime as dt
from .config import BREAKOUT_PERIOD, EXIT_PERIOD, MAX_POSITIONS, OVERHEAT_THRESHOLD, JST

# ==========================================
# 1. バックテスト専用ロジック (v10 Legacy)
# ==========================================

def calculate_all_technicals_v10(full_data, breakout_p=BREAKOUT_PERIOD, exit_p=EXIT_PERIOD):
    if full_data is None or full_data.empty: return None
    close, high, low, volume, open_p = [full_data.xs(k, axis=1, level=1) for k in ["Close", "High", "Low", "Volume", "Open"]]
    
    # Daily Gap Guard (データ異常・分割修正漏れ検知)
    # 前日終値と当日始値の間に50%以上の乖離がある銘柄を「不完全データ」として全期間除隊
    abs_gap = (open_p / close.shift(1) - 1).abs()
    invalid_mask = (abs_gap > 0.50).any()
    valid_tickers = invalid_mask[~invalid_mask].index.tolist()
    
    if len(valid_tickers) < len(close.columns):
        close, high, low, volume, open_p = [df.loc[:, valid_tickers] for df in [close, high, low, volume, open_p]]

    sma200 = close.rolling(200).mean()
    sma200_slope = sma200.diff(5)
    ht = high.rolling(breakout_p).max().shift(1)
    le = low.rolling(exit_p).min().shift(1)
    vol_confirm = volume > volume.shift(1)
    sma20 = close.rolling(20).mean()
    div = (close / sma20 - 1) * 100
    
    # ATR (Average True Range) - Period 14
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = np.maximum(np.maximum(tr1, tr2), tr3)
    atr = tr.rolling(14).mean()

    return {
        "Close": close, "High": high, "Low": low, "Volume": volume,
        "SMA200": sma200, "SMA200_Slope": sma200_slope,
        "HT": ht, "LE": le, "Vol_Confirm": vol_confirm, "Divergence": div,
        "ATR": atr,
        "Open": open_p
    }

def manage_positions_v10(portfolio, current_time, bundle, use_shield=True, use_profit_guard=False):
    """
    バックテスト用のポジション管理ロジック。
    [Unified Logic] 本番運用と同じ判定順序・実行タイミング（ルックアヘッド排除）に統一。
    """
    trade_logs, remaining = [], []
    is_bear = False
    if use_shield:
        try:
            etf = "1321.T"
            timeline = bundle["Close"].index
            current_idx = timeline.get_loc(current_time)
            if current_idx > 0:
                prev_time = timeline[current_idx - 1]
                # 前日の終値で判定（現実的）
                if bundle["Close"].at[prev_time, etf] < bundle["SMA200"].at[prev_time, etf]:
                    is_bear = True
        except: pass

    for p in portfolio:
        code = str(p['code']); ticker = f"{code}.T"
        try:
            op, lp, hp, le_std = [bundle[k].at[current_time, ticker] for k in ["Open", "Low", "High", "LE"]]
            cp = bundle["Close"].at[current_time, ticker]
            atr = bundle["ATR"].at[current_time, ticker]
            
            if 'max_p' not in p or p['max_p'] < hp: p['max_p'] = hp
            if 'held_days' not in p: p['held_days'] = 0
            p['held_days'] += 1

            le = le_std
            is_be_active = False
            if (p['max_p'] - p['buy_price']) > (1.5 * atr):
                le = max(le, p['buy_price'])
                is_be_active = True

            r, ep, timing = (None, 0, "immediate")
            
            # --- エグジット判定 (判定順序を本番に合わせる) ---
            # 1. 相場急変 (Market Shield) -> 当日の寄り付きで売却 (前日判定済み)
            if is_bear:
                r = "Market Shield Exit"; ep = op; timing = "immediate"
            
            # 2. ガップダウン -> 当日の寄り付きで売略
            elif not r and op < le:
                r = "Gap Down Exit"; ep = op; timing = "immediate"
            
            # 3. 通常の逆指値 -> 当日の逆指値価格(le)で売却 (日中のStopヒットを模擬)
            elif not r and lp < le:
                r = "Trend Exit" if not is_be_active else "Break-even Exit"
                ep = le; timing = "immediate"

            # 4. タイムストップ (Stagnation) -> 今日の終値(cp)で判断し、「翌営業日の寄り付き」で売却
            if not r and p['held_days'] >= 10:
                if (cp - p['buy_price']) < (0.5 * atr):
                    r = "Time Stop"; timing = "next_open"

            if r:
                trade_logs.append({
                    "code": code, "reason": r, "price": ep, 
                    "shares": p['shares'], "buy_price": p['buy_price'], "buy_time": p.get('buy_time', str(current_time)),
                    "timing": timing 
                })
            else:
                remaining.append(p)
        except: remaining.append(p)
    return remaining, trade_logs

def select_candidates_v10(current_time, bundle, target_codes, max_count=3, overheat_threshold=25.0, use_shield=True):
    if use_shield:
        try:
            etf = "1321.T"
            if bundle["Close"].at[current_time, etf] < bundle["SMA200"].at[current_time, etf]:
                return []
        except: pass

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
            # [Optimization] Use Turnover (Volume * Price) for better liquidity matching
            candidates.append({"code": code, "score": float(v[ticker] * cp), "price": cp})
    return sorted(candidates, key=lambda x: x['score'], reverse=True)[:max_count]

# ==========================================
# 2. 本番用リアルタイムロジック (Live Integrated)
# ==========================================

def detect_market_regime(broker=None, buffer=None, bundle=None, current_time=None, **kwargs):
    """
    相場環境(Regime)を判定する。
    1321.T (TOPIX ETF) が SMA200 の上にあるか下にあるかで BULL/BEAR を判定。
    """
    try:
        if bundle is not None and current_time is not None:
            etf = "1321.T"
            if etf in bundle["Close"].columns:
                cp = bundle["Close"].at[current_time, etf]
                sma200 = bundle["SMA200"].at[current_time, etf]
                return "BULL" if cp > sma200 else "BEAR"

        import yfinance as yf
        df = yf.download("1321.T", period="2y", interval="1d", progress=False)
        if df.empty: return "BULL"
        
        close = df['Close']
        if isinstance(close, pd.Series):
            cp = close.iloc[-1]
            sma200 = close.rolling(200).mean().iloc[-1]
        else: # MultiIndex case
            cp = close.iloc[-1, 0]
            sma200 = close.rolling(200).mean().iloc[-1, 0]
            
        return "BULL" if cp > sma200 else "BEAR"
    except Exception as e:
        print(f"[DEBUG] detect_market_regime fallback: {e}")
        return "BULL"

def manage_positions(portfolio, account, broker=None, regime="BULL", is_simulation=True, realtime_buffers=None):
    """ 本番運用用の損切り・ポジション管理 (防衛ロジック搭載) """
    sell_actions, trade_logs = [], []
    is_panic = (regime == "BEAR")
    new_portfolio = []
    now_dt = datetime.datetime.now(JST)

    for p in portfolio:
        code = str(p['code'])
        ticker = f"{code}.T"
        cp = p.get('current_price', p['buy_price'])
        
        atr = 0
        if realtime_buffers and code in realtime_buffers:
            buffer = realtime_buffers[code]
            cp = buffer.last_price or cp
            try:
                df = buffer.data
                if not df.empty:
                    tr = np.maximum(np.maximum(df['High']-df['Low'], (df['High']-df['Close'].shift(1)).abs()), (df['Low']-df['Close'].shift(1)).abs())
                    atr = tr.rolling(14).mean().iloc[-1]
            except: pass
            
        if cp > p.get('highest_price', 0):
            p['highest_price'] = cp
            
        try:
            buy_dt = datetime.datetime.strptime(p['buy_time'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=JST)
            held_days = (now_dt - buy_dt).days
        except: held_days = 0

        le = p.get('low_exit', 0)
        reason = None
        
        if atr > 0 and (p['highest_price'] - p['buy_price']) > (1.5 * atr):
            safe_le = p['buy_price'] * 1.001
            if le < safe_le:
                le = safe_le

        if held_days >= 10:
            if atr > 0 and (cp - p['buy_price']) < (0.5 * atr):
                reason = "Time Stop (Stagnation)"

        if is_panic:
            reason = "Market Shield Exit (BEAR Regime)"
            
        if not reason and le > 0 and cp < le:
            reason = "Trend Exit (Break Stop Loss)"
            
        if reason:
            sell_actions.append(f"SELL {code} @ {cp} ({reason})")
            trade_logs.append({
                "code": code, "shares": p['shares'], "price": cp, "reason": reason,
                "buy_price": p['buy_price'], "buy_time": p.get('buy_time')
            })
            if is_simulation:
                account['cash'] += cp * p['shares']
        else:
            p['current_price'] = cp
            p['low_exit'] = le
            new_portfolio.append(p)
            
    return new_portfolio, account, sell_actions, trade_logs

def select_best_candidates(data_df, targets, df_symbols, regime, realtime_buffers=None):
    if regime == "BEAR": return []
    bundle = calculate_all_technicals_v10(data_df)
    if not bundle: return []
    current_time = data_df.index[-1]
    return select_candidates_v10(current_time, bundle, targets, max_count=50, overheat_threshold=OVERHEAT_THRESHOLD, use_shield=False)

# ==========================================
# 3. ユーティリティ
# ==========================================

def normalize_tick_size(price, is_buy=True):
    if price is None or price <= 0: return 0
    if price < 3000: tick = 1
    elif price < 5000: tick = 5
    elif price < 30000: tick = 10
    elif price < 50000: tick = 50
    else: tick = 100
    return (np.ceil(price / tick) if is_buy else np.floor(price / tick)) * tick

class RealtimeBuffer:
    def __init__(self, code, seed_data=None, interval_mins=15):
        self.code = code
        self.last_price = 0
        self.last_volume = 0
        self.data = seed_data
    def update(self, price, volume, dt):
        if price and price > 0:
            self.last_price = price
            self.last_volume = volume

def load_invalid_tickers():
    from core.config import DATA_ROOT
    path = os.path.join(DATA_ROOT, "invalid_tickers.json")
    if os.path.exists(path):
        with open(path, 'r') as f: return set(json.load(f))
    return set()

def save_invalid_tickers(tickers):
    from core.config import DATA_ROOT
    path = os.path.join(DATA_ROOT, "invalid_tickers.json")
    with open(path, 'w') as f: json.dump(list(tickers), f)