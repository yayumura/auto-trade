import os
import sys
import datetime
import pandas as pd
import time
import pickle
import signal
import jpholiday
from enum import Enum
from core.log_setup import setup_logging, send_discord_notify
from core.preflight import pre_flight_check
from core.kabu_launcher import ensure_kabu_station_running, terminate_kabu_station, check_api_health
from core.utils import calculate_effective_age

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
    LEVERAGE_RATE, JST, COOLING_DAYS, BULL_GAP_LIMIT,
    SMA_MEDIUM_PERIOD,
    SLIPPAGE_RATE, load_insider_exclusion_codes
)
from core.file_io import atomic_write_json

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
    RealtimeBuffer, calculate_dynamic_leverage
)
from core.monthly_rotation_strategy import (
    build_rotation_live_snapshot,
    build_rotation_entry_plan,
    build_rotation_position_record,
    build_rotation_rebalance_plan,
    build_rotation_watchlist,
    compute_rotation_order_size,
    PROD_MONTHLY_ROTATION_CONFIG,
    mark_rotation_portfolio,
)
from core.ai_filter import ai_qualitative_filter, get_recent_news

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
    watchlist = []
    special_quote_watchlist = {} # { "code": item_dict }
    realtime_buffers = {}
    canceled_orders = {}
    cooling_until = None # [V132] Over-trading prevention (Date based parity)
    breadth_val = 0.5    # [Parity] Market breadth (updated each scan, default neutral)
    
    # --- [Aegis Protocol State] ---
    current_month_str = server_datetime.strftime('%Y-%m')
    account_data = safe_read_json(ACCOUNT_FILE)
    month_start_equity = account_data.get('month_start_equity', 0)
    
    # 初回起動時または月替わり時に月初資産を記録
    account = broker.get_account_balance()
    initial_total = account['cash'] + sum([p.get('current_price', p['buy_price']) * p['shares'] for p in broker.get_positions()])
    if month_start_equity <= 0 or current_month_str != account_data.get('current_month', ''):
        month_start_equity = initial_total
        account_data['month_start_equity'] = month_start_equity
        account_data['current_month'] = current_month_str
        atomic_write_json(ACCOUNT_FILE, account_data)
        print(f"🛡️ [Aegis] 新しい月の開始です。月初資産を記録しました: Y{month_start_equity:,.0f}")

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
            account = broker.get_account_balance()
            portfolio = broker.get_positions()
        except Exception as e:
            print(f"[WARNING] 口座情報取得エラー: {e}")
            time.sleep(MONITOR_INTERVAL_SEC)
            continue

        # --- [Step 3.2] 特注監視（特別気配・価格未定）銘柄の高頻度チェック ---
        force_scan = False
        if special_quote_watchlist and len(portfolio) < PROD_MONTHLY_ROTATION_CONFIG.max_pos:
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

        try:
            watch_plan = build_rotation_watchlist(
                candidates=[{"code": code} for code in watchlist],
                portfolio=portfolio,
                max_pos=PROD_MONTHLY_ROTATION_CONFIG.max_pos,
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
                        realtime_buffers[code].update(price, vol, server_datetime)
        except Exception as e:
            print(f"[WARNING] バッファ同期エラー: {e}")

        try:
            # [V131.1 Aegis Enhancement] Regime Filter & Trend Health
            regime, is_trend_snapped = detect_market_regime(data_df=jp_cache_df, buffer=realtime_buffers)
        except:
            regime, is_trend_snapped = "RANGE", False
            last_scan_time = loop_start_time

        # Calculate Monthly Drawdown for Aegis Protocol
        current_total = account['cash'] + sum([float(p.get('current_price', p['buy_price'])) * int(p['shares']) for p in portfolio])
        month_drawdown = (current_total / month_start_equity) - 1.0 if month_start_equity > 0 else 0
        
        print(f"[STAT] レジーム: 【{regime}】 | TrendSnapped: {is_trend_snapped} | MonthDD: {month_drawdown:+.2%}")
        
        latest_close_map = {
            str(code).replace(".T", ""): float(info.get("Close", 0) or 0)
            for code, info in jp_cache.items()
        }
        portfolio = mark_rotation_portfolio(
            portfolio,
            realtime_buffers=realtime_buffers,
            latest_close_map=latest_close_map,
        )

        # [V17.0 Final Persistence]
        # [V17.0 Imperial Sync] Finalizing position and equity state for the current loop.
        broker.save_account(account)
        broker.save_portfolio(portfolio)

        should_scan = True
        if month_drawdown <= -0.15 and not portfolio: should_scan = False  # Block fresh entries, but still allow rebalance/liquidation.
        elif not should_scan_override: should_scan = False
        elif now_time < datetime.time(9, 30) and not DEBUG_MODE: should_scan = False
        elif now_time >= datetime.time(14, 0) and not DEBUG_MODE: should_scan = False
        
        if should_scan and not force_scan:
             if time.time() - last_scan_time < SCAN_INTERVAL_SEC:
                  should_scan = False

        if should_scan:
            last_scan_time = time.time()
            print("\n=> 🔍 定期スキャン処理（銘柄探索）を開始します...")
            
            should_continue_scan = True
            # [V17.0 Imperial Sync] Use JQuants Cache instead of yfinance
            try:
                if os.path.exists(JQUANTS_CACHE_FILE):
                    with open(JQUANTS_CACHE_FILE, 'rb') as f:
                        data_df = pickle.load(f)
                    
                    # Clean MultiIndex columns
                    new_cols = []
                    for col in data_df.columns:
                        ticker, field = col[0], col[1]
                        if isinstance(field, tuple): field = field[0]
                        new_cols.append((ticker, field))
                    data_df.columns = pd.MultiIndex.from_tuples(new_cols)
                    
                    # Filtering targets
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
                    
                    snapshot = build_rotation_live_snapshot(
                        data_df=data_df,
                        symbols_df=df_symbols,
                        held_codes=held_codes,
                        config=PROD_MONTHLY_ROTATION_CONFIG,
                    )
                    breadth_val = snapshot["breadth"] if snapshot["breadth"] > 0 else 0.5
                    print(f"📊 [Rotation] Market Breadth (Prime): {breadth_val:.1%}")

                    dynamic_lev = calculate_dynamic_leverage(breadth_val, config_leverage=LEVERAGE_RATE)
                    if not snapshot["is_bull"] or dynamic_lev <= 0:
                        print("🛡️ [Safeguard] Shared monthly rotation filter is not in entry mode.")

                    print(f"✅ Scanning {len(targets)} tickers from JQuants Cache (Leverage: {dynamic_lev}x).")
                else:
                    print("❌ JQuants Cache not found. Skipping scan.")
                    should_continue_scan = False
            except Exception as e:
                print(f"[WARNING] JQuants Cache 読込エラー: {e}")
                should_continue_scan = False

            if should_continue_scan:
                # [Optimization] We cannot fetch 3400+ board prices sequentially via kabucom REST API (exhausts quota and takes 15 mins).
                # We rely purely on highly accurate JQuants EOD cache for the initial heavy Perfect Order scan.
                # Live validation is done on the top 50 candidates in the next step.
                if not is_sim:
                     print("🚀 [OMS] 一次スキャンはJQuantsキャッシュ(EOD)速度を優先して実行します...")
                
                try:
                    last_update = data_df.index[-1]
                    if last_update.tzinfo is None: last_update = last_update.replace(tzinfo=JST)
                    age = calculate_effective_age(last_update, datetime.datetime.now(JST))
                    if age > 3600:
                        print(f"⚠️ [Data Delay Warning] Acquired price data is too old (effective delay: {age/60:.1f} minutes).")
                except: pass

            if should_continue_scan:
                top_candidates = snapshot["top_candidates"]
                rotation_breadth = snapshot["breadth"]
                rotation_bull = snapshot["is_bull"]
                if rotation_bull:
                    breadth_val = rotation_breadth
                    dynamic_lev = PROD_MONTHLY_ROTATION_CONFIG.leverage_rate
                latest_close_snapshot = snapshot["latest_close_map"]
                sma20_snapshot = snapshot["sma20_map"]
                portfolio = mark_rotation_portfolio(
                    portfolio,
                    realtime_buffers=realtime_buffers,
                    latest_close_map=latest_close_snapshot,
                )

                rebalance_plan = build_rotation_rebalance_plan(
                    portfolio=portfolio,
                    snapshot=snapshot,
                    config=PROD_MONTHLY_ROTATION_CONFIG,
                )
                rebalanced_portfolio = list(rebalance_plan["keep_positions"])
                for p in rebalance_plan["exit_positions"]:

                    code = str(p["code"])
                    shares = int(p["shares"])
                    current_price = float(p.get("current_price", p["buy_price"]))

                    if is_sim:
                        sell_price = current_price * (1.0 - SLIPPAGE_RATE)
                        pnl = (sell_price - float(p["buy_price"])) * shares
                        account["cash"] = round(float(account["cash"]) + (sell_price * shares), 4)
                        broker.log_trade({
                            "time": datetime.datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S'),
                            "code": code,
                            "name": p.get("name", code),
                            "side": "ROTATION_SELL",
                            "shares": shares,
                            "buy_price": round(float(p["buy_price"]), 4),
                            "sell_price": round(float(sell_price), 4),
                            "pnl": round(float(pnl), 4),
                            "holding_days": 0,
                            "note": "monthly_rotation_exit",
                        })
                        actions_taken.append(f"SELL {code} - Monthly rotation exit (@{sell_price:,.1f})")
                    else:
                        details = broker.execute_chase_order(code, shares, side="1")
                        if details and details.get("State") in [6, 7]:
                            exec_qty = int(details.get("Qty", shares))
                            exec_price = float(details.get("Price", current_price)) or current_price
                            if exec_qty < shares:
                                remainder = dict(p)
                                remainder["shares"] = shares - exec_qty
                                rebalanced_portfolio.append(remainder)
                            actions_taken.append(f"SELL {code} - Monthly rotation exit (@{exec_price:,.1f})")
                        else:
                            rebalanced_portfolio.append(p)
                            continue

                portfolio = rebalanced_portfolio
                broker.save_account(account)
                broker.save_portfolio(portfolio)

                if not top_candidates:
                    should_continue_scan = False
                else:
                    watch_plan = build_rotation_watchlist(
                        candidates=top_candidates,
                        portfolio=portfolio,
                        max_pos=PROD_MONTHLY_ROTATION_CONFIG.max_pos,
                    )
                    watchlist = watch_plan["watchlist"]
                    realtime_buffers = {}
                    empty_df = pd.DataFrame()
                    for code in watchlist:
                        realtime_buffers[code] = RealtimeBuffer(code, empty_df)
                    for p in portfolio:
                        c = str(p['code'])
                        if c not in realtime_buffers:
                            realtime_buffers[c] = RealtimeBuffer(c, empty_df)
                    if '1321' not in realtime_buffers:
                        try:
                            if '1321.T' in jp_cache:
                                realtime_buffers['1321'] = RealtimeBuffer('1321', None)
                                realtime_buffers['1321'].latest_price = jp_cache['1321.T'].get('Close', 0)
                        except:
                            pass
                    if not is_sim:
                        broker.unregister_all()
                        broker.register_symbols(watch_plan["registration_targets"])

            if should_continue_scan and rotation_bull:
                print(f"\n--- AI Qualitative Filter Check ---")
                scan_targets = top_candidates
                num_filled = 0
                max_to_buy = PROD_MONTHLY_ROTATION_CONFIG.max_pos - len(portfolio)
                
                if max_to_buy <= 0:
                    should_continue_scan = False
                else:
                    selected_candidates = []
                    for item in scan_targets:
                        if len(selected_candidates) >= max_to_buy:
                            break
                        
                        # 1. 特別気配チェック
                        if not is_sim and hasattr(broker, 'get_board_data'):
                            try:
                                board = broker.get_board_data([item['code']])
                                b_info = board.get(str(item['code']).replace(".T", ""))
                                if b_info:
                                    c_price = b_info.get('price')
                                    p_close = b_info.get('prev_close', item['price'])
                                    if not c_price or c_price == 0:
                                        print(f"WAIT: {item['code']} special quote or undecided. Adding to watchlist.")
                                        special_quote_watchlist[str(item['code'])] = item
                                        continue
                                    gap_pct = (c_price - p_close) / p_close if p_close > 0 else 0
                                    gap_threshold = BULL_GAP_LIMIT
                                    if gap_pct < -0.02 or abs(gap_pct) > gap_threshold:
                                        print(f"[Skip] {item['code']} Gap check failed: {gap_pct:.2%}")
                                        continue
                                    item['price'] = c_price
                            except Exception as e:
                                print(f"[WARNING] 板情報チェック中のエラー: {e}")

                        # 2. AI定性フィルタ
                        news = get_recent_news(item['code'], item['name'])
                        if news and news != "ニュースなし":
                            is_safe, reason = ai_qualitative_filter(item['code'], item['name'], news)
                            if not is_safe:
                                print(f"🚫 [AI Filter] {item['code']} skipped: {reason}")
                                continue

                        selected_candidates.append(item)

                    if not selected_candidates:
                        should_continue_scan = False
                    else:
                        entry_plan = build_rotation_entry_plan(
                            candidates=selected_candidates,
                            portfolio=portfolio,
                            account_cash=account['cash'],
                            dynamic_leverage=dynamic_lev,
                            config=PROD_MONTHLY_ROTATION_CONFIG,
                        )
                        target_allocations = entry_plan["target_allocations"]

                        for item in entry_plan["planned_entries"]:

                            p = float(item['price']) if item['price'] else 0.0
                            a = float(item.get('atr', 0))
                            if p <= 0 or a <= 0:
                                continue

                            buy_price = normalize_tick_size(p, is_buy=True)
                            target_allocation = target_allocations.get(str(item['code']), 0.0)
                            ts = compute_rotation_order_size(
                                target_allocation=target_allocation,
                                buy_price=buy_price,
                                account_cash=account['cash'],
                            )
                            if ts < 100:
                                continue

                            if is_sim:
                                print(f"🛒 [BUY SIM] {item['code']} {ts} shares @ {buy_price}")
                                exec_p = buy_price * (1.0 + SLIPPAGE_RATE)
                                account['cash'] -= exec_p * ts
                                portfolio.append(
                                    build_rotation_position_record(
                                        item=item,
                                        executed_price=exec_p,
                                        shares=ts,
                                        buy_time=datetime.datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S'),
                                    )
                                )
                                num_filled += 1
                            else:
                                print(f"🚀 [OMS] Chase: {item['code']} ({ts} shares)")
                                details = broker.execute_chase_order(item['code'], ts, side="2", atr=a)
                                if details and details.get('State') in [6, 7]:
                                    actual_qty = int(details.get('Qty', 0))
                                    exec_p = float(details.get('Price', 0)) or buy_price
                                    if not broker.is_production: account['cash'] -= exec_p * actual_qty

                                    portfolio.append(
                                        build_rotation_position_record(
                                            item=item,
                                            executed_price=exec_p,
                                            shares=actual_qty,
                                            buy_time=datetime.datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S'),
                                        )
                                    )
                                    num_filled += 1

                            if hasattr(broker, 'save_portfolio'): broker.save_portfolio(portfolio)
                            if hasattr(broker, 'save_account'): broker.save_account(account)
                            if item['code'] in watchlist: watchlist.remove(item['code'])

        summary_record = {
            "time": datetime.datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S'),
            "actions": actions_taken,
            "portfolio": portfolio,
            "stock_value_yen": sum([float(p.get('current_price', p['buy_price'])) * int(p['shares']) for p in portfolio]),
            "cash_yen": account['cash'],
            "total_assets_yen": account['cash'] + sum([float(p.get('current_price', p['buy_price'])) * int(p['shares']) for p in portfolio]),
            "regime": regime
        }
        if hasattr(broker, 'log_execution_summary'): broker.log_execution_summary(summary_record)

        elapsed = time.time() - loop_start_time
        sleep_time = max( MONITOR_INTERVAL_SEC - elapsed, 5.0)
        print(f"\nNext loop in {sleep_time:.1f}s...")
        time.sleep(sleep_time)

if __name__ == "__main__":
    main()
