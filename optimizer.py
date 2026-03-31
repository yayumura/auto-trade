import subprocess
import re
import pandas as pd

# --- Parameter Optimizer (Searching for Consistency) ---

breakouts = [10, 20, 25, 30]
exits = [5, 10, 15]
positions = [3, 5, 10]

print("Starting Parameter Optimization for Consistency...")
results = []

for b in breakouts:
    for e in exits:
        if e >= b: continue # Avoid senseless parameters
        for p in positions:
            cmd = [
                "python", "backtest.py",
                "--stocks", "prime",
                "--breakout", str(b),
                "--exit", str(e),
                "--max_pos", str(p)
            ]
            print(f"[Testing B:{b} E:{e} Pos:{p}] ... ", end="", flush=True)
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate()
            
            # Use regex to parse the output
            # FINAL VERIFIED RESULT: Market:PRIME B:20 E:10 Pos:3 | Profit:+201.85% Trades:190 | MonthlyWin:44.0% Sharpe:0.163
            match = re.search(r"Profit:([-+]?\d*\.?\d+)% Trades:(\d+) \| MonthlyWin:(\d*\.?\d+)% Sharpe:(\d*\.?\d+)", stdout)
            
            if match:
                profit = float(match.group(1))
                trades = int(match.group(2))
                win_rate = float(match.group(3))
                sharpe = float(match.group(4))
                
                print(f"Profit:{profit:+.2f}%, WinRate:{win_rate:.1f}%, Sharpe:{sharpe:.3f}")
                results.append({
                    "B": b, "E": e, "Pos": p,
                    "Profit": profit, "Trades": trades, "MonthlyWin": win_rate, "Sharpe": sharpe
                })
            else:
                print("FAILED")
                # print(stdout) # For debugging if needed

# Convert to DataFrame for better analysis
df = pd.DataFrame(results)
if not df.empty:
    print("\n" + "="*80)
    print("TOP RESULTS BY SHARPE RATIO (CONSISTENCY)")
    print("="*80)
    print(df.sort_values("Sharpe", ascending=False).head(10).to_string(index=False))

    print("\n" + "="*80)
    print("TOP RESULTS BY TOTAL PROFIT")
    print("="*80)
    print(df.sort_values("Profit", ascending=False).head(10).to_string(index=False))

    best = df.sort_values("Sharpe", ascending=False).iloc[0]
    print(f"\nRecommended Settings for CONSISTENCY: B={best['B']}, E={best['E']}, Pos={best['Pos']} (Sharpe: {best['Sharpe']:.3f})")

    best_p = df.sort_values("Profit", ascending=False).iloc[0]
    print(f"Recommended Settings for MAX PROFIT: B={best_p['B']}, E={best_p['E']}, Pos={best_p['Pos']} (Profit: {best_p['Profit']:+.2f}%)")
