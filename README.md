# Auto-Trade

日本株向けの自動売買・バックテスト用リポジトリです。  

現在の主戦略は、**当日中に建玉を閉じるデイトレード戦略**です。

このリポジトリでは、**本番戦略ロジックを唯一の判断源**として扱います。  

バックテストは本番ロジックを検証するための実行レイヤーであり、独自の売買判断を持たせない前提です。運用ルールの詳細は [AGENTS.md](AGENTS.md) を参照してください。

また、探索の履歴と「もうそのまま再試行しない案」は [STRATEGY_EXPERIMENT_LOG.md](STRATEGY_EXPERIMENT_LOG.md) に残しています。
次セッションでの改善順序、API停止中に進める評価基盤、再試行禁止項目は [次セッション戦略開発方針](docs/strategy_development_next_session.md) にまとめています。


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

  - `primary` の Wednesday hot-gap / below-SMA では、score `>= 7.5` の tail を no-trade にする

  - `primary` の Wednesday hot-gap / below-SMA では、low-breadth / weak-market / sub-six pocket (`breadth < 0.52` / `market_ratio 1.00-1.02` / `score < 6.0` / `gap >= 1.2%` / `open_vs_sma_atr < 0` / `prev_return >= 0`) を no-trade にする

  - `primary` の Wednesday hot-gap / below-SMA では、`open_vs_sma_atr <= -1.5` の深い tail を no-trade にする

  - `primary` の Wednesday hot-gap / mid-breadth / hot-market pocket (`breadth 0.55-0.65` / `market_ratio >= 1.17` / `gap >= 2.0%`) は no-trade にする

  - `primary` の Wednesday hot-gap / mid-breadth / hot-market exact pocket (`breadth 0.55-0.65` / `market_ratio 1.10-1.15` / `gap 0-1%` / `score 6.0-8.0` / `open_vs_sma_atr < 0`) は no-trade にする

  - `primary` の Wednesday `10-11` continuation は no-trade にする

  - `primary` の Wednesday mid-breadth / hot-market / high-score / low-open residual pocket (`breadth 0.60-0.71` / `market_ratio 1.15-1.20` / `score 7.5-10` / `open_vs_sma_atr < 1.0`) は no-trade にする

  - `primary` の intraday failed-runup exit は、entry後に一度でも建値を上回ったあと建値以下へ失速したら、stop/target優先の保守的順序を維持してbreak-evenへ退避する

  - `catchup_rs` の Monday / Friday 高 breadth hot-market は selector から除外する

  - `catchup_rs` の Monday mid-breadth / stretched-open pocket は selector から除外する

  - `catchup_rs` の Tuesday low-breadth / weak-market / high-score pocket は selector から除外する

  - `catchup_rs` の Tuesday low-breadth / moderate-market pocket（`breadth < 0.45` / `market_ratio 1.00-1.05` / `score 8-10`）は selector から除外する

  - `fallback` の high breadth / hot-market pocket は selector から除外する

  - `catchup_rs` の Friday low breadth / modest market pocket（`market_ratio 1.00-1.10` / `breadth < 0.55`）は selector から除外する

  - `catchup_rs` の low-breadth / strong-continuation pure-win pocket（`breadth < 0.50` / `prev_return >= 3%` / `open_vs_sma_atr <= 1.0` / `score >= 10.0`）は selected base leverage を `0.35` に引き上げ、equity notional を `5.0` / risk budget を `0.30` にする

  - broad `catchup_gapdown` family は、複数年 train で net negative かつ月次 `+20%` 達成本数を改善しないため、細かな例外を足さず shared setup 全体を no-trade にする

  - `fallback` の Tuesday / Friday 弱市場（`market_ratio 1.00-1.10` / `breadth < 0.55` / positive gap）は equity notional を `0.50` に抑える

  - `fallback` の Monday mid-breadth / neutral-market / stable-open pocket（`breadth 0.45-0.55` / `market_ratio 0.98-1.01` / `score 4.5-6.5` / `open_vs_sma_atr 2.0-3.5`）は notional を `0.25`、equity notional を `2.5` に引き上げる
  - `fallback` の Wednesday mid-breadth / hot-market / stretched-open pocket（`breadth 0.45-0.55` / `market_ratio 1.00-1.05` / `score 6.0-8.0` / `prev_return >= 4%` / `open_vs_sma_atr >= 3.5`）は notional を `0.25`、equity notional を `2.0` に引き上げる
  - `primary` の broader high-breadth / hot-market / stable-gap / mid-high-score pure-win pocket（`breadth 0.60-0.78` / `market_ratio 1.17-1.225` / `score 6.5-13.0` / `gap -1.0%~0.5%` / `open_vs_sma_atr -0.5~3.5` / `prev_return >= 1%`）は equity notional を `6.0` にする
  - `primary` の high-confidence continuation family（`primary_equity_notional_pct >= 3.0`）は notional の下限を `0.20` にする

  - `primary` の Wednesday mid-breadth / hot-market / stable-gap / pure-win pocket（`breadth 0.65-0.70` / `market_ratio 1.16-1.20` / `score 4.8-6.0` / `gap <= 0%` / `open_vs_sma_atr >= 2.0`）は equity notional を `3.0` にする
  - `primary` の Wednesday high-breadth / hot-market / stable-gap / high-score pure-win pocket（`breadth 0.70-0.75` / `market_ratio 1.15-1.20` / `score 6.5-8.0` / `gap <= 0%`）は equity notional を `3.0` にする
  - `primary` の Tuesday high-breadth / extreme hot-market / large-gap pure-win pocket（`breadth >= 0.75` / `market_ratio 1.10-1.15` / `score >= 10` / `gap >= 2.0%`）は equity notional を `3.0` にする
  - `primary` の Friday high-breadth / hot-market / stable-gap / high-score pure-win pocket（`breadth 0.60-0.75` / `market_ratio >= 1.15` / `gap 0-0.5%` / `score 6.0-8.0` / `prev_return >= 1%` / `prev_rsi2 >= 50.0` / `open_vs_sma_atr <= 2.7`）は equity notional を `10.50` にする

  - `catchup_rs` の Tuesday low-breadth probe candidate（`breadth 0.18-0.36` / `score 8.0-12.0` / `gap <= 1.0%`）は probe leverage を `0.25` にする

  - `fallback` の Friday low-breadth / sub-neutral-market / stable-open pocket（`breadth < 0.45` / `market_ratio < 1.00` / `score <= 4.5` / `open_vs_sma_atr 1.5-2.3`）は no-trade にする

  - `primary` の Tuesday high-market mid-breadth では、stop-heavy な low-score / low-RS サブクラスターだけを quarter-size に落とす

  - `primary` の Tuesday mid-breadth / low-score / hot-market continuation は、small-gap pocket を 0.10 に寄せつつ、low market-ratio / positive-gap pocket は no-trade にする

  - `primary` の Tuesday mid-breadth / low-score / stretched-open / hot-market pocket は no-trade にする

  - `primary` の Tuesday high-breadth / hot-market / low-score / sub-half-ATR-open pocket は selected base leverage を `0.10` に制限する

  - `primary` の Wednesday high-breadth / hot-market / low-score / mid-open pocket は selected base leverage を `0.10` に制限する

  - `primary` の Wednesday high-breadth / hot-market / low-score / broad probe pocket (`breadth 0.60-0.78` / `market_ratio >= 1.20` / `score <= 8.0` / `gap <= 1.0%`) は selected base leverage を `0.10` に制限する

  - `primary` の Wednesday high-open / low-score / tight-gap pocket (`market_ratio <= 1.08` / `score <= 6.7` / `gap <= 0.5%` / `open_vs_sma_atr >= 2.0`) は no-trade にする

  - `primary` の Tuesday stretched-open / mid-breadth / hot-market / weak-RSI pocket は RSI2 `71.0` 未満を no-trade にする

  - `primary` の Tuesday low-open / mid-breadth / hot-market / weak-open pocket は no-trade にする

  - `primary` の Wednesday mid-breadth / hot-market / low-prev-return pocket は no-trade にする

  - `primary` の Tuesday / Wednesday high-breadth / hot-market / mid-score / high-RSI pocket (`breadth 0.65-0.75` / `market_ratio 1.15-1.28` / `score 6.0-8.0` / `open_vs_sma_atr -0.5-2.0` / `prev_rsi2 >= 50.0`) は no-trade にする

  - `primary` の low-breadth / weak-market / score `6.0-8.0` / positive-gap pocket (`breadth 0.45-0.55` / `market_ratio 1.00-1.05` / `score 6.0-8.0` / `gap 0-2%` / `open_vs_sma_atr 1.0-3.0` / `prev_return <= 4.5%`) は no-trade にする

  - `primary` の Wednesday hot-market / low-score / negative-gap / low-open pocket (`breadth 0.60-0.75` / `market_ratio 1.10-1.15` / `score <= 6.5` / `gap -0.5%~0%` / `open_vs_sma_atr <= 1.5` / `prev_return >= 1%`) は no-trade にする

  - `primary` の Friday hot-market / low-score / negative-gap / low-open pocket (`breadth 0.65-0.75` / `market_ratio 1.10-1.15` / `score <= 6.0` / `gap -0.5%~0%` / `open_vs_sma_atr <= 0.5` / `prev_return >= 1%`) は no-trade にする

  - `primary` の Friday low-breadth / near-neutral-market / small-positive-gap pocket は no-trade にする

  - `primary` の Wednesday `breadth >= 0.50` / `open_from_prev_low_atr >= 1.5` の stretched-open pocket は no-trade にする

  - `primary` の Tuesday high breadth / high-score / stretched open は half-size に落とす

  - `primary` の Tuesday / Thursday mid-breadth / hot-market / score `8-10` は selected base leverage を `0.10` に制限する

  - `primary` の火曜以外の high breadth / mid-hot market / score `> 8` は equity notional を `1.00` にする

  - `strong_oversold` の Tuesday 伸び切り open は selector から除外する

  - `primary` の Monday high-market high-breadth / low-RS は no-trade を許容する

  - `primary` の Monday high-market high-breadth / high-RS / stretched continuation は no-trade を許容する

  - `primary` の Monday / Thursday broad hot-market は no-trade を許容する

  - `primary` の Monday mid-high breadth / hot-market / non-positive-gap pocket は no-trade を許容する

  - `primary` の Monday mid-breadth / mildly hot-market / tight-gap pocket は no-trade を許容する

  - `primary` の Monday mid-breadth / moderate-extension は no-trade を許容する

  - `primary` の Monday high-breadth / soft-gap continuation は no-trade を許容する

  - `primary` の Wednesday high-market mid-breadth / high-RS / stretched open は quarter-size に落とす

  - `primary` の Wednesday mid-breadth / hot-market / score `9-12` / breadth `0.60-0.80` / market_ratio `1.07-1.21` は selected base leverage を `0.10` に制限する
  - `primary` の broader high-breadth / hot-market / stable-gap / mid-high-score pure-win pocket（`breadth 0.60-0.78` / `market_ratio 1.17-1.225` / `score 6.5-13.0` / `gap -1.0%~0.5%` / `open_vs_sma_atr -0.5~3.5` / `prev_return >= 1%`）は equity notional を `6.0` にする
  - `primary` の high-confidence continuation family（`primary_equity_notional_pct >= 3.0`）は notional の下限を `0.20` にする

  - `primary` の Wednesday mid-breadth / hot-market / stable-gap / pure-win pocket（`breadth 0.65-0.70` / `market_ratio 1.16-1.20` / `score 4.8-6.0` / `gap <= 0%` / `open_vs_sma_atr >= 2.0`）は equity notional を `3.0` にする

  - `primary` の high market-ratio / mid-breadth / mid-score / moderate-prev-return / positive-gap は quarter-size に落とす

  - `primary` の Wednesday low-breadth / high-gap / high-score / strong-open は quarter-size に落とす

  - `primary` の Wednesday low-breadth / weak-market / small-gap pocket は no-trade にする

  - `primary` の Wednesday mid-breadth / weak-market / score `6-8` / small-gap pocket は no-trade にする

  - `primary` の Thursday high-score / moderate-prev-return / hot-market / stretched open は quarter-size に落とす

  - 火曜の low-score / hot-market の narrow pocket は no-trade にする

  - 月曜 / 木曜 / 金曜の low-score / hot-market continuation は no-trade にする

  - `primary` の very hot / low-breadth / negative-gap / strong-prior-day continuation は no-trade を許容する

  - リスク、流動性、スリッページ、急落時損失を無視した過大建玉は採らない

