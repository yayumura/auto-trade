import unittest
import json
import io
import tempfile
from dataclasses import replace
from hashlib import sha256
from unittest.mock import patch
import os
from pathlib import Path
import zipfile
import pandas as pd
from types import SimpleNamespace

from core.config import RUNTIME_LIVE_ORDER_CONFIG_HASH
from core.kabucom_broker import KabucomBroker, RequestBudgetBucket, BrokerOperationClass
from core.kabucom_broker import BrokerEndpointConfig
from core.kabucom_broker import BrokerEnvironment
from core.kabu_launcher import _wait_for_api_server, check_api_health
from core.kabucom_order_state import (
    CancelResult,
    CancelStatus,
    CancelTerminalStatus,
    classify_cancel_response,
    ExecutionWaitResult,
    OrderProcessState,
    OrderSubmissionResult,
    OrderTerminalReason,
    StockOrderAction,
    SubmissionResult,
    SubmissionStatus,
    classify_submission_response,
    parse_kabucom_order,
    resolve_stock_order_action,
    resolve_stock_order_action_context,
)
from core.kabucom_quote import parse_board_quote
from core.kabucom_contracts import TEST_CONTRACT_FIXTURE_PATH, hash_contract_fixture, load_contract_fixture
from core.jpx_calendar import get_jpx_trading_day_status
from core.live_order_gate import (
    EntryAuthorizationContext,
    evaluate_entry_authorization,
    get_kabucom_live_financial_write_gate_status,
    get_live_order_gate_status,
)
from core.live_readiness_report import build_live_readiness_report
from core.live_approval_manifest import read_git_commit_sha
from core.github_actions_artifact_source import (
    clear_live_write_attestation_artifact_source_cache,
    verify_live_write_attestation_artifact_source,
)
from core.live_write_attestation import (
    LIVE_WRITE_ATTESTATION_DIGEST_SUFFIX,
    LIVE_WRITE_ATTESTATION_TEST_COMMAND,
    compute_live_write_attestation_hash,
    build_live_write_attestation,
    read_git_remote_repository_full_name,
    write_live_write_attestation,
)
from core.live_approval_manifest import compute_live_approval_manifest_hash
from core.startup_recovery import build_startup_recovery_report
from core.order_journal import build_order_journal_replay_summary
from core.sim_broker import SimulationBroker
from scripts import build_live_write_attestation as build_live_write_attestation_script


