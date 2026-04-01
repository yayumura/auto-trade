import subprocess
import re
import pandas as pd
import time

# --- Ultimate Parameter Optimizer (Windows Compatible) ---

# 検証したいパラメータ範囲
stocks = ["prime"]
breakouts = [15, 20, 25, 30]
exits = [5, 10, 15]
positions = [3, 5]
overheats = [25.0, 30.0, 40.0, 100.0]

print("Starting Ultimate Parameter Search (All Options enabled)...")
results = []
count = 0
total = len(stocks) * len(breakouts) * len(exits) * len(positions) * len(overheats)

for s in stocks:
    for b in breakouts:
        for e in exits:
            if e >= b: continue 
            for p in positions:
                for oh in overheats:
                    count += 1
                    cmd = [
                        "python", "backtest.py",
                        "--stocks", s,
                        "--breakout", str(b),
                        "--exit", str(e),
                        "--max_pos", str(p),
                        "--overheat", str(oh)
                    ]
                    # Windowsコンソール向けに絵文字を排除
                    print(f"[{count}/{total}] {s.upper()} B:{b} E:{e} Pos:{p} OH:{oh}% ... ", end="", flush=True)
                    
                    try:
                        # encoding指定で文字コードエラーを防止
                        process = subprocess.Popen(
                            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                            text=True, encoding='utf-8', errors='ignore'
                        )
                        stdout, stderr = process.communicate()
                        
                        # [RESULT]タグで始まる行を抽出
                        # [RESULT] Profit:+241.62% Trades:305 | MonthlyWin:52.0% Sharpe:0.172
                        match = re.search(r"\[RESULT\] Profit:([-+]?[\d\.]+)% Trades:(\d+) \| MonthlyWin:([\d\.]+)% Sharpe:([\d\.]+)", stdout)
                        
                        if match:
                            profit = float(match.group(1))
                            trades = int(match.group(2))
                            win_rate = float(match.group(3))
                            sharpe = float(match.group(4))
                            
                            print(f"Profit:{profit:+.2f}%, Sharpe:{sharpe:.3f}")
                            results.append({
                                "Market": s, "B": b, "E": e, "Pos": p, "OH": oh,
                                "Profit": profit, "Trades": trades, "MonthlyWin": win_rate, "Sharpe": sharpe
                            })
                        else:
                            print("FAILED (No result line found)")
                    except Exception as e_:
                        print(f"ERROR: {e_}")

df = pd.DataFrame(results)
if not df.empty:
    print("\n" + "="*80)
    print("SUMMARY: TOP 10 RESULTS BY SHARPE RATIO (STABILITY)")
    print("="*80)
    print(df.sort_values("Sharpe", ascending=False).head(10).to_string(index=False))

    print("\n" + "="*80)
    print("SUMMARY: TOP 10 RESULTS BY TOTAL PROFIT")
    print("="*80)
    print(df.sort_values("Profit", ascending=False).head(10).to_string(index=False))

    best_p = df.sort_values("Profit", ascending=False).iloc[0]
    print("\n" + "="*80)
    print(f"CURRENT ABSOLUTE CHAMPION")
    print("="*80)
    print(f"Settings: Market:{best_p['Market']}, B:{best_p['B']}, E:{best_p['E']}, Pos:{best_p['Pos']}, OH:{best_p['OH']}%")
    print(f"Result  : Profit:{best_p['Profit']:+.2f}%, Sharpe:{best_p['Sharpe']:.3f}, Trades:{int(best_p['Trades'])}")
