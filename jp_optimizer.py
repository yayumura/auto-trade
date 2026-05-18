import argparse
import concurrent.futures
import os
import pickle
import sys

import numpy as np
import pandas as pd

# Append current directory to sys.path
sys.path.append(os.getcwd())

from backtest import run_backtest_v16_production
from core.config import (
    BEAR_GAP_LIMIT,
    EXIT_ON_SMA20_BREACH,
    INITIAL_CASH,
    LIQUIDITY_LIMIT_RATE,
    SLIPPAGE_RATE,
)
from core.monthly_rotation_strategy import build_rotation_backtest_inputs_from_cache
from jp_backtest import (
    WARMUP_START,
    _filter_trade_log_window,
    _refresh_cache_if_requested,
    _resolve_holdout_start_date,
    _summarize_window,
)

DEFAULT_MIN_TRAIN_MONTHS = 24
DEFAULT_ROBUSTNESS_WINDOW_MONTHS = 3
DEFAULT_ROBUSTNESS_STEP_MONTHS = 1


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Optimize parameter candidates on the JP day-trade strategy using train-only ranking, "
            "then optionally replay the top candidates on a trailing holdout window."
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
        default=1,
        help=(
            "Trailing calendar-month span reserved as holdout. "
            "Ranking is done on train only. Use 0 to disable holdout splitting."
        ),
    )
    parser.add_argument(
        "--top-k-holdout",
        type=int,
        default=10,
        help="Replay the top N train-ranked candidates on full history and print their holdout metrics.",
    )
    parser.add_argument(
        "--output-csv",
        default="opt_results.csv",
        help="CSV path for train-ranked results and any attached holdout review columns.",
    )
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Refresh the JP cache before running train/holdout optimization.",
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
        "--min-train-months",
        type=int,
        default=DEFAULT_MIN_TRAIN_MONTHS,
        help=(
            "Require at least this many calendar months in the train window before ranking candidates. "
            "This guards against fitting short, recently refreshed slices."
        ),
    )
    parser.add_argument(
        "--robustness-window-months",
        type=int,
        default=DEFAULT_ROBUSTNESS_WINDOW_MONTHS,
        help="Rolling train subwindow length used to score consistency inside train.",
    )
    parser.add_argument(
        "--robustness-step-months",
        type=int,
        default=DEFAULT_ROBUSTNESS_STEP_MONTHS,
        help="Calendar-month step between consecutive train robustness windows.",
    )
    return parser.parse_args()


def _build_empty_metric_record(score=-9999.0, reason="insufficient_data"):
    return {
        "pf": 0.0,
        "win_rate": 0.0,
        "mdd": 100.0,
        "worst_day_pct": 100.0,
        "plus_1pct_week_rate": 0.0,
        "positive_week_rate": 0.0,
        "avg_month_active_rate": 0.0,
        "months_3q_active": 0,
        "month_count": 0,
        "window_count": 0,
        "positive_window_rate": 0.0,
        "median_window_return_pct": 0.0,
        "worst_window_return_pct": 0.0,
        "median_window_pf": 0.0,
        "eligible": False,
        "eligibility_failures": reason,
        "score": float(score),
    }


def _normalize_day_keys(timeline):
    return [pd.Timestamp(ts).strftime("%Y-%m-%d") for ts in timeline]


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


def _describe_timeline_span(timeline):
    timeline_index = pd.DatetimeIndex(pd.to_datetime(timeline))
    if len(timeline_index) == 0:
        return {
            "start_date": None,
            "end_date": None,
            "day_count": 0,
            "calendar_month_span": 0,
        }

    start_ts = timeline_index[0].normalize()
    end_ts = timeline_index[-1].normalize()
    calendar_month_span = (end_ts.year - start_ts.year) * 12 + (end_ts.month - start_ts.month)
    return {
        "start_date": start_ts.strftime("%Y-%m-%d"),
        "end_date": end_ts.strftime("%Y-%m-%d"),
        "day_count": len(timeline_index),
        "calendar_month_span": int(calendar_month_span),
    }