class _FakeResponse:
    def __init__(self, status_code, payload=None, text="", headers=None, content=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text
        self.headers = headers if headers is not None else {}
        if content is None:
            content = text.encode("utf-8")
        self._content = content

    def json(self):
        return self._payload

    @property
    def content(self):
        return self._content


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

    def get(self, url, headers=None, **kwargs):
        return self.request("GET", url, headers=headers, **kwargs)


def _make_broker(session):
    os.environ.setdefault("KABUCOM_ACCOUNT_TYPE", "4")
    broker = KabucomBroker.__new__(KabucomBroker)
    broker.is_production = False
    broker.port = 18081
    broker.base_url = "http://localhost:18081/kabusapi"
    broker.password = "test-password"
    broker.order_password = "test-order-password"
    broker.token = "token"
    broker._auth_lock = None
    broker.session = session
    broker.request_count = 0
    broker.last_reset_time = 0
    return broker


def _write_live_write_attestation_artifact(
    tmpdir: str,
    *,
    runtime_config_hash: str = "sha256:runtime",
    approved_config_hash: str = "sha256:runtime",
    approval_manifest_hash: str | None = None,
    ci_run_id: str = "12345",
    test_command: str = LIVE_WRITE_ATTESTATION_TEST_COMMAND,
) -> tuple[Path, Path, object]:
    fixture = load_contract_fixture(TEST_CONTRACT_FIXTURE_PATH)
    assert isinstance(fixture, dict)
    mutated_fixture = json.loads(json.dumps(fixture))
    mutated_fixture["captured_from_kabucom_test"] = True

    fixture_path = Path(tmpdir) / "kabucom_test_contract_fixture.json"
    fixture_path.write_text(json.dumps(mutated_fixture, ensure_ascii=False, indent=2), encoding="utf-8")

    attestation = build_live_write_attestation(
        fixture_path=fixture_path,
        runtime_config_hash=runtime_config_hash,
        approved_config_hash=approved_config_hash,
        ci_run_id=ci_run_id,
        ci_run_url=f"https://github.com/yayumura/auto-trade/actions/runs/{ci_run_id}",
        test_command=test_command,
        approval_manifest_hash=approval_manifest_hash or compute_live_approval_manifest_hash(),
    )
    attestation_path = Path(tmpdir) / "live_write_attestation.json"
    write_live_write_attestation(attestation_path, attestation)
    return fixture_path, attestation_path, attestation


def _write_live_risk_review_artifact(
    tmpdir: str,
    *,
    code_commit_sha: str | None = None,
    approval_manifest_hash: str | None = None,
    runtime_config_hash: str | None = None,
    reviewer: str = "qa-operator",
) -> Path:
    review_path = Path(tmpdir) / "live_risk_review.json"
    payload = {
        "schema_version": 1,
        "status": "ready",
        "reviewed_at": "2099-01-01T00:00:00+09:00",
        "reviewer": reviewer,
        "code_commit_sha": code_commit_sha or read_git_commit_sha(),
        "approval_manifest_hash": approval_manifest_hash or compute_live_approval_manifest_hash(),
        "runtime_config_hash": runtime_config_hash or RUNTIME_LIVE_ORDER_CONFIG_HASH,
        "train_holdout_review": {"status": "ready", "summary": "train/holdout review complete"},
        "walk_forward_review": {"status": "ready", "summary": "walk-forward review complete"},
        "transaction_cost_stress": {"status": "ready", "summary": "cost stress complete"},
        "slippage_stress": {"status": "ready", "summary": "slippage stress complete"},
        "capacity_liquidity_stress": {"status": "ready", "summary": "capacity stress complete"},
        "rule_complexity_report": {"status": "ready", "summary": "rule complexity review complete"},
        "no_lookahead_audit_hash": "sha256:no-lookahead",
    }
    review_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return review_path


class TestKabucomBroker(unittest.TestCase):
    def test_broker_endpoint_config_rejects_mismatched_environment_and_port(self):
        with self.assertRaises(ValueError):
            BrokerEndpointConfig(BrokerEnvironment.LIVE, 18081).validate()

        with self.assertRaises(ValueError):
            BrokerEndpointConfig(BrokerEnvironment.TEST, 18080).validate()

        with self.assertRaises(ValueError):
            BrokerEndpointConfig(BrokerEnvironment.LIVE, 18080, "http://localhost:18081/kabusapi").validate()

    def test_authorize_operation_blocks_live_new_exposure_without_order_password(self):
        with patch("core.kabucom_broker.KABUCOM_API_PASSWORD", "api-secret"), \
            patch("core.kabucom_broker.KABUCOM_ORDER_PASSWORD", ""), \
            patch("core.kabucom_broker.TRADE_MODE", "KABUCOM_LIVE"), \
            patch("core.kabucom_broker.DEBUG_MODE", False), \
            patch(
                "core.kabucom_broker.get_live_order_gate_status",
                return_value=SimpleNamespace(
                    allowed=True,
                    reason="approval_granted",
                    runtime_config_hash="sha256:runtime",
                    approved_config_hash="sha256:runtime",
                ),
            ), \
            patch(
                "core.kabucom_broker.get_kabucom_live_financial_write_gate_status",
                return_value=SimpleNamespace(allowed=True, reason="ready"),
            ), \
            patch.object(KabucomBroker, "_authenticate", lambda self: None):
            broker = KabucomBroker(BrokerEndpointConfig.live())
            broker.token = "token"

            allowed, reason = broker._authorize_operation(BrokerOperationClass.NEW_EXPOSURE)

        self.assertFalse(allowed)
        self.assertEqual(reason, "order_password_missing")

    def test_infer_request_sent_treats_order_password_missing_as_preflight(self):
        broker = _make_broker(_FakeSession([]))
        submission = SubmissionResult(
            status=SubmissionStatus.REJECTED,
            intent_id="intent-1",
            broker_order_id=None,
            symbol="1234",
            side="2",
            qty=100,
            price=1234.2,
            http_status=None,
            rejection_reason="order_password_missing",
        )

        self.assertFalse(broker._infer_request_sent(submission))

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

    def test_parse_kabucom_order_sorts_details_by_seqnum_and_ignores_non_fill_execution_ids(self):
        parsed = parse_kabucom_order({
            "OrderId": "ORDER-S",
            "State": 3,
            "OrderQty": 40,
            "CumQty": 40,
            "Details": [
                {"SeqNum": 2, "RecType": 8, "State": 3, "Qty": 15, "Price": 1010, "ExecutionID": "EX-2"},
                {"SeqNum": 1, "RecType": 8, "State": 3, "Qty": 25, "Price": 1000, "ExecutionID": "EX-1"},
                {"SeqNum": 3, "RecType": 4, "State": 4, "Qty": 40, "Price": 1000, "ExecutionID": "IGNORE"},
            ],
        })

        self.assertEqual(parsed.execution_ids, ("EX-1", "EX-2"))
        self.assertEqual(parsed.latest_detail_rec_type, 4)
        self.assertEqual(parsed.process_state, OrderProcessState.UNKNOWN)

    def test_parse_kabucom_order_marks_state_4_terminal_detail_as_rejected(self):
        parsed = parse_kabucom_order({
            "OrderId": "ORDER-R",
            "State": 5,
            "OrderQty": 100,
            "CumQty": 0,
            "Details": [
                {"SeqNum": 1, "RecType": 4, "State": 4, "Qty": 100, "Price": 1000, "ExecutionID": "EX-1"},
            ],
        })

        self.assertEqual(parsed.process_state, OrderProcessState.TERMINAL)
        self.assertEqual(parsed.terminal_reason, OrderTerminalReason.REJECTED)
        self.assertFalse(parsed.has_partial_fill)

    def test_parse_kabucom_order_marks_duplicate_seqnum_as_unknown(self):
        parsed = parse_kabucom_order({
            "OrderId": "ORDER-D",
            "State": 3,
            "OrderQty": 40,
            "CumQty": 40,
            "Details": [
                {"SeqNum": 1, "RecType": 8, "State": 3, "Qty": 20, "Price": 1000, "ExecutionID": "EX-1"},
                {"SeqNum": 1, "RecType": 8, "State": 3, "Qty": 20, "Price": 1010, "ExecutionID": "EX-2"},
            ],
        })

        self.assertEqual(parsed.process_state, OrderProcessState.UNKNOWN)

    def test_resolve_stock_order_action_defaults_to_long_only_and_rejects_short_actions(self):
        self.assertEqual(resolve_stock_order_action("2", 2), StockOrderAction.MARGIN_NEW_LONG)
        self.assertEqual(resolve_stock_order_action("1", 3), StockOrderAction.MARGIN_CLOSE_LONG)
        with self.assertRaises(ValueError):
            resolve_stock_order_action("2", 3)
        with self.assertRaises(ValueError):
            resolve_stock_order_action("1", 2)

    def test_resolve_stock_order_action_context_maps_long_only_actions_and_rejects_short_actions(self):
        new_long = resolve_stock_order_action_context(StockOrderAction.MARGIN_NEW_LONG)
        self.assertEqual(new_long.side, "2")
        self.assertEqual(new_long.cash_margin, 2)
        self.assertEqual(new_long.deliv_type, 0)
        self.assertFalse(new_long.requires_close_positions)

        close_long = resolve_stock_order_action_context(StockOrderAction.MARGIN_CLOSE_LONG)
        self.assertEqual(close_long.side, "1")
        self.assertEqual(close_long.cash_margin, 3)
        self.assertEqual(close_long.deliv_type, 2)
        self.assertTrue(close_long.requires_close_positions)

        with self.assertRaises(ValueError):
            resolve_stock_order_action_context(StockOrderAction.MARGIN_NEW_SHORT)
        with self.assertRaises(ValueError):
            resolve_stock_order_action_context(StockOrderAction.MARGIN_CLOSE_SHORT)

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
                "BidTime": "2026-04-21T09:00:58",
                "AskTime": "2026-04-21T09:00:59",
                "OpeningPriceTime": "2026-04-21T09:00:00",
                "ReceivedAt": "2026-04-21T09:01:01",
            },
        )
        self.assertTrue(quote.is_valid)
        self.assertEqual(quote.best_sell_price, 1001.0)
        self.assertEqual(quote.best_buy_price, 1000.0)
        self.assertEqual(quote.best_sell_qty, 200)
        self.assertEqual(quote.best_buy_qty, 150)
        self.assertEqual(quote.received_at.isoformat(), "2026-04-21T09:01:01")
        self.assertEqual(quote.bid_timestamp.isoformat(), "2026-04-21T09:00:58")
        self.assertEqual(quote.ask_timestamp.isoformat(), "2026-04-21T09:00:59")
        self.assertEqual(quote.opening_price_timestamp.isoformat(), "2026-04-21T09:00:00")

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

    def test_parse_board_quote_keeps_received_at_separate_from_quote_timestamp(self):
        quote = parse_board_quote(
            "1234",
            {
                "CurrentPrice": 1000,
                "BidPrice": 1001,
                "AskPrice": 1000,
                "CurrentPriceStatus": 0,
                "ReceivedAt": "2026-04-21T09:01:01",
            },
        )
        self.assertIsNone(quote.quote_timestamp)
        self.assertEqual(quote.received_at.isoformat(), "2026-04-21T09:01:01")

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

        cancel_accept = classify_cancel_response(
            intent_id="intent-3",
            response=_FakeResponse(200, {"Result": 0}),
        )
        self.assertEqual(cancel_accept.status, SubmissionStatus.ACCEPTED)
        self.assertIsNone(cancel_accept.broker_order_id)

        long_response = classify_submission_response(
            intent_id="intent-3b",
            symbol="1234",
            side="2",
            qty=100,
            price=1000.0,
            response=_FakeResponse(200, {"Result": 0, "OrderId": "ORDER-L"}, text=("y" * 3000)),
        )
        self.assertEqual(long_response.status, SubmissionStatus.ACCEPTED)
        self.assertTrue(long_response.response_text.startswith("y"))
        self.assertTrue(long_response.response_text.endswith("...[truncated]"))
        self.assertLessEqual(len(long_response.response_text), 2062)

        secret_text = "{" + "\"Password\":\"abc123\"," + "\"Token\":\"xyz789\"}" + ("x" * 3000)
        secret_response = classify_cancel_response(
            intent_id="intent-3c",
            response=_FakeResponse(200, {"Result": 0}, text=secret_text),
        )
        self.assertEqual(secret_response.status, SubmissionStatus.ACCEPTED)
        self.assertIn("***REDACTED***", secret_response.response_text)
        self.assertLessEqual(len(secret_response.response_text), 2062)

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

    def test_live_order_gate_requires_explicit_enable_and_hash_match(self):
        blocked = get_live_order_gate_status(
            trade_mode="KABUCOM_LIVE",
            debug_mode=False,
            enable_live_order=True,
            approved_config_hash="sha256:abc",
            runtime_config_hash="sha256:def",
        )
        self.assertFalse(blocked.allowed)
        self.assertEqual(blocked.reason, "config_hash_mismatch")

        ready = get_live_order_gate_status(
            trade_mode="KABUCOM_LIVE",
            debug_mode=False,
            enable_live_order=True,
            approved_config_hash="sha256:abc",
            runtime_config_hash="sha256:abc",
        )
        self.assertTrue(ready.allowed)
        self.assertEqual(ready.reason, "ready")

        non_live = get_live_order_gate_status(
            trade_mode="SIM",
            debug_mode=False,
            enable_live_order=False,
            approved_config_hash="",
            runtime_config_hash="sha256:abc",
        )
        self.assertTrue(non_live.allowed)
        self.assertEqual(non_live.reason, "non_live_mode")

    def test_entry_authorization_blocks_live_entries_on_runtime_reconciliation_and_quote_failure(self):
        status = evaluate_entry_authorization(
            EntryAuthorizationContext(
                production_endpoint=True,
                approved_manifest_valid=False,
                reconciliation_clean=False,
                unresolved_order_count=2,
                ambiguous_position_count=1,
                wallet_snapshot_fresh=False,
                positions_snapshot_fresh=False,
                orders_snapshot_fresh=False,
                quote_fresh=False,
                registry_ready=False,
                critical_state_valid=False,
                session_allows_entry=False,
                clock_healthy=False,
                shutdown_requested=True,
            )
        )

        self.assertFalse(status.allowed)
        self.assertIn("approved_manifest_invalid", status.blocking_reasons)
        self.assertIn("reconciliation_dirty", status.blocking_reasons)
        self.assertIn("quote_stale", status.blocking_reasons)
        self.assertIn("registry_not_ready", status.blocking_reasons)
        self.assertIn("shutdown_requested", status.blocking_reasons)

    def test_entry_authorization_blocks_on_pending_orphaned_protective_stop(self):
        status = evaluate_entry_authorization(
            EntryAuthorizationContext(
                production_endpoint=True,
                approved_manifest_valid=True,
                reconciliation_clean=True,
                unresolved_order_count=0,
                ambiguous_position_count=0,
                wallet_snapshot_fresh=True,
                positions_snapshot_fresh=True,
                orders_snapshot_fresh=True,
                quote_fresh=True,
                registry_ready=True,
                critical_state_valid=True,
                session_allows_entry=True,
                clock_healthy=True,
                shutdown_requested=False,
                protective_stop_pending_count=1,
                protective_stop_orphan_count=1,
            )
        )

        self.assertFalse(status.allowed)
        self.assertIn("protective_stop_pending:1", status.blocking_reasons)
        self.assertIn("protective_stop_orphan:1", status.blocking_reasons)

    def test_entry_authorization_allows_non_production_endpoints(self):
        status = evaluate_entry_authorization(
            EntryAuthorizationContext(
                production_endpoint=False,
                approved_manifest_valid=False,
                reconciliation_clean=False,
                unresolved_order_count=3,
                ambiguous_position_count=2,
                wallet_snapshot_fresh=False,
                positions_snapshot_fresh=False,
                orders_snapshot_fresh=False,
                quote_fresh=False,
                registry_ready=False,
                critical_state_valid=False,
                session_allows_entry=False,
                clock_healthy=False,
                shutdown_requested=True,
            )
        )

        self.assertTrue(status.allowed)
        self.assertEqual(status.reason, "non_production_endpoint")

    def test_api_request_does_not_retry_post_on_server_error(self):
        session = _FakeSession([_FakeResponse(500, text="server error")])
        broker = _make_broker(session)

        response = broker._api_request("POST", "sendorder", json={"foo": "bar"})

        self.assertEqual(len(session.calls), 1)
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 500)

    def test_api_request_retries_get_on_rate_limit(self):
        session = _FakeSession([
            _FakeResponse(429, text="rate limited"),
            _FakeResponse(200, {"ok": True}),
        ])
        broker = _make_broker(session)

        with patch("core.kabucom_broker.time.sleep", return_value=None):
            response = broker._api_request("GET", "orders")

        self.assertEqual(len(session.calls), 2)
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 200)

    def test_api_request_does_not_retry_post_on_rate_limit(self):
        session = _FakeSession([_FakeResponse(429, text="rate limited")])
        broker = _make_broker(session)

        response = broker._api_request("POST", "sendorder", json={"foo": "bar"})

        self.assertEqual(len(session.calls), 1)
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 429)

    def test_live_endpoint_blocks_write_when_trade_mode_is_not_live(self):
        with patch("core.kabucom_broker.KABUCOM_API_PASSWORD", ""), \
             patch("core.kabucom_broker.TRADE_MODE", "SIM"):
            broker = KabucomBroker(BrokerEndpointConfig.live())
            broker.token = "token"
            broker._api_request = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("API should not be called"))

            submission = broker._submit_market_order("1234", 100, side="2", price=1234.2, exchange=9)

        self.assertEqual(submission.status, SubmissionStatus.REJECTED)
        self.assertEqual(submission.rejection_reason, "live_endpoint_write_blocked_by_trade_mode")
        self.assertIsNone(submission.broker_order_id)

    def test_test_endpoint_requires_kabucom_test_mode_for_write(self):
        with patch("core.kabucom_broker.KABUCOM_API_PASSWORD", ""), \
             patch("core.kabucom_broker.TRADE_MODE", "SIM"):
            broker = KabucomBroker(BrokerEndpointConfig.test())
            broker.token = "token"
            broker._api_request = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("API should not be called"))

            submission = broker._submit_market_order("1234", 100, side="2", price=1234.2, exchange=9)

        self.assertEqual(submission.status, SubmissionStatus.REJECTED)
        self.assertEqual(submission.rejection_reason, "test_endpoint_requires_kabucom_test_mode")

    def test_api_request_does_not_retry_post_on_unauthorized(self):
        session = _FakeSession([_FakeResponse(401, text="unauthorized")])
        broker = _make_broker(session)
        broker._authenticate = lambda: None

        response = broker._api_request("POST", "sendorder", json={"foo": "bar"})

        self.assertEqual(len(session.calls), 1)
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 401)

    def test_api_request_retries_get_on_unauthorized(self):
        session = _FakeSession([
            _FakeResponse(401, text="unauthorized"),
            _FakeResponse(200, {"ok": True}),
        ])
        broker = _make_broker(session)
        broker._authenticate = lambda: None

        response = broker._api_request("GET", "orders")

        self.assertEqual(len(session.calls), 2)
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 200)

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
            result = broker.execute_market_order("1234", 100, action=StockOrderAction.MARGIN_NEW_LONG, price=1234.2)

        self.assertIsInstance(result, OrderSubmissionResult)
        self.assertEqual(result.broker_order_id, "ORDER-1")
        self.assertEqual(result.status, SubmissionStatus.ACCEPTED)
        self.assertTrue(result.request_sent)
        self.assertEqual(result.action, StockOrderAction.MARGIN_NEW_LONG)
        self.assertEqual(result.limit_price, 1235.0)
        self.assertIsNone(result.trigger_price)
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

        result = broker.execute_market_order("1234", 100, action=StockOrderAction.MARGIN_NEW_LONG, price=0, exchange=9)

        self.assertEqual(result.broker_order_id, "ORDER-0")
        self.assertEqual(result.status, SubmissionStatus.ACCEPTED)
        self.assertTrue(result.request_sent)
        self.assertEqual(result.action, StockOrderAction.MARGIN_NEW_LONG)
        self.assertIsNone(result.limit_price)
        self.assertEqual(captured["json"]["FrontOrderType"], 10)
        self.assertEqual(captured["json"]["Price"], 0)

    def test_execute_market_order_uses_order_password_when_separate_from_api_password(self):
        captured = {}

        def fake_api_request(method, endpoint, **kwargs):
            captured["json"] = kwargs["json"]
            return _FakeResponse(200, {"Result": 0, "OrderId": "ORDER-1"})

        broker = _make_broker(_FakeSession([]))
        broker.password = "api-secret"
        broker.order_password = "order-secret"
        broker._api_request = fake_api_request

        result = broker.execute_market_order("1234", 100, action=StockOrderAction.MARGIN_NEW_LONG, price=1234.2, exchange=9)

        self.assertEqual(result.status, SubmissionStatus.ACCEPTED)
        self.assertEqual(captured["json"]["Password"], "order-secret")
        self.assertNotEqual(captured["json"]["Password"], broker.password)

    def test_live_broker_requires_explicit_order_password_for_write(self):
        with patch("core.kabucom_broker.KABUCOM_API_PASSWORD", "api-secret"), \
            patch("core.kabucom_broker.KABUCOM_ORDER_PASSWORD", ""), \
            patch("core.kabucom_broker.TRADE_MODE", "KABUCOM_LIVE"), \
            patch("core.kabucom_broker.DEBUG_MODE", False), \
            patch(
                "core.kabucom_broker.get_live_order_gate_status",
                return_value=SimpleNamespace(
                    allowed=True,
                    reason="approval_granted",
                    runtime_config_hash="sha256:runtime",
                    approved_config_hash="sha256:approved",
                ),
            ), \
            patch(
                "core.kabucom_broker.get_kabucom_live_financial_write_gate_status",
                return_value=SimpleNamespace(
                    allowed=True,
                    reason="ready",
                    blocking_reasons=(),
                ),
            ), \
            patch.object(KabucomBroker, "_authenticate", lambda self: None):
            broker = KabucomBroker(BrokerEndpointConfig.live())
            broker.token = "token"
            broker._api_request = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("API should not be called"))

            market_result = broker.execute_market_order("1234", 100, action=StockOrderAction.MARGIN_NEW_LONG, price=1234.2, exchange=9)
            cancel_result = broker.cancel_order("ORDER-1")

        self.assertIsNone(broker.order_password)
        self.assertEqual(market_result.status, SubmissionStatus.REJECTED)
        self.assertEqual(market_result.rejection_reason, "missing_order_password")
        self.assertFalse(market_result.request_sent)
        self.assertEqual(cancel_result.status, CancelStatus.REJECTED)
        self.assertEqual(cancel_result.rejection_reason, "missing_order_password")
        self.assertFalse(cancel_result.request_sent)

    def test_live_financial_write_gate_blocks_without_actual_kabucom_test_capture(self):
        status = get_kabucom_live_financial_write_gate_status(
            base_gate_status=SimpleNamespace(
                allowed=True,
                reason="ready",
                runtime_config_hash="sha256:runtime",
                approved_config_hash="sha256:runtime",
            ),
            operator_acknowledged=True,
        )

        self.assertFalse(status.allowed)
        self.assertIn("test_contract_fixture_not_captured_from_kabucom_test", status.reason)
        self.assertIn("live_write_attestation_missing", status.reason)
        self.assertTrue(status.test_fixture_present)
        self.assertTrue(status.test_fixture_valid)
        self.assertFalse(status.test_fixture_captured_from_kabucom_test)
        self.assertFalse(status.ci_artifact_attested)
        self.assertTrue(status.operator_acknowledged)
        self.assertFalse(status.live_write_attestation_present)
        self.assertFalse(status.live_write_attestation_valid)

    def test_live_financial_write_gate_preserves_base_gate_rejection_reason(self):
        status = get_kabucom_live_financial_write_gate_status(
            base_gate_status=SimpleNamespace(allowed=False, reason="approval_missing"),
            operator_acknowledged=True,
        )

        self.assertFalse(status.allowed)
        self.assertEqual(status.reason, "approval_missing")
        self.assertEqual(status.blocking_reasons, ("approval_missing",))
        self.assertFalse(status.test_fixture_present)
        self.assertFalse(status.ci_artifact_attested)
        self.assertTrue(status.operator_acknowledged)
        self.assertFalse(status.live_write_attestation_present)

    def test_live_financial_write_gate_allows_only_with_matching_attestation_artifact(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_path, attestation_path, _ = _write_live_write_attestation_artifact(tmpdir)
            with patch.dict(os.environ, {"KABUCOM_LIVE_OPERATOR_ACK": "true"}, clear=False):
                status = get_kabucom_live_financial_write_gate_status(
                    base_gate_status=SimpleNamespace(
                        allowed=True,
                        reason="ready",
                        runtime_config_hash="sha256:runtime",
                        approved_config_hash="sha256:runtime",
                    ),
                    test_fixture_path=fixture_path,
                    live_write_attestation_path=attestation_path,
                )

        self.assertTrue(status.allowed)
        self.assertEqual(status.reason, "ready")
        self.assertEqual(status.blocking_reasons, ())
        self.assertTrue(status.test_fixture_present)
        self.assertTrue(status.test_fixture_valid)
        self.assertTrue(status.test_fixture_captured_from_kabucom_test)
        self.assertTrue(status.ci_artifact_attested)
        self.assertTrue(status.operator_acknowledged)
        self.assertTrue(status.live_write_attestation_present)
        self.assertTrue(status.live_write_attestation_valid)
        self.assertTrue(status.live_write_attestation_captured_from_kabucom_test)

    def test_live_financial_write_gate_blocks_when_operator_ack_is_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_path, attestation_path, _ = _write_live_write_attestation_artifact(tmpdir)
            with patch.dict(os.environ, {"KABUCOM_LIVE_OPERATOR_ACK": "false"}, clear=False):
                status = get_kabucom_live_financial_write_gate_status(
                    base_gate_status=SimpleNamespace(
                        allowed=True,
                        reason="ready",
                        runtime_config_hash="sha256:runtime",
                        approved_config_hash="sha256:runtime",
                    ),
                    test_fixture_path=fixture_path,
                    live_write_attestation_path=attestation_path,
                )

        self.assertFalse(status.allowed)
        self.assertIn("operator_ack_missing", status.reason)
        self.assertTrue(status.ci_artifact_attested)
        self.assertFalse(status.operator_acknowledged)

    def test_live_financial_write_gate_allows_with_structured_operator_ack_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_path, attestation_path, attestation = _write_live_write_attestation_artifact(tmpdir)
            ack_context = {
                "operator_id": "qa-operator",
                "acknowledged_at": "2099-01-01T00:00:00+09:00",
                "expires_at": "2099-12-31T23:59:59+09:00",
                "code_commit_sha": read_git_commit_sha(),
                "approved_config_hash": "sha256:runtime",
                "runtime_config_hash": "sha256:runtime",
                "repository_full_name": read_git_remote_repository_full_name(),
                "test_fixture_hash": hash_contract_fixture(fixture_path),
                "live_write_attestation_hash": compute_live_write_attestation_hash(attestation),
                "reason": "manual approval for test",
            }
            with patch.dict(
                os.environ,
                {
                    "KABUCOM_LIVE_OPERATOR_ACK": "false",
                    "LIVE_WRITE_OPERATOR_ACK": "false",
                    "KABUCOM_LIVE_OPERATOR_ACK_CONTEXT": json.dumps(ack_context, ensure_ascii=False),
                },
                clear=False,
            ), patch("core.live_order_gate.TRADE_MODE", "KABUCOM_LIVE"), patch(
                "core.live_order_gate.get_jpx_trading_day_status",
                return_value=SimpleNamespace(
                    trading_day=True,
                    source_ready=True,
                    source_reason="calendar_trading_date",
                    used_fallback=False,
                ),
            ):
                status = get_kabucom_live_financial_write_gate_status(
                    base_gate_status=SimpleNamespace(
                        allowed=True,
                        reason="ready",
                        runtime_config_hash="sha256:runtime",
                        approved_config_hash="sha256:runtime",
                    ),
                    test_fixture_path=fixture_path,
                    live_write_attestation_path=attestation_path,
                )

        self.assertTrue(status.allowed)
        self.assertEqual(status.operator_ack_source, "structured_context")
        self.assertEqual(status.operator_ack_reason, "operator_ack_context_ok")
        self.assertTrue(status.operator_acknowledged)

    def test_live_financial_write_gate_blocks_when_legacy_operator_ack_paths_are_used_in_live_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_path, attestation_path, _ = _write_live_write_attestation_artifact(tmpdir)
            base_gate_status = SimpleNamespace(
                allowed=True,
                reason="ready",
                runtime_config_hash="sha256:runtime",
                approved_config_hash="sha256:runtime",
            )

            cases = [
                ("legacy_boolean", {"KABUCOM_LIVE_OPERATOR_ACK": "true"}, None),
                ("explicit_argument", {}, True),
            ]

            for label, env_overrides, explicit_ack in cases:
                with self.subTest(label=label):
                    with patch.dict(os.environ, env_overrides, clear=False), \
                        patch("core.live_order_gate.TRADE_MODE", "KABUCOM_LIVE"), \
                        patch(
                            "core.live_order_gate.get_jpx_trading_day_status",
                            return_value=SimpleNamespace(
                                trading_day=True,
                                source_ready=True,
                                source_reason="calendar_trading_date",
                                used_fallback=False,
                            ),
                        ):
                        status = get_kabucom_live_financial_write_gate_status(
                            base_gate_status=base_gate_status,
                            test_fixture_path=fixture_path,
                            live_write_attestation_path=attestation_path,
                            operator_acknowledged=explicit_ack,
                        )

                    self.assertFalse(status.allowed)
                    self.assertIn("operator_ack_context_missing", status.reason)
                    self.assertEqual(status.operator_ack_source, "structured_context")
                    self.assertEqual(status.operator_ack_reason, "operator_ack_context_missing")
                    self.assertFalse(status.operator_acknowledged)

    def test_live_financial_write_gate_blocks_when_structured_operator_ack_context_is_expired(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_path, attestation_path, attestation = _write_live_write_attestation_artifact(tmpdir)
            ack_context = {
                "operator_id": "qa-operator",
                "acknowledged_at": "2020-01-01T00:00:00+09:00",
                "expires_at": "2020-01-02T00:00:00+09:00",
                "code_commit_sha": read_git_commit_sha(),
                "approved_config_hash": "sha256:runtime",
                "runtime_config_hash": "sha256:runtime",
                "repository_full_name": read_git_remote_repository_full_name(),
                "test_fixture_hash": hash_contract_fixture(fixture_path),
                "live_write_attestation_hash": compute_live_write_attestation_hash(attestation),
                "reason": "expired approval for test",
            }
            with patch.dict(
                os.environ,
                {
                    "KABUCOM_LIVE_OPERATOR_ACK": "false",
                    "LIVE_WRITE_OPERATOR_ACK": "false",
                    "KABUCOM_LIVE_OPERATOR_ACK_CONTEXT": json.dumps(ack_context, ensure_ascii=False),
                },
                clear=False,
            ):
                status = get_kabucom_live_financial_write_gate_status(
                    base_gate_status=SimpleNamespace(
                        allowed=True,
                        reason="ready",
                        runtime_config_hash="sha256:runtime",
                        approved_config_hash="sha256:runtime",
                    ),
                    test_fixture_path=fixture_path,
                    live_write_attestation_path=attestation_path,
                )

        self.assertFalse(status.allowed)
        self.assertIn("operator_ack_context_expired", status.reason)
        self.assertEqual(status.operator_ack_source, "structured_context")
        self.assertFalse(status.operator_acknowledged)

    def test_build_live_readiness_report_blocks_when_risk_review_artifact_is_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            startup_recovery_report = build_startup_recovery_report(
                portfolio=[],
                active_orders_info={"orders": [], "has_unknown": False, "unresolved_order_ids": []},
                order_journal_summary=build_order_journal_replay_summary(str(Path(tmpdir) / "order_journal.jsonl")),
                wallet_snapshot_incomplete=False,
            )
            report = build_live_readiness_report(
                portfolio=[],
                startup_recovery_report=startup_recovery_report,
                order_journal_summary=build_order_journal_replay_summary(str(Path(tmpdir) / "order_journal.jsonl")),
                request_budget_counts={bucket: 0 for bucket in RequestBudgetBucket},
                quote_fresh=True,
                risk_review_path=Path(tmpdir) / "missing_live_risk_review.json",
            )

        self.assertFalse(report.allowed)
        item_map = {item.name: item for item in report.items}
        self.assertEqual(item_map["risk_readiness"].status, "not_verified")
        self.assertEqual(item_map["no_lookahead_audit"].status, "not_verified")
        self.assertIn("risk_readiness:not_verified:risk_review_missing", report.reason)

    def test_build_live_readiness_report_allows_when_all_evidence_is_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            portfolio = [
                {
                    "code": "1234",
                    "ownership": "MANAGED_BY_BOT",
                    "position_lot_key_source": "execution_id",
                    "position_lot_key_needs_review": False,
                }
            ]
            startup_recovery_report = build_startup_recovery_report(
                portfolio=portfolio,
                active_orders_info={"orders": [], "has_unknown": False, "unresolved_order_ids": []},
                order_journal_summary=build_order_journal_replay_summary(str(Path(tmpdir) / "order_journal.jsonl")),
                wallet_snapshot_incomplete=False,
            )
            risk_review_path = _write_live_risk_review_artifact(tmpdir)
            report = build_live_readiness_report(
                portfolio=portfolio,
                startup_recovery_report=startup_recovery_report,
                order_journal_summary=build_order_journal_replay_summary(str(Path(tmpdir) / "order_journal.jsonl")),
                request_budget_counts={bucket: 0 for bucket in RequestBudgetBucket},
                quote_fresh=True,
                risk_review_path=risk_review_path,
                expected_runtime_config_hash=RUNTIME_LIVE_ORDER_CONFIG_HASH,
                expected_approval_manifest_hash=compute_live_approval_manifest_hash(),
                expected_code_commit_sha=read_git_commit_sha(),
            )

        self.assertTrue(report.allowed)
        self.assertEqual(report.reason, "ready")
        item_map = {item.name: item for item in report.items}
        self.assertEqual(item_map["protective_stop_lifecycle"].status, "ready")
        self.assertEqual(item_map["partial_fill_unresolved"].status, "ready")
        self.assertEqual(item_map["execution_id_truth"].status, "ready")
        self.assertEqual(item_map["quote_freshness"].status, "ready")
        self.assertEqual(item_map["journal_reconciliation"].status, "ready")
        self.assertEqual(item_map["request_budget"].status, "ready")
        self.assertEqual(item_map["risk_readiness"].status, "ready")
        self.assertEqual(item_map["no_lookahead_audit"].status, "ready")

    def test_build_live_readiness_report_blocks_when_risk_review_runtime_config_hash_mismatches(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            portfolio = [
                {
                    "code": "1234",
                    "ownership": "MANAGED_BY_BOT",
                    "position_lot_key_source": "execution_id",
                    "position_lot_key_needs_review": False,
                }
            ]
            startup_recovery_report = build_startup_recovery_report(
                portfolio=portfolio,
                active_orders_info={"orders": [], "has_unknown": False, "unresolved_order_ids": []},
                order_journal_summary=build_order_journal_replay_summary(str(Path(tmpdir) / "order_journal.jsonl")),
                wallet_snapshot_incomplete=False,
            )
            risk_review_path = _write_live_risk_review_artifact(
                tmpdir,
                runtime_config_hash="sha256:unexpected-runtime-config",
            )
            report = build_live_readiness_report(
                portfolio=portfolio,
                startup_recovery_report=startup_recovery_report,
                order_journal_summary=build_order_journal_replay_summary(str(Path(tmpdir) / "order_journal.jsonl")),
                request_budget_counts={bucket: 0 for bucket in RequestBudgetBucket},
                quote_fresh=True,
                risk_review_path=risk_review_path,
                expected_runtime_config_hash=RUNTIME_LIVE_ORDER_CONFIG_HASH,
                expected_approval_manifest_hash=compute_live_approval_manifest_hash(),
                expected_code_commit_sha=read_git_commit_sha(),
            )

        self.assertFalse(report.allowed)
        item_map = {item.name: item for item in report.items}
        self.assertEqual(item_map["risk_readiness"].status, "blocked")
        self.assertEqual(item_map["risk_readiness"].reason, "risk_review_runtime_config_hash_mismatch")

    def test_entry_authorization_blocks_when_live_readiness_report_is_not_ready(self):
        status = evaluate_entry_authorization(
            EntryAuthorizationContext(
                production_endpoint=True,
                approved_manifest_valid=True,
                reconciliation_clean=True,
                unresolved_order_count=0,
                ambiguous_position_count=0,
                wallet_snapshot_fresh=True,
                positions_snapshot_fresh=True,
                orders_snapshot_fresh=True,
                quote_fresh=True,
                registry_ready=True,
                critical_state_valid=True,
                session_allows_entry=True,
                clock_healthy=True,
                shutdown_requested=False,
                live_readiness_allowed=False,
                live_readiness_reason="risk_readiness:not_verified:risk_review_missing",
            )
        )

        self.assertFalse(status.allowed)
        self.assertIn("live_readiness_report_unready:risk_readiness:not_verified:risk_review_missing", status.blocking_reasons)

    def test_verify_live_write_attestation_artifact_source_accepts_matching_github_artifact(self):
        clear_live_write_attestation_artifact_source_cache()
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_path, attestation_path, attestation = _write_live_write_attestation_artifact(tmpdir)
            digest_path = attestation_path.with_name(attestation_path.name + LIVE_WRITE_ATTESTATION_DIGEST_SUFFIX)

            archive_buffer = io.BytesIO()
            with zipfile.ZipFile(archive_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(f"contracts/{attestation_path.name}", attestation_path.read_text(encoding="utf-8"))
                archive.writestr(f"contracts/{attestation_path.name}.sha256", digest_path.read_text(encoding="utf-8"))
            archive_bytes = archive_buffer.getvalue()
            archive_digest = f"sha256:{sha256(archive_bytes).hexdigest()}"

            run_id = "12345"
            fake_session = _FakeSession([
                _FakeResponse(
                    200,
                    {
                        "id": int(run_id),
                        "status": "completed",
                        "conclusion": "success",
                        "head_sha": read_git_commit_sha(),
                        "html_url": f"https://github.com/yayumura/auto-trade/actions/runs/{run_id}",
                    },
                ),
                _FakeResponse(
                    200,
                    {
                        "total_count": 1,
                        "artifacts": [
                            {
                                "id": 77,
                                "name": "live-write-attestation",
                                "expired": False,
                                "digest": archive_digest,
                                "archive_download_url": "https://api.github.com/repos/yayumura/auto-trade/actions/artifacts/77/zip",
                                "workflow_run": {
                                    "id": int(run_id),
                                    "head_sha": read_git_commit_sha(),
                                    "head_branch": "main",
                                },
                            }
                        ],
                    },
                ),
                _FakeResponse(200, payload={}, content=archive_bytes),
            ])

            result = verify_live_write_attestation_artifact_source(
                repository_full_name="yayumura/auto-trade",
                workflow_run_id=run_id,
                head_sha=read_git_commit_sha(),
                local_attestation_path=attestation_path,
                token="token",
                session=fake_session,
            )
            cached_result = verify_live_write_attestation_artifact_source(
                repository_full_name="yayumura/auto-trade",
                workflow_run_id=run_id,
                head_sha=read_git_commit_sha(),
                local_attestation_path=attestation_path,
                token="token",
                session=fake_session,
            )

        self.assertTrue(result.valid)
        self.assertEqual(result.reason, "github_actions_artifact_source_verified")
        self.assertEqual(result.workflow_run_id, int(run_id))
        self.assertEqual(result.artifact_name, "live-write-attestation")
        self.assertEqual(result.artifact_digest, archive_digest)
        self.assertTrue(cached_result.valid)
        self.assertEqual(cached_result.reason, "github_actions_artifact_source_verified")
        self.assertEqual(len(fake_session.calls), 3)

    def test_verify_live_write_attestation_artifact_source_revalidates_when_cache_ttl_is_disabled(self):
        clear_live_write_attestation_artifact_source_cache()
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_path, attestation_path, attestation = _write_live_write_attestation_artifact(tmpdir)
            digest_path = attestation_path.with_name(attestation_path.name + LIVE_WRITE_ATTESTATION_DIGEST_SUFFIX)

            archive_buffer = io.BytesIO()
            with zipfile.ZipFile(archive_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(f"contracts/{attestation_path.name}", attestation_path.read_text(encoding="utf-8"))
                archive.writestr(f"contracts/{attestation_path.name}.sha256", digest_path.read_text(encoding="utf-8"))
            archive_bytes = archive_buffer.getvalue()
            archive_digest = f"sha256:{sha256(archive_bytes).hexdigest()}"

            run_id = "12345"
            responses = [
                _FakeResponse(
                    200,
                    {
                        "id": int(run_id),
                        "status": "completed",
                        "conclusion": "success",
                        "head_sha": read_git_commit_sha(),
                        "html_url": f"https://github.com/yayumura/auto-trade/actions/runs/{run_id}",
                    },
                ),
                _FakeResponse(
                    200,
                    {
                        "total_count": 1,
                        "artifacts": [
                            {
                                "id": 77,
                                "name": "live-write-attestation",
                                "expired": False,
                                "digest": archive_digest,
                                "archive_download_url": "https://api.github.com/repos/yayumura/auto-trade/actions/artifacts/77/zip",
                                "workflow_run": {
                                    "id": int(run_id),
                                    "head_sha": read_git_commit_sha(),
                                    "head_branch": "main",
                                },
                            }
                        ],
                    },
                ),
                _FakeResponse(200, payload={}, content=archive_bytes),
                _FakeResponse(
                    200,
                    {
                        "id": int(run_id),
                        "status": "completed",
                        "conclusion": "success",
                        "head_sha": read_git_commit_sha(),
                        "html_url": f"https://github.com/yayumura/auto-trade/actions/runs/{run_id}",
                    },
                ),
                _FakeResponse(
                    200,
                    {
                        "total_count": 1,
                        "artifacts": [
                            {
                                "id": 77,
                                "name": "live-write-attestation",
                                "expired": False,
                                "digest": archive_digest,
                                "archive_download_url": "https://api.github.com/repos/yayumura/auto-trade/actions/artifacts/77/zip",
                                "workflow_run": {
                                    "id": int(run_id),
                                    "head_sha": read_git_commit_sha(),
                                    "head_branch": "main",
                                },
                            }
                        ],
                    },
                ),
                _FakeResponse(200, payload={}, content=archive_bytes),
            ]
            fake_session = _FakeSession(responses)

            with patch.dict(os.environ, {"GITHUB_ARTIFACT_SOURCE_CACHE_TTL_SEC": "0"}, clear=False):
                first_result = verify_live_write_attestation_artifact_source(
                    repository_full_name="yayumura/auto-trade",
                    workflow_run_id=run_id,
                    head_sha=read_git_commit_sha(),
                    local_attestation_path=attestation_path,
                    token="token",
                    session=fake_session,
                )
                second_result = verify_live_write_attestation_artifact_source(
                    repository_full_name="yayumura/auto-trade",
                    workflow_run_id=run_id,
                    head_sha=read_git_commit_sha(),
                    local_attestation_path=attestation_path,
                    token="token",
                    session=fake_session,
                )

        self.assertTrue(first_result.valid)
        self.assertTrue(second_result.valid)
        self.assertEqual(len(fake_session.calls), 6)

    def test_verify_live_write_attestation_artifact_source_does_not_leak_token_or_response_body_on_http_failure(self):
        clear_live_write_attestation_artifact_source_cache()
        with tempfile.TemporaryDirectory() as tmpdir:
            _, attestation_path, _ = _write_live_write_attestation_artifact(tmpdir)
            secret_token = "super-secret-token"
            secret_body = '{"error":"super-secret-token","detail":"should-not-leak"}'
            fake_session = _FakeSession([
                _FakeResponse(500, text=secret_body),
            ])

            result = verify_live_write_attestation_artifact_source(
                repository_full_name="yayumura/auto-trade",
                workflow_run_id="12345",
                head_sha=read_git_commit_sha(),
                local_attestation_path=attestation_path,
                token=secret_token,
                session=fake_session,
            )

        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "workflow_run_http_500")
        self.assertNotIn(secret_token, result.reason)
        self.assertNotIn("should-not-leak", result.reason)

    def test_live_financial_write_gate_blocks_when_github_artifact_source_verification_is_required_and_token_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_path, attestation_path, _ = _write_live_write_attestation_artifact(tmpdir)
            with patch.dict(os.environ, {"KABUCOM_LIVE_OPERATOR_ACK": "true"}, clear=False), \
                patch("core.live_order_gate.TRADE_MODE", "KABUCOM_LIVE"):
                status = get_kabucom_live_financial_write_gate_status(
                    base_gate_status=SimpleNamespace(
                        allowed=True,
                        reason="ready",
                        runtime_config_hash="sha256:runtime",
                        approved_config_hash="sha256:runtime",
                    ),
                    test_fixture_path=fixture_path,
                    live_write_attestation_path=attestation_path,
                    require_github_artifact_source=True,
                )

        self.assertFalse(status.allowed)
        self.assertIn("github_attestation_source_unverified:github_token_missing", status.reason)
        self.assertTrue(status.github_artifact_source_required)
        self.assertFalse(status.github_artifact_source_verified)

    def test_write_live_write_attestation_emits_digest_sidecar(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _, attestation_path, attestation = _write_live_write_attestation_artifact(tmpdir)
            digest_path = attestation_path.with_name(attestation_path.name + LIVE_WRITE_ATTESTATION_DIGEST_SUFFIX)
            self.assertTrue(digest_path.exists())
            self.assertEqual(
                digest_path.read_text(encoding="utf-8").strip(),
                compute_live_write_attestation_hash(attestation),
            )

    def test_live_financial_write_gate_blocks_when_attestation_digest_mismatch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_path, attestation_path, _ = _write_live_write_attestation_artifact(tmpdir)
            digest_path = attestation_path.with_name(attestation_path.name + LIVE_WRITE_ATTESTATION_DIGEST_SUFFIX)
            digest_path.write_text("sha256:bogus\n", encoding="utf-8")
            with patch.dict(os.environ, {"KABUCOM_LIVE_OPERATOR_ACK": "true"}, clear=False):
                status = get_kabucom_live_financial_write_gate_status(
                    base_gate_status=SimpleNamespace(
                        allowed=True,
                        reason="ready",
                        runtime_config_hash="sha256:runtime",
                        approved_config_hash="sha256:runtime",
                    ),
                    test_fixture_path=fixture_path,
                    live_write_attestation_path=attestation_path,
                )

        self.assertFalse(status.allowed)
        self.assertIn("live_write_attestation_digest_mismatch", status.reason)
        self.assertFalse(status.live_write_attestation_digest_valid)

    def test_live_financial_write_gate_blocks_when_jpx_calendar_source_is_missing_in_live_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_path, attestation_path, _ = _write_live_write_attestation_artifact(tmpdir)
            with patch.dict(os.environ, {"KABUCOM_LIVE_OPERATOR_ACK": "true"}, clear=False), \
                patch("core.live_order_gate.TRADE_MODE", "KABUCOM_LIVE"):
                status = get_kabucom_live_financial_write_gate_status(
                    base_gate_status=SimpleNamespace(
                        allowed=True,
                        reason="ready",
                        runtime_config_hash="sha256:runtime",
                        approved_config_hash="sha256:runtime",
                    ),
                    test_fixture_path=fixture_path,
                    live_write_attestation_path=attestation_path,
                )

        self.assertFalse(status.allowed)
        self.assertIn("jpx_calendar_missing", status.reason)
        self.assertFalse(status.jpx_calendar_ready)

    def test_jpx_calendar_strict_mode_fails_closed_on_coverage_gap(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            calendar_path = Path(tmpdir) / "jpx_trading_calendar.json"
            calendar_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "closed_dates": [],
                        "trading_dates": [],
                        "half_day_dates": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            strict_status = get_jpx_trading_day_status(
                pd.Timestamp("2026-06-03"),
                calendar_path=calendar_path,
                require_source=True,
            )
            fallback_status = get_jpx_trading_day_status(
                pd.Timestamp("2026-06-03"),
                calendar_path=calendar_path,
                require_source=False,
            )

        self.assertTrue(strict_status.source_present)
        self.assertTrue(strict_status.source_valid)
        self.assertFalse(strict_status.trading_day)
        self.assertFalse(strict_status.source_ready)
        self.assertEqual(strict_status.source_reason, "jpx_calendar_coverage_gap")
        self.assertFalse(strict_status.used_fallback)
        self.assertTrue(fallback_status.source_ready)
        self.assertEqual(fallback_status.source_reason, "calendar_fallback")
        self.assertTrue(fallback_status.used_fallback)

    def test_jpx_calendar_marks_half_day_sessions_in_strict_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            calendar_path = Path(tmpdir) / "jpx_trading_calendar.json"
            calendar_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "closed_dates": [],
                        "trading_dates": [],
                        "half_day_dates": ["2026-06-03"],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            status = get_jpx_trading_day_status(
                pd.Timestamp("2026-06-03"),
                calendar_path=calendar_path,
                require_source=True,
            )

        self.assertTrue(status.source_present)
        self.assertTrue(status.source_valid)
        self.assertTrue(status.trading_day)
        self.assertTrue(status.source_ready)
        self.assertEqual(status.source_reason, "calendar_half_day")
        self.assertTrue(status.half_day)
        self.assertFalse(status.used_fallback)

    def test_live_financial_write_gate_blocks_when_jpx_calendar_source_has_coverage_gap_in_live_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_path, attestation_path, _ = _write_live_write_attestation_artifact(tmpdir)
            with patch.dict(os.environ, {"KABUCOM_LIVE_OPERATOR_ACK": "true"}, clear=False), \
                patch("core.live_order_gate.TRADE_MODE", "KABUCOM_LIVE"), \
                patch(
                    "core.live_order_gate.get_jpx_trading_day_status",
                    return_value=SimpleNamespace(
                        trading_day=False,
                        source_ready=False,
                        source_reason="jpx_calendar_coverage_gap",
                        used_fallback=False,
                    ),
                ):
                status = get_kabucom_live_financial_write_gate_status(
                    base_gate_status=SimpleNamespace(
                        allowed=True,
                        reason="ready",
                        runtime_config_hash="sha256:runtime",
                        approved_config_hash="sha256:runtime",
                    ),
                    test_fixture_path=fixture_path,
                    live_write_attestation_path=attestation_path,
                )

        self.assertFalse(status.allowed)
        self.assertIn("jpx_calendar_coverage_gap", status.reason)
        self.assertFalse(status.jpx_calendar_ready)

    def test_live_financial_write_gate_blocks_on_attestation_mismatches(self):
        base_gate_status = SimpleNamespace(
            allowed=True,
            reason="ready",
            runtime_config_hash="sha256:runtime",
            approved_config_hash="sha256:runtime",
        )

        cases = [
            ("fixture_hash", "live_write_attestation_invalid:live_write_attestation_test_fixture_hash_mismatch", lambda attestation: replace(attestation, test_fixture_hash="sha256:bad")),
            ("ci_head_sha", "live_write_attestation_invalid:live_write_attestation_ci_head_sha_mismatch", lambda attestation: replace(attestation, ci_head_sha="sha256:bad")),
            ("repository", "live_write_attestation_invalid:live_write_attestation_repository_full_name_mismatch", lambda attestation: replace(attestation, repository_full_name="example/repo")),
            ("test_command", "live_write_attestation_invalid:live_write_attestation_test_command_mismatch", lambda attestation: replace(attestation, test_command="python -m pytest tests/test_logic.py")),
            ("approval_manifest_hash", "live_write_attestation_invalid:live_write_attestation_approval_manifest_hash_mismatch", lambda attestation: replace(attestation, approval_manifest_hash="sha256:bad")),
            ("approved_hash", "live_write_attestation_invalid:live_write_attestation_approved_config_hash_mismatch", lambda attestation: replace(attestation, approved_config_hash="sha256:bad")),
        ]

        for label, expected_reason, mutate_attestation in cases:
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as tmpdir:
                    fixture_path, attestation_path, attestation = _write_live_write_attestation_artifact(tmpdir)
                    if label == "fixture_hash":
                        fixture = load_contract_fixture(TEST_CONTRACT_FIXTURE_PATH)
                        assert isinstance(fixture, dict)
                        mutated_fixture = json.loads(json.dumps(fixture))
                        mutated_fixture["captured_from_kabucom_test"] = True
                        mutated_fixture["provenance_note"] = "mismatched fixture"
                        fixture_path.write_text(json.dumps(mutated_fixture, ensure_ascii=False, indent=2), encoding="utf-8")
                    else:
                        mutated_attestation = mutate_attestation(attestation)
                        write_live_write_attestation(attestation_path, mutated_attestation)

                    status = get_kabucom_live_financial_write_gate_status(
                        base_gate_status=base_gate_status,
                        test_fixture_path=fixture_path,
                        live_write_attestation_path=attestation_path,
                        operator_acknowledged=True,
                    )

                self.assertFalse(status.allowed)
                self.assertIn(expected_reason, status.reason)

    def test_build_live_write_attestation_skips_manual_fixture_without_approved_config_hash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture = load_contract_fixture(TEST_CONTRACT_FIXTURE_PATH)
            assert isinstance(fixture, dict)
            manual_fixture = json.loads(json.dumps(fixture))
            manual_fixture["captured_from_kabucom_test"] = False

            fixture_path = Path(tmpdir) / "kabucom_test_contract_fixture.json"
            fixture_path.write_text(json.dumps(manual_fixture, ensure_ascii=False, indent=2), encoding="utf-8")
            output_path = Path(tmpdir) / "live_write_attestation.json"

            with patch.object(
                build_live_write_attestation_script.sys,
                "argv",
                [
                    "build_live_write_attestation.py",
                    "--fixture-path",
                    str(fixture_path),
                    "--output",
                    str(output_path),
                ],
            ):
                self.assertEqual(build_live_write_attestation_script.main(), 0)

            self.assertFalse(output_path.exists())

    def test_build_live_write_attestation_requires_approved_config_hash_for_actual_fixture(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture = load_contract_fixture(TEST_CONTRACT_FIXTURE_PATH)
            assert isinstance(fixture, dict)
            actual_fixture = json.loads(json.dumps(fixture))
            actual_fixture["captured_from_kabucom_test"] = True

            fixture_path = Path(tmpdir) / "kabucom_test_contract_fixture.json"
            fixture_path.write_text(json.dumps(actual_fixture, ensure_ascii=False, indent=2), encoding="utf-8")
            output_path = Path(tmpdir) / "live_write_attestation.json"

            with patch.object(
                build_live_write_attestation_script.sys,
                "argv",
                [
                    "build_live_write_attestation.py",
                    "--fixture-path",
                    str(fixture_path),
                    "--output",
                    str(output_path),
                    "--ci-run-id",
                    "12345",
                    "--ci-head-sha",
                    "sha256:head",
                    "--repository-full-name",
                    "yayumura/auto-trade",
                ],
            ):
                with self.assertRaises(SystemExit) as exc:
                    build_live_write_attestation_script.main()

            self.assertIn("APPROVED_CONFIG_HASH", str(exc.exception))
            self.assertFalse(output_path.exists())

    def test_execute_market_order_sell_side_uses_close_positions_and_daytrade_margin(self):
        captured = {}

        def fake_api_request(method, endpoint, **kwargs):
            captured["json"] = kwargs["json"]
            return _FakeResponse(200, {"Result": 0, "OrderId": "ORDER-SELL"})

        broker = _make_broker(_FakeSession([]))
        broker._api_request = fake_api_request

        result = broker.execute_market_order(
            "1234",
            100,
            action=StockOrderAction.MARGIN_CLOSE_LONG,
            price=1234.2,
            close_positions=[{"HoldID": "HOLD-1", "Qty": 100}],
            exchange=1,
            margin_trade_type=3,
        )

        self.assertEqual(result.broker_order_id, "ORDER-SELL")
        self.assertEqual(result.status, SubmissionStatus.ACCEPTED)
        self.assertTrue(result.request_sent)
        self.assertEqual(result.action, StockOrderAction.MARGIN_CLOSE_LONG)
        self.assertEqual(result.limit_price, 1234.0)
        self.assertEqual(captured["json"]["CashMargin"], 3)
        self.assertEqual(captured["json"]["MarginTradeType"], 3)
        self.assertEqual(captured["json"]["DelivType"], 2)
        self.assertEqual(captured["json"]["Exchange"], 1)
        self.assertIn("ClosePositions", captured["json"])

    def test_execute_market_order_aborts_without_close_positions_on_sell_side(self):
        broker = _make_broker(_FakeSession([]))
        broker._api_request = lambda *args, **kwargs: _FakeResponse(200, {"Result": 0, "OrderId": "ORDER-FAIL"})

        result = broker.execute_market_order("1234", 100, action=StockOrderAction.MARGIN_CLOSE_LONG, price=1234.2)

        self.assertEqual(result.status, SubmissionStatus.REJECTED)
        self.assertFalse(result.request_sent)
        self.assertEqual(result.rejection_reason, "missing_close_route")
        self.assertIsNone(result.broker_order_id)
        self.assertEqual(result.action, StockOrderAction.MARGIN_CLOSE_LONG)

    def test_execute_market_order_rejects_empty_close_positions_list_on_sell_side(self):
        broker = _make_broker(_FakeSession([]))
        broker._api_request = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("API should not be called"))

        result = broker.execute_market_order(
            "1234",
            100,
            action=StockOrderAction.MARGIN_CLOSE_LONG,
            price=1234.2,
            close_positions=[],
            exchange=1,
            margin_trade_type=3,
        )

        self.assertEqual(result.status, SubmissionStatus.REJECTED)
        self.assertFalse(result.request_sent)
        self.assertEqual(result.rejection_reason, "close_positions_unavailable")
        self.assertIsNone(result.broker_order_id)
        self.assertEqual(result.action, StockOrderAction.MARGIN_CLOSE_LONG)

    def test_submit_market_order_rejects_live_new_buy_when_live_gate_blocks(self):
        with patch("core.kabucom_broker.KABUCOM_API_PASSWORD", ""), \
            patch("core.kabucom_broker.KABUCOM_ORDER_PASSWORD", "order-secret"), \
            patch("core.kabucom_broker.TRADE_MODE", "KABUCOM_LIVE"), \
            patch("core.kabucom_broker.DEBUG_MODE", False), \
            patch(
                "core.kabucom_broker.get_live_order_gate_status",
                return_value=SimpleNamespace(
                    allowed=False,
                    reason="approval_missing",
                    runtime_config_hash="sha256:runtime",
                    approved_config_hash="",
                ),
            ):
            broker = KabucomBroker(BrokerEndpointConfig.live())
            broker.token = "token"

            with patch("core.kabucom_broker.append_order_journal") as mock_journal, \
                patch.object(broker, "_api_request", side_effect=AssertionError("API should not be called")):
                submission = broker._submit_market_order("1234", 100, side="2", price=1234.2, exchange=9)

        self.assertEqual(submission.status, SubmissionStatus.REJECTED)
        self.assertEqual(submission.rejection_reason, "live_new_order_disabled:approval_missing")
        self.assertEqual(mock_journal.call_count, 1)
        self.assertEqual(mock_journal.call_args.args[0]["event"], "REJECTED")

    def test_execute_stop_order_allows_protective_exit_when_live_gate_blocks_entries(self):
        captured = {}
        journal_events = []
        stop_details = [
            {
                "OrderId": "STOP-1",
                "State": 3,
                "OrderQty": 100,
                "CumQty": 0,
                "CashMargin": 3,
                "DelivType": 2,
                "Exchange": 1,
                "MarginTradeType": 3,
                "Side": "1",
                "ReverseLimitOrder": {
                    "TriggerSec": 1,
                    "TriggerPrice": 3000.0,
                    "UnderOver": 1,
                    "AfterHitOrderType": 1,
                    "AfterHitPrice": 0,
                },
                "ClosePositions": [{"HoldID": "HOLD-1", "Qty": 100}],
                "Details": [
                    {"RecType": 4, "SeqNum": 1, "State": 3, "Qty": 100, "Price": 0, "ExecutionID": "EX-STOP"},
                ],
            }
        ]

        def fake_api_request(method, endpoint, **kwargs):
            if method == "POST" and endpoint == "sendorder":
                captured["method"] = method
                captured["endpoint"] = endpoint
                captured["json"] = kwargs["json"]
                return _FakeResponse(200, {"Result": 0, "OrderId": "STOP-1"})
            if method == "GET" and endpoint == "orders?id=STOP-1":
                return _FakeResponse(200, stop_details)
            raise AssertionError(f"unexpected request: {method} {endpoint}")

        with patch("core.kabucom_broker.KABUCOM_API_PASSWORD", ""), \
            patch("core.kabucom_broker.TRADE_MODE", "KABUCOM_LIVE"), \
            patch("core.kabucom_broker.DEBUG_MODE", False), \
            patch(
                "core.kabucom_broker.get_live_order_gate_status",
                return_value=SimpleNamespace(
                    allowed=False,
                    reason="approval_missing",
                    runtime_config_hash="sha256:runtime",
                    approved_config_hash="",
                ),
            ):
            broker = KabucomBroker(BrokerEndpointConfig.live())
            broker.password = "test-password"
            broker.order_password = "test-password"
            broker.token = "token"
            broker._api_request = fake_api_request
            broker.get_positions = lambda: [
                {
                    "hold_id": "HOLD-1",
                    "exchange": 1,
                    "margin_trade_type": 3,
                    "available_qty": 100,
                    "hold_qty": 0,
                    "code": "1234",
                    "ownership": "MANAGED_BY_BOT",
                }
            ]

            with patch("core.kabucom_broker.append_order_journal", side_effect=lambda event, path=None: journal_events.append(event)):
                result = broker.execute_stop_order("1234", 100, action=StockOrderAction.MARGIN_CLOSE_LONG, trigger_price=3001.2, hold_id="HOLD-1")

        self.assertIsInstance(result, OrderSubmissionResult)
        self.assertEqual(result.broker_order_id, "STOP-1")
        self.assertEqual(result.status, SubmissionStatus.ACCEPTED)
        self.assertTrue(result.request_sent)
        self.assertTrue(result.confirmed)
        self.assertEqual(result.action, StockOrderAction.MARGIN_CLOSE_LONG)
        self.assertEqual(result.trigger_price, 3000.0)
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["endpoint"], "sendorder")
        self.assertEqual(captured["json"]["FrontOrderType"], 30)
        self.assertEqual(captured["json"]["CashMargin"], 3)
        self.assertEqual(captured["json"]["ReverseLimitOrder"]["UnderOver"], 1)
        self.assertEqual([event["event"] for event in journal_events[:3]], ["PLANNED", "ROUTE_RESOLVED", "ACCEPTED"])
        self.assertEqual(journal_events[1]["close_positions"], [{"HoldID": "HOLD-1", "Qty": 100}])
        self.assertEqual(journal_events[1]["hold_ids"], ["HOLD-1"])
        self.assertEqual(journal_events[2]["expected_close_positions"], [{"HoldID": "HOLD-1", "Qty": 100}])
        self.assertEqual(journal_events[2]["route_resolution_stage"], "fallback_single_hold")

    def test_execute_market_order_writes_order_journal(self):
        journal_events = []

        def fake_api_request(method, endpoint, **kwargs):
            return _FakeResponse(200, {"Result": 0, "OrderId": "ORDER-1"})

        def fake_append(event, path=None):
            journal_events.append(event)

        broker = _make_broker(_FakeSession([]))
        broker._api_request = fake_api_request

        with patch("core.kabucom_broker.append_order_journal", side_effect=fake_append):
            result = broker.execute_market_order("1234", 100, action=StockOrderAction.MARGIN_NEW_LONG, price=1234.2, exchange=9)

        self.assertEqual(result.broker_order_id, "ORDER-1")
        self.assertEqual(result.status, SubmissionStatus.ACCEPTED)
        self.assertGreaterEqual(len(journal_events), 2)
        self.assertEqual(journal_events[0]["event"], "PLANNED")
        self.assertEqual(journal_events[1]["event"], "ACCEPTED")

    def test_execute_market_order_rejects_missing_buy_exchange(self):
        broker = _make_broker(_FakeSession([]))
        broker._api_request = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("API should not be called"))

        result = broker.execute_market_order("1234", 100, action=StockOrderAction.MARGIN_NEW_LONG, price=1234.2)

        self.assertEqual(result.status, SubmissionStatus.REJECTED)
        self.assertFalse(result.request_sent)
        self.assertEqual(result.rejection_reason, "missing_buy_exchange")
        self.assertIsNone(result.broker_order_id)

    def test_execute_market_order_rejects_missing_account_type(self):
        broker = _make_broker(_FakeSession([]))
        broker._api_request = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("API should not be called"))

        with patch.dict(os.environ, {"KABUCOM_ACCOUNT_TYPE": ""}):
            result = broker.execute_market_order("1234", 100, action=StockOrderAction.MARGIN_NEW_LONG, price=1234.2, exchange=9)

        self.assertEqual(result.status, SubmissionStatus.REJECTED)
        self.assertFalse(result.request_sent)
        self.assertEqual(result.rejection_reason, "missing_account_type")
        self.assertIsNone(result.broker_order_id)

    def test_execute_market_order_rejects_unsupported_short_action_without_sending_request(self):
        broker = _make_broker(_FakeSession([]))
        broker._api_request = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("API should not be called"))

        result = broker.execute_market_order("1234", 100, action=StockOrderAction.MARGIN_NEW_SHORT, price=1234.2)

        self.assertEqual(result.status, SubmissionStatus.REJECTED)
        self.assertFalse(result.request_sent)
        self.assertEqual(result.rejection_reason, "unsupported_stock_order_action")
        self.assertIsNone(result.broker_order_id)
        self.assertEqual(result.action, StockOrderAction.MARGIN_NEW_SHORT)

    def test_execute_stop_order_rejects_missing_buy_exchange(self):
        broker = _make_broker(_FakeSession([]))
        broker._api_request = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("API should not be called"))

        result = broker.execute_stop_order("1234", 100, action=StockOrderAction.MARGIN_NEW_LONG, trigger_price=3001.2)

        self.assertEqual(result.status, SubmissionStatus.REJECTED)
        self.assertFalse(result.request_sent)
        self.assertEqual(result.rejection_reason, "missing_buy_exchange")
        self.assertIsNone(result.broker_order_id)

    def test_execute_stop_order_rejects_unsupported_short_action_without_sending_request(self):
        broker = _make_broker(_FakeSession([]))
        broker._api_request = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("API should not be called"))

        result = broker.execute_stop_order("1234", 100, action=StockOrderAction.MARGIN_CLOSE_SHORT, trigger_price=3001.2)

        self.assertEqual(result.status, SubmissionStatus.REJECTED)
        self.assertFalse(result.request_sent)
        self.assertEqual(result.rejection_reason, "unsupported_stock_order_action")
        self.assertIsNone(result.broker_order_id)
        self.assertEqual(result.action, StockOrderAction.MARGIN_CLOSE_SHORT)

    def test_execute_stop_order_normalizes_trigger_price(self):
        captured = {}
        stop_details = [
            {
                "OrderId": "STOP-1",
                "State": 3,
                "OrderQty": 100,
                "CumQty": 0,
                "CashMargin": 3,
                "DelivType": 2,
                "Exchange": 1,
                "MarginTradeType": 3,
                "Side": "1",
                "ReverseLimitOrder": {
                    "TriggerSec": 1,
                    "TriggerPrice": 3000.0,
                    "UnderOver": 1,
                    "AfterHitOrderType": 1,
                    "AfterHitPrice": 0,
                },
                "ClosePositions": [{"HoldID": "HOLD-1", "Qty": 100}],
                "Details": [
                    {"RecType": 4, "SeqNum": 1, "State": 3, "Qty": 100, "Price": 0, "ExecutionID": "EX-STOP"},
                ],
            }
        ]

        def fake_api_request(method, endpoint, **kwargs):
            if method == "POST" and endpoint == "sendorder":
                captured["method"] = method
                captured["endpoint"] = endpoint
                captured["json"] = kwargs["json"]
                return _FakeResponse(200, {"Result": 0, "OrderId": "STOP-1"})
            if method == "GET" and endpoint == "orders?id=STOP-1":
                return _FakeResponse(200, stop_details)
            raise AssertionError(f"unexpected request: {method} {endpoint}")

        broker = _make_broker(_FakeSession([]))
        broker._api_request = fake_api_request
        broker.get_positions = lambda: [
            {
                "hold_id": "HOLD-1",
                "exchange": 1,
                "margin_trade_type": 3,
                "available_qty": 100,
                "code": "1234",
                "ownership": "MANAGED_BY_BOT",
            }
        ]

        result = broker.execute_stop_order("1234", 100, action=StockOrderAction.MARGIN_CLOSE_LONG, trigger_price=3001.2, hold_id="HOLD-1")

        self.assertEqual(result.broker_order_id, "STOP-1")
        self.assertEqual(result.status, SubmissionStatus.ACCEPTED)
        self.assertEqual(result.action, StockOrderAction.MARGIN_CLOSE_LONG)
        self.assertTrue(result.request_sent)
        self.assertEqual(result.trigger_price, 3000.0)
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
        self.assertTrue(result.confirmed)

    def test_execute_stop_order_accepts_multiple_close_positions_for_multi_hold_protective_stop(self):
        captured = {}
        journal_events = []
        stop_details = [
            {
                "OrderId": "STOP-MULTI",
                "State": 3,
                "OrderQty": 100,
                "CumQty": 0,
                "CashMargin": 3,
                "DelivType": 2,
                "Exchange": 1,
                "MarginTradeType": 3,
                "Side": "1",
                "ReverseLimitOrder": {
                    "TriggerSec": 1,
                    "TriggerPrice": 3000.0,
                    "UnderOver": 1,
                    "AfterHitOrderType": 1,
                    "AfterHitPrice": 0,
                },
                "ClosePositions": [{"HoldID": "HOLD-1", "Qty": 60}, {"HoldID": "HOLD-2", "Qty": 40}],
                "Details": [
                    {"RecType": 4, "SeqNum": 1, "State": 3, "Qty": 100, "Price": 0, "ExecutionID": "EX-STOP"},
                ],
            }
        ]

        def fake_api_request(method, endpoint, **kwargs):
            if method == "POST" and endpoint == "sendorder":
                captured["method"] = method
                captured["endpoint"] = endpoint
                captured["json"] = kwargs["json"]
                return _FakeResponse(200, {"Result": 0, "OrderId": "STOP-MULTI"})
            if method == "GET" and endpoint == "orders?id=STOP-MULTI":
                return _FakeResponse(200, stop_details)
            raise AssertionError(f"unexpected request: {method} {endpoint}")

        broker = _make_broker(_FakeSession([]))
        broker._api_request = fake_api_request

        with patch("core.kabucom_broker.append_order_journal", side_effect=lambda event, path=None: journal_events.append(event)):
            result = broker.execute_stop_order(
                "1234",
                100,
                action=StockOrderAction.MARGIN_CLOSE_LONG,
                trigger_price=3001.2,
                close_positions=[{"HoldID": "HOLD-1", "Qty": 60}, {"HoldID": "HOLD-2", "Qty": 40}],
                exchange=1,
                margin_trade_type=3,
            )

        self.assertEqual(result.broker_order_id, "STOP-MULTI")
        self.assertEqual(result.status, SubmissionStatus.ACCEPTED)
        self.assertTrue(result.confirmed)
        self.assertEqual(result.action, StockOrderAction.MARGIN_CLOSE_LONG)
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["endpoint"], "sendorder")
        self.assertEqual(captured["json"]["CashMargin"], 3)
        self.assertEqual(captured["json"]["Exchange"], 1)
        self.assertEqual(captured["json"]["MarginTradeType"], 3)
        self.assertEqual(captured["json"]["ClosePositions"], [{"HoldID": "HOLD-1", "Qty": 60}, {"HoldID": "HOLD-2", "Qty": 40}])
        self.assertEqual([event["event"] for event in journal_events[:3]], ["PLANNED", "ROUTE_RESOLVED", "ACCEPTED"])
        self.assertEqual(journal_events[1]["close_positions"], [{"HoldID": "HOLD-1", "Qty": 60}, {"HoldID": "HOLD-2", "Qty": 40}])
        self.assertEqual(journal_events[1]["hold_ids"], ["HOLD-1", "HOLD-2"])
        self.assertEqual(journal_events[2]["expected_close_positions"], [{"HoldID": "HOLD-1", "Qty": 60}, {"HoldID": "HOLD-2", "Qty": 40}])
        self.assertEqual(journal_events[2]["route_resolution_stage"], "resolved")

    def test_order_submission_result_bool_is_accepted_only_and_exposes_confirmation_helpers(self):
        result = OrderSubmissionResult(
            status=SubmissionStatus.ACCEPTED,
            intent_id="intent-1",
            broker_order_id="ORDER-1",
            request_sent=True,
            action=StockOrderAction.MARGIN_CLOSE_LONG,
            symbol="1234",
            qty=100,
            side="1",
            confirmed=False,
        )

        self.assertTrue(bool(result))
        self.assertTrue(result.is_accepted)
        self.assertFalse(result.is_confirmed)
        self.assertFalse(result.is_protective_stop_armed)

    def test_execute_stop_order_uses_generated_close_positions_for_single_hold_fallback_confirmation(self):
        captured = {}
        journal_events = []
        stop_details = [
            {
                "OrderId": "STOP-FALLBACK",
                "State": 3,
                "OrderQty": 100,
                "CumQty": 0,
                "CashMargin": 3,
                "DelivType": 2,
                "Exchange": 1,
                "MarginTradeType": 3,
                "Side": "1",
                "ReverseLimitOrder": {
                    "TriggerSec": 1,
                    "TriggerPrice": 3000.0,
                    "UnderOver": 1,
                    "AfterHitOrderType": 1,
                    "AfterHitPrice": 0,
                },
                "ClosePositions": [{"HoldID": "HOLD-1", "Qty": 100}],
                "Details": [
                    {"RecType": 4, "SeqNum": 1, "State": 3, "Qty": 100, "Price": 0, "ExecutionID": "EX-STOP"},
                ],
            }
        ]

        def fake_api_request(method, endpoint, **kwargs):
            if method == "POST" and endpoint == "sendorder":
                captured["json"] = kwargs["json"]
                return _FakeResponse(200, {"Result": 0, "OrderId": "STOP-FALLBACK"})
            if method == "GET" and endpoint == "orders?id=STOP-FALLBACK":
                return _FakeResponse(200, stop_details)
            raise AssertionError(f"unexpected request: {method} {endpoint}")

        broker = _make_broker(_FakeSession([]))
        broker._api_request = fake_api_request
        broker.get_positions = lambda: [
            {
                "hold_id": "HOLD-1",
                "exchange": 1,
                "margin_trade_type": 3,
                "available_qty": 100,
                "hold_qty": 100,
                "code": "1234",
                "ownership": "MANAGED_BY_BOT",
            }
        ]

        with patch("core.kabucom_broker.append_order_journal", side_effect=lambda event, path=None: journal_events.append(event)):
            result = broker.execute_stop_order("1234", 100, action=StockOrderAction.MARGIN_CLOSE_LONG, trigger_price=3001.2, hold_id="HOLD-1")

        self.assertIsInstance(result, OrderSubmissionResult)
        self.assertTrue(result.confirmed)
        self.assertTrue(result.is_confirmed)
        self.assertEqual(captured["json"]["ClosePositions"], [{"HoldID": "HOLD-1", "Qty": 100}])
        self.assertEqual(journal_events[1]["route_resolution_stage"], "fallback_single_hold")
        self.assertEqual(journal_events[1]["route_resolution_reason"], "single_hold_fallback")
        self.assertEqual(journal_events[2]["expected_close_positions"], [{"HoldID": "HOLD-1", "Qty": 100}])

    def test_execute_stop_order_records_redacted_confirmation_summary_when_single_hold_fallback_confirmation_fails(self):
        captured = {}
        journal_events = []
        stop_details = [
            {
                "OrderId": "STOP-FALLBACK",
                "State": 3,
                "OrderQty": 100,
                "CumQty": 0,
                "CashMargin": 3,
                "DelivType": 2,
                "Exchange": 1,
                "MarginTradeType": 3,
                "Side": "1",
                "ReverseLimitOrder": {
                    "TriggerSec": 1,
                    "TriggerPrice": 3000.0,
                    "UnderOver": 1,
                    "AfterHitOrderType": 1,
                    "AfterHitPrice": 0,
                },
                "ClosePositions": [{"HoldID": "HOLD-1", "Qty": 50}],
                "Password": "super-secret",
                "Token": "session-token",
                "OpaqueField": {"nested": "private"},
                "Details": [
                    {"RecType": 4, "SeqNum": 1, "State": 3, "Qty": 100, "Price": 0, "ExecutionID": "EX-STOP"},
                ],
            }
        ]

        def fake_api_request(method, endpoint, **kwargs):
            if method == "POST" and endpoint == "sendorder":
                captured["json"] = kwargs["json"]
                return _FakeResponse(200, {"Result": 0, "OrderId": "STOP-FALLBACK"})
            if method == "GET" and endpoint == "orders?id=STOP-FALLBACK":
                return _FakeResponse(200, stop_details)
            raise AssertionError(f"unexpected request: {method} {endpoint}")

        broker = _make_broker(_FakeSession([]))
        broker._api_request = fake_api_request
        broker.get_positions = lambda: [
            {
                "hold_id": "HOLD-1",
                "exchange": 1,
                "margin_trade_type": 3,
                "available_qty": 100,
                "hold_qty": 100,
                "code": "1234",
                "ownership": "MANAGED_BY_BOT",
            }
        ]

        with patch("core.kabucom_broker.append_order_journal", side_effect=lambda event, path=None: journal_events.append(event)):
            result = broker.execute_stop_order("1234", 100, action=StockOrderAction.MARGIN_CLOSE_LONG, trigger_price=3001.2, hold_id="HOLD-1")

        self.assertIsInstance(result, OrderSubmissionResult)
        self.assertFalse(result.confirmed)
        self.assertFalse(result.is_confirmed)
        self.assertEqual(result.confirmation_reason, "stop_order_close_positions_mismatch")
        self.assertEqual(captured["json"]["ClosePositions"], [{"HoldID": "HOLD-1", "Qty": 100}])
        summary = journal_events[-1]["confirmation_details"]
        self.assertIsInstance(summary, dict)
        self.assertEqual(summary["response_shape_version"], 1)
        self.assertEqual(summary["mismatch_reason"], "stop_order_close_positions_mismatch")
        self.assertEqual(summary["expected_close_positions"], [{"HoldID": "HOLD-1", "Qty": 100}])
        self.assertEqual(summary["close_positions"], [{"HoldID": "HOLD-1", "Qty": 50}])
        self.assertFalse(summary["close_positions_match"])
        self.assertNotIn("Password", summary)
        self.assertNotIn("Token", summary)
        self.assertNotIn("OpaqueField", summary)
        self.assertLess(len(json.dumps(summary, ensure_ascii=False)), 4096)

    def test_execute_stop_order_rejects_empty_close_positions_list_even_when_hold_id_is_available(self):
        broker = _make_broker(_FakeSession([]))
        broker._api_request = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("API should not be called"))

        result = broker.execute_stop_order(
            "1234",
            100,
            action=StockOrderAction.MARGIN_CLOSE_LONG,
            trigger_price=3001.2,
            hold_id="HOLD-1",
            close_positions=[],
            exchange=1,
            margin_trade_type=3,
        )

        self.assertEqual(result.status, SubmissionStatus.REJECTED)
        self.assertFalse(result.request_sent)
        self.assertEqual(result.rejection_reason, "close_positions_invalid")
        self.assertIsNone(result.broker_order_id)
        self.assertEqual(result.action, StockOrderAction.MARGIN_CLOSE_LONG)

    def test_execute_stop_order_uses_buy_side_reverse_limit_direction(self):
        captured = {}
        stop_details = [
            {
                "OrderId": "STOP-2",
                "State": 3,
                "OrderQty": 100,
                "CumQty": 0,
                "CashMargin": 2,
                "DelivType": 0,
                "Exchange": 9,
                "MarginTradeType": 3,
                "Side": "2",
                "ReverseLimitOrder": {
                    "TriggerSec": 1,
                    "TriggerPrice": 3005.0,
                    "UnderOver": 2,
                    "AfterHitOrderType": 1,
                    "AfterHitPrice": 0,
                },
                "Details": [
                    {"RecType": 4, "SeqNum": 1, "State": 3, "Qty": 100, "Price": 0, "ExecutionID": "EX-STOP"},
                ],
            }
        ]

        def fake_api_request(method, endpoint, **kwargs):
            if method == "POST" and endpoint == "sendorder":
                captured["json"] = kwargs["json"]
                return _FakeResponse(200, {"Result": 0, "OrderId": "STOP-2"})
            if method == "GET" and endpoint == "orders?id=STOP-2":
                return _FakeResponse(200, stop_details)
            raise AssertionError(f"unexpected request: {method} {endpoint}")

        broker = _make_broker(_FakeSession([]))
        broker._api_request = fake_api_request

        result = broker.execute_stop_order("1234", 100, action=StockOrderAction.MARGIN_NEW_LONG, trigger_price=3001.2, exchange=9)

        self.assertEqual(result.broker_order_id, "STOP-2")
        self.assertEqual(result.status, SubmissionStatus.ACCEPTED)
        self.assertTrue(result.confirmed)
        self.assertEqual(result.action, StockOrderAction.MARGIN_NEW_LONG)
        self.assertEqual(result.trigger_price, 3005.0)
        self.assertEqual(captured["json"]["ReverseLimitOrder"]["TriggerPrice"], 3005.0)
        self.assertEqual(captured["json"]["ReverseLimitOrder"]["UnderOver"], 2)

    def test_execute_stop_order_aborts_without_hold_id_on_sell_side(self):
        broker = _make_broker(_FakeSession([]))
        broker._api_request = lambda *args, **kwargs: _FakeResponse(200, {"Result": 0, "OrderId": "STOP-FAIL"})
        journal_events = []

        with patch("core.kabucom_broker.append_order_journal", side_effect=lambda event, path=None: journal_events.append(event)):
            result = broker.execute_stop_order("1234", 100, action=StockOrderAction.MARGIN_CLOSE_LONG, trigger_price=3001.2)

        self.assertEqual(result.status, SubmissionStatus.REJECTED)
        self.assertFalse(result.request_sent)
        self.assertEqual(result.rejection_reason, "missing_close_route")
        self.assertIsNone(result.broker_order_id)
        self.assertEqual(result.action, StockOrderAction.MARGIN_CLOSE_LONG)
        self.assertEqual(journal_events[0]["event"], "REJECTED")
        self.assertEqual(journal_events[0]["route_resolution_stage"], "pre_resolution")
        self.assertEqual(journal_events[0]["route_resolution_reason"], "missing_close_route")
        self.assertIsNone(journal_events[0]["close_positions"])

    def test_execute_chase_order_stops_after_unknown_submission_without_forcing_second_order(self):
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
            {"code": "1234", "hold_id": "HOLD-1", "exchange": 1, "margin_trade_type": 3, "leaves_qty": 60, "hold_qty": 0, "available_qty": 60, "buy_time": "2026-04-21 09:00:00", "execution_id": "EX-1", "ownership": "MANAGED_BY_BOT"},
            {"code": "1234", "hold_id": "HOLD-2", "exchange": 1, "margin_trade_type": 3, "leaves_qty": 40, "hold_qty": 0, "available_qty": 40, "buy_time": "2026-04-21 09:01:00", "execution_id": "EX-2", "ownership": "MANAGED_BY_BOT"},
        ]
        broker.cancel_order = lambda order_id: True

        def fake_submit_market_order(code, shares, side, price=0, close_positions=None, exchange=None, margin_trade_type=None, **kwargs):
            call_args.append({
                "code": code,
                "shares": shares,
                "side": side,
                "price": price,
                "close_positions": close_positions,
                "exchange": exchange,
                "margin_trade_type": margin_trade_type,
                "operation_class": kwargs.get("operation_class"),
            })
            return SubmissionResult(
                status=SubmissionStatus.UNKNOWN,
                intent_id="market-1",
                broker_order_id=None,
                symbol=code,
                side=side,
                qty=shares,
                price=price,
                http_status=None,
                rejection_reason="no_response",
            )

        broker._submit_market_order = fake_submit_market_order

        result = broker.execute_chase_order("1234", 100, action=StockOrderAction.MARGIN_CLOSE_LONG, atr=10.0)

        self.assertEqual(len(call_args), 1)
        self.assertEqual(
            call_args[0]["close_positions"],
            [
                {"HoldID": "HOLD-1", "Qty": 60},
                {"HoldID": "HOLD-2", "Qty": 40},
            ],
        )
        self.assertEqual(call_args[0]["exchange"], 1)
        self.assertEqual(call_args[0]["margin_trade_type"], 3)
        self.assertTrue(result["unresolved"])
        self.assertEqual(result["process_state"], OrderProcessState.UNKNOWN.value)
        self.assertIsNone(result["terminal_reason"])

    def test_execute_chase_order_logs_filled_terminal_event_when_order_completes(self):
        call_args = []
        journal_events = []

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
        broker._build_close_positions_for_symbol = lambda code, requested_qty, managed_execution_ids=None: {
            "close_positions": [
                {"HoldID": "HOLD-1", "Qty": 60},
                {"HoldID": "HOLD-2", "Qty": 40},
            ],
            "exchange": 1,
            "margin_trade_type": 3,
        }

        def fake_submit_market_order(code, shares, side, price=0, close_positions=None, exchange=None, margin_trade_type=None, **kwargs):
            call_args.append({
                "code": code,
                "shares": shares,
                "side": side,
                "price": price,
                "close_positions": close_positions,
                "exchange": exchange,
                "margin_trade_type": margin_trade_type,
                "operation_class": kwargs.get("operation_class"),
            })
            return SubmissionResult(
                status=SubmissionStatus.ACCEPTED,
                intent_id="market-1",
                broker_order_id="ORDER-1",
                symbol=code,
                side=side,
                qty=shares,
                price=price,
                http_status=200,
            )

        broker._submit_market_order = fake_submit_market_order
        broker.get_order_details = lambda order_id: {
            "OrderId": "ORDER-1",
            "State": 5,
            "OrderQty": 100,
            "CumQty": 100,
            "Details": [
                {"RecType": 8, "State": 5, "Qty": 60, "Price": 1000.0, "ExecutionID": "EX-1"},
                {"RecType": 8, "State": 5, "Qty": 40, "Price": 1001.0, "ExecutionID": "EX-2"},
            ],
        }

        with patch("core.kabucom_broker.time.sleep", return_value=None), \
            patch("core.kabucom_broker.append_order_journal", side_effect=lambda event, path=None: journal_events.append(event)):
            result = broker.execute_chase_order("1234", 100, action=StockOrderAction.MARGIN_CLOSE_LONG, atr=10.0)

        self.assertEqual(len(call_args), 1)
        self.assertEqual(call_args[0]["close_positions"], [
            {"HoldID": "HOLD-1", "Qty": 60},
            {"HoldID": "HOLD-2", "Qty": 40},
        ])
        self.assertEqual(result["process_state"], OrderProcessState.TERMINAL.value)
        self.assertEqual(result["terminal_reason"], OrderTerminalReason.FILLED.value)
        self.assertFalse(result["unresolved"])
        self.assertEqual(result["execution_status"], "completed")
        self.assertEqual(result["exit_execution_status"], "completed")
        self.assertTrue(any(event.get("event") == "FILLED" for event in journal_events))

    def test_wait_for_execution_returns_unresolved_partial_fill_after_timeout(self):
        details_iter = iter([
            {
                "OrderId": "ORDER-1",
                "State": 3,
                "OrderQty": 100,
                "CumQty": 40,
                "Details": [
                    {"RecType": 8, "State": 3, "Qty": 25, "Price": 1000.0, "ExecutionID": "EX-1"},
                    {"RecType": 8, "State": 3, "Qty": 15, "Price": 1010.0, "ExecutionID": "EX-2"},
                ],
            },
        ])

        broker = _make_broker(_FakeSession([]))
        broker.get_order_details = lambda order_id: next(details_iter, None)
        broker.cancel_order = lambda order_id: False
        broker._confirm_terminal_order_state = lambda order_id, timeout_sec=5: None

        with patch("core.kabucom_broker.time.time", side_effect=[0.0, 0.1, 1.0]), \
            patch("core.kabucom_broker.time.sleep", return_value=None):
            result = broker.wait_for_execution("ORDER-1", timeout_sec=0.5)

        self.assertIsInstance(result, ExecutionWaitResult)
        self.assertTrue(result.unresolved)
        self.assertEqual(result.process_state, OrderProcessState.UNKNOWN)
        self.assertEqual(result.cumulative_qty, 40)
        self.assertEqual(result.remaining_qty, 60)
        self.assertEqual(len(result.fills), 2)
        self.assertEqual(result.execution_ids, ("EX-1", "EX-2"))
        self.assertAlmostEqual(result.average_price, (25 * 1000.0 + 15 * 1010.0) / 40)
        legacy = result.to_legacy_dict(symbol="1234", side="2")
        self.assertEqual(legacy["__parsed_process_state__"], OrderProcessState.UNKNOWN.value)
        self.assertEqual(legacy["__parsed_cumulative_qty__"], 40)
        self.assertEqual(legacy["Qty"], 40)
        self.assertAlmostEqual(legacy["Price"], (25 * 1000.0 + 15 * 1010.0) / 40)
        self.assertEqual(legacy["execution_status"], "partial_unresolved")
        self.assertEqual(legacy["entry_execution_status"], "partial_unresolved")

    def test_wait_for_execution_marks_unknown_state_as_unresolved(self):
        details_iter = iter([
            {
                "OrderId": "ORDER-2",
                "State": 4,
                "OrderQty": 100,
                "CumQty": 40,
                "Details": [
                    {"RecType": 8, "SeqNum": 1, "State": 3, "Qty": 25, "Price": 1000.0, "ExecutionID": "EX-1"},
                    {"RecType": 8, "SeqNum": 2, "State": 3, "Qty": 5, "Price": 1010.0, "ExecutionID": "EX-2"},
                ],
            },
        ])

        broker = _make_broker(_FakeSession([]))
        broker.get_order_details = lambda order_id: next(details_iter, None)
        broker.cancel_order = lambda order_id: False
        broker._confirm_terminal_order_state = lambda order_id, timeout_sec=5: None

        result = broker.wait_for_execution("ORDER-2", timeout_sec=30)

        self.assertIsInstance(result, ExecutionWaitResult)
        self.assertTrue(result.unresolved)
        self.assertEqual(result.unresolved_reason, "unknown_state")
        self.assertEqual(result.process_state, OrderProcessState.UNKNOWN)
        self.assertEqual(result.cumulative_qty, 40)
        self.assertEqual(result.remaining_qty, 60)
        self.assertEqual(len(result.fills), 2)
        legacy = result.to_legacy_dict(symbol="1234", side="2")
        self.assertEqual(legacy["__parsed_process_state__"], OrderProcessState.UNKNOWN.value)
        self.assertEqual(legacy["__parsed_cumulative_qty__"], 40)
        self.assertEqual(legacy["Qty"], 40)
        self.assertEqual(legacy["execution_status"], "partial_unresolved")
        self.assertEqual(legacy["entry_execution_status"], "partial_unresolved")

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
        self.assertNotIn("configured_risk_capital", snapshot)
        self.assertNotIn("realized_pnl_today", snapshot)
        self.assertFalse(snapshot["wallet_snapshot_incomplete"])

    def test_request_budget_is_tracked_by_endpoint_bucket(self):
        broker = _make_broker(_FakeSession([
            _FakeResponse(500, text="retry"),
            _FakeResponse(200, []),
            _FakeResponse(200, {"StockAccountWallet": 1.0}),
            _FakeResponse(200, {"MarginAccountWallet": 2.0}),
            _FakeResponse(200, {"ok": True}),
        ]))

        broker._api_request("GET", "orders")
        broker._api_request("GET", "wallet/cash")
        broker._api_request("GET", "wallet/margin")
        broker._api_request("GET", "register")

        self.assertGreaterEqual(broker.request_budget_counts[RequestBudgetBucket.ORDERS], 2)
        self.assertGreaterEqual(broker.request_budget_counts[RequestBudgetBucket.WALLET], 2)
        self.assertGreaterEqual(broker.request_budget_counts[RequestBudgetBucket.REGISTRY], 1)
        self.assertEqual(broker._classify_request_bucket("GET", "board/7203@1"), RequestBudgetBucket.MARKET_DATA)
        self.assertEqual(broker._classify_request_bucket("POST", "sendorder"), RequestBudgetBucket.ORDERS)
        self.assertEqual(broker._classify_request_bucket("PUT", "cancelorder"), RequestBudgetBucket.ORDERS)

    def test_auth_budget_is_tracked_when_authentication_runs(self):
        broker = _make_broker(_FakeSession([]))
        broker.token = None
        broker.password = "test-password"

        class _DummyLock:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        broker._auth_lock = _DummyLock()

        class _AuthResponse(_FakeResponse):
            pass

        def fake_post(url, headers=None, json=None, timeout=None):
            return _AuthResponse(200, {"Token": "TOKEN"})

        broker.session.post = fake_post
        broker._authenticate()

        self.assertGreaterEqual(broker.request_budget_counts[RequestBudgetBucket.AUTH], 1)

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

        with patch("core.portfolio_state.safe_read_json", return_value=None), \
            patch("core.portfolio_state.safe_read_csv", return_value=pd.DataFrame([
                {"code": "1234", "execution_id": "EX-1", "execution_ids": ["EX-1", "EX-2"], "buy_time": "2026-04-21 09:00:00", "highest_price": 1000.0, "partial_sold": False}
            ])):
            positions = broker.get_positions()

        self.assertEqual(positions[0]["ownership"], "MANAGED_BY_BOT")
        self.assertEqual(positions[0]["ownership_reason"], "matched_execution_id")

    def test_get_positions_live_marks_managed_by_bot_using_any_execution_id_in_execution_ids(self):
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
                "ExecutionID": "EX-2",
                "Exchange": 1,
                "MarginTradeType": 3,
            }
        ])

        with patch("core.portfolio_state.safe_read_json", return_value=None), \
            patch("core.portfolio_state.safe_read_csv", return_value=pd.DataFrame([
                {"code": "1234", "execution_id": "EX-1", "execution_ids": ["EX-1", "EX-2"], "buy_time": "2026-04-21 09:00:00", "highest_price": 1000.0, "partial_sold": False}
            ])):
            positions = broker.get_positions()

        self.assertEqual(positions[0]["ownership"], "MANAGED_BY_BOT")
        self.assertEqual(positions[0]["ownership_reason"], "matched_execution_id")

    def test_get_positions_live_uses_execution_id_specific_local_metadata_without_symbol_merge(self):
        broker = _make_broker(_FakeSession([]))
        broker.is_production = True
        broker._api_request = lambda *args, **kwargs: _FakeResponse(200, [
            {
                "Symbol": "1234",
                "SymbolName": "Foo-A",
                "CurrentPrice": 1000.0,
                "LeavesQty": 60,
                "HoldQty": 0,
                "Price": 900.0,
                "ExecutionID": "EX-1",
                "Exchange": 1,
                "MarginTradeType": 3,
            },
            {
                "Symbol": "1234",
                "SymbolName": "Foo-B",
                "CurrentPrice": 1000.0,
                "LeavesQty": 40,
                "HoldQty": 0,
                "Price": 910.0,
                "ExecutionID": "EX-2",
                "Exchange": 1,
                "MarginTradeType": 3,
            },
        ])

        with patch("core.portfolio_state.safe_read_json", return_value=None), \
            patch("core.portfolio_state.safe_read_csv", return_value=pd.DataFrame([
                {"code": "1234", "execution_id": "EX-1", "buy_time": "2026-04-21 09:00:00", "highest_price": 1100.0, "partial_sold": False},
                {"code": "1234", "execution_id": "EX-2", "buy_time": "2026-04-21 09:05:00", "highest_price": 1200.0, "partial_sold": True},
            ])):
            positions = broker.get_positions()

        self.assertEqual(len(positions), 2)
        self.assertEqual(positions[0]["execution_id"], "EX-1")
        self.assertEqual(positions[0]["buy_time"], "2026-04-21 09:00:00")
        self.assertEqual(positions[0]["highest_price"], 1100.0)
        self.assertEqual(positions[0]["ownership"], "MANAGED_BY_BOT")
        self.assertEqual(positions[1]["execution_id"], "EX-2")
        self.assertEqual(positions[1]["buy_time"], "2026-04-21 09:05:00")
        self.assertEqual(positions[1]["highest_price"], 1200.0)
        self.assertEqual(positions[1]["ownership"], "MANAGED_BY_BOT")

    def test_get_positions_live_preserves_unknown_hold_qty_and_blocks_close_allocation(self):
        broker = _make_broker(_FakeSession([]))
        broker.is_production = True
        broker._api_request = lambda *args, **kwargs: _FakeResponse(200, [
            {
                "Symbol": "1234",
                "SymbolName": "Foo",
                "CurrentPrice": 1000.0,
                "LeavesQty": 100,
                "HoldQty": None,
                "Price": 900.0,
                "ExecutionID": "EX-1",
                "Exchange": 1,
                "MarginTradeType": 3,
            }
        ])

        with patch("core.portfolio_state.safe_read_json", return_value=None), \
            patch("core.portfolio_state.safe_read_csv", return_value=pd.DataFrame([
                {"code": "1234", "execution_id": "EX-1", "buy_time": "2026-04-21 09:00:00", "highest_price": 1000.0, "partial_sold": False}
            ])):
            positions = broker.get_positions()

        self.assertIsNone(positions[0]["hold_qty"])
        self.assertIsNone(positions[0]["available_qty"])

        broker.get_positions = lambda: positions
        self.assertIsNone(broker._build_close_positions_for_symbol("1234", 50))

    def test_build_close_positions_for_symbol_filters_by_execution_id_set(self):
        broker = _make_broker(_FakeSession([]))
        broker.get_positions = lambda: [
            {"code": "1234", "hold_id": "HOLD-1", "exchange": 1, "margin_trade_type": 3, "leaves_qty": 60, "hold_qty": 0, "available_qty": 60, "buy_time": "2026-04-21 09:00:00", "execution_id": "EX-1", "ownership": "MANAGED_BY_BOT"},
            {"code": "1234", "hold_id": "HOLD-2", "exchange": 1, "margin_trade_type": 3, "leaves_qty": 40, "hold_qty": 0, "available_qty": 40, "buy_time": "2026-04-21 09:01:00", "execution_id": "EX-2", "ownership": "MANAGED_BY_BOT"},
        ]

        route = broker._build_close_positions_for_symbol("1234", 40, managed_execution_ids={"EX-2"})

        self.assertIsNotNone(route)
        self.assertEqual(route["exchange"], 1)
        self.assertEqual(route["margin_trade_type"], 3)
        self.assertEqual(route["close_positions"], [{"HoldID": "HOLD-2", "Qty": 40}])

    def test_cancel_order_writes_order_journal(self):
        journal_events = []
        captured_cancel = {}

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
            if endpoint == "cancelorder":
                captured_cancel["json"] = kwargs["json"]
            return next(responses)

        def fake_append(event, path=None):
            journal_events.append(event)

        broker = _make_broker(_FakeSession([]))
        broker._api_request = fake_api_request

        with patch("core.kabucom_broker.append_order_journal", side_effect=fake_append):
            result = broker.cancel_order("ORDER-1")

        self.assertIsInstance(result, CancelResult)
        self.assertEqual(result.status, CancelStatus.ACCEPTED)
        self.assertTrue(result.confirmed)
        self.assertFalse(result)
        self.assertEqual(result.terminal_status, CancelTerminalStatus.FILLED_BEFORE_CANCEL)
        self.assertEqual(result.terminal_reason, OrderTerminalReason.FILLED)
        self.assertEqual(result.order_id, "ORDER-1")
        self.assertEqual(result.cumulative_qty, 100)
        self.assertEqual(result.remaining_qty, 0)
        self.assertIsNotNone(result.parsed_order)
        self.assertGreaterEqual(len(journal_events), 2)
        self.assertEqual(journal_events[0]["event"], "CANCEL_REQUESTED")
        self.assertEqual(journal_events[1]["event"], "FILLED_BEFORE_CANCEL")
        self.assertEqual(captured_cancel["json"]["OrderID"], "ORDER-1")
        self.assertNotIn("OrderId", captured_cancel["json"])

    def test_cancel_order_marks_filled_before_cancel_as_terminal_and_not_successful(self):
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

        broker = _make_broker(_FakeSession([]))
        broker._api_request = lambda *args, **kwargs: next(responses)

        result = broker.cancel_order("ORDER-1")

        self.assertEqual(result.status, CancelStatus.ACCEPTED)
        self.assertTrue(result.confirmed)
        self.assertEqual(result.terminal_status, CancelTerminalStatus.FILLED_BEFORE_CANCEL)
        self.assertEqual(result.terminal_reason, OrderTerminalReason.FILLED)
        self.assertFalse(result)
        self.assertEqual(result.rejection_reason, "filled_before_cancel")

    def test_cancel_order_uses_order_password_when_separate_from_api_password(self):
        captured = {}

        def fake_api_request(method, endpoint, **kwargs):
            if endpoint == "cancelorder":
                captured["json"] = kwargs["json"]
            return _FakeResponse(200, {"Result": 0, "OrderId": "ORDER-1"})

        broker = _make_broker(_FakeSession([]))
        broker.password = "api-secret"
        broker.order_password = "order-secret"
        broker._api_request = fake_api_request
        broker._confirm_terminal_order_state = lambda *args, **kwargs: None

        result = broker.cancel_order("ORDER-1")

        self.assertEqual(captured["json"]["Password"], "order-secret")
        self.assertEqual(result.status, CancelStatus.UNKNOWN)

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
             patch("core.kabu_launcher.time.monotonic", side_effect=[0.0, 0.01, 0.02, 0.2]):
            self.assertTrue(_wait_for_api_server(timeout_sec=0.1, silent=True))

        self.assertIn("/kabusapi/board/7203@1", mocked_get.call_args.args[0])

    def test_check_api_health_requires_authenticated_token(self):
        with patch("core.kabu_launcher.KABUCOM_API_PASSWORD", "secret"), \
            patch("core.kabu_launcher.requests.get", return_value=_FakeResponse(401)), \
            patch("core.kabu_launcher.requests.post", return_value=_FakeResponse(200, {"Token": None})), \
            patch("core.kabu_launcher.time.sleep", return_value=None), \
            patch("core.kabu_launcher.time.monotonic", side_effect=[0.0, 0.01, 3.0, 3.01, 5.5]):
            self.assertFalse(check_api_health())

    def test_get_server_time_uses_wallet_date_header_instead_of_symbol_endpoint(self):
        broker = _make_broker(_FakeSession([]))

        class _ResponseWithDate(_FakeResponse):
            def __init__(self):
                super().__init__(200, {"StockAccountWallet": 0.0}, headers={"Date": "Tue, 21 Apr 2026 00:00:00 GMT"})

        broker._api_request = lambda *args, **kwargs: _ResponseWithDate()
        current_time = broker.get_server_time()

        self.assertEqual(getattr(current_time.tzinfo, "key", None), "Asia/Tokyo")
        self.assertEqual(current_time.hour, 9)
        self.assertEqual(current_time.day, 21)

    def test_log_trade_appends_rows_instead_of_overwriting_history(self):
        broker = _make_broker(_FakeSession([]))
        trade_record = {"code": "1234", "shares": 100, "pnl": 123.0}

        with patch("core.kabucom_broker.append_csv_rows") as mocked_append:
            broker.log_trade(trade_record)

        mocked_append.assert_called_once()

    def test_save_positions_includes_broker_context_metadata(self):
        broker = _make_broker(_FakeSession([]))
        broker._environment = BrokerEnvironment.LIVE
        captured = {}

        def fake_write(path, portfolio, metadata=None):
            captured["path"] = path
            captured["portfolio"] = portfolio
            captured["metadata"] = metadata

        with patch("core.kabucom_broker.write_portfolio_state", side_effect=fake_write):
            broker.save_positions([{"code": "1234", "execution_id": "EX-1"}])

        self.assertIn("metadata", captured)
        self.assertEqual(captured["metadata"]["source"], "kabucom_broker")
        self.assertEqual(captured["metadata"]["broker_environment"], "live")
        self.assertEqual(captured["metadata"]["broker_account_type"], 4)
        self.assertEqual(captured["metadata"]["broker_product"], "margin")

    def test_simulation_broker_log_trade_appends_rows(self):
        broker = SimulationBroker()
        trade_record = {"code": "1234", "shares": 100, "pnl": 123.0}

        with patch("core.sim_broker.append_csv_rows") as mocked_append:
            broker.log_trade(trade_record)

        mocked_append.assert_called_once()

    def test_simulation_broker_save_positions_includes_simulation_metadata(self):
        broker = SimulationBroker()
        captured = {}

        def fake_write(path, portfolio, metadata=None):
            captured["path"] = path
            captured["portfolio"] = portfolio
            captured["metadata"] = metadata

        with patch("core.sim_broker.write_portfolio_state", side_effect=fake_write):
            broker.save_positions([{"code": "1234", "execution_id": "EX-1"}])

        self.assertIn("metadata", captured)
        self.assertEqual(captured["metadata"]["source"], "simulation_broker")
        self.assertEqual(captured["metadata"]["broker_environment"], "simulation")
        self.assertEqual(captured["metadata"]["broker_product"], "simulation")


if __name__ == "__main__":
    unittest.main()
