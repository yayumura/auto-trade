import yfinance as yf
import pandas as pd
import sys, os
sys.path.append(os.getcwd())
from core.config import JST, INITIAL_CASH, DATA_FILE, MAX_RISK_PER_TRADE, MAX_ALLOCATION_PCT, MIN_ALLOCATION_AMOUNT, MAX_POSITIONS, ATR_STOP_LOSS, RANGE_ATR_STOP_LOSS
from core.logic import select_best_candidates, manage_positions, RealtimeBuffer, detect_market_regime
from core.sim_broker import SimulationBroker
from datetime import datetime

target_codes = ["8306", "7203", "9101", "8058", "6758"]
tickers = [f"{c}.T" for c in target_codes] + ["1321.T"]
print("Downloading...")
full_data = yf.download(tickers, period="60d", interval="15m", group_by='ticker', auto_adjust=True, progress=False, threads=False)
full_data.index = full_data.index.tz_localize('UTC').tz_convert(JST) if full_data.index.tzinfo is None else full_data.index.tz_convert(JST)

df_1321_full = full_data['1321.T'].dropna()
df_symbols = pd.read_csv(DATA_FILE)

account = {"cash": INITIAL_CASH}
portfolio = []
trade_history = []
broker = SimulationBroker()

all_times = df_1321_full.index.unique().sort_values()
# 直近5日間のみ
test_start_idx = max(0, len(all_times) - 130)
timeline = all_times[test_start_idx:]

print(f"Running {len(timeline)} steps from {timeline[0]} to {timeline[-1]}")

for current_time in timeline:
    mock_buffers = {}
    sliced_data = full_data.loc[:current_time]
    for code in target_codes:
        ticker = f"{code}.T"
        if ticker in sliced_data.columns.levels[0]:
            df_sliced = sliced_data[ticker].dropna()
            if not df_sliced.empty:
                mock_buffers[code] = RealtimeBuffer(code, df_sliced)
    if not df_1321_full.loc[:current_time].empty:
        mock_buffers['1321'] = RealtimeBuffer('1321', df_1321_full.loc[:current_time])

    regime = detect_market_regime(broker=None, buffer=mock_buffers.get('1321'), current_time_override=current_time, verbose=False)

    portfolio, account, actions, logs = manage_positions(
        portfolio, account, broker=broker, regime=regime,
        is_simulation=True, realtime_buffers=mock_buffers,
        current_time_override=current_time, verbose=False
    )
    trade_history.extend(logs)

    market_time = current_time.time()
    start_buy = datetime.strptime("09:30", "%H:%M").time()
    end_buy = datetime.strptime("14:00", "%H:%M").time()

    if start_buy <= market_time < end_buy and len(portfolio) < MAX_POSITIONS:
        if current_time.minute in [0, 15, 30, 45]:
            held_codes = [str(p['code']) for p in portfolio]
            scan_targets = [c for c in target_codes if str(c) not in held_codes]

            candidates = select_best_candidates(None, scan_targets, df_symbols, regime,
                                               realtime_buffers=mock_buffers, current_time_override=current_time, verbose=False)
            if candidates:
                best = candidates[0]
                best_df = mock_buffers[best['code']].df
                buy_price = float(best_df.iloc[-1]['Close'])
                atr = best['atr']
                risk_per_share = atr * (RANGE_ATR_STOP_LOSS if regime == "RANGE" else ATR_STOP_LOSS)
                ideal_shares = int(INITIAL_CASH * MAX_RISK_PER_TRADE // risk_per_share) if risk_per_share > 0 else 100
                max_shares_cash = int(account['cash'] // buy_price)
                raw_shares = min(ideal_shares, max_shares_cash)
                shares_to_buy = (raw_shares // 100) * 100
                if shares_to_buy == 0 and account['cash'] >= buy_price * 100:
                    fallback_shares = int(min(MIN_ALLOCATION_AMOUNT, account['cash'] * 0.3) // buy_price)
                    shares_to_buy = (fallback_shares // 100) * 100
                cost = buy_price * shares_to_buy
                if shares_to_buy >= 100 and account['cash'] >= cost:
                    portfolio.append({
                        "code": best['code'], "name": best['name'],
                        "buy_price": buy_price, "shares": shares_to_buy,
                        "buy_time": current_time, "atr": atr
                    })
                    account['cash'] -= cost
                    print(f"[{current_time.strftime('%m/%d %H:%M')}] BUY  {best['code']} {best['name']} {shares_to_buy}sh @ {buy_price:.1f}  ATR={atr:.1f}  stop_range={risk_per_share:.1f}  regime={regime}")

print("\n=== TRADE LOG ===")
for t in trade_history:
    profit_pct = t['profit_pct'] * 100
    mark = "WIN" if t['net_profit'] > 0 else "LOSS"
    print(f"[{mark}] {t['code']} {t['name']}: buy={t['buy_price']:.1f} -> sell={t['sell_price']:.1f} ({profit_pct:+.2f}%) reason={t['reason']} net={t['net_profit']:+.0f}")

final_stock_value = sum(float(mock_buffers[p['code']].df.iloc[-1]['Close']) * p['shares'] for p in portfolio if p['code'] in mock_buffers)
total = account['cash'] + final_stock_value
print(f"\nFinal: {total:,.0f} | Cash: {account['cash']:,.0f} | Stock: {final_stock_value:,.0f}")
print(f"Trades: {len(trade_history)} | Wins: {sum(1 for t in trade_history if t['net_profit'] > 0)}")
print(f"Held: {len(portfolio)}")
for p in portfolio:
    if p['code'] in mock_buffers:
        cur = float(mock_buffers[p['code']].df.iloc[-1]['Close'])
        pnl = (cur - p['buy_price']) / p['buy_price'] * 100
        print(f"  Holding {p['code']} {p['name']}: buy={p['buy_price']:.1f} cur={cur:.1f} pnl={pnl:+.2f}%")
