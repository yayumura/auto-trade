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
  - `primary` の intraday failed-runup exit は、セッション中の高値が買値から `+2%` 以上伸びたあとに失速したら break-even で退避する
  - `catchup_rs` の Monday / Friday 高 breadth hot-market は selector から除外する
  - `fallback` の high breadth / hot-market pocket は selector から除外する
  - `catchup_rs` の Friday low breadth / modest market pocket（`market_ratio 1.00-1.10` / `breadth < 0.55`）は selector から除外する
  - `catchup_gapdown` の Friday deep-gap / high-score pocket（`score > 6` / `gap <= -1%`）の equity notional は `0.25` に抑える
  - `fallback` の Tuesday / Friday 弱市場（`market_ratio 1.00-1.10` / `breadth < 0.55` / positive gap）は equity notional を `0.50` に抑える
  - `primary` の Tuesday high-market mid-breadth では、stop-heavy な low-score / low-RS サブクラスターだけを quarter-size に落とす
  - `primary` の Tuesday mid-breadth / low-score / hot-market continuation は、small-gap pocket を 0.10 に寄せつつ、low market-ratio / positive-gap pocket は no-trade にする
  - `primary` の Tuesday high breadth / high-score / stretched open は half-size に落とす
  - `primary` の Tuesday / Thursday mid-breadth / hot-market / score `8-10` は selected base leverage を `0.10` に制限する
  - `strong_oversold` の Tuesday 伸び切り open は selector から除外する
  - `primary` の Monday high-market high-breadth / low-RS は no-trade を許容する
  - `primary` の Monday high-market high-breadth / high-RS / stretched continuation は no-trade を許容する
  - `primary` の Monday / Thursday broad hot-market は no-trade を許容する
  - `primary` の Monday high-breadth / soft-gap continuation は no-trade を許容する
  - `primary` の Wednesday high-market mid-breadth / high-RS / stretched open は quarter-size に落とす
  - `primary` の Wednesday mid-breadth / hot-market / score `9-12` / breadth `0.60-0.80` / market_ratio `1.07-1.21` は selected base leverage を `0.10` に制限する
  - `primary` の high market-ratio / mid-breadth / mid-score / moderate-prev-return / positive-gap は quarter-size に落とす
  - `primary` の Wednesday low-breadth / high-gap / high-score / strong-open は quarter-size に落とす
  - `primary` の Thursday high-score / moderate-prev-return / hot-market / stretched open は quarter-size に落とす
  - `primary` の very hot / low-breadth / negative-gap / strong-prior-day continuation は no-trade を許容する
  - リスク、流動性、スリッページ、急落時損失を無視した過大建玉は採らない

共有戦略ロジックの中心は [core/logic.py](core/logic.py) です。

改善方針、探索ルール、train / holdout の厳守事項は [AGENTS.md](AGENTS.md) を参照してください。  
採用済み baseline と不採用案の履歴は [STRATEGY_EXPERIMENT_LOG.md](STRATEGY_EXPERIMENT_LOG.md) に集約しています。

## 現在の検証状況

最新確認日は **2026-06-22** です。
使用データの最新日は **2026-06-19** です。
`python jp_backtest.py --holdout-months 6 --standalone-latest-months 1` の最新確認値:

- `FINAL EQUITY: 3,730,972円`
- `CLOSED TRADES: 533`
- `WIN RATE: 45.03%`
- `WEEKS >= +1%: 80/225`
- `POSITIVE WEEKS: 109/225`
- `TOTAL RETURN: +273.10%`
- `PROFIT FACTOR: 1.67`
- `AVG MONTH ACTIVE RATE: 50.44%`
- `MONTHS >= 50% ACTIVE: 28/52`
- `MONTHS >= 2/3 ACTIVE: 11/52`
- `MONTHS >= 3/4 ACTIVE: 7/52`
- `WORST DAY: -226,270円`

直近 6ヶ月 holdout `2025-12-22` から `2026-06-19` の確認値:

- `START EQUITY: 2,131,217円`
- `FINAL EQUITY: 3,730,972円`
- `CLOSED TRADES: 51`
- `WIN RATE: 50.98%`
- `TOTAL RETURN: +75.06%`
- `WEEKS >= +1%: 14/26`
- `POSITIVE WEEKS: 17/26`
- `PROFIT FACTOR: 2.61`
- `WORST DAY: -226,270円`
- `AVG MONTH ACTIVE RATE: 40.69%`
- `MONTHS >= 50% ACTIVE: 2/6`
- `MONTHS >= 2/3 ACTIVE: 0/6`
- `MONTHS >= 3/4 ACTIVE: 0/6`

直近1ヶ月 `100万円 standalone` `2026-05-20` から `2026-06-19` の確認値:

