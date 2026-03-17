import pandas as pd
import time
import yfinance as yf
from datetime import datetime

from core.config import DEBUG_MODE, MAX_POSITIONS, DATA_FILE, MAX_RISK_PER_TRADE, ATR_STOP_LOSS, TRADE_MODE, MAX_ALLOCATION_PCT, MIN_ALLOCATION_AMOUNT
from core.log_setup import setup_logging, send_discord_notify
from core.sim_broker import SimulationBroker
from core.kabucom_broker import KabucomBroker
from core.logic import detect_market_regime, manage_positions, select_best_candidates
from core.ai_filter import ai_qualitative_filter, get_recent_news

def main():
    setup_logging()
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🚀 ヘッジファンド仕様・アルゴリズムBOT 起動 (Brokerパターン稼働中)")
    
    # --- 0. タイムフィルター ---
    if not DEBUG_MODE:
        now = datetime.now()
        if now.weekday() >= 5: return
        
        c_time = now.time()
        m_open, m_close = datetime.strptime("09:00", "%H:%M").time(), datetime.strptime("11:30", "%H:%M").time()
        a_open, a_close = datetime.strptime("12:30", "%H:%M").time(), datetime.strptime("15:30", "%H:%M").time()
        
        if not ((m_open <= c_time <= m_close) or (a_open <= c_time <= a_close)):
            return

    # --- 1. Brokerの初期化と口座情報取得 ---
    if TRADE_MODE == "KABUCOM_LIVE":
        print("⚡ 【本番モード】auカブコム証券 本番API (Port 8080) に接続します")
        broker = KabucomBroker(is_production=True)
        is_sim = False
    elif TRADE_MODE == "KABUCOM_TEST":
        print("🧪 【テストモード】auカブコム証券 検証用API (Port 8081) に接続します")
        broker = KabucomBroker(is_production=False)
        is_sim = False
    else:
        print("🎮 【シミュレーションモード】ローカルCSVベースで実行します")
        broker = SimulationBroker()
        is_sim = True
        
    account = broker.get_account_balance()
    portfolio = broker.get_positions()
    actions_taken = []
    
    # --- 2. 相場環境（レジーム）判定 ---
    regime = detect_market_regime()
    print(f"📊 現在のレジーム: 【{regime}】")
    
    if regime == "BEAR":
        print("🚨 【警告】パニック・弱気相場を検知。資金保護のため新規買い付けを完全に停止します。")
        send_discord_notify("🚨 【BEAR相場検知】パニック・弱気相場のため新規買い付けを停止。手仕舞いのみ実行します。")
        portfolio, account, sell_acts, trade_logs = manage_positions(portfolio, account, broker, is_simulation=is_sim)
        actions_taken.extend(sell_acts)
        broker.save_positions(portfolio)
        broker.save_account(account)
        for log in trade_logs: broker.log_trade(log)
        
        stock_value = sum([float(p.get('current_price', p['buy_price'])) * int(p['shares']) for p in portfolio])
        broker.log_execution_summary({
            "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "actions": actions_taken, "portfolio": portfolio, "regime": regime,
            "cash_yen": account['cash'], "stock_value_yen": stock_value,
            "total_assets_yen": account['cash'] + stock_value
        })
        return

    # --- 3. ポジション管理（利確・損切・タイムストップ） ---
    portfolio, account, sell_acts, trade_logs = manage_positions(portfolio, account, broker, is_simulation=is_sim)
    actions_taken.extend(sell_acts)
    broker.save_positions(portfolio)
    broker.save_account(account)
    for log in trade_logs: broker.log_trade(log)

    # --- サマリー記録用ヘルパー ---
    def record_summary(actions):
        stock_value = sum([float(p.get('current_price', p['buy_price'])) * int(p['shares']) for p in portfolio])
        broker.log_execution_summary({
            "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "actions": actions, "portfolio": portfolio, "regime": regime,
            "cash_yen": account['cash'], "stock_value_yen": stock_value,
            "total_assets_yen": account['cash'] + stock_value
        })

    if len(portfolio) >= MAX_POSITIONS:
        print(f"\n💡 最大ポジション（{MAX_POSITIONS}銘柄）保有中。新規スキャンをスキップします。")
        send_discord_notify(f"💡 【見送り】最大ポジション（{MAX_POSITIONS}銘柄）保有中のため新規スキャンをスキップしました。")
        record_summary(actions_taken)
        return

    now_time = datetime.now().time()
    if now_time < datetime.strptime("09:30", "%H:%M").time() and not DEBUG_MODE:
        print("\n💡 寄り付き直後（9:30前）は値動きがランダムで危険なため、新規エントリーのスキャンを待機します。")
        send_discord_notify("💡 【見送り】寄り付き直後（9:30前）のためエントリー待機中。保有監視のみ実行しました。")
        record_summary(actions_taken)
        return

    if now_time >= datetime.strptime("14:30", "%H:%M").time():
        print("\n💡 大引け前（14:30以降）のため、オーバーナイトリスクを避けるべく本日の新規買付を終了します。")
        send_discord_notify("💡 【見送り】大引け前（14:30以降）のため新規買付を終了。保有ポジションの決済監視のみ実行しました。")
        record_summary(actions_taken)
        return

    # --- 4. スクリーニング ---
    try:
        df_symbols = pd.read_csv(DATA_FILE)
        
        # 【修正】ETF・REIT等を除外：完全一致ではなく「内国株式」という文字が含まれるものだけを残す（部分一致）
        if '市場・商品区分' in df_symbols.columns:
            df_symbols = df_symbols[df_symbols['市場・商品区分'].str.contains('内国株式', na=False)]
            
        # 既に保有している銘柄は除外
        held_codes = [str(p['code']) for p in portfolio]
        targets = [str(t) for t in df_symbols['コード'].tolist() if str(t) not in held_codes]
    except Exception as e:
        print(f"⚠️ 銘柄リスト読み込みエラー: {e}")
        return

    tickers = [f"{code}.T" for code in targets]
    print(f"\n--- 📈 数学的スクリーニング ({len(tickers)}銘柄) ---")
    
    data_dfs = []
    chunk_size = 500
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i + chunk_size]
        try:
            chunk_df = yf.download(chunk, period="5d", interval="15m", group_by='ticker', threads=True, progress=False)
            if chunk_df is not None and not chunk_df.empty:
                if isinstance(chunk_df.columns, pd.MultiIndex):
                    data_dfs.append(chunk_df)
            time.sleep(0.5)
        except Exception as e:
            print(f"⚠️ データ取得エラー(Chunk {i}): {e}")
            continue

    if not data_dfs:
        msg = "⚠️ 【エラー】データ取得に完全に失敗しました。APIレートリミットまたはネットワーク障害の可能性があります。"
        print(msg)
        send_discord_notify(msg)
        record_summary(actions_taken)
        return

    data_df = pd.concat(data_dfs, axis=1) if len(data_dfs) > 1 else data_dfs[0]
    print("✅ データ取得完了。評価アルゴリズムを実行します...")
    
    top_candidates = select_best_candidates(data_df, targets, df_symbols, regime)
    
    if not top_candidates:
        msg = f"💡 【見送り】レジーム: {regime} | スクリーニングの結果、優位性のある銘柄が見つかりませんでした。"
        print(f"💡 現在のレジーム({regime})で優位性のある銘柄は見つかりませんでした。無駄な売買を見送ります。")
        send_discord_notify(msg)
        record_summary(actions_taken)
        return

    # --- 5. AI定性フィルター ---
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



    # --- 6. エントリー ---
    if best_target:
        if pd.isna(best_target['price']) or pd.isna(best_target['atr']) or best_target['price'] <= 0:
            msg = f"⚠️ 【安全装置作動】{best_target['code']} {best_target['name']} の価格データに異常を検知（{best_target['price']}）。買付を強制キャンセルしました。"
            print(msg)
            send_discord_notify(msg)
            record_summary(actions_taken)
            return
            
        # シミュレーション用スリッページ
        buy_price = float(best_target['price']) * 1.001 
        atr = float(best_target['atr'])
        
        stock_value = sum([float(p.get('current_price', p['buy_price'])) * int(p['shares']) for p in portfolio])
        total_equity = account['cash'] + stock_value
        risk_amount = total_equity * MAX_RISK_PER_TRADE
        risk_per_share = atr * ATR_STOP_LOSS
        
        ideal_shares = int(risk_amount // risk_per_share) if risk_per_share > 0 else 100
        
        # 【修正】1銘柄あたりの最大投資額キャップ（ハイブリッド方式）
        # 「総資金の30%」と「最低保証額（20万円）」の大きい方をキャップとして採用
        max_investment_amount = max(total_equity * MAX_ALLOCATION_PCT, MIN_ALLOCATION_AMOUNT)
        max_shares_by_allocation = int(max_investment_amount // buy_price)

        # 実際の現金余力とすり合わせ
        max_shares_by_cash = int(account['cash'] // buy_price)
        
        # 理想の株数、上限キャップ、現金残高のうち、最も少ない（安全な）株数を採用する
        raw_shares = min(ideal_shares, max_shares_by_allocation, max_shares_by_cash)
        
        shares_to_buy = (raw_shares // 100) * 100
        cost = buy_price * shares_to_buy
        
        if cost <= account['cash'] and shares_to_buy >= 100:
            if account['cash'] - cost < 0:
                 msg = "⚠️ 【安全装置作動】資金計算エラー: 買付余力がマイナスになるため取引を強制ブロックしました。"
                 print(msg)
                 send_discord_notify(msg)
            else:
                # リアルAPI（Kabucom）の場合は実際に買い注文を発注
                buy_success = True
                if not is_sim:
                    buy_success = broker.execute_market_order(best_target['code'], shares_to_buy, side="2") # 2: 買い
                
                if buy_success:
                    print(f"\n🏆 【シグナル点灯】{regime}戦略に基づく最適銘柄: {best_target['code']} {best_target['name']}")
                    print(f"🛒 買付価格: {buy_price:,.1f}円 | 数量: {shares_to_buy}株 | 概算代金: {cost:,.0f}円 (ATR: {atr:.1f})")
                    
                    notify_msg = f"🏆 **【新規買付】{best_target['code']} {best_target['name']}**\n戦略: {regime} | 価格: {buy_price:,.1f}円 × {shares_to_buy}株 (代金: {cost:,.0f}円)\n📊 AI判定: 問題なし"
                    send_discord_notify(notify_msg)
                    
                    actions_taken.append(f"買付: {best_target['code']} {best_target['name']} {shares_to_buy}株 ({cost:,.0f}円)")
                    
                    if is_sim: 
                        account['cash'] -= cost
                        
                    portfolio.append({
                        "code": best_target['code'], "name": best_target['name'], 
                        "buy_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                        "buy_price": buy_price, "highest_price": buy_price, 
                        "current_price": buy_price, "shares": shares_to_buy
                    })
                    broker.save_positions(portfolio)
                    broker.save_account(account)
                else:
                    msg = f"⚠️ 【注文エラー】{best_target['code']}の買付注文が証券会社APIで受付拒否されました。"
                    print(msg)
                    send_discord_notify(msg)
        else:
            if shares_to_buy < 100:
                msg = f"💡 【見送り】{best_target['code']} {best_target['name']} — ボラティリティ過大(ATR:{atr:.1f})のためリスク管理制限で買付キャンセル。"
                print(msg)
                send_discord_notify(msg)
            else:
                msg = f"💡 【見送り】{best_target['code']} {best_target['name']} — 現金不足 ({cost:,.0f}円必要 / 残高{account['cash']:,.0f}円)。"
                print(msg)
                send_discord_notify(msg)
    else:
        msg = "💡 【見送り】AI定性フィルターにより全候補がリジェクトされました。安全のため見送ります。"
        print(msg)
        send_discord_notify(msg)
        
    record_summary(actions_taken)

if __name__ == "__main__":
    main()
