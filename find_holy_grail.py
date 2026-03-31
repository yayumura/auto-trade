import subprocess

# --- 聖杯ハンター (V10.2 真実のトレンド検索版) ---
# このスクリプトは、プライム市場に絞って「最も利益が出る設定」をお客様自身で探るためのツールです。

# 検証するパラメータ候補
breakouts = [20, 25, 30]
exits = [5, 10, 15]
positions = [3, 4] # 集中投資 vs 標準分散

print("Holy Grail Hunter (Peak Hunt Phase V10.2)...")
print("Target: PRIME Market Only")

results = []

for b in breakouts:
    for e in exits:
        for p in positions:
            cmd = [
                "python", "backtest.py",
                "--stocks", "prime",
                "--breakout", str(b),
                "--exit", str(e),
                "--max_pos", str(p)
            ]
            print(f"[Testing B:{b} E:{e} Pos:{p}] ...")
            
            # 結果取得
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            last_line = ""
            for line in process.stdout:
                if "FINAL VERIFIED RESULT:" in line:
                    last_line = line.strip()
                    print(f"  -> {last_line}")
            process.wait()
            results.append(last_line)

print("\n" + "="*70)
print("SEARCH COMPLETE - TOP RESULTS RANKING")
print("="*70)
for r in results:
    if r: print(r)