- `START EQUITY: 1,000,000円`
- `FINAL EQUITY: 1,142,235円`
- `TOTAL RETURN: +14.22%`
- `CLOSED TRADES: 4`
- `PROFIT FACTOR: inf`
- `WEEKS >= +1%: 3/4`
- `POSITIVE WEEKS: 3/4`
- `WORST DAY: 0円`
- `TRADE DAY RATE: 17.39%`
- `AVG MONTH ACTIVE RATE: 13.33%`
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
- 次の `clean holdout` は、現在の使用データ最新日 `2026-06-19` の翌営業日以降、つまり `2026-06-20` 以降の未観測データです
- `KABUCOM_LIVE` の新規エントリーは、`ENABLE_LIVE_ORDER=true` と `APPROVED_CONFIG_HASH` が `core.config.RUNTIME_LIVE_ORDER_CONFIG_HASH` と一致した場合にのみ許可されます
- `RUNTIME_LIVE_ORDER_CONFIG_HASH` は、実行設定に加えて `core.logic` の daytrade 定数、monthly rotation モジュール fingerprint、主要コードファイルの fingerprint も含めた承認マニフェストから計算します
- LIVE の financial write は、actual `KABUCOM_TEST` fixture provenance、CI artifact 由来の attestation bundle (`contracts/kabucom_live_write_attestation.json` + `.sha256`)、operator ACK、JPX calendar source をまとめて fail closed で判定します。`KABUCOM_LIVE` では operator ACK は `KABUCOM_LIVE_OPERATOR_ACK_CONTEXT` の structured context を必須にし、legacy boolean や explicit 引数だけでは開きません。さらに、`LiveReadinessReport` が protective stop lifecycle / partial fill / execution-ID truth / quote freshness / journal reconciliation / request budget / risk readiness / no-lookahead audit をまとめて fail closed で示し、`execution_ids` の集約ロットや重複 execution_id は truth lot ではなく blocked 扱いにします。`LIVE_RISK_REVIEW_PATH` か `contracts/live_risk_review.json` が無い場合は not_verified のまま閉じます。`no_lookahead_audit` は risk review 自体が ready の場合にだけ ready とみなします。`GITHUB_TOKEN` / `GH_TOKEN` がある場合は GitHub Actions の workflow run と artifact を API で照合し、artifact の digest と zip 内容まで確認します。verification 結果はプロセス内で `GITHUB_ARTIFACT_SOURCE_CACHE_TTL_SEC` 秒だけ再利用し、キャッシュキーには repository / workflow run / head_sha / artifact 名 / local attestation hash / local digest / token fingerprint / session fingerprint を含めます。期限切れ後や token ローテーション後、local attestation 更新後は再検証され、必要なら `clear_live_write_attestation_artifact_source_cache()` で手動クリアできます
- `KABUCOM_LIVE` では、calendar source が未配置・無効・coverage gap/fallback の場合も金融 write を開けません。`half_day_dates` に入った日は午前立会のみとして扱い、11:30 以降はその日の運用を終了します

structured operator ACK の例:

```json
{
  "operator_id": "qa-operator",
  "acknowledged_at": "2026-06-18T09:00:00+09:00",
  "expires_at": "2026-06-18T18:00:00+09:00",
  "code_commit_sha": "ba57385e9490fab1cc6e423b7546f8d5a32a7ecf",
  "approved_config_hash": "sha256:...",
  "runtime_config_hash": "sha256:...",
  "repository_full_name": "yayumura/auto-trade",
  "test_fixture_hash": "sha256:...",
  "live_write_attestation_hash": "sha256:...",
  "reason": "manual approval for live write"
}
```

`KABUCOM_LIVE_OPERATOR_ACK=true` の legacy boolean は local test / shadow 用のみに留め、`KABUCOM_LIVE` の live gate では structured context を使ってください。
- `LiveReadinessReport` は startup log と entry authorization で参照され、risk review artifact が欠けている間は live entry を止めます。
- 不一致または未設定の場合でも、監視・保護逆指値・決済は継続します

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
│   ├── jpx_calendar.py
│   ├── logic.py
│   ├── monthly_rotation_strategy.py
│   ├── kabucom_broker.py
│   └── sim_broker.py
└── tests/
    ├── test_analyze_backtest_trade_log.py
    ├── test_backtest.py
    ├── test_kabucom_broker.py
    ├── test_jp_backtest.py
    ├── test_jp_jquants_fetcher_v2.py
    ├── test_jp_optimizer.py
    ├── test_jp_walkforward.py
    ├── test_kabucom_contracts_test_fixture.py
    └── test_logic.py
