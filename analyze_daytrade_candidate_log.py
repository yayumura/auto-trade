import argparse
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
from jp_backtest import FROZEN_HOLDOUT_START, WARMUP_START, _resolve_holdout_start_date


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Replay the JP day-trade backtest with candidate diagnostics, including "
            "generated-but-not-selected candidates and no-trade day reasons."
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
        default=6,
        help="Trailing holdout months. Train-side diagnostics exclude this window.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Number of grouped rows to print per section.",
    )
    parser.add_argument(
        "--output-day-csv",
        default="",
        help="Optional path to save candidate day summary rows as CSV.",
    )
    parser.add_argument(
        "--output-candidate-csv",
        default="",
        help="Optional path to save generated candidate rows as CSV.",
    )
    return parser


def load_prepared_inputs(cache_path):
    with open(cache_path, "rb") as f:
        data = pickle.load(f)
    prepared = build_rotation_backtest_inputs_from_cache(data)
    univ_indices = np.asarray(prepared.get("univ_indices", []), dtype=int)
    return prepared, univ_indices


def replay_candidate_log(cache_path):
    prepared, univ_indices = load_prepared_inputs(cache_path)
    bundle_np = prepared["bundle_np"]
    timeline = prepared["timeline"]
    breadth_series = prepared["breadth_series"]
    _, _, _, _, daily_stats, trade_log, candidate_log = run_backtest_v16_production(
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
        return_candidate_log=True,
        verbose=False,
    )
    return prepared, daily_stats, trade_log, candidate_log


def _filter_train(df, holdout_start):
    if df.empty:
        return df
    result = df[df["day_key"] >= WARMUP_START].copy()
    if holdout_start is not None:
        result = result[result["day_key"] < holdout_start]
    return result


def _print_section(title):
    print()
    print("-" * 80)
    print(title)
    print("-" * 80)


def _print_frame(df, top_n):
    if df.empty:
        print("(none)")
        return
    print(df.head(top_n).to_string(index=False))


def summarize_day_reasons(day_df, top_n):
    _print_section("TRAIN DAY REASONS")
    counts = (
        day_df.groupby("reason", dropna=False)
        .agg(days=("day_key", "count"), trades=("trade_count", "sum"))
        .reset_index()
        .sort_values(["days", "trades"], ascending=[False, False])
    )
    _print_frame(counts, top_n)

    _print_section("TRAIN NO-TRADE MONTHS / REASONS")
    no_trade = day_df[day_df["trade_count"] == 0].copy()
    if no_trade.empty:
        print("(none)")
        return
    monthly = (
        no_trade.groupby(["month_key", "reason"], dropna=False)
        .agg(days=("day_key", "count"), total_candidates=("total_candidates", "sum"))
        .reset_index()
        .sort_values(["month_key", "days"], ascending=[True, False])
    )
    _print_frame(monthly, top_n)


def summarize_scan_reasons(day_df, top_n):
    scan_cols = [col for col in day_df.columns if col.startswith("scan_")]
    setup_cols = [col for col in day_df.columns if col.startswith("setup_")]
    no_trade = day_df[day_df["trade_count"] == 0].copy()

    _print_section("TRAIN NO-TRADE SCAN / SETUP TOTALS")
    if no_trade.empty or (not scan_cols and not setup_cols):
        print("(none)")
        return
    totals = []
    bottleneck_cols = [col for col in scan_cols + setup_cols if col not in {"scan_universe", "scan_passed_scan"}]
    for col in bottleneck_cols:
        total = float(pd.to_numeric(no_trade[col], errors="coerce").fillna(0).sum())
        if total > 0:
            totals.append({"reason": col, "count": int(total)})
    totals_df = pd.DataFrame(totals).sort_values("count", ascending=False)
    _print_frame(totals_df, top_n)

    _print_section("TRAIN NO-CANDIDATE DAY BOTTLENECKS BY MONTH")
    no_candidate = day_df[day_df["reason"].isin(["no_candidates", "market_gate_blocked"])].copy()
    if no_candidate.empty:
        print("(none)")
        return
    group_cols = ["month_key", "reason"]
    value_cols = [
        col
        for col in scan_cols + setup_cols
        if col in no_candidate.columns and col not in {"scan_universe", "scan_passed_scan"}
    ]
    monthly = no_candidate[group_cols + value_cols].copy()
    for col in value_cols:
        monthly[col] = pd.to_numeric(monthly[col], errors="coerce").fillna(0)
    monthly = monthly.groupby(group_cols, dropna=False)[value_cols].sum().reset_index()
    if value_cols:
        monthly["top_bottleneck"] = monthly[value_cols].idxmax(axis=1)
        monthly["top_bottleneck_count"] = monthly[value_cols].max(axis=1).astype(int)
    _print_frame(monthly[["month_key", "reason", "top_bottleneck", "top_bottleneck_count"]], top_n)


