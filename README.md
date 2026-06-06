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
  - 1トレード当たりの equity risk budget と equity notional cap で大負け日を抑える
  - setup ごとの脆弱性が明確なら、shared な setup 別 risk budget で損失集中を下げる
  - `primary` の hot-gap chase では、train で再現した low-score / broad warm / overheated low-breadth の損失クラスターを no-trade に寄せる
  - `primary` の Tuesday high-market mid-breadth では、stop-heavy な low-score / low-RS サブクラスターだけを quarter-size に落とす
  - `primary` の Monday high-market high-breadth / low-RS は no-trade を許容する
  - `primary` の Monday high-market high-breadth / high-RS / stretched continuation は no-trade を許容する
  - `primary` の Wednesday high-market mid-breadth / high-RS / stretched open は quarter-size に落とす
  - `primary` の very hot / low-breadth / negative-gap / strong-prior-day continuation は no-trade を許容する
  - リスク、流動性、スリッページ、急落時損失を無視した過大建玉は採らない

共有戦略ロジックの中心は [core/logic.py](core/logic.py) です。

改善方針、探索ルール、train / holdout の厳守事項は [AGENTS.md](AGENTS.md) を参照してください。  
採用済み baseline と不採用案の履歴は [STRATEGY_EXPERIMENT_LOG.md](STRATEGY_EXPERIMENT_LOG.md) に集約しています。

## 現在の検証状況

最新確認日は **2026-06-06** です。
使用データの最新日は **2026-06-05** です。
`python jp_backtest.py --holdout-months 6 --standalone-latest-months 1` の最新確認値:

- `FINAL EQUITY: 2,505,626円`
- `CLOSED TRADES: 609`
- `WIN RATE: 43.19%`
- `WEEKS >= +1%: 82/223`
- `POSITIVE WEEKS: 104/223`
- `TOTAL RETURN: +150.56%`
- `PROFIT FACTOR: 1.25`
- `AVG MONTH ACTIVE RATE: 57.83%`
- `MONTHS >= 3/4 ACTIVE: 13/52`
- `WORST DAY: -162,631円`

直近 6ヶ月 holdout `2025-12-08` から `2026-06-05` の確認値:

- `START EQUITY: 1,832,794円`
- `FINAL EQUITY: 2,505,626円`
- `CLOSED TRADES: 65`
- `WIN RATE: 43.08%`
- `TOTAL RETURN: +36.71%`
- `WEEKS >= +1%: 11/26`
- `POSITIVE WEEKS: 14/26`
- `PROFIT FACTOR: 1.50`
- `WORST DAY: -162,631円`
- `AVG MONTH ACTIVE RATE: 49.21%`
- `MONTHS >= 50% ACTIVE: 2/6`
- `MONTHS >= 2/3 ACTIVE: 2/6`
- `MONTHS >= 3/4 ACTIVE: 0/6`

直近1ヶ月 `100万円 standalone` `2026-05-07` から `2026-06-05` の確認値:

- `START EQUITY: 1,000,000円`
- `FINAL EQUITY: 1,001,032円`
- `TOTAL RETURN: +0.10%`
- `CLOSED TRADES: 2`
- `WIN RATE: 50.00%`
- `PROFIT FACTOR: 1.89`
- `WEEKS >= +1%: 0/5`
- `POSITIVE WEEKS: 1/5`
- `WORST DAY: -1,165円`
- `TRADE DAY RATE: 9.09%`
- `AVG MONTH ACTIVE RATE: 20.00%`
- `MONTHS >= 50% ACTIVE: 0/1`
- `MONTHS >= 2/3 ACTIVE: 0/1`
- `MONTHS >= 3/4 ACTIVE: 0/1`

補足:

- これは将来成績を保証するものではありません
- データ更新やロジック変更で数値は変動します
- 月間 `3/4` 稼働目標は、現時点では未達です
- 週次 `+1%` は保証値ではなく、改善目標として扱っています
- 上の holdout と standalone は、すでに改善判断で参照した汚染済み期間です
- そのため、現時点では採用の加点材料ではなく、悪化が大きい案を止める `veto` 用の監視値として扱います
- 次の `clean holdout` は、現在の使用データ最新日 `2026-06-05` の翌営業日以降、つまり `2026-06-08` 以降の未観測データです

