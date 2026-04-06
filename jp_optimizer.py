import pandas as pd
import numpy as np
import os
import sys
import concurrent.futures

# Append current directory to sys.path
sys.path.append(os.getcwd())
from core.logic import calculate_all_technicals_v12
from backtest import run_backtest_v16_production
from jp_scanner import get_prime_tickers

def run_single_opt(params_pack):
    univ_indices, bundle_np, timeline, breadth_ratio, p = params_pack
    final_assets, trade_count, _ = run_backtest_v16_production(
        univ_indices=univ_indices,
        bundle_np=bundle_np,
        timeline=timeline,
        breadth_ratio=breadth_ratio,
        initial_cash=10000000,
        max_pos=p['max_pos'],
        sl_mult=p['sl'],
        tp_mult=p['tp'],
        breadth_threshold=p['breadth']
    )
    return {**p, "final": final_assets, "trades": trade_count}

def optimize_jp_imperial(cache_path):
    print(f"📡 Loading JP Mega-Data Cache: {cache_path}")
    all_data = pd.read_pickle(cache_path)
    all_data = all_data.loc[:, ~all_data.columns.duplicated()]
    
    # Calculate Imperial V17.0 Technicals (SMA5/20/100/ATR)
    # Note: Using v12 calculator but logic inside it provides standard SMAs
    bundle = calculate_all_technicals_v12(all_data)
    
    # V17.0 Imperial Breadth (SMA100 base)
    tickers = bundle['Close'].columns.tolist()
    prime_ref = get_prime_tickers()
    elite_indices = [i for i, t in enumerate(tickers) if t in prime_ref]
    
    # Calculate Breadth: % of Prime tickers above SMA100
    breadth_matrix = bundle['Close'].values[:, elite_indices] > bundle['SMA100'].values[:, elite_indices]
    breadth_series = np.nanmean(breadth_matrix.astype(float), axis=1)
    
    univ_indices = np.array([i for i, t in enumerate(tickers) if t not in {'1306.T', '1321.T'}], dtype=int)
    bundle_np = {k: v.values for k, v in bundle.items()}
    timeline = bundle['Close'].index
    
    # Imperial Grid Search
    grid = []
    # Testing for the "Perfect Balance"
    for b in [0.35, 0.40, 0.45]:           # Market Tone
        for sl in [4.0, 5.0, 6.0]:          # Tight vs Loose Stop
            for tp in [15.0, 20.0, 25.0]:    # Moon Shot vs Steady Profit
                for p_size in [5, 10]:       # Concentration vs Diversification
                    grid.append({
                        "breadth": b, "sl": sl, "tp": tp, "max_pos": p_size
                    })
    
    print(f"🚀 [IMPERIAL_OPT] Starting Multi-Process Grid Search ({len(grid)} combinations)...")
    
    results = []
    with concurrent.futures.ProcessPoolExecutor() as executor:
        tasks = [(univ_indices, bundle_np, timeline, breadth_series, p) for p in grid]
        results = list(executor.map(run_single_opt, tasks))
    
    df_res = pd.DataFrame(results)
    df_res['return_pct'] = (df_res['final'] / 10000000 - 1) * 100
    
    # Sort by performance
    df_res = df_res.sort_values('return_pct', ascending=False)
    
    print("\n" + "="*80)
    print("🏆 IMPERIAL ORACLE V17.0 - OPTIMIZED PARAMETER RANKING")
    print("="*80)
    print(df_res.head(15).to_string(index=False))
    print("="*80 + "\n")
    
    best = df_res.iloc[0]
    print(f"🥇 BEST CONFIGURATION DISCOVERED:")
    print(f" - Max Positions: {best['max_pos']:.0f}")
    print(f" - Breadth Threshold: {best['breadth']:.2f}")
    print(f" - Stop Loss: ATR * {best['sl']}")
    print(f" - Profit Target: ATR * {best['tp']}")
    print(f"📈 Estimated 5-Year Return: {best['return_pct']:+.2f}% ({best['trades']} trades)")
    print("="*80)

if __name__ == "__main__":
    optimize_jp_imperial("data_cache/jp_broad/jp_mega_cache.pkl")
