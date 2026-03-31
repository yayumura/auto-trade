import os
from datetime import datetime

# ==========================================
# V10.5 PRODUCTION CONFIG (Unified)
# ==========================================

# 成果実績 (Backtest 2021-2026)
TRUTH_PROFIT_V10 = 200.06
TRUTH_TRADES_V10 = 316

# 市場設定
STOCKS_TYPE = 'prime'
TARGET_MARKETS = ['プライム（内国株式）', 'スタンダード（内国株式）'] # 拡大の余地あり
MAX_POSITIONS = 5
MAX_DAILY_BUYS = 5

# ロジック・パラメータ
BREAKOUT_PERIOD = 20
EXIT_PERIOD = 10
STOP_LOSS_MULT = 3.0
ATR_STOP_LOSS = 3.0
RANGE_ATR_STOP_LOSS = 2.0
MAX_RISK_PER_TRADE = 0.01
MAX_ALLOCATION_PCT = 0.20
MIN_ALLOCATION_AMOUNT = 100000

# 動作モード
DEBUG_MODE = False
TRADE_MODE = "SIMULATION" # or "KABUCOM_LIVE", "KABUCOM_TEST"

# データ・時間設定
JST = "Asia/Tokyo"
DATA_DIR = os.path.join(os.getcwd(), 'data', 'simulation')
if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)

DATA_FILE = r'c:\Users\yayum\git_work\auto-trade\data\symbols_with_market.csv'
PORTFOLIO_FILE = os.path.join(DATA_DIR, 'virtual_portfolio.csv')
HISTORY_FILE = os.path.join(DATA_DIR, 'trade_history.csv')
ACCOUNT_FILE = os.path.join(DATA_DIR, 'account.json')
EXECUTION_LOG_FILE = os.path.join(DATA_DIR, 'execution_log.csv')
EXCLUSION_CACHE_FILE = os.path.join(DATA_DIR, 'invalid_tickers.json')

# 外部API (環境変数から取得)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
GEMINI_MODEL = "gemini-1.5-flash"

# 税金・手数料設定
TAX_RATE = 0.20315
SLIPPAGE_RATE = 0.001

# 初期資産
INITIAL_CASH = 1000000

# ログ設定
LOG_LEVEL = "INFO"
LOG_DIR = os.path.join(os.getcwd(), 'logs')
if not os.path.exists(LOG_DIR): os.makedirs(LOG_DIR)

def load_insider_exclusion_codes():
    import json
    path = os.path.join(os.getcwd(),'insider_exclusion.json')
    if os.path.exists(path):
        try:
            with open(path, 'r') as f: return json.load(f).get('codes', [])
        except: return []
    return []

print(f"  [System Mode] Alpha-Multiplier Active (Market:{STOCKS_TYPE} B:{BREAKOUT_PERIOD} Pos:{MAX_POSITIONS})")
print(f"  [Target] +200% Growth Path (V10.5 Momentum Engine Ready)")
