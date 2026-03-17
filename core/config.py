import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# --- Timezone ---
JST = timezone(timedelta(hours=9))

# --- Base Directories ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- Mode-Specific Data Directories ---
# TRADE_MODE: "SIMULATION" or "KABUCOM_TEST" or "KABUCOM_LIVE"
load_dotenv(os.path.join(BASE_DIR, '.env'))
TRADE_MODE = os.environ.get("TRADE_MODE", "SIMULATION")

# モードごとに保存先フォルダを分ける
mode_dir_map = {
    "SIMULATION": "simulation",
    "KABUCOM_TEST": "kabucom_test",
    "KABUCOM_LIVE": "kabucom_live"
}
MODE_SUBDIR = mode_dir_map.get(TRADE_MODE, "simulation")
DATA_ROOT = os.path.join(BASE_DIR, 'data', MODE_SUBDIR)
os.makedirs(DATA_ROOT, exist_ok=True)

# ログディレクトリもモード別に分ける
LOG_DIR = os.path.join(DATA_ROOT, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)



# --- File Paths (Mode Specific) ---
DATA_FILE = os.path.join(BASE_DIR, 'data_j.csv') # これは全モード共通
ACCOUNT_FILE = os.path.join(DATA_ROOT, 'account.json')
PORTFOLIO_FILE = os.path.join(DATA_ROOT, 'virtual_portfolio.csv')
HISTORY_FILE = os.path.join(DATA_ROOT, 'trade_history.csv')
EXECUTION_LOG_FILE = os.path.join(DATA_ROOT, 'execution_log.csv') 
EXCLUSION_CACHE_FILE = os.path.join(DATA_ROOT, 'invalid_tickers.json')

# --- API Keys & Webhooks ---
KABUCOM_API_PASSWORD = os.environ.get("KABUCOM_API_PASSWORD")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# --- Models ---
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

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
