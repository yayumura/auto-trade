import json
import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from unittest.mock import patch
from types import SimpleNamespace

import auto_trade
from auto_trade import (
    build_daytrade_position_record,
    build_daytrade_watch_plan,
    close_daytrade_positions_by_signal,
    compute_daytrade_snapshot,
    is_inverse_only_candidate_set,
    sync_daytrade_registry,
)
from core.logic import (
    RealtimeBuffer,
    cancel_linked_protective_stop_before_exit,
    resolve_daytrade_live_exit_decision,
)
from core.kabucom_order_state import CancelResult, CancelStatus, CancelTerminalStatus
from core.kabucom_order_state import StockOrderAction


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
    assert broker.registered == [["1000"]]
    assert broker.unregistered == [["9999"]]


def test_arm_daytrade_protective_stop_matches_live_position_and_records_order_id():
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
    assert updated_account["realized_pnl_today"] > 0


def test_close_daytrade_positions_by_signal_marks_partial_remainder_unresolved_when_rearm_fails():
    position = {
        "code": "1000",
        "name": "Foo",
        "setup_type": "primary",
        "buy_time": "2026-04-21 09:03:00",
        "buy_price": 100.0,
        "highest_price": 105.0,
        "lowest_price": 99.2,
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
    assert updated_account["realized_pnl_today"] > 0


def test_close_daytrade_positions_by_signal_skips_exit_when_protective_stop_cancel_is_unconfirmed():
    position = {
        "code": "1000",
        "name": "Foo",
        "setup_type": "primary",
        "buy_time": "2026-04-21 09:03:00",
        "buy_price": 100.0,
        "highest_price": 105.0,
        "lowest_price": 99.2,
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
        open_price=100.0,
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
    assert merged["daytrade_week_start_equity"] == 1_010_000.0
    assert merged["month_start_equity"] == 1_100_000.0
    assert merged["stock_buying_power"] == 333.0
    assert merged["margin_buying_power"] == 222.0
    assert merged["wallet_snapshot_incomplete"] is True
    assert merged["wallet_cash_ok"] is True
    assert merged["wallet_margin_ok"] is False
