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

    def close(self):
        """ M-3: プロセス終了時にファイルをクローズする。Windowsでのファイルロックを防止。"""
        try:
            self.file.flush()
            self.file.close()
        except Exception:
            pass

def setup_logging():
    import atexit
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"  
    
    # 既存のTeeLoggerがセットされていなければセット
    if not isinstance(sys.stdout, TeeLogger):
        # 先に元のストリームを正しく保持する
        orig_stdout = sys.stdout
        orig_stderr = sys.stderr
        
        # WindowsのUnicodeEncodeError対策のためにTextIOWrapperでラップしてからTeeLoggerに渡す
        wrapped_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        wrapped_stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        
        tee_out = TeeLogger(wrapped_stdout, LOG_FILE)
        tee_err = TeeLogger(wrapped_stderr, LOG_FILE)
        sys.stdout = tee_out
        sys.stderr = tee_err
        # M-3: atexitでclose()を登録し、プロセス終了時にファイルを確実にクローズ
        # 終了時の例外（標準IOが先にクローズされるなど）を防ぐためにラッパー関数を使う
        def safe_close(logger):
            try: logger.close()
            except: pass
        atexit.register(safe_close, tee_out)
        atexit.register(safe_close, tee_err)
    # H-7: clean_old_logsをモジュールロード時ではなくここで呼ぶ（副作用を局所化）
    clean_old_logs()

def send_discord_notify(message):
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        # L-1: timeoutを指定してDiscordサーバー障害時にメインループをブロックしないよう修正
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=5)
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

# H-7: clean_old_logsはモジュール読み込み時には実行しない
# setup_logging() 内で1度だけ呼ばれる
