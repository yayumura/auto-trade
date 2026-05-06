import os
import sys
import datetime
import numpy as np
import pandas as pd
import time
import pickle
import signal
import jpholiday
from enum import Enum
from core.log_setup import setup_logging, send_discord_notify
from core.preflight import pre_flight_check

class MarketPhase(Enum):
    PRE_MARKET = "寄り前"
    MORNING = "前場"
    LUNCH = "昼休み"
    AFTERNOON = "後場"
    CLOSING_TIME = "大引け後"

def get_market_phase(now_time) -> MarketPhase:
    """現在時刻から市場のフェーズを判定する"""
    t900 = datetime.time(9, 0)
    t1130 = datetime.time(11, 30)
    t1230 = datetime.time(12, 30)
    t1530 = datetime.time(15, 30)
    
    if now_time < t900:
        return MarketPhase.PRE_MARKET
    elif t900 <= now_time < t1130:
        return MarketPhase.MORNING
    elif t1130 <= now_time < t1230:
        return MarketPhase.LUNCH
    elif t1230 <= now_time < t1530:
        return MarketPhase.AFTERNOON
    else:
        return MarketPhase.CLOSING_TIME

# --- ファイルパス・設定・APIキー設定 (core.configより一括取得) ---
from core.config import (
    PROJECT_ROOT, DATA_ROOT,
    DATA_FILE, PORTFOLIO_FILE, HISTORY_FILE, ACCOUNT_FILE,
    EXECUTION_LOG_FILE, TARGET_MARKETS,
    DEBUG_MODE, TRADE_MODE,
    LEVERAGE_RATE, JST, BULL_GAP_LIMIT,
    SMA_LONG_PERIOD, MAX_POSITIONS,
    SLIPPAGE_RATE, STOP_LOSS_ATR, load_insider_exclusion_codes,
    INTRADAY_SNAPSHOT_FILE,
)
from core.file_io import atomic_write_json, append_csv_rows, rotate_csv_if_large, safe_read_json

# --- インスタンスロック機構 ---
LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".bot_sim.lock")

def acquire_lock():
    """原子的なロックファイル取得。open('x')はファイルが既存の場合FileExistsErrorを発生させる。"""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                old_pid = int(f.read().strip())
            import psutil
            if psutil.pid_exists(old_pid):
                print(f"[WARNING] エラー: 他のインスタンス(PID: {old_pid})が既に実行中です。")
                return False
            print(f"[WARNING] 古いロックファイルを検出(PID: {old_pid}, 既に終了)。削除して続行します。")
            os.remove(LOCK_FILE)
        except (ValueError, ImportError, OSError) as e:
            print(f"[WARNING] ロックファイルの解析に失敗しました({e})。古いロックを削除して続行します。")
            try:
                os.remove(LOCK_FILE)
            except OSError:
                pass
    try:
        with open(LOCK_FILE, 'x') as f:
            f.write(str(os.getpid()))
        return True
    except FileExistsError:
        print("[WARNING] エラー: ロックファイルの競合が発生しました。別のインスタンスが起動した可能性があります。")
        return False

def release_lock():
    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
        except OSError as e:
            print(f"[WARNING] ロックファイルの削除に失敗しました: {e}")

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
)
from core.watchlist import load_watchlist, save_watchlist
from core.ai_filter import ai_qualitative_filter, get_recent_news


def build_daytrade_watch_plan(watchlist, portfolio, market_index_code="1321"):
    watch_codes = [str(code) for code in watchlist]
    portfolio_codes = [str(position["code"]) for position in portfolio]
    registration_targets = list(dict.fromkeys((watch_codes + portfolio_codes + [market_index_code])[:50]))
    return {
        "watchlist": watch_codes,
        "portfolio_codes": portfolio_codes,
        "registration_targets": registration_targets,
        "current_targets": set(registration_targets),
    }


def is_inverse_only_candidate_set(candidates):
    return bool(candidates) and all(
        is_daytrade_inverse_setup_type(item.get("setup_type")) for item in candidates
    )


def merge_account_state(account, persisted_state):
    merged = dict(persisted_state or {})
    merged.update(account or {})
    return merged


def ensure_daytrade_week_state(account, total_equity, server_datetime):
    week_key = get_daytrade_week_key(server_datetime)
    if account.get("daytrade_current_week") != week_key or float(account.get("daytrade_week_start_equity", 0) or 0) <= 0:
        account["daytrade_current_week"] = week_key
        account["daytrade_week_start_equity"] = float(total_equity)
    return account


def mark_daytrade_portfolio(portfolio, realtime_buffers=None, latest_close_map=None):
    latest_close_map = latest_close_map or {}
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
        updated.append(pos)
    return updated


def build_daytrade_position_record(item, executed_price, shares, buy_time):
    return {
        "code": str(item["code"]),
        "name": item.get("name", str(item["code"])),
        "buy_time": buy_time,
        "buy_price": round(float(executed_price), 1),
        "highest_price": round(float(executed_price), 1),
        "current_price": round(float(executed_price), 1),
        "shares": int(shares),
        "buy_atr": float(item.get("atr", 0.0)),
    }


def compute_daytrade_snapshot(data_df, symbols_df, targets, regime):
    bundle = calculate_all_technicals_v12(data_df)
    close = bundle["Close"].iloc[-1]
    sma_long = bundle[f"SMA{SMA_LONG_PERIOD}"].iloc[-1]
    prime_ref = set(get_prime_tickers())
    elite_cols = [ticker for ticker in close.index if ticker in prime_ref and ticker in sma_long.index]
    breadth_val = 0.0
    if elite_cols:
        breadth_val = float(np.mean([
            float(close[ticker]) > float(sma_long[ticker])
            for ticker in elite_cols
            if pd.notna(close[ticker]) and pd.notna(sma_long[ticker])
        ]))

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
        "latest_close_map": latest_close_map,
    }


def close_daytrade_positions(portfolio, account, broker, is_sim, realtime_buffers):
    original_positions = [dict(position) for position in portfolio]
    updated_portfolio, sell_actions = manage_positions_live(
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
    return updated_portfolio, sell_actions, account


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
            "bid": board.get("bid"),
            "ask": board.get("ask"),
            "volume": board.get("volume"),
            "session_open": None if buffer is None else buffer.get_session_open(),
            "session_high": None if buffer is None else buffer.get_session_high(),
            "session_low": None if buffer is None else buffer.get_session_low(),
        })
    append_csv_rows(INTRADAY_SNAPSHOT_FILE, rows)
    rotate_csv_if_large(INTRADAY_SNAPSHOT_FILE, max_size_mb=20)

