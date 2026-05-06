# Auto-Trade

日本株向けの自動売買・バックテスト用リポジトリです。  
現在の主戦略は、**当日中に建玉を閉じるデイトレード戦略**です。

このリポジトリでは、**本番戦略ロジックを唯一の判断源**として扱います。  
バックテストは本番ロジックを検証するための実行レイヤーであり、独自の売買判断を持たせない前提です。運用ルールの詳細は [AGENTS.md](AGENTS.md) を参照してください。

また、探索の履歴と「もうそのまま再試行しない案」は [STRATEGY_EXPERIMENT_LOG.md](STRATEGY_EXPERIMENT_LOG.md) に残しています。

## 現在の戦略概要

- 主戦略: 日本株デイトレード
- 対象: 主に `.T` 銘柄と一部 ETF
- 執行前提: 寄り付き前後で候補を選び、当日中に全ポジションを解消
- 主な判断軸:
  - 市場 breadth
  - 指数トレンド
  - 個別銘柄のトレンド
  - 前日リターンと寄りギャップ
  - ATR、RSI2、相対強度
- 補助セットアップ:
  - `fallback`
  - `strong_oversold`
  - `catchup`
  - `inverse`
  - `inverse_pullback`
- 設計方針:
  - 週初資産比 `+1%` の達成週数を最適化目標として追う
  - 稼働率も見るが、低品質なエントリーの水増しはしない
  - リスク、流動性、スリッページ、急落時損失を無視した過大建玉は採らない

共有戦略ロジックの中心は [core/logic.py](core/logic.py) です。

## 現在の検証状況

最新確認日は **2026-05-06** です。  
`python jp_backtest.py` の最新確認値:

- `FINAL EQUITY: 48,347,449円`
- `CLOSED TRADES: 509`
- `WIN RATE: 49.51%`
- `WEEKS >= +1%: 138/215`
- `POSITIVE WEEKS: 142/215`
- `TOTAL RETURN: +4734.74%`
- `PROFIT FACTOR: 1.33`
- `AVG MONTH ACTIVE RATE: 50.48%`
- `MONTHS >= 3/4 ACTIVE: 2/50`
- `WORST DAY: -4,201,220円`

補足:

- これは将来成績を保証するものではありません
- データ更新やロジック変更で数値は変動します
- 月間 `3/4` 稼働目標は、現時点では未達です
- 週次 `+1%` は保証値ではなく、改善目標として扱っています

## リポジトリ構成

```text
auto-trade/
├── AGENTS.md
├── STRATEGY_EXPERIMENT_LOG.md
├── README.md
├── auto_trade.py
├── backtest.py
├── jp_backtest.py
├── jp_jquants_fetcher_v2.py
├── jp_jquants_margin_fetcher.py
├── jp_optimizer.py
├── run_daily_cycle.py
├── run_imperial_oracle.bat
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

## 主要スクリプト

- `auto_trade.py`  
  本番の自動売買実行エントリです。

- `backtest.py`  
  共有戦略ロジックを使って仮想約定を行うバックテスト実行レイヤーです。

- `jp_backtest.py`  
  日本株キャッシュを読み込み、現行デイトレード戦略の評価を出す確認用スクリプトです。

- `jp_optimizer.py`  
  パラメータ探索用スクリプトです。採用判断は、必ず shared logic と説明可能性を前提に行ってください。

- `jp_jquants_fetcher_v2.py`  
  株価キャッシュを更新します。

- `jp_jquants_margin_fetcher.py`  
  信用銘柄キャッシュを更新します。

- `run_daily_cycle.py` / `run_imperial_oracle.bat`  
  日次実行の補助スクリプトです。

## 月次ローテーションについて

`core/monthly_rotation_strategy.py` と関連テストは、まだリポジトリ内に残っています。  
ただし、**現在の主戦略は月次ローテーションではなくデイトレード**です。

月次ローテーション系コードは、

- 過去資産
- 参照実装
- 一部テストの依存先

として残っているもので、現行の主改善対象はデイトレード側です。

## セットアップ

Python 3.10 以上を想定しています。

```bash
pip install -r requirements.txt
```

`.env` には少なくとも次の系統の設定が必要です。

- auカブコム証券 API
- J-Quants
- AI フィルタ用 API キー
- 通知先やデバッグ設定

## データ更新

株価キャッシュ:

```bash
python jp_jquants_fetcher_v2.py
```

信用銘柄キャッシュ:

```bash
python jp_jquants_margin_fetcher.py
```

## 実行

バックテスト:

```bash
python jp_backtest.py
```

最適化:

```bash
python jp_optimizer.py
```

自動売買:

```bash
python auto_trade.py
```

## テスト

現在のテストは主に次を確認します。

- `tests/test_logic.py`
  - shared strategy の判定関数
  - setup ごとの境界条件
  - 候補選択、買付余力、サイズ計算
- `tests/test_backtest.py`
  - `backtest.py` から shared logic を参照したときの売買フロー
  - 日中決済、stop/target、inverse 系を含むバックテスト挙動
  - 月次ローテーションの既存参照実装
- `tests/test_auto_trade.py`
  - `auto_trade.py` の軽量な回帰確認
  - スナップショット計算
  - live 側での inverse / `inverse_pullback` の扱い

全件実行:

```bash
python -m pytest tests
```

ファイル単位で実行:

```bash
python -m pytest tests/test_logic.py
python -m pytest tests/test_backtest.py
python -m pytest tests/test_auto_trade.py
```

## 運用メモ

- 戦略変更は、まず [core/logic.py](core/logic.py) の shared logic を直し、その結果を本番・バックテストから参照させます
- 改善探索では、やみくもに閾値を振るのではなく、負け日・未達週の原因分析から仮説を立てます
- 効かなかった案は [STRATEGY_EXPERIMENT_LOG.md](STRATEGY_EXPERIMENT_LOG.md) に残して、別セッションで同じ試行を繰り返さないようにします
- テストを追加・変更した場合は、README のテスト欄にも対象内容と実行方法を反映します

Last updated: 2026-05-06