```

## 主要スクリプト

- `auto_trade.py`
  本番の自動売買実行エントリです。
  `KABUCOM_LIVE` では新規エントリーはデフォルト無効で、`ENABLE_LIVE_ORDER=true` と `APPROVED_CONFIG_HASH` の一致がそろうまで監視と決済のみを行います。
  LIVE の financial write は actual `KABUCOM_TEST` fixture の provenance、CI artifact 由来の structured attestation bundle (`contracts/kabucom_live_write_attestation.json` + `.sha256`)、structured operator ACK、JPX calendar source、GitHub artifact verification がそろったときだけ開きます。`KABUCOM_LIVE` では `KABUCOM_LIVE_OPERATOR_ACK_CONTEXT` が必須で、`KABUCOM_LIVE_OPERATOR_ACK=true` の legacy boolean や explicit 引数だけでは開きません。`GITHUB_TOKEN` / `GH_TOKEN` がある live 実行では GitHub Actions の run と artifact を API で照合し、artifact digest と zip 内容まで確認します。verification 結果はプロセス内で `GITHUB_ARTIFACT_SOURCE_CACHE_TTL_SEC` 秒だけ再利用し、期限切れ後は再検証します。`TRADE_MODE=KABUCOM_LIVE` では JPX calendar source が無い場合だけでなく、coverage gap や fallback に落ちる場合も live financial write を開けません。`half_day_dates` は午前立会として扱い、11:30 以降はその日の運用を終了します。要点と未完了項目は下の KABUCOM_LIVE 再開 runbook と [docs/kabucom_live_deferred_external_tasks.md](docs/kabucom_live_deferred_external_tasks.md) に分けています。
  shared scan 候補と live 側の entry 判定は `data/.../daytrade_decisions.csv` に記録されます。
  保有中の板スナップショットは `data/.../intraday_snapshots.csv` に記録され、entry context、含み損益、stop までの距離、高値からの剥落、安値からの戻りも追えます。
  live 側の intraday stop / target / primary failed-runup exit と、`14:30` 以降の force flatten は shared helper で判定され、`data/.../daytrade_exit_log.csv` に quote ベースの exit、target までの距離、simulation では slippage 込み modeled exit、live では実約定ベースの exit が記録されます。live entry 後は保護逆指値を張り、`protective_stop_order_id` を portfolio に残して通常の stuck-order 自動取消から除外します。部分約定も `filled_shares` / `remaining_shares` 付きで event として残ります。

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
  `primary` の failed-runup fade cluster も独立に追跡できます。
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

- 現在の `1m holdout` `2026-05-20` から `2026-06-19` と、`6m holdout` `2025-12-22` から `2026-06-19` は `contaminated holdout` として扱う
- 次の `clean holdout` は `2026-06-20` 以降の未観測データで積み上げる
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
- `KABUCOM_API_PASSWORD` と、LIVE では明示必須の注文用 `KABUCOM_ORDER_PASSWORD`（TEST では API password からの互換 fallback 可）
- J-Quants
- AI フィルタ用 API キー
- 通知先やデバッグ設定

`jp_jquants_fetcher_v2.py` と `jp_jquants_margin_fetcher.py` を実行する場合は、J-Quants 用の `jquantsapi` 依存も必要です。  
ただし、pytest の収集や通常のバックテストだけなら、この依存が未導入でも落ちないようにしています。

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

`KABUCOM_LIVE` で新規エントリーを許可する場合は、事前に `ENABLE_LIVE_ORDER=true` と `APPROVED_CONFIG_HASH` を設定し、起動ログに出る `runtime_hash` と一致させてください。actual `KABUCOM_TEST` capture から attestation を作る段階では `APPROVED_CONFIG_HASH` が空だと build が止まります。
必要なら `core.live_approval_manifest.write_live_approval_manifest()` で承認マニフェストをファイルへ書き出してから、その hash を使ってください。
  さらに `contracts/live_risk_review.json` か `LIVE_RISK_REVIEW_PATH` で指す risk review artifact が必要で、`LiveReadinessReport` が ready にならない限り新規 entry は保留されます。

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
  - `RealtimeBuffer` の前日終値と当日 session 値の分離
  - live exit の未約定 / 部分約定を flat 扱いしない安全側フォールバック
  - 火曜・水曜・木曜・金曜の `primary` 防御フィルタ
  - 火曜 mid breadth / 指数ギャップアップ時の `primary` 防御
  - 月曜・火曜・水曜・木曜 `primary` の条件別 equity 建玉上限
  - 月曜 low breadth / hot gap / near-SMA `primary` の追加 equity cap
  - 月曜 breadth `0.50-0.65` / `market_ratio 1.00-1.05` / strong-prev / trend `>= 1 ATR` `primary` の追加 equity cap
  - 月曜の extreme gap / modest-trend `primary` の追加 equity cap
  - breadth `0.45-0.65` / `market_ratio 1.05-1.10` / score `<= 6` / gap `<= 1%` `primary` の追加 equity cap
  - breadth `0.63-0.75` / `market_ratio 1.05-1.11` / score `4.0-7.3` / `open_vs_sma_atr >= 0.2` `primary` の half-size equity cap
  - Wednesday low-breadth / high-gap / high-score / strong-open `primary` の追加 equity cap
  - breadth `< 0.60` / `market_ratio 1.00-1.05` / gap `>= 2.0%` / RS `<= 50` `primary` の no-trade guard
  - 火曜 mid-high breadth / positive-gap / neutral-trend `primary` の追加 equity cap
  - 火曜 mid-high breadth / 非プラスギャップ `primary` の equity 建玉上限
  - 火曜 mid-high breadth / high-RS / trend `1-3 ATR` / flat-to-mild-gap の crowded `primary` 防御
  - 火曜 high breadth / 中位ギャップ `primary` の equity 建玉上限
  - 水曜 hot gap / below-SMA `primary` の追加 equity cap
  - 木曜 breadth `0.55-0.70` / 小幅ギャップ continuation `primary` の tighter equity cap
  - 木曜 mid breadth / 小幅ギャップ / continuation `primary` の追加 equity cap
  - high market-ratio / mid-breadth / mid-score / moderate-prev-return / positive-gap `primary` の quarter-size cap
  - 木曜 high-score / moderate-prev-return / hot-market / stretched open の quarter-size cap
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
  - `catchup_rs` の Monday / Friday 高 breadth hot-market selector フィルタ
  - `fallback` の hot-market / high-breadth selector フィルタ
  - 火曜 mid-breadth continuation / 水曜 high breadth `fallback` の曜日別 equity cap
  - 水曜 high breadth / gap `> 0.5%` `fallback` の追加 equity cap
  - `inverse_pullback` の high-confidence probe leverage / executable-share 回帰
  - `catchup_rs` の setup 別 risk budget
  - `100万円` 近辺の small-account で、`catchup` の board-lot 最低実行単位と cheap `primary` substitute skip が shared sizing に反映されること
  - `100万円` 近辺の small-account で、hot / mid-score `catchup_rs` の board-lot を無理に建てないこと
  - `100万円` 近辺の small-account で、fallback が board-lot を建てられないときだけ executable な `catchup_rs` / `catchup_gapdown` に限定差し替えすること
  - `catchup_rs` / `catchup_gapdown` の差し替えが、score 優位が足りない場合は fallback を維持すること
  - `catchup_rs` の Monday weak-market / moderate-gap pocket を selector から除外すること
  - `catchup_rs` の Friday low breadth / modest market pocket（`market_ratio 1.00-1.10` / `breadth < 0.55`）を selector から除外すること
  - `catchup_gapdown` の Wednesday negative-trend pocket を selector から除外すること
  - `fallback` の Tuesday / Friday 弱市場（`market_ratio 1.00-1.10` / `breadth < 0.55` / positive gap）は equity notional を `0.50` に抑えること
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
  - open エントリーで同日 breadth を見ない no-lookahead 回帰
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
  - インスタンスロックのメタデータ保存と、malformed LIVE lock を削除せず停止すること
  - LIVE 口座 snapshot が `configured_risk_capital` や `realized_pnl_today` を 0 で潰さないこと
  - スナップショット計算
  - scan 候補と live entry 判断ログの行生成
  - server time ベースの月次 state / 月初資産ロールオーバー
  - 保有中ポジションの intraday snapshot 行生成と entry context 付与
  - live entry 後の protective stop arming と portfolio 反映
  - daytrade exit decision 行の modeled exit / fade 指標と、live 約定時の二重スリッページ防止
  - live での intraday failed-runup break-even exit と post-entry high/low 追跡
  - post-entry high/low が legacy `highest_price` / `lowest_price` に引きずられず、fresh な current quote から更新されること。stale quote では更新しないこと
  - shared intraday stop / target と `14:30` force flatten の live exit フロー
  - live 部分約定時に shares を減らして保有継続し、partial fill event を exit log へ残すこと
  - live での unmanaged position を signal flatten / force flatten から除外すること
  - exact `execution_id` でのみ保護逆指値を紐づけること
  - 複数 `execution_id` 既知時は close route 不明の fallback を止めること
  - `confirmed` 欠損の stop result では protective stop を armed にしないこと
  - `HoldQty` 欠損の建玉を fail closed にして、保護逆指値 / 返済割当で数量を推測しないこと
  - `protective_stop_unconfirmed_order_id` が残る間は同一建玉への再 armed を止めること
  - signal/manual exit 前に linked protective stop を cancel し、未確定なら exit を止めること
  - signal/manual exit 後に partial remainder の protective stop を再 arm すること
  - partial remainder の protective stop rearm が失敗したら unresolved exit として止めること
  - entry record が複数 `execution_id` を保持し、保護逆指値の紐づけでその集合を使うこと
  - entry / exit の unresolved partial / zero-fill で `entry_order_execution_status` / `exit_order_execution_status` を残すこと
  - `received_at` は分離して保持し、`quote_timestamp` / `current_price_timestamp` が無い quote は entry で使わないこと。`LiveReadinessReport` では `quote_timestamp` / `received_at` / `age_seconds` / `max_age_seconds` の evidence も残すこと
  - multi-HoldID の protective stop を `ClosePositions` 経路で設定し、空の close route は通さないこと
  - stop journal が `ROUTE_RESOLVED` と route summary を残し、multi-HoldID の `ClosePositions` と `hold_ids` を復元できること
  - protective stop cancel 未確定を unresolved exit として扱い、新規 scan を止めること
  - protective stop が filled-before-cancel だった場合も exit を送らずに止めること
  - shared flatten 経路でも protective stop cancel 未確定なら exit を送らないこと
  - unresolved な exit order を持つ建玉では重複する flatten を送らないこと
  - non-trading day の終了処理でも safe shutdown 経由にすること
  - safe shutdown が protective stop pending / orphan を検出したら flatten を止めること
  - armed protective stop が broker 側 snapshot から消えていたら flatten を止めること
  - live entry の unresolved partial / zero-fill を未解決注文として journal に残し、続きの entry を止めること
  - live 側での inverse / `inverse_pullback` / `inverse_rebreak` の扱い
  - watchlist / portfolio / market index の 50 銘柄上限制御と優先順位
  - 監視銘柄 registry 同期の成功 / 失敗を entry gate に反映すること
  - orders API で未確認だった protective stop の order_id も後続 cancel へ引き継ぐこと
  - SIGINT/SIGTERM が安全停止フラグに変換され、signal handler が I/O を行わないこと
  - safe shutdown の structured result と reconciliation failure の可視化
  - safe shutdown が managed order cancel 未確定なら flatten を見送ること
  - safe shutdown が managed order だけを cancel し、unmanaged order / position を触らないこと
  - unexpected exception が最後の runtime state を使って safe shutdown を試みること
  - board quote freshness helper が stale / cross-day quote を entry 前に落とし、`quote_timestamp` / `received_at` / `age_seconds` の evidence を返すこと
- `tests/test_kabucom_broker.py`
  - `resolve_stock_order_action()` が long-only の fail-closed になり、short action を拒否すること
  - `core/kabucom_broker.py` の POST 再送抑止
  - `core/kabucom_broker.py` の GET 429 Retry-After 待機が上限付きで、shutdown 要求で中断できること
  - `KABUCOM_LIVE` の新規 entry を `ENABLE_LIVE_ORDER` / `APPROVED_CONFIG_HASH` なしで拒否すること
  - LIVE financial write gate が `KABUCOM_TEST` fixture provenance と structured CI attestation bundle (`.json` + `.sha256`) を要求し、`KABUCOM_LIVE` では operator ack を `KABUCOM_LIVE_OPERATOR_ACK_CONTEXT` に限定し、legacy boolean / explicit 引数を live gate に使えないこと
  - live 実行では GitHub Actions の workflow run / artifact の照合ができる場合、artifact digest と zip 内容まで検証すること
  - GitHub artifact verification の cache hit と TTL=0 再検証が想定どおり動くこと
  - GitHub artifact verification の失敗理由が token / response body を漏らさず generic のまま返ること
  - GitHub artifact verification が session fingerprint 変更で cache invalid になること
  - GitHub artifact verification が workflow_run_head_sha_mismatch / workflow_artifact_head_sha_mismatch / workflow_run_conclusion_failure / workflow_artifact_expired / timeout で fail closed になること
  - attestation bundle の digest sidecar が欠けるか mismatch なら live write を閉じること
  - `TRADE_MODE=KABUCOM_LIVE` で JPX calendar source の `source_url` / `source_hash` / `generated_at` / `coverage_start` / `coverage_end` / duplicate / overlap / stale を検証し、coverage gap / fallback に落ちる場合に live write を閉じること
  - `LiveReadinessReport` の `execution_id_truth` が aggregate `execution_ids` / duplicate execution_id / `position_lot_key_needs_review=True` を blocked にし、truth lot だけを ready 扱いすること
  - `LiveReadinessReport` の `execution_id_truth` が duplicate execution_id も blocked にすること
  - `LiveReadinessReport` の `no_lookahead_audit` が risk review blocked 時に ready にならないこと
  - structured operator ACK が code_commit_sha / approved_config_hash / runtime_config_hash / repository_full_name / test_fixture_hash / live_write_attestation_hash mismatch で閉じること
  - risk review が `code_commit_sha` / `approval_manifest_hash` mismatch で blocked になること
  - `build_live_write_attestation.py` が actual KABUCOM_TEST capture では `APPROVED_CONFIG_HASH` を必須にし、手動 fixture では skip すること
  - `OrdersSuccess` 系の注文状態パーサーと `State=1..10` の解釈
  - `SeqNum` 順の detail 並べ替え、`RecType=8` のみを fill / ExecutionID に使うこと、`State=4` detail を reject 扱いにすること
  - `BoardQuote` への bid/ask 正規化と special / inverted quote の reject
  - `SubmissionResult` の accepted / rejected / unknown 分岐
  - response text が長すぎる場合の truncation と秘密値 redaction
  - `OrderSubmissionResult` / `ExecutionWaitResult` / `CancelResult` の typed result と、未解決・取消結果の情報落ち防止
  - `OrderSubmissionResult` の `bool` は accepted 判定であり、confirmed とは別であること
  - `ExecutionWaitResult` の `execution_status` / `entry_execution_status` / `exit_execution_status` を legacy dict へ残すこと
  - single HoldID fallback で生成した `ClosePositions` を orders API 確認へ渡すこと
  - confirmation failure 時の `confirmation_details` が secret を含まない bounded summary であること
  - stop journal が `ROUTE_RESOLVED` を含み、`ClosePositions` / `hold_ids` / route stage を残すこと
  - `live_approval_manifest` の hash が strategy 定数変更で変わり、`generated_at` では変わらないこと
  - runtime entry authorization context が未解決注文、曖昧建玉、stale quote、shutdown 要求をまとめてブロックすること
  - runtime entry authorization context が protective stop pending / orphan もブロックすること
  - runtime entry authorization context が registry 未同期もブロックすること
  - `LiveReadinessReport` が protective stop lifecycle / partial fill / execution-ID truth / quote freshness / journal reconciliation / request budget / risk readiness / no-lookahead audit をまとめて fail closed にし、`quote_freshness` では `quote_timestamp` / `received_at` / `age_seconds` / `max_age_seconds` の evidence を残し、`journal_reconciliation` では accepted order missing at broker / broker position without journal / journal filled without position / unconfirmed stop replay / corrupt final line / corrupt middle line を見分けること
  - `request_budget` は new exposure だけを止め、protective stop / exit / cancel / read-only は別経路で継続すること
  - `request_budget` が orders / wallet / positions / registry / market_data / auth / other のいずれかで予算超過すると blocked になること
  - `LIVE_RISK_REVIEW_PATH` か `contracts/live_risk_review.json` が無い場合に risk readiness / no-lookahead audit が ready にならないこと
  - risk review の `code_commit_sha` / `runtime_config_hash` / `approval_manifest_hash` 不一致が live readiness を閉じること
  - live 口座余力の `wallet/cash` / `wallet/margin` 分離と、永続 strategy state を broker snapshot に混ぜないこと
  - `BrokerEnvironment` / `BrokerEndpointConfig` の mismatch を constructor / validate で拒否すること
  - live / test endpoint の mutating write が trade mode 不一致では拒否されること
  - 新規注文の `Exchange` 設定参照と返済ルート由来の `Exchange` / `MarginTradeType`
  - 買い新規の `Exchange` 未設定時は `KABUCOM_ORDER_EXCHANGE` を暗黙既定せずに reject すること
  - `AccountType` 未設定時は暗黙 4 へ fallback せずに reject すること
  - broker position の `ownership` 判定と live での unmanaged スキップ
  - broker position の ownership 判定が local `execution_ids` の any-match を使うこと
  - `HoldQty` 欠損の建玉を unknown 扱いにし、返済割当を fail closed にすること
  - 注文 payload の tick 正規化と float 送信
  - 逆指値 payload の trigger price 正規化
  - `cancelorder` の `OrderID` 送信と cancel 完了確認、unknown order 監視
  - cancel 完了時の terminal reason を保持し、filled-before-cancel / expired を見分けること
  - `KABUCOM_ORDER_PASSWORD` を設定した場合に sendorder / cancelorder が API 認証用パスワードと分離されること
  - LIVE では `KABUCOM_ORDER_PASSWORD` 未設定の sendorder / cancelorder を送信前に reject すること
  - stop journal が route summary を保存し、pre-resolution reject と resolved route を区別できること
  - `POST 401` の再送抑止と `GET 401` の再試行
  - managed position だけを使う売り返済の close position 割り当て
  - `execution_id` 単位で local metadata を復元し、symbol merge で状態を混ぜないこと
  - `_build_close_positions_for_symbol()` が execution_id 指定で対象建玉を絞り込むこと
  - sell side の `ClosePositions` 空配列を fail closed にすること
  - `StockOrderAction` ベースの public order API が long-only contract を守り、unsupported short action を送信前に reject すること
  - `execute_chase_order()` が約定完了時に `FILLED` journal event を残すこと
  - 注文一覧取得失敗時の fail closed
  - API health が 401 を成功扱いしないこと
  - launcher の port reachable と authenticated ready を分離し、401 を認証完了扱いしないこと
  - `get_server_time` が symbol endpoint ではなく `wallet/cash` の `Date` header を使うこと
  - request budget が orders / wallet / positions / registry / market_data / auth / other で分かれて記録されること
  - trade history の append-only 化
  - order journal の append-only 記録
- `tests/test_file_io.py`
  - JSONL 監査ログ helper が append-only に追記すること
- `tests/test_kabucom_contracts.py`
  - kabucom API 契約 fixture が送受信の validator を通ること
  - fixture の内容変更で hash が変わること
  - official `kabucom/kabusapi` の `reference/kabu_STATION_API.yaml` (commit `0119077f1647b7c3ff64460b862c1978142df43d`) と version `1.5` を manifest に記録すること
  - order / cancel の request password policy を検証すること
- `tests/test_kabucom_contracts_test_fixture.py`
  - `KABUCOM_TEST` 用の sanitized contract fixture が validators を通ること
  - `fixture_kind` と `password_policy` が TEST 用 fixture に明記されていること
  - test fixture の provenance metadata が明記され、`captured_from_kabucom_test` が欠けた fixture を fail closed にすること
  - structured CI attestation artifact が fixture hash / approval manifest hash / commit sha / repo / test command / run URL の整合を要求すること
  - 現在の test fixture は手動で sanitization したもので、実 KABUCOM_TEST 取得結果ではないことを明示していること
- `tests/test_portfolio_state.py`
  - schema versioned portfolio JSON の write / read
  - execution_id primary の lot identity と legacy migration backup
- `tests/test_analyze_intraday_logs.py`
  - `analyze_intraday_logs.py` の decision 集計
  - intraday trade path 集計
  - exit log を使った final outcome 上書き
  - source file status と analysis readiness の可視化
  - setup 別サマリー出力
- `tests/test_live_approval_manifest.py`
  - ライブ承認マニフェスト hash の生成と永続化
  - `generated_at` を hash から除外すること
  - `core.logic` の strategy 定数変更で hash が変わること
- `tests/test_order_journal.py`
  - order journal に `schema_version` / `event_id` / `sequence` / `process_id` を付けること
  - JSONL append が連番で追記されること
  - journal replay が PLANNED / ACCEPTED / CANCEL_REQUESTED の未解決 intent を拾うこと
  - startup recovery が corrupt journal 行を final / middle で分けて扱い、accepted order missing at broker / broker position without journal / journal filled without position / unconfirmed stop replay も manual review にすること
  - startup recovery が protective stop の pending / orphan 状態も manual review にすること
  - startup recovery が armed だが broker snapshot に無い protective stop も manual review にすること
  - journal replay が `FILLED` / filled-before-cancel を終端扱いにし、fsync 失敗を fail closed にすること
- `tests/test_portfolio_state.py`
  - `portfolio.json` を schema-versioned JSON で保存すること
  - legacy CSV を読み込んで migration できること
  - 空の `portfolio.json` でも CSV フォールバックで読み込めること
  - aggregate `execution_ids` lot を review-needed として保存すること
  - migration 時に archive backup を残すこと

全件実行:

```bash
python -m pytest tests -q
```

GitHub Actions でも同じく `python -m pytest tests -q` を Windows runner で実行し、fixture が actual `KABUCOM_TEST` capture になった段階で `contracts/kabucom_live_write_attestation.json` と `.sha256` を生成して artifact としてアップロードします。現状の手動 fixture では build step はスキップされますが、actual capture に進むと `APPROVED_CONFIG_HASH` が必須になります。`TRADE_MODE=KABUCOM_LIVE` では `contracts/jpx_trading_calendar.json` も必要で、coverage gap / fallback が出る場合は live financial write を開けません。

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
python -m pytest tests/test_kabucom_broker.py
python -m pytest tests/test_kabucom_contracts.py
python -m pytest tests/test_kabucom_contracts_test_fixture.py
python -m pytest tests/test_portfolio_state.py
python -m pytest tests/test_analyze_intraday_logs.py
python -m pytest tests/test_order_journal.py
```

