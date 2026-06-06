import argparse
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.append(os.getcwd())

from backtest import run_backtest_v16_production, _resolve_intraday_exit
from core.config import (
    DAYTRADE_API_EXPLICIT_TRADE_COST,
    INITIAL_CASH,
    SLIPPAGE_RATE,
    TAX_RATE,
)
from core.logic import get_daytrade_week_key
from core.monthly_rotation_strategy import build_rotation_backtest_inputs_from_cache
from jp_backtest import WARMUP_START, _resolve_holdout_start_date


STOP_EXIT_REASONS = {"open_stop", "intraday_stop", "intraday_stop_priority"}
TARGET_EXIT_REASONS = {"open_target", "intraday_target"}
MISS_WEEK_REDUCTION_FRACS = (0.25, 0.50, 0.75, 1.00)


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Replay the current JP day-trade backtest once and summarize train-only "
            "miss weeks, worst days, primary stop clusters, and primary close-loss fades."
        )
    )
    parser.add_argument(
        "--cache-path",
        default="data_cache/jp_broad/jp_mega_cache.pkl",
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
        default=12,
        help="Number of rows to print in each detail section.",
    )
    parser.add_argument(
        "--output-trades-csv",
        default="",
        help="Optional path to save the full replay trade log as CSV.",
    )
    return parser


def load_prepared_inputs(cache_path):
    with open(cache_path, "rb") as f:
        data = pickle.load(f)
    prepared = build_rotation_backtest_inputs_from_cache(data)
    univ_indices = np.asarray(prepared.get("univ_indices", []), dtype=int)
    return prepared, univ_indices


