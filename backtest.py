import yfinance as yf
import pandas as pd
from datetime import datetime
import os
import sys

# プロジェクトルートをパスに追加
sys.path.append(os.getcwd())

from core.logic import select_best_candidates, manage_positions, RealtimeBuffer, detect_market_regime
from core.sim_broker import SimulationBroker
from core.config import (
    INITIAL_CASH, DATA_FILE, JST, 
    MAX_RISK_PER_TRADE, MAX_ALLOCATION_PCT, MIN_ALLOCATION_AMOUNT,
    ATR_STOP_LOSS, RANGE_ATR_STOP_LOSS
)

def run_backtest(target_codes, initial_cash_val=1000000, period="30d", interval="15m"):
    # 1. 過去データのダウンロード
    download_period = "60d" 
    tickers = [f"{code}.T" for code in target_codes] + ["1321.T"]
    print(f"Backtest Start: (Initial Cash={initial_cash_val:,.0f}, period={download_period}, test_eval=20d)")
    print(f"Target codes: {len(target_codes)}")
    print(f"Downloading historical data...")
    full_data = yf.download(tickers, period=download_period, interval=interval, group_by='ticker', auto_adjust=False, progress=True, threads=False)
    
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

    # 2. タイムライン作成
    all_times = df_1321_full.index.unique().sort_values()
    test_start_idx = max(0, len(all_times) - 500) 
    timeline = all_times[test_start_idx:]
    print(f"Timeline generated: Total {len(timeline)} steps (Warmup points: {test_start_idx})")

    # 3. 口座とポートフォリオの初期化
    account = {"cash": initial_cash_val}
    portfolio = [] 
    trade_history = []
    broker = SimulationBroker()
    
    # 銘柄情報の読み込み
    df_symbols = pd.read_csv(DATA_FILE)

    # 4. タイムマシン・ループ
    for current_time in timeline:
        # --- A. データのスライス ---
        sliced_data = full_data.loc[:current_time]
        
        mock_buffers = {}
        for code in target_codes:
            ticker = f"{code}.T"
            if ticker in sliced_data.columns.levels[0]:
                df_sliced = sliced_data[ticker].dropna()
                if not df_sliced.empty:
                    mock_buffers[code] = RealtimeBuffer(code, df_sliced)
        
        if not df_1321_full.loc[:current_time].empty:
            mock_buffers['1321'] = RealtimeBuffer('1321', df_1321_full.loc[:current_time])

        # --- B. レジーム判定 ---
        regime = detect_market_regime(broker=None, buffer=mock_buffers.get('1321'), current_time_override=current_time)

        # --- C. 保有ポジションの管理 ---
        portfolio, account, actions, logs = manage_positions(
            portfolio, account, broker=broker, regime=regime, 
            is_simulation=True, realtime_buffers=mock_buffers,
            current_time_override=current_time
        )
        trade_history.extend(logs)

        # --- D. 新規買付判定 ---
        market_time = current_time.time()
        start_buy = datetime.strptime("09:30", "%H:%M").time()
        end_buy = datetime.strptime("14:00", "%H:%M").time()

        if start_buy <= market_time < end_buy and len(portfolio) < 4:
            if current_time.minute in [0, 15, 30, 45]:
                if not (current_time.hour == 11 and current_time.minute > 30) and not (current_time.hour == 12):
                    held_codes = [str(p['code']) for p in portfolio]
                    scan_targets = [c for c in target_codes if str(c) not in held_codes]
                    
                    candidates = select_best_candidates(None, scan_targets, df_symbols, regime, 
                                                       realtime_buffers=mock_buffers, current_time_override=current_time)
                    
                    if candidates:
                        best = candidates[0]
                        best_df = mock_buffers[best['code']].df
                        buy_price = float(best_df.iloc[-1]['Close'])
                        atr = best['atr']
                        
                        # --- 資金管理ロジック (auto_trade.py から移植) ---
                        total_equity = account['cash'] + sum([float(p.get('current_price', p['buy_price'])) * int(p['shares']) for p in portfolio])
                        
                        # 1トレードあたりの許容リスク (2%)
                        risk_amount = total_equity * MAX_RISK_PER_TRADE
                        current_sl_mult = RANGE_ATR_STOP_LOSS if regime == "RANGE" else ATR_STOP_LOSS
                        risk_per_share = atr * current_sl_mult
                        
                        # リスクベースの理想株数
                        ideal_shares = int(risk_amount // risk_per_share) if risk_per_share > 0 else 100
                        
                        # 1銘柄あたりの投資上限 (30% or 最低保証額)
                        max_inv = max(total_equity * MAX_ALLOCATION_PCT, MIN_ALLOCATION_AMOUNT)
                        max_shares_inv = int(max_inv // buy_price)
                        max_shares_cash = int(account['cash'] // buy_price)
                        
                        raw_shares = min(ideal_shares, max_shares_inv, max_shares_cash)
                        shares_to_buy = (raw_shares // 100) * 100
                        cost = buy_price * shares_to_buy
                        
                        if shares_to_buy >= 100 and account['cash'] >= cost:
                            broker.execute_market_order(best['code'], shares_to_buy, "buy", price=buy_price)
                            portfolio.append({
                                "code": best['code'], "name": best['name'],
                                "buy_price": buy_price, "shares": shares_to_buy,
                                "buy_time": current_time, "atr": atr
                            })
                            account['cash'] -= cost
                            print(f"[{current_time.strftime('%m/%d %H:%M')}] Buy: {best['code']} {shares_to_buy} shares @ {buy_price:.1f} (Regime:{regime})")
                        else:
                            # 資金不足で買えない場合のデバッグログ
                            if current_time.minute == 0:
                                reason = "Cash Short" if account['cash'] < buy_price * 100 else "Risk/Alloc Limit"
                                print(f"  [Scan Debug] {current_time.strftime('%m/%d %H:%M')} {best['code']} skip ({reason}: Need {buy_price*100:,.0f} for 100sh)")

    # 5. バックテスト結果サマリー
    print("\n" + "="*40)
    print("Backtest Result Summary")
    print("="*40)
    final_stock_value = 0
    for p in portfolio:
        code = p['code']
        if code in mock_buffers:
            p['current_price'] = float(mock_buffers[code].df.iloc[-1]['Close'])
            final_stock_value += p['current_price'] * p['shares']
            
    total_assets = account['cash'] + final_stock_value
    profit_total = total_assets - initial_cash_val
    profit_pct = (profit_total / initial_cash_val) * 100

    print(f"Initial Cash: {initial_cash_val:,.0f}")
    print(f"Final Assets: {total_assets:,.0f} (Cash: {account['cash']:,.0f}, Stocks: {final_stock_value:,.0f})")
    print(f"Net Profit:   {profit_total:+.0f} ({profit_pct:+.2f}%)")
    print(f"Total Trades: {len(trade_history)}")
    
    if trade_history:
        win_trades = [t for t in trade_history if t.get('net_profit', 0) > 0]
        win_rate = len(win_trades) / len(trade_history) * 100
        print(f"Win Rate: {win_rate:.1f}% ({len(win_trades)}W / {len(trade_history)-len(win_trades)}L)")
    print("="*40)

if __name__ == "__main__":
    # 現実に即したユニバース（100万円で買いやすい1500円以下の銘柄も追加）
    test_universe = ["8306", "7203", "9101", "8058", "6758", "4063"] # 元の銘柄
    test_universe += ["9501", "6723", "7201", "8411", "9503"] # 100万円で買いやすい銘柄 (東電, ルネサス, 日産, みずほ, 関電)
    
    # 100万円で実行
    run_backtest(target_codes=test_universe, initial_cash_val=1000000, period="20d", interval="15m")
