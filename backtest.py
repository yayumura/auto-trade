import yfinance as yf
import pandas as pd
from datetime import datetime
import os
import sys
import argparse
import pytz
import time
import pickle

# プロジェクトルートをパスに追加
sys.path.append(os.getcwd())

from core.logic import select_best_candidates, manage_positions, RealtimeBuffer, detect_market_regime, get_tick_size
from core.sim_broker import SimulationBroker
from core.config import (
    INITIAL_CASH, DATA_FILE, JST, 
    MAX_RISK_PER_TRADE, MAX_ALLOCATION_PCT, MIN_ALLOCATION_AMOUNT,
    MAX_POSITIONS, ATR_STOP_LOSS, RANGE_ATR_STOP_LOSS, TAX_RATE
)

# --- Stock Universes ---
PHASE1_STOCKS = [
    "7203", "7267", "7201", "8306", "8316", "8411", "8766", "8591", "8035", "6857", 
    "6920", "6723", "6758", "9984", "9432", "7974", "8058", "8031", "8001", "7011", 
    "6301", "6501", "5401", "9501", "9983", "3382", "4661", "6098", "4502", "4519", 
    "4063", "8801", "9101", "5020"
]

PHASE2_STOCKS = [
    "7203", "7267", "7269", "7201", "7270", "7211", "7202", "7282", "7259",
    "8306", "8316", "8411", "8308", "8309", "8604", "8601", "8766", "8750", "8795", "8591",
    "8035", "6857", "6920", "6526", "6723", "6981", "6954", "6594", "6861", "6971", "6762", "7741", "7733", "7751",
    "9984", "9432", "9433", "9434", "6758", "7974", "3659", "4751", "4307",
    "8058", "8031", "8001", "8002", "8053", "2768", "8015",
    "7011", "7012", "6301", "6326", "6501", "6503", "5401", "5411", "9501", "9502", "9503",
    "9983", "3382", "4661", "4689", "6098", "2413", "4543", "4452", "8113", "4911", "2502", "2503",
    "4502", "4503", "4519", "4568", "4523", "4507",
    "8801", "8802", "8830", "9020", "9021", "9022", "1925", "1928", "1801", "1802", "1803",
    "4063", "3402", "4183", "4005", "4901", "5020", "5108", "9101", "9104", "9107"
]

def get_topix500_stocks():
    """
    data_j.csvからTOPIX500（Core30, Large70, Mid400）の銘柄コードを動的に取得する
    規模コード: 1=Core30, 2=Large70, 4=Mid400
    """
    try:
        if os.path.exists(DATA_FILE):
            df = pd.read_csv(DATA_FILE, dtype={'規模コード': str, 'コード': str})
            # 規模コード 1, 2, 4 の銘柄を抽出
            topix500 = df[df['規模コード'].isin(['1', '2', '4'])]['コード'].tolist()
            if topix500:
                return topix500
    except Exception as e:
        print(f"  [Warning] Failed to load TOPIX500 from {DATA_FILE}: {e}")
    # 失敗した場合はフェイルセーフとしてPHASE2を返す
    return PHASE2_STOCKS

PHASE3_STOCKS = get_topix500_stocks()

