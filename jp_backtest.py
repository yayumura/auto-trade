import argparse
import os
import pickle
import sys

import numpy as np
import pandas as pd

# Append current directory to sys.path
sys.path.append(os.getcwd())

from backtest import run_backtest_v16_production
from core.config import INITIAL_CASH, SLIPPAGE_RATE
from core.logic import get_daytrade_week_key
from core.monthly_rotation_strategy import build_rotation_backtest_inputs_from_cache


WARMUP_START = "2022-03-01"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the JP day-trade backtest and optionally report a trailing holdout window."
    )
    parser.add_argument(
        "--cache-path",
        default="data_cache/jp_broad/jp_mega_cache.pkl",
        help="Path to the cached JP market data pickle.",
    )
    parser.add_argument(
        "--holdout-months",
        type=int,
        default=0,
        help=(
            "Exclude the latest trailing N calendar months from optimization review and "
            "report them separately as a holdout window. "
            "Example: with latest data 2026-04-03 and --holdout-months 1, holdout is 2026-03-04 to 2026-04-03."
        ),
    )
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Refresh the JP cache before loading it, then derive train/holdout from the refreshed latest date.",
    )
    parser.add_argument(
        "--refresh-start-date",
        default="",
        help="Optional YYYYMMDD override for cache refresh start date.",
    )
    parser.add_argument(
        "--refresh-overlap-days",
        type=int,
        default=7,
        help="When refreshing against an existing cache, re-fetch this many trailing days before the cached latest day.",
    )
    return parser.parse_args()


def _refresh_cache_if_requested(cache_path, refresh_cache=False, refresh_start_date="", refresh_overlap_days=7):
    if not refresh_cache:
        return

    print("Refreshing JP cache before validation...")
    from jp_jquants_fetcher_v2 import fetch_jquants_v2_turbo_revelation

    fetch_jquants_v2_turbo_revelation(
        output_path=cache_path,
        start_date=refresh_start_date or None,
        refresh_overlap_days=refresh_overlap_days,
    )

def _resolve_holdout_start_date(timeline, holdout_months):
    if holdout_months is None or int(holdout_months) <= 0:
        return None
    last_date = pd.Timestamp(timeline[-1]).normalize()
    cutoff_exclusive = last_date - pd.DateOffset(months=int(holdout_months))
    holdout_days = [
        pd.Timestamp(ts).strftime("%Y-%m-%d")
        for ts in timeline
        if pd.Timestamp(ts).normalize() > cutoff_exclusive
    ]
    return holdout_days[0] if holdout_days else None


def _filter_trade_log_window(trade_log, start_date=None, end_date=None):
    filtered = []
    for item in trade_log:
        day_key = str(item["day_key"])
        if start_date is not None and day_key < start_date:
            continue
        if end_date is not None and day_key > end_date:
            continue
        filtered.append(item)
    return filtered


def _build_global_period_boundaries(day_keys):
    week_bounds = {}
    month_bounds = {}
    for day_key in sorted(day_keys):
        week_key = get_daytrade_week_key(pd.Timestamp(day_key))
        week_record = week_bounds.setdefault(week_key, {"first": day_key, "last": day_key})
        week_record["last"] = day_key

        month_key = day_key[:7]
        month_record = month_bounds.setdefault(month_key, {"first": day_key, "last": day_key})
        month_record["last"] = day_key
    return week_bounds, month_bounds


