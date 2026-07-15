import argparse
import os
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backtest import run_backtest_v16_production
from core.config import DATA_CACHE_ROOT, INITIAL_CASH, DAYTRADE_API_EXPLICIT_TRADE_COST, SLIPPAGE_RATE, TAX_RATE, load_insider_exclusion_codes
from core.daytrade_observation_universe import (
    DAYTRADE_DISCOVERY_MAX_SYMBOLS,
    build_daytrade_production_observation_indices_by_day,
    build_daytrade_rotating_discovery_indices_by_day,
)
from core.logic import get_daytrade_week_key, get_prime_tickers, load_invalid_tickers
from core.monthly_rotation_strategy import build_rotation_backtest_inputs_from_cache


WARMUP_START = "2022-03-01"
FROZEN_HOLDOUT_START = "2026-01-13"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the JP day-trade backtest and optionally report a trailing holdout window."
    )
    parser.add_argument(
        "--cache-path",
        default=str(DATA_CACHE_ROOT / "jp_broad" / "jp_mega_cache.pkl"),
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
    parser.add_argument(
        "--standalone-latest-months",
        type=int,
        default=0,
        help="Run a standalone replay for the latest N months with 1,000,000 yen initial cash.",
    )
    parser.add_argument(
        "--standalone-initial-cash",
        type=float,
        default=float(INITIAL_CASH),
        help="Initial cash for the standalone latest-window replay.",
    )
    parser.add_argument(
        "--production-observation-replay",
        action="store_true",
        help=(
            "Constrain each trade date to the fixed production prior-day 49-symbol observation policy."
        ),
    )
    parser.add_argument(
        "--rotating-discovery-replay",
        action="store_true",
        help=(
            "Constrain each date to four sequential 49-symbol batches selected from prior-day scenarios."
        ),
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

def _resolve_holdout_start_date(timeline, holdout_months, earliest_holdout_start=None):
    if holdout_months is None or int(holdout_months) <= 0:
        return None
    last_date = pd.Timestamp(timeline[-1]).normalize()
    cutoff_exclusive = last_date - pd.DateOffset(months=int(holdout_months))
    holdout_days = [
        pd.Timestamp(ts).strftime("%Y-%m-%d")
        for ts in timeline
        if pd.Timestamp(ts).normalize() > cutoff_exclusive
    ]
    resolved_start = holdout_days[0] if holdout_days else None
    if resolved_start is None or earliest_holdout_start in (None, ""):
        return resolved_start

    earliest_ts = pd.Timestamp(earliest_holdout_start).normalize()
    if earliest_ts >= pd.Timestamp(resolved_start).normalize():
        return resolved_start
    frozen_days = [
        pd.Timestamp(ts).strftime("%Y-%m-%d")
        for ts in timeline
        if pd.Timestamp(ts).normalize() >= earliest_ts
    ]
    return frozen_days[0] if frozen_days else resolved_start


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


def _print_daily_rows(daily_stats, start_date, end_date):
    window_day_keys = [
        day_key
        for day_key in sorted(daily_stats.keys())
        if start_date <= day_key <= end_date
    ]
    if not window_day_keys:
        return

    first_day = window_day_keys[0]
    start_equity = float(daily_stats[first_day]["equity"]) - float(daily_stats[first_day]["day_pnl"])

    print("-" * 50)
    print("STANDALONE DAILY RESULT")
    print("-" * 50)
    print("DATE           | DAY_PNL     | TRADES | END_EQUITY  | CUM_RETURN")
    for day_key in window_day_keys:
        item = daily_stats[day_key]
        day_pnl = float(item["day_pnl"])
        end_equity = float(item["equity"])
        cum_return_pct = ((end_equity / start_equity) - 1.0) * 100.0 if start_equity > 0 else 0.0
        print(
            f"{day_key} | "
            f"{day_pnl:+11,.0f} | "
            f"{int(item['trade_count']):>6} | "
            f"{end_equity:11,.0f} | "
            f"{cum_return_pct:+9.2f}%"
        )


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

    evaluation_day_keys = [day_key for day_key in window_day_keys if day_key >= warmup_start]
    evaluation_day_key_set = set(evaluation_day_keys)
    boundary_day_keys = global_day_keys if global_day_keys is not None else daily_stats.keys()
    week_bounds, month_bounds = _build_global_period_boundaries(boundary_day_keys)
    global_month_keys = sorted(month_bounds)
    unprovable_edge_months = set()
    if global_month_keys:
        unprovable_edge_months.add(global_month_keys[0])
        unprovable_edge_months.add(global_month_keys[-1])
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
    return_month_stats = {}
    month_totals = {}
    month_active = {}

    for day_key in window_day_keys:
        item = daily_stats[day_key]
        day_pnl = float(item["day_pnl"])
        day_trade_count = int(item["trade_count"])

        if day_key < warmup_start:
            continue

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

        return_month_key = day_key[:7]
        return_month_record = return_month_stats.setdefault(
            return_month_key,
            {
                "start_equity": float(item["equity"]) - day_pnl,
                "pnl": 0.0,
            },
        )
        return_month_record["pnl"] += day_pnl

        month_key = day_key[:7]
        month_totals[month_key] = month_totals.get(month_key, 0) + 1
        if day_trade_count > 0:
            month_active[month_key] = month_active.get(month_key, 0) + 1

        week_key = get_daytrade_week_key(pd.Timestamp(day_key))
        week_bound = week_bounds[week_key]
        # Segmented weekly stats are counted only when the full ISO week is inside the window.
        if week_bound["first"] not in evaluation_day_key_set or week_bound["last"] not in evaluation_day_key_set:
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
        if month_key in unprovable_edge_months:
            continue
        month_bound = month_bounds[month_key]
        # Segmented monthly stats are counted only when the full calendar month is inside the window.
        if month_bound["first"] not in evaluation_day_key_set or month_bound["last"] not in evaluation_day_key_set:
            continue
        if total <= 0:
            continue
        full_month_rates.append(month_active.get(month_key, 0) / total)

    full_month_returns = []
    for month_key, month_record in sorted(return_month_stats.items()):
        if month_key in unprovable_edge_months:
            continue
        month_bound = month_bounds[month_key]
        if month_bound["first"] not in evaluation_day_key_set or month_bound["last"] not in evaluation_day_key_set:
            continue
        month_start_equity = float(month_record["start_equity"])
        month_return = (
            float(month_record["pnl"]) / month_start_equity
            if month_start_equity > 0
            else 0.0
        )
        full_month_returns.append(month_return)

    plus_day_rate = (plus_days / active_days * 100.0) if active_days > 0 else 0.0
    trade_day_rate = (
        period_active_trade_days / len(evaluation_day_keys) * 100.0
        if evaluation_day_keys
        else 0.0
    )
    plus_1pct_weeks = sum(
        1 for item in week_stats.values() if item["pnl"] >= (item["start_equity"] * 0.01)
    )
    positive_weeks = sum(1 for item in week_stats.values() if item["pnl"] > 0)

    return {
        "label": label,
        "start_date": first_day,
        "end_date": last_day,
        "evaluation_start_date": evaluation_day_keys[0] if evaluation_day_keys else None,
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
        "full_month_returns": full_month_returns,
        "months_ge_20pct": sum(1 for value in full_month_returns if value >= 0.20),
        "plus_1pct_weeks": plus_1pct_weeks,
        "positive_weeks": positive_weeks,
        "week_count": len(week_stats),
    }


def _print_window_summary(summary):
    print("-" * 50)
    print(f"{summary['label']} WINDOW")
    print("-" * 50)
    print(f"WINDOW:        {summary['start_date']} to {summary['end_date']}")
    if summary.get("evaluation_start_date") != summary["start_date"]:
        print(f"EVALUATION:    {summary.get('evaluation_start_date')} to {summary['end_date']} (post-warmup)")
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

    if summary["full_month_returns"]:
        print(
            f"MONTHS >= +20%: {summary['months_ge_20pct']}/"
            f"{len(summary['full_month_returns'])}"
        )
    else:
        print("MONTHS >= +20%: N/A")

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
    standalone_latest_months=0,
    standalone_initial_cash=float(INITIAL_CASH),
    production_observation_replay=False,
    rotating_discovery_replay=False,
):
    print(
        "REFERENCE-ONLY: daily OHLC backtest is not production-equivalent. "
        "Use jp_production_replay.py for observed board/order/exit validation."
    )
    if production_observation_replay and rotating_discovery_replay:
        print("Error: observation replay modes are mutually exclusive.")
        return 1
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
    univ_indices = prepared["univ_indices"]

    observation_universe_indices_by_day = None
    if production_observation_replay or rotating_discovery_replay:
        observation_exclusions = set(load_invalid_tickers())
        observation_exclusions.update(load_insider_exclusion_codes())
    if production_observation_replay:
        observation_universe_indices_by_day = build_daytrade_production_observation_indices_by_day(
            bundle_np=bundle_np,
            timeline=timeline,
            prime_tickers=get_prime_tickers(),
            max_symbols=49,
            excluded_codes=observation_exclusions,
        )
        univ_indices = np.asarray(
            sorted({
                int(index)
                for indices in observation_universe_indices_by_day.values()
                for index in indices
            }),
            dtype=int,
        )
        observed_counts = [
            len(indices)
            for day_key, indices in observation_universe_indices_by_day.items()
            if day_key >= WARMUP_START
        ]
        print(
            "PRODUCTION OBSERVATION REPLAY: fixed prior-day policy, "
            f"max=49, evaluation-days={len(observed_counts)}, "
            f"selected/day={min(observed_counts, default=0)}..{max(observed_counts, default=0)}"
        )
        print(
            "REPORT MODE: production-observation-constrained daily OHLC reference-only; "
            "not evidence of 9:30 board, fill, order lifecycle, or live profitability."
        )
    elif rotating_discovery_replay:
        observation_universe_indices_by_day = build_daytrade_rotating_discovery_indices_by_day(
            bundle_np=bundle_np,
            timeline=timeline,
            prime_tickers=get_prime_tickers(),
            excluded_codes=observation_exclusions,
        )
        univ_indices = np.asarray(
            sorted({
                int(index)
                for indices in observation_universe_indices_by_day.values()
                for index in indices
            }),
            dtype=int,
        )
        observed_counts = [
            len(indices)
            for day_key, indices in observation_universe_indices_by_day.items()
            if day_key >= WARMUP_START
        ]
        zero_observation_days = sum(count == 0 for count in observed_counts)
        full_observation_days = sum(
            count == DAYTRADE_DISCOVERY_MAX_SYMBOLS for count in observed_counts
        )
        print(
            "ROTATING DISCOVERY REPLAY: prior-day -2%/flat/+2% scenarios, "
            f"batches=4x49, max={DAYTRADE_DISCOVERY_MAX_SYMBOLS}, "
            f"evaluation-days={len(observed_counts)}, "
            f"selected/day={min(observed_counts, default=0)}..{max(observed_counts, default=0)}, "
            f"full-days={full_observation_days}, zero-days={zero_observation_days}"
        )
        print(
            "REPORT MODE: rotating-discovery-constrained daily OHLC reference-only; "
            "registry timing, Board failures, fills, and live profitability remain unverified."
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
        explicit_trade_cost=DAYTRADE_API_EXPLICIT_TRADE_COST,
        profit_tax_rate=TAX_RATE,
        observation_universe_indices_by_day=observation_universe_indices_by_day,
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
    holdout_start = _resolve_holdout_start_date(
        timeline,
        holdout_months,
        earliest_holdout_start=FROZEN_HOLDOUT_START,
    )
    if holdout_start is not None:
        train_end = (
            pd.Timestamp(holdout_start) - pd.Timedelta(days=1)
        ).strftime("%Y-%m-%d")
        print(
            f"HOLDOUT SPLIT: train={full_summary['start_date']} to {train_end}, "
            f"holdout={holdout_start} to {full_summary['end_date']} "
            f"(minimum trailing {int(holdout_months)} month span; "
            f"frozen boundary {FROZEN_HOLDOUT_START})"
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

    standalone_summary = None
    standalone_daily_stats = None
    standalone_start = None
    standalone_end = None
    standalone_context_start = None
    if standalone_latest_months is not None and int(standalone_latest_months) > 0:
        standalone_start = _resolve_holdout_start_date(timeline, standalone_latest_months)
        standalone_end = str(pd.Timestamp(timeline[-1]).date())
        if standalone_start is not None:
            standalone_bundle_np = bundle_np
            standalone_timeline = timeline
            standalone_breadth_series = breadth_series
            standalone_context_start = standalone_start
            (
                _sa_final_assets,
                _sa_trade_count,
                _sa_monthly_assets,
                _sa_trade_results,
                standalone_daily_stats,
                standalone_trade_log,
            ) = run_backtest_v16_production(
                univ_indices=univ_indices,
                bundle_np=standalone_bundle_np,
                timeline=standalone_timeline,
                breadth_ratio=standalone_breadth_series,
                initial_cash=float(standalone_initial_cash),
                slippage=SLIPPAGE_RATE,
                explicit_trade_cost=DAYTRADE_API_EXPLICIT_TRADE_COST,
                profit_tax_rate=TAX_RATE,
                evaluation_start_date=standalone_start,
                observation_universe_indices_by_day=observation_universe_indices_by_day,
                return_daily_stats=True,
                return_trade_log=True,
                verbose=False,
            )
            if standalone_daily_stats is not None and standalone_start is not None:
                standalone_day_keys = sorted(standalone_daily_stats.keys())
                baseline_day_keys = [
                    day_key for day_key in standalone_day_keys if day_key < standalone_start
                ]
                if baseline_day_keys:
                    baseline_day_key = baseline_day_keys[-1]
                    baseline_equity = float(standalone_daily_stats[baseline_day_key]["equity"])
                    equity_offset = float(standalone_initial_cash) - baseline_equity
                    if abs(equity_offset) > 1e-9:
                        for day_key in standalone_day_keys:
                            if day_key >= standalone_start:
                                item = dict(standalone_daily_stats[day_key])
                                item["equity"] = float(item["equity"]) + equity_offset
                                standalone_daily_stats[day_key] = item
            standalone_summary = _summarize_window(
                daily_stats=standalone_daily_stats,
                trade_log=standalone_trade_log,
                label=f"STANDALONE LATEST {int(standalone_latest_months)}M",
                start_date=standalone_start,
                end_date=standalone_end,
                global_day_keys=[pd.Timestamp(ts).strftime("%Y-%m-%d") for ts in timeline],
            )
            if standalone_summary is not None:
                print("-" * 50)
                print(
                    "NOTE: standalone latest-window replay starts from "
                    f"Y{float(standalone_initial_cash):,.0f} and includes prior context days only for signal calculation."
                )
                if standalone_context_start is not None:
                    print(f"CONTEXT START: {standalone_context_start}")
                _print_window_summary(standalone_summary)
                if standalone_daily_stats is not None and standalone_start is not None and standalone_end is not None:
                    _print_daily_rows(standalone_daily_stats, standalone_start, standalone_end)

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
            standalone_latest_months=args.standalone_latest_months,
            standalone_initial_cash=args.standalone_initial_cash,
            production_observation_replay=args.production_observation_replay,
            rotating_discovery_replay=args.rotating_discovery_replay,
        )
    )
