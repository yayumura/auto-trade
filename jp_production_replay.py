import argparse
import ast
import csv
from datetime import datetime, timedelta
from hashlib import sha256
import math
import os

from core.config import (
    DAYTRADE_DECISION_LOG_FILE,
    DAYTRADE_EXIT_LOG_FILE,
    DAYTRADE_PRODUCTION_SNAPSHOT_FILE,
    ORDER_JOURNAL_FILE,
    RUNTIME_LIVE_ORDER_CONFIG_HASH,
)
from core.daytrade_production_replay import (
    load_daytrade_production_snapshots,
    replay_daytrade_production_snapshot,
)
from core.logic import (
    normalize_tick_size,
    resolve_daytrade_entry_risk_envelope,
)
from core.live_approval_manifest import read_git_commit_sha
from core.order_journal import load_order_journal_events


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Replay point-in-time daytrade production snapshots with the shared "
            "candidate engine and report actual linked exits."
        )
    )
    parser.add_argument(
        "--snapshots-file",
        default=DAYTRADE_PRODUCTION_SNAPSHOT_FILE,
    )
    parser.add_argument(
        "--exit-log",
        default=DAYTRADE_EXIT_LOG_FILE,
    )
    parser.add_argument(
        "--decision-log",
        default=DAYTRADE_DECISION_LOG_FILE,
    )
    parser.add_argument(
        "--order-journal",
        default=ORDER_JOURNAL_FILE,
    )
    parser.add_argument(
        "--trade-mode",
        default="KABUCOM_LIVE",
        choices=("KABUCOM_LIVE", "KABUCOM_TEST"),
    )
    parser.add_argument(
        "--min-snapshots",
        type=int,
        default=1,
        help="Operational completeness threshold only; it is not a profitability proof.",
    )
    parser.add_argument(
        "--allow-incomplete-lifecycle",
        action="store_true",
        help="Report signal parity without failing on missing linked order lifecycle evidence.",
    )
    return parser.parse_args()


def _as_bool(value):
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def _load_linked_exits(path, snapshot_ids):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("decision_snapshot_id") not in snapshot_ids:
                continue
            if _as_bool(row.get("is_simulation")):
                continue
            rows.append(row)
    return rows


def _load_linked_decisions(path, snapshot_ids, trade_mode):
    if not path or not os.path.exists(path):
        return []
    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("decision_snapshot_id") not in snapshot_ids:
                continue
            if _as_bool(row.get("is_simulation")):
                continue
            if str(row.get("trade_mode") or "").upper() != trade_mode:
                continue
            rows.append(row)
    return rows


def _load_linked_order_events(path, snapshot_ids):
    if not path:
        return []
    return [
        event
        for event in load_order_journal_events(path)
        if str(event.get("decision_snapshot_id") or "") in snapshot_ids
    ]


def _remaining_shares_is_zero(row):
    value = row.get("remaining_shares")
    if value in (None, ""):
        return False
    try:
        return int(float(value)) == 0
    except (TypeError, ValueError):
        return False


def _finite_float(value):
    if value in (None, ""):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _actual_cost_evidence_reasons(row):
    reasons = []
    if str(row.get("actual_cost_evidence_schema_version") or "") != "1":
        reasons.append("actual_cost_schema_invalid")
    if not _as_bool(row.get("actual_cost_evidence_complete")):
        reasons.append("actual_cost_flag_incomplete")
    if str(row.get("actual_cost_evidence_reason") or "").strip():
        reasons.append("actual_cost_reason_present")

    costs = {}
    for field in (
        "entry_commission",
        "entry_commission_tax",
        "position_expenses",
        "exit_commission",
        "exit_commission_tax",
    ):
        value = _finite_float(row.get(field))
        if value is None or value < 0:
            reasons.append(f"{field}_invalid")
        else:
            costs[field] = value

    gross = _finite_float(row.get("observed_gross_pnl"))
    execution_net = _finite_float(row.get("observed_execution_net_pnl"))
    total_cost = _finite_float(row.get("actual_total_cost"))
    buy_price = _finite_float(row.get("buy_price"))
    observed_price = _finite_float(row.get("observed_price"))
    held_shares = _finite_float(row.get("held_shares"))
    filled_shares = _finite_float(row.get("filled_shares"))
    remaining_shares = _finite_float(row.get("remaining_shares"))
    for field, value in (
        ("buy_price", buy_price),
        ("observed_price", observed_price),
    ):
        if value is None or value <= 0:
            reasons.append(f"{field}_invalid")
    for field, value in (
        ("held_shares", held_shares),
        ("filled_shares", filled_shares),
        ("remaining_shares", remaining_shares),
    ):
        if value is None or value < 0 or int(value) != value:
            reasons.append(f"{field}_invalid")
    if (
        held_shares is not None
        and filled_shares is not None
        and int(held_shares) != int(filled_shares)
    ):
        reasons.append("exit_fill_qty_mismatch")
    if remaining_shares is not None and int(remaining_shares) != 0:
        reasons.append("exit_remaining_shares_nonzero")
    if _as_bool(row.get("is_partial_fill")):
        reasons.append("exit_marked_partial")
    if (
        gross is not None
        and buy_price is not None
        and observed_price is not None
        and filled_shares is not None
    ):
        expected_gross = (observed_price - buy_price) * filled_shares
        rounding_tolerance = max(0.02, filled_shares * 0.000051)
        if abs(gross - expected_gross) > rounding_tolerance:
            reasons.append("observed_gross_pnl_price_qty_mismatch")
    if gross is None:
        reasons.append("observed_gross_pnl_invalid")
    if execution_net is None:
        reasons.append("observed_execution_net_pnl_invalid")
    if total_cost is None or total_cost < 0:
        reasons.append("actual_total_cost_invalid")
    if len(costs) == 5 and total_cost is not None:
        expected_cost = sum(costs.values())
        if abs(total_cost - expected_cost) > 0.02:
            reasons.append("actual_total_cost_mismatch")
    if gross is not None and execution_net is not None and total_cost is not None:
        if abs(execution_net - (gross - total_cost)) > 0.02:
            reasons.append("observed_execution_net_pnl_mismatch")
    return reasons


def _actual_net_evidence_reasons(row):
    reasons = []
    if _actual_cost_evidence_reasons(row):
        reasons.append("actual_cost_evidence_incomplete")
    if not _as_bool(row.get("actual_net_pnl_evidence_complete")):
        reasons.append("actual_net_flag_incomplete")
    if not _as_bool(row.get("capital_gains_tax_evidence_complete")):
        reasons.append("capital_gains_tax_flag_incomplete")
    capital_gains_tax = _finite_float(row.get("capital_gains_tax"))
    execution_net = _finite_float(row.get("observed_execution_net_pnl"))
    net = _finite_float(row.get("observed_net_pnl"))
    if capital_gains_tax is None or capital_gains_tax < 0:
        reasons.append("capital_gains_tax_invalid")
    if execution_net is None:
        reasons.append("observed_execution_net_pnl_invalid")
    if net is None:
        reasons.append("observed_net_pnl_invalid")
    if execution_net is not None and net is not None and capital_gains_tax is not None:
        if abs(net - (execution_net - capital_gains_tax)) > 0.02:
            reasons.append("observed_net_pnl_mismatch")
    return reasons


def _sha256_text(value):
    return f"sha256:{sha256(str(value or '').encode('utf-8')).hexdigest()}"


def _first_ai_token(raw_response):
    lines = [
        line.strip().upper()
        for line in str(raw_response or "").splitlines()
        if line.strip()
    ]
    if not lines:
        return None
    return lines[0].split(maxsplit=1)[0].rstrip(":：")


def _operational_evidence_reasons(row):
    reasons = []
    if str(row.get("operational_evidence_schema_version") or "") != "1":
        reasons.append("operational_evidence_schema_invalid")

    news_status = str(row.get("news_fetch_status") or "")
    news_text = str(row.get("news_text") or "")
    news_error = str(row.get("news_error") or "")
    if not str(row.get("news_query_url") or ""):
        reasons.append("news_query_url_missing")
    if str(row.get("news_sha256") or "") != _sha256_text(news_text):
        reasons.append("news_hash_mismatch")

    ai_outcome = str(row.get("ai_outcome") or "")
    ai_prompt = str(row.get("ai_prompt") or "")
    ai_raw_response = str(row.get("ai_raw_response") or "")
    ai_error = str(row.get("ai_error") or "")
    if str(row.get("ai_prompt_sha256") or "") != _sha256_text(ai_prompt):
        reasons.append("ai_prompt_hash_mismatch")
    if str(row.get("ai_raw_response_sha256") or "") != _sha256_text(ai_raw_response):
        reasons.append("ai_raw_response_hash_mismatch")

    if news_status == "error":
        if not news_error:
            reasons.append("news_error_missing")
        if news_text:
            reasons.append("news_error_contains_news_text")
        if ai_outcome != "not_requested_news_fetch_failed":
            reasons.append("news_error_ai_outcome_mismatch")
    elif news_status == "no_news":
        if news_text:
            reasons.append("no_news_contains_news_text")
        if ai_outcome != "not_requested_no_news":
            reasons.append("no_news_ai_outcome_mismatch")
    elif news_status == "ok":
        if not news_text:
            reasons.append("news_text_missing")
        if not str(row.get("ai_provider") or ""):
            reasons.append("ai_provider_missing")
        if not str(row.get("ai_model") or ""):
            reasons.append("ai_model_missing")
        if not ai_prompt:
            reasons.append("ai_prompt_missing")
        if ai_outcome in {"approved", "blocked_adverse_news"}:
            if not ai_raw_response:
                reasons.append("ai_raw_response_missing")
            expected = "NO" if ai_outcome == "approved" else "YES"
            if _first_ai_token(ai_raw_response) != expected:
                reasons.append("ai_outcome_raw_response_mismatch")
        elif ai_outcome in {
            "blocked_ai_invalid_response",
            "blocked_ai_unavailable",
            "blocked_ai_timeout",
        }:
            if not ai_error:
                reasons.append("ai_error_missing")
        else:
            reasons.append("ai_outcome_invalid")
    else:
        reasons.append("news_fetch_status_invalid")

    decision = str(row.get("decision") or "")
    reason = str(row.get("reason") or "")
    if decision == "operational_review_passed" and ai_outcome not in {
        "approved",
        "not_requested_no_news",
    }:
        reasons.append("operational_pass_outcome_mismatch")
    if decision == "blocked_operational_veto":
        if reason.startswith("news_fetch:") and ai_outcome != "not_requested_news_fetch_failed":
            reasons.append("news_block_outcome_mismatch")
        if reason.startswith("ai_filter:") and ai_outcome in {
            "approved",
            "not_requested_no_news",
        }:
            reasons.append("ai_block_outcome_mismatch")
    return reasons


def _strict_jst_datetime(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(hours=9):
        return None
    return parsed


def _entry_quote_evidence_reasons(row):
    reasons = []
    if str(row.get("entry_quote_evidence_schema_version") or "") != "1":
        reasons.append("entry_quote_evidence_schema_invalid")

    decision = str(row.get("decision") or "")
    status = str(row.get("entry_quote_status") or "")
    evidence_reason = str(row.get("entry_quote_reason") or "")
    code = str(row.get("code") or "")
    if str(row.get("entry_quote_code") or "") != code:
        reasons.append("entry_quote_code_mismatch")
    if decision == "entry_quote_refresh_passed":
        if status != "fresh":
            reasons.append("entry_quote_pass_status_mismatch")
        if evidence_reason:
            reasons.append("entry_quote_pass_has_rejection_reason")
    elif decision == "blocked_entry_quote_refresh":
        if status != "rejected":
            reasons.append("entry_quote_block_status_mismatch")
        if not evidence_reason:
            reasons.append("entry_quote_block_reason_missing")
    else:
        reasons.append("entry_quote_decision_invalid")

    max_batch_span = _finite_float(row.get("entry_quote_max_batch_span_seconds"))
    max_age = _finite_float(row.get("entry_quote_max_age_seconds"))
    if max_batch_span is None or abs(max_batch_span - 5.0) > 0.001:
        reasons.append("entry_quote_max_batch_span_invalid")
    if max_age is None or abs(max_age - 30.0) > 0.001:
        reasons.append("entry_quote_max_age_invalid")

    timestamp_fields = {
        "started": "entry_quote_batch_started_at",
        "completed": "entry_quote_batch_completed_at",
        "price": "entry_quote_price_timestamp",
        "received": "entry_quote_received_at",
    }
    raw_timestamps = {
        name: str(row.get(field) or "").strip()
        for name, field in timestamp_fields.items()
    }
    timestamps = {
        name: _strict_jst_datetime(value)
        for name, value in raw_timestamps.items()
    }
    if status == "fresh":
        for name in timestamp_fields:
            if timestamps[name] is None:
                reasons.append(f"entry_quote_{name}_timestamp_invalid")
    else:
        for name, raw_value in raw_timestamps.items():
            if raw_value and timestamps[name] is None:
                reasons.append(f"entry_quote_{name}_timestamp_invalid")

    started_at = timestamps["started"]
    completed_at = timestamps["completed"]
    received_at = timestamps["received"]
    price_timestamp = timestamps["price"]
    batch_span = _finite_float(row.get("entry_quote_batch_span_seconds"))
    if started_at is not None and completed_at is not None:
        expected_span = (completed_at - started_at).total_seconds()
        if batch_span is None or abs(batch_span - expected_span) > 0.02:
            reasons.append("entry_quote_batch_span_mismatch")
        if expected_span < 0:
            reasons.append("entry_quote_batch_time_reversed")
        elif max_batch_span is not None and expected_span > max_batch_span:
            reasons.append("entry_quote_batch_span_exceeded")
    elif status == "fresh":
        reasons.append("entry_quote_batch_timestamp_incomplete")

    transport_age = _finite_float(row.get("entry_quote_transport_age_seconds"))
    if received_at is not None and started_at is not None and completed_at is not None:
        expected_transport = (completed_at - received_at).total_seconds()
        if transport_age is None or abs(transport_age - expected_transport) > 0.02:
            reasons.append("entry_quote_transport_age_mismatch")
        if received_at < started_at or received_at > completed_at:
            reasons.append("entry_quote_received_at_outside_batch")
    elif status == "fresh":
        reasons.append("entry_quote_received_at_incomplete")

    quote_age = _finite_float(row.get("entry_quote_age_seconds"))
    if price_timestamp is not None and completed_at is not None:
        expected_age = (completed_at - price_timestamp).total_seconds()
        if quote_age is None or abs(quote_age - expected_age) > 0.02:
            reasons.append("entry_quote_age_mismatch")
        if price_timestamp.date() != completed_at.date():
            reasons.append("entry_quote_cross_day")
        elif expected_age < -60:
            reasons.append("entry_quote_timestamp_future")
        elif max_age is not None and expected_age > max_age:
            reasons.append("entry_quote_stale")
    elif status == "fresh":
        reasons.append("entry_quote_price_timestamp_incomplete")

    source = str(row.get("entry_quote_price_timestamp_source") or "")
    if status == "fresh" and source not in {
        "bid_timestamp",
        "quote_timestamp",
        "current_price_timestamp",
    }:
        reasons.append("entry_quote_price_timestamp_source_invalid")

    current_price = _finite_float(row.get("entry_quote_current_price"))
    best_sell_price = _finite_float(row.get("entry_quote_best_sell_price"))
    if status == "fresh":
        if current_price is None or current_price <= 0:
            reasons.append("entry_quote_current_price_invalid")
        if best_sell_price is None or best_sell_price <= 0:
            reasons.append("entry_quote_best_sell_price_invalid")
    return reasons

def _entry_risk_evidence_reasons(row, entry_quote_rows_by_code=None):
    reasons = []
    if str(row.get("entry_risk_evidence_schema_version") or "") != "1":
        reasons.append("entry_risk_evidence_schema_invalid")
    code = str(row.get("code") or "")
    if str(row.get("entry_risk_code") or "") != code:
        reasons.append("entry_risk_code_mismatch")

    numeric_fields = {
        "current_equity": "entry_risk_current_equity",
        "theoretical_buying_power": "entry_risk_theoretical_buying_power",
        "wallet_margin_buying_power": "entry_risk_wallet_margin_buying_power",
        "buying_power": "entry_risk_buying_power",
        "dynamic_leverage": "entry_risk_dynamic_leverage",
        "quote_price": "entry_risk_quote_price",
        "sizing_price": "entry_risk_sizing_price",
        "stop_price": "entry_risk_stop_price",
        "turnover": "entry_risk_turnover",
        "max_positions": "entry_risk_max_positions",
        "raw_shares": "entry_risk_raw_shares",
        "shares": "entry_risk_shares",
        "max_entry_price": "entry_risk_max_entry_price",
    }
    values = {
        name: _finite_float(row.get(field))
        for name, field in numeric_fields.items()
    }
    for name, value in values.items():
        if value is None:
            reasons.append(f"entry_risk_{name}_invalid")
    if any(value is None for value in values.values()):
        return reasons

    if abs(
        values["buying_power"]
        - min(
            values["theoretical_buying_power"],
            values["wallet_margin_buying_power"],
        )
    ) > 0.02:
        reasons.append("entry_risk_wallet_cap_mismatch")

    if entry_quote_rows_by_code is not None:
        quote_row = entry_quote_rows_by_code.get(code)
        if quote_row is None:
            reasons.append("entry_risk_quote_evidence_missing")
        else:
            quote_status = str(quote_row.get("entry_quote_status") or "")
            quote_best_sell = _finite_float(
                quote_row.get("entry_quote_best_sell_price")
            )
            if quote_status != "fresh":
                reasons.append("entry_risk_quote_not_fresh")
            if (
                quote_best_sell is None
                or abs(values["quote_price"] - quote_best_sell) > 0.001
            ):
                reasons.append("entry_risk_quote_price_mismatch")

    normalized_sizing_price = normalize_tick_size(
        values["quote_price"],
        is_buy=True,
    )
    if abs(values["sizing_price"] - normalized_sizing_price) > 0.001:
        reasons.append("entry_risk_sizing_price_mismatch")

    def optional_float(field):
        raw_value = row.get(field)
        if raw_value in (None, ""):
            return None
        return _finite_float(raw_value)

    notional_pct = optional_float("entry_risk_notional_pct")
    equity_notional_pct = optional_float("entry_risk_equity_notional_pct")
    risk_budget_pct = optional_float("entry_risk_risk_budget_pct")
    size_multiplier = optional_float("entry_risk_size_multiplier")
    envelope = resolve_daytrade_entry_risk_envelope(
        current_equity=values["current_equity"],
        buying_power=values["buying_power"],
        entry_price=values["sizing_price"],
        stop_price=values["stop_price"],
        dynamic_leverage=values["dynamic_leverage"],
        max_positions=int(values["max_positions"]),
        turnover=values["turnover"],
        notional_pct=notional_pct,
        equity_notional_pct=equity_notional_pct,
        risk_budget_pct=risk_budget_pct,
        size_multiplier=size_multiplier,
    )
    recorded_status = str(row.get("entry_risk_status") or "")
    recorded_reason = str(row.get("entry_risk_reason") or "")
    if recorded_status != str(envelope.get("status") or ""):
        reasons.append("entry_risk_status_mismatch")
    if recorded_reason != str(envelope.get("reason") or ""):
        reasons.append("entry_risk_reason_mismatch")
    if int(values["raw_shares"]) != int(envelope.get("raw_shares", 0) or 0):
        reasons.append("entry_risk_raw_shares_mismatch")
    if int(values["shares"]) != int(envelope.get("shares", 0) or 0):
        reasons.append("entry_risk_shares_mismatch")
    if abs(
        values["max_entry_price"]
        - float(envelope.get("max_entry_price", 0.0) or 0.0)
    ) > 0.001:
        reasons.append("entry_risk_price_ceiling_mismatch")
    if recorded_status == "approved":
        if values["shares"] < 100:
            reasons.append("entry_risk_approved_below_board_lot")
        if values["max_entry_price"] < values["sizing_price"]:
            reasons.append("entry_risk_approved_below_sizing_price")
    elif recorded_status != "blocked":
        reasons.append("entry_risk_status_invalid")
    return reasons


def _entry_order_risk_reasons(event, risk_rows_by_code):
    reasons = []
    code = str(event.get("symbol") or event.get("code") or "")
    risk_row = risk_rows_by_code.get(code)
    if risk_row is None:
        return ["entry_order_risk_evidence_missing"]
    if str(event.get("entry_risk_evidence_schema_version") or "") != "1":
        reasons.append("entry_order_risk_schema_invalid")
    ceiling = _finite_float(event.get("entry_price_ceiling"))
    sizing_price = _finite_float(event.get("entry_sizing_price"))
    sizing_shares = _finite_float(event.get("entry_sizing_shares"))
    order_price = _finite_float(event.get("price"))
    order_qty = _finite_float(event.get("qty"))
    expected_ceiling = _finite_float(risk_row.get("entry_risk_max_entry_price"))
    expected_sizing_price = _finite_float(risk_row.get("entry_risk_sizing_price"))
    expected_shares = _finite_float(risk_row.get("entry_risk_shares"))
    if ceiling is None or expected_ceiling is None or abs(ceiling - expected_ceiling) > 0.001:
        reasons.append("entry_order_price_ceiling_mismatch")
    if sizing_price is None or expected_sizing_price is None or abs(sizing_price - expected_sizing_price) > 0.001:
        reasons.append("entry_order_sizing_price_mismatch")
    if sizing_shares is None or expected_shares is None or int(sizing_shares) != int(expected_shares):
        reasons.append("entry_order_sizing_shares_mismatch")
    if (
        order_qty is None
        or order_qty <= 0
        or int(order_qty) != order_qty
        or int(order_qty) % 100 != 0
    ):
        reasons.append("entry_order_qty_invalid")
    elif expected_shares is not None and order_qty > expected_shares:
        reasons.append("entry_order_qty_exceeds_sizing_shares")
    if order_price is None or order_price <= 0:
        reasons.append("entry_order_limit_price_invalid")
    elif ceiling is not None and order_price > ceiling + 0.001:
        reasons.append("entry_order_price_ceiling_exceeded")
    return reasons


def _opened_entry_risk_reasons(row, risk_rows_by_code):
    reasons = []
    code = str(row.get("code") or "")
    risk_row = risk_rows_by_code.get(code)
    if risk_row is None:
        return ["opened_entry_risk_evidence_missing"]
    shares = _finite_float(row.get("shares"))
    entry_price = _finite_float(row.get("entry_price"))
    expected_shares = _finite_float(risk_row.get("entry_risk_shares"))
    expected_ceiling = _finite_float(
        risk_row.get("entry_risk_max_entry_price")
    )
    if (
        shares is None
        or shares <= 0
        or int(shares) != shares
        or int(shares) % 100 != 0
    ):
        reasons.append("opened_entry_shares_invalid")
    elif expected_shares is None or shares > expected_shares:
        reasons.append("opened_entry_shares_exceed_risk_envelope")
    if entry_price is None or entry_price <= 0:
        reasons.append("opened_entry_price_invalid")
    elif (
        expected_ceiling is None
        or entry_price > expected_ceiling + 0.001
    ):
        reasons.append("opened_entry_price_exceeds_risk_envelope")
    return reasons


def _entry_fill_evidence_reasons(opened_row, entry_events, risk_rows_by_code):
    reasons = []
    code = str(opened_row.get("code") or "")
    opened_shares = _finite_float(opened_row.get("shares"))
    opened_price = _finite_float(opened_row.get("entry_price"))
    risk_row = risk_rows_by_code.get(code, {})
    expected_requested_qty = _finite_float(risk_row.get("entry_risk_shares"))
    aggregate_fills = [
        event
        for event in entry_events
        if str(event.get("event") or "") == "FILLED"
        and str(event.get("symbol") or event.get("code") or "") == code
        and str(event.get("side") or "") == "2"
        and _as_bool(event.get("aggregate_execution"))
    ]
    if len(aggregate_fills) != 1:
        return ["entry_aggregate_fill_count_invalid"]

    event = aggregate_fills[0]
    event_qty = _finite_float(event.get("qty"))
    filled_qty = _finite_float(event.get("filled_qty"))
    requested_qty = _finite_float(event.get("requested_qty"))
    remaining_qty = _finite_float(event.get("remaining_qty"))
    average_price = _finite_float(event.get("average_price"))
    average_fill_price = _finite_float(event.get("average_fill_price"))
    if str(event.get("execution_evidence_schema_version") or "") != "1":
        reasons.append("entry_execution_evidence_schema_invalid")
    if (
        opened_shares is None
        or event_qty != opened_shares
        or filled_qty != opened_shares
        or requested_qty != expected_requested_qty
        or remaining_qty != 0
    ):
        reasons.append("entry_execution_qty_mismatch")
    if (
        opened_price is None
        or average_price is None
        or average_fill_price is None
        or abs(average_price - opened_price) > 0.001
        or abs(average_fill_price - opened_price) > 0.001
    ):
        reasons.append("entry_execution_price_mismatch")
    if (
        str(event.get("process_state") or "") != "terminal"
        or str(event.get("terminal_reason") or "") != "filled"
        or str(event.get("submission_status") or "") != "accepted"
    ):
        reasons.append("entry_execution_state_invalid")
    execution_ids = _identifier_set(event.get("execution_ids"))
    primary_execution_ids = _identifier_set(event.get("execution_id"))
    if not execution_ids:
        reasons.append("entry_execution_ids_missing")
    elif len(primary_execution_ids) != 1 or not primary_execution_ids.issubset(
        execution_ids
    ):
        reasons.append("entry_execution_primary_id_invalid")
    order_ids = _identifier_set(event.get("order_ids"))
    final_order_id = str(event.get("order_id") or "").strip()
    accepted_order_ids = {
        str(candidate.get("order_id") or "").strip()
        for candidate in entry_events
        if str(candidate.get("event") or "") == "ACCEPTED"
        and str(candidate.get("symbol") or candidate.get("code") or "") == code
        and str(candidate.get("side") or "") == "2"
        and str(candidate.get("order_id") or "").strip()
    }
    if (
        not order_ids
        or final_order_id not in order_ids
        or not order_ids.issubset(accepted_order_ids)
    ):
        reasons.append("entry_execution_order_ids_mismatch")
    return reasons


def _normalized_close_positions(value):
    if not isinstance(value, list) or not value:
        return None
    normalized = []
    seen_hold_ids = set()
    for item in value:
        if not isinstance(item, dict):
            return None
        hold_id = str(item.get("HoldID") or item.get("hold_id") or "").strip()
        qty = _finite_float(item.get("Qty") if "Qty" in item else item.get("qty"))
        if (
            not hold_id
            or hold_id in seen_hold_ids
            or qty is None
            or qty <= 0
            or int(qty) != qty
        ):
            return None
        seen_hold_ids.add(hold_id)
        normalized.append((hold_id, int(qty)))
    return tuple(normalized)


def _protective_stop_risk_reasons(
    opened_row,
    stop_events,
    risk_rows_by_code,
):
    reasons = []
    code = str(opened_row.get("code") or "")
    opened_shares = _finite_float(opened_row.get("shares"))
    opened_price = _finite_float(opened_row.get("entry_price"))
    risk_row = risk_rows_by_code.get(code)
    if risk_row is None:
        return ["protective_stop_risk_evidence_missing"]
    confirmed_events = [
        event
        for event in stop_events
        if str(event.get("event") or "") == "ACCEPTED"
        and str(event.get("kind") or "") == "stop"
        and str(event.get("symbol") or event.get("code") or "") == code
        and _as_bool(event.get("confirmed"))
    ]
    if not confirmed_events:
        return ["missing_confirmed_protective_stop"]
    if len(confirmed_events) != 1:
        reasons.append("confirmed_protective_stop_count_invalid")
        return reasons

    event = confirmed_events[0]
    stop_qty = _finite_float(event.get("qty"))
    trigger_price = _finite_float(event.get("trigger_price"))
    if str(event.get("side") or "") != "1":
        reasons.append("protective_stop_side_invalid")
    if not str(event.get("order_id") or "").strip():
        reasons.append("protective_stop_order_id_missing")
    if (
        stop_qty is None
        or stop_qty <= 0
        or int(stop_qty) != stop_qty
        or int(stop_qty) % 100 != 0
    ):
        reasons.append("protective_stop_qty_invalid")
    elif opened_shares is None or int(stop_qty) != int(opened_shares):
        reasons.append("protective_stop_qty_mismatch")
    confirmation_details = event.get("confirmation_details")
    if str(event.get("confirmation_evidence_schema_version") or "") != "1":
        reasons.append("protective_stop_confirmation_schema_invalid")
    if str(event.get("confirmation_reason") or "") != "orders_api_confirmed":
        reasons.append("protective_stop_confirmation_reason_invalid")
    if not isinstance(confirmation_details, dict):
        reasons.append("protective_stop_confirmation_evidence_missing")
    else:
        confirmed_order_id = str(confirmation_details.get("order_id") or "").strip()
        event_order_id = str(event.get("order_id") or "").strip()
        confirmed_symbol = str(confirmation_details.get("symbol") or "").strip()
        confirmed_qty = _finite_float(confirmation_details.get("order_qty"))
        confirmed_cumulative_qty = _finite_float(
            confirmation_details.get("cumulative_qty")
        )
        confirmed_remaining_qty = _finite_float(
            confirmation_details.get("remaining_qty")
        )
        confirmed_trigger = _finite_float(
            confirmation_details.get("trigger_price")
        )
        if (
            str(confirmation_details.get("response_shape_version") or "") != "2"
            or not _as_bool(confirmation_details.get("details_present"))
            or str(confirmation_details.get("mismatch_reason") or "") != "confirmed"
            or _as_bool(confirmation_details.get("summary_truncated"))
        ):
            reasons.append("protective_stop_confirmation_evidence_invalid")
        if (
            not confirmed_order_id
            or confirmed_order_id != event_order_id
            or str(confirmation_details.get("requested_order_id") or "").strip()
            != event_order_id
        ):
            reasons.append("protective_stop_confirmation_order_id_mismatch")
        if confirmed_symbol != code:
            reasons.append("protective_stop_confirmation_symbol_mismatch")
        if (
            str(confirmation_details.get("process_state") or "") != "active"
            or confirmation_details.get("terminal_reason") not in (None, "")
            or _as_bool(confirmation_details.get("has_partial_fill"))
            or not _as_bool(confirmation_details.get("is_consistent"))
        ):
            reasons.append("protective_stop_confirmation_state_invalid")
        if (
            stop_qty is None
            or confirmed_qty != stop_qty
            or _finite_float(confirmation_details.get("expected_qty")) != stop_qty
            or confirmed_cumulative_qty != 0
            or confirmed_remaining_qty != stop_qty
        ):
            reasons.append("protective_stop_confirmation_qty_mismatch")
        if (
            str(confirmation_details.get("side") or "") != "1"
            or _finite_float(confirmation_details.get("cash_margin")) != 3
            or _finite_float(confirmation_details.get("deliv_type")) != 2
            or _finite_float(event.get("exchange")) is None
            or _finite_float(event.get("margin_trade_type")) is None
            or _finite_float(confirmation_details.get("exchange"))
            != _finite_float(event.get("exchange"))
            or _finite_float(confirmation_details.get("margin_trade_type"))
            != _finite_float(event.get("margin_trade_type"))
        ):
            reasons.append("protective_stop_confirmation_route_mismatch")
        if (
            trigger_price is None
            or confirmed_trigger is None
            or abs(confirmed_trigger - trigger_price) > 0.001
            or abs(
                (_finite_float(confirmation_details.get("expected_trigger_price")) or 0)
                - trigger_price
            ) > 0.001
        ):
            reasons.append("protective_stop_confirmation_trigger_mismatch")
        reverse_limit = confirmation_details.get("reverse_limit")
        if (
            not isinstance(reverse_limit, dict)
            or _finite_float(reverse_limit.get("TriggerSec")) != 1
            or _finite_float(reverse_limit.get("TriggerPrice")) != trigger_price
            or _finite_float(reverse_limit.get("UnderOver")) != 1
            or _finite_float(reverse_limit.get("AfterHitOrderType")) != 1
            or _finite_float(reverse_limit.get("AfterHitPrice")) != 0
        ):
            reasons.append("protective_stop_confirmation_reverse_limit_mismatch")

        confirmed_close_positions = _normalized_close_positions(
            confirmation_details.get("close_positions")
        )
        expected_close_positions = _normalized_close_positions(
            event.get("expected_close_positions")
        )
        if (
            confirmed_close_positions is None
            or confirmed_close_positions != expected_close_positions
            or confirmation_details.get("close_positions_match") is not True
            or opened_shares is None
            or sum(qty for _, qty in confirmed_close_positions)
            != int(opened_shares)
        ):
            reasons.append(
                "protective_stop_confirmation_close_positions_mismatch"
            )
    sizing_price = _finite_float(risk_row.get("entry_risk_sizing_price"))
    sizing_stop = _finite_float(risk_row.get("entry_risk_stop_price"))
    if (
        trigger_price is None
        or trigger_price <= 0
        or opened_price is None
        or sizing_price is None
        or sizing_stop is None
    ):
        reasons.append("protective_stop_trigger_invalid")
    else:
        expected_trigger = normalize_tick_size(
            max(0.01, opened_price - (sizing_price - sizing_stop)),
            is_buy=False,
        )
        if abs(trigger_price - expected_trigger) > 0.001:
            reasons.append("protective_stop_trigger_mismatch")
    return reasons


def _identifier_set(value):
    if value in (None, ""):
        return set()
    parsed = value
    if isinstance(value, str):
        text = value.strip()
        try:
            parsed = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            parsed = [part.strip() for part in text.split(",")]
    if isinstance(parsed, (list, tuple, set)):
        values = parsed
    else:
        values = [parsed]
    return {
        str(item or "").strip()
        for item in values
        if str(item or "").strip()
    }


def _exit_lifecycle_evidence_reasons(
    opened_row,
    exit_row,
    entry_fill_events,
    fill_events,
):
    reasons = []
    code = str(opened_row.get("code") or "")
    opened_shares = _finite_float(opened_row.get("shares"))
    opened_price = _finite_float(opened_row.get("entry_price"))
    held_shares = _finite_float(exit_row.get("held_shares"))
    filled_shares = _finite_float(exit_row.get("filled_shares"))
    remaining_shares = _finite_float(exit_row.get("remaining_shares"))
    buy_price = _finite_float(exit_row.get("buy_price"))
    observed_price = _finite_float(exit_row.get("observed_price"))
    if str(exit_row.get("code") or "") != code:
        reasons.append("actual_exit_code_mismatch")
    if opened_shares is None or held_shares is None or int(held_shares) != int(opened_shares):
        reasons.append("actual_exit_held_shares_mismatch")
    if opened_shares is None or filled_shares is None or int(filled_shares) != int(opened_shares):
        reasons.append("actual_exit_filled_shares_mismatch")
    if remaining_shares is None or int(remaining_shares) != 0:
        reasons.append("actual_exit_remaining_shares_mismatch")
    if opened_price is None or buy_price is None or abs(buy_price - opened_price) > 0.001:
        reasons.append("actual_exit_buy_price_mismatch")

    entry_execution_ids = _identifier_set(
        exit_row.get("entry_execution_ids")
    )
    if not entry_execution_ids:
        reasons.append("actual_entry_execution_ids_missing")
    linked_entry_ids = set().union(
        *(
            _identifier_set(event.get("execution_ids"))
            | _identifier_set(event.get("execution_id"))
            for event in entry_fill_events
            if str(event.get("event") or "") == "FILLED"
            and str(event.get("symbol") or event.get("code") or "") == code
            and str(event.get("side") or "") == "2"
            and _as_bool(event.get("aggregate_execution"))
            and str(event.get("execution_evidence_schema_version") or "") == "1"
        )
    )
    if (
        entry_execution_ids
        and entry_execution_ids != linked_entry_ids
    ):
        reasons.append("actual_entry_execution_ids_mismatch")

    exit_order_id = str(exit_row.get("exit_order_id") or "").strip()
    exit_execution_ids = _identifier_set(exit_row.get("exit_execution_ids"))
    if not exit_order_id:
        reasons.append("actual_exit_order_id_missing")
    if not exit_execution_ids:
        reasons.append("actual_exit_execution_ids_missing")
    linked_fills = [
        event
        for event in fill_events
        if str(event.get("event") or "") in {"FILLED", "FILLED_BEFORE_CANCEL"}
        and str(event.get("symbol") or event.get("code") or "") == code
        and str(event.get("order_id") or "").strip() == exit_order_id
    ]
    if not linked_fills:
        reasons.append("actual_exit_fill_event_missing")
    else:
        aggregate_fills = [
            event
            for event in linked_fills
            if _as_bool(event.get("aggregate_execution"))
            and str(event.get("execution_evidence_schema_version") or "") == "1"
        ]
        if len(aggregate_fills) != 1:
            reasons.append("actual_exit_aggregate_fill_count_invalid")
        else:
            fill_event = aggregate_fills[0]
            journal_execution_ids = (
                _identifier_set(fill_event.get("execution_ids"))
                | _identifier_set(fill_event.get("execution_id"))
            )
            event_qty = _finite_float(fill_event.get("qty"))
            event_filled_qty = _finite_float(fill_event.get("filled_qty"))
            event_requested_qty = _finite_float(fill_event.get("requested_qty"))
            event_remaining_qty = _finite_float(fill_event.get("remaining_qty"))
            event_average_price = _finite_float(
                fill_event.get("average_fill_price")
            )
            if event_average_price is None:
                event_average_price = _finite_float(fill_event.get("average_price"))
            if str(fill_event.get("side") or "") != "1":
                reasons.append("actual_exit_fill_side_invalid")
            if (
                filled_shares is None
                or event_qty != filled_shares
                or event_filled_qty != filled_shares
                or event_requested_qty != held_shares
                or event_remaining_qty != 0
            ):
                reasons.append("actual_exit_execution_qty_mismatch")
            if (
                observed_price is None
                or event_average_price is None
                or abs(event_average_price - observed_price) > 0.001
            ):
                reasons.append("actual_exit_execution_price_mismatch")
            if (
                str(fill_event.get("process_state") or "") != "terminal"
                or str(fill_event.get("terminal_reason") or "") != "filled"
            ):
                reasons.append("actual_exit_execution_state_invalid")
            if not journal_execution_ids or exit_execution_ids != journal_execution_ids:
                reasons.append("actual_exit_execution_ids_mismatch")
            order_ids = _identifier_set(fill_event.get("order_ids"))
            accepted_order_ids = {
                str(candidate.get("order_id") or "").strip()
                for candidate in fill_events
                if str(candidate.get("event") or "") == "ACCEPTED"
                and str(candidate.get("symbol") or candidate.get("code") or "") == code
                and str(candidate.get("side") or "") == "1"
                and str(candidate.get("order_id") or "").strip()
            }
            if (
                not order_ids
                or exit_order_id not in order_ids
                or not order_ids.issubset(accepted_order_ids)
            ):
                reasons.append("actual_exit_execution_order_ids_mismatch")
    return reasons





def _build_lifecycle_summary(results, decisions, order_events, exits, *, require_actual_net=False):
    terminal_no_entry = {
        "blocked_operational_veto",
        "blocked_entry_quote_refresh",
        "skipped_review_cap",
        "skipped_size_floor",
        "entry_rejected",
    }
    decisions_by_snapshot = {}
    orders_by_snapshot = {}
    exits_by_snapshot = {}
    for row in decisions:
        decisions_by_snapshot.setdefault(str(row.get("decision_snapshot_id") or ""), []).append(row)
    for event in order_events:
        orders_by_snapshot.setdefault(str(event.get("decision_snapshot_id") or ""), []).append(event)
    for row in exits:
        exits_by_snapshot.setdefault(str(row.get("decision_snapshot_id") or ""), []).append(row)

    complete = 0
    incomplete = 0
    reason_counts = {}
    for result in results:
        if not result.parity or not result.replayable:
            continue
        snapshot_id = str(result.snapshot_id)
        if not result.selected_codes:
            complete += 1
            continue

        snapshot_decisions = decisions_by_snapshot.get(snapshot_id, [])
        snapshot_orders = orders_by_snapshot.get(snapshot_id, [])
        snapshot_exits = exits_by_snapshot.get(snapshot_id, [])
        decision_names = {str(row.get("decision") or "") for row in snapshot_decisions}
        reasons = []
        actionable_decisions = {
            "opened_live",
            "entry_unresolved",
            "entry_rejected",
            "selected_for_sizing",
            "skipped_size_floor",
            "entry_quote_refresh_passed",
            "blocked_entry_quote_refresh",
            "entry_risk_resolved",
        }
        operational_rows = [
            row
            for row in snapshot_decisions
            if str(row.get("decision") or "") == "operational_review_passed"
            or (
                str(row.get("decision") or "") == "blocked_operational_veto"
                and str(row.get("reason") or "").startswith(("ai_filter:", "news_fetch:"))
            )
        ]
        requires_operational_review = bool(
            decision_names.intersection(actionable_decisions)
            or operational_rows
        )
        if requires_operational_review and not operational_rows:
            reasons.append("missing_operational_review_evidence")
        if operational_rows:
            required_codes = {
                str(row.get("code") or "")
                for row in snapshot_decisions
                if (
                    str(row.get("decision") or "") in actionable_decisions
                    or row in operational_rows
                )
                and str(row.get("code") or "")
            }
            reviewed_codes = {
                str(row.get("code") or "")
                for row in operational_rows
                if str(row.get("code") or "")
            }
            if not required_codes.issubset(reviewed_codes):
                reasons.append("missing_operational_review_evidence")
            for operational_row in operational_rows:
                reasons.extend(_operational_evidence_reasons(operational_row))

        entry_quote_rows = [
            row
            for row in snapshot_decisions
            if str(row.get("decision") or "") in {
                "entry_quote_refresh_passed",
                "blocked_entry_quote_refresh",
            }
        ]
        requires_entry_quote = bool(
            decision_names.intersection(actionable_decisions)
            or entry_quote_rows
        )
        if requires_entry_quote and not entry_quote_rows:
            reasons.append("missing_entry_quote_evidence")
        if entry_quote_rows:
            required_quote_codes = {
                str(row.get("code") or "")
                for row in snapshot_decisions
                if str(row.get("decision") or "") in actionable_decisions
                and str(row.get("code") or "")
            }
            evidenced_quote_codes = {
                str(row.get("code") or "")
                for row in entry_quote_rows
                if str(row.get("code") or "")
            }
            if not required_quote_codes.issubset(evidenced_quote_codes):
                reasons.append("missing_entry_quote_evidence")
            for entry_quote_row in entry_quote_rows:
                reasons.extend(
                    _entry_quote_evidence_reasons(entry_quote_row)
                )
        entry_quote_rows_by_code = {
            str(row.get("code") or ""): row
            for row in entry_quote_rows
            if str(row.get("code") or "")
        }

        risk_required_decisions = {
            "opened_live",
            "entry_unresolved",
            "entry_rejected",
            "selected_for_sizing",
            "skipped_size_floor",
            "entry_risk_resolved",
        }
        entry_risk_rows = [
            row
            for row in snapshot_decisions
            if str(row.get("decision") or "") == "entry_risk_resolved"
        ]
        requires_entry_risk = bool(
            decision_names.intersection(risk_required_decisions)
        )
        if requires_entry_risk and not entry_risk_rows:
            reasons.append("missing_entry_risk_evidence")
        risk_rows_by_code = {
            str(row.get("code") or ""): row
            for row in entry_risk_rows
            if str(row.get("code") or "")
        }
        if entry_risk_rows:
            required_risk_codes = {
                str(row.get("code") or "")
                for row in snapshot_decisions
                if str(row.get("decision") or "") in risk_required_decisions
                and str(row.get("code") or "")
            }
            if not required_risk_codes.issubset(risk_rows_by_code):
                reasons.append("missing_entry_risk_evidence")
            for entry_risk_row in entry_risk_rows:
                reasons.extend(
                    _entry_risk_evidence_reasons(
                        entry_risk_row,
                        entry_quote_rows_by_code,
                    )
                )

        planned_entry_events = [
            event
            for event in snapshot_orders
            if str(event.get("lifecycle_stage") or "") == "entry"
            and str(event.get("event") or "") in {"PLANNED", "ACCEPTED"}
            and str(event.get("side") or "") == "2"
        ]
        for planned_entry_event in planned_entry_events:
            reasons.extend(
                _entry_order_risk_reasons(
                    planned_entry_event,
                    risk_rows_by_code,
                )
            )

        opened_entry_rows = [
            row
            for row in snapshot_decisions
            if str(row.get("decision") or "") == "opened_live"
        ]
        for opened_entry_row in opened_entry_rows:
            reasons.extend(
                _opened_entry_risk_reasons(opened_entry_row, risk_rows_by_code)
            )

        entry_events = [
            event for event in snapshot_orders
            if str(event.get("lifecycle_stage") or "") == "entry"
        ]
        stop_events = [
            event for event in snapshot_orders
            if str(event.get("lifecycle_stage") or "") == "protective_stop"
        ]
        exit_events = [
            event for event in snapshot_orders
            if str(event.get("lifecycle_stage") or "") == "exit"
        ]
        if opened_entry_rows:
            expected_initial_order_qty = {
                str(row.get("code") or ""): _finite_float(
                    risk_rows_by_code.get(
                        str(row.get("code") or ""),
                        {},
                    ).get("entry_risk_shares")
                )
                for row in opened_entry_rows
            }
            for code, expected_qty in expected_initial_order_qty.items():
                if not any(
                    str(event.get("event") or "") == "PLANNED"
                    and str(event.get("symbol") or "") == code
                    and _finite_float(event.get("qty")) == expected_qty
                    for event in entry_events
                ):
                    reasons.append("missing_initial_entry_order_qty")
        if not snapshot_decisions:
            reasons.append("missing_linked_decision")
        elif "opened_live" in decision_names:
            if not any(str(event.get("event") or "") == "FILLED" for event in entry_events):
                reasons.append("missing_entry_fill")
            if not planned_entry_events:
                reasons.append("missing_entry_order_risk_envelope")
            if not any(str(event.get("event") or "") == "ACCEPTED" for event in stop_events):
                reasons.append("missing_protective_stop_acceptance")
            for opened_entry_row in opened_entry_rows:
                reasons.extend(
                    _entry_fill_evidence_reasons(
                        opened_entry_row, entry_events, risk_rows_by_code
                    )
                )

                reasons.extend(
                    _protective_stop_risk_reasons(
                        opened_entry_row,
                        stop_events,
                        risk_rows_by_code,
                    )
                )
            exit_filled = any(str(event.get("event") or "") == "FILLED" for event in exit_events)
            stop_filled = any(
                str(event.get("event") or "") in {"FILLED", "FILLED_BEFORE_CANCEL"}
                for event in stop_events
            )
            all_exit_fill_events = [
                *exit_events,
                *stop_events,
            ]
            for opened_entry_row in opened_entry_rows:
                code = str(opened_entry_row.get("code") or "")
                matching_exits = [
                    row
                    for row in snapshot_exits
                    if str(row.get("code") or "") == code
                ]
                if len(matching_exits) != 1:
                    reasons.append("actual_exit_count_invalid")
                    continue
                reasons.extend(
                    _exit_lifecycle_evidence_reasons(
                        opened_entry_row,
                        matching_exits[0],
                        entry_events,
                        all_exit_fill_events,
                    )
                )
            if not exit_filled and not stop_filled:
                reasons.append("missing_exit_fill")
            if not any(_remaining_shares_is_zero(row) for row in snapshot_exits):
                reasons.append("missing_flat_actual_exit")
            if snapshot_exits and any(
                _actual_cost_evidence_reasons(row) for row in snapshot_exits
            ):
                reasons.append("actual_cost_evidence_incomplete")
            if require_actual_net and snapshot_exits and any(
                _actual_net_evidence_reasons(row) for row in snapshot_exits
            ):
                reasons.append("actual_net_pnl_evidence_incomplete")
        elif "entry_unresolved" in decision_names:
            reasons.append("entry_unresolved")
        elif decision_names & terminal_no_entry:
            if "entry_rejected" in decision_names:
                entry_events = [
                    event for event in snapshot_orders
                    if str(event.get("lifecycle_stage") or "") == "entry"
                ]
                if not any(str(event.get("event") or "") == "REJECTED" for event in entry_events):
                    reasons.append("missing_entry_rejection")
        else:
            reasons.append("missing_terminal_decision")

        if reasons:
            incomplete += 1
            for reason in sorted(set(reasons)):
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
        else:
            complete += 1

    return {
        "linked_decision_events": len(decisions),
        "linked_order_events": len(order_events),
        "lifecycle_complete_snapshots": complete,
        "lifecycle_incomplete_snapshots": incomplete,
        "lifecycle_incomplete_reasons": ",".join(
            f"{reason}:{count}" for reason, count in sorted(reason_counts.items())
        ),
    }


def _float(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    return result if math.isfinite(result) else 0.0


def run_production_replay(
    *,
    snapshots_file,
    exit_log,
    trade_mode,
    min_snapshots=1,
    decision_log=None,
    order_journal=None,
    require_complete_lifecycle=False,
    expected_code_commit_sha=None,
    expected_runtime_config_hash=None,
):
    snapshots = [
        snapshot
        for snapshot in load_daytrade_production_snapshots(snapshots_file)
        if str(snapshot.get("trade_mode") or "").upper() == trade_mode
        and not bool(snapshot.get("is_simulation"))
    ]
    results = [
        replay_daytrade_production_snapshot(
            snapshot,
            expected_code_commit_sha=expected_code_commit_sha,
            expected_runtime_config_hash=expected_runtime_config_hash,
        )
        for snapshot in snapshots
    ]
    parity_count = sum(result.parity for result in results)
    replayable_count = sum(result.replayable for result in results)
    replayable_ids = {
        result.snapshot_id
        for result in results
        if result.parity and result.replayable
    }
    eligible_ids = {
        result.snapshot_id
        for snapshot, result in zip(snapshots, results)
        if result.parity
        and result.replayable
        and bool(snapshot.get("eligible_for_decision_clean_holdout"))
    }
    # KABUCOM_TEST snapshots can prove schema / selector / order-lifecycle parity,
    # even though they must never be counted as LIVE clean-holdout evidence.
    exits = _load_linked_exits(exit_log, replayable_ids)
    decisions = _load_linked_decisions(decision_log, replayable_ids, trade_mode)
    order_events = _load_linked_order_events(order_journal, replayable_ids)
    lifecycle_summary = _build_lifecycle_summary(
        results,
        decisions,
        order_events,
        exits,
        require_actual_net=trade_mode == "KABUCOM_LIVE",
    )
    gross_pnl = [
        _float(row.get("observed_gross_pnl") if row.get("observed_gross_pnl") not in (None, "") else row.get("observed_pnl"))
        for row in exits
    ]
    gross_profit = sum(value for value in gross_pnl if value > 0)
    gross_loss = abs(sum(value for value in gross_pnl if value < 0))
    gross_profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    complete_cost_exits = [row for row in exits if not _actual_cost_evidence_reasons(row)]
    all_costs_complete = bool(exits) and len(complete_cost_exits) == len(exits)
    execution_net_pnl = [_finite_float(row.get("observed_execution_net_pnl")) for row in complete_cost_exits]
    execution_net_profit_factor = None
    if all_costs_complete:
        execution_net_profit = sum(value for value in execution_net_pnl if value is not None and value > 0)
        execution_net_loss = abs(sum(value for value in execution_net_pnl if value is not None and value < 0))
        execution_net_profit_factor = execution_net_profit / execution_net_loss if execution_net_loss > 0 else float("inf")

    complete_net_exits = [row for row in exits if not _actual_net_evidence_reasons(row)]
    all_net_complete = bool(exits) and len(complete_net_exits) == len(exits)
    net_pnl = [_finite_float(row.get("observed_net_pnl")) for row in complete_net_exits]
    net_profit_factor = None
    if all_net_complete:
        net_profit = sum(value for value in net_pnl if value is not None and value > 0)
        net_loss = abs(sum(value for value in net_pnl if value is not None and value < 0))
        net_profit_factor = net_profit / net_loss if net_loss > 0 else float("inf")
    summary = {
        "trade_mode": trade_mode,
        "snapshots": len(snapshots),
        "replayable": replayable_count,
        "parity": parity_count,
        "eligible_execution_replay": len(replayable_ids),
        "eligible_decision_clean_holdout": len(eligible_ids),
        "selected_decisions": sum(bool(result.selected_codes) for result in results),
        "linked_actual_exits": len(exits),
        "observed_pnl": sum(gross_pnl),
        "observed_gross_pnl": sum(gross_pnl),
        "observed_profit_factor": gross_profit_factor,
        "observed_gross_profit_factor": gross_profit_factor,
        "linked_execution_net_actual_exits": len(complete_cost_exits),
        "execution_cost_incomplete_exits": len(exits) - len(complete_cost_exits),
        "net_cost_incomplete_exits": len(exits) - len(complete_cost_exits),
        "observed_execution_net_pnl": sum(execution_net_pnl) if all_costs_complete else None,
        "observed_execution_net_profit_factor": execution_net_profit_factor,
        "linked_net_actual_exits": len(complete_net_exits),
        "net_evidence_incomplete_exits": len(exits) - len(complete_net_exits),
        "observed_net_pnl": sum(net_pnl) if all_net_complete else None,
        "observed_net_profit_factor": net_profit_factor,
        **lifecycle_summary,
    }
    if len(snapshots) < int(min_snapshots):
        return 2, summary
    if parity_count != len(snapshots):
        return 3, summary
    if require_complete_lifecycle and int(summary["lifecycle_incomplete_snapshots"]) > 0:
        return 4, summary
    return 0, summary


def main():
    args = parse_args()
    code, summary = run_production_replay(
        snapshots_file=args.snapshots_file,
        exit_log=args.exit_log,
        trade_mode=args.trade_mode,
        min_snapshots=args.min_snapshots,
        decision_log=args.decision_log,
        order_journal=args.order_journal,
        require_complete_lifecycle=not args.allow_incomplete_lifecycle,
        expected_code_commit_sha=read_git_commit_sha(),
        expected_runtime_config_hash=RUNTIME_LIVE_ORDER_CONFIG_HASH,
    )
    print("=" * 60)
    print("DAYTRADE PRODUCTION SNAPSHOT REPLAY")
    print("=" * 60)
    for key, value in summary.items():
        if (
            key in {
                "observed_profit_factor",
                "observed_gross_profit_factor",
                "observed_execution_net_profit_factor",
                "observed_net_profit_factor",
            }
            and isinstance(value, (int, float))
            and math.isinf(value)
        ):
            value = "inf"
        print(f"{key.upper()}: {value}")
    if code == 2:
        print("STATUS: INSUFFICIENT_SNAPSHOTS")
    elif code == 3:
        print("STATUS: PARITY_FAILED")
    elif code == 4:
        print("STATUS: LIFECYCLE_INCOMPLETE")
    else:
        print("STATUS: PARITY_OK")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
