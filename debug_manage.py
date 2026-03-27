"""
manage_positionsのexitロジックを独立してテストする。
ポートフォリオにトヨタのポジションを直接設定し、どの決済条件が発火するか確認。
"""
import yfinance as yf
import pandas as pd
import sys, os, numpy as np
sys.path.append(os.getcwd())
from core.config import JST
from core.logic import manage_positions, RealtimeBuffer
from core.sim_broker import SimulationBroker
from datetime import datetime

code = '7203'
ticker = f'{code}.T'
print("Downloading Toyota...")
df_raw = yf.download(ticker, period='10d', interval='15m', auto_adjust=True, progress=False, threads=False)
df_raw.index = df_raw.index.tz_localize('UTC').tz_convert(JST) if df_raw.index.tzinfo is None else df_raw.index.tz_convert(JST)
if isinstance(df_raw.columns, pd.MultiIndex):
    df_raw.columns = df_raw.columns.droplevel('Ticker')

print(f"Data: {len(df_raw)} rows. Columns: {list(df_raw.columns)}")
print(f"Has Adj Close: {'Adj Close' in df_raw.columns}")

# 全タイムラインで管理テスト
all_times = df_raw.index.unique().sort_values()
timeline = all_times[-50:]  # 直近50ステップ

# ポジション初期 (3/19のopenとして設定)
buy_time = timeline[0]
buy_price = float(df_raw.loc[buy_time]['Close'])
print(f"\nBuy time: {buy_time}, buy_price: {buy_price:.1f}")
print(f"TP target: {buy_price*1.015:.1f}")
print(f"Init stop: {buy_price*0.985:.1f}")

account = {"cash": 500000}
portfolio = [{
    "code": code,
    "name": "トヨタ自動車",
    "buy_price": buy_price,
    "shares": 100,
    "buy_time": buy_time,
    "atr": 10.5
}]
broker = SimulationBroker()

for current_time in timeline[1:]:
    sliced = df_raw.loc[:current_time]
    mock_buffers = {code: RealtimeBuffer(code, sliced)}

    portfolio, account, actions, logs = manage_positions(
        portfolio, account, broker=broker, regime="RANGE",
        is_simulation=True, realtime_buffers=mock_buffers,
        current_time_override=current_time, verbose=False
    )
    if logs:
        for l in logs:
            print(f"\n=== EXIT FIRED ===")
            print(f"  Time: {current_time}")
            print(f"  Reason: {l['reason']}")
            print(f"  Buy={l['buy_price']:.1f} Sell={l['sell_price']:.1f} PnL={l['profit_pct']*100:+.2f}% NetProfit={l['net_profit']:+.0f}")
    if not portfolio:
        print("Portfolio now empty, done.")
        break
    

if portfolio:
    last_price = float(df_raw.iloc[-1]['Close'])
    pnl = (last_price - buy_price) / buy_price * 100
    print(f"\nStill holding at end: cur={last_price:.1f} ({pnl:+.2f}%)")
    print(f"  TP={buy_price*1.015:.1f} | Stop={buy_price*0.985:.1f}")
    print(f"Last row in portfolio: {portfolio[0]}")
