# -*- coding: utf-8 -*-
"""
🖥️ トレーディングダッシュボード
auto_trade.py が出力する CSV/JSON をブラウザで可視化するダッシュボード。
起動: python dashboard.py → http://127.0.0.1:5000
"""
import os
import json
import pandas as pd
from flask import Flask, jsonify

from core.config import ACCOUNT_FILE, PORTFOLIO_FILE, HISTORY_FILE, EXECUTION_LOG_FILE
from core.file_io import safe_read_json, safe_read_csv

app = Flask(__name__)


# ── API Endpoints ──────────────────────────────────────────────
def _read_csv_safe(path):
    return safe_read_csv(path)


@app.route('/api/account')
def api_account():
    account = safe_read_json(ACCOUNT_FILE)
    return jsonify(account if account is not None else {"cash": 0})


@app.route('/api/portfolio')
def api_portfolio():
    df = _read_csv_safe(PORTFOLIO_FILE)
    return jsonify(df.to_dict('records'))


@app.route('/api/history')
def api_history():
    df = _read_csv_safe(HISTORY_FILE)
    if not df.empty:
        # Normalize column names across schema versions
        if 'profit_amount' in df.columns and 'net_profit' not in df.columns:
            df['net_profit'] = df['profit_amount']
        if 'net_profit' not in df.columns:
            df['net_profit'] = 0
        if 'profit_pct' not in df.columns:
            df['profit_pct'] = 0
        df = df.sort_index(ascending=False)
        df = df.fillna(0)
    return jsonify(df.to_dict('records'))


@app.route('/api/execution_log')
def api_execution_log():
    df = _read_csv_safe(EXECUTION_LOG_FILE)
    return jsonify(df.to_dict('records'))


# ── Main HTML Page ─────────────────────────────────────────────
@app.route('/')
def index():
    return DASHBOARD_HTML


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Auto-Trade Dashboard</title>
<meta name="description" content="自動売買BOTのリアルタイムダッシュボード">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
/* ── Design Tokens ─────────────────────────────── */
:root {
  --bg-primary: #0a0e1a;
  --bg-secondary: #111827;
  --bg-card: rgba(17, 24, 39, 0.65);
  --bg-card-hover: rgba(30, 41, 59, 0.75);
  --border-card: rgba(99, 102, 241, 0.18);
  --border-card-hover: rgba(99, 102, 241, 0.35);
  --text-primary: #f1f5f9;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --accent-indigo: #818cf8;
  --accent-violet: #a78bfa;
  --accent-cyan: #22d3ee;
  --color-profit: #34d399;
  --color-profit-bg: rgba(52, 211, 153, 0.12);
  --color-loss: #fb7185;
  --color-loss-bg: rgba(251, 113, 133, 0.12);
  --color-neutral: #fbbf24;
  --gradient-hero: linear-gradient(135deg, #0a0e1a 0%, #1e1b4b 50%, #0a0e1a 100%);
  --gradient-accent: linear-gradient(135deg, #6366f1, #8b5cf6, #06b6d4);
  --shadow-card: 0 4px 24px rgba(0,0,0,0.35), 0 1px 3px rgba(0,0,0,0.25);
  --shadow-glow: 0 0 40px rgba(99, 102, 241, 0.08);
  --radius: 16px;
  --radius-sm: 10px;
  --font-sans: 'Inter', 'Noto Sans JP', system-ui, sans-serif;
  --transition: 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

/* ── Reset & Base ──────────────────────────────── */
*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  font-family: var(--font-sans);
  background: var(--gradient-hero);
  color: var(--text-primary);
  min-height: 100vh;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}

/* Animated bg particles */
body::before {
  content: '';
  position: fixed; inset: 0; z-index: -1;
  background: radial-gradient(ellipse 600px 600px at 20% 30%, rgba(99,102,241,0.07) 0%, transparent 70%),
              radial-gradient(ellipse 500px 500px at 80% 70%, rgba(139,92,246,0.06) 0%, transparent 70%);
  animation: bgPulse 12s ease-in-out infinite alternate;
}
@keyframes bgPulse {
  0% { opacity: 0.6; }
  100% { opacity: 1; }
}

/* ── Layout ────────────────────────────────────── */
.dashboard {
  max-width: 1360px;
  margin: 0 auto;
  padding: 24px 28px 60px;
}

/* ── Header ────────────────────────────────────── */
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 32px;
  padding-bottom: 24px;
  border-bottom: 1px solid rgba(99, 102, 241, 0.12);
}
.header-left { display: flex; align-items: center; gap: 14px; }
.header h1 {
  font-size: 1.65rem;
  font-weight: 800;
  background: var(--gradient-accent);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: -0.02em;
}
.header-logo {
  width: 38px; height: 38px;
  background: var(--gradient-accent);
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.2rem;
  box-shadow: 0 0 20px rgba(99,102,241,0.25);
}
.header-right {
  display: flex; align-items: center; gap: 16px;
  font-size: 0.82rem; color: var(--text-muted);
}
.status-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--color-profit);
  animation: pulse 2s ease-in-out infinite;
  display: inline-block;
}
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
.btn-refresh {
  background: rgba(99,102,241,0.12);
  border: 1px solid rgba(99,102,241,0.25);
  color: var(--accent-indigo);
  padding: 7px 16px;
  border-radius: 8px;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: var(--transition);
  font-family: var(--font-sans);
}
.btn-refresh:hover {
  background: rgba(99,102,241,0.22);
  border-color: rgba(99,102,241,0.5);
  transform: translateY(-1px);
}

