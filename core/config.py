import os
from datetime import datetime
import json
from dotenv import load_dotenv
import pytz

# --- Timezone ---
JST = pytz.timezone('Asia/Tokyo')

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

# --- インサイダー取引防止設定 ---
# プロジェクトルートの insider_exclusion.json で管理。新規買付のみ禁止（保有中のポジション管理は対象外）。
INSIDER_EXCLUSION_FILE = os.path.join(BASE_DIR, 'insider_exclusion.json')

# --- API Keys & Webhooks ---
KABUCOM_API_PASSWORD = os.environ.get("KABUCOM_API_PASSWORD")
KABUCOM_LOGIN_PASSWORD = os.environ.get("KABUCOM_LOGIN_PASSWORD")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# --- Models ---
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

# --- Strategy Parameters ---
DEBUG_MODE = os.environ.get("DEBUG_MODE", "false").lower() == "true"
INITIAL_CASH = 1000000    # 初回シミュレーション用資金
MAX_POSITIONS = 8         # リスク分散上限（100万円での分散性を高めるため、6から8に拡大）
MAX_RISK_PER_TRADE = 0.02 # 1トレードあたりの許容リスク（総資金の2%）
MAX_ALLOCATION_PCT = 0.30 # 1銘柄あたりの最大投資比率（分散向上のため40%から30%へ）
MIN_ALLOCATION_AMOUNT = 120000 # 少額資金時の最低投資保証額
TAX_RATE = 0.20315        # 約20.3%

# --- 【Holy Grail】Donchian Breakout Parameters ---
DONCHIAN_BREAKOUT = 25    # エントリー：25日高値更新
DONCHIAN_EXIT = 10        # エグジット：10日安値更新
MIN_TURNOVER = 50000000   # 流動性フィルター：売買代金5,000万円以上
ATR_STOP_MULT = 2.5       # 損切り幅：2.5 x ATR

# --- Market Filters ---
TARGET_MARKETS = ['プライム（内国株式）', 'スタンダード（内国株式）', 'グロース（内国株式）']

def load_insider_exclusion_codes() -> set:
    if not os.path.exists(INSIDER_EXCLUSION_FILE):
        return set()
    try:
        with open(INSIDER_EXCLUSION_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        codes = data.get('codes', [])
        return set(str(c) for c in codes if not str(c).startswith('_'))
    except Exception as e:
        print(f"⚠️ [insider_exclusion.json] 読み込みエラー（除外なしで続行）: {e}")
        return set()

# --- Target Exits ---
ATR_STOP_LOSS = 5.0
RANGE_ATR_STOP_LOSS = 6.0
ATR_TRAIL = 8.0

# --- Scenario B (Professional Baseline Strategy 4.3) ---
MIN_VOLUME_SURGE = 2.5
ATR_TARGET_MULT = 10.0
ATR_STOP_MULT = 2.5
BREAKEVEN_TRIGGER = 0.040
TRAIL_STOP_MULT = 6.0
MIN_MOMENTUM_THRESHOLD = 0.10
