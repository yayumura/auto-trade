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
  - `inverse_rebreak`
- 設計方針:
  - 週初資産比 `+1%` の達成週数を最適化目標として追う
  - 稼働率も見るが、低品質なエントリーの水増しはしない
  - リスク、流動性、スリッページ、急落時損失を無視した過大建玉は採らない

共有戦略ロジックの中心は [core/logic.py](core/logic.py) です。

改善方針、探索ルール、train / holdout の厳守事項は [AGENTS.md](AGENTS.md) を参照してください。  
採用済み baseline と不採用案の履歴は [STRATEGY_EXPERIMENT_LOG.md](STRATEGY_EXPERIMENT_LOG.md) に集約しています。

## 現在の検証状況

最新確認日は **2026-05-15** です。
`python jp_backtest.py` の最新確認値:

- `FINAL EQUITY: 478,999,037円`
- `CLOSED TRADES: 503`
- `WIN RATE: 54.67%`
- `WEEKS >= +1%: 181/220`
- `POSITIVE WEEKS: 184/220`
- `TOTAL RETURN: +47799.90%`
- `PROFIT FACTOR: 3.45`
- `AVG MONTH ACTIVE RATE: 48.60%`
- `MONTHS >= 3/4 ACTIVE: 3/51`
- `WORST DAY: -9,678,458円`

直近 holdout `2026-04-16` から `2026-05-15` の確認値:

- `TOTAL RETURN: +1.32%`
- `WEEKS >= +1%: 1/4`
- `POSITIVE WEEKS: 3/4`
- `PROFIT FACTOR: 3.18`
- `WORST DAY: -1,229,147円`

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
├── jp_walkforward.py
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
    ├── test_jp_backtest.py
    ├── test_jp_jquants_fetcher_v2.py
    ├── test_jp_optimizer.py
    ├── test_jp_walkforward.py
    └── test_logic.py
```

## 主要スクリプト

- `auto_trade.py`
  本番の自動売買実行エントリです。

- `backtest.py`
  共有戦略ロジックを使って仮想約定を行うバックテスト実行レイヤーです。

- `jp_backtest.py`
  現行デイトレード戦略の確認用バックテストです。
  `python jp_backtest.py --holdout-months 1` で trailing 1 month の `train / holdout` を分けて確認できます。
  `--refresh-cache` を付けると、キャッシュ更新後の最新日を基準に holdout を切ります。

- `jp_walkforward.py`
  現行 shared strategy を1回だけ replay し、その結果を rolling な `train / holdout` 窓へ切り出して疑似 forward を確認します。
  用途は「各 window の train で自動再最適化すること」ではなく、「現行ロジックの頑健性確認」です。

- `jp_optimizer.py`
  `train` 期間だけで候補を順位付けし、上位候補だけを trailing holdout で再確認する optimizer です。
  既定では `--min-train-months 24` を要求し、短い recent slice への当て込みを避けます。

- `jp_jquants_fetcher_v2.py`
  日本株キャッシュを更新します。
  増分更新、checkpoint seed、full refresh 再開、subscription floor 自動調整に対応しています。

- `jp_jquants_margin_fetcher.py`
  信用銘柄キャッシュを更新します。

- `run_daily_cycle.py` / `run_imperial_oracle.bat`
  日次実行の補助スクリプトです。

## Train / Holdout 運用

このリポジトリの戦略改善は、原則として次の運用で進めます。

1. 最新データの直近1ヶ月を `holdout`、それ以前を `train` として切り分ける
2. 原因分析、閾値比較、候補順位付けなどの最適化は `train` だけで行う
3. `holdout` は採用候補の最終確認にだけ使い、近い案を何度も見比べて当て込みを起こさない
4. 最新データが取得できる場合は、先に `--refresh-cache` でキャッシュを更新してから `holdout` を切り直す
5. rolling な確認が必要な場合は `jp_walkforward.py` を使い、目的を「頑健性確認」に限定する

推奨コマンド:

```bash
python jp_backtest.py --refresh-cache --holdout-months 1
python jp_walkforward.py --holdout-months 1 --step-months 1 --min-train-months 24 --max-windows 6
python jp_optimizer.py --holdout-months 1 --top-k-holdout 10
```

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

最新分だけ増分更新したい場合:

```bash
python jp_jquants_fetcher_v2.py --refresh-overlap-days 7
```

checkpoint や consolidated cache の履歴が欠けている場合に、全期間を作り直すには:

```bash
python jp_jquants_fetcher_v2.py --force-full-refresh
```

`429` が多い場合は、並列度を落として再試行:

```bash
python jp_jquants_fetcher_v2.py --force-full-refresh --max-workers 2
```

失敗理由を少数銘柄で切り分けたい場合:

```bash
python jp_jquants_fetcher_v2.py --force-full-refresh --max-workers 1 --limit-tickers 3
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

最新データ更新後に直近1ヶ月 holdout を確認:

```bash
python jp_backtest.py --refresh-cache --holdout-months 1
```

rolling holdout 確認:

```bash
python jp_walkforward.py --holdout-months 1 --step-months 1 --min-train-months 24 --max-windows 6
```

最適化:

```bash
python jp_optimizer.py --holdout-months 1 --top-k-holdout 10
```

最新データ更新後に train-only 最適化:

```bash
python jp_optimizer.py --refresh-cache --holdout-months 1 --top-k-holdout 10
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
  - 火曜・水曜・木曜・金曜の `primary` 防御フィルタ
  - 火曜 mid breadth / 指数ギャップアップ時の `primary` 防御
  - 月曜・火曜・水曜・木曜 `primary` の条件別 equity 建玉上限
  - 月曜 low breadth / hot gap / near-SMA `primary` の追加 equity cap
  - 火曜 mid-high breadth / positive-gap / neutral-trend `primary` の追加 equity cap
  - 火曜 mid-high breadth / 非プラスギャップ `primary` の equity 建玉上限
  - 火曜 mid-high breadth / high-RS / trend `1-3 ATR` / flat-to-mild-gap の crowded `primary` 防御
  - 火曜 high breadth / 中位ギャップ `primary` の equity 建玉上限
  - 水曜 hot gap / below-SMA `primary` の追加 equity cap
  - 木曜 breadth `0.55-0.70` / 小幅ギャップ continuation `primary` の tighter equity cap
  - 木曜 mid breadth / 小幅ギャップ / continuation `primary` の追加 equity cap
  - 月曜 high breadth / 小幅ギャップ `primary` の equity 建玉上限
  - 高 breadth / mildly crowded market / mid-score `primary` の equity cap
  - 火曜の指数過熱局面 `primary` の equity cap
  - 低 breadth / 過熱指数 / low-score / near-SMA `primary` の equity cap
  - 低 RS `primary` の equity cap
  - `open_vs_sma_atr 4.0-5.0` の伸び切り失速帯 `primary` equity cap
  - `fallback` のギャップ上限と低 breadth フラットギャップ防御
  - `fallback` の low breadth / weak score equity cap
  - 低 breadth / 前日プラス / near-SMA `fallback` の equity cap
  - `fallback` の score 再較正と structural room 回帰
  - `fallback` の equity 建玉上限
  - 高 breadth / 前日上昇 / SMA から遠い `fallback` の equity 建玉上限
  - 火曜・水曜 `fallback` の曜日別 equity cap
  - 水曜 high breadth / gap `> 0.5%` `fallback` の追加 equity cap
  - 高 market_ratio / high crowding の `primary` を `catchup` 先頭へ差し替える selector
  - `primary` 不在の low breadth / hot market mismatch で、弱い `fallback` より restrained `catchup_rs` を優先する selector
  - 週次キー、週次レバレッジ、週次 +1% 利益ガード
  - fragile hot market での非 `inverse` selected leverage cap
  - 低 score / 過熱 market / non-negative-gap `primary` の no-trade selected leverage guard
  - 水木金の high-score / hot-market `primary` no-trade selected leverage guard
  - 水曜 high breadth / non-positive-gap / moderate-score `primary` の no-trade selected leverage guard
  - low-score / non-negative-gap hot market `primary` の selected leverage cap
  - high-score / positive-gap hot market `primary` の selected leverage cap
  - low breadth / 過熱 market / positive-gap `primary` の selected leverage cap
  - mid breadth / hot gap / strong-prev continuation `primary` の equity cap
  - `catchup_gapdown` の建玉上限
  - 月曜 deep-gap / below-SMA `catchup_gapdown` の追加 equity cap
  - 火曜 shallow-gap / neutral-trend `catchup_gapdown` の tighter equity cap
  - 火曜 shallow `catchup_gapdown` の追加 equity cap
  - 水木金 low breadth / moderate-score `catchup_gapdown` の probe leverage
  - 月曜 low breadth / hot gap / extended trend `catchup_rs` の equity cap
  - low breadth / hot prev_return `catchup_rs` の equity cap
  - 火曜 low breadth / moderate-score `catchup_rs` の probe leverage
  - 火曜 low breadth で too-hot な `catchup_rs` を moderate candidate に差し替える selector
  - low breadth bull ETF rebound の candidate 生成と selector precedence
  - extreme risk-off breadth での low-turnover `inverse` 許可と縮小 buying power
  - panic breadth / failed rebound の `inverse_rebreak`
  - 金曜 low breadth / hot gap / extended trend `catchup_rs` の equity cap
  - 金曜 `strong_oversold` / `inverse_pullback` の countertrend selector filter
  - 候補選択、買付余力、サイズ計算
- `tests/test_backtest.py`
  - `backtest.py` から shared logic を参照したときの売買フロー
  - 日中決済、stop/target、inverse 系を含むバックテスト挙動
  - 火曜 low breadth `catchup_rs` の probe 約定フロー
  - low breadth bull ETF rebound の約定フロー
  - panic breadth での low-turnover `inverse` 約定フロー
  - 非金曜での `strong_oversold` / `inverse_pullback` / `inverse_rebreak` 約定フロー
  - 月次ローテーションの既存参照実装
- `tests/test_jp_backtest.py`
  - `jp_backtest.py` の holdout 開始日の切り方
  - `train / holdout` 分割時に、部分週を週次 +1% 集計へ混ぜないこと
- `tests/test_jp_jquants_fetcher_v2.py`
  - `jp_jquants_fetcher_v2.py` の増分更新開始日の決め方
  - overlap を含む増分取得結果が checkpoint へ正しくマージされること
  - consolidated cache から checkpoint を seed して履歴を保全できること
  - legacy な checkpoint 名や master `429` 時の fallback universe 解決
  - full refresh が途中停止後も未完了銘柄だけを再開できること
  - 非200レスポンス時に失敗理由を具体的に返すこと
  - 契約開始日エラーを `RANGE_ERROR` として認識できること
- `tests/test_jp_walkforward.py`
  - `jp_walkforward.py` の rolling window 切り方
  - holdout 集計が window 単位で正しくロールアップされること
- `tests/test_jp_optimizer.py`
  - `jp_optimizer.py` の `train / holdout` 分割日付
  - optimizer 用の train slice が時系列配列だけを正しく切り出すこと
  - 短すぎる `train` を拒否すること
  - rolling train window の切り方
  - 一貫性の高い候補が fragility の高い候補より上に来る採点
- `tests/test_auto_trade.py`
  - `auto_trade.py` の軽量な回帰確認
  - スナップショット計算
  - live 側での inverse / `inverse_pullback` / `inverse_rebreak` の扱い

全件実行:

```bash
python -m pytest tests -q
```

ファイル単位で実行:

```bash
python -m pytest tests/test_logic.py
python -m pytest tests/test_backtest.py
python -m pytest tests/test_jp_backtest.py
python -m pytest tests/test_jp_jquants_fetcher_v2.py
python -m pytest tests/test_jp_optimizer.py
python -m pytest tests/test_jp_walkforward.py
python -m pytest tests/test_auto_trade.py
```

## 運用メモ

- 戦略変更は、まず [core/logic.py](core/logic.py) の shared logic を直し、その結果を本番・バックテストから参照させます
- 改善探索では、やみくもに閾値を振るのではなく、負け日・未達週の原因分析から仮説を立てます
- 効かなかった案は [STRATEGY_EXPERIMENT_LOG.md](STRATEGY_EXPERIMENT_LOG.md) に残して、別セッションで同じ試行を繰り返さないようにします
- テストを追加・変更した場合は、README のテスト欄にも対象内容と実行方法を反映します

Last updated: 2026-05-18
