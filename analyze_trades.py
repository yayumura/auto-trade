import pandas as pd
import sys, os
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

# Import from current project
from core.logic import select_best_candidates, manage_positions, RealtimeBuffer, detect_market_regime
from core.sim_broker import SimulationBroker
from core.config import INITIAL_CASH, DATA_FILE, JST, MAX_POSITIONS
import yfinance as yf

def analyze_all_trades():
    test_universe = ["8306", "7203", "9101", "8058", "6758", "4063", "9501", "6723", "7201", "8411", "9503"]
    tickers = [f"{code}.T" for code in test_universe] + ["1321.T"]
    
    print("Downloading full data for analysis...")
    full_data = yf.download(tickers, period="60d", interval="15m", group_by='ticker', auto_adjust=True, progress=False)
    
    if full_data.index.tzinfo is None:
        full_data.index = full_data.index.tz_localize('UTC').tz_convert(JST)
    else:
        full_data.index = full_data.index.tz_convert(JST)

    df_1321_full = full_data['1321.T'].dropna()
    df_symbols = pd.read_csv(DATA_FILE)
    all_times = df_1321_full.index.unique().sort_values()
    
    # Analyze the same period as the user (Last 500 steps)
    test_start_idx = max(0, len(all_times) - 500)
    timeline = all_times[test_start_idx:]
    
    account = {"cash": INITIAL_CASH}
    portfolio = []
    trade_history = []
    broker = SimulationBroker()
    
    print(f"Analyzing trades from {timeline[0]} to {timeline[-1]}...")
    
    for current_time in timeline:
        mock_buffers = {}
        sliced_data = full_data.loc[:current_time]
        for code in test_universe:
            ticker = f"{code}.T"
            if ticker in sliced_data.columns.levels[0]:
                df_sliced = sliced_data[ticker].dropna()
                if not df_sliced.empty:
                    mock_buffers[code] = RealtimeBuffer(code, df_sliced)
        
        if not df_1321_full.loc[:current_time].empty:
            mock_buffers['1321'] = RealtimeBuffer('1321', df_1321_full.loc[:current_time])

        regime = detect_market_regime(None, mock_buffers.get('1321'), current_time, verbose=False)
        
        portfolio, account, actions, logs = manage_positions(
            portfolio, account, broker, regime, True, mock_buffers, current_time, verbose=False
        )
        trade_history.extend(logs)
        
        # Entry Logic (Simplified for analysis)
        if len(portfolio) < MAX_POSITIONS:
            market_time = current_time.time()
            if datetime.strptime("09:30", "%H:%M").time() <= market_time < datetime.strptime("14:00", "%H:%M").time():
                if current_time.minute in [0, 15, 30, 45]:
                   held_codes = [str(p['code']) for p in portfolio]
                   scan_targets = [c for c in test_universe if str(c) not in held_codes]
                   candidates = select_best_candidates(None, scan_targets, df_symbols, regime, mock_buffers, current_time, verbose=False)
                   
                   if candidates:
                       best = candidates[0]
                       buy_price = float(mock_buffers[best['code']].df.iloc[-1]['Close'])
                       portfolio.append({
                           "code": best['code'], "name": best['name'],
                           "buy_price": buy_price, "shares": 100, # Fixed for simpler analysis
                           "buy_time": current_time, "atr": best['atr']
                       })
                       account['cash'] -= buy_price * 100

    # Report
    df_trades = pd.DataFrame(trade_history)
    if df_trades.empty:
        print("No trades found.")
        return

    print("\n--- Trade Analysis Report ---")
    print(f"Total Trades: {len(df_trades)}")
    print(f"Win Rate: {(df_trades['profit_pct'] > 0).sum() / len(df_trades) * 100:.1f}%")
    print(f"Avg Profit%: {df_trades['profit_pct'].mean() * 100:.2f}%")
    print(f"Max Loss%: {df_trades['profit_pct'].min() * 100:.2f}%")
    print(f"Max Win%: {df_trades['profit_pct'].max() * 100:.2f}%")
    
    print("\n--- Exit Reasons ---")
    print(df_trades['reason'].value_counts())
    
    # Calculate Avg Profit per Reason
    reason_stats = df_trades.groupby('reason')['profit_pct'].agg(['mean', 'count']).sort_values('mean', ascending=False)
    print("\n--- Stats by Reason ---")
    print(reason_stats)

if __name__ == "__main__":
    analyze_all_trades()