/* ── Summary Cards ─────────────────────────────── */
.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 18px;
  margin-bottom: 32px;
}
.card {
  background: var(--bg-card);
  backdrop-filter: blur(24px) saturate(1.4);
  -webkit-backdrop-filter: blur(24px) saturate(1.4);
  border: 1px solid var(--border-card);
  border-radius: var(--radius);
  padding: 22px 24px;
  box-shadow: var(--shadow-card);
  transition: var(--transition);
  position: relative;
  overflow: hidden;
  animation: cardIn 0.5s ease-out both;
}
.card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: var(--gradient-accent);
  opacity: 0;
  transition: var(--transition);
}
.card:hover {
  border-color: var(--border-card-hover);
  transform: translateY(-3px);
  box-shadow: var(--shadow-card), var(--shadow-glow);
}
.card:hover::before { opacity: 1; }
@keyframes cardIn {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}
.card:nth-child(2) { animation-delay: 0.06s; }
.card:nth-child(3) { animation-delay: 0.12s; }
.card:nth-child(4) { animation-delay: 0.18s; }

.card-icon {
  width: 40px; height: 40px;
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.15rem;
  margin-bottom: 14px;
}
.card-icon.total  { background: rgba(99,102,241,0.15); }
.card-icon.cash   { background: rgba(34,211,238,0.13); }
.card-icon.stock  { background: rgba(167,139,250,0.14); }
.card-icon.pnl    { background: rgba(52,211,153,0.12); }

