import os
import sys
import datetime
import subprocess

def run_script(script_name):
    print(f"\n🚀 [IMPERIAL_CYCLE] Starting: {script_name}")
    try:
        # Pass sys.executable to ensure we use the same Python interpreter
        result = subprocess.run([sys.executable, script_name], check=True)
        print(f"✅ [IMPERIAL_CYCLE] Completed: {script_name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ [IMPERIAL_CYCLE] Error in {script_name}: {e}")
        return False

def main():
    now = datetime.datetime.now()
    hour = now.hour
    minute = now.minute
    time_val = hour * 100 + minute # e.g. 845 for 08:45
    
    print(f"📅 Current Time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)
    
    # --- [ Imperial Orchestrator: Sequential Flow ] ---
    # This orchestrator is now designed to be launched ONCE per day via the .bat file.

    if time_val > 1530:
        print("🌙 [NIGHT PHASE] Market is already closed for today.")
        print("📊 TASK: OFF-MARKET ANALYSIS (BACKTEST)")
        run_script("jp_backtest.py")
    else:
        print("☀️ [DAY PHASE] Initiating daily sequence...")
        
        # 1. ALWAYS ensure we have the latest EOD data for the scanner
        print("📡 STEP 1: DATA SYNC (JQuants)")
        run_script("jp_jquants_fetcher_v2.py")
        
        # 2. Start the autonomous trading bot (This will block & run infinitely until 15:30)
        print("🤖 STEP 2: LIVE TRADING SESSION")
        run_script("auto_trade.py")
        
        # 3. After the bot gracefully shuts down at 15:30, run the daily integrity check (backtest)
        print("📊 STEP 3: OFF-MARKET ANALYSIS (BACKTEST)")
        run_script("jp_backtest.py")

    print("\n" + "="*50)
    print("🏁 Imperial Cycle Execution Finished.")

if __name__ == "__main__":
    main()
