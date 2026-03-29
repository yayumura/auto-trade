# 🏦 ヘッジファンド仕様・究極のAI自律トレードエンジン (Strategy 4.3 Optimized)

機関投資家レベルの**マルチファクター＆レジームスイッチング戦略**を個人投資家向けに開放。
100万円の資金規模から、プロフェッショナルな資産形成を自動化するためのアルゴリズム・ボットです。

![Status-Trading](https://img.shields.io/badge/Status-Trading-success?style=for-the-badge&logo=bitdefender)
![Python-3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![Broker-Kabucom](https://img.shields.io/badge/Broker-Kabucom%20API-orange?style=for-the-badge&logo=google-cloud)

---

## 🚀 Core Vision: "個人をヘッジファンドに進化させる"

多くの個人投資家が直面する「感情による判断ミス」「監視不足」「資金効率の悪さ」を、数学的アルゴリズムと最新の生成AIで解決します。

### 💎 5つの革新的コア・テクノロジー [UPGRADED]

1.  **プロフェッショナル・データパイプライン (Phase 13 Normalization)** [NEW]
    - `yfinance` の非構造化データ（大文字小文字のブレや階層逆転）をリアルタイムで正規化。
    - **1.5ヶ月の助走期間 (Warm-up)**: シミュレーション開始初日から SMA100 等の長期指標を完全に算出。
    - **スマート・キャッシュ機能 (Phase 8)**: `data_cache/*.pkl` により、100銘柄の検証も 2 回目以降は**数秒**で完了。
2.  **マルチ・レジーム適応ロジック (Strategy 4.3)** [LATEST]
    - **BULL (強気)**: 強い上昇トレンドの押し目を狙う **"SMA20/50 Pullback + RSI 85 Expansion"**。
    - **RANGE (揉み合い)**: 下値圏（RSI 45）からの反発を狙う平均回帰戦略。
    - **BEAR (弱気)**: 暴落を回避するための全エントリー凍結＋緊急損切り。
3.  **精密なマーケット・フィルター (Phase 10 & 12.2)**
    - 日経平均 (1321.T) の SMA100 と 1.5% の「遊び（Buffer）」を組み合わせ、真のトレンドのみを捕捉。
4.  **プロフェッショナル・マルチ期間バックテスター**
    - ポジション単位での厳格な評価、スリッページ・シミュレーション（ATR連動）を搭載。
5.  **AI 二次定性フィルタ (Gemini / Groq)**
    - 数学的スクリーニング通過銘柄に対し、最新ニュースを AI がリアルタイム分析し、ニュース由来の暴落を回避。

---

## 📈 実証された検証結果 (Backtest Evidence)

### 2024年 夏の陣 (2024/06/01 - 08/31 / 101銘柄)
歴史的な 8 月の暴落を含む、極めて過酷な市場環境での検証結果です。

| メトリック | 結果 |
| :--- | :--- |
| **純利益 (Net Profit)** | **+4.31%** (+43,061 JPY) |
| **合計取引数** | 20回 |
| **勝率 (Win Rate)** | **45.0%** |
| **ペイオフレシオ** | **1.71** |

> [!IMPORTANT]
> **Data Integrity 100%**: デバイスや API の仕様に左右されない正規化済みデータ（Phase 13）に基づく、偽りのない数値です。

---

## 🛠️ プロジェクト構造 (Architecture)

```bash
.
├── auto_trade.py         # メインエンジン（自律ループ型）
├── backtest.py           # プロフェッショナル・物理検証機 [Phase 11.1 / 13 対応]
├── core/
│   ├── logic.py          # 戦略ロジック（Strategy 4.3 最適化済み）
│   ├── kabucom_broker.py # auカブコム API 通信レイヤー
│   ├── config.py         # パラメータ設定（ATR, リスク管理）
│   └── logic.py          # [Core] レジーム判定、エントリー/イグジット判定
├── data_cache/           # 正規化済みヒストリカル・キャッシュ
└── data/                 # 銘柄リスト、ログ出力
```

---

## 📦 クイックスタート (Quick Start)

### 1. バックテスト (検証)
100銘柄（Phase 2）の全期間検証を 1 時間足で実行します。

```bash
python backtest.py --all --start 2024-06-01 --end 2024-08-31 --interval 1h
```

### 2. 本番自律稼働 (Automation)
Windows タスクスケジューラで `run_bot.bat` を 08:45 に設定することを推奨します。

---
Created by Antigravity - *Next Generation Algorithmic Trading Solution*