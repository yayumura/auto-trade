import os
import sys
import io
import requests
from datetime import datetime
from core.config import LOG_DIR, DISCORD_WEBHOOK_URL

os.makedirs(LOG_DIR, exist_ok=True)
current_date = datetime.now().strftime('%Y-%m-%d')
LOG_FILE = os.path.join(LOG_DIR, f"console_{current_date}.log")

class TeeLogger:
    def __init__(self, stream, filepath):
        self.stream = stream
        self.file = open(filepath, 'a', encoding='utf-8')

    def write(self, message):
        self.stream.write(message)
        self.file.write(message)
        self.file.flush()

    def flush(self):
        self.stream.flush()
        self.file.flush()

def setup_logging():
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"  
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    
    # 既存のTeeLoggerがセットされていなければセット
    if not isinstance(sys.stdout, TeeLogger):
        sys.stdout = TeeLogger(sys.stdout, LOG_FILE)
        sys.stderr = TeeLogger(sys.stderr, LOG_FILE)

def send_discord_notify(message):
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    except Exception as e:
        print(f"⚠️ Discord通知エラー: {e}")

def clean_old_logs(days=30):
    """古いログファイルを自動的に削除し、ディスク容量を保護します。"""
    try:
        now = datetime.now()
        count = 0
        for filename in os.listdir(LOG_DIR):
            if filename.startswith("console_") and filename.endswith(".log"):
                filepath = os.path.join(LOG_DIR, filename)
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                if (now - file_time).days > days:
                    os.remove(filepath)
                    count += 1
        if count > 0:
            print(f"🧹 [Housekeeping] {count}個の古いログファイルを削除しました。")
    except Exception as e:
        print(f"⚠️ ログクリーンアップ失敗: {e}")

# 初期化時に実行
clean_old_logs()
