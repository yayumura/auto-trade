import json
import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch
from types import SimpleNamespace

import auto_trade
from auto_trade import (
    build_daytrade_position_record,
    build_daytrade_production_observation_universe,
    build_daytrade_rotating_discovery_universe,
    build_daytrade_watch_plan,
    close_daytrade_positions_by_signal,
    compute_daytrade_snapshot,
    compute_observed_daytrade_production_snapshot,
    compute_rotating_daytrade_production_snapshot,
    ensure_daytrade_month_state,
    is_inverse_only_candidate_set,
    resolve_runtime_server_clock,
    should_capture_daytrade_production_snapshot,
    sync_daytrade_registry,
)
from core.daytrade_opening_discovery import (
    DaytradeDiscoveryBatchEvidence,
    DaytradeOpeningDiscoveryResult,
    DaytradeProtectedBoardEvidence,
)
from core.logic import (
    RealtimeBuffer,
    cancel_linked_protective_stop_before_exit,
    resolve_daytrade_live_exit_decision,
)
from core.kabucom_order_state import CancelResult, CancelStatus, CancelTerminalStatus
from core.kabucom_order_state import StockOrderAction
from core.order_journal import append_order_journal


@pytest.fixture(autouse=True)
def isolate_runtime_logs(tmp_path, monkeypatch):
    monkeypatch.setattr(auto_trade, "DAYTRADE_DECISION_LOG_FILE", str(tmp_path / "daytrade_decisions.csv"))
    monkeypatch.setattr(auto_trade, "DAYTRADE_EXIT_LOG_FILE", str(tmp_path / "daytrade_exit_log.csv"))
    monkeypatch.setattr(auto_trade, "INTRADAY_SNAPSHOT_FILE", str(tmp_path / "intraday_snapshots.csv"))
    monkeypatch.setattr(
        auto_trade,
        "DAYTRADE_PRODUCTION_SNAPSHOT_FILE",
        str(tmp_path / "daytrade_production_snapshots.jsonl"),
    )


def _server_clock_evidence(timestamp):
    value = pd.Timestamp(timestamp)
    return {
        "schema_version": 1,
        "verified": True,
        "source": "wallet_cash_date_header",
        "reason": "verified",
        "server_time": value.isoformat(),
        "received_at": value.isoformat(),
        "fallback_time": value.isoformat(),
        "drift_seconds": 0.0,
        "max_abs_drift_seconds": 30.0,
    }


def _side_from_action(action):
    if action == StockOrderAction.MARGIN_CLOSE_LONG:
        return "1"
    if action == StockOrderAction.MARGIN_NEW_LONG:
        return "2"
    return str(action)


def _build_snapshot_df():
    dates = pd.date_range("2024-01-01", periods=30)
    tickers = ["1000.T", "1321.T"]
    fields = ["Open", "High", "Low", "Close", "Volume"]
    columns = pd.MultiIndex.from_tuples((ticker, field) for ticker in tickers for field in fields)

    rows = []
    for idx in range(len(dates)):
        row = []
        for ticker_offset in (0.0, 10.0):
            base = 100.0 + ticker_offset + idx
            row.extend([base - 0.5, base + 1.0, base - 1.0, base, 1_000_000.0])
        rows.append(row)
    return pd.DataFrame(rows, index=dates, columns=columns)


def _build_production_snapshot_df():
    dates = pd.bdate_range(end="2026-07-10", periods=260)
    tickers = ["1000.T", "1321.T"]
    fields = ["Open", "High", "Low", "Close", "Volume"]
    columns = pd.MultiIndex.from_tuples(
        (ticker, field) for ticker in tickers for field in fields
    )
    rows = []
    for idx in range(len(dates)):
        row = []
        for ticker_offset in (0.0, 100.0):
            base = 100.0 + ticker_offset + (idx * 0.05) + ((idx % 5) - 2) * 0.2
            row.extend([base - 0.2, base + 1.0, base - 1.0, base, 1_000_000.0])
        rows.append(row)
    return pd.DataFrame(rows, index=dates, columns=columns)


def test_compute_daytrade_snapshot_calculates_breadth_without_name_error():
    data_df = _build_snapshot_df()
    symbols_df = pd.DataFrame({"コード": ["1000", "1321"], "銘柄名": ["Foo", "Bar"]})

    with patch("auto_trade.SMA_LONG_PERIOD", 5), \
         patch("auto_trade.get_prime_tickers", return_value=["1000.T", "1321.T"]), \
         patch("auto_trade.select_best_candidates", return_value=[{"code": "1000", "price": 120.0}]):
        snapshot = compute_daytrade_snapshot(
            data_df=data_df,
            symbols_df=symbols_df,
            targets=["1000", "1321"],
            regime="bull",
        )

    assert snapshot["top_candidates"][0]["code"] == "1000"
    assert snapshot["breadth"] == 1.0
    assert snapshot["latest_close_map"]["1000"] > 0


def test_runtime_server_clock_requires_exact_fresh_broker_evidence_for_live_entry():
    observed = pd.Timestamp("2026-07-15T09:30:00+09:00").to_pydatetime()
    broker = SimpleNamespace(
        get_server_time=lambda: observed,
        last_server_time_evidence={
            "schema_version": 1,
            "verified": True,
            "source": "wallet_cash_date_header",
            "reason": "verified",
            "server_time": observed.isoformat(),
            "received_at": observed.isoformat(),
            "fallback_time": observed.isoformat(),
            "drift_seconds": 0.0,
        },
    )

    resolved, verified, evidence = resolve_runtime_server_clock(broker, is_sim=False)

    assert resolved == observed
    assert verified is True
    assert evidence["source"] == "wallet_cash_date_header"
    assert evidence["max_abs_drift_seconds"] == 30.0


def test_runtime_server_clock_rejects_local_fallback_and_mismatched_evidence():
    observed = pd.Timestamp("2026-07-15T09:30:00+09:00").to_pydatetime()
    fallback_broker = SimpleNamespace(
        get_server_time=lambda: observed,
        last_server_time_evidence={
            "schema_version": 1,
            "verified": False,
            "source": "local_clock_fallback",
            "reason": "wallet_cash_date_header_missing",
            "server_time": None,
            "received_at": observed.isoformat(),
            "fallback_time": observed.isoformat(),
            "drift_seconds": None,
        },
    )
    mismatch_broker = SimpleNamespace(
        get_server_time=lambda: observed,
        last_server_time_evidence={
            "schema_version": 1,
            "verified": True,
            "source": "wallet_cash_date_header",
            "reason": "verified",
            "server_time": (observed + pd.Timedelta(minutes=1)).isoformat(),
            "received_at": observed.isoformat(),
            "drift_seconds": 60.0,
        },
    )

    _, fallback_verified, fallback_evidence = resolve_runtime_server_clock(
        fallback_broker,
        is_sim=False,
    )
    _, mismatch_verified, mismatch_evidence = resolve_runtime_server_clock(
        mismatch_broker,
        is_sim=False,
    )

    assert fallback_verified is False
    assert fallback_evidence["reason"] == "wallet_cash_date_header_missing"
    assert mismatch_verified is False
    assert mismatch_evidence["verified"] is False


def test_runtime_server_clock_rejects_stale_server_date_even_when_evidence_claims_verified():
    observed = pd.Timestamp("2026-07-15T09:30:00+09:00").to_pydatetime()
    received_at = observed + pd.Timedelta(seconds=31)
    broker = SimpleNamespace(
        get_server_time=lambda: observed,
        last_server_time_evidence={
            "schema_version": 1,
            "verified": True,
            "source": "wallet_cash_date_header",
            "reason": "verified",
            "server_time": observed.isoformat(),
            "received_at": received_at.isoformat(),
            "drift_seconds": -31.0,
        },
    )

    _, verified, evidence = resolve_runtime_server_clock(broker, is_sim=False)

    assert verified is False
    assert evidence["verified"] is False


def test_daytrade_month_state_initializes_and_does_not_reset_within_same_month():
    first = ensure_daytrade_month_state(
        {},
        1_000_000.0,
        pd.Timestamp("2026-07-01T09:30:00+09:00"),
    )
    same_month = ensure_daytrade_month_state(
        first,
        1_250_000.0,
        pd.Timestamp("2026-07-31T14:00:00+09:00"),
    )

    assert first["current_month"] == "2026-07"
    assert first["month_start_equity"] == 1_000_000.0
    assert same_month["current_month"] == "2026-07"
    assert same_month["month_start_equity"] == 1_000_000.0


def test_daytrade_month_state_rolls_on_verified_server_month_boundary():
    state = ensure_daytrade_month_state(
        {"current_month": "2026-07", "month_start_equity": 1_000_000.0},
        1_180_000.0,
        pd.Timestamp("2026-08-03T09:30:00+09:00"),
    )

    assert state["current_month"] == "2026-08"
    assert state["month_start_equity"] == 1_180_000.0


def test_daytrade_month_state_preserves_anchor_for_invalid_equity():
    original = {"current_month": "2026-07", "month_start_equity": 1_000_000.0}

    state = ensure_daytrade_month_state(
        original,
        float("nan"),
        pd.Timestamp("2026-08-03T09:30:00+09:00"),
    )

    assert state == original


def test_production_observation_universe_uses_prior_liquidity_and_keeps_market_separate():
    data_df = _build_production_snapshot_df()

    with patch("auto_trade.get_prime_tickers", return_value=["1000.T", "1321.T"]), patch(
        "auto_trade.resolve_daytrade_scan_min_turnover",
        return_value=0.0,
    ):
        first = build_daytrade_production_observation_universe(
            data_df,
            max_symbols=49,
        )
        second = build_daytrade_production_observation_universe(
            data_df,
            max_symbols=49,
        )

    assert first == second
    assert first == ["1000"]
    assert "1321" not in first


def test_live_rotating_discovery_adapter_uses_shared_one_day_selector():
    data_df = _build_production_snapshot_df()
    trade_date = data_df.index[-1] + pd.offsets.BDay(1)

    with patch(
        "auto_trade.select_daytrade_rotating_discovery_codes",
        return_value=["1000"],
    ) as shared_selector, patch(
        "auto_trade.get_prime_tickers",
        return_value=["1000.T", "1321.T"],
    ):
        selected = build_daytrade_rotating_discovery_universe(
            data_df,
            trade_date=trade_date,
            excluded_codes=("9999",),
        )

    assert selected == ["1000"]
    kwargs = shared_selector.call_args.kwargs
    assert kwargs["tickers"] == ["1000.T", "1321.T"]
    assert kwargs["feature_asof"] == pd.Timestamp(data_df.index[-1]).normalize()
    assert kwargs["trade_date"] == pd.Timestamp(trade_date).normalize()
    assert kwargs["excluded_codes"] == ("9999",)
    assert len(kwargs["close_prev"]) == 2
    assert len(kwargs["close_prev2"]) == 2


def test_live_rotating_discovery_adapter_rejects_non_future_trade_date():
    data_df = _build_production_snapshot_df()
    with patch("auto_trade.select_daytrade_rotating_discovery_codes") as shared_selector:
        selected = build_daytrade_rotating_discovery_universe(
            data_df,
            trade_date=data_df.index[-1],
        )

    assert selected == []
    shared_selector.assert_not_called()



def test_rotating_discovery_snapshot_adapter_forwards_one_complete_evidence_contract():
    codes = tuple(str(2000 + index) for index in range(196))
    started_at = pd.Timestamp("2026-07-13 09:29:35", tz="Asia/Tokyo")
    protected_started = pd.Timestamp("2026-07-13 09:29:36", tz="Asia/Tokyo")
    protected_completed = pd.Timestamp("2026-07-13 09:29:37", tz="Asia/Tokyo")
    batches = []
    for batch_index in range(4):
        requested = codes[batch_index * 49:(batch_index + 1) * 49]
        batch_started = pd.Timestamp(
            f"2026-07-13 09:29:{38 + batch_index * 2:02d}",
            tz="Asia/Tokyo",
        )
        batch_completed = batch_started + pd.Timedelta(seconds=1)
        batches.append(DaytradeDiscoveryBatchEvidence(
            batch_index=batch_index,
            requested=requested,
            register_ok=True,
            board_requested=requested,
            observed=requested,
            failures=(),
            unregister_ok=True,
            started_at=batch_started,
            completed_at=batch_completed,
        ))
    completed_at = pd.Timestamp("2026-07-13 09:29:50", tz="Asia/Tokyo")
    result = DaytradeOpeningDiscoveryResult(
        requested=codes,
        observations={code: {"open": 100.0} for code in (*codes, "1321")},
        failures={},
        protected_board=DaytradeProtectedBoardEvidence(
            requested=("1321",),
            board_requested=("1321",),
            observed=("1321",),
            failures=(),
            started_at=protected_started,
            completed_at=protected_completed,
        ),
        batches=tuple(batches),
        started_at=started_at,
        completed_at=completed_at,
        registry_clean=True,
        final_registered_codes=("1321",),
        rejection_reasons=(),
    )

    with patch(
        "auto_trade.compute_observed_daytrade_production_snapshot",
        return_value={"decision_allowed": True},
    ) as observed_snapshot:
        output = compute_rotating_daytrade_production_snapshot(
            data_df="data",
            symbols_df="symbols",
            discovery_result=result,
            current_equity=1_000_000.0,
            week_start_equity=1_000_000.0,
            account_cash=1_000_000.0,
            server_clock_evidence=_server_clock_evidence(completed_at),
            trade_mode="KABUCOM_TEST",
        )

    assert output == {"decision_allowed": True}
    kwargs = observed_snapshot.call_args.kwargs
    assert len(kwargs["requested_codes"]) == 197
    assert kwargs["requested_codes"][-1] == "1321"
    assert kwargs["boards"] is result.observations
    assert kwargs["event_time"] == completed_at
    assert kwargs["board_batch_started_at"] == started_at
    assert kwargs["board_batch_completed_at"] == completed_at
    assert kwargs["observation_policy"] == "rotating_discovery_196_v1"
    assert len(kwargs["opening_discovery_evidence"]["batches"]) == 4


