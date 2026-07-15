from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from core.config import JST
from core.daytrade_opening_discovery import (
    DAYTRADE_DISCOVERY_MAX_SPAN_SECONDS,
    collect_daytrade_opening_discovery,
    plan_daytrade_discovery_batches,
    serialize_daytrade_opening_discovery_result,
)
from core.daytrade_observation_universe import DAYTRADE_DISCOVERY_MAX_SYMBOLS


class _Clock:
    def __init__(self, step_seconds=1):
        self.current = datetime(2026, 7, 15, 9, 30, tzinfo=JST)
        self.step = timedelta(seconds=step_seconds)

    def __call__(self):
        value = self.current
        self.current += self.step
        return value


class _Broker:
    def __init__(
        self,
        registered=("1321",),
        *,
        fail_register_batch=None,
        fail_unregister_batch=None,
        board_failure_code=None,
    ):
        self.registered = set(registered)
        self.fail_register_batch = fail_register_batch
        self.fail_unregister_batch = fail_unregister_batch
        self.board_failure_code = board_failure_code
        self.register_count = 0
        self.unregister_count = 0
        self.calls = []

    def register_symbols(self, symbols):
        codes = tuple(str(code) for code in symbols)
        self.calls.append(("register", codes))
        call_index = self.register_count
        self.register_count += 1
        if call_index == self.fail_register_batch:
            self.registered.update(codes[:1])
            return False
        self.registered.update(codes)
        return True

    def unregister_symbols(self, symbols):
        codes = tuple(str(code) for code in symbols)
        self.calls.append(("unregister", codes))
        call_index = self.unregister_count
        self.unregister_count += 1
        if call_index == self.fail_unregister_batch:
            return False
        self.registered.difference_update(codes)
        return True

    def get_board_snapshot_batch(self, symbols):
        codes = tuple(str(code) for code in symbols)
        self.calls.append(("board", codes))
        observations = {
            code: {"symbol": code, "open": 100.0}
            for code in codes
            if code != self.board_failure_code
        }
        failures = {}
        if self.board_failure_code in codes:
            failures[self.board_failure_code] = SimpleNamespace(reason="http")
        return SimpleNamespace(
            requested=codes,
            observations=observations,
            failures=failures,
        )


def test_discovery_plan_is_exactly_four_batches_and_excludes_protected_codes():
    symbols = ["1321", *(f"{1000 + index}.T" for index in range(196)), "1000"]
    batches = plan_daytrade_discovery_batches(symbols)

    assert tuple(len(batch) for batch in batches) == (49, 49, 49, 49)
    assert len({code for batch in batches for code in batch}) == 196
    assert "1321" not in {code for batch in batches for code in batch}

    with pytest.raises(ValueError, match="maximum is 196"):
        plan_daytrade_discovery_batches(str(2000 + index) for index in range(197))


def test_discovery_collects_all_batches_and_restores_only_protected_registry():
    broker = _Broker(registered=("1321", "9999"))
    symbols = [str(1000 + index) for index in range(DAYTRADE_DISCOVERY_MAX_SYMBOLS)]

    result = collect_daytrade_opening_discovery(
        broker,
        symbols,
        initial_registered_codes=("1321", "9999"),
        clock=_Clock(),
    )

    assert result.success
    assert result.registry_clean
    assert len(result.observations) == DAYTRADE_DISCOVERY_MAX_SYMBOLS + 1
    assert len(result.batches) == 4
    assert result.final_registered_codes == ("1321",)
    assert broker.registered == {"1321"}
    assert broker.calls[0] == ("unregister", ("9999",))
    assert all(batch.register_ok and batch.unregister_ok for batch in result.batches)


def test_discovery_register_failure_attempts_cleanup_and_stops_fail_closed():
    broker = _Broker(fail_register_batch=0)
    result = collect_daytrade_opening_discovery(
        broker,
        ["1000", "2000"],
        initial_registered_codes=("1321",),
        clock=_Clock(),
    )

    assert not result.success
    assert "batch_0:register_failed" in result.rejection_reasons
    assert result.final_registered_codes == ("1321",)
    assert [call[0] for call in broker.calls] == ["board", "register", "unregister"]


