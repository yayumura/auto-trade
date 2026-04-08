import pandas as pd
import numpy as np
import os
import sys
import pickle

# Append current directory to sys.path
sys.path.append(os.getcwd())
from core.logic import calculate_all_technicals_v12

from core.config import (
    INITIAL_CASH, MAX_POSITIONS, LEVERAGE_RATE, ATR_STOP_LOSS, TARGET_PROFIT_MULT, BREADTH_THRESHOLD, EXIT_ON_SMA20_BREACH, SMA20_EXIT_BUFFER
)

def run_jp_broad_backtest(cache_path):
    if not os.path.exists(cache_path):
        print(f"Error: Cache not found at {cache_path}")
        return

    print("WARNING: Ensure your dataset includes delisted tickers to avoid survivorship bias.")
    print(f"Loading JP Mega-Data Cache: {cache_path}")
    with open(cache_path, 'rb') as f:
        data = pickle.load(f)

    # REPAIR DATA: Flatten MultiIndex columns if necessary
    # Example columns: ('3836.T', 'Open') or ('1321.T', ('Open', '1321.T'))
    new_cols = []
    for col in data.columns:
        ticker, field = col[0], col[1]
        if isinstance(field, tuple): # Handle the ('Open', '1321.T') case
            field = field[0]
        new_cols.append((ticker, field))
    data.columns = pd.MultiIndex.from_tuples(new_cols)

    # Extract clean bundle
    bundle = {
        'Open': data.xs('Open', axis=1, level=1),
        'High': data.xs('High', axis=1, level=1),
        'Low': data.xs('Low', axis=1, level=1),
        'Close': data.xs('Close', axis=1, level=1),
        'Volume': data.xs('Volume', axis=1, level=1),
    }

    # Verify 1321.T inclusion
    if '1321.T' in bundle['Close'].columns:
        print("1321.T Found and Normalized.")
    else:
        print("1321.T not found in primary close columns!")

    # Universe Selection
    all_tickers = bundle['Close'].columns
    univ_indices = np.array([i for i, t in enumerate(all_tickers) if t not in {'1306.T', '1321.T'}], dtype=int)
    
    # Bundle Tickers for Index Lookup in engine
    bundle_np = {k: v.values for k, v in bundle.items()}
    bundle_np['tickers'] = list(all_tickers)

    # Indicators
    print("Calculating Technical Indicators for JP Universe...")
    indicator_bundle = calculate_all_technicals_v12(data) # Pass full dataframe
    bundle_np.update({k: v.values for k, v in indicator_bundle.items()})

    # Breadth (Prime-Exclusive SMA100 Sync V17.0)
    from core.logic import get_prime_tickers
    prime_ref = get_prime_tickers()
    elite_indices = [i for i, t in enumerate(all_tickers) if t in prime_ref]
    
    breadth_matrix = bundle['Close'].values[:, elite_indices] > indicator_bundle['SMA100'].values[:, elite_indices]
    breadth_series = np.nanmean(breadth_matrix.astype(float), axis=1)
    timeline = bundle['Close'].index
    
    # RUN BACKTEST (V17.0 IMPERIAL ORACLE SYNC)
    from backtest import run_backtest_v16_production
    
    print("\nStarting Japan IMPERIAL ORACLE Backtest (V20.1 Premium Reversion Sync)...")
    final_assets, trade_count, monthly_assets, trade_results = run_backtest_v16_production(
        univ_indices=univ_indices,
        bundle_np=bundle_np,
        timeline=timeline,
        breadth_ratio=breadth_series,
        initial_cash=INITIAL_CASH,
        max_pos=4,
        sl_mult=3.0,
        tp_mult=60.0,
        leverage_rate=2.0,
        breadth_threshold=0.3,
        slippage=0.001,
        max_hold_days=5,
        use_sma_exit=False,
        verbose=False
    )

    # Report
    print("="*50)
    print("JAPAN IMPERIAL ORACLE PERFORMANCE (V17.0)")
    print("="*50)
    print(f"PERIOD:        {timeline[0].date()} to {timeline[-1].date()}")
    print(f"INITIAL CASH:  Y{INITIAL_CASH:,.0f}")
    print(f"FINAL EQUITY:  Y{final_assets:,.0f}")
    print(f"TOTAL RETURN:  {((final_assets/INITIAL_CASH)-1)*100:+.2f}%")
    print(f"TOTAL TRADES:  {trade_count}")
    
    if trade_count > 0:
        wins = [r for r in trade_results if r > 0]
        losses = [r for r in trade_results if r <= 0]
        win_rate = len(wins) / trade_count * 100
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        
        print(f"WIN RATE:      {win_rate:.2f}%")
        print(f"PROFIT FACTOR: {pf:.2f}")
        print(f"AVERAGE WIN:   Y{avg_win:,.0f}")
        print(f"AVERAGE LOSS:  Y{avg_loss:,.0f}")
    
    print("-" * 50)
    
    print("HISTORICAL EQUITY PROGRESS:")
    sorted_months = sorted(monthly_assets.keys())
    for m in sorted_months:
        val = monthly_assets[m]
        print(f" {m:15} | Y{val:12,.0f}")
    print("="*50 + "\n")

if __name__ == "__main__":
    run_jp_broad_backtest('data_cache/jp_broad/jp_mega_cache.pkl')