def test_production_snapshot_collection_continues_while_entry_gate_is_closed():
    assert should_capture_daytrade_production_snapshot(
        is_sim=False,
        scan_interval_ready=True,
        phase_entry_blocked=False,
        now_time=pd.Timestamp("2026-07-13 09:30:00").time(),
    )
    assert not should_capture_daytrade_production_snapshot(
        is_sim=True,
        scan_interval_ready=True,
        phase_entry_blocked=False,
        now_time=pd.Timestamp("2026-07-13 09:30:00").time(),
    )
    assert not should_capture_daytrade_production_snapshot(
        is_sim=False,
        scan_interval_ready=True,
        phase_entry_blocked=False,
        now_time=pd.Timestamp("2026-07-13 14:00:00").time(),
    )


def test_observed_production_snapshot_uses_board_open_and_replays_exactly():
    data_df = _build_production_snapshot_df()
    symbols_df = pd.DataFrame(
        {"コード": ["1000", "1321"], "銘柄名": ["Foo", "Market"]}
    )
    opening_time = pd.Timestamp("2026-07-13 09:00:00", tz="Asia/Tokyo")
    quote_time = pd.Timestamp("2026-07-13 09:30:00", tz="Asia/Tokyo")
    batch_started_at = pd.Timestamp("2026-07-13 09:29:50", tz="Asia/Tokyo")
    previous_close_time = pd.Timestamp("2026-07-10 00:00:00", tz="Asia/Tokyo")
    prior_1000 = float(data_df[("1000.T", "Close")].iloc[-1])
    prior_1321 = float(data_df[("1321.T", "Close")].iloc[-1])
    boards = {
        "1000": {
            "open": 113.0,
            "price": 114.0,
            "current_price": 114.0,
            "opening_price_timestamp": opening_time,
            "previous_close_timestamp": previous_close_time,
            "quote_timestamp": quote_time,
            "current_price_timestamp": quote_time,
            "received_at": quote_time,
            "best_sell_price": 114.1,
            "best_buy_price": 113.9,
            "prev_close": prior_1000,
        },
        "1321": {
            "open": 213.0,
            "price": 214.0,
            "current_price": 214.0,
            "opening_price_timestamp": opening_time,
            "previous_close_timestamp": previous_close_time,
            "quote_timestamp": quote_time,
            "current_price_timestamp": quote_time,
            "received_at": quote_time,
            "best_sell_price": 214.1,
            "best_buy_price": 213.9,
            "prev_close": prior_1321,
        },
    }

    with patch("auto_trade.get_prime_tickers", return_value=["1000.T", "1321.T"]):
        result = compute_observed_daytrade_production_snapshot(
            data_df=data_df,
            symbols_df=symbols_df,
            requested_codes={"1321", "1000"},
            boards=boards,
            board_failures={},
            board_batch_started_at=batch_started_at,
            board_batch_completed_at=quote_time,
            event_time=quote_time,
            current_equity=1_000_000.0,
            week_start_equity=1_000_000.0,
            account_cash=1_000_000.0,
            server_clock_evidence=_server_clock_evidence(quote_time),
            trade_mode="KABUCOM_TEST",
            is_simulation=False,
        )

    snapshot = result["production_snapshot"]
    replay = auto_trade.replay_daytrade_production_snapshot(snapshot)
    symbol_by_code = {
        item["code"]: item
        for item in snapshot["inputs"]["symbols"]
    }
    assert snapshot["decision_allowed"] is True
    assert snapshot["eligible_for_decision_clean_holdout"] is False
    assert replay.parity is True
    assert replay.replayable is True
    assert symbol_by_code["1000"]["open_today"] == 113.0
    assert "session_high" not in symbol_by_code["1000"]
    assert symbol_by_code["1000"]["previous_close_timestamp"].startswith("2026-07-10")
    assert snapshot["inputs"]["execution_quotes"][0]["current_price"] in {114.0, 214.0}

    mismatched_boards = {code: dict(value) for code, value in boards.items()}
    mismatched_boards["1000"]["prev_close"] = prior_1000 + 10.0
    with patch("auto_trade.get_prime_tickers", return_value=["1000.T", "1321.T"]):
        blocked = compute_observed_daytrade_production_snapshot(
            data_df=data_df,
            symbols_df=symbols_df,
            requested_codes={"1321", "1000"},
            boards=mismatched_boards,
            board_failures={},
            event_time=quote_time,
            board_batch_started_at=batch_started_at,
            board_batch_completed_at=quote_time,
            current_equity=1_000_000.0,
            week_start_equity=1_000_000.0,
            account_cash=1_000_000.0,
            server_clock_evidence=_server_clock_evidence(quote_time),
            trade_mode="KABUCOM_TEST",
            is_simulation=False,
        )
    assert blocked["decision_allowed"] is False
    assert "1000:board_cache_prev_close_mismatch" in blocked["rejection_reasons"]



