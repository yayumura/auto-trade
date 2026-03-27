"""快速確認: manage_positions を verbose=True で実行"""
import yfinance as yf
import pandas as pd
import sys, os
sys.path.append(os.getcwd())
from core.config import JST
from core.logic import manage_positions, RealtimeBuffer
from core.sim_broker import SimulationBroker

code = '7203'
df_raw = yf.download(f'{code}.T', period='10d', interval='15m', auto_adjust=True, progress=False, threads=False)
df_raw.index = df_raw.index.tz_localize('UTC').tz_convert(JST) if df_raw.index.tzinfo is None else df_raw.index.tz_convert(JST)
if isinstance(df_raw.columns, pd.MultiIndex):
    df_raw.columns = df_raw.columns.droplevel('Ticker')

all_times = df_raw.index.unique().sort_values()
timeline = all_times[-20:]  # 最後の5時間分のみ

buy_price = 3345.0
account = {"cash": 500000}
portfolio = [{"code": code, "name": "トヨタ", "buy_price": buy_price, "shares": 100, "buy_time": timeline[0], "atr": 10.5}]

for t in timeline[1:]:
    sliced = df_raw.loc[:t]
    mock = {code: RealtimeBuffer(code, sliced)}
    portfolio, account, actions, logs = manage_positions(
        portfolio, account, broker=SimulationBroker(), regime="RANGE",
        is_simulation=True, realtime_buffers=mock, current_time_override=t, verbose=True
    )
    if logs:
        print(f"\n!!!! EXIT at {t}: {logs[0]['reason']}, profit={logs[0]['profit_pct']*100:+.2f}%")
        break

print(f"\nbuy_price={buy_price}, TP={buy_price*1.015:.1f}")
print("Last row close:", df_raw.iloc[-1]['Close'])