## リポジトリ構成

```text
auto-trade/
├── AGENTS.md
├── STRATEGY_EXPERIMENT_LOG.md
├── README.md
├── analyze_backtest_trade_log.py
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
    ├── test_analyze_backtest_trade_log.py
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
  shared scan 候補と live 側の entry 判定は `data/.../daytrade_decisions.csv` に記録されます。
  保有中の板スナップショットは `data/.../intraday_snapshots.csv` に記録され、entry context、含み損益、stop までの距離、高値からの剥落、安値からの戻りも追えます。
  live 側の intraday stop / target と、`14:30` 以降の force flatten は shared helper で判定され、`data/.../daytrade_exit_log.csv` に quote ベースの exit、target までの距離、simulation では slippage 込み modeled exit、live では実約定ベースの exit が記録されます。部分約定も `filled_shares` / `remaining_shares` 付きで event として残ります。

- `backtest.py`
  共有戦略ロジックを使って仮想約定を行うバックテスト実行レイヤーです。

- `jp_backtest.py`
  現行デイトレード戦略の確認用バックテストです。
  shared strategy を同じ形で replay するのが目的で、実運用の板・注文拒否・部分約定までを再現するものではありません。
  表示される損益・勝率は税引き後ベースです。
  `kabuステーションAPI` 経由のデイトレ信用は手数料無料なので、`explicit_trade_cost` は 0 円のままです。
  `slippage` と税引き後計算は `scripts/jp_refresh_validate.py` と同じ cost model を使います。
  さらに、発注数量は日次出来高比の `liquidity_limit` で上限を掛けて、薄い銘柄での過大約定を抑えています。
  改善判断では `python jp_backtest.py --holdout-months 6` を基準に、直近 6 ヶ月の `train / holdout` を分けて確認します。
  `--standalone-latest-months 1` を付けると、最新直近1ヶ月を `100万円` 初期資金の standalone replay でも併記できます。
  `--refresh-cache` を付けると、キャッシュ更新後の最新日を基準に holdout を切ります。

- `scripts/jp_refresh_validate.py`
  最新キャッシュの更新、`jp_backtest.py` と同じ universe / cost model での再検証、直近1ヶ月 standalone の日次損益表をまとめて出す一括ツールです。
  `--validate-only` を付けると、更新は飛ばして既存キャッシュだけを検証できます。
  この更新フローの skill 本体は `.codex/skills/jp-refresh-latest/` にあります。
  このリポジトリで「日付を更新して」「最新日まで更新して」と言われたら、まずこの skill とこのツールを使います。

- `analyze_backtest_trade_log.py`
  `jp_backtest.py` と同じ shared strategy replay を 1 回だけ行い、`train` 側の miss week、worst day、`primary` stop cluster、`primary close_exit` の fade cluster を再集計する分析スクリプトです。
  miss week については、「worst trade をどれだけ浅くすれば週次 +1% が反転するか」「loss の何割を単一 trade が占めているか」も定量化できます。
  `backtest.py` の `trade_log` に含まれる `exit_reason`、stop/target 距離、equity 比 notional、日中高安から見た run-up / fade も確認できます。

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

- `analyze_intraday_logs.py`
  `data/.../daytrade_decisions.csv`、`data/.../intraday_snapshots.csv`、`data/.../daytrade_exit_log.csv` を集計し、setup ごとの run-up、fade、stop 接近、exit 時点の modeled 成績を要約する分析スクリプトです。
  先頭で source file の `missing / empty / header_only / populated` も出すので、「ログが無い」のか「中身が無い」のかを切り分けられます。

## 実行モードの違い

初見の人は、次のように覚えると分かりやすいです。

| モード | 何を見るか | 本番との近さ | 注意点 |
| --- | --- | --- | --- |
| `jp_backtest.py` | 戦略ロジックの再現性 | shared logic の再現に最も向く | 板、特別気配、注文拒否、部分約定は再現しない |
| `SIM` | ローカルの動作確認 | 速い | board チェックを飛ばし、約定が簡略化されるので本番より甘く見えやすい |
| `KABUCOM_TEST` | 実注文に近い執行確認 | 執行面では最も本番寄り | 検証 API を使うが、口座残高はローカル台帳で管理する |
| `KABUCOM_LIVE` | 実運用 | もちろん最も本番寄り | 実資金なので検証用途ではなく本番用途 |

使い分けの目安は次のとおりです。

1. まず `jp_backtest.py` で、shared strategy の良し悪しを確認する
2. 次に `KABUCOM_TEST` で、板・注文・部分約定を含む執行の差を確認する
3. 最後に `KABUCOM_LIVE` で実運用する

つまり、`jp_backtest.py` は「戦略ロジックの確認に最適」、`KABUCOM_TEST` は「執行の確認に最適」、`SIM` は「高速なローカル確認用」という役割分担です。

## Train / Holdout 運用

このリポジトリの戦略改善は、原則として次の運用で進めます。

1. 最新データの直近6ヶ月を `holdout`、それ以前を `train` として切り分ける
2. 原因分析、閾値比較、候補順位付けなどの最適化は `train` だけで行う
3. `holdout` は採用候補の最終確認にだけ使い、近い案を何度も見比べて当て込みを起こさない
4. 最新データが取得できる場合は、先に `--refresh-cache` でキャッシュを更新してから `holdout` を切り直す
5. rolling な確認が必要な場合は `jp_walkforward.py` を使い、目的を「頑健性確認」に限定する

信頼度の扱い:

- `clean holdout`: まだ改善判断に使っていない未観測期間。強い採用根拠に使う
- `contaminated holdout`: 以前の `train` と重なった期間、または何度も見ながら改善した期間。良くても採用理由にせず、悪化が大きい案を止める `veto` 用に限定する
- `reference-only`: `full history`、現行 `train`、rolling / walk-forward。絶対成績の証明ではなく、方向性確認と下振れ監視に使う

現時点の運用メモ:

- 現在の `1m holdout` `2026-05-07` から `2026-06-02` と、`6m holdout` `2025-12-03` から `2026-06-02` は `contaminated holdout` として扱う
- 次の `clean holdout` は `2026-06-03` 以降の未観測データで積み上げる
- それまでは `train` と `jp_walkforward.py` を採用判断の主軸にし、既存 holdout は `veto` 専用で使う

推奨コマンド:

```bash
python jp_backtest.py --refresh-cache --holdout-months 6
python jp_backtest.py --holdout-months 6 --standalone-latest-months 1
python jp_walkforward.py --holdout-months 6 --step-months 1 --min-train-months 24 --max-windows 6
python jp_optimizer.py --holdout-months 6 --top-k-holdout 10
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