def _validate_train_timeline_or_raise(timeline, min_train_months=DEFAULT_MIN_TRAIN_MONTHS):
    timeline_index = pd.DatetimeIndex(pd.to_datetime(timeline))
    if len(timeline_index) == 0:
        raise ValueError("Train window is empty. Check the cache path and holdout split.")

    if int(min_train_months) <= 0:
        return

    start_ts = timeline_index[0].normalize()
    end_ts = timeline_index[-1].normalize()
    if end_ts >= start_ts + pd.DateOffset(months=int(min_train_months)):
        return

    span = _describe_timeline_span(timeline_index)
    raise ValueError(
        "Train window is too short for robust optimization: "
        f"{span['start_date']} to {span['end_date']} "
        f"({span['day_count']} trading days, {span['calendar_month_span']} calendar months). "
        f"Require at least {int(min_train_months)} calendar months. "
        "Rebuild the JP cache with `python jp_jquants_fetcher_v2.py --force-full-refresh` "
        "or temporarily lower `--min-train-months` only for a smoke test."
    )


def _build_robustness_windows(
    timeline,
    window_months=DEFAULT_ROBUSTNESS_WINDOW_MONTHS,
    step_months=DEFAULT_ROBUSTNESS_STEP_MONTHS,
    warmup_start=WARMUP_START,
):
    if int(window_months) <= 0:
        raise ValueError("window_months must be >= 1")
    if int(step_months) <= 0:
        raise ValueError("step_months must be >= 1")

    day_keys = _normalize_day_keys(timeline)
    if not day_keys:
        return []

    day_index = _resolve_day_index(day_keys)
    latest_day = day_index[-1]
    warmup_ts = pd.Timestamp(warmup_start).normalize()
    windows_recent_first = []
    seen_window_ends = set()
    step_count = 0

    while True:
        anchor_target = latest_day - pd.DateOffset(months=int(step_months) * step_count)
        window_end = _resolve_last_day_on_or_before(day_index, day_keys, anchor_target)
        if window_end is None:
            break
        if window_end in seen_window_ends:
            step_count += 1
            continue
        seen_window_ends.add(window_end)

        window_start = _resolve_first_day_after(
            day_index,
            day_keys,
            pd.Timestamp(window_end) - pd.DateOffset(months=int(window_months)),
        )
        if window_start is None:
            break
        if pd.Timestamp(window_start).normalize() < warmup_ts:
            break

        windows_recent_first.append(
            {
                "window_id": len(windows_recent_first) + 1,
                "start_date": window_start,
                "end_date": window_end,
            }
        )
        step_count += 1

    windows = list(reversed(windows_recent_first))
    for idx, window in enumerate(windows, start=1):
        window["window_id"] = idx
    return windows


def _calculate_window_drawdown_stats(daily_stats, start_date=None, end_date=None, initial_cash=INITIAL_CASH):
    window_day_keys = [
        day_key
        for day_key in sorted(daily_stats.keys())
        if (start_date is None or day_key >= start_date)
        and (end_date is None or day_key <= end_date)
    ]
    if not window_day_keys:
        return {"mdd": 100.0, "worst_day_pct": 100.0}

    first_day = window_day_keys[0]
    start_equity = float(daily_stats[first_day]["equity"]) - float(daily_stats[first_day]["day_pnl"])
    equity_curve = [max(float(initial_cash), start_equity)]
    worst_day_pct = 0.0

    for day_key in window_day_keys:
        equity = float(daily_stats[day_key]["equity"])
        day_pnl = float(daily_stats[day_key]["day_pnl"])
        prior_equity = equity - day_pnl
        if prior_equity > 0 and day_pnl < 0:
            worst_day_pct = max(worst_day_pct, abs(day_pnl / prior_equity) * 100.0)
        equity_curve.append(equity)

    curve_np = np.asarray(equity_curve, dtype=float)
    running_max = np.maximum.accumulate(curve_np)
    denom = np.where(running_max > 0, running_max, 1.0)
    drawdowns = (running_max - curve_np) / denom
    return {
        "mdd": float(np.max(drawdowns) * 100.0),
        "worst_day_pct": float(worst_day_pct),
    }


