import pandas as pd

from analyze_intraday_logs import (
    build_report,
    normalize_decision_log,
    normalize_exit_log,
    normalize_snapshot_log,
    summarize_analysis_readiness,
    summarize_decisions,
    summarize_exits,
    summarize_intraday_trades,
    summarize_source_files,
    summarize_setup_paths,
)


def test_summarize_decisions_builds_daily_counts():
    decisions = pd.DataFrame(
        [
            {"time": "2026-05-19 09:01:00", "decision": "scan_candidate", "reason": "shared_scan"},
            {"time": "2026-05-19 09:01:00", "decision": "scan_candidate", "reason": "shared_scan"},
            {"time": "2026-05-19 09:02:00", "decision": "selected_for_sizing", "reason": "passed_live_filters"},
            {"time": "2026-05-19 09:03:00", "decision": "opened_sim", "reason": "entry_filled"},
            {"time": "2026-05-19 09:04:00", "decision": "skipped_ai_filter", "reason": "red_flag"},
            {"time": "2026-05-20 09:01:00", "decision": "scan_blocked", "reason": "weekly_profit_guard"},
        ]
    )

    summary = summarize_decisions(normalize_decision_log(decisions))
    daily = summary["daily_summary"]

    day1 = daily[daily["trade_date"] == "2026-05-19"].iloc[0]
    assert day1["scan_candidates"] == 2
    assert day1["selected_for_sizing"] == 1
    assert day1["opened"] == 1
    assert day1["skipped"] == 1
    assert day1["blocked"] == 0

    skip_row = summary["skip_reason_counts"].iloc[0]
    assert skip_row["decision"] == "scan_blocked"
    assert skip_row["reason"] == "weekly_profit_guard"


def test_summarize_intraday_trades_aggregates_path_metrics():
    snapshots = pd.DataFrame(
        [
            {
                "time": "2026-05-19 09:31:00",
                "code": "1234",
                "is_held": True,
                "buy_time": "2026-05-19 09:30:30",
                "setup_type": "primary",
                "buy_price": 100.0,
                "held_shares": 300,
                "entry_phase": "前場",
                "entry_candidate_rank": 1,
                "entry_stop_mult": 0.67,
                "entry_stop_price": 98.0,
                "entry_breadth": 0.58,
                "entry_market_ratio": 1.04,
                "buy_gap_pct": 0.01,
                "buy_live_gap_pct": 0.015,
                "buy_prev_return": 0.03,
                "buy_open_vs_sma_atr": 1.7,
                "buy_score": 11.0,
                "buy_rs": 42.0,
                "buy_rsi2": 88.0,
                "current_pnl": 150.0,
                "current_return_pct": 0.005,
                "distance_to_stop_pct": 0.025,
                "distance_to_stop_atr": 1.0,
                "session_runup_pct": 0.010,
                "session_drawdown_pct": -0.010,
                "drawdown_from_session_high_pct": -0.005,
            },
            {
                "time": "2026-05-19 09:35:00",
                "code": "1234",
                "is_held": True,
                "buy_time": "2026-05-19 09:30:30",
                "setup_type": "primary",
                "buy_price": 100.0,
                "held_shares": 300,
                "entry_stop_price": 98.0,
                "current_pnl": -60.0,
                "current_return_pct": -0.002,
                "distance_to_stop_pct": 0.010,
                "distance_to_stop_atr": 0.4,
                "session_runup_pct": 0.012,
                "session_drawdown_pct": -0.015,
                "drawdown_from_session_high_pct": -0.014,
            },
            {
                "time": "2026-05-19 09:40:00",
                "code": "1234",
                "is_held": True,
                "buy_time": "2026-05-19 09:30:30",
                "setup_type": "primary",
                "buy_price": 100.0,
                "held_shares": 300,
                "entry_stop_price": 98.0,
                "current_pnl": 90.0,
                "current_return_pct": 0.003,
                "distance_to_stop_pct": 0.015,
                "distance_to_stop_atr": 0.6,
                "session_runup_pct": 0.012,
                "session_drawdown_pct": -0.012,
                "drawdown_from_session_high_pct": -0.009,
            },
        ]
    )

    trades = summarize_intraday_trades(normalize_snapshot_log(snapshots))
    assert len(trades) == 1

    trade = trades.iloc[0]
    assert trade["trade_date"] == "2026-05-19"
    assert trade["code"] == "1234"
    assert trade["setup_type"] == "primary"
    assert trade["hold_minutes"] == 9.0
    assert trade["n_snapshots"] == 3
    assert trade["final_return_pct"] == 0.003
    assert trade["worst_return_pct"] == -0.002
    assert trade["max_runup_pct"] == 0.012
    assert trade["max_drawdown_return_pct"] == -0.015
    assert round(trade["fade_from_peak_pct"], 6) == -0.009
    assert trade["max_drawdown_from_peak_pct"] == -0.014
    assert trade["min_distance_to_stop_pct"] == 0.010
    assert trade["min_distance_to_stop_atr"] == 0.4
    assert trade["touched_stop_proxy"] == False
    assert trade["recovered_from_red"] == True


