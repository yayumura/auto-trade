import json
import os
import datetime
from .config import WATCHLIST_FILE

def save_watchlist(candidates, filename=WATCHLIST_FILE):
    """
    Save list of monster candidates to JSON.
    Auto-creates the directory if it does not exist.
    """
    # [Professional Upgrade] Ensure the data sanctuary exists before writing
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    data = {
        "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "candidates": candidates
    }
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"✅ Watchlist persisted to {filename} ({len(candidates)} symbols)")

def load_watchlist(filename=WATCHLIST_FILE):
    """
    Load the monster watchlist.
    """
    if not os.path.exists(filename):
        return []
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("candidates", [])
    except:
        return []

def clear_watchlist(filename=WATCHLIST_FILE):
    if os.path.exists(filename):
        os.remove(filename)
