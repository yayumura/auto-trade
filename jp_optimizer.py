import pandas as pd
import numpy as np
import os
import sys
import concurrent.futures
import pickle

# Append current directory to sys.path
sys.path.append(os.getcwd())
from core.logic import calculate_all_technicals_v12
from backtest import run_backtest_v16_production
from core.logic import get_prime_tickers
from core.config import (
    INITIAL_CASH, EXIT_ON_SMA20_BREACH, SMA20_EXIT_BUFFER, LIQUIDITY_LIMIT_RATE,
    BULL_GAP_LIMIT, BEAR_GAP_LIMIT, SMA_LONG_PERIOD,
    SLIPPAGE
)

def calculate_stability_metrics(final_assets, trade_results, monthly_assets, initial_cash):
    """
    ロバスト性評価関数（Stability Score）
    1. 月次勝率 (MWR): 40%
    2. シャープレシオ (SR): 30%
    3. プロフィットファクター (PF): 20%
    4. 最大ドローダウン (MDD) ペナルティ: -10%〜
    """
    if not trade_results or len(trade_results) < 10:
        return {"mwr": 0, "pf": 0, "sharpe": 0, "mdd": 100, "win_rate": 0, "score": -9999}

    # --- 基本統計 ---
    wins = [r for r in trade_results if r > 0]
    losses = [r for r in trade_results if r < 0]
    win_rate = len(wins) / len(trade_results)
    
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    pf = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)
    
    # --- 月次リターンと安定性 ---
    if not monthly_assets:
        return {"mwr": 0, "pf": pf, "sharpe": 0, "mdd": 100, "win_rate": win_rate, "score": -9999}
        
    sorted_months = sorted(monthly_assets.keys())
    equities = [initial_cash] + [monthly_assets[m] for m in sorted_months]
    monthly_returns = []
    for i in range(1, len(equities)):
        prev = equities[i-1]
        m_ret = (equities[i] / prev - 1.0) if prev > 0 else 0
        monthly_returns.append(m_ret)
    
    m_returns_np = np.array(monthly_returns)
    mwr = np.mean(m_returns_np > 0) if len(m_returns_np) > 0 else 0
    
    # シャープレシオ (年率換算。簡略化のため月次ベース)
    mean_ret = np.mean(m_returns_np)
    std_ret = np.std(m_returns_np)
    sharpe = (mean_ret / std_ret) * (12**0.5) if std_ret > 0 else 0
    
    # 最大ドローダウン (資産推移から算出)
    running_max = np.maximum.accumulate(equities)
    drawdowns = (running_max - equities) / running_max
    mdd_pct = np.max(drawdowns) * 100
    
    # --- 制約フィルター (足切り) ---
    # 取引回数 100回未満, 勝率 50%未満, PF 1.2未満は失格
    MIN_TRADES = 100
    MIN_WIN_RATE = 0.50
    MIN_PF = 1.2
    
    trade_count = len(trade_results)
    if trade_count < MIN_TRADES or win_rate < MIN_WIN_RATE or pf < MIN_PF:
        # スコアを大幅に下げつつ、比較のために数値を保持
        return {
            "mwr": mwr, "pf": pf, "sharpe": sharpe, "mdd": mdd_pct, "win_rate": win_rate, 
            "score": -10000 + (trade_count / 100.0) # 順位は取引回数順にする
        }
    
    # --- スコア算定式 (ロバスト性重視) ---
    # 月次勝率(0-1)を500倍, Sharpe(0-4)を100倍, PF(0-3)を50倍程度で重み付け
    # MDDが20%を超えると急激に減点
    score = (mwr * 500) + (min(max(sharpe, 0), 4) * 100) + (min(pf, 3) * 50)
    
    # ドローダウンペナルティ
    mdd_penalty = mdd_pct * 5.0
    if mdd_pct > 20.0:
        mdd_penalty += (mdd_pct - 20.0) * 20.0 # 20%超えは厳罰
    
    score -= mdd_penalty
    
    return {
        "mwr": mwr, "pf": pf, "sharpe": sharpe, "mdd": mdd_pct, "win_rate": win_rate, "score": score
    }

