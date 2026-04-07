import numpy as np
import pandas as pd
from backtest import run_backtest_v16_production

def test_dynamic_reversion_exit_sma5():
    """
    SMA5上抜けテスト:
    エントリー後のポジションにおいて、ある日の close_np > sma5_np になった場合、
    翌日（次のiteration）にエグジットされることを確認する。
    """
    T = 110
    dates = pd.date_range("2024-01-01", periods=T)
    num_tickers = 1
    
    # 基本的に価格が下がり続けるが、105日目にSMA5を上抜ける設定
    close_data = np.linspace(100, 90, T).reshape(T, 1)
    close_data[105, 0] = 95 # 急激な反発
    
    sma5_data = np.linspace(105, 95, T).reshape(T, 1)
    sma5_data[105, 0] = 92 # SMA5は92なので、Close(95) > SMA5(92) となる
    
    # エントリーさせるため、101日目に強烈な売られすぎを設定
    rsi2_data = np.zeros((T, 1)) + 50
    rsi2_data[101, 0] = 5  # RSI < 10 (Panic)
    close_data[101, 0] = 80
    bb_lower_data = np.zeros((T, 1)) + 90 # Close(80) < BB_LOWER(90)
    sma100_data = np.zeros((T, 1)) + 50 # UPTREND
    
    bundle_np = {
        'Close': close_data,
        'Open': close_data, # Open=Close for simplicity
        'High': close_data + 5,
        'Low': close_data - 5,
        'SMA5': sma5_data,
        'SMA20': np.zeros((T, 1)),
        'SMA100': sma100_data,
        'ATR': np.ones((T, 1)) * 2,
        'RSI2': rsi2_data,
        'BB_LOWER_2': bb_lower_data,
        'tickers': ["1000.T"]
    }
    
    univ_indices = np.arange(num_tickers)
    breadth_ratio = np.ones(T) * 0.5
    
    # 実行
    final_assets, trade_count, monthly, results = run_backtest_v16_production(
        univ_indices=univ_indices,
        bundle_np=bundle_np,
        timeline=dates,
        breadth_ratio=breadth_ratio,
        initial_cash=10000000,
        max_pos=1,
        sl_mult=10.0, # SLにかからないように広く
        tp_mult=10.0, # TPにかからないように広く
        leverage_rate=1.0,
        breadth_threshold=0.3,
        max_hold_days=10 # タイムストップにかからないように長く
    )
    
    # i=101でシグナル、i=102買（約定）、i=105でSMA5上抜け判定、i=106売
    assert trade_count == 1, f"Expected 1 trade, got {trade_count}"


def test_dynamic_reversion_exit_rsi2():
    """
    RSI2過熱テスト:
    エントリー後のポジションにおいて、ある日の rsi2_np > 70 になった場合、
    翌日（次のiteration）にエグジットされることを確認する。
    """
    T = 110
    dates = pd.date_range("2024-01-01", periods=T)
    num_tickers = 1
    
    close_data = np.linspace(100, 90, T).reshape(T, 1)
    sma5_data = np.linspace(105, 95, T).reshape(T, 1) # SMA5上抜けはしない
    
    rsi2_data = np.zeros((T, 1)) + 50
    rsi2_data[101, 0] = 5  # RSI < 10 (Panic) -> エントリートリガー
    rsi2_data[105, 0] = 80 # RSI > 70 (Overbought) -> エグジットトリガー
    
    close_data[101, 0] = 80
    bb_lower_data = np.zeros((T, 1)) + 90 # Close(80) < BB_LOWER(90)
    sma100_data = np.zeros((T, 1)) + 50 # UPTREND
    
    bundle_np = {
        'Close': close_data,
        'Open': close_data,
        'High': close_data + 5,
        'Low': close_data - 5,
        'SMA5': sma5_data, # SMA5は遠いままなので条件満たさない
        'SMA20': np.zeros((T, 1)),
        'SMA100': sma100_data,
        'ATR': np.ones((T, 1)) * 2,
        'RSI2': rsi2_data,
        'BB_LOWER_2': bb_lower_data,
        'tickers': ["1000.T"]
    }
    
    univ_indices = np.arange(num_tickers)
    breadth_ratio = np.ones(T) * 0.5
    
    final_assets, trade_count, monthly, results = run_backtest_v16_production(
        univ_indices=univ_indices,
        bundle_np=bundle_np,
        timeline=dates,
        breadth_ratio=breadth_ratio,
        initial_cash=10000000,
        max_pos=1,
        sl_mult=10.0,
        tp_mult=10.0,
        leverage_rate=1.0,
        breadth_threshold=0.3,
        max_hold_days=10
    )
    
    assert trade_count == 1, f"Expected 1 trade, got {trade_count}"
