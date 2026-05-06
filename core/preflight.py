import time
import os
import sys
import requests
from pathlib import Path
from datetime import datetime, timedelta
from core.config import (
    KABUCOM_API_PASSWORD, GEMINI_API_KEY, TRADE_MODE,
    DATA_ROOT, LOG_DIR, CONFIG_DIR
)

# [Imperial Safeguard] 
# 重要ファイル（ポートフォリオ・取引履歴）は絶対に削除対象外
_PROTECTED_FILES = {
    "virtual_portfolio.csv",
    "trade_history.csv",
    "account.json",
    "execution_log.csv",
    "jp_watchlist.json",
    "intraday_snapshots.csv",
}

def pre_flight_check():
    """
    ボット起動前に実行環境、設定、ネットワークを点検します。
    すべての操作は DATA_ROOT (絶対パス) 傘下で行われます。
    """
    # config.py の場所を起点に、確実にプロジェクトルートを特定
    project_root = CONFIG_DIR.parent
    
    print("\n[Pre-flight Check] 🛠️ 帝国起動前点検を開始します...")
    
    # 1. 環境設定ファイルの確認
    env_path = project_root / ".env"
    if not env_path.exists():
        print(f"❌ [.env 欠落] {env_path} が見つかりません。")
        sys.exit(1)

    # 2. 必須ディレクトリの整合性
    dirs_to_check = [DATA_ROOT, LOG_DIR]
    for d in dirs_to_check:
        if not os.path.exists(d):
            print(f"📁 [ディレクトリ作成] {d} を作成します...")
            os.makedirs(d, exist_ok=True)

    # 3. 必須APIキーの存在確認 (TRADE_MODEに応じて必須キーを決定)
    missing_keys = []
    if not GEMINI_API_KEY: missing_keys.append("GEMINI_API_KEY")
    if TRADE_MODE in ("KABUCOM_LIVE", "KABUCOM_TEST"):
        if not KABUCOM_API_PASSWORD: missing_keys.append("KABUCOM_API_PASSWORD")
    
    if missing_keys:
        print(f"❌ [設定漏れ] 以下の必須設定が .env にありません: {', '.join(missing_keys)}")
        sys.exit(1)

    # 4. ネットワーク接続テスト
    print("🌐 [Net Check] 接続を確認中...")
    try:
        requests.get("https://www.google.com", timeout=3)
        print("✅ ネットワーク接続 OK")
    except Exception as e:
        print(f"❌ [ネットワーク遮断] 接続できません: {e}")
        sys.exit(1)

    # 5. JQuants Cache 動作確認
    print("📈 [Data Check] JQuantsキャッシュの健全性確認...")
    jquant_cache = project_root / "data_cache" / "jp_broad" / "jp_mega_cache.pkl"
    if not jquant_cache.exists():
        print(f"⚠️ [Data 警告] JQuantsキャッシュ ({jquant_cache.name}) が見つかりません。")
    else:
        try:
            mtime = os.path.getmtime(jquant_cache)
            cache_date = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
            print(f"✅ JQuants Cache OK (最終更新: {cache_date})")
        except:
            print("⚠️ [Data 警告] キャッシュ属性の取得に失敗しました。")

    # 6. ディスク・クリーンアップ (DATA_ROOT 傘下のみ)
    print("🧹 [Housekeeping] 古い一時データの清掃 (DATA_ROOT)...")
    try:
        now_ts = time.time()
        for filename in os.listdir(DATA_ROOT):
            # 重要ファイルは除外 (絶対パスではなく名前でチェック)
            if filename in _PROTECTED_FILES:
                continue
            # 削除対象: invalid_tickers等
            if filename.endswith(".json") and filename.startswith("invalid_"):
                file_path = os.path.join(DATA_ROOT, filename)
                if now_ts - os.path.getmtime(file_path) > 604800:
                    os.remove(file_path)
                    print(f"   🗑️ 古いキャッシュを削除: {filename}")
    except Exception as e:
        print(f"⚠️ 清掃中にエラー（続行）: {e}")

    print("🚀 [Pre-flight Check] 全ての点検をパスしました。\n")
    return True