def _score_train_robustness(metrics):
    failures = []
    if int(metrics["trade_count"]) < 100:
        failures.append("trades<100")
    if int(metrics["week_count"]) < 26:
        failures.append("weeks<26")
    if int(metrics["window_count"]) < 6:
        failures.append("windows<6")
    if float(metrics["pf"]) < 1.20:
        failures.append("pf<1.20")
    if float(metrics["plus_1pct_week_rate"]) < 0.55:
        failures.append("plus_1pct_week_rate<55%")
    if float(metrics["positive_window_rate"]) < 0.55:
        failures.append("positive_window_rate<55%")

    upside = 0.0
    upside += float(metrics["plus_1pct_week_rate"]) * 450.0
    upside += float(metrics["positive_week_rate"]) * 175.0
    upside += float(metrics["positive_window_rate"]) * 175.0
    upside += min(max(float(metrics["median_window_return_pct"]), 0.0), 12.0) * 8.0
    upside += min(float(metrics["pf"]), 3.0) * 45.0
    upside += min(float(metrics["median_window_pf"]), 3.0) * 30.0
    upside += float(metrics["avg_month_active_rate"]) * 60.0

    downside = 0.0
    downside += float(metrics["mdd"]) * 8.0
    downside += float(metrics["worst_day_pct"]) * 90.0
    downside += max(0.0, -float(metrics["worst_window_return_pct"])) * 10.0
    if int(metrics["months_3q_active"]) == 0:
        downside += 25.0

    score = upside - downside
    if failures:
        score -= 20000.0

    return {
        "eligible": len(failures) == 0,
        "eligibility_failures": ",".join(failures) if failures else "",
        "score": float(score),
    }


def calculate_window_stability_metrics(
    daily_stats,
    trade_log,
    start_date,
    end_date,
    global_day_keys,
    initial_cash,
    robustness_windows=None,
    warmup_start=WARMUP_START,
):
    train_summary = _summarize_window(
        daily_stats=daily_stats,
        trade_log=trade_log,
        label="TRAIN",
        start_date=start_date,
        end_date=end_date,
        warmup_start=warmup_start,
        global_day_keys=global_day_keys,
    )
    if train_summary is None:
        return _build_empty_metric_record(reason="missing_train_window")

    window_trades = _filter_trade_log_window(trade_log, start_date=start_date, end_date=end_date)
    trade_results = [float(item["net_pnl"]) for item in window_trades]
    wins = [result for result in trade_results if result > 0]
    losses = [result for result in trade_results if result < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    pf = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)
    win_rate = (len(wins) / len(trade_results)) if trade_results else 0.0

    drawdown_stats = _calculate_window_drawdown_stats(
        daily_stats=daily_stats,
        start_date=start_date,
        end_date=end_date,
        initial_cash=initial_cash,
    )

    window_summaries = []
    for window in robustness_windows or []:
        summary = _summarize_window(
            daily_stats=daily_stats,
            trade_log=trade_log,
            label=f"ROBUSTNESS_{window['window_id']}",
            start_date=window["start_date"],
            end_date=window["end_date"],
            warmup_start=warmup_start,
            global_day_keys=global_day_keys,
        )
        if summary is None or int(summary["week_count"]) <= 0:
            continue

        window_pf = float(summary["profit_factor"])
        if not np.isfinite(window_pf):
            window_pf = 0.0

        window_summaries.append(
            {
                "return_pct": float(summary["total_return_pct"]),
                "pf": window_pf,
                "plus_1pct_week_rate": (
                    float(summary["plus_1pct_weeks"]) / float(summary["week_count"])
                    if int(summary["week_count"]) > 0
                    else 0.0
                ),
                "positive_week_rate": (
                    float(summary["positive_weeks"]) / float(summary["week_count"])
                    if int(summary["week_count"]) > 0
                    else 0.0
                ),
            }
        )

    full_month_rates = [float(rate) for rate in train_summary.get("full_month_rates", [])]
    avg_month_active_rate = float(np.mean(full_month_rates)) if full_month_rates else 0.0
    months_3q_active = sum(1 for rate in full_month_rates if rate >= 0.75)
    week_count = int(train_summary["week_count"])
    plus_1pct_week_rate = (
        float(train_summary["plus_1pct_weeks"]) / float(week_count) if week_count > 0 else 0.0
    )
    positive_week_rate = (
        float(train_summary["positive_weeks"]) / float(week_count) if week_count > 0 else 0.0
    )

    if window_summaries:
        window_returns = [item["return_pct"] for item in window_summaries]
        window_pfs = [item["pf"] for item in window_summaries]
        positive_window_rate = sum(1 for item in window_summaries if item["return_pct"] > 0.0) / len(window_summaries)
        median_window_return_pct = float(np.median(window_returns))
        worst_window_return_pct = float(np.min(window_returns))
        median_window_pf = float(np.median(window_pfs))
    else:
        positive_window_rate = 0.0
        median_window_return_pct = 0.0
        worst_window_return_pct = 0.0
        median_window_pf = 0.0

    metrics = {
        "pf": float(pf),
        "win_rate": float(win_rate),
        "mdd": float(drawdown_stats["mdd"]),
        "worst_day_pct": float(drawdown_stats["worst_day_pct"]),
        "plus_1pct_week_rate": float(plus_1pct_week_rate),
        "positive_week_rate": float(positive_week_rate),
        "avg_month_active_rate": float(avg_month_active_rate),
        "months_3q_active": int(months_3q_active),
        "month_count": len(full_month_rates),
        "window_count": len(window_summaries),
        "positive_window_rate": float(positive_window_rate),
        "median_window_return_pct": float(median_window_return_pct),
        "worst_window_return_pct": float(worst_window_return_pct),
        "median_window_pf": float(median_window_pf),
        "trade_count": len(trade_results),
        "week_count": week_count,
    }
    metrics.update(_score_train_robustness(metrics))
    return metrics