## KABUCOM_LIVE 再開 runbook

### KABUCOM_LIVE financial write gate

`KABUCOM_LIVE` の financial write は、外部依存が揃ったときだけ開きます。足りないものは捏造せず、closed のままにします。現時点では actual `KABUCOM_TEST` capture / GitHub Actions run-state / JPX calendar / structured operator ACK / risk review が未完了なので、reopen checklist が揃うまで closed です。

### Required external evidence

| 何を見るか | 必要条件 |
| --- | --- |
| 外部証跡 | actual `KABUCOM_TEST` capture / GitHub Actions run-state / JPX calendar source |
| 承認証跡 | structured operator ACK / CI attestation artifact / risk review |
| 実行前 readiness | `LiveReadinessReport ready` / `request-budget readiness true` / `no-lookahead review complete` |
| 判定 | 1 つでも欠けたら closed のまま |

### actual `KABUCOM_TEST` fixture capture

- 実口座の `KABUCOM_TEST` でしか取れない fixture は、手書きで作らない
- 発注前に、対象銘柄、最小数量、板、余力、約定リスク、即時取消手順を確認する
- 注文後は orders を取得し、即時 cancel して cancel 完了を確認する
- 取消確認が取れない場合は fixture 化せず、手動対応記録だけ残す
- capture した raw response には秘密値が残るので、fixture は sanitization と provenance metadata を付けて保存する
- `captured_from_kabucom_test=true` を含む provenance が無い fixture は LIVE に使わない
- actual capture から attestation を作る段階では `APPROVED_CONFIG_HASH` を必須にし、手動 fixture では build を skip する

