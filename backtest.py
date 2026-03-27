import yfinance as yf
import pandas as pd
from datetime import datetime
import os
import sys

# プロジェクトルートをパスに追加
sys.path.append(os.getcwd())

from core.logic import select_best_candidates, manage_positions, RealtimeBuffer, detect_market_regime
from core.sim_broker import SimulationBroker
from core.config import INITIAL_CASH, DATA_FILE, JST

def run_backtest(target_codes, period="30d", interval="15m"):
    print(f"Backtest Start: Period {period} (Interval: {interval})")
    print(f"Target codes: {len(target_codes)}")
    
    # 1. 過去データの「全期間」を一括ダウンロード
    tickers = [f"{code}.T" for code in target_codes] + ["1321.T"]
    print("Downloading historical data...")
    full_data = yf.download(tickers, period=period, interval=interval, group_by='ticker', auto_adjust=False, progress=True, threads=False)
    
    if full_data.empty:
        print("Data download failed.")
        return

    # インデックスを JST に統一
    if full_data.index.tzinfo is None:
        full_data.index = full_data.index.tz_localize('UTC').tz_convert(JST)
    else:
        full_data.index = full_data.index.tz_convert(JST)

    # 日経平均ETF（1321）のデータを取り出す（レジーム判定用）
    df_1321_full = full_data['1321.T'].dropna() if '1321.T' in full_data.columns.levels[0] else pd.DataFrame()

    # 2. シミュレーション用の「タイムライン（時刻の配列）」を作成
    # 1321のインデックス（時刻）を基準とする
    timeline = df_1321_full.index.unique().sort_values()
    print(f"Timeline generated: Total {len(timeline)} steps")

    # 3. 口座とポートフォリオの初期化
    account = {"cash": INITIAL_CASH}
    portfolio = []
    trade_history = []
    broker = SimulationBroker()

    # スクリーニング用銘柄情報
    df_symbols = pd.read_csv(DATA_FILE)

    # 4. タイムマシン・ループ（過去から未来へ1ステップずつ進む）
    for current_time in timeline:
        # --- A. データのスライス（未来のデータを隠す / Look-ahead Biasの排除） ---
        sliced_data = full_data.loc[:current_time]
        
        mock_buffers = {}
        for code in target_codes:
            ticker = f"{code}.T"
            if ticker in sliced_data.columns.levels[0]:
                df_sliced = sliced_data[ticker].dropna()
                if not df_sliced.empty:
                    # RealtimeBufferを「過去のその時点までのデータ」で初期化
                    mock_buffers[code] = RealtimeBuffer(code, df_sliced)
        
        # 1321のバッファも作成（レジーム判定用）
        if not df_1321_full.loc[:current_time].empty:
            mock_buffers['1321'] = RealtimeBuffer('1321', df_1321_full.loc[:current_time])

        # --- B. レジーム判定 (仮想時間の注入) ---
        regime = detect_market_regime(broker=None, buffer=mock_buffers.get('1321'), current_time_override=current_time)

        # --- C. 保有ポジションの管理（売却判定 / 仮想時間の注入） ---
        portfolio, account, actions, logs = manage_positions(
            portfolio, account, broker=broker, regime=regime, 
            is_simulation=True, realtime_buffers=mock_buffers,
            current_time_override=current_time
        )
        trade_history.extend(logs)

        # --- D. 新規銘柄のスキャンと買付判定 (仮想時間の注入) ---
        # 9:30〜14:00の間のみ買付を行う（本業 auto_trade.py の仕様に準拠）
        market_time = current_time.time()
        start_buy = datetime.strptime("09:30", "%H:%M").time()
        end_buy = datetime.strptime("14:00", "%H:%M").time()

        if start_buy <= market_time < end_buy and len(portfolio) < 4:
            held_codes = [str(p['code']) for p in portfolio]
            scan_targets = [c for c in target_codes if str(c) not in held_codes]
            
            # ロジックを呼び出してスコアリング
            candidates = select_best_candidates(sliced_data, scan_targets, df_symbols, regime, 
                                               realtime_buffers=mock_buffers, current_time_override=current_time)
            
            if candidates:
                best = candidates[0]
                buy_price = float(best['price'])
                
                # 資金管理ロジック (暫定: 1銘柄あたり総資産の 25% 上限)
                total_equity = account['cash'] + sum([p.get('current_price', p['buy_price']) * p['shares'] for p in portfolio])
                invest_amount = total_equity * 0.25
                shares = (int(invest_amount // buy_price) // 100) * 100
                
                if shares >= 100 and (buy_price * shares) <= account['cash']:
                    cost = buy_price * shares
                    account['cash'] -= cost
                    portfolio.append({
                        "code": best['code'], "name": best['name'],
                        "buy_time": current_time.strftime('%Y-%m-%d %H:%M:%S'),
                        "buy_price": round(buy_price, 1), "highest_price": round(buy_price, 1),
                        "current_price": round(buy_price, 1), "shares": shares
                    })
                    print(f"[{current_time.strftime('%m/%d %H:%M')}] Buy: {best['code']} {shares} shares @ {buy_price:.1f} (Regime:{regime})")

    # 5. バックテスト結果のサマリー
    print("\n" + "="*40)
    print("Backtest Result Summary")
    print("="*40)
    final_stock_value = sum([p.get('current_price', p['buy_price']) * p['shares'] for p in portfolio])
    total_assets = account['cash'] + final_stock_value
    profit_total = total_assets - INITIAL_CASH
    profit_pct = (profit_total / INITIAL_CASH) * 100

    print(f"Initial Cash: {INITIAL_CASH:,.0f}")
    print(f"Final Assets: {total_assets:,.0f}")
    print(f"Net Profit:   {profit_total:+.0f} ({profit_pct:+.2f}%)")
    print(f"Total Trades: {len(trade_history)}")
    
    if trade_history:
        win_trades = [t for t in trade_history if t.get('net_profit', 0) > 0]
        win_rate = len(win_trades) / len(trade_history) * 100
        print(f"Win Rate: {win_rate:.1f}% ({len(win_trades)}W / {len(trade_history)-len(win_trades)}L)")
    print("="*40)

if __name__ == "__main__":
    # 初期検証セット: 日本を代表する流動性の高い銘柄
    test_universe = ["7203", "8306", "9984", "8035", "9101", "6758", "4063", "8058"]
    # 実行 (15分足の最大期間 60d 以内を推奨)
    run_backtest(target_codes=test_universe, period="20d", interval="15m")
