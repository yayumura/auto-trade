import os
import sys
import io
import random
from datetime import datetime
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
from core.kabu_launcher import ensure_kabu_station_running
from core.utils import calculate_effective_age, get_previous_business_day

class MarketPhase(Enum):
    PRE_MARKET = "寄り前"
    MORNING = "前場"
    LUNCH = "昼休み"
    AFTERNOON = "後場"
    CLOSING_TIME = "大引け後"

def get_market_phase(now_time) -> MarketPhase:
    """現在時刻から市場のフェーズを判定する"""
    t900 = datetime.strptime("09:00", "%H:%M").time()
    t1130 = datetime.strptime("11:30", "%H:%M").time()
    t1230 = datetime.strptime("12:30", "%H:%M").time()
    t1530 = datetime.strptime("15:30", "%H:%M").time()
    
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
    MAX_ALLOCATION_PCT, MIN_ALLOCATION_AMOUNT,
    ATR_STOP_LOSS, RANGE_ATR_STOP_LOSS, ATR_TRAIL, TAX_RATE, JST,
    load_insider_exclusion_codes
)
from core.file_io import atomic_write_json, atomic_write_csv, safe_read_json, safe_read_csv

# --- インスタンスロック機構 ---
LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".bot_sim.lock")

def acquire_lock():
    """原子的なロックファイル取得。open('x')はファイルが既存の場合FileExistsErrorを発生させる（TOCTOU安全）。"""
    # まず既存ロックが有効なプロセスのものか確認
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                old_pid = int(f.read().strip())
            import psutil
            if psutil.pid_exists(old_pid):
                print(f"[WARNING] エラー: 他のインスタンス(PID: {old_pid})が既に実行中です。")
                return False
            # 古いプロセスは終了済み → ロックファイルを削除して再取得
            print(f"[WARNING] 古いロックファイルを検出(PID: {old_pid}, 既に終了)。削除して続行します。")
            os.remove(LOCK_FILE)
        except (ValueError, ImportError, OSError) as e:
            print(f"[WARNING] ロックファイルの解析に失敗しました({e})。古いロックを削除して続行します。")
            try:
                os.remove(LOCK_FILE)
            except OSError:
                pass
    # open('x') = 排他的新規作成。ファイルが既存の場合は FileExistsError (原子的)
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

# --- 不要になった既存CSVとJSONの読み書き処理およびサマリー出力（M-1, L-2） ---
# これらはBroker(sim_broker.py, kabucom_broker.py)内に移行済みのため削除しました。


