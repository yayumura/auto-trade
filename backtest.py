import pandas as pd
import numpy as np
import os
import sys
import argparse
from datetime import datetime

sys.path.append(os.getcwd())
from core.config import (
    INITIAL_CASH, DATA_FILE, JST, TAX_RATE, MIN_PRICE, MAX_PRICE,
    STOCKS_TYPE, BREAKOUT_PERIOD, EXIT_PERIOD, MAX_POSITIONS, TARGET_PROFIT, STOP_LOSS_RATE
)
from core.logic import calculate_all_technicals_v12

# ============================================================
# CORE ENGINE: optimizer.py と完全同一の numpy ベースエンジン
# 月次資産トラッキングを追加
# ============================================================
def run_backtest_with_monthly(univ_indices, bundle_np, timeline, tickers_list,
                               initial_cash=1000000, max_pos=5,
                               tp=0.07, sl=0.03, time_limit=3, apply_tax=True):
    """
    optimizer.py の run_numpy_backtest_v12 と完全同一ロジック。
    月次資産トラッキングを追加した拡張版。
    """
    TAX = 0.20315
    cash = float(initial_cash)
    portfolio = []
    trade_count = 0
    annual_profit, tax_paid_this_year = 0, 0
    current_year = timeline[0].year
    monthly_assets = {}

    open_np   = bundle_np['Open']
    close_np  = bundle_np['Close']
    high_np   = bundle_np['High']
    low_np    = bundle_np['Low']
    sma20_np  = bundle_np['SMA20']
    ret3_np   = bundle_np['Ret3']
    volume_np = bundle_np['Volume']
    sma20_vol_np = bundle_np['SMA20_Vol']
    ht_np     = bundle_np['HT']

    warmup, T = 25, len(timeline)

    for i in range(warmup, T):
        curr_time = timeline[i]

        # 年次リセット
        if curr_time.year != current_year:
            annual_profit = 0
            tax_paid_this_year = 0
            current_year = curr_time.year

        # ==========================================
        # Step 1: ポジション管理 (optimizer と完全同一)
        # ==========================================
        nxt = []
        pending_cash = 0.0

        for p in portfolio:
            p['held_days'] += 1
            tidx = p['s_idx']

            if high_np[i, tidx] >= p['buy_price'] * (1 + tp):
                # TP: 即座にキャッシュ回収
                exit_p = p['buy_price'] * (1 + tp)
                realized = (exit_p - p['buy_price']) * p['shares']
                if apply_tax:
                    annual_profit += realized
                    new_tax = max(0, int(annual_profit * TAX))
                    tax_diff = new_tax - tax_paid_this_year
                    tax_paid_this_year = new_tax
                    cash += (exit_p * p['shares']) - tax_diff
                else:
                    cash += (exit_p * p['shares'])
                trade_count += 1

            elif low_np[i, tidx] <= p['buy_price'] * (1 - sl):
                # SL: 即座にキャッシュ回収
                exit_p = p['buy_price'] * (1 - sl)
                realized = (exit_p - p['buy_price']) * p['shares']
                if apply_tax:
                    annual_profit += realized
                    new_tax = max(0, int(annual_profit * TAX))
                    tax_diff = new_tax - tax_paid_this_year
                    tax_paid_this_year = new_tax
                    cash += (exit_p * p['shares']) - tax_diff
                else:
                    cash += (exit_p * p['shares'])
                trade_count += 1

            elif p['held_days'] >= time_limit:
                # タイムリミット: 翌日始値で売却 (pending_cash に積む)
                if i + 1 < T:
                    exit_p = open_np[i + 1, tidx]
                    if np.isnan(exit_p):
                        exit_p = close_np[i, tidx]
                else:
                    exit_p = close_np[i, tidx]

                realized = (exit_p - p['buy_price']) * p['shares']
                if apply_tax:
                    annual_profit += realized
                    new_tax = max(0, int(annual_profit * TAX))
                    tax_diff = new_tax - tax_paid_this_year
                    tax_paid_this_year = new_tax
                    pending_cash += (exit_p * p['shares']) - tax_diff
                else:
                    pending_cash += (exit_p * p['shares'])
                trade_count += 1

            else:
                nxt.append(p)

        portfolio = nxt

        # ==========================================
        # Step 2: スキャン & 買い (optimizer と完全同一)
        # ==========================================
        if i + 1 < T:
            idx_scan = i
            cp_u = close_np[idx_scan, univ_indices]

            valid_mask = (
                (cp_u >= MIN_PRICE) & (cp_u <= MAX_PRICE) &
                (cp_u > sma20_np[idx_scan, univ_indices]) &
                (ret3_np[idx_scan, univ_indices] > 5) &
                (volume_np[idx_scan, univ_indices] > sma20_vol_np[idx_scan, univ_indices] * 1.5) &
                (cp_u > ht_np[idx_scan, univ_indices])
            )
            valid_can_idx = univ_indices[valid_mask]

            if len(valid_can_idx) > 0 and len(portfolio) < max_pos:
                sorted_can_idx = valid_can_idx[
                    np.argsort(ret3_np[idx_scan, valid_can_idx])[::-1]
                ]
                for s_idx in sorted_can_idx:
                    if len(portfolio) >= max_pos:
                        break
                    if s_idx in [pw['s_idx'] for pw in portfolio]:
                        continue

                    total_eq = cash + sum(
                        close_np[i, p['s_idx']] * p['shares'] for p in portfolio
                    )
                    max_cap = total_eq / max_pos
                    buy_p = open_np[i + 1, s_idx]
                    if not np.isnan(buy_p):
                        sh = int(min(cash // buy_p, max_cap // buy_p))
                        sh = (sh // 100) * 100
                        if sh >= 100:
                            portfolio.append({
                                's_idx': s_idx,
                                'buy_price': buy_p,
                                'shares': sh,
                                'held_days': 0
                            })
                            cash -= float(buy_p * sh)

        # ==========================================
        # Step 3: タイムリミット売却のキャッシュ回収
        # (買いループ後に加算 → 翌日の買いで使用可能)
        # ==========================================
        cash += pending_cash

        # ==========================================
        # 月次資産記録
        # ==========================================
        is_last = (i == T - 1)
        is_month_end = (not is_last and timeline[i].month != timeline[i + 1].month)
        if is_last or is_month_end:
            hold_val = sum(close_np[i, p['s_idx']] * p['shares'] for p in portfolio)
            monthly_assets[curr_time.strftime("%Y-%m")] = cash + hold_val

    # 最終資産計算
    final_assets = cash + sum(close_np[-1, p['s_idx']] * p['shares'] for p in portfolio)
    return final_assets, trade_count, monthly_assets


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--breakout', type=int, default=BREAKOUT_PERIOD)
    parser.add_argument('--exit',     type=int, default=EXIT_PERIOD)
    parser.add_argument('--max_pos',  type=int, default=MAX_POSITIONS)
    parser.add_argument('--tp',       type=float, default=TARGET_PROFIT)
    parser.add_argument('--sl',       type=float, default=STOP_LOSS_RATE)
    args = parser.parse_args()

    # 1. ユニバース読み込み (optimizer.py と完全同一)
    from core.config import TARGET_MARKETS
    df_sym = pd.read_csv(DATA_FILE)
    univ_codes = [
        str(c) for i, c in enumerate(df_sym['コード'])
        if df_sym.iloc[i]['市場・商品区分'] in TARGET_MARKETS
    ]

    univ_cache = os.path.join("data_cache", "hist_3616stocks_2021-01-01_2026-03-29_None_1d_v4.pkl")
    if not os.path.exists(univ_cache):
        print(f"Error: Cache not found at {univ_cache}")
        sys.exit(1)

    print(f"Loading base cache: {univ_cache}")
    all_data_full = pd.read_pickle(univ_cache)

    # optimizer.py と完全同一のフィルタリング
    target_tickers = [f"{code}.T" for code in univ_codes]
    valid_tickers = [t for t in target_tickers if t in all_data_full.columns.get_level_values(0).unique()]
    all_data = all_data_full.loc[:, (valid_tickers, slice(None))]
    all_data.index = all_data.index.tz_localize('UTC').tz_convert(JST)

    print(f"Universe Size: {len(valid_tickers)} stocks (Filtered from {len(univ_codes)} initial codes)")

    # 2. テクニカル計算
    bundle_static = calculate_all_technicals_v12(all_data, breakout_p=args.breakout)
    tickers_list = bundle_static['Close'].columns.tolist()
    timeline = bundle_static["Close"].index.unique().sort_values()
    univ_indices = np.array([tickers_list.index(t) for t in valid_tickers])
    bundle_np = {k: bundle_static[k].to_numpy() for k in bundle_static}

    # 3. バックテスト実行 (NET と GROSS の両方)
    fa_net,   tc_net,   ma_net   = run_backtest_with_monthly(
        univ_indices, bundle_np, timeline, tickers_list,
        max_pos=args.max_pos, tp=args.tp, sl=args.sl, time_limit=args.exit,
        apply_tax=True
    )
    fa_gross, tc_gross, ma_gross = run_backtest_with_monthly(
        univ_indices, bundle_np, timeline, tickers_list,
        max_pos=args.max_pos, tp=args.tp, sl=args.sl, time_limit=args.exit,
        apply_tax=False
    )

    pct_net   = (fa_net   - INITIAL_CASH) / INITIAL_CASH * 100
    pct_gross = (fa_gross - INITIAL_CASH) / INITIAL_CASH * 100

    print(f"\n" + "="*80)
    print(f" FINAL PERFORMANCE SUMMARY (COMPARISON MODE)")
    print(f" Params: TP={args.tp*100:.0f}% SL={args.sl*100:.0f}% POS={args.max_pos} T={args.exit}")
    print(f"="*80)
    print(f" {'METRIC':<20} | {'GROSS (TAX-FREE)':>25} | {'NET (PRODUCTION)':>25}")
    print(f" {'-'*20} + {'-'*25} + {'-'*25}")
    print(f" {'Total Profit (%)':<20} | {pct_gross:>+24.2f}% | {pct_net:>+24.2f}%")
    print(f" {'Final Assets (JPY)':<20} | {int(fa_gross):>25,d} | {int(fa_net):>25,d}")
    print(f" {'Total Trades':<20} | {tc_gross:>25} | {tc_net:>25}")
    print(f"="*80)

    print("\nMONTHLY ASSET COMPARISON (NET vs GROSS)")
    print("-" * 84)
    print(f" {'MONTH':<10} | {'NET ASSET (JPY)':>20} | {'GROSS ASSET (JPY)':>20} | {'DIFF (NET-GROSS)':>22}")
    print("-" * 84)
    for month in sorted(ma_net.keys()):
        na = ma_net[month]
        ga = ma_gross.get(month, 0)
        diff = na - ga
        print(f" {month:<10} | {int(na):>20,d} | {int(ga):>20,d} | {int(diff):>+22,d}")
    print("-" * 84 + "\n")
