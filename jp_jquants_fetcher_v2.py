import argparse
import os
import pickle
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import jquantsapi
import pandas as pd
import requests
from dotenv import load_dotenv

# Append current directory to sys.path
sys.path.append(os.getcwd())

try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

load_dotenv()

CHECKPOINT_DIR = "data_cache/jp_broad/checkpoints"
DEFAULT_OUTPUT_PATH = "data_cache/jp_broad/jp_mega_cache.pkl"
DEFAULT_START_DATE = "20210405"
DEFAULT_REFRESH_OVERLAP_DAYS = 7
DEFAULT_MAX_WORKERS = 4

os.makedirs(CHECKPOINT_DIR, exist_ok=True)


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
    normalized.to_pickle(path)
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
        if _checkpoint_exists(ticker_code):
            continue
        history = _extract_ticker_history_from_output_cache(cached, ticker_code)
        if history.empty:
            continue
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

    checkpointed_tickers = _list_checkpointed_tickers()
    normalized_checkpoint_codes = {_normalize_ticker_code(code) for code in checkpointed_tickers}
    ticker_codes, used_fallback_universe = fetch_ticker_master_with_fallback(
        output_path=output_path,
        checkpointed_tickers=checkpointed_tickers,
        api_key=api_key,
    )
    if os.path.exists(output_path):
        seeded = seed_missing_checkpoints_from_output_cache(output_path, ticker_codes)
        if seeded:
            print(f"Seeded {seeded} checkpoint files from the existing consolidated cache.")
            checkpointed_tickers = _list_checkpointed_tickers()
    incremental_mode = (effective_start_date != DEFAULT_START_DATE) and not force_full_refresh
    if force_full_refresh:
        target_tickers = resolve_full_refresh_target_tickers(ticker_codes, effective_start_date)
    else:
        target_tickers = (
            resolve_incremental_target_tickers(output_path, ticker_codes, checkpointed_tickers)
            if incremental_mode and not used_fallback_universe
            else [
                _normalize_ticker_code(code)
                for code in ticker_codes
                if _normalize_ticker_code(code) not in normalized_checkpoint_codes
            ]
        )
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

    if not target_tickers:
        print("All tickers already fetched. Proceeding to consolidation...")
    else:
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
    with open(output_path, "wb") as handle:
        pickle.dump(pivot_df, handle)

    latest_day = pd.Timestamp(pivot_df.index.max()).date()
    print(f"Cache refresh completed: {output_path} (latest day {latest_day})")


if __name__ == "__main__":
    args = parse_args()
    fetch_jquants_v2_turbo_revelation(
        output_path=args.output_path,
        start_date=args.start_date or None,
        refresh_overlap_days=args.refresh_overlap_days,
        force_full_refresh=args.force_full_refresh,
        max_workers=args.max_workers,
        limit_tickers=args.limit_tickers,
        debug_failure_samples=args.debug_failure_samples,
    )
