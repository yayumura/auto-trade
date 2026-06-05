import pandas as pd

from analyze_backtest_trade_log import (
    build_miss_week_flip_potential_table,
    build_miss_week_loss_dominance_table,
    build_miss_week_sensitivity_table,
    build_primary_close_fade_table,
    build_train_week_table,
    classify_exit_bucket,
    summarize_trade_clusters,
)


def test_classify_exit_bucket_uses_exit_reason():
    trades = pd.DataFrame(
        [
            {"exit_reason": "intraday_stop"},
            {"exit_reason": "open_target"},
            {"exit_reason": "close_exit"},
        ]
    )

    classified = classify_exit_bucket(trades)

    assert classified["exit_bucket"].tolist() == ["stop", "target", "close_or_open"]


def test_build_train_week_table_skips_partial_weeks():
    all_daily = pd.DataFrame(
        [
            {"day_key": "2026-01-05", "equity": 100.0, "day_pnl": 0.0, "trade_count": 0},
            {"day_key": "2026-01-06", "equity": 101.0, "day_pnl": 1.0, "trade_count": 1},
            {"day_key": "2026-01-07", "equity": 102.0, "day_pnl": 1.0, "trade_count": 1},
            {"day_key": "2026-01-08", "equity": 103.0, "day_pnl": 1.0, "trade_count": 1},
            {"day_key": "2026-01-09", "equity": 104.0, "day_pnl": 1.0, "trade_count": 1},
            {"day_key": "2026-01-12", "equity": 104.0, "day_pnl": 0.0, "trade_count": 0},
            {"day_key": "2026-01-13", "equity": 105.0, "day_pnl": 1.0, "trade_count": 1},
            {"day_key": "2026-01-14", "equity": 106.0, "day_pnl": 1.0, "trade_count": 1},
            {"day_key": "2026-01-15", "equity": 107.0, "day_pnl": 1.0, "trade_count": 1},
            {"day_key": "2026-01-16", "equity": 108.0, "day_pnl": 1.0, "trade_count": 1},
        ]
    )
    train_daily = all_daily.iloc[:-1].copy()

    week_table = build_train_week_table(train_daily, all_daily)

    assert list(week_table.index) == ["2026-W02"]
    assert week_table.iloc[0]["trade_count"] == 4
    assert bool(week_table.iloc[0]["positive"]) is True


def test_build_train_week_table_skips_warmup_partial_week():
    all_daily = pd.DataFrame(
        [
            {"day_key": "2026-03-02", "equity": 100.0, "day_pnl": 0.0, "trade_count": 0},
            {"day_key": "2026-03-03", "equity": 101.0, "day_pnl": 1.0, "trade_count": 1},
            {"day_key": "2026-03-04", "equity": 102.0, "day_pnl": 1.0, "trade_count": 1},
            {"day_key": "2026-03-05", "equity": 103.0, "day_pnl": 1.0, "trade_count": 1},
            {"day_key": "2026-03-06", "equity": 104.0, "day_pnl": 1.0, "trade_count": 1},
            {"day_key": "2026-03-09", "equity": 105.0, "day_pnl": 1.0, "trade_count": 1},
            {"day_key": "2026-03-10", "equity": 106.0, "day_pnl": 1.0, "trade_count": 1},
            {"day_key": "2026-03-11", "equity": 107.0, "day_pnl": 1.0, "trade_count": 1},
            {"day_key": "2026-03-12", "equity": 108.0, "day_pnl": 1.0, "trade_count": 1},
            {"day_key": "2026-03-13", "equity": 109.0, "day_pnl": 1.0, "trade_count": 1},
        ]
    )

    week_table = build_train_week_table(
        all_daily.copy(),
        all_daily,
        warmup_start="2026-03-04",
    )

    assert list(week_table.index) == ["2026-W11"]
    assert week_table.iloc[0]["trade_count"] == 5
    assert bool(week_table.iloc[0]["positive"]) is True


def test_build_primary_close_fade_table_sorts_largest_givebacks_first():
    trades = pd.DataFrame(
        [
            {
                "day_key": "2026-01-05",
                "code": "1111.T",
                "net_pnl": -200000.0,
                "high_return_pct": 2.5,
                "close_return_pct": -0.8,
                "fade_from_high_pct": -3.3,
                "exit_reason": "close_exit",
                "breadth": 0.62,
                "market_ratio": 1.04,
                "gap_pct": 0.004,
                "prev_return": 0.03,
                "open_vs_sma_atr": 1.5,
                "rs_alpha": 45.0,
            },
            {
                "day_key": "2026-01-06",
                "code": "2222.T",
                "net_pnl": -150000.0,
                "high_return_pct": 1.5,
                "close_return_pct": -0.2,
                "fade_from_high_pct": -1.7,
                "exit_reason": "close_exit",
                "breadth": 0.58,
                "market_ratio": 1.02,
                "gap_pct": 0.001,
                "prev_return": 0.01,
                "open_vs_sma_atr": 0.9,
                "rs_alpha": 22.0,
            },
        ]
    )

    fades = build_primary_close_fade_table(trades, top_n=5)

    assert fades["code"].tolist() == ["1111.T", "2222.T"]
    assert "fade_from_high_pct" in fades.columns


