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
                        print(f"[WARNING] データ取得中にエラーが発生しました: {e}")
                        err_msg = str(e).lower()
                        if "possibly delisted" in err_msg or "not found" in err_msg:
                            # [AI修正] チャンク全体ではなく、エラー文に含まれる特定の銘柄を抽出してブラックリストに入れる
                            # 例: "['1949.T']: possibly delisted" から '1949' を抽出
                            found_codes = re.findall(r"(\d{4})\.T", err_msg, re.IGNORECASE)
                            if found_codes:
                                print(f"🚫 以下の銘柄が無効または上場廃止の可能性があるためブラックリストに登録します: {found_codes}")
                                invalid_tickers.update(found_codes)
                                save_invalid_tickers(invalid_tickers)
                            else:
                                # 銘柄が特定できない場合は、念のため chunk の個別再試行を行うか、警告に留める
                                # ここではリミットを考慮し、ブラックリスト入りは特定の銘柄が明示されている時のみとする
                                pass
                    finally:
                        # [OK] エラーが起きても起きなくても必ずスリープし、IPブロックを防ぐ
                        time.sleep(random.uniform(1.0, 2.5))

                if not data_dfs:
                    print("[WARNING] データの取得に完全に失敗しました。")
                    send_discord_notify("[WARNING] 【エラー】データ取得に完全に失敗しました。APIレートリミットまたはネットワーク障害の可能性があります。")
                    should_continue_scan = False

            if should_continue_scan:
                data_df = pd.concat(data_dfs, axis=1, sort=False) if len(data_dfs) > 1 else data_dfs[0]
                try:
                    last_update = data_df.index[-1]
                    if last_update.tzinfo is None:
                        last_update = last_update.replace(tzinfo=JST)
                    
                    age = calculate_effective_age(last_update, datetime.now(JST))
                    if is_morning_scan:
                        # [Expert Refinement] 朝の日足スキャン時は秒数ではなく「日付」で判定
                        prev_biz_day = get_previous_business_day(datetime.now(JST))
                        if last_update.date() < prev_biz_day:
                            msg = f"🚨 【致命的遅延】yfinanceの日足データが前営業日({prev_biz_day})より古いです(最新: {last_update.date()})。提供元の異常と判断し、本日の運用を停止します。"
                            print(msg)
                            send_discord_notify(msg)
                            should_continue_scan = False
                    elif age > 3600: 
                        msg = f"[WARNING] 【データ遅延警告】取得された価格データが古すぎます（実効遅延: {age/60:.0f}分）。安全のため買付を見送ります。"
                        print(msg)
                        send_discord_notify(msg)
                        should_continue_scan = False
                except Exception as e:
                    print(f"[WARNING] 鮮度チェック中にエラー（警告のみ）: {e}")

            if should_continue_scan:
                print("[OK] データ取得完了。評価アルゴリズムを実行します...")
                # [Professional Audit] 二重買付防止：既に保有している銘柄をスキャンの対象から外す
                held_codes = set(str(p['code']) for p in portfolio)
                targets = [t for t in targets if str(t) not in held_codes]
                
                top_candidates = select_best_candidates(data_df, targets, df_symbols, regime, realtime_buffers=realtime_buffers)
                
                if is_morning_scan:
                    # 朝のスキャンの場合は選定銘柄をウォッチリストに登録
                    max_watchlist = max(5, 50 - len(portfolio) - 2) 
                    watchlist = [c['code'] for c in top_candidates[:max_watchlist]]
                    has_morning_scanned = True
                    print(f"📋 【ウォッチリスト確定】本日監視する {len(watchlist)} 銘柄を登録しました。")
                    
                    # --- [Phase 2] バッファの初期化 ---
                    realtime_buffers = {}
                    for code in watchlist:
                        realtime_buffers[code] = RealtimeBuffer(code, data_df)
                    for p in portfolio:
                        c = str(p['code'])
                        if c not in realtime_buffers:
                            realtime_buffers[c] = RealtimeBuffer(c, data_df)
                    # レジーム判定用の1321も初期化
                    if '1321' not in realtime_buffers:
                        try:
                            df_1321 = yf.download('1321.T', period='1mo', interval='15m', progress=False)
                            realtime_buffers['1321'] = RealtimeBuffer('1321', df_1321)
                        except: pass

                    # APIへの登録 (BrokerがKabucomなら)
                    if not is_sim:
                        broker.unregister_all()
                        reg_targets = watchlist + held_codes
                        broker.register_symbols(reg_targets[:50])
                    
                    should_continue_scan = False # 朝は買うわけではないのでここで終了
                
                elif not top_candidates:
                    print(f"💡 現在のレジーム({regime})で優位性のある銘柄は見つかりませんでした。無駄な売買を見送ります。")
                    should_continue_scan = False

            if should_continue_scan:
                print(f"\n--- 🤖 AI定性フィルターチェック (対象: 最上位1銘柄のみ) ---")
                # [Hybrid Path] 日中はウォッチリストのみを精査対象にする
                # 朝のスキャンで抽出された銘柄リスト（上位500件程度を対象にしても良い）から、
                # リアルタイム価格で再度上位を絞り込む
                scan_targets = top_candidates[:5] if not watchlist else [c for c in top_candidates if c['code'] in watchlist][:10]
                
                best_target = None
                
                for item in scan_targets:
                    # --- [Extra Phase] Gap & Special Quote Check (Expert Refinement) ---
                    if not is_sim and hasattr(broker, 'get_board_data'):
                        board = broker.get_board_data([item['code']])
                        b_info = board.get(str(item['code']))
                        if b_info:
                            c_price = b_info.get('price')
                            p_close = b_info.get('prev_close', item['price']) # カブコム由来の前日終値を優先
                            
                            # 9:00直後の特別気配（0円/None）をガード
                            if not c_price or c_price == 0:
                                print(f"⏳ {item['code']} は現在特別気配中または価格未決定です。値がつくまで待機（次ループへ）します。")
                                continue # 除外はせず、単にこのターンの判定を飛ばす
                                
                            # [Professional Audit] レジーム連動型・動的ギャップフィルター
                            gap_pct = (c_price - p_close) / p_close if p_close > 0 else 0
                            gap_threshold = 0.05 if regime == "BULL" else 0.02
                            is_gap_up = gap_pct > gap_threshold
                            is_gap_down = gap_pct < -gap_threshold
                            
                            should_exclude = False
                            if regime == "BULL":
                                if gap_pct < -0.02: # BULL(上昇相場)でも下窓2%以上は「腰折れ」の兆候として警戒
                                    should_exclude = True
                                # 上窓は gap_threshold (0.05) 以内なら許容
                            else: # RANGE/BEAR等
                                if abs(gap_pct) > gap_threshold: # 2%以上の窓開けは一律除外
                                    should_exclude = True
                            
                            if should_exclude:
                                print(f"[WARNING] {item['code']} 窓開け検知 ({gap_pct*100:+.1f}%, Regime:{regime})。リスク回避のため本日の監視から除外します。")
                                if watchlist and item['code'] in watchlist:
                                    watchlist.remove(item['code'])
                                continue
                            
                            # 現在値を最新化
                            item['price'] = c_price

                    print(f"審査中: {item['code']} {item['name']} (スコア: {item['score']:.1f})")
                    news = get_recent_news(item['code'], item['name'])
                    
                    if not news or news == "ニュースなし":
                        print("  -> ニュースなし(問題なしと判断)")
                        best_target = item
                        break
                        
                    is_safe, reason = ai_qualitative_filter(item['code'], item['name'], news)
                    if is_safe:
                        print(f"  -> [OK] 合格 (悪材料なし)")
                        best_target = item
                        break
                    else:
                        print(f"  -> 🚨 リジェクト検知: {reason} (見送り)")

                if best_target:
                    raw_price = float(best_target['price'])
                    atr = float(best_target['atr'])
                    # [AI修正] ATRの値そのものよりも、投資価格に対するATR比率（ボラティリティ）を重視してチェック
                    atr_pct = (atr / raw_price) if raw_price > 0 else 0
                    if pd.isna(raw_price) or pd.isna(atr) or raw_price <= 0 or atr <= 0:
                        print(f"\n💡 異常な価格/ATRデータを検知したため、安全装置が作動し買付を強制キャンセルしました。(price={raw_price}, atr={atr})")
                        send_discord_notify(f"[WARNING] 【安全装置作動】{best_target['code']} {best_target['name']} の価格/ATRデータに異常を検知。買付を強制キャンセルしました。")
                        last_scan_time = loop_start_time
                        should_continue_scan = False
                    elif atr_pct > 0.10: # 例: 15分足ベースのATRが株価の10%を超えるような超激動銘柄は避ける
                        msg = f"💡 【見送り】{best_target['code']} {best_target['name']} — 異常なボラティリティ検知(ATR比率:{atr_pct*100:.1f}%)。ギャンブル性が高いため見送ります。"
                        print(f"\n{msg}")
                        send_discord_notify(msg)
                        should_continue_scan = False
                else:
                    print("\n💡 AI定性フィルターにより、全ての候補がリジェクトされました（または対象なし）。安全のため見送ります。")
                    send_discord_notify("💡 【見送り】AI定性フィルターにより全候補がリジェクトされました。安全のため見送ります。")
                    should_continue_scan = False

            if should_continue_scan and best_target:
                # ATRベースのスリッページを加味し、呼値（Tick Size）に合わせて正規化（不利な方向に丸めて約定優先）
                buy_price = normalize_tick_size(raw_price + (atr * 0.1), is_buy=True)
                
                
                total_equity = account['cash'] + sum([float(p.get('current_price', p['buy_price'])) * int(p['shares']) for p in portfolio])
                risk_amount = total_equity * MAX_RISK_PER_TRADE
                
                current_sl_mult = RANGE_ATR_STOP_LOSS if regime == "RANGE" else ATR_STOP_LOSS
                risk_per_share = atr * current_sl_mult
                
                ideal_shares = int(risk_amount // risk_per_share) if risk_per_share > 0 else 100
                
                max_investment_amount = max(total_equity * MAX_ALLOCATION_PCT, MIN_ALLOCATION_AMOUNT)
                max_shares_by_allocation = int(max_investment_amount // buy_price)

                # 手数料完全無料前提だが、float演算誤差による資金不足判定を防ぐ極小のバッファ
                COMMISSION_BUFFER = 1.0001  


                max_shares_by_cash = int((account['cash'] / COMMISSION_BUFFER) // buy_price)
                raw_shares = min(ideal_shares, max_shares_by_allocation, max_shares_by_cash)
                
                shares_to_buy = (raw_shares // 100) * 100
                cost = buy_price * shares_to_buy
                
                # [Professional Audit] 同一銘柄の「反対注文」衝突回避 (Wash Trade防止)
                # 買付前に、同じ銘柄の売り注文が出ていないか確認する
                if not is_sim:
                    active_orders_for_code = [o for o in broker.get_active_orders() if str(o.get('Symbol')) == str(best_target['code'])]
                    sell_orders = [o for o in active_orders_for_code if o.get('Side') == '1'] # 1:売
                    if sell_orders:
                        print(f"🛡️ {best_target['code']} に有効な売り注文を検出しました。仮装売買防止のため、このターンの買い付けを見送ります。")
                        continue 
                
                if shares_to_buy >= 100 and cost * COMMISSION_BUFFER <= account['cash']:
                    if is_sim:
                        print(f"\n🏆 【シグナル点灯】{regime}戦略に基づく最適銘柄: {best_target['code']} {best_target['name']}")
                        print(f"[BUY] 買付価格: {buy_price:,.1f}円 | 数量: {shares_to_buy}株 | 代金: {cost:,.0f}円")
                        notify_msg = f"🏆 **【新規買付(SIM)】{best_target['code']} {best_target['name']}**\n戦略: {regime} | 価格: {buy_price:,.1f}円 × {shares_to_buy}株 (代金: {cost:,.0f}円)\n[STAT] AI判定: 問題なし"
                        send_discord_notify(notify_msg)
                        actions_taken.append(f"買付: {best_target['code']} {best_target['name']} {shares_to_buy}株 ({cost:,.0f}円)")
                        
                        # [OK] 手数料ゼロ化に伴い、代金分のみを現金から引く
                        account['cash'] -= cost
                        # [Professional Audit] 資金管理の原子性（二重使用防止）のため、即座に保存
                        if hasattr(broker, 'save_account'): broker.save_account(account)
                        
                        portfolio.append({
                            "code": best_target['code'], "name": best_target['name'],
                            "buy_time": datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S'),
                            "buy_price": round(buy_price, 1), "highest_price": round(buy_price, 1),
                            "current_price": round(buy_price, 1), "shares": shares_to_buy
                        })
                        # [Professional Audit] 買付後はウォッチリストから除外して監視を卒業させる（永続化含む）
                        if best_target['code'] in watchlist:
                            watchlist.remove(best_target['code'])
                            save_watchlist(watchlist)
                        if hasattr(broker, 'save_portfolio'): broker.save_portfolio(portfolio)
                        if hasattr(broker, 'save_account'): broker.save_account(account)
                    else:
                        print(f"🛡️ 【OMS発動】追従型指値注文（Chase Order）で買い付けを開始します")
                        # 買付時は `shares_to_buy` と `atr` を渡して追従発注
                        details = broker.execute_chase_order(best_target['code'], shares_to_buy, side="2", atr=atr)
                        
                        # [Professional Audit Round 3] 部分約定 (State=7) を受容し、データの欠落を防ぐ
                        state = details.get('State') if details else None
                        actual_qty = int(details.get('Qty', 0)) if details else 0
                        
                        if details and state in [6, 7] and actual_qty > 0:
                            exec_price = float(details.get('Price', 0))
                            if exec_price == 0:
                                exec_price = buy_price
                                exec_details = details.get('Details', [])
                                if exec_details:
                                    total_val = sum(float(d.get('Price', 0)) * float(d.get('Qty', 0)) for d in exec_details)
                                    total_qty = sum(float(d.get('Qty', 0)) for d in exec_details)
                                    if total_qty > 0:
                                        exec_price = total_val / total_qty
                            
                            exec_cost = exec_price * actual_qty
                            
                            print(f"[OK] 注文完了（追従済）: {best_target['code']} {actual_qty}株 @ {exec_price:,.1f}円")
                            notify_msg = f"🏆 **【新規買付・約定】{best_target['code']} {best_target['name']}**\n戦略: {regime} | 約定価格: {exec_price:,.1f}円 × {actual_qty}株\n[STAT] OMS: 追従完了"
                            send_discord_notify(notify_msg)
                            actions_taken.append(f"買付: {best_target['code']} {best_target['name']} {actual_qty}株 ({exec_cost:,.0f}円)")
                            portfolio.append({
                                "code": best_target['code'], "name": best_target['name'],
                                "buy_time": datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S'),
                                "buy_price": round(exec_price, 1), "highest_price": round(exec_price, 1),
                                "current_price": round(exec_price, 1), "shares": actual_qty
                            })
                            # [Professional Audit] 買付後はウォッチリストから除外して監視を卒業させる（永続化含む）
                            if best_target['code'] in watchlist:
                                watchlist.remove(best_target['code'])
                                save_watchlist(watchlist)
                            if hasattr(broker, 'save_portfolio'): broker.save_portfolio(portfolio)
                        else:
                            msg = f"[WARNING] 【注文未約定/エラー】{best_target['code']} の追従発注が完了しませんでした。次サイクルで再試行します。"
                            print(msg)
                            send_discord_notify(msg)
                else:
                    if shares_to_buy < 100:
                        # [AI修正] 指摘の通り、「ATR 18.9」などが異常なのではなく、100株単位の制約とリスク許容度のミスマッチであることを明示
                        target_risk_yen = risk_amount
                        required_risk_for_100_shares = (atr * current_sl_mult) * 100
                        msg = f"💡 【見送り】{best_target['code']} {best_target['name']} — 資金管理上の制限。1単元(100株)のリスク量({required_risk_for_100_shares:,.0f}円)が、許容上限({target_risk_yen:,.0f}円/トレード)を超えています。"
                        print(f"\n{msg}")
                        send_discord_notify(msg)
                    else:
                        msg = f"💡 【見送り】{best_target['code']} {best_target['name']} — 現金不足 ({cost:,.0f}円必要 / 残高{account['cash']:,.0f}円)。"
                        print(f"\n{msg}")
                        send_discord_notify(msg)

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

        # --- [Phase 11-13] キャッシュ清掃・GC・リソース保護 ---
        # 1時間に1回、非アクティブなバッファを解放する (GC)
        if int(time.time()) % 3600 < 30:
            active_codes = set([str(p['code']) for p in portfolio] + watchlist + ['1321'])
            inactive_codes = [c for c in realtime_buffers if c not in active_codes]
            for c in inactive_codes:
                print(f"🧹 [GC] 非アクティブなバッファ {c} をメモリ解放します。")
                del realtime_buffers[c]

        elapsed = time.time() - loop_start_time
        sleep_time = max(5.0, MONITOR_INTERVAL_SEC - elapsed)
        print(f"\n💤 次の監視({MONITOR_INTERVAL_SEC}秒周期)まで待機します...")
        time.sleep(sleep_time)

if __name__ == "__main__":
    main()