def _summarize_window(
    daily_stats,
    trade_log,
    label,
    start_date=None,
    end_date=None,
    warmup_start=WARMUP_START,
    global_day_keys=None,
):
    window_day_keys = [
        day_key
        for day_key in sorted(daily_stats.keys())
        if (start_date is None or day_key >= start_date)
        and (end_date is None or day_key <= end_date)
    ]
    if not window_day_keys:
        return None

    day_key_set = set(window_day_keys)
    boundary_day_keys = global_day_keys if global_day_keys is not None else daily_stats.keys()
    week_bounds, month_bounds = _build_global_period_boundaries(boundary_day_keys)
    window_trades = _filter_trade_log_window(trade_log, start_date=start_date, end_date=end_date)
    trade_results = [float(item["net_pnl"]) for item in window_trades]

    first_day = window_day_keys[0]
    last_day = window_day_keys[-1]
    start_equity = float(daily_stats[first_day]["equity"]) - float(daily_stats[first_day]["day_pnl"])
    final_equity = float(daily_stats[last_day]["equity"])
    total_return_pct = ((final_equity / start_equity) - 1.0) * 100.0 if start_equity > 0 else 0.0

    wins = [pnl for pnl in trade_results if pnl > 0]
    losses = [pnl for pnl in trade_results if pnl <= 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    average_win = sum(wins) / len(wins) if wins else 0.0
    average_loss = sum(losses) / len(losses) if losses else 0.0
    win_rate = (len(wins) / len(trade_results) * 100.0) if trade_results else 0.0

    plus_days = 0
    minus_days = 0
    flat_days = 0
    active_days = 0
    worst_day = None
    best_day = None
    period_active_trade_days = 0

    week_stats = {}
    month_totals = {}
    month_active = {}

    for day_key in window_day_keys:
        item = daily_stats[day_key]
        day_pnl = float(item["day_pnl"])
        day_trade_count = int(item["trade_count"])

        if day_pnl > 0:
            plus_days += 1
        elif day_pnl < 0:
            minus_days += 1
        else:
            flat_days += 1

        if day_trade_count > 0:
            period_active_trade_days += 1
        if day_pnl != 0:
            active_days += 1

        worst_day = day_pnl if worst_day is None else min(worst_day, day_pnl)
        best_day = day_pnl if best_day is None else max(best_day, day_pnl)

        if day_key < warmup_start:
            continue

        month_key = day_key[:7]
        month_totals[month_key] = month_totals.get(month_key, 0) + 1
        if day_trade_count > 0:
            month_active[month_key] = month_active.get(month_key, 0) + 1

        week_key = get_daytrade_week_key(pd.Timestamp(day_key))
        week_bound = week_bounds[week_key]
        # Segmented weekly stats are counted only when the full ISO week is inside the window.
        if week_bound["first"] not in day_key_set or week_bound["last"] not in day_key_set:
            continue
        week_record = week_stats.setdefault(
            week_key,
            {
                "start_equity": float(item["equity"]) - day_pnl,
                "pnl": 0.0,
            },
        )
        week_record["pnl"] += day_pnl

    full_month_rates = []
    for month_key, total in sorted(month_totals.items()):
        month_bound = month_bounds[month_key]
        # Segmented monthly stats are counted only when the full calendar month is inside the window.
        if month_bound["first"] not in day_key_set or month_bound["last"] not in day_key_set:
            continue
        if total <= 0:
            continue
        full_month_rates.append(month_active.get(month_key, 0) / total)

    plus_day_rate = (plus_days / active_days * 100.0) if active_days > 0 else 0.0
    trade_day_rate = (period_active_trade_days / len(window_day_keys) * 100.0) if window_day_keys else 0.0
    plus_1pct_weeks = sum(
        1 for item in week_stats.values() if item["pnl"] >= (item["start_equity"] * 0.01)
    )
    positive_weeks = sum(1 for item in week_stats.values() if item["pnl"] > 0)

    return {
        "label": label,
        "start_date": first_day,
        "end_date": last_day,
        "start_equity": start_equity,
        "final_equity": final_equity,
        "total_return_pct": total_return_pct,
        "trade_count": len(trade_results),
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "average_win": average_win,
        "average_loss": average_loss,
        "plus_days": plus_days,
        "minus_days": minus_days,
        "flat_days": flat_days,
        "plus_day_rate": plus_day_rate,
        "trade_day_rate": trade_day_rate,
        "best_day": best_day if best_day is not None else 0.0,
        "worst_day": worst_day if worst_day is not None else 0.0,
        "full_month_rates": full_month_rates,
        "plus_1pct_weeks": plus_1pct_weeks,
        "positive_weeks": positive_weeks,
        "week_count": len(week_stats),
    }


def _print_window_summary(summary):
    print("-" * 50)
    print(f"{summary['label']} WINDOW")
    print("-" * 50)
    print(f"WINDOW:        {summary['start_date']} to {summary['end_date']}")
    print(f"START EQUITY:  Y{summary['start_equity']:,.0f}")
    print(f"FINAL EQUITY:  Y{summary['final_equity']:,.0f}")
    print(f"TOTAL RETURN:  {summary['total_return_pct']:+.2f}%")
    print(f"CLOSED TRADES: {summary['trade_count']}")

    if summary["trade_count"] > 0:
        print(f"WIN RATE:      {summary['win_rate']:.2f}%")
        print(f"PROFIT FACTOR: {summary['profit_factor']:.2f}")
        print(f"AVERAGE WIN:   Y{summary['average_win']:,.0f}")
        print(f"AVERAGE LOSS:  Y{summary['average_loss']:,.0f}")

    print(f"TRADE DAY RATE:{summary['trade_day_rate']:.2f}%")
    print(f"PLUS DAYS:     {summary['plus_days']}")
    print(f"MINUS DAYS:    {summary['minus_days']}")
    print(f"FLAT DAYS:     {summary['flat_days']}")
    print(f"PLUS DAY RATE: {summary['plus_day_rate']:.2f}%")
    print(f"BEST DAY:      Y{summary['best_day']:,.0f}")
    print(f"WORST DAY:     Y{summary['worst_day']:,.0f}")

    if summary["full_month_rates"]:
        month_rates = summary["full_month_rates"]
        months_ge_two_thirds = sum(1 for rate in month_rates if rate >= (2.0 / 3.0))
        months_ge_three_quarters = sum(1 for rate in month_rates if rate >= 0.75)
        print(f"AVG MONTH ACTIVE RATE: {np.mean(month_rates) * 100.0:.2f}%")
        print(f"MED MONTH ACTIVE RATE: {np.median(month_rates) * 100.0:.2f}%")
        print(f"MONTHS >= 50% ACTIVE: {sum(1 for rate in month_rates if rate >= 0.5)}/{len(month_rates)}")
        print(f"MONTHS >= 2/3 ACTIVE: {months_ge_two_thirds}/{len(month_rates)}")
        print(f"MONTHS >= 3/4 ACTIVE: {months_ge_three_quarters}/{len(month_rates)}")
    else:
        print("AVG MONTH ACTIVE RATE: N/A (window does not contain a full calendar month)")
        print("MONTHS >= 3/4 ACTIVE: N/A")

    if summary["week_count"] > 0:
        print(f"WEEKS >= +1%:  {summary['plus_1pct_weeks']}/{summary['week_count']}")
        print(f"POSITIVE WEEKS: {summary['positive_weeks']}/{summary['week_count']}")
    else:
        print("WEEKS >= +1%:  N/A (window does not contain a full ISO week)")
        print("POSITIVE WEEKS: N/A")


def _print_report(full_summary, split_summaries=None, monthly_assets=None):
    print("=" * 50)
    print("JAPAN IMPERIAL ORACLE PERFORMANCE (DAY TRADE PRODUCTION)")
    print("=" * 50)
    print(f"DATA WINDOW:   {full_summary['start_date']} to {full_summary['end_date']}")
    print(f"ACTIVE TEST:   {full_summary['start_date']} to {full_summary['end_date']}")
    print(f"INITIAL CASH:  Y{INITIAL_CASH:,.0f}")
    _print_window_summary(full_summary)

    if split_summaries:
        print("-" * 50)
        print("NOTE: segmented weekly/monthly metrics count only full ISO weeks / full calendar months fully inside each window.")
        for item in split_summaries:
            _print_window_summary(item)

    print("-" * 50)
    print("HISTORICAL EQUITY PROGRESS:")
    for month_key in sorted(monthly_assets.keys()):
        print(f" {month_key:15} | Y{monthly_assets[month_key]:12,.0f}")
    print("=" * 50 + "\n")


def run_jp_broad_backtest(
    cache_path,
    holdout_months=0,
    refresh_cache=False,
    refresh_start_date="",
    refresh_overlap_days=7,
):
    _refresh_cache_if_requested(
        cache_path=cache_path,
        refresh_cache=refresh_cache,
        refresh_start_date=refresh_start_date,
        refresh_overlap_days=refresh_overlap_days,
    )
    if not os.path.exists(cache_path):
        print(f"Error: Cache not found at {cache_path}")
        return 1

    print("WARNING: Ensure your dataset includes delisted tickers to avoid survivorship bias.")
    print(f"Loading JP Mega-Data Cache: {cache_path}")
    with open(cache_path, "rb") as f:
        data = pickle.load(f)

    prepared = build_rotation_backtest_inputs_from_cache(data)
    bundle = prepared["bundle"]
    bundle_np = prepared["bundle_np"]
    timeline = prepared["timeline"]
    breadth_series = prepared["breadth_series"]
    tickers = list(bundle_np.get("tickers", []))
    univ_indices = np.array(
        [
            idx
            for idx, ticker in enumerate(tickers)
            if str(ticker).endswith(".T") and ticker not in {"1306.T", "1321.T"}
        ],
        dtype=int,
    )

    if "1321.T" in bundle["Close"].columns:
        print("1321.T Found and Normalized.")
    else:
        print("1321.T not found in primary close columns!")

    print("Calculating Technical Indicators for JP Universe...")
    print("\nStarting Japan IMPERIAL ORACLE Backtest (Day Trade Production)...")
    _final_assets, _trade_count, monthly_assets, _trade_results, daily_stats, trade_log = run_backtest_v16_production(
        univ_indices=univ_indices,
        bundle_np=bundle_np,
        timeline=timeline,
        breadth_ratio=breadth_series,
        initial_cash=INITIAL_CASH,
        slippage=SLIPPAGE_RATE,
        explicit_trade_cost=0.0,
        profit_tax_rate=0.0,
        return_daily_stats=True,
        return_trade_log=True,
        verbose=False,
    )

    full_summary = _summarize_window(
        daily_stats=daily_stats,
        trade_log=trade_log,
        label="FULL",
        start_date=str(timeline[0].date()),
        end_date=str(timeline[-1].date()),
    )
    if full_summary is None:
        print("Error: no daily statistics were produced by the backtest.")
        return 1

    split_summaries = []
    holdout_start = _resolve_holdout_start_date(timeline, holdout_months)
    if holdout_start is not None:
        train_end = (
            pd.Timestamp(holdout_start) - pd.Timedelta(days=1)
        ).strftime("%Y-%m-%d")
        print(
            f"HOLDOUT SPLIT: train={full_summary['start_date']} to {train_end}, "
            f"holdout={holdout_start} to {full_summary['end_date']} "
            f"(trailing {int(holdout_months)} month span from latest data date {timeline[-1].date()})"
        )

        train_summary = _summarize_window(
            daily_stats=daily_stats,
            trade_log=trade_log,
            label="TRAIN",
            start_date=full_summary["start_date"],
            end_date=train_end,
        )
        holdout_summary = _summarize_window(
            daily_stats=daily_stats,
            trade_log=trade_log,
            label="HOLDOUT",
            start_date=holdout_start,
            end_date=full_summary["end_date"],
        )
        if train_summary is not None:
            split_summaries.append(train_summary)
        if holdout_summary is not None:
            split_summaries.append(holdout_summary)

    _print_report(full_summary, split_summaries=split_summaries, monthly_assets=monthly_assets)
    return 0


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(
        run_jp_broad_backtest(
            cache_path=args.cache_path,
            holdout_months=args.holdout_months,
            refresh_cache=args.refresh_cache,
            refresh_start_date=args.refresh_start_date,
            refresh_overlap_days=args.refresh_overlap_days,
        )
    )
