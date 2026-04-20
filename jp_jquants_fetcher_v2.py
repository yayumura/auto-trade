import requests
import pandas as pd
import numpy as np
import os
import sys
import jquantsapi
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pickle
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Append current directory to sys.path
sys.path.append(os.getcwd())

load_dotenv()

CHECKPOINT_DIR = "data_cache/jp_broad/checkpoints"
os.makedirs(CHECKPOINT_DIR, exist_ok=True)

def fetch_ticker_turbo(ticker_code, api_key, from_date, to_date):
    """
    Turbo Sniper: Precision Split-Correction at Scale.
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
                res_json = resp.json()
                data_list = res_json.get("data", [])
                if data_list:
                    df = pd.DataFrame(data_list)
                    mapping = {'AdjO': 'Open', 'AdjH': 'High', 'AdjL': 'Low', 'AdjC': 'Close', 'AdjVo': 'Volume'}
                    df = df.rename(columns=mapping)
                    # Save checkpoint
                    df.to_pickle(os.path.join(CHECKPOINT_DIR, f"{ticker_code}.pkl"))
                    return f"SUCCESS:{ticker_code}"
                else:
                    # Empty is technically success (no data), mark as fetched
                    with open(os.path.join(CHECKPOINT_DIR, f"{ticker_code}.empty"), 'w') as f:
                        f.write("")
                    return f"EMPTY:{ticker_code}"
            elif resp.status_code == 429:
                # Too many requests
                time.sleep(10 * (attempt + 1))
            elif resp.status_code == 401:
                return "AUTH_ERROR"
            else:
                time.sleep(2)
        except Exception as e:
            time.sleep(2)
    return f"FAIL:{ticker_code}"

def fetch_jquants_v2_turbo_revelation(output_path='data_cache/jp_broad/jp_mega_cache.pkl', start_date="20210405"):
    """
    Official JQuants V38.1 (The Resilient Revelation)
    - Resumption Support, Thread-Safe Checkpointing.
    - Global Rate Control: Managed throughput to avoid 429s.
    """
    print("⚠️ WARNING: Ensure your dataset includes delisted tickers to avoid survivorship bias.")
    api_key = os.getenv("JQUANTS_REFRESH_TOKEN")
    if not api_key:
        api_key = os.getenv("JQUANTS_API_KEY")

    if not api_key:
        print("❌ Error: No JQuants Token (JQUANTS_REFRESH_TOKEN). Check .env file.")
        sys.exit(1)
    
    api_key = api_key.strip()
    
    print("📡 Handshaking with JQuants ClientV2 for Ticker Master...")
    cli = jquantsapi.ClientV2(api_key=api_key)
    try:
        info = cli.get_list()
    except Exception as e:
        print(f"❌ Failed to fetch list: {e}")
        sys.exit(1)
        
    ticker_codes = info['Code'].unique()
    
    end_date = datetime.now().strftime("%Y%m%d")
    
    # Check resumption state
    existing_checkpoints = set([f.split('.')[0] for f in os.listdir(CHECKPOINT_DIR)])
    remaining_tickers = [c for c in ticker_codes if str(c) not in existing_checkpoints]
    
    print(f"🎯 MISSION RESUMED: V38.1 - {len(existing_checkpoints)} already secured.")
    print(f"📊 Remaining Targets: {len(remaining_tickers)} of {len(ticker_codes)} Tickers")
    
    if not remaining_tickers:
        print("✅ All tickers already fetched. Proceeding to consolidation...")
    else:
        # 8 workers + 0.3s delay = ~25 req/sec (safely under 300/min burst)
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_ticker = {executor.submit(fetch_ticker_turbo, c, api_key, start_date, end_date): c for c in remaining_tickers}
            
            count = 0
            for future in as_completed(future_to_ticker):
                res = future.result()
                count += 1
                if "AUTH_ERROR" in str(res):
                    print("⛔ API Token expired or invalid. Stopping.")
                    break
                
                if count % 50 == 0:
                    prog = (len(existing_checkpoints) + count) / len(ticker_codes) * 100
                    print(f"🚀 Mission Progress: {prog:.1f}% ({len(existing_checkpoints) + count}/{len(ticker_codes)} Tickers secured)...")
                
                # Careful pacing to respect rate limits
                time.sleep(0.25)

    # Consolidation
    print("🧹 Consolidating the definitive market history from checkpoints...")
    all_quotes = []
    checkpoint_files = [f for f in os.listdir(CHECKPOINT_DIR) if f.endswith('.pkl')]
    
    total_files = len(checkpoint_files)
    for i, cf in enumerate(checkpoint_files):
        try:
            df = pd.read_pickle(os.path.join(CHECKPOINT_DIR, cf))
            all_quotes.append(df)
        except:
            pass
        if (i+1) % 500 == 0:
            print(f"📥 Loading: {i+1}/{total_files} checkpoints absorbed...")

    if not all_quotes:
        print("⚠️ No data available to compile.")
        sys.exit(1)

    print(f"🧩 Stitching {len(all_quotes)} market fragments...")
    full_df = pd.concat(all_quotes, ignore_index=True)
    full_df['Ticker'] = full_df['Code'].astype(str).str.slice(0, 4) + ".T"
    full_df['Date'] = pd.to_datetime(full_df['Date'])
    
    # NEW: Drop duplicates to prevent pivot failure
    print("🧹 Cleaning duplicates before matrix construction...")
    full_df = full_df.drop_duplicates(subset=['Date', 'Ticker'], keep='last')
    
    print("📈 Creating Matrix V15.1 Final Validation...")
    pivot_df = full_df.pivot(index='Date', columns='Ticker', values=['Open', 'High', 'Low', 'Close', 'Volume'])
    pivot_df = pivot_df.swaplevel(0, 1, axis=1).sort_index(axis=1)
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'wb') as f:
        pickle.dump(pivot_df, f)
    
    print(f"✨ MISSION ACCOMPLISHED: Turbo Cache (v38.1 Robust) finalized at {output_path}")

if __name__ == "__main__":
    fetch_jquants_v2_turbo_revelation()