def test_build_miss_week_sensitivity_table_quantifies_flip_paths():
    week_table = pd.DataFrame(
        [
            {
                "week_key": "2026-W01",
                "start_equity": 100.0,
                "pnl": 0.4,
                "trade_count": 2,
                "hit_1pct": False,
                "positive": True,
            },
            {
                "week_key": "2026-W02",
                "start_equity": 100.0,
                "pnl": -1.2,
                "trade_count": 2,
                "hit_1pct": False,
                "positive": False,
            },
            {
                "week_key": "2026-W03",
                "start_equity": 100.0,
                "pnl": 1.5,
                "trade_count": 1,
                "hit_1pct": True,
                "positive": True,
            },
        ]
    ).set_index("week_key")
    trades = pd.DataFrame(
        [
            {"week_key": "2026-W01", "setup_type": "primary", "exit_bucket": "target", "net_pnl": 1.2},
            {"week_key": "2026-W01", "setup_type": "primary", "exit_bucket": "stop", "net_pnl": -0.8},
            {"week_key": "2026-W02", "setup_type": "primary", "exit_bucket": "stop", "net_pnl": -1.0},
            {"week_key": "2026-W02", "setup_type": "fallback", "exit_bucket": "close_or_open", "net_pnl": -0.2},
            {"week_key": "2026-W03", "setup_type": "primary", "exit_bucket": "target", "net_pnl": 1.5},
        ]
    )

    sensitivity = build_miss_week_sensitivity_table(week_table, trades)

    assert sensitivity["week_key"].tolist() == ["2026-W01", "2026-W02"]
    first_week = sensitivity.iloc[0]
    assert first_week["gap_to_target_pct"] == 0.6
    assert first_week["worst_trade_pnl"] == -0.8
    assert first_week["worst_trade_setup"] == "primary"
    assert first_week["worst_trade_exit_bucket"] == "stop"
    assert first_week["primary_stop_pnl"] == -0.8
    assert first_week["worst_trade_loss_share"] == 1.0
    assert bool(first_week["flip_if_reduce_worst_75pct"]) is True
    assert bool(first_week["flip_if_reduce_primary_stop_75pct"]) is True


def test_build_miss_week_flip_and_dominance_tables_summarize_counts():
    sensitivity = pd.DataFrame(
        [
            {
                "week_key": "2026-W01",
                "primary_stop_pnl": -0.8,
                "worst_trade_loss_share": 1.0,
                "flip_if_reduce_worst_25pct": False,
                "flip_if_reduce_worst_50pct": False,
                "flip_if_reduce_worst_75pct": True,
                "flip_if_reduce_worst_100pct": True,
                "flip_if_reduce_primary_stop_25pct": False,
                "flip_if_reduce_primary_stop_50pct": False,
                "flip_if_reduce_primary_stop_75pct": True,
                "flip_if_reduce_primary_stop_100pct": True,
            },
            {
                "week_key": "2026-W02",
                "primary_stop_pnl": 0.0,
                "worst_trade_loss_share": 0.5,
                "flip_if_reduce_worst_25pct": False,
                "flip_if_reduce_worst_50pct": False,
                "flip_if_reduce_worst_75pct": False,
                "flip_if_reduce_worst_100pct": False,
                "flip_if_reduce_primary_stop_25pct": False,
                "flip_if_reduce_primary_stop_50pct": False,
                "flip_if_reduce_primary_stop_75pct": False,
                "flip_if_reduce_primary_stop_100pct": False,
            },
        ]
    )

    flip_summary = build_miss_week_flip_potential_table(sensitivity)
    dominance = build_miss_week_loss_dominance_table(sensitivity)

    worst_75 = flip_summary[flip_summary["scenario"] == "reduce_worst_trade_75pct"].iloc[0]
    primary_stop_75 = flip_summary[flip_summary["scenario"] == "reduce_primary_stop_75pct"].iloc[0]
    assert worst_75["flipped_weeks"] == 1
    assert primary_stop_75["flipped_weeks"] == 1
    assert worst_75["total_miss_weeks"] == 2

    dominance_map = dict(zip(dominance["metric"], dominance["value"]))
    assert dominance_map["miss_weeks"] == 2
    assert dominance_map["weeks_worst_trade_gt_50pct_losses"] == 1
    assert dominance_map["weeks_with_primary_stop_loss"] == 1


def test_summarize_trade_clusters_bins_generic_primary_losses():
    trades = pd.DataFrame(
        [
            {
                "weekday": "Monday",
                "breadth": 0.61,
                "market_ratio": 1.07,
                "gap_pct": 0.003,
                "score": 8.5,
                "open_vs_sma_atr": 2.2,
                "net_pnl": -100000.0,
            },
            {
                "weekday": "Monday",
                "breadth": 0.63,
                "market_ratio": 1.06,
                "gap_pct": 0.004,
                "score": 8.0,
                "open_vs_sma_atr": 2.5,
                "net_pnl": -200000.0,
            },
        ]
    )

    clusters = summarize_trade_clusters(trades, top_n=5)

    assert set(clusters.keys()) == {"weekday", "breadth_bin", "market_bin", "gap_bin", "score_bin", "trend_bin"}
    assert clusters["weekday"].iloc[0]["weekday"] == "Monday"
    assert clusters["weekday"].iloc[0]["trades"] == 2
