import pandas as pd
import numpy as np
import time
import os
import json
from .config import BREAKOUT_PERIOD, EXIT_PERIOD, MAX_POSITIONS, OVERHEAT_THRESHOLD

# ==========================================
# 1. バックテスト専用ロジック (v10 Legacy)
# ==========================================

def calculate_all_technicals_v10(full_data, breakout_p=BREAKOUT_PERIOD, exit_p=EXIT_PERIOD):
    if full_data is None or full_data.empty: return None
    close = full_data.xs('Close', axis=1, level=1) if 'Close' in full_data.columns.get_level_values(1) else full_data
    high = full_data.xs('High', axis=1, level=1) if 'High' in full_data.columns.get_level_values(1) else full_data
    low = full_data.xs('Low', axis=1, level=1) if 'Low' in full_data.columns.get_level_values(1) else full_data
    volume = full_data.xs('Volume', axis=1, level=1) if 'Volume' in full_data.columns.get_level_values(1) else full_data
    sma200 = close.rolling(200).mean()
    sma200_slope = sma200.diff(5)
    ht = high.rolling(breakout_p).max().shift(1)
    le = low.rolling(exit_p).min().shift(1)
    vol_confirm = volume > volume.shift(1)
    sma20 = close.rolling(20).mean()
    div = (close / sma20 - 1) * 100
    return {
        "Close": close, "High": high, "Low": low, "Volume": volume,
        "SMA200": sma200, "SMA200_Slope": sma200_slope,
        "HT": ht, "LE": le, "Vol_Confirm": vol_confirm, "Divergence": div,
        "Open": full_data.xs('Open', axis=1, level=1) if 'Open' in full_data.columns.get_level_values(1) else full_data
    }

def manage_positions_v10(portfolio, current_time, bundle, use_shield=True, use_profit_guard=False):
    trade_logs, remaining = [], []
    is_bear = False
    if use_shield:
        try:
            etf = "1321.T"
            timeline = bundle["Close"].index
            current_idx = timeline.get_loc(current_time)
            if current_idx > 0:
                prev_time = timeline[current_idx - 1]
                if bundle["Close"].at[prev_time, etf] < bundle["SMA200"].at[prev_time, etf]:
                    is_bear = True
        except: pass

    for p in portfolio:
        code = str(p['code']); ticker = f"{code}.T"
        try:
            op, lp, le_std = [bundle[k].at[current_time, ticker] for k in ["Open", "Low", "LE"]]
            cp = bundle["Close"].at[current_time, ticker]
            gain = (cp / p['buy_price']) - 1
            if gain > 0.30 and use_profit_guard:
                try:
                    le = bundle["Low"].loc[:current_time, ticker].iloc[-6:-1].min()
                except: le = le_std
            else:
                le = le_std

            r, ep = (None, 0)
            if is_bear:
                r = "Market Shield Exit"; ep = op
            elif op < le:
                r = "Gap Exit"; ep = op
            elif lp < le:
                r = "Trend Exit"; ep = le
                
            if r:
                trade_logs.append({"code": code, "reason": r, "price": ep, "shares": p['shares'], "buy_price": p['buy_price'], "buy_time": p['buy_time']})
            else:
                remaining.append(p)
        except: remaining.append(p)
    return remaining, trade_logs

def select_candidates_v10(current_time, bundle, target_codes, max_count=3, overheat_threshold=30.0, use_shield=True):
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
            candidates.append({"code": code, "score": float(v[ticker]), "price": cp})
    return sorted(candidates, key=lambda x: x['score'], reverse=True)[:max_count]

# ==========================================
# 2. 本番用リアルタイムロジック (Live Integrated)
# ==========================================

def detect_market_regime(bundle, current_time):
    try:
        etf = "1321.T"
        cp = bundle["Close"].at[current_time, etf]
        sma200 = bundle["SMA200"].at[current_time, etf]
        return "BULL" if cp > sma200 else "BEAR"
    except: return "BULL"

def manage_positions(portfolio, account, regime="BULL", is_simulation=True, realtime_buffers=None):
    """ 本番運用用の損切り・ポジション管理 """
    sell_actions, trade_logs = [], []
    is_panic = (regime == "BEAR")
    new_portfolio = []
    
    for p in portfolio:
        code = str(p['code'])
        # 損切り価格(Low Exit)を過去データ(bundle等)から取得し、保有時に記録している想定
        # ここでは簡易的に、現在の価格がLE(損切ライン)を割ったかを判定
        cp = p.get('current_price', p['buy_price'])
        if realtime_buffers and code in realtime_buffers:
            cp = realtime_buffers[code].last_price or cp
            
        le = p.get('low_exit', 0)
        reason = None
        if is_panic:
            reason = "Market Shield Exit (BEAR Regime)"
        elif le > 0 and cp < le:
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
            new_portfolio.append(p)
            
    return new_portfolio, account, sell_actions, trade_logs

def select_best_candidates(data_df, targets, df_symbols, regime, realtime_buffers=None):
    if regime == "BEAR": return []
    bundle = calculate_all_technicals_v10(data_df)
    if not bundle: return []
    current_time = data_df.index[-1]
    return select_candidates_v10(current_time, bundle, targets, max_count=MAX_POSITIONS, overheat_threshold=OVERHEAT_THRESHOLD, use_shield=False)

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