def replay_backtest(cache_path):
    prepared, univ_indices = load_prepared_inputs(cache_path)
    bundle_np = prepared["bundle_np"]
    timeline = prepared["timeline"]
    breadth_series = prepared["breadth_series"]
    _, _, _, _, daily_stats, trade_log = run_backtest_v16_production(
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
    return prepared, daily_stats, trade_log


def infer_trade_exit_reasons(trades_df, prepared):
    if trades_df.empty:
        return pd.Series(dtype=object, index=trades_df.index)

    bundle_np = prepared["bundle_np"]
    tickers = [str(ticker) for ticker in bundle_np.get("tickers", [])]
    ticker_to_idx = {ticker: idx for idx, ticker in enumerate(tickers)}
    day_to_idx = {str(pd.Timestamp(ts).date()): idx for idx, ts in enumerate(prepared["timeline"])}

    open_np = bundle_np["Open"]
    high_np = bundle_np["High"]
    low_np = bundle_np["Low"]
    close_np = bundle_np["Close"]

    reasons = []
    for row in trades_df.itertuples(index=False):
        day_key = str(getattr(row, "day_key", ""))
        code = str(getattr(row, "code", ""))
        day_idx = day_to_idx.get(day_key)
        s_idx = ticker_to_idx.get(code)
        if day_idx is None or s_idx is None:
            reasons.append("missing_lookup_fallback")
            continue

        entry_price = float(getattr(row, "entry_price", float("nan")))
        stop_price = float(getattr(row, "stop_price", float("nan")))
        target_price = float(getattr(row, "target_price", float("nan")))
        if not np.isfinite([entry_price, stop_price, target_price]).all():
            reasons.append("missing_ohlc_fallback")
            continue

        _raw_exit, exit_reason = _resolve_intraday_exit(
            entry_price=entry_price,
            open_price=float(open_np[day_idx, s_idx]),
            high_price=float(high_np[day_idx, s_idx]),
            low_price=float(low_np[day_idx, s_idx]),
            close_price=float(close_np[day_idx, s_idx]),
            stop_price=stop_price,
            target_price=target_price,
        )
        reasons.append(exit_reason if isinstance(exit_reason, str) else "missing_ohlc_fallback")

    return pd.Series(reasons, index=trades_df.index, dtype=object)


def add_trade_price_features(trades_df, prepared):
    if trades_df.empty:
        return trades_df.copy()

    bundle_np = prepared["bundle_np"]
    tickers = [str(ticker) for ticker in bundle_np.get("tickers", [])]
    ticker_to_idx = {ticker: idx for idx, ticker in enumerate(tickers)}
    day_to_idx = {str(pd.Timestamp(ts).date()): idx for idx, ts in enumerate(prepared["timeline"])}

    high_np = bundle_np["High"]
    close_np = bundle_np["Close"]

    enriched = trades_df.copy()
    high_return_pct = []
    close_return_pct = []
    fade_from_high_pct = []

    for row in enriched.itertuples(index=False):
        day_idx = day_to_idx.get(str(getattr(row, "day_key", "")))
        s_idx = ticker_to_idx.get(str(getattr(row, "code", "")))
        entry_price = float(getattr(row, "entry_price", float("nan")))
        exit_price = float(getattr(row, "exit_price", float("nan")))

        if (
            day_idx is None
            or s_idx is None
            or not np.isfinite(entry_price)
            or entry_price <= 0.0
            or not np.isfinite(exit_price)
        ):
            high_return_pct.append(np.nan)
            close_return_pct.append(np.nan)
            fade_from_high_pct.append(np.nan)
            continue

        day_high = float(high_np[day_idx, s_idx])
        day_close = float(close_np[day_idx, s_idx])
        if not np.isfinite(day_high) or not np.isfinite(day_close):
            high_return_pct.append(np.nan)
            close_return_pct.append(np.nan)
            fade_from_high_pct.append(np.nan)
            continue

        high_ret = (day_high - entry_price) / entry_price * 100.0
        close_ret = (exit_price - entry_price) / entry_price * 100.0
        high_return_pct.append(high_ret)
        close_return_pct.append(close_ret)
        fade_from_high_pct.append(high_ret - close_ret)

    enriched["high_return_pct"] = high_return_pct
    enriched["close_return_pct"] = close_return_pct
    enriched["fade_from_high_pct"] = fade_from_high_pct
    return enriched


def build_daily_frame(daily_stats):
    return pd.DataFrame([{"day_key": day_key, **values} for day_key, values in daily_stats.items()]).sort_values(
        "day_key"
    )


def classify_exit_bucket(trades_df, prepared=None):
    classified = trades_df.copy()
    if classified.empty:
        classified["exit_bucket"] = pd.Series(dtype=object)
        return classified
    exit_reason = classified.get("exit_reason", pd.Series(index=classified.index, dtype=object)).fillna("")
    if prepared is not None and (exit_reason.eq("").any() or "exit_reason" not in classified.columns):
        inferred = infer_trade_exit_reasons(classified, prepared)
        exit_reason = exit_reason.where(exit_reason.ne(""), inferred)
    classified["exit_reason"] = exit_reason
    classified["exit_bucket"] = np.where(
        exit_reason.isin(STOP_EXIT_REASONS),
        "stop",
        np.where(exit_reason.isin(TARGET_EXIT_REASONS), "target", "close_or_open"),
    )
    return classified


def build_train_frames(timeline, daily_df, trades_df, holdout_months):
    holdout_start = _resolve_holdout_start_date(timeline, holdout_months)
    if holdout_start is None:
        train_end = str(pd.Timestamp(timeline[-1]).date())
    else:
        train_end = (pd.Timestamp(holdout_start) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    train_start = str(daily_df["day_key"].min()) if not daily_df.empty else str(pd.Timestamp(timeline[0]).date())
    train_daily = daily_df[(daily_df["day_key"] >= train_start) & (daily_df["day_key"] <= train_end)].copy()
    train_trades = trades_df[(trades_df["day_key"] >= train_start) & (trades_df["day_key"] <= train_end)].copy()
    return train_start, train_end, holdout_start, train_daily, train_trades


def build_train_week_table(train_daily, all_daily, warmup_start=None):
    if train_daily.empty:
        return pd.DataFrame(
            columns=["week_key", "start_equity", "pnl", "trade_count", "hit_1pct", "positive"]
        ).set_index("week_key")

    train_daily = train_daily.copy()
    all_daily = all_daily.copy()
    warmup_ts = pd.Timestamp(warmup_start).normalize() if warmup_start else None
    train_daily["week_key"] = pd.to_datetime(train_daily["day_key"]).map(get_daytrade_week_key)
    all_daily["week_key"] = pd.to_datetime(all_daily["day_key"]).map(get_daytrade_week_key)

    train_bounds = train_daily.groupby("week_key")["day_key"].agg(train_min="min", train_max="max")
    all_bounds = all_daily.groupby("week_key")["day_key"].agg(all_min="min", all_max="max")
    bounds = train_bounds.join(all_bounds, how="left")
    full_weeks_mask = (bounds["train_min"] == bounds["all_min"]) & (bounds["train_max"] == bounds["all_max"])
    if warmup_ts is not None:
        full_weeks_mask = full_weeks_mask & (pd.to_datetime(bounds["all_min"]).dt.normalize() >= warmup_ts)
    full_weeks = set(bounds[full_weeks_mask].index)

    rows = []
    for week_key, group in train_daily.groupby("week_key", sort=True):
        if week_key not in full_weeks:
            continue
        start_equity = float(group.iloc[0]["equity"] - group.iloc[0]["day_pnl"])
        pnl = float(group["day_pnl"].sum())
        trade_count = int(group["trade_count"].sum())
        rows.append(
            {
                "week_key": week_key,
                "start_equity": start_equity,
                "pnl": pnl,
                "trade_count": trade_count,
                "hit_1pct": pnl >= (start_equity * 0.01),
                "positive": pnl > 0.0,
            }
        )
    return pd.DataFrame(rows).set_index("week_key") if rows else pd.DataFrame().set_index(pd.Index([], name="week_key"))


def summarize_setup_contribution(trades_df, group_cols, top_n):
    if trades_df.empty:
        return pd.DataFrame()
    return (
        trades_df.groupby(group_cols, dropna=False, observed=False)
        .agg(
            trades=("net_pnl", "size"),
            wins=("net_pnl", lambda values: int((values > 0).sum())),
            pnl=("net_pnl", "sum"),
            avg=("net_pnl", "mean"),
        )
        .sort_values("pnl")
        .head(top_n)
        .reset_index()
    )


def add_cluster_bins(trades_df):
    clustered = trades_df.copy()
    if clustered.empty:
        return clustered
    clustered["breadth_bin"] = pd.cut(
        clustered["breadth"],
        bins=[-np.inf, 0.45, 0.55, 0.65, 0.75, np.inf],
        labels=["<0.45", "0.45-0.55", "0.55-0.65", "0.65-0.75", ">=0.75"],
    )
    clustered["market_bin"] = pd.cut(
        clustered["market_ratio"],
        bins=[-np.inf, 1.0, 1.05, 1.10, 1.15, 1.20, np.inf],
        labels=["<1.00", "1.00-1.05", "1.05-1.10", "1.10-1.15", "1.15-1.20", ">=1.20"],
    )
    clustered["gap_bin"] = pd.cut(
        clustered["gap_pct"],
        bins=[-np.inf, 0.0, 0.005, 0.01, 0.015, 0.02, np.inf],
        labels=["<=0", "0-0.5%", "0.5-1.0%", "1.0-1.5%", "1.5-2.0%", ">=2.0%"],
    )
    clustered["score_bin"] = pd.cut(
        clustered["score"],
        bins=[-np.inf, 6.0, 8.0, 10.0, 12.0, 14.0, np.inf],
        labels=["<=6", "6-8", "8-10", "10-12", "12-14", ">=14"],
    )
    clustered["trend_bin"] = pd.cut(
        clustered["open_vs_sma_atr"],
        bins=[-np.inf, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0, np.inf],
        labels=["<0", "0-1", "1-2", "2-3", "3-4", "4-5", ">=5"],
    )
    return clustered


def summarize_trade_clusters(trades_df, top_n):
    if trades_df.empty:
        return {}
    clustered = add_cluster_bins(trades_df)
    return {
        "weekday": summarize_setup_contribution(clustered, ["weekday"], top_n),
        "breadth_bin": summarize_setup_contribution(clustered, ["breadth_bin"], top_n),
        "market_bin": summarize_setup_contribution(clustered, ["market_bin"], top_n),
        "gap_bin": summarize_setup_contribution(clustered, ["gap_bin"], top_n),
        "score_bin": summarize_setup_contribution(clustered, ["score_bin"], top_n),
        "trend_bin": summarize_setup_contribution(clustered, ["trend_bin"], top_n),
    }


def _frame_preview(df):
    if df is None or df.empty:
        return "(no rows)"
    return df.to_string(index=False)


def build_primary_close_fade_table(primary_close_loss_df, top_n):
    if primary_close_loss_df.empty:
        return pd.DataFrame()
    columns = [
        "day_key",
        "code",
        "net_pnl",
        "high_return_pct",
        "close_return_pct",
        "fade_from_high_pct",
        "exit_reason",
        "breadth",
        "market_ratio",
        "gap_pct",
        "prev_return",
        "open_vs_sma_atr",
        "rs_alpha",
    ]
    available_columns = [column for column in columns if column in primary_close_loss_df.columns]
    return (
        primary_close_loss_df.sort_values(["fade_from_high_pct", "net_pnl"])
        .loc[:, available_columns]
        .head(top_n)
        .copy()
    )


def build_miss_week_sensitivity_table(week_table, train_trades, reduction_fracs=MISS_WEEK_REDUCTION_FRACS):
    columns = [
        "week_key",
        "start_equity",
        "pnl",
        "trade_count",
        "ret_pct",
        "gap_to_target_pct",
        "negative_trade_count",
        "total_negative_pnl",
        "worst_trade_pnl",
        "worst_trade_setup",
        "worst_trade_exit_bucket",
        "primary_stop_pnl",
        "worst_trade_loss_share",
    ]
    if week_table.empty:
        return pd.DataFrame(columns=columns)

    miss_table = week_table.loc[~week_table["hit_1pct"], ["start_equity", "pnl", "trade_count"]].copy()
    if miss_table.empty:
        return pd.DataFrame(columns=columns)

    miss_trades = train_trades[train_trades["week_key"].isin(miss_table.index)].copy()
    miss_table["ret_pct"] = np.where(
        miss_table["start_equity"] > 0.0,
        miss_table["pnl"] / miss_table["start_equity"] * 100.0,
        np.nan,
    )
    miss_table["gap_to_target_pct"] = 1.0 - miss_table["ret_pct"]

    negative_trades = miss_trades[miss_trades["net_pnl"] < 0.0].copy()
    negative_summary = (
        negative_trades.groupby("week_key", observed=False)
        .agg(
            negative_trade_count=("net_pnl", "size"),
            total_negative_pnl=("net_pnl", "sum"),
        )
        .copy()
        if not negative_trades.empty
        else pd.DataFrame(columns=["negative_trade_count", "total_negative_pnl"])
    )
    miss_table = miss_table.join(negative_summary, how="left")

    if negative_trades.empty:
        miss_table["worst_trade_pnl"] = 0.0
        miss_table["worst_trade_setup"] = ""
        miss_table["worst_trade_exit_bucket"] = ""
    else:
        worst_trade_idx = negative_trades.groupby("week_key", observed=False)["net_pnl"].idxmin()
        worst_trades = (
            negative_trades.loc[worst_trade_idx, ["week_key", "net_pnl", "setup_type", "exit_bucket"]]
            .rename(
                columns={
                    "net_pnl": "worst_trade_pnl",
                    "setup_type": "worst_trade_setup",
                    "exit_bucket": "worst_trade_exit_bucket",
                }
            )
            .set_index("week_key")
        )
        miss_table = miss_table.join(worst_trades, how="left")

    primary_stop = miss_trades[
        (miss_trades["setup_type"] == "primary")
        & (miss_trades["exit_bucket"] == "stop")
        & (miss_trades["net_pnl"] < 0.0)
    ]
    primary_stop_summary = (
        primary_stop.groupby("week_key", observed=False)["net_pnl"].sum().rename("primary_stop_pnl")
        if not primary_stop.empty
        else pd.Series(dtype=float, name="primary_stop_pnl")
    )
    miss_table = miss_table.join(primary_stop_summary, how="left")

    miss_table["negative_trade_count"] = miss_table["negative_trade_count"].fillna(0).astype(int)
    miss_table["total_negative_pnl"] = miss_table["total_negative_pnl"].fillna(0.0)
    miss_table["worst_trade_pnl"] = miss_table["worst_trade_pnl"].fillna(0.0)
    miss_table["worst_trade_setup"] = miss_table["worst_trade_setup"].fillna("")
    miss_table["worst_trade_exit_bucket"] = miss_table["worst_trade_exit_bucket"].fillna("")
    miss_table["primary_stop_pnl"] = miss_table["primary_stop_pnl"].fillna(0.0)
    miss_table["worst_trade_loss_share"] = np.where(
        miss_table["total_negative_pnl"] < 0.0,
        miss_table["worst_trade_pnl"].abs() / miss_table["total_negative_pnl"].abs(),
        0.0,
    )

    for reduction_frac in reduction_fracs:
        pct_label = int(round(float(reduction_frac) * 100))
        miss_table[f"flip_if_reduce_worst_{pct_label}pct"] = (
            miss_table["pnl"] + miss_table["worst_trade_pnl"].clip(upper=0.0).abs() * float(reduction_frac)
        ) >= (miss_table["start_equity"] * 0.01)
        miss_table[f"flip_if_reduce_primary_stop_{pct_label}pct"] = (
            miss_table["pnl"] + miss_table["primary_stop_pnl"].clip(upper=0.0).abs() * float(reduction_frac)
        ) >= (miss_table["start_equity"] * 0.01)

    miss_table = miss_table.reset_index().rename(columns={"index": "week_key"})
    return miss_table.sort_values(["ret_pct", "gap_to_target_pct"], ascending=[False, True]).reset_index(drop=True)


def build_miss_week_flip_potential_table(
    miss_week_sensitivity_df,
    reduction_fracs=MISS_WEEK_REDUCTION_FRACS,
):
    columns = ["scenario", "flipped_weeks", "total_miss_weeks", "flip_rate"]
    if miss_week_sensitivity_df.empty:
        return pd.DataFrame(columns=columns)

    total_miss_weeks = int(len(miss_week_sensitivity_df))
    rows = []
    for scenario_key, label in (("worst", "reduce_worst_trade"), ("primary_stop", "reduce_primary_stop")):
        for reduction_frac in reduction_fracs:
            pct_label = int(round(float(reduction_frac) * 100))
            column = f"flip_if_reduce_{scenario_key}_{pct_label}pct"
            flipped_weeks = int(miss_week_sensitivity_df[column].sum()) if column in miss_week_sensitivity_df else 0
            rows.append(
                {
                    "scenario": f"{label}_{pct_label}pct",
                    "flipped_weeks": flipped_weeks,
                    "total_miss_weeks": total_miss_weeks,
                    "flip_rate": flipped_weeks / total_miss_weeks if total_miss_weeks else 0.0,
                }
            )
    return pd.DataFrame(rows, columns=columns)


def build_miss_week_loss_dominance_table(miss_week_sensitivity_df):
    columns = ["metric", "value"]
    if miss_week_sensitivity_df.empty:
        return pd.DataFrame(columns=columns)

    dominance = miss_week_sensitivity_df["worst_trade_loss_share"].fillna(0.0)
    rows = [
        {"metric": "miss_weeks", "value": int(len(miss_week_sensitivity_df))},
        {"metric": "mean_worst_trade_loss_share", "value": float(dominance.mean())},
        {"metric": "median_worst_trade_loss_share", "value": float(dominance.median())},
        {"metric": "weeks_worst_trade_gt_50pct_losses", "value": int((dominance > 0.50).sum())},
        {"metric": "weeks_worst_trade_gt_75pct_losses", "value": int((dominance > 0.75).sum())},
        {
            "metric": "weeks_with_primary_stop_loss",
            "value": int((miss_week_sensitivity_df["primary_stop_pnl"] < 0.0).sum()),
        },
    ]
    return pd.DataFrame(rows, columns=columns)


def build_closest_miss_weeks_table(miss_week_sensitivity_df, top_n):
    if miss_week_sensitivity_df.empty:
        return pd.DataFrame()
    columns = [
        "week_key",
        "start_equity",
        "pnl",
        "ret_pct",
        "gap_to_target_pct",
        "trade_count",
        "negative_trade_count",
        "worst_trade_pnl",
        "worst_trade_setup",
        "worst_trade_exit_bucket",
        "primary_stop_pnl",
        "worst_trade_loss_share",
    ]
    available_columns = [column for column in columns if column in miss_week_sensitivity_df.columns]
    return miss_week_sensitivity_df.loc[:, available_columns].head(top_n).copy()


def build_report(summary, top_n):
    lines = [
        "BACKTEST TRAIN ANALYSIS",
        f"train:   {summary['train_start']} to {summary['train_end']}",
        f"holdout: {summary['holdout_start'] or '(none)'} to {summary['latest_day']}",
        "",
        "Miss Week Summary",
        (
            f"train weeks={summary['train_week_count']} | miss={summary['miss_week_count']} | "
            f"negative={summary['negative_miss_weeks']} | positive_miss={summary['positive_miss_weeks']} | "
            f"miss_no_trade={summary['miss_no_trade_weeks']}"
        ),
        "",
        "Miss-Week Setup Contribution",
        _frame_preview(summary["miss_setup"].head(top_n)),
        "",
        "Miss-Week Exit Buckets",
        _frame_preview(summary["miss_exit"].head(top_n)),
        "",
        "Closest Miss Weeks",
        _frame_preview(summary["closest_miss_weeks"]),
        "",
        "Miss-Week Flip Potential",
        _frame_preview(summary["miss_week_flip_potential"]),
        "",
        "Miss-Week Loss Dominance",
        _frame_preview(summary["miss_week_loss_dominance"]),
        "",
        "Worst Train Days",
        _frame_preview(summary["worst_days"].head(top_n)),
        "",
        "Worst-Day Trades",
        _frame_preview(summary["worst_day_trades"].head(top_n)),
        "",
        "Primary Stop Clusters",
    ]
    for key, df in summary["primary_stop_clusters"].items():
        lines.extend(["", f"[{key}]", _frame_preview(df.head(top_n))])
    lines.extend(["", "Primary Close-Loss Clusters"])
    for key, df in summary["primary_close_clusters"].items():
        lines.extend(["", f"[{key}]", _frame_preview(df.head(top_n))])
    lines.extend(["", "Worst Primary Close Fades", _frame_preview(summary["primary_close_fades"].head(top_n))])
    return "\n".join(lines)


def analyze_backtest_trade_log(cache_path, holdout_months=6, top_n=12):
    prepared, daily_stats, trade_log = replay_backtest(cache_path)
    timeline = prepared["timeline"]
    daily_df = build_daily_frame(daily_stats)
    trades_df = classify_exit_bucket(pd.DataFrame(trade_log), prepared=prepared)
    trades_df = add_trade_price_features(trades_df, prepared=prepared)
    trades_df["date"] = pd.to_datetime(trades_df["day_key"], errors="coerce")
    trades_df["weekday"] = trades_df["date"].dt.day_name()

    train_start, train_end, holdout_start, train_daily, train_trades = build_train_frames(
        timeline, daily_df, trades_df, holdout_months
    )
    week_table = build_train_week_table(train_daily, daily_df, warmup_start=WARMUP_START)
    miss_weeks = set(week_table.index[~week_table["hit_1pct"]]) if not week_table.empty else set()
    miss_trades = train_trades[train_trades["week_key"].isin(miss_weeks)].copy()
    miss_week_sensitivity = build_miss_week_sensitivity_table(week_table, train_trades)
    primary_stop = train_trades[
        (train_trades["setup_type"] == "primary") & (train_trades["exit_bucket"] == "stop")
    ].copy()
    primary_close_loss = train_trades[
        (train_trades["setup_type"] == "primary")
        & (train_trades["exit_bucket"] == "close_or_open")
        & (train_trades["net_pnl"] < 0.0)
    ].copy()

    worst_days = (
        train_daily.nsmallest(top_n, "day_pnl")[["day_key", "day_pnl", "trade_count", "equity"]].copy()
        if not train_daily.empty
        else pd.DataFrame()
    )
    worst_day_keys = set(worst_days["day_key"]) if not worst_days.empty else set()
    worst_day_columns = [
        "day_key",
        "setup_type",
        "code",
        "net_pnl",
        "exit_reason",
        "score",
        "breadth",
        "market_ratio",
        "gap_pct",
        "prev_return",
        "open_vs_sma_atr",
        "rs_alpha",
    ]
    available_worst_day_columns = [column for column in worst_day_columns if column in train_trades.columns]
    worst_day_trades = (
        train_trades[train_trades["day_key"].isin(worst_day_keys)]
        .sort_values(["day_key", "net_pnl"])[available_worst_day_columns]
        .copy()
        if worst_day_keys
        else pd.DataFrame()
    )

    return {
        "prepared": prepared,
        "daily_df": daily_df,
        "trades_df": trades_df,
        "train_start": train_start,
        "train_end": train_end,
        "holdout_start": holdout_start,
        "latest_day": str(pd.Timestamp(timeline[-1]).date()),
        "train_week_count": int(len(week_table)),
        "miss_week_count": int((~week_table["hit_1pct"]).sum()) if not week_table.empty else 0,
        "negative_miss_weeks": int((week_table.loc[~week_table["hit_1pct"], "pnl"] <= 0).sum())
        if not week_table.empty
        else 0,
        "positive_miss_weeks": int((week_table.loc[~week_table["hit_1pct"], "pnl"] > 0).sum())
        if not week_table.empty
        else 0,
        "miss_no_trade_weeks": int((week_table.loc[~week_table["hit_1pct"], "trade_count"] == 0).sum())
        if not week_table.empty
        else 0,
        "week_table": week_table,
        "miss_weeks": miss_weeks,
        "miss_setup": summarize_setup_contribution(miss_trades, ["setup_type"], top_n),
        "miss_exit": summarize_setup_contribution(miss_trades, ["setup_type", "exit_bucket"], top_n),
        "miss_week_sensitivity": miss_week_sensitivity,
        "closest_miss_weeks": build_closest_miss_weeks_table(miss_week_sensitivity, top_n),
        "miss_week_flip_potential": build_miss_week_flip_potential_table(miss_week_sensitivity),
        "miss_week_loss_dominance": build_miss_week_loss_dominance_table(miss_week_sensitivity),
        "worst_days": worst_days,
        "worst_day_trades": worst_day_trades,
        "primary_stop_clusters": summarize_trade_clusters(
            primary_stop[primary_stop["week_key"].isin(miss_weeks)], top_n
        ),
        "primary_close_clusters": summarize_trade_clusters(
            primary_close_loss[primary_close_loss["week_key"].isin(miss_weeks)], top_n
        ),
        "primary_close_fades": build_primary_close_fade_table(
            primary_close_loss[primary_close_loss["week_key"].isin(miss_weeks)],
            top_n,
        ),
    }


def main(argv=None):
    args = build_parser().parse_args(argv)
    summary = analyze_backtest_trade_log(
        cache_path=args.cache_path,
        holdout_months=max(0, int(args.holdout_months)),
        top_n=max(1, int(args.top_n)),
    )
    if args.output_trades_csv:
        summary["trades_df"].to_csv(args.output_trades_csv, index=False, encoding="utf-8-sig")
    print(build_report(summary, top_n=max(1, int(args.top_n))))


if __name__ == "__main__":
    main()