def test_discovery_board_or_unregister_failure_never_returns_success():
    board_failure = collect_daytrade_opening_discovery(
        _Broker(board_failure_code="2000"),
        ["1000", "2000"],
        initial_registered_codes=("1321",),
        clock=_Clock(),
    )
    dirty_registry = collect_daytrade_opening_discovery(
        _Broker(fail_unregister_batch=0),
        ["1000", "2000"],
        initial_registered_codes=("1321",),
        clock=_Clock(),
    )

    assert not board_failure.success
    assert "discovery_board_failures" in board_failure.rejection_reasons
    assert not dirty_registry.success
    assert "discovery_registry_dirty" in dirty_registry.rejection_reasons


def test_discovery_board_exception_still_unregisters_batch_and_fails_closed():
    class BoardRaises(_Broker):
        def get_board_snapshot_batch(self, symbols):
            codes = tuple(str(code) for code in symbols)
            if codes == ("1321",):
                return super().get_board_snapshot_batch(symbols)
            self.calls.append(("board", codes))
            raise RuntimeError("transport failed")

    broker = BoardRaises()
    result = collect_daytrade_opening_discovery(
        broker,
        ["1000", "2000"],
        initial_registered_codes=("1321",),
        clock=_Clock(),
    )

    assert not result.success
    assert "batch_0:board_exception" in result.rejection_reasons
    assert result.registry_clean
    assert result.final_registered_codes == ("1321",)
    assert [call[0] for call in broker.calls] == [
        "board", "register", "board", "unregister"
    ]


def test_discovery_register_exception_attempts_full_batch_cleanup():
    class RegisterRaises(_Broker):
        def register_symbols(self, symbols):
            codes = tuple(str(code) for code in symbols)
            self.calls.append(("register", codes))
            self.registered.add(codes[0])
            raise RuntimeError("unknown partial registration")

    broker = RegisterRaises()
    result = collect_daytrade_opening_discovery(
        broker,
        ["1000", "2000"],
        initial_registered_codes=("1321",),
        clock=_Clock(),
    )

    assert not result.success
    assert "batch_0:register_failed" in result.rejection_reasons
    assert result.final_registered_codes == ("1321",)
    assert [call[0] for call in broker.calls] == ["board", "register", "unregister"]


def test_discovery_rejects_board_request_contract_mismatch():
    class RequestMismatch(_Broker):
        def get_board_snapshot_batch(self, symbols):
            result = super().get_board_snapshot_batch(symbols)
            result.requested = result.requested[:1]
            return result

    result = collect_daytrade_opening_discovery(
        RequestMismatch(),
        ["1000", "2000"],
        initial_registered_codes=("1321",),
        clock=_Clock(),
    )

    assert not result.success
    assert "batch_0:board_request_mismatch" in result.rejection_reasons


def test_discovery_rejects_over_30_second_capture_span():
    result = collect_daytrade_opening_discovery(
        _Broker(),
        ["1000"],
        initial_registered_codes=("1321",),
        clock=_Clock(step_seconds=DAYTRADE_DISCOVERY_MAX_SPAN_SECONDS),
    )

    assert not result.success

    assert "discovery_span_exceeded" in result.rejection_reasons

def test_discovery_protected_board_failure_stops_before_rotation():
    result = collect_daytrade_opening_discovery(
        _Broker(board_failure_code="1321"),
        ["1000", "2000"],
        initial_registered_codes=("1321",),
        clock=_Clock(),
    )

    assert not result.success
    assert result.batches == ()
    assert result.protected_board.failures == ("1321",)
    assert "protected_observations_missing:1321" in result.rejection_reasons


def test_discovery_evidence_serializes_protected_and_rotating_batches():
    result = collect_daytrade_opening_discovery(
        _Broker(),
        [str(1000 + index) for index in range(DAYTRADE_DISCOVERY_MAX_SYMBOLS)],
        initial_registered_codes=("1321",),
        clock=_Clock(),
    )

    evidence = serialize_daytrade_opening_discovery_result(result)

    assert evidence["protected_board"]["requested"] == ["1321"]
    assert evidence["protected_board"]["observed"] == ["1321"]
    assert len(evidence["batches"]) == 4
    assert sum(len(batch["requested"]) for batch in evidence["batches"]) == 196
    assert evidence["final_registered_codes"] == ["1321"]
    assert evidence["rejection_reasons"] == []
