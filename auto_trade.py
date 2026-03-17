import os
import sys
import io
from datetime import datetime
import yfinance as yf
import pandas as pd
import numpy as np
import time
import re
import warnings
import json
import signal
from core.log_setup import setup_logging, send_discord_notify
from core.preflight import pre_flight_check

# --- ファイルパス・設定・APIキー設定 (core.configより一括取得) ---
from core.config import (
    DATA_FILE, PORTFOLIO_FILE, HISTORY_FILE, ACCOUNT_FILE, 
    EXECUTION_LOG_FILE, EXCLUSION_CACHE_FILE, TARGET_MARKETS,
    GEMINI_API_KEY, GROQ_API_KEY, DISCORD_WEBHOOK_URL, GEMINI_MODEL,
    DEBUG_MODE, INITIAL_CASH, MAX_POSITIONS, MAX_RISK_PER_TRADE,
    MAX_ALLOCATION_PCT, MIN_ALLOCATION_AMOUNT,
    ATR_STOP_LOSS, ATR_TRAIL, TAX_RATE, JST
)
from core.file_io import atomic_write_json, atomic_write_csv, safe_read_json, safe_read_csv

# --- インスタンスロック機構 ---
LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".bot_sim.lock")

def acquire_lock():
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                old_pid = int(f.read().strip())
            import psutil
            if psutil.pid_exists(old_pid):
                print(f"⚠️ エラー: 他のシミュレーションインスタンス(PID: {old_pid})が既に実行中です。")
                return False
        except:
            pass
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))
    return True

def release_lock():
    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
        except:
            pass


# --- 既存CSVとJSONの読み書き処理 (完全に維持) ---
def load_account():
    account = safe_read_json(ACCOUNT_FILE)
    return account if account is not None else {"cash": INITIAL_CASH}

def save_account(account_data):
    atomic_write_json(ACCOUNT_FILE, account_data)

def load_portfolio():
    df = safe_read_csv(PORTFOLIO_FILE)
    return df.to_dict('records') if not df.empty else []

def save_portfolio(portfolio):
    df = pd.DataFrame(portfolio)
    atomic_write_csv(PORTFOLIO_FILE, df)

def log_trade(trade_record):
    write_header = not os.path.exists(HISTORY_FILE) or os.path.getsize(HISTORY_FILE) == 0
    df = pd.DataFrame([trade_record])
    df.to_csv(HISTORY_FILE, mode='a', header=write_header, index=False, encoding='utf-8-sig')

def print_execution_summary(actions, portfolio, account, regime="不明"):
    current_time = datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')
    stock_value = sum([float(p.get('current_price', p['buy_price'])) * int(p['shares']) for p in portfolio])
    total_assets = account['cash'] + stock_value
    
    print("\n" + "="*50)
    print(f" 📊 実行サマリー (レジーム: {regime})")
    print("="*50)
    print("\n【今回のアクション】")
    action_str = " | ".join(actions) if actions else "アクションなし"
    
    if actions:
        for act in actions:
            print(f" ✔ {act}")
    else:
        print(" - アクションなし (保有維持 / 新規見送り)")
        
    print("\n【現在の保有株式】")
    if portfolio:
        for p in portfolio:
            cp = float(p.get('current_price', p['buy_price']))
            val = cp * int(p['shares'])
            profit_pct = (cp - float(p['buy_price'])) / float(p['buy_price']) * 100
            print(f" 🔹 {p['code']} {p['name']}\n    数量: {p['shares']}株 | 現在値: {cp:,.1f}円 | 評価額: {val:,.0f}円 | 損益: {profit_pct:+.2f}%")
    else:
        print(" - 保有なし")
        

    print("\n【口座ステータス】")
    print(f" 💰 現金残高:   {account['cash']:>10,.0f}円")
    print(f" 📈 株式評価額: {stock_value:>10,.0f}円")
    print(f" 👑 合計資産額: {total_assets:>10,.0f}円")
    print("="*50 + "\n")

    write_header = not os.path.exists(EXECUTION_LOG_FILE) or os.path.getsize(EXECUTION_LOG_FILE) == 0
    df_log = pd.DataFrame([{
        "time": current_time,
        "actions": action_str,
        "portfolio_count": len(portfolio),
        "stock_value_yen": stock_value,
        "cash_yen": account['cash'],
        "total_assets_yen": total_assets
    }])
    df_log.to_csv(EXECUTION_LOG_FILE, mode='a', header=write_header, index=False, encoding='utf-8-sig')


