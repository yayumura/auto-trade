import yfinance as yf
import pandas as pd
from datetime import datetime
import os
import sys
import argparse
import time

sys.path.append(os.getcwd())

from core.logic import (
    calculate_all_technicals_v4, manage_positions_v4, select_best_candidates_v4
)
from core.config import (
    INITIAL_CASH, DATA_FILE, JST, 
    MAX_RISK_PER_TRADE, MAX_ALLOCATION_PCT, TAX_RATE,
    MAX_POSITIONS
)

# --- Stock Universes ---
PHASE1_STOCKS = ["7203", "8306", "9984"] 

def get_historical_data(target_codes, start=None, end=None, interval="1d"):
    tickers = [f"{code}.T" for code in target_codes] + ["1321.T"]
    cache_path = os.path.join("data_cache", f"hist_{len(tickers)}stocks_{start or 'None'}_{end or 'None'}_None_{interval}_v4.pkl")
    if os.path.exists(cache_path):
        print(f"[OK] Cache hit: {cache_path}")
        df = pd.read_pickle(cache_path)
    else:
        print("[API] Downloading...")
        df = yf.download(tickers, start=start, end=end, interval=interval, group_by='ticker', auto_adjust=True, progress=False, threads=False)
        df.to_pickle(cache_path)
    if df.index.tzinfo is None: df.index = df.index.tz_localize('UTC').tz_convert(JST)
    else: df.index = df.index.tz_convert(JST)
    return df

def run_backtest_session_v4(target_codes, bundle, timeline, initial_cash_val=1000000, show_trades=True, stop_mult=2.5, liquidity=100000000):
    account = {"cash": initial_cash_val}
    portfolio, trade_history, pending_exits = [], [], []
    
    print("  [Turbo V4] Simulation Loop Start...")
    start_time = time.time()
    
    for i in range(len(timeline)):
        current_time = timeline[i]
        portfolio_snap = portfolio.copy() # ループ開始時のスナップショット
        
        # 1. 決済の執行 (本日 Open)
        if pending_exits:
            new_pending = []
            for pe in pending_exits:
                ticker = f"{pe['code']}.T"
                try:
                    open_p = bundle["Open"].at[current_time, ticker]
                    if not pd.isna(open_p):
                        exec_p = max(bundle["Low"].at[current_time, ticker], open_p - max(1.0, pe['atr']*0.01))
                        gross = (exec_p - pe['buy_price']) * pe['shares']
                        tax = max(0, gross * TAX_RATE) if gross > 0 else 0
                        account['cash'] += (exec_p * pe['shares']) - tax
                        trade_history.append({
                            "code": pe['code'], "net_profit": gross - tax, "profit_pct": (exec_p/pe['buy_price']-1),
                            "buy_price": pe['buy_price'], "sell_price": exec_p, "reason": pe['reason']
                        })
                        portfolio = [p for p in portfolio if str(p['code']) != str(pe['code'])]
                        if show_trades: print(f"    [{current_time.date()}] Sell: {pe['code']} @ {exec_p:.1f} ({pe['reason']})")
                    else: new_pending.append(pe)
                except: new_pending.append(pe)
            pending_exits = new_pending

        # 2. 保有ポジション管理 (判定のみ・決済は翌営業日)
        if portfolio:
            # manage_positions_v4 内部で portfolio を更新
            portfolio, account, logs = manage_positions_v4(portfolio, account, current_time, bundle, stop_mult=stop_mult)
            for log in logs:
                # ログに Buy 情報を付与 (snapから取得)
                p_info = next(p for p in portfolio_snap if str(p['code']) == str(log['code']))
                log['buy_price'], log['buy_time'], log['atr'] = p_info['buy_price'], p_info['buy_time'], p_info['atr']
                pending_exits.append(log)

        # 3. 新規。予約執行
        for p in portfolio:
            if p.get('pending_buy') and p.get('buy_time') == current_time:
                ticker = f"{p['code']}.T"
                try:
                    buy_p = bundle["Open"].at[current_time, ticker]
                    if not pd.isna(buy_p):
                        # 実保有ポジションの資産
                        held_stock_value = sum(p_['buy_price']*p_['shares'] for p_ in portfolio if not p_.get('pending_buy'))
                        total_eq = account['cash'] + held_stock_value
                        risk_sum = total_eq * MAX_RISK_PER_TRADE
                        risk_p_sh = p['atr'] * stop_mult
                        sh = int(min(risk_sum // risk_p_sh if risk_p_sh > 0 else 100, account['cash'] // buy_p))
                        sh = (sh // 100) * 100
                        if sh >= 100:
                            p.update({"buy_price": buy_p, "shares": sh, "pending_buy": False})
                            account['cash'] -= buy_p * sh
                            if show_trades: print(f"    [{current_time.date()}] Buy: {p['code']} @ {buy_p:.1f}")
                        else: p['ignore'] = True 
                    else: p['ignore'] = True
                except: p['ignore'] = True
        
        portfolio = [p for p in portfolio if not p.get('ignore')]
        held_count = len([p for p in portfolio if not p.get('pending_buy')])
        
        # 4. 新規。スキャン
        if held_count < MAX_POSITIONS:
            candidates = select_best_candidates_v4(current_time, bundle, target_codes, min_turnover=liquidity)
            if candidates and i + 1 < len(timeline):
                best = candidates[0]
                if not any(str(p['code']) == str(best['code']) for p in portfolio):
                    portfolio.append({"code": best['code'], "buy_price": 0, "shares": 0, "buy_time": timeline[i+1], "atr": best['atr'], "pending_buy": True})

    print(f"  [Turbo V4] Simulation Done ({time.time() - start_time:.1f}s)")
    last_dt = timeline[-1]
    final_stock_val = sum(float(bundle["Close"].at[last_dt, f"{p['code']}.T"]) * p['shares'] for p in portfolio if not p.get('pending_buy'))
    total_assets = account['cash'] + final_stock_val
    return {"profit_pct": (total_assets - initial_cash_val) / initial_cash_val * 100, "trade_count": len(trade_history), "final_assets": total_assets}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--stocks', type=str, default='phase1')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--start', type=str)
    parser.add_argument('--end', type=str)
    parser.add_argument('--breakout', type=int, default=15)
    parser.add_argument('--exit', type=int, default=7)
    parser.add_argument('--liquidity', type=float, default=100000000)
    parser.add_argument('--stop_mult', type=float, default=2.5)
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    if args.all:
        df_sym = pd.read_csv(DATA_FILE)
        univ = [str(c) for i, c in enumerate(df_sym['コード']) if len(str(c)) == 4 and str(c).isdigit() and df_sym.iloc[i]['市場・商品区分'] in ['プライム（内国株式）', 'スタンダード（内国株式）', 'グロース（内国株式）']]
    else: univ = PHASE1_STOCKS
    
    full_data = get_historical_data(univ, args.start, args.end)
    bundle = calculate_all_technicals_v4(full_data, breakout_period=args.breakout, exit_period=args.exit)
    
    times = bundle["Close"].index.unique().sort_values()
    st = pd.to_datetime(args.start).tz_localize(JST) if args.start else times[0]
    en = pd.to_datetime(args.end).tz_localize(JST) if args.end else times[-1]
    timeline = times[(times >= st) & (times <= en)]
    
    res = run_backtest_session_v4(univ, bundle, timeline, show_trades=args.verbose, stop_mult=args.stop_mult, liquidity=args.liquidity)
    print(f"RESULT: Profit:{res['profit_pct']:+.2f}% Trades:{res['trade_count']}")
