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
    
    # エントリーシグナルを発生させるための調整 (i=101)
    # is_white_candle: Close > Open
    # is_rebound: (Close - Low) / (High - Low) >= 0.6
    close_data[101, 0] = 82
    open_data = close_data.copy()
    open_data[101, 0] = 81 # 陽線
    high_data = close_data + 1
    low_data = close_data - 2
    # Result: (82 - 80) / (83 - 80) = 2/3 = 0.666 >= 0.6
    
    bundle_np = {
        'Close': close_data,
        'Open': open_data,
        'High': high_data,
        'Low': low_data,
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
    
    assert trade_count == 1, f"Expected 1 trade, got {trade_count}"


def test_dynamic_reversion_exit_failed_bounce():
    """
    Fast Cutテスト:
    エントリーから2日経過しても含み損（Close < BuyPrice）の場合、
    翌日にエグジットされることを確認する。
    """
    T = 110
    dates = pd.date_range("2024-01-01", periods=T)
    num_tickers = 1
    
    # ずっと価格が下がり続ける設定
    close_data = np.linspace(100, 70, T).reshape(T, 1)
    
    # 101日目にシグナル（パニック売り + 反発確認）
    rsi2_data = np.zeros((T, 1)) + 50
    rsi2_data[101, 0] = 5 # RSI < 10
    close_data[101, 0] = 80 # 急落
    open_data = close_data.copy()
    open_data[101, 0] = 85 # 陰線ではないよう調整
    high_data = close_data + 10
    low_data = close_data - 2
    
    # 反発サインを満たすように調整 (is_white_candle & is_rebound)
    # c=82, o=81, h=83, l=80 -> (82-80)/(83-80) = 2/3 = 0.66 >= 0.6
    close_data[101, 0] = 82
    open_data[101, 0] = 81
    high_data[101, 0] = 83
    low_data[101, 0] = 80
    
    bb_lower_data = np.zeros((T, 1)) + 90
    sma100_data = np.zeros((T, 1)) + 50
    
    bundle_np = {
        'Close': close_data,
        'Open': open_data,
        'High': high_data,
        'Low': low_data,
        'SMA5': np.zeros((T, 1)) + 200, # SMA5は遠くに設定
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
    
    # i=101シグナル, i=102買成立, i=103(1日目), i=104(2日目: 含み損継続), i=105売
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
    
    # 反発シグナルの生成 (i=101)
    close_data[101, 0] = 82
    open_data = close_data.copy()
    open_data[101, 0] = 81
    high_data = close_data + 1
    low_data = close_data - 2

    bundle_np = {
        'Close': close_data,
        'Open': open_data,
        'High': high_data,
        'Low': low_data,
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