### Codex hooks での完了通知（任意）

Codex でこのリポジトリを操作するときに、セッション終了時の通知を Discord へ飛ばす設定を入れています。
`Stop` hook は turn-scoped なので、Codex の 1 回の返答ターンが終わるたびに通知されます。完了だけでなく中断終了でも走ります。
通知は短く、`完了 / 要対応` と `あなたの対応は不要 / 必要` だけを出します。最後の assistant メッセージから、ユーザー側の対応が要るかをざっくり判定します。

- 設定ファイル: [`.codex/hooks.json`](.codex/hooks.json)
- 実行スクリプト: [`.codex/hooks/discord_notify.py`](.codex/hooks/discord_notify.py)
- 送信先: 既存の `DISCORD_WEBHOOK_URL`

初回は Codex 側で `/hooks` からこの hook を trust してください。
`.env` に `DISCORD_WEBHOOK_URL` が入っていれば、その値を再利用します。
Webhook を使わない場合は、hook の実行環境で `DISCORD_WEBHOOK_URL` を空に上書きするか、`.env` の該当行を外してください。
`.codex/hooks.json` を編集した場合は、hash が変わるので `/hooks` から `Stop` hook を再 trust してください。

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

更新前に checkpoint の欠損や短縮を監査したい場合:

```bash
python jp_jquants_fetcher_v2.py --audit-only
```

バックアップ一覧の確認:

```bash
python jp_jquants_fetcher_v2.py --list-backups
```

