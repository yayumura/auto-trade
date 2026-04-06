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
    print(f"📡 [IMPERIAL_CONFIG] PROJECT_ROOT -> {PROJECT_ROOT}")
    print(f"📡 [IMPERIAL_CONFIG] DATA_ROOT -> {DATA_ROOT}")

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

# --- Imperial Oracle V21.0 (Dynamic Risk Management Sync) ---
USE_DYNAMIC_LEVERAGE  = True   # ★NEW: 市場環境（Breadth）に応じてレバレッジを自動調整
MAX_POSITIONS         = 7      # ★NEW: 7 stocks (超集中投資)
BREADTH_THRESHOLD     = 0.20   # ★NEW: 0.20 (総悲観の底から現物で拾い始める設定)
MAX_RISK_PER_TRADE    = 0.01   # 1% Risk per trade
LEVERAGE_RATE         = 3.0    # 最大レバレッジ (Breadth >= 0.5 の時)
MAX_ALLOCATION_PCT    = 0.428  # (LEVERAGE 3.0 / 7 POS ≒ 0.428)
MAX_ALLOCATION_AMOUNT = 10000000 
LIQUIDITY_LIMIT_RATE  = 0.01   
MIN_ALLOCATION_AMOUNT = 50000  
ATR_STOP_LOSS         = 6.0    # ★NEW: 6.0 (動的レバによる防御を前提に損切り幅を適正化)
TARGET_PROFIT_MULT    = 20.0   # ★NEW: 20.0 (確実な利益確定によるドローダウン抑制)
RS_THRESHOLD          = 10.0   # Minimum Relative Strength
MIN_PRICE             = 200    # Minimum stock price
MAX_PRICE             = 10000  # Maximum stock price
ATR_TRAIL             = True   # Trailing stop enabled
EXIT_ON_SMA20_BREACH  = True   # [V17.3] Technical Exit: Close < SMA20
SMA20_EXIT_BUFFER     = 0.985  # ★NEW: 0.985 (損切り・微益撤退のバランス最適化)
SMA_SHORT_PERIOD      = 5
SMA_MEDIUM_PERIOD     = 20
SMA_LONG_PERIOD       = 100
SMA_BREADTH_PERIOD    = 100    # Breadth calculation base

# --- Insider Exclusion ---
def load_insider_exclusion_codes():
    """インサイダー取引疑義銘柄の除外リストを読み込む"""
    try:
        with open(INSIDER_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("codes", [])
    except Exception:
        return []
