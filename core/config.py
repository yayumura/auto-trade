import os
from datetime import datetime
from dotenv import load_dotenv

# プロジェクトルートのパス取得 (.env を読み込むため)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

# ==========================================
# V10.5 PRODUCTION CONFIG (Unified)
# ==========================================

# 成果実績 (Backtest 2021-2026)
TRUTH_PROFIT_V10 = 200.06
TRUTH_TRADES_V10 = 316

# --- 運用パラメータ (V11.0 Ultimate Winner Optimized) ---
STOCKS_TYPE = "prime"      # ターゲット市場 (prime)
if STOCKS_TYPE == "prime":
    TARGET_MARKETS = ["プライム（内国株式）"]
elif STOCKS_TYPE == "standard":
    TARGET_MARKETS = ["スタンダード（内国株式）"]
elif STOCKS_TYPE == "growth":
    TARGET_MARKETS = ["グロース（内国株式）"]
else:
    TARGET_MARKETS = ["プライム（内国株式）"]

BREAKOUT_PERIOD = 30       # 最強の30日ブレイク (V11.1 Ultimate Winner)
EXIT_PERIOD = 10           # 10日安値エグジット (Quick Recovery)
MAX_POSITIONS = 2          # 2銘柄集中投資 (Concentration Alpha)
OVERHEAT_THRESHOLD = 25.0  # 乖離率25.0%まで制限 (Safety Edge)
MAX_DAILY_BUYS = 5

# ロジック・パラメータ
STOP_LOSS_MULT = 3.0
ATR_STOP_LOSS = 3.0
RANGE_ATR_STOP_LOSS = 2.0
MAX_RISK_PER_TRADE = 0.05  # リスク許容度を5%に引き上げ (33%配分を妨げないための調整)
MAX_ALLOCATION_PCT = 0.50   # 1銘柄最大50%まで (分散2銘柄で資金を使い切る設定)
MIN_ALLOCATION_AMOUNT = 100000

# 動作モード (環境変数から取得、なければデフォルト)
DEBUG_MODE = False
TRADE_MODE = os.getenv("TRADE_MODE", "SIMULATION") # or "KABUCOM_LIVE", "KABUCOM_TEST"

# データ・時間設定
from zoneinfo import ZoneInfo
JST = ZoneInfo("Asia/Tokyo")
BASE_DATA_DIR = os.path.join(BASE_DIR, 'data') # データの大元
DATA_ROOT = BASE_DATA_DIR # preflight.py 互換用

# モードごとにデータ保存先を分ける
if TRADE_MODE == "KABUCOM_LIVE":
    DATA_DIR = os.path.join(BASE_DATA_DIR, 'kabucom_live')
elif TRADE_MODE == "KABUCOM_TEST":
    DATA_DIR = os.path.join(BASE_DATA_DIR, 'kabucom_test')
else:
    DATA_DIR = os.path.join(BASE_DATA_DIR, 'simulation')

if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)

DATA_ROOT = DATA_DIR # preflight.py 互換用

DATA_FILE = os.path.join(BASE_DIR, 'data_j.csv')
PORTFOLIO_FILE = os.path.join(DATA_DIR, 'virtual_portfolio.csv')
HISTORY_FILE = os.path.join(DATA_DIR, 'trade_history.csv')
ACCOUNT_FILE = os.path.join(DATA_DIR, 'account.json')
EXECUTION_LOG_FILE = os.path.join(DATA_DIR, 'execution_log.csv')
EXCLUSION_CACHE_FILE = os.path.join(DATA_DIR, 'invalid_tickers.json')

# 外部API (環境変数から取得)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
KABUCOM_API_PASSWORD = os.getenv("KABUCOM_API_PASSWORD", "")
KABUCOM_LOGIN_PASSWORD = os.getenv("KABUCOM_LOGIN_PASSWORD", "")
GEMINI_MODEL = "gemini-1.5-flash"

# ロジック追加パラメータ
ATR_TRAIL = 3.0

# 税金・手数料設定
TAX_RATE = 0.20315
SLIPPAGE_RATE = 0.001

# 初期資産
INITIAL_CASH = 1000000

# ログ設定
LOG_LEVEL = "INFO"
LOG_DIR = os.path.join(DATA_DIR, 'logs')
if not os.path.exists(LOG_DIR): os.makedirs(LOG_DIR)

def load_insider_exclusion_codes():
    import json
    path = os.path.join(BASE_DIR, 'insider_exclusion.json')
    if os.path.exists(path):
        try:
            with open(path, 'r') as f: return json.load(f).get('codes', [])
        except: return []
    return []

print(f"  [System Mode] Alpha-Multiplier Active (Market:{STOCKS_TYPE} B:{BREAKOUT_PERIOD} Pos:{MAX_POSITIONS})")
print(f"  [Target] +200% Growth Path (V10.5 Momentum Engine Ready)")
