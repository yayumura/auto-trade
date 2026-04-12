import unittest
import pandas as pd
import numpy as np
from core.logic import calculate_all_technicals_v12

class TestLogic(unittest.TestCase):
    def test_calculate_all_technicals_v12_mean_reversion(self):
        # Create a mock dataframe
        dates = pd.date_range("2024-01-01", periods=30)
        tickers = ["1000.T", "1321.T"]
        
        # MultiIndex columns setup similar to application
        columns = pd.MultiIndex.from_tuples(
            [(t, f) for t in tickers for f in ["Close", "High", "Low", "Open", "Volume"]]
        )
        data = np.random.randn(30, len(columns)) * 5 + 100
        df = pd.DataFrame(data, index=dates, columns=columns)
        
        bundle = calculate_all_technicals_v12(df)
        
        # Assert indicators exist
        self.assertIn('RSI2', bundle)
        self.assertIn('BB_LOWER_2', bundle)
        
        # Verify RSI calculation values (values between 0 and 100)
        rsi_vals = bundle['RSI2'].values
        valid_rsi = rsi_vals[~np.isnan(rsi_vals)]
        if len(valid_rsi) > 0:
            self.assertTrue(np.all((valid_rsi >= 0) & (valid_rsi <= 100)))

        # Verify Bollinger Bands calculations
        valid_bb = bundle['BB_LOWER_2'].values[~np.isnan(bundle['BB_LOWER_2'].values)]
        self.assertTrue(len(valid_bb) > 0)

if __name__ == '__main__':
    unittest.main()
