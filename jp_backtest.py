import pandas as pd
import numpy as np
import os
import sys
import pickle

# Append current directory to sys.path
sys.path.append(os.getcwd())

from core.config import INITIAL_CASH, SLIPPAGE_RATE
from core.monthly_rotation_strategy import (
    build_rotation_backtest_inputs_from_cache,
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
    tickers = list(bundle_np.get("tickers", []))
    univ_indices = np.array([
        i for i, ticker in enumerate(tickers)
        if str(ticker).endswith(".T") and ticker not in {"1306.T", "1321.T"}
    ], dtype=int)
    breadth_series = prepared["breadth_series"]
    margin_cache = load_margin_cache()

    # Verify 1321.T inclusion
    if '1321.T' in bundle['Close'].columns:
        print("1321.T Found and Normalized.")
    else:
        print("1321.T not found in primary close columns!")

    print("Calculating Technical Indicators for JP Universe...")
    
    from backtest import run_backtest_v16_production

    print("\nStarting Japan IMPERIAL ORACLE Backtest (Day Trade Production)...")
    final_assets, trade_count, monthly_assets, trade_results, daily_stats = run_backtest_v16_production(
        univ_indices=univ_indices,
        bundle_np=bundle_np,
        timeline=timeline,
        breadth_ratio=breadth_series,
        initial_cash=INITIAL_CASH,
        slippage=SLIPPAGE_RATE,
        explicit_trade_cost=0.0,
        profit_tax_rate=0.0,
        return_daily_stats=True,
        verbose=False
    )

    # Report
    print("="*50)
    print("JAPAN IMPERIAL ORACLE PERFORMANCE (DAY TRADE PRODUCTION)")
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
    if daily_stats:
        day_values = list(daily_stats.values())
        plus_days = sum(1 for item in day_values if item["day_pnl"] > 0)
        flat_days = sum(1 for item in day_values if item["day_pnl"] == 0)
        minus_days = sum(1 for item in day_values if item["day_pnl"] < 0)
        active_days = plus_days + minus_days
        plus_day_rate = (plus_days / active_days * 100.0) if active_days > 0 else 0.0
        worst_day = min(item["day_pnl"] for item in day_values)
        best_day = max(item["day_pnl"] for item in day_values)
        print(f"PLUS DAYS:     {plus_days}")
        print(f"MINUS DAYS:    {minus_days}")
        print(f"FLAT DAYS:     {flat_days}")
        print(f"PLUS DAY RATE: {plus_day_rate:.2f}%")
        print(f"BEST DAY:      Y{best_day:,.0f}")
        print(f"WORST DAY:     Y{worst_day:,.0f}")

        warmup_start = "2022-03-01"
        week_stats = {}
        month_active = {}
        month_total = {}
        for day_key, item in daily_stats.items():
            if day_key < warmup_start:
                continue
            week_key = np.datetime64(day_key).astype("datetime64[W]").astype(str)
            day_pnl = float(item["day_pnl"])
            week_record = week_stats.setdefault(
                week_key,
                {
                    "start_equity": float(item["equity"]) - day_pnl,
                    "pnl": 0.0,
                },
            )
            week_record["pnl"] += day_pnl
            month_key = day_key[:7]
            month_total[month_key] = month_total.get(month_key, 0) + 1
            if int(item["trade_count"]) > 0:
                month_active[month_key] = month_active.get(month_key, 0) + 1
        month_rates = [
            month_active.get(month_key, 0) / total
            for month_key, total in month_total.items()
            if total > 0
        ]
        if month_rates:
            months_ge_two_thirds = sum(1 for rate in month_rates if rate >= (2.0 / 3.0))
            print(f"AVG MONTH ACTIVE RATE: {np.mean(month_rates) * 100.0:.2f}%")
            print(f"MED MONTH ACTIVE RATE: {np.median(month_rates) * 100.0:.2f}%")
            print(f"MONTHS >= 50% ACTIVE: {sum(1 for rate in month_rates if rate >= 0.5)}/{len(month_rates)}")
            print(f"MONTHS >= 2/3 ACTIVE: {months_ge_two_thirds}/{len(month_rates)}")
        if week_stats:
            plus_1pct_weeks = sum(
                1
                for item in week_stats.values()
                if item["pnl"] >= (item["start_equity"] * 0.01)
            )
            positive_weeks = sum(1 for item in week_stats.values() if item["pnl"] > 0)
            print(f"WEEKS >= +1%:  {plus_1pct_weeks}/{len(week_stats)}")
            print(f"POSITIVE WEEKS: {positive_weeks}/{len(week_stats)}")
            print(f"TARGET CHECK:   active-month 2/3={'PASS' if month_rates and np.mean(month_rates) >= (2.0 / 3.0) else 'MISS'} | weekly +1%={'PASS' if plus_1pct_weeks == len(week_stats) else 'MISS'}")
    
    print("-" * 50)
    
    print("HISTORICAL EQUITY PROGRESS:")
    sorted_months = sorted(monthly_assets.keys())
    for m in sorted_months:
        val = monthly_assets[m]
        print(f" {m:15} | Y{val:12,.0f}")
    print("="*50 + "\n")

if __name__ == "__main__":
    run_jp_broad_backtest('data_cache/jp_broad/jp_mega_cache.pkl')