共有戦略ロジックの中心は [core/logic.py](core/logic.py) です。

改善方針、探索ルール、train / holdout の厳守事項は [AGENTS.md](AGENTS.md) を参照してください。  

採用済み baseline と不採用案の履歴は [STRATEGY_EXPERIMENT_LOG.md](STRATEGY_EXPERIMENT_LOG.md) に集約しています。

## 現在の検証状況

最新確認日は **2026-07-15** です。

使用データの最新日は **2026-07-14** です。

データ更新と標準確認は `python scripts/jp_refresh_validate.py --holdout-months 6 --standalone-latest-months 1` で行いました。

採用 baseline の確認は `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1` で行いました。

train-only diagnostics は `python analyze_backtest_trade_log.py --holdout-months 6 --top-n 30 --output-trades-csv tmp\train_trade_log.csv` で確認しました。

以下の数値は日足OHLCによる `reference-only` baselineです。2026-07-14時点ではproduction snapshotとlinked actual exitがまだ0件なので、本番条件での収益性は未検証です。

2026-07-14 09:42..09:52に、live writeを無効にした `KABUCOM_TEST` でactual snapshot取得を再試行しました。しかしkabuステーションのログイン/API認証が10分以内に完了せず、snapshotは0件のままです。`KABUCOM_TEST / KABUCOM_LIVE` のstrict production replayはいずれも `STATUS: INSUFFICIENT_SNAPSHOTS` でfail closedになりました。

2026-07-14 23:01に読み取り専用で再監査した時点でも、認証済みAPIは利用不可で、TEST / LIVE strict replayは双方 `SNAPSHOTS: 0 / STATUS: INSUFFICIENT_SNAPSHOTS` です。大引け後のため、当日9:30時点のsnapshotを日足から後付け補完していません。

同日23:32に既定の `data/kabucom_test/order_journal.jsonl` を全件監査したところ、6,891行のうち銘柄付き6,051行はすべて単体テスト用 `1234`、銘柄なし840行もすべて疑似注文ID `ORDER-1` で、production snapshot IDとtrade modeは全行欠落していました。実注文証拠を無視する分岐は追加せず、原本2,930,677 bytesを `data/kabucom_test/quarantine/order_journal.unit_test_synthetic.20260611_20260714.f47f5587.jsonl` へ隔離しました。SHA-256は `F47F5587A77D55D3DDFFCDBA0F6972A028EFE6742CF8FF2C87F0AF8037700C14` で移動前後一致です。既定journalは未解決0件となり、空ポジション・空注文・wallet完全時のstartup recoveryはmanual review不要へ戻りました。隔離後の全テストでも既定journalは未生成のままです。API healthは引き続きfalse、TEST / LIVE strict replayは双方snapshot 0なので、本番同等未検証・本番収益性未検証は継続します。

