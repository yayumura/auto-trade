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
from core.config import (
    DATA_CACHE_ROOT,
    DAYTRADE_API_EXPLICIT_TRADE_COST,
    INITIAL_CASH,
    SLIPPAGE_RATE,
    TAX_RATE,
)
from core.monthly_rotation_strategy import build_rotation_backtest_inputs_from_cache
from jp_backtest import FROZEN_HOLDOUT_START, WARMUP_START, _refresh_cache_if_requested, _summarize_window


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run a rolling holdout report for the current shared JP day-trade strategy. "
            "This replays the current logic once, then slices sequential train/holdout windows "
            "for pseudo-forward diagnostics."
        )
    )
    parser.add_argument(
        "--cache-path",
        default=str(DATA_CACHE_ROOT / "jp_broad" / "jp_mega_cache.pkl"),
        help="Path to the cached JP market data pickle.",
    )
    parser.add_argument(
        "--holdout-months",
        type=int,
        default=1,
        help="Length of each holdout window in trailing calendar months.",
    )
    parser.add_argument(
        "--step-months",
        type=int,
        default=1,
        help="Calendar-month step between consecutive holdout end anchors.",
    )
    parser.add_argument(
        "--min-train-months",
        type=int,
        default=24,
        help="Minimum number of calendar months required in the train window before a holdout begins.",
    )
    parser.add_argument(
        "--max-windows",
        type=int,
        default=0,
        help="Limit to the most recent N rolling windows. Use 0 to include every eligible window.",
    )
    parser.add_argument(
        "--output-csv",
        default="",
        help="Optional path to save the per-window walkforward table as CSV.",
    )
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Refresh the JP cache before replaying walkforward windows.",
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


def _normalize_day_keys(timeline):
    return [pd.Timestamp(ts).strftime("%Y-%m-%d") for ts in timeline]


def _truncate_replay_before_frozen_holdout(timeline, bundle_np, breadth_series):
    frozen_start = pd.Timestamp(FROZEN_HOLDOUT_START).normalize()
    keep_mask = np.asarray(pd.DatetimeIndex(timeline).normalize() < frozen_start)
    keep_count = int(keep_mask.sum())
    if keep_count <= 0:
        raise ValueError(
            f"No replay data exists before frozen holdout start {FROZEN_HOLDOUT_START}."
        )
    if not bool(keep_mask[:keep_count].all()) or bool(keep_mask[keep_count:].any()):
        raise ValueError("Timeline must be sorted before applying the frozen holdout boundary.")

    original_count = len(timeline)
    truncated_bundle = {
        key: (
            value[:keep_count]
            if isinstance(value, np.ndarray)
            and value.ndim >= 1
            and value.shape[0] == original_count
            else value
        )
        for key, value in bundle_np.items()
    }
    return (
        timeline[:keep_count],
        truncated_bundle,
        np.asarray(breadth_series)[:keep_count],
    )


def _resolve_production_univ_indices(prepared):
    return np.asarray(prepared.get("univ_indices", []), dtype=int)


def _resolve_day_index(day_keys):
    return pd.DatetimeIndex(pd.to_datetime(day_keys))


def _resolve_last_day_on_or_before(day_index, day_keys, target_date):
    target_ts = pd.Timestamp(target_date).normalize()
    pos = day_index.searchsorted(target_ts, side="right") - 1
    if pos < 0:
        return None
    return day_keys[pos]


def _resolve_first_day_after(day_index, day_keys, cutoff_date):
    cutoff_ts = pd.Timestamp(cutoff_date).normalize()
    pos = day_index.searchsorted(cutoff_ts, side="right")
    if pos >= len(day_keys):
        return None
    return day_keys[pos]


