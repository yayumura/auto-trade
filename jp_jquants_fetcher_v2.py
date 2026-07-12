import argparse
import json
import os
import pickle
import re
import shutil
import sys
import time
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

try:
    import jquantsapi
except ModuleNotFoundError as exc:
    _JQUANTSAPI_IMPORT_ERROR = exc

    def _missing_jquants_client(*args, **kwargs):
        raise ModuleNotFoundError(
            "jquantsapi is required to refresh J-Quants caches. Install the dependency "
            "before calling jp_jquants_fetcher_v2.py."
        ) from _JQUANTSAPI_IMPORT_ERROR

    jquantsapi = SimpleNamespace(ClientV2=_missing_jquants_client)
import pandas as pd
import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

load_dotenv()

CHECKPOINT_DIR = str(REPO_ROOT / "data_cache" / "jp_broad" / "checkpoints")
DEFAULT_OUTPUT_PATH = str(REPO_ROOT / "data_cache" / "jp_broad" / "jp_mega_cache.pkl")
DEFAULT_START_DATE = "20210405"
DEFAULT_REFRESH_OVERLAP_DAYS = 7
DEFAULT_MAX_WORKERS = 4
DEFAULT_BULK_REFRESH_MAX_DAYS = 31
_REFRESH_BACKUP_TAG = None

os.makedirs(CHECKPOINT_DIR, exist_ok=True)


def _ensure_jquants_no_proxy():
    no_proxy_value = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
    hosts = [entry.strip() for entry in no_proxy_value.split(",") if entry.strip()]
    if "api.jquants.com" not in hosts:
        hosts.append("api.jquants.com")
    joined = ",".join(dict.fromkeys(hosts))
    os.environ["NO_PROXY"] = joined
    os.environ["no_proxy"] = joined


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Refresh the JP J-Quants daily cache. By default, if an existing cache is present, "
            "only the most recent overlap window is re-fetched and merged into each ticker checkpoint."
        )
    )
    parser.add_argument(
        "--output-path",
        default=DEFAULT_OUTPUT_PATH,
        help="Where to save the consolidated JP cache pickle.",
    )
    parser.add_argument(
        "--start-date",
        default="",
        help="Optional YYYYMMDD override for the fetch start date.",
    )
    parser.add_argument(
        "--refresh-overlap-days",
        type=int,
        default=DEFAULT_REFRESH_OVERLAP_DAYS,
        help="When an existing cache is found, re-fetch this many trailing days before the cached latest date.",
    )
    parser.add_argument(
        "--force-full-refresh",
        action="store_true",
        help="Ignore incremental start-date detection and re-fetch the full history from the default start date.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help="Maximum concurrent ticker fetch workers. Lower this if the API returns 429s.",
    )
    parser.add_argument(
        "--limit-tickers",
        type=int,
        default=0,
        help="Optional cap on how many target tickers to fetch. Use 0 for all tickers.",
    )
    parser.add_argument(
        "--debug-failure-samples",
        type=int,
        default=5,
        help="Print up to this many concrete failure samples during refresh.",
    )
    parser.add_argument(
        "--audit-only",
        action="store_true",
        help="Only audit checkpoint vs cache drift and exit without refreshing.",
    )
    parser.add_argument(
        "--list-backups",
        action="store_true",
        help="List available full cache snapshots and exit.",
    )
    parser.add_argument(
        "--restore-backup",
        default="",
        help="Restore a previously created full cache snapshot (use 'latest' for the newest snapshot) and exit.",
    )
    return parser.parse_args()


def _checkpoint_pickle_path(ticker_code):
    return os.path.join(CHECKPOINT_DIR, f"{ticker_code}.pkl")


def _checkpoint_empty_path(ticker_code):
    return os.path.join(CHECKPOINT_DIR, f"{ticker_code}.empty")


def _legacy_checkpoint_code(ticker_code):
    code = str(ticker_code)
    return f"{code}0" if len(code) == 4 else code


def _checkpoint_pickle_candidates(ticker_code):
    code = str(ticker_code)
    candidates = [_checkpoint_pickle_path(code)]
    legacy_code = _legacy_checkpoint_code(code)
    legacy_path = _checkpoint_pickle_path(legacy_code)
    if legacy_path not in candidates:
        candidates.append(legacy_path)
    return candidates


def _checkpoint_empty_candidates(ticker_code):
    code = str(ticker_code)
    candidates = [_checkpoint_empty_path(code)]
    legacy_code = _legacy_checkpoint_code(code)
    legacy_path = _checkpoint_empty_path(legacy_code)
    if legacy_path not in candidates:
        candidates.append(legacy_path)
    return candidates


def _checkpoint_exists(ticker_code):
    return any(os.path.exists(path) for path in _checkpoint_pickle_candidates(ticker_code))


def _cache_root_dir():
    checkpoint_dir = os.path.abspath(CHECKPOINT_DIR)
    if os.path.basename(checkpoint_dir.rstrip(os.sep)).lower() == "checkpoints":
        return os.path.dirname(checkpoint_dir)
    return checkpoint_dir