最新の安全スナップショットへ戻したい場合:

```bash
python jp_jquants_fetcher_v2.py --restore-backup latest
```

`jp_jquants_fetcher_v2.py` を使った refresh では、実行前に自動で audit-only 相当を走らせ、必要なら短い checkpoint を修復したうえで `data_cache/jp_broad/backups/<timestamp>/` へ安全スナップショットを残します。

信用銘柄キャッシュ:

```bash
python jp_jquants_margin_fetcher.py
```

## 実行

バックテスト:

```bash
python jp_backtest.py
```

最新データ更新後に直近6ヶ月 holdout を確認:

```bash
python jp_backtest.py --refresh-cache --holdout-months 6
```

実運用初期条件の直近1ヶ月 `100万円 standalone` も併記して確認:

```bash
python jp_backtest.py --holdout-months 6 --standalone-latest-months 1
```

更新と検証をまとめて実行:

```bash
python scripts/jp_refresh_validate.py --holdout-months 6 --standalone-latest-months 1
python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1
```

rolling holdout 確認:

```bash
python jp_walkforward.py --holdout-months 6 --step-months 1 --min-train-months 24 --max-windows 6
```

最適化:

```bash
python jp_optimizer.py --holdout-months 6 --top-k-holdout 10
```

最新データ更新後に train-only 最適化:

```bash
python jp_optimizer.py --refresh-cache --holdout-months 6 --top-k-holdout 10
```

自動売買:

```bash
python auto_trade.py
```

backtest trade log 分析:

```bash
python analyze_backtest_trade_log.py --holdout-months 6 --top-n 20
```

intraday ログ分析:

```bash
python analyze_intraday_logs.py
python analyze_intraday_logs.py --output-csv reports/intraday_trade_paths.csv --top-n 20
python analyze_intraday_logs.py --exits-file data/kabucom_test/daytrade_exit_log.csv --top-n 20
```

## テスト

現在のテストは主に次を確認します。

