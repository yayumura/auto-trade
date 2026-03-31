import subprocess
import os

# パラメータ設定 (Phase 28)
breakout_values = [15, 20, 25]
exit_values = [7, 10]
liquidity_values = [50000000, 100000000] # 50M, 100M
stop_mult = 2.5 # 2.0は狭すぎたので2.5で固定

start_date = "2021-01-01"
end_date = "2026-03-29"

results = []
print(f"Sweep Start (Phase 28): {len(breakout_values) * len(exit_values) * len(liquidity_values)} combinations")

for liq in liquidity_values:
    for b in breakout_values:
        for e in exit_values:
            if e >= b: continue 
            
            cmd = [
                "python", "-u", "backtest.py",
                "--all",
                "--start", start_date,
                "--end", end_date,
                "--breakout", str(b),
                "--exit", str(e),
                "--liquidity", str(liq),
                "--stop_mult", str(stop_mult)
            ]
            
            liq_label = f"{int(liq/1000000)}M"
            print(f"\n[Testing] B={b}, E={e}, Liq={liq_label} ...")
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            last_result = ""
            for line in process.stdout:
                if "RESULT:" in line:
                    last_result = line.strip()
                    print(f"  -> {last_result}")
            process.wait()
            results.append((b, e, liq_label, last_result))

print("\n\n" + "="*60)
print("PHASE 28 FINAL PARAMETER SWEEP RESULTS")
print("="*60)
for b, e, liq, res in results:
    print(f"B:{b:2d} E:{e:2d} Liq:{liq:<4s} | {res}")
