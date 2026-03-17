import time
from datetime import datetime, timedelta
from core.config import (
    KABUCOM_API_PASSWORD, GEMINI_API_KEY, 
    DATA_ROOT, LOG_DIR, BASE_DIR
)

def pre_flight_check():
    """
    ボット起動前に実行環境、設定、ネットワークを点検します。
    問題があればシステムを終了し、致命的なエラーを防止します。
    """
    print("\n[Pre-flight Check] 🛠️ 起動前点検を開始します...")
    
    # 1. 環境設定ファイルの確認
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        print("❌ [.env 欠落] プロジェクトルートに .env ファイルが見つかりません。")
        sys.exit(1)

    # 2. 必須ディレクトリの整合性
    dirs_to_check = [DATA_ROOT, LOG_DIR]
    for d in dirs_to_check:
        if not os.path.exists(d):
            print(f"📁 [ディレクトリ作成] {d} を作成します...")
            os.makedirs(d, exist_ok=True)

    # 3. 必須APIキーの存在確認 (警告のみか強制停止かは運用によるが、ここでは停止)
    missing_keys = []
    if not KABUCOM_API_PASSWORD: missing_keys.append("KABUCOM_API_PASSWORD")
    if not GEMINI_API_KEY: missing_keys.append("GEMINI_API_KEY")
    
    if missing_keys:
        print(f"❌ [設定漏れ] 以下の必須設定が .env にありません: {', '.join(missing_keys)}")
        sys.exit(1)

    # 4. ネットワーク接続テスト
    print("🌐 [Net Check] インターネット接続を確認中...")
    try:
        # Googleへの疎通確認（タイムアウト3秒）
        requests.get("https://www.google.com", timeout=3)
        print("✅ ネットワーク接続 OK")
    except Exception as e:
        print(f"❌ [ネットワーク遮断] インターネットに接続できません: {e}")
        sys.exit(1)

    # 5. yfinance 動作確認（簡易）
    print("📈 [API Check] マーケットデータAPI (yfinance) 疎通確認...")
    import yfinance as yf
    try:
        ticker = yf.Ticker("7203.T") # トヨタ
        if ticker.fast_info['lastPrice'] is None:
            raise ValueError("データ受信失敗")
        print("✅ マーケットデータ API OK")
    except Exception as e:
        print(f"⚠️ [API 警告] マーケットデータAPIに不安定な兆候があります: {e}")
    # yfinanceは一時的な事が多いので警告にとどめる

    # 6. ディスク・クリーンアップ (Phase 14)
    print("🧹 [Housekeeping] 古い一時データの清掃確認...")
    try:
        now_ts = time.time()
        for filename in os.listdir(DATA_ROOT):
            if filename.endswith(".csv"):
                file_path = os.path.join(DATA_ROOT, filename)
                # 7日以上(604800秒)経過したものを削除
                if now_ts - os.path.getmtime(file_path) > 604800:
                    os.remove(file_path)
                    print(f"   🗑️ 古いキャッシュを削除: {filename}")
    except Exception as e:
        print(f"⚠️ 清掃中にエラー（続行）: {e}")

    print("🚀 [Pre-flight Check] 全ての点検をパスしました。システムを起動します。\n")
    return True
