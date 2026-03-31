import pandas as pd
import numpy as np
import time
from core.config import (
    DONCHIAN_BREAKOUT, DONCHIAN_EXIT, MIN_TURNOVER, ATR_STOP_MULT, TAX_RATE
)

def calculate_all_technicals_v4(full_data, breakout_period=DONCHIAN_BREAKOUT, exit_period=DONCHIAN_EXIT):
    """
    [Turbo V4] Vectorized calculation of indicators with SMA200 Slope.
    """
    if full_data is None or full_data.empty: return None
    print(f"  [Turbo V4] {len(full_data.columns.levels[0])} 銘柄を一括計算中...")
    
    close = full_data.xs('Close', axis=1, level=1)
    high = full_data.xs('High', axis=1, level=1)
    low = full_data.xs('Low', axis=1, level=1)
    volume = full_data.xs('Volume', axis=1, level=1)
    open_p = full_data.xs('Open', axis=1, level=1)
    
    # Basic Indicators
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()
    
    # SMA200 Slope (20-day trend)
    sma200_slope = (sma200 - sma200.shift(20)) / 20
    
    turnover_avg = (close * volume).rolling(20).mean()
    high_trigger = high.rolling(breakout_period).max().shift(1)
    low_exit = low.rolling(exit_period).min().shift(1)
    
    # ATR
    tr1, tr2, tr3 = high-low, (high-close.shift()).abs(), (low-close.shift()).abs()
    tr = np.maximum(tr1, np.maximum(tr2, tr3))
    atr = tr.rolling(14).mean().fillna(close * 0.02).clip(lower=1.0)
    
    return {
        "Close": close, "Open": open_p, "High": high, "Low": low,
        "SMA50": sma50, "SMA200": sma200, "SMA200_Slope": sma200_slope,
        "Turnover_Avg": turnover_avg, "High_Trigger": high_trigger, "Low_Exit": low_exit, "ATR": atr
    }

def manage_positions_v4(portfolio, account, current_time, tech_bundle, stop_mult=ATR_STOP_MULT):
    trade_logs = []
    
    for p in portfolio:
        ticker = f"{p['code']}.T"
        try:
            curr_p = tech_bundle["Close"].at[current_time, ticker]
            open_p = tech_bundle["Open"].at[current_time, ticker]
            low_p = tech_bundle["Low"].at[current_time, ticker]
            atr = tech_bundle["ATR"].at[current_time, ticker]
            low_exit = tech_bundle["Low_Exit"].at[current_time, ticker]
            buy_p = p['buy_price']
            
            sell_reason = None
            stop_price = buy_p - (atr * stop_mult)
            
            if open_p <= stop_price: sell_reason = "Gap Down"; curr_p = open_p
            elif low_p <= stop_price: sell_reason = "Stop Loss"; curr_p = stop_price
            elif low_p < low_exit: sell_reason = "Trend Exit"; curr_p = low_exit
            
            if sell_reason:
                gross = (curr_p - buy_p) * p['shares']
                tax = max(0, gross * TAX_RATE) if gross > 0 else 0
                account['cash'] += (curr_p * p['shares']) - tax
                trade_logs.append({"code": p['code'], "profit": gross-tax, "reason": sell_reason, "buy_price": buy_p, "buy_time": p['buy_time'], "atr": p.get('atr', atr)})
            else: pass
        except: pass
    
    # portfolio の更新は呼び出し側で行うのが安全だが、ここではlogsに含まれるものを除外したリストを返す（または呼び出し側で処理）
    return portfolio, account, trade_logs # 注意: 戻り値の形式は backtest.py と合わせる

def select_best_candidates_v4(current_time, tech_bundle, target_codes, min_turnover=MIN_TURNOVER):
    candidates = []
    c, s50, s200, slope, to, ht, atr = [tech_bundle[k].loc[current_time] for k in ["Close", "SMA50", "SMA200", "SMA200_Slope", "Turnover_Avg", "High_Trigger", "ATR"]]
    
    for code in target_codes:
        ticker = f"{code}.T"
        if ticker not in c.index: continue
        cp = c[ticker]
        if pd.isna(cp) or cp > 3000 or to[ticker] < min_turnover: continue
        if not (s50[ticker] > s200[ticker] and cp > s200[ticker] and slope[ticker] > 0): continue
        if cp > ht[ticker]:
            candidates.append({"code": code, "score": cp / ht[ticker], "price": cp, "atr": atr[ticker]})
    return sorted(candidates, key=lambda x: x['score'], reverse=True)[:3]

# バックテスト互換用のクラス定義
class RealtimeBuffer:
    def __init__(self, code, df):
        self.code = code
        self.df = df
    def get_df(self): return self.df