def test_summarize_intraday_trades_prefers_exit_log_for_final_outcome():
    snapshots = pd.DataFrame(
        [
            {
                "time": "2026-05-19 09:31:00",
                "code": "1234",
                "is_held": True,
                "buy_time": "2026-05-19 09:30:30",
                "setup_type": "primary",
                "current_pnl": 150.0,
                "current_return_pct": 0.005,
                "distance_to_stop_pct": 0.025,
                "distance_to_stop_atr": 1.0,
                "session_runup_pct": 0.010,
                "session_drawdown_pct": -0.010,
                "drawdown_from_session_high_pct": -0.005,
                "fade_from_session_high_pct": -0.005,
                "rebound_from_session_low_pct": 0.015,
            },
            {
                "time": "2026-05-19 09:35:00",
                "code": "1234",
                "is_held": True,
                "buy_time": "2026-05-19 09:30:30",
                "setup_type": "primary",
                "current_pnl": -60.0,
                "current_return_pct": -0.002,
                "distance_to_stop_pct": 0.010,
                "distance_to_stop_atr": 0.4,
                "session_runup_pct": 0.012,
                "session_drawdown_pct": -0.012,
                "drawdown_from_session_high_pct": -0.014,
                "fade_from_session_high_pct": -0.014,
                "rebound_from_session_low_pct": 0.010,
            },
        ]
    )
    exits = pd.DataFrame(
        [
            {
                "time": "2026-05-19 14:30:00",
                "trade_id": "1234|2026-05-19 09:30:30",
                "code": "1234",
                "buy_time": "2026-05-19 09:30:30",
                "exit_reason": "daytrade_flatten",
                "observed_price": 100.2,
                "modeled_exit_price": 100.0,
                "modeled_pnl": 0.0,
                "modeled_return_pct": 0.0,
                "current_pnl": 60.0,
                "current_return_pct": 0.002,
                "distance_to_stop_pct": 0.008,
                "distance_to_stop_atr": 0.3,
                "session_runup_pct": 0.015,
                "session_drawdown_pct": -0.013,
                "drawdown_from_session_high_pct": -0.020,
            }
        ]
    )

    trades = summarize_intraday_trades(
        normalize_snapshot_log(snapshots),
        exits_df=normalize_exit_log(exits),
    )

    trade = trades.iloc[0]
    assert trade["used_exit_log"] == True
    assert trade["exit_reason"] == "daytrade_flatten"
    assert trade["final_return_pct"] == 0.0
    assert trade["final_pnl"] == 0.0
    assert trade["max_runup_pct"] == 0.015
    assert trade["worst_return_pct"] == -0.002
    assert trade["max_drawdown_return_pct"] == -0.013
    assert trade["min_distance_to_stop_pct"] == 0.008
    assert trade["min_distance_to_stop_atr"] == 0.3
    assert trade["max_drawdown_from_peak_pct"] == -0.020
    assert trade["fade_from_peak_pct"] == -0.015


