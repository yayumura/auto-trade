from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backtest import run_backtest_v16_production
from core.config import (
    INITIAL_CASH,
    SLIPPAGE_RATE,
)
from core.monthly_rotation_strategy import build_rotation_backtest_inputs_from_cache
from jp_backtest import (
    _print_window_summary,
    _resolve_holdout_start_date,
    _summarize_window,
)
from jp_jquants_fetcher_v2 import (
    DEFAULT_MAX_WORKERS,
    DEFAULT_OUTPUT_PATH,
    DEFAULT_REFRESH_OVERLAP_DAYS,
    fetch_jquants_v2_turbo_revelation,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh the latest JP cache and rerun the standard validation backtest "
            "with a standalone latest-month replay."
        )
    )
    parser.add_argument(
        "--cache-path",
        default=DEFAULT_OUTPUT_PATH,
        help="Consolidated JP cache pickle to refresh and validate.",
    )
    parser.add_argument(
        "--refresh-start-date",
        default="",
        help="Optional YYYYMMDD override for the refresh start date.",
    )
    parser.add_argument(
        "--refresh-overlap-days",
        type=int,
        default=DEFAULT_REFRESH_OVERLAP_DAYS,
        help="Re-fetch this many trailing days before the cached latest day.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help="Maximum concurrent ticker fetch workers used during refresh.",
    )
    parser.add_argument(
        "--limit-tickers",
        type=int,
        default=0,
        help="Optional cap on how many tickers to fetch during refresh.",
    )
    parser.add_argument(
        "--debug-failure-samples",
        type=int,
        default=0,
        help="Print up to this many failed fetch samples during refresh.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Skip the refresh step and only validate the existing cache.",
    )
    parser.add_argument(
        "--holdout-months",
        type=int,
        default=6,
        help="Trailing holdout span to report from the refreshed cache.",
    )
    parser.add_argument(
        "--standalone-latest-months",
        type=int,
        default=1,
        help="Trailing standalone replay span to run from 1,000,000 yen initial cash.",
    )
    parser.add_argument(
        "--standalone-initial-cash",
        type=float,
        default=float(INITIAL_CASH),
        help="Initial cash for the standalone latest-window replay.",
    )
    return parser.parse_args()


def _refresh_cache(args: argparse.Namespace) -> None:
    if args.validate_only:
        print("Skipping refresh step (--validate-only).")
        return

    print("Refreshing JP cache before validation...")
    fetch_jquants_v2_turbo_revelation(
        output_path=args.cache_path,
        start_date=args.refresh_start_date or None,
        refresh_overlap_days=args.refresh_overlap_days,
        max_workers=args.max_workers,
        limit_tickers=args.limit_tickers,
        debug_failure_samples=args.debug_failure_samples,
    )


def _load_cache(cache_path: str | Path) -> dict:
    cache_path = Path(cache_path)
    if not cache_path.exists():
        raise FileNotFoundError(f"Cache not found: {cache_path}")
    with cache_path.open("rb") as handle:
        return pickle.load(handle)


def _slice_backtest_inputs_for_window(
    bundle_np: dict,
    timeline: pd.Index,
    breadth_ratio: np.ndarray,
    start_date: str,
    end_date: str,
    context_days: int = 2,
) -> tuple[dict, pd.Index, np.ndarray, str | None]:
    timeline_ts = pd.DatetimeIndex(timeline)
    window_mask = (timeline_ts >= pd.Timestamp(start_date)) & (timeline_ts <= pd.Timestamp(end_date))
    window_indices = np.flatnonzero(window_mask)
    if window_indices.size == 0:
        return bundle_np, timeline, breadth_ratio, None

    start_idx = max(0, int(window_indices[0]) - int(context_days))
    end_idx = int(window_indices[-1])
    sliced_bundle_np = {}
    for key, value in bundle_np.items():
        if key == "tickers":
            sliced_bundle_np[key] = value
            continue
        if hasattr(value, "shape") and len(value) > end_idx:
            sliced_bundle_np[key] = value[start_idx : end_idx + 1]
        else:
            sliced_bundle_np[key] = value
    sliced_timeline = timeline_ts[start_idx : end_idx + 1]
    sliced_breadth_ratio = breadth_ratio[start_idx : end_idx + 1]
    context_start = str(pd.Timestamp(sliced_timeline[0]).date())
    return sliced_bundle_np, sliced_timeline, sliced_breadth_ratio, context_start