### GitHub Actions 実 run 確認

- GitHub Actions の workflow run で `python -m pytest tests -q` が green になっていることを確認する
- Checks view / Checks API / Actions run page のいずれかで、commit SHA と run id を記録する
- workflow run id / head SHA / conclusion success / artifact expiration を照合する
- artifact の digest と zip 内容を確認し、ローカル attestation と一致させる
- branch protection の required checks が green であることを確認する
- `GITHUB_TOKEN` / `GH_TOKEN` は read-capable secret として管理し、rotation 時は secret を更新して再検証する
- token / response body / archive contents はそのままログに出さず、失敗理由は generic に保つ
- 既定の `GITHUB_ARTIFACT_SOURCE_CACHE_TTL_SEC` は `600` 秒で、短くすると再検証が増え、長くするとローテーション反映が遅れる
- verification 結果は `GITHUB_ARTIFACT_SOURCE_CACHE_TTL_SEC` 秒だけ再利用し、期限切れ後は再検証する
- キャッシュを明示的に捨てたいときは `clear_live_write_attestation_artifact_source_cache()` を使う
- GitHub API 側の timeout / 一時障害は generic な `workflow_run_request_failed` などとして扱い、token をログに出さずに再試行する
- CI 実 run が未確認なら `KABUCOM_LIVE` の write gate は開けない

