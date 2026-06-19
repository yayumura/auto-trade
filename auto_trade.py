import os
import sys
import datetime
import json
from pathlib import Path
import numpy as np
import pandas as pd
import time
import pickle
import signal
import socket
from enum import Enum
from dataclasses import dataclass
import psutil
from core.log_setup import setup_logging, send_discord_notify
from core.preflight import pre_flight_check
from core.kabucom_order_state import StockOrderAction, SubmissionStatus
from core.jpx_calendar import get_jpx_trading_day_status

class MarketPhase(Enum):
    PRE_MARKET = "寄り前"
    MORNING = "前場"
    LUNCH = "昼休み"
    AFTERNOON = "後場"
    CLOSING_TIME = "大引け後"

def get_market_phase(now_time, *, half_day: bool = False) -> MarketPhase:
    """現在時刻から市場のフェーズを判定する"""
    t900 = datetime.time(9, 0)
    t1130 = datetime.time(11, 30)
    t1230 = datetime.time(12, 30)
    t1530 = datetime.time(15, 30)
    
    if now_time < t900:
        return MarketPhase.PRE_MARKET
    elif t900 <= now_time < t1130:
        return MarketPhase.MORNING
    elif half_day:
        return MarketPhase.CLOSING_TIME
    elif t1130 <= now_time < t1230:
        return MarketPhase.LUNCH
    elif t1230 <= now_time < t1530:
        return MarketPhase.AFTERNOON
    else:
        return MarketPhase.CLOSING_TIME


def _is_submission_accepted(result) -> bool:
    status = getattr(result, "status", None)
    if status is None:
        return False
    status_value = getattr(status, "value", status)
    return str(status_value).strip().lower() == SubmissionStatus.ACCEPTED.value


def _is_submission_confirmed(result) -> bool:
    if result is None:
        return False
    if hasattr(result, "is_confirmed"):
        return bool(getattr(result, "is_confirmed"))
    confirmed = getattr(result, "confirmed", None)
    if confirmed is None:
        return False
    return bool(confirmed)


@dataclass(frozen=True)
class ShutdownResult:
    success: bool
    managed_remaining_orders: tuple[dict, ...]
    managed_remaining_positions: tuple[dict, ...]
    unmanaged_orders: tuple[dict, ...]
    unmanaged_positions: tuple[dict, ...]
    ambiguous_items: tuple[dict, ...]
    unknown_items: tuple[dict, ...]
    errors: tuple[str, ...]
    updated_portfolio: list[dict]
    updated_account: dict

    def __iter__(self):
        yield self.updated_portfolio
        yield self.updated_account

# --- ファイルパス・設定・APIキー設定 (core.configより一括取得) ---
from core.config import (
    PROJECT_ROOT, DATA_ROOT,
    DATA_FILE, PORTFOLIO_FILE, HISTORY_FILE, ACCOUNT_FILE,
    EXECUTION_LOG_FILE, TARGET_MARKETS, DAYTRADE_EXIT_LOG_FILE,
    DEBUG_MODE, TRADE_MODE, RUNTIME_LIVE_ORDER_CONFIG_HASH,
    LEVERAGE_RATE, JST, BULL_GAP_LIMIT,
    SMA_LONG_PERIOD, SMA_TREND_PERIOD, MAX_POSITIONS,
    SLIPPAGE_RATE, STOP_LOSS_ATR, INITIAL_CASH, load_insider_exclusion_codes,
    INTRADAY_SNAPSHOT_FILE, DATA_CACHE_ROOT,
)
from core.file_io import atomic_write_json, append_csv_rows, rotate_csv_if_large, safe_read_json
from core.live_approval_manifest import read_git_commit_sha
from core.live_readiness_report import build_live_readiness_report

# --- インスタンスロック機構 ---
LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".bot_sim.lock")
LOCK_SCHEMA_VERSION = 1
STOP_FILE = os.path.join(PROJECT_ROOT, "stop.txt")
ENTRY_SCAN_CUTOFF_TIME = datetime.time(14, 0)
FORCE_FLATTEN_TIME = datetime.time(14, 30)
SHUTDOWN_REQUESTED = False
SHUTDOWN_REASON = ""
ACTIVE_RUNTIME_STATE = {
    "broker": None,
    "portfolio": [],
    "account": {},
    "is_sim": True,
    "realtime_buffers": {},
}
LIVE_RISK_REVIEW_PATH = Path(PROJECT_ROOT) / "contracts" / "live_risk_review.json"

def _resolve_lock_broker_environment(trade_mode: str | None = None) -> str:
    mode = TRADE_MODE if trade_mode is None else str(trade_mode).strip().upper()
    if mode == "KABUCOM_LIVE":
        return "live"
    if mode == "KABUCOM_TEST":
        return "test"
    return "sim"


def _current_lock_identity(trade_mode: str | None = None) -> dict[str, object]:
    process = psutil.Process(os.getpid())
    code_sha = read_git_commit_sha()
    if not code_sha:
        raise RuntimeError("Git commit SHA を取得できませんでした。")
    approval_hash = str(RUNTIME_LIVE_ORDER_CONFIG_HASH or "").strip()
    if not approval_hash:
        raise RuntimeError("LIVE 承認ハッシュが空です。")
    return {
        "pid": int(process.pid),
        "process_start_time": round(float(process.create_time()), 6),
        "hostname": socket.gethostname() or "unknown",
        "executable": os.path.abspath(sys.executable),
        "trade_mode": str(TRADE_MODE if trade_mode is None else trade_mode).strip().upper(),
        "broker_environment": _resolve_lock_broker_environment(trade_mode),
        "code_sha": str(code_sha).strip(),
        "approval_hash": approval_hash,
    }


def _build_lock_payload(trade_mode: str | None = None) -> dict[str, object]:
    payload = dict(_current_lock_identity(trade_mode))
    payload["schema_version"] = LOCK_SCHEMA_VERSION
    payload["acquired_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return payload


def _normalize_lock_payload(payload: object) -> dict[str, object] | None:
    if not isinstance(payload, dict):
        return None
    try:
        schema_version = int(payload["schema_version"])
        pid = int(payload["pid"])
        process_start_time = float(payload["process_start_time"])
    except (KeyError, TypeError, ValueError):
        return None
    hostname = str(payload.get("hostname") or "").strip()
    executable = str(payload.get("executable") or "").strip()
    trade_mode = str(payload.get("trade_mode") or "").strip().upper()
    broker_environment = str(payload.get("broker_environment") or "").strip().lower()
    code_sha = str(payload.get("code_sha") or "").strip()
    approval_hash = str(payload.get("approval_hash") or "").strip()
    acquired_at = str(payload.get("acquired_at") or "").strip()
    if schema_version != LOCK_SCHEMA_VERSION:
        return None
    if pid <= 0 or process_start_time <= 0:
        return None
    if not hostname or not executable or not trade_mode or not broker_environment or not code_sha or not approval_hash or not acquired_at:
        return None
    if trade_mode not in {"SIM", "KABUCOM_TEST", "KABUCOM_LIVE"}:
        return None
    if broker_environment != _resolve_lock_broker_environment(trade_mode):
        return None
    normalized = dict(payload)
    normalized.update(
        {
            "schema_version": schema_version,
            "pid": pid,
            "process_start_time": process_start_time,
            "hostname": hostname,
            "executable": executable,
            "trade_mode": trade_mode,
            "broker_environment": broker_environment,
            "code_sha": code_sha,
            "approval_hash": approval_hash,
            "acquired_at": acquired_at,
        }
    )
    return normalized


def _read_lock_payload(lock_file: str) -> tuple[str, dict[str, object] | None, str]:
    if not os.path.exists(lock_file):
        return "missing", None, "missing"
    try:
        if os.path.getsize(lock_file) == 0:
            return "empty", None, "empty"
    except OSError as exc:
        return "corrupt", None, f"stat_failed:{exc}"

    try:
        with open(lock_file, "r", encoding="utf-8") as handle:
            raw = handle.read()
    except OSError as exc:
        return "corrupt", None, f"read_failed:{exc}"

    stripped = raw.strip()
    if not stripped:
        return "empty", None, "blank"

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        if stripped.isdigit():
            return "legacy", {"pid": int(stripped)}, "legacy_pid_text"
        return "corrupt", None, "json_parse_failed"

    normalized = _normalize_lock_payload(payload)
    if normalized is None:
        return "schema_mismatch", payload if isinstance(payload, dict) else None, "invalid_schema"
    return "valid", normalized, "ok"


def _lock_identity_matches_current(existing_payload: dict[str, object], current_identity: dict[str, object]) -> bool:
    identity_keys = (
        "pid",
        "process_start_time",
        "hostname",
        "executable",
        "trade_mode",
        "broker_environment",
        "code_sha",
        "approval_hash",
    )
    for key in identity_keys:
        if key == "process_start_time":
            try:
                existing_start = float(existing_payload.get(key))
                current_start = float(current_identity.get(key))
            except (TypeError, ValueError):
                return False
            if abs(existing_start - current_start) > 0.001:
                return False
            continue
        if str(existing_payload.get(key)) != str(current_identity.get(key)):
            return False
    return True


def _get_pid_start_time(pid: int) -> float | None:
    try:
        return round(float(psutil.Process(int(pid)).create_time()), 6)
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, ValueError, TypeError, OSError):
        return None