def _build_walkforward_windows(
    timeline,
    holdout_months,
    step_months=1,
    min_train_months=24,
    max_windows=0,
    warmup_start=WARMUP_START,
):
    if int(holdout_months) <= 0:
        raise ValueError("holdout_months must be >= 1")
    if int(step_months) <= 0:
        raise ValueError("step_months must be >= 1")
    if int(min_train_months) < 0:
        raise ValueError("min_train_months must be >= 0")
    if int(max_windows) < 0:
        raise ValueError("max_windows must be >= 0")

    day_keys = _normalize_day_keys(timeline)
    if not day_keys:
        return []
    day_index = _resolve_day_index(day_keys)
    latest_day = day_index[-1]
    warmup_ts = pd.Timestamp(warmup_start).normalize()

    windows_recent_first = []
    seen_holdout_ends = set()
    step_count = 0

    while True:
        anchor_target = latest_day - pd.DateOffset(months=int(step_months) * step_count)
        holdout_end = _resolve_last_day_on_or_before(day_index, day_keys, anchor_target)
        if holdout_end is None:
            break
        if holdout_end in seen_holdout_ends:
            step_count += 1
            continue
        seen_holdout_ends.add(holdout_end)

        holdout_start = _resolve_first_day_after(
            day_index,
            day_keys,
            pd.Timestamp(holdout_end) - pd.DateOffset(months=int(holdout_months)),
        )
        if holdout_start is None:
            break

        holdout_start_pos = day_keys.index(holdout_start)
        train_end_pos = holdout_start_pos - 1
        if train_end_pos < 0:
            break
        train_end = day_keys[train_end_pos]

        min_train_cutoff = warmup_ts + pd.DateOffset(months=int(min_train_months))
        if pd.Timestamp(holdout_start).normalize() <= min_train_cutoff:
            break

        windows_recent_first.append(
            {
                "window_id": len(windows_recent_first) + 1,
                "train_start": max(day_keys[0], warmup_ts.strftime("%Y-%m-%d")),
                "train_end": train_end,
                "holdout_start": holdout_start,
                "holdout_end": holdout_end,
            }
        )

        step_count += 1
        if int(max_windows) > 0 and len(windows_recent_first) >= int(max_windows):
            break

    windows = list(reversed(windows_recent_first))
    for idx, window in enumerate(windows, start=1):
        window["window_id"] = idx
    return windows


def _build_window_table(window_results):
    rows = []
    for item in window_results:
        train = item["train_summary"]
        holdout = item["holdout_summary"]
        rows.append(
            {
                "WINDOW": int(item["window_id"]),
                "TRAIN_END": train["end_date"],
                "HOLDOUT_START": holdout["start_date"],
                "HOLDOUT_END": holdout["end_date"],
                "TRAIN_+1%": f"{train['plus_1pct_weeks']}/{train['week_count']}",
                "HOLDOUT_+1%": f"{holdout['plus_1pct_weeks']}/{holdout['week_count']}",
                "HOLDOUT_RET_PCT": float(holdout["total_return_pct"]),
                "HOLDOUT_PF": float(holdout["profit_factor"]),
                "HOLDOUT_TRADES": int(holdout["trade_count"]),
                "HOLDOUT_WORST_DAY": float(holdout["worst_day"]),
            }
        )
    return pd.DataFrame(rows)