.card-label {
  font-size: 0.78rem;
  color: var(--text-muted);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 6px;
}
.card-value {
  font-size: 1.7rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.card-sub {
  font-size: 0.78rem;
  color: var(--text-secondary);
  margin-top: 4px;
}

/* ── Section (Chart / Tables) ──────────────────── */
.section {
  background: var(--bg-card);
  backdrop-filter: blur(24px) saturate(1.4);
  -webkit-backdrop-filter: blur(24px) saturate(1.4);
  border: 1px solid var(--border-card);
  border-radius: var(--radius);
  padding: 24px 28px;
  box-shadow: var(--shadow-card);
  margin-bottom: 24px;
  animation: cardIn 0.5s ease-out both;
}
.section-title {
  font-size: 1.05rem;
  font-weight: 700;
  margin-bottom: 18px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.section-title .emoji { font-size: 1.15rem; }
.section-badge {
  font-size: 0.7rem;
  font-weight: 600;
  background: rgba(99,102,241,0.12);
  color: var(--accent-indigo);
  padding: 3px 10px;
  border-radius: 20px;
  margin-left: 8px;
}

/* ── Chart ─────────────────────────────────────── */
.chart-container {
  position: relative;
  height: 320px;
  width: 100%;
}

/* ── Tables ────────────────────────────────────── */
.table-wrap { overflow-x: auto; }
table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 0.84rem;
}
thead th {
  text-align: left;
  padding: 10px 14px;
  color: var(--text-muted);
  font-weight: 600;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  border-bottom: 1px solid rgba(99,102,241,0.12);
  white-space: nowrap;
  position: sticky;
  top: 0;
  background: var(--bg-card);
}
tbody td {
  padding: 11px 14px;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  white-space: nowrap;
  transition: background var(--transition);
}
tbody tr:hover td { background: rgba(99,102,241,0.05); }
.text-right { text-align: right; }
.text-profit { color: var(--color-profit); }
.text-loss   { color: var(--color-loss); }
.text-neutral { color: var(--color-neutral); }
.badge-profit {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 6px;
  font-weight: 600;
  font-size: 0.78rem;
}
.badge-profit.positive { background: var(--color-profit-bg); color: var(--color-profit); }
.badge-profit.negative { background: var(--color-loss-bg); color: var(--color-loss); }

/* ── Empty State ───────────────────────────────── */
.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: var(--text-muted);
  font-size: 0.9rem;
}
.empty-state .icon { font-size: 2rem; margin-bottom: 8px; }

/* ── Footer ────────────────────────────────────── */
.footer {
  text-align: center;
  padding: 24px 0 0;
  color: var(--text-muted);
  font-size: 0.72rem;
}

/* ── Responsive ────────────────────────────────── */
@media (max-width: 768px) {
  .dashboard { padding: 16px 14px 40px; }
  .header h1 { font-size: 1.3rem; }
  .summary-grid { grid-template-columns: repeat(2, 1fr); gap: 12px; }
  .card { padding: 16px 18px; }
  .card-value { font-size: 1.3rem; }
  .chart-container { height: 240px; }
  .section { padding: 18px 16px; }
}
@media (max-width: 480px) {
  .summary-grid { grid-template-columns: 1fr; }
}
</style>
</head>
<body>
<div class="dashboard">

  <!-- ── Header ─────────────────────────────────── -->
  <header class="header">
    <div class="header-left">
      <div class="header-logo">📈</div>
      <h1>Auto-Trade Dashboard</h1>
    </div>
    <div class="header-right">
      <span><span class="status-dot"></span> Live</span>
      <span id="lastUpdate">--</span>
      <button class="btn-refresh" id="btnRefresh" onclick="loadAll()">↻ 更新</button>
    </div>
  </header>

  <!-- ── Summary Cards ──────────────────────────── -->
  <div class="summary-grid">
    <div class="card">
      <div class="card-icon total">👑</div>
      <div class="card-label">合計資産額</div>
      <div class="card-value" id="totalAssets">--</div>
      <div class="card-sub" id="totalAssetsSub"></div>
    </div>
    <div class="card">
      <div class="card-icon cash">💰</div>
      <div class="card-label">現金残高</div>
      <div class="card-value" id="cashBalance">--</div>
      <div class="card-sub" id="cashSub"></div>
    </div>
    <div class="card">
      <div class="card-icon stock">📊</div>
      <div class="card-label">株式評価額</div>
      <div class="card-value" id="stockValue">--</div>
      <div class="card-sub" id="stockSub"></div>
    </div>
    <div class="card">
      <div class="card-icon pnl">💹</div>
      <div class="card-label">実現損益合計</div>
      <div class="card-value" id="realizedPnl">--</div>
      <div class="card-sub" id="pnlSub"></div>
    </div>
  </div>

  <!-- ── Asset Chart ────────────────────────────── -->
  <div class="section" style="animation-delay:0.24s">
    <div class="section-title">
      <span class="emoji">📈</span> 資産推移
      <span class="section-badge" id="chartBadge">--</span>
    </div>
    <div class="chart-container">
      <canvas id="assetChart"></canvas>
    </div>
  </div>

  <!-- ── Portfolio ──────────────────────────────── -->
  <div class="section" style="animation-delay:0.30s">
    <div class="section-title">
      <span class="emoji">💼</span> 現在の保有銘柄
      <span class="section-badge" id="portfolioBadge">0 銘柄</span>
    </div>
    <div class="table-wrap" id="portfolioTable"></div>
  </div>

  <!-- ── Trade History ──────────────────────────── -->
  <div class="section" style="animation-delay:0.36s">
    <div class="section-title">
      <span class="emoji">📜</span> 売買履歴
      <span class="section-badge" id="historyBadge">0 件</span>
    </div>
    <div class="table-wrap" id="historyTable"></div>
  </div>

  <div class="footer">Auto-Trade Dashboard — データは60秒ごとに自動更新されます</div>