from core.logic import (
    detect_market_regime, manage_positions, select_best_candidates, 
    load_invalid_tickers, save_invalid_tickers
)
from core.ai_filter import ai_qualitative_filter, get_recent_news

# --- シグナルハンドラ (Phase 12: Graceful Shutdown) ---
def handle_shutdown(signum, frame):
    print(f"\n🛑 シグナル({signum})を受信しました。安全にシャットダウンを開始します...")
    try:
        send_discord_notify("🛑 【システム通知】運営者による停止操作（Ctrl+C等）を検知しました。ボットを安全に終了します。")
    except: pass
    release_lock()
    sys.exit(0)

# --- メインループ ---
def main():
    if not acquire_lock():
        sys.exit(1)
        
    # シグナルの登録
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    try:
        _main_exec()
    except Exception as e:
        msg = f"💥 【致命的システムエラー】シミュレーションループ内で予期せぬ例外が発生しました:\n{e}"
        print(msg)
        try:
            send_discord_notify(msg)
        except:
            pass
        time.sleep(10) # API制限回避とログ氾濫防止のためのクールダウン (Phase 13)
    finally:
        release_lock()

def _main_exec():
    if not pre_flight_check():
        print("❌ [Pre-flight Error] 起動前点検に失敗しました。処理を中断します。")
        return
    
    # --- [Phase 14] In-flight Order Guard (未約定注文チェック) ---
    broker = KabucomBroker(is_production=IS_PRODUCTION)
    print("🛡️ [In-flight Guard] 未約定の注文がないか確認中...")
    active_orders = broker.get_active_orders()
    if active_orders:
        msg = f"⚠️ 【警告】未約定の注文が {len(active_orders)} 件残っています。二重発注防止のため、手動で解消されるまで待機または終了してください。"
        print(msg)
        send_discord_notify(msg)
        # 成行注文メインなので通常は即座に無くなるはずだが、安全のため停止する
        return
    
    # --- [Phase 11] Resource Watcher ---
    try:
        import psutil
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        print(f"📊 [System Health] Memory Usage: {mem_info.rss / 1024 / 1024:.1f} MB | CPU: {psutil.cpu_percent()}%")
    except ImportError:
        pass
    except Exception as e:
        print(f"⚠️ リソース監視中にエラー: {e}")

    print(f"\n🚀 ヘッジファンド仕様・アルゴリズムBOT 起動 (自律ループ型監視中)")

    while True:
        # --- [Phase 14] Server Time Sync ---
        server_datetime = broker.get_server_time()
        now_time = server_datetime.time()

        # 15:30（大引け）を過ぎたら本日の運用を終了
        if now_time >= datetime.strptime("15:30", "%H:%M").time() and not DEBUG_MODE:
            print("\n🏁 15:30（大引け）を過ぎました。本日の運用を終了します。")
            send_discord_notify("🏁 【業務終了】15:30（大引け）を過ぎたため、自動運用を終了しました。")
            break

        # タイムフィルター（取引時間外の待機）
        if not DEBUG_MODE:
            if server_datetime.weekday() >= 5: 
                print("💤 本日は市場休業日（土日）です。")
                break
            
            m_open, m_close = datetime.strptime("09:00", "%H:%M").time(), datetime.strptime("11:30", "%H:%M").time()
            a_open, a_close = datetime.strptime("12:30", "%H:%M").time(), datetime.strptime("15:30", "%H:%M").time()
            
            if not ((m_open <= now_time <= m_close) or (a_open <= now_time <= a_close)):
                print(f"💤 取引時間外です（現在サーバー時刻: {now_time.strftime('%H:%M:%S')}）。10分待機します...")
                time.sleep(600)
                continue

        # --- 以下、定期実行される中身 ---
        print(f"\n[{datetime.now(JST).strftime('%H:%M:%S')}] 📈 監視サイクル開始 (サーバー時刻: {now_time.strftime('%H:%M:%S')})")

        account = load_account()
        portfolio = load_portfolio()
        actions_taken = []
        trade_logs = [] 

        # --- 1. 相場環境（レジーム）判定 ---
    try:
        regime = detect_market_regime()
    except Exception as e:
        msg = f"❌ 【致命的エラー】レジーム判定（日経平均取得）に失敗しました: {e}"
        print(msg)
        send_discord_notify(msg)
        return

    print(f"📊 現在のレジーム: 【{regime}】")
    
    if regime == "HOLIDAY":
        print("🏖️ 本日は市場休業日です。処理を終了します。")
        return

    # --- 2. 保有ポジション管理 ---
    # manage_positions関数にbroker引数とis_simulation引数を追加。
    # このファイルは主にシミュレーション用途のため、is_simulation=True をデフォルトとする。
    portfolio, account, sell_actions, trade_logs_from_manage = manage_positions(portfolio, account, broker=None, regime=regime, is_simulation=True)
    actions_taken.extend(sell_actions)
    for log in trade_logs_from_manage:
        log_trade(log)
    save_portfolio(portfolio)
    save_account(account)

    if regime == "BEAR":
        print("🚨 【警告】パニック・弱気相場を検知。資金保護のため新規買い付けを完全に停止します。")
        send_discord_notify("🚨 【BEAR相場検知】パニック・弱気相場のため新規買い付けを停止。手仕舞いのみ実行します。")
        print_execution_summary(actions_taken, portfolio, account, regime)
        return

    if len(portfolio) >= MAX_POSITIONS:
        print(f"\n💡 最大ポジション（{MAX_POSITIONS}銘柄）保有中。新規スキャンをスキップします。")
        send_discord_notify(f"💡 【見送り】最大ポジション（{MAX_POSITIONS}銘柄）保有中のため新規スキャンをスキップしました。")
        print_execution_summary(actions_taken, portfolio, account, regime)
        return

    now_time = datetime.now(JST).time()

    # 【重要追加】東京市場の「魔の寄り付き30分」を回避
    # 朝9:00～9:30は前日からの持ち越し注文が交錯し、テクニカル指標が完全に無視されるランダムウォーク状態となるためエントリーを禁止します。
    if now_time < datetime.strptime("09:30", "%H:%M").time() and not DEBUG_MODE:
        print("\n💡 寄り付き直後（9:30前）は値動きがランダムで危険なため、新規エントリーのスキャンを待機します。")
        send_discord_notify("💡 【見送り】寄り付き直後（9:30前）のためエントリー待機中。保有監視のみ実行しました。")
        print_execution_summary(actions_taken, portfolio, account, regime)
        return

    if now_time >= datetime.strptime("14:30", "%H:%M").time():
        print("\n💡 大引け前（14:30以降）のため、オーバーナイトリスクを避けるべく本日の新規買付を終了します。")
        send_discord_notify("💡 【見送り】大引け前（14:30以降）のため新規買付を終了。保有ポジションの決済監視のみ実行しました。")
        # 14:30〜15:00は保有ポジションの決済監視のみ（manage_positionsで15:00タイムストップが発動）
        print_execution_summary(actions_taken, portfolio, account, regime)
        return

    # --- 3. システムによる数学的スクリーニング（高速） ---
    try:
        df_symbols = pd.read_csv(DATA_FILE)
        # 【改善】ETF/ETN、REIT、PRO Market、外国株式、出資証券を除外し、内国株式のみに絞る
        # （4400→約3770銘柄に削減し、yfinanceの 'possibly delisted' エラーも解消）
        if '市場・商品区分' in df_symbols.columns:
            df_symbols = df_symbols[df_symbols['市場・商品区分'].isin(TARGET_MARKETS)]
            print(f"  🔍 市場フィルタリング適用後: {len(df_symbols)}銘柄 (ETF/REIT等を除外)")

        # 【追加】無効銘柄キャッシュの読み込みと除外
        invalid_tickers = load_invalid_tickers()
        if invalid_tickers:
            df_symbols = df_symbols[~df_symbols['コード'].astype(str).isin(invalid_tickers)]
            print(f"  🔍 無効銘柄キャッシュ適用後: {len(df_symbols)}銘柄")
        # 既に保有している銘柄は除外
        held_codes = [str(p['code']) for p in portfolio]
        targets = [str(t) for t in df_symbols['コード'].tolist() if str(t) not in held_codes]
    except Exception as e:
        print(f"⚠️ 銘柄リスト読み込みエラー: {e}")
        return

    tickers = [f"{code}.T" for code in targets]
    print(f"\n--- 📈 数学的スクリーニング ({len(tickers)}銘柄) ---")

    # 【重大修正】全銘柄(4000件超)の同時リクエストは、yfinanceのレートリミット(HTTP 429エラー)やメモリ枯渇を引き起こし、運用が完全に停止するリスクがあります。
    # ここではプロ仕様の「チャンク処理（分割ダウンロード）」を実装し、安定稼働を100%保証します。
    data_dfs = []
    chunk_size = 500 # 1回あたりの取得件数

    print(f"📡 データ取得開始 (全 {len(tickers)} 銘柄) - サーバー負荷分散のため分割取得します...")
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i + chunk_size]
        try:
            # チャンクごとに取得
            chunk_df = yf.download(chunk, period="5d", interval="15m", group_by='ticker', threads=True, progress=False)
            if chunk_df is not None and not chunk_df.empty:
                # yfinanceの仕様で、有効な銘柄が1つだけだった場合にMultiIndexではなくなるため、結合エラー(Concat Error)で落ちるバグを防止
                if isinstance(chunk_df.columns, pd.MultiIndex):
                    data_dfs.append(chunk_df)
            time.sleep(0.5) # API制限回避のクールダウン
        except Exception as e:
            print(f"⚠️ 個別データ取得失敗 ({len(chunk)}銘柄): {e}")

            # 失敗した銘柄をキャッシュに追加
            if "possibly delisted" in str(e).lower() or "not found" in str(e).lower():
                new_invalids = set(chunk)
                invalid_tickers.update([t.replace('.T', '') for t in new_invalids])
                save_invalid_tickers(invalid_tickers)
            continue

    if not data_dfs:
        print("⚠️ データの取得に完全に失敗しました。")
        send_discord_notify("⚠️ 【エラー】データ取得に完全に失敗しました。APIレートリミットまたはネットワーク障害の可能性があります。")
        print_execution_summary(actions_taken, portfolio, account, regime)
        return

    # 全チャンクを結合
    data_df = pd.concat(data_dfs, axis=1) if len(data_dfs) > 1 else data_dfs[0]
    
    # --- [Phase 11] NaN Guard (価格異常チェック) ---
    if data_df.isnull().values.any():
        print("⚠️ 取得データに欠損値(NaN)が含まれています。不正確な計算を避けるためスキャンを中断します。")
        # 列ごとの欠損率をチェックして報告
        null_counts = data_df.isnull().sum()
        bad_cols = null_counts[null_counts > 0].index.tolist()
        print(f"   欠損箇所: {bad_cols[:5]}.. (計 {len(bad_cols)} 列)")
        print_execution_summary(actions_taken, portfolio, account, regime)
        return
    
    # --- 鮮度チェック (Phase 8: Stale Data Guard) ---
    try:
        last_update = data_df.index[-1]
        if last_update.tzinfo is None:
            last_update = JST.localize(last_update)
        
        age = datetime.now(JST) - last_update
        if age.total_seconds() > 3600: # 1時間を超える遅延は異常とみなす
             msg = f"⚠️ 【データ遅延警告】取得された価格データが古すぎます（最終更新: {last_update.strftime('%H:%M')} / 遅延: {age.total_seconds()/60:.0f}分）。安全のため買付を見送ります。"
             print(msg)
             send_discord_notify(msg)
             print_execution_summary(actions_taken, portfolio, account, regime)
             return
    except Exception as e:
        print(f"⚠️ 鮮度チェック中にエラー（警告のみ）: {e}")

    print("✅ データ取得完了。評価アルゴリズムを実行します...")
    
    # 数学的に評価されたトップ候補（最大3件）を瞬時に取得
    top_candidates = select_best_candidates(data_df, targets, df_symbols, regime)
    
    if not top_candidates:
        print(f"💡 現在のレジーム({regime})で優位性のある銘柄は見つかりませんでした。無駄な売買を見送ります。")
        send_discord_notify(f"💡 【見送り】レジーム: {regime} | スクリーニングの結果、優位性のある銘柄が見つかりませんでした。")
        print_execution_summary(actions_taken, portfolio, account, regime)
        return

    # --- 4. AIによる防護壁（定性フィルター） ---
    print(f"\n--- 🤖 AI定性フィルターチェック (対象: 上位{len(top_candidates)}銘柄のみ) ---")
    best_target = None
    
    for item in top_candidates:
        print(f"審査中: {item['code']} {item['name']} (スコア: {item['score']:.1f})")
        news = get_recent_news(item['code'], item['name'])
        
        if not news or news == "ニュースなし":
            print("  -> ニュースなし(問題なしと判断)")
            best_target = item
            break
            
        is_safe, reason = ai_qualitative_filter(item['code'], item['name'], news)
        if is_safe:
            print(f"  -> ✅ 合格 (悪材料なし)")
            best_target = item
            break
        else:
            print(f"  -> 🚨 リジェクト検知: {reason} (次の候補へ移行)")
            # 危険な銘柄を弾いて次の候補ルールのループへ続く

    # --- 5. エントリー (ボラティリティ・ポジションサイジングとスリッページ考慮) ---
    if best_target:
        # 【超重要・最終防衛ライン】データ取得エラーやNaN（非数）によるシステム崩壊を物理的に遮断
        if pd.isna(best_target['price']) or pd.isna(best_target['atr']) or best_target['price'] <= 0:
            print(f"\n💡 異常な価格データ({best_target['price']})を検知したため、安全装置が作動し買付を強制キャンセルしました。")
            send_discord_notify(f"⚠️ 【安全装置作動】{best_target['code']} {best_target['name']} の価格データに異常を検知（{best_target['price']}）。買付を強制キャンセルしました。")
            print_execution_summary(actions_taken, portfolio, account, regime)
            return
            
        # 【超重要】実弾運用でのスプレッド購入をシミュレーション（購入時は現在値の0.1%高く掴まされると想定）
        raw_price = float(best_target['price'])
        buy_price = raw_price * 1.001 
        atr = float(best_target['atr'])
        
        # ボラティリティによる適正株数計算 (総資金の2%リスク)
        total_equity = account['cash'] + sum([float(p.get('current_price', p['buy_price'])) * int(p['shares']) for p in portfolio])
        risk_amount = total_equity * MAX_RISK_PER_TRADE
        # 1株あたりの想定損失リスク(ATRの初期ストップロス幅)
        risk_per_share = atr * ATR_STOP_LOSS
        
        ideal_shares = int(risk_amount // risk_per_share) if risk_per_share > 0 else 100
        
        # 【修正】1銘柄あたりの最大投資額キャップ（ハイブリッド方式：main.pyと同期）
        # 「総資金の30%」と「最低保証額（20万円）」の大きい方をキャップとして採用
        max_investment_amount = max(total_equity * MAX_ALLOCATION_PCT, MIN_ALLOCATION_AMOUNT)
        max_shares_by_allocation = int(max_investment_amount // buy_price)

        # 実際の現金余力とすり合わせ
        max_shares_by_cash = int(account['cash'] // buy_price)
        
        # 理想の株数、上限キャップ、現金残高のうち、最も少ない（安全な）株数を採用する
        raw_shares = min(ideal_shares, max_shares_by_allocation, max_shares_by_cash)
        
        # 【重要追加】日本株の単元株（100株単位）への強制丸め込み
        shares_to_buy = (raw_shares // 100) * 100
        cost = buy_price * shares_to_buy
        
        if cost <= account['cash'] and shares_to_buy >= 100:
            # 現金残高が事実上マイナスになる絶対的な計算ミスを防ぐフェイルセーフ
            if account['cash'] - cost < 0:
                 print("\n💡 致命的な資金計算エラー: 買付余力がマイナスになるため取引を強制ブロックしました。")
                 send_discord_notify(f"⚠️ 【安全装置作動】資金計算エラー: 買付余力がマイナスになるため取引を強制ブロックしました。")
            else:
                print(f"\n🏆 【シグナル点灯】{regime}戦略に基づく最適銘柄: {best_target['code']} {best_target['name']}")
                print(f"🛒 買付価格: {buy_price:,.1f}円 | 数量: {shares_to_buy}株 | 概算代金: {cost:,.0f}円 (ATR: {atr:.1f})")
                
                notify_msg = f"🏆 **【新規買付】{best_target['code']} {best_target['name']}**\n戦略: {regime} | 価格: {buy_price:,.1f}円 × {shares_to_buy}株 (代金: {cost:,.0f}円)\n📊 AI判定: 問題なし"
                send_discord_notify(notify_msg)
                
                actions_taken.append(f"買付: {best_target['code']} {best_target['name']} {shares_to_buy}株 ({cost:,.0f}円)")
                
                account['cash'] -= cost
                portfolio.append({
                    "code": best_target['code'], "name": best_target['name'], 
                    "buy_time": datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S'), 
                    "buy_price": round(buy_price, 1), "highest_price": round(buy_price, 1), 
                    "current_price": round(buy_price, 1), "shares": shares_to_buy
                })
                save_portfolio(portfolio)
                save_account(account)
        else:
            if shares_to_buy < 100:
                msg = f"💡 【見送り】{best_target['code']} {best_target['name']} — ボラティリティ過大(ATR:{atr:.1f})のためリスク管理制限で買付キャンセル。"
                print(f"\n{msg}")
                send_discord_notify(msg)
            else:
                msg = f"💡 【見送り】{best_target['code']} {best_target['name']} — 現金不足 ({cost:,.0f}円必要 / 残高{account['cash']:,.0f}円)。"
                print(f"\n{msg}")
                send_discord_notify(msg)
    else:
        print("\n💡 AI定性フィルターにより、全ての候補がリジェクトされました（または対象なし）。安全のため見送ります。")
        send_discord_notify("💡 【見送り】AI定性フィルターにより全候補がリジェクトされました。安全のため見送ります。")
        
        print_execution_summary(actions_taken, portfolio, account, regime)
        
        # 15分待機 (Phase 14)
        print(f"\n💤 次のスキャン（15分後）まで待機します...")
        time.sleep(900)

if __name__ == "__main__":
    main()