def run_single_opt(params_pack):
    univ_indices, bundle_np, timeline, breadth_ratio, p = params_pack
    # --- Concentrated Elite Mode (V89.0) ---
    final_assets, trade_count, monthly_assets, trade_results = run_backtest_v16_production(
        univ_indices=univ_indices,
        bundle_np=bundle_np,
        timeline=timeline,
        breadth_ratio=breadth_ratio,
        initial_cash=INITIAL_CASH,
        max_pos=p['max_pos'],
        sl_mult=p['sl'],
        tp_mult=p['tp'],
        leverage_rate=p['leverage'],
        breadth_threshold=p['breadth'],
        max_hold_days=p['max_hold_days'],
        slippage=SLIPPAGE,
        use_sma_exit=EXIT_ON_SMA20_BREACH, 
        exit_buffer=p['exit_buffer'],
        liquidity_limit=LIQUIDITY_LIMIT_RATE,
        bull_gap_limit=p['bgap'],
        bear_gap_limit=BEAR_GAP_LIMIT,
        atr_trail_mult=p['atr_trail'],
        rsi_threshold=p['rsi_th'],
        use_trailing_stop=p['use_trail'],
        individual_trend_sma=p['trend_sma'],
        market_trend_sma_period=p['mkt_trend_sma']
    )
    
    # 安定性スコアの計算
    metrics = calculate_stability_metrics(final_assets, trade_results, monthly_assets, INITIAL_CASH)
    
    return {**p, "final": final_assets, "trades": trade_count, **metrics}

