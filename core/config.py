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
DEBUG_MODE = os.environ.get("DEBUG_MODE", "false").lower() == "true"  # .envで DEBUG_MODE=true に設定して切り替え
INITIAL_CASH = 1000000    # 初回シミュレーション用資金
MAX_POSITIONS = 4         # リスク分散上限
MAX_RISK_PER_TRADE = 0.02 # 1トレードあたりの許容リスク（総資金の2%）
MAX_ALLOCATION_PCT = 0.40 # 1銘柄あたりの最大投資比率（40%に拡大: 100万円等の少額運用向け）
MIN_ALLOCATION_AMOUNT = 200000 # 少額資金時の最低投資保証額（20万円）
TAX_RATE = 0.20315        # 約20.3%

# --- Market Filters ---
TARGET_MARKETS = ['プライム（内国株式）', 'スタンダード（内国株式）', 'グロース（内国株式）']

def load_insider_exclusion_codes() -> set:
    """
    insider_exclusion.json から取引禁止銘柄コードのセットを読み込む。
    ファイルが存在しない・JSON破損の場合は空のsetを返す（フェイルセーフ）。
    M-6: '_' で始まるものを「コメント行・無視アイテム」として除外するかどうかは
    実際の証券コード体系とぶつかるリスクを考慮すると、'description'のようなキーを
    別途設けるのが正規ですが、現状互換性のため維持しコメント追記します。
    """
    if not os.path.exists(INSIDER_EXCLUSION_FILE):
        return set()
    try:
        with open(INSIDER_EXCLUSION_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        codes = data.get('codes', [])
        # L-3: ローカルインポートを削除。
        return set(str(c) for c in codes if not str(c).startswith('_'))
    except Exception as e:
        print(f"⚠️ [insider_exclusion.json] 読み込みエラー（除外なしで続行）: {e}")
        return set()

# --- Target Exits ---
ATR_STOP_LOSS = 1.0       # 損切りを早くする(ATRの1倍) - BULL用
RANGE_ATR_STOP_LOSS = 1.5 # レンジ相場でも1.5倍で切る
ATR_TRAIL = 2.0           # トレール幅を広げてトレンドに長く乗る(最高値からATRの2倍)