def _build_full_validation_report(
    cache_path: str | Path,
    holdout_months: int,
    standalone_latest_months: int,
    standalone_initial_cash: float,
) -> tuple[dict, dict | None, dict | None, dict | None, dict | None, str | None, str | None, str | None]:
    data = _load_cache(cache_path)
    prepared = build_rotation_backtest_inputs_from_cache(data)
    bundle = prepared["bundle"]
    bundle_np = prepared["bundle_np"]
    timeline = prepared["timeline"]
    breadth_series = prepared["breadth_series"]
    univ_indices = prepared["univ_indices"]

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
        raise RuntimeError("No daily statistics were produced by the full backtest.")

    holdout_start = _resolve_holdout_start_date(timeline, holdout_months)
    train_summary = None
    holdout_summary = None
    if holdout_start is not None:
        train_end = (pd.Timestamp(holdout_start) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
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

    standalone_summary = None
    standalone_daily_stats = None
    standalone_start = None
    standalone_end = None
    standalone_context_start = None
    if standalone_latest_months is not None and int(standalone_latest_months) > 0:
        standalone_start = _resolve_holdout_start_date(timeline, standalone_latest_months)
        standalone_end = str(pd.Timestamp(timeline[-1]).date())
        if standalone_start is not None:
            (
                standalone_bundle_np,
                standalone_timeline,
                standalone_breadth_series,
                standalone_context_start,
            ) = _slice_backtest_inputs_for_window(
                bundle_np=bundle_np,
                timeline=timeline,
                breadth_ratio=breadth_series,
                start_date=standalone_start,
                end_date=standalone_end,
                context_days=2,
            )
            (
                _sa_final_assets,
                _sa_trade_count,
                _sa_monthly_assets,
                _sa_trade_results,
                standalone_daily_stats,
                standalone_trade_log,
            ) = run_backtest_v16_production(
                univ_indices=prepared["univ_indices"],
                bundle_np=standalone_bundle_np,
                timeline=standalone_timeline,
                breadth_ratio=standalone_breadth_series,
                initial_cash=float(standalone_initial_cash),
                slippage=SLIPPAGE_RATE,
                explicit_trade_cost=0.0,
                profit_tax_rate=0.0,
                return_daily_stats=True,
                return_trade_log=True,
                verbose=False,
            )
            standalone_summary = _summarize_window(
                daily_stats=standalone_daily_stats,
                trade_log=standalone_trade_log,
                label=f"STANDALONE LATEST {int(standalone_latest_months)}M",
                start_date=standalone_start,
                end_date=standalone_end,
                global_day_keys=[pd.Timestamp(ts).strftime("%Y-%m-%d") for ts in timeline],
            )

    return (
        full_summary,
        train_summary,
        holdout_summary,
        standalone_summary,
        standalone_daily_stats,
        standalone_start,
        standalone_end,
        standalone_context_start,
    )


def _print_daily_rows(daily_stats: dict, start_date: str, end_date: str) -> None:
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


def main() -> int:
    args = parse_args()
    _refresh_cache(args)

    if not Path(args.cache_path).exists():
        print(f"Error: Cache not found at {args.cache_path}")
        return 1

    print(f"Loading JP Mega-Data Cache: {args.cache_path}")
    try:
        (
            full_summary,
            train_summary,
            holdout_summary,
            standalone_summary,
            standalone_daily_stats,
            standalone_start,
            standalone_end,
            standalone_context_start,
        ) = _build_full_validation_report(
            args.cache_path,
            args.holdout_months,
            args.standalone_latest_months,
            args.standalone_initial_cash,
        )
    except Exception as exc:
        print(f"Error: {exc}")
        return 1

    print("=" * 50)
    print("JP REFRESH + VALIDATE SUMMARY")
    print("=" * 50)
    print(f"DATA WINDOW:   {full_summary['start_date']} to {full_summary['end_date']}")
    print(f"INITIAL CASH:  Y{INITIAL_CASH:,.0f}")
    _print_window_summary(full_summary)

    if train_summary is not None and holdout_summary is not None:
        print("-" * 50)
        print(
            "NOTE: segmented weekly/monthly metrics count only full ISO weeks / full calendar months fully inside each window."
        )
        _print_window_summary(train_summary)
        _print_window_summary(holdout_summary)

    if standalone_summary is not None:
        print("-" * 50)
        print(
            "NOTE: standalone latest-window replay starts from "
            f"Y{float(args.standalone_initial_cash):,.0f} and includes prior context days only for signal calculation."
        )
        if standalone_context_start is not None:
            print(f"CONTEXT START: {standalone_context_start}")
        _print_window_summary(standalone_summary)
        if standalone_daily_stats is not None and standalone_start is not None and standalone_end is not None:
            _print_daily_rows(standalone_daily_stats, standalone_start, standalone_end)

    print("=" * 50)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
