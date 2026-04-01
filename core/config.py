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

# --- 運用パラメータ (V10.8 Absolute Champion Optimized) ---
STOCKS_TYPE = "prime"      # ターゲット市場 (prime)
BREAKOUT_PERIOD = 25       # 最強の25日ブレイク
EXIT_PERIOD = 10           # 安定の10日安値割れ
MAX_POSITIONS = 3          # 爆発力を高める3銘柄集中投資
OVERHEAT_THRESHOLD = 25.0  # 厳格な高値掴み防止
MAX_DAILY_BUYS = 5

# ロジック・パラメータ
STOP_LOSS_MULT = 3.0
ATR_STOP_LOSS = 3.0
RANGE_ATR_STOP_LOSS = 2.0
MAX_RISK_PER_TRADE = 0.01
MAX_ALLOCATION_PCT = 0.20
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
LOG_DIR = os.path.join(BASE_DIR, 'logs')
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
