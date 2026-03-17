import os
import json
import tempfile
import pandas as pd
import time
from functools import wraps

def retry_io(max_retries=3, delay=0.1):
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
    except Exception as e:
        print(f"⚠️ [Data Recovery] CSVファイル {path} の読み込みに失敗しました({e})。空のデータとして処理します。")
        return pd.DataFrame()
