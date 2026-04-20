import os
import pickle
from pathlib import Path

import pandas as pd


DEFAULT_MARGIN_CACHE_PATH = Path("data_cache") / "jp_broad" / "jquants_margin_cache.pkl"


def load_margin_cache(path: str | os.PathLike = DEFAULT_MARGIN_CACHE_PATH) -> dict:
    cache_path = Path(path)
    if not cache_path.exists():
        return {}
    with cache_path.open("rb") as f:
        return pickle.load(f)


def save_margin_cache(cache: dict, path: str | os.PathLike = DEFAULT_MARGIN_CACHE_PATH) -> None:
    cache_path = Path(path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("wb") as f:
        pickle.dump(cache, f)


def normalize_margin_date(date_like) -> str:
    return pd.Timestamp(date_like).strftime("%Y-%m-%d")


def get_eligible_margin_codes_for_date(cache: dict, date_like) -> set[str] | None:
    if not cache:
        return None

    target_date = pd.Timestamp(date_like)
    normalized_dates = sorted(pd.Timestamp(key) for key in cache.keys())
    eligible_dates = [dt for dt in normalized_dates if dt <= target_date]
    if not eligible_dates:
        return None

    selected_key = eligible_dates[-1].strftime("%Y-%m-%d")
    selected_codes = cache.get(selected_key, {})
    eligible_codes = {
        str(code)
        for code, info in selected_codes.items()
        if str(info.get("MarginCode", "")) in {"1", "2"}
    }
    return eligible_codes or None