### JPX calendar source 運用

- `contracts/jpx_trading_calendar.json` は authoritative source として扱う
- `schema_version=1`、`source_url`、`source_hash`、`generated_at`、`coverage_start`、`coverage_end`、`closed_dates`、`trading_dates`、`half_day_dates` を明記する
- `source` は legacy compatibility field としてのみ読み込み、`KABUCOM_LIVE` の require_source では `source_url` 欠落を invalid 扱いにする
- `generated_at` が `JPX_CALENDAR_MAX_AGE_DAYS = 370` を超えたら stale として fail closed にする
- duplicate / overlap の日付は invalid にする
- missing / invalid / stale / coverage gap / fallback は全部 fail closed
- half-day は 11:30 で終了し、以後の新規 entry はしない

### Required runtime acknowledgement

- `operator_id`
- `acknowledged_at`
- `expires_at`
- `code_commit_sha`
- `approved_config_hash`
- `runtime_config_hash`
- `repository_full_name`
- `test_fixture_hash`
- `live_write_attestation_hash`
- `reason`
- `KABUCOM_LIVE` では `KABUCOM_LIVE_OPERATOR_ACK_CONTEXT` を必須にし、legacy boolean / explicit 引数だけでは通さない
- ACK 期限切れ、hash 不一致、repo 不一致、fixture 不一致、attestation 不一致は全部 closed