2026-07-15 08:56..09:08に `KABUCOM_TEST / ENABLE_LIVE_ORDER=false` でactual captureを再試行しました。kabuステーションへのログインは完了しましたが、18080 / 18081のどちらにもAPI待受がなく、snapshotは0件でした。これはtoken認証以前の `api_port_not_listening` です。[公式初期設定](https://kabucom.github.io/kabusapi/ptal/howto.html)どおり、kabuステーション右上の `</>` を右クリックし、APIシステム設定で「APIを利用する」とAPIパスワードを設定して再起動する必要があります。launcherは今後、ポート未起動・パスワード未設定・token認証失敗を分離表示します。API利用可否はユーザー確認待ちとし、利用可能になるまでcaptureを再試行しません。

APIとは独立して、[JPX公式の営業時間・休業日一覧](https://www.jpx.co.jp/corporate/about-jpx/calendar/index.html)から `scripts/update_jpx_trading_calendar.py` で `contracts/jpx_trading_calendar.json` を生成しました。coverageは `2026-01-01..2027-12-31`、営業日486日、休場日244日、取得元HTMLのhashは `sha256:d6106b352ebdbecd922291c17933df6c10278634a4e69812a4746e37bf35559e` です。LIVE strict modeは公式HTTPS URLと64桁SHA-256だけを受け付け、calendar artifact自体もlive承認fingerprintへ含めます。2026-07-15は営業日、2026-07-20と2027-12-31は休場日としてstrict判定済みです。最新full testは `541 passed, 41 subtests passed`、runtime hashは `sha256:c510b6f0ccd30c1be0b8300d5ef9c151865c5019fad6643c8a78dc7266eecdd7` です。calendar gateは解消しましたが、actual TEST証跡など他の必須条件が未完了なのでLIVE writeは閉じたままです。

非simulationの運用時刻は、認証済み `wallet/cash` のHTTP `Date` headerだけをverified broker clockとして扱います。token欠落、HTTP失敗、header欠落・不正、受信時刻との30秒超の乖離ではローカルJSTへfallbackして監視・安全決済を継続しますが、新規entry、日次・週次・月次state更新、production snapshotはfail closedで停止します。verified時だけ月替わりを判定して `current_month` と `month_start_equity` を同時にロールし、schema v4 snapshotはsource、reason、server / received / fallback time、drift算術をidentityへ固定してstrict replayします。

発注直前のfresh最良売気配で数量を決めるだけでなく、その数量が許容できる最高entry価格も共有risk engineで同時に固定します。この価格上限はleverage、wallet余力、前日turnover流動性、stop risk、buying-power notional、equity notionalをすべて維持する最小上限です。LIVEの信用余力が正しく0円なら理論余力へfallbackせず0円のままentryを停止し、追従・強制指値が上限を超えた場合も注文を送信しません。decision log、order journal、strict replayはsizing価格・株数・価格上限、実注文qty、entry / exitの全追従注文IDと各ACCEPTED、aggregate実約定株数・加重平均価格・残数・ExecutionID、orders API応答から正規化した保護逆指値の注文ID・銘柄・state・qty・trigger・side・route、actual exitの全量決済・価格×数量gross PnLを同じsnapshotへ連結し、不一致や上限超過をfail closedにします。

API停止中にも本番母集団との差を検証できるよう、`python jp_backtest.py --holdout-months 6 --standalone-latest-months 1 --production-observation-replay` を追加しました。これは本番と同じ前日確定値、固定49銘柄、除外リスト、bull/inverse ETF予約、流動性headroomを共通関数で再生し、日ごとの候補母集団をその49銘柄へfail closedで制限します。共通観測ポリシー自体もlive承認hashへ含めます。ただし、9:30のBoard、特別気配、注文、約定、exitを再現するものではなく、引き続きdaily OHLC `reference-only` です。

2026-07-14までのproduction-observation-constrained確認値:

- train `2022-03-01..2026-01-09`: `RETURN -43.84% / 288 trades / WIN 32.99% / PF 0.72 / WEEKS >= +1% 35/201 / POSITIVE 52/201 / MONTHS >= +20% 0/46 / MONTHS >= 3/4 ACTIVE 0/46 / WORST DAY -51,000円`
- contaminated holdout `2026-01-13..2026-07-14`: `RETURN +10.20% / 21 trades / PF 2.08 / WEEKS >= +1% 5/27 / POSITIVE 9/27 / MONTHS >= +20% 0/5 / MONTHS >= 3/4 ACTIVE 0/5 / WORST DAY -18,000円`
- 100万円 standalone `2026-06-15..2026-07-14`: `RETURN +0.14% / 1 trade / WIN 100.00% / PF inf / WEEKS >= +1% 0/5 / POSITIVE 1/5 / WORST DAY 0円`

したがって、全Primeを見られる標準daily OHLC baselineの高収益を本番再現可能な収益として扱いません。過去に不採用とした50銘柄のgap / score / 曜日近傍は再探索せず、外部の全銘柄寄前feed、または履歴化してreplay可能なregistry入替経路がない限り、この制約下のalphaを採用しません。

上記の再試行条件に対応するAPI非依存の診断として、`python jp_backtest.py --holdout-months 6 --standalone-latest-months 1 --rotating-discovery-replay` も追加しました。[kabuステーションAPI公式リファレンス](https://kabucom.github.io/kabusapi/reference/index.html)の登録総数50銘柄制約に合わせ、指数 `1321` を常時保護し、残り49銘柄を4バッチ、合計196銘柄だけ巡回します。196は成績探索値ではなく、公式の情報系API上限10回/秒と既存30秒snapshot SLOから事前固定した運用上限です。

銘柄選定は前日確定値だけを使います。共有candidate engineへ前日終値比 `-2% / 0% / +2%` の固定仮想寄付を入力し、3シナリオで安定する候補、最大score、前日流動性の順に196銘柄を決めます。当日の実open、high、low、close、損益、曜日別成績はshortlistへ使いません。このreplayも日足OHLC `reference-only` であり、actual Boardや約定の証拠ではありません。

履歴全体を直接処理する分岐は持たせず、1営業日分の共有selectorを `core` に置き、history replayとlive準備adapterが同じ入力契約を呼びます。`trade_date <= feature_asof`、正規化後のticker重複、feature vector不整合、`1321` またはbreadth証拠欠落は空集合へfail closedにします。この厳格化により、`1321` のSMA200が未成立な `2022-03-01..2022-03-30` の21営業日は観測0、残り1,049営業日は196銘柄になりました。該当21日は従来もmarket gateで取引0だったため、全ての損益指標は不変です。

2026-07-14までのrotating-discovery-constrained確認値:

- full `2022-03-01..2026-07-14`: `RETURN +2428.31% / 405 trades / WIN 64.44% / PF 8.45 / WEEKS >= +1% 93/228 / POSITIVE 155/228 / MONTHS >= +20% 4/52 / MONTHS >= 3/4 ACTIVE 1/52 / WORST DAY -370,600円`
- train `2022-03-01..2026-01-09`: `RETURN +1217.72% / 360 trades / WIN 63.89% / PF 6.20 / WEEKS >= +1% 80/201 / POSITIVE 134/201 / MONTHS >= +20% 3/46 / MONTHS >= 3/4 ACTIVE 1/46 / WORST DAY -370,600円`
- contaminated holdout `2026-01-13..2026-07-14`: `RETURN +91.87% / 45 trades / WIN 68.89% / PF 14.23 / WEEKS >= +1% 13/27 / POSITIVE 21/27 / MONTHS >= +20% 1/5 / MONTHS >= 3/4 ACTIVE 0/5 / WORST DAY -325,000円`
- 100万円 standalone `2026-06-15..2026-07-14`: `RETURN +2.62% / 5 trades / WIN 60.00% / PF 13.47 / WEEKS >= +1% 1/5 / POSITIVE 3/5 / WORST DAY -2,100円`

train取引差分では、全Prime 335件と巡回196件の共通取引は287件でした。巡回側は全Primeの48件・合計 `+506,460円` を取り逃し、再順位付けした73件が合計 `-980,823円`、その後の共通取引も資本経路差で約630万円縮小しました。したがって固定49の赤字は大幅に解消したものの、全Primeの `+1996.83% / PF 35.90 / WORST -122,400円` には届きません。

原因仮説に対して次の2案だけをtrainで追加確認し、いずれも不採用にしました。

- 共有gap上限±3%を等間隔5点で覆う案: `RETURN +1150.69% / 355 trades / PF 5.55 / WEEKS >= +1% 80/201 / WORST -370,600円`
- 合成gapを使わない前日流動性上位196案: `RETURN +109.06% / 341 trades / PF 1.43 / WEEKS >= +1% 53/201 / WORST -149,600円`

運用側には `core/daytrade_opening_discovery.py` を追加し、初期registry清掃後に保護登録した `1321` のBoardを取得してから、4回の `register -> Board -> unregister` を行います。`1321` と全196件のBoard完全性、各batchの順序、30秒上限、最終registryが `1321` だけであることを1つのfail-closed結果へ束縛し、schema v4 snapshotへ保存できる証拠形式にしました。`compute_rotating_daytrade_production_snapshot()` がcollector結果からrequested codes、Board、失敗理由、全体時刻、policy、証拠を一意に組み立てるため、API復旧時に手作業で1321や時刻を落とす経路は使いません。ブローカー層もHTTP 200だけで成功扱いせず、公式 `RegistList` による登録・解除の完全反映を検証し、50銘柄超の単一登録をAPI送信前に拒否します。例外・部分登録・板欠損・解除失敗では候補選択へ進みません。

ただし、この巡回collectorはactual `KABUCOM_TEST` で未検証のため、`auto_trade.py` の本番観測経路にはまだ有効化していません。API利用可能の連絡後に同じcode/runtimeでregistry、Board時刻、candidate digest、注文lifecycleをstrict replayできるまで、「本番同等未検証」「本番収益性未検証」を継続します。train月20%も `3/46` のままで未達です。

full history の最新確認値（daily OHLC reference-only）:

- `FINAL EQUITY: 39,014,693円`
- `CLOSED TRADES: 379`
- `WIN RATE: 70.45%`
- `TOTAL RETURN: +3801.47%`
- `PROFIT_FACTOR: 22.13`
- `WEEKS >= +1%: 99/228`
- `POSITIVE WEEKS: 167/228`
- `MONTHS >= 3/4 ACTIVE: 1/52`
- `MONTHS >= 20%: 4/52`
- `WORST DAY: -525,000円`

train window の最新確認値:

- `EVALUATION: 2022-03-01 to 2026-01-09 (post-warmup)`
- `FINAL EQUITY: 20,968,302円`
- `CLOSED TRADES: 335`
- `WIN RATE: 70.75%`
- `TOTAL RETURN: +1996.83%`
- `PROFIT_FACTOR: 35.90`
- `WEEKS >= +1%: 85/201`
- `POSITIVE WEEKS: 146/201`
- `MONTHS >= 3/4 ACTIVE: 1/46`
- `WORST DAY: -122,400円`
- `MONTHS >= 20% (post-warmup full calendar months inside train): 3/46`

直近 6ヶ月 holdout `2026-01-13` から `2026-07-14` の確認値（contaminated / veto 用）:

- `FINAL EQUITY: 39,014,693円`
- `CLOSED TRADES: 44`
- `WIN RATE: 68.18%`
- `TOTAL RETURN: +86.07%`
- `PROFIT_FACTOR: 15.71`
- `WEEKS >= +1%: 14/27`
- `POSITIVE WEEKS: 21/27`
- `MONTHS >= 3/4 ACTIVE: 0/5`
- `MONTHS >= 20%: 1/5`
- `WORST DAY: -525,000円`

直近1ヶ月 `100万円 standalone` `2026-06-15` から `2026-07-14` の確認値（独立 replay）:

- `START EQUITY: 1,000,000円`
- `FINAL EQUITY: 1,026,188円`
- `TOTAL RETURN: +2.62%`
- `CLOSED TRADES: 5`
- `PROFIT_FACTOR: 13.47`
- `WEEKS >= +1%: 1/5`
- `POSITIVE WEEKS: 3/5`
- `WORST DAY: -2,100円`
現行 baseline は、setup 共通の通常 exposure を上限とし、過去の局所的な pure-win box による size-up を無効化しています。primary は score に応じて通常上限の50%から100%まで連続的に de-risk しますが、通常上限を超えて増幅しません。failed-runup exit は固定 slippage 後の手取り建値を trigger とし、backtest と live が同じ共有判定を使います。デイトレ replay は翌営業日を必要としないため、cache の最終営業日も評価対象です。


補足:

- これは将来成績を保証するものではありません

- データ更新やロジック変更で数値は変動します

- 月間 `3/4` 稼働目標は、現時点では未達です

- 週次 `+1%` は保証値ではなく、改善目標として扱っています

- holdout と standalone は、採用の加点材料ではなく、reference / veto 用の確認値です

- そのため、現時点では採用の加点材料ではなく、悪化が大きい案を止める `veto` 用の監視値として扱います

- 次の `clean holdout` は、今回のロジック凍結後となる `2026-07-14` 以降の未観測営業日から積み上げます

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

├── jp_production_replay.py

├── jp_jquants_fetcher_v2.py

├── jp_jquants_margin_fetcher.py

├── jp_optimizer.py

├── jp_walkforward.py

├── run_daily_cycle.py

├── run_imperial_oracle.bat

├── core/

│   ├── config.py

│   ├── daytrade_candidate_engine.py

│   ├── daytrade_production_replay.py

│   ├── jquants_margin_cache.py

│   ├── jpx_calendar.py

│   ├── logic.py

│   ├── monthly_rotation_strategy.py

│   ├── kabucom_broker.py

│   └── sim_broker.py

└── tests/

    ├── test_analyze_backtest_trade_log.py

    ├── test_backtest.py

    ├── test_daytrade_candidate_engine.py

    ├── test_daytrade_production_replay.py

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

  shared scan 候補と live 側の entry 判定は `data/.../daytrade_decisions.csv` に記録されます。operational review行にはRSS取得状態、news本文/hash、AI provider/model、prompt/raw responseと各hashを同じ `decision_snapshot_id` で保存します。

  liveのlong候補はnews/AI審査後、sizing直前に候補全体のBoardを再取得します。取得batchは5秒以内、買い指値に使う最良売気配の価格時刻は完了時刻から30秒以内、受信時刻はbatch内、現在値と最良売気配は正値であることを必須とします。1銘柄でも欠損・古い・時刻不整合・request不一致なら全候補を停止し、古い現在値で数量を決めたり下位候補へ落ちたりしません。freshな最良売気配をsizing価格へ使い、全時刻・価格・数量・拒否理由をsnapshot-linked decisionへ保存します。

  現行 `KABUCOM_TEST / KABUCOM_LIVE` の候補判断は、前日確定値だけで作った49銘柄の観測 universe と市場指数 `1321` を合わせた最大50銘柄に限定します。9:30以降の最初の板 batchから当日寄付を固定し、明示したobservation policy、batch開始・終了時刻と30秒上限、各銘柄の `PreviousCloseTime` をschema v4 snapshot identityへ保存します。schema v4はverified broker clockに加え、将来の巡回196接続用に、`1321` Boardと4×49の登録・Board・解除、時系列、最終registry復元証拠もstrict replayできますが、actual TEST未検証のため現行loopでは巡回を有効化していません。`core/daytrade_candidate_engine.py` と同じ selector を通した判断は `data/.../daytrade_production_snapshots.jsonl` へ1日1件保存し、現在値・bid/ask・日中 high/low・volume はexecution evidenceとしてsignal入力から分離します。

  snapshot収集は live write gate が閉じていても継続しますが、注文は引き続き readiness / financial-write gate で停止します。板の一部欠落、別日timestamp、batch時間幅超過、`PreviousCloseTime != feature_asof`、前日cacheと板の前日終値不一致、registry同期失敗、snapshot replay不一致に加え、RSS取得失敗、AI未設定・timeout・不正応答も新規entryをfail closedにします。一度見送った上位候補を後刻の価格で再順位付けしたり、次順位候補へ差し替えたりもしません。

  保有中の板スナップショットは `data/.../intraday_snapshots.csv` に記録され、entry context、含み損益、stop までの距離、高値からの剥落、安値からの戻りも追えます。

  live 側の intraday stop / target / primary failed-runup exit と、`14:30` 以降の force flatten は shared helper で判定され、`data/.../daytrade_exit_log.csv` に quote ベースの exit、target までの距離、simulation では slippage 込み modeled exit、live では実約定ベースの exit が記録されます。live entry 後は保護逆指値を張り、`protective_stop_order_id` を portfolio に残して通常の stuck-order 自動取消から除外します。部分約定も `filled_shares` / `remaining_shares` 付きで event として残ります。
  scan のたびに shared strategy が生成した候補、sizing 対象、board lot 不成立、simulation / live の entry を `data/.../daytrade_decisions.csv` へ記録します。各行には `TRADE_MODE` と `is_simulation` を残すため、`KABUCOM_TEST` や simulation の記録を本番由来の clean holdout と混同しません。

- `backtest.py`

  共有戦略ロジックを使って仮想約定を行うバックテスト実行レイヤーです。

  daytrade 候補は `core/daytrade_candidate_engine.py` を通し、入力を当日寄付と前日までに確定した特徴量へ限定します。当日 `close / high / low` は候補生成後の約定シミュレーションだけで使います。

- `jp_backtest.py`

  現行デイトレード戦略の確認用バックテストです。

  shared strategy を同じ形で replay するのが目的で、実運用の板・注文拒否・部分約定までを再現するものではありません。

  表示される損益・勝率は税引き後ベースです。

  `kabuステーションAPI` 経由のデイトレ信用は手数料無料なので、`explicit_trade_cost` は 0 円のままです。

  `slippage` と税引き後計算は `scripts/jp_refresh_validate.py` と同じ cost model を使います。

  さらに、発注数量は日次出来高比の `liquidity_limit` で上限を掛けて、薄い銘柄での過大約定を抑えています。

  改善判断では `python jp_backtest.py --holdout-months 6` を基準に、直近 6 ヶ月の `train / holdout` を分けて確認します。

  `--production-observation-replay` を付けると、全Primeを参照する標準baselineとは別に、本番と同じ前日固定49銘柄だけを候補母集団にした制約付き日足replayを実行します。このモードの49銘柄数は探索パラメータではなく、本番APIの登録上限から固定されています。

  `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1 --production-observation-replay`

  `--rotating-discovery-replay` を付けると、`1321` を保護したまま49銘柄×4バッチで観測する固定196銘柄policyを日ごとに再生します。`--production-observation-replay` とは同時指定できません。

  `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1 --rotating-discovery-replay`

  train取引差分は `python analyze_backtest_trade_log.py --holdout-months 6 --top-n 20 --rotating-discovery-replay --output-trades-csv tmp\rotating_discovery_train_trades.csv` で出力できます。CSVへholdoutは書き出しません。

  `--standalone-latest-months 1` を付けると、最新直近1ヶ月を `100万円` 初期資金の standalone replay でも併記できます。

  `--refresh-cache` を付けると、キャッシュ更新後の最新日を基準に holdout を切ります。

  これは日足OHLCによる `reference-only` 検証です。本番相当の検証結果として扱わず、実観測結果は次の `jp_production_replay.py` で確認します。

- `jp_production_replay.py`

  `daytrade_production_snapshots.jsonl` を共有candidate engineへ再投入し、candidate / selected digestを完全照合します。さらに `decision_snapshot_id` で非simulation decision log、news/AI operational evidence、entry / protective stop / cancel / exit のorder journal、残数量0のactual exitを連結します。entry / exitは全追従注文IDのACCEPTEDとaggregate約定のqty・加重平均価格・残数・ExecutionIDをactual rowへ照合し、保護逆指値はorders API応答の正規化実値まで再計算します。news、prompt、raw responseのhash不一致やselected decisionに必要なlifecycle欠落はfail closedにし、`KABUCOM_TEST` のlinked exitはexecution replayへ含めますが、`eligible_for_decision_clean_holdout` には含めません。

  snapshot不足、parity不一致、またはselected decisionのlinked lifecycle不足なら非zeroで終了します。lifecycle不足は `STATUS: LIFECYCLE_INCOMPLETE` と理由別件数で表示します。`--allow-incomplete-lifecycle` はsignal-only診断用で、本番同等完了の証拠には使いません。

```bash
python jp_production_replay.py --trade-mode KABUCOM_TEST --min-snapshots 1

python jp_production_replay.py --trade-mode KABUCOM_LIVE --min-snapshots 1
```

- `scripts/jp_refresh_validate.py`

  最新キャッシュの更新、`jp_backtest.py` と同じ universe / cost model での再検証、直近1ヶ月 standalone の日次損益表をまとめて出す一括ツールです。

  `--validate-only` を付けると、更新は飛ばして既存キャッシュだけを検証できます。

  この更新フローの skill 本体は `.codex/skills/jp-refresh-latest/` にあります。

  このリポジトリで「日付を更新して」「最新日まで更新して」と言われたら、まずこの skill とこのツールを使います。

- `scripts/update_jpx_trading_calendar.py`

  [JPX公式の営業時間・休業日一覧](https://www.jpx.co.jp/corporate/about-jpx/calendar/index.html)から年別休業日表を取得し、指定年の全暦日を `trading_dates / closed_dates` へ明示分類して `contracts/jpx_trading_calendar.json` を原子的に更新します。

  要求年の表欠落、年ごとの休業日が15件未満、cross-year日付、空レスポンスは成功扱いにしません。通常の更新コマンドは次です。

```bash
python -B scripts/update_jpx_trading_calendar.py --start-year 2026 --end-year 2027
```

- `analyze_backtest_trade_log.py`

  `jp_backtest.py` と同じ shared strategy replay を 1 回だけ行い、`train` 側の miss week、worst day、`primary` stop cluster、`primary close_exit` の fade cluster を再集計する分析スクリプトです。

  `primary` の failed-runup fade cluster も独立に追跡できます。

  miss week については、「worst trade をどれだけ浅くすれば週次 +1% が反転するか」「loss の何割を単一 trade が占めているか」も定量化できます。

  `backtest.py` の `trade_log` に含まれる `exit_reason`、stop/target 距離、equity 比 notional、日中高安から見た run-up / fade も確認できます。

- `jp_walkforward.py`

  現行 shared strategy を1回だけ replay し、その結果を rolling な `train / holdout` 窓へ切り出して疑似 forward を確認します。

  用途は「各 window の train で自動再最適化すること」ではなく、「現行ロジックの頑健性確認」です。

  税・明示コストは標準 `jp_backtest.py` と同じ共有設定を使います。

- `jp_optimizer.py`

  `train` 期間だけで候補を順位付けし、上位候補だけを trailing holdout で再確認する optimizer です。

  既定では `--min-train-months 24` を要求し、短い recent slice への当て込みを避けます。

  train ranking / holdout reviewとも、税・明示コストは標準 `jp_backtest.py` と同じ共有設定を使います。

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

使い分けは、証拠レベルを混同しないよう次の順にします。

1. `pytest` / `SIM` / `jp_backtest.py` は、shared logic の回帰と train 仮説の `reference-only` 確認に使う
2. `KABUCOM_TEST` の actual production snapshot で signal parity、注文拒否、部分約定、取消、保護逆指値などの schema / lifecycle を確認する。本番収益の根拠にはしない
3. write gate を閉じた `KABUCOM_LIVE` でも point-in-time decision snapshot を蓄積し、同一 code / config で exact replay する
4. 本番収益は、非simulation `KABUCOM_LIVE` snapshotへ連結した actual exit と口座コスト証跡でのみ評価する

### 本番との差分と証拠レベル

| 項目 | 日足OHLC / SIM | production snapshot / KABUCOM_TEST / LIVE | 現在の扱い |
| --- | --- | --- | --- |
| 候補母集団 | 標準は現在のPrime全銘柄。`--production-observation-replay` は前日固定49銘柄、`--rotating-discovery-replay` は前日固定196銘柄へ制限 | 現行は前日固定49銘柄 + `1321`。196巡回はactual TEST未検証のため未有効 | 49銘柄trainは赤字。196銘柄trainは改善したが全Prime未満で、9:30 Boardと実約定を再現しないreference-only |
| 判断時刻 | 公式寄付でentryしたものとして一日全体を評価 | 9:30以降、最初に取得できた逐次Board batchで判断 | 9:00〜取得時刻の値動きは本番entry前。過去日足では再現不能 |
| 基準時刻 | ローカル日付で日足を評価 | 非simulationは認証済みwallet応答のHTTP `Date` headerと受信時刻を保存し、30秒以内のverified broker clockだけで日次・週次・月次stateとsnapshotを更新 | ローカルfallbackは監視・安全決済専用。token / HTTP / header / timezone / drift不正では新規entryとsnapshotをfail closed。actual TEST/LIVEでの時刻証拠は未確認 |
| Board / 鮮度 | 板、特別気配、取得失敗なし | 観測snapshotに加え、news/AI審査後の候補全体を発注直前に再取得。5秒batch、最良売気配の価格時刻30秒、受信時刻のbatch内包含を保存 | 観測側の欠損・重複・未要求銘柄・cross-day・registry汚染等に加え、execution quoteの一部欠損・stale・時刻/価格不整合も候補全体でfail closed化済み。actual TEST/LIVE snapshotでの再確認は未完了 |
| entry / 流動性 | 固定slippage、前日turnover比上限、全量約定 | freshな最良売気配でsizingし、leverage・wallet余力・流動性・stop risk・notionalを維持する最高entry価格を固定。その後の追従・強制注文でもBoardを再取得し、上限超過なら送信しない | 古いcurrent priceでの過大数量、信用余力0円から理論余力へのfallback、追従中のrisk超過、失敗時の下位候補差替えを停止。過去日足の全量約定差は残る |
| exit | 日足High/Lowでstop優先、残りは日足Close | post-entry quote、orders API実応答で注文ID・銘柄・state・qty・trigger・side・取引所・信用区分・返済HoldIDまで確認した保護逆指値、取消確認、14:30 flatten、aggregate実約定 | stopのsendorder受理やbooleanだけではarmed証拠にせず、確認実値、実約定株数、entry risk距離、exitのqty・加重平均価格・残数・ExecutionIDが一致する場合だけstrict lifecycleを通す。actual TEST/LIVE再確認は未完了 |
| position state | 1日内で完結 | broker positionを毎loop再取得 | ExecutionID一致時にstrategy / stop / snapshot metadataを保持するよう修正済み |
| selector / sizing | model cashの複利 | TESTはlocal台帳、LIVEはwallet信用余力を0円も含めてcap。sizing時の資産・理論/実余力・stop・turnover・株数・価格上限を保存 | snapshotは当時のselector contextとentry risk envelopeを固定するが、資産軌跡そのものは同一ではない |
| 税・費用 | 利益取引ごとに税を引く保守的近似 | 注文明細の `Commission / CommissionTax` と建玉の `Expenses / Commission / CommissionTax` をactual exitへ連結 | 完全決済・全執行費用・算術整合で `observed_execution_net_pnl` を確定する。正の損益は既存 `TAX_RATE` reserve後、損失は全額を日中risk capitalへ反映し、証拠が完全な前日分だけを翌日の基準資本へ繰り越す。部分決済・費用欠損・旧undated損益は推定せず、日付が変わっても新規entryをfail closedにする。`CommissionTax` と譲渡益税を混同せず、譲渡益税証跡もある場合だけ最終 `observed_net_pnl` を確定する |
| 外部news / AI veto | 原則再現しない | shared selector後に外部newsとAIでoperational veto | RSS取得状態、news本文/hash、provider/model、prompt/raw responseと各hashをsnapshot-linked decisionへ保存し、欠損・改ざん・AI不明状態をfail closed化済み。actual TEST/LIVE snapshotでの再確認は未完了 |
| replay範囲 | signalと損益を同時に近似 | candidate / selected digest、news/AI、発注直前quote、entry risk envelope、注文qty/価格、entry / exit aggregate約定qty・加重平均価格・残数・ExecutionID、orders確認実値、全量決済、価格×数量gross PnLをsnapshot単位で監査 | quote / risk / entry・exit execution / order / stop / exit証跡の欠落、wallet cap・価格・株数・上限・stop距離・gross算術の不一致や改ざんをfail closed化済み。actual snapshot 0件のため本番同等性は未検証 |
| 履歴証拠 | 過去へ遡及可能だがreference-only | 実観測snapshotは導入後にしか蓄積できない | snapshot / linked actual exitが不足する間は「本番同等未検証」「本番収益性未検証」 |

解消済みのコード差分があっても、actual snapshotとlinked lifecycleで再確認されるまでは本番同等の完了証拠にはしません。標準実行の `STATUS: PARITY_OK` はselected decisionがあるsnapshotについてlinked lifecycleも完了した場合に限りますが、収益性の証明には十分ではありません。

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

- 現在の `6m holdout` `2026-01-13` から `2026-07-14` は `contaminated holdout` として扱う

- 次の `clean holdout` は今回のロジック凍結後となる `2026-07-14` 以降の未観測営業日から積み上げる

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

backtest candidate log 分析:

```bash

python analyze_daytrade_candidate_log.py --holdout-months 6 --top-n 20

```
intraday ログ分析:

```bash

python analyze_intraday_logs.py

python analyze_intraday_logs.py --output-csv reports/intraday_trade_paths.csv --top-n 20

python analyze_intraday_logs.py --exits-file data/kabucom_test/daytrade_exit_log.csv --top-n 20

```

## 本番同等replayの開始条件

日足backtestではなく本番同等として扱うには、次をすべて満たす必要があります。

1. J-Quants cacheのfeature日がtrade dateより前であり、同日partial rowを含まない
2. snapshotにobservation policyを明示し、現行固定49では49銘柄と `1321` のregistry同期、巡回196を将来有効化する場合は事前固定196銘柄と保護対象 `1321` の初期同期が成功している
3. 固定49では9:30以降の最初の板batchが全50銘柄を返す。巡回196では `1321` Boardと4回の49銘柄batchが全件を重複なく返し、各登録・解除成功、時系列非重複、全体30秒以内、最終registryが `1321` だけで、OpeningPriceTimeとtrade dateが一致する
4. 板のPreviousCloseとcacheの前日終値がJPX tick単位で一致し、PreviousCloseTimeがcacheのfeature_asofと一致する
5. candidate入力には当日寄付だけを使い、現在値・high/low・volume・bid/askはexecution evidenceへ分離する
6. 保存snapshotを同じcode/configでreplayし、candidate digestとselected digestが完全一致する
7. RSS取得状態、news本文/hash、AI provider/model、prompt/raw responseと各hash、operational veto、注文拒否、zero / partial fill、保護逆指値、取消、exit、残数量0を同じ `decision_snapshot_id` で接続できる
8. 収益評価は非simulationの実約定exitだけで行い、欠損を日足OHLCや有利な価格で補完しない

最初に `KABUCOM_TEST` でschema/parity/order journalを確認します。その後もlive write gateを閉じたまま `KABUCOM_LIVE` のdecision snapshotを蓄積できます。今回のロジック凍結後となる2026-07-14以降の未観測営業日をdecision clean holdoutの起点とし、実注文を再開した日以降だけをexecution clean holdoutとして別集計します。

```powershell
$env:TRADE_MODE = "KABUCOM_TEST"
python auto_trade.py

$env:TRADE_MODE = "KABUCOM_LIVE"
$env:ENABLE_LIVE_ORDER = "false"
python auto_trade.py
```

```bash
python jp_production_replay.py --trade-mode KABUCOM_TEST --min-snapshots 1

python jp_production_replay.py --trade-mode KABUCOM_LIVE --min-snapshots 1
```

標準実行ではselected decisionのlinked lifecycle、またはactual exitの費用証跡が欠けると `STATUS: LIFECYCLE_INCOMPLETE` で失敗します。`OBSERVED_GROSS_PNL` は費用前、`OBSERVED_EXECUTION_NET_PNL` は手数料・手数料税・信用費用控除後です。`CommissionTax` は譲渡益税ではないため、譲渡益税証跡も揃う場合だけ最終 `OBSERVED_NET_PNL` を表示します。部分決済を単純按分したり欠損を0円補完したりしません。LIVE strict replayは最終net証跡も要求しますが、TESTはschema / lifecycle / execution-cost検証に限定します。

AIが候補、sizing、entry / exit、注文、risk、時刻、市場データ処理を変更した場合、このproduction replayとlinked lifecycle確認を完了条件にします。actual snapshotがまだ無ければ未検証と報告し、日足OHLCやSIMを本番同等の代替証拠にはしません。

## テスト

現在のテストは主に次を確認します。

- `tests/test_logic.py`

  - shared strategy の判定関数

  - lot sizingが前日turnoverの共有 `liquidity_limit` を発注株数上限として適用すること

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

  - Wednesday high-breadth / stretched-open `primary` の no-trade guard

  - Tuesday low-open / mid-breadth / hot-market `primary` の no-trade guard

  - Tuesday stretched-open / weak-RSI `primary` の no-trade guard

  - Wednesday mid-breadth / hot-market / low-prev-return `primary` の no-trade guard

  - Monday mid-breadth / moderate-extension `primary` の no-trade guard

  - breadth `< 0.60` / `market_ratio 1.00-1.05` / gap `>= 2.0%` / RS `<= 50` `primary` の no-trade guard

  - 火曜 mid-high breadth / positive-gap / neutral-trend `primary` の追加 equity cap

  - 火曜 mid-high breadth / 非プラスギャップ `primary` の equity 建玉上限

  - 火曜 mid-high breadth / high-RS / trend `1-3 ATR` / flat-to-mild-gap の crowded `primary` 防御

  - 火曜 high breadth / 中位ギャップ `primary` の equity 建玉上限

  - 水曜 hot gap / below-SMA `primary` の追加 equity cap

  - 木曜 breadth `0.55-0.70` / 小幅ギャップ continuation `primary` の tighter equity cap

  - 木曜 mid breadth / 小幅ギャップ / continuation `primary` の追加 equity cap

  - high market-ratio / mid-breadth / mid-score / moderate-prev-return / positive-gap `primary` の quarter-size cap

  - 木曜 mid-breadth / hot-market / stretched-open の no-trade guard

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

  - `strong_oversold` の過去のpure-win入力でも、notional / equity notional / risk budget / size multiplierをsetup共通の通常値より増幅しないこと

  - `fallback` のギャップ上限と低 breadth フラットギャップ防御

  - `fallback` の low breadth / weak score equity cap

  - 低 breadth / 前日プラス / near-SMA `fallback` の equity cap

  - `fallback` のscore境界とsmall-account board-lot判定を維持しつつ、notional resolverがsetup共通上限を超えないこと

  - `fallback` の equity 建玉上限

  - 高 breadth / 前日上昇 / SMA から遠い `fallback` の equity 建玉上限

  - `catchup_rs` の Monday / Friday 高 breadth hot-market selector フィルタ

  - `catchup_rs` の Monday mid-breadth / stretched-open pocket selector フィルタ

  - `catchup_rs` の Tuesday low-breadth / weak-market / high-score pocket selector フィルタ

  - `catchup_rs` の Tuesday low-breadth / moderate-market pocket selector フィルタ

  - `fallback` の hot-market / high-breadth selector フィルタ

  - 火曜 mid-breadth continuation / 水曜 high breadth `fallback` の曜日別 equity cap

  - 水曜 high breadth / gap `> 0.5%` `fallback` の追加 equity cap

  - `inverse_pullback` の high-confidence probe leverage / executable-share 回帰

  - `catchup_rs` の setup 別 risk budget

  - `100万円` 近辺の small-account で、`catchup` の board-lot 最低実行単位と cheap `primary` substitute skip が shared sizing に反映されること

  - `100万円` 近辺の small-account で、hot / mid-score `catchup_rs` の board-lot を無理に建てないこと

  - `100万円` 近辺の small-account で、fallback が board-lot を建てられないときだけ executable な `catchup_rs` / `catchup_gapdown` に限定差し替えすること

  - 通常 exposure では100株に届かない `catchup_gapdown` を board-lot rescue 目的で size-up しないこと

  - `catchup_rs` / `catchup_gapdown` の差し替えが、score 優位が足りない場合は fallback を維持すること

  - `catchup_rs` の Monday weak-market / moderate-gap pocket を selector から除外すること

  - `catchup_rs` の Friday low breadth / modest market pocket（`market_ratio 1.00-1.10` / `breadth < 0.55`）を selector から除外すること

  - `catchup_gapdown` の Wednesday negative-trend pocket を selector から除外すること

  - `fallback` の Tuesday / Friday 弱市場（`market_ratio 1.00-1.10` / `breadth < 0.55` / positive gap）は equity notional を `0.50` に抑えること

  - `primary` の hot-market no-trade pocket を board-lot 回復で壊さないこと

  - Tuesday breadth `0.65-0.75` / `market_ratio 1.15-1.30` / score `<= 8.5` / RS `<= 50` / `open_vs_sma_atr <= 4.0` `primary` の quarter-size equity cap

  - `100万円` 近辺の木曜low-breadth `primary` probeも、通常exposure上限内でのみ選択し、notional floorで増幅しないこと

  - `100万円` 近辺の月曜low-breadth / high-market-ratio `catchup_rs` probeも、setup共通notional / equity / risk上限を超えて拡大しないこと

  - weekly profit lock / Thursday selected leverageの判定でも、狭いfallback帯を通常exposureより上へboard-lot rescueしないこと

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

  - low-breadth / strong-continuation pure-win `catchup_rs` の selected leverage / equity notional / risk budget 回帰

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

  - 発注直前価格で決めたboard lotについて、leverage・買付余力・流動性・stop risk・notionalを同時に守る最高entry価格を計算し、0円余力・欠損流動性をfail closedにすること

  - setup共通の通常 exposure 上限が局所 size-up を無効化し、既存の縮小・no-tradeと候補log identityを維持すること

  - primary scoreを通常上限内の連続的な50%-100% de-riskへ変換すること

  - `primary` の failed-runup exit が、建値を上回った後の建値割れだけで発動し、建値ちょうどの初期値では発動しないこと

  - 水曜の live-compatible `evaluate_daytrade_setup` が sizing 専用の未定義 context を参照せず評価できること

  - open snapshot の `feature_asof < trade_date` と `open_asof == trade_date` を強制し、同日確定値や前日openの混入を拒否すること

- `tests/test_backtest.py`

  - `backtest.py` から shared logic を参照したときの売買フロー

  - 日中決済、stop/target、JPX tick の buy/sell 方向丸め、inverse 系を含むバックテスト挙動

  - open エントリーで同日 breadth を見ない no-lookahead 回帰

  - selector / leverage / sizing候補の辞書へ当日 `close / high / low` を渡さず、execution simulationだけが別mapから参照すること

  - `primary` の intraday failed-runup exit を trade_log の `exit_reason` として記録すること

  - fixed slippage 後に手取り建値となる failed-runup trigger を backtest / live 共通で使うこと

  - 翌営業日がなくてもcache最終日のデイトレを評価すること

  - `trade_log` の `exit_reason`、stop/target、OHLC fade 監査列

  - `candidate_log` の日次 summary、scan / setup counters、selected / not_selected / opened / blocked 診断列

  - 火曜 low breadth `catchup_rs` の probe 約定フロー

  - candidate adapter が `catchup_gapdown` を受け取った場合も backtest 側で候補化・約定でき、shared setup 有効化時の実装差分を作らないこと

  - small-account で `raw_shares < 100` の fallback board-lot 候補が shared resolve へ到達すること

  - low breadth bull ETF rebound の約定フロー

  - panic breadth での low-turnover `inverse` 約定フロー

  - `inverse_pullback` high-confidence probe の約定フローと size-up 回帰

  - 非金曜での `strong_oversold` / `inverse_pullback` / `inverse_rebreak` 約定フロー

  - 日ごとのproduction observation universeを候補母集団の縮小制約として適用し、欠損日はno-trade、標準universe外への拡張は拒否すること

  - 月次ローテーションの既存参照実装

- `tests/test_daytrade_observation_universe.py`

  - 本番とバックテストで共有する前日固定49銘柄の予約ETF、Prime、除外、流動性順位、同日データ非参照、配列整合性のfail closed


  - 固定196銘柄の1日共有selector、3シナリオ感度順位、同日OHLC非参照、as-of逆転・重複ticker・配列不整合・market証拠欠落のfail closed

- `tests/test_daytrade_opening_discovery.py`

  - 保護登録した `1321` Boardの先行取得、49銘柄×4バッチの登録・Board・解除、最終registry復元、30秒上限、証拠serialization、例外・部分失敗・要求不一致のfail closed
- `tests/test_analyze_backtest_trade_log.py`

  - `analyze_backtest_trade_log.py` の exit bucket 分類

  - `train` 週次集計で部分週を除外すること

  - `train` miss-week 集計で warmup 前の部分週を除外すること

  - miss-week の flip sensitivity と loss dominance 集計

  - `primary close_exit` fade テーブルと cluster 集計

- `tests/test_jp_backtest.py`

  - `jp_backtest.py` の holdout 開始日の切り方

  - frozen holdout 開始日を最新日に合わせて後退させず、cache が境界後から始まる場合は全件 holdout として fail closed にすること

  - candidate / trade 診断CSVへ holdout 行を書き出さないこと

  - `train / holdout` 分割時に、部分週を週次 +1% 集計へ混ぜないこと

  - latest standalone window 切り出しで、直前営業日の context だけ残しつつ評価期間を固定すること

  - `jp_backtest.py` と `jp_refresh_validate.py` の universe / cost model が揃っていること

  - production observation replayが固定の日次制約をbacktestへ渡し、予約ETFを含む観測対象だけを基礎universeにすること

  - rotating discovery replayの固定日次制約と、2つのobservation replay modeを同時指定できないこと

  - `PROFIT FACTOR` の非有限値を `N/A` 表示に正規化すること

  - full calendar month だけで月次 `+20%` 達成本数を集計すること

  - warmup前の取引不能日・月を週次、月次、稼働率の評価分母へ混ぜないこと

- `tests/test_jp_jquants_fetcher_v2.py`

  - `jp_jquants_fetcher_v2.py` の増分更新開始日の決め方

  - overlap を含む増分取得結果が checkpoint へ正しくマージされること

  - 31日以内の増分更新で、日付指定の全銘柄一括取得を使い ticker ごとに一度だけ checkpoint へ統合すること

  - consolidated cache から checkpoint を seed して履歴を保全できること

  - checkpoint 上書き時に history を短くしないことと、短い checkpoint を cache から修復できること

  - refresh 前の cache audit を自動で走らせること、バックアップ一覧、最新スナップショット復元

  - legacy な checkpoint 名や master `429` 時の fallback universe 解決

  - full refresh が途中停止後も未完了銘柄だけを再開できること

  - 非200レスポンス時に失敗理由を具体的に返すこと

  - 契約開始日エラーを `RANGE_ERROR` として認識できること

- `tests/test_jp_walkforward.py`

  - `jp_walkforward.py` の rolling window 切り方

  - frozen holdout 境界以降を rolling replay へ戻さないこと

  - 標準 backtest と同じ prepared production universe を使うこと

  - holdout 集計が window 単位で正しくロールアップされること

  - holdout PF 集計が非有限値に汚染されないこと

- `tests/test_jp_optimizer.py`

  - `jp_optimizer.py` の `train / holdout` 分割日付

  - optimizer 用の train slice が時系列配列だけを正しく切り出すこと

  - 短すぎる `train` を拒否すること

  - rolling train window の切り方

  - 一貫性の高い候補が fragility の高い候補より上に来る採点

- `tests/test_ai_filter.py`

  - RSSのHTTP/parse失敗を「ニュースなし」と混同せず、entry停止用のerror evidenceにすること

  - AI provider未設定、timeout、例外、不正応答を自動承認せずfail closedにすること

  - 明示的な `NO / YES` だけを承認 / vetoへ対応させ、news・prompt・raw responseのhashを保存すること

- `tests/test_auto_trade.py`

  - `auto_trade.py` の軽量な回帰確認

  - インスタンスロックのメタデータ保存と、malformed LIVE lock を削除せず停止すること

  - LIVE 口座 snapshot が `configured_risk_capital` や `realized_pnl_today` を 0 で潰さないこと

  - LIVE realized PnLをJST取引日ごとに区切り、完全なexecution-netだけを税reserve後のrisk capitalへ反映し、完全な前日分だけを翌日へ累積すること

  - 部分決済・費用欠損・取引日不明のlegacy PnLではgrossを補完せず、日付変更後も新規entryをfail closedにすること

  - スナップショット計算

  - simulation の通常 / inverse entry が cash・setup 別 buying power・managed position を一体で更新すること

  - 前日確定値だけの観測49銘柄、1321別枠、registryのunregister-before-registerを確認すること

  - 巡回196のlive準備adapterが前日履歴を1日共有selectorへ渡し、当日行や独自順位判断を持たないこと。collector-to-snapshot adapterがrequested codes、`1321`、Board、失敗理由、全体時刻、schema v4 evidenceを一意に転送すること

  - write gateが閉じていてもproduction snapshot収集を続け、simulationではclean observation扱いしないこと

  - board/cache前日終値不一致、cross-day opening timestamp、batch欠損・30秒超過、`PreviousCloseTime != feature_asof` をfail closedにすること

  - scan 候補、news/AI operational evidence、sizing 対象、board lot 不成立、simulation / live entry の判断ログと `TRADE_MODE` 分離

  - news/AI審査後の発注直前Boardを候補全体で再取得し、5秒batch・30秒価格鮮度・最良売気配を満たす場合だけsizingへ進み、一部障害では全候補を停止すること

  - LIVE信用余力0円を理論余力で上書きせず、entry risk envelopeと価格上限をdecision logへ保存すること

  - broker clock evidenceのsource / reason / timezone / driftを厳格照合し、ローカルfallbackでは新規entryとstate更新を停止すること。verified JSTの月替わりだけで月次 state / 月初資産をロールし、同月・不正資産では既存anchorを保つこと

  - 保有中ポジションの intraday snapshot 行生成と entry context 付与

  - live entry 後の protective stop arming と portfolio 反映

  - daytrade exit decision 行の modeled exit / fade 指標と、live 約定時の二重スリッページ防止

  - live での intraday failed-runup break-even exit と post-entry high/low 追跡

  - post-entry high/low が legacy `highest_price` / `lowest_price` に引きずられず、fresh な current quote から更新されること。stale quote では更新しないこと

  - shared intraday stop / target と `14:30` force flatten の live exit フロー

  - 9:30以降のlive entryではentry前の公式寄値をexit pathへ混ぜず、entry fillをpost-entry pathの起点にすること

  - live 部分約定時に shares を減らして保有継続し、partial fill event を exit log へ残すこと

  - actual exitは完全決済かつentry / position / exitの全執行費用が揃う場合だけexecution-netを確定し、譲渡益税証跡が無ければ最終netを推測しないこと

  - 保護逆指値のarm失敗を未解決entryとして後続entry停止へ反映すること

- `tests/test_daytrade_candidate_engine.py`

  - 候補生成入力が当日 `close / high / low / volume` を公開せず、当日寄付と前日確定特徴だけを受け取ること

  - 1日分の NumPy view がコピーを作らず、universe と各特徴量の shape 不整合を拒否すること

  - 共通候補エンジンが point-in-time market context を使って候補グループと診断値を返すこと

- `tests/test_daytrade_production_replay.py`

  - 保存したsignal入力からcandidate / selected digestが完全一致すること

  - current price、bid/ask、session high/low、volumeを変えてもsignal identityと選択が変わらないこと

  - feature_asof逆転、board failure、batch時刻逆転・30秒超過・capture先行、`PreviousCloseTime` 不一致、snapshot改ざんをfail closedにすること

  - schema v4の巡回196証拠が `1321 + 4×49` の全観測、登録・解除、時系列、最終registryを要求し、欠損・重複・未要求銘柄混入・registry汚染・nested型破損・naive / mixed timezoneを例外終了させずfail closedにすること

  - schema v4がverified broker clockのsource / reason、server / received / fallback時刻、30秒drift算術、trade date整合を要求し、欠落・unverified・stale・改ざんをfail closedにすること

  - JSONL round-trip、1日最初のsnapshot固定、actual exitのsnapshot ID連結、最低件数不足の非zero終了を確認すること

  - linked news/AI evidence / decision / entry fill / protective stop / exit fill / 残数量0の欠損やevidence hash改ざんを `LIFECYCLE_INCOMPLETE` にすること

  - 発注直前quoteのJST時刻、batch span、price age、受信時刻、現在値、最良売気配、pass/block statusを厳格照合し、証跡欠落や改ざんを `LIFECYCLE_INCOMPLETE` にすること

  - entry risk envelopeを共有ロジックで再計算し、fresh最良売気配、wallet cap、初回/追従注文qty・価格、entry ExecutionID、実約定株数・平均価格、orders API確認済みstop qty・trigger、actual exitの注文/ExecutionID・全量決済・価格×数量gross PnLとの不一致や改ざんを `LIFECYCLE_INCOMPLETE` にすること

  - actual cost schema、5執行費用項目、gross / execution-net、譲渡益税 / final-netの各算術不一致をfail closedにすること

  - `KABUCOM_TEST` のlinked actual exitをexecution replayへ含めつつ、LIVE clean holdout資格とは分離すること

  - live での unmanaged position を signal flatten / force flatten から除外すること

  - exact `execution_id` でのみ保護逆指値を紐づけること

  - 複数 `execution_id` 既知時は close route 不明の fallback を止めること

  - `confirmed` 欠損の stop result では protective stop を armed にしないこと

  - `HoldQty` 欠損の建玉を fail closed にして、保護逆指値 / 返済割当で数量を推測しないこと

  - `protective_stop_unconfirmed_order_id` が残る間は同一建玉への再 armed を止めること

  - signal/manual exit 前に linked protective stop を cancel し、未確定なら exit を止めること

  - signal/manual exit 後に partial remainder の protective stop を再 arm すること

  - kabuステーション起動確認より前にUnicode-safe loggingを初期化し、Windowsのリダイレクト出力でも絵文字による起動停止を防ぐこと

  - broker position消失をactual protective-stop fillへ照合し、全量・価格・ExecutionIDが揃う場合だけsnapshot-linked exit/PnLを確定すること

  - stop execution evidence欠損時はghost positionを保持してfail closedにし、既存exit order IDでは二重計上しないこと

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

  - `get_server_time()` が認証済みwallet応答のtimezone-aware HTTP `Date` headerだけをverified evidenceにし、token欠落・header欠落ではローカルfallbackを明示すること

  - `resolve_stock_order_action()` が long-only の fail-closed になり、short action を拒否すること

  - Board parserが `PreviousCloseTime` を欠落させず、production snapshotへ渡せること

  - `core/kabucom_broker.py` の POST 再送抑止

  - brokerテストのorder journalを一時ディレクトリへ隔離し、`data/kabucom_test/order_journal.jsonl` を変更しないこと

  - broker position再取得時にExecutionID一致のstrategy / stop / snapshot metadataを保持し、数量・価格・routeはbroker値を優先すること

  - `core/kabucom_broker.py` の GET 429 Retry-After 待機が上限付きで、shutdown 要求で中断できること

  - `KABUCOM_LIVE` の新規 entry を `ENABLE_LIVE_ORDER` / `APPROVED_CONFIG_HASH` なしで拒否すること

  - LIVE financial write gate が `KABUCOM_TEST` fixture provenance と structured CI attestation bundle (`.json` + `.sha256`) を要求し、`KABUCOM_LIVE` では operator ack を `KABUCOM_LIVE_OPERATOR_ACK_CONTEXT` に限定し、legacy boolean / explicit 引数を live gate に使えないこと

  - live 実行では GitHub Actions の workflow run / artifact の照合ができる場合、artifact digest と zip 内容まで検証すること

  - GitHub artifact verification の cache hit と TTL=0 再検証が想定どおり動くこと

  - GitHub artifact verification の失敗理由が token / response body を漏らさず generic のまま返ること

  - GitHub artifact verification が session fingerprint 変更で cache invalid になること

  - GitHub artifact verification が workflow_run_head_sha_mismatch / workflow_artifact_head_sha_mismatch / workflow_run_conclusion_failure / workflow_artifact_expired / timeout で fail closed になること

  - attestation bundle の digest sidecar が欠けるか mismatch なら live write を閉じること

  - `TRADE_MODE=KABUCOM_LIVE` で JPX calendar source の公式HTTPS URL、64桁SHA-256、`generated_at` / `coverage_start` / `coverage_end` / duplicate / overlap / stale を検証し、untrusted URL、coverage gap、fallbackでlive writeを閉じること

- `tests/test_update_jpx_trading_calendar.py`

  - JPX公式HTMLの年別休業日表から、coverage内の全暦日を重複なしで営業日・休場日へ分割すること

  - 要求年の欠落と不自然に短い休業日表をfail closedにすること


  - `LiveReadinessReport` の `execution_id_truth` が aggregate `execution_ids` / duplicate execution_id / `position_lot_key_needs_review=True` を blocked にし、truth lot だけを ready 扱いすること

  - `LiveReadinessReport` の `execution_id_truth` が duplicate execution_id も blocked にすること

  - `LiveReadinessReport` の `no_lookahead_audit` が risk review blocked 時に ready にならないこと

  - structured operator ACK が code_commit_sha / approved_config_hash / runtime_config_hash / repository_full_name / test_fixture_hash / live_write_attestation_hash mismatch で閉じること

  - risk review が `code_commit_sha` / `approval_manifest_hash` mismatch で blocked になること

  - `build_live_write_attestation.py` が actual KABUCOM_TEST capture では `APPROVED_CONFIG_HASH` を必須にし、手動 fixture では skip すること

  - `OrdersSuccess` 系の注文状態パーサーと `State=1..10` の解釈

  - `SeqNum` 順の detail 並べ替え、`RecType=8` のみを fill / ExecutionID に使うこと、`State=4` detail を reject 扱いにすること

  - `BoardQuote` への bid/ask 正規化と special / inverted quote の reject

  - 板 batch 取得が requested / observations / failures を分離し、transport / HTTP / malformed JSON / invalid quote / no token を成功扱いしないこと

  - `SubmissionResult` の accepted / rejected / unknown 分岐

  - response text が長すぎる場合の truncation と秘密値 redaction

  - `OrderSubmissionResult` / `ExecutionWaitResult` / `CancelResult` の typed result と、未解決・取消結果の情報落ち防止

  - `OrderSubmissionResult` の `bool` は accepted 判定であり、confirmed とは別であること

  - `ExecutionWaitResult` の `execution_status` / `entry_execution_status` / `exit_execution_status` を legacy dict へ残すこと

  - 約定明細の `TransactTime / Commission / CommissionTax` をfill単位で保持・追従注文単位で合算し、建玉の `Expenses / Commission / CommissionTax` を欠損と0円を区別して保持すること

  - 新規long追従注文がboard lotと正のentry価格上限を必須にし、通常追従・強制指値のどちらも上限超過時は注文送信前に終端拒否すること。entry / exitは全追従注文ID、各ACCEPTED、aggregate実約定qty・加重平均価格・残数・ExecutionIDをjournalへ残し、保護逆指値はsendorder受理後にorders API実応答の注文ID・銘柄・state・qty・trigger・side・routeを正規化保存すること

  - single HoldID fallback で生成した `ClosePositions` を orders API 確認へ渡すこと

  - confirmation成功・失敗時の `confirmation_details` がsecretを含まないbounded summaryで、欠損した実値を期待値で補完せず、strict replayがboolean単独やqty・trigger・order ID・route改ざんを拒否すること

  - stop journal が `ROUTE_RESOLVED` を含み、`ClosePositions` / `hold_ids` / route stage を残すこと

  - `live_approval_manifest` の hash が strategy定数・AI filterコード・AI model設定の変更で変わり、`generated_at` では変わらないこと

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

  - launcher待機失敗時に、APIポート未起動・APIパスワード未設定・token認証失敗を区別し、ポート未起動では公式APIシステム設定と再起動を案内すること

  - `get_server_time` が symbol endpoint ではなく `wallet/cash` の `Date` header を使うこと

  - request budget が orders / wallet / positions / registry / market_data / auth / other で分かれて記録されること

  - trade history の append-only 化

  - order journal の append-only 記録

  - broker単体テストのorder journalをテストごとの一時パスへ隔離し、既定のactual journalを生成・変更しないこと

- `tests/test_file_io.py`

  - JSONL 監査ログ helper が append-only に追記すること

  - CSVへ新しい証跡列を追加するとき、既存headerを原子的に拡張し、旧行と新規行の列ずれを防ぐこと

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

  - candidate engine、production observation universe、production replay、JPX calendar、API launcher、quote parser、order journalのコードとJPX calendar artifactを承認hashへ含めること

- `tests/test_order_journal.py`

  - order journal に `schema_version` / `event_id` / `sequence` / `process_id` を付けること

  - scoped journal contextがentry / protective stop / cancel / exitへ `decision_snapshot_id` を継承し、scope外へ漏らさないこと

  - JSONL append が連番で追記されること

  - journal replay が PLANNED / ACCEPTED / CANCEL_REQUESTED の未解決 intent を拾うこと

  - startup recovery が corrupt journal 行を final / middle で分けて扱い、accepted order missing at broker / broker position without journal / journal filled without position / unconfirmed stop replay も manual review にすること

  - startup recovery が protective stop の pending / orphan 状態も manual review にすること

  - protective stop のarm失敗もorphanとしてmanual reviewにすること

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

python -m pytest tests/test_ai_filter.py

python -m pytest tests/test_auto_trade.py

python -m pytest tests/test_daytrade_candidate_engine.py

python -m pytest tests/test_daytrade_production_replay.py

python -m pytest tests/test_kabucom_broker.py

python -m pytest tests/test_kabucom_contracts.py

python -m pytest tests/test_kabucom_contracts_test_fixture.py

python -m pytest tests/test_portfolio_state.py

python -m pytest tests/test_analyze_intraday_logs.py

python -m pytest tests/test_update_jpx_trading_calendar.py
python -m pytest tests/test_daytrade_observation_universe.py tests/test_daytrade_opening_discovery.py


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

- `python -B scripts/update_jpx_trading_calendar.py --start-year 2026 --end-year 2027` でJPX公式表から `contracts/jpx_trading_calendar.json` を更新する

- `source_url` は `https://www.jpx.co.jp/corporate/about-jpx/calendar/index.html` に固定し、任意URLやHTTPはLIVEで受け付けない

- `schema_version=1`、64桁SHA-256の `source_hash`、`generated_at`、`coverage_start`、`coverage_end`、`closed_dates`、`trading_dates`、`half_day_dates` を明記する

- `source` は legacy compatibility field としてのみ読み込み、`KABUCOM_LIVE` の require_source では `source_url` 欠落を invalid 扱いにする


- calendar artifactのファイルhashはlive承認manifestへ含め、更新後は旧承認hashを再利用しない
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

- 同等品質を維持できる読み取り監査、ログ集計、機械的照合は廉価モデル / サブエージェントへ委譲できます。採否、金融安全、holdout管理、差分レビュー、authoritative test / production replayは親担当が保持します。詳細は [AGENTS.md](AGENTS.md) を参照してください

Last updated: 2026-07-15