</div>

<script>
// ── Utilities ──────────────────────────────────────
const fmt = (n) => {
  if (n == null || isNaN(n)) return '--';
  return Number(n).toLocaleString('ja-JP', { maximumFractionDigits: 0 });
};
const fmtPct = (n) => {
  if (n == null || isNaN(n)) return '--';
  return (Number(n) * 100).toFixed(2) + '%';
};
const fmtPrice = (n) => {
  if (n == null || isNaN(n)) return '--';
  return Number(n).toLocaleString('ja-JP', { maximumFractionDigits: 1 });
};
const pnlClass = (v) => v > 0 ? 'text-profit' : v < 0 ? 'text-loss' : '';
const badgeClass = (v) => v > 0 ? 'positive' : v < 0 ? 'negative' : '';

// ── Chart Setup ────────────────────────────────────
let assetChart = null;
function initChart() {
  const ctx = document.getElementById('assetChart').getContext('2d');
  const gradient = ctx.createLinearGradient(0, 0, 0, 320);
  gradient.addColorStop(0, 'rgba(99, 102, 241, 0.25)');
  gradient.addColorStop(0.5, 'rgba(139, 92, 246, 0.08)');
  gradient.addColorStop(1, 'rgba(6, 182, 212, 0.01)');

  assetChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: '合計資産 (¥)',
        data: [],
        borderColor: '#818cf8',
        backgroundColor: gradient,
        borderWidth: 2.5,
        fill: true,
        tension: 0.35,
        pointRadius: 0,
        pointHitRadius: 12,
        pointHoverRadius: 5,
        pointHoverBackgroundColor: '#818cf8',
        pointHoverBorderColor: '#fff',
        pointHoverBorderWidth: 2,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(15,23,42,0.92)',
          titleColor: '#94a3b8',
          bodyColor: '#f1f5f9',
          borderColor: 'rgba(99,102,241,0.25)',
          borderWidth: 1,
          padding: 12,
          titleFont: { family: "'Inter','Noto Sans JP',sans-serif", size: 11 },
          bodyFont: { family: "'Inter','Noto Sans JP',sans-serif", size: 13, weight: 600 },
          callbacks: {
            label: (ctx) => '¥' + fmt(ctx.parsed.y)
          }
        }
      },
      scales: {
        x: {
          ticks: { color: '#475569', maxTicksLimit: 10, font: { size: 11 } },
          grid: { color: 'rgba(99,102,241,0.06)' },
          border: { color: 'rgba(99,102,241,0.08)' }
        },
        y: {
          ticks: {
            color: '#475569',
            font: { size: 11 },
            callback: (v) => '¥' + (v / 10000).toFixed(0) + '万'
          },
          grid: { color: 'rgba(99,102,241,0.06)' },
          border: { color: 'rgba(99,102,241,0.08)' }
        }
      }
    }
  });
}

