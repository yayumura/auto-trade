import pandas as pd
import numpy as np
import os
import sys
import concurrent.futures
import pickle

# Append current directory to sys.path
sys.path.append(os.getcwd())
from core.logic import calculate_all_technicals_v12
from backtest import run_backtest_v16_production
from core.logic import get_prime_tickers
from core.config import (
    INITIAL_CASH, EXIT_ON_SMA20_BREACH, SMA20_EXIT_BUFFER
)

def run_single_opt(params_pack):
    univ_indices, bundle_np, timeline, breadth_ratio, p = params_pack
    # --- Concentrated Elite Mode (V89.0) ---
    final_assets, trade_count, _, _ = run_backtest_v16_production(
        univ_indices=univ_indices,
        bundle_np=bundle_np,
        timeline=timeline,
        breadth_ratio=breadth_ratio,
        initial_cash=INITIAL_CASH,
        max_pos=p['max_pos'],
        sl_mult=p['sl'],
        tp_mult=p['tp'],
        leverage_rate=p['leverage'],
        breadth_threshold=p['breadth'],
        max_hold_days=p['max_hold_days'],
        use_sma_exit=EXIT_ON_SMA20_BREACH, # Sync with production config
        exit_buffer=SMA20_EXIT_BUFFER      # Sync with production config
    )
    return {**p, "final": final_assets, "trades": trade_count}

def optimize_jp_imperial(cache_path):
    print(f"Loading JP Mega-Data Cache: {cache_path}")
    with open(cache_path, 'rb') as f:
        all_data = pickle.load(f)

    new_cols = []
    for col in all_data.columns:
        ticker, field = col[0], col[1]
        if isinstance(field, tuple):
            field = field[0]
        new_cols.append((ticker, field))
    all_data.columns = pd.MultiIndex.from_tuples(new_cols)

    bundle = {
        'Open': all_data.xs('Open', axis=1, level=1),
        'High': all_data.xs('High', axis=1, level=1),
        'Low': all_data.xs('Low', axis=1, level=1),
        'Close': all_data.xs('Close', axis=1, level=1),
        'Volume': all_data.xs('Volume', axis=1, level=1)
    }
    
    indicator_bundle = calculate_all_technicals_v12(all_data)
    bundle.update(indicator_bundle)
    
    tickers = bundle['Close'].columns.tolist()
    prime_ref = get_prime_tickers()
    elite_indices = [i for i, t in enumerate(tickers) if t in prime_ref]
    
    breadth_matrix = bundle['Close'].values[:, elite_indices] > bundle['SMA100'].values[:, elite_indices]
    breadth_series = np.nanmean(breadth_matrix.astype(float), axis=1)
    
    univ_indices = np.array([i for i, t in enumerate(tickers) if t not in {'1306.T', '1321.T'}], dtype=int)
    bundle_np = {k: v.values for k, v in bundle.items()}
    bundle_np['tickers'] = list(tickers)
    timeline = bundle['Close'].index
    
    # --- Aggressive Mean Reversion Search ---
    
    # --- Sovereign Optimization Grid (V131.3) ---
    param_grid = {
        'breadth': [0.3],
        'sl_mult': [3.0, 4.5],
        'tp_mult': [40.0, 60.0, 80.0],
        'max_pos': [3, 4, 5],
        'leverage_rate': [2.0, 2.5],
        'max_hold_days': [30]
    }

    grid = []
    for b in param_grid['breadth']:           
        for sl in param_grid['sl_mult']:          
            for tp in param_grid['tp_mult']: 
                for p_size in param_grid['max_pos']:
                    for lev in param_grid['leverage_rate']:
                        for mhd in param_grid['max_hold_days']: 
                            grid.append({
                                "breadth": b, "sl": sl, "tp": tp, 
                                "max_pos": p_size, "leverage": lev, "max_hold_days": mhd
                            })
    
    print(f"[CONCENTRATED_OPT] Starting Grid Search ({len(grid)} combinations)...")

    
    results = []
    with concurrent.futures.ProcessPoolExecutor() as executor:
        tasks = []
        for p in grid:
            tasks.append((univ_indices, bundle_np, timeline, breadth_series, p))
        results = list(executor.map(run_single_opt, tasks))
    
    df_res = pd.DataFrame(results)
    df_res['return_pct'] = (df_res['final'] / INITIAL_CASH - 1) * 100
    
    # Sort by performance
    df_res = df_res.sort_values('return_pct', ascending=False)
    
    # Save to CSV for reliability
    df_res.to_csv("opt_results.csv", index=False)
    
    print("\n" + "="*80)
    print("SHORT SWING (MEAN REVERSION) RESULTS")
    print("="*80)
    print(df_res.head(30).to_string(index=False))
    print("="*80 + "\n")
    
    best = df_res.iloc[0]
    print(f"BEST SHORT SWING CONFIGURATION:")
    print(f" - Max Positions:     {best['max_pos']:.0f}")
    print(f" - Breadth Threshold: {best['breadth']:.2f}")
    print(f" - Stop Loss:         ATR * {best['sl']}")
    print(f" - Profit Target:     ATR * {best['tp']}")
    print(f" - Max Hold Days:     {best['max_hold_days']:.0f}")
    print(f"Estimated 5-Year Return: {best['return_pct']:+.2f}% ({best['trades']} trades)")
    print("="*80)


if __name__ == "__main__":
    if not os.path.exists("data_cache"):
        print("❌ Error: Please run from the project root directory.")
        sys.exit(1)
        
    optimize_jp_imperial("data_cache/jp_broad/jp_mega_cache.pkl")
