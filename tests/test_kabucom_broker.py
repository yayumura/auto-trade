import unittest
from unittest.mock import patch
import os
import pandas as pd

from core.kabucom_broker import KabucomBroker
from core.kabu_launcher import _wait_for_api_server
from core.kabucom_order_state import (
    OrderProcessState,
    OrderTerminalReason,
    SubmissionStatus,
    classify_submission_response,
    parse_kabucom_order,
)
from core.kabucom_quote import parse_board_quote
from core.sim_broker import SimulationBroker


class _FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, headers=None, **kwargs):
        self.calls.append({
            "method": method,
            "url": url,
            "headers": headers,
            "kwargs": kwargs,
        })
        if self.responses:
            response = self.responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response
        return _FakeResponse(500, text="unexpected request")


def _make_broker(session):
    broker = KabucomBroker.__new__(KabucomBroker)
    broker.is_production = False
    broker.port = 18081
    broker.base_url = "http://localhost:18081/kabusapi"
    broker.password = "test-password"
    broker.token = "token"
    broker._auth_lock = None
    broker.session = session
    broker.request_count = 0
    broker.last_reset_time = 0
    return broker


class TestKabucomBroker(unittest.TestCase):
    def test_parse_kabucom_order_handles_active_partial_terminal_and_unknown_states(self):
        active = parse_kabucom_order({
            "OrderId": "ORDER-A",
            "State": 3,
            "OrderQty": 100,
            "CumQty": 0,
            "Details": [
                {"RecType": 4, "State": 3, "Qty": 100, "Price": 1000, "ExecutionID": "EX-A"},
            ],
        })
        self.assertEqual(active.process_state, OrderProcessState.ACTIVE)
        self.assertEqual(active.terminal_reason, None)
        self.assertEqual(active.working_qty, 100)
        self.assertFalse(active.has_partial_fill)

        partial = parse_kabucom_order({
            "OrderId": "ORDER-P",
            "State": 3,
            "OrderQty": 100,
            "CumQty": 40,
            "Details": [
                {"RecType": 8, "State": 3, "Qty": 25, "Price": 1000, "ExecutionID": "EX-1"},
                {"RecType": 8, "State": 3, "Qty": 15, "Price": 1010, "ExecutionID": "EX-2"},
            ],
        })
        self.assertEqual(partial.process_state, OrderProcessState.ACTIVE)
        self.assertEqual(partial.cumulative_qty, 40)
        self.assertEqual(partial.working_qty, 60)
        self.assertTrue(partial.has_partial_fill)
        self.assertEqual(partial.execution_ids, ("EX-1", "EX-2"))
        self.assertAlmostEqual(partial.average_fill_price, (25 * 1000 + 15 * 1010) / 40)

        filled = parse_kabucom_order({
            "OrderId": "ORDER-F",
            "State": 5,
            "OrderQty": 100,
            "CumQty": 100,
            "Details": [
                {"RecType": 8, "State": 5, "Qty": 60, "Price": 1000, "ExecutionID": "EX-3"},
                {"RecType": 8, "State": 5, "Qty": 40, "Price": 1005, "ExecutionID": "EX-4"},
            ],
        })
        self.assertEqual(filled.process_state, OrderProcessState.TERMINAL)
        self.assertEqual(filled.terminal_reason, OrderTerminalReason.FILLED)
        self.assertEqual(filled.working_qty, 0)
        self.assertTrue(filled.is_consistent)

        cancelled = parse_kabucom_order({
            "OrderId": "ORDER-C",
            "State": 5,
            "OrderQty": 100,
            "CumQty": 40,
            "Details": [
                {"RecType": 8, "State": 3, "Qty": 40, "Price": 999, "ExecutionID": "EX-5"},
                {"RecType": 6, "State": 5, "Qty": 60, "Price": 0, "ExecutionID": "EX-6"},
            ],
        })
        self.assertEqual(cancelled.process_state, OrderProcessState.TERMINAL)
        self.assertEqual(cancelled.terminal_reason, OrderTerminalReason.CANCELLED)
        self.assertEqual(cancelled.cumulative_qty, 40)
        self.assertEqual(cancelled.working_qty, 0)
        self.assertTrue(cancelled.has_partial_fill)

        unknown = parse_kabucom_order({
            "OrderId": "ORDER-U",
            "State": 10,
            "OrderQty": 100,
            "CumQty": 0,
            "Details": [
                {"RecType": 4, "State": 10, "Qty": 100, "Price": 1000, "ExecutionID": "EX-7"},
            ],
        })
        self.assertEqual(unknown.process_state, OrderProcessState.UNKNOWN)
        self.assertIsNone(unknown.terminal_reason)

    def test_parse_board_quote_maps_buy_sell_and_rejects_inverted_and_special_quotes(self):
        quote = parse_board_quote(
            "1234",
            {
                "CurrentPrice": 1000,
                "BidPrice": 1001,
                "AskPrice": 1000,
                "BidQty": 200,
                "AskQty": 150,
                "CurrentPriceStatus": 0,
                "QuoteTime": "2026-04-21T09:01:00",
                "CurrentPriceTime": "2026-04-21T09:01:00",
            },
        )
        self.assertTrue(quote.is_valid)
        self.assertEqual(quote.best_sell_price, 1001.0)
        self.assertEqual(quote.best_buy_price, 1000.0)
        self.assertEqual(quote.best_sell_qty, 200)
        self.assertEqual(quote.best_buy_qty, 150)

        inverted = parse_board_quote(
            "1234",
            {
                "CurrentPrice": 1000,
                "BidPrice": 1000,
                "AskPrice": 1001,
                "CurrentPriceStatus": 0,
            },
        )
        self.assertFalse(inverted.is_valid)
        self.assertEqual(inverted.rejection_reason, "inverted_spread")

        special = parse_board_quote(
            "1234",
            {
                "CurrentPrice": 1000,
                "BidPrice": 1001,
                "AskPrice": 1000,
                "CurrentPriceStatus": 3,
            },
        )
        self.assertFalse(special.is_valid)
        self.assertEqual(special.rejection_reason, "special_quote_status_3")

    def test_classify_submission_response_distinguishes_accepted_rejected_and_unknown(self):
        accepted = classify_submission_response(
            intent_id="intent-1",
            symbol="1234",
            side="2",
            qty=100,
            price=1000.0,
            response=_FakeResponse(200, {"Result": 0, "OrderId": "ORDER-1"}),
        )
        self.assertEqual(accepted.status, SubmissionStatus.ACCEPTED)
        self.assertEqual(accepted.broker_order_id, "ORDER-1")

        missing_order_id = classify_submission_response(
            intent_id="intent-2",
            symbol="1234",
            side="2",
            qty=100,
            price=1000.0,
            response=_FakeResponse(200, {"Result": 0}),
        )
        self.assertEqual(missing_order_id.status, SubmissionStatus.UNKNOWN)

        cancel_accept = classify_submission_response(
            intent_id="intent-3",
            symbol="1234",
            side="1",
            qty=0,
            price=None,
            response=_FakeResponse(200, {"Result": 0}),
            allow_missing_order_id=True,
        )
        self.assertEqual(cancel_accept.status, SubmissionStatus.ACCEPTED)

        rejected = classify_submission_response(
            intent_id="intent-4",
            symbol="1234",
            side="2",
            qty=100,
            price=1000.0,
            response=_FakeResponse(200, {"Result": 1, "OrderId": "ORDER-X"}),
        )
        self.assertEqual(rejected.status, SubmissionStatus.REJECTED)

        transient = classify_submission_response(
            intent_id="intent-5",
            symbol="1234",
            side="2",
            qty=100,
            price=1000.0,
            response=_FakeResponse(500, text="server error"),
        )
        self.assertEqual(transient.status, SubmissionStatus.UNKNOWN)

    def test_api_request_does_not_retry_post_on_server_error(self):
        session = _FakeSession([_FakeResponse(500, text="server error")])
        broker = _make_broker(session)

        response = broker._api_request("POST", "sendorder", json={"foo": "bar"})

        self.assertEqual(len(session.calls), 1)
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 500)

    def test_execute_market_order_uses_tick_normalization_and_float_price(self):
        captured = {}

        def fake_api_request(method, endpoint, **kwargs):
            captured["method"] = method
            captured["endpoint"] = endpoint
            captured["json"] = kwargs["json"]
            return _FakeResponse(200, {"Result": 0, "OrderId": "ORDER-1"})

        broker = _make_broker(_FakeSession([]))
        broker._api_request = fake_api_request

        with patch.dict(os.environ, {"KABUCOM_ORDER_EXCHANGE": "9"}):
            order_id = broker.execute_market_order("1234", 100, side="2", price=1234.2)

        self.assertEqual(order_id, "ORDER-1")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["endpoint"], "sendorder")
        self.assertIsInstance(captured["json"]["Price"], float)
        self.assertEqual(captured["json"]["Price"], 1235.0)
        self.assertEqual(captured["json"]["MarginTradeType"], 3)
        self.assertEqual(captured["json"]["DelivType"], 0)
        self.assertEqual(captured["json"]["Exchange"], 9)

    def test_execute_market_order_uses_market_order_front_type_for_zero_price(self):
        captured = {}

        def fake_api_request(method, endpoint, **kwargs):
            captured["json"] = kwargs["json"]
            return _FakeResponse(200, {"Result": 0, "OrderId": "ORDER-0"})

        broker = _make_broker(_FakeSession([]))
        broker._api_request = fake_api_request

        order_id = broker.execute_market_order("1234", 100, side="2", price=0)

        self.assertEqual(order_id, "ORDER-0")
        self.assertEqual(captured["json"]["FrontOrderType"], 10)
        self.assertEqual(captured["json"]["Price"], 0)

    def test_execute_market_order_sell_side_uses_close_positions_and_daytrade_margin(self):
        captured = {}

        def fake_api_request(method, endpoint, **kwargs):
            captured["json"] = kwargs["json"]
            return _FakeResponse(200, {"Result": 0, "OrderId": "ORDER-SELL"})

        broker = _make_broker(_FakeSession([]))
        broker._api_request = fake_api_request

        order_id = broker.execute_market_order(
            "1234",
            100,
            side="1",
            price=1234.2,
            close_positions=[{"HoldID": "HOLD-1", "Qty": 100}],
            exchange=1,
            margin_trade_type=3,
        )

        self.assertEqual(order_id, "ORDER-SELL")
        self.assertEqual(captured["json"]["CashMargin"], 3)
        self.assertEqual(captured["json"]["MarginTradeType"], 3)
        self.assertEqual(captured["json"]["DelivType"], 2)
        self.assertEqual(captured["json"]["Exchange"], 1)
        self.assertIn("ClosePositions", captured["json"])

    def test_execute_market_order_aborts_without_close_positions_on_sell_side(self):
        broker = _make_broker(_FakeSession([]))
        broker._api_request = lambda *args, **kwargs: _FakeResponse(200, {"Result": 0, "OrderId": "ORDER-FAIL"})

        self.assertIsNone(broker.execute_market_order("1234", 100, side="1", price=1234.2))

    def test_execute_market_order_writes_order_journal(self):
        journal_events = []

        def fake_api_request(method, endpoint, **kwargs):
            return _FakeResponse(200, {"Result": 0, "OrderId": "ORDER-1"})

        def fake_append(event, path=None):
            journal_events.append(event)

        broker = _make_broker(_FakeSession([]))
        broker._api_request = fake_api_request

        with patch("core.kabucom_broker.append_order_journal", side_effect=fake_append):
            order_id = broker.execute_market_order("1234", 100, side="2", price=1234.2)

        self.assertEqual(order_id, "ORDER-1")
        self.assertGreaterEqual(len(journal_events), 2)
        self.assertEqual(journal_events[0]["event"], "PLANNED")
        self.assertEqual(journal_events[1]["event"], "ACCEPTED")

    def test_execute_stop_order_normalizes_trigger_price(self):
        captured = {}

        def fake_api_request(method, endpoint, **kwargs):
            captured["method"] = method
            captured["endpoint"] = endpoint
            captured["json"] = kwargs["json"]
            return _FakeResponse(200, {"Result": 0, "OrderId": "STOP-1"})

        broker = _make_broker(_FakeSession([]))
        broker._api_request = fake_api_request
        broker.get_positions = lambda: [
            {
                "hold_id": "HOLD-1",
                "exchange": 1,
                "margin_trade_type": 3,
                "available_qty": 100,
                "code": "1234",
            }
        ]

        order_id = broker.execute_stop_order("1234", 100, side="1", trigger_price=3001.2, hold_id="HOLD-1")

        self.assertEqual(order_id, "STOP-1")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["endpoint"], "sendorder")
        self.assertEqual(captured["json"]["FrontOrderType"], 30)
        self.assertEqual(captured["json"]["CashMargin"], 3)
        self.assertEqual(captured["json"]["MarginTradeType"], 3)
        self.assertEqual(captured["json"]["DelivType"], 2)
        self.assertEqual(captured["json"]["ReverseLimitOrder"]["TriggerSec"], 1)
        self.assertEqual(captured["json"]["ReverseLimitOrder"]["UnderOver"], 1)
        self.assertEqual(captured["json"]["ReverseLimitOrder"]["AfterHitOrderType"], 1)
        self.assertEqual(captured["json"]["ReverseLimitOrder"]["AfterHitPrice"], 0)
        self.assertIsInstance(captured["json"]["ReverseLimitOrder"]["TriggerPrice"], float)
        self.assertEqual(captured["json"]["ReverseLimitOrder"]["TriggerPrice"], 3000.0)
        self.assertEqual(captured["json"]["Exchange"], 1)
        self.assertIn("ClosePositions", captured["json"])

    def test_execute_stop_order_uses_buy_side_reverse_limit_direction(self):
        captured = {}

        def fake_api_request(method, endpoint, **kwargs):
            captured["json"] = kwargs["json"]
            return _FakeResponse(200, {"Result": 0, "OrderId": "STOP-2"})

        broker = _make_broker(_FakeSession([]))
        broker._api_request = fake_api_request

        order_id = broker.execute_stop_order("1234", 100, side="2", trigger_price=3001.2)

        self.assertEqual(order_id, "STOP-2")
        self.assertEqual(captured["json"]["ReverseLimitOrder"]["UnderOver"], 2)

    def test_execute_stop_order_aborts_without_hold_id_on_sell_side(self):
        broker = _make_broker(_FakeSession([]))
        broker._api_request = lambda *args, **kwargs: _FakeResponse(200, {"Result": 0, "OrderId": "STOP-FAIL"})

        self.assertIsNone(broker.execute_stop_order("1234", 100, side="1", trigger_price=3001.2))

    def test_execute_chase_order_force_branch_passes_close_positions_for_sell_side(self):
        call_args = []

        broker = _make_broker(_FakeSession([]))
        broker.get_board_data = lambda symbols: {
            "1234": {
                "price": 1000.0,
                "best_sell_price": 999.0,
                "best_buy_price": 1001.0,
                "upper_limit": 2000.0,
                "lower_limit": 500.0,
            }
        }
        broker.get_positions = lambda: [
            {"code": "1234", "hold_id": "HOLD-1", "exchange": 1, "margin_trade_type": 3, "leaves_qty": 60, "hold_qty": 0, "buy_time": "2026-04-21 09:00:00", "execution_id": "EX-1"},
            {"code": "1234", "hold_id": "HOLD-2", "exchange": 1, "margin_trade_type": 3, "leaves_qty": 40, "hold_qty": 0, "buy_time": "2026-04-21 09:01:00", "execution_id": "EX-2"},
        ]
        broker.cancel_order = lambda order_id: True

        def fake_execute_market_order(code, shares, side, price=0, close_positions=None, exchange=None, margin_trade_type=None):
            call_args.append({
                "code": code,
                "shares": shares,
                "side": side,
                "price": price,
                "close_positions": close_positions,
                "exchange": exchange,
                "margin_trade_type": margin_trade_type,
            })
            return None if len(call_args) == 1 else "ORDER-FORCE"

        broker.execute_market_order = fake_execute_market_order
        broker.wait_for_execution = lambda *args, **kwargs: {
            "State": 5,
            "OrderQty": 100,
            "CumQty": 100,
            "Details": [
                {"RecType": 8, "State": 5, "Qty": 100, "Price": 1000.0, "ExecutionID": "EX-100"},
            ],
        }

        result = broker.execute_chase_order("1234", 100, side="1", atr=10.0)

        self.assertEqual(len(call_args), 2)
        self.assertEqual(
            call_args[0]["close_positions"],
            [
                {"HoldID": "HOLD-1", "Qty": 60},
                {"HoldID": "HOLD-2", "Qty": 40},
            ],
        )
        self.assertEqual(call_args[0]["exchange"], 1)
        self.assertEqual(call_args[0]["margin_trade_type"], 3)
        self.assertEqual(result["Qty"], 100)
        self.assertEqual(result["filled_qty"], 100)
        self.assertEqual(result["process_state"], OrderProcessState.TERMINAL.value)
        self.assertEqual(result["terminal_reason"], OrderTerminalReason.FILLED.value)

    def test_get_account_balance_live_separates_wallet_cash_and_margin(self):
        responses = iter([
            _FakeResponse(200, {"StockAccountWallet": 123456.0}),
            _FakeResponse(200, {"MarginAccountWallet": 654321.0}),
        ])

        def fake_api_request(method, endpoint, **kwargs):
            return next(responses)

        broker = _make_broker(_FakeSession([]))
        broker.is_production = True
        broker._api_request = fake_api_request

        snapshot = broker.get_account_balance()

        self.assertEqual(snapshot["stock_buying_power"], 123456.0)
        self.assertEqual(snapshot["margin_buying_power"], 654321.0)
        self.assertFalse(snapshot["wallet_snapshot_incomplete"])

    def test_get_positions_live_marks_managed_by_bot_using_execution_id(self):
        broker = _make_broker(_FakeSession([]))
        broker.is_production = True
        broker._api_request = lambda *args, **kwargs: _FakeResponse(200, [
            {
                "Symbol": "1234",
                "SymbolName": "Foo",
                "CurrentPrice": 1000.0,
                "LeavesQty": 100,
                "HoldQty": 0,
                "Price": 900.0,
                "ExecutionID": "EX-1",
                "Exchange": 1,
                "MarginTradeType": 3,
            }
        ])

        with patch("core.kabucom_broker.safe_read_csv", return_value=pd.DataFrame([
            {"code": "1234", "execution_id": "EX-1", "buy_time": "2026-04-21 09:00:00", "highest_price": 1000.0, "partial_sold": False}
        ])):
            positions = broker.get_positions()

        self.assertEqual(positions[0]["ownership"], "MANAGED_BY_BOT")
        self.assertEqual(positions[0]["ownership_reason"], "matched_execution_id")

    def test_cancel_order_writes_order_journal(self):
        journal_events = []

        responses = iter([
            _FakeResponse(200, {"Result": 0, "OrderId": "ORDER-1"}),
            _FakeResponse(200, [
                {
                    "OrderId": "ORDER-1",
                    "State": 5,
                    "OrderQty": 100,
                    "CumQty": 100,
                    "Details": [
                        {"RecType": 8, "State": 5, "Qty": 100, "Price": 1000.0, "ExecutionID": "EX-1"},
                    ],
                }
            ]),
        ])

        def fake_api_request(method, endpoint, **kwargs):
            return next(responses)

        def fake_append(event, path=None):
            journal_events.append(event)

        broker = _make_broker(_FakeSession([]))
        broker._api_request = fake_api_request

        with patch("core.kabucom_broker.append_order_journal", side_effect=fake_append):
            self.assertTrue(broker.cancel_order("ORDER-1"))

        self.assertGreaterEqual(len(journal_events), 2)
        self.assertEqual(journal_events[0]["event"], "CANCEL_REQUESTED")
        self.assertEqual(journal_events[1]["event"], "CANCELLED")

    def test_get_active_orders_flags_unknown_orders_and_filters_terminal_orders(self):
        broker = _make_broker(_FakeSession([]))
        broker._api_request = lambda *args, **kwargs: _FakeResponse(200, [
            {
                "OrderId": "ACTIVE-1",
                "State": 3,
                "OrderQty": 100,
                "CumQty": 0,
                "Details": [
                    {"RecType": 4, "State": 3, "Qty": 100, "Price": 1000, "ExecutionID": "EX-1"},
                ],
            },
            {
                "OrderId": "UNKNOWN-1",
                "State": 10,
                "OrderQty": 100,
                "CumQty": 0,
                "Details": [
                    {"RecType": 4, "State": 10, "Qty": 100, "Price": 1000, "ExecutionID": "EX-2"},
                ],
            },
            {
                "OrderId": "DONE-1",
                "State": 5,
                "OrderQty": 100,
                "CumQty": 100,
                "Details": [
                    {"RecType": 8, "State": 5, "Qty": 100, "Price": 1000, "ExecutionID": "EX-3"},
                ],
            },
        ])

        active_orders = broker.get_active_orders()
        self.assertIsNotNone(active_orders)
        self.assertEqual(len(active_orders["orders"]), 1)
        self.assertEqual(active_orders["orders"][0]["OrderId"], "ACTIVE-1")
        self.assertTrue(active_orders["has_unknown"])
        self.assertIn("UNKNOWN-1", active_orders["unresolved_order_ids"])

    def test_get_active_orders_returns_none_when_request_layer_fails(self):
        broker = _make_broker(_FakeSession([]))
        broker._api_request = lambda *args, **kwargs: None

        self.assertIsNone(broker.get_active_orders())

    def test_api_health_accepts_authenticated_failure_responses(self):
        with patch("core.kabu_launcher.requests.get", return_value=_FakeResponse(401)) as mocked_get, \
             patch("core.kabu_launcher.time.sleep", return_value=None), \
             patch("core.kabu_launcher.time.time", side_effect=[0.0, 0.01, 0.02, 0.2]):
            self.assertTrue(_wait_for_api_server(timeout_sec=0.1, silent=True))

        self.assertIn("/kabusapi/board/7203@1", mocked_get.call_args.args[0])

    def test_log_trade_appends_rows_instead_of_overwriting_history(self):
        broker = _make_broker(_FakeSession([]))
        trade_record = {"code": "1234", "shares": 100, "pnl": 123.0}

        with patch("core.kabucom_broker.append_csv_rows") as mocked_append:
            broker.log_trade(trade_record)

        mocked_append.assert_called_once()

    def test_simulation_broker_log_trade_appends_rows(self):
        broker = SimulationBroker()
        trade_record = {"code": "1234", "shares": 100, "pnl": 123.0}

        with patch("core.sim_broker.append_csv_rows") as mocked_append:
            broker.log_trade(trade_record)

        mocked_append.assert_called_once()


if __name__ == "__main__":
    unittest.main()
