import os
import json
from pathlib import Path
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

# .envファイルを読み込む
load_dotenv()

# --- Basic Settings ---
JST = ZoneInfo("Asia/Tokyo")
DATA_FILE = "data/symbols_with_market.csv"
INITIAL_CASH = 1000000 # 100万円基準
TAX_RATE = 0.20315      # 日本 株取引所得税

# 日本株全市場をターゲット
TARGET_MARKETS = [
    "プライム（内国株式）",
    "スタンダード（内国株式）",
    "グロース（内国株式）"
]

# --- Discord Settings ---
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# --- API Settings ---
KABUCOM_API_PASSWORD = os.getenv("KABUCOM_API_PASSWORD", "your_password")
KABUCOM_LOGIN_PASSWORD = os.getenv("KABUCOM_LOGIN_PASSWORD", "your_login_password")
KABUCOM_API_TOKEN_FILE = ".kabu_token"
KABUCOM_PORT_LIVE = 18080
KABUCOM_PORT_TEST = 18081
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL      = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GROQ_API_KEY      = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL        = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# --- Bot Execution Mode ---
TRADE_MODE = os.getenv("TRADE_MODE", "SIM")
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# --- [Imperial Proclamation] 黄金の絶対座標 (Project Root Discovery) ---
# コンフィグファイルの場所(coreフォルダ)から、プロジェクトルートを絶対パスで特定
CONFIG_DIR = Path(os.path.abspath(os.path.dirname(__file__)))
PROJECT_ROOT = CONFIG_DIR.parent

# データ保存聖域の決定
if TRADE_MODE == "SIM":
    DATA_ROOT = PROJECT_ROOT / "data" / "simulation"
else:
    DATA_ROOT = PROJECT_ROOT / "data" / "kabucom_test"

# [Imperial Safeguard] 実行時に保存先を絶対的に宣言する
if DEBUG_MODE:
    print(f"[IMPERIAL_CONFIG] PROJECT_ROOT -> {PROJECT_ROOT}")
    print(f"[IMPERIAL_CONFIG] DATA_ROOT -> {DATA_ROOT}")

# すべて絶対パスに変換
DATA_ROOT_STR       = str(DATA_ROOT)
LOG_DIR             = str(DATA_ROOT / "logs")
PORTFOLIO_FILE      = str(DATA_ROOT / "portfolio.json")
HISTORY_FILE        = str(DATA_ROOT / "trade_history.csv")
ACCOUNT_FILE        = str(DATA_ROOT / "account.json")
EXECUTION_LOG_FILE  = str(DATA_ROOT / "execution_log.csv")
EXCLUSION_CACHE_FILE = str(DATA_ROOT / "invalid_tickers.json")
INSIDER_FILE        = str(DATA_ROOT / "insider_exclusion.json")
WATCHLIST_FILE      = str(DATA_ROOT / "jp_watchlist.json")

# --- Imperial Oracle V17.0 FINAL (V17 Golden Logic) ---
USE_COMPOUNDING       = True   # ★GOLDEN: Compounding on
MAX_POSITIONS         = 3      # ★GOLDEN: Concentration
LEVERAGE              = 1.5    # ★GOLDEN: 1.5x Leverage
INITIAL_CASH          = 1000000

# Strategy Core (V17 Golden Plateau)
BREADTH_THRESHOLD     = 0.60   # ★GOLDEN: Market Breadth
SMA20_EXIT_BUFFER     = 0.975  # ★GOLDEN: Trend Exit Buffer
STOP_LOSS_ATR         = 5.0    # ★GOLDEN: Stop Loss Mult
TAKE_PROFIT_ATR       = 40.0   # ★GOLDEN: Take Profit Mult
BULL_GAP_LIMIT        = 0.11   # ★GOLDEN: Gap Limit
BEAR_GAP_LIMIT        = 0.02
RS_THRESHOLD          = 25.0

# Aliases for compatibility with restored V17 code
ATR_STOP_LOSS         = STOP_LOSS_ATR
TARGET_PROFIT_MULT    = TAKE_PROFIT_ATR
LEVERAGE_RATE         = LEVERAGE

MAX_ALLOCATION_PCT    = 1.0  
MAX_ALLOCATION_AMOUNT = 10000000 
LIQUIDITY_LIMIT_RATE  = 0.025  
MIN_ALLOCATION_AMOUNT = 50000  
MIN_PRICE             = 200    
MAX_PRICE             = 10000  

EXIT_ON_SMA20_BREACH  = True   
SMA_SHORT_PERIOD      = 5
SMA_MEDIUM_PERIOD     = 20
SMA_LONG_PERIOD       = 100
SMA_BREADTH_PERIOD    = 100    # Breadth calculation base
SMA_TREND_PERIOD      = 200    # Long-term trend detection
COOLING_DAYS          = 2      # [V132] Wait after exit to avoid whip-saws
SLIPPAGE              = 0.003  # Round-trip slippage rate (buy: +0.3%, sell: -0.3%)
MAX_HOLD_DAYS         = 30     # [V17.0] Time-stop parity

# --- Insider Exclusion ---
def load_insider_exclusion_codes():
    """インサイダー取引疑義銘柄の除外リストを読み込む"""
    try:
        with open(INSIDER_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("codes", [])
    except Exception:
        return []
