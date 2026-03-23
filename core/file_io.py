import os
import json
import tempfile
import pandas as pd
import time
import shutil
from functools import wraps

def retry_io(max_retries=5, delay=0.1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_err = None
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (IOError, PermissionError) as e:
                    last_err = e
                    time.sleep(delay * (2 ** i)) # 指数バックオフ
            raise last_err
        return wrapper
    return decorator

@retry_io()
def atomic_write_json(path, data):
    """ファイルを一時ファイル経由で安全に書き込み、OSレベルでアトミックに置換します。"""
    dir_name = os.path.dirname(path)
    fd, temp_path = tempfile.mkstemp(dir=dir_name, prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        os.replace(temp_path, path)
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise e

@retry_io()
def atomic_write_csv(path, df):
    """Pandas DataFrameを一時ファイル経由でアトミックにCSV保存します。"""
    dir_name = os.path.dirname(path)
    fd, temp_path = tempfile.mkstemp(dir=dir_name, prefix=".tmp_", suffix=".csv")
    try:
        os.close(fd)
        df.to_csv(temp_path, index=False, encoding='utf-8-sig')
        os.replace(temp_path, path)
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise e

@retry_io()
def safe_read_json(path, default=None):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return default
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"⚠️ [Data Recovery] ファイル {path} が破損しています({e})。デフォルト値で継続します。")
        return default

@retry_io()
def safe_read_csv(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    except Exception as e:
        print(f"⚠️ [Data Recovery] CSVファイル {path} の読み込みに失敗しました({e})。空のデータとして処理します。")
        return pd.DataFrame()

@retry_io()
def rotate_csv_if_large(filepath, max_size_mb=2):
    """ファイルサイズが増大した場合に、アーカイブフォルダへ退避させます。"""
    if not os.path.exists(filepath):
        return
    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    if size_mb > max_size_mb:
        dir_name = os.path.dirname(filepath)
        archive_dir = os.path.join(dir_name, "archive")
        os.makedirs(archive_dir, exist_ok=True)
        base_name = os.path.basename(filepath)
        name, ext = os.path.splitext(base_name)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        archive_path = os.path.join(archive_dir, f"{name}_{timestamp}{ext}")
        shutil.move(filepath, archive_path)
        print(f"📦 [Archive] ログ肥大化防止: {base_name} が {max_size_mb}MB を超過したため、{archive_dir} へ退避・初期化しました。")
