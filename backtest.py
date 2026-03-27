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
    MAX_POSITIONS, ATR_STOP_LOSS, RANGE_ATR_STOP_LOSS
)

def get_historical_data(target_codes, period="60d", interval="15m"):
    """過去データのダウンロードと前処理"""
    tickers = [f"{code}.T" for code in target_codes] + ["1321.T"]
    print(f"Downloading historical data (period={period}, interval={interval})...")
    full_data = yf.download(tickers, period=period, interval=interval, group_by='ticker', auto_adjust=True, progress=False, threads=False)
    
    if full_data.empty:
        return None, None

    # インデックスを JST に統一
    if full_data.index.tzinfo is None:
        full_data.index = full_data.index.tz_localize('UTC').tz_convert(JST)
    else:
        full_data.index = full_data.index.tz_convert(JST)

    # 日経平均ETF（1321）のデータを取り出す（レジーム判定用）
    df_1321_full = full_data['1321.T'].dropna() if '1321.T' in full_data.columns.levels[0] else pd.DataFrame()
    return full_data, df_1321_full

def run_backtest_session(target_codes, full_data, df_1321_full, timeline, initial_cash_val=1000000, verbose=True):
    """特定のタイムライン上でバックテストを実行"""
    if verbose:
        print(f"  Session Start: {timeline[0].strftime('%Y-%m-%d')} to {timeline[-1].strftime('%Y-%m-%d')} ({len(timeline)} steps)")

    # 銘柄情報の読み込み
    df_symbols = pd.read_csv(DATA_FILE)

    # アカウントとポートフォリオの初期化
    account = {"cash": initial_cash_val}
    portfolio = [] 
    trade_history = []
    broker = SimulationBroker()

    # タイムマシン・ループ
    for current_time in timeline:
        # --- A. データのスライス ---
        # 15分足バッファを作成
        mock_buffers = {}
        sliced_data = full_data.loc[:current_time]
        
        for code in target_codes:
            ticker = f"{code}.T"
            if ticker in sliced_data.columns.levels[0]:
                df_sliced = sliced_data[ticker].dropna()
                if not df_sliced.empty:
                    mock_buffers[code] = RealtimeBuffer(code, df_sliced)
        
        if not df_1321_full.loc[:current_time].empty:
            mock_buffers['1321'] = RealtimeBuffer('1321', df_1321_full.loc[:current_time])

        # --- B. レジーム判定 ---
        regime = detect_market_regime(broker=None, buffer=mock_buffers.get('1321'), current_time_override=current_time, verbose=verbose)

        # --- C. 保有ポジションの管理 ---
        portfolio, account, actions, logs = manage_positions(
            portfolio, account, broker=broker, regime=regime, 
            is_simulation=True, realtime_buffers=mock_buffers,
            current_time_override=current_time, verbose=verbose
        )
        trade_history.extend(logs)

        # --- D. 新規買付判定 ---
        market_time = current_time.time()
        start_buy = datetime.strptime("09:30", "%H:%M").time()
        end_buy = datetime.strptime("14:00", "%H:%M").time()

        if start_buy <= market_time < end_buy and len(portfolio) < MAX_POSITIONS:
            if current_time.minute in [0, 15, 30, 45]:
                if not (current_time.hour == 11 and current_time.minute > 30) and not (current_time.hour == 12):
                    held_codes = [str(p['code']) for p in portfolio]
                    scan_targets = [c for c in target_codes if str(c) not in held_codes]
                    
                    candidates = select_best_candidates(None, scan_targets, df_symbols, regime, 
                                                       realtime_buffers=mock_buffers, current_time_override=current_time, verbose=verbose)
                    
                    if candidates:
                        best = candidates[0]
                        best_df = mock_buffers[best['code']].df
                        buy_price = float(best_df.iloc[-1]['Close'])
                        atr = best['atr']
                        
                        # 資金管理ロジック
                        total_equity = account['cash'] + sum([float(p.get('current_price', p['buy_price'])) * int(p['shares']) for p in portfolio])
                        risk_amount = total_equity * MAX_RISK_PER_TRADE
                        current_sl_mult = RANGE_ATR_STOP_LOSS if regime == "RANGE" else ATR_STOP_LOSS
                        risk_per_share = atr * current_sl_mult
                        
                        ideal_shares = int(risk_amount // risk_per_share) if risk_per_share > 0 else 100
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
                            if verbose:
                                print(f"    [{current_time.strftime('%m/%d %H:%M')}] Buy: {best['code']} {shares_to_buy}sh @ {buy_price:.1f}")

    # 結果集計
    final_stock_value = 0
    for p in portfolio:
        code = p['code']
        if code in mock_buffers:
            p['current_price'] = float(mock_buffers[code].df.iloc[-1]['Close'])
            final_stock_value += p['current_price'] * p['shares']
            
    total_assets = account['cash'] + final_stock_value
    profit_pct = (total_assets - initial_cash_val) / initial_cash_val * 100
    win_rate = 0
    if trade_history:
        win_trades = [t for t in trade_history if t.get('net_profit', 0) > 0]
        win_rate = len(win_trades) / len(trade_history) * 100

    return {
        "start_date": timeline[0].strftime('%Y/%m/%d'),
        "end_date": timeline[-1].strftime('%Y/%m/%d'),
        "initial_cash": initial_cash_val,
        "final_assets": total_assets,
        "profit_pct": profit_pct,
        "trade_count": len(trade_history),
        "win_rate": win_rate,
        "held_count": len(portfolio)
    }

def run_multi_period_backtest(target_codes, full_data, df_1321_full, window_days=5):
    """複数期間に分割してバックテストを実行"""
    print(f"\n{'='*60}\nMulti-Period Backtest Start (Window: {window_days} days)\n{'='*60}")
    
    if full_data is None: return

    all_times = df_1321_full.index.unique().sort_values()
    
    # 営業日ベースで分割
    dates = pd.Series(all_times.date).unique()
    results = []

    # window_days ごとに分割して実行
    warmup_days = 10
    if len(dates) <= warmup_days:
        print(f"  [Error] Data too short for warmup ({len(dates)} days)")
        return
        
    evaluation_dates = dates[warmup_days:]

    for i in range(0, len(evaluation_dates), window_days):
        window_dates = evaluation_dates[i : i + window_days]
        if len(window_dates) < window_days and i > 0: # 最後の端数が少なすぎる場合はスキップ
            continue
            
        start_dt, end_dt = window_dates[0], window_dates[-1]
        timeline = all_times[(all_times.date >= start_dt) & (all_times.date <= end_dt)]
        
        if len(timeline) < 10: continue
        
        res = run_backtest_session(target_codes, full_data, df_1321_full, timeline, verbose=False)
        results.append(res)
        print(f"  Result: {res['start_date']} - {res['end_date']} | Profit: {res['profit_pct']:+.2f}% | Trades: {res['trade_count']}")

    # サマリー表示
    print("\n" + "="*70)
    print(f"{'Period':<25} | {'Profit':>8} | {'Trades':>6} | {'Win%':>6}")
    print("-"*70)
    total_profit_sum = 0
    for r in results:
        period_str = f"{r['start_date']}-{r['end_date'][5:]}"
        print(f"{period_str:<25} | {r['profit_pct']:>7.2f}% | {r['trade_count']:>6} | {r['win_rate']:>5.1f}%")
        total_profit_sum += r['profit_pct']
    
    avg_profit = total_profit_sum / len(results) if results else 0
    print("-"*70)
    print(f"{'Average Performance':<25} | {avg_profit:>7.2f}% | {'-':>6} | {'-':>6}")
    print("="*70 + "\n")

if __name__ == "__main__":
    test_universe = ["8306", "7203", "9101", "8058", "6758", "4063", "9501", "6723", "7201", "8411", "9503"]
    
    # 一括でデータをダウンロード
    full_data, df_1321_full = get_historical_data(test_universe, period="60d")
    
    if full_data is not None:
        # 1. 複数期間のサマリーを表示
        run_multi_period_backtest(test_universe, full_data, df_1321_full, window_days=5)
        
        # 2. 直近20日間の詳細サマリーを表示
        print("\n" + "="*40)
        print("Detailed Summary (Last 500 steps / approx. 20 days)")
        print("="*40)
        
        all_times = df_1321_full.index.unique().sort_values()
        test_start_idx = max(0, len(all_times) - 500) 
        timeline = all_times[test_start_idx:]
        res = run_backtest_session(test_universe, full_data, df_1321_full, timeline, verbose=True)
        
        print("\n" + "="*40)
        print("Backtest Result Summary")
        print("="*40)
        print(f"Initial Cash: {res['initial_cash']:,.0f}")
        print(f"Final Assets: {res['final_assets']:,.0f}")
        print(f"Net Profit:   {res['final_assets'] - res['initial_cash']:+.0f} ({res['profit_pct']:+.2f}%)")
        print(f"Total Trades: {res['trade_count']}")
        print(f"Win Rate:     {res['win_rate']:.1f}%")
        print(f"Held Positions: {res['held_count']}")
        print("="*40)
        
        # --- Discord Summary Notification ---
        from core.log_setup import send_discord_notify
        summary_msg = (
            f"【BACKTEST 最終結果】\n"
            f"期間: {res['start_date']} - {res['end_date']}\n"
            f"最終資産: {res['final_assets']:,.0f}円 ({res['profit_pct']:+.2f}%)\n"
            f"取引回数: {res['trade_count']}回 | 勝率: {res['win_rate']:.1f}% | 保有: {res['held_count']}件"
        )
        send_discord_notify(summary_msg)