# --- シグナルハンドラ ---
def handle_shutdown(signum, frame):
    print(f"\n[STOP] シグナル({signum})を受信しました。安全にシャットダウンを開始します...")
    try:
        send_discord_notify("[STOP] 【システム通知】運営者による停止操作（Ctrl+C等）を検知しました。ボットを安全に終了します。")
    except: pass
    release_lock()
    os._exit(0)

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
    
    from core.sim_broker import SimulationBroker
    from core.kabucom_broker import KabucomBroker
    
    try:
        if TRADE_MODE == "KABUCOM_LIVE":
            print("[LIVE] 【本番モード】auカブコム証券 本番API (Port 18080) に接続します")
            broker = KabucomBroker(is_production=True)
            is_sim = False
        elif TRADE_MODE == "KABUCOM_TEST":
            print("[TEST] 【テストモード】auカブコム証券 検証用API (Port 18081) に接続します")
            broker = KabucomBroker(is_production=False)
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
    JQUANTS_CACHE_FILE = os.path.join("data_cache", "jp_broad", "jp_mega_cache.pkl")
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
    canceled_orders = {}
    cooling_until = None # [V132] Over-trading prevention (Date based parity)
    breadth_val = 0.5    # [Parity] Market breadth (updated each scan, default neutral)
    
    # --- [Aegis Protocol State] ---
    current_month_str = datetime.datetime.now(JST).strftime('%Y-%m')
    account_data = safe_read_json(ACCOUNT_FILE, default={}) or {}
    month_start_equity = account_data.get('month_start_equity', 0)
    
    # 初回起動時または月替わり時に月初資産を記録
    account = merge_account_state(broker.get_account_balance(), account_data)
    initial_total = account['cash'] + sum([p.get('current_price', p['buy_price']) * p['shares'] for p in broker.get_positions()])
    if month_start_equity <= 0 or current_month_str != account_data.get('current_month', ''):
        month_start_equity = initial_total
        account['month_start_equity'] = month_start_equity
        account['current_month'] = current_month_str
        atomic_write_json(ACCOUNT_FILE, account)
        print(f"🛡️ [Aegis] 新しい月の開始です。月初資産を記録しました: Y{month_start_equity:,.0f}")
    account = ensure_daytrade_week_state(account, initial_total, datetime.datetime.now(JST))
    atomic_write_json(ACCOUNT_FILE, account)

    while True:
        if os.path.exists("stop.txt"):
            print("[STOP] stop.txt を検出しました。安全に停止します。")
            try: os.remove("stop.txt")
            except: pass
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

        if phase == MarketPhase.CLOSING_TIME and not DEBUG_MODE:
            print("\n🏁 15:30（大引け）を過ぎました。本日の運用を終了します。")
            send_discord_notify("🏁 【業務終了】大引けを過ぎたため運用を終了しました。")
            if not is_sim:
                broker.unregister_all()
                active_orders_final = broker.get_active_orders()
                for o in active_orders_final:
                    oid = o.get('ID')
                    if oid: broker.cancel_order(oid)
            terminate_kabu_station()
            break

        if not DEBUG_MODE:
            is_weekend = server_datetime.weekday() >= 5
            is_holiday = jpholiday.is_holiday(server_datetime.date())
            if is_weekend or is_holiday:
                terminate_kabu_station()
                break
            
            if phase in [MarketPhase.PRE_MARKET, MarketPhase.LUNCH]:
                time.sleep(MONITOR_INTERVAL_SEC)
                continue

        if not is_sim:
            try:
                active_orders = broker.get_active_orders()
                if active_orders:
                    has_stuck_order = False
                    for order in active_orders:
                        order_id = order.get('ID')
                        recv_time_str = order.get('RecvTime')
                        if order_id and recv_time_str:
                            try:
                                clean_time_str = recv_time_str[:19].replace("T", " ")
                                order_time = datetime.datetime.strptime(clean_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=JST)
                                duration_mins = (datetime.datetime.now(JST) - order_time).total_seconds() / 60
                                if duration_mins >= 5.0:
                                    cancel_count = canceled_orders.get(order_id, 0)
                                    if cancel_count >= 3: continue
                                    broker.cancel_order(order_id)
                                    canceled_orders[order_id] = cancel_count + 1
                                    has_stuck_order = True
                            except: pass
                    if has_stuck_order:
                        time.sleep(10)
                        continue
                    print(f"[WARNING] 未約定の注文が {len(active_orders)} 件あります。待機します。")
                    time.sleep(MONITOR_INTERVAL_SEC)
                    continue
            except: pass

        try:
            account = merge_account_state(
                broker.get_account_balance(),
                safe_read_json(ACCOUNT_FILE, default={}) or {},
            )
            portfolio = broker.get_positions()
        except Exception as e:
            print(f"[WARNING] 口座情報取得エラー: {e}")
            time.sleep(MONITOR_INTERVAL_SEC)
            continue

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
        try:
            watch_plan = build_daytrade_watch_plan(
                watchlist=watchlist,
                portfolio=portfolio,
            )
            current_targets = watch_plan["current_targets"]
            already_tracked = set(realtime_buffers.keys())
            new_codes = current_targets - already_tracked
            removed_codes = (already_tracked - current_targets) - {'1321'}
            
            if not is_sim:
                if new_codes: broker.register_symbols(list(new_codes))
                if removed_codes: broker.unregister_symbols(list(removed_codes))
            
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
                        realtime_buffers[code].update(prev_close, 0, server_datetime)
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
            print(f"[WARNING] バッファ同期エラー: {e}")
        if boards:
            record_intraday_snapshots(server_datetime, boards, realtime_buffers)

        try:
            # [V131.1 Aegis Enhancement] Regime Filter & Trend Health
            regime, is_trend_snapped = detect_market_regime(data_df=jp_cache_df, buffer=realtime_buffers)
        except:
            regime, is_trend_snapped = "RANGE", False
            last_scan_time = loop_start_time

        # Calculate Monthly Drawdown for Aegis Protocol
        current_total = account['cash'] + sum([float(p.get('current_price', p['buy_price'])) * int(p['shares']) for p in portfolio])
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
        )

        # [V17.0 Final Persistence]
        # [V17.0 Imperial Sync] Finalizing position and equity state for the current loop.
        broker.save_account(account)
        broker.save_portfolio(portfolio)

        should_scan = True
        if monthly_risk_blocked and not portfolio: should_scan = False  # Block fresh entries, but still allow liquidation.
        elif not should_scan_override: should_scan = False
        elif now_time < datetime.time(9, 30) and not DEBUG_MODE: should_scan = False
        elif now_time >= datetime.time(14, 0) and not DEBUG_MODE: should_scan = False
        
        if should_scan and not force_scan:
             if time.time() - last_scan_time < SCAN_INTERVAL_SEC:
                  should_scan = False

        if phase in [MarketPhase.AFTERNOON, MarketPhase.CLOSING_TIME] and portfolio:
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
                    dynamic_lev = calculate_dynamic_leverage(breadth_val, config_leverage=LEVERAGE_RATE)
                    dynamic_lev = resolve_daytrade_weekly_leverage(
                        base_leverage=dynamic_lev,
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
            if weekly_profit_guard_active:
                save_watchlist([])
            elif should_continue_scan and (dynamic_lev > 0 or inverse_only):
                watchlist = [str(item["code"]) for item in top_candidates[:max(5, MAX_POSITIONS * 4)]]
                save_watchlist(watchlist)

                selected_candidates = []
                max_to_buy = MAX_POSITIONS - len(portfolio)
                max_to_review = max(5, max_to_buy * 4)
                for item in top_candidates:
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

                current_exposure = sum([float(p.get('current_price', p['buy_price'])) * int(p['shares']) for p in portfolio])
                day_equity = account['cash'] + current_exposure
                day_buying_power = resolve_daytrade_buying_power(
                    current_equity=day_equity,
                    account_cash=account['cash'],
                    dynamic_leverage=dynamic_lev,
                    current_exposure=current_exposure,
                )
                inverse_day_buying_power = 0.0
                if inverse_only:
                    inverse_day_buying_power = resolve_daytrade_inverse_buying_power(
                        current_equity=day_equity,
                        account_cash=account['cash'],
                        current_exposure=current_exposure,
                    )
                opened_count = 0
                for item in selected_candidates:
                    if opened_count >= max_to_buy:
                        break

                    buy_price = normalize_tick_size(float(item['price']), is_buy=True)
                    stop_mult = float(item.get("stop_mult", resolve_daytrade_intraday_stop_mult(STOP_LOSS_ATR)))
                    stop_price = max(0.01, buy_price - (float(item.get('atr', 0.0)) * stop_mult))
                    candidate_buying_power = day_buying_power
                    candidate_dynamic_lev = dynamic_lev
                    if is_daytrade_inverse_setup_type(item.get("setup_type")):
                        candidate_buying_power = inverse_day_buying_power
                        candidate_dynamic_lev = 1.0
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
                            )
                        )
                        actions_taken.append(f"BUY {item['code']} - Daytrade entry (@{exec_p:,.1f})")
                        opened_count += 1
                    else:
                        details = broker.execute_chase_order(item['code'], shares, side="2", atr=float(item.get('atr', 0.0)))
                        if details and details.get('State') in [6, 7]:
                            actual_qty = int(details.get('Qty', 0))
                            exec_p = float(details.get('Price', 0)) or buy_price
                            portfolio.append(
                                build_daytrade_position_record(
                                    item=item,
                                    executed_price=exec_p,
                                    shares=actual_qty,
                                    buy_time=datetime.datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S'),
                                )
                            )
                            actions_taken.append(f"BUY {item['code']} - Daytrade entry (@{exec_p:,.1f})")
                            opened_count += 1

                    broker.save_portfolio(portfolio)
                    broker.save_account(account)

        summary_record = {
            "time": datetime.datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S'),
            "actions": actions_taken,
            "portfolio": portfolio,
            "stock_value_yen": sum([float(p.get('current_price', p['buy_price'])) * int(p['shares']) for p in portfolio]),
            "cash_yen": account['cash'],
            "total_assets_yen": account['cash'] + sum([float(p.get('current_price', p['buy_price'])) * int(p['shares']) for p in portfolio]),
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