// ── Data Loading ───────────────────────────────────
async function loadAll() {
  try {
    const [accRes, portRes, histRes, logRes] = await Promise.all([
      fetch('/api/account'),
      fetch('/api/portfolio'),
      fetch('/api/history'),
      fetch('/api/execution_log'),
    ]);
    const account = await accRes.json();
    const portfolio = await portRes.json();
    const history = await histRes.json();
    const execLog = await logRes.json();

    renderSummary(account, portfolio, history, execLog);
    renderChart(execLog);
    renderPortfolio(portfolio);
    renderHistory(history);

    document.getElementById('lastUpdate').textContent =
      '更新: ' + new Date().toLocaleTimeString('ja-JP');
  } catch (err) {
    console.error('Data load error:', err);
  }
}

// ── Render Summary Cards ───────────────────────────
function renderSummary(account, portfolio, history, execLog) {
  const cash = account.cash || 0;
  let stockValue = 0;
  portfolio.forEach(p => {
    const price = p.current_price || p.buy_price || 0;
    stockValue += price * (p.shares || 0);
  });
  const totalAssets = cash + stockValue;

  let realizedPnl = 0;
  history.forEach(h => { realizedPnl += (h.net_profit || 0); });

  document.getElementById('totalAssets').textContent = '¥' + fmt(totalAssets);
  document.getElementById('cashBalance').textContent = '¥' + fmt(cash);
  document.getElementById('stockValue').textContent = '¥' + fmt(stockValue);

  const pnlEl = document.getElementById('realizedPnl');
  pnlEl.textContent = (realizedPnl >= 0 ? '+' : '') + '¥' + fmt(realizedPnl);
  pnlEl.className = 'card-value ' + pnlClass(realizedPnl);

  // Sub info
  const cashPct = totalAssets > 0 ? (cash / totalAssets * 100).toFixed(1) : 0;
  const stockPct = totalAssets > 0 ? (stockValue / totalAssets * 100).toFixed(1) : 0;
  document.getElementById('totalAssetsSub').textContent = portfolio.length + ' 銘柄保有中';
  document.getElementById('cashSub').textContent = '資産の ' + cashPct + '%';
  document.getElementById('stockSub').textContent = '資産の ' + stockPct + '%';
  document.getElementById('pnlSub').textContent = history.length + ' 件の取引';
}

// ── Render Chart ───────────────────────────────────
function renderChart(execLog) {
  if (!execLog.length) {
    document.getElementById('chartBadge').textContent = 'データなし';
    return;
  }
  const labels = execLog.map(e => {
    const t = e.time || '';
    // Show just MM/DD HH:mm
    const parts = t.split(' ');
    if (parts.length >= 2) {
      const dateParts = parts[0].split('-');
      return (dateParts[1] || '') + '/' + (dateParts[2] || '') + ' ' + parts[1].substring(0, 5);
    }
    return t;
  });
  const data = execLog.map(e => e.total_assets_yen || 0);

  assetChart.data.labels = labels;
  assetChart.data.datasets[0].data = data;
  assetChart.update('none');

  const first = data[0] || 1;
  const last = data[data.length - 1] || 0;
  const changePct = ((last - first) / first * 100).toFixed(2);
  const badge = document.getElementById('chartBadge');
  badge.textContent = (changePct >= 0 ? '+' : '') + changePct + '%';
  badge.style.color = changePct >= 0 ? 'var(--color-profit)' : 'var(--color-loss)';
  badge.style.background = changePct >= 0 ? 'var(--color-profit-bg)' : 'var(--color-loss-bg)';
}

