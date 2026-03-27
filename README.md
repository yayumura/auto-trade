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

1.  **プロフェッショナル・バックテスター (`backtest.py`)** [NEW]
    - 過去データを yfinance から15分足単位で取得し、実際の「時間軸」に沿ってトレードを擬似実行。
    - ルックアヘッド・バイアス（未来情報の混入）を完全に排除した、信頼性の高い戦略検証。
2.  **ハイブリッド・リアルタイム監視エンジン**
    - 朝の「モーニング・スクリーニング」で全500銘柄以上から 50 銘柄を精査。
    - 日中は kabuステーション API の板情報（PUSH配信）と同期し、30秒単位でポジションを自動制御。
3.  **マルチ・レジーム適応ロジック**
    - 日経平均（1321）のモメンタムを監視し、相場を **BULL（強気）/ RANGE（揉み合い）/ BEAR（弱気）** に自動分類。
    - 相場状況に応じて、利益確定の目標値や損切りの深さを動的に変更。
4.  **AI 二次定性フィルタ (Gemini / Groq)**
    - 数学的スクリーニングを通過した銘柄に対し、最新ニュースを AI がリアルタイム分析。
    - 不祥事や悪材料を検知した場合、瞬時にエントリーをブロック。

---

## ✨ 主要機能 (Feature Highlights)

### 📈 1M JPY 資金管理最適化 (Capital Efficiency)
- **100万円運用特化**: 1単元が高価な銘柄を自動で避け、10万円〜30万円前後で流動性の高い銘柄を優先選択。
- **リスクベース・サイジング**: 1トレードの許容損失を総資金の 2%（MAX_RISK_PER_TRADE）に抑えるよう株数を自動計算。

### 🤖 kabuステーション・オートパイロット
- **自動起動・WebViewログイン監視**: `core/kabu_launcher.py` がアプリの起動から API サーバー（18080/18081）の待機までを完全制御。
- **インテリジェント・チェイス発注**: 成行ではなく、板の最良気配（Tick）を追いかけながら確実に約定させる OMS（Order Management System）を搭載。

### 🛡️ 究極の安全防御システム (Safety Guard)
- **IP Ban & Rate Limit 防止**: yfinance データ取得時にランダムな揺らぎ（Jitter）と待機（Sleep）を挿入。
- **インサイダー保護**: `insider_exclusion.json` に設定した銘柄を全自動で除外。
- **ゾンビ注文ガード**: 5分以上約定しない「未約定注文」を検知し、自動キャンセル（オートキャンセル）。
- **デリスト銘柄ブラックリスト**: 無効な ticker や上場廃止銘柄を自動で学習・キャッシュ。

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
│   ├── config.py         # パラメータ設定（リスク許容度、資金等）
│   └── kabu_launcher.py  # kabuステーションの自動制御
├── data/                 # トレードログ、ポートフォリオ保存
└── dashboard.py          # リアルタイム運用状況の可視化
```

---

## 📦 設定・クイックスタート

### 1. 環境構築
```bash
pip install -r requirements.txt
cp .env.example .env
# 各種 API キー、Discord Webhook URL を設定
```

### 2. バックテストで戦略を検証
まずは自身の戦略が機能するか、過去データで確認します。
```bash
python backtest.py
```
※ `initial_cash=1000000` でシミュレーションされます。

### 3. 本番/シミュレーション起動
`.env` の `TRADE_MODE` を設定して起動します。

| モード | 内容 |
| :--- | :--- |
| `SIMULATION` | ローカル仮想資金（100万円）で動作。まずはここから開始。 |
| `KABUCOM_TEST` | カブコム検証用 API (Port 18081) を使用。 |
| `KABUCOM_LIVE` | カブコム本番 API (Port 18080) を使用。 |

```bash
python auto_trade.py
```

---

## 📊 運用監視 (Monitoring)

- **Discord 通知**: エントリー、利確、損切り、システムエラーを即座にスマートフォンへ通知。
- **ダッシュボード**: `python dashboard.py` で資産推移と現在の保有ポジションをグラフィカルに確認可能。

---

## ⚖️ リスク免責事項 (Disclaimer)

- 本ツールは教育・研究を目的として提供されており、投資成果を保証するものではありません。
- 実際の取引には証券口座の開設と API の利用設定が必要です。
- 運用中の損失について、開発者は一切の責任を負いません。余裕資金での運用を強く推奨します。

---
Created by Antigravity - *Next Generation Algorithmic Trading Solution*