def _prepare_backtest_inputs(cache_path):
    print("WARNING: Ensure your dataset includes delisted tickers to avoid survivorship bias.")
    print(f"Loading JP Mega-Data Cache: {cache_path}")
    with open(cache_path, "rb") as handle:
        data = pickle.load(handle)

    prepared = build_rotation_backtest_inputs_from_cache(data)
    bundle = prepared["bundle"]
    bundle_np = prepared["bundle_np"]
    timeline = pd.DatetimeIndex(prepared["timeline"])
    breadth_series = np.asarray(prepared["breadth_series"], dtype=float)
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

    return {
        "bundle_np": bundle_np,
        "timeline": timeline,
        "breadth_series": breadth_series,
        "univ_indices": univ_indices,
    }


def _resolve_optimizer_split(timeline, holdout_months):
    holdout_start = _resolve_holdout_start_date(timeline, holdout_months)
    if holdout_start is None:
        return {"holdout_start": None, "train_end": None}

    train_end = (pd.Timestamp(holdout_start) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    return {
        "holdout_start": holdout_start,
        "train_end": train_end,
    }


def _slice_backtest_inputs(bundle_np, timeline, breadth_ratio, end_date=None):
    timeline_index = pd.DatetimeIndex(pd.to_datetime(timeline))
    breadth_np = np.asarray(breadth_ratio, dtype=float)
    if end_date is None:
        return bundle_np, timeline_index, breadth_np

    mask = timeline_index <= pd.Timestamp(end_date).normalize()
    if not mask.any():
        raise ValueError(f"No train data found on or before {end_date}.")

    sliced_bundle_np = {}
    for key, values in bundle_np.items():
        if isinstance(values, np.ndarray) and values.ndim >= 1 and values.shape[0] == len(timeline_index):
            sliced_bundle_np[key] = values[mask]
        else:
            sliced_bundle_np[key] = values

    return sliced_bundle_np, timeline_index[mask], breadth_np[mask]


def _build_param_grid():
    param_grid = {
        "breadth": [0.5, 0.6],
        "sl_mult": [3.0, 5.0, 7.0, 10.0],
        "tp_mult": [30.0, 40.0, 50.0, 60.0],
        "max_pos": [3, 5, 10],
        "leverage_rate": [1.0, 1.5],
        "bull_gap_limit": [0.11],
        "exit_buffer": [0.975],
        "max_hold_days": [30],
    }

    grid = []
    for breadth in param_grid["breadth"]:
        for sl_mult in param_grid["sl_mult"]:
            for tp_mult in param_grid["tp_mult"]:
                for max_pos in param_grid["max_pos"]:
                    for leverage_rate in param_grid["leverage_rate"]:
                        grid.append(
                            {
                                "breadth": breadth,
                                "exit_buffer": param_grid["exit_buffer"][0],
                                "sl": sl_mult,
                                "tp": tp_mult,
                                "max_pos": max_pos,
                                "leverage": leverage_rate,
                                "bgap": param_grid["bull_gap_limit"][0],
                                "max_hold_days": param_grid["max_hold_days"][0],
                            }
                        )
    return grid


def _run_parameterized_backtest(univ_indices, bundle_np, timeline, breadth_ratio, params, return_window_stats):
    result = run_backtest_v16_production(
        univ_indices=univ_indices,
        bundle_np=bundle_np,
        timeline=timeline,
        breadth_ratio=breadth_ratio,
        initial_cash=INITIAL_CASH,
        max_pos=params["max_pos"],
        sl_mult=params["sl"],
        tp_mult=params["tp"],
        leverage_rate=params["leverage"],
        breadth_threshold=params["breadth"],
        max_hold_days=params["max_hold_days"],
        slippage=SLIPPAGE_RATE,
        use_sma_exit=EXIT_ON_SMA20_BREACH,
        exit_buffer=params["exit_buffer"],
        liquidity_limit=LIQUIDITY_LIMIT_RATE,
        bull_gap_limit=params["bgap"],
        bear_gap_limit=BEAR_GAP_LIMIT,
        explicit_trade_cost=0.0,
        profit_tax_rate=0.0,
        return_daily_stats=return_window_stats,
        return_trade_log=return_window_stats,
        verbose=False,
    )
    if return_window_stats:
        final_assets, trade_count, monthly_assets, trade_results, daily_stats, trade_log = result
        return {
            "final_assets": final_assets,
            "trade_count": trade_count,
            "monthly_assets": monthly_assets,
            "trade_results": trade_results,
            "daily_stats": daily_stats,
            "trade_log": trade_log,
        }

    final_assets, trade_count, monthly_assets, trade_results = result
    return {
        "final_assets": final_assets,
        "trade_count": trade_count,
        "monthly_assets": monthly_assets,
        "trade_results": trade_results,
    }


def _format_week_metric(hit_count, week_count):
    return f"{int(hit_count)}/{int(week_count)}" if int(week_count) > 0 else "-"


def run_single_opt(params_pack):
    univ_indices, bundle_np, timeline, breadth_ratio, params, global_day_keys, robustness_windows = params_pack
    backtest_result = _run_parameterized_backtest(
        univ_indices=univ_indices,
        bundle_np=bundle_np,
        timeline=timeline,
        breadth_ratio=breadth_ratio,
        params=params,
        return_window_stats=True,
    )
    train_start = str(pd.Timestamp(timeline[0]).date())
    train_end = str(pd.Timestamp(timeline[-1]).date())
    metrics = calculate_window_stability_metrics(
        daily_stats=backtest_result["daily_stats"],
        trade_log=backtest_result["trade_log"],
        start_date=train_start,
        end_date=train_end,
        global_day_keys=global_day_keys,
        initial_cash=INITIAL_CASH,
        robustness_windows=robustness_windows,
    )
    train_summary = _summarize_window(
        daily_stats=backtest_result["daily_stats"],
        trade_log=backtest_result["trade_log"],
        label="TRAIN",
        start_date=train_start,
        end_date=train_end,
        warmup_start=WARMUP_START,
        global_day_keys=global_day_keys,
    )
    return {
        **params,
        "final": backtest_result["final_assets"],
        "trades": backtest_result["trade_count"],
        **metrics,
        "train_total_return_pct": float(train_summary["total_return_pct"]) if train_summary is not None else 0.0,
        "train_plus_1pct_weeks": int(train_summary["plus_1pct_weeks"]) if train_summary is not None else 0,
        "train_week_count": int(train_summary["week_count"]) if train_summary is not None else 0,
        "train_positive_weeks": int(train_summary["positive_weeks"]) if train_summary is not None else 0,
        "train_worst_day": float(train_summary["worst_day"]) if train_summary is not None else 0.0,
    }


def _evaluate_top_holdout_candidates(df_res, full_inputs, split_plan, top_k_holdout):
    holdout_start = split_plan["holdout_start"]
    train_end = split_plan["train_end"]
    if holdout_start is None or int(top_k_holdout) <= 0:
        return pd.DataFrame()

    top_candidates = df_res.head(int(top_k_holdout)).reset_index(drop=True)
    rows = []
    for _, candidate in top_candidates.iterrows():
        params = {
            "breadth": float(candidate["breadth"]),
            "exit_buffer": float(candidate["exit_buffer"]),
            "sl": float(candidate["sl"]),
            "tp": float(candidate["tp"]),
            "max_pos": int(candidate["max_pos"]),
            "leverage": float(candidate["leverage"]),
            "bgap": float(candidate["bgap"]),
            "max_hold_days": int(candidate["max_hold_days"]),
        }
        backtest_result = _run_parameterized_backtest(
            univ_indices=full_inputs["univ_indices"],
            bundle_np=full_inputs["bundle_np"],
            timeline=full_inputs["timeline"],
            breadth_ratio=full_inputs["breadth_series"],
            params=params,
            return_window_stats=True,
        )
        train_summary = _summarize_window(
            daily_stats=backtest_result["daily_stats"],
            trade_log=backtest_result["trade_log"],
            label="TRAIN",
            start_date=str(full_inputs["timeline"][0].date()),
            end_date=train_end,
            warmup_start=WARMUP_START,
        )
        holdout_summary = _summarize_window(
            daily_stats=backtest_result["daily_stats"],
            trade_log=backtest_result["trade_log"],
            label="HOLDOUT",
            start_date=holdout_start,
            end_date=str(full_inputs["timeline"][-1].date()),
            warmup_start=WARMUP_START,
        )
        if train_summary is None or holdout_summary is None:
            continue

        rows.append(
            {
                "rank": int(candidate["rank"]),
                "holdout_start": holdout_summary["start_date"],
                "holdout_end": holdout_summary["end_date"],
                "holdout_return_pct": float(holdout_summary["total_return_pct"]),
                "holdout_pf": float(holdout_summary["profit_factor"]),
                "holdout_trades": int(holdout_summary["trade_count"]),
                "holdout_plus_1pct_weeks": int(holdout_summary["plus_1pct_weeks"]),
                "holdout_week_count": int(holdout_summary["week_count"]),
                "holdout_positive_weeks": int(holdout_summary["positive_weeks"]),
                "holdout_worst_day": float(holdout_summary["worst_day"]),
                "confirmed_train_plus_1pct_weeks": int(train_summary["plus_1pct_weeks"]),
                "confirmed_train_week_count": int(train_summary["week_count"]),
            }
        )

    return pd.DataFrame(rows)


def _run_grid_search(tasks):
    try:
        with concurrent.futures.ProcessPoolExecutor() as executor:
            return list(executor.map(run_single_opt, tasks))
    except (OSError, PermissionError) as exc:
        print(
            "[TRAIN_ONLY_OPT] Parallel worker startup failed; "
            f"falling back to serial execution. ({exc})"
        )
        return [run_single_opt(task) for task in tasks]


def _print_split_plan(
    full_timeline,
    train_timeline,
    split_plan,
    min_train_months,
    robustness_window_months,
    robustness_step_months,
):
    print("\n" + "=" * 120)
    print("TRAIN-FIRST OPTIMIZATION SCOPE")
    print("=" * 120)
    if split_plan["holdout_start"] is None:
        print(
            "No holdout split configured. Ranking uses the full available history. "
            "Set --holdout-months 1 (or more) to reserve a trailing window."
        )
    else:
        print(
            f"TRAIN WINDOW: {train_timeline[0].date()} to {train_timeline[-1].date()} "
            f"(ranking only)"
        )
        print(
            f"HOLDOUT WINDOW: {split_plan['holdout_start']} to {full_timeline[-1].date()} "
            "(final pseudo-forward check only)"
        )
    print(
        f"ROBUSTNESS SCORE: min_train={int(min_train_months)}m | "
        f"rolling_train_windows={int(robustness_window_months)}m step {int(robustness_step_months)}m"
    )
    print("=" * 120)


def _print_train_rankings(df_res):
    df_display = df_res.copy()
    df_display["train_week_hits"] = df_display.apply(
        lambda row: _format_week_metric(row["train_plus_1pct_weeks"], row["train_week_count"]),
        axis=1,
    )
    df_display["train_positive_week_hits"] = df_display.apply(
        lambda row: _format_week_metric(row["train_positive_weeks"], row["train_week_count"]),
        axis=1,
    )

    display_cols = [
        "rank",
        "score",
        "eligible",
        "train_total_return_pct",
        "trades",
        "win_rate",
        "pf",
        "mdd",
        "train_week_hits",
        "plus_1pct_week_rate",
        "train_positive_week_hits",
        "positive_window_rate",
        "median_window_return_pct",
        "worst_window_return_pct",
        "avg_month_active_rate",
        "worst_day_pct",
        "train_worst_day",
        "sl",
        "tp",
        "max_pos",
        "leverage",
        "breadth",
    ]

    print("\n" + "=" * 120)
    print("TRAIN-RANKED OPTIMIZATION RESULTS (Top 30)")
    print("=" * 120)
    print(
        df_display[display_cols].head(30).to_string(
            index=False,
            formatters={
                "score": "{:,.1f}".format,
                "train_total_return_pct": "{:+,.1f}%".format,
                "win_rate": "{:.1%}".format,
                "pf": "{:.2f}".format,
                "mdd": "{:.1f}%".format,
                "plus_1pct_week_rate": "{:.1%}".format,
                "positive_window_rate": "{:.1%}".format,
                "median_window_return_pct": "{:+.1f}%".format,
                "worst_window_return_pct": "{:+.1f}%".format,
                "avg_month_active_rate": "{:.1%}".format,
                "worst_day_pct": "{:.2f}%".format,
                "train_worst_day": lambda value: f"Y{value:,.0f}",
                "leverage": "{:.1f}x".format,
                "breadth": "{:.2f}".format,
            },
        )
    )
    print("=" * 120)


def _print_holdout_review(holdout_df):
    if holdout_df.empty:
        return

    df_display = holdout_df.copy()
    df_display["holdout_week_hits"] = df_display.apply(
        lambda row: _format_week_metric(row["holdout_plus_1pct_weeks"], row["holdout_week_count"]),
        axis=1,
    )
    df_display["confirmed_train_week_hits"] = df_display.apply(
        lambda row: _format_week_metric(
            row["confirmed_train_plus_1pct_weeks"],
            row["confirmed_train_week_count"],
        ),
        axis=1,
    )

    display_cols = [
        "rank",
        "confirmed_train_week_hits",
        "holdout_start",
        "holdout_end",
        "holdout_return_pct",
        "holdout_pf",
        "holdout_trades",
        "holdout_week_hits",
        "holdout_worst_day",
    ]

    print("\n" + "=" * 120)
    print("HOLDOUT REVIEW FOR TOP TRAIN CANDIDATES")
    print("=" * 120)
    print(
        df_display[display_cols].to_string(
            index=False,
            formatters={
                "holdout_return_pct": "{:+.2f}%".format,
                "holdout_pf": "{:.2f}".format,
                "holdout_worst_day": lambda value: f"Y{value:,.0f}",
            },
        )
    )
    print("=" * 120)


def optimize_jp_imperial(
    cache_path,
    holdout_months=1,
    top_k_holdout=10,
    output_csv="opt_results.csv",
    refresh_cache=False,
    refresh_start_date="",
    refresh_overlap_days=7,
    min_train_months=DEFAULT_MIN_TRAIN_MONTHS,
    robustness_window_months=DEFAULT_ROBUSTNESS_WINDOW_MONTHS,
    robustness_step_months=DEFAULT_ROBUSTNESS_STEP_MONTHS,
):
    _refresh_cache_if_requested(
        cache_path=cache_path,
        refresh_cache=refresh_cache,
        refresh_start_date=refresh_start_date,
        refresh_overlap_days=refresh_overlap_days,
    )
    full_inputs = _prepare_backtest_inputs(cache_path)
    split_plan = _resolve_optimizer_split(full_inputs["timeline"], holdout_months)
    train_bundle_np, train_timeline, train_breadth_series = _slice_backtest_inputs(
        bundle_np=full_inputs["bundle_np"],
        timeline=full_inputs["timeline"],
        breadth_ratio=full_inputs["breadth_series"],
        end_date=split_plan["train_end"],
    )
    _validate_train_timeline_or_raise(train_timeline, min_train_months=min_train_months)
    robustness_windows = _build_robustness_windows(
        timeline=train_timeline,
        window_months=robustness_window_months,
        step_months=robustness_step_months,
        warmup_start=WARMUP_START,
    )
    if not robustness_windows:
        raise ValueError(
            "No rolling train robustness windows were produced. "
            "Increase the train history or lower `--robustness-window-months`."
        )
    _print_split_plan(
        full_inputs["timeline"],
        train_timeline,
        split_plan,
        min_train_months,
        robustness_window_months,
        robustness_step_months,
    )

    grid = _build_param_grid()
    print(f"[TRAIN_ONLY_OPT] Starting Grid Search ({len(grid)} combinations)...")

    tasks = [
        (
            full_inputs["univ_indices"],
            train_bundle_np,
            train_timeline,
            train_breadth_series,
            params,
            full_inputs["timeline"].strftime("%Y-%m-%d").tolist(),
            robustness_windows,
        )
        for params in grid
    ]
    results = _run_grid_search(tasks)

    df_res = pd.DataFrame(results)
    df_res["return_pct"] = (df_res["final"] / INITIAL_CASH - 1.0) * 100.0
    df_res = df_res.sort_values("score", ascending=False).reset_index(drop=True)
    df_res["rank"] = np.arange(1, len(df_res) + 1)

    _print_train_rankings(df_res)

    holdout_df = _evaluate_top_holdout_candidates(
        df_res=df_res,
        full_inputs=full_inputs,
        split_plan=split_plan,
        top_k_holdout=top_k_holdout,
    )
    _print_holdout_review(holdout_df)

    if not holdout_df.empty:
        df_res = df_res.merge(holdout_df, on="rank", how="left")

    if output_csv:
        df_res.to_csv(output_csv, index=False)
        print(f"Saved optimization results to {output_csv}")

    best = df_res.iloc[0]
    print("\nBEST TRAIN CONFIGURATION:")
    print(f" - Train Robustness Score: {best['score']:.1f}")
    print(f" - Train Candidate Status: {'ELIGIBLE' if bool(best['eligible']) else 'INELIGIBLE'}")
    if str(best.get("eligibility_failures", "")):
        print(f" - Eligibility Flags:      {best['eligibility_failures']}")
    print(f" - Train Profit Factor:    {best['pf']:.2f}")
    print(f" - Train Max Drawdown:     {best['mdd']:.1f}%")
    print(f" - Train Worst Day:        Y{best['train_worst_day']:,.0f} ({best['worst_day_pct']:.2f}%)")
    print(f" - Train Weeks >= +1%:     {_format_week_metric(best['train_plus_1pct_weeks'], best['train_week_count'])}")
    print(f" - Train Week Hit Rate:    {best['plus_1pct_week_rate']:.1%}")
    print(f" - Positive Window Rate:   {best['positive_window_rate']:.1%}")
    print(f" - Median Window Return:   {best['median_window_return_pct']:+.2f}%")
    print(f" - Worst Window Return:    {best['worst_window_return_pct']:+.2f}%")
    print(f" - Avg Month Active Rate:  {best['avg_month_active_rate']:.1%}")
    print("-" * 30)
    print(f" - Max Positions:          {int(best['max_pos'])}")
    print(f" - Breadth Threshold:      {best['breadth']:.2f}")
    print(f" - SMA20 Exit Buffer:      {best['exit_buffer']:.3f}")
    print(f" - Stop Loss:              ATR * {best['sl']}")
    print(f" - Profit Target:          ATR * {best['tp']}")
    print(f" - BULL Gap Limit:         {best['bgap']:.2%}")
    print(f" - Leverage:               {best['leverage']}x")
    print(f" - Train Return:           {best['train_total_return_pct']:+.2f}% ({int(best['trades'])} trades)")
    if split_plan["holdout_start"] is not None and "holdout_return_pct" in best and pd.notna(best["holdout_return_pct"]):
        print("-" * 30)
        print(
            f" - Holdout Window:         {best['holdout_start']} to {best['holdout_end']} "
            f"({best['holdout_return_pct']:+.2f}%)"
        )
        print(
            f" - Holdout Weeks >= +1%:   "
            f"{_format_week_metric(best['holdout_plus_1pct_weeks'], best['holdout_week_count'])}"
        )
        print(f" - Holdout Profit Factor:  {best['holdout_pf']:.2f}")
    print("=" * 120)


if __name__ == "__main__":
    args = parse_args()
    if not os.path.exists("data_cache"):
        print("Error: Please run from the project root directory.")
        sys.exit(1)

    optimize_jp_imperial(
        cache_path=args.cache_path,
        holdout_months=args.holdout_months,
        top_k_holdout=args.top_k_holdout,
        output_csv=args.output_csv,
        refresh_cache=args.refresh_cache,
        refresh_start_date=args.refresh_start_date,
        refresh_overlap_days=args.refresh_overlap_days,
        min_train_months=args.min_train_months,
        robustness_window_months=args.robustness_window_months,
        robustness_step_months=args.robustness_step_months,
    )