- `tests/test_logic.py`
  - shared strategy の判定関数
  - setup ごとの境界条件
  - live daytrade の stop / target 解決 helper と intraday exit 判定
  - `primary` の intraday failed-runup break-even exit 判定と highest_price 更新
  - live exit の未約定 / 部分約定を flat 扱いしない安全側フォールバック
  - 火曜・水曜・木曜・金曜の `primary` 防御フィルタ
  - 火曜 mid breadth / 指数ギャップアップ時の `primary` 防御
  - 月曜・火曜・水曜・木曜 `primary` の条件別 equity 建玉上限
  - 月曜 low breadth / hot gap / near-SMA `primary` の追加 equity cap
  - 月曜 breadth `0.50-0.65` / `market_ratio 1.00-1.05` / strong-prev / trend `>= 1 ATR` `primary` の追加 equity cap
  - 月曜の extreme gap / modest-trend `primary` の追加 equity cap
  - breadth `0.45-0.65` / `market_ratio 1.05-1.10` / score `<= 6` / gap `<= 1%` `primary` の追加 equity cap
  - breadth `0.63-0.75` / `market_ratio 1.05-1.11` / score `4.0-7.3` / `open_vs_sma_atr >= 0.2` `primary` の half-size equity cap
  - breadth `< 0.60` / `market_ratio 1.00-1.05` / gap `>= 2.0%` / RS `<= 50` `primary` の no-trade guard
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
  - mild-broad と high-breadth / tepid-market early-week `strong_oversold` の no-trade selected leverage guard
  - `open_vs_sma_atr >= 6.0` または `market_ratio >= 1.20` `strong_oversold` の probe selected leverage cap
  - Monday / Friday の weak-market `primary` で、`gap` と `open_vs_sma_atr` が弱い帯を絞る equity cap
  - `open_vs_sma_atr >= 8.0` / `market_ratio >= 1.20` の極端な `strong_oversold` をさらに薄くする selected leverage cap
  - `fallback` のギャップ上限と低 breadth フラットギャップ防御
  - `fallback` の low breadth / weak score equity cap
  - 低 breadth / 前日プラス / near-SMA `fallback` の equity cap
  - `fallback` の score 再較正と mid-score size-up / small-account board-lot floor 回帰
  - `fallback` の equity 建玉上限
  - 高 breadth / 前日上昇 / SMA から遠い `fallback` の equity 建玉上限
  - 火曜 mid-breadth continuation / 水曜 high breadth `fallback` の曜日別 equity cap
  - 水曜 high breadth / gap `> 0.5%` `fallback` の追加 equity cap
  - `inverse_pullback` の high-confidence probe leverage / executable-share 回帰
  - `catchup_rs` の setup 別 risk budget
  - `100万円` 近辺の small-account で、`catchup` の board-lot 最低実行単位と cheap `primary` substitute skip が shared sizing に反映されること
  - `100万円` 近辺の small-account で、hot / mid-score `catchup_rs` の board-lot を無理に建てないこと
  - `100万円` 近辺の small-account で、fallback が board-lot を建てられないときだけ executable な `catchup_rs` / `catchup_gapdown` に限定差し替えすること
  - `catchup_rs` / `catchup_gapdown` の差し替えが、score 優位が足りない場合は fallback を維持すること
  - `catchup_rs` の Monday weak-market / moderate-gap pocket を selector から除外すること
  - `catchup_gapdown` の Wednesday negative-trend pocket を selector から除外すること
  - `primary` の hot-market no-trade pocket を board-lot 回復で壊さないこと
  - Tuesday breadth `0.65-0.75` / `market_ratio 1.15-1.30` / score `<= 8.5` / RS `<= 50` / `open_vs_sma_atr <= 4.0` `primary` の quarter-size equity cap
  - `100万円` 近辺の small-account で、木曜 low breadth の `primary` probe 候補を 0.30 notional / 1.0 leverage floor で優先できること
  - `100万円` 近辺の small-account で、月曜 low breadth / high market_ratio `catchup_rs` probe 候補を 0.35 notional / 4.9 equity / 0.155 risk floor で拡大できること
  - weekly profit lock / Thursday selected leverage の rescue で、train-supported narrow fallback band を board-lot rescue できること
  - `inverse_pullback` の high-confidence probe leverage / executable-share 回帰
  - 高 market_ratio / high crowding の `primary` を `catchup` 先頭へ差し替える selector
  - breadth `>= 0.75` / `market_ratio 1.05-1.15` で、`catchup` score が `primary` score を `12.0` 以上上回るときの broad warm tape selector replacement
  - breadth `< 0.60` / `market_ratio 1.00-1.05` / gap `1.5-2.0%` / `open_vs_sma_atr 1.0-2.0` の tepid hot-gap `primary` selector filter
  - `primary` 不在の low breadth / hot market mismatch で、弱い `fallback` より restrained `catchup_rs` を優先する selector
  - 週次キー、週次レバレッジ、週次 +1% 利益ガード
  - fragile hot market での setup 別 selected leverage cap (`primary` / `catchup_rs` / `catchup_gapdown` / `fallback`)
  - breadth `>= 0.60` / `market_ratio >= 1.05` / score `10-12` / gap `1-2%` `primary` の no-trade selected leverage guard
  - breadth `>= 0.75` / `market_ratio >= 1.25` / score `< 12` / non-negative-gap `primary` の no-trade selected leverage guard
  - breadth `>= 0.75` / `market_ratio 1.15-1.20` / score `< 10` / non-negative-gap `primary` の no-trade selected leverage guard
  - `market_ratio 1.05-1.10` / gap `-1%〜0%` / prev_return `2-4%` `primary` の no-trade selected leverage guard
  - 月曜 `market_ratio 1.00-1.05` / gap `0-1%` / prev_return `2-4%` `primary` の probe selected leverage cap
  - 月曜 breadth `< 0.50` / `market_ratio 1.00-1.05` / gap `>= 1%` `primary` の probe selected leverage cap
  - breadth `< 0.57` / `market_ratio >= 1.10` / score `10-12` / non-negative-gap `primary` の no-trade selected leverage guard
  - breadth `0.55-0.65` / score `10-12` / RS `25-50` `primary` の selected leverage cap
  - breadth `0.55-0.65` / `market_ratio 1.00-1.10` / `open_vs_sma_atr 2.0-6.0` `strong_oversold` の no-trade selected leverage guard
  - `market_ratio 1.05-1.10` / 前日上昇 `4-6%` / score `<= 6` `primary` の no-trade selected leverage guard
  - breadth `< 0.65` / `market_ratio 1.05-1.10` / 前日上昇 `2-4%` / score `<= 6` / gap `<= 1%` `primary` の no-trade selected leverage guard
  - 火曜 `open_vs_sma_atr 2.0-3.0` `fallback` の no-trade selected leverage guard
  - 木曜 breadth `< 0.55` / `open_vs_sma_atr 1.0-2.0` `fallback` の no-trade selected leverage guard
  - 低 score / 過熱 market / non-negative-gap `primary` の no-trade selected leverage guard
  - 水木金の high-score / hot-market `primary` no-trade selected leverage guard
  - 水曜 high breadth / non-positive-gap / moderate-score `primary` の no-trade selected leverage guard
  - low-score / non-negative-gap hot market `primary` の selected leverage cap
  - mid breadth / hot market / low-score / muted prev-return `primary` の equity cap
  - 月火水の high-RS / overheated low-breadth `primary` の no-trade selected leverage guard
  - high-score / positive-gap hot market `primary` の selected leverage cap
  - low breadth / 過熱 market / positive-gap `primary` の selected leverage cap
  - mid breadth / hot gap / strong-prev continuation `primary` の equity cap
  - tepid market / hot-gap / strong-prev continuation `primary` の equity cap
  - `catchup_gapdown` の建玉上限
  - 月曜 deep-gap / below-SMA `catchup_gapdown` の追加 equity cap
  - 火曜 shallow-gap / neutral-trend `catchup_gapdown` の tighter equity cap
  - 火曜 shallow `catchup_gapdown` の追加 equity cap
  - positive-prev-return / market_ratio `>= 1.00` `catchup_gapdown` の no-trade selected leverage guard
  - 水木金 low breadth / moderate-score `catchup_gapdown` の probe leverage
  - 月曜 low breadth / hot gap / extended trend `catchup_rs` の equity cap
  - low breadth / hot prev_return `catchup_rs` の equity cap
  - low breadth / hot market / score `12-16` `catchup_rs` の selected leverage cap
  - 火曜 low breadth / moderate-score `catchup_rs` の probe leverage
  - 火曜 low breadth で too-hot な `catchup_rs` を moderate candidate に差し替える selector
  - 水曜 low breadth の `catchup_rs` を selector から除外
  - low breadth bull ETF rebound の candidate 生成と selector precedence
  - extreme risk-off breadth での low-turnover `inverse` 許可と縮小 buying power
  - panic breadth / failed rebound の `inverse_rebreak`
  - 金曜 low breadth / hot gap / extended trend `catchup_rs` の equity cap
  - 金曜 `strong_oversold` / `inverse_pullback` の countertrend selector filter
  - 候補選択、買付余力、サイズ計算、risk budget cap
