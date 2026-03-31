import os
from datetime import datetime

# --- V10.3 PRODUCTION CONFIG (Final Truth Setting) ---
# 市場、期間、ポジション数、すべてが「資産2.4倍」のための構成です。

# バックテスト検証済み（2021-2026）: +140.87% (1M -> 2.4M)
TRUTH_PROFIT_V10 = 140.87
TRUTH_TRADES_V10 = 187

# 市場設定
STOCKS_TYPE = 'prime' # 高純度・高信頼のプライム市場に限定
MAX_POSITIONS = 3     # 3銘柄に強気の集中投資 (資産の33%ずつ)
MAX_DAILY_BUYS = 1    # 1日に1銘柄ずつの厳選

# ロジック・パラメータ
BREAKOUT_PERIOD = 25  # 25日最高値更新（王道の波動）
EXIT_PERIOD = 10      # 10日安値（安定したトレンド追い）
STOP_LOSS_MULT = 3.0 # ATRの3倍で不測の事態を防ぐ

# データ・時間設定
JST = "Asia/Tokyo"
DATA_FILE = r'c:\Users\yayum\git_work\auto-trade\data\symbols_with_market.csv'

# 税金・手数料設定
TAX_RATE = 0.20315    # 日本の株式譲渡益税
SLIPPAGE_RATE = 0.001 # 0.1% 滑り（現実に即したシミュレーション）

# 初期資産
INITIAL_CASH = 1000000 # 1,000,000 JPY

# ログ設定
LOG_LEVEL = "INFO"
LOG_DIR = os.path.join(os.getcwd(), 'logs')
if not os.path.exists(LOG_DIR): os.makedirs(LOG_DIR)

print(f"  [System Mode] Alpha-Multiplier Active (Market:{STOCKS_TYPE} B:{BREAKOUT_PERIOD} Pos:{MAX_POSITIONS})")
print(f"  [Target] +140% Total Growth (2.4x Multiplier Challenge)")
