# Auto-Trade

日本株向けの自動売買・バックテスト用リポジトリです。  
現在の主戦略は、`当日中にポジションを閉じるデイトレード戦略` です。

このリポジトリでは、バックテストは本番戦略を検証するためのものとして扱い、戦略判断はできるだけ本番ロジックと共有する方針を採っています。詳細な原則は [AGENTS.md](/C:/Users/yayum/git_work/auto-trade/AGENTS.md:1) を参照してください。

## 現在の戦略概要

- 主戦略: デイトレード
- 対象: 日本株全市場の `.T` 銘柄
- 判断軸: 市場 breadth、指数トレンド、個別銘柄の長期トレンド、前日上昇、寄り付きギャップ、ATR、RSI2、相対強度
- 執行思想: 当日寄り付き前後に候補を選び、当日中に全ポジションを閉じる
- 週次評価: 週初資産比 +1% の達成週数を追跡しつつ、共通戦略ロジックでは週初 +0.5% までキャッチアップ用の買付余力を強く引き上げる

共有戦略ロジックの中心は [core/logic.py](/C:/Users/yayum/git_work/auto-trade/core/logic.py:1) にあります。

## 現在のバックテスト前提

`jp_backtest.py` のデイトレード検証では、次の前提を反映しています。

- 当日の価格帯でシグナル判定
- 当日寄り付きベースでエントリー
- 当日中にクローズ
- 明示的なデイトレ信用コストは 0 前提で評価可能
- 約定スリッページは別パラメータで評価
- 流動性制約あり

一方で、次の点はまだ完全には再現していません。

- 特別気配や寄り付き不成立
- 部分約定の詳細モデル
- 証券会社独自の信用規制
- broker 固有の信用建て可否

`backtest.py` の日計り検証では、`明示的な諸経費` と `約定スリッページ` を分けて扱います。

- デイトレ信用の当日返済を前提にする場合、`explicit_trade_cost=0.0`、`profit_tax_rate=0.0` を使って明示コストをゼロ前提で検証できます
- 一方で、板や約定位置のズレは `entry_slippage` / `exit_slippage` で別途評価します

## 最新の参考バックテスト結果

`python jp_backtest.py` 実行時の直近確認結果:

`WEEKS >= +1%` は、各週の開始資産に対する +1% 達成週数です。

- DATA WINDOW: 2021-04-05 to 2026-04-03
- ACTIVE TEST: 2021-04 to 2026-04-03
- FINAL EQUITY: Y10,900,101
- TOTAL RETURN: +990.01%
- CLOSED TRADES: 670
- WIN RATE: 43.88%
- PROFIT FACTOR: 1.06
- PLUS DAY RATE: 43.88%
- AVG MONTH ACTIVE RATE: 66.93%
- MED MONTH ACTIVE RATE: 80.00%
- MONTHS >= 50% ACTIVE: 34/50
- MONTHS >= 2/3 ACTIVE: 33/50
- WEEKS >= +1%: 96/215
- POSITIVE WEEKS: 100/215
- TARGET CHECK: active-month 2/3=PASS / weekly +1%=MISS

この数値は将来の成績を保証するものではありません。  
また、データ更新やロジック変更により変動します。

## リポジトリ主要構成

```text
auto-trade/
├── AGENTS.md
├── auto_trade.py
├── backtest.py
├── jp_backtest.py
├── jp_jquants_fetcher_v2.py
├── jp_jquants_margin_fetcher.py
├── jp_optimizer.py
├── core/
│   ├── config.py
│   ├── jquants_margin_cache.py
│   ├── logic.py
│   ├── monthly_rotation_strategy.py
│   ├── kabucom_broker.py
│   └── sim_broker.py
└── tests/
    ├── test_backtest.py
    └── test_logic.py
```

## セットアップ

### 1. 依存ライブラリ

Python 3.10 以上を想定しています。

```bash
pip install -r requirements.txt
```

### 2. `.env` の設定

最低限、次の項目を設定してください。

```ini
# auカブコム証券 API
TRADE_MODE=KABUCOM_TEST
KABUCOM_API_PASSWORD=xxxxxxxx
KABUCOM_LOGIN_PASSWORD=yyyyyyyy
KABUCOM_ACCOUNT_TYPE=4

# J-Quants
JQUANTS_REFRESH_TOKEN=zzz...

# AIフィルタ
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash
GROQ_API_KEY=...
GROQ_MODEL=llama-3.3-70b-versatile

# 通知・デバッグ
DISCORD_WEBHOOK_URL=https://...
DEBUG_MODE=true
```

## データ構築

### 株価キャッシュ作成

```bash
python jp_jquants_fetcher_v2.py
```

### 信用銘柄キャッシュ作成

```bash
python jp_jquants_margin_fetcher.py
```

注意:

- `J-Quants Light` では `listed/info` の `MarginCode` が利用できないため、信用銘柄キャッシュに信用区分が入らない場合があります
- その場合、現在の実装では信用銘柄フィルタは自動的に無効化されます
- `MarginCode` を使いたい場合は `Standard` 以上のプランが必要です

## 実行方法

### バックテスト

```bash
python jp_backtest.py
```

### 最適化

```bash
python jp_optimizer.py
```

### 自動売買

```bash
python auto_trade.py
```

### 日次オーケストレーション

```bash
run_imperial_oracle.bat
```

## テスト

```bash
python -m pytest tests\test_backtest.py tests\test_logic.py
```

## 補足

- 現在の README は、古い月次ローテーション戦略の説明ではなく、現行のデイトレード戦略に合わせて更新しています
- 戦略変更時は、まず共有戦略ロジックを修正し、その後にバックテストや本番実行側を参照させる構成を維持してください

Last updated: 2026-04-27
