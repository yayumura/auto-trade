import yfinance as yf
import pandas as pd
import sys, os, numpy as np
sys.path.append(os.getcwd())
from core.config import JST, ATR_STOP_LOSS
from core.logic import calculate_technicals_for_scan, RealtimeBuffer
from datetime import datetime

# トヨタの直近5日間データで単体テスト
code = '7203'
ticker = f'{code}.T'
df_raw = yf.download(ticker, period='10d', interval='15m', auto_adjust=True, progress=False, threads=False)
df_raw.index = df_raw.index.tz_localize('UTC').tz_convert(JST) if df_raw.index.tzinfo is None else df_raw.index.tz_convert(JST)
if isinstance(df_raw.columns, pd.MultiIndex):
    df_raw.columns = df_raw.columns.droplevel('Ticker')

# ポジション模擬
buy_price = 3345.0
highest_price = 3345.0

# manage_positionsと全く同じ計算を追跡
df = df_raw.copy()
df2 = calculate_technicals_for_scan(df)
if df2 is None:
    print("Not enough data!")
    exit()

# ATR計算
tr1 = df['High'] - df['Low']
tr2 = abs(df['High'] - df['Close'].shift())
tr3 = abs(df['Low'] - df['Close'].shift())
atr = float(pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean().iloc[-1])
print(f"ATR = {atr:.2f}")

is_simulation = True
slippage = atr * 0.03
is_partial_sold = False

# 直近の価格を見てみる
print("\n=== 直近30本の価格と損切/利確ライン ===")
for i in range(-30, 0):
    row = df.iloc[i]
    current_price_raw = float(row['Close'])
    current_price = max(0.1, current_price_raw - slippage)  # sim slippage
    
    # split_ratio: Adj Closeがない場合は1.0
    split_ratio = 1.0
    
    bp_adj = buy_price * split_ratio
    hp_adj = highest_price * split_ratio
    
    is_in_profit_mode = hp_adj >= bp_adj * 1.01
    if is_in_profit_mode:
        chandelier_stop = hp_adj - (atr * 2.5)
    else:
        chandelier_stop = max(bp_adj * 0.98, bp_adj - (atr * 3.5))
    
    take_profit_price = bp_adj * 1.02
    hard_stop = bp_adj * 0.96
    
    # 最高値更新
    new_hp = max(hp_adj, current_price) / split_ratio if split_ratio > 0 else max(hp_adj, current_price)
    highest_price = new_hp
    
    flags = []
    if current_price <= hard_stop: flags.append("HARD_STOP")
    if current_price <= chandelier_stop: flags.append("CHANDELIER")
    if current_price >= take_profit_price: flags.append("TAKE_PROFIT!")
    
    print(f"  {df.index[i].strftime('%m/%d %H:%M')} Close={current_price_raw:.1f} (sim={current_price:.1f}) | TP={take_profit_price:.1f} | chan={chandelier_stop:.1f} | hard={hard_stop:.1f} | highest={hp_adj:.1f} | {flags}")

print(f"\nbuy_price={buy_price}, ATR={atr:.2f}")
print(f"+2% TP target = {buy_price*1.02:.1f}")
print(f"-2% Initial stop = {buy_price*0.98:.1f}")
print(f"ATR 3.5x = {atr*3.5:.1f} -> initial stop = {max(buy_price*0.98, buy_price - atr*3.5):.1f}")