- `tests/test_backtest.py`
  - `backtest.py` から shared logic を参照したときの売買フロー
  - 日中決済、stop/target、inverse 系を含むバックテスト挙動
  - `primary` の intraday failed-runup exit を trade_log の `exit_reason` として記録すること
  - `trade_log` の `exit_reason`、stop/target、OHLC fade 監査列
  - 火曜 low breadth `catchup_rs` の probe 約定フロー
  - small-account で `raw_shares < 100` の fallback board-lot 候補が shared resolve へ到達すること
  - low breadth bull ETF rebound の約定フロー
  - panic breadth での low-turnover `inverse` 約定フロー
  - `inverse_pullback` high-confidence probe の約定フローと size-up 回帰
  - 非金曜での `strong_oversold` / `inverse_pullback` / `inverse_rebreak` 約定フロー
  - 月次ローテーションの既存参照実装
- `tests/test_analyze_backtest_trade_log.py`
  - `analyze_backtest_trade_log.py` の exit bucket 分類
  - `train` 週次集計で部分週を除外すること
  - `train` miss-week 集計で warmup 前の部分週を除外すること
  - miss-week の flip sensitivity と loss dominance 集計
  - `primary close_exit` fade テーブルと cluster 集計
- `tests/test_jp_backtest.py`
  - `jp_backtest.py` の holdout 開始日の切り方
  - `train / holdout` 分割時に、部分週を週次 +1% 集計へ混ぜないこと
  - latest standalone window 切り出しで、直前営業日の context だけ残しつつ評価期間を固定すること
  - `jp_backtest.py` と `jp_refresh_validate.py` の universe / cost model が揃っていること
  - `PROFIT FACTOR` の非有限値を `N/A` 表示に正規化すること
