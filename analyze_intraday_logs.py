import argparse
from pathlib import Path

import pandas as pd

from core.config import DAYTRADE_DECISION_LOG_FILE, DAYTRADE_EXIT_LOG_FILE, INTRADAY_SNAPSHOT_FILE


OPEN_DECISIONS = {"opened_sim", "opened_live"}
SKIP_DECISIONS = {
    "scan_blocked",
    "skipped_ai_filter",
    "skipped_board_gap_filter",
    "skipped_max_positions",
    "skipped_review_cap",
    "skipped_size_floor",
}


def load_csv_or_empty(path):
    csv_path = Path(path)
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(csv_path, encoding="utf-8-sig")


def summarize_source_files(decisions_path, snapshots_path, exits_path, decisions_df, snapshots_df, exits_df):
    rows = []
    for source_name, path_value, df in [
        ("decisions", decisions_path, decisions_df),
        ("snapshots", snapshots_path, snapshots_df),
        ("exits", exits_path, exits_df),
    ]:
        csv_path = Path(path_value)
        exists = csv_path.exists()
        size_bytes = int(csv_path.stat().st_size) if exists else 0
        last_modified = (
            pd.Timestamp(csv_path.stat().st_mtime, unit="s").strftime("%Y-%m-%d %H:%M:%S")
            if exists
            else ""
        )
        if not exists:
            status = "missing"
        elif size_bytes == 0:
            status = "empty_file"
        elif df.empty:
            status = "header_only"
        else:
            status = "populated"
        rows.append(
            {
                "source": source_name,
                "status": status,
                "rows": int(len(df)),
                "size_bytes": size_bytes,
                "last_modified": last_modified,
                "path": str(csv_path),
            }
        )
    return pd.DataFrame(rows)


def summarize_analysis_readiness(source_summary, trades_df):
    columns = ["check", "status", "detail"]
    if source_summary.empty:
        return pd.DataFrame(columns=columns)

    source_map = source_summary.set_index("source")
    rows = []
    decisions_status = str(source_map.at["decisions", "status"]) if "decisions" in source_map.index else "missing"
    snapshots_status = str(source_map.at["snapshots", "status"]) if "snapshots" in source_map.index else "missing"
    exits_status = str(source_map.at["exits", "status"]) if "exits" in source_map.index else "missing"
    trades_count = int(len(trades_df))

    rows.append(
        {
            "check": "decision_log",
            "status": "ready" if decisions_status == "populated" else "blocked",
            "detail": (
                "scan and entry decisions are captured"
                if decisions_status == "populated"
                else f"decision source is {decisions_status}"
            ),
        }
    )
    rows.append(
        {
            "check": "snapshot_log",
            "status": "ready" if snapshots_status == "populated" else "blocked",
            "detail": (
                "intraday path snapshots are captured"
                if snapshots_status == "populated"
                else f"snapshot source is {snapshots_status}"
            ),
        }
    )
    rows.append(
        {
            "check": "exit_log",
            "status": "ready" if exits_status == "populated" else "blocked",
            "detail": (
                "flatten / stop exit context is captured"
                if exits_status == "populated"
                else f"exit source is {exits_status}"
            ),
        }
    )
    rows.append(
        {
            "check": "shared_exit_research",
            "status": "ready" if trades_count > 0 else "blocked",
            "detail": (
                f"captured_trades={trades_count}"
                if trades_count > 0
                else "no populated trade paths yet; live/shared exit study is still blocked"
            ),
        }
    )
    return pd.DataFrame(rows, columns=columns)


def _coerce_bool(value):
    if pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return text in {"1", "true", "t", "yes", "y"}


def _coerce_numeric(df, columns):
    for column in columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def normalize_decision_log(decisions_df):
    if decisions_df.empty:
        return decisions_df.copy()
    normalized = decisions_df.copy()
    if "time" in normalized.columns:
        normalized["time"] = pd.to_datetime(normalized["time"], errors="coerce")
        normalized["trade_date"] = normalized["time"].dt.strftime("%Y-%m-%d")
    else:
        normalized["trade_date"] = ""
    return _coerce_numeric(
        normalized,
        [
            "candidate_rank",
            "selected_count",
            "breadth",
            "market_ratio",
            "score",
            "live_gap_pct",
            "stop_mult",
            "stop_price",
            "shares",
        ],
    )


def normalize_snapshot_log(snapshots_df):
    if snapshots_df.empty:
        return snapshots_df.copy()
    normalized = snapshots_df.copy()
    if "time" in normalized.columns:
        normalized["time"] = pd.to_datetime(normalized["time"], errors="coerce")
    if "buy_time" in normalized.columns:
        normalized["buy_time"] = pd.to_datetime(normalized["buy_time"], errors="coerce")
        normalized["trade_date"] = normalized["buy_time"].dt.strftime("%Y-%m-%d")
    else:
        normalized["trade_date"] = ""
    if "is_held" in normalized.columns:
        normalized["is_held"] = normalized["is_held"].map(_coerce_bool)
    else:
        normalized["is_held"] = False
    return _coerce_numeric(
        normalized,
        [
            "price",
            "buy_price",
            "buy_atr",
            "held_shares",
            "entry_candidate_rank",
            "entry_stop_mult",
            "entry_stop_price",
            "entry_target_mult",
            "entry_target_price",
            "entry_breadth",
            "entry_market_ratio",
            "buy_gap_pct",
            "buy_live_gap_pct",
            "buy_prev_return",
            "buy_open_vs_sma_atr",
            "buy_score",
            "buy_rs",
            "buy_rsi2",
            "current_pnl",
            "current_return_pct",
            "distance_to_stop_pct",
            "distance_to_stop_atr",
            "distance_to_target_pct",
            "distance_to_target_atr",
            "session_runup_pct",
            "session_drawdown_pct",
            "drawdown_from_session_high_pct",
            "fade_from_session_high_pct",
            "rebound_from_session_low_pct",
        ],
    )


def normalize_exit_log(exits_df):
    if exits_df.empty:
        return exits_df.copy()
    normalized = exits_df.copy()
    if "time" in normalized.columns:
        normalized["time"] = pd.to_datetime(normalized["time"], errors="coerce")
    if "buy_time" in normalized.columns:
        normalized["buy_time"] = pd.to_datetime(normalized["buy_time"], errors="coerce")
        normalized["trade_date"] = normalized["buy_time"].dt.strftime("%Y-%m-%d")
    else:
        normalized["trade_date"] = ""
    if "is_simulation" in normalized.columns:
        normalized["is_simulation"] = normalized["is_simulation"].map(_coerce_bool)
    if "is_partial_fill" in normalized.columns:
        normalized["is_partial_fill"] = normalized["is_partial_fill"].map(_coerce_bool)
    return _coerce_numeric(
        normalized,
        [
            "observed_price",
            "modeled_exit_price",
            "modeled_pnl",
            "modeled_return_pct",
            "session_open",
            "session_high",
            "session_low",
            "held_shares",
            "filled_shares",
            "remaining_shares",
            "buy_price",
            "buy_atr",
            "entry_candidate_rank",
            "entry_stop_mult",
            "entry_stop_price",
            "entry_target_mult",
            "entry_target_price",
            "entry_breadth",
            "entry_market_ratio",
            "buy_gap_pct",
            "buy_live_gap_pct",
            "buy_prev_return",
            "buy_open_vs_sma_atr",
            "buy_score",
            "buy_rs",
            "buy_rsi2",
            "current_pnl",
            "current_return_pct",
            "distance_to_stop_pct",
            "distance_to_stop_atr",
            "distance_to_target_pct",
            "distance_to_target_atr",
            "session_runup_pct",
            "session_drawdown_pct",
            "drawdown_from_session_high_pct",
            "fade_from_session_high_pct",
            "rebound_from_session_low_pct",
        ],
    )


def _first_valid(series):
    non_null = series.dropna()
    if non_null.empty:
        return None
    return non_null.iloc[0]


def _last_valid(series):
    non_null = series.dropna()
    if non_null.empty:
        return None
    return non_null.iloc[-1]


def summarize_decisions(decisions_df):
    if decisions_df.empty:
        return {
            "decision_counts": pd.DataFrame(columns=["decision", "count"]),
            "skip_reason_counts": pd.DataFrame(columns=["decision", "reason", "count"]),
            "daily_summary": pd.DataFrame(
                columns=["trade_date", "scan_candidates", "selected_for_sizing", "opened", "skipped", "blocked"]
            ),
        }

    decision_counts = (
        decisions_df.groupby("decision", dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values(["count", "decision"], ascending=[False, True])
        .reset_index(drop=True)
    )

    skip_reason_counts = (
        decisions_df[decisions_df["decision"].isin(SKIP_DECISIONS)]
        .groupby(["decision", "reason"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values(["count", "decision", "reason"], ascending=[False, True, True])
        .reset_index(drop=True)
    )

    daily_frames = []
    for decision_name, column_name in [
        ("scan_candidate", "scan_candidates"),
        ("selected_for_sizing", "selected_for_sizing"),
    ]:
        daily_frames.append(
            decisions_df[decisions_df["decision"] == decision_name]
            .groupby("trade_date")
            .size()
            .rename(column_name)
        )
    daily_frames.append(
        decisions_df[decisions_df["decision"].isin(OPEN_DECISIONS)]
        .groupby("trade_date")
        .size()
        .rename("opened")
    )
    daily_frames.append(
        decisions_df[decisions_df["decision"].isin(SKIP_DECISIONS)]
        .groupby("trade_date")
        .size()
        .rename("skipped")
    )
    daily_frames.append(
        decisions_df[decisions_df["decision"] == "scan_blocked"]
        .groupby("trade_date")
        .size()
        .rename("blocked")
    )

    daily_summary = pd.concat(daily_frames, axis=1).fillna(0).reset_index()
    if not daily_summary.empty:
        numeric_cols = ["scan_candidates", "selected_for_sizing", "opened", "skipped", "blocked"]
        for column in numeric_cols:
            daily_summary[column] = daily_summary[column].astype(int)
        daily_summary = daily_summary.sort_values("trade_date").reset_index(drop=True)

    return {
        "decision_counts": decision_counts,
        "skip_reason_counts": skip_reason_counts,
        "daily_summary": daily_summary,
    }


def summarize_exits(exits_df):
    if exits_df.empty:
        return {
            "exit_counts": pd.DataFrame(columns=["exit_reason", "count"]),
            "daily_exit_summary": pd.DataFrame(columns=["trade_date", "exits"]),
        }
    exit_counts = (
        exits_df.groupby("exit_reason", dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values(["count", "exit_reason"], ascending=[False, True])
        .reset_index(drop=True)
    )
    daily_exit_summary = (
        exits_df.groupby("trade_date", dropna=False)
        .size()
        .reset_index(name="exits")
        .sort_values("trade_date")
        .reset_index(drop=True)
    )
    return {
        "exit_counts": exit_counts,
        "daily_exit_summary": daily_exit_summary,
    }


def summarize_intraday_trades(snapshots_df, exits_df=None):
    required_columns = {"code", "time", "buy_time", "is_held"}
    if snapshots_df.empty or not required_columns.issubset(snapshots_df.columns):
        return pd.DataFrame()

    held = snapshots_df[snapshots_df["is_held"]].copy()
    held = held[held["buy_time"].notna() & held["time"].notna()]
    if held.empty:
        return pd.DataFrame()

    held["code"] = held["code"].astype(str)
    held["trade_id"] = held["code"] + "|" + held["buy_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
    held = held.sort_values(["trade_id", "time"]).reset_index(drop=True)

    rows = []
    for trade_id, trade in held.groupby("trade_id", sort=False):
        current_returns = trade["current_return_pct"] if "current_return_pct" in trade.columns else pd.Series(dtype=float)
        session_runups = trade["session_runup_pct"] if "session_runup_pct" in trade.columns else pd.Series(dtype=float)
        runup_series = pd.concat([current_returns, session_runups], axis=1).max(axis=1, skipna=True)
        min_stop_distance_pct = trade["distance_to_stop_pct"].min() if "distance_to_stop_pct" in trade.columns else None

        max_runup_pct = runup_series.max() if not runup_series.empty else None
        final_return_pct = _last_valid(current_returns) if not current_returns.empty else None
        final_pnl = _last_valid(trade["current_pnl"]) if "current_pnl" in trade.columns else None
        worst_return_pct = current_returns.min() if not current_returns.empty else None
        max_drawdown_from_peak_pct = (
            trade["drawdown_from_session_high_pct"].min()
            if "drawdown_from_session_high_pct" in trade.columns
            else None
        )
        min_distance_to_stop_atr = (
            trade["distance_to_stop_atr"].min() if "distance_to_stop_atr" in trade.columns else None
        )
        fade_from_peak_pct = None
        if pd.notna(max_runup_pct) and pd.notna(final_return_pct):
            fade_from_peak_pct = float(final_return_pct - max_runup_pct)

        first_snapshot = trade["time"].iloc[0]
        last_snapshot = trade["time"].iloc[-1]
        hold_minutes = (last_snapshot - first_snapshot).total_seconds() / 60.0

        rows.append(
            {
                "trade_id": trade_id,
                "trade_date": _first_valid(trade["trade_date"]),
                "code": trade["code"].iloc[0],
                "setup_type": _first_valid(trade.get("setup_type", pd.Series(dtype=object))),
                "buy_time": trade["buy_time"].iloc[0],
                "first_snapshot_time": first_snapshot,
                "last_snapshot_time": last_snapshot,
                "hold_minutes": hold_minutes,
                "n_snapshots": int(len(trade)),
                "buy_price": _first_valid(trade.get("buy_price", pd.Series(dtype=float))),
                "held_shares": _first_valid(trade.get("held_shares", pd.Series(dtype=float))),
                "entry_phase": _first_valid(trade.get("entry_phase", pd.Series(dtype=object))),
                "entry_candidate_rank": _first_valid(trade.get("entry_candidate_rank", pd.Series(dtype=float))),
                "entry_stop_mult": _first_valid(trade.get("entry_stop_mult", pd.Series(dtype=float))),
                "entry_stop_price": _first_valid(trade.get("entry_stop_price", pd.Series(dtype=float))),
                "entry_breadth": _first_valid(trade.get("entry_breadth", pd.Series(dtype=float))),
                "entry_market_ratio": _first_valid(trade.get("entry_market_ratio", pd.Series(dtype=float))),
                "buy_gap_pct": _first_valid(trade.get("buy_gap_pct", pd.Series(dtype=float))),
                "buy_live_gap_pct": _first_valid(trade.get("buy_live_gap_pct", pd.Series(dtype=float))),
                "buy_prev_return": _first_valid(trade.get("buy_prev_return", pd.Series(dtype=float))),
                "buy_open_vs_sma_atr": _first_valid(trade.get("buy_open_vs_sma_atr", pd.Series(dtype=float))),
                "buy_score": _first_valid(trade.get("buy_score", pd.Series(dtype=float))),
                "buy_rs": _first_valid(trade.get("buy_rs", pd.Series(dtype=float))),
                "buy_rsi2": _first_valid(trade.get("buy_rsi2", pd.Series(dtype=float))),
                "final_return_pct": final_return_pct,
                "final_pnl": final_pnl,
                "worst_return_pct": worst_return_pct,
                "max_runup_pct": max_runup_pct,
                "max_drawdown_return_pct": trade["session_drawdown_pct"].min()
                if "session_drawdown_pct" in trade.columns
                else None,
                "fade_from_peak_pct": fade_from_peak_pct,
                "max_drawdown_from_peak_pct": max_drawdown_from_peak_pct,
                "min_distance_to_stop_pct": min_stop_distance_pct,
                "min_distance_to_stop_atr": min_distance_to_stop_atr,
                "touched_stop_proxy": bool(pd.notna(min_stop_distance_pct) and min_stop_distance_pct <= 0),
                "recovered_from_red": bool(
                    pd.notna(worst_return_pct)
                    and pd.notna(final_return_pct)
                    and worst_return_pct < 0
                    and final_return_pct > 0
                ),
                "exit_time": None,
                "exit_reason": "",
                "observed_exit_price": None,
                "modeled_exit_price": None,
                "used_exit_log": False,
            }
        )

    summary = pd.DataFrame(rows)
    if exits_df is not None and not exits_df.empty and not summary.empty:
        exit_rows = exits_df.copy()
        if "trade_id" not in exit_rows.columns:
            exit_rows["code"] = exit_rows.get("code", pd.Series(dtype=object)).astype(str)
            exit_rows["trade_id"] = exit_rows["code"] + "|" + exit_rows["buy_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
        exit_rows = exit_rows.sort_values(["trade_id", "time"]).groupby("trade_id", as_index=False).tail(1)
        exit_lookup = exit_rows.set_index("trade_id")
        for idx, row in summary.iterrows():
            trade_id = row["trade_id"]
            if trade_id not in exit_lookup.index:
                continue
            exit_row = exit_lookup.loc[trade_id]
            exit_quote_return = exit_row.get("current_return_pct")
            exit_modeled_return = exit_row.get("modeled_return_pct")
            exit_quote_pnl = exit_row.get("current_pnl")
            exit_modeled_pnl = exit_row.get("modeled_pnl")
            exit_runup = exit_row.get("session_runup_pct")
            exit_drawdown = exit_row.get("session_drawdown_pct")
            exit_stop_pct = exit_row.get("distance_to_stop_pct")
            exit_stop_atr = exit_row.get("distance_to_stop_atr")
            exit_peak_drawdown = exit_row.get("drawdown_from_session_high_pct")

            final_return_pct = exit_modeled_return if pd.notna(exit_modeled_return) else exit_quote_return
            final_pnl = exit_modeled_pnl if pd.notna(exit_modeled_pnl) else exit_quote_pnl
            max_runup_pct = row["max_runup_pct"]
            if pd.notna(exit_runup):
                max_runup_pct = exit_runup if pd.isna(max_runup_pct) else max(max_runup_pct, exit_runup)
            worst_return_pct = row["worst_return_pct"]
            if pd.notna(exit_quote_return):
                worst_return_pct = exit_quote_return if pd.isna(worst_return_pct) else min(worst_return_pct, exit_quote_return)
            max_drawdown_return_pct = row["max_drawdown_return_pct"]
            if pd.notna(exit_drawdown):
                max_drawdown_return_pct = (
                    exit_drawdown if pd.isna(max_drawdown_return_pct) else min(max_drawdown_return_pct, exit_drawdown)
                )
            min_distance_to_stop_pct = row["min_distance_to_stop_pct"]
            if pd.notna(exit_stop_pct):
                min_distance_to_stop_pct = (
                    exit_stop_pct if pd.isna(min_distance_to_stop_pct) else min(min_distance_to_stop_pct, exit_stop_pct)
                )
            min_distance_to_stop_atr = row["min_distance_to_stop_atr"]
            if pd.notna(exit_stop_atr):
                min_distance_to_stop_atr = (
                    exit_stop_atr if pd.isna(min_distance_to_stop_atr) else min(min_distance_to_stop_atr, exit_stop_atr)
                )
            max_drawdown_from_peak_pct = row["max_drawdown_from_peak_pct"]
            if pd.notna(exit_peak_drawdown):
                max_drawdown_from_peak_pct = (
                    exit_peak_drawdown
                    if pd.isna(max_drawdown_from_peak_pct)
                    else min(max_drawdown_from_peak_pct, exit_peak_drawdown)
                )
            fade_from_peak_pct = None
            if pd.notna(max_runup_pct) and pd.notna(final_return_pct):
                fade_from_peak_pct = float(final_return_pct - max_runup_pct)

            summary.at[idx, "final_return_pct"] = final_return_pct
            summary.at[idx, "final_pnl"] = final_pnl
            summary.at[idx, "worst_return_pct"] = worst_return_pct
            summary.at[idx, "max_runup_pct"] = max_runup_pct
            summary.at[idx, "max_drawdown_return_pct"] = max_drawdown_return_pct
            summary.at[idx, "fade_from_peak_pct"] = fade_from_peak_pct
            summary.at[idx, "max_drawdown_from_peak_pct"] = max_drawdown_from_peak_pct
            summary.at[idx, "min_distance_to_stop_pct"] = min_distance_to_stop_pct
            summary.at[idx, "min_distance_to_stop_atr"] = min_distance_to_stop_atr
            summary.at[idx, "touched_stop_proxy"] = bool(
                pd.notna(min_distance_to_stop_pct) and float(min_distance_to_stop_pct) <= 0
            )
            summary.at[idx, "recovered_from_red"] = bool(
                pd.notna(worst_return_pct)
                and pd.notna(final_return_pct)
                and float(worst_return_pct) < 0
                and float(final_return_pct) > 0
            )
            summary.at[idx, "exit_time"] = exit_row.get("time")
            summary.at[idx, "exit_reason"] = str(exit_row.get("exit_reason", ""))
            summary.at[idx, "observed_exit_price"] = exit_row.get("observed_price")
            summary.at[idx, "modeled_exit_price"] = exit_row.get("modeled_exit_price")
            summary.at[idx, "used_exit_log"] = True
    if not summary.empty:
        summary = summary.sort_values(["trade_date", "buy_time", "code"]).reset_index(drop=True)
    return summary


def summarize_setup_paths(trades_df):
    if trades_df.empty or "setup_type" not in trades_df.columns:
        return pd.DataFrame()

    rows = []
    for setup_type, group in trades_df.groupby("setup_type", dropna=False):
        final_returns = pd.to_numeric(group["final_return_pct"], errors="coerce")
        rows.append(
            {
                "setup_type": "" if pd.isna(setup_type) else str(setup_type),
                "trades": int(len(group)),
                "win_rate": float((final_returns > 0).mean()) if len(group) else 0.0,
                "avg_final_return_pct": float(final_returns.mean()) if not final_returns.empty else None,
                "avg_max_runup_pct": float(pd.to_numeric(group["max_runup_pct"], errors="coerce").mean()),
                "avg_fade_from_peak_pct": float(pd.to_numeric(group["fade_from_peak_pct"], errors="coerce").mean()),
                "avg_min_distance_to_stop_atr": float(
                    pd.to_numeric(group["min_distance_to_stop_atr"], errors="coerce").mean()
                ),
                "stop_pressure_rate": float(group["touched_stop_proxy"].mean()),
                "recovery_rate": float(group["recovered_from_red"].mean()),
            }
        )
    summary = pd.DataFrame(rows)
    if not summary.empty:
        summary = summary.sort_values(["trades", "setup_type"], ascending=[False, True]).reset_index(drop=True)
    return summary


def _frame_preview(df, top_n):
    if df.empty:
        return "(no rows)"
    return df.head(top_n).to_string(index=False)


def build_report(
    decision_summary,
    trades_df,
    setup_summary,
    source_summary,
    readiness_summary,
    decisions_path,
    snapshots_path,
    exits_path,
    top_n=10,
):
    lines = [
        "INTRADAY LOG ANALYSIS",
        f"decisions_file: {decisions_path}",
        f"snapshots_file: {snapshots_path}",
        f"exits_file: {exits_path}",
        "",
        "Source File Status",
        _frame_preview(source_summary, max(top_n, 3)),
        "",
        "Analysis Readiness",
        _frame_preview(readiness_summary, max(top_n, 4)),
        "",
        "Decision Counts",
        _frame_preview(decision_summary["decision_counts"], top_n),
        "",
        "Skip Reasons",
        _frame_preview(decision_summary["skip_reason_counts"], top_n),
        "",
        "Daily Scan Summary",
        _frame_preview(decision_summary["daily_summary"], top_n),
        "",
        "Exit Counts",
        _frame_preview(decision_summary.get("exit_counts", pd.DataFrame()), top_n),
        "",
        "Daily Exit Summary",
        _frame_preview(decision_summary.get("daily_exit_summary", pd.DataFrame()), top_n),
        "",
        f"Captured Trades: {len(trades_df)}",
        "",
        "Setup Path Summary",
        _frame_preview(setup_summary, top_n),
        "",
        "Worst Fade From Peak",
        _frame_preview(
            trades_df.sort_values("fade_from_peak_pct").loc[
                :, ["trade_date", "code", "setup_type", "final_return_pct", "max_runup_pct", "fade_from_peak_pct"]
            ]
            if not trades_df.empty
            else pd.DataFrame(),
            top_n,
        ),
        "",
        "Closest To Stop",
        _frame_preview(
            trades_df.sort_values("min_distance_to_stop_atr").loc[
                :,
                [
                    "trade_date",
                    "code",
                    "setup_type",
                    "final_return_pct",
                    "min_distance_to_stop_pct",
                    "min_distance_to_stop_atr",
                    "touched_stop_proxy",
                ],
            ]
            if not trades_df.empty
            else pd.DataFrame(),
            top_n,
        ),
    ]
    return "\n".join(lines)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Analyze daytrade decision and intraday snapshot logs for exit/de-risk research."
    )
    parser.add_argument("--decisions-file", default=DAYTRADE_DECISION_LOG_FILE, help="Path to daytrade_decisions.csv")
    parser.add_argument("--snapshots-file", default=INTRADAY_SNAPSHOT_FILE, help="Path to intraday_snapshots.csv")
    parser.add_argument("--exits-file", default=DAYTRADE_EXIT_LOG_FILE, help="Path to daytrade_exit_log.csv")
    parser.add_argument("--output-csv", default="", help="Optional path to write the per-trade summary CSV")
    parser.add_argument("--top-n", type=int, default=10, help="Number of rows to print per report section")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    decisions_df = normalize_decision_log(load_csv_or_empty(args.decisions_file))
    snapshots_df = normalize_snapshot_log(load_csv_or_empty(args.snapshots_file))
    exits_df = normalize_exit_log(load_csv_or_empty(args.exits_file))
    source_summary = summarize_source_files(
        args.decisions_file,
        args.snapshots_file,
        args.exits_file,
        decisions_df,
        snapshots_df,
        exits_df,
    )
    decision_summary = summarize_decisions(decisions_df)
    decision_summary.update(summarize_exits(exits_df))
    trades_df = summarize_intraday_trades(snapshots_df, exits_df=exits_df)
    setup_summary = summarize_setup_paths(trades_df)
    readiness_summary = summarize_analysis_readiness(source_summary, trades_df)

    if args.output_csv:
        output_path = Path(args.output_csv)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        trades_df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(
        build_report(
            decision_summary=decision_summary,
            trades_df=trades_df,
            setup_summary=setup_summary,
            source_summary=source_summary,
            readiness_summary=readiness_summary,
            decisions_path=args.decisions_file,
            snapshots_path=args.snapshots_file,
            exits_path=args.exits_file,
            top_n=max(1, args.top_n),
        )
    )


if __name__ == "__main__":
    main()
