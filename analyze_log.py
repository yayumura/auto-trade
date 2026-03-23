import re
import sys

def analyze():
    log_path = r'C:\Users\yayum\git_work\auto-trade\data\simulation\logs\console_2026-03-23.log'
    lines = []
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        with open(log_path, 'r', encoding='shift_jis') as f:
            lines = f.readlines()

    errors = []
    warnings = []
    trades = []
    balances = []
    purchases = []
    sales = []

    for line in lines:
        line = line.strip().replace('\r', '').replace('\n', '')
        if 'ERROR' in line or 'Exception' in line or '⚠️' in line:
            errors.append(line)
        if 'WARNING' in line:
            warnings.append(line)
        if '約定' in line or '発注' in line or '損益' in line or '売却' in line or '購入' in line:
            trades.append(line)
        if '合計資産額' in line:
            balances.append(line)
        if '購入' in line and '約定' in line:
             purchases.append(line)
        if '売却' in line and '約定' in line:
             sales.append(line)

    with open('analysis_result.txt', 'w', encoding='utf-8') as out:
        out.write(f"Total lines: {len(lines)}\n")
        out.write(f"Errors/Warnings count: {len(errors)}\n")
        unique_errors = list(set([re.sub(r'\[\d{2}:\d{2}:\d{2}\]', '', e).strip() for e in errors]))
        if unique_errors:
            out.write("Unique errors/warnings:\n")
            for e in unique_errors[:20]:
                out.write(f" - {e}\n")

        out.write(f"\nTrades info count: {len(trades)}\n")
        for t in trades[:30]:
            out.write(f" - {t}\n")
        
        out.write(f"\nPurchases count: {len(purchases)}\n")
        for p in purchases[:10]:
            out.write(f" - {p}\n")
            
        out.write(f"\nSales count: {len(sales)}\n")
        for s in sales[:10]:
            out.write(f" - {s}\n")

        out.write(f"\nBalances:\n")
        if balances:
            out.write(f"Initial Balance: {balances[0]}\n")
            out.write(f"Final Balance: {balances[-1]}\n")

if __name__ == '__main__':
    analyze()