- `tests/test_jp_jquants_fetcher_v2.py`
  - `jp_jquants_fetcher_v2.py` の増分更新開始日の決め方
  - overlap を含む増分取得結果が checkpoint へ正しくマージされること
  - consolidated cache から checkpoint を seed して履歴を保全できること
  - checkpoint 上書き時に history を短くしないことと、短い checkpoint を cache から修復できること
  - refresh 前の cache audit を自動で走らせること、バックアップ一覧、最新スナップショット復元
  - legacy な checkpoint 名や master `429` 時の fallback universe 解決
  - full refresh が途中停止後も未完了銘柄だけを再開できること
  - 非200レスポンス時に失敗理由を具体的に返すこと
  - 契約開始日エラーを `RANGE_ERROR` として認識できること
- `tests/test_jp_walkforward.py`
  - `jp_walkforward.py` の rolling window 切り方
  - holdout 集計が window 単位で正しくロールアップされること
  - holdout PF 集計が非有限値に汚染されないこと
- `tests/test_jp_optimizer.py`
  - `jp_optimizer.py` の `train / holdout` 分割日付
  - optimizer 用の train slice が時系列配列だけを正しく切り出すこと
  - 短すぎる `train` を拒否すること
  - rolling train window の切り方
  - 一貫性の高い候補が fragility の高い候補より上に来る採点
- `tests/test_auto_trade.py`
  - `auto_trade.py` の軽量な回帰確認
  - スナップショット計算
  - scan 候補と live entry 判断ログの行生成
  - server time ベースの月次 state / 月初資産ロールオーバー
  - 保有中ポジションの intraday snapshot 行生成と entry context 付与
  - daytrade exit decision 行の modeled exit / fade 指標と、live 約定時の二重スリッページ防止
  - live での intraday failed-runup break-even exit と highest_price 追跡
  - shared intraday stop / target と `14:30` force flatten の live exit フロー
  - live 部分約定時に shares を減らして保有継続し、partial fill event を exit log へ残すこと
  - live 側での inverse / `inverse_pullback` / `inverse_rebreak` の扱い
- `tests/test_analyze_intraday_logs.py`
  - `analyze_intraday_logs.py` の decision 集計
  - intraday trade path 集計
  - exit log を使った final outcome 上書き
  - source file status と analysis readiness の可視化
  - setup 別サマリー出力

全件実行:

```bash
python -m pytest tests -q
```

ファイル単位で実行:

```bash
python -m pytest tests/test_logic.py
python -m pytest tests/test_backtest.py
python -m pytest tests/test_analyze_backtest_trade_log.py
python -m pytest tests/test_jp_backtest.py
python -m pytest tests/test_jp_jquants_fetcher_v2.py
python -m pytest tests/test_jp_optimizer.py
python -m pytest tests/test_jp_walkforward.py
python -m pytest tests/test_auto_trade.py
python -m pytest tests/test_analyze_intraday_logs.py
```

## 運用メモ

- 戦略変更は、まず [core/logic.py](core/logic.py) の shared logic を直し、その結果を本番・バックテストから参照させます
- 改善探索では、やみくもに閾値を振るのではなく、負け日・未達週の原因分析から仮説を立てます
- 効かなかった案は [STRATEGY_EXPERIMENT_LOG.md](STRATEGY_EXPERIMENT_LOG.md) に残して、別セッションで同じ試行を繰り返さないようにします
- テストを追加・変更した場合は、README のテスト欄にも対象内容と実行方法を反映します

Last updated: 2026-06-06
