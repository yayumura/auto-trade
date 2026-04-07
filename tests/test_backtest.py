import unittest
import numpy as np
import pandas as pd
from backtest import run_backtest_v16_production

class TestBacktest(unittest.TestCase):
    def test_run_backtest_mean_reversion(self):
        T = 150
        dates = pd.date_range("2024-01-01", periods=T)
        num_tickers = 5
        
        bundle_np = {
            'Close': np.random.randn(T, num_tickers).cumsum(axis=0) + 100,
            'Open': np.random.randn(T, num_tickers).cumsum(axis=0) + 100,
            'High': np.random.randn(T, num_tickers).cumsum(axis=0) + 105,
            'Low': np.random.randn(T, num_tickers).cumsum(axis=0) + 95,
            'SMA5': np.zeros((T, num_tickers)),
            'SMA20': np.zeros((T, num_tickers)),
            'SMA100': np.zeros((T, num_tickers)) + 90, # UPTREND
            'ATR': np.ones((T, num_tickers)) * 2,
            'RSI2': np.zeros((T, num_tickers)) + 5,    # OVERSOLD (Panic)
            'BB_LOWER_2': np.zeros((T, num_tickers)) + 110, # Current Close < BB_LOWER_2
            'tickers': [f"{1000+i}.T" for i in range(num_tickers)]
        }
        
        univ_indices = np.arange(num_tickers)
        timeline = dates
        breadth_ratio = np.ones(T) * 0.5
        
        # Execute customized short swing backtest logic
        final_assets, trade_count, monthly, results = run_backtest_v16_production(
            univ_indices=univ_indices,
            bundle_np=bundle_np,
            timeline=timeline,
            breadth_ratio=breadth_ratio,
            initial_cash=10000000,
            max_pos=3,
            sl_mult=1.0,
            tp_mult=2.0,
            leverage_rate=2.0,
            breadth_threshold=0.3,
            max_hold_days=4
        )
        
        # Verify valid end results
        self.assertTrue(final_assets > 0)
        self.assertTrue(isinstance(trade_count, int))

if __name__ == '__main__':
    unittest.main()