def test_daytrade_decision_log_records_shared_candidate_context():
    candidates = [
        {
            "code": "1000",
            "name": "Foo",
            "setup_type": "primary",
            "candidate_rank": 2,
            "score": 8.5,
            "gap_pct": 0.004,
            "open_vs_sma_atr": 1.2,
            "rs_alpha": 35.0,
            "decision_snapshot_id": "snapshot-1",
        }
    ]
    rows = auto_trade.build_daytrade_decision_log_rows(
        candidates,
        decision="selected_for_sizing",
        event_time="2026-07-10 09:31:00",
        reason="entry_review_passed",
        breadth=0.62,
        market_ratio=1.04,
        selected_count=1,
        dynamic_leverage=1.5,
        is_simulation=False,
        trade_mode="KABUCOM_TEST",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["time"] == "2026-07-10 09:31:00"
    assert row["trade_mode"] == "KABUCOM_TEST"
    assert row["is_simulation"] is False
    assert row["decision"] == "selected_for_sizing"
    assert row["candidate_rank"] == 2
    assert row["selected_count"] == 1
    assert row["code"] == "1000"
    assert row["setup_type"] == "primary"
    assert row["decision_snapshot_id"] == "snapshot-1"
    assert row["breadth"] == 0.62
    assert row["market_ratio"] == 1.04

    with patch("auto_trade.append_csv_rows") as append_rows, patch(
        "auto_trade.rotate_csv_if_large"
    ) as rotate:
        recorded = auto_trade.record_daytrade_decision(
            candidates,
            decision="scan_candidate",
            event_time="2026-07-10 09:30:00",
            breadth=0.62,
            market_ratio=1.04,
            is_simulation=True,
            trade_mode="SIM",
        )

    assert recorded[0]["decision"] == "scan_candidate"
    append_rows.assert_called_once_with(auto_trade.DAYTRADE_DECISION_LOG_FILE, recorded)
    rotate.assert_called_once_with(auto_trade.DAYTRADE_DECISION_LOG_FILE, max_size_mb=20)



def test_daytrade_decision_log_records_operational_evidence():
    candidate = {
        "code": "1000",
        "name": "Foo",
        "decision_snapshot_id": "snapshot-1",
    }
    evidence = {
        "operational_evidence_schema_version": 1,
        "news_fetch_status": "ok",
        "news_query_url": "https://example.test/news",
        "news_text": "material news",
        "news_sha256": "sha256:news",
        "news_error": "",
        "ai_outcome": "approved",
        "ai_provider": "gemini",
        "ai_model": "test-model",
        "ai_prompt": "prompt",
        "ai_prompt_sha256": "sha256:prompt",
        "ai_raw_response": "NO\n問題なし",
        "ai_raw_response_sha256": "sha256:response",
        "ai_error": "",
        "unexpected": "must not leak",
    }

    rows = auto_trade.build_daytrade_decision_log_rows(
        [candidate],
        decision="operational_review_passed",
        event_time="2026-07-14 09:31:00",
        reason="ai_filter:approved",
        is_simulation=False,
        trade_mode="KABUCOM_TEST",
        operational_evidence=evidence,
    )

    assert rows[0]["decision_snapshot_id"] == "snapshot-1"
    assert rows[0]["news_text"] == "material news"
    assert rows[0]["ai_model"] == "test-model"
    assert rows[0]["ai_raw_response"] == "NO\n問題なし"
    assert "unexpected" not in rows[0]


def test_daytrade_decision_log_records_entry_quote_evidence():
    evidence = {
        "entry_quote_evidence_schema_version": 1,
        "entry_quote_status": "fresh",
        "entry_quote_code": "1000",
        "entry_quote_batch_completed_at": "2026-07-14T09:30:01+09:00",
        "entry_quote_age_seconds": 6.0,
        "entry_quote_best_sell_price": 101.0,
        "entry_quote_reason": "",
        "unexpected": "must not leak",
    }

    rows = auto_trade.build_daytrade_decision_log_rows(
        [{"code": "1000", "decision_snapshot_id": "snapshot-1"}],
        decision="entry_quote_refresh_passed",
        event_time="2026-07-14 09:30:01",
        entry_price=101.0,
        is_simulation=False,
        entry_quote_evidence=evidence,
    )

    assert rows[0]["entry_quote_status"] == "fresh"
    assert rows[0]["entry_quote_best_sell_price"] == 101.0
    assert rows[0]["entry_quote_age_seconds"] == 6.0
    assert "unexpected" not in rows[0]


def test_entry_risk_evidence_caps_wallet_power_and_records_price_ceiling():
    item = {
        "code": "1000",
        "turnover": 1_000_000_000,
        "notional_pct": 0.15,
        "risk_budget_pct": 0.10,
    }

    envelope, evidence = auto_trade.build_daytrade_entry_risk_evidence(
        item,
        day_equity=1_000_000,
        theoretical_buying_power=5_000_000,
        wallet_margin_buying_power=5_000_000,
        candidate_buying_power=5_000_000,
        candidate_dynamic_leverage=1.0,
        quote_price=1_000.0,
        buy_price=1_000.0,
        stop_price=890.0,
    )

    assert envelope["status"] == "approved"
    assert envelope["shares"] == 700
    assert envelope["max_entry_price"] == 1_032.0
    assert evidence["entry_risk_status"] == "approved"
    assert evidence["entry_risk_code"] == "1000"
    assert evidence["entry_risk_shares"] == 700
    assert evidence["entry_risk_max_entry_price"] == 1_032.0

    rows = auto_trade.build_daytrade_decision_log_rows(
        [{"code": "1000", "decision_snapshot_id": "snapshot-1"}],
        decision="entry_risk_resolved",
        event_time="2026-07-15 09:30:02",
        is_simulation=False,
        entry_risk_evidence={**evidence, "unexpected": "must not leak"},
    )
    assert rows[0]["entry_risk_buying_power"] == 5_000_000
    assert rows[0]["entry_risk_max_entry_price"] == 1_032.0
    assert "unexpected" not in rows[0]


def test_entry_risk_evidence_blocks_zero_wallet_buying_power():
    envelope, evidence = auto_trade.build_daytrade_entry_risk_evidence(
        {
            "code": "1000",
            "turnover": 1_000_000_000,
            "notional_pct": 0.15,
        },
        day_equity=1_000_000,
        theoretical_buying_power=5_000_000,
        wallet_margin_buying_power=0.0,
        candidate_buying_power=0.0,
        candidate_dynamic_leverage=1.0,
        quote_price=1_000.0,
        buy_price=1_000.0,
        stop_price=900.0,
    )

    assert envelope["status"] == "blocked"
    assert envelope["reason"] == "nonpositive_required_input"
    assert evidence["entry_risk_wallet_margin_buying_power"] == 0.0
    assert evidence["entry_risk_buying_power"] == 0.0
    assert evidence["entry_risk_shares"] == 0


def test_resolve_daytrade_entry_shares_forwards_risk_budget_pct():
    captured = {}

    def _capture_cap_daytrade_position_size(*args, **kwargs):
        captured["risk_budget_pct"] = kwargs.get("risk_budget_pct")
        captured["size_multiplier"] = kwargs.get("size_multiplier")
        return 100

    with patch("auto_trade.calculate_lot_size", return_value=200), patch(
        "auto_trade.cap_daytrade_position_size", side_effect=_capture_cap_daytrade_position_size
    ):
        shares = auto_trade.resolve_daytrade_entry_shares(
            item={
                "atr": 2.0,
                "notional_pct": 1.0,
                "equity_notional_pct": 2.0,
                "risk_budget_pct": 0.105,
                "size_multiplier": 1.5,
            },
            day_equity=10_000_000,
            candidate_buying_power=5_000_000,
            candidate_dynamic_lev=1.0,
            buy_price=100.0,
            stop_price=90.0,
        )

    assert shares == 100
    assert captured["risk_budget_pct"] == 0.105
    assert captured["size_multiplier"] == 1.5


def test_inverse_only_candidate_set_accepts_inverse_pullback():
    assert is_inverse_only_candidate_set([{"setup_type": "inverse_pullback"}])
    assert is_inverse_only_candidate_set(
        [{"setup_type": "inverse"}, {"setup_type": "inverse_pullback"}]
    )
    assert not is_inverse_only_candidate_set([{"setup_type": "inverse_pullback"}, {"setup_type": "fallback"}])
    assert not is_inverse_only_candidate_set([])


def test_build_daytrade_position_record_preserves_setup_and_risk_context():
    record = build_daytrade_position_record(
        {
            "code": "1000",
            "name": "Foo",
            "setup_type": "primary",
            "atr": 2.0,
            "stop_mult": 1.0,
            "target_mult": 1.5,
            "candidate_rank": 3,
            "breadth": 0.62,
            "market_ratio": 1.05,
            "gap_pct": 0.004,
            "prev_return": 0.03,
            "open_vs_sma_atr": 1.2,
            "score": 8.4,
            "rs_alpha": 42.0,
            "prev_rsi2": 63.0,
            "decision_snapshot_id": "snapshot-1",
        },
        executed_price=105.0,
        shares=300,
        buy_time="2026-04-21 09:03:00",
    )

    assert record["setup_type"] == "primary"
    assert record["entry_stop_price"] == 103.0
    assert record["entry_target_price"] == 108.0
    assert record["entry_candidate_rank"] == 3
    assert record["post_entry_high"] == 105.0
    assert record["post_entry_low"] == 105.0
    assert record["buy_rs"] == 42.0
    assert record["buy_rsi2"] == 63.0
    assert record["protective_stop_order_id"] is None
    assert record["decision_snapshot_id"] == "snapshot-1"

def test_daytrade_exit_log_requires_complete_actual_cost_evidence_for_net_pnl():
    position = build_daytrade_position_record(
        {"code": "1000", "name": "Foo", "setup_type": "primary", "atr": 2.0},
        executed_price=100.0,
        shares=100,
        buy_time="2026-07-14 09:01:00",
        execution_id="ENTRY-1",
        entry_commission=10.0,
        entry_commission_tax=1.0,
        entry_execution_costs_complete=True,
    )
    position.update({
        "broker_position_expenses": 3.0,
        "broker_position_commission": 10.0,
        "broker_position_commission_tax": 1.0,
    })

    row = auto_trade.build_daytrade_exit_log_row(
        position,
        exit_reason="target",
        observed_price=110.0,
        modeled_exit_price=110.0,
        exit_time="2026-07-14 10:00:00",
        filled_shares=100,
        remaining_shares=0,
        is_simulation=False,
        exit_order_id="EXIT-1",
        exit_execution_ids=("EXIT-EXEC-1",),
        exit_commission=5.0,
        exit_commission_tax=0.5,
        exit_execution_costs_complete=True,
    )

    assert row["observed_gross_pnl"] == 1000.0
    assert row["actual_total_cost"] == 19.5
    assert row["observed_execution_net_pnl"] == 980.5
    assert row["observed_net_pnl"] is None
    assert row["actual_cost_evidence_complete"] is True
    assert row["actual_net_pnl_evidence_complete"] is False
    assert row["actual_cost_evidence_reason"] == ""
    assert row["entry_cost_source"] == "positions_api"
    assert row["entry_execution_ids"] == ("ENTRY-1",)

    taxed_row = auto_trade.build_daytrade_exit_log_row(
        position,
        exit_reason="target",
        observed_price=110.0,
        modeled_exit_price=110.0,
        exit_time="2026-07-14 10:00:00",
        filled_shares=100,
        remaining_shares=0,
        is_simulation=False,
        exit_commission=5.0,
        exit_commission_tax=0.5,
        exit_execution_costs_complete=True,
        capital_gains_tax=100.0,
        capital_gains_tax_evidence_complete=True,
    )

    assert taxed_row["observed_execution_net_pnl"] == 980.5
    assert taxed_row["observed_net_pnl"] == 880.5
    assert taxed_row["actual_net_pnl_evidence_complete"] is True


def test_daytrade_exit_log_does_not_invent_net_pnl_for_partial_exit():
    position = build_daytrade_position_record(
        {"code": "1000", "name": "Foo", "setup_type": "primary", "atr": 2.0},
        executed_price=100.0, shares=100, buy_time="2026-07-14 09:01:00",
        entry_commission=0.0, entry_commission_tax=0.0, entry_execution_costs_complete=True,
    )
    position.update({
        "broker_position_expenses": 0.0,
        "broker_position_commission": 0.0,
        "broker_position_commission_tax": 0.0,
    })

    row = auto_trade.build_daytrade_exit_log_row(
        position, exit_reason="partial", observed_price=101.0, modeled_exit_price=101.0,
        exit_time="2026-07-14 10:00:00", filled_shares=50, remaining_shares=50,
        is_simulation=False, is_partial_fill=True, exit_commission=0.0,
        exit_commission_tax=0.0, exit_execution_costs_complete=True,
    )

    assert row["actual_cost_evidence_complete"] is False
    assert row["observed_net_pnl"] is None
    assert "partial_exit_cost_allocation_unverified" in row["actual_cost_evidence_reason"]

@pytest.mark.parametrize(
    ("setup_type", "expected_day_buying_power", "expected_inverse_buying_power"),
    [
        ("primary", 979_800.0, 500_000.0),
        ("inverse_pullback", 1_000_000.0, 479_800.0),
    ],
)
def test_open_simulated_daytrade_position_persists_all_setup_types(
    setup_type,
    expected_day_buying_power,
    expected_inverse_buying_power,
):
    account = {"cash": 1_000_000.0}
    portfolio = []
    item = {
        "code": "1459" if setup_type.startswith("inverse") else "1000",
        "name": "Test",
        "setup_type": setup_type,
        "atr": 2.0,
    }

    with patch("auto_trade.SLIPPAGE_RATE", 0.01):
        executed_price, day_buying_power, inverse_day_buying_power = (
            auto_trade.open_simulated_daytrade_position(
                account=account,
                portfolio=portfolio,
                item=item,
                buy_price=100.0,
                shares=200,
                day_buying_power=1_000_000.0,
                inverse_day_buying_power=500_000.0,
                buy_time="2026-07-11 09:30:00",
            )
        )

    assert executed_price == 101.0
    assert account["cash"] == 979_800.0
    assert day_buying_power == expected_day_buying_power
    assert inverse_day_buying_power == expected_inverse_buying_power
    assert len(portfolio) == 1
    assert portfolio[0]["code"] == item["code"]
    assert portfolio[0]["setup_type"] == setup_type
    assert portfolio[0]["shares"] == 200
    assert portfolio[0]["buy_price"] == 101.0


def test_mark_daytrade_portfolio_updates_post_entry_extrema_from_current_quote_not_legacy_high_low():
    portfolio = [
        {
            "code": "1000",
            "name": "Foo",
            "buy_time": "2026-04-21 09:03:00",
            "buy_price": 100.0,
            "current_price": 100.0,
            "highest_price": 120.0,
            "lowest_price": 95.0,
            "post_entry_high": 105.0,
            "post_entry_low": 99.0,
            "shares": 300,
        }
    ]

    updated = auto_trade.mark_daytrade_portfolio(
        portfolio,
        latest_close_map={"1000": 106.0},
        quote_time=pd.Timestamp("2026-04-21 09:15:00"),
    )

    record = updated[0]
    assert record["current_price"] == 106.0
    assert record["post_entry_high"] == 106.0
    assert record["post_entry_low"] == 99.0
    assert record["highest_price"] == 106.0
    assert record["lowest_price"] == 99.0


def test_mark_daytrade_portfolio_initializes_post_entry_extrema_without_legacy_high_low_bootstrap():
    portfolio = [
        {
            "code": "1000",
            "name": "Foo",
            "buy_time": "2026-04-21 09:03:00",
            "buy_price": 100.0,
            "current_price": 100.0,
            "highest_price": 120.0,
            "lowest_price": 95.0,
            "shares": 300,
        }
    ]

    updated = auto_trade.mark_daytrade_portfolio(
        portfolio,
        latest_close_map={"1000": 106.0},
        quote_time=pd.Timestamp("2026-04-21 09:15:00"),
        quote_is_fresh=True,
    )

    record = updated[0]
    assert record["current_price"] == 106.0
    assert record["post_entry_high"] == 106.0
    assert record["post_entry_low"] == 100.0
    assert record["highest_price"] == 106.0
    assert record["lowest_price"] == 100.0


def test_mark_daytrade_portfolio_skips_post_entry_extrema_update_for_stale_quote():
    portfolio = [
        {
            "code": "1000",
            "name": "Foo",
            "buy_time": "2026-04-21 09:03:00",
            "buy_price": 100.0,
            "current_price": 100.0,
            "post_entry_high": 105.0,
            "post_entry_low": 99.0,
            "shares": 300,
        }
    ]

    updated = auto_trade.mark_daytrade_portfolio(
        portfolio,
        latest_close_map={"1000": 110.0},
        quote_time=pd.Timestamp("2026-04-21 09:15:00"),
        quote_is_fresh=False,
    )

    record = updated[0]
    assert record["current_price"] == 110.0
    assert record["post_entry_high"] == 105.0
    assert record["post_entry_low"] == 99.0
    assert record["highest_price"] == 105.0
    assert record["lowest_price"] == 99.0


def test_sync_daytrade_registry_tracks_success_and_failure():
    class _Broker:
        def __init__(self, register_result=True, unregister_result=True):
            self.register_result = register_result
            self.unregister_result = unregister_result
            self.registered = []
            self.unregistered = []

        def register_symbols(self, symbols):
            self.registered.append(list(symbols))
            return self.register_result

        def unregister_symbols(self, symbols):
            self.unregistered.append(list(symbols))
            return self.unregister_result

    broker = _Broker(register_result=True, unregister_result=False)
    ok, new_codes, removed_codes = sync_daytrade_registry(
        broker=broker,
        current_targets={"1000", "1321"},
        already_tracked={"1321", "9999"},
        market_index_code="1321",
        is_sim=False,
    )

    assert ok is False
    assert new_codes == {"1000"}
    assert removed_codes == {"9999"}
    assert broker.registered == []
    assert broker.unregistered == [["9999"]]


def test_sync_daytrade_registry_unregisters_before_registering_new_universe():
    class _Broker:
        def __init__(self):
            self.calls = []

        def unregister_symbols(self, symbols):
            self.calls.append(("unregister", set(symbols)))
            return True

        def register_symbols(self, symbols):
            self.calls.append(("register", set(symbols)))
            return True

    broker = _Broker()
    ok, _, _ = sync_daytrade_registry(
        broker=broker,
        current_targets={"1000", "1321"},
        already_tracked={"1321", "9999"},
        market_index_code="1321",
        is_sim=False,
    )

    assert ok is True
    assert broker.calls == [
        ("unregister", {"9999"}),
        ("register", {"1000"}),
    ]


def test_arm_daytrade_protective_stop_matches_live_position_and_records_order_id(tmp_path):
    record = build_daytrade_position_record(
        {
            "code": "1000",
            "name": "Foo",
            "setup_type": "primary",
            "atr": 2.0,
            "stop_mult": 1.0,
            "target_mult": 1.5,
            "decision_snapshot_id": "snapshot-1",
        },
        executed_price=105.0,
        shares=300,
        buy_time="2026-04-21 09:03:00",
        execution_id="EX-1",
    )

    captured = {}

    class _Broker:
        def get_positions(self):
            return [
                {
                    "code": "1000",
                    "ownership": "MANAGED_BY_BOT",
                    "execution_id": "EX-1",
                    "hold_id": "HOLD-1",
                    "exchange": 1,
                    "margin_trade_type": 3,
                    "shares": 300,
                    "hold_qty": 300,
                    "available_qty": 300,
                }
            ]

        def execute_stop_order(self, code, shares, action, trigger_price, hold_id=None, close_positions=None, exchange=None, margin_trade_type=None):
            captured["journal_event"] = append_order_journal(
                {"event": "PLANNED", "kind": "stop", "symbol": code},
                path=str(tmp_path / "order_journal.jsonl"),
            )
            captured.update({
                "code": code,
                "shares": shares,
                "action": action,
                "side": _side_from_action(action),
                "trigger_price": trigger_price,
                "hold_id": hold_id,
                "exchange": exchange,
                "margin_trade_type": margin_trade_type,
            })
            return SimpleNamespace(broker_order_id="STOP-1", status="accepted", confirmed=True)

    stop_order_id = auto_trade._arm_daytrade_protective_stop(
        _Broker(),
        record,
        trigger_price=99.0,
        expected_shares=300,
    )

    assert stop_order_id == "STOP-1"
    assert record["hold_id"] == "HOLD-1"
    assert record["protective_stop_order_id"] == "STOP-1"
    assert record["protective_stop_trigger_price"] == 99.0
    assert record["protective_stop_status"] == "armed"
    journal_event = captured.pop("journal_event")
    assert journal_event["decision_snapshot_id"] == "snapshot-1"
    assert journal_event["lifecycle_stage"] == "protective_stop"
    assert captured == {
        "code": "1000",
        "shares": 300,
        "action": StockOrderAction.MARGIN_CLOSE_LONG,
        "side": "1",
        "trigger_price": 99.0,
        "hold_id": "HOLD-1",
        "exchange": 1,
        "margin_trade_type": 3,
    }


def test_arm_daytrade_protective_stop_requires_exact_execution_id_match():
    record = build_daytrade_position_record(
        {
            "code": "1000",
            "name": "Foo",
            "setup_type": "primary",
            "atr": 2.0,
            "stop_mult": 1.0,
            "target_mult": 1.5,
        },
        executed_price=105.0,
        shares=300,
        buy_time="2026-04-21 09:03:00",
        execution_id="EX-1",
    )

    class _Broker:
        def get_positions(self):
            return [
                {
                    "code": "1000",
                    "ownership": "MANAGED_BY_BOT",
                    "execution_id": "EX-2",
                    "hold_id": "HOLD-1",
                    "exchange": 1,
                    "margin_trade_type": 3,
                    "shares": 300,
                    "hold_qty": 300,
                    "available_qty": 300,
                }
            ]

        def execute_stop_order(self, *args, **kwargs):
            raise AssertionError("execute_stop_order should not be called without an exact execution_id match")

    assert auto_trade._arm_daytrade_protective_stop(
        _Broker(),
        record,
        trigger_price=99.0,
        expected_shares=300,
    ) is None


def test_arm_daytrade_protective_stop_refuses_accepted_stop_without_confirmed_flag():
    record = build_daytrade_position_record(
        {
            "code": "1000",
            "name": "Foo",
            "setup_type": "primary",
            "atr": 2.0,
            "stop_mult": 1.0,
            "target_mult": 1.5,
        },
        executed_price=105.0,
        shares=300,
        buy_time="2026-04-21 09:03:00",
        execution_id="EX-1",
        execution_ids=("EX-1", "EX-2"),
    )

    class _Broker:
        def get_positions(self):
            raise AssertionError("get_positions should not be called when multiple execution_ids have no close route")

        def execute_stop_order(self, code, shares, action, trigger_price, hold_id=None, close_positions=None, exchange=None, margin_trade_type=None):
            raise AssertionError("execute_stop_order should not be called when fallback is disallowed")

    assert record["execution_ids"] == ("EX-1", "EX-2")
    assert auto_trade._arm_daytrade_protective_stop(
        _Broker(),
        record,
        trigger_price=99.0,
        expected_shares=300,
    ) is None
    assert record["protective_stop_status"] == "failed"
    assert record["protective_stop_confirmation_reason"] == "multiple_execution_ids_without_close_route"
    assert record["protective_stop_order_id"] is None
    assert record["protective_stop_unconfirmed_order_id"] is None


def test_arm_daytrade_protective_stop_uses_close_positions_route_when_available():
    record = build_daytrade_position_record(
        {
            "code": "1000",
            "name": "Foo",
            "setup_type": "primary",
            "atr": 2.0,
            "stop_mult": 1.0,
            "target_mult": 1.5,
        },
        executed_price=105.0,
        shares=100,
        buy_time="2026-04-21 09:03:00",
        execution_id="EX-1",
        execution_ids=("EX-1", "EX-2"),
    )

    captured = {}

    class _Broker:
        def _build_close_positions_for_symbol(self, code, requested_qty, managed_execution_ids=None):
            assert code == "1000"
            assert requested_qty == 100
            assert managed_execution_ids == {"EX-1", "EX-2"}
            return {
                "close_positions": [{"HoldID": "HOLD-1", "Qty": 60}, {"HoldID": "HOLD-2", "Qty": 40}],
                "exchange": 1,
                "margin_trade_type": 3,
            }

        def execute_stop_order(self, code, shares, action, trigger_price, hold_id=None, close_positions=None, exchange=None, margin_trade_type=None):
            captured.update({
                "code": code,
                "shares": shares,
                "action": action,
                "side": _side_from_action(action),
                "trigger_price": trigger_price,
                "hold_id": hold_id,
                "close_positions": close_positions,
                "exchange": exchange,
                "margin_trade_type": margin_trade_type,
            })
            return SimpleNamespace(broker_order_id="STOP-MULTI", status="accepted", confirmed=True)

    stop_order_id = auto_trade._arm_daytrade_protective_stop(
        _Broker(),
        record,
        trigger_price=99.0,
        expected_shares=100,
    )

    assert stop_order_id == "STOP-MULTI"
    assert captured["hold_id"] is None
    assert captured["action"] == StockOrderAction.MARGIN_CLOSE_LONG
    assert captured["close_positions"] == [{"HoldID": "HOLD-1", "Qty": 60}, {"HoldID": "HOLD-2", "Qty": 40}]
    assert captured["exchange"] == 1
    assert captured["margin_trade_type"] == 3


def test_arm_daytrade_protective_stop_refuses_unconfirmed_accepted_stop():
    record = build_daytrade_position_record(
        {
            "code": "1000",
            "name": "Foo",
            "setup_type": "primary",
            "atr": 2.0,
            "stop_mult": 1.0,
            "target_mult": 1.5,
        },
        executed_price=105.0,
        shares=300,
        buy_time="2026-04-21 09:03:00",
        execution_id="EX-1",
    )

    class _Broker:
        def get_positions(self):
            return [
                {
                    "code": "1000",
                    "ownership": "MANAGED_BY_BOT",
                    "execution_id": "EX-1",
                    "hold_id": "HOLD-1",
                    "exchange": 1,
                    "margin_trade_type": 3,
                    "shares": 300,
                    "hold_qty": 300,
                    "available_qty": 300,
                }
            ]

        def execute_stop_order(self, *args, **kwargs):
            return SimpleNamespace(
                broker_order_id="STOP-1",
                status="accepted",
                confirmed=False,
                confirmation_reason="stop_order_not_found",
            )

    assert auto_trade._arm_daytrade_protective_stop(
        _Broker(),
        record,
        trigger_price=99.0,
        expected_shares=300,
    ) is None
    assert record["protective_stop_status"] == "failed"
    assert record["protective_stop_confirmation_reason"] == "stop_order_not_found"
    assert record["protective_stop_order_id"] is None
    assert record["protective_stop_unconfirmed_order_id"] == "STOP-1"


def test_arm_daytrade_protective_stop_refuses_to_double_send_when_unconfirmed_stop_is_pending():
    record = build_daytrade_position_record(
        {
            "code": "1000",
            "name": "Foo",
            "setup_type": "primary",
            "atr": 2.0,
            "stop_mult": 1.0,
            "target_mult": 1.5,
        },
        executed_price=105.0,
        shares=300,
        buy_time="2026-04-21 09:03:00",
        execution_id="EX-1",
    )
    record["protective_stop_unconfirmed_order_id"] = "STOP-PENDING"
    record["protective_stop_status"] = "failed"

    class _Broker:
        def get_positions(self):
            raise AssertionError("get_positions should not be called while a protective stop is pending confirmation")

        def execute_stop_order(self, *args, **kwargs):
            raise AssertionError("execute_stop_order should not be called while a protective stop is pending confirmation")

    assert auto_trade._arm_daytrade_protective_stop(
        _Broker(),
        record,
        trigger_price=99.0,
        expected_shares=300,
    ) is None
    assert record["protective_stop_status"] == "failed"
    assert record["protective_stop_confirmation_reason"] == "protective_stop_pending_confirmation"
    assert record["protective_stop_unconfirmed_order_id"] == "STOP-PENDING"


def test_arm_daytrade_protective_stop_refuses_fallback_when_multiple_execution_ids_are_known():
    record = build_daytrade_position_record(
        {
            "code": "1000",
            "name": "Foo",
            "setup_type": "primary",
            "atr": 2.0,
            "stop_mult": 1.0,
            "target_mult": 1.5,
        },
        executed_price=105.0,
        shares=300,
        buy_time="2026-04-21 09:03:00",
        execution_id="EX-1",
    )

    class _Broker:
        def get_positions(self):
            return [
                {
                    "code": "1000",
                    "ownership": "MANAGED_BY_BOT",
                    "execution_id": "EX-1",
                    "hold_id": "HOLD-1",
                    "exchange": 1,
                    "margin_trade_type": 3,
                    "shares": 300,
                    "hold_qty": 300,
                    "available_qty": 300,
                }
            ]

        def execute_stop_order(self, *args, **kwargs):
            return SimpleNamespace(
                broker_order_id="STOP-1",
                status="accepted",
            )

    assert auto_trade._arm_daytrade_protective_stop(
        _Broker(),
        record,
        trigger_price=99.0,
        expected_shares=300,
    ) is None
    assert record["protective_stop_status"] == "failed"
    assert record["protective_stop_confirmation_reason"] == "stop_order_unconfirmed"
    assert record["protective_stop_order_id"] is None
    assert record["protective_stop_unconfirmed_order_id"] == "STOP-1"


def test_cancel_linked_protective_stop_before_exit_uses_unconfirmed_stop_order_id():
    position = {
        "code": "1000",
        "protective_stop_status": "failed",
        "protective_stop_unconfirmed_order_id": "STOP-1",
        "protective_stop_trigger_price": 99.0,
    }
    captured = {}

    class _Broker:
        def cancel_order(self, order_id):
            captured["order_id"] = order_id
            return True

    cancel_ok, cancel_result = cancel_linked_protective_stop_before_exit(
        broker=_Broker(),
        position=position,
    )

    assert cancel_ok is True
    assert cancel_result is None
    assert captured["order_id"] == "STOP-1"
    assert position["protective_stop_status"] == "cancelled"
    assert position["protective_stop_cancelled_order_id"] == "STOP-1"
    assert position["protective_stop_order_id"] is None
    assert position["protective_stop_unconfirmed_order_id"] is None
    assert position["protective_stop_trigger_price"] is None


def test_arm_daytrade_protective_stop_refuses_when_hold_qty_is_unknown():
    record = build_daytrade_position_record(
        {
            "code": "1000",
            "name": "Foo",
            "setup_type": "primary",
            "atr": 2.0,
            "stop_mult": 1.0,
            "target_mult": 1.5,
        },
        executed_price=105.0,
        shares=300,
        buy_time="2026-04-21 09:03:00",
        execution_id="EX-1",
    )

    class _Broker:
        def get_positions(self):
            return [
                {
                    "code": "1000",
                    "ownership": "MANAGED_BY_BOT",
                    "execution_id": "EX-1",
                    "hold_id": "HOLD-1",
                    "exchange": 1,
                    "margin_trade_type": 3,
                    "shares": 300,
                    "hold_qty": None,
                    "available_qty": None,
                }
            ]

        def execute_stop_order(self, *args, **kwargs):
            raise AssertionError("execute_stop_order should not be called when hold_qty is unknown")

    assert auto_trade._arm_daytrade_protective_stop(
        _Broker(),
        record,
        trigger_price=99.0,
        expected_shares=300,
    ) is None


def test_close_daytrade_positions_by_signal_cancels_protective_stop_before_exit_and_rearms_partial_remainder():
    position = {
        "code": "1000",
        "name": "Foo",
        "setup_type": "primary",
        "buy_time": "2026-04-21 09:03:00",
        "buy_price": 100.0,
        "highest_price": 105.0,
        "lowest_price": 99.2,
        "post_entry_high": 105.0,
        "post_entry_low": 99.2,
        "current_price": 100.0,
        "shares": 300,
        "buy_atr": 2.0,
        "stop_mult": 1.0,
        "target_mult": 1.5,
        "entry_stop_price": 98.0,
        "entry_target_price": 103.0,
        "execution_id": "EX-1",
        "hold_id": "HOLD-1",
        "protective_stop_order_id": "STOP-1",
        "protective_stop_trigger_price": 98.0,
        "protective_stop_status": "armed",
        "ownership": "MANAGED_BY_BOT",
    }

    buffer = RealtimeBuffer("1000")
    buffer.update(
        100.0,
        1_000,
        pd.Timestamp("2026-04-21 10:15:00"),
        open_price=100.0,
        high_price=105.0,
        low_price=99.5,
    )

    call_order = []

    class _Broker:
        def __init__(self):
            self.positions = [
                {
                    "code": "1000",
                    "ownership": "MANAGED_BY_BOT",
                    "execution_id": "EX-1",
                    "hold_id": "HOLD-1",
                    "exchange": 1,
                    "margin_trade_type": 3,
                    "shares": 150,
                    "hold_qty": 150,
                    "available_qty": 150,
                }
            ]

        def cancel_order(self, order_id):
            call_order.append(("cancel_order", order_id))
            return CancelResult(
                status=CancelStatus.ACCEPTED,
                order_id=order_id,
                parsed_order=None,
                cumulative_qty=0,
                remaining_qty=0,
                request_sent=True,
                confirmed=True,
            )

        def execute_chase_order(self, code, shares, action, atr=0):
            call_order.append(("execute_chase_order", code, shares, _side_from_action(action)))
            assert shares == 300
            self.positions[0]["shares"] = 150
            self.positions[0]["hold_qty"] = 150
            self.positions[0]["available_qty"] = 150
            return {
                "filled_qty": 150,
                "average_price": 101.0,
                "remaining_qty": 150,
                "unresolved": False,
                "execution_ids": ("EX-1",),
                "execution_id": "EX-1",
                "submission_status": "accepted",
                "process_state": "terminal",
            }

        def get_positions(self):
            call_order.append(("get_positions", None))
            return list(self.positions)

        def execute_stop_order(self, code, shares, action, trigger_price, hold_id=None, close_positions=None, exchange=None, margin_trade_type=None):
            call_order.append(("execute_stop_order", code, shares, _side_from_action(action), trigger_price, hold_id, close_positions, exchange, margin_trade_type))
            return SimpleNamespace(broker_order_id="STOP-2", status="accepted", confirmed=True)

        def log_trade(self, trade_record):
            call_order.append(("log_trade", trade_record["side"], trade_record["shares"]))

    remaining_portfolio, exit_actions, updated_account = auto_trade.close_daytrade_positions_by_signal(
        portfolio=[position],
        account={"cash": 1_000_000.0, "realized_pnl_today": 0.0},
        broker=_Broker(),
        is_sim=False,
        realtime_buffers={"1000": buffer},
    )

    assert call_order[0] == ("cancel_order", "STOP-1")
    assert any(item[0] == "execute_chase_order" for item in call_order)
    assert any(item[0] == "execute_stop_order" for item in call_order)
    assert any(action.startswith("STOP 1000 - protective stop rearmed") for action in exit_actions)
    assert len(remaining_portfolio) == 1
    assert remaining_portfolio[0]["shares"] == 150
    assert remaining_portfolio[0]["protective_stop_order_id"] == "STOP-2"
    assert remaining_portfolio[0]["protective_stop_status"] == "armed"
    assert updated_account["realized_pnl_today"] == 0.0
    assert updated_account["realized_pnl_evidence_complete"] is False
    assert updated_account["realized_pnl_unresolved_exit_count"] == 1


def test_close_daytrade_positions_by_signal_marks_partial_remainder_unresolved_when_rearm_fails():
    position = {
        "code": "1000",
        "name": "Foo",
        "setup_type": "primary",
        "buy_time": "2026-04-21 09:03:00",
        "buy_price": 100.0,
        "highest_price": 105.0,
        "lowest_price": 99.2,
        "post_entry_high": 105.0,
        "post_entry_low": 99.2,
        "current_price": 100.0,
        "shares": 300,
        "buy_atr": 2.0,
        "stop_mult": 1.0,
        "target_mult": 1.5,
        "entry_stop_price": 98.0,
        "entry_target_price": 103.0,
        "execution_id": "EX-1",
        "hold_id": "HOLD-1",
        "protective_stop_order_id": "STOP-1",
        "protective_stop_trigger_price": 98.0,
        "protective_stop_status": "armed",
        "ownership": "MANAGED_BY_BOT",
    }

    buffer = RealtimeBuffer("1000")
    buffer.update(
        100.0,
        1_000,
        pd.Timestamp("2026-04-21 10:15:00"),
        open_price=100.0,
        high_price=105.0,
        low_price=99.5,
    )

    class _Broker:
        def __init__(self):
            self.positions = [
                {
                    "code": "1000",
                    "ownership": "MANAGED_BY_BOT",
                    "execution_id": "EX-1",
                    "hold_id": "HOLD-1",
                    "exchange": 1,
                    "margin_trade_type": 3,
                    "shares": 150,
                    "hold_qty": 150,
                    "available_qty": 150,
                }
            ]

        def cancel_order(self, order_id):
            return CancelResult(
                status=CancelStatus.ACCEPTED,
                order_id=order_id,
                parsed_order=None,
                cumulative_qty=0,
                remaining_qty=0,
                request_sent=True,
                confirmed=True,
            )

        def execute_chase_order(self, code, shares, action, atr=0):
            self.positions[0]["shares"] = 150
            self.positions[0]["hold_qty"] = 150
            self.positions[0]["available_qty"] = 150
            return {
                "filled_qty": 150,
                "average_price": 101.0,
                "remaining_qty": 150,
                "unresolved": False,
                "execution_ids": ("EX-1",),
                "execution_id": "EX-1",
                "submission_status": "accepted",
                "process_state": "terminal",
            }

        def get_positions(self):
            return list(self.positions)

        def execute_stop_order(self, *args, **kwargs):
            return SimpleNamespace(status="accepted")

        def log_trade(self, trade_record):
            pass

    remaining_portfolio, exit_actions, updated_account = auto_trade.close_daytrade_positions_by_signal(
        portfolio=[position],
        account={"cash": 1_000_000.0, "realized_pnl_today": 0.0},
        broker=_Broker(),
        is_sim=False,
        realtime_buffers={"1000": buffer},
    )

    assert len(remaining_portfolio) == 1
    assert remaining_portfolio[0]["exit_order_unresolved"] is True
    assert remaining_portfolio[0]["exit_order_unresolved_reason"] == "protective_stop_rearm_failed"
    assert remaining_portfolio[0]["exit_order_remaining_qty"] == 150
    assert any(action.startswith("STOP 1000 - protective stop rearm failed") for action in exit_actions)
    assert updated_account["realized_pnl_today"] == 0.0
    assert updated_account["realized_pnl_evidence_complete"] is False
    assert updated_account["realized_pnl_unresolved_exit_count"] == 1


def test_close_daytrade_positions_by_signal_skips_exit_when_protective_stop_cancel_is_unconfirmed():
    position = {
        "code": "1000",
        "name": "Foo",
        "setup_type": "primary",
        "buy_time": "2026-04-21 09:03:00",
        "buy_price": 100.0,
        "highest_price": 105.0,
        "lowest_price": 99.2,
        "post_entry_high": 105.0,
        "post_entry_low": 99.2,
        "current_price": 100.0,
        "shares": 300,
        "buy_atr": 2.0,
        "stop_mult": 1.0,
        "target_mult": 1.5,
        "entry_stop_price": 98.0,
        "entry_target_price": 103.0,
        "execution_id": "EX-1",
        "hold_id": "HOLD-1",
        "protective_stop_order_id": "STOP-1",
        "protective_stop_status": "armed",
        "ownership": "MANAGED_BY_BOT",
    }

    buffer = RealtimeBuffer("1000")
    buffer.update(
        100.0,
        1_000,
        pd.Timestamp("2026-04-21 10:15:00"),
        open_price=100.0,
        high_price=105.0,
        low_price=99.5,
    )

    class _Broker:
        def cancel_order(self, order_id):
            return CancelResult(
                status=CancelStatus.UNKNOWN,
                order_id=order_id,
                parsed_order=None,
                cumulative_qty=0,
                remaining_qty=0,
                request_sent=True,
                confirmed=False,
                rejection_reason="cancel_not_confirmed",
            )

        def execute_chase_order(self, *args, **kwargs):
            raise AssertionError("execute_chase_order should not be called until the linked stop is cleared")

    remaining_portfolio, exit_actions, updated_account = auto_trade.close_daytrade_positions_by_signal(
        portfolio=[position],
        account={"cash": 1_000_000.0, "realized_pnl_today": 0.0},
        broker=_Broker(),
        is_sim=False,
        realtime_buffers={"1000": buffer},
    )

    assert len(remaining_portfolio) == 1
    assert remaining_portfolio[0]["protective_stop_cancel_unresolved"] is True
    assert remaining_portfolio[0]["protective_stop_cancel_reason"] == "cancel_not_confirmed"
    assert remaining_portfolio[0]["exit_order_unresolved"] is True
    assert any(action.startswith("SKIP 1000 - protective stop cancel unresolved") for action in exit_actions)
    assert updated_account["realized_pnl_today"] == 0.0


def test_daytrade_primary_failed_runup_exit_uses_live_session_high():
    record = build_daytrade_position_record(
        {
            "code": "1000",
            "setup_type": "primary",
            "atr": 2.0,
            "stop_mult": 1.0,
            "target_mult": 1.5,
        },
        executed_price=105.0,
        shares=300,
        buy_time="2026-04-21 09:03:00",
    )

    buffer = RealtimeBuffer("1000")
    buffer.update(
        104.8,
        1_000,
        pd.Timestamp("2026-04-21 10:00:00"),
        open_price=105.0,
        high_price=107.6,
        low_price=104.6,
    )

    exit_price, exit_reason = resolve_daytrade_live_exit_decision(
        setup_type=record["setup_type"],
        buy_price=record["buy_price"],
        open_price=buffer.get_session_open(),
        high_price=buffer.get_session_high(),
        low_price=buffer.get_session_low(),
        current_price=buffer.get_latest_price(),
        stop_price=record["entry_stop_price"],
        target_price=record["entry_target_price"],
        session_high=buffer.get_session_high(),
        allow_close_exit=False,
    )

    assert exit_reason == "intraday_failed_runup"
    assert exit_price == record["buy_price"]


def test_build_daytrade_watch_plan_prioritizes_open_positions_and_index():
    watchlist = [f"{1000 + idx}" for idx in range(60)]
    portfolio = [{"code": "9000"}]

    plan = build_daytrade_watch_plan(watchlist=watchlist, portfolio=portfolio, market_index_code="1321")

    assert len(plan["registration_targets"]) == 50
    assert plan["registration_targets"][0] == "9000"
    assert plan["registration_targets"][1] == "1321"
    assert "9000" in plan["current_targets"]
    assert "1321" in plan["current_targets"]


def test_close_daytrade_positions_by_signal_ignores_pre_entry_session_extremes():
    position = {
        "code": "1000",
        "name": "Foo",
        "setup_type": "primary",
        "buy_time": "2026-04-21 09:03:00",
        "buy_price": 100.0,
        "highest_price": 101.0,
        "lowest_price": 99.2,
        "current_price": 100.0,
        "shares": 100,
        "buy_atr": 2.0,
        "stop_mult": 1.0,
        "target_mult": 1.5,
        "entry_stop_price": 98.0,
        "entry_target_price": 103.0,
    }

    buffer = RealtimeBuffer("1000")
    buffer.update(
        99.8,
        1_000,
        pd.Timestamp("2026-04-21 10:15:00"),
        open_price=95.0,
        high_price=120.0,
        low_price=95.0,
    )

    class _FailIfCalledBroker:
        def execute_chase_order(self, *args, **kwargs):
            raise AssertionError("execute_chase_order should not be called when only pre-entry extremes are present")

    remaining_portfolio, exit_actions, updated_account = close_daytrade_positions_by_signal(
        portfolio=[position],
        account={"cash": 1_000_000.0},
        broker=_FailIfCalledBroker(),
        is_sim=True,
        realtime_buffers={"1000": buffer},
    )

    assert exit_actions == []
    assert len(remaining_portfolio) == 1
    assert remaining_portfolio[0]["code"] == "1000"
    assert updated_account["cash"] == 1_000_000.0


def test_close_daytrade_positions_skips_unmanaged_live_positions():
    position = {
        "code": "1000",
        "name": "Foo",
        "setup_type": "primary",
        "buy_time": "2026-04-21 09:03:00",
        "buy_price": 100.0,
        "highest_price": 101.0,
        "lowest_price": 99.2,
        "current_price": 100.0,
        "shares": 100,
        "ownership": "UNMANAGED",
    }

    buffer = RealtimeBuffer("1000")
    buffer.update(
        99.8,
        1_000,
        pd.Timestamp("2026-04-21 10:15:00"),
        open_price=100.0,
        high_price=120.0,
        low_price=95.0,
    )

    class _FailIfCalledBroker:
        def execute_chase_order(self, *args, **kwargs):
            raise AssertionError("execute_chase_order should not be called for unmanaged live positions")

    remaining_portfolio, sell_actions, updated_account = auto_trade.close_daytrade_positions(
        portfolio=[position],
        account={"cash": 1_000_000.0},
        broker=_FailIfCalledBroker(),
        is_sim=False,
        realtime_buffers={"1000": buffer},
    )

    assert len(remaining_portfolio) == 1
    assert remaining_portfolio[0]["code"] == "1000"
    assert sell_actions and sell_actions[0].startswith("SKIP 1000")
    assert updated_account["cash"] == 1_000_000.0


def test_close_daytrade_positions_blocks_live_exit_when_protective_stop_cancel_is_unconfirmed():
    position = {
        "code": "1000",
        "name": "Foo",
        "setup_type": "primary",
        "buy_time": "2026-04-21 09:03:00",
        "buy_price": 100.0,
        "highest_price": 101.0,
        "lowest_price": 99.2,
        "current_price": 100.0,
        "shares": 100,
        "buy_atr": 2.0,
        "stop_mult": 1.0,
        "target_mult": 1.5,
        "entry_stop_price": 98.0,
        "entry_target_price": 103.0,
        "execution_id": "EX-1",
        "hold_id": "HOLD-1",
        "protective_stop_order_id": "STOP-1",
        "protective_stop_status": "armed",
        "ownership": "MANAGED_BY_BOT",
    }

    buffer = RealtimeBuffer("1000")
    buffer.update(
        95.0,
        1_000,
        pd.Timestamp("2026-04-21 10:15:00"),
        open_price=100.0,
        high_price=120.0,
        low_price=95.0,
    )

    class _FailIfCalledBroker:
        def cancel_order(self, order_id):
            return CancelResult(
                status=CancelStatus.UNKNOWN,
                order_id=order_id,
                parsed_order=None,
                cumulative_qty=0,
                remaining_qty=0,
                request_sent=True,
                confirmed=False,
                rejection_reason="cancel_not_confirmed",
            )

        def execute_chase_order(self, *args, **kwargs):
            raise AssertionError("execute_chase_order should not be called until the linked stop is cleared")

    remaining_portfolio, sell_actions, updated_account = auto_trade.close_daytrade_positions(
        portfolio=[position],
        account={"cash": 1_000_000.0, "realized_pnl_today": 0.0},
        broker=_FailIfCalledBroker(),
        is_sim=False,
        realtime_buffers={"1000": buffer},
    )

    assert len(remaining_portfolio) == 1
    assert remaining_portfolio[0]["protective_stop_cancel_unresolved"] is True
    assert remaining_portfolio[0]["exit_order_unresolved"] is True
    assert remaining_portfolio[0]["exit_order_unresolved_reason"] == "cancel_not_confirmed"
    assert any(action.startswith("SKIP 1000 - protective stop cancel unresolved") for action in sell_actions)
    assert updated_account["realized_pnl_today"] == 0.0


def test_close_daytrade_positions_skips_exit_when_protective_stop_filled_before_cancel():
    position = {
        "code": "1000",
        "name": "Foo",
        "setup_type": "primary",
        "buy_time": "2026-04-21 09:03:00",
        "buy_price": 100.0,
        "highest_price": 101.0,
        "lowest_price": 99.2,
        "current_price": 100.0,
        "shares": 100,
        "buy_atr": 2.0,
        "stop_mult": 1.0,
        "target_mult": 1.5,
        "entry_stop_price": 98.0,
        "entry_target_price": 103.0,
        "execution_id": "EX-1",
        "hold_id": "HOLD-1",
        "protective_stop_order_id": "STOP-1",
        "protective_stop_status": "armed",
        "ownership": "MANAGED_BY_BOT",
    }

    buffer = RealtimeBuffer("1000")
    buffer.update(
        95.0,
        1_000,
        pd.Timestamp("2026-04-21 10:15:00"),
        open_price=100.0,
        high_price=120.0,
        low_price=95.0,
    )

    class _FailIfCalledBroker:
        def cancel_order(self, order_id):
            return CancelResult(
                status=CancelStatus.ACCEPTED,
                order_id=order_id,
                parsed_order=None,
                cumulative_qty=100,
                remaining_qty=0,
                request_sent=True,
                confirmed=True,
                terminal_status=CancelTerminalStatus.FILLED_BEFORE_CANCEL,
            )

        def execute_chase_order(self, *args, **kwargs):
            raise AssertionError("execute_chase_order should not be called when the linked stop filled before cancel")

    remaining_portfolio, sell_actions, updated_account = auto_trade.close_daytrade_positions(
        portfolio=[position],
        account={"cash": 1_000_000.0, "realized_pnl_today": 0.0},
        broker=_FailIfCalledBroker(),
        is_sim=False,
        realtime_buffers={"1000": buffer},
    )

    assert len(remaining_portfolio) == 1
    assert remaining_portfolio[0]["protective_stop_cancel_unresolved"] is True
    assert remaining_portfolio[0]["exit_order_unresolved"] is True
    assert remaining_portfolio[0]["exit_order_unresolved_reason"] == "filled_before_cancel"
    assert any(action.startswith("SKIP 1000 - protective stop cancel unresolved") for action in sell_actions)
    assert updated_account["realized_pnl_today"] == 0.0


def test_close_daytrade_positions_by_signal_skips_unmanaged_live_positions():
    position = {
        "code": "1000",
        "name": "Foo",
        "setup_type": "primary",
        "buy_time": "2026-04-21 09:03:00",
        "buy_price": 100.0,
        "highest_price": 101.0,
        "lowest_price": 99.2,
        "current_price": 100.0,
        "shares": 100,
        "ownership": "UNMANAGED",
    }

    buffer = RealtimeBuffer("1000")
    buffer.update(
        95.0,
        1_000,
        pd.Timestamp("2026-04-21 10:15:00"),
        open_price=100.0,
        high_price=120.0,
        low_price=95.0,
    )

    class _FailIfCalledBroker:
        def execute_chase_order(self, *args, **kwargs):
            raise AssertionError("execute_chase_order should not be called for unmanaged live positions")

    remaining_portfolio, exit_actions, updated_account = auto_trade.close_daytrade_positions_by_signal(
        portfolio=[position],
        account={"cash": 1_000_000.0},
        broker=_FailIfCalledBroker(),
        is_sim=False,
        realtime_buffers={"1000": buffer},
    )

    assert len(remaining_portfolio) == 1
    assert remaining_portfolio[0]["code"] == "1000"
    assert exit_actions and exit_actions[0].startswith("SKIP 1000")
    assert updated_account["cash"] == 1_000_000.0


def test_close_daytrade_positions_by_signal_skips_pending_unresolved_exit_orders():
    position = {
        "code": "1000",
        "name": "Foo",
        "setup_type": "primary",
        "buy_time": "2026-04-21 09:03:00",
        "buy_price": 100.0,
        "highest_price": 101.0,
        "lowest_price": 99.2,
        "current_price": 100.0,
        "shares": 100,
        "exit_order_unresolved": True,
    }

    buffer = RealtimeBuffer("1000")
    buffer.update(
        95.0,
        1_000,
        pd.Timestamp("2026-04-21 10:15:00"),
        open_price=100.0,
        high_price=120.0,
        low_price=95.0,
    )

    class _FailIfCalledBroker:
        def execute_chase_order(self, *args, **kwargs):
            raise AssertionError("execute_chase_order should not be called while an exit order is unresolved")

    remaining_portfolio, exit_actions, updated_account = auto_trade.close_daytrade_positions_by_signal(
        portfolio=[position],
        account={"cash": 1_000_000.0},
        broker=_FailIfCalledBroker(),
        is_sim=False,
        realtime_buffers={"1000": buffer},
    )

    assert len(remaining_portfolio) == 1
    assert remaining_portfolio[0]["code"] == "1000"
    assert exit_actions and exit_actions[0].startswith("SKIP 1000 - unresolved exit order pending")
    assert updated_account["cash"] == 1_000_000.0


def test_close_daytrade_positions_skips_pending_unresolved_exit_orders():
    position = {
        "code": "1000",
        "name": "Foo",
        "setup_type": "primary",
        "buy_time": "2026-04-21 09:03:00",
        "buy_price": 100.0,
        "highest_price": 101.0,
        "lowest_price": 99.2,
        "current_price": 100.0,
        "shares": 100,
        "exit_order_unresolved": True,
    }

    buffer = RealtimeBuffer("1000")
    buffer.update(
        95.0,
        1_000,
        pd.Timestamp("2026-04-21 10:15:00"),
        open_price=100.0,
        high_price=120.0,
        low_price=95.0,
    )

    class _FailIfCalledBroker:
        def execute_chase_order(self, *args, **kwargs):
            raise AssertionError("execute_chase_order should not be called while an exit order is unresolved")

    remaining_portfolio, sell_actions, updated_account = auto_trade.close_daytrade_positions(
        portfolio=[position],
        account={"cash": 1_000_000.0},
        broker=_FailIfCalledBroker(),
        is_sim=False,
        realtime_buffers={"1000": buffer},
    )

    assert len(remaining_portfolio) == 1
    assert remaining_portfolio[0]["code"] == "1000"
    assert sell_actions and sell_actions[0].startswith("SKIP 1000 - unresolved exit order pending")
    assert updated_account["cash"] == 1_000_000.0


def test_handle_shutdown_marks_shutdown_requested_without_exiting():
    prev_requested = auto_trade.SHUTDOWN_REQUESTED
    prev_reason = auto_trade.SHUTDOWN_REASON
    try:
        auto_trade.SHUTDOWN_REQUESTED = False
        auto_trade.SHUTDOWN_REASON = ""
        auto_trade.handle_shutdown(15, None)
        assert auto_trade.SHUTDOWN_REQUESTED is True
        assert auto_trade.SHUTDOWN_REASON == "signal:15"
    finally:
        auto_trade.SHUTDOWN_REQUESTED = prev_requested
        auto_trade.SHUTDOWN_REASON = prev_reason


def test_perform_safe_shutdown_returns_structured_result_when_reconciliation_is_clean():
    class _Broker:
        def __init__(self):
            self.cancelled = []
            self.saved_account = None
            self.saved_portfolio = None

        def get_active_orders(self):
            return {"orders": [], "has_unknown": False, "unresolved_order_ids": []}

        def cancel_order(self, order_id):
            self.cancelled.append(order_id)
            return True

        def save_account(self, account):
            self.saved_account = account

        def save_portfolio(self, portfolio):
            self.saved_portfolio = portfolio

    broker = _Broker()
    with patch("auto_trade.send_discord_notify", return_value=None):
        result = auto_trade.perform_safe_shutdown(
            broker=broker,
            portfolio=[],
            account={"cash": 1_000_000.0},
            is_sim=False,
            realtime_buffers={},
            reason="unit-test",
        )

    assert result.success is True
    assert result.managed_remaining_orders == ()
    assert result.managed_remaining_positions == ()
    assert result.unknown_items == ()
    assert result.errors == ()
    assert result.updated_portfolio == []
    assert result.updated_account["cash"] == 1_000_000.0
    assert broker.saved_portfolio == []
    assert broker.saved_account["cash"] == 1_000_000.0


def test_perform_safe_shutdown_reports_reconciliation_failure_when_active_orders_snapshot_is_missing():
    class _Broker:
        def save_account(self, account):
            self.saved_account = account

        def save_portfolio(self, portfolio):
            self.saved_portfolio = portfolio

        def get_active_orders(self):
            return None

    def _fail_if_called_close_daytrade_positions(*args, **kwargs):
        raise AssertionError("close_daytrade_positions should not run when active orders snapshot is missing")

    broker = _Broker()
    with patch("auto_trade.close_daytrade_positions", side_effect=_fail_if_called_close_daytrade_positions), patch(
        "auto_trade.send_discord_notify",
        return_value=None,
    ):
        result = auto_trade.perform_safe_shutdown(
            broker=broker,
            portfolio=[],
            account={"cash": 1_000_000.0},
            is_sim=False,
            realtime_buffers={},
            reason="unit-test",
        )

    assert result.success is False
    assert "active_orders_snapshot_unavailable" in result.errors


def test_perform_safe_shutdown_blocks_flatten_when_armed_protective_stop_is_missing_from_broker_snapshot():
    class _Broker:
        def __init__(self):
            self.cancelled = []
            self.saved_account = None
            self.saved_portfolio = None

        def get_active_orders(self):
            return {
                "orders": [],
                "has_unknown": False,
                "unresolved_order_ids": [],
            }

        def cancel_order(self, order_id):
            self.cancelled.append(order_id)
            return True

        def save_account(self, account):
            self.saved_account = account

        def save_portfolio(self, portfolio):
            self.saved_portfolio = portfolio

    def _fail_if_called_close_daytrade_positions(*args, **kwargs):
        raise AssertionError("close_daytrade_positions should not run when the protective stop is missing")

    broker = _Broker()
    portfolio = [
        {
            "code": "1000",
            "ownership": "MANAGED_BY_BOT",
            "protective_stop_status": "armed",
            "protective_stop_order_id": "STOP-1",
        },
    ]

    with patch("auto_trade.close_daytrade_positions", side_effect=_fail_if_called_close_daytrade_positions), patch(
        "auto_trade.send_discord_notify",
        return_value=None,
    ):
        result = auto_trade.perform_safe_shutdown(
            broker=broker,
            portfolio=portfolio,
            account={"cash": 1_000_000.0},
            is_sim=False,
            realtime_buffers={},
            reason="unit-test",
        )

    assert result.success is False
    assert any(entry.startswith("protective_stop_missing:1") for entry in result.errors)


def test_perform_safe_shutdown_cancels_only_managed_orders():
    class _Broker:
        def __init__(self):
            self.cancelled = []
            self.saved_account = None
            self.saved_portfolio = None

        def get_active_orders(self):
            return {
                "orders": [
                    {"ID": "STOP-M", "Symbol": "1000"},
                    {"ID": "UNM-1", "Symbol": "2000"},
                ],
                "has_unknown": False,
                "unresolved_order_ids": [],
            }

        def cancel_order(self, order_id):
            self.cancelled.append(order_id)
            return True

        def save_account(self, account):
            self.saved_account = account

        def save_portfolio(self, portfolio):
            self.saved_portfolio = portfolio

    def _noop_close_daytrade_positions(*, portfolio, account, broker, is_sim, realtime_buffers):
        return portfolio, [], account

    broker = _Broker()
    portfolio = [
        {
            "code": "1000",
            "ownership": "MANAGED_BY_BOT",
            "protective_stop_order_id": "STOP-M",
        },
        {
            "code": "2000",
            "ownership": "UNMANAGED",
        },
    ]

    with patch("auto_trade.close_daytrade_positions", side_effect=_noop_close_daytrade_positions), patch(
        "auto_trade.send_discord_notify",
        return_value=None,
    ):
        result = auto_trade.perform_safe_shutdown(
            broker=broker,
            portfolio=portfolio,
            account={"cash": 1_000_000.0},
            is_sim=False,
            realtime_buffers={},
            reason="unit-test",
        )

    assert broker.cancelled == ["STOP-M"]
    assert any(item.get("ID") == "UNM-1" for item in result.unmanaged_orders)
    assert result.success is False


def test_perform_safe_shutdown_blocks_flatten_when_managed_cancel_is_unconfirmed():
    class _Broker:
        def __init__(self):
            self.cancelled = []
            self.saved_account = None
            self.saved_portfolio = None

        def get_active_orders(self):
            return {
                "orders": [
                    {"ID": "STOP-M", "Symbol": "1000"},
                ],
                "has_unknown": False,
                "unresolved_order_ids": [],
            }

        def cancel_order(self, order_id):
            self.cancelled.append(order_id)
            return CancelResult(
                status=CancelStatus.UNKNOWN,
                order_id=order_id,
                parsed_order=None,
                cumulative_qty=0,
                remaining_qty=0,
                request_sent=True,
                confirmed=False,
                rejection_reason="cancel_not_confirmed",
            )

        def save_account(self, account):
            self.saved_account = account

        def save_portfolio(self, portfolio):
            self.saved_portfolio = portfolio

    def _fail_if_called_close_daytrade_positions(*args, **kwargs):
        raise AssertionError("close_daytrade_positions should not run while managed order cancel is unconfirmed")

    broker = _Broker()
    portfolio = [
        {
            "code": "1000",
            "ownership": "MANAGED_BY_BOT",
            "protective_stop_order_id": "STOP-M",
        },
    ]

    with patch("auto_trade.close_daytrade_positions", side_effect=_fail_if_called_close_daytrade_positions), patch(
        "auto_trade.send_discord_notify",
        return_value=None,
    ):
        result = auto_trade.perform_safe_shutdown(
            broker=broker,
            portfolio=portfolio,
            account={"cash": 1_000_000.0},
            is_sim=False,
            realtime_buffers={},
            reason="unit-test",
        )

    assert broker.cancelled == ["STOP-M"]
    assert result.success is False
    assert any(entry.startswith("managed_cancel_unconfirmed:STOP-M") for entry in result.errors)


def test_perform_safe_shutdown_blocks_flatten_when_protective_stop_is_pending():
    class _Broker:
        def __init__(self):
            self.cancelled = []
            self.saved_account = None
            self.saved_portfolio = None

        def get_active_orders(self):
            return {"orders": [], "has_unknown": False, "unresolved_order_ids": []}

        def cancel_order(self, order_id):
            self.cancelled.append(order_id)
            return True

        def save_account(self, account):
            self.saved_account = account

        def save_portfolio(self, portfolio):
            self.saved_portfolio = portfolio

    def _fail_if_called_close_daytrade_positions(*args, **kwargs):
        raise AssertionError("close_daytrade_positions should not run while a protective stop is pending")

    broker = _Broker()
    portfolio = [
        {
            "code": "1000",
            "ownership": "MANAGED_BY_BOT",
            "protective_stop_unconfirmed_order_id": "STOP-PENDING",
        },
    ]

    with patch("auto_trade.close_daytrade_positions", side_effect=_fail_if_called_close_daytrade_positions), patch(
        "auto_trade.send_discord_notify",
        return_value=None,
    ):
        result = auto_trade.perform_safe_shutdown(
            broker=broker,
            portfolio=portfolio,
            account={"cash": 1_000_000.0},
            is_sim=False,
            realtime_buffers={},
            reason="unit-test",
        )

    assert result.success is False
    assert any(entry.startswith("protective_stop_pending:1") for entry in result.errors)


def test_main_exec_initializes_unicode_safe_logging_before_kabu_launcher():
    events = []

    with patch.object(auto_trade, "TRADE_MODE", "KABUCOM_TEST"), patch(
        "auto_trade.setup_logging",
        side_effect=lambda: events.append("logging"),
    ), patch(
        "core.kabu_launcher.ensure_kabu_station_running",
        side_effect=lambda: events.append("launcher") or False,
    ):
        auto_trade._main_exec()

    assert events == ["logging", "launcher"]

def test_main_attempts_safe_shutdown_when_main_exec_raises():
    class _Broker:
        pass

    fake_broker = _Broker()
    fake_result = auto_trade.ShutdownResult(
        success=True,
        managed_remaining_orders=(),
        managed_remaining_positions=(),
        unmanaged_orders=(),
        unmanaged_positions=(),
        ambiguous_items=(),
        unknown_items=(),
        errors=(),
        updated_portfolio=[],
        updated_account={},
    )
    original_state = dict(auto_trade.ACTIVE_RUNTIME_STATE)
    performed = []
    terminated = []

    def _fake_safe_shutdown(**kwargs):
        performed.append(kwargs)
        return fake_result

    def _fake_terminate():
        terminated.append(True)

    try:
        auto_trade.ACTIVE_RUNTIME_STATE.update(
            {
                "broker": fake_broker,
                "portfolio": [{"code": "1000", "ownership": "MANAGED_BY_BOT"}],
                "account": {"cash": 1_000_000.0},
                "is_sim": False,
                "realtime_buffers": {},
            }
        )
        with patch("auto_trade.acquire_lock", return_value=True), \
            patch("auto_trade._main_exec", side_effect=RuntimeError("boom")), \
            patch("auto_trade.send_discord_notify", return_value=None), \
            patch("auto_trade.time.sleep", return_value=None), \
            patch("auto_trade.release_lock", return_value=None), \
            patch("auto_trade.perform_safe_shutdown", side_effect=_fake_safe_shutdown), \
            patch("core.kabu_launcher.terminate_kabu_station", side_effect=_fake_terminate):
            try:
                auto_trade.main()
                raise AssertionError("main() should have exited")
            except SystemExit as exc:
                assert exc.code == 1

        assert performed and performed[0]["broker"] is fake_broker
        assert performed[0]["reason"] == "unexpected_exception"
        assert terminated
    finally:
        auto_trade.ACTIVE_RUNTIME_STATE.clear()
        auto_trade.ACTIVE_RUNTIME_STATE.update(original_state)


def test_perform_non_trading_day_shutdown_uses_safe_shutdown_before_terminating():
    class _Broker:
        pass

    fake_broker = _Broker()
    fake_result = auto_trade.ShutdownResult(
        success=True,
        managed_remaining_orders=(),
        managed_remaining_positions=(),
        unmanaged_orders=(),
        unmanaged_positions=(),
        ambiguous_items=(),
        unknown_items=(),
        errors=(),
        updated_portfolio=[],
        updated_account={},
    )
    performed = []
    terminated = []

    def _fake_safe_shutdown(**kwargs):
        performed.append(kwargs)
        return fake_result

    def _fake_terminate():
        terminated.append(True)

    with patch("auto_trade.perform_safe_shutdown", side_effect=_fake_safe_shutdown), \
        patch("auto_trade.send_discord_notify", return_value=None), \
        patch("core.kabu_launcher.terminate_kabu_station", side_effect=_fake_terminate):
        result = auto_trade.perform_non_trading_day_shutdown(
            broker=fake_broker,
            portfolio=[{"code": "1000", "ownership": "MANAGED_BY_BOT"}],
            account={"cash": 1_000_000.0},
            is_sim=False,
            realtime_buffers={},
            reason="weekend",
        )

    assert result.success is True
    assert performed and performed[0]["broker"] is fake_broker
    assert performed[0]["reason"] == "weekend"
    assert terminated


def test_is_board_quote_snapshot_fresh_accepts_recent_same_day_quotes():
    boards = {
        "1000": {
            "quote_timestamp": pd.Timestamp("2026-04-21 09:10:00", tz="Asia/Tokyo"),
        }
    }
    reference_time = pd.Timestamp("2026-04-21 09:14:00", tz="Asia/Tokyo")

    assert auto_trade._is_board_quote_snapshot_fresh(boards, reference_time, max_age_seconds=600)


def test_is_board_quote_snapshot_fresh_rejects_stale_or_cross_day_quotes():
    stale_boards = {
        "1000": {
            "quote_timestamp": pd.Timestamp("2026-04-21 09:00:00", tz="Asia/Tokyo"),
        }
    }
    cross_day_boards = {
        "1000": {
            "quote_timestamp": pd.Timestamp("2026-04-20 15:00:00", tz="Asia/Tokyo"),
        }
    }
    reference_time = pd.Timestamp("2026-04-21 09:20:00", tz="Asia/Tokyo")

    assert not auto_trade._is_board_quote_snapshot_fresh(stale_boards, reference_time, max_age_seconds=600)
    assert not auto_trade._is_board_quote_snapshot_fresh(cross_day_boards, reference_time, max_age_seconds=600)


def test_portfolio_has_unresolved_execution_state_detects_status_only_partial_fill():
    portfolio = [
        {
            "code": "1000",
            "entry_order_execution_status": "partial_unresolved",
        }
    ]

    assert auto_trade._portfolio_has_unresolved_execution_state(portfolio)
    assert auto_trade._position_has_unresolved_execution_state(portfolio[0])


def test_is_board_quote_snapshot_fresh_rejects_received_at_only_quotes():
    boards = {
        "1000": {
            "received_at": pd.Timestamp("2026-04-21 09:14:00", tz="Asia/Tokyo"),
        }
    }
    reference_time = pd.Timestamp("2026-04-21 09:15:00", tz="Asia/Tokyo")

    assert not auto_trade._is_board_quote_snapshot_fresh(boards, reference_time, max_age_seconds=600)


def test_describe_board_quote_snapshot_freshness_returns_evidence():
    boards = {
        "1000": {
            "quote_timestamp": pd.Timestamp("2026-04-21 09:10:00", tz="Asia/Tokyo"),
            "received_at": pd.Timestamp("2026-04-21 09:10:05", tz="Asia/Tokyo"),
        }
    }
    reference_time = pd.Timestamp("2026-04-21 09:14:00", tz="Asia/Tokyo")

    fresh, evidence = auto_trade._describe_board_quote_snapshot_freshness(boards, reference_time, max_age_seconds=600)

    assert fresh
    assert "reference_time=2026-04-21T09:14:00+09:00" in evidence
    assert "max_age_seconds=600" in evidence
    assert "1000:source=quote_timestamp" in evidence
    assert "1000:quote_timestamp=2026-04-21T09:10:00+09:00" in evidence
    assert "1000:received_at=2026-04-21T09:10:05+09:00" in evidence
    assert "1000:age_seconds=240" in evidence
    assert "board_snapshot_fresh=true" in evidence



def _entry_quote_batch(
    *,
    requested=("1000",),
    observations=None,
    failures=None,
    started_at=None,
    completed_at=None,
):
    started_at = started_at or pd.Timestamp(
        "2026-07-14 09:30:00", tz="Asia/Tokyo"
    )
    completed_at = completed_at or pd.Timestamp(
        "2026-07-14 09:30:01", tz="Asia/Tokyo"
    )
    return SimpleNamespace(
        requested=tuple(requested),
        observations=dict(observations or {}),
        failures=dict(failures or {}),
        started_at=started_at,
        completed_at=completed_at,
    )


def _fresh_entry_board(code="1000", *, bid_time="2026-07-14 09:29:55"):
    return {
        "symbol": code,
        "current_price": 100.0,
        "best_sell_price": 101.0,
        "best_sell_qty": 300,
        "bid_timestamp": pd.Timestamp(bid_time, tz="Asia/Tokyo"),
        "received_at": pd.Timestamp(
            "2026-07-14 09:30:00.800", tz="Asia/Tokyo"
        ),
    }


def test_refresh_daytrade_entry_execution_quotes_uses_fresh_best_sell_for_sizing():
    batch = _entry_quote_batch(
        observations={"1000": _fresh_entry_board()},
    )
    broker = SimpleNamespace(
        get_board_snapshot_batch=lambda codes: batch,
    )

    refreshed, evidence, reasons = (
        auto_trade.refresh_daytrade_entry_execution_quotes(
            broker,
            [{"code": "1000", "price": 99.0}],
        )
    )

    assert reasons == ()
    assert refreshed[0]["price"] == 101.0
    assert evidence["1000"]["entry_quote_status"] == "fresh"
    assert evidence["1000"]["entry_quote_age_seconds"] == 6.0
    assert evidence["1000"]["entry_quote_price_timestamp_source"] == "bid_timestamp"


def test_refresh_daytrade_entry_execution_quotes_rejects_stale_price_timestamp():
    batch = _entry_quote_batch(
        observations={
            "1000": _fresh_entry_board(
                bid_time="2026-07-14 09:29:00",
            )
        },
    )
    broker = SimpleNamespace(
        get_board_snapshot_batch=lambda codes: batch,
    )

    refreshed, evidence, reasons = (
        auto_trade.refresh_daytrade_entry_execution_quotes(
            broker,
            [{"code": "1000"}],
        )
    )

    assert refreshed == []
    assert evidence["1000"]["entry_quote_status"] == "rejected"
    assert "price_timestamp_stale" in evidence["1000"]["entry_quote_reason"]
    assert "1000:price_timestamp_stale" in reasons


def test_refresh_daytrade_entry_execution_quotes_blocks_all_on_partial_failure():
    second_board = _fresh_entry_board("2000")
    batch = _entry_quote_batch(
        requested=("1000", "2000"),
        observations={"2000": second_board},
        failures={"1000": SimpleNamespace(reason="transport")},
    )
    broker = SimpleNamespace(
        get_board_snapshot_batch=lambda codes: batch,
    )

    refreshed, evidence, reasons = (
        auto_trade.refresh_daytrade_entry_execution_quotes(
            broker,
            [{"code": "1000"}, {"code": "2000"}],
        )
    )

    assert refreshed == []
    assert evidence["1000"]["entry_quote_status"] == "rejected"
    assert evidence["2000"]["entry_quote_status"] == "fresh"
    assert "1000:board_failure:transport" in reasons

def test_get_market_phase_treats_half_day_as_morning_only_until_midday_close():
    assert auto_trade.get_market_phase(auto_trade.datetime.time(10, 0), half_day=True) == auto_trade.MarketPhase.MORNING
    assert auto_trade.get_market_phase(auto_trade.datetime.time(11, 30), half_day=True) == auto_trade.MarketPhase.CLOSING_TIME
    assert auto_trade.get_market_phase(auto_trade.datetime.time(12, 0), half_day=True) == auto_trade.MarketPhase.CLOSING_TIME
    assert auto_trade.get_market_phase(auto_trade.datetime.time(12, 0), half_day=False) == auto_trade.MarketPhase.LUNCH
    assert auto_trade.get_market_phase(auto_trade.datetime.time(13, 0), half_day=False) == auto_trade.MarketPhase.AFTERNOON


def test_acquire_lock_writes_metadata_and_release_removes_owned_lock():
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_path = Path(tmpdir) / "bot.lock"

        with patch("auto_trade.LOCK_FILE", str(lock_path)), \
             patch("auto_trade.TRADE_MODE", "KABUCOM_LIVE"), \
             patch("auto_trade.read_git_commit_sha", return_value="sha-test"):
            assert auto_trade.acquire_lock()
            payload = json.loads(lock_path.read_text(encoding="utf-8"))

            assert payload["schema_version"] == 1
            assert payload["pid"] == os.getpid()
            assert payload["trade_mode"] == "KABUCOM_LIVE"
            assert payload["broker_environment"] == "live"
            assert payload["code_sha"] == "sha-test"
            assert payload["approval_hash"] == auto_trade.RUNTIME_LIVE_ORDER_CONFIG_HASH
            assert isinstance(payload["process_start_time"], float)
            assert payload["process_start_time"] > 0
            assert payload["hostname"]
            assert payload["executable"]
            assert payload["acquired_at"]

            auto_trade.release_lock()
            assert not lock_path.exists()


def test_acquire_lock_refuses_malformed_live_lock_without_deleting_it():
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_path = Path(tmpdir) / "bot.lock"
        lock_path.write_text('{"schema_version": 1, "pid": 123}', encoding="utf-8")

        with patch("auto_trade.LOCK_FILE", str(lock_path)), \
             patch("auto_trade.TRADE_MODE", "KABUCOM_LIVE"), \
             patch("auto_trade.read_git_commit_sha", return_value="sha-test"):
            assert not auto_trade.acquire_lock()

        assert lock_path.exists()


def test_acquire_lock_detects_pid_reuse_and_replaces_stale_lock():
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_path = Path(tmpdir) / "bot.lock"

        with patch("auto_trade.LOCK_FILE", str(lock_path)), \
             patch("auto_trade.TRADE_MODE", "KABUCOM_LIVE"), \
             patch("auto_trade.read_git_commit_sha", return_value="sha-test"):
            current_identity = auto_trade._current_lock_identity()
            stale_payload = dict(current_identity)
            stale_payload["schema_version"] = 1
            stale_payload["acquired_at"] = "2026-06-11T00:00:00+00:00"
            stale_payload["process_start_time"] = float(current_identity["process_start_time"]) - 100.0
            lock_path.write_text(json.dumps(stale_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            assert auto_trade.acquire_lock()
            refreshed = json.loads(lock_path.read_text(encoding="utf-8"))

            assert refreshed["pid"] == current_identity["pid"]
            assert refreshed["process_start_time"] == current_identity["process_start_time"]
            assert refreshed["trade_mode"] == "KABUCOM_LIVE"
            assert refreshed["broker_environment"] == "live"
            assert refreshed["code_sha"] == "sha-test"


def test_merge_account_state_preserves_live_strategy_state_when_wallet_snapshot_is_incomplete():
    persisted = {
        "cash": 123456.0,
        "configured_risk_capital": 1_000_000.0,
        "realized_pnl_today": 12_345.0,
        "risk_capital_pnl_today": 9_000.0,
        "risk_capital_evidence_complete": False,
        "risk_capital_evidence_reasons": ["cost_reconciliation_pending"],
        "realized_pnl_trade_date": "2026-07-14",
        "daytrade_week_start_equity": 1_010_000.0,
        "month_start_equity": 1_100_000.0,
        "stock_buying_power": 111.0,
        "margin_buying_power": 222.0,
    }
    snapshot = {
        "cash": 0.0,
        "stock_buying_power": 333.0,
        "margin_buying_power": 0.0,
        "wallet_snapshot_incomplete": True,
        "wallet_cash_ok": True,
        "wallet_margin_ok": False,
    }

    merged = auto_trade.merge_account_state(snapshot, persisted, is_sim=False)

    assert merged["cash"] == 123456.0
    assert merged["configured_risk_capital"] == 1_000_000.0
    assert merged["realized_pnl_today"] == 12_345.0
    assert merged["risk_capital_pnl_today"] == 9_000.0
    assert merged["risk_capital_evidence_complete"] is False
    assert merged["risk_capital_evidence_reasons"] == ["cost_reconciliation_pending"]
    assert merged["realized_pnl_trade_date"] == "2026-07-14"
    assert merged["daytrade_week_start_equity"] == 1_010_000.0
    assert merged["month_start_equity"] == 1_100_000.0
    assert merged["stock_buying_power"] == 333.0
    assert merged["margin_buying_power"] == 222.0
    assert merged["wallet_snapshot_incomplete"] is True
    assert merged["wallet_cash_ok"] is True
    assert merged["wallet_margin_ok"] is False


def test_ensure_live_realized_pnl_state_resets_only_on_new_jst_trade_date():
    prior = {
        "configured_risk_capital": 1_000_000.0,
        "realized_pnl_trade_date": "2026-07-13",
        "realized_pnl_today": 1_000.0,
        "risk_capital_pnl_today": 800.0,
        "realized_pnl_evidence_complete": True,
        "risk_capital_evidence_complete": True,
    }

    rolled = auto_trade.ensure_live_realized_pnl_state(
        prior,
        pd.Timestamp("2026-07-14 08:00:00", tz="Asia/Tokyo"),
    )

    assert rolled["realized_pnl_trade_date"] == "2026-07-14"
    assert rolled["configured_risk_capital"] == 1_000_800.0
    assert rolled["risk_capital_asof_date"] == "2026-07-13"
    assert rolled["realized_pnl_today"] == 0.0
    assert rolled["risk_capital_pnl_today"] == 0.0
    assert rolled["realized_pnl_evidence_complete"] is True
    assert rolled["risk_capital_evidence_complete"] is True
    assert rolled["realized_pnl_evidence_reasons"] == []
    assert rolled["realized_pnl_unresolved_exit_count"] == 0

    rolled["realized_pnl_today"] = 500.0
    rolled["risk_capital_pnl_today"] = 400.0
    same_day = auto_trade.ensure_live_realized_pnl_state(
        rolled,
        pd.Timestamp("2026-07-14 15:00:00", tz="Asia/Tokyo"),
    )
    assert same_day["realized_pnl_today"] == 500.0
    assert same_day["risk_capital_pnl_today"] == 400.0
    assert same_day["configured_risk_capital"] == 1_000_800.0


def test_ensure_live_realized_pnl_state_fails_closed_for_undated_legacy_pnl():
    state = auto_trade.ensure_live_realized_pnl_state(
        {"realized_pnl_today": -500.0},
        pd.Timestamp("2026-07-14 10:00:00", tz="Asia/Tokyo"),
    )

    assert state["realized_pnl_trade_date"] == "2026-07-14"
    assert state["realized_pnl_today"] == 0.0
    assert state["realized_pnl_evidence_complete"] is False
    assert state["realized_pnl_evidence_reasons"] == [
        "legacy_realized_pnl_trade_date_missing"
    ]
    assert state["realized_pnl_unresolved_exit_count"] == 1
    assert state["risk_capital_evidence_complete"] is False
    assert state["risk_capital_evidence_reasons"] == [
        "legacy_realized_pnl_trade_date_missing"
    ]


def test_live_realized_pnl_rollover_keeps_incomplete_prior_day_blocked():
    state = auto_trade.ensure_live_realized_pnl_state(
        {
            "configured_risk_capital": 1_000_000.0,
            "realized_pnl_trade_date": "2026-07-13",
            "realized_pnl_today": -500.0,
            "risk_capital_pnl_today": 0.0,
            "realized_pnl_evidence_complete": False,
            "risk_capital_evidence_complete": False,
        },
        pd.Timestamp("2026-07-14 08:00:00", tz="Asia/Tokyo"),
    )

    assert state["configured_risk_capital"] == 1_000_000.0
    assert state["realized_pnl_today"] == 0.0
    assert state["realized_pnl_evidence_complete"] is True
    assert state["risk_capital_evidence_complete"] is False
    assert "prior_day_risk_capital_unsettled:2026-07-13" in state[
        "risk_capital_evidence_reasons"
    ]
    assert (
        auto_trade._realized_pnl_evidence_allows_entry(state, is_sim=False)
        is False
    )


def test_live_account_equity_reserves_tax_on_profit_and_keeps_full_loss():
    account = {
        "configured_risk_capital": 1_000_000.0,
        "risk_capital_pnl_today": 100.0,
    }
    profit_position = {
        "buy_price": 100.0,
        "current_price": 110.0,
        "shares": 100,
    }
    expected_profit_equity = (
        1_000_100.0
        + auto_trade._conservative_risk_capital_delta(1_000.0)
    )
    assert auto_trade._resolve_account_equity(
        account,
        [profit_position],
        is_sim=False,
    ) == pytest.approx(expected_profit_equity)

    loss_position = dict(profit_position, current_price=90.0)
    assert auto_trade._resolve_account_equity(
        account,
        [loss_position],
        is_sim=False,
    ) == 999_100.0
    assert auto_trade._resolve_account_equity(
        {"configured_risk_capital": 0.0, "risk_capital_pnl_today": 0.0},
        [],
        is_sim=False,
    ) == 0.0


def test_apply_live_realized_pnl_uses_execution_net_and_fails_closed_without_costs():
    account = {"realized_pnl_today": 100.0}
    complete = {
        "trade_id": "1000|entry",
        "filled_shares": 100,
        "actual_cost_evidence_complete": True,
        "observed_execution_net_pnl": 980.5,
    }
    auto_trade._apply_live_realized_pnl(account, complete)
    assert account["realized_pnl_today"] == 1080.5
    assert account["realized_pnl_evidence_complete"] is True
    assert account["risk_capital_pnl_today"] == round(
        980.5 * (1.0 - auto_trade.TAX_RATE),
        4,
    )
    assert account["risk_capital_evidence_complete"] is True

    incomplete = {
        "trade_id": "2000|entry",
        "filled_shares": 100,
        "actual_cost_evidence_complete": False,
        "actual_cost_evidence_reason": "position_expenses_missing",
        "observed_execution_net_pnl": None,
    }
    auto_trade._apply_live_realized_pnl(account, incomplete)
    assert account["realized_pnl_today"] == 1080.5
    assert account["realized_pnl_evidence_complete"] is False
    assert account["realized_pnl_unresolved_exit_count"] == 1
    assert account["realized_pnl_evidence_reasons"] == ["2000|entry:position_expenses_missing"]
    assert account["risk_capital_evidence_complete"] is False
    assert account["risk_capital_evidence_reasons"] == [
        "2000|entry:position_expenses_missing"
    ]
    assert auto_trade._realized_pnl_evidence_allows_entry(account, is_sim=False) is False
    account["realized_pnl_evidence_complete"] = True
    account["risk_capital_evidence_complete"] = True
    assert auto_trade._realized_pnl_evidence_allows_entry(account, is_sim=False) is True
    account["realized_pnl_evidence_complete"] = False
    assert auto_trade._realized_pnl_evidence_allows_entry(account, is_sim=True) is True


def _managed_position_for_stop_reconcile():
    return {
        "code": "1000",
        "name": "Foo",
        "ownership": "MANAGED_BY_BOT",
        "shares": 100,
        "buy_price": 100.0,
        "buy_time": "2026-07-13 09:35:00",
        "buy_atr": 2.0,
        "entry_stop_price": 95.0,
        "entry_target_price": 110.0,
        "post_entry_high": 103.0,
        "post_entry_low": 94.0,
        "execution_id": "ENTRY-EX-1",
        "execution_ids": ("ENTRY-EX-1",),
        "entry_order_filled_qty": 100,
        "entry_commission": 10.0,
        "entry_commission_tax": 1.0,
        "entry_execution_costs_complete": True,
        "broker_position_expenses": 3.0,
        "broker_position_commission": 10.0,
        "broker_position_commission_tax": 1.0,
        "decision_snapshot_id": "snapshot-1",
        "protective_stop_order_id": "STOP-1",
        "protective_stop_status": "armed",
    }


def _filled_stop_order_details(*, execution_id="STOP-EX-1", qty=100):
    detail = {
        "SeqNum": 1,
        "RecType": 8,
        "State": 5,
        "Qty": qty,
        "Price": 94.0,
        "Commission": 5.0,
        "CommissionTax": 0.5,
    }
    if execution_id is not None:
        detail["ExecutionID"] = execution_id
    return {
        "ID": "STOP-1",
        "State": 5,
        "OrderQty": 100,
        "CumQty": qty,
        "Details": [detail],
    }


def test_reconcile_disappeared_protective_stop_records_actual_fill_and_flattens():
    position = _managed_position_for_stop_reconcile()
    captured = {}

    class _Broker:
        def get_order_details(self, order_id):
            assert order_id == "STOP-1"
            return _filled_stop_order_details()

        def log_trade(self, row):
            captured["trade"] = row

    with patch("auto_trade.safe_read_csv", return_value=pd.DataFrame()), patch(
        "auto_trade.append_order_journal"
    ) as append_journal, patch(
        "auto_trade.append_daytrade_exit_log"
    ) as append_exit:
        portfolio, account, evidence = (
            auto_trade.reconcile_disappeared_protective_stop_positions(
                previous_portfolio=[position],
                broker_portfolio=[],
                broker=_Broker(),
                account={"realized_pnl_today": 0.0},
                event_time=pd.Timestamp("2026-07-13 10:00:00", tz="Asia/Tokyo"),
            )
        )

    assert portfolio == []
    assert account["realized_pnl_today"] == -619.5
    assert account["realized_pnl_evidence_complete"] is True
    assert evidence == [{
        "status": "reconciled",
        "decision_snapshot_id": "snapshot-1",
        "stop_order_id": "STOP-1",
        "execution_ids": ("STOP-EX-1",),
        "code": "1000",
        "filled_shares": 100,
        "fill_price": 94.0,
        "remaining_shares": 0,
    }]
    journal_row = append_journal.call_args.args[0]
    assert journal_row["event"] == "FILLED"
    assert journal_row["order_id"] == "STOP-1"
    assert journal_row["execution_ids"] == ("STOP-EX-1",)
    exit_row = append_exit.call_args.args[0]
    assert journal_row["order_ids"] == ("STOP-1",)
    assert journal_row["side"] == "1"
    assert journal_row["qty"] == 100
    assert journal_row["execution_evidence_schema_version"] == 1
    assert journal_row["aggregate_execution"] is True
    assert journal_row["requested_qty"] == 100
    assert journal_row["average_fill_price"] == 94.0
    assert journal_row["remaining_qty"] == 0
    assert exit_row["decision_snapshot_id"] == "snapshot-1"
    assert exit_row["exit_reason"] == "protective_stop_fill"
    assert exit_row["exit_order_id"] == "STOP-1"
    assert exit_row["exit_execution_ids"] == ("STOP-EX-1",)
    assert exit_row["remaining_shares"] == 0
    assert captured["trade"]["decision_snapshot_id"] == "snapshot-1"


def test_reconcile_disappeared_protective_stop_keeps_unresolved_ghost_on_missing_execution_id():
    position = _managed_position_for_stop_reconcile()

    class _Broker:
        def get_order_details(self, order_id):
            return _filled_stop_order_details(execution_id=None)

    with patch("auto_trade.safe_read_csv", return_value=pd.DataFrame()), patch(
        "auto_trade.append_order_journal"
    ) as append_journal, patch(
        "auto_trade.append_daytrade_exit_log"
    ) as append_exit:
        portfolio, account, evidence = (
            auto_trade.reconcile_disappeared_protective_stop_positions(
                previous_portfolio=[position],
                broker_portfolio=[],
                broker=_Broker(),
                account={"realized_pnl_today": 0.0},
            )
        )

    assert len(portfolio) == 1
    assert portfolio[0]["exit_order_unresolved"] is True
    assert portfolio[0]["protective_stop_reconcile_unresolved"] is True
    assert portfolio[0]["exit_order_unresolved_reason"] == "stop_execution_id_missing"
    assert account["realized_pnl_today"] == 0.0
    assert evidence[0]["status"] == "unresolved"
    assert evidence[0]["reason"] == "stop_execution_id_missing"
    append_journal.assert_not_called()
    append_exit.assert_not_called()


def test_reconcile_disappeared_protective_stop_is_idempotent_when_exit_already_exists():
    position = _managed_position_for_stop_reconcile()
    existing = pd.DataFrame([
        {
            "decision_snapshot_id": "snapshot-1",
            "exit_order_id": "STOP-1",
            "remaining_shares": 0,
        }
    ])

    class _Broker:
        def get_order_details(self, order_id):
            raise AssertionError("already reconciled stop must not query order details")

    with patch("auto_trade.safe_read_csv", return_value=existing), patch(
        "auto_trade.append_order_journal"
    ) as append_journal, patch(
        "auto_trade.append_daytrade_exit_log"
    ) as append_exit:
        portfolio, account, evidence = (
            auto_trade.reconcile_disappeared_protective_stop_positions(
                previous_portfolio=[position],
                broker_portfolio=[],
                broker=_Broker(),
                account={"realized_pnl_today": -600.0},
            )
        )

    assert portfolio == []
    assert account["realized_pnl_today"] == -600.0
    assert evidence[0]["status"] == "already_reconciled"
    append_journal.assert_not_called()
    append_exit.assert_not_called()
