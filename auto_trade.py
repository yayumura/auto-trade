import os
import sys
import io
import random
import datetime
import yfinance as yf
import pandas as pd
import numpy as np
import time
import re
import warnings
import json
import signal
import jpholiday
from enum import Enum
from core.log_setup import setup_logging, send_discord_notify
from core.preflight import pre_flight_check
from core.kabu_launcher import ensure_kabu_station_running, terminate_kabu_station, check_api_health
from core.utils import calculate_effective_age, get_previous_business_day

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
    DATA_FILE, PORTFOLIO_FILE, HISTORY_FILE, ACCOUNT_FILE, 
    EXECUTION_LOG_FILE, EXCLUSION_CACHE_FILE, TARGET_MARKETS,
    GEMINI_API_KEY, GROQ_API_KEY, DISCORD_WEBHOOK_URL, GEMINI_MODEL,
    DEBUG_MODE, TRADE_MODE, INITIAL_CASH, MAX_POSITIONS, MAX_RISK_PER_TRADE,
    MAX_ALLOCATION_PCT, MAX_ALLOCATION_AMOUNT, LIQUIDITY_LIMIT_RATE, MIN_ALLOCATION_AMOUNT,
    ATR_STOP_LOSS, RANGE_ATR_STOP_LOSS, ATR_TRAIL, TAX_RATE, JST,
    load_insider_exclusion_codes
)
from core.file_io import atomic_write_json, atomic_write_csv, safe_read_json, safe_read_csv

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
    detect_market_regime, manage_positions_live, select_best_candidates, 
    load_invalid_tickers, save_invalid_tickers, normalize_tick_size,
    RealtimeBuffer
)
from core.ai_filter import ai_qualitative_filter, get_recent_news