def _write_lock_payload(lock_file: str, payload: dict[str, object]) -> bool:
    try:
        with open(lock_file, "x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        return True
    except FileExistsError:
        return False
    except OSError as exc:
        print(f"[WARNING] ロックファイルの作成に失敗しました: {exc}")
        return False


def acquire_lock():
    """原子的なロックファイル取得。ロックの不整合は fail closed で扱う。"""
    try:
        current_identity = _current_lock_identity()
    except Exception as exc:
        print(f"[WARNING] ロックメタデータの生成に失敗しました: {exc}")
        return False

    status, payload, reason = _read_lock_payload(LOCK_FILE)
    if status == "missing":
        return _write_lock_payload(LOCK_FILE, _build_lock_payload())

    if status in {"empty", "corrupt", "schema_mismatch"}:
        print(
            f"[WARNING] ロックファイル({LOCK_FILE})が {reason} のため、上書きせず終了します。"
        )
        return False

    if status == "legacy":
        legacy_pid = int((payload or {}).get("pid") or 0)
        if legacy_pid > 0 and not psutil.pid_exists(legacy_pid):
            print(
                f"[WARNING] 旧ロックを検出(PID: {legacy_pid}, 既に終了)。削除して続行します。"
            )
            try:
                os.remove(LOCK_FILE)
            except OSError as exc:
                print(f"[WARNING] 旧ロックファイルの削除に失敗しました: {exc}")
                return False
            return _write_lock_payload(LOCK_FILE, _build_lock_payload())
        print(
            f"[WARNING] 旧形式のロックファイルを検出しましたが、PID {legacy_pid} の所有権を安全に確認できません。"
        )
        return False

    if status != "valid" or payload is None:
        print(f"[WARNING] ロックファイルの状態を解釈できませんでした: {reason}")
        return False

    existing_pid = int(payload["pid"])
    existing_start = float(payload["process_start_time"])
    if _lock_identity_matches_current(payload, current_identity):
        return True

    if not psutil.pid_exists(existing_pid):
        print(
            f"[WARNING] 古いロックファイルを検出(PID: {existing_pid}, 既に終了)。削除して続行します。"
        )
        try:
            os.remove(LOCK_FILE)
        except OSError as exc:
            print(f"[WARNING] 古いロックファイルの削除に失敗しました: {exc}")
            return False
        return _write_lock_payload(LOCK_FILE, _build_lock_payload())

    current_start = _get_pid_start_time(existing_pid)
    if current_start is None:
        print(
            f"[WARNING] PID {existing_pid} の起動時刻を確認できないため、ロックを上書きせず終了します。"
        )
        return False
    if abs(current_start - existing_start) > 0.001:
        print(
            f"[WARNING] PID再利用を検出しました(PID: {existing_pid}, lock_start={existing_start}, current_start={current_start})。削除して続行します。"
        )
        try:
            os.remove(LOCK_FILE)
        except OSError as exc:
            print(f"[WARNING] 旧ロックファイルの削除に失敗しました: {exc}")
            return False
        return _write_lock_payload(LOCK_FILE, _build_lock_payload())

    print(f"[WARNING] エラー: 他のインスタンス(PID: {existing_pid})が既に実行中です。")
    return False

def release_lock():
    if os.path.exists(LOCK_FILE):
        try:
            status, payload, reason = _read_lock_payload(LOCK_FILE)
            current_identity = _current_lock_identity()
            if status == "valid" and payload is not None:
                if _lock_identity_matches_current(payload, current_identity):
                    os.remove(LOCK_FILE)
                    return
                print(
                    f"[WARNING] ロックファイル({LOCK_FILE})は現在プロセスの所有物ではないため削除しません。"
                )
                return
            if status == "legacy" and payload is not None:
                if int(payload.get("pid") or 0) == int(current_identity["pid"]):
                    os.remove(LOCK_FILE)
                    return
                print(
                    f"[WARNING] 旧形式ロック({LOCK_FILE})の所有権を確認できないため削除しません。"
                )
                return
            print(f"[WARNING] ロックファイル({LOCK_FILE})は {reason} のため削除しません。")
        except OSError as e:
            print(f"[WARNING] ロックファイルの削除に失敗しました: {e}")


def _set_active_runtime_state(*, broker=None, portfolio=None, account=None, is_sim=None, realtime_buffers=None):
    if broker is not None:
        ACTIVE_RUNTIME_STATE["broker"] = broker
    if portfolio is not None:
        ACTIVE_RUNTIME_STATE["portfolio"] = portfolio
    if account is not None:
        ACTIVE_RUNTIME_STATE["account"] = account
    if is_sim is not None:
        ACTIVE_RUNTIME_STATE["is_sim"] = bool(is_sim)
    if realtime_buffers is not None:
        ACTIVE_RUNTIME_STATE["realtime_buffers"] = realtime_buffers


def _resolve_live_risk_review_path() -> str:
    env_path = os.getenv("LIVE_RISK_REVIEW_PATH")
    if env_path and str(env_path).strip():
        return str(env_path).strip()
    return str(LIVE_RISK_REVIEW_PATH)


def _build_live_readiness_report(
    *,
    broker,
    portfolio,
    startup_recovery_report,
    order_journal_summary,
    quote_fresh,
    quote_freshness_evidence=None,
    checked_at=None,
):
    request_budget_counts = getattr(broker, "request_budget_counts", None)
    return build_live_readiness_report(
        portfolio=portfolio,
        startup_recovery_report=startup_recovery_report,
        order_journal_summary=order_journal_summary,
        request_budget_counts=request_budget_counts,
        quote_fresh=quote_fresh,
        quote_freshness_evidence=quote_freshness_evidence,
        risk_review_path=_resolve_live_risk_review_path(),
        checked_at=checked_at,
    )

from core.logic import (
    detect_market_regime,
    load_invalid_tickers, normalize_tick_size,
    RealtimeBuffer, calculate_dynamic_leverage,
    calculate_all_technicals_v12, get_prime_tickers,
    manage_positions_live, select_best_candidates,
    calculate_lot_size, cap_daytrade_position_size,
    is_daytrade_inverse_setup_type,
    get_daytrade_week_key, resolve_daytrade_weekly_leverage,
    is_daytrade_weekly_profit_guard_active,
    is_daytrade_monthly_risk_blocked,
    resolve_daytrade_breadth_exposure_scale,
    resolve_daytrade_intraday_stop_mult,
    resolve_daytrade_inverse_buying_power,
    resolve_daytrade_buying_power,
    resolve_daytrade_selected_leverage,
    resolve_daytrade_selected_inverse_buying_power_leverage,
    resolve_daytrade_intraday_target_mult,
    resolve_daytrade_live_exit_decision,
    calculate_position_stops,
    cancel_linked_protective_stop_before_exit,
    resolve_protective_stop_order_id,
)
from core.watchlist import load_watchlist, save_watchlist
from core.ai_filter import ai_qualitative_filter, get_recent_news
from core.live_order_gate import (
    EntryAuthorizationContext,
    evaluate_entry_authorization,
    get_kabucom_live_financial_write_gate_status,
    get_live_order_gate_status,
)
from core.order_journal import build_order_journal_replay_summary
from core.startup_recovery import build_startup_recovery_report


def build_daytrade_watch_plan(watchlist, portfolio, market_index_code="1321"):
    watch_codes = [str(code) for code in watchlist]
    portfolio_codes = [str(position["code"]) for position in portfolio]
    # Open positions and the market index must win the 50-symbol registration budget first.
    prioritized_codes = portfolio_codes + [market_index_code] + watch_codes
    registration_targets = list(dict.fromkeys(prioritized_codes))[:50]
    return {
        "watchlist": watch_codes,
        "portfolio_codes": portfolio_codes,
        "registration_targets": registration_targets,
        "current_targets": set(registration_targets),
    }


def sync_daytrade_registry(broker, current_targets, already_tracked, market_index_code="1321", is_sim=False):
    """監視銘柄の register / unregister 結果から registry 同期成功可否を返す。"""
    new_codes = set(current_targets) - set(already_tracked)
    removed_codes = (set(already_tracked) - set(current_targets)) - {str(market_index_code)}
    registry_sync_ok = True

    if not is_sim:
        if new_codes:
            registry_sync_ok = bool(broker.register_symbols(list(new_codes))) and registry_sync_ok
        if removed_codes:
            registry_sync_ok = bool(broker.unregister_symbols(list(removed_codes))) and registry_sync_ok

    return registry_sync_ok, new_codes, removed_codes


def is_inverse_only_candidate_set(candidates):
    return bool(candidates) and all(
        is_daytrade_inverse_setup_type(item.get("setup_type")) for item in candidates
    )


def merge_account_state(account, persisted_state, *, is_sim: bool):
    """broker snapshot を durable state に安全に反映する。

    SIM では local account.json が唯一の状態源なので、snapshot をそのまま反映する。
    LIVE では wallet snapshot だけを取り込み、strategy state を 0 で潰さない。
    """
    snapshot = dict(account or {})
    merged = dict(persisted_state or {})

    if is_sim:
        merged.update(snapshot)
        return merged

    wallet_snapshot_incomplete = bool(snapshot.get("wallet_snapshot_incomplete"))
    if snapshot.get("wallet_cash_ok") or not wallet_snapshot_incomplete:
        if "stock_buying_power" in snapshot:
            merged["stock_buying_power"] = snapshot["stock_buying_power"]
    if snapshot.get("wallet_margin_ok") or not wallet_snapshot_incomplete:
        if "margin_buying_power" in snapshot:
            merged["margin_buying_power"] = snapshot["margin_buying_power"]

    for key in ("wallet_snapshot_incomplete", "wallet_cash_ok", "wallet_margin_ok"):
        if key in snapshot:
            merged[key] = snapshot[key]

    return merged


def ensure_daytrade_week_state(account, total_equity, server_datetime):
    week_key = get_daytrade_week_key(server_datetime)
    if account.get("daytrade_current_week") != week_key or float(account.get("daytrade_week_start_equity", 0) or 0) <= 0:
        account["daytrade_current_week"] = week_key
        account["daytrade_week_start_equity"] = float(total_equity)
    return account


def mark_daytrade_portfolio(portfolio, realtime_buffers=None, latest_close_map=None, quote_time=None):
    latest_close_map = latest_close_map or {}
    quote_time_str = quote_time.strftime('%Y-%m-%d %H:%M:%S') if quote_time is not None else None
    updated = []
    for position in portfolio:
        pos = dict(position)
        code = str(pos["code"])
        current_price = float(pos.get("current_price", pos["buy_price"]))
        if realtime_buffers and code in realtime_buffers:
            rt_price = realtime_buffers[code].get_latest_price()
            if rt_price and rt_price > 0:
                current_price = rt_price
        elif code in latest_close_map and latest_close_map[code] > 0:
            current_price = latest_close_map[code]
        pos["current_price"] = round(float(current_price), 1)
        pos["highest_price"] = round(max(float(pos.get("highest_price", pos["buy_price"])), float(current_price)), 1)
        pos["lowest_price"] = round(min(float(pos.get("lowest_price", pos["buy_price"])), float(current_price)), 1)
        pos["post_entry_high"] = pos["highest_price"]
        pos["post_entry_low"] = pos["lowest_price"]
        if "entry_timestamp" not in pos:
            pos["entry_timestamp"] = pos.get("buy_time")
        if quote_time_str is not None:
            pos["last_quote_timestamp"] = quote_time_str
        elif "last_quote_timestamp" not in pos:
            pos["last_quote_timestamp"] = pos.get("buy_time")
        updated.append(pos)
    return updated


def _portfolio_market_value(portfolio):
    return sum(
        float(position.get("current_price", position["buy_price"])) * int(position.get("shares", 0))
        for position in portfolio or []
    )


def _portfolio_unrealized_pnl(portfolio):
    return sum(
        (
            float(position.get("current_price", position["buy_price"]))
            - float(position.get("buy_price", 0))
        )
        * int(position.get("shares", 0))
        for position in portfolio or []
    )


def _resolve_account_equity(account, portfolio, is_sim):
    if is_sim:
        return float(account.get("cash", 0.0)) + _portfolio_market_value(portfolio)
    configured_risk_capital = float(account.get("configured_risk_capital", INITIAL_CASH) or INITIAL_CASH)
    realized_pnl_today = float(account.get("realized_pnl_today", 0.0) or 0.0)
    return configured_risk_capital + realized_pnl_today + _portfolio_unrealized_pnl(portfolio)


def _resolve_live_buying_power(account, key):
    value = account.get(key)
    if value is None:
        return 0.0
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


def _apply_live_realized_pnl(account, position, fill_price, filled_shares):
    if filled_shares <= 0:
        return account
    realized = (float(fill_price) - float(position["buy_price"])) * int(filled_shares)
    account["realized_pnl_today"] = round(float(account.get("realized_pnl_today", 0.0)) + realized, 4)
    return account


def _collect_protective_stop_order_ids(portfolio):
    stop_order_ids = set()
    for position in portfolio or []:
        stop_order_id = resolve_protective_stop_order_id(position)
        if stop_order_id:
            stop_order_ids.add(stop_order_id)
    return stop_order_ids


_UNRESOLVED_EXECUTION_STATUSES = {"partial_unresolved", "zero_fill_unresolved"}


def _position_has_unresolved_execution_state(position: dict | None) -> bool:
    if not isinstance(position, dict):
        return False
    if position.get("entry_order_unresolved") or position.get("exit_order_unresolved"):
        return True
    entry_status = str(position.get("entry_order_execution_status") or "").strip().lower()
    exit_status = str(position.get("exit_order_execution_status") or "").strip().lower()
    return entry_status in _UNRESOLVED_EXECUTION_STATUSES or exit_status in _UNRESOLVED_EXECUTION_STATUSES


def _portfolio_has_unresolved_execution_state(portfolio) -> bool:
    return any(_position_has_unresolved_execution_state(position) for position in portfolio or [])


def _coerce_jst_datetime(value):
    if not isinstance(value, datetime.datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=JST)
    return value.astimezone(JST)


def _describe_board_quote_snapshot_freshness(boards, reference_time, max_age_seconds=300):
    reference_dt = _coerce_jst_datetime(reference_time)
    if reference_dt is None:
        return False, ("reference_time_missing",)

    evidence = [
        f"reference_time={reference_dt.isoformat()}",
        f"max_age_seconds={int(max_age_seconds)}",
    ]
    if not boards:
        evidence.append("board_snapshot_missing")
        return False, tuple(evidence)

    max_age = datetime.timedelta(seconds=int(max_age_seconds))
    for code, board in boards.items():
        code_text = str(code or "").strip() or "unknown"
        if not isinstance(board, dict):
            evidence.append(f"{code_text}:invalid_board")
            return False, tuple(evidence)
        raw_quote_timestamp = board.get("quote_timestamp")
        source = "quote_timestamp"
        if raw_quote_timestamp is None:
            raw_quote_timestamp = board.get("current_price_timestamp")
            source = "current_price_timestamp" if raw_quote_timestamp is not None else "missing"
        quote_dt = _coerce_jst_datetime(raw_quote_timestamp)
        received_dt = _coerce_jst_datetime(board.get("received_at"))
        evidence.append(f"{code_text}:source={source}")
        evidence.append(f"{code_text}:quote_timestamp={quote_dt.isoformat() if quote_dt else 'missing'}")
        evidence.append(f"{code_text}:received_at={received_dt.isoformat() if received_dt else 'missing'}")
        if quote_dt is None:
            # 受信時刻だけでは価格時刻の freshness を保証できないので、entry では落とす。
            evidence.append(f"{code_text}:missing_quote_timestamp")
            return False, tuple(evidence)
        if quote_dt.date() != reference_dt.date():
            evidence.append(f"{code_text}:cross_day_quote_timestamp")
            return False, tuple(evidence)
        if quote_dt > reference_dt + datetime.timedelta(minutes=1):
            evidence.append(f"{code_text}:quote_timestamp_future")
            return False, tuple(evidence)
        age_seconds = int((reference_dt - quote_dt).total_seconds())
        evidence.append(f"{code_text}:age_seconds={age_seconds}")
        if reference_dt - quote_dt > max_age:
            evidence.append(f"{code_text}:stale_over_max_age")
            return False, tuple(evidence)

    evidence.append("board_snapshot_fresh=true")
    return True, tuple(evidence)


def _is_board_quote_snapshot_fresh(boards, reference_time, max_age_seconds=300):
    return _describe_board_quote_snapshot_freshness(boards, reference_time, max_age_seconds=max_age_seconds)[0]


def _find_live_managed_position_for_entry(broker, code, execution_id=None, execution_ids=None, shares=None):
    if broker is None or not hasattr(broker, "get_positions"):
        return None

    try:
        live_positions = broker.get_positions()
    except Exception as exc:
        print(f"⚠️ {code} のライブ建玉照合に失敗しました: {exc}")
        return None

    code_str = str(code)
    execution_id_str = str(execution_id or "").strip()
    execution_id_set = {execution_id_str} if execution_id_str else set()
    for item in execution_ids or []:
        execution_text = str(item or "").strip()
        if execution_text:
            execution_id_set.add(execution_text)

    exact_matches = []

    for position in live_positions or []:
        if str(position.get("code")) != code_str:
            continue
        ownership = str(position.get("ownership", "")).upper()
        if ownership != "MANAGED_BY_BOT":
            continue

        live_execution_id = str(position.get("execution_id") or "").strip()
        if execution_id_set and live_execution_id in execution_id_set:
            exact_matches.append(position)

    if exact_matches:
        return exact_matches[0]
    return None


def _arm_daytrade_protective_stop(broker, position, trigger_price, expected_shares=None):
    if broker is None or not hasattr(broker, "execute_stop_order"):
        return None

    code = str(position.get("code") or "").strip()
    if not code:
        return None

    trigger_price = float(trigger_price or 0.0)
    if trigger_price <= 0:
        return None

    execution_id = position.get("execution_id")
    execution_ids = position.get("execution_ids")
    shares = int(expected_shares if expected_shares is not None else position.get("shares", 0) or 0)
    if shares <= 0:
        return None

    normalized_execution_ids = []
    raw_execution_ids = execution_ids
    if isinstance(raw_execution_ids, str):
        raw_execution_ids = [raw_execution_ids]
    elif raw_execution_ids is None:
        raw_execution_ids = []
    elif not isinstance(raw_execution_ids, (list, tuple, set)):
        raw_execution_ids = [raw_execution_ids]
    for item in raw_execution_ids:
        execution_text = str(item or "").strip()
        if execution_text and execution_text not in normalized_execution_ids:
            normalized_execution_ids.append(execution_text)
    execution_id_text = str(execution_id or "").strip()
    if execution_id_text and execution_id_text not in normalized_execution_ids:
        normalized_execution_ids.insert(0, execution_id_text)
    managed_execution_ids = set(normalized_execution_ids)

    pending_stop_order_id = str(position.get("protective_stop_unconfirmed_order_id") or "").strip()
    if pending_stop_order_id:
        print(f"⚠️ {code} の保護逆指値は未確認の注文 ID {pending_stop_order_id} が残っているため、新規 armed を止めました。")
        position["protective_stop_status"] = "failed"
        position["protective_stop_confirmation_reason"] = "protective_stop_pending_confirmation"
        return None

    close_route = None
    build_close_positions = getattr(broker, "_build_close_positions_for_symbol", None)
    if callable(build_close_positions):
        try:
            close_route = build_close_positions(
                code,
                shares,
                managed_execution_ids=managed_execution_ids or None,
            )
        except TypeError:
            close_route = build_close_positions(code, shares)

    close_positions = None
    exchange = None
    margin_trade_type = None
    hold_id = None
    live_position = None
    if close_route and close_route.get("close_positions"):
        close_positions = list(close_route["close_positions"])
        exchange = close_route.get("exchange")
        margin_trade_type = close_route.get("margin_trade_type")
        hold_ids = [
            str(item.get("HoldID") or "").strip()
            for item in close_positions
            if isinstance(item, dict) and str(item.get("HoldID") or "").strip()
        ]
        if len(hold_ids) == 1:
            hold_id = hold_ids[0]
    else:
        if len(managed_execution_ids) != 1:
            print(f"⚠️ {code} の保護逆指値は複数 execution_id のため close route を解決できず、fallback を中止しました。execution_ids={normalized_execution_ids}")
            position["protective_stop_status"] = "failed"
            position["protective_stop_confirmation_reason"] = "multiple_execution_ids_without_close_route"
            position["protective_stop_cancelled_order_id"] = None
            position["protective_stop_unconfirmed_order_id"] = None
            return None
        live_position = _find_live_managed_position_for_entry(
            broker=broker,
            code=code,
            execution_id=execution_id,
            execution_ids=execution_ids,
            shares=expected_shares if expected_shares is not None else position.get("shares"),
        )
        if live_position is None:
            print(f"⚠️ {code} の保護逆指値を設定するためのライブ建玉が特定できませんでした。")
            return None

        hold_id = str(live_position.get("hold_id") or live_position.get("execution_id") or "").strip()
        if not hold_id:
            print(f"⚠️ {code} の保護逆指値に必要な HoldID が取得できませんでした。")
            return None

        if live_position.get("hold_qty") is None or live_position.get("available_qty") is None:
            print(f"⚠️ {code} の保護逆指値に必要な建玉数量が不明です。")
            return None

        live_hold_qty = int(live_position.get("hold_qty") or 0)
        live_available_qty = int(live_position.get("available_qty") or 0)
        if live_hold_qty != shares or live_available_qty != shares:
            print(f"⚠️ {code} の保護逆指値は建玉数量が一致しないため fallback を中止しました。hold_qty={live_hold_qty}, available_qty={live_available_qty}, requested_shares={shares}")
            position["protective_stop_status"] = "failed"
            position["protective_stop_confirmation_reason"] = "protective_stop_fallback_qty_mismatch"
            position["protective_stop_cancelled_order_id"] = None
            position["protective_stop_unconfirmed_order_id"] = None
            return None

        exchange = live_position.get("exchange")
        margin_trade_type = live_position.get("margin_trade_type")

    stop_result = broker.execute_stop_order(
        code,
        shares,
        action=StockOrderAction.MARGIN_CLOSE_LONG,
        trigger_price=trigger_price,
        hold_id=hold_id,
        close_positions=close_positions,
        exchange=None if exchange is None else int(exchange),
        margin_trade_type=None if margin_trade_type is None else int(margin_trade_type),
    )
    stop_order_id = getattr(stop_result, "broker_order_id", None)
    stop_accepted = _is_submission_accepted(stop_result)
    stop_confirmed = _is_submission_confirmed(stop_result)
    if stop_accepted and stop_order_id and stop_confirmed:
        if close_positions and len(close_positions) > 1:
            position["hold_ids"] = tuple(
                str(item.get("HoldID") or "").strip()
                for item in close_positions
                if isinstance(item, dict) and str(item.get("HoldID") or "").strip()
            )
            position.pop("hold_id", None)
        elif hold_id:
            position["hold_id"] = hold_id
        if exchange is not None:
            position["exchange"] = exchange
        if margin_trade_type is not None:
            position["margin_trade_type"] = margin_trade_type
        position["protective_stop_order_id"] = stop_order_id
        position["protective_stop_cancelled_order_id"] = None
        position["protective_stop_unconfirmed_order_id"] = None
        position["protective_stop_confirmation_reason"] = None
        position["protective_stop_trigger_price"] = round(trigger_price, 1)
        position["protective_stop_status"] = "armed"
        return stop_order_id

    if stop_accepted and stop_order_id and not stop_confirmed:
        confirmation_reason = str(getattr(stop_result, "confirmation_reason", "") or "stop_order_unconfirmed")
        print(f"⚠️ {code} の保護逆指値は受理されましたが、orders API で確認できなかったため armed しませんでした: {confirmation_reason}")
        position["protective_stop_status"] = "failed"
        position["protective_stop_confirmation_reason"] = confirmation_reason
        position["protective_stop_cancelled_order_id"] = None
        position["protective_stop_unconfirmed_order_id"] = stop_order_id
        return None

    position["protective_stop_status"] = "failed"
    return None


def build_daytrade_position_record(item, executed_price, shares, buy_time, execution_id=None, execution_ids=None):
    setup_type = str(item.get("setup_type", ""))
    stop_mult = float(item.get("stop_mult", resolve_daytrade_intraday_stop_mult(STOP_LOSS_ATR)))
    target_mult = float(item.get("target_mult", resolve_daytrade_intraday_target_mult()))
    buy_atr = float(item.get("atr", 0.0))
    entry_stop_price = max(0.01, float(executed_price) - (buy_atr * stop_mult))
    entry_target_price = float(executed_price) + (buy_atr * target_mult)

    normalized_execution_ids = []
    for item_execution_id in (execution_ids or []):
        execution_text = str(item_execution_id or "").strip()
        if execution_text and execution_text not in normalized_execution_ids:
            normalized_execution_ids.append(execution_text)
    execution_id_text = str(execution_id or "").strip() or None
    if execution_id_text and execution_id_text not in normalized_execution_ids:
        normalized_execution_ids.insert(0, execution_id_text)
    if not execution_id_text and normalized_execution_ids:
        execution_id_text = normalized_execution_ids[0]

    return {
        "code": str(item["code"]),
        "name": item.get("name", str(item["code"])),
        "setup_type": setup_type,
        "buy_time": buy_time,
        "entry_timestamp": buy_time,
        "buy_price": round(float(executed_price), 1),
        "highest_price": round(float(executed_price), 1),
        "lowest_price": round(float(executed_price), 1),
        "post_entry_high": round(float(executed_price), 1),
        "post_entry_low": round(float(executed_price), 1),
        "current_price": round(float(executed_price), 1),
        "last_quote_timestamp": buy_time,
        "shares": int(shares),
        "execution_id": execution_id_text,
        "execution_ids": tuple(normalized_execution_ids),
        "hold_id": None,
        "exchange": None,
        "margin_trade_type": None,
        "buy_atr": buy_atr,
        "stop_mult": stop_mult,
        "target_mult": target_mult,
        "entry_stop_price": round(float(entry_stop_price), 1),
        "entry_target_price": round(float(entry_target_price), 1),
        "entry_candidate_rank": item.get("candidate_rank"),
        "entry_breadth": item.get("breadth"),
        "entry_market_ratio": item.get("market_ratio"),
        "buy_gap_pct": item.get("gap_pct"),
        "buy_live_gap_pct": item.get("live_gap_pct", item.get("gap_pct")),
        "buy_prev_return": item.get("prev_return"),
        "buy_open_vs_sma_atr": item.get("open_vs_sma_atr"),
        "buy_score": item.get("score"),
        "buy_rs": item.get("rs_alpha"),
        "buy_rsi2": item.get("prev_rsi2"),
        "protective_stop_order_id": None,
        "protective_stop_trigger_price": None,
        "protective_stop_status": None,
        "entry_order_execution_status": "completed",
        "entry_order_unresolved": False,
        "entry_order_unresolved_reason": None,
        "entry_order_submission_status": None,
        "entry_order_filled_qty": int(shares),
        "entry_order_remaining_qty": 0,
        "exit_order_execution_status": None,
        "exit_order_unresolved": False,
        "exit_order_unresolved_reason": None,
        "exit_order_submission_status": None,
        "exit_order_filled_qty": 0,
        "exit_order_remaining_qty": 0,
    }


def build_daytrade_exit_log_row(
    position,
    *,
    exit_reason,
    observed_price,
    modeled_exit_price,
    exit_time,
    session_open=None,
    session_high=None,
    session_low=None,
    filled_shares=None,
    remaining_shares=0,
    is_simulation=True,
    is_partial_fill=False,
):
    buy_price = float(position["buy_price"])
    buy_atr = float(position.get("buy_atr", 0.0))
    shares = int(position.get("shares", 0) if filled_shares is None else filled_shares)
    stop_price = float(position.get("entry_stop_price", max(0.01, buy_price - (buy_atr * float(position.get("stop_mult", resolve_daytrade_intraday_stop_mult(STOP_LOSS_ATR)))))))
    target_price = float(position.get("entry_target_price", buy_price + (buy_atr * float(position.get("target_mult", resolve_daytrade_intraday_target_mult())))))

    observed_price = float(observed_price if observed_price is not None else buy_price)
    modeled_exit_price = float(modeled_exit_price if modeled_exit_price is not None else observed_price)
    session_open = float(session_open if session_open not in (None, 0) else buy_price)
    session_high = float(session_high if session_high not in (None, 0) else max(buy_price, observed_price))
    session_low = float(session_low if session_low not in (None, 0) else min(buy_price, observed_price))

    observed_pnl = (observed_price - buy_price) * shares
    modeled_pnl = (modeled_exit_price - buy_price) * shares
    observed_return_pct = (observed_price / buy_price - 1.0) if buy_price > 0 else 0.0
    modeled_return_pct = (modeled_exit_price / buy_price - 1.0) if buy_price > 0 else 0.0
    session_runup_pct = (session_high / buy_price - 1.0) if buy_price > 0 else 0.0
    session_drawdown_pct = (session_low / buy_price - 1.0) if buy_price > 0 else 0.0
    drawdown_from_session_high_pct = (observed_price / session_high - 1.0) if session_high > 0 else 0.0
    fade_from_session_high_pct = drawdown_from_session_high_pct
    rebound_from_session_low_pct = (observed_price / session_low - 1.0) if session_low > 0 else 0.0

    return {
        "time": exit_time,
        "trade_id": f"{position['code']}|{position['buy_time']}",
        "code": str(position["code"]),
        "name": position.get("name", position["code"]),
        "buy_time": position["buy_time"],
        "setup_type": position.get("setup_type", ""),
        "exit_reason": str(exit_reason or ""),
        "is_simulation": bool(is_simulation),
        "is_partial_fill": bool(is_partial_fill),
        "observed_price": round(observed_price, 4),
        "modeled_exit_price": round(modeled_exit_price, 4),
        "observed_pnl": round(observed_pnl, 4),
        "modeled_pnl": round(modeled_pnl, 4),
        "observed_return_pct": round(observed_return_pct, 6),
        "modeled_return_pct": round(modeled_return_pct, 6),
        "session_open": round(session_open, 4),
        "session_high": round(session_high, 4),
        "session_low": round(session_low, 4),
        "held_shares": int(position.get("shares", 0)),
        "filled_shares": int(shares),
        "remaining_shares": int(remaining_shares),
        "buy_price": round(buy_price, 4),
        "buy_atr": round(buy_atr, 4),
        "entry_candidate_rank": position.get("entry_candidate_rank"),
        "entry_stop_mult": position.get("stop_mult"),
        "entry_stop_price": round(stop_price, 4),
        "entry_target_mult": position.get("target_mult"),
        "entry_target_price": round(target_price, 4),
        "entry_breadth": position.get("entry_breadth"),
        "entry_market_ratio": position.get("entry_market_ratio"),
        "buy_gap_pct": position.get("buy_gap_pct"),
        "buy_live_gap_pct": position.get("buy_live_gap_pct"),
        "buy_prev_return": position.get("buy_prev_return"),
        "buy_open_vs_sma_atr": position.get("buy_open_vs_sma_atr"),
        "buy_score": position.get("buy_score"),
        "buy_rs": position.get("buy_rs"),
        "buy_rsi2": position.get("buy_rsi2"),
        "current_pnl": round(observed_pnl, 4),
        "current_return_pct": round(observed_return_pct, 6),
        "distance_to_stop_pct": round((observed_price - stop_price) / buy_price if buy_price > 0 else 0.0, 6),
        "distance_to_stop_atr": round((observed_price - stop_price) / buy_atr if buy_atr > 0 else 0.0, 6),
        "distance_to_target_pct": round((target_price - observed_price) / buy_price if buy_price > 0 else 0.0, 6),
        "distance_to_target_atr": round((target_price - observed_price) / buy_atr if buy_atr > 0 else 0.0, 6),
        "session_runup_pct": round(session_runup_pct, 6),
        "session_drawdown_pct": round(session_drawdown_pct, 6),
        "drawdown_from_session_high_pct": round(drawdown_from_session_high_pct, 6),
        "fade_from_session_high_pct": round(fade_from_session_high_pct, 6),
        "rebound_from_session_low_pct": round(rebound_from_session_low_pct, 6),
    }


def append_daytrade_exit_log(row):
    append_csv_rows(DAYTRADE_EXIT_LOG_FILE, [row])


def compute_daytrade_snapshot(data_df, symbols_df, targets, regime):
    bundle = calculate_all_technicals_v12(data_df)
    close = bundle["Close"].iloc[-1]
    sma_long = bundle[f"SMA{SMA_LONG_PERIOD}"].iloc[-1]
    market_open = np.nan
    prev_market_sma_trend = np.nan
    if "1321.T" in bundle["Open"].columns and len(bundle["Open"]) >= 2:
        market_open = bundle["Open"]["1321.T"].iloc[-1]
        prev_market_sma_trend = bundle[f"SMA{SMA_TREND_PERIOD}"]["1321.T"].iloc[-2]
    prime_ref = set(get_prime_tickers())
    elite_cols = [ticker for ticker in close.index if ticker in prime_ref and ticker in sma_long.index]
    breadth_val = 0.0
    if elite_cols:
        breadth_val = float(np.mean([
            float(close[ticker]) > float(sma_long[ticker])
            for ticker in elite_cols
            if pd.notna(close[ticker]) and pd.notna(sma_long[ticker])
        ]))
    market_ratio = np.nan
    if not pd.isna(market_open) and not pd.isna(prev_market_sma_trend) and float(prev_market_sma_trend) > 0:
        market_ratio = float(market_open) / float(prev_market_sma_trend)

    top_candidates = select_best_candidates(
        data_df=data_df,
        targets=targets,
        symbols_df=symbols_df,
        regime=regime,
        breadth_val=breadth_val,
    )
    latest_close_map = {
        str(col).replace(".T", ""): float(close[col])
        for col in close.index
        if pd.notna(close[col])
    }
    return {
        "top_candidates": top_candidates,
        "breadth": breadth_val,
        "market_ratio": market_ratio,
        "latest_close_map": latest_close_map,
    }


def close_daytrade_positions(portfolio, account, broker, is_sim, realtime_buffers):
    original_positions = [dict(position) for position in portfolio]
    updated_portfolio, sell_actions, fill_events = manage_positions_live(
        portfolio=portfolio,
        broker=broker,
        is_simulation=is_sim,
        realtime_buffers=realtime_buffers,
    )
    if is_sim and original_positions:
        for position in original_positions:
            current_price = float(position.get("current_price", position["buy_price"]))
            sell_price = current_price * (1.0 - SLIPPAGE_RATE)
            shares = int(position["shares"])
            pnl = (sell_price - float(position["buy_price"])) * shares
            account["cash"] = round(float(account["cash"]) + (sell_price * shares), 4)
            broker.log_trade({
                "time": datetime.datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S'),
                "code": position["code"],
                "name": position.get("name", position["code"]),
                "side": "DAYTRADE_SELL",
                "shares": shares,
                "buy_price": round(float(position["buy_price"]), 4),
                "sell_price": round(float(sell_price), 4),
                "pnl": round(float(pnl), 4),
                "holding_days": 0,
                "note": "daytrade_flatten",
            })
            append_daytrade_exit_log(
                build_daytrade_exit_log_row(
                    position,
                    exit_reason="daytrade_flatten",
                    observed_price=sell_price,
                    modeled_exit_price=current_price,
                    exit_time=datetime.datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S'),
                    session_open=position.get("buy_price"),
                    session_high=position.get("post_entry_high", position.get("highest_price", current_price)),
                    session_low=position.get("post_entry_low", min(float(position.get("buy_price", current_price)), float(current_price))),
                    filled_shares=shares,
                    remaining_shares=0,
                    is_simulation=True,
                    is_partial_fill=False,
                )
            )
    elif original_positions:
        for fill_event in fill_events:
            position = fill_event["position"]
            shares = int(fill_event["filled_shares"])
            observed_price = float(fill_event["observed_price"])
            modeled_exit_price = float(fill_event["modeled_exit_price"])
            exit_reason = fill_event["exit_reason"]
            remaining_shares = int(fill_event["remaining_shares"])
            account = _apply_live_realized_pnl(account, position, observed_price, shares)
            broker.log_trade({
                "time": fill_event["exit_time"],
                "code": position["code"],
                "name": position.get("name", position["code"]),
                "side": "DAYTRADE_SELL",
                "shares": shares,
                "buy_price": round(float(position["buy_price"]), 4),
                "sell_price": round(float(observed_price), 4),
                "pnl": round((observed_price - float(position["buy_price"])) * shares, 4),
                "holding_days": 0,
                "note": exit_reason,
            })
            append_daytrade_exit_log(
                build_daytrade_exit_log_row(
                    position,
                    exit_reason=exit_reason,
                    observed_price=observed_price,
                    modeled_exit_price=modeled_exit_price,
                    exit_time=fill_event["exit_time"],
                    session_open=fill_event.get("session_open"),
                    session_high=fill_event.get("session_high"),
                    session_low=fill_event.get("session_low"),
                    filled_shares=shares,
                    remaining_shares=remaining_shares,
                    is_simulation=False,
                    is_partial_fill=remaining_shares > 0,
                )
            )
    return updated_portfolio, sell_actions, account


def close_daytrade_positions_by_signal(portfolio, account, broker, is_sim, realtime_buffers):
    if not portfolio:
        return [], [], account

    remaining_portfolio = []
    exit_actions = []
    exit_time = datetime.datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')

    for position in portfolio:
        code = str(position["code"])
        ownership = str(position.get("ownership", "MANAGED_BY_BOT" if is_sim else "AMBIGUOUS")).upper()
        if not is_sim and position.get("exit_order_unresolved"):
            remaining_portfolio.append(position)
            exit_actions.append(f"SKIP {code} - unresolved exit order pending")
            continue
        if not is_sim and ownership != "MANAGED_BY_BOT":
            remaining_portfolio.append(position)
            exit_actions.append(f"SKIP {code} - unmanaged position ({ownership})")
            continue
        buffer = realtime_buffers.get(code)
        if buffer is None:
            remaining_portfolio.append(position)
            continue

        current_price = float(buffer.get_latest_price() or position.get("current_price", position["buy_price"]))
        if current_price <= 0:
            remaining_portfolio.append(position)
            continue

        session_open = float(buffer.get_session_open() or position.get("buy_price") or current_price)
        session_high = max(
            float(position.get("post_entry_high", position.get("highest_price", position["buy_price"]))),
            float(current_price),
        )
        session_low = float(position.get("post_entry_low", position.get("lowest_price", position["buy_price"])))
        if not session_low or session_low <= 0:
            session_low = min(float(position.get("buy_price", current_price)), current_price)

        buy_price = float(position["buy_price"])
        buy_atr = float(position.get("buy_atr", 0.0))
        stop_mult = float(position.get("stop_mult", resolve_daytrade_intraday_stop_mult(STOP_LOSS_ATR)))
        target_mult = float(position.get("target_mult", resolve_daytrade_intraday_target_mult()))
        fallback_stop_price, fallback_target_price = calculate_position_stops(
            buy_price,
            buy_atr,
            float(position.get("highest_price", buy_price)),
            current_price,
            stop_mult,
            target_mult,
        )
        stop_price = float(position.get("entry_stop_price", fallback_stop_price))
        target_price = float(position.get("entry_target_price", fallback_target_price))

        modeled_exit_price, exit_reason = resolve_daytrade_live_exit_decision(
            setup_type=position.get("setup_type"),
            buy_price=buy_price,
            open_price=session_open,
            high_price=session_high,
            low_price=session_low,
            current_price=current_price,
            stop_price=stop_price,
            target_price=target_price,
            session_high=session_high,
            allow_close_exit=False,
        )
        if not exit_reason or modeled_exit_price is None:
            remaining_portfolio.append(position)
            continue

        shares = int(position["shares"])
        stop_order_id = resolve_protective_stop_order_id(position)
        if not is_sim and stop_order_id:
            stop_cancel_ok, stop_cancel_result = cancel_linked_protective_stop_before_exit(
                broker=broker,
                position=position,
                stop_order_id=stop_order_id,
            )
            if not stop_cancel_ok:
                unresolved_position = dict(position)
                unresolved_position["protective_stop_cancel_unresolved"] = True
                unresolved_position["exit_order_unresolved"] = True
                cancel_reason = None
                if stop_cancel_result is not None:
                    cancel_reason = getattr(stop_cancel_result, "rejection_reason", None)
                    cancel_status = getattr(stop_cancel_result, "status", None)
                    if cancel_reason is None and cancel_status is not None:
                        cancel_reason = getattr(cancel_status, "value", str(cancel_status))
                unresolved_position["protective_stop_cancel_reason"] = cancel_reason
                unresolved_position["exit_order_unresolved_reason"] = cancel_reason or "protective_stop_cancel_unconfirmed"
                unresolved_position["exit_order_submission_status"] = None if stop_cancel_result is None else getattr(getattr(stop_cancel_result, "status", None), "value", None)
                unresolved_position["exit_order_remaining_qty"] = shares
                remaining_portfolio.append(unresolved_position)
                exit_actions.append(f"SKIP {code} - protective stop cancel unresolved")
                continue
        if is_sim:
            observed_price = float(modeled_exit_price) * (1.0 - SLIPPAGE_RATE)
            account["cash"] = round(float(account["cash"]) + (observed_price * shares), 4)
            broker.log_trade({
                "time": exit_time,
                "code": position["code"],
                "name": position.get("name", position["code"]),
                "side": "DAYTRADE_SELL",
                "shares": shares,
                "buy_price": round(float(position["buy_price"]), 4),
                "sell_price": round(float(observed_price), 4),
                "pnl": round((observed_price - float(position["buy_price"])) * shares, 4),
                "holding_days": 0,
                "note": exit_reason,
            })
            append_daytrade_exit_log(
                build_daytrade_exit_log_row(
                    position,
                    exit_reason=exit_reason,
                    observed_price=observed_price,
                    modeled_exit_price=modeled_exit_price,
                    exit_time=exit_time,
                    session_open=session_open,
                    session_high=session_high,
                    session_low=session_low,
                    filled_shares=shares,
                    remaining_shares=0,
                    is_simulation=True,
                    is_partial_fill=False,
                )
            )
            exit_actions.append(f"SELL {code} - {exit_reason} (@{observed_price:,.1f})")
            continue

        details = broker.execute_chase_order(code, shares, action=StockOrderAction.MARGIN_CLOSE_LONG, atr=buy_atr)
        filled_shares = 0
        observed_price = current_price
        if isinstance(details, dict) and details:
            filled_shares = int(details.get("filled_qty", details.get("Qty", 0)) or 0)
            observed_price = float(details.get("average_price", details.get("Price", current_price)) or current_price)
        if filled_shares <= 0:
            if isinstance(details, dict) and details.get("unresolved"):
                unresolved_position = dict(position)
                unresolved_position["exit_order_unresolved"] = True
                unresolved_position["exit_order_execution_status"] = details.get("exit_execution_status") or details.get("execution_status") or "zero_fill_unresolved"
                unresolved_position["exit_order_unresolved_reason"] = details.get("terminal_reason") or details.get("process_state") or "unknown"
                unresolved_position["exit_order_submission_status"] = details.get("submission_status")
                unresolved_position["exit_order_remaining_qty"] = int(details.get("remaining_qty", shares) or shares)
                remaining_portfolio.append(unresolved_position)
            else:
                remaining_portfolio.append(position)
            continue

        remaining_shares = max(0, shares - filled_shares)
        account = _apply_live_realized_pnl(account, position, observed_price, filled_shares)
        broker.log_trade({
            "time": exit_time,
            "code": position["code"],
            "name": position.get("name", position["code"]),
            "side": "DAYTRADE_SELL",
            "shares": filled_shares,
            "buy_price": round(float(position["buy_price"]), 4),
            "sell_price": round(float(observed_price), 4),
            "pnl": round((observed_price - float(position["buy_price"])) * filled_shares, 4),
            "holding_days": 0,
            "note": exit_reason,
        })
        append_daytrade_exit_log(
            build_daytrade_exit_log_row(
                position,
                exit_reason=exit_reason,
                observed_price=observed_price,
                modeled_exit_price=modeled_exit_price,
                exit_time=exit_time,
                session_open=session_open,
                session_high=session_high,
                session_low=session_low,
                filled_shares=filled_shares,
                remaining_shares=remaining_shares,
                is_simulation=False,
                is_partial_fill=remaining_shares > 0,
            )
        )
        exit_actions.append(f"SELL {code} - {exit_reason} (@{observed_price:,.1f})")
        if remaining_shares > 0:
            remaining_position = dict(position)
            remaining_position["shares"] = remaining_shares
            remaining_position["current_price"] = round(observed_price, 1)
            remaining_position["highest_price"] = round(max(float(position.get("highest_price", buy_price)), session_high), 1)
            remaining_position["lowest_price"] = round(min(float(position.get("lowest_price", buy_price)), session_low), 1)
            remaining_position["post_entry_high"] = remaining_position["highest_price"]
            remaining_position["post_entry_low"] = remaining_position["lowest_price"]
            remaining_position["last_quote_timestamp"] = exit_time
            if isinstance(details, dict) and details.get("unresolved"):
                remaining_position["exit_order_unresolved"] = True
                remaining_position["exit_order_execution_status"] = details.get("exit_execution_status") or details.get("execution_status") or "partial_unresolved"
                remaining_position["exit_order_unresolved_reason"] = details.get("terminal_reason") or details.get("process_state") or "unknown"
                remaining_position["exit_order_submission_status"] = details.get("submission_status")
                remaining_position["exit_order_filled_qty"] = filled_shares
                remaining_position["exit_order_remaining_qty"] = remaining_shares
            elif not is_sim and stop_order_id:
                remaining_position["protective_stop_order_id"] = None
                remaining_position["protective_stop_unconfirmed_order_id"] = None
                remaining_position["protective_stop_trigger_price"] = None
                remaining_position["protective_stop_status"] = None
                rearmed_stop_order_id = _arm_daytrade_protective_stop(
                    broker,
                    remaining_position,
                    trigger_price=float(position.get("entry_stop_price", stop_price)),
                    expected_shares=remaining_shares,
                )
                if rearmed_stop_order_id:
                    exit_actions.append(f"STOP {code} - protective stop rearmed (ID: {rearmed_stop_order_id})")
                else:
                    remaining_position["protective_stop_status"] = "failed"
                    remaining_position["exit_order_unresolved"] = True
                    remaining_position["exit_order_unresolved_reason"] = "protective_stop_rearm_failed"
                    remaining_position["exit_order_submission_status"] = "unknown"
                    remaining_position["exit_order_remaining_qty"] = remaining_shares
                    exit_actions.append(f"STOP {code} - protective stop rearm failed")
            remaining_portfolio.append(remaining_position)

    return remaining_portfolio, exit_actions, account


def request_shutdown(reason: str):
    global SHUTDOWN_REQUESTED, SHUTDOWN_REASON
    SHUTDOWN_REQUESTED = True
    SHUTDOWN_REASON = str(reason or "shutdown")


def _normalize_shutdown_order_id(order: dict) -> str:
    return str(order.get("ID") or order.get("OrderId") or order.get("OrderID") or "").strip()


def _classify_shutdown_portfolio_items(portfolio: list[dict] | None) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    managed: list[dict] = []
    unmanaged: list[dict] = []
    ambiguous: list[dict] = []
    unknown: list[dict] = []
    for position in portfolio or []:
        ownership = str(position.get("ownership", "")).upper()
        if ownership == "MANAGED_BY_BOT":
            managed.append(position)
        elif ownership == "UNMANAGED":
            unmanaged.append(position)
        elif ownership == "AMBIGUOUS":
            ambiguous.append(position)
        else:
            unknown.append(position)
    return managed, unmanaged, ambiguous, unknown


def _classify_shutdown_orders(active_orders_info: dict | None, portfolio: list[dict] | None) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    managed_positions, unmanaged_positions, ambiguous_positions, unknown_positions = _classify_shutdown_portfolio_items(portfolio)
    managed_symbols = {str(position.get("code") or "").replace(".T", "") for position in managed_positions}
    unmanaged_symbols = {str(position.get("code") or "").replace(".T", "") for position in unmanaged_positions}
    ambiguous_symbols = {str(position.get("code") or "").replace(".T", "") for position in ambiguous_positions}
    protected_stop_ids = _collect_protective_stop_order_ids(portfolio or [])

    managed_orders: list[dict] = []
    unmanaged_orders: list[dict] = []
    ambiguous_orders: list[dict] = []
    unknown_orders: list[dict] = []

    if active_orders_info is None:
        if managed_positions or unmanaged_positions or ambiguous_positions or unknown_positions:
            unknown_orders.append({
                "kind": "orders_snapshot_unavailable",
                "reason": "get_active_orders_failed",
            })
        return managed_orders, unmanaged_orders, ambiguous_orders, unknown_orders

    for order in active_orders_info.get("orders", []):
        if not isinstance(order, dict):
            continue
        order_id = _normalize_shutdown_order_id(order)
        symbol = str(order.get("Symbol") or order.get("symbol") or "").replace(".T", "")
        if order_id and order_id in protected_stop_ids:
            managed_orders.append(order)
        elif symbol and symbol in managed_symbols:
            managed_orders.append(order)
        elif symbol and symbol in unmanaged_symbols:
            unmanaged_orders.append(order)
        elif symbol and symbol in ambiguous_symbols:
            ambiguous_orders.append(order)
        else:
            unknown_orders.append(order)

    for unresolved_order_id in active_orders_info.get("unresolved_order_ids", []):
        if unresolved_order_id:
            unknown_orders.append({
                "kind": "unresolved_order",
                "order_id": unresolved_order_id,
            })

    if active_orders_info.get("has_unknown"):
        unknown_orders.append({
            "kind": "has_unknown",
            "reason": "order_state_unresolved",
        })

    return managed_orders, unmanaged_orders, ambiguous_orders, unknown_orders


def _collect_active_order_ids(active_orders_info: dict | None) -> set[str]:
    active_order_ids: set[str] = set()
    if not isinstance(active_orders_info, dict):
        return active_order_ids
    for order in active_orders_info.get("orders", []):
        if not isinstance(order, dict):
            continue
        for key in ("ID", "OrderId", "OrderID"):
            order_id = str(order.get(key) or "").strip()
            if order_id:
                active_order_ids.add(order_id)
                break
    return active_order_ids


def perform_safe_shutdown(broker, portfolio, account, is_sim, realtime_buffers, reason: str):
    shutdown_msg = f"[STOP] 安全停止を開始します: {reason}"
    print(f"\n{shutdown_msg}")
    try:
        send_discord_notify(f"🛑 {shutdown_msg}")
    except Exception:
        pass

    updated_portfolio = list(portfolio or [])
    updated_account = dict(account or {})
    errors: list[str] = []
    pre_shutdown_active_orders = None
    pre_shutdown_managed_orders: list[dict] = []
    pre_shutdown_unmanaged_orders: list[dict] = []
    pre_shutdown_ambiguous_orders: list[dict] = []
    pre_shutdown_unknown_orders: list[dict] = []
    managed_order_cancel_failed = False

    if broker and not is_sim:
        try:
            pre_shutdown_active_orders = broker.get_active_orders()
            if pre_shutdown_active_orders is None:
                print("⚠️ [STOP] 未約定注文の照会に失敗しました。キャンセルを見送ります。")
                errors.append("active_orders_snapshot_unavailable")
                managed_order_cancel_failed = True
            else:
                (
                    pre_shutdown_managed_orders,
                    pre_shutdown_unmanaged_orders,
                    pre_shutdown_ambiguous_orders,
                    pre_shutdown_unknown_orders,
                ) = _classify_shutdown_orders(pre_shutdown_active_orders, updated_portfolio)
                for order in pre_shutdown_managed_orders:
                    order_id = order.get("ID")
                    if order_id:
                        cancel_result = broker.cancel_order(order_id)
                        cancel_confirmed = bool(cancel_result)
                        cancel_reason = None
                        if not cancel_confirmed:
                            cancel_reason = getattr(cancel_result, "rejection_reason", None)
                            cancel_terminal_status = getattr(cancel_result, "terminal_status", None)
                            if cancel_reason is None and cancel_terminal_status is not None:
                                cancel_reason = getattr(cancel_terminal_status, "value", str(cancel_terminal_status))
                            cancel_status = getattr(cancel_result, "status", None)
                            if cancel_reason is None and cancel_status is not None:
                                cancel_reason = getattr(cancel_status, "value", str(cancel_status))
                        if not cancel_confirmed:
                            managed_order_cancel_failed = True
                            errors.append(f"managed_cancel_unconfirmed:{order_id}:{cancel_reason or 'unknown'}")
                            print(
                                f"⚠️ [STOP] managed order {order_id} の取消が未確定のため、ポジション解消を保留します。"
                            )
                if pre_shutdown_unknown_orders:
                    print("⚠️ [STOP] 終端状態が不明な注文がありました。手動確認が必要です。")
                if pre_shutdown_unmanaged_orders:
                    print("⚠️ [STOP] unmanaged 注文が残っているため、安全停止は保留扱いになります。")
                if pre_shutdown_ambiguous_orders:
                    print("⚠️ [STOP] 所有権が曖昧な注文が残っているため、安全停止は保留扱いになります。")
        except Exception as exc:
            print(f"⚠️ [STOP] 未約定注文のキャンセル中にエラー: {exc}")
            errors.append(f"cancel_orders_error:{exc}")
            managed_order_cancel_failed = True

    pending_protective_stop_positions = [
        position
        for position in updated_portfolio
        if str(position.get("ownership") or "").upper() == "MANAGED_BY_BOT"
        and str(position.get("protective_stop_unconfirmed_order_id") or "").strip()
    ]
    orphan_protective_stop_positions = [
        position
        for position in updated_portfolio
        if str(position.get("ownership") or "").upper() == "MANAGED_BY_BOT"
        and str(position.get("protective_stop_status") or "").lower() == "armed"
        and not str(position.get("protective_stop_order_id") or "").strip()
        and not str(position.get("protective_stop_unconfirmed_order_id") or "").strip()
    ]
    if pending_protective_stop_positions:
        pending_codes = ",".join(sorted({str(position.get("code") or "").strip() for position in pending_protective_stop_positions if str(position.get("code") or "").strip()}))
        print(f"⚠️ [STOP] 未確認の protective stop が残っているため、ポジション解消を保留します: {pending_codes or 'unknown'}")
        errors.append(f"protective_stop_pending:{len(pending_protective_stop_positions)}")
        managed_order_cancel_failed = True
    if orphan_protective_stop_positions:
        orphan_codes = ",".join(sorted({str(position.get("code") or "").strip() for position in orphan_protective_stop_positions if str(position.get("code") or "").strip()}))
        print(f"⚠️ [STOP] orphan protective stop が残っているため、ポジション解消を保留します: {orphan_codes or 'unknown'}")
        errors.append(f"protective_stop_orphan:{len(orphan_protective_stop_positions)}")
        managed_order_cancel_failed = True

    active_stop_ids = _collect_active_order_ids(pre_shutdown_active_orders)
    missing_protective_stop_positions = [
        position
        for position in updated_portfolio
        if str(position.get("ownership") or "").upper() == "MANAGED_BY_BOT"
        and str(position.get("protective_stop_status") or "").lower() == "armed"
        and str(position.get("protective_stop_order_id") or "").strip()
        and not str(position.get("protective_stop_unconfirmed_order_id") or "").strip()
        and str(position.get("protective_stop_order_id") or "").strip() not in active_stop_ids
    ]
    if missing_protective_stop_positions:
        missing_codes = ",".join(sorted({str(position.get("code") or "").strip() for position in missing_protective_stop_positions if str(position.get("code") or "").strip()}))
        print(f"⚠️ [STOP] armed protective stop が broker 側で見つからないため、ポジション解消を保留します: {missing_codes or 'unknown'}")
        errors.append(f"protective_stop_missing:{len(missing_protective_stop_positions)}")
        managed_order_cancel_failed = True

    if updated_portfolio and not managed_order_cancel_failed:
        try:
            updated_portfolio, close_actions, updated_account = close_daytrade_positions(
                portfolio=updated_portfolio,
                account=updated_account,
                broker=broker,
                is_sim=is_sim,
                realtime_buffers=realtime_buffers,
            )
            if close_actions:
                for action in close_actions:
                    print(f"[STOP] {action}")
        except Exception as exc:
            print(f"⚠️ [STOP] ポジション解消中にエラー: {exc}")
            errors.append(f"close_positions_error:{exc}")
    elif managed_order_cancel_failed:
        print("⚠️ [STOP] managed order の取消未確定のため、ポジション解消は見送りました。")

    try:
        if broker:
            broker.save_account(updated_account)
            broker.save_portfolio(updated_portfolio)
    except Exception as exc:
        print(f"⚠️ [STOP] state 保存に失敗しました: {exc}")
        errors.append(f"state_save_error:{exc}")

    post_shutdown_active_orders = None
    if broker and not is_sim:
        try:
            post_shutdown_active_orders = broker.get_active_orders()
        except Exception as exc:
            print(f"⚠️ [STOP] 停止後の未約定注文照会に失敗しました: {exc}")
            errors.append(f"post_shutdown_orders_error:{exc}")

    managed_positions, unmanaged_positions, ambiguous_positions, unknown_positions = _classify_shutdown_portfolio_items(updated_portfolio)
    managed_orders, unmanaged_orders, ambiguous_orders, unknown_orders = _classify_shutdown_orders(
        post_shutdown_active_orders if post_shutdown_active_orders is not None else pre_shutdown_active_orders,
        updated_portfolio,
    )
    success = (
        not errors
        and not managed_positions
        and not managed_orders
        and not unmanaged_positions
        and not unmanaged_orders
        and not ambiguous_positions
        and not ambiguous_orders
        and not unknown_positions
        and not unknown_orders
    )

    if success:
        print("✅ [STOP] 安全停止が完了しました。managed state は解放済みです。")
    else:
        print("⚠️ [STOP] 安全停止は完了しましたが、reconciliation が残っています。")

    return ShutdownResult(
        success=success,
        managed_remaining_orders=tuple(managed_orders),
        managed_remaining_positions=tuple(managed_positions),
        unmanaged_orders=tuple(unmanaged_orders),
        unmanaged_positions=tuple(unmanaged_positions),
        ambiguous_items=tuple(ambiguous_orders) + tuple(ambiguous_positions),
        unknown_items=tuple(unknown_orders) + tuple(unknown_positions),
        errors=tuple(errors),
        updated_portfolio=updated_portfolio,
        updated_account=updated_account,
    )


def perform_non_trading_day_shutdown(broker, portfolio, account, is_sim, realtime_buffers, reason: str):
    shutdown_msg = f"[STOP] 非取引日のため安全停止します: {reason}"
    print(f"\n{shutdown_msg}")

    if is_sim:
        return ShutdownResult(
            success=True,
            managed_remaining_orders=(),
            managed_remaining_positions=(),
            unmanaged_orders=(),
            unmanaged_positions=(),
            ambiguous_items=(),
            unknown_items=(),
            errors=(),
            updated_portfolio=list(portfolio or []),
            updated_account=dict(account or {}),
        )

    shutdown_result = perform_safe_shutdown(
        broker=broker,
        portfolio=portfolio,
        account=account,
        is_sim=is_sim,
        realtime_buffers=realtime_buffers,
        reason=reason,
    )
    if shutdown_result.success:
        from core.kabu_launcher import terminate_kabu_station
        terminate_kabu_station()
    else:
        print("⚠️ [STOP] 非取引日の安全停止が未解決のため、kabuステーション終了は見送ります。")
    return shutdown_result


def record_intraday_snapshots(snapshot_time, boards, realtime_buffers):
    if not boards:
        return
    rows = []
    timestamp = snapshot_time.strftime('%Y-%m-%d %H:%M:%S')
    for code, board in boards.items():
        buffer = realtime_buffers.get(str(code))
        rows.append({
            "time": timestamp,
            "code": str(code),
            "price": board.get("price"),
            "open": board.get("open"),
            "high": board.get("high"),
            "low": board.get("low"),
            "prev_close": board.get("prev_close"),
            "best_sell_price": board.get("best_sell_price"),
            "best_buy_price": board.get("best_buy_price"),
            "volume": board.get("volume"),
            "session_open": None if buffer is None else buffer.get_session_open(),
            "session_high": None if buffer is None else buffer.get_session_high(),
            "session_low": None if buffer is None else buffer.get_session_low(),
        })
    append_csv_rows(INTRADAY_SNAPSHOT_FILE, rows)
    rotate_csv_if_large(INTRADAY_SNAPSHOT_FILE, max_size_mb=20)

# --- シグナルハンドラ ---
def handle_shutdown(signum, frame):
    request_shutdown(f"signal:{signum}")

# --- メインループ ---
def main():
    if not acquire_lock():
        sys.exit(1)
        
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    try:
        _main_exec()
    except Exception as e:
        import traceback
        msg = f"[CRITICAL] 【致命的システムエラー】シミュレーションループ内で予期せぬ例外が発生しました:\n{e}\n{traceback.format_exc()}"
        print(msg)
        try:
            send_discord_notify(msg)
        except:
            pass
        try:
            request_shutdown("unexpected_exception")
            runtime_state = ACTIVE_RUNTIME_STATE
            broker = runtime_state.get("broker")
            if broker is not None:
                shutdown_result = perform_safe_shutdown(
                    broker=broker,
                    portfolio=runtime_state.get("portfolio") or [],
                    account=runtime_state.get("account") or {},
                    is_sim=bool(runtime_state.get("is_sim")),
                    realtime_buffers=runtime_state.get("realtime_buffers") or {},
                    reason="unexpected_exception",
                )
                if shutdown_result.success and not bool(runtime_state.get("is_sim")):
                    from core.kabu_launcher import terminate_kabu_station
                    terminate_kabu_station()
        except Exception as shutdown_exc:
            print(f"⚠️ [CRITICAL] 予期しない例外後の安全停止に失敗しました: {shutdown_exc}")
        time.sleep(1)
        sys.exit(1)
    finally:
        release_lock()

def _main_exec():
    from core.kabu_launcher import ensure_kabu_station_running, terminate_kabu_station, check_api_health

    # --- 【新規】kabuステーションの自動起動・ログイン ---
    if TRADE_MODE in ["KABUCOM_LIVE", "KABUCOM_TEST"]:
        if not ensure_kabu_station_running():
            print("❌ kabuステーションの準備が整わなかったため、システムを終了します。")
            return

    # --- [Imperial Sanctuary Audit] 実行時の各ファイルパスを最終点検 ---
    if True: # DEBUG_MODEに関わらず起動時に一度だけ表示
        print(f"📂 [Sanctuary Audit] PROJECT_ROOT: {PROJECT_ROOT}")
        print(f"📂 [Sanctuary Audit] DATA_ROOT:    {DATA_ROOT}")
        print(f"📂 [Sanctuary Audit] ACCOUNT:      {ACCOUNT_FILE}")
        print(f"📂 [Sanctuary Audit] PORTFOLIO:    {PORTFOLIO_FILE}")
        print(f"📂 [Sanctuary Audit] EXEC_LOG:     {EXECUTION_LOG_FILE}")
        print(f"📂 [Sanctuary Audit] HISTORY:      {HISTORY_FILE}")

    if not pre_flight_check():
        print("❌ [Pre-flight Error] 起動前点検に失敗しました。処理を中断します。")
        return
    
    setup_logging()
    
    from core.file_io import rotate_csv_if_large
    rotate_csv_if_large(EXECUTION_LOG_FILE, max_size_mb=2)
    rotate_csv_if_large(HISTORY_FILE, max_size_mb=2)
    rotate_csv_if_large(DAYTRADE_EXIT_LOG_FILE, max_size_mb=2)
    
    from core.sim_broker import SimulationBroker
    from core.kabucom_broker import KabucomBroker
    
    try:
        if TRADE_MODE == "KABUCOM_LIVE":
            print("[LIVE] 【本番モード】auカブコム証券 本番API (Port 18080) に接続します")
            broker = KabucomBroker.from_trade_mode(TRADE_MODE)
            is_sim = False
        elif TRADE_MODE == "KABUCOM_TEST":
            print("[TEST] 【テストモード】auカブコム証券 検証用API (Port 18081) に接続します")
            broker = KabucomBroker.from_trade_mode(TRADE_MODE)
            is_sim = False
        else:
            print("[SIM] 【シミュレーションモード】ローカルCSVベースで実行します")
            broker = SimulationBroker()
            is_sim = True
    except Exception as e:
        msg = f"❌ 【致命的エラー】証券会社APIの初期化に失敗しました: {e}"
        print(msg)
        send_discord_notify(msg)
        return
    _set_active_runtime_state(broker=broker, is_sim=is_sim)

    live_order_gate_status = None
    live_financial_write_gate_status = None
    if TRADE_MODE == "KABUCOM_LIVE":
        live_order_gate_status = get_live_order_gate_status()
        live_financial_write_gate_status = get_kabucom_live_financial_write_gate_status(
            base_gate_status=live_order_gate_status,
            require_github_artifact_source=True,
        )
        print(
            "🔐 [LIVE-GATE] "
            f"allowed={live_order_gate_status.allowed} "
            f"reason={live_order_gate_status.reason} "
            f"runtime_hash={live_order_gate_status.runtime_config_hash}"
        )
        print(
            "🔐 [LIVE-WRITE-GATE] "
            f"allowed={live_financial_write_gate_status.allowed} "
            f"reason={live_financial_write_gate_status.reason} "
            f"test_fixture={live_financial_write_gate_status.test_fixture_captured_from_kabucom_test} "
            f"ci_artifact={live_financial_write_gate_status.ci_artifact_attested} "
            f"operator_ack={live_financial_write_gate_status.operator_acknowledged} "
            f"ack_source={live_financial_write_gate_status.operator_ack_source} "
            f"ack_reason={live_financial_write_gate_status.operator_ack_reason} "
            f"github_source={live_financial_write_gate_status.github_artifact_source_required}/"
            f"{live_financial_write_gate_status.github_artifact_source_verified} "
            f"github_reason={live_financial_write_gate_status.github_artifact_source_reason} "
            f"digest={live_financial_write_gate_status.live_write_attestation_digest_present}/"
            f"{live_financial_write_gate_status.live_write_attestation_digest_valid} "
            f"calendar={live_financial_write_gate_status.jpx_calendar_ready}/"
            f"{live_financial_write_gate_status.jpx_calendar_trading_day} "
            f"attestation={live_financial_write_gate_status.live_write_attestation_present}/"
            f"{live_financial_write_gate_status.live_write_attestation_valid}"
        )
        send_discord_notify(
            "🔐 [LIVE-GATE] "
            f"allowed={live_order_gate_status.allowed} "
            f"reason={live_order_gate_status.reason} | "
            "[LIVE-WRITE-GATE] "
            f"allowed={live_financial_write_gate_status.allowed} "
            f"reason={live_financial_write_gate_status.reason} "
            f"ci_artifact={live_financial_write_gate_status.ci_artifact_attested} "
            f"operator_ack={live_financial_write_gate_status.operator_acknowledged} "
            f"ack_source={live_financial_write_gate_status.operator_ack_source} "
            f"ack_reason={live_financial_write_gate_status.operator_ack_reason} "
            f"github_source={live_financial_write_gate_status.github_artifact_source_required}/"
            f"{live_financial_write_gate_status.github_artifact_source_verified} "
            f"github_reason={live_financial_write_gate_status.github_artifact_source_reason} "
            f"digest={live_financial_write_gate_status.live_write_attestation_digest_present}/"
            f"{live_financial_write_gate_status.live_write_attestation_digest_valid} "
            f"calendar={live_financial_write_gate_status.jpx_calendar_ready}/"
            f"{live_financial_write_gate_status.jpx_calendar_trading_day} "
            f"attestation={live_financial_write_gate_status.live_write_attestation_present}/"
            f"{live_financial_write_gate_status.live_write_attestation_valid}"
        )
        if not live_financial_write_gate_status.allowed:
            print("🛑 [LIVE-GATE] 新規エントリーはコード側で停止しています。監視と決済だけ継続します。")

    try:
        import psutil
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        print(f"[STAT] [System Health] Memory Usage: {mem_info.rss / 1024 / 1024:.1f} MB | CPU: {psutil.cpu_percent()}%")
    except: pass

    print(f"\n[START] ヘッジファンド仕様・アルゴリズムBOT 起動 (自律ループ型監視中)")

    # --- [V2-C1] ループ頻度の分離 ---
    last_scan_time = 0
    SCAN_INTERVAL_SEC = 900
    MONITOR_INTERVAL_SEC = 30
    
    # --- [Imperial Persistence] JQuants Cache Management ---
    JQUANTS_CACHE_FILE = str(DATA_CACHE_ROOT / "jp_broad" / "jp_mega_cache.pkl")
    jp_cache = {}
    jp_cache_df = None
    if os.path.exists(JQUANTS_CACHE_FILE):
        try:
            with open(JQUANTS_CACHE_FILE, 'rb') as f:
                jp_cache_df = pickle.load(f)
            
            # multi-index Columns -> Dict for fast lookup
            for col in jp_cache_df.columns:
                ticker = col[0]
                if ticker not in jp_cache: jp_cache[ticker] = {}
                jp_cache[ticker][col[1]] = jp_cache_df[col].iloc[-1]
            print(f"✅ Loaded JQuants Cache: {len(jp_cache)} tickers secured.")
        except Exception as e:
            print(f"⚠️ Error loading JQuants Cache: {e}")

    # --- [Hybrid Monitoring State] ---
    watchlist = load_watchlist()
    special_quote_watchlist = {} # { "code": item_dict }
    realtime_buffers = {}
    _set_active_runtime_state(realtime_buffers=realtime_buffers)
    canceled_orders = {}
    cooling_until = None # [V132] Over-trading prevention (Date based parity)
    breadth_val = 0.5    # [Parity] Market breadth (updated each scan, default neutral)
    
    # --- [Aegis Protocol State] ---
    current_month_str = datetime.datetime.now(JST).strftime('%Y-%m')
    account_data = safe_read_json(ACCOUNT_FILE, default={}) or {}
    month_start_equity = account_data.get('month_start_equity', 0)

    # 初回起動時または月替わり時に月初資産を記録
    account = merge_account_state(broker.get_account_balance(), account_data, is_sim=is_sim)
    if float(account.get("configured_risk_capital", 0.0) or 0.0) <= 0:
        account["configured_risk_capital"] = float(INITIAL_CASH)
    account.setdefault("realized_pnl_today", float(account.get("realized_pnl_today", 0.0) or 0.0))
    positions_snapshot_fresh = True
    try:
        initial_portfolio = broker.get_positions()
    except Exception:
        initial_portfolio = []
        positions_snapshot_fresh = False
    portfolio = list(initial_portfolio)
    initial_total = _resolve_account_equity(account, initial_portfolio, is_sim)
    _set_active_runtime_state(portfolio=portfolio, account=account)
    if month_start_equity <= 0 or current_month_str != account_data.get('current_month', ''):
        month_start_equity = initial_total
        account['month_start_equity'] = month_start_equity
        account['current_month'] = current_month_str
        atomic_write_json(ACCOUNT_FILE, account)
        print(f"🛡️ [Aegis] 新しい月の開始です。月初資産を記録しました: Y{month_start_equity:,.0f}")
    account = ensure_daytrade_week_state(account, initial_total, datetime.datetime.now(JST))

    initial_active_orders_info = None
    if not is_sim:
        try:
            initial_active_orders_info = broker.get_active_orders()
        except Exception:
            initial_active_orders_info = None

    order_journal_replay_summary = build_order_journal_replay_summary()
    startup_recovery_report = build_startup_recovery_report(
        portfolio=portfolio,
        active_orders_info=initial_active_orders_info,
        order_journal_summary=order_journal_replay_summary,
        wallet_snapshot_incomplete=bool(account.get("wallet_snapshot_incomplete")),
    )
    account["order_journal_unresolved_count"] = order_journal_replay_summary.unresolved_count
    account["order_journal_total_intents"] = len(order_journal_replay_summary.intents)
    account["order_journal_corrupt_count"] = order_journal_replay_summary.corrupt_lines
    account["order_journal_unresolved_keys"] = [
        intent.tracking_key for intent in order_journal_replay_summary.unresolved_intents[:25]
    ]
    account["startup_recovery_needs_manual_review"] = startup_recovery_report.needs_manual_review
    account["startup_recovery_blocking_reasons"] = list(startup_recovery_report.blocking_reasons[:25])
    if order_journal_replay_summary.has_unresolved:
        print(
            "⚠️ [Journal Replay] 未解決の注文 intent が "
            f"{order_journal_replay_summary.unresolved_count} 件あります。"
            "新規 entry は保留されます。"
        )
        for intent in order_journal_replay_summary.unresolved_intents[:5]:
            print(
                "⚠️ [Journal Replay] "
                f"{intent.tracking_key} / event={intent.latest_event} / reason={intent.unresolved_reason}"
            )
    else:
        print("✅ [Journal Replay] 未解決の注文 intent はありません。")
    if startup_recovery_report.needs_manual_review:
        print("⚠️ [Startup Recovery] manual review が必要です:")
        for reason in startup_recovery_report.blocking_reasons[:5]:
            print(f"⚠️ [Startup Recovery] - {reason}")

    startup_live_readiness_report = _build_live_readiness_report(
        broker=broker,
        portfolio=portfolio,
        startup_recovery_report=startup_recovery_report,
        order_journal_summary=order_journal_replay_summary,
        quote_fresh=None,
        checked_at=datetime.datetime.now(JST),
    )
    account["live_readiness_allowed"] = startup_live_readiness_report.allowed
    account["live_readiness_reason"] = startup_live_readiness_report.reason
    account["live_readiness_checked_at"] = startup_live_readiness_report.checked_at
    account["live_readiness_blocking_reasons"] = list(startup_live_readiness_report.blocking_reasons[:25])
    print(f"⚠️ [LIVE-READINESS] {startup_live_readiness_report.format_compact()}")
    for item in startup_live_readiness_report.blocking_items[:5]:
        evidence_text = ", ".join(item.evidence[:4]) if item.evidence else "none"
        print(f"⚠️ [LIVE-READINESS] - {item.name}: {item.reason} | evidence={evidence_text}")
    if TRADE_MODE == "KABUCOM_LIVE" and not startup_live_readiness_report.allowed:
        send_discord_notify(f"🔎 [LIVE-READINESS] {startup_live_readiness_report.format_compact()}")

    atomic_write_json(ACCOUNT_FILE, account)

    while True:
        if os.path.exists(STOP_FILE):
            print("[STOP] stop.txt を検出しました。安全に停止します。")
            try: os.remove(STOP_FILE)
            except: pass
            request_shutdown("stop.txt")

        if SHUTDOWN_REQUESTED:
            shutdown_result = perform_safe_shutdown(
                broker=broker,
                portfolio=portfolio,
                account=account,
                is_sim=is_sim,
                realtime_buffers=realtime_buffers,
                reason=SHUTDOWN_REASON,
            )
            portfolio = shutdown_result.updated_portfolio
            account = shutdown_result.updated_account
            if not is_sim and shutdown_result.success:
                terminate_kabu_station()
            elif not is_sim:
                print("⚠️ [STOP] 安全停止のreconciliationが完了しないため、kabuステーション終了は見送ります。")
            break

        loop_start_time = time.time()
        server_datetime = broker.get_server_time() if hasattr(broker, 'get_server_time') else datetime.datetime.now(JST)
        now_time = server_datetime.time()
        phase = get_market_phase(now_time)
        
        if not is_sim and not check_api_health():
            msg = "⚠️ 【警告】kabuステーションのAPI応答がありません。"
            print(f"\n{msg}")
            send_discord_notify(msg)
            ensure_kabu_station_running()
            
        print(f"\n[{datetime.datetime.now(JST).strftime('%H:%M:%S')}] [UP] 監視サイクル開始 (Phase: {phase.value})")
        if cooling_until and server_datetime < cooling_until:
            print(f"🛡️ [Cooling] Paused until {cooling_until.strftime('%Y-%m-%d %H:%M')}. Skipping entry scan.")
            should_scan_override = False
        else:
            should_scan_override = True

        phase_entry_blocked = False
        if not DEBUG_MODE:
            jpx_day_status = get_jpx_trading_day_status(
                server_datetime,
                require_source=TRADE_MODE == "KABUCOM_LIVE",
            )
            if not jpx_day_status.trading_day:
                non_trading_day_reason = jpx_day_status.source_reason
                perform_non_trading_day_shutdown(
                    broker=broker,
                    portfolio=portfolio,
                    account=account,
                    is_sim=is_sim,
                    realtime_buffers=realtime_buffers,
                    reason=non_trading_day_reason,
                )
                break
            half_day_session = bool(getattr(jpx_day_status, "half_day", False))
            phase = get_market_phase(now_time, half_day=half_day_session)

            if phase == MarketPhase.CLOSING_TIME:
                closing_label = "11:30（半日立会の大引け）" if half_day_session else "15:30（大引け）"
                print(f"\n🏁 {closing_label}を過ぎました。本日の運用を終了します。")
                send_discord_notify(f"🏁 【業務終了】{closing_label}を過ぎたため運用を終了しました。")
                shutdown_result = perform_safe_shutdown(
                    broker=broker,
                    portfolio=portfolio,
                    account=account,
                    is_sim=is_sim,
                    realtime_buffers=realtime_buffers,
                    reason="closing_time",
                )
                portfolio = shutdown_result.updated_portfolio
                account = shutdown_result.updated_account
                if not is_sim and shutdown_result.success:
                    terminate_kabu_station()
                elif not is_sim:
                    print("⚠️ [STOP] 大引けの安全停止が未解決のため、kabuステーション終了は見送ります。")
                break

            if phase in [MarketPhase.PRE_MARKET, MarketPhase.LUNCH]:
                phase_entry_blocked = True

        active_orders_info = None
        active_orders_block_entry = False
        if not is_sim:
            try:
                active_orders_info = broker.get_active_orders()
                if active_orders_info is None:
                    msg = "⚠️ 未約定注文の取得に失敗しました。新規エントリーを保留します。"
                    print(msg)
                    send_discord_notify(msg)
                    active_orders_block_entry = True
                else:
                    protected_stop_order_ids = _collect_protective_stop_order_ids(portfolio)
                    active_orders = active_orders_info.get("orders", [])
                    blocking_unknown_order_ids = [
                        order_id
                        for order_id in active_orders_info.get("unresolved_order_ids", [])
                        if order_id not in protected_stop_order_ids
                    ]
                    blocking_orders = []
                    has_stuck_order = False
                    for order in active_orders:
                        order_id = order.get('ID')
                        if order_id and order_id in protected_stop_order_ids:
                            continue
                        blocking_orders.append(order)
                        recv_time_str = order.get('RecvTime')
                        if order_id and recv_time_str:
                            try:
                                clean_time_str = recv_time_str[:19].replace("T", " ")
                                order_time = datetime.datetime.strptime(clean_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=JST)
                                duration_mins = (datetime.datetime.now(JST) - order_time).total_seconds() / 60
                                if duration_mins >= 5.0:
                                    cancel_count = canceled_orders.get(order_id, 0)
                                    if cancel_count >= 3:
                                        continue
                                    broker.cancel_order(order_id)
                                    canceled_orders[order_id] = cancel_count + 1
                                    has_stuck_order = True
                            except: pass
                    if blocking_unknown_order_ids:
                        msg = (
                            "⚠️ 注文状態が不明な注文があります。"
                            "reconciliationが必要なため新規エントリーを保留します。"
                        )
                        print(msg)
                        send_discord_notify(msg)
                        active_orders_block_entry = True
                    if has_stuck_order:
                        active_orders_block_entry = True
                    if blocking_orders:
                        print(f"[WARNING] 未約定の注文が {len(blocking_orders)} 件あります。待機します。")
                        active_orders_block_entry = True
            except Exception as exc:
                print(f"⚠️ 未約定注文の取得中に例外が発生しました: {exc}")
                active_orders_block_entry = True

        try:
            account = merge_account_state(
                broker.get_account_balance(),
                safe_read_json(ACCOUNT_FILE, default={}) or {},
                is_sim=is_sim,
            )
            portfolio = broker.get_positions()
        except Exception as e:
            print(f"[WARNING] 口座情報取得エラー: {e}")
            time.sleep(MONITOR_INTERVAL_SEC)
            continue

        current_order_journal_replay_summary = build_order_journal_replay_summary()
        loop_recovery_report = build_startup_recovery_report(
            portfolio=portfolio,
            active_orders_info=active_orders_info,
            order_journal_summary=current_order_journal_replay_summary,
            wallet_snapshot_incomplete=bool(account.get("wallet_snapshot_incomplete")),
        )
        account["order_journal_unresolved_count"] = current_order_journal_replay_summary.unresolved_count
        account["order_journal_total_intents"] = len(current_order_journal_replay_summary.intents)
        account["order_journal_corrupt_count"] = current_order_journal_replay_summary.corrupt_lines
        account["order_journal_unresolved_keys"] = [
            intent.tracking_key for intent in current_order_journal_replay_summary.unresolved_intents[:25]
        ]
        account["startup_recovery_needs_manual_review"] = loop_recovery_report.needs_manual_review
        account["startup_recovery_blocking_reasons"] = list(loop_recovery_report.blocking_reasons[:25])

        # --- [Step 3.2] 特注監視（特別気配・価格未定）銘柄の高頻度チェック ---
        force_scan = False
        if special_quote_watchlist and len(portfolio) < MAX_POSITIONS:
            print(f"📡 [HighFreq] 特別気配/価格未定の {len(special_quote_watchlist)} 銘柄を再チェックします...")
            sq_codes = list(special_quote_watchlist.keys())
            try:
                sq_boards = broker.get_board_data(sq_codes) if not is_sim else {}
                for code in sq_codes:
                    if code in sq_boards:
                        b_info = sq_boards[code]
                        c_p = b_info.get('price')
                        if c_p and c_p > 0:
                            print(f"✨ [HighFreq] {code} の価格が決定しました (@{c_p})。即時スキャンを実行します。")
                            if code not in watchlist: watchlist.append(code)
                            del special_quote_watchlist[code]
                            force_scan = True
            except: pass

        actions_taken = []
        trade_logs = [] 

        boards = {}
        registry_sync_ok = True
        try:
            watch_plan = build_daytrade_watch_plan(
                watchlist=watchlist,
                portfolio=portfolio,
            )
            current_targets = watch_plan["current_targets"]
            already_tracked = set(realtime_buffers.keys())
            registry_sync_ok, new_codes, removed_codes = sync_daytrade_registry(
                broker=broker,
                current_targets=current_targets,
                already_tracked=already_tracked,
                market_index_code="1321",
                is_sim=is_sim,
            )
            
            for code in new_codes:
                print(f"[NEW] 新規銘柄をバッファに追加: {code}")
                try:
                    ticker_with_t = str(code) + ".T" if not str(code).endswith(".T") else str(code)
                    prev_close = 0
                    if ticker_with_t in jp_cache:
                        prev_close = jp_cache[ticker_with_t].get('Close', 0)
                    
                    # V17.1 Buffer: No yfinance download. Init with cache stats.
                    realtime_buffers[code] = RealtimeBuffer(code, None, interval_mins=15)
                    if prev_close > 0:
                        realtime_buffers[code].set_previous_close(prev_close)
                except Exception as e:
                    print(f"⚠️ [Buffer Error] {code} 加盟失敗: {e}")
                    continue
            
            for code in removed_codes:
                realtime_buffers.pop(code, None)

            if not is_sim:
                boards = broker.get_board_data(list(current_targets))
                for code, b_info in boards.items():
                    price = b_info.get('price')
                    vol = b_info.get('volume', 0)
                    if code in realtime_buffers:
                        realtime_buffers[code].update(
                            price,
                            vol,
                            server_datetime,
                            open_price=b_info.get('open'),
                            high_price=b_info.get('high'),
                            low_price=b_info.get('low'),
                        )
        except Exception as e:
            registry_sync_ok = False
            print(f"[WARNING] バッファ同期エラー: {e}")
        if boards:
            record_intraday_snapshots(server_datetime, boards, realtime_buffers)

        quote_fresh_ok = True
        quote_freshness_evidence = None
        if not is_sim:
            quote_fresh_ok, quote_freshness_evidence = _describe_board_quote_snapshot_freshness(boards, server_datetime)

        live_readiness_report = _build_live_readiness_report(
            broker=broker,
            portfolio=portfolio,
            startup_recovery_report=loop_recovery_report,
            order_journal_summary=current_order_journal_replay_summary,
            quote_fresh=quote_fresh_ok if not is_sim else True,
            quote_freshness_evidence=quote_freshness_evidence,
            checked_at=server_datetime,
        )
        account["live_readiness_allowed"] = live_readiness_report.allowed
        account["live_readiness_reason"] = live_readiness_report.reason
        account["live_readiness_checked_at"] = live_readiness_report.checked_at
        account["live_readiness_blocking_reasons"] = list(live_readiness_report.blocking_reasons[:25])
        if not live_readiness_report.allowed:
            print(f"⚠️ [LIVE-READINESS] {live_readiness_report.format_compact()}")

        try:
            # [V131.1 Aegis Enhancement] Regime Filter & Trend Health
            regime, is_trend_snapped = detect_market_regime(data_df=jp_cache_df, buffer=realtime_buffers)
        except:
            regime, is_trend_snapped = "RANGE", False
            last_scan_time = loop_start_time

        # Calculate Monthly Drawdown for Aegis Protocol
        current_total = _resolve_account_equity(account, portfolio, is_sim)
        account = ensure_daytrade_week_state(account, current_total, server_datetime)
        month_drawdown = (current_total / month_start_equity) - 1.0 if month_start_equity > 0 else 0
        monthly_risk_blocked = is_daytrade_monthly_risk_blocked(month_start_equity, current_total)
        
        print(
            f"[STAT] レジーム: 【{regime}】 | TrendSnapped: {is_trend_snapped} "
            f"| MonthDD: {month_drawdown:+.2%}"
        )
        
        latest_close_map = {
            str(code).replace(".T", ""): float(info.get("Close", 0) or 0)
            for code, info in jp_cache.items()
        }
        portfolio = mark_daytrade_portfolio(
            portfolio,
            realtime_buffers=realtime_buffers,
            latest_close_map=latest_close_map,
            quote_time=server_datetime,
        )
        portfolio, signal_close_actions, account = close_daytrade_positions_by_signal(
            portfolio=portfolio,
            account=account,
            broker=broker,
            is_sim=is_sim,
            realtime_buffers=realtime_buffers,
        )
        if signal_close_actions:
            actions_taken.extend(signal_close_actions)

        # [V17.0 Final Persistence]
        # [V17.0 Imperial Sync] Finalizing position and equity state for the current loop.
        broker.save_account(account)
        broker.save_portfolio(portfolio)
        _set_active_runtime_state(portfolio=portfolio, account=account, realtime_buffers=realtime_buffers)

        should_scan = True
        if monthly_risk_blocked and not portfolio: should_scan = False  # Block fresh entries, but still allow liquidation.
        elif not should_scan_override: should_scan = False
        elif phase_entry_blocked: should_scan = False
        elif active_orders_block_entry: should_scan = False
        elif not is_sim and account.get("wallet_snapshot_incomplete"): should_scan = False
        elif not is_sim and any(str(position.get("ownership", "")).upper() != "MANAGED_BY_BOT" for position in portfolio): should_scan = False
        elif not is_sim and _portfolio_has_unresolved_execution_state(portfolio): should_scan = False
        elif not is_sim and loop_recovery_report.needs_manual_review: should_scan = False
        elif TRADE_MODE == "KABUCOM_LIVE" and not live_readiness_report.allowed: should_scan = False
        elif (
            live_financial_write_gate_status is not None
            and not live_financial_write_gate_status.allowed
        ): should_scan = False
        elif now_time < datetime.time(9, 30) and not DEBUG_MODE: should_scan = False
        elif now_time >= ENTRY_SCAN_CUTOFF_TIME and not DEBUG_MODE: should_scan = False

        entry_authorization_context = EntryAuthorizationContext(
            production_endpoint=TRADE_MODE == "KABUCOM_LIVE",
            approved_manifest_valid=(
                bool(live_financial_write_gate_status.allowed)
                if live_financial_write_gate_status is not None
                else True
            ),
            reconciliation_clean=not loop_recovery_report.needs_manual_review,
            unresolved_order_count=loop_recovery_report.active_orders_unknown_count,
            ambiguous_position_count=loop_recovery_report.ambiguous_position_count,
            wallet_snapshot_fresh=is_sim or not loop_recovery_report.wallet_snapshot_incomplete,
            positions_snapshot_fresh=is_sim or positions_snapshot_fresh,
            orders_snapshot_fresh=is_sim or active_orders_info is not None,
            quote_fresh=is_sim or quote_fresh_ok,
            registry_ready=is_sim or registry_sync_ok,
            critical_state_valid=not loop_recovery_report.needs_manual_review,
            session_allows_entry=(
                should_scan_override
                and not phase_entry_blocked
                and not monthly_risk_blocked
                and now_time >= datetime.time(9, 30)
                and now_time < ENTRY_SCAN_CUTOFF_TIME
            ),
            clock_healthy=server_datetime is not None,
            shutdown_requested=SHUTDOWN_REQUESTED,
            protective_stop_pending_count=loop_recovery_report.protective_stop_pending_count,
            protective_stop_orphan_count=loop_recovery_report.protective_stop_orphan_count,
            live_readiness_allowed=live_readiness_report.allowed,
            live_readiness_reason=live_readiness_report.reason,
        )
        entry_authorization = evaluate_entry_authorization(entry_authorization_context)
        if not entry_authorization.allowed:
            print(f"🛑 [ENTRY-AUTH] 新規エントリーを保留しました: {entry_authorization.reason}")
            should_scan = False
        
        if should_scan and not force_scan:
             if time.time() - last_scan_time < SCAN_INTERVAL_SEC:
                  should_scan = False

        if now_time >= FORCE_FLATTEN_TIME and portfolio:
            portfolio, close_actions, account = close_daytrade_positions(
                portfolio=portfolio,
                account=account,
                broker=broker,
                is_sim=is_sim,
                realtime_buffers=realtime_buffers,
            )
            actions_taken.extend(close_actions)
            watchlist = []
            save_watchlist(watchlist)
            broker.save_account(account)
            broker.save_portfolio(portfolio)

        if should_scan:
            last_scan_time = time.time()
            print("\n=> 🔍 デイトレード定期スキャン処理を開始します...")
            should_continue_scan = True
            dynamic_lev = 0.0
            base_dynamic_lev = 0.0
            top_candidates = []
            weekly_profit_guard_active = False
            try:
                if os.path.exists(JQUANTS_CACHE_FILE):
                    with open(JQUANTS_CACHE_FILE, 'rb') as f:
                        data_df = pickle.load(f)

                    new_cols = []
                    for col in data_df.columns:
                        ticker, field = col[0], col[1]
                        if isinstance(field, tuple):
                            field = field[0]
                        new_cols.append((ticker, field))
                    data_df.columns = pd.MultiIndex.from_tuples(new_cols)

                    df_symbols = pd.read_csv(DATA_FILE)
                    if '市場・商品区分' in df_symbols.columns:
                        df_symbols = df_symbols[df_symbols['市場・商品区分'].isin(TARGET_MARKETS)]

                    invalid_tickers = load_invalid_tickers()
                    if invalid_tickers:
                        df_symbols = df_symbols[~df_symbols['コード'].astype(str).isin(invalid_tickers)]

                    insider_codes = load_insider_exclusion_codes()
                    if insider_codes:
                        df_symbols = df_symbols[~df_symbols['コード'].astype(str).isin(insider_codes)]

                    held_codes = [str(p['code']) for p in portfolio]
                    targets = [str(t) for t in df_symbols['コード'].tolist() if str(t) not in held_codes]
                    snapshot = compute_daytrade_snapshot(
                        data_df=data_df,
                        symbols_df=df_symbols,
                        targets=targets,
                        regime=regime,
                    )
                    breadth_val = snapshot["breadth"] if snapshot["breadth"] > 0 else breadth_val
                    base_dynamic_lev = calculate_dynamic_leverage(breadth_val, config_leverage=LEVERAGE_RATE)
                    dynamic_lev = resolve_daytrade_weekly_leverage(
                        base_leverage=base_dynamic_lev,
                        week_start_equity=account.get("daytrade_week_start_equity", current_total),
                        current_equity=current_total,
                        current_time=server_datetime,
                    )
                    dynamic_lev *= resolve_daytrade_breadth_exposure_scale(breadth_val)
                    weekly_profit_guard_active = is_daytrade_weekly_profit_guard_active(
                        week_start_equity=account.get("daytrade_week_start_equity", current_total),
                        current_equity=current_total,
                        current_time=server_datetime,
                    )
                    latest_close_snapshot = snapshot["latest_close_map"]
                    portfolio = mark_daytrade_portfolio(
                        portfolio,
                        realtime_buffers=realtime_buffers,
                        latest_close_map=latest_close_snapshot,
                        quote_time=server_datetime,
                    )
                    top_candidates = snapshot["top_candidates"]
                    print(f"📊 [DayTrade] Market Breadth (Prime): {breadth_val:.1%}")
                    print(f"✅ Shared daytrade scan found {len(top_candidates)} candidates.")
                    if weekly_profit_guard_active:
                        top_candidates = []
                        print("🛡️ [DayTrade] Weekly profit guard active. Skipping new entries for late-week protection.")
                else:
                    print("❌ JQuants Cache not found. Skipping scan.")
                    should_continue_scan = False
            except Exception as e:
                print(f"[WARNING] JQuants Cache 読込エラー: {e}")
                should_continue_scan = False

            inverse_only = is_inverse_only_candidate_set(top_candidates)
            selected_base_lev = resolve_daytrade_selected_leverage(
                base_leverage=base_dynamic_lev,
                selected_candidates=top_candidates,
                breadth_val=breadth_val,
                market_ratio=snapshot.get("market_ratio"),
                trade_date=server_datetime,
            )
            selected_dynamic_lev = resolve_daytrade_weekly_leverage(
                base_leverage=selected_base_lev,
                week_start_equity=account.get("daytrade_week_start_equity", current_total),
                current_equity=current_total,
                current_time=server_datetime,
            )
            selected_dynamic_lev *= resolve_daytrade_breadth_exposure_scale(breadth_val)
            if weekly_profit_guard_active:
                save_watchlist([])
            elif should_continue_scan and (selected_dynamic_lev > 0 or inverse_only):
                watchlist = [str(item["code"]) for item in top_candidates[:max(5, MAX_POSITIONS * 4)]]
                save_watchlist(watchlist)

                selected_candidates = []
                max_to_buy = MAX_POSITIONS - len(portfolio)
                max_to_review = max(5, max_to_buy * 4)
                entry_flow_halted = False
                for item in top_candidates:
                    if entry_flow_halted:
                        break
                    if len(selected_candidates) >= max_to_review:
                        break

                    if not is_sim and hasattr(broker, 'get_board_data'):
                        try:
                            board = broker.get_board_data([item['code']])
                            b_info = board.get(str(item['code']).replace(".T", ""))
                            if b_info:
                                c_price = b_info.get('price')
                                p_close = b_info.get('prev_close', item['price'])
                                if not c_price or c_price == 0:
                                    special_quote_watchlist[str(item['code'])] = item
                                    continue
                                gap_pct = (c_price - p_close) / p_close if p_close > 0 else 0
                                if gap_pct < -0.02 or abs(gap_pct) > BULL_GAP_LIMIT:
                                    continue
                                item['price'] = c_price
                        except Exception as e:
                            print(f"[WARNING] 板情報チェック中のエラー: {e}")

                    news = get_recent_news(item['code'], item['name'])
                    if news and news != "ニュースなし":
                        is_safe, reason = ai_qualitative_filter(item['code'], item['name'], news)
                        if not is_safe:
                            print(f"🚫 [AI Filter] {item['code']} skipped: {reason}")
                            continue

                    selected_candidates.append(item)

                current_exposure = _portfolio_market_value(portfolio)
                day_equity = _resolve_account_equity(account, portfolio, is_sim)
                day_buying_power = resolve_daytrade_buying_power(
                    current_equity=day_equity,
                    account_cash=float(account.get("cash", 0.0)) if is_sim else 0.0,
                    dynamic_leverage=selected_dynamic_lev,
                    current_exposure=current_exposure,
                )
                if not is_sim:
                    margin_buying_power = _resolve_live_buying_power(account, "margin_buying_power")
                    if margin_buying_power > 0:
                        day_buying_power = min(day_buying_power, margin_buying_power)
                inverse_day_buying_power = 0.0
                inverse_buying_power_leverage = 1.0
                if inverse_only:
                    inverse_buying_power_leverage = resolve_daytrade_selected_inverse_buying_power_leverage(
                        top_candidates,
                        breadth_val,
                    )
                    inverse_day_buying_power = resolve_daytrade_inverse_buying_power(
                        current_equity=day_equity,
                        account_cash=float(account.get("cash", 0.0)) if is_sim else 0.0,
                        current_exposure=current_exposure,
                        leverage=inverse_buying_power_leverage,
                    )
                    if not is_sim:
                        margin_buying_power = _resolve_live_buying_power(account, "margin_buying_power")
                        if margin_buying_power > 0:
                            inverse_day_buying_power = min(inverse_day_buying_power, margin_buying_power)
                opened_count = 0
                for item in selected_candidates:
                    if opened_count >= max_to_buy:
                        break

                    buy_price = normalize_tick_size(float(item['price']), is_buy=True)
                    stop_mult = float(item.get("stop_mult", resolve_daytrade_intraday_stop_mult(STOP_LOSS_ATR)))
                    stop_price = max(0.01, buy_price - (float(item.get('atr', 0.0)) * stop_mult))
                    candidate_buying_power = day_buying_power
                    candidate_dynamic_lev = selected_dynamic_lev
                    if is_daytrade_inverse_setup_type(item.get("setup_type")):
                        candidate_buying_power = inverse_day_buying_power
                        candidate_dynamic_lev = inverse_buying_power_leverage
                    shares = calculate_lot_size(
                        current_equity=day_equity,
                        atr=float(item.get('atr', 0.0)),
                        sl_mult=5.0,
                        price=buy_price,
                        dynamic_leverage=candidate_dynamic_lev,
                        max_positions=MAX_POSITIONS,
                        buying_power=candidate_buying_power,
                    )
                    shares = cap_daytrade_position_size(
                        raw_shares=shares,
                        current_equity=day_equity,
                        buying_power=candidate_buying_power,
                        entry_price=buy_price,
                        stop_price=stop_price,
                        notional_pct=item.get("notional_pct"),
                        equity_notional_pct=item.get("equity_notional_pct"),
                    )
                    if shares < 100:
                        continue

                    if is_sim:
                        exec_p = buy_price * (1.0 + SLIPPAGE_RATE)
                        account['cash'] -= exec_p * shares
                        if is_daytrade_inverse_setup_type(item.get("setup_type")):
                            inverse_day_buying_power = max(0.0, inverse_day_buying_power - (exec_p * shares))
                        else:
                            day_buying_power = max(0.0, day_buying_power - (exec_p * shares))
                            portfolio.append(
                                build_daytrade_position_record(
                                    item=item,
                                    executed_price=exec_p,
                                    shares=shares,
                                    buy_time=datetime.datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S'),
                                    execution_id=None,
                                    execution_ids=(),
                                )
                            )
                        actions_taken.append(f"BUY {item['code']} - Daytrade entry (@{exec_p:,.1f})")
                        opened_count += 1
                    else:
                        details = broker.execute_chase_order(
                            item['code'],
                            shares,
                            action=StockOrderAction.MARGIN_NEW_LONG,
                            atr=float(item.get('atr', 0.0)),
                        )
                        actual_qty = int(details.get("filled_qty", details.get("Qty", 0)) or 0) if isinstance(details, dict) else 0
                        unresolved_entry = bool(isinstance(details, dict) and details.get("unresolved"))
                        if actual_qty > 0:
                            exec_p = float(details.get("average_price", details.get("Price", 0)) or buy_price)
                            execution_ids = details.get("execution_ids") or ()
                            execution_id = details.get("execution_id")
                            if execution_id is None and execution_ids:
                                execution_id = execution_ids[0]
                            position_record = build_daytrade_position_record(
                                item=item,
                                executed_price=exec_p,
                                shares=actual_qty,
                                buy_time=datetime.datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S'),
                                execution_id=execution_id,
                                execution_ids=execution_ids,
                            )
                            if isinstance(details, dict) and details.get("unresolved"):
                                entry_execution_status = details.get("entry_execution_status") or details.get("execution_status") or details.get("unresolved_reason") or "partial_unresolved"
                                position_record["entry_order_unresolved"] = True
                                position_record["entry_order_unresolved_reason"] = details.get("unresolved_reason") or details.get("process_state") or "unknown"
                                position_record["entry_order_submission_status"] = details.get("submission_status")
                                position_record["entry_order_filled_qty"] = actual_qty
                                position_record["entry_order_remaining_qty"] = int(details.get("remaining_qty", max(0, shares - actual_qty)) or max(0, shares - actual_qty))
                                position_record["entry_order_execution_status"] = entry_execution_status
                                position_record["entry_order_unresolved_state"] = entry_execution_status
                            else:
                                position_record["entry_order_execution_status"] = details.get("entry_execution_status") or details.get("execution_status") or "completed"
                            portfolio.append(position_record)
                            broker.save_portfolio(portfolio)
                            broker.save_account(account)
                            stop_order_id = _arm_daytrade_protective_stop(
                                broker=broker,
                                position=position_record,
                                trigger_price=position_record["entry_stop_price"],
                                expected_shares=actual_qty,
                            )
                            broker.save_portfolio(portfolio)
                            if position_record.get("entry_order_unresolved"):
                                actions_taken.append(
                                    f"BUY {item['code']} - Daytrade entry unresolved (@{exec_p:,.1f})"
                                )
                                entry_flow_halted = True
                            else:
                                actions_taken.append(f"BUY {item['code']} - Daytrade entry (@{exec_p:,.1f})")
                            if stop_order_id:
                                actions_taken.append(f"STOP {item['code']} - protective stop armed (ID: {stop_order_id})")
                            if not entry_flow_halted:
                                opened_count += 1
                            else:
                                break
                        elif unresolved_entry:
                            actions_taken.append(f"BUY {item['code']} - Daytrade entry unresolved (no fill)")
                            entry_flow_halted = True
                            break

                    if is_sim:
                        broker.save_portfolio(portfolio)
                        broker.save_account(account)

        summary_equity = _resolve_account_equity(account, portfolio, is_sim)
        summary_record = {
            "time": datetime.datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S'),
            "actions": actions_taken,
            "portfolio": portfolio,
            "stock_value_yen": _portfolio_market_value(portfolio),
            "cash_yen": float(account.get("cash", 0.0)) if is_sim else float(account.get("cash", 0.0) or 0.0),
            "equity_yen": summary_equity,
            "total_assets_yen": summary_equity,
            "margin_buying_power_yen": _resolve_live_buying_power(account, "margin_buying_power") if not is_sim else None,
            "stock_buying_power_yen": _resolve_live_buying_power(account, "stock_buying_power") if not is_sim else None,
            "realized_pnl_today": float(account.get("realized_pnl_today", 0.0) or 0.0),
            "regime": regime
        }
        if hasattr(broker, 'log_execution_summary'):
            broker.log_execution_summary(summary_record)

        elapsed = time.time() - loop_start_time
        sleep_time = max(MONITOR_INTERVAL_SEC - elapsed, 5.0)
        print(f"\nNext loop in {sleep_time:.1f}s...")
        time.sleep(sleep_time)
        continue

if __name__ == "__main__":
    main()
