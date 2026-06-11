import unittest
from unittest.mock import patch

from core.kabucom_broker import KabucomBroker
from core.kabu_launcher import _wait_for_api_server
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

        order_id = broker.execute_market_order("1234", 100, side="2", price=1234.2)

        self.assertEqual(order_id, "ORDER-1")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["endpoint"], "sendorder")
        self.assertIsInstance(captured["json"]["Price"], float)
        self.assertEqual(captured["json"]["Price"], 1235.0)
        self.assertEqual(captured["json"]["MarginTradeType"], 3)
        self.assertEqual(captured["json"]["DelivType"], 0)

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
        )

        self.assertEqual(order_id, "ORDER-SELL")
        self.assertEqual(captured["json"]["CashMargin"], 3)
        self.assertEqual(captured["json"]["MarginTradeType"], 3)
        self.assertEqual(captured["json"]["DelivType"], 2)
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
                "bid": 999.0,
                "ask": 1001.0,
                "upper_limit": 2000.0,
                "lower_limit": 500.0,
            }
        }
        broker.get_positions = lambda: [{"code": "1234", "hold_id": "HOLD-1"}]
        broker.cancel_order = lambda order_id: True
        broker.get_order_details = lambda order_id: {"State": 10}

        def fake_execute_market_order(code, shares, side, price=0, close_positions=None):
            call_args.append({
                "code": code,
                "shares": shares,
                "side": side,
                "price": price,
                "close_positions": close_positions,
            })
            return None if len(call_args) == 1 else "ORDER-FORCE"

        broker.execute_market_order = fake_execute_market_order
        broker.wait_for_execution = lambda *args, **kwargs: None

        result = broker.execute_chase_order("1234", 100, side="1", atr=10.0)

        self.assertEqual(result["Qty"], 0)
        self.assertGreaterEqual(len(call_args), 2)
        self.assertIsNotNone(call_args[-1]["close_positions"])
        self.assertEqual(call_args[-1]["close_positions"][0]["HoldID"], "HOLD-1")

    def test_cancel_order_writes_order_journal(self):
        journal_events = []

        def fake_api_request(method, endpoint, **kwargs):
            return _FakeResponse(200, {"Result": 0})

        def fake_append(event, path=None):
            journal_events.append(event)

        broker = _make_broker(_FakeSession([]))
        broker._api_request = fake_api_request

        with patch("core.kabucom_broker.append_order_journal", side_effect=fake_append):
            self.assertTrue(broker.cancel_order("ORDER-1"))

        self.assertGreaterEqual(len(journal_events), 2)
        self.assertEqual(journal_events[0]["event"], "CANCEL_REQUESTED")
        self.assertEqual(journal_events[1]["event"], "CANCELLED")

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