// ── Render Portfolio Table ─────────────────────────
function renderPortfolio(portfolio) {
  const container = document.getElementById('portfolioTable');
  const badge = document.getElementById('portfolioBadge');
  badge.textContent = portfolio.length + ' 銘柄';

  if (!portfolio.length) {
    container.innerHTML = '<div class="empty-state"><div class="icon">📭</div>現在の保有銘柄はありません</div>';
    return;
  }

  let html = `<table>
    <thead><tr>
      <th>コード</th><th>銘柄名</th><th>購入日時</th>
      <th class="text-right">買値 (¥)</th><th class="text-right">現在値 (¥)</th>
      <th class="text-right">数量</th><th class="text-right">評価額 (¥)</th>
      <th class="text-right">損益率</th>
    </tr></thead><tbody>`;

  portfolio.forEach(p => {
    const buyP = p.buy_price || 0;
    const curP = p.current_price || buyP;
    const shares = p.shares || 0;
    const valuation = curP * shares;
    const pctChange = buyP > 0 ? (curP - buyP) / buyP : 0;
    const cls = pnlClass(pctChange);

    html += `<tr>
      <td><strong>${p.code || '--'}</strong></td>
      <td>${p.name || '--'}</td>
      <td style="color:var(--text-secondary)">${p.buy_time || '--'}</td>
      <td class="text-right">${fmtPrice(buyP)}</td>
      <td class="text-right ${cls}">${fmtPrice(curP)}</td>
      <td class="text-right">${fmt(shares)} 株</td>
      <td class="text-right">${fmt(valuation)}</td>
      <td class="text-right"><span class="badge-profit ${badgeClass(pctChange)}">${(pctChange >= 0 ? '+' : '') + (pctChange * 100).toFixed(2)}%</span></td>
    </tr>`;
  });

  html += '</tbody></table>';
  container.innerHTML = html;
}

// ── Render History Table ───────────────────────────
function renderHistory(history) {
  const container = document.getElementById('historyTable');
  const badge = document.getElementById('historyBadge');
  badge.textContent = history.length + ' 件';

  if (!history.length) {
    container.innerHTML = '<div class="empty-state"><div class="icon">📝</div>売買履歴はまだありません</div>';
    return;
  }

  let html = `<table>
    <thead><tr>
      <th>決済日時</th><th>コード</th><th>銘柄名</th>
      <th class="text-right">買値</th><th class="text-right">売値</th>
      <th class="text-right">数量</th><th class="text-right">税引後損益</th>
      <th class="text-right">損益率</th><th>理由</th>
    </tr></thead><tbody>`;

  history.forEach(h => {
    const netP = h.net_profit || 0;
    const pct = h.profit_pct || 0;
    const cls = pnlClass(netP);

    html += `<tr>
      <td style="color:var(--text-secondary)">${h.sell_time || '--'}</td>
      <td><strong>${h.code || '--'}</strong></td>
      <td>${h.name || '--'}</td>
      <td class="text-right">${fmtPrice(h.buy_price)}</td>
      <td class="text-right">${fmtPrice(h.sell_price)}</td>
      <td class="text-right">${fmt(h.shares)} 株</td>
      <td class="text-right ${cls}"><strong>${(netP >= 0 ? '+' : '') + fmt(netP)}</strong></td>
      <td class="text-right"><span class="badge-profit ${badgeClass(pct)}">${(pct >= 0 ? '+' : '') + (pct * 100).toFixed(2)}%</span></td>
      <td style="color:var(--text-secondary);font-size:0.78rem;max-width:200px;overflow:hidden;text-overflow:ellipsis">${h.reason || '--'}</td>
    </tr>`;
  });

  html += '</tbody></table>';
  container.innerHTML = html;
}

// ── Init ───────────────────────────────────────────
initChart();
loadAll();
setInterval(loadAll, 60000);
</script>
</body>
</html>
"""

if __name__ == '__main__':
    print("\n🖥️  ダッシュボードを起動します...")
    print("📡  http://127.0.0.1:5000 をブラウザで開いてください\n")
    app.run(debug=True, host='127.0.0.1', port=5000)
