import pandas as pd
import numpy as np

# --- V10.3 FINAL PRODUCTION ENGINE (Corrected Names) ---

def calculate_all_technicals_v10(full_data, breakout_p=25, exit_p=10):
    """
    本番・バックテスト共通の指標計算エンジン。
    """
    if full_data is None or full_data.empty: return None
    
    close = full_data.xs('Close', axis=1, level=1)
    high = full_data.xs('High', axis=1, level=1)
    low = full_data.xs('Low', axis=1, level=1)
    volume = full_data.xs('Volume', axis=1, level=1)
    open_p = full_data.xs('Open', axis=1, level=1)
    
    # 指標
    sma200 = close.rolling(200).mean()
    sma200_slope = (sma200 - sma200.shift(20)) / 20
    
    # ドンチャン
    ht = high.rolling(breakout_p).max().shift(1)
    le = low.rolling(exit_p).min().shift(1)
    
    # 出来高確認
    vol_confirm = volume > volume.shift(1)
    
    # ATR (損切り用)
    tr1, tr2, tr3 = high-low, (high-close.shift()).abs(), (low-close.shift()).abs()
    tr = np.maximum(tr1, np.maximum(tr2, tr3))
    atr = tr.rolling(14).mean().fillna(close * 0.02).clip(lower=1.0)
    
    return {
        "Close": close, "Open": open_p, "High": high, "Low": low, "Volume": volume,
        "SMA200": sma200, "SMA200_Slope": sma200_slope,
        "HT": ht, "LE": le, "Vol_Confirm": vol_confirm, "ATR": atr
    }

def select_candidates_v10(current_time, bundle, target_codes, max_count=3):
    """
    本番・バックテスト共通のスキャンエンジン。
    """
    candidates = []
    c, s200, slope, ht, v_conf, v, atr = [bundle[k].loc[current_time] for k in ["Close", "SMA200", "SMA200_Slope", "HT", "Vol_Confirm", "Volume", "ATR"]]
    
    for code in target_codes:
        ticker = f"{code}.T"
        if ticker not in c.index: continue
        cp = c[ticker]
        if pd.isna(cp) or cp < 100: continue
        
        if slope[ticker] > 0 and cp > s200[ticker] and cp > ht[ticker] and v_conf[ticker]:
            candidates.append({"code": code, "score": v[ticker], "price": cp, "atr": atr[ticker]})
            
    return sorted(candidates, key=lambda x: x['score'], reverse=True)[:max_count]

def manage_positions_v10(portfolio, current_time, bundle, stop_mult=3.0):
    """
    本番・バックテスト共通のポジション管理エンジン。
    """
    trade_logs = []
    remaining = []
    
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