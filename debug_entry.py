import yfinance as yf
import pandas as pd
import sys, os
sys.path.append(os.getcwd())
from core.config import JST
from core.logic import detect_market_regime, calculate_technicals_for_scan, RealtimeBuffer

codes = ['8306', '7203', '9101']
tickers = [f'{c}.T' for c in codes] + ['1321.T']
full_data = yf.download(tickers, period='60d', interval='15m', group_by='ticker', auto_adjust=True, progress=False, threads=False)
full_data.index = full_data.index.tz_localize('UTC').tz_convert(JST) if full_data.index.tzinfo is None else full_data.index.tz_convert(JST)

df_1321 = full_data['1321.T'].dropna()
buf_1321 = RealtimeBuffer('1321', df_1321)
regime = detect_market_regime(broker=None, buffer=buf_1321, current_time_override=None, verbose=True)
print(f'\n==> Regime: {regime}\n')

for code in codes:
    ticker = f'{code}.T'
    if ticker not in full_data.columns.levels[0]:
        continue
    df_raw = full_data[ticker].dropna()
    buf = RealtimeBuffer(code, df_raw)
    df = buf.df
    df2 = calculate_technicals_for_scan(df.copy())
    if df2 is None:
        print(f'{code}: not enough data')
        continue
    latest = df2.iloc[-1]
    sma5 = df2['Close'].rolling(5).mean().iloc[-1]
    if len(df2) >= 50:
        momentum_50 = (latest['Close'] - df2['Close'].iloc[-50]) / df2['Close'].iloc[-50]
    else:
        momentum_50 = 0.0
    today_df = df2[df2.index.date == df2.index[-1].date()]
    if not today_df.empty and today_df['Volume'].sum() > 0:
        tp = (today_df['High'] + today_df['Low'] + today_df['Close']) / 3
        vwap = (tp * today_df['Volume']).sum() / today_df['Volume'].sum()
    else:
        vwap = latest['Close']
    avg_vol = latest['Avg_Vol_15m']
    vol_ratio = latest['Volume'] / avg_vol if avg_vol > 0 else 0
    print(f"{code}: Close={latest['Close']:.1f} VWAP={vwap:.1f} SMA5={sma5:.1f} RSI={latest['RSI']:.1f} mom50={momentum_50:.3f}")
    print(f"  Above VWAP*0.99: {latest['Close'] >= vwap * 0.99} | Above SMA5: {latest['Close'] > sma5} | mom>-0.05: {momentum_50 >= -0.05} | RSI<80: {latest['RSI'] < 80}")
    if momentum_50 >= -0.05 and latest['Close'] > sma5 and latest['Close'] >= vwap * 0.99 and latest['RSI'] < 80:
        print(f"  => ENTRY SIGNAL FIRES! score estimated")
    else:
        print(f"  => no entry")
    print()
