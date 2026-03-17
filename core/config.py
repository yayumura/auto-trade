import os
from dotenv import load_dotenv

# --- Base Directories ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, 'logs')

# --- File Paths ---
DATA_FILE = os.path.join(BASE_DIR, 'data_j.csv')
PORTFOLIO_FILE = os.path.join(BASE_DIR, 'virtual_portfolio.csv')
HISTORY_FILE = os.path.join(BASE_DIR, 'trade_history.csv')
ACCOUNT_FILE = os.path.join(BASE_DIR, 'account.json')
EXECUTION_LOG_FILE = os.path.join(BASE_DIR, 'execution_log.csv') 
EXCLUSION_CACHE_FILE = os.path.join(BASE_DIR, 'invalid_tickers.json')

# --- API Keys ---
load_dotenv(os.path.join(BASE_DIR, '.env'))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
GEMINI_MODEL = "gemini-2.5-flash"

KABUCOM_API_PASSWORD = os.environ.get("KABUCOM_API_PASSWORD")
# TRADE_MODE: "SIMULATION" or "KABUCOM_TEST" or "KABUCOM_LIVE"
TRADE_MODE = os.environ.get("TRADE_MODE", "SIMULATION")

# --- Strategy Parameters ---
DEBUG_MODE = False        # 本番運用時は必ずFalse
INITIAL_CASH = 1000000    # 初回シミュレーション用資金
MAX_POSITIONS = 4         # リスク分散上限
MAX_RISK_PER_TRADE = 0.02 # 1トレードあたりの許容リスク（総資金の2%）
MAX_ALLOCATION_PCT = 0.30 # 1銘柄あたりの最大投資比率（30%）
MIN_ALLOCATION_AMOUNT = 200000 # 少額資金時の最低投資保証額（20万円）
TAX_RATE = 0.20315        # 約20.3%

# --- Market Filters ---
TARGET_MARKETS = ['プライム（内国株式）', 'スタンダード（内国株式）', 'グロース（内国株式）']

# --- Target Exits ---
ATR_STOP_LOSS = 2.0       # 絶対損切(ATRの2倍) - BULL用
RANGE_ATR_STOP_LOSS = 3.0 # RANGEレジーム用の緩めの損切
ATR_TRAIL = 1.5           # トレール利確(最高値からATRの1.5倍)