from core.logic import (
    detect_market_regime, manage_positions, select_best_candidates, 
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
        msg = f"[CRITICAL] 【致命的システムエラー】シミュレーションループ内で予期せぬ例外が発生しました:\n{e}"
        print(msg)
        try:
            send_discord_notify(msg)
        except:
            pass
        time.sleep(10)
    finally:
        release_lock()

def _main_exec():
    # --- 【新規】kabuステーションの自動起動・ログイン ---
    if TRADE_MODE in ["KABUCOM_LIVE", "KABUCOM_TEST"]:
        if not ensure_kabu_station_running():
            print("❌ kabuステーションの準備が整わなかったため、システムを終了します。")
            return

    # 既存のプレフライトチェック
    if not pre_flight_check():
        print("❌ [Pre-flight Error] 起動前点検に失敗しました。処理を中断します。")
        return
    
    setup_logging()
    
    # [Day 2 Ops] CSV肥大化防止のアーカイブ処理
    from core.file_io import rotate_csv_if_large
    rotate_csv_if_large(EXECUTION_LOG_FILE, max_size_mb=2)
    rotate_csv_if_large(HISTORY_FILE, max_size_mb=2)
    
    # --- 1. Brokerの初期化 ---
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

    # --- [Phase 11] Resource Watcher ---
    try:
        import psutil
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        print(f"[STAT] [System Health] Memory Usage: {mem_info.rss / 1024 / 1024:.1f} MB | CPU: {psutil.cpu_percent()}%")
    except ImportError:
        pass
    except Exception as e:
        print(f"[WARNING] リソース監視中にエラー: {e}")

    print(f"\n[START] ヘッジファンド仕様・アルゴリズムBOT 起動 (自律ループ型監視中)")

    # --- [V2-C1] ループ頻度の分離 ---
    last_scan_time = 0
    SCAN_INTERVAL_SEC = 900   # スキャン間隔（15分）
    MONITOR_INTERVAL_SEC = 30 # ポジション監視間隔（30秒）
    
    # --- [Hybrid Monitoring State] ---
    watchlist = []
    realtime_buffers = {} # { "code": RealtimeBuffer_instance }
    has_morning_scanned = False
    registered_count = 0

    # [Day 2 Ops] タイムアウトによりキャンセル要求済みの注文IDをキャッシュする（回数カウント付き）
    canceled_orders = {}

    while True:
        # [Phase 15] ファイルベース・ソフトストップ
        if os.path.exists("stop.txt"):
            print("[STOP] stop.txt を検出しました。安全に停止します。")
            try: os.remove("stop.txt")
            except: pass
            break

        loop_start_time = time.time()
        # --- [Phase 14] Server Time Sync ---
        server_datetime = broker.get_server_time() if hasattr(broker, 'get_server_time') else datetime.now(JST)
        now_time = server_datetime.time()

        phase = get_market_phase(now_time)
        print(f"\n[{datetime.now(JST).strftime('%H:%M:%S')}] [UP] 監視サイクル開始 (サーバー時刻: {now_time.strftime('%H:%M:%S')} - Phase: {phase.value})")

        if phase == MarketPhase.CLOSING_TIME and not DEBUG_MODE:
            print("\n🏁 15:30（大引け）を過ぎました。本日の運用を終了します。")
            send_discord_notify("🏁 【業務終了】15:30（大引け）を過ぎたため、自動運用を終了しました。")
            if not is_sim:
                broker.unregister_all() # [Expert Refinement] 終了時に登録解除
                # [Professional Audit] 未約定注文があれば全て強制的にキャンセル（翌日への持ち越し防止）
                active_orders_final = broker.get_active_orders()
                for o in active_orders_final:
                    oid = o.get('ID')
                    if oid:
                        print(f"🧹 [Closing Cleanup] 未約定注文 {oid} を取り消します...")
                        broker.cancel_order(oid)
            break

        if not DEBUG_MODE:
            # H-3修正: 土日 + 日本の祝日（jpholiday）を判定
            is_weekend = server_datetime.weekday() >= 5
            is_holiday = jpholiday.is_holiday(server_datetime.date())
            if is_weekend or is_holiday:
                reason = "土日" if is_weekend else f"祝日({jpholiday.is_holiday_name(server_datetime.date())})"
                print(f"💤 本日は市場休業日（{reason}）です。")
                break
            
            if phase in [MarketPhase.PRE_MARKET, MarketPhase.LUNCH]:
                # 寄り前のみスキャンを実行 (朝8:30以降)
                if phase == MarketPhase.PRE_MARKET and now_time >= datetime.strptime("08:30", "%H:%M").time() and not has_morning_scanned:
                    print(f"🌅 【朝のスキャン】監視銘柄の選定を開始します...")
                    # ここでダミーの should_scan をバイパスして強制実行
                    pass 
                else:
                    print(f"💤 取引時間外（{phase.value}）です。次の監視まで待機します...")
                    time.sleep(MONITOR_INTERVAL_SEC)
                    continue

        # --- 【追加】In-flight Guard をループ内に移動（二重発注の完全防止） ---
        if not is_sim:
            try:
                active_orders = broker.get_active_orders()
                if active_orders:
                    # [OK] [Day 2 Ops] 未約定注文のオートキャンセル（5分滞留）
                    has_stuck_order = False
                    for order in active_orders:
                        order_id = order.get('ID')
                        recv_time_str = order.get('RecvTime')
                        if order_id and recv_time_str:
                            try:
                                clean_time_str = recv_time_str[:19].replace("T", " ")
                                order_time = datetime.strptime(clean_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=JST)
                                duration_mins = (datetime.now(JST) - order_time).total_seconds() / 60
                                
                                if duration_mins >= 5.0:
                                    # [Phase 11] 注文キャッシュの定期清掃 (1000件超で古い順に削除)
                                    if len(canceled_orders) > 1000:
                                        oldest_keys = sorted(canceled_orders.keys())[:100]
                                        for k in oldest_keys: canceled_orders.pop(k, None)

                                    cancel_count = canceled_orders.get(order_id, 0)
                                    if cancel_count >= 3:
                                        # 【修正】通知は「ちょうど3回目」の時だけ送る（スパム防止）
                                        if cancel_count == 3:
                                            msg = f"🚨 【要手動介入】注文 ID: {order_id} が3回取消要求しても消えません！証券アプリから状況を確認してください。"
                                            print(msg)
                                            send_discord_notify(msg)
                                        
                                        # カウントを進めて次回以降の通知を抑制
                                        canceled_orders[order_id] = cancel_count + 1
                                        # has_stuck_order = True にしないことで、10sループに吸い込まれるのを防ぐ
                                        # 後続の「未約定注文あり」ブロックで30s待機状態に移行させる
                                        continue

                                    print(f"🚨 【タイムアウト】注文ID: {order_id} は発注から {duration_mins:.1f} 分経過しましたが約定していません。")
                                    print(f"🔄 ゾンビ化と完全フリーズを防ぐため、強制オートキャンセルを実行します（試行 {cancel_count + 1}/3）。")
                                    if broker.cancel_order(order_id):
                                        canceled_orders[order_id] = cancel_count + 1
                                    
                                    send_discord_notify(f"🚨 【オートキャンセル発動】注文ID: {order_id} が5分以上約定しないため、システムが取り消しを試行しました。")
                                    has_stuck_order = True
                            except Exception as e:
                                print(f"[WARNING] 注文時間のパースエラー: {e}")

                    if has_stuck_order:
                        print("⏳ キャンセル処理を行ったため、反映を待機します...")
                        time.sleep(10)
                        continue
                        
                    msg = f"[WARNING] 【警告】未約定の注文が {len(active_orders)} 件残っています。二重発注事故を防ぐため、約定または取消されるまでスキャンを待機します。"
                    print(msg)
                    send_discord_notify(msg)
                    print(f"\n💤 次の監視({MONITOR_INTERVAL_SEC}秒後)まで待機します...")
                    time.sleep(MONITOR_INTERVAL_SEC)
                    continue
            except Exception as e:
                print(f"[WARNING] 注文状態の確認エラー: {e}")

        # --- 【修正】Brokerパターン完全適用（APIから最新の口座・ポジションを取得） ---
        try:
            account = broker.get_account_balance()
            portfolio = broker.get_positions()
        except Exception as e:
            msg = f"[WARNING] 【API通信エラー】口座情報またはポジションの取得に失敗しました: {e}"
            print(msg)
            send_discord_notify(msg)
            print(f"\n💤 一時的な通信障害のため、次の監視({MONITOR_INTERVAL_SEC}秒後)まで待機します...")
            time.sleep(MONITOR_INTERVAL_SEC)
            continue

        actions_taken = []
        trade_logs = [] 

        # --- 1. [Phase 4] 銘柄登録・バッファ同期ロジック ---
        try:
            current_targets = set(watchlist + [str(p['code']) for p in portfolio] + ['1321'])
            already_tracked = set(realtime_buffers.keys())
            
            new_codes = current_targets - already_tracked
            removed_codes = (already_tracked - current_targets) - {'1321'}
            
            if not is_sim:
                if new_codes:
                    broker.register_symbols(list(new_codes))
                if removed_codes:
                    broker.unregister_symbols(list(removed_codes))
            
            # 新規銘柄の初期化（yfinanceからのシードデータ取得）
            for code in new_codes:
                print(f"[NEW] 新規銘柄をバッファに追加: {code}")
                # 5日分の15分足を初期データとして取得
                hist = yf.download(str(code)+".T", period="5d", interval="15m", progress=False, threads=False)
                realtime_buffers[code] = RealtimeBuffer(code, hist, interval_mins=15)
            
            # 監視対象外のパージ（メモリリーク防止）
            for code in removed_codes:
                print(f"[DELETE] 監視対象外のバッファを削除: {code}")
                realtime_buffers.pop(code, None)

            # --- [Phase 2] 板情報によるバッファ更新 ---
            if not is_sim:
                boards = broker.get_board_data(list(current_targets))
                for code, b_info in boards.items():
                    price = b_info.get('price')
                    vol = b_info.get('volume', 0)
                    if code in realtime_buffers:
                        realtime_buffers[code].update(price, vol, server_datetime)
        except Exception as e:
            print(f"[WARNING] リアルタイムバッファ・同期エラー: {e}")

        # --- 2. 相場環境（レジーム）判定 (Phase 1) ---
        try:
            # バッファを渡すことで、日内での yf.download の重複を排除
            regime = detect_market_regime(broker=broker, buffer=realtime_buffers.get("1321"))
        except Exception as e:
            msg = f"[WARNING] 【警告】レジーム判定に失敗: {e}\n安全のためRANGE戦略に切り替え、保有監視のみ継続します。"
            print(msg)
            send_discord_notify(msg)
            regime = "RANGE"
            last_scan_time = loop_start_time

        print(f"[STAT] 現在のレジーム: 【{regime}】")
        
        if regime == "HOLIDAY":
            print("🏖️ 本日は市場休業日です。処理を終了します。")
            break

        # (旧 Buffer Update 位置 - 現在は上部に移動済み)

        # --- 2. 保有ポジション管理 ---
        # manage_positions に realtime_buffers を渡し、最新データで判定できるようにする
        portfolio, account, sell_actions, trade_logs_from_manage = manage_positions(
            portfolio, account, broker=broker, regime=regime, is_simulation=is_sim,
            realtime_buffers=realtime_buffers
        )
        
        actions_taken.extend(sell_actions)
        for log in trade_logs_from_manage:
            if hasattr(broker, 'log_trade'): broker.log_trade(log)
        if hasattr(broker, 'save_portfolio'): broker.save_portfolio(portfolio)
        if hasattr(broker, 'save_account'): broker.save_account(account)

        # --- スキャン実行の判定（Reporting Bypass解消のため should_scan フラグ制御） ---
        should_scan = True

        if regime == "BEAR":
            print("🚨 【警告】パニック・弱気相場を検知。資金保護のため新規買い付けを完全に停止します。")
            should_scan = False
        elif len(portfolio) >= MAX_POSITIONS:
            should_scan = False
        elif now_time < datetime.strptime("09:30", "%H:%M").time() and not DEBUG_MODE:
            should_scan = False
        elif now_time >= datetime.strptime("14:00", "%H:%M").time():
            should_scan = False

        
        # --- 2.5 朝の銘柄選定 (Hybrid Path) ---
        if phase == MarketPhase.PRE_MARKET and now_time >= datetime.strptime("08:30", "%H:%M").time() and not has_morning_scanned:
             should_scan = True
             is_morning_scan = True
        else:
             is_morning_scan = False

        # ▼【追加】日中スキャンの頻度制限（これを入れないと30秒ごとにyfinanceを叩いてIP BANされます）
        if should_scan and not is_morning_scan:
             if time.time() - last_scan_time < SCAN_INTERVAL_SEC:
                 should_scan = False

        # --- 3. システムによる数学的スクリーニング ---
        if should_scan:
            last_scan_time = time.time()
            print("\n=> 🔍 定期スキャン処理（銘柄探索）を開始します...")
            
            should_continue_scan = True
            try:
                df_symbols = pd.read_csv(DATA_FILE)
                if '市場・商品区分' in df_symbols.columns:
                    df_symbols = df_symbols[df_symbols['市場・商品区分'].isin(TARGET_MARKETS)]
                    print(f"  🔍 市場フィルタリング適用後: {len(df_symbols)}銘柄 (ETF/REIT等を除外)")

                invalid_tickers = load_invalid_tickers()
                if invalid_tickers:
                    df_symbols = df_symbols[~df_symbols['コード'].astype(str).isin(invalid_tickers)]
                    print(f"  🔍 無効銘柄キャッシュ適用後: {len(df_symbols)}銘柄")

                # --- インサイダー取引防止フィルタ ---
                insider_codes = load_insider_exclusion_codes()
                if insider_codes:
                    before_count = len(df_symbols)
                    df_symbols = df_symbols[~df_symbols['コード'].astype(str).isin(insider_codes)]
                    excluded_count = before_count - len(df_symbols)
                    print(f"  🚫 インサイダー除外適用後: {len(df_symbols)}銘柄 ({excluded_count}銘柄を除外)")

                held_codes = [str(p['code']) for p in portfolio]
                targets = [str(t) for t in df_symbols['コード'].tolist() if str(t) not in held_codes]
            except Exception as e:
                print(f"[WARNING] 銘柄リスト読み込みエラー: {e}")
                should_continue_scan = False

            if should_continue_scan:
                tickers = [f"{code}.T" for code in targets]
                print(f"\n--- [UP] 数学的スクリーニング ({len(tickers)}銘柄) ---")

                data_dfs = []
                chunk_size = 100 

                print(f"📡 データ取得開始 (全 {len(tickers)} 銘柄) - サーバー負荷分散のため分割取得します...")
                for i in range(0, len(tickers), chunk_size):
                    chunk = tickers[i:i + chunk_size]
                    # [Professional Audit] 規則的なアクセスによる外部検知を回避するため、0.5〜1.5秒の揺らぎ（Jitter）を付与
                    if i > 0: time.sleep(random.uniform(0.5, 1.5))
                    try:
                        # モーニングスキャンなら日足、日中なら15分足
                        dl_period = "3mo" if is_morning_scan else "5d"
                        dl_interval = "1d" if is_morning_scan else "15m"
                        # [Professional Audit] auto_adjust=False を明示し、Tickデータ（未調整価格）との整合性を 100% 保証する
                        chunk_df = yf.download(chunk, period=dl_period, interval=dl_interval, group_by='ticker', 
                                               auto_adjust=False, threads=False, progress=False)
                        if chunk_df is not None and not chunk_df.empty:
                            if isinstance(chunk_df.columns, pd.MultiIndex):
                                data_dfs.append(chunk_df)
                            elif len(chunk) == 1:
                                # 1銘柄のみの場合、結合形式(MultiIndex)に合わせてから追加する
                                chunk_df.columns = pd.MultiIndex.from_product([[chunk[0]], chunk_df.columns])
                                data_dfs.append(chunk_df)
                    except Exception as e:
                        print(f"[WARNING] An error occurred during data acquisition: {e}")
                        err_msg = str(e).lower()
                        if "possibly delisted" in err_msg or "not found" in err_msg:
                            # [AI Correction] Extract specific symbols from error message, not the entire chunk, and add to blacklist
                            # Example: Extract '1949' from "['1949.T']: possibly delisted"
                            found_codes = re.findall(r"(\d{4})\.T", err_msg, re.IGNORECASE)
                            if found_codes:
                                print(f"EXCLUDE: The following symbols may be invalid or delisted, adding to blacklist: {found_codes}")
                                invalid_tickers.update(found_codes)
                                save_invalid_tickers(invalid_tickers)
                            else:
                                # If symbol cannot be identified, either retry individual chunk or just warn
                                # Here, considering limits, only blacklist if specific symbol is explicit
                                pass
                    finally:
                        # [OK] Always sleep whether error occurs or not to prevent IP block
                        time.sleep(random.uniform(1.0, 2.5))

                if not data_dfs:
                    print("[WARNING] Data acquisition completely failed.")
                    send_discord_notify("[WARNING] [Error] Data acquisition completely failed. Possible API rate limit or network failure.")
                    should_continue_scan = False

            if should_continue_scan:
                data_df = pd.concat(data_dfs, axis=1, sort=False) if len(data_dfs) > 1 else data_dfs[0]
                try:
                    last_update = data_df.index[-1]
                    if last_update.tzinfo is None:
                        last_update = last_update.replace(tzinfo=JST)
                    
                    age = calculate_effective_age(last_update, datetime.now(JST))
                    if is_morning_scan:
                        # [Expert Refinement] For morning daily scan, judge by "date" not seconds
                        prev_biz_day = get_previous_business_day(datetime.now(JST))
                        if last_update.date() < prev_biz_day:
                            msg = f"ALERT: [Critical Delay] yfinance daily data is older than previous business day ({prev_biz_day}) (latest: {last_update.date()}). Assuming provider anomaly, stopping today's operation."
                            print(msg)
                            send_discord_notify(msg)
                            should_continue_scan = False
                    elif age > 3600: 
                        msg = f"[WARNING] [Data Delay Warning] Acquired price data is too old (effective delay: {age/60:.0f} minutes). For safety, skipping purchase."
                        print(msg)
                        send_discord_notify(msg)
                        should_continue_scan = False
                except Exception as e:
                    print(f"[WARNING] Error during freshness check (warning only): {e}")

            if should_continue_scan:
                print("[OK] Data acquisition complete. Executing evaluation algorithm...")
                # [Professional Audit] Prevent duplicate purchases: Exclude already held symbols from scan targets
                held_codes = set(str(p['code']) for p in portfolio)
                targets = [t for t in targets if str(t) not in held_codes]
                
                top_candidates = select_best_candidates(data_df, targets, df_symbols, regime, realtime_buffers=realtime_buffers)
                
                if is_morning_scan:
                    # For morning scan, register selected symbols to watchlist
                    max_watchlist = max(5, 50 - len(portfolio) - 2) 
                    watchlist = [c['code'] for c in top_candidates[:max_watchlist]]
                    has_morning_scanned = True
                    print(f"INFO: [Watchlist Confirmed] Registered {len(watchlist)} symbols for today's monitoring.")
                    
                    # --- [Phase 2] Buffer Initialization ---
                    realtime_buffers = {}
                    for code in watchlist:
                        realtime_buffers[code] = RealtimeBuffer(code, data_df)
                    for p in portfolio:
                        c = str(p['code'])
                        if c not in realtime_buffers:
                            realtime_buffers[c] = RealtimeBuffer(c, data_df)
                    # Initialize 1321 for regime determination
                    if '1321' not in realtime_buffers:
                        try:
                            df_1321 = yf.download('1321.T', period='1mo', interval='15m', progress=False)
                            realtime_buffers['1321'] = RealtimeBuffer('1321', df_1321)
                        except: pass

                    # Register to API (if Broker is Kabucom)
                    if not is_sim:
                        broker.unregister_all()
                        reg_targets = watchlist + held_codes
                        broker.register_symbols(reg_targets[:50])
                    
                    should_continue_scan = False # Morning scan doesn't buy, so terminate here
                
                elif not top_candidates:
                    print(f"INFO: No advantageous symbols found for current regime ({regime}). Skipping unnecessary trades.")
                    should_continue_scan = False

            if should_continue_scan and regime in ["BULL", "RANGE"]:
                print(f"\n--- AI Qualitative Filter Check (Target: Top 1 symbol only) ---")
                # [Hybrid Path] During intraday, only scrutinize watchlist
                # From the list of symbols extracted in the morning scan (can target up to 500),
                # narrow down the top ones again with real-time prices
                scan_targets = top_candidates[:5] if not watchlist else [c for c in top_candidates if c['code'] in watchlist][:10]
                
                # [Professional Audit] Optimization for small capital operations like 1 million yen
                # Scrutinize all candidates in order, and select one with the highest score within budget (can buy 1 unit) to execute.
                best_target = None
                shares_to_buy = 0
                buy_price = 0
                cost = 0
                final_atr = 0 # Initialize final_atr here

                for item in scan_targets:
                    # --- [Extra Phase] Gap & Special Quote Check (Expert Refinement) ---
                    if not is_sim and hasattr(broker, 'get_board_data'):
                        board = broker.get_board_data([item['code']])
                        b_info = board.get(str(item['code']))
                        if b_info:
                            c_price = b_info.get('price')
                            p_close = b_info.get('prev_close', item['price']) # Prioritize previous day's closing price from Kabucom
                            
                            # Guard against special quotes (0 yen/None) immediately after 9:00
                            if not c_price or c_price == 0:
                                print(f"WAIT: {item['code']} is currently under special quote or price undecided. Waiting for price to be set (to next loop).")
                                continue # Do not exclude, just skip this turn's judgment
                                
                            # [Professional Audit] Regime-linked dynamic gap filter
                            gap_pct = (c_price - p_close) / p_close if p_close > 0 else 0
                            gap_threshold = 0.05 if regime == "BULL" else 0.02
                            
                            should_exclude = False
                            if regime == "BULL":
                                if gap_pct < -0.02: # Even in BULL (uptrend), a downward gap of 2% or more is a sign of "weakness" and should be cautious
                                    should_exclude = True
                                # Upward gap is allowed within gap_threshold (0.05)
                            else: # RANGE/BEAR etc.
                                if abs(gap_pct) > gap_threshold: # Exclude all gaps of 2% or more
                                    should_exclude = True
                            
                            if should_exclude:
                                print(f"[WARNING] {item['code']} Gap detected ({gap_pct*100:+.1f}%, Regime:{regime}). Excluding from today's monitoring to avoid risk.")
                                if watchlist and item['code'] in watchlist:
                                    watchlist.remove(item['code'])
                                continue
                            
                            # Update current price
                            item['price'] = c_price

                    print(f"Reviewing: {item['code']} {item['name']} (Score: {item['score']:.1f})")
                    news = get_recent_news(item['code'], item['name'])
                    
                    if not news or news == "ニュースなし":
                        print("  -> No news (judged as no problem)")
                        # If no news, proceed to capital management
                    else:
                        is_safe, reason = ai_qualitative_filter(item['code'], item['name'], news)
                        if not is_safe:
                            print(f"  -> ALERT: Rejection detected: {reason} (Skipping)")
                            continue # Skip this item if AI filter rejects it
                        else:
                            print(f"  -> [OK] Passed (no negative news)")

                    # Capital management
                    p = float(item['price'])
                    a = float(item['atr'])
                    if p <= 0 or a <= 0:
                        print(f"  -> [Skip] {item['code']} - Invalid price or ATR (price={p}, atr={a})")
                        continue
                    
                    # [AI Correction] Check ATR ratio (volatility) against investment price, rather than ATR value itself
                    atr_pct = (a / p) if p > 0 else 0
                    if pd.isna(p) or pd.isna(a) or p <= 0 or a <= 0:
                        print(f"\nINFO: Detected abnormal price/ATR data, safety device activated and purchase forcibly cancelled. (price={p}, atr={a})")
                        send_discord_notify(f"[WARNING] [Safety Device Activated] Abnormal price/ATR data detected for {item['code']} {item['name']}. Purchase forcibly cancelled.")
                        last_scan_time = loop_start_time
                        should_continue_scan = False
                        break # Exit the loop if safety device activates
                    elif atr_pct > 0.10: # E.g., avoid highly volatile stocks where 15-min ATR exceeds 10% of stock price
                        msg = f"INFO: [Skipping] {item['code']} {item['name']} - Abnormal volatility detected (ATR ratio:{atr_pct*100:.1f}%). High gambling nature, skipping."
                        print(f"\n{msg}")
                        send_discord_notify(msg)
                        continue # Skip this item if volatility is too high

                    tp = normalize_tick_size(p + (a * 0.1), is_buy=True)
                    te = account['cash'] + sum([float(px.get('current_price', px['buy_price'])) * int(px['shares']) for px in portfolio])
                    ra = te * MAX_RISK_PER_TRADE
                    sm = RANGE_ATR_STOP_LOSS if regime == "RANGE" else ATR_STOP_LOSS
                    rps = a * sm
                    is_sh = int(ra // rps) if rps > 0 else 100
                    ma = max(te * MAX_ALLOCATION_PCT, MIN_ALLOCATION_AMOUNT)
                    ms_a = int(ma // tp)
                    ms_c = int((account['cash'] / 1.0001) // tp)
                    ts = (min(is_sh, ms_a, ms_c) // 100) * 100
                    
                    if ts >= 100:
                        best_target, shares_to_buy, buy_price, cost, final_atr = item, ts, tp, tp * ts, a
                        print(f"  -> [OK] Selected: {code} ({ts} shares)")
                        break
                    else:
                        print(f"  -> [Skip] {code} - Budget Short (Needs {tp*100:,.0f} / Cash {account['cash']:,.0f})")

                if not best_target:
                    print("\n[Scan] No passing candidate found.")
                    should_continue_scan = False

            if should_continue_scan and best_target:
                if not is_sim:
                    active_o = [o for o in broker.get_active_orders() if str(o.get('Symbol')) == str(best_target['code'])]
                    if [o for o in active_o if o.get('Side') == '1']:
                        print(f"🛡️ {best_target['code']} has active sell order. Skip.")
                        should_continue_scan = False

                if should_continue_scan:
                    if is_sim:
                        print(f"\n[BUY SIM] {best_target['code']} {best_target['name']} | {buy_price:,.1f} x {shares_to_buy}")
                        send_discord_notify(f"BUY SIM: {best_target['code']} {best_target['name']} | {buy_price:,.1f} x {shares_to_buy}")
                        account['cash'] -= cost
                        portfolio.append({
                            "code": best_target['code'], "name": best_target['name'],
                            "buy_time": datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S'),
                            "buy_price": round(buy_price, 1), "highest_price": round(buy_price, 1),
                            "current_price": round(buy_price, 1), "shares": shares_to_buy
                        })
                        if best_target['code'] in watchlist:
                            watchlist.remove(best_target['code'])
                        if hasattr(broker, 'save_portfolio'): broker.save_portfolio(portfolio)
                        if hasattr(broker, 'save_account'): broker.save_account(account)
                    else:
                        print(f"[OMS] Chase Order: {best_target['code']}")
                        details = broker.execute_chase_order(best_target['code'], shares_to_buy, side="2", atr=final_atr)
                        state = details.get('State') if details else None
                        actual_qty = int(details.get('Qty', 0)) if details else 0
                        if details and state in [6, 7] and actual_qty > 0:
                            exec_p = float(details.get('Price', 0)) or buy_price
                            print(f"[OK] Buy Done: {best_target['code']} {actual_qty} @ {exec_p:,.1f}")
                            send_discord_notify(f"BUY EXEC: {best_target['code']} | {exec_p:,.1f} x {actual_qty}")
                            portfolio.append({
                                "code": best_target['code'], "name": best_target['name'],
                                "buy_time": datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S'),
                                "buy_price": round(exec_p, 1), "highest_price": round(exec_p, 1),
                                "current_price": round(exec_p, 1), "shares": actual_qty
                            })
                            if best_target['code'] in watchlist:
                                watchlist.remove(best_target['code'])
                            if hasattr(broker, 'save_portfolio'): broker.save_portfolio(portfolio)
                        else:
                            print(f"[WARNING] Order rejected/failed for {best_target['code']}")

        summary_record = {
            "time": datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S'),
            "actions": actions_taken,
            "portfolio": portfolio,
            "stock_value_yen": sum([float(p.get('current_price', p['buy_price'])) * int(p['shares']) for p in portfolio]),
            "cash_yen": account['cash'],
            "total_assets_yen": account['cash'] + sum([float(p.get('current_price', p['buy_price'])) * int(p['shares']) for p in portfolio]),
            "regime": regime
        }
        if hasattr(broker, 'log_execution_summary'):
            broker.log_execution_summary(summary_record)

        if int(time.time()) % 3600 < 30:
            active_codes = set([str(p['code']) for p in portfolio] + watchlist + ['1321'])
            inactive_codes = [c for c in realtime_buffers if c not in active_codes]
            for c in inactive_codes:
                print(f"[GC] Clearing {c}")
                del realtime_buffers[c]

        elapsed = time.time() - loop_start_time
        sleep_time = max( MONITOR_INTERVAL_SEC - elapsed, 5.0)
        print(f"\nNext loop in {sleep_time:.1f}s...")
        time.sleep(sleep_time)

if __name__ == "__main__":
    main()