def _get_refresh_backup_tag():
    global _REFRESH_BACKUP_TAG
    if not _REFRESH_BACKUP_TAG:
        _REFRESH_BACKUP_TAG = datetime.now().strftime("%Y%m%d_%H%M%S")
    return _REFRESH_BACKUP_TAG


def _backup_root_dir():
    return os.path.join(_cache_root_dir(), "backups")


def _snapshot_root_dir(snapshot_tag):
    return os.path.join(_backup_root_dir(), snapshot_tag)


def _normalize_snapshot_name(snapshot_name):
    return str(snapshot_name).strip()


def _load_snapshot_manifest(snapshot_tag):
    manifest_path = os.path.join(_snapshot_root_dir(snapshot_tag), "manifest.json")
    if not os.path.exists(manifest_path):
        return None
    try:
        with open(manifest_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def _list_snapshot_tags(include_partial=False):
    root = _backup_root_dir()
    if not os.path.isdir(root):
        return []
    tags = []
    for entry in sorted(os.listdir(root)):
        snapshot_root = os.path.join(root, entry)
        if not os.path.isdir(snapshot_root):
            continue
        manifest = _load_snapshot_manifest(entry)
        if not include_partial and (not manifest or manifest.get("kind") != "full_snapshot"):
            continue
        tags.append(entry)
    return tags


def _resolve_snapshot_tag(snapshot_name):
    snapshot_name = _normalize_snapshot_name(snapshot_name)
    tags = _list_snapshot_tags(include_partial=False)
    if not tags:
        return None
    if snapshot_name in {"", "latest"}:
        return tags[-1]
    if snapshot_name not in tags:
        raise FileNotFoundError(
            f"Snapshot '{snapshot_name}' not found. Available snapshots: {', '.join(tags) or '(none)'}"
        )
    return snapshot_name


def _copy_file_to_snapshot(path, snapshot_tag):
    if not os.path.exists(path):
        return None

    snapshot_root = _snapshot_root_dir(snapshot_tag)
    cache_root = _cache_root_dir()
    abs_path = os.path.abspath(path)
    abs_root = os.path.abspath(cache_root)
    try:
        rel_path = os.path.relpath(abs_path, abs_root)
    except ValueError:
        rel_path = os.path.basename(abs_path)

    backup_path = os.path.join(snapshot_root, rel_path)
    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
    shutil.copy2(abs_path, backup_path)
    return backup_path


def _backup_existing_file(path):
    if not os.path.exists(path):
        return None

    return _copy_file_to_snapshot(path, _get_refresh_backup_tag())


def _atomic_pickle_dump(path, obj):
    dir_name = os.path.dirname(path)
    os.makedirs(dir_name, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(dir=dir_name, prefix=".tmp_", suffix=".pkl")
    try:
        os.close(fd)
        with open(temp_path, "wb") as handle:
            pickle.dump(obj, handle)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def _date_set(frame):
    if frame is None or frame.empty or "Date" not in frame.columns:
        return set()
    dates = pd.to_datetime(frame["Date"], errors="coerce").dropna().dt.normalize()
    return set(pd.DatetimeIndex(dates))


def _history_is_strictly_longer(candidate, existing):
    candidate_dates = _date_set(candidate)
    existing_dates = _date_set(existing)
    if not candidate_dates:
        return False
    if not existing_dates:
        return True
    return existing_dates.issubset(candidate_dates) and len(candidate_dates) > len(existing_dates)


def _checkpoint_needs_repair_from_cache(ticker_code, history, existing):
    if history is None or history.empty:
        return False
    if existing is None or existing.empty:
        return True

    ticker_code = str(ticker_code).upper()
    history_rows = len(history)
    existing_rows = len(existing)

    if history_rows < 50:
        return False
    if ticker_code.endswith("A"):
        return False
    if existing_rows <= 10:
        return True
    if history_rows >= 200 and existing_rows <= max(30, int(history_rows * 0.05)):
        return True
    return False


def _snapshot_current_cache_state(output_path=DEFAULT_OUTPUT_PATH, snapshot_tag=None):
    snapshot_tag = snapshot_tag or _get_refresh_backup_tag()
    snapshot_root = _snapshot_root_dir(snapshot_tag)
    os.makedirs(snapshot_root, exist_ok=True)

    copied = []
    if os.path.exists(output_path):
        copied_path = _copy_file_to_snapshot(output_path, snapshot_tag)
        if copied_path:
            copied.append(copied_path)

    if os.path.isdir(CHECKPOINT_DIR):
        for filename in sorted(os.listdir(CHECKPOINT_DIR)):
            path = os.path.join(CHECKPOINT_DIR, filename)
            if not os.path.isfile(path):
                continue
            copied_path = _copy_file_to_snapshot(path, snapshot_tag)
            if copied_path:
                copied.append(copied_path)

    manifest = {
        "kind": "full_snapshot",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "snapshot_tag": snapshot_tag,
        "source_output_path": os.path.abspath(output_path),
        "cache_root": os.path.abspath(_cache_root_dir()),
        "checkpoint_dir": os.path.abspath(CHECKPOINT_DIR),
        "file_count": len(copied),
    }
    manifest_path = os.path.join(snapshot_root, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
    return snapshot_root


def _restore_snapshot(snapshot_name, output_path=DEFAULT_OUTPUT_PATH):
    snapshot_tag = _resolve_snapshot_tag(snapshot_name)
    if snapshot_tag is None:
        raise FileNotFoundError("No full cache snapshots are available to restore.")

    snapshot_root = _snapshot_root_dir(snapshot_tag)
    manifest = _load_snapshot_manifest(snapshot_tag)
    if not manifest or manifest.get("kind") != "full_snapshot":
        raise RuntimeError(f"Snapshot '{snapshot_tag}' is not a full snapshot and cannot be restored safely.")

    preserved_tag = f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    _snapshot_current_cache_state(output_path=output_path, snapshot_tag=preserved_tag)

    if os.path.exists(output_path):
        os.remove(output_path)

    if os.path.isdir(CHECKPOINT_DIR):
        for filename in os.listdir(CHECKPOINT_DIR):
            path = os.path.join(CHECKPOINT_DIR, filename)
            if os.path.isfile(path):
                os.remove(path)

    restored = 0
    for root, _dirs, files in os.walk(snapshot_root):
        for filename in files:
            if filename == "manifest.json":
                continue
            src = os.path.join(root, filename)
            rel_path = os.path.relpath(src, snapshot_root)
            dst = os.path.join(_cache_root_dir(), rel_path)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            restored += 1

    return {
        "snapshot_tag": snapshot_tag,
        "snapshot_root": snapshot_root,
        "restored_files": restored,
    }


def _audit_checkpoint_drift(output_path, ticker_codes, debug_failure_samples=5, repair=False):
    cached = _load_output_cache_frame(output_path)
    if cached is None:
        print("CACHE AUDIT: consolidated cache not found or unreadable; skipping checkpoint drift audit.")
        return {"missing": 0, "shorter": 0, "aligned": 0, "repaired": 0}

    ticker_codes = sorted({_normalize_ticker_code(code) for code in ticker_codes})
    missing = []
    truncated = []
    aligned = []
    for ticker_code in ticker_codes:
        history = _extract_ticker_history_from_output_cache(cached, ticker_code)
        existing = _load_existing_checkpoint(ticker_code)
        if history.empty:
            missing.append(ticker_code)
        elif existing.empty:
            missing.append(ticker_code)
        elif _checkpoint_needs_repair_from_cache(ticker_code, history, existing):
            truncated.append(ticker_code)
        else:
            aligned.append(ticker_code)

    samples = truncated[: max(0, int(debug_failure_samples))]
    print(
        "CACHE AUDIT: "
        f"aligned={len(aligned)} missing={len(missing)} truncated={len(truncated)} "
        f"latest_cache={str(pd.Timestamp(cached.index.max()).date())}"
    )
    if missing:
        print("CACHE AUDIT missing samples: " + ", ".join(missing[: max(0, int(debug_failure_samples))]))
    if truncated:
        print("CACHE AUDIT truncated samples: " + ", ".join(samples))

    repaired = 0
    if repair and (missing or truncated):
        repaired = seed_missing_checkpoints_from_output_cache(output_path, ticker_codes)
        if repaired:
            print(f"CACHE AUDIT repaired={repaired} checkpoint files from consolidated cache.")

    return {
        "missing": len(missing),
        "truncated": len(truncated),
        "aligned": len(aligned),
        "repaired": repaired,
        "missing_samples": missing[: max(0, int(debug_failure_samples))],
        "truncated_samples": truncated[: max(0, int(debug_failure_samples))],
    }


def _run_cache_audit_only(output_path=DEFAULT_OUTPUT_PATH, debug_failure_samples=5, repair=False):
    cached = _load_output_cache_frame(output_path)
    if cached is None:
        print(f"CACHE AUDIT: consolidated cache not found or unreadable at {output_path}")
        return {"missing": 0, "shorter": 0, "aligned": 0, "repaired": 0}

    ticker_codes = {
        _normalize_ticker_code(str(ticker).replace(".T", ""))
        for ticker in cached.columns.get_level_values(0).unique()
    }
    return _audit_checkpoint_drift(
        output_path=output_path,
        ticker_codes=sorted(ticker_codes),
        debug_failure_samples=debug_failure_samples,
        repair=repair,
    )


def _print_backup_catalog():
    full_tags = _list_snapshot_tags(include_partial=False)
    partial_tags = [tag for tag in _list_snapshot_tags(include_partial=True) if tag not in full_tags]

    print("FULL SNAPSHOTS:")
    if full_tags:
        for tag in full_tags:
            manifest = _load_snapshot_manifest(tag) or {}
            created_at = manifest.get("created_at", "?")
            file_count = manifest.get("file_count", "?")
            print(f" - {tag} | created_at={created_at} | files={file_count}")
    else:
        print(" - (none)")

    print("PARTIAL BACKUPS:")
    if partial_tags:
        for tag in partial_tags:
            snapshot_root = _snapshot_root_dir(tag)
            file_count = sum(
                1
                for root, _dirs, files in os.walk(snapshot_root)
                for filename in files
                if filename != "manifest.json"
            )
            print(f" - {tag} | files={file_count}")
    else:
        print(" - (none)")


def _normalize_ticker_code(ticker_code):
    return str(ticker_code)[:4]


def _normalize_quote_frame(frame, ticker_code):
    if frame is None or len(frame) == 0:
        return pd.DataFrame()

    df = frame.copy()
    mapping = {"AdjO": "Open", "AdjH": "High", "AdjL": "Low", "AdjC": "Close", "AdjVo": "Volume"}
    df = df.rename(columns=mapping)
    if "Code" not in df.columns:
        df["Code"] = str(ticker_code)
    df["Date"] = pd.to_datetime(df["Date"])
    return df.sort_values("Date").reset_index(drop=True)


def _load_existing_checkpoint(ticker_code):
    frames = []
    for path in _checkpoint_pickle_candidates(ticker_code):
        if not os.path.exists(path):
            continue
        try:
            frames.append(_normalize_quote_frame(pd.read_pickle(path), ticker_code))
        except Exception:
            continue
    if not frames:
        return pd.DataFrame()
    merged = pd.concat(frames, ignore_index=True)
    return merged.drop_duplicates(subset=["Date"], keep="last").sort_values("Date").reset_index(drop=True)


def _save_checkpoint_frame(ticker_code, frame):
    normalized_code = _normalize_ticker_code(ticker_code)
    path = _checkpoint_pickle_path(normalized_code)
    normalized = _normalize_quote_frame(frame, ticker_code)
    existing = _load_existing_checkpoint(normalized_code)
    if not existing.empty:
        _backup_existing_file(path)
        merged = pd.concat([existing, normalized], ignore_index=True)
        normalized = merged.drop_duplicates(subset=["Date"], keep="last").sort_values("Date").reset_index(drop=True)
    _atomic_pickle_dump(path, normalized)
    for legacy_path in _checkpoint_pickle_candidates(normalized_code)[1:]:
        if os.path.exists(legacy_path):
            os.remove(legacy_path)
    for empty_path in _checkpoint_empty_candidates(normalized_code):
        if os.path.exists(empty_path):
            os.remove(empty_path)


def _mark_checkpoint_empty(ticker_code):
    empty_path = _checkpoint_empty_path(_normalize_ticker_code(ticker_code))
    with open(empty_path, "w", encoding="utf-8") as handle:
        handle.write("")


def _list_checkpointed_tickers():
    checkpointed = set()
    for filename in os.listdir(CHECKPOINT_DIR):
        stem, _ext = os.path.splitext(filename)
        checkpointed.add(stem)
    return checkpointed


def _load_output_cache_frame(output_path):
    if not os.path.exists(output_path):
        return None
    try:
        with open(output_path, "rb") as handle:
            cached = pickle.load(handle)
    except Exception:
        return None
    if not isinstance(getattr(cached, "columns", None), pd.MultiIndex):
        return None
    return cached


def _extract_ticker_history_from_output_cache(cached, ticker_code):
    if cached is None:
        return pd.DataFrame()

    ticker = f"{str(ticker_code)[:4]}.T"
    available_tickers = set(cached.columns.get_level_values(0))
    if ticker not in available_tickers:
        return pd.DataFrame()

    ticker_frame = cached.xs(ticker, axis=1, level=0, drop_level=True).copy()
    ticker_frame = ticker_frame.reset_index().rename(columns={"index": "Date"})
    ticker_frame["Code"] = str(ticker_code)
    ordered_cols = ["Date", "Code", "Open", "High", "Low", "Close", "Volume"]
    return _normalize_quote_frame(ticker_frame[ordered_cols], ticker_code)


def seed_missing_checkpoints_from_output_cache(output_path, ticker_codes):
    cached = _load_output_cache_frame(output_path)
    if cached is None:
        return 0

    seeded = 0
    for ticker_code in sorted({_normalize_ticker_code(code) for code in ticker_codes}):
        history = _extract_ticker_history_from_output_cache(cached, ticker_code)
        if history.empty:
            continue
        existing = _load_existing_checkpoint(ticker_code)
        if _checkpoint_needs_repair_from_cache(ticker_code, history, existing):
            _save_checkpoint_frame(ticker_code, history)
            seeded += 1
    return seeded


def _resolve_cached_universe_codes(output_path, checkpointed_tickers):
    cached_codes = set()
    cached = _load_output_cache_frame(output_path)
    if cached is not None:
        cached_codes = {
            _normalize_ticker_code(str(ticker).replace(".T", ""))
            for ticker in cached.columns.get_level_values(0).unique()
        }

    checkpoint_codes = {_normalize_ticker_code(code) for code in checkpointed_tickers}
    return sorted(code for code in (cached_codes | checkpoint_codes) if code)


def _checkpoint_covers_start_date(ticker_code, required_start_date):
    checkpoint = _load_existing_checkpoint(ticker_code)
    if checkpoint.empty:
        return False
    earliest = pd.Timestamp(checkpoint["Date"].min()).normalize()
    return earliest <= pd.Timestamp(required_start_date).normalize()


def resolve_full_refresh_target_tickers(ticker_codes, start_date):
    required_start = pd.Timestamp(str(start_date))
    target_tickers = []
    for ticker_code in sorted({_normalize_ticker_code(code) for code in ticker_codes}):
        if not _checkpoint_covers_start_date(ticker_code, required_start):
            target_tickers.append(ticker_code)
    return target_tickers


def _shorten_text(value, limit=240):
    text = str(value)
    return text if len(text) <= int(limit) else (text[: int(limit) - 3] + "...")


def _extract_subscription_floor_date_from_text(text):
    match = re.search(r"covers the following dates:\s*(\d{4}-\d{2}-\d{2})\s*~", str(text))
    return match.group(1) if match else None


def fetch_ticker_master_with_fallback(output_path, checkpointed_tickers, api_key, max_retries=4):
    _ensure_jquants_no_proxy()
    print("Handshaking with J-Quants ClientV2 for ticker master...")
    cli = jquantsapi.ClientV2(api_key=api_key)
    last_exc = None

    for attempt in range(max(1, int(max_retries))):
        try:
            info = cli.get_list()
            ticker_codes = sorted({str(code)[:4] for code in info["Code"].unique()})
            return ticker_codes, False
        except Exception as exc:
            last_exc = exc
            if "429" not in str(exc):
                break
            sleep_sec = 10 * (attempt + 1)
            print(
                f"Ticker master is rate-limited (attempt {attempt + 1}/{max_retries}). "
                f"Sleeping {sleep_sec}s before retry..."
            )
            time.sleep(sleep_sec)

    fallback_codes = _resolve_cached_universe_codes(output_path, checkpointed_tickers)
    if fallback_codes:
        print(
            "Ticker master fetch failed; falling back to the existing cache/checkpoint universe. "
            f"({len(fallback_codes)} codes)"
        )
        return fallback_codes, True

    print(f"Failed to fetch ticker list: {last_exc}")
    sys.exit(1)


def resolve_refresh_start_date(
    output_path=DEFAULT_OUTPUT_PATH,
    start_date=None,
    refresh_overlap_days=DEFAULT_REFRESH_OVERLAP_DAYS,
    force_full_refresh=False,
    default_start_date=DEFAULT_START_DATE,
):
    if start_date:
        return str(start_date)

    if force_full_refresh or not os.path.exists(output_path):
        return default_start_date

    try:
        with open(output_path, "rb") as handle:
            cached = pickle.load(handle)
        latest_cached_day = pd.Timestamp(cached.index.max()).normalize()
    except Exception:
        return default_start_date

    overlap_days = max(int(refresh_overlap_days), 0)
    refresh_start = latest_cached_day - timedelta(days=overlap_days)
    return max(default_start_date, refresh_start.strftime("%Y%m%d"))


def resolve_incremental_target_tickers(output_path, ticker_codes, checkpointed_tickers):
    normalized_checkpoint_codes = {_normalize_ticker_code(code) for code in checkpointed_tickers}
    try:
        with open(output_path, "rb") as handle:
            cached = pickle.load(handle)
        if isinstance(cached.columns, pd.MultiIndex):
            cached_tickers = {
                str(ticker).replace(".T", "")
                for ticker in cached.columns.get_level_values(0).unique()
            }
        else:
            cached_tickers = set()
    except Exception:
        return list(ticker_codes)

    master_codes = {_normalize_ticker_code(code) for code in ticker_codes}
    missing_checkpoint_codes = {
        _normalize_ticker_code(code)
        for code in ticker_codes
        if _normalize_ticker_code(code) not in normalized_checkpoint_codes
    }
    prioritized_codes = {code for code in cached_tickers if code in master_codes}
    return sorted(prioritized_codes | missing_checkpoint_codes)


def fetch_ticker_turbo(ticker_code, api_key, from_date, to_date):
    """
    Fetch one ticker and merge any overlapping rows back into the local checkpoint.
    """
    _ensure_jquants_no_proxy()
    code_raw = str(ticker_code)
    code = code_raw[:4]
    if len(code) == 4:
        code = code + "0"

    url = f"https://api.jquants.com/v2/equities/bars/daily?code={code}&from={from_date}&to={to_date}"
    headers = {"x-api-key": api_key}

    for attempt in range(3):
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                response_json = resp.json()
                data_list = response_json.get("data", [])
                if data_list:
                    fetched_df = _normalize_quote_frame(pd.DataFrame(data_list), ticker_code)
                    existing_df = _load_existing_checkpoint(ticker_code)
                    merged_df = pd.concat([existing_df, fetched_df], ignore_index=True)
                    merged_df = merged_df.drop_duplicates(subset=["Date"], keep="last")
                    merged_df = merged_df.sort_values("Date").reset_index(drop=True)
                    _save_checkpoint_frame(ticker_code, merged_df)
                    return f"SUCCESS:{ticker_code}"

                if _checkpoint_exists(ticker_code):
                    return f"NO_CHANGE:{ticker_code}"
                _mark_checkpoint_empty(ticker_code)
                return f"EMPTY:{ticker_code}"

            if resp.status_code == 429:
                time.sleep(10 * (attempt + 1))
                continue
            if resp.status_code == 401:
                return "AUTH_ERROR"

            floor_date = _extract_subscription_floor_date_from_text(resp.text)
            if resp.status_code == 400 and floor_date:
                return f"RANGE_ERROR:{_normalize_ticker_code(ticker_code)}:min_date={floor_date}"

            return (
                f"FAIL:{_normalize_ticker_code(ticker_code)}:status={resp.status_code}:"
                f"body={_shorten_text(resp.text)}"
            )

            time.sleep(2)
        except Exception as exc:
            if attempt == 2:
                return f"FAIL:{_normalize_ticker_code(ticker_code)}:exception={_shorten_text(exc)}"
            time.sleep(2)
    return f"FAIL:{_normalize_ticker_code(ticker_code)}:exhausted_retries"


def fetch_daily_quotes_for_date(api_key, target_date):
    """Fetch every listed issue for one date using the official bulk-date query."""
    _ensure_jquants_no_proxy()
    normalized_date = pd.Timestamp(target_date).strftime("%Y%m%d")
    url = f"https://api.jquants.com/v2/equities/bars/daily?date={normalized_date}"
    headers = {"x-api-key": api_key}

    for attempt in range(3):
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                response_json = resp.json()
                return _normalize_quote_frame(pd.DataFrame(response_json.get("data", [])), "")
            if resp.status_code == 429:
                time.sleep(10 * (attempt + 1))
                continue
            if resp.status_code == 401:
                raise RuntimeError("J-Quants token expired or invalid during bulk refresh.")
            floor_date = _extract_subscription_floor_date_from_text(resp.text)
            if resp.status_code == 400 and floor_date:
                raise RuntimeError(
                    f"Bulk refresh date {normalized_date} is before subscription floor {floor_date}."
                )
            raise RuntimeError(
                f"Bulk refresh failed for {normalized_date}: "
                f"status={resp.status_code} body={_shorten_text(resp.text)}"
            )
        except RuntimeError:
            raise
        except Exception as exc:
            if attempt == 2:
                raise RuntimeError(
                    f"Bulk refresh failed for {normalized_date}: exception={_shorten_text(exc)}"
                ) from exc
            time.sleep(2)
    raise RuntimeError(f"Bulk refresh exhausted retries for {normalized_date}.")


def refresh_incremental_checkpoints_by_date(api_key, start_date, end_date, target_tickers):
    """Refresh a short incremental window with one API request per business date."""
    normalized_targets = {_normalize_ticker_code(code) for code in target_tickers}
    requested_dates = [
        timestamp
        for timestamp in pd.date_range(
            pd.Timestamp(str(start_date)),
            pd.Timestamp(str(end_date)),
            freq="D",
        )
        if timestamp.weekday() < 5
    ]
    daily_frames = []
    for target_date in requested_dates:
        frame = fetch_daily_quotes_for_date(api_key, target_date)
        if frame.empty:
            print(f"Bulk refresh {target_date.date()}: no rows.")
            continue
        frame = frame.copy()
        frame["_TickerCode"] = frame["Code"].astype(str).str.slice(0, 4)
        frame = frame[frame["_TickerCode"].isin(normalized_targets)]
        if not frame.empty:
            daily_frames.append(frame)
        print(f"Bulk refresh {target_date.date()}: {len(frame)} target rows.")

    if not daily_frames:
        return {
            "requested_dates": len(requested_dates),
            "rows": 0,
            "tickers": 0,
        }

    combined = pd.concat(daily_frames, ignore_index=True)
    grouped = list(combined.groupby("_TickerCode", sort=True))
    for index, (ticker_code, frame) in enumerate(grouped, start=1):
        _save_checkpoint_frame(
            ticker_code,
            frame.drop(columns=["_TickerCode"]).reset_index(drop=True),
        )
        if index % 500 == 0:
            print(f"Bulk checkpoint merge: {index}/{len(grouped)} tickers.")

    return {
        "requested_dates": len(requested_dates),
        "rows": len(combined),
        "tickers": len(grouped),
    }


def fetch_jquants_v2_turbo_revelation(
    output_path=DEFAULT_OUTPUT_PATH,
    start_date=None,
    refresh_overlap_days=DEFAULT_REFRESH_OVERLAP_DAYS,
    force_full_refresh=False,
    max_workers=DEFAULT_MAX_WORKERS,
    limit_tickers=0,
    debug_failure_samples=5,
):
    """
    Official J-Quants cache refresh with checkpoint-aware incremental updates.
    """
    print("WARNING: Ensure your dataset includes delisted tickers to avoid survivorship bias.")
    global _REFRESH_BACKUP_TAG
    _REFRESH_BACKUP_TAG = datetime.now().strftime("%Y%m%d_%H%M%S")

    if os.path.exists(output_path) or os.path.isdir(CHECKPOINT_DIR):
        snapshot_root = _snapshot_current_cache_state(output_path=output_path)
        print(f"Created safety snapshot: {snapshot_root}")

    print("Running preflight cache audit before refresh...")
    _run_cache_audit_only(
        output_path=output_path,
        debug_failure_samples=debug_failure_samples,
        repair=True,
    )
    checkpointed_tickers = _list_checkpointed_tickers()
    normalized_checkpoint_codes = {_normalize_ticker_code(code) for code in checkpointed_tickers}

    api_key = os.getenv("JQUANTS_REFRESH_TOKEN")
    if not api_key:
        api_key = os.getenv("JQUANTS_API_KEY")

    if not api_key:
        print("Error: No J-Quants token found. Check .env.")
        sys.exit(1)

    api_key = api_key.strip()

    effective_start_date = resolve_refresh_start_date(
        output_path=output_path,
        start_date=start_date,
        refresh_overlap_days=refresh_overlap_days,
        force_full_refresh=force_full_refresh,
    )
    end_date = datetime.now().strftime("%Y%m%d")

    ticker_codes, _used_fallback_universe = fetch_ticker_master_with_fallback(
        output_path=output_path,
        checkpointed_tickers=checkpointed_tickers,
        api_key=api_key,
    )
    incremental_mode = (effective_start_date != DEFAULT_START_DATE) and not force_full_refresh
    if force_full_refresh:
        target_tickers = resolve_full_refresh_target_tickers(ticker_codes, effective_start_date)
    elif incremental_mode:
        # Even when the ticker master fetch falls back to the cached/checkpoint universe,
        # we still want to refresh every already-known ticker in that universe. Limiting
        # the target set to only missing checkpoints would turn an incremental refresh
        # into a no-op whenever the master endpoint is unavailable.
        target_tickers = resolve_incremental_target_tickers(output_path, ticker_codes, checkpointed_tickers)
    else:
        target_tickers = [
            _normalize_ticker_code(code)
            for code in ticker_codes
            if _normalize_ticker_code(code) not in normalized_checkpoint_codes
        ]
    if int(limit_tickers) > 0:
        target_tickers = target_tickers[: int(limit_tickers)]

    if force_full_refresh and target_tickers:
        probe_result = fetch_ticker_turbo(target_tickers[0], api_key, effective_start_date, end_date)
        if str(probe_result).startswith("RANGE_ERROR:"):
            min_date = str(probe_result).split("min_date=", 1)[1]
            normalized_min_date = min_date.replace("-", "")
            if normalized_min_date > str(effective_start_date):
                print(
                    "Detected subscription date floor from the API. "
                    f"Adjusting full-refresh start: {effective_start_date} -> {normalized_min_date}"
                )
                effective_start_date = normalized_min_date
                target_tickers = resolve_full_refresh_target_tickers(ticker_codes, effective_start_date)
                if int(limit_tickers) > 0:
                    target_tickers = target_tickers[: int(limit_tickers)]

    mode_label = "incremental refresh" if incremental_mode else ("full refresh" if force_full_refresh else "resume")
    print(f"MODE: {mode_label}")
    print(f"FETCH WINDOW: {effective_start_date} -> {end_date}")
    print(f"CHECKPOINTED TICKERS: {len(checkpointed_tickers)}")
    print(f"TARGET TICKERS: {len(target_tickers)} of {len(ticker_codes)}")

    bulk_refresh_used = False
    refresh_span_days = (
        pd.Timestamp(str(end_date)) - pd.Timestamp(str(effective_start_date))
    ).days + 1
    if (
        target_tickers
        and incremental_mode
        and refresh_span_days <= DEFAULT_BULK_REFRESH_MAX_DAYS
    ):
        try:
            bulk_summary = refresh_incremental_checkpoints_by_date(
                api_key=api_key,
                start_date=effective_start_date,
                end_date=end_date,
                target_tickers=target_tickers,
            )
            print(
                "Bulk incremental refresh completed: "
                f"dates={bulk_summary['requested_dates']} "
                f"rows={bulk_summary['rows']} "
                f"tickers={bulk_summary['tickers']}"
            )
            bulk_refresh_used = True
        except RuntimeError as exc:
            print(f"Bulk incremental refresh unavailable; falling back to per-ticker fetch: {exc}")

    if not target_tickers:
        print("All tickers already fetched. Proceeding to consolidation...")
    elif not bulk_refresh_used:
        with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as executor:
            future_to_ticker = {
                executor.submit(fetch_ticker_turbo, code, api_key, effective_start_date, end_date): code
                for code in target_tickers
            }
            count = 0
            status_counts = {}
            failure_samples = []
            for future in as_completed(future_to_ticker):
                result = future.result()
                count += 1
                result_prefix = str(result).split(":", 1)[0]
                status_counts[result_prefix] = status_counts.get(result_prefix, 0) + 1
                if (
                    result_prefix in {"FAIL", "RANGE_ERROR"}
                    and len(failure_samples) < max(0, int(debug_failure_samples))
                ):
                    failure_samples.append(str(result))
                    print(f"[FAIL_SAMPLE {len(failure_samples)}] {result}")
                if "AUTH_ERROR" in str(result):
                    print("API token expired or invalid. Stopping.")
                    break
                if count % 10 == 0:
                    progress = count / max(len(target_tickers), 1) * 100.0
                    print(
                        f"Refresh progress: {progress:.1f}% "
                        f"({count}/{len(target_tickers)} ticker fetches completed) | "
                        f"SUCCESS={status_counts.get('SUCCESS', 0)} "
                        f"NO_CHANGE={status_counts.get('NO_CHANGE', 0)} "
                        f"EMPTY={status_counts.get('EMPTY', 0)} "
                        f"RANGE_ERROR={status_counts.get('RANGE_ERROR', 0)} "
                        f"FAIL={status_counts.get('FAIL', 0)}"
                    )
                time.sleep(0.25)
            if failure_samples:
                print("Failure samples captured during refresh:")
                for item in failure_samples:
                    print(f" - {item}")

    print("Consolidating the definitive market history from checkpoints...")
    all_quotes = []
    checkpoint_files = [filename for filename in os.listdir(CHECKPOINT_DIR) if filename.endswith(".pkl")]
    total_files = len(checkpoint_files)
    for idx, checkpoint_file in enumerate(checkpoint_files, start=1):
        try:
            all_quotes.append(pd.read_pickle(os.path.join(CHECKPOINT_DIR, checkpoint_file)))
        except Exception:
            pass
        if idx % 500 == 0:
            print(f"Loading: {idx}/{total_files} checkpoints absorbed...")

    if not all_quotes:
        print("No data available to compile.")
        sys.exit(1)

    print(f"Stitching {len(all_quotes)} market fragments...")
    full_df = pd.concat(all_quotes, ignore_index=True)
    full_df["Ticker"] = full_df["Code"].astype(str).str.slice(0, 4) + ".T"
    full_df["Date"] = pd.to_datetime(full_df["Date"])
    full_df = full_df.drop_duplicates(subset=["Date", "Ticker"], keep="last")

    print("Creating consolidated price matrix...")
    pivot_df = full_df.pivot(index="Date", columns="Ticker", values=["Open", "High", "Low", "Close", "Volume"])
    pivot_df = pivot_df.swaplevel(0, 1, axis=1).sort_index(axis=1)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if os.path.exists(output_path):
        existing_cache = _load_output_cache_frame(output_path)
        if existing_cache is not None:
            existing_index = pd.DatetimeIndex(existing_cache.index).normalize()
            new_index = pd.DatetimeIndex(pivot_df.index).normalize()
            shrank = (
                len(new_index) < len(existing_index)
                or new_index.min() > existing_index.min()
                or new_index.max() < existing_index.max()
            )
            if shrank:
                backup_path = _backup_existing_file(output_path)
                raise RuntimeError(
                    "Refusing to overwrite consolidated JP cache with shorter history. "
                    f"Existing cache preserved at {backup_path or output_path}."
                )
        _backup_existing_file(output_path)
    _atomic_pickle_dump(output_path, pivot_df)

    latest_day = pd.Timestamp(pivot_df.index.max()).date()
    print(f"Cache refresh completed: {output_path} (latest day {latest_day})")


if __name__ == "__main__":
    args = parse_args()
    if args.list_backups:
        _print_backup_catalog()
        sys.exit(0)
    if args.restore_backup:
        restored = _restore_snapshot(args.restore_backup, output_path=args.output_path)
        print(
            f"Restored snapshot '{restored['snapshot_tag']}' "
            f"into {restored['restored_files']} files from {restored['snapshot_root']}."
        )
        cached = _load_output_cache_frame(args.output_path)
        if cached is not None:
            latest_day = pd.Timestamp(cached.index.max()).date()
            print(f"Restored consolidated cache latest day {latest_day} at {args.output_path}")
        sys.exit(0)
    if args.audit_only:
        _run_cache_audit_only(output_path=args.output_path, debug_failure_samples=args.debug_failure_samples)
        sys.exit(0)
    fetch_jquants_v2_turbo_revelation(
        output_path=args.output_path,
        start_date=args.start_date or None,
        refresh_overlap_days=args.refresh_overlap_days,
        force_full_refresh=args.force_full_refresh,
        max_workers=args.max_workers,
        limit_tickers=args.limit_tickers,
        debug_failure_samples=args.debug_failure_samples,
    )
