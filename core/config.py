import os
import json
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

# .envファイルを読み込む
load_dotenv()

# --- Basic Settings ---
STOCKS_TYPE = "prime"  # "prime", "standard", "growth"
JST = ZoneInfo("Asia/Tokyo")
DATA_FILE = "data/symbols_with_market.csv"
INITIAL_CASH = 1000000  # 100万円

if STOCKS_TYPE == "standard":
    TARGET_MARKETS = ["スタンダード（内国株式）"]
elif STOCKS_TYPE == "growth":
    TARGET_MARKETS = ["グロース（内国株式）"]
else:
    TARGET_MARKETS = ["グロース（内国株式）"]

# --- Trading Parameters (V12.0 Growth Monster Optimized Rank #1) ---
STOCKS_TYPE = "growth" 
BREAKOUT_PERIOD = 5   # Hyper-breakout (standardized)
EXIT_PERIOD = 3       # Optimized Time-limit (Rank #1, most stable)
MAX_POSITIONS = 5     # Optimized Concentration
TARGET_PROFIT = 0.07  # Optimized Take-Profit (Rank #1)
INITIAL_CASH = 1000000 
MAX_DAILY_BUYS = 5
STOP_LOSS_RATE = 0.03 # Optimized Stop-Loss
RANK_METRIC = "Ret3"  # Momentum Score
MIN_PRICE = 200
MAX_PRICE = 10000
VOL_MULTIPLIER = 1.5

# --- Risk Management ---
ATR_PERIOD = 20
STOP_LOSS_ATR = 2.0  # 2*ATR stop
TAX_RATE = 0.20315   # Japan Capital Gains Tax

# --- Discord Settings ---
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# --- API Settings ---
KABUCOM_API_PASSWORD = os.getenv("KABU_API_PASSWORD", "your_password")
KABUCOM_LOGIN_PASSWORD = os.getenv("KABU_LOGIN_PASSWORD", "your_login_password")
KABUCOM_API_TOKEN_FILE = ".kabu_token"
KABUCOM_PORT_LIVE = 18080
KABUCOM_PORT_TEST = 18081
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY      = os.getenv("GROQ_API_KEY", "")
GEMINI_MODEL      = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# --- Bot Execution Mode ---
# SIM: ローカルCSVシミュレーション / KABUCOM_TEST: 検証API / KABUCOM_LIVE: 本番API
TRADE_MODE = os.getenv("TRADE_MODE", "SIM")
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# --- File Paths ---
BASE_DIR            = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_ROOT           = os.path.join("data", "kabucom_test")
LOG_DIR             = os.path.join("data", "kabucom_test", "logs")
PORTFOLIO_FILE      = "portfolio.json"
HISTORY_FILE        = "trade_history.csv"
ACCOUNT_FILE        = "account.csv"
EXECUTION_LOG_FILE  = "execution_log.csv"
EXCLUSION_CACHE_FILE = "invalid_tickers.json"

# --- Position Sizing (ATR-based, live trading only) ---
MAX_RISK_PER_TRADE    = 0.02   # 総資産の2%をリスク許容額とする
MAX_ALLOCATION_PCT    = 0.20   # 1銘柄に総資産の最大20%まで
MAX_ALLOCATION_AMOUNT = 5000000 # 1銘柄の最大投資額（スリッページ防止: 500万円）
LIQUIDITY_LIMIT_RATE  = 0.01    # 1銘柄の購入額を平均売買代金の1%以内に抑える
MIN_ALLOCATION_AMOUNT = 100000 # 最低10万円以上でないと購入しない
ATR_STOP_LOSS         = 2.0    # ATR × 2.0 を損切り幅とする
RANGE_ATR_STOP_LOSS   = 1.5    # レンジ相場時は ATR × 1.5 に縮小
ATR_TRAIL             = False  # トレーリングストップ（未使用）

# --- Insider Exclusion ---
def load_insider_exclusion_codes():
    """インサイダー取引疑義銘柄の除外リストを読み込む"""
    try:
        with open("insider_exclusion.json", "r", encoding="utf-8") as f:
            return json.load(f).get("codes", [])
    except Exception:
        return []