def get_historical_data(target_codes, start=None, end=None, period=None, interval="15m"):
    """過去データのダウンロードと前処理 (Phase 8: キャッシュ機構と分割ダウンロード)"""
    tickers = [f"{code}.T" for code in target_codes] + ["1321.T"]
    
    cache_dir = "data_cache"
    os.makedirs(cache_dir, exist_ok=True)
    
    # キャッシュファイル名の生成（バージョンv2にして再取得を強制）
    safe_start = start if start else "None"
    safe_end = end if end else "None"
    safe_period = period if period else "None"
    cache_filename = f"hist_{len(tickers)}stocks_{safe_start}_{safe_end}_{safe_period}_{interval}_v4.pkl"
    cache_path = os.path.join(cache_dir, cache_filename)

    if os.path.exists(cache_path):
        print(f"[OK] ローカルキャッシュからデータを高速読み込みします: {cache_filename}")
        full_data = pd.read_pickle(cache_path)
    else:
        print(f"[API] Yahoo APIからデータを取得します (データ構造のブレを完全に正規化します)")
        chunk_size = 20
        df_list = []
        
        # 助走期間（4ヶ月分）を考慮した開始日の計算 (Phase 17)
        adjusted_start = start
        if start:
            start_date = pd.to_datetime(start)
            adjusted_start = (start_date - pd.DateOffset(months=12)).strftime('%Y-%m-%d')

        for i in range(0, len(tickers), chunk_size):
            chunk = tickers[i:i+chunk_size]
            print(f"  -> Downloading chunk {i//chunk_size + 1} ({len(chunk)} tickers) ...")
            
            if start and end:
                temp_df = yf.download(chunk, start=adjusted_start, end=end, interval=interval, group_by='ticker', auto_adjust=True, progress=False, threads=False)
            else:
                p = period if period else "60d"
                temp_df = yf.download(chunk, period=p, interval=interval, group_by='ticker', auto_adjust=True, progress=False, threads=False)
            
            if temp_df.empty:
                continue
                
            # 【究極の防波堤】yfinanceの仕様変更や単一/複数銘柄によるデータ構造のブレを完全に正規化
            if isinstance(temp_df.columns, pd.MultiIndex):
                # (Price, Ticker) になっている場合は (Ticker, Price) に反転
                if any(str(c) in temp_df.columns.levels[1] for c in chunk):
                    temp_df = temp_df.swaplevel(0, 1, axis=1)
                
                # カラム名を強制的に頭文字大文字（'close' -> 'Close'）に統一
                temp_df.rename(columns=lambda x: str(x).capitalize(), level=1, inplace=True)
            else:
                # 1銘柄だけ取得した場合 (フラットなIndex)
                temp_df.rename(columns=lambda x: str(x).capitalize(), inplace=True)
                temp_df.columns = pd.MultiIndex.from_product([chunk, temp_df.columns], names=['Ticker', 'Price'])
                
            df_list.append(temp_df)
            
            if i + chunk_size < len(tickers):
                time.sleep(2)
            
        # 分割取得したデータを横方向（銘柄別）に結合
        full_data = pd.concat(df_list, axis=1)
        
        # 次回のためにキャッシュとして保存
        full_data.to_pickle(cache_path)
        print(f"[SAVE] データをキャッシュに保存しました！")
    
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

