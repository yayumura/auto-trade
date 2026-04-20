import pandas as pd
import numpy as np
import os
import sys
import pickle

# Append current directory to sys.path
sys.path.append(os.getcwd())

from core.config import INITIAL_CASH, SLIPPAGE_RATE
from core.monthly_rotation_strategy import (
    PROD_MONTHLY_ROTATION_CONFIG,
    build_rotation_backtest_inputs_from_cache,
    get_prod_monthly_rotation_backtest_params,
)
from core.jquants_margin_cache import load_margin_cache

def run_jp_broad_backtest(cache_path):
    if not os.path.exists(cache_path):
        print(f"Error: Cache not found at {cache_path}")
        return

    print("WARNING: Ensure your dataset includes delisted tickers to avoid survivorship bias.")
    print(f"Loading JP Mega-Data Cache: {cache_path}")
    with open(cache_path, 'rb') as f:
        data = pickle.load(f)

    prepared = build_rotation_backtest_inputs_from_cache(data)
    bundle = prepared["bundle"]
    bundle_np = prepared["bundle_np"]
    timeline = prepared["timeline"]
    univ_indices = prepared["univ_indices"]
    breadth_series = prepared["breadth_series"]
    margin_cache = load_margin_cache()

    # Verify 1321.T inclusion
    if '1321.T' in bundle['Close'].columns:
        print("1321.T Found and Normalized.")
    else:
        print("1321.T not found in primary close columns!")

    print("Calculating Technical Indicators for JP Universe...")
    
    # RUN BACKTEST (V17.0 IMPERIAL ORACLE SYNC)
    from backtest import run_backtest_v19_monthly_rotation
    
    print(f"\nStarting Japan IMPERIAL ORACLE Backtest ({PROD_MONTHLY_ROTATION_CONFIG.version_label})...")
    final_assets, trade_count, monthly_assets, trade_results = run_backtest_v19_monthly_rotation(
        univ_indices=univ_indices,
        bundle_np=bundle_np,
        timeline=timeline,
        breadth_ratio=breadth_series,
        initial_cash=INITIAL_CASH,
        slippage=SLIPPAGE_RATE,
        eligible_codes_by_date=margin_cache,
        **get_prod_monthly_rotation_backtest_params(),
        verbose=False
    )

    # Report
    print("="*50)
    print(f"JAPAN IMPERIAL ORACLE PERFORMANCE ({PROD_MONTHLY_ROTATION_CONFIG.version_label.upper()})")
    print("="*50)
    active_start = sorted(monthly_assets.keys())[0] if monthly_assets else str(timeline[0].date())
    print(f"DATA WINDOW:   {timeline[0].date()} to {timeline[-1].date()}")
    print(f"ACTIVE TEST:   {active_start} to {timeline[-1].date()}")
    print(f"INITIAL CASH:  Y{INITIAL_CASH:,.0f}")
    print(f"FINAL EQUITY:  Y{final_assets:,.0f}")
    print(f"TOTAL RETURN:  {((final_assets/INITIAL_CASH)-1)*100:+.2f}%")
    print(f"CLOSED TRADES: {trade_count}")
    
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
