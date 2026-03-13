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