# --- シグナルハンドラ ---
def handle_shutdown(signum, frame):
    print(f"\n[STOP] シグナル({signum})を受信しました。安全にシャットダウンを開始します...")
    try:
        send_discord_notify("[STOP] 【システム通知】運営者による停止操作（Ctrl+C等）を検知しました。ボットを安全に終了します。")
    except: pass
    release_lock()
    sys.exit(0)

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
    
    # --- [Hybrid Monitoring State] ---
    watchlist = []
    special_quote_watchlist = {} # { "code": item_dict }
    realtime_buffers = {}
    has_morning_scanned = False
    canceled_orders = {}

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
            
        print(f"\n[{datetime.datetime.now(JST).strftime('%H:%M:%S')}] [UP] 監視サイクル開始 (サーバー時刻: {now_time.strftime('%H:%M:%S')} - Phase: {phase.value})")

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
                if phase == MarketPhase.PRE_MARKET and now_time >= datetime.time(8, 30) and not has_morning_scanned:
                    pass 
                else:
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

        try:
            current_targets = set(watchlist + [str(p['code']) for p in portfolio] + ['1321'])
            already_tracked = set(realtime_buffers.keys())
            new_codes = current_targets - already_tracked
            removed_codes = (already_tracked - current_targets) - {'1321'}
            
            if not is_sim:
                if new_codes: broker.register_symbols(list(new_codes))
                if removed_codes: broker.unregister_symbols(list(removed_codes))
            
            for code in new_codes:
                print(f"[NEW] 新規銘柄をバッファに追加: {code}")
                hist = yf.download(str(code)+".T", period="10d", interval="15m", progress=False, threads=False)
                realtime_buffers[code] = RealtimeBuffer(code, hist, interval_mins=15)
            
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
            regime = detect_market_regime(broker=broker, buffer=None)
        except:
            regime = "RANGE"
            last_scan_time = loop_start_time

        print(f"[STAT] 現在のレジーム: 【{regime}】")
        
        portfolio, account, sell_actions, trade_logs_from_manage = manage_positions_live(
            portfolio, account, broker=broker, regime=regime, is_simulation=is_sim,
            realtime_buffers=realtime_buffers
        )
        
        actions_taken.extend(sell_actions)
        for log in trade_logs_from_manage:
            timing = log.get('timing', 'immediate')
            if timing == 'next_open':
                # タイムリミット → 翌朝始値で売却（即時執行しない）
                print(f"⏰ [DEFERRED] {log['code']}: タイムリミット → 翌朝始値で売却予定")
                if hasattr(broker, 'log_trade'): broker.log_trade(log)
                continue
            if not is_sim:
                broker.execute_chase_order(log['code'], log['shares'], side="1")
            if hasattr(broker, 'log_trade'): broker.log_trade(log)
        
        if hasattr(broker, 'save_portfolio'): broker.save_portfolio(portfolio)
        if hasattr(broker, 'save_account'): broker.save_account(account)

        should_scan = True
        if regime == "BEAR": should_scan = False
        elif len(portfolio) >= MAX_POSITIONS: should_scan = False
        elif now_time < datetime.time(9, 30) and not DEBUG_MODE: should_scan = False
        elif now_time >= datetime.time(14, 0) and not DEBUG_MODE: should_scan = False
        
        if phase == MarketPhase.PRE_MARKET and now_time >= datetime.time(8, 30) and not has_morning_scanned:
             should_scan = True
             is_morning_scan = True
        else:
             is_morning_scan = False

        if should_scan and not (is_morning_scan or force_scan):
             if time.time() - last_scan_time < SCAN_INTERVAL_SEC:
                  should_scan = False

        if should_scan:
            last_scan_time = time.time()
            print("\n=> 🔍 定期スキャン処理（銘柄探索）を開始します...")
            
            should_continue_scan = True
            try:
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
                tickers = [f"{code}.T" for code in targets]
            except Exception as e:
                print(f"[WARNING] 銘柄リスト読込エラー: {e}")
                should_continue_scan = False

            if should_continue_scan:
                data_dfs = []
                chunk_size = 100 
                for i in range(0, len(tickers), chunk_size):
                    chunk = tickers[i:i + chunk_size]
                    if i > 0: time.sleep(random.uniform(0.5, 1.5))
                    try:
                        dl_period = "2y" if is_morning_scan else "1mo" 
                        dl_interval = "1d" if is_morning_scan else "15m"
                        chunk_df = yf.download(chunk, period=dl_period, interval=dl_interval, group_by='ticker', 
                                               auto_adjust=False, threads=False, progress=False)
                        if chunk_df is not None and not chunk_df.empty:
                            if isinstance(chunk_df.columns, pd.MultiIndex):
                                data_dfs.append(chunk_df)
                            elif len(chunk) == 1:
                                chunk_df.columns = pd.MultiIndex.from_product([[chunk[0]], chunk_df.columns])
                                data_dfs.append(chunk_df)
                    except: pass
                    finally: time.sleep(random.uniform(1.0, 2.5))

                if not data_dfs: should_continue_scan = False
            
            if should_continue_scan:
                data_df = pd.concat(data_dfs, axis=1, sort=False) if len(data_dfs) > 1 else data_dfs[0]
                # [Step 1.3] Real-time injection
                if not is_sim and hasattr(broker, 'get_board_data'):
                    print("🚀 [OMS] テクニカル計算に最新の板情報を反映します...")
                    try:
                        board_res = broker.get_board_data(tickers)
                        now_jst = datetime.datetime.now(JST)
                        for t_id in tickers:
                            # tickersは "7203.T", board_resのキーは "7203"
                            code_only = t_id.replace(".T", "")
                            if code_only in board_res:
                                bx = board_res[code_only]
                                px = bx.get('price')
                                if px and px > 0:
                                    data_df.loc[now_jst, (t_id, 'Close')] = px
                                    data_df.loc[now_jst, (t_id, 'High')] = bx.get('high') or px
                                    data_df.loc[now_jst, (t_id, 'Low')] = bx.get('low') or px
                                    data_df.loc[now_jst, (t_id, 'Volume')] = bx.get('volume', 0)
                                    data_df.loc[now_jst, (t_id, 'Open')] = bx.get('open') or px
                        data_df.sort_index(inplace=True)
                    except Exception as e:
                        print(f"[WARNING] リアルタイム価格の注入に失敗しました: {e}")

                try:
                    last_update = data_df.index[-1]
                    if last_update.tzinfo is None: last_update = last_update.replace(tzinfo=JST)
                    age = calculate_effective_age(last_update, datetime.datetime.now(JST))
                    if is_morning_scan:
                        prev_biz = get_previous_business_day(datetime.datetime.now(JST))
                        if last_update.date() < prev_biz: should_continue_scan = False
                    elif age > 3600:
                        print(f"⚠️ [Data Delay Warning] Acquired price data is too old (effective delay: {age/60:.1f} minutes).")
                except: pass

            if should_continue_scan:
                top_candidates = select_best_candidates(data_df, targets, df_symbols, regime, realtime_buffers=realtime_buffers)
                
                if is_morning_scan:
                    max_watchlist = max(5, 50 - len(portfolio) - 2) 
                    watchlist = [c['code'] for c in top_candidates[:max_watchlist]]
                    has_morning_scanned = True
                    realtime_buffers = {}
                    for code in watchlist: realtime_buffers[code] = RealtimeBuffer(code, data_df)
                    for p in portfolio:
                        c = str(p['code'])
                        if c not in realtime_buffers: realtime_buffers[c] = RealtimeBuffer(c, data_df)
                    if '1321' not in realtime_buffers:
                        try:
                            df_1321 = yf.download('1321.T', period='1mo', interval='15m', progress=False)
                            realtime_buffers['1321'] = RealtimeBuffer('1321', df_1321)
                        except: pass
                    if not is_sim:
                        broker.unregister_all()
                        reg_targets = watchlist + list(set(str(p['code']) for p in portfolio))
                        broker.register_symbols(reg_targets[:50])
                    should_continue_scan = False
                
                elif not top_candidates:
                    should_continue_scan = False

            if should_continue_scan and regime in ["BULL", "RANGE"]:
                print(f"\n--- AI Qualitative Filter Check ---")
                scan_targets = top_candidates
                num_filled = 0
                max_to_buy = MAX_POSITIONS - len(portfolio)
                
                if max_to_buy <= 0:
                    should_continue_scan = False
                else:
                    for item in scan_targets:
                        if num_filled >= max_to_buy: break
                        
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
                                    gap_threshold = 0.05 if regime == "BULL" else 0.02
                                    if (regime == "BULL" and gap_pct < -0.02) or (regime != "BULL" and abs(gap_pct) > gap_threshold):
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

                        # 3. 資金管理と注文
                        p = float(item['price']) if item['price'] else 0.0
                        a = float(item.get('atr', 0))
                        if p <= 0 or a <= 0: continue
                        
                        tp = normalize_tick_size(p + (a * 0.1), is_buy=True)
                        te = account['cash'] + sum([float(px.get('current_price', px['buy_price'])) * int(px['shares']) for px in portfolio])
                        ra = te * MAX_RISK_PER_TRADE
                        sm = RANGE_ATR_STOP_LOSS if regime == "RANGE" else ATR_STOP_LOSS
                        rps = a * sm
                        is_sh = int(ra // rps) if rps > 0 else 100
                        ma = min(max(te * MAX_ALLOCATION_PCT, MIN_ALLOCATION_AMOUNT), MAX_ALLOCATION_AMOUNT)
                        adv = item.get('adv_yen', 0)
                        if adv > 0:
                            ma = min(ma, adv * LIQUIDITY_LIMIT_RATE)
                        
                        ms_a = int(ma // tp)
                        ms_c = int((account['cash'] / 1.0001) // tp)
                        ts = (min(is_sh, ms_a, ms_c) // 100) * 100
                        
                        if ts >= 100:
                            if is_sim:
                                print(f"🛒 [BUY SIM] {item['code']} {ts} shares @ {tp}")
                                account['cash'] -= tp * ts
                                portfolio.append({"code": item['code'], "name": item['name'], "buy_time": datetime.datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S'), "buy_price": round(tp, 1), "highest_price": round(tp, 1), "current_price": round(tp, 1), "shares": ts, "buy_atr": a})
                                num_filled += 1
                            else:
                                print(f"🚀 [OMS] Chase: {item['code']} ({ts} shares)")
                                details = broker.execute_chase_order(item['code'], ts, side="2", atr=a)
                                if details and details.get('State') in [6, 7]:
                                    actual_qty = int(details.get('Qty', 0))
                                    exec_p = float(details.get('Price', 0)) or tp
                                    if not broker.is_production: account['cash'] -= exec_p * actual_qty
                                    portfolio.append({"code": item['code'], "name": item['name'], "buy_time": datetime.datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S'), "buy_price": round(exec_p, 1), "highest_price": round(exec_p, 1), "current_price": round(exec_p, 1), "shares": actual_qty, "buy_atr": a})
                                    num_filled += 1
                            if hasattr(broker, 'save_portfolio'): broker.save_portfolio(portfolio)
                            if hasattr(broker, 'save_account'): broker.save_account(account)
                            if item['code'] in watchlist: watchlist.remove(item['code'])
                        else:
                            print(f"[Skip] {item['code']} Budget short.")

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
