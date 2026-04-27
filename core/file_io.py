import os
import json
import tempfile
import pandas as pd
import time
import shutil
import traceback
from functools import wraps
from pathlib import Path

def ensure_absolute_path(path):
    p = Path(path)
    if not p.is_absolute():
        # [Imperial Relocation] 相対パスは全て聖域 (DATA_ROOT) へ強制的にリダイレクトします。
        from core.config import DATA_ROOT
        return str(Path(DATA_ROOT) / path)
    return str(path)

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
                    time.sleep(delay * (2 ** i))
            raise last_err
        return wrapper
    return decorator

@retry_io()
def atomic_write_json(path, data):
    # [Mission Critical Debug] 犯人を特定するためのスタックトレース表示
    # if "data" not in str(path):
    #    print(f"\n🚨 [FILE_IO DEBUG] atomic_write_json called for: {path}")
    #    traceback.print_stack(limit=5)
    
    path = ensure_absolute_path(path)
    dir_name = os.path.dirname(path)
    os.makedirs(dir_name, exist_ok=True)
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
    path = ensure_absolute_path(path)
    dir_name = os.path.dirname(path)
    os.makedirs(dir_name, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(dir=dir_name, prefix=".tmp_", suffix=".csv")
    try:
        os.close(fd)
        df.to_csv(temp_path, index=False, encoding='utf-8-sig')
        os.replace(temp_path, path)
        # [Mission Critical Debug]
        # if "data" not in str(path):
        #    print(f"\n🚨 [FILE_IO DEBUG] atomic_write_csv called for: {path}")
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise e


@retry_io()
def append_csv_rows(path, rows):
    if not rows:
        return
    path = ensure_absolute_path(path)
    dir_name = os.path.dirname(path)
    os.makedirs(dir_name, exist_ok=True)
    df = pd.DataFrame(rows)
    write_header = (not os.path.exists(path)) or os.path.getsize(path) == 0
    df.to_csv(path, mode='a', index=False, header=write_header, encoding='utf-8-sig')

@retry_io()
def safe_read_json(path, default=None):
    path = ensure_absolute_path(path)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return default
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        return default

@retry_io()
def safe_read_csv(path):
    path = ensure_absolute_path(path)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()

@retry_io()
def rotate_csv_if_large(filepath, max_size_mb=2):
    filepath = ensure_absolute_path(filepath)
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