### LIVE readiness report

- `LiveReadinessReport` は startup log と entry authorization で参照する
- `protective_stop_lifecycle`
- `partial_fill_unresolved`
- `execution_id_truth`
- `quote_freshness` は `quote_timestamp` / `current_price_timestamp` / `received_at` / `age_seconds` / `max_age_seconds` を evidence に残す
- `journal_reconciliation` は accepted order missing at broker / broker position without journal / journal filled without position / unconfirmed stop replay / corrupt final line / corrupt middle line を含めて判定する
- `request_budget`
- `risk_readiness`
- `no_lookahead_audit`
- どれか 1 つでも `not_verified` / `blocked` なら新規 entry は止める
- startup で blocked になった項目は Discord にも出す

### risk strategy review

- risk review は別途 `train / validation / untouched holdout` と `walk-forward` を揃えてから承認する
- `transaction_cost_stress` / `slippage_stress` / `capacity_liquidity_stress` / `rule_complexity_report` / `no_lookahead_audit_hash` が揃わない限り `risk_readiness` は true にしない
- `code_commit_sha` / `runtime_config_hash` / `approval_manifest_hash` が現在値と一致しない review は使わない

### Reopen checklist

- actual `KABUCOM_TEST` fixture captured
- GitHub Actions run green confirmed
- attestation artifact verified
- JPX calendar source valid and within coverage
- structured operator ACK valid
- LiveReadinessReport ready
- risk readiness true
- request-budget readiness true
- no-lookahead review complete

## 運用メモ

- 戦略変更は、まず [core/logic.py](core/logic.py) の shared logic を直し、その結果を本番・バックテストから参照させます
- 改善探索では、やみくもに閾値を振るのではなく、負け日・未達週の原因分析から仮説を立てます
- 効かなかった案は [STRATEGY_EXPERIMENT_LOG.md](STRATEGY_EXPERIMENT_LOG.md) に残して、別セッションで同じ試行を繰り返さないようにします
- 実地取得や外部状態確認が必要で今回のコード差分に入れない項目は [docs/kabucom_live_deferred_external_tasks.md](docs/kabucom_live_deferred_external_tasks.md) に整理します
- テストを追加・変更した場合は、README のテスト欄にも対象内容と実行方法を反映します

Last updated: 2026-06-22