def run_backtest_session(target_codes, full_data, df_1321_full, timeline, initial_cash_val=1000000, verbose=False, show_trades=True, interval="15m"):
    """特定のタイムライン上でバックテストを実行"""
    if show_trades or verbose:
        print(f"  Session Start: {timeline[0].strftime('%Y-%m-%d')} to {timeline[-1].strftime('%Y-%m-%d')} ({len(timeline)} steps)")

    # 銘柄情報の読み込み
    df_symbols = pd.read_csv(DATA_FILE)

    # アカウントとポートフォリオの初期化
    account = {"cash": initial_cash_val}
    portfolio = [] 
    trade_history = []
    pending_exits = [] # 【Round 2】次足決済用
    broker = SimulationBroker()

    # タイムマシン・ループ
    for i in range(len(timeline)):
        current_time = timeline[i]
        # --- [Phase 0] 決済の執行 (Next Bar Open Exit) ---
        if pending_exits:
            new_pending = []
            for pe in pending_exits:
                code = pe['code']
                ticker_sym = f"{code}.T"
                if ticker_sym in full_data.columns.levels[0]:
                    bar_data = full_data[ticker_sym].loc[current_time]
                    if not bar_data.empty and not pd.isna(bar_data['Open']):
                        op = float(bar_data['Open'])
                        hi = float(bar_data['High'])
                        lo = float(bar_data['Low'])
                        
                        # スリッページ計算 (売却)
                        tick_size = get_tick_size(op)
                        slippage = max(tick_size, pe['atr'] * 0.01)
                        exec_price = max(lo, op - slippage)
                        
                        # 損益計算の再実行
                        actual_qty = pe['shares']
                        buy_price = pe['buy_price']
                        gross_profit = (exec_price - buy_price) * actual_qty
                        tax_amount = int(gross_profit * TAX_RATE) if gross_profit > 0 else 0
                        
                        COMMISSION_RATE = 0.000
                        sell_commission = int((exec_price * actual_qty) * COMMISSION_RATE)
                        buy_commission = int((buy_price * actual_qty) * COMMISSION_RATE)
                        sale_proceeds = (exec_price * actual_qty) - tax_amount - sell_commission
                        net_profit = gross_profit - tax_amount - sell_commission - buy_commission
                        
                        account['cash'] += sale_proceeds
                        
                        # ポートフォリオからポジションを特定
                        p_idx = next((idx for idx, p in enumerate(portfolio) if str(p['code']) == str(code)), None)
                        if p_idx is not None:
                            p = portfolio[p_idx]
                            # 集計用データの蓄積
                            p['total_sell_proceeds'] = p.get('total_sell_proceeds', 0) + sale_proceeds
                            p['total_tax'] = p.get('total_tax', 0) + tax_amount
                            p['total_sell_qty'] = p.get('total_sell_qty', 0) + actual_qty
                            
                            if actual_qty < p['shares']:
                                p['shares'] -= actual_qty
                                if "分割利確" in pe['reason']: p['partial_sold'] = True
                            else:
                                # 全決済完了時に trade_history へ記録
                                final_qty = p['total_sell_qty']
                                avg_sell_price = p['total_sell_proceeds'] / final_qty if final_qty > 0 else exec_price
                                total_buy_cost = p['buy_price'] * final_qty
                                gross_pnl = p['total_sell_proceeds'] - total_buy_cost
                                
                                trade_record = {
                                    "code": p['code'], "name": p['name'],
                                    "buy_time": p['buy_time'], "buy_price": p['buy_price'],
                                    "sell_time": current_time.strftime('%Y-%m-%d %H:%M:%S'),
                                    "sell_price": avg_sell_price,
                                    "shares": final_qty,
                                    "net_profit": gross_pnl - p['total_tax'],
                                    "profit_pct": (avg_sell_price - p['buy_price']) / p['buy_price'] if p['buy_price'] > 0 else 0,
                                    "reason": pe['reason']
                                }
                                trade_history.append(trade_record)
                                portfolio.pop(p_idx)
                        
                        if show_trades or verbose:
                            print(f"    [{current_time.strftime('%m/%d %H:%M')}] Sell Executed (Next Bar Open): {code} @ {exec_price:.1f} ({pe['reason']})")
                    else:
                        # データがない場合は次の足に持ち越し
                        new_pending.append(pe)
                else:
                    new_pending.append(pe)
            pending_exits = new_pending

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

        # --- C. 保有ポジションの管理 (シグナル発生のみ) ---
        # 既に売却予約されている銘柄は manage_positions の対象から外す
        temp_portfolio = [p for p in portfolio if not any(str(pe['code']) == str(p['code']) for pe in pending_exits)]
        
        _, account, actions, logs = manage_positions(
            temp_portfolio, account, broker=broker, regime=regime, 
            is_simulation=True, realtime_buffers=mock_buffers,
            current_time_override=current_time, verbose=verbose,
            delay_sim_execution=True # 【Round 2】
        )
        
        # 発生したログを売却予約として蓄積
        for log in logs:
            if not any(str(pe['code']) == str(log['code']) for pe in pending_exits):
                pending_exits.append(log)

        # --- D. 新規買付判定 ---
        # 1d（日足）の場合は時間フィルターと分単位のチェックをスキップする (Phase 22 Fix)
        if interval == "1d":
            should_scan = (len(portfolio) < MAX_POSITIONS)
        else:
            market_time = current_time.time()
            start_buy = datetime.strptime("09:30", "%H:%M").time()
            end_buy = datetime.strptime("14:00", "%H:%M").time()
            is_open = (start_buy <= market_time < end_buy)
            is_not_lunch = not (current_time.hour == 11 and current_time.minute > 30) and not (current_time.hour == 12)
            is_on_quarter = (current_time.minute in [0, 15, 30, 45])
            should_scan = (is_open and is_on_quarter and is_not_lunch and len(portfolio) < MAX_POSITIONS)

        if should_scan:
            held_codes = [str(p['code']) for p in portfolio]
            scan_targets = [c for c in target_codes if str(c) not in held_codes]
            
            candidates = select_best_candidates(None, scan_targets, df_symbols, regime, 
                                               is_simulation=True, realtime_buffers=mock_buffers, 
                                               current_time_override=current_time, verbose=verbose)
            
            if candidates:
                best = candidates[0]
                code = best['code']
                
                # 【重要】執行を「次の足」に遅延させる (Lookahead Bias 回避)
                if i + 1 < len(timeline):
                    next_time = timeline[i+1]
                    ticker_sym = f"{code}.T"
                    
                    # 次足のデータを確認
                    if ticker_sym in full_data.columns.levels[0]:
                        next_bar = full_data[ticker_sym].loc[next_time]
                        if next_bar.empty or pd.isna(next_bar['Open']):
                            continue
                        
                        next_open = float(next_bar['Open'])
                        next_high = float(next_bar['High'])
                        next_vol = float(next_bar['Volume']) if 'Volume' in next_bar else 0
                        
                        if next_open <= 0: continue

                        # スリッページ計算 (買付は Open + slippage)
                        tick_size = get_tick_size(next_open)
                        slippage = max(tick_size, best['atr'] * 0.01)
                        buy_price = min(next_high, next_open + slippage) # クリップ処理
                        
                        # 資金管理ロジック
                        current_stock_value = sum([float(p.get('current_price', p['buy_price'])) * int(p['shares']) for p in portfolio])
                        total_equity = account['cash'] + current_stock_value
                        risk_amount = total_equity * MAX_RISK_PER_TRADE
                        current_sl_mult = RANGE_ATR_STOP_LOSS if regime == "RANGE" else ATR_STOP_LOSS
                        risk_per_share = best['atr'] * current_sl_mult
                        
                        ideal_shares = int(risk_amount // risk_per_share) if risk_per_share > 0 else 100
                        # 1銘柄への最大投資額を制限 (資産の30% もしくは 固定2000万円の小さい方)
                        max_inv_limit = min(total_equity * 0.3, 20000000)
                        max_inv = min(max(total_equity * MAX_ALLOCATION_PCT, MIN_ALLOCATION_AMOUNT), max_inv_limit)

                        max_shares_inv = int(max_inv // buy_price)
                        max_shares_cash = int(account['cash'] // buy_price)
                        
                        # 【新規】流動性制限 (次の足の出来高の1.0%まで、最低100株。0なら100株とする)
                        liquidity_limit = max(100, int(next_vol * 0.01))
                        
                        raw_shares = min(ideal_shares, max_shares_inv, max_shares_cash, liquidity_limit)
                        shares_to_buy = (raw_shares // 100) * 100
                        
                        cost = buy_price * shares_to_buy
                        
                        if shares_to_buy >= 100 and account['cash'] >= cost:
                            broker.execute_market_order(best['code'], shares_to_buy, "buy", price=buy_price)
                            portfolio.append({
                                "code": best['code'], "name": best['name'],
                                "buy_price": buy_price, "shares": shares_to_buy,
                                "buy_time": next_time, "atr": best['atr']
                            })
                            account['cash'] -= cost
                            if show_trades or verbose:
                                print(f"    [{next_time.strftime('%m/%d %H:%M')}] Buy: {best['code']} {shares_to_buy}sh @ {buy_price:.1f} (Vol: {next_vol:.0f})")
                else:
                    if verbose:
                        print(f"    [{current_time.strftime('%m/%d %H:%M')}] Signal on Last Bar: {code} (Execution skipped)")

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
    avg_net_profit = 0
    payoff_ratio = 0
    if trade_history:
        win_trades = [t for t in trade_history if t.get('net_profit', 0) > 0]
        loss_trades = [t for t in trade_history if t.get('net_profit', 0) <= 0]
        win_rate = len(win_trades) / len(trade_history) * 100
        total_pnl = total_assets - initial_cash_val
        avg_net_profit = total_pnl / len(trade_history) if len(trade_history) > 0 else 0
        
        avg_win = sum(t['net_profit'] for t in win_trades) / len(win_trades) if win_trades else 0
        avg_loss = sum(t['net_profit'] for t in loss_trades) / len(loss_trades) if loss_trades else 0
        payoff_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0

    return {
        "start_date": timeline[0].strftime('%Y/%m/%d'),
        "end_date": timeline[-1].strftime('%Y/%m/%d'),
        "initial_cash": initial_cash_val,
        "final_assets": total_assets,
        "profit_pct": profit_pct,
        "trade_count": len(trade_history),
        "win_rate": win_rate,
        "avg_net_profit": avg_net_profit,
        "payoff_ratio": payoff_ratio,
        "held_count": len(portfolio)
    }

def run_multi_period_backtest(target_codes, full_data, df_1321_full, window_days=5, start_date=None, end_date=None, interval="15m"):
    """複数期間に分割してバックテストを実行"""
    print(f"\n{'='*60}\nMulti-Period Backtest Start (Window: {window_days} days)\n{'='*60}")
    
    if full_data is None: return

    all_times = df_1321_full.index.unique().sort_values()
    dates = pd.Series(all_times.date).unique()
    
    # シミュレーション対象期間の決定 (Phase 11.1)
    if start_date:
        sim_start = pd.to_datetime(start_date).date()
        evaluation_dates = [d for d in dates if d >= sim_start]
    else:
        # デフォルト10営業日を助走に充てる
        warmup_days = 10
        evaluation_dates = dates[warmup_days:]

    if not evaluation_dates:
        print(f"  [Error] No dates found for evaluation after warmup")
        return

    results = []
    for i in range(0, len(evaluation_dates), window_days):
        window_dates = evaluation_dates[i : i + window_days]
        if len(window_dates) < window_days and i > 0: # 最後の端数が少なすぎる場合はスキップ
            continue
            
        start_dt, end_dt = window_dates[0], window_dates[-1]
        timeline = all_times[(all_times.date >= start_dt) & (all_times.date <= end_dt)]
        
        if len(timeline) < 10: continue
        
        res = run_backtest_session(target_codes, full_data, df_1321_full, timeline, verbose=False, show_trades=False, interval=interval)
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
    parser = argparse.ArgumentParser(description='Trade Bot Backtester')
    parser.add_argument('--stocks', type=str, default='phase1', choices=['phase1', 'phase2', 'phase3'], help='Stocks set (phase1=34, phase2=100, phase3=TOPIX500)')
    parser.add_argument('--all', action='store_true', help='Alias for --stocks phase3 (TOPIX500)')
    parser.add_argument('--start', type=str, help='Start date (YYYY-MM-DD)', default=None)
    parser.add_argument('--end', type=str, help='End date (YYYY-MM-DD)', default=None)
    parser.add_argument('--period', type=str, help='Data period (e.g. 60d, 1y)', default='60d')
    parser.add_argument('--interval', type=str, help='Data interval (15m, 1h, 1d)', default='15m')
    parser.add_argument('--verbose', action='store_true', help='Show detailed regime/buffer logs')
    args = parser.parse_args()

    if args.all or args.stocks == 'phase3':
        test_universe = PHASE3_STOCKS
        mode_name = f"Phase 3 (TOPIX 500 - {len(PHASE3_STOCKS)} stocks)"
    elif args.stocks == 'phase2':
        test_universe = PHASE2_STOCKS
        mode_name = "Phase 2 (100 stocks)"
    else:
        test_universe = PHASE1_STOCKS
        mode_name = "Phase 1 (34 stocks)"
    
    print(f"\n{'='*60}")
    print(f"Mode: {mode_name}")
    print(f"{'='*60}\n")
    
    # 一括でデータをダウンロード
    full_data, df_1321_full = get_historical_data(test_universe, start=args.start, end=args.end, period=args.period, interval=args.interval)
    
    if full_data is not None:
        # 1. 複数期間のサマリーを表示
        run_multi_period_backtest(test_universe, full_data, df_1321_full, window_days=5, start_date=args.start, end_date=args.end, interval=args.interval)
        
        # 2. 指定期間（または全期間）の統合サマリーを表示
        print("\n" + "="*40)
        print("Detailed Summary (Test Period Only)")
        print("="*40)
        
        all_times = df_1321_full.index.unique().sort_values()
        # `--start` / `--end` がある場合はその期間内のみを対象にする (Phase 11.1)
        if args.start and args.end:
            # タイムゾーン考慮: ユーザー入力を東京時間として解釈し、データのTZ (通常UTC) に変換
            data_tz = all_times.tz
            start_dt = pd.to_datetime(args.start).tz_localize('Asia/Tokyo').tz_convert(data_tz)
            end_dt = pd.to_datetime(args.end).tz_localize('Asia/Tokyo').tz_convert(data_tz)
            timeline = all_times[(all_times >= start_dt) & (all_times < end_dt)]
        else:
            test_start_idx = max(0, len(all_times) - 500) 
            timeline = all_times[test_start_idx:]
            
        if len(timeline) > 0:
            res = run_backtest_session(test_universe, full_data, df_1321_full, timeline, verbose=args.verbose, show_trades=True, interval=args.interval)
        
        print("\n" + "="*40)
        print("Backtest Result Summary")
        print("="*40)
        print(f"Initial Cash: {res['initial_cash']:,.0f}")
        print(f"Final Assets: {res['final_assets']:,.0f}")
        print(f"Net Profit:   {res['final_assets'] - res['initial_cash']:+.0f} ({res['profit_pct']:+.2f}%)")
        print(f"Total Trades: {res['trade_count']}")
        print(f"Win Rate:     {res['win_rate']:.1f}%")
        print(f"Avg Profit:   {res['avg_net_profit']:+,.0f} yen")
        print(f"Payoff Ratio: {res['payoff_ratio']:.2f}")
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