def optimize_jp_imperial(cache_path):
    print(f"Loading JP Mega-Data Cache: {cache_path}")
    with open(cache_path, 'rb') as f:
        all_data = pickle.load(f)

    new_cols = []
    for col in all_data.columns:
        ticker, field = col[0], col[1]
        if isinstance(field, tuple):
            field = field[0]
        new_cols.append((ticker, field))
    all_data.columns = pd.MultiIndex.from_tuples(new_cols)

    bundle = {
        'Open': all_data.xs('Open', axis=1, level=1),
        'High': all_data.xs('High', axis=1, level=1),
        'Low': all_data.xs('Low', axis=1, level=1),
        'Close': all_data.xs('Close', axis=1, level=1),
        'Volume': all_data.xs('Volume', axis=1, level=1)
    }
    
    indicator_bundle = calculate_all_technicals_v12(all_data)
    bundle.update(indicator_bundle)
    
    tickers = bundle['Close'].columns.tolist()
    prime_ref = get_prime_tickers()
    elite_indices = [i for i, t in enumerate(tickers) if t in prime_ref]
    
    breadth_matrix = bundle['Close'].values[:, elite_indices] > bundle[f'SMA{SMA_LONG_PERIOD}'].values[:, elite_indices]
    breadth_series = np.nanmean(breadth_matrix.astype(float), axis=1)
    
    univ_indices = np.array([i for i, t in enumerate(tickers) if t not in {'1306.T', '1321.T'}], dtype=int)
    bundle_np = {k: v.values for k, v in bundle.items()}
    bundle_np['tickers'] = list(tickers)
    timeline = bundle['Close'].index
    
    # --- Aggressive Mean Reversion Search ---
    
    # --- V17 Sovereign Trend Grid (Momentum Persistence) ---
    param_grid = {
        'sl_mult': [3.0, 5.0],
        'tp_mult': [20.0, 40.0],
        'rsi_th': [30, 50, 70],
        'trend_sma': [200],         # 個別銘柄長期線
        'mkt_trend_sma': [50, 100], # 【新】市場環境線
        'use_trail': [False, True],
        'atr_trail': [3.0, 5.0],
        'leverage_rate': [1.0],
        'bull_gap_limit': [0.11],
        'max_hold_days': [30]
    }

    grid = []
    for sl in param_grid['sl_mult']:          
        for tp in param_grid['tp_mult']:
            for rsi_th in param_grid['rsi_th']:
                for m_sma in param_grid['mkt_trend_sma']:
                    for u_trail in param_grid['use_trail']:
                        grid.append({
                            "breadth": 0.5, "exit_buffer": 0.975,
                            "sl": sl, "tp": tp, 
                            "atr_trail": 5.0, "rsi_th": rsi_th,
                            "trend_sma": 200, "mkt_trend_sma": m_sma,
                            "use_trail": u_trail,
                            "max_pos": 3, "leverage": 1.0, 
                            "bgap": 0.11, "max_hold_days": 30
                        })
    
    print(f"[CONCENTRATED_OPT] Starting Grid Search ({len(grid)} combinations)...")

    
    results = []
    with concurrent.futures.ProcessPoolExecutor() as executor:
        tasks = []
        for p in grid:
            tasks.append((univ_indices, bundle_np, timeline, breadth_series, p))
        results = list(executor.map(run_single_opt, tasks))
    
    df_res = pd.DataFrame(results)
    df_res['return_pct'] = (df_res['final'] / INITIAL_CASH - 1) * 100
    
    # 安定性スコアでソート
    df_res = df_res.sort_values('score', ascending=False)
    
    # 読みやすいように列を整理
    display_cols = [
        'score', 'return_pct', 'trades', 'win_rate', 'mwr', 'pf', 'sharpe', 'mdd',
        'sl', 'tp', 'rsi_th', 'mkt_trend_sma', 'use_trail'
    ]
    # 出力用の一時的なデータフレームを作成
    df_display = df_res[[c for c in display_cols if c in df_res.columns]].copy()
    
    # CSV保存 (全てのカラムを保持)
    df_res.to_csv("opt_results.csv", index=False)
    
    print("\n" + "="*120)
    print(f"STABILITY-DRIVEN OPTIMIZATION RESULTS (Top 30)")
    print("="*120)
    # フォーマット調整して表示
    print(df_display.head(30).to_string(index=False, formatters={
        'score': '{:,.1f}'.format,
        'return_pct': '{:,.1f}%'.format,
        'win_rate': '{:.1%}'.format,
        'mwr': '{:.1%}'.format,
        'pf': '{:.2f}'.format,
        'sharpe': '{:.2f}'.format,
        'mdd': '{:.1f}%'.format,
        'bgap': '{:.1%}'.format
    }))
    print("="*120 + "\n")
    
    best = df_res.iloc[0]
    if best['score'] < 0:
        print("⚠️ WARNING: No candidates passed all standard filters (Trades >= 100, WinRate >= 50%, PF >= 1.2)")
    
    print(f"BEST STABILITY CONFIGURATION:")
    print(f" - Stability Score:   {best['score']:.1f}")
    print(f" - Monthly Win Rate:  {best['mwr']:.1%}")
    print(f" - Sharpe Ratio:      {best['sharpe']:.2f}")
    print(f" - Profit Factor:     {best['pf']:.2f}")
    print(f" - Max Drawdown:      {best['mdd']:.1f}%")
    print("-" * 30)
    print(f" - Max Positions:     {best['max_pos']:.0f}")
    print(f" - Breadth Threshold: {best['breadth']:.2f}")
    print(f" - SMA20 Exit Buffer: {best['exit_buffer']:.3f}")
    print(f" - Stop Loss:         ATR * {best['sl']}")
    print(f" - Profit Target:     ATR * {best['tp']}")
    print(f" - BULL Gap Limit:    {best['bgap']:.2%}")
    print(f" - Leverage:          {best['leverage']}x")
    print(f"Estimated Return:     {best['return_pct']:+.2f}% ({best['trades']} trades)")
    print("="*120)


if __name__ == "__main__":
    if not os.path.exists("data_cache"):
        print("❌ Error: Please run from the project root directory.")
        sys.exit(1)
        
    optimize_jp_imperial("data_cache/jp_broad/jp_mega_cache.pkl")