def _aggregate_holdout_summaries(window_results):
    holdouts = [item["holdout_summary"] for item in window_results]
    if not holdouts:
        return None

    holdout_returns = [float(item["total_return_pct"]) for item in holdouts]
    holdout_pfs = [float(item["profit_factor"]) for item in holdouts]
    total_holdout_weeks = sum(int(item["week_count"]) for item in holdouts)
    total_plus_1pct_weeks = sum(int(item["plus_1pct_weeks"]) for item in holdouts)
    total_positive_weeks = sum(int(item["positive_weeks"]) for item in holdouts)

    return {
        "window_count": len(holdouts),
        "positive_windows": sum(1 for item in holdouts if float(item["total_return_pct"]) > 0.0),
        "windows_all_weeks_hit": sum(
            1
            for item in holdouts
            if int(item["week_count"]) > 0 and int(item["plus_1pct_weeks"]) == int(item["week_count"])
        ),
        "avg_holdout_return_pct": float(np.mean(holdout_returns)),
        "median_holdout_return_pct": float(np.median(holdout_returns)),
        "min_holdout_return_pct": float(np.min(holdout_returns)),
        "max_holdout_return_pct": float(np.max(holdout_returns)),
        "avg_holdout_pf": float(np.mean(holdout_pfs)),
        "median_holdout_pf": float(np.median(holdout_pfs)),
        "total_holdout_trades": sum(int(item["trade_count"]) for item in holdouts),
        "total_holdout_weeks": total_holdout_weeks,
        "total_plus_1pct_weeks": total_plus_1pct_weeks,
        "total_positive_weeks": total_positive_weeks,
        "best_window": max(holdouts, key=lambda item: float(item["total_return_pct"])),
        "worst_window": min(holdouts, key=lambda item: float(item["total_return_pct"])),
    }


def _print_walkforward_report(window_results, aggregate_summary, params):
    print("=" * 72)
    print("JP WALKFORWARD REPORT")
    print("=" * 72)
    print(
        "NOTE: this does not auto-refit parameters inside each window; it slices the "
        "current shared strategy into rolling train/holdout periods for pseudo-forward validation."
    )
    print(
        f"SETTINGS: holdout={params['holdout_months']}m | step={params['step_months']}m | "
        f"min_train={params['min_train_months']}m | windows={len(window_results)}"
    )

    if not window_results:
        print("No eligible walkforward windows were produced.")
        print("=" * 72)
        return

    table = _build_window_table(window_results)
    print("-" * 72)
    print("PER-WINDOW HOLDOUT RESULTS")
    print("-" * 72)
    print(
        table.to_string(
            index=False,
            formatters={
                "HOLDOUT_RET_PCT": "{:+.2f}%".format,
                "HOLDOUT_PF": "{:.2f}".format,
                "HOLDOUT_WORST_DAY": lambda value: f"Y{value:,.0f}",
            },
        )
    )

    if aggregate_summary is None:
        print("=" * 72)
        return

    print("-" * 72)
    print("AGGREGATE HOLDOUT SUMMARY")
    print("-" * 72)
    print(f"POSITIVE WINDOWS: {aggregate_summary['positive_windows']}/{aggregate_summary['window_count']}")
    print(
        f"WINDOWS WITH ALL WEEKS >= +1%: "
        f"{aggregate_summary['windows_all_weeks_hit']}/{aggregate_summary['window_count']}"
    )
    print(
        f"HOLDOUT WEEKS >= +1%: "
        f"{aggregate_summary['total_plus_1pct_weeks']}/{aggregate_summary['total_holdout_weeks']}"
    )
    print(
        f"HOLDOUT POSITIVE WEEKS: "
        f"{aggregate_summary['total_positive_weeks']}/{aggregate_summary['total_holdout_weeks']}"
    )
    print(f"AVG HOLDOUT RETURN: {aggregate_summary['avg_holdout_return_pct']:+.2f}%")
    print(f"MED HOLDOUT RETURN: {aggregate_summary['median_holdout_return_pct']:+.2f}%")
    print(
        f"HOLDOUT RETURN RANGE: "
        f"{aggregate_summary['min_holdout_return_pct']:+.2f}% to {aggregate_summary['max_holdout_return_pct']:+.2f}%"
    )
    print(f"AVG HOLDOUT PF: {aggregate_summary['avg_holdout_pf']:.2f}")
    print(f"MED HOLDOUT PF: {aggregate_summary['median_holdout_pf']:.2f}")
    print(f"TOTAL HOLDOUT TRADES: {aggregate_summary['total_holdout_trades']}")
    print(
        f"BEST HOLDOUT WINDOW: {aggregate_summary['best_window']['start_date']} to "
        f"{aggregate_summary['best_window']['end_date']} "
        f"({aggregate_summary['best_window']['total_return_pct']:+.2f}%)"
    )
    print(
        f"WORST HOLDOUT WINDOW: {aggregate_summary['worst_window']['start_date']} to "
        f"{aggregate_summary['worst_window']['end_date']} "
        f"({aggregate_summary['worst_window']['total_return_pct']:+.2f}%)"
    )
    print("=" * 72)


def run_jp_walkforward(
    cache_path,
    holdout_months=1,
    step_months=1,
    min_train_months=24,
    max_windows=0,
    output_csv="",
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
    timeline, bundle_np, breadth_series = _truncate_replay_before_frozen_holdout(
        timeline,
        bundle_np,
        breadth_series,
    )
    print(
        f"FROZEN ANALYSIS WINDOW: through {pd.Timestamp(timeline[-1]).date()} "
        f"(excludes {FROZEN_HOLDOUT_START} onward)"
    )
    univ_indices = _resolve_production_univ_indices(prepared)

    if "1321.T" in bundle["Close"].columns:
        print("1321.T Found and Normalized.")
    else:
        print("1321.T not found in primary close columns!")

    print("Calculating Technical Indicators for JP Universe...")
    print("\nStarting Japan IMPERIAL ORACLE Walkforward Replay...")
    _final_assets, _trade_count, _monthly_assets, _trade_results, daily_stats, trade_log = run_backtest_v16_production(
        univ_indices=univ_indices,
        bundle_np=bundle_np,
        timeline=timeline,
        breadth_ratio=breadth_series,
        initial_cash=INITIAL_CASH,
        slippage=SLIPPAGE_RATE,
        explicit_trade_cost=DAYTRADE_API_EXPLICIT_TRADE_COST,
        profit_tax_rate=TAX_RATE,
        return_daily_stats=True,
        return_trade_log=True,
        verbose=False,
    )

    windows = _build_walkforward_windows(
        timeline=timeline,
        holdout_months=holdout_months,
        step_months=step_months,
        min_train_months=min_train_months,
        max_windows=max_windows,
        warmup_start=WARMUP_START,
    )
    if not windows:
        print("No eligible walkforward windows were produced with the requested settings.")
        return 1

    window_results = []
    for window in windows:
        train_summary = _summarize_window(
            daily_stats=daily_stats,
            trade_log=trade_log,
            label=f"TRAIN-{window['window_id']}",
            start_date=window["train_start"],
            end_date=window["train_end"],
        )
        holdout_summary = _summarize_window(
            daily_stats=daily_stats,
            trade_log=trade_log,
            label=f"HOLDOUT-{window['window_id']}",
            start_date=window["holdout_start"],
            end_date=window["holdout_end"],
        )
        if train_summary is None or holdout_summary is None:
            continue
        window_results.append(
            {
                "window_id": window["window_id"],
                "train_summary": train_summary,
                "holdout_summary": holdout_summary,
            }
        )

    aggregate_summary = _aggregate_holdout_summaries(window_results)
    _print_walkforward_report(
        window_results,
        aggregate_summary,
        params={
            "holdout_months": holdout_months,
            "step_months": step_months,
            "min_train_months": min_train_months,
        },
    )

    if output_csv:
        table = _build_window_table(window_results)
        table.to_csv(output_csv, index=False)
        print(f"Saved walkforward table to {output_csv}")

    return 0


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(
        run_jp_walkforward(
            cache_path=args.cache_path,
            holdout_months=args.holdout_months,
            step_months=args.step_months,
            min_train_months=args.min_train_months,
            max_windows=args.max_windows,
            output_csv=args.output_csv,
            refresh_cache=args.refresh_cache,
            refresh_start_date=args.refresh_start_date,
            refresh_overlap_days=args.refresh_overlap_days,
        )
    )
