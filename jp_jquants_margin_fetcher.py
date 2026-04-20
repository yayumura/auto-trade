import os
import sys
from datetime import datetime

import jquantsapi
import pandas as pd
from dotenv import load_dotenv

from core.jquants_margin_cache import normalize_margin_date, save_margin_cache


def fetch_margin_cache(output_path="data_cache/jp_broad/jquants_margin_cache.pkl", start_date="2022-01-31"):
    load_dotenv()

    api_key = os.getenv("JQUANTS_REFRESH_TOKEN") or os.getenv("JQUANTS_API_KEY")
    if not api_key:
        print("❌ Error: No J-Quants token found.")
        sys.exit(1)

    cli = jquantsapi.ClientV2(api_key=api_key.strip())
    month_ends = pd.date_range(start=start_date, end=datetime.now(), freq="BME")
    cache = {}

    for dt in month_ends:
        date_key = normalize_margin_date(dt)
        print(f"Fetching J-Quants listed info for {date_key} ...")
        listed = cli.get_list(date_yyyymmdd=dt.strftime("%Y%m%d"))
        if listed is None or listed.empty:
            cache[date_key] = {}
            continue

        columns = ["Code", "MarginCode", "MarginCodeName", "MarketCodeName"]
        available_cols = [col for col in columns if col in listed.columns]
        slim = listed[available_cols].copy()
        slim["Code"] = slim["Code"].astype(str).str.slice(0, 4)
        cache[date_key] = {
            str(row["Code"]): {
                "MarginCode": str(row.get("MarginCode", "")),
                "MarginCodeName": row.get("MarginCodeName", ""),
                "MarketCodeName": row.get("MarketCodeName", ""),
            }
            for _, row in slim.iterrows()
        }

    save_margin_cache(cache, output_path)
    print(f"Saved J-Quants margin cache to {output_path}")


if __name__ == "__main__":
    fetch_margin_cache()
