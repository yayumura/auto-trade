# 🏦 ヘッジファンド仕様・究極のAI自律トレードエンジン (1M JPY Optimized)

機関投資家レベルの**マルチファクター＆レジームスイッチング戦略**を個人投資家向けに開放。
100万円の資金規模から、プロフェッショナルな資産形成を自動化するためのアルゴリズム・ボットです。

![Main Dashboard](https://img.shields.io/badge/Status-Trading-success?style=for-the-badge&logo=bitdefender)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![API](https://img.shields.io/badge/Broker-Kabucom%20API-orange?style=for-the-badge&logo=google-cloud)
![AI](https://img.shields.io/badge/AI-Gemini%20%2F%20Groq-8E44AD?style=for-the-badge&logo=google-gemini)

---

## 🚀 Core Vision: "個人をヘッジファンドに進化させる"

多くの個人投資家が直面する「感情による判断ミス」「監視不足」「資金効率の悪さ」を、数学的アルゴリズムと最新の生成AIで解決します。

### 💎 4つの革新的コア・テクノロジー

1.  **プロフェショナル・複数期間バックテスター (`backtest.py`)** [UPGRADED]
    - 過去60日間のデータを15分足単位で取得し、5日ごとの複数フェーズに分割して一括評価。
    - **正確な集計ロジック**: ポジション単位（エントリーから全決済まで）での損益・平均利益算出。含み益も適正に反映し、実態に即した評価が可能。
    - 各期間の損益、勝率を一覧表で出力し、戦略の持続性と相場適応力を可視化。
2.  **ハイブリッド・リアルタイム監視エンジン**
    - 朝の「モーニング・スクリーニング」で全500銘柄以上から 50 銘柄を精査。
    - 日中は kabuステーション API の板情報（PUSH配信）と同期し、30秒単位でポジションを自動制御。
3.  **マルチ・レジーム適応ロジック (Strategy 4.3)** [LATEST - 💎 Swing Optimized]
    - 相場を **BULL（強気）/ RANGE（揉み合い）/ BEAR（弱気）** に自動分類し、各環境に最適化したエントリーを実行。
    - **BULL**: 強い銘柄の押し目を狙う **"SMA20 Pullback + SMA5 Momentum Check"** 戦略。
    - **Professional Exit Management**: ATRベースの多段階利確（10.0x ATR）と追従トレール（2.5x ATR）により、大きなトレンドを確実に捕捉。
    - **Breakeven Protection**: 含み益が1.2%を超えた時点でストップを建値へ自動移動。
4.  **AI 二次定性フィルタ (Gemini / Groq)**
    - 数学的スクリーニングを通過した銘柄に対し、最新ニュースを AI がリアルタイム分析。
    - 不祥事や悪材料を検知した場合、瞬時にエントリーをブロック。

---

## ✨ 主要機能 (Feature Highlights)

### 📈 資金管理とリスクコントロール (Capital Management)
- **100万円運用特化**: 少額（10〜30万円前後）で流動性の高い銘柄を優先。
- **リスクベース・サイジング**: 1トレードの許容損失を総資金の 2%（MAX_RISK_PER_TRADE）に抑えるよう株数を自動計算。
- **投資上限フィルタ [NEW]**: 単一銘柄への投資を「総資産の30%」かつ「最大2,000万円」に制限し、資産規模拡大時もリスク分散を維持。

### 🚢 流動性・執行エンジン [NEW]
- **出来高連動フィルタ**: 非現実的な大量約定を防ぐため、次足の予想出来高の 1.0% を超える発注を自動制限。
- **スリッページ・シミュレーション**: 執行時の気配乖離を ATR の 1% 単位で厳格に適用し、理論値と実運用の乖離を最小化。

---

## 🛠️ プロジェクト構造 (Architecture)

```bash
.
├── auto_trade.py         # メインエンジン（自律ループ型）
├── backtest.py           # プロフェッショナル・バックテスター [NEW]
├── core/
│   ├── logic.py          # 戦略ロジック（レジーム判定、ポジション管理）
│   ├── kabucom_broker.py # auカブコム API 通信レイヤー
│   ├── ai_filter.py      # Gemini/Groq によるニュース定性分析
│   ├── config.py         # パラメータ設定（最新・戦略4.3定数）
│   └── kabu_launcher.py  # kabuステーションの自動制御
├── data/                 # トレードログ、ポートフォリオ保存
└── dashboard.py          # リアルタイム運用状況の可視化
```

---

## 📦 クイックスタート (Quick Start)

### 1. バックテスト (検証)
戦略 4.3 の性能を検証します。
```bash
# 基本銘柄セット (Phase 1)
python backtest.py --stocks phase1

# 厳格なストレステスト (Phase 2 - 100銘柄)
python backtest.py --stocks phase2
```

### 2. 本番起動
```bash
python auto_trade.py
```

---
Created by Antigravity - *Next Generation Algorithmic Trading Solution*