def summarize_candidates(candidate_df, top_n):
    _print_section("TRAIN CANDIDATE STATUS")
    status = (
        candidate_df.groupby(["source_bucket", "setup_type", "execution_status"], dropna=False)
        .agg(
            candidates=("code", "count"),
            selected=("selected", "sum"),
            opened=("opened", "sum"),
            avg_score=("score", "mean"),
            avg_modeled_pnl_100=("modeled_net_pnl_per_100", "mean"),
            total_modeled_pnl_100=("modeled_net_pnl_per_100", "sum"),
        )
        .reset_index()
        .sort_values(["opened", "total_modeled_pnl_100", "candidates"], ascending=[False, False, False])
    )
    _print_frame(status, top_n)

    _print_section("UNSELECTED MODELED EDGE BY SETUP / WEEKDAY")
    unselected = candidate_df[candidate_df["execution_status"] == "not_selected"].copy()
    if unselected.empty:
        print("(none)")
        return
    unselected["modeled_win"] = unselected["modeled_net_pnl_per_100"] > 0
    edge = (
        unselected.groupby(["setup_type", "weekday"], dropna=False)
        .agg(
            candidates=("code", "count"),
            months=("month_key", "nunique"),
            win_rate=("modeled_win", "mean"),
            avg_pnl_100=("modeled_net_pnl_per_100", "mean"),
            total_pnl_100=("modeled_net_pnl_per_100", "sum"),
            avg_score=("score", "mean"),
            avg_breadth=("breadth", "mean"),
            avg_market_ratio=("market_ratio", "mean"),
        )
        .reset_index()
    )
    edge["win_rate"] *= 100.0
    edge = edge.sort_values(["total_pnl_100", "months", "candidates"], ascending=[False, False, False])
    _print_frame(edge, top_n)


def main(argv=None):
    args = build_parser().parse_args(argv)
    prepared, daily_stats, trade_log, candidate_log = replay_candidate_log(args.cache_path)
    holdout_start = _resolve_holdout_start_date(
        prepared["timeline"],
        args.holdout_months,
        earliest_holdout_start=FROZEN_HOLDOUT_START,
    )
    latest = pd.Timestamp(prepared["timeline"][-1]).strftime("%Y-%m-%d")

    day_df = pd.DataFrame(candidate_log["days"])
    candidate_df = pd.DataFrame(candidate_log["candidates"])
    train_day_df = _filter_train(day_df, holdout_start)
    train_candidate_df = _filter_train(candidate_df, holdout_start)

    print(f"DATA LATEST: {latest}")
    print(f"TRAIN WINDOW: {WARMUP_START} to {pd.Timestamp(holdout_start).date() if holdout_start else latest} (exclusive holdout start)")
    print(f"HOLDOUT START: {holdout_start or '(none)'}")
    print(f"TRAIN DAYS: {len(train_day_df):,}")
    print(f"TRAIN CANDIDATES: {len(train_candidate_df):,}")
    print(f"TRAIN TRADES: {len(_filter_train(pd.DataFrame(trade_log), holdout_start)):,}")

    summarize_day_reasons(train_day_df, args.top_n)
    summarize_scan_reasons(train_day_df, args.top_n)
    summarize_candidates(train_candidate_df, args.top_n)

    if args.output_day_csv:
        out = Path(args.output_day_csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        train_day_df.to_csv(out, index=False, encoding="utf-8-sig")
    if args.output_candidate_csv:
        out = Path(args.output_candidate_csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        train_candidate_df.to_csv(out, index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