def test_summarize_exits_counts_exit_reasons():
    exits = pd.DataFrame(
        [
            {"time": "2026-05-19 14:30:00", "buy_time": "2026-05-19 09:30:30", "exit_reason": "daytrade_flatten"},
            {"time": "2026-05-20 14:30:00", "buy_time": "2026-05-20 09:30:30", "exit_reason": "daytrade_flatten"},
        ]
    )

    summary = summarize_exits(normalize_exit_log(exits))

    assert summary["exit_counts"].iloc[0]["exit_reason"] == "daytrade_flatten"
    assert summary["exit_counts"].iloc[0]["count"] == 2


def test_build_report_includes_setup_summary():
    decisions = summarize_decisions(normalize_decision_log(pd.DataFrame()))
    decisions.update(summarize_exits(normalize_exit_log(pd.DataFrame())))
    source_summary = summarize_source_files(
        "decisions.csv",
        "snapshots.csv",
        "exits.csv",
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
    )
    trades = pd.DataFrame(
        [
            {
                "trade_date": "2026-05-19",
                "code": "1234",
                "setup_type": "primary",
                "final_return_pct": 0.003,
                "max_runup_pct": 0.012,
                "fade_from_peak_pct": -0.009,
                "min_distance_to_stop_pct": 0.010,
                "min_distance_to_stop_atr": 0.4,
                "touched_stop_proxy": False,
                "recovered_from_red": True,
            }
        ]
    )
    setup_summary = summarize_setup_paths(trades)
    readiness_summary = summarize_analysis_readiness(source_summary, trades)
    report = build_report(
        decision_summary=decisions,
        trades_df=trades,
        setup_summary=setup_summary,
        source_summary=source_summary,
        readiness_summary=readiness_summary,
        decisions_path="decisions.csv",
        snapshots_path="snapshots.csv",
        exits_path="exits.csv",
        top_n=5,
    )

    assert "INTRADAY LOG ANALYSIS" in report
    assert "Source File Status" in report
    assert "Analysis Readiness" in report
    assert "Exit Counts" in report
    assert "Setup Path Summary" in report
    assert "primary" in report


def test_summarize_source_files_distinguishes_missing_empty_and_populated(tmp_path):
    decisions_path = tmp_path / "decisions.csv"
    snapshots_path = tmp_path / "snapshots.csv"
    exits_path = tmp_path / "exits.csv"
    decisions_path.write_text("", encoding="utf-8")
    snapshots_path.write_text("time,code\n", encoding="utf-8")
    exits_path.write_text("time,code\n2026-05-19 14:30:00,1234\n", encoding="utf-8")

    summary = summarize_source_files(
        decisions_path,
        snapshots_path,
        exits_path,
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame([{"time": "2026-05-19 14:30:00", "code": "1234"}]),
    )
    status_map = dict(zip(summary["source"], summary["status"]))

    assert status_map["decisions"] == "empty_file"
    assert status_map["snapshots"] == "header_only"
    assert status_map["exits"] == "populated"


def test_summarize_analysis_readiness_flags_missing_trade_paths():
    source_summary = pd.DataFrame(
        [
            {"source": "decisions", "status": "populated"},
            {"source": "snapshots", "status": "missing"},
            {"source": "exits", "status": "empty_file"},
        ]
    )

    readiness = summarize_analysis_readiness(source_summary, pd.DataFrame())
    readiness_map = {row["check"]: row for _, row in readiness.iterrows()}

    assert readiness_map["decision_log"]["status"] == "ready"
    assert readiness_map["snapshot_log"]["status"] == "blocked"
    assert readiness_map["exit_log"]["status"] == "blocked"
    assert readiness_map["shared_exit_research"]["status"] == "blocked"
