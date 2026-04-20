# Auto-Trade

日本株向けの自動売買・バックテスト用リポジトリです。  
現在の主戦略は、`月次ローテーション型の順張り戦略` です。

このリポジトリでは、バックテストは本番戦略を検証するためのものとして扱い、戦略判断はできるだけ本番ロジックと共有する方針を採っています。詳細な原則は [AGENTS.md](/C:/Users/yayum/git_work/auto-trade/AGENTS.md:1) を参照してください。

## 現在の戦略概要

- 主戦略: 月次ローテーション
- 対象: 日本株プライム中心
- 判断軸: 市場 breadth、長期トレンド、相対強度、流動性、ATR、モメンタム
- 執行思想: 月末に判定し、翌営業日寄り付きベースで売買

共有戦略ロジックの中心は [core/monthly_rotation_strategy.py](/C:/Users/yayum/git_work/auto-trade/core/monthly_rotation_strategy.py:1) にあります。

## 現在のバックテスト前提

`jp_backtest.py` の月次ローテーション検証では、次の前提を反映しています。

- 月末終値でシグナル判定
- 翌営業日寄り付きで約定
- スリッページあり
- 税金あり
- 信用買方金利あり
- 流動性制約あり

一方で、次の点はまだ完全には再現していません。

- 特別気配や寄り付き不成立
- 部分約定の詳細モデル
- 証券会社独自の信用規制
- broker 固有の信用建て可否

## 最新の参考バックテスト結果

`python jp_backtest.py` 実行時の直近確認結果:

- DATA WINDOW: 2021-04-05 to 2026-04-03
- ACTIVE TEST: 2022-01 to 2026-04-03
- FINAL EQUITY: Y5,763,432
- TOTAL RETURN: +476.34%
- CLOSED TRADES: 55

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

- 現在の README は、古い逆張り戦略の説明ではなく、現行の月次ローテーション戦略に合わせて更新しています
- 戦略変更時は、まず共有戦略ロジックを修正し、その後にバックテストや本番実行側を参照させる構成を維持してください

Last updated: 2026-04-20
