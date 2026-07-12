# Strategy Experiment Log

このファイルは、日本株デイトレード戦略の探索ログである。

別セッションで同じ仮説をそのまま再試行しないため、主要な採用案と不採用案だけを残す。

## Current Baseline

- As of 2026-07-11

- Latest data: 2026-07-10

- 採用中ロジック:

  - 月曜の高 breadth / 高ギャップ / 前日過熱 `primary` を除外

  - 火曜の mid breadth で、失速しやすい `primary` を2種類だけ除外

  - 火曜の mid breadth で、弱い `primary` より少し強い `fallback` がある場合は差し替え

  - 火曜の中途半端な寄りギャップ `primary` を除外

  - 火曜の trend 距離が遠すぎる `primary` を除外

  - 火曜の高 breadth / 高スコア / 伸び切り open の `primary` は no-trade にする

  - 火曜 / 木曜の mid-breadth / hot-market / score `8-10` の `primary` は selected base leverage を `0.10` に制限する

  - 火曜の mid breadth / low-score / hot-market continuation は、small-gap pocket を 0.10 に寄せつつ、low market-ratio / positive-gap pocket は no-trade にする

  - 火曜の mid breadth / low-score / stretched-open / hot-market pocket は no-trade にする

  - `primary` の Tuesday high-breadth / hot-market / low-score / low-open pocket は no-trade にする

  - `primary` の Wednesday high-breadth / hot-market / low-score / mid-open pocket は selected base leverage を `0.10` に制限する

  - `primary` の Wednesday low-breadth / weak-market / small-gap pocket は no-trade にする

  - `primary` の Wednesday mid-breadth / weak-market / score `6-8` / small-gap pocket は no-trade にする

  - `primary` の Wednesday high-breadth / hot-market / low-score / broad probe pocket (`breadth 0.60-0.78` / `market_ratio >= 1.20` / `score <= 8.0` / `gap <= 1.0%`) は selected base leverage を `0.10` に制限する

  - `primary` の Wednesday high-open / low-score / tight-gap pocket (`market_ratio <= 1.08` / `score <= 6.7` / `gap <= 0.5%` / `open_vs_sma_atr >= 2.0`) は no-trade にする

  - `primary` の Wednesday hot-gap / mid-breadth / hot-market pocket (`breadth 0.55-0.65` / `market_ratio >= 1.17` / `gap >= 2.0%`) は no-trade にする

  - `primary` の Wednesday hot-gap / mid-breadth / hot-market exact pocket (`breadth 0.55-0.65` / `market_ratio 1.10-1.15` / `gap 0-1%` / `score 6.0-8.0` / `open_vs_sma_atr < 0`) は no-trade にする

  - 火曜の stretched-open / mid-breadth / hot-market / weak-RSI pocket は RSI2 `71.0` 未満を no-trade にする

  - 火曜の mid breadth で指数が +1%以上ギャップアップしている `primary` を除外

  - 水曜の小さすぎる寄りギャップ、中途半端な寄りギャップ、または trend 距離が遠すぎる `primary` を除外

  - 水曜の mid-breadth / hot-market / score `9-12` / breadth `0.60-0.80` / market_ratio `1.07-1.21` の `primary` は selected base leverage を `0.10` に制限する

  - 木曜の mid breadth で、失速しやすい `primary` を2種類だけ除外

  - 木曜の前日大幅上昇 `primary` を除外

  - 木曜の trend 距離が中途半端または失速しやすい `primary` を除外

  - 金曜の mid-high breadth / 弱 RS / 横ばいギャップ `primary` を除外

  - `primary` の hot-gap chase では、train で再現した low-score / broad warm / overheated low-breadth の損失クラスターを no-trade にする

  - `primary` の Wednesday hot-gap / below-SMA では、score `>= 7.5` の tail を no-trade にする

  - `primary` の Wednesday hot-gap / below-SMA では、low-breadth / weak-market / sub-six pocket (`breadth < 0.52` / `market_ratio 1.00-1.02` / `score < 6.0` / `gap >= 1.2%` / `open_vs_sma_atr < 0` / `prev_return >= 0`) を no-trade にする

  - `primary` の Wednesday hot-gap / below-SMA では、`open_vs_sma_atr <= -1.5` の深い tail を no-trade にする

  - `primary` の Wednesday 10-11 continuation は no-trade にする

  - `primary` の Wednesday mid-breadth / hot-market / high-score / low-open residual pocket (`breadth 0.60-0.71` / `market_ratio 1.15-1.20` / `score 7.5-10` / `open_vs_sma_atr < 1.0`) は no-trade にする

  - `primary` の Tuesday / Wednesday high-breadth / hot-market / mid-score / high-RSI pocket (`breadth 0.65-0.75` / `market_ratio 1.15-1.28` / `score 6.0-8.0` / `open_vs_sma_atr -0.5-2.0` / `prev_rsi2 >= 50.0`) は no-trade にする

  - `primary` の low-breadth / weak-market / score `6.0-8.0` / positive-gap pocket (`breadth 0.45-0.55` / `market_ratio 1.00-1.05` / `score 6.0-8.0` / `gap 0-2%` / `open_vs_sma_atr 1.0-3.0` / `prev_return <= 4.5%`) は no-trade にする

  - `primary` の Wednesday hot-market / low-score / negative-gap / low-open pocket (`breadth 0.60-0.75` / `market_ratio 1.10-1.15` / `score <= 6.5` / `gap -0.5%~0%` / `open_vs_sma_atr <= 1.5` / `prev_return >= 1%`) は no-trade にする

  - `primary` の Friday hot-market / low-score / negative-gap / low-open pocket (`breadth 0.65-0.75` / `market_ratio 1.10-1.15` / `score <= 6.0` / `gap -0.5%~0%` / `open_vs_sma_atr <= 0.5` / `prev_return >= 1%`) は no-trade にする

  - `primary` の Friday low-breadth / near-neutral-market / small-positive-gap pocket は no-trade にする

  - `primary` の Wednesday `breadth >= 0.50` / `open_from_prev_low_atr >= 1.5` の stretched-open pocket は no-trade にする

  - `primary` の very hot / low-breadth / negative-gap / strong-prior-day continuation は no-trade にする

  - `primary` の Monday / Thursday broad hot-market は no-trade にする

  - `primary` の Monday mid-high breadth / hot-market / non-positive-gap pocket は no-trade を許容する

  - `primary` の Monday mid-breadth / mildly hot-market / tight-gap pocket は no-trade にする

  - `primary` の Monday mid-breadth / mildly hot-market / mid-score / low-open pocket (`breadth 0.45-0.50` / `market_ratio 1.05-1.10` / `score 8.0-10.0` / `open_vs_sma_atr <= 1.0`) は no-trade にする

  - `primary` の Monday mid-breadth / moderate-extension は no-trade にする

  - `primary` の Monday high-breadth / soft-gap continuation は no-trade にする

  - 月曜の near-SMA / low-score / hot-market pocket は no-trade にする

  - 火曜の low-score hot-market の narrow pocket は no-trade にする

  - 月曜 / 木曜 / 金曜の low-score hot-market continuation は no-trade にする

  - high market-ratio / mid-breadth / mid-score / moderate-prev-return / positive-gap `primary` の equity notional 上限は `0.25`

  - `primary` の broader high-breadth / hot-market / stable-gap / mid-high-score pure-win pocket（`breadth 0.60-0.78` / `market_ratio 1.17-1.225` / `score 6.5-13.0` / `gap -1.0%~0.5%` / `open_vs_sma_atr -0.5~3.5` / `prev_return >= 1%`）は equity notional を `6.0` にする
  - `primary` の high-confidence continuation family（`primary_equity_notional_pct >= 3.0`）は Tue/Wed の notional 下限を `0.20`、Thu/Fri の notional 下限を `0.25` にする
  - `primary` の high-confidence continuation family（`primary_equity_notional_pct >= 3.0`）は Tue-Fri の risk budget を `0.25` にする

  - `primary` の Wednesday mid-breadth / hot-market / stable-gap / pure-win pocket（`breadth 0.65-0.70` / `market_ratio 1.16-1.20` / `score 4.8-6.0` / `gap <= 0%` / `open_vs_sma_atr >= 2.0`）は equity notional を `3.0` にする

  - 水曜の low-breadth / high-gap / high-score / strong-open `primary` の equity notional 上限は `0.25`

  - 木曜の high-score / moderate-prev-return / hot-market / stretched open `primary` の equity notional 上限は `0.25`

  - 月曜の hot-market medium-score `primary`（`market_ratio 1.05-1.10` / `score <= 10`）の equity notional 上限は `0.50`

  - tepid market / strong prior-day / mid-high-score `primary` の equity notional 上限は `0.25`

  - high breadth / mid-hot market / mid-high-score `primary` の equity notional 上限は `1.00`

  - 月曜の mid-gap / far-trend `primary` の equity notional 上限は `0.50`

  - 月曜の breadth `0.50-0.55` / gap `>= 2.0%` / near-SMA `primary` の equity notional 上限は `1.00`

  - 月曜の breadth `0.50-0.65` / `market_ratio 1.00-1.05` / 非マイナス gap / 前日上昇 `>= 6%` / trend `>= 1.0 ATR` `primary` の equity notional 上限は `1.00`

  - 月曜の extreme gap / modest-trend `primary` の equity notional 上限は `0.75`

  - 火曜の breadth `0.60-0.70` / positive-gap / neutral-trend `primary` の equity notional 上限は `0.50`

  - 火曜の breadth `0.60-0.70` / neutral-trend `primary` の equity notional 上限は `0.75`

  - 火曜の breadth `0.60-0.70` / 非プラスギャップ `primary` の equity notional 上限は `0.75`

  - 火曜の breadth `0.60-0.70` / high-RS / trend `1.0-3.0 ATR` / gap `<= 1.0%` の crowded `primary` を除外

  - 月曜の breadth `0.70-0.80` / gap `0-0.6%` `primary` の equity notional 上限は `1.00`

  - 水曜の hot gap / below-SMA `primary` の equity notional 上限は `0.50`

  - 木曜の breadth `0.55-0.70` / gap `0-0.6%` / continuation `primary` の equity notional 上限は `0.90`

  - 木曜の breadth `0.50-0.55` / gap `0-0.6%` / continuation `primary` の equity notional 上限は `1.00`

  - `fallback` の寄りギャップ上限を `1.2%` に制限

  - 低 breadth で寄りギャップが横ばいの `fallback` を除外

  - 低 breadth / weak score `fallback` の equity notional cap は `0.30/0.50`

  - `fallback` の equity notional 上限は `1.20`

  - 火曜の breadth `0.45-0.55` / 前日上昇 `>= 2%` / trend `1.5-3.0 ATR` `fallback` の equity notional 上限は `0.50`

  - 水曜の high breadth / gap `> 0.5%` `fallback` の equity notional 上限は `0.30`

  - 週次利益ガードは金曜、週次 `+1%` 到達後に開始

  - 1トレード当たりの equity risk budget は `9%`

  - `catchup_rs` の 1トレード当たり equity risk budget は `8%`

  - 週後半の catchup レバレッジ倍率は `30`

  - `primary` の intraday failed-runup exit は、セッション中の高値が買値から `+2%` 以上伸びたあとに失速したら break-even で退避する

  - `catchup_gapdown` の equity notional 上限は `0.50`

  - `catchup_rs` の Monday weak-market / moderate-gap pocket を selector から除外する

  - `catchup_rs` の Monday mid-breadth / stretched-open pocket を selector から除外する

  - `catchup_rs` の Tuesday low-breadth / weak-market / high-score pocket を selector から除外する

  - `catchup_rs` の Tuesday low-breadth / moderate-market pocket（`breadth < 0.45` / `market_ratio 1.00-1.05` / `score 8-10`）を selector から除外する

  - `catchup_rs` の Monday / Friday 高 breadth hot-market を selector から除外する

  - `catchup_rs` の Friday low breadth / modest market pocket（`market_ratio 1.00-1.10` / `breadth < 0.55`）を selector から除外する

  - `catchup_rs` の low-breadth / strong-continuation pure-win pocket（`breadth < 0.50` / `prev_return >= 3%` / `open_vs_sma_atr <= 1.0` / `score >= 10.0`）は selected base leverage を `0.35` に引き上げ、equity notional を `5.0` / risk budget を `0.30` にする

  - `catchup_gapdown` の Wednesday negative-trend pocket を selector から除外する

  - `catchup_gapdown` の Friday deep-gap / high-score pocket（`score > 6` / `gap <= -1%`）の equity notional を `0.25` に抑える

  - `fallback` の high breadth / hot-market pocket を selector から除外する

  - `fallback` の Tuesday / Friday 弱市場（`market_ratio 1.00-1.10` / `breadth < 0.55` / positive gap）は equity notional を `0.50` に抑える

  - `fallback` の Monday mid-breadth / neutral-market / stable-open pocket（`breadth 0.45-0.55` / `market_ratio 0.98-1.01` / `score 4.5-6.5` / `open_vs_sma_atr 2.0-3.5`）は notional を `0.25`、equity notional を `2.5` に引き上げる
  - `fallback` の Wednesday mid-breadth / hot-market / stretched-open pocket（`breadth 0.45-0.55` / `market_ratio 1.00-1.05` / `score 6.0-8.0` / `prev_return >= 4%` / `open_vs_sma_atr >= 3.5`）は notional を `0.25`、equity notional を `2.0` に引き上げる
  - `primary` の broader high-breadth / hot-market / stable-gap / mid-high-score pure-win pocket（`breadth 0.60-0.78` / `market_ratio 1.17-1.225` / `score 6.5-13.0` / `gap -1.0%~0.5%` / `open_vs_sma_atr -0.5~3.5` / `prev_return >= 1%`）は equity notional を `6.0` にする

  - `primary` の Wednesday mid-breadth / hot-market / stable-gap / pure-win pocket（`breadth 0.65-0.70` / `market_ratio 1.16-1.20` / `score 4.8-6.0` / `gap <= 0%` / `open_vs_sma_atr >= 2.0`）は equity notional を `3.0` にする
  - `primary` の Wednesday high-breadth / hot-market / stable-gap / high-score pure-win pocket（`breadth 0.70-0.75` / `market_ratio 1.15-1.20` / `score 6.5-8.0` / `gap <= 0%`）は equity notional を `3.0` にする
  - `primary` の Tuesday high-breadth / extreme hot-market / large-gap pure-win pocket（`breadth >= 0.75` / `market_ratio 1.10-1.15` / `score >= 10` / `gap >= 2.0%`）は equity notional を `3.0` にする
  - `primary` の Friday high-breadth / hot-market / stable-gap / high-score pure-win pocket（`breadth 0.60-0.75` / `market_ratio >= 1.15` / `gap 0-0.5%` / `score 6.0-8.0` / `prev_return >= 1%` / `prev_rsi2 >= 50.0` / `open_vs_sma_atr <= 2.7`）は equity notional を `7.0` にする

  - `catchup_rs` の Tuesday low-breadth probe candidate（`breadth 0.18-0.36` / `score 8.0-12.0` / `gap <= 1.0%`）は probe leverage を `0.25` にする

  - `fallback` の Friday low-breadth / sub-neutral-market / stable-open pocket（`breadth < 0.45` / `market_ratio < 1.00` / `score <= 4.5` / `open_vs_sma_atr 1.5-2.3`）は no-trade にする

  - `fallback` の Wednesday low-breadth / high-open pocket は selector から除外する

  - 月曜の breadth `0.35-0.45` / gap `-2.0%~-1.5%` / below-SMA `catchup_gapdown` の equity notional 上限は `0.25`

  - 火曜の breadth `0.35-0.45` / gap `-1.0%~-0.6%` / neutral-trend `catchup_gapdown` の equity notional 上限は `0.10`

  - 火曜の breadth `0.35-0.45` / gap `-1.5%~-0.6%` `catchup_gapdown` の equity notional 上限は `0.25`

  - 火曜の high breadth で、前日強いのに RS が弱く、寄り位置が高い `primary` を除外

  - `market_ratio >= 1.10` かつ `selected_count >= 20` かつ `catchup score` が `primary score` を `1.0-2.0` 上回るときだけ、`primary` の先頭1件を `catchup` の先頭1件へ差し替える

  - breadth `>= 0.75` かつ `market_ratio 1.05-1.15` かつ `catchup score` が `primary score` を `12.0` 以上上回るときだけ、`primary` より `catchup` を優先

  - `primary` が不在で、breadth `< 0.55` かつ `market_ratio >= 1.10` かつ restrained `catchup_rs` が弱い `fallback` を score で `6.0` 以上上回るときだけ、`fallback` より `catchup_rs` を優先

  - `inverse_pullback` 追加

  - `inverse_pullback` は、前日上昇 `>= 3%` かつ寄り gap `<= -1%` のときだけ採用する

  - panic breadth / failed rebound の `inverse_rebreak` 追加

  - `inverse` / `inverse_pullback` / `inverse_rebreak` の equity notional 上限は `0.70`

  - 高 breadth / hot continuation `primary` の equity notional 上限は `0.60`

  - `market_ratio 1.00-1.05` / gap `1.5-2.5%` / 前日上昇 `6-10%` の `primary` は、equity notional 上限を `1.40` に制限

  - breadth `< 0.60` / `market_ratio 1.00-1.05` / gap `1.5-2.0%` / `open_vs_sma_atr 1.0-2.0` の tepid hot-gap `primary` は selector から除外

  - breadth `0.45-0.65` / `market_ratio 1.05-1.10` / score `<= 6` / gap `<= 1%` の `primary` は、equity notional 上限を `1.40` に制限

  - 低 RS `primary` の equity notional 上限は `1.00`

  - `open_vs_sma_atr 4.0-5.0` の伸び切り失速帯 `primary` の equity notional 上限は `1.00`

  - `primary` の default equity notional 上限は `2.50`

  - 火曜の指数過熱 `market_ratio >= 1.20` `primary` の equity notional 上限は `0.75`

  - low breadth / 過熱指数 / low-score / near-SMA `primary` の equity notional 上限は `1.00`

  - 高 breadth 日に、弱めの `primary` より明確に強い bull ETF 候補がある場合だけ ETF 優先

  - low breadth では bull ETF を catchup より優先

  - low breadth の `bull_etf_rebound` は、上向き gap のときだけ採用する

  - low breadth / 前日プラス / near-SMA `fallback` の equity notional 上限は `0.50`

  - 水木金の low breadth / moderate-score `catchup_gapdown` probe は `0.35`

  - 金曜の low breadth / hot gap / extended trend `catchup_rs` の equity notional 上限は `0.35`

  - breadth `>= 0.60` / `market_ratio >= 1.05` / score `10-12` / gap `1-2%` の `primary` は、selected base leverage を `0.00` に制限

  - breadth `>= 0.75` / `market_ratio >= 1.25` / score `< 12` / 非マイナス gap の `primary` は、selected base leverage を `0.00` に制限

  - breadth `>= 0.75` / `market_ratio 1.15-1.20` / score `< 10` / 非マイナス gap の `primary` は、selected base leverage を `0.00` に制限

  - `market_ratio 1.05-1.10` / gap `-1%〜0%` / 前日上昇 `2-4%` の `primary` は、selected base leverage を `0.00` に制限

  - 月曜の `market_ratio 1.00-1.05` / gap `0-1%` / 前日上昇 `2-4%` の `primary` は、selected base leverage を `0.10` に制限

  - 月曜の breadth `< 0.50` / `market_ratio 1.00-1.05` / gap `>= 1.0%` の `primary` は、selected base leverage を `0.10` に制限

  - breadth `< 0.60` / `market_ratio 1.00-1.05` / gap `>= 2.0%` / RS `<= 50` の `primary` は、selected base leverage を `0.00` に制限

  - breadth `< 0.57` / `market_ratio >= 1.10` / score `10-12` / 非マイナス gap の `primary` は、selected base leverage を `0.00` に制限

  - 月火水の high-RS / overheated low-breadth `primary` は、selected base leverage を `0.00` に制限

  - breadth `0.55-0.65` / score `10-12` / RS `25-50` の `primary` は、selected base leverage を `0.10` に制限

  - breadth `0.55-0.65` / `market_ratio 1.00-1.10` / `open_vs_sma_atr 2.0-6.0` の `strong_oversold` は、selected base leverage を `0.00` に制限

  - 月火水の breadth `>= 0.70` / `market_ratio 1.00-1.10` / `open_vs_sma_atr >= 4.0` の `strong_oversold` は、selected base leverage を `0.00` に制限

  - `open_vs_sma_atr >= 6.0` または `market_ratio >= 1.20` の `strong_oversold` は、selected base leverage を `0.25` に制限

  - `strong_oversold` の Wednesday / Thursday 純勝ち帯と、hot-market / stable-market の broader 純勝ち帯は notional を `0.07`、equity notional を `4.0` にする

  - 火曜の `strong_oversold` で `open_vs_sma_atr >= 2.0` の伸び切り open pocket は selector から除外する

  - `market_ratio 1.05-1.10` / 前日上昇 `4-6%` / score `<= 6` の `primary` は、selected base leverage を `0.00` に制限

  - breadth `< 0.65` / `market_ratio 1.05-1.10` / 前日上昇 `2-4%` / score `<= 6` / gap `<= 1%` の low-sponsorship continuation `primary` は、selected base leverage を `0.00` に制限

  - 火曜の `open_vs_sma_atr 2.0-3.0` `fallback` は、selected base leverage を `0.00` に制限

  - 木曜の breadth `< 0.55` / `open_vs_sma_atr 1.0-2.0` `fallback` は、selected base leverage を `0.00` に制限

  - broad `catchup_gapdown` family は、複数年 train で net negative かつ月次 `+20%` 達成本数を改善しないため、shared setup 全体を no-trade にする

  - breadth `< 0.55` / `market_ratio >= 1.15` / score `12-16` の `catchup_rs` は、selected base leverage を `0.00` に制限

  - breadth `< 0.55` / `market_ratio >= 1.15` の fragile hot market では、`primary` を `1.00`、`catchup_rs` を `0.00`、`fallback` を `0.10` に制限

  - breadth `< 0.60` / `market_ratio >= 1.20` / `score <= 8.0` / 非マイナス gap の `primary` は、selected base leverage を `0.00` に制限

  - 水木金の breadth `< 0.60` / `market_ratio >= 1.15` / score `>= 10` の `primary` は、selected base leverage を `0.00` に制限

  - 水曜の high breadth / 非プラス gap / score `8-10` `primary` は、selected base leverage を `0.00` に制限

  - breadth `< 0.60` / `market_ratio >= 1.15` / `score <= 8.0` / 非マイナス gap の `primary` は、selected base leverage を `0.05` に制限

  - breadth `< 0.60` / `market_ratio >= 1.15` / score `>= 10` / プラス gap の `primary` は、selected base leverage を `0.05` に制限

  - breadth `< 0.60` / `market_ratio >= 1.20` / 非マイナス gap の `primary` は、selected base leverage を `0.05` に制限

  - breadth `0.55-0.70` / `market_ratio 1.05-1.15` / gap `>= 1.5%` / score `10-14` / 前日上昇 `>= 3.5%` の `primary` は、equity notional 上限を `0.75` に制限

  - `100万円` 近辺の small-account では、`catchup_rs` の 1-board-lot が risk / equity cap の範囲に収まるときだけ、notional cap より実行可能性を優先

  - `100万円` 近辺の small-account では、hot / mid-score `catchup_rs` の board-lot を無理に建てない

  - `100万円` 近辺の small-account では、上位 `primary` が board-lot 制約で入れず、rank `4+` / score gap `>= 8.0` の cheap substitute しか残らない日は no-trade

- 火曜 low-breadth `catchup_rs` の moderate-score probe leverage は `0.20`

- 火曜 low-breadth で too-hot な `catchup_rs` は moderate candidate に selector cooling する

- 水曜 low-breadth の `catchup_rs` は selector から除外する

- `primary` の Monday / Tuesday / Thursday near-neutral / low-score / small-gap pocket は、breadth < 0.55 と breadth 0.58-0.70、open_vs_sma_atr 1.0-2.0 の 2 帯で selected base leverage を `0.03` に制限する

- 最新確認値（FULL / daily OHLC reference-only）:
- `FINAL EQUITY: 600,707,511円`
- `CLOSED TRADES: 406`
- `WIN RATE: 67.24%`
- `WEEKS >= +1%: 103/228`
- `POSITIVE WEEKS: 160/228`
- `TOTAL RETURN: +59970.75%`
- `PROFIT_FACTOR: 21.64`
- `AVG MONTH ACTIVE RATE: 38.11%`
- `MED MONTH ACTIVE RATE: 38.10%`
- `MONTHS >= 50% ACTIVE: 13/52`
- `MONTHS >= 2/3 ACTIVE: 3/52`
- `MONTHS >= 3/4 ACTIVE: 1/52`
- `MONTHS >= 20%: 18/61`
- `WORST DAY: -8,100,000円`

- 最新確認値（TRAIN / daily OHLC reference-only）:
- `FINAL EQUITY: 243,023,054円`
- `CLOSED TRADES: 364`
- `WIN RATE: 67.03%`
- `WEEKS >= +1%: 89/202`
- `POSITIVE WEEKS: 140/202`
- `TOTAL RETURN: +24202.31%`
- `PROFIT_FACTOR: 51.86`
- `MONTHS >= 3/4 ACTIVE: 1/46`
- `MONTHS >= 20%: 16/55`
- `WORST DAY: -1,426,300円`

### 2026-06-21: Tuesday / Thursday Mid-Breadth Hot-Market Selected-Leverage Cap Adopted

- 試したこと:

  - `primary` の Tuesday / Thursday mid-breadth / hot-market / score `8.0-10.0` を、selected base leverage `0.10` に制限した

  - train で再現した loss pocket `2024-02-15 3984.T` / `2025-10-09 6269.T` / `2025-10-21 6310.T` を shared cap で浅くした

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

  - `FULL WINDOW: FINAL EQUITY Y3,049,410 / TOTAL RETURN +204.94% / CLOSED TRADES 523 / WIN RATE 45.32% / PROFIT FACTOR 1.54 / WEEKS >= +1% 79/225 / POSITIVE WEEKS 108/225 / MONTHS >= 3/4 ACTIVE 7/52 / WORST DAY -197,986`

  - `TRAIN WINDOW: FINAL EQUITY Y1,862,911 / TOTAL RETURN +86.29% / CLOSED TRADES 472 / PROFIT FACTOR 1.29 / WEEKS >= +1% 67/199 / POSITIVE WEEKS 92/199 / MONTHS >= 3/4 ACTIVE 7/45 / WORST DAY -117,641`

  - `HOLDOUT WINDOW: FINAL EQUITY Y3,049,410 / TOTAL RETURN +63.69% / CLOSED TRADES 51 / WIN RATE 50.98% / PROFIT FACTOR 2.46 / WEEKS >= +1% 12/26 / POSITIVE WEEKS 16/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -197,986`

  - `100万円 standalone latest 1m: FINAL EQUITY Y1,008,345 / TOTAL RETURN +0.83% / CLOSED TRADES 1 / PROFIT FACTOR inf / WEEKS >= +1% 0/4 / POSITIVE WEEKS 1/4 / WORST DAY 0`

- 判断:

  - 採用

- 再試行するとしたら:

  - Thursday / Tuesday mid-breadth hot-market でも score / breadth / market_ratio がさらに低い、train で複数回再現する pocket が見つかった場合だけ

  - それ以外は broad no-trade を増やすより shared leverage cap で浅くする方針を優先

### 2026-06-22: Wednesday Mid-Breadth Hot-Market Selected-Leverage Cap Adopted

- 試したこと:

  - `primary` の Wednesday mid-breadth / hot-market / score `9-12` を selected base leverage `0.10` に制限した

  - train で再現した `2024-01-10 4046.T` / `2024-03-13 4186.T` / `2025-11-26 6525.T` / `2025-12-03 4971.T` の損失 pocket を shared cap で浅くした

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

  - `FULL WINDOW: FINAL EQUITY Y3,105,209 / TOTAL RETURN +210.52% / CLOSED TRADES 527 / WIN RATE 45.16% / PROFIT FACTOR 1.55 / WEEKS >= +1% 79/225 / POSITIVE WEEKS 107/225 / MONTHS >= 3/4 ACTIVE 7/52 / WORST DAY -197,986`

  - `TRAIN WINDOW: FINAL EQUITY Y1,915,368 / TOTAL RETURN +91.54% / CLOSED TRADES 476 / PROFIT FACTOR 1.31 / WEEKS >= +1% 67/199 / POSITIVE WEEKS 91/199 / MONTHS >= 3/4 ACTIVE 7/45 / WORST DAY -117,641`

  - `HOLDOUT WINDOW: FINAL EQUITY Y3,105,209 / TOTAL RETURN +62.12% / CLOSED TRADES 51 / WIN RATE 50.98% / PROFIT FACTOR 2.45 / WEEKS >= +1% 12/26 / POSITIVE WEEKS 16/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -197,986`

  - `100万円 standalone latest 1m: FINAL EQUITY Y1,008,345 / TOTAL RETURN +0.83% / CLOSED TRADES 1 / PROFIT FACTOR inf / WEEKS >= +1% 0/4 / POSITIVE WEEKS 1/4 / WORST DAY 0`

- 判断:

  - 採用

- 再試行するとしたら:

  - Wednesday の mid-breadth hot-market でも score 8-12 の train 再現 pocket がさらに見つかり、holdout の veto を壊さないときだけ

### 2026-06-22: Tuesday Low-Market Small-Gap Hot-Market Rebalance Adopted

- 試したこと:

  - `primary` の Tuesday mid-breadth / low-market / low-score / positive-gap pocket を no-trade にした

  - Tuesday mid-breadth / hot-market の境界を少し引き上げ、small-gap 側は 0.10 に寄せつつ、強い側の 0.50 は維持した

  - train で再現した `2023-04-18 9107.T` / `2023-04-25 6191.T` / `2023-08-15 6266.T` / `2024-05-14 6361.T` の負け pocket を、shared no-trade と 0.10 cap に分けて浅くした

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

  - `FULL WINDOW: FINAL EQUITY Y3,374,032 / TOTAL RETURN +237.40% / CLOSED TRADES 527 / WIN RATE 45.16% / PROFIT FACTOR 1.61 / WEEKS >= +1% 82/225 / POSITIVE WEEKS 110/225 / MONTHS >= 3/4 ACTIVE 7/52 / WORST DAY -219,199`

  - `TRAIN WINDOW: FINAL EQUITY Y2,080,462 / TOTAL RETURN +108.05% / CLOSED TRADES 475 / PROFIT FACTOR 1.36 / WEEKS >= +1% 70/199 / POSITIVE WEEKS 95/199 / MONTHS >= 3/4 ACTIVE 7/45 / WORST DAY -117,641`

  - `HOLDOUT WINDOW: FINAL EQUITY Y3,374,032 / TOTAL RETURN +62.18% / CLOSED TRADES 52 / WIN RATE 48.08% / PROFIT FACTOR 2.37 / WEEKS >= +1% 12/26 / POSITIVE WEEKS 15/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -219,199`

  - `100万円 standalone latest 1m: FINAL EQUITY Y1,008,345 / TOTAL RETURN +0.83% / CLOSED TRADES 1 / PROFIT FACTOR inf / WEEKS >= +1% 0/4 / POSITIVE WEEKS 1/4 / WORST DAY 0`

- 判断:

  - 採用

- 再試行するとしたら:

  - Tuesday mid-breadth hot-market で、`market_ratio` と `gap` がさらに弱い pocket が train に複数再現する場合だけ

  - それ以外は、small-gap の当て込みではなく shared cap / no-trade のどちらかで train-supported に閉じる

### 2026-06-21: J-Quants Proxy Bypass Restored Refresh to 2026-06-19

- 変更:

  - `jp_jquants_fetcher_v2.py` で `api.jquants.com` を `NO_PROXY` に追加し、`HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` が localhost blackhole でも refresh を通すようにした

  - `fetch_ticker_master_with_fallback(...)` の fallback universe でも incremental refresh が落ちないよう、`resolve_incremental_target_tickers(...)` を維持した

  - `scripts/jp_refresh_validate.py --holdout-months 6 --standalone-latest-months 1` を再実行し、cache を `2026-06-19` まで更新した

- 結果:

  - latest cache day: `2026-06-19`

  - full: `TOTAL RETURN +193.18% / PROFIT FACTOR 1.51 / WEEKS >= +1% 80/225 / POSITIVE WEEKS 108/225 / WORST DAY -190,915円`

  - train: `TOTAL RETURN +79.36% / PROFIT FACTOR 1.26 / WEEKS >= +1% 68/199 / POSITIVE WEEKS 92/199 / WORST DAY -117,641円`

  - holdout: `TOTAL RETURN +63.46% / PROFIT FACTOR 2.44 / WEEKS >= +1% 12/26 / POSITIVE WEEKS 16/26 / WORST DAY -190,915円`

  - `100万円 standalone latest 1m TOTAL RETURN +0.83% / CLOSED TRADES 1 / PROFIT FACTOR inf / WEEKS >= +1% 0/4 / POSITIVE WEEKS 1/4 / WORST DAY 0円`

- 判断:

  - 採用（データ更新経路の修正）

- 再試行するとしたら:

  - J-Quants 側の proxy 前提が変わったときだけ

### 2026-06-20: Tuesday Mid-Breadth Low-Score Hot-Market Veto Moved Ahead of Neutral-Trend Caps

- 試したこと:

  - `primary` の Tuesday mid-breadth / low-score / hot-market continuation no-trade を、broader Tuesday neutral-trend caps より前に移動した

  - train の exact loss pocket `2023-07-11 4385.T` / `2023-07-25 7095.T` / `2024-04-16 3186.T` を no-trade に寄せた

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

  - `FULL TOTAL RETURN +190.97% / PROFIT FACTOR 1.50 / WEEKS >= +1% 80/223 / POSITIVE WEEKS 107/223 / WORST DAY -190,915円`

  - `TRAIN TOTAL RETURN +70.23% / PROFIT FACTOR 1.24 / WEEKS >= +1% 67/197 / POSITIVE WEEKS 91/197 / WORST DAY -117,641円`

  - `HOLDOUT TOTAL RETURN +70.93% / PROFIT FACTOR 2.42 / WEEKS >= +1% 13/26 / POSITIVE WEEKS 16/26 / WORST DAY -190,915円`

  - `100万円 standalone latest 1m TOTAL RETURN +0.00% / CLOSED TRADES 0 / PROFIT FACTOR N/A / WEEKS >= +1% 0/5 / POSITIVE WEEKS 0/5 / WORST DAY 0円`

  - `train miss weeks 129/196 | negative 105 | positive_miss 24 | miss_no_trade 13`

- 判断:

  - 採用

- 再試行するとしたら:

  - さらに進めるなら、train で複数回再現する新しい residual cluster が見つかったときだけ

### 2026-06-20: Monday / Thursday Broad Hot-Market and Monday Soft-Gap Vetoes Adopted

- 試したこと:

  - `primary` の Monday / Thursday broad hot-market を no-trade にした

  - Monday high-breadth の soft-gap continuation を no-trade にした

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

  - `FULL TOTAL RETURN +106.73% / PROFIT FACTOR 1.28 / WEEKS >= +1% 79/223 / POSITIVE WEEKS 107/223 / WORST DAY -141,419円`

  - `TRAIN TOTAL RETURN +27.98% / PROFIT FACTOR 1.09 / WEEKS >= +1% 65/197 / POSITIVE WEEKS 91/197 / WORST DAY -99,841円`

  - `HOLDOUT TOTAL RETURN +61.54% / PROFIT FACTOR 1.97 / WEEKS >= +1% 14/26 / POSITIVE WEEKS 16/26 / WORST DAY -141,419円`

  - `100万円 standalone latest 1m TOTAL RETURN +0.00% / CLOSED TRADES 0 / PROFIT FACTOR N/A / WEEKS >= +1% 0/5 / POSITIVE WEEKS 0/5 / WORST DAY 0円`

- 判断:

  - 採用

- 再試行するとしたら:

  - 同じ周辺の hot-market continuation を広げるのではなく、train-supported で別の shared tail-loss pocket が見つかったときだけ

### 2026-06-20: Monday Weak-Market Catchup RS Gap Extension Rejected

- 試したこと:

  - `catchup_rs` の Monday weak-market pocket について、`gap_pct` 上限を `1.0% -> 1.2% / 1.5%` へ広げる what-if を確認した

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

  - `FULL TOTAL RETURN +145.59% / PROFIT FACTOR 1.34 / WEEKS >= +1% 77/223 / POSITIVE WEEKS 108/223 / WORST DAY -169,702円`

  - `TRAIN TOTAL RETURN +54.94% / PROFIT FACTOR 1.17 / WEEKS >= +1% 64/197 / POSITIVE WEEKS 93/197 / WORST DAY -104,036円`

  - `HOLDOUT TOTAL RETURN +58.50% / PROFIT FACTOR 1.87 / WEEKS >= +1% 13/26 / POSITIVE WEEKS 15/26 / WORST DAY -169,702円`

  - `100万円 standalone latest 1m TOTAL RETURN +0.00% / CLOSED TRADES 0 / PROFIT FACTOR N/A / WEEKS >= +1% 0/5 / POSITIVE WEEKS 0/5 / WORST DAY 0円`

- 判断:

  - 不採用

- 再試行するとしたら:

  - Monday weak-market catchup_rs の別軸が train で明確に再現し、worst day を悪化させずに切れるときだけ

### 2026-06-06: Primary Failed-Runup Exit Restored as Shared Logic

- 試したこと:

  - `primary` だけに効く intraday failed-runup exit を shared helper へ戻し、`backtest.py` と live 側の `auto_trade.py` が同じ `exit_reason` を使うようにした

  - `auto_trade.py` では position record に `setup_type` / stop / target / entry context を保持し、`DAYTRADE_EXIT_LOG_FILE` に exit event を書くようにした

  - `analyze_backtest_trade_log.py` では `intraday_failed_runup` を `fade` bucket として独立集計し、train の `primary` fade cluster として追跡できるようにした

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

  - `FULL TOTAL RETURN +160.85% / PROFIT FACTOR 1.27 / WEEKS >= +1% 83/223 / POSITIVE WEEKS 104/223 / WORST DAY -169,702円`

  - `TRAIN TOTAL RETURN +83.09% / PROFIT FACTOR 1.18 / WEEKS >= +1% 72/197 / POSITIVE WEEKS 90/197 / WORST DAY -134,635円`

  - `HOLDOUT TOTAL RETURN +42.47% / PROFIT FACTOR 1.61 / WEEKS >= +1% 11/26 / POSITIVE WEEKS 14/26 / WORST DAY -169,702円`

  - `100万円 standalone latest 1m TOTAL RETURN +0.10% / CLOSED TRADES 2 / PROFIT FACTOR 1.89 / WEEKS >= +1% 0/5 / POSITIVE WEEKS 1/5 / WORST DAY -1,165円`

  - `rolling 3-window walkforward: POSITIVE WINDOWS 3/3 / AVG HOLDOUT PF 6.09 / HOLDOUT WEEKS >= +1% 68/78`

- 判断:

  - 採用

  - train / holdout / rolling の全部で shared strategy として破綻せず、`primary` の run-up fade を浅くする方向として説明可能だった

- 再試行するとしたら:

  - `+2%` failed-runup guard を当て込み方向に動かすのではなく、別の train-supported fade cluster が見つかったときだけ

### 2026-06-06: Early-Week Hot-Market No-Trade Rejected

- 試したこと:

  - Monday / Tuesday の hot-market `primary` に broad no-trade を入れて、train の損失クラスタをまとめて閉じる案を試した

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

  - `FULL TOTAL RETURN +40.25% / PROFIT FACTOR 1.08`

  - `TRAIN TOTAL RETURN +23.34% / PROFIT FACTOR 1.06`

  - `HOLDOUT TOTAL RETURN +13.71% / PROFIT FACTOR 1.20`

- 判断:

  - 不採用

  - train の改善幅が baseline を下回り、broad no-trade は shared strategy として広すぎた

- 再試行するとしたら:

  - 週初の hot-market pocket をさらに広げるのではなく、別の train-supported loss cluster が見つかったときだけ

### 2026-06-07: Catchup/Fallback Hot-Market Selector Filters Adopted

- 試したこと:

  - `catchup_rs` の Monday / Friday 高 breadth hot-market pocket を selector から除外した

  - `fallback` の high-breadth / hot-market pocket を selector から除外した

  - 既存の shared intraday failed-runup exit は維持し、live / backtest / analyzer の共通経路を崩さないことを優先した

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - `FULL TOTAL RETURN +231.11% / PROFIT_FACTOR 1.36 / WEEKS >= +1% 83/223 / POSITIVE WEEKS 105/223 / WORST DAY -219,199円`

    - `TRAIN TOTAL RETURN +131.76% / PROFIT_FACTOR 1.28 / WEEKS >= +1% 72/197 / POSITIVE WEEKS 92/197 / WORST DAY -141,551円`

    - `HOLDOUT TOTAL RETURN +42.87% / PROFIT_FACTOR 1.59 / WEEKS >= +1% 11/26 / POSITIVE WEEKS 13/26 / WORST DAY -219,199円`

    - `100万円 standalone latest 1m TOTAL RETURN +0.10% / CLOSED TRADES 2 / PROFIT_FACTOR 1.89 / WEEKS >= +1% 0/5 / POSITIVE WEEKS 1/5 / WORST DAY -1,165円`

  - `python analyze_backtest_trade_log.py --holdout-months 6 --top-n 20`

    - `train weeks=196 | miss=124 | negative=104 | positive_miss=20 | miss_no_trade=12`

    - `primary stop` は依然として最大の損失要因だが、`catchup_rs` / `fallback` の hot-market residual はさらに薄くなった

  - `python jp_walkforward.py --holdout-months 6 --step-months 1 --min-train-months 24 --max-windows 3`

    - `POSITIVE WINDOWS: 3/3`

    - `AVG HOLDOUT PF: 5.75`

    - `HOLDOUT WEEKS >= +1%: 68/78`

    - `HOLDOUT POSITIVE WEEKS: 70/78`

- 判断:

  - 採用

  - `catchup_rs` / `fallback` の高熱帯残差を shared selector で閉じても full / train / holdout / rolling を壊さず、実運用初期条件の standalone も維持できた

- 再試行するとしたら:

  - 残る候補は `primary stop` の broad band だが、同帯の holdout 側に勝ち例があるため、広い no-trade / cap は当て込みになりやすい

  - 追加で進めるなら、train で再現が増えた新しい residual cluster が見つかったときだけ

### 2026-06-06: Early-Week High-Ratio Probe Rejected

- 試したこと:

  - Monday / Tuesday hot-market `primary` を `market_ratio >= 1.15` 近傍で `0.10` probe 化して、selected order まで含めて train loss を削る案を試した

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

  - `FULL TOTAL RETURN +52.52% / PROFIT FACTOR 1.11`

  - `TRAIN TOTAL RETURN +17.15% / PROFIT FACTOR 1.04`

  - `HOLDOUT TOTAL RETURN +30.19% / PROFIT FACTOR 1.50`

- 判断:

  - 不採用

  - holdout だけ良く見えるが train が悪化し、selection effect を含めると shared rule としては弱かった

- 再試行するとしたら:

  - `market_ratio` だけの近傍当て込みではなく、train で再現する別 regime として説明できるときだけ

### 2026-06-06: Tepid Market Strong-Prior Cap Adopted

- 試したこと:

  - `primary` のうち、`market_ratio <= 1.05` / `prev_return >= 0.03` / `score > 8` に入る tepid-market continuation だけ、`equity_notional_pct` を `0.50` に抑える shared cap を追加した

  - 後続の再分析で、この帯はさらに `0.25` まで tighten した

  - train-only では `2024` と `2025` の loss cluster が目立ち、`2024-11-25 6240.T` / `2025-06-05 9235.T` / `2025-06-06 4593.T` / `2024-09-02 3791.T` のような large-loss 日に一致していた

  - holdout の direct match はほぼ無く、`100万円 standalone` の最新 1ヶ月も主要な no-trade 日を壊さなかった

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

  - `FULL TOTAL RETURN -60.12% / PROFIT FACTOR 0.85 / WEEKS >= +1% 89/223 / POSITIVE WEEKS 99/223 / WORST DAY -114,757円`

  - `TRAIN TOTAL RETURN -67.03% / PROFIT FACTOR 0.83 / WEEKS >= +1% 77/197 / POSITIVE WEEKS 87/197 / WORST DAY -114,757円`

  - `HOLDOUT TOTAL RETURN +20.94% / PROFIT FACTOR 1.28 / WEEKS >= +1% 12/26 / POSITIVE WEEKS 12/26 / WORST DAY -28,284円`

  - `100万円 standalone latest 1m TOTAL RETURN +0.10% / CLOSED TRADES 2 / PROFIT FACTOR 1.89 / WEEKS >= +1% 0/5 / POSITIVE WEEKS 1/5 / WORST DAY -1,165円`

- 判断:

  - 採用

  - low-breadth 版よりも train-only の loss cluster に素直で、full も改善したため、こちらを current shared cap とした

- 再試行するとしたら:

  - `market_ratio <= 1.05` の tepid tape で、さらに train 再現が増えた別の shared continuation guard が見つかったときだけ

  - この帯をさらに広げて holdout まで追いかけることはしない

### 2026-06-06: High-Breadth Mid-Hot Primary Cap Adopted

- 試したこと:

  - `primary` のうち、`breadth >= 0.75` / `market_ratio < 1.20` / `score > 8` に入る high-breadth mid-hot continuation だけ、`equity_notional_pct` を `0.50` に抑える shared cap を追加した

  - train-only では `Monday / Wednesday / Thursday / Friday` が net negative で、`Tuesday` だけが positive だったため、曜日混在のまま広げるのではなく residual cluster として切った

  - `Tuesday` だけを外す案と `strong_oversold` の一律半減は試したが、どちらも train を悪化させたので不採用にした

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

  - `FULL TOTAL RETURN -52.62% / PROFIT FACTOR 0.87 / WEEKS >= +1% 85/223 / POSITIVE WEEKS 97/223 / WORST DAY -114,757円`

  - `TRAIN TOTAL RETURN -60.47% / PROFIT FACTOR 0.84 / WEEKS >= +1% 74/197 / POSITIVE WEEKS 86/197 / WORST DAY -114,757円`

  - `HOLDOUT TOTAL RETURN +19.87% / PROFIT FACTOR 1.33 / WEEKS >= +1% 11/26 / POSITIVE WEEKS 11/26 / WORST DAY -28,284円`

  - `100万円 standalone latest 1m TOTAL RETURN +0.10% / CLOSED TRADES 2 / PROFIT FACTOR 1.89 / WEEKS >= +1% 0/5 / POSITIVE WEEKS 1/5 / WORST DAY -1,165円`

- 判断:

  - 採用

  - tepid cap の残差として残っていた高 breadth / mid-hot `primary` の loss cluster を落とせたので、current shared cap に追加した

- 再試行するとしたら:

  - `breadth >= 0.75` の残差に対して、さらに曜日分割の train-supported guard が増えたときだけ

  - この帯を持ったまま holdout を追いかけることはしない

### 2026-06-06: Evaluation Harness Unified on Prime Universe + Tax

- 変更:

  - `jp_backtest.py` の universe selection を `prepared["univ_indices"]` に統一した

  - `scripts/jp_refresh_validate.py` の `profit_tax_rate` を `TAX_RATE` に統一し、`explicit_trade_cost` を `DAYTRADE_API_EXPLICIT_TRADE_COST` に統一した

- 結果:

  - `FULL TOTAL RETURN -89.72% / PROFIT FACTOR 0.80 / WEEKS >= +1% 99/223 / POSITIVE WEEKS 109/223 / WORST DAY -156,160円`

  - `TRAIN TOTAL RETURN -87.36% / PROFIT FACTOR 0.80 / WEEKS >= +1% 92/197 / POSITIVE WEEKS 101/197 / WORST DAY -156,160円`

  - `HOLDOUT TOTAL RETURN -18.70% / PROFIT FACTOR 0.72 / WEEKS >= +1% 7/26 / POSITIVE WEEKS 8/26 / WORST DAY -10,845円`

  - `100万円 standalone latest 1m TOTAL RETURN +0.10% / CLOSED TRADES 2 / PROFIT FACTOR 1.89 / WEEKS >= +1% 0/5 / POSITIVE WEEKS 1/5 / WORST DAY -1,165円`

- 判断:

  - 採用

  - `jp_backtest.py` と strict validation の universe / cost model が揃い、以前の高 PF 記録が別ハーネス由来だったことを切り分けられた

- 再試行するとしたら:

  - 次は train の残存 loss cluster を shared logic で再分析する

### 2026-06-05: Tuesday Catchup Cooling + Wednesday Veto Adopted

- 変更:

  - `select_daytrade_candidates` に、火曜 `0.18 <= breadth < 0.36` の `catchup_rs` で top score `>= 12.0` のときだけ、score `8.0-12.0` / gap `<= +1.0%` の moderate candidate を先頭へ繰り上げる selector cooling を追加した

  - `resolve_daytrade_selected_leverage` に、火曜 `0.18 <= breadth < 0.36` / top `catchup_rs` score `8.0 <= score < 12.0` / gap `<= +1.0%` の small-account probe leverage `0.20` を追加した

  - 水曜の low-breadth `catchup_rs` を selector から除外する shared veto を追加した

  - `catchup_gapdown` の Wed-Fri low-breadth / score `6.0-8.0` probe leverage `0.35` は維持した

- 結果:

  - `FULL TOTAL RETURN -20.07% / PROFIT FACTOR 0.97 / WEEKS >= +1% 114/223 / POSITIVE WEEKS 119/223 / WORST DAY -190,862円`

  - `TRAIN TOTAL RETURN -46.82% / PROFIT FACTOR 0.94 / WEEKS >= +1% 103/197 / POSITIVE WEEKS 106/197 / WORST DAY -190,862円`

  - `HOLDOUT TOTAL RETURN +50.31% / PROFIT FACTOR 1.69 / WEEKS >= +1% 11/26 / POSITIVE WEEKS 13/26 / WORST DAY -49,496円`

  - `100万円 standalone latest 1m TOTAL RETURN +0.16% / CLOSED TRADES 2 / PROFIT FACTOR 2.37 / WEEKS >= +1% 0/5 / POSITIVE WEEKS 1/5 / WORST DAY -1,165円`

- 判断:

  - 採用

  - 週次ヒットはまだ未達だが、`2026-05-27` の Wednesday `catchup_rs` loss cluster を shared veto で落とし、standalone を赤字から黒字へ戻せた

- 再試行するとしたら:

  - 残る Monday `primary` の小さな loss cluster を train で再現できるときだけ

  - 現状の Tuesday cooling / Wednesday veto を広げるのではなく、別の train-supported shared regime が見つかったときだけ

### 2026-06-05: Cache Refill to Latest Data

- 変更:

  - J-Quants から短い A-shares `570A` 〜 `580A` を再取得し、`data_cache/jp_broad/jp_mega_cache.pkl` を 2026-06-05 まで再合成した

  - 戦略ロジックは変更していない

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

  - full: `TOTAL RETURN -20.19%`, `PROFIT FACTOR 0.97`, `WEEKS >= +1% 116/223`, `POSITIVE WEEKS 121/223`, `WORST DAY -196,646`

  - holdout: `TOTAL RETURN +50.76%`, `PROFIT FACTOR 1.70`, `WEEKS >= +1% 11/26`, `POSITIVE WEEKS 13/26`, `WORST DAY -49,496`

  - standalone latest 1m: `TOTAL RETURN -0.78%`, `CLOSED TRADES 3`, `PROFIT FACTOR 0.26`, `WEEKS >= +1% 0/5`, `POSITIVE WEEKS 1/5`, `WORST DAY -9,360`

- 採用:

  - ロジック採用なし。cache 修復のみ

- 再試行するとしたら:

  - この cache を基準に train 側の損失 cluster を再分析する

### 2026-06-03: Cache Refresh to 2026-06-02 Data

- 変更:

  - `data_cache/jp_broad/jp_mega_cache.pkl` を 2026-06-02 まで更新した

  - 戦略ロジックは変更していない

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

  - full: `TOTAL RETURN: +398093.85%`, `PROFIT FACTOR: 21.51`, `WEEKS >= +1%: 187/223`, `POSITIVE WEEKS: 189/223`, `WORST DAY: -29,490,967円`

  - holdout: `TOTAL RETURN: +250.50%`, `PROFIT FACTOR: 31.46`, `WEEKS >= +1%: 21/26`, `POSITIVE WEEKS: 21/26`, `WORST DAY: -29,490,967円`

  - standalone latest 1m: `TOTAL RETURN: +10.12%`, `CLOSED TRADES: 5`, `PROFIT FACTOR: N/A (損失合計 0)`, `WEEKS >= +1%: 3/5`, `POSITIVE WEEKS: 4/5`, `WORST DAY: 0円`

- 採用:

  - ロジック採用はなし。baseline 数値の更新のみ

- 再試行するとしたら:

  - 新しいデータが追加されたとき、または shared strategy の変更候補が出たとき

### 2026-06-03: Backtest / Live Parity Hardening

- 目的:

  - `jp_backtest` の評価前提を実運用に寄せ、都合よく利益が出る見え方を減らす

- 変更:

  - `jp_backtest.py` / `jp_walkforward.py` / `jp_optimizer.py` / `analyze_backtest_trade_log.py` / `scripts/jp_refresh_validate.py` の評価前提を統一した

  - `explicit_trade_cost = 0`

  - `profit_tax_rate = TAX_RATE`

  - `entry_slippage` / `exit_slippage` を本番より不利側へ寄せた

  - `backtest.py` に日次 turnover ベースの `liquidity_limit` を追加した

  - `trade_log` に `requested_shares` / `liquidity_cap_shares` / `liquidity_fill_ratio` を記録するようにした

  - `AGENTS.md` に backtest を都合よく勝たせないための厳格ルールを追記した

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

  - full: `FINAL EQUITY Y86,614,276`, `TOTAL RETURN +8561.43%`, `CLOSED TRADES 489`, `WIN RATE 53.17%`, `PROFIT FACTOR 4.04`, `WEEKS >= +1% 151/223`, `POSITIVE WEEKS 170/223`, `WORST DAY -1,219,299円`

  - holdout: `TOTAL RETURN +105.59%`, `PROFIT FACTOR 7.83`, `WEEKS >= +1% 14/26`, `POSITIVE WEEKS 19/26`, `WORST DAY -1,123,919円`

  - standalone latest 1m: `FINAL EQUITY Y1,023,403`, `TOTAL RETURN +2.34%`, `CLOSED TRADES 5`, `PROFIT FACTOR 1.51`, `WEEKS >= +1% 2/5`, `POSITIVE WEEKS 2/5`, `WORST DAY -45,114円`

- 採用:

  - 採用（評価厳格化）

- 再試行するとしたら:

  - live log で `order_not_filled` / `partial fill` / `cancel` の偏りが明確になったときだけ、さらに不利側へ寄せる

## Adopted Logic

### 2026-06-06: Thursday Low-Score Hot Market + Monday Medium-Score Hot Market Caps

- 分析:

  - train の primary stop losses は Monday と Thursday に集中しており、Thursday の `score <= 8` hot-market pocket は train-only でかなり悪かった

  - Monday も `market_ratio 1.05-1.10` / `score 9-10` の hot-market pocket が train-only で悪かった

  - Monday の `score <= 12` まで広げる broad cap は full / holdout を少し悪化させたため不採用にした

- 変更:

  - `core/logic.py` に Thursday low-score hot-market primary の `0.50` cap を追加した

  - さらに Monday medium-score hot-market primary (`market_ratio 1.05-1.10` / `score <= 10`) の `0.50` cap を追加した

  - `tests/test_logic.py` に Thursday と Monday の回帰テストを追加した

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

  - `FULL TOTAL RETURN -60.24% / PROFIT FACTOR 0.85 / WEEKS >= +1% 97/223 / POSITIVE WEEKS 103/223 / WORST DAY -144,592円`

  - `TRAIN TOTAL RETURN -70.37% / PROFIT FACTOR 0.82 / WEEKS >= +1% 84/197 / POSITIVE WEEKS 90/197 / WORST DAY -144,592円`

  - `HOLDOUT TOTAL RETURN +34.19% / PROFIT FACTOR 1.45 / WEEKS >= +1% 13/26 / POSITIVE WEEKS 13/26 / WORST DAY -22,280円`

  - `100万円 standalone latest 1m TOTAL RETURN +0.10% / CLOSED TRADES 2 / PROFIT FACTOR 1.89 / WEEKS >= +1% 0/5 / POSITIVE WEEKS 1/5 / WORST DAY -1,165円`

- 判断:

  - 採用

  - Thursday loss cluster と Monday medium-score hot-market pocket は train-only で悪く、holdout への直撃もなかったので shared cap として採用した

- 再試行するとしたら:

  - Monday `1.00-1.05 / score 8-10` の残り pocket を別の train-supported shared rule として見つけられたときだけ

  - broad Monday `score <= 12` のような広げ方は full / holdout を壊しやすいので追わない

### 2026-06-03: Wednesday Low-Breadth Catchup RS Probe Rejected

- 分析:

  - train の Wednesday `catchup_rs` には、`breadth < 0.45 / score 6-11 / open_vs_sma_atr < 3` で `+78,060` 相当の positive sum はあった

  - ただし、実際の `2026-05-20` の selected pool には `9513.T fallback` / `8282.T catchup_rs` / `8368.T catchup_rs` しか入らず、以前見えていた `1407.T` の positive sample は再現しなかった

  - target day の top catchup_rs は `8368.T` で、`score 5.83` / `intraday_stop` / `-6,555.63 per 100 shares` だった

  - probe を有効化した validation では、`FULL` が `FINAL EQUITY Y3,832,949,875` / `CLOSED TRADES 427` / `WORST DAY -17,396,785` まで悪化し、`TRAIN` も `+110316.92%` で baseline の `+116047.65%` を下回った

  - `100万円 standalone 1M` は `TOTAL RETURN +10.12% / CLOSED TRADES 5 / WORST DAY 0` のままで、目標の daily +1% には届かなかった

- 変更:

  - Wednesday low-breadth `catchup_rs` probe を shared logic に追加して検証したが、結果が悪かったため revert した

  - 同 probe 用の回帰テストも一時追加したが、最終的には削除した

- 採用:

  - 不採用

- 再試行するとしたら:

  - まず `select_daytrade_candidates` 側で、この帯の catchup 候補が `selected_candidates` に入るように selection ranking を再設計し、その上で train だけで再評価する

  - それができない限り、同じ family を small-account probe で延命しても standalone には届かない

### 2026-06-03: Thursday Fallback Rescue Probe for Small Accounts

- 分析:

  - `2026-05-21` の `fallback 6754.T` は、train で再現のある `score 5-7` / `prev_return >= 0` / `open_vs_sma_atr 2-3` / `open_from_prev_low_atr >= 1.0` 帯だったが、100株の board-lot では直近1ヶ月 standalone の貢献が小さかった

  - 同じ帯を 500株まで広げる案は `2026-05-22` を消して total equity を下げたため、small-account の rescue probe は Thursday のみ、かつ 400株までに抑えるのが安全だった

- 変更:

  - `core/logic.py` に Thursday-only の small-account fallback rescue probe を追加した

  - `prefer_daytrade_small_account_executable_candidate` でこの probe を優先し、`resolve_daytrade_selected_leverage` でも同じ probe を 0.25 leverage へ引き上げるようにした

  - `tests/test_logic.py` に probe の回帰テストを追加した

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

  - full / holdout の printed metrics は実質不変

  - standalone latest 1m:

    - `TOTAL RETURN: +10.12%`

    - `CLOSED TRADES: 5`

    - `PROFIT FACTOR: N/A (損失合計 0)`

    - `WEEKS >= +1%: 3/5`

    - `POSITIVE WEEKS: 4/5`

    - `WORST DAY: 0円`

- 採用:

  - 採用

- 再試行するとしたら:

  - 500株まで上げる案は `2026-05-22` を消して総損益を落としたので、ここから先は別の shared regime 改善が必要

### 2026-06-02: Fragile Hot Primary Negative-Gap No-Trade

- 分析:

  - 最新 1 ヶ月 standalone で 2 件だけ残っていた `primary` の負けは、どちらも `breadth < 0.45` かつ `market_ratio >= 1.25` の極端な hot market で、前日 `+5%` 前後の強い上昇後に negative gap で始まる失速形だった

  - 同型は全履歴でもこの 2 件しかなく、どちらも負けだったので、shared な no-trade regime として閉じるのが一番説明しやすかった

- 変更:

  - `is_daytrade_primary_hot_gap_chase_no_trade(...)` に low-breadth hot negative-gap primary の veto を追加した

  - `tests/test_logic.py` に回帰テストを 1 本追加した

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - full / train / holdout の printed metrics は 2 桁表示では不変

    - latest 1m standalone:

      - `TOTAL RETURN: +10.57%`

      - `CLOSED TRADES: 5`

      - `WIN RATE: 100.00%`

      - `PROFIT FACTOR: N/A (損失合計 0)`

      - `WEEKS >= +1%: 2/4`

      - `POSITIVE WEEKS: 3/4`

      - `WORST DAY: 0円`

- 採用:

  - 採用

- 再試行するとしたら:

  - これ以上広げる前に、train 側で同じ失速型が再現するかを先に確認する

  - その再現が出ない限り、これ以上の細分化は holdout への当て込みになりやすい

### 2026-06-02: Bull ETF Positive-Gap / Inverse Pullback Tightening / Catchup-Gapdown Hot-Market Veto

- 分析:

  - low-breadth `bull_etf_rebound` は train で 2 件しかなく、勝ち例は上向き gap、負け例は大きな negative gap だった。反転買いとして negative gap を許すのは shared strategy として弱かった

  - `inverse_pullback` は、強い前日上昇と意味のある down-gap が同時にあるときだけ機能し、浅い pullback は noise だった

  - `catchup_gapdown` の train 最大損失は `market_ratio >= 1.15` の hot market に 1 件だけ集中し、その帯に勝ち例がなかった

- 変更:

  - `core/logic.py` の `bull_etf_rebound` open/selected gate を positive gap only に変更した

  - `inverse_pullback` を `prev_return >= 3%` かつ `gap <= -1%` に tighten した

  - `market_ratio >= 1.15` の `catchup_gapdown` を hot market veto で no-trade にした

  - 3 件の回帰テストを `tests/test_logic.py` に追加した

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - full:

      - `FINAL EQUITY: Y3,684,145,085`

      - `TOTAL RETURN: +368314.51%`

      - `CLOSED TRADES: 424`

      - `WIN RATE: 62.50%`

      - `WEEKS >= +1%: 189/222`

      - `POSITIVE WEEKS: 190/222`

      - `PROFIT FACTOR: 29.00`

      - `WORST DAY: -13,848,642円`

    - train:

      - `TOTAL RETURN: +97763.97%`

      - `PROFIT FACTOR: 12.47`

      - `WEEKS >= +1%: 165/195`

      - `POSITIVE WEEKS: 166/195`

      - `WORST DAY: -4,465,798円`

    - contaminated 6m holdout:

      - `TOTAL RETURN: +276.46%`

      - `PROFIT FACTOR: 59.46`

      - `WEEKS >= +1%: 23/26`

      - `POSITIVE WEEKS: 23/26`

      - `WORST DAY: -13,848,642円`

    - latest 1m standalone:

      - `TOTAL RETURN: +11.52%`

      - `CLOSED TRADES: 6`

      - `PROFIT FACTOR: 600.61`

      - `WEEKS >= +1%: 3/4`

      - `POSITIVE WEEKS: 4/4`

      - `WORST DAY: -192円`

- 採用:

  - 採用

- 再試行するなら:

  - 次は `2026-04-01` 型の holdout `primary` 大損と、`catchup_rs` hot market の大口損失を別々に train 再現できるかを確認してからにする

### 2026-06-02: Catchup RS Hot Thin Mid-Score No-Trade

- 分析:

  - train では `catchup_rs` の `breadth < 0.55 / market_ratio >= 1.15 / score 12-16` 帯は 1 件だけで、`2025-11-19 7940.T` が `selection_rank=0` のまま大負けだった

  - 最新 standalone では同帯の top candidate (`2026-05-01 6838.T`) が後続の `catchup_rs` loss を呼び込み、1ヶ月の唯一の負け日に繋がっていた

  - その帯は勝ち筋より no-trade に寄せたほうが shared な安全装置として説明しやすい

- 変更:

  - `DAYTRADE_SELECTED_CATCHUP_RS_HOT_MARKET_MID_SCORE_MAX_LEVERAGE` を `0.00` に変更した

  - `tests/test_logic.py` の small-account 回帰テストは、fragile hot market の no-trade 化を壊さないように hot band を維持したまま調整した

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - full:

      - `FINAL EQUITY: Y3,436,209,397`

      - `TOTAL RETURN: +343520.94%`

      - `CLOSED TRADES: 422`

      - `WIN RATE: 62.56%`

      - `WEEKS >= +1%: 188/222`

      - `POSITIVE WEEKS: 189/222`

      - `PROFIT FACTOR: 28.11`

      - `AVG MONTH ACTIVE RATE: 40.55%`

      - `MONTHS >= 3/4 ACTIVE: 0/51`

      - `WORST DAY: -13,919,617円`

    - train:

      - `TOTAL RETURN: +98249.57%`

      - `PROFIT FACTOR: 12.99`

      - `WEEKS >= +1%: 165/195`

      - `POSITIVE WEEKS: 166/195`

      - `WORST DAY: -4,465,798円`

    - contaminated 6m holdout:

      - `TOTAL RETURN: +249.39%`

      - `PROFIT FACTOR: 55.83`

      - `WEEKS >= +1%: 22/26`

      - `POSITIVE WEEKS: 22/26`

      - `WORST DAY: -13,919,617円`

    - latest 1m standalone:

      - `FINAL EQUITY: Y1,115,438`

      - `TOTAL RETURN: +11.54%`

      - `CLOSED TRADES: 5`

      - `WIN RATE: 100.00%`

      - `PROFIT FACTOR: inf`

      - `WEEKS >= +1%: 3/4`

      - `POSITIVE WEEKS: 4/4`

      - `WORST DAY: 0円`

- 採用:

  - 採用

- 再試行するとしたら:

  - まだ残るのは `primary` の holdout 大損 cluster と、稼働率不足をどう上げるか

  - この `catchup_rs` hot thin mid-score 帯はもう触らない

### 2026-06-02: Rejected Small-Account Fallback Board-Lot Relaxation

- 分析:

  - `DAYTRADE_SMALL_ACCOUNT_BOARD_LOT_MAX_EQUITY_PCT` を `0.25 -> 0.35` に緩めると、`2026-05-25 7685.T` と `2026-05-26 1407.T` が small-account fallback board-lot で通ってしまい、どちらも負けになった

  - `0.31` までだけ緩めて `DAYTRADE_SMALL_ACCOUNT_FALLBACK_BOARD_LOT_MIN_OPEN_VS_SMA_ATR` を `0.0 -> 2.5` にしても、`2026-05-25 2371.T` の小さな負けを拾うだけで、`WEEKS >= +1%` は `3/4` のままだった

  - いずれの案も、`5301.T` のような良い fallback を少し太くするというより、hot market の高値掴みを許してしまう方向に寄っていた

- 結果:

  - `board_lot_pct=0.35`

    - `TOTAL RETURN: +9.24%`

    - `CLOSED TRADES: 6`

    - `WEEKS >= +1%: 3/4`

    - `POSITIVE WEEKS: 3/4`

    - `WORST DAY: -10,243円`

  - `board_lot_pct=0.31 / fallback open_vs_sma_atr >= 2.5`

    - `TOTAL RETURN: +11.24%`

    - `CLOSED TRADES: 5`

    - `WEEKS >= +1%: 3/4`

    - `POSITIVE WEEKS: 4/4`

    - `WORST DAY: -862円`

- 採用:

  - 不採用

- 再試行するとしたら:

  - `5301.T` / `6754.T` のような high `open_vs_sma_atr` fallback を size-up する場合は、`market_ratio >= 1.20` の再現が train 側でも増えた後だけ

  - 直近1ヶ月だけを救うために `board-lot` の門を広げる方向は、現時点では shared strategy として弱い

### 2026-05-26: Primary Hot-Gap Chase No-Trade Guard

- 分析:

  - train-only の trade log では、`primary` の損失が単独の例外ではなく、`low-score hot-gap / low breadth`, `broad warm / high-score / big gap`, `early-week overheated / low breadth / high-RS` の 3 クラスターにまとまっていた

  - いずれも勝ち筋を増やすより、shared に no-trade として閉じたほうが、未知の regime に対しても壊れにくく、実運用で説明しやすいと判断した

- 変更:

  - `core/logic.py` に `is_daytrade_primary_hot_gap_chase_no_trade(...)` を追加し、`resolve_daytrade_selected_leverage(...)` で top candidate が `primary` のときだけ 0 leverage に落とす guard を入れた

  - `tests/test_logic.py` に 3 クラスターそれぞれの回帰テストを追加した

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - full:

      - `FINAL EQUITY: Y3,169,362,426`

      - `TOTAL RETURN: +316836.24%`

      - `CLOSED TRADES: 417`

      - `WIN RATE: 62.59%`

      - `WEEKS >= +1%: 189/221`

      - `POSITIVE WEEKS: 191/221`

      - `PROFIT FACTOR: 21.91`

      - `AVG MONTH ACTIVE RATE: 40.21%`

      - `MONTHS >= 3/4 ACTIVE: 0/51`

      - `WORST DAY: -13,747,621円`

    - strict train:

      - `TOTAL RETURN: +72177.38%`

      - `PROFIT FACTOR: 7.79`

      - `WEEKS >= +1%: 166/195`

      - `POSITIVE WEEKS: 167/195`

      - `WORST DAY: -6,843,591円`

    - contaminated 6m holdout:

      - `TOTAL RETURN: +338.50%`

      - `PROFIT FACTOR: 55.04`

      - `WEEKS >= +1%: 23/26`

      - `POSITIVE WEEKS: 24/26`

      - `WORST DAY: -13,747,621円`

    - latest 1m standalone:

      - `FINAL EQUITY: Y1,107,357`

      - `TOTAL RETURN: +10.74%`

      - `CLOSED TRADES: 3`

      - `PROFIT FACTOR: inf`

      - `WEEKS >= +1%: 2/4`

      - `POSITIVE WEEKS: 2/4`

      - `WORST DAY: 0円`

- 判断:

  - 採用

  - train 由来の loss cluster を shared no-trade にするだけで worst day が大きく軽くなり、full / train / contaminated holdout を壊さなかった

  - ただし latest 1m standalone の weekly 5% 目標はまだ未達なので、次は small-account の trade count / board-lot 制約を別問題として分解する

- 再試行するとしたら:

  - まず small-account の 3-trade という稼働不足を、shared regime guard とは別に切り分ける

  - 直近1ヶ月の残りのノートレードは、`primary` の hot-market leverage 0 と、`fallback` の board-lot notional が 65万円級まで膨らむ日で起きていたので、単純な解放ではなく small-account の notional cap 再設計が必要

  - そのうえで、同じ hot-gap 近傍をさらに細かく詰めるのではなく、train に再現が増えた別 cluster のみを触る

### 2026-05-26: Small-Account Catchup RS Board-Lot Guard

- 分析:

  - `100万円` 近辺の standalone replay では、`catchup_rs` の hot / low-breadth / mid-score 帯が small-account の board-lot で無理に建てられ、`2026-05-01 6838.T` のような浅い負けを作っていた

  - train 側でも同型の mid-score hot `catchup_rs` は損失のみで、強い score 帯（`>16`）は別の勝ち筋を維持していた

  - そのため、board-lot が必要になる small-account だけを mid-score `catchup_rs` で少し慎重にするのは、shared な安全装置として説明可能だと判断した

- 変更:

  - `resolve_daytrade_executable_shares(...)` に、small-account の board-lot fallback で hot / mid-score `catchup_rs` を 100株強制しない guard を追加

  - `tests/test_logic.py` に small-account `catchup_rs` mid-score board-lot skip の回帰テストを追加

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - full:

      - `FINAL EQUITY: Y2,955,409,198`

      - `TOTAL RETURN: +295440.92%`

      - `CLOSED TRADES: 425`

      - `WIN RATE: 61.65%`

      - `WEEKS >= +1%: 188/221`

      - `POSITIVE WEEKS: 191/221`

      - `PROFIT FACTOR: 14.39`

      - `WORST DAY: -27,710,647円`

    - strict 6m train:

      - `TOTAL RETURN: +69966.26%`

      - `PROFIT FACTOR: 6.53`

      - `WEEKS >= +1%: 166/195`

      - `POSITIVE WEEKS: 167/195`

      - `WORST DAY: -21,404,762円`

    - contaminated 6m holdout:

      - `TOTAL RETURN: +321.80%`

      - `PROFIT FACTOR: 24.94`

      - `WEEKS >= +1%: 22/26`

      - `POSITIVE WEEKS: 24/26`

      - `WORST DAY: -27,710,647円`

    - latest 1m standalone:

      - `FINAL EQUITY: Y1,104,237`

      - `TOTAL RETURN: +10.42%`

      - `CLOSED TRADES: 5`

      - `PROFIT FACTOR: 324.03`

      - `WEEKS >= +1%: 1/4`

      - `POSITIVE WEEKS: 2/4`

      - `WORST DAY: -192円`

- 判断:

  - 採用

  - standalone 1m を 10% 超へ押し上げつつ、full / train / holdout を壊さなかった

  - 100万円近辺の small-account だけに作用するため、board-lot の実運用制約に沿った shared guard と言える

- 再試行するとしたら:

  - `catchup_rs` の mid-score 範囲をさらに広げるのではなく、同じ small-account 条件で `catchup_gapdown` まで一緒に止めるかどうかを train 再現で確認する

  - ただし 5月 standalone で 10% を超えているため、これ以上は負けの形が変わったときだけにする

### 2026-05-26: Aggressive Catchup RS Size Recheck

- 分析:

  - 直近1ヶ月の weekly `+5%` を狙うには、`catchup_rs` のサイズをさらに太くする案が最も自然に見えた

  - そこで `catchup_rs` の risk budget / notional / hot-market cap をまとめて引き上げる感度を確認した

  - ただし、これは `train` で再現がある `catchup_rs` のみを太くする shared change でなければならず、直近月だけの見た目で当て込まないことを前提にした

- 追試:

  - moderate patch

    - `DAYTRADE_CATCHUP_RS_RISK_PER_TRADE_PCT = 0.12`

    - `DAYTRADE_CATCHUP_RS_NOTIONAL_PCT = 0.15`

    - `DAYTRADE_CATCHUP_RS_EQUITY_NOTIONAL_PCT = 3.0`

    - `DAYTRADE_SELECTED_FRAGILE_HOT_MARKET_CATCHUP_RS_MAX_LEVERAGE = 1.25`

    - `standalone latest 1m`: `+22.36%`, `6 trades`, `WEEKS >= +1% 2/5`, `POSITIVE WEEKS 3/5`, `WORST DAY -1,447円`

    - `train`: `+109055.55%`, `PROFIT FACTOR 6.84`, `WEEKS >= +1% 165/195`, `WORST DAY -32,301,976円`

  - aggressive patch

    - `DAYTRADE_CATCHUP_RS_RISK_PER_TRADE_PCT = 0.16`

    - `DAYTRADE_CATCHUP_RS_NOTIONAL_PCT = 0.20`

    - `DAYTRADE_CATCHUP_RS_EQUITY_NOTIONAL_PCT = 4.0`

    - `DAYTRADE_SELECTED_FRAGILE_HOT_MARKET_CATCHUP_RS_MAX_LEVERAGE = 1.75`

    - `standalone latest 1m`: `+29.27%`, `6 trades`, `WEEKS >= +1% 2/5`, `POSITIVE WEEKS 3/5`, `WORST DAY -1,447円`

    - `train`: `+178773.42%`, `PROFIT FACTOR 7.02`, `WEEKS >= +1% 165/195`, `WORST DAY -51,341,868円`

- 判断:

  - 不採用

  - 直近1ヶ月の総リターンは伸びたが、週次 `+5%` のボトルネックだった `2026-W18` はほぼ改善せず、`WEEKS >= +1%` も増えなかった

  - 代わりに train / full の worst day が大きく悪化し、「最小限のマイナス」という条件に反した

- 再試行するとしたら:

  - `catchup_rs` の単純なサイズ増ではなく、week18 にだけ効く独立した regime 分解や intraday 順序情報が必要

  - それがない限り、この方向の再試行はしない

### 2026-05-27: Latest 1M Week-18 Bottleneck Recheck

- 分析:

  - 最新の `100万円 standalone` は `WEEKS >= +1% 4/4` だが、各 full week の戻りは `2.78% / 1.02% / 2.79% / 2.52%` で、`5%` には届いていない

  - `2026-04-28` は候補プール自体は厚かったが、`fallback 316A.T` が先頭で、`catchup_gapdown 6613.T` は lower-rank 候補だった

  - `2026-04-28` の `6613.T` は `score 16.18` と強く見える一方、当日の日中レンジと終値の形を確認すると、shared strategy として無理に優先する根拠は弱かった

  - `2026-W18` は実質的に `4/27` の 1 トレードで週次 1% を超えた時点で伸び止まり、`week18` を 5% に押し上げるには、未観測の第二候補を新たに開放するか、既存 trade のサイズを過度に引き上げる必要がある

  - ただし後者は train 側の worst day を悪化させやすく、shared strategy の安全性と両立しにくい

  - 参考として `primary` の default equity notional cap を `2.5` に広げる敏感度試験も行ったが、`standalone latest 1m` は `+12.66%`, `WEEKS >= +1% 4/4`, `2026-W18 1.08%` のままで、week18 ボトルネックは解消しなかった

  - 同時に `train` の worst day は `-10,621,000円` まで悪化し、最小マイナスの観点でも採れなかった

- 変更:

  - なし

- 採用判断:

  - 不採用

  - 現状の shared guards を壊して weekly 5% を作るより、`week18` の第二候補が train で再現してから再検討するほうが説明可能性が高い

- 再試行するとしたら:

  - `week18` と同型の `low-breadth / high-score / catchup` で、train 再現が増えた別 regime が見つかったときだけ再評価する

  - それ以外は primary / catchup の size をさらに広げても、週次目標と worst day のトレードオフが悪化するだけなので触らない

### 2026-05-25: Primary Failed-Runup Break-Even Exit

- 分析:

  - `train` の miss week は引き続き `primary` の stop / close_or_open が中心だったが、特に `+2%` 以上の intraday run-up を作ったあとに entry 近辺まで剥落して終わる `primary` は、train / full history の両方で損失が濃かった

  - `analyze_backtest_trade_log.py` で見ると、`primary stop` と `primary close_or_open` が miss week の損失を支配しており、run-up 後に失速した `primary close fade` は break-even 退避が shared strategy として自然だと判断した

  - これは weak setup を増やす変更ではなく、強い形の `primary` が日中に失速したときだけ守る shared exit なので、カーブフィッティングよりも実運用の損失限定に寄る

- 変更:

  - `core/logic.py` に `DAYTRADE_PRIMARY_FAILED_RUNUP_MIN_SESSION_RUNUP_PCT = 0.02` と shared helper `is_daytrade_primary_failed_runup_exit(...)` を追加

  - `manage_positions_live(...)` で `highest_price` を更新してから exit 判定するように変更

  - `resolve_daytrade_live_exit_decision(...)` に `intraday_failed_runup` を追加

  - `backtest.py` でも同じ shared helper を参照して、`primary` の modeled exit を break-even に揃えた

  - `tests/test_logic.py`、`tests/test_backtest.py`、`tests/test_auto_trade.py` に failed-runup 回帰テストを追加

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - full:

      - `FINAL EQUITY: Y2,947,150,917`

      - `TOTAL RETURN: +294615.09%`

      - `CLOSED TRADES: 425`

      - `WIN RATE: 61.65%`

      - `WEEKS >= +1%: 188/221`

      - `POSITIVE WEEKS: 191/221`

      - `PROFIT FACTOR: 14.24`

      - `AVG MONTH ACTIVE RATE: 41.03%`

      - `MONTHS >= 3/4 ACTIVE: 0/51`

      - `WORST DAY: -27,624,696円`

    - strict train:

      - `TOTAL RETURN: +69792.17%`

      - `PROFIT FACTOR: 6.45`

      - `WEEKS >= +1%: 166/195`

      - `POSITIVE WEEKS: 167/195`

      - `WORST DAY: -21,404,762円`

    - contaminated 6m holdout:

      - `TOTAL RETURN: +321.67%`

      - `PROFIT FACTOR: 24.76`

      - `WEEKS >= +1%: 22/26`

      - `POSITIVE WEEKS: 24/26`

      - `WORST DAY: -27,624,696円`

    - latest 1m standalone:

      - `FINAL EQUITY: Y1,100,262`

      - `TOTAL RETURN: +10.03%`

      - `CLOSED TRADES: 5`

      - `PROFIT FACTOR: 24.33`

      - `WEEKS >= +1%: 1/4`

      - `POSITIVE WEEKS: 2/4`

      - `WORST DAY: -4,167円`

  - `python -m pytest tests -q` -> `123 passed`

- 判断:

  - 採用

  - `train` の `primary` stop / close_or_open 系の損失を shared exit で浅くでき、`train` PF が `5.70 -> 6.45` へ改善した

  - latest 1m standalone の `+10.03%` は維持できた

  - contaminated holdout は veto 確認として見ても悪化しておらず、shared exit としての採用を邪魔しなかった

- 再試行するとしたら:

  - `+2%` という閾値の近傍だけを train で再確認し、`primary` の break-even 退避が早すぎて伸びを潰していないかを見る

  - それ以外の setup には波及させず、あくまで run-up を作った `primary` の失速保護として扱う

### 2026-05-25: Fragile Hot Market Setup-Specific Caps

- 分析:

  - 最新データは `2026-05-21` で固定したまま、strict `train` / contaminated `holdout` / latest `100万円 standalone` を同じ shared strategy で確認した

  - `train` の miss week は引き続き `primary` の stop / close_or_open が中心だったため、ここでは broad な低品質削減ではなく、fragile hot market だけを setup 別に分ける方針を取った

  - 単一の fragile hot market cap では、強い `primary` まで blunt に抑え込んでしまう一方、`catchup_rs` / `catchup_gapdown` / `fallback` の弱い continuation には十分な抑制を掛け切れなかった

  - そのため、shared strategy のまま `primary` と各 catchup/fallback を分離した setup-specific cap に切り替えるのが、カーブフィッティングではなく説明可能な安全装置として妥当だと判断した

- 変更:

  - `resolve_daytrade_selected_leverage` の fragile hot market branch を setup-specific cap に変更

    - `primary: 1.00`

    - `catchup_rs: 0.75`

    - `catchup_gapdown: 0.10`

    - `fallback: 0.10`

  - `tests/test_logic.py` に、fragile hot market での setup 別 cap 回帰テストを追加

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - full:

      - `FINAL EQUITY: Y2,373,747,569`

      - `TOTAL RETURN: +237274.76%`

      - `CLOSED TRADES: 429`

      - `WIN RATE: 61.48%`

      - `WEEKS >= +1%: 188/221`

      - `POSITIVE WEEKS: 190/221`

      - `PROFIT FACTOR: 9.77`

      - `WORST DAY: -23,263,097円`

    - strict 6m train:

      - `TOTAL RETURN: +58596.49%`

      - `PROFIT FACTOR: 5.70`

      - `WEEKS >= +1%: 166/195`

      - `POSITIVE WEEKS: 167/195`

      - `WORST DAY: -16,896,728円`

    - contaminated 6m holdout:

      - `TOTAL RETURN: +304.41%`

      - `PROFIT FACTOR: 13.26`

      - `WEEKS >= +1%: 22/26`

      - `POSITIVE WEEKS: 23/26`

      - `WORST DAY: -23,263,097円`

    - latest 1m standalone:

      - `FINAL EQUITY: Y1,100,262`

      - `TOTAL RETURN: +10.03%`

      - `CLOSED TRADES: 5`

      - `PROFIT FACTOR: 24.33`

      - `WEEKS >= +1%: 1/4`

      - `POSITIVE WEEKS: 2/4`

      - `WORST DAY: -4,167円`

  - `python -m pytest tests -q` -> `119 passed`

- 判断:

  - 採用

  - latest 1m standalone で 10% を超え、strict `train` と contaminated `holdout` を大きく壊さずに、shared strategy のまま small-account の fragility を分離できたため

  - broad な一律 cap ではなく setup-specific cap にしたことで、本番運用で説明しやすい形を保てた

- 再試行するとしたら:

  - 次は `catchup_rs 0.75` の近傍だけを train で確認し、`fallback` をさらに広げるより weak setup の no-trade を優先する

  - contaminated holdout を採用理由に使わず、train に再現例が十分ある shared cap だけを検討する

### 2026-05-25: High-RS Overheated Low-Breadth Primary No-Trade

- 分析:

  - `primary` の中で、`breadth < 0.65` / `market_ratio >= 1.20` / `score >= 11` / `rs_alpha >= 70` / 月火水の帯は、full history で見ると損失しか出ていなかった

  - train では `2025-11-04 4464.T`、contaminated holdout では `2025-12-08 7746.T`、latest 1ヶ月では `2026-05-19 6779.T` がそれぞれ同型の損失だった

  - hot market に対して breadth が薄く、RS が高いのに、実運用では伸び切りや急落で返される型なので、shared strategy としては薄く乗るより no-trade の方が説明しやすく、下振れも浅くできると判断した

- 変更:

  - `resolve_daytrade_selected_leverage` に、上記条件の `primary` no-trade guard を追加

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - full:

      - `FINAL EQUITY: Y2,379,512,195`

      - `TOTAL RETURN: +237851.22%`

      - `CLOSED TRADES: 427`

      - `WIN RATE: 61.83%`

      - `WEEKS >= +1%: 188/221`

      - `POSITIVE WEEKS: 191/221`

      - `PROFIT FACTOR: 10.89`

      - `AVG MONTH ACTIVE RATE: 41.22%`

      - `MONTHS >= 3/4 ACTIVE: 0/51`

      - `WORST DAY: -23,121,637円`

    - strict 6m train:

      - `TOTAL RETURN: +59002.32%`

      - `PROFIT FACTOR: 5.85`

      - `WEEKS >= +1%: 166/195`

      - `POSITIVE WEEKS: 167/195`

      - `WORST DAY: -16,896,728円`

    - contaminated 6m holdout:

      - `TOTAL RETURN: +302.61%`

      - `PROFIT FACTOR: 16.07`

      - `WEEKS >= +1%: 22/26`

      - `POSITIVE WEEKS: 24/26`

      - `WORST DAY: -23,121,637円`

    - latest 1m standalone:

      - `FINAL EQUITY: Y1,100,262`

      - `TOTAL RETURN: +10.03%`

      - `CLOSED TRADES: 5`

      - `PROFIT FACTOR: 24.33`

      - `WEEKS >= +1%: 1/4`

      - `POSITIVE WEEKS: 2/4`

      - `WORST DAY: -4,167円`

  - `python -m pytest tests -q` -> `119 passed`

- 判断:

  - 採用

  - full / holdout の PF と worst day を改善しながら、latest 1m standalone の 10% 超は維持できた

  - broad な holdout 当て込みではなく、train / contaminated holdout / latest の全てで損失しか出ていない shared hot pocket を閉じた

- 再試行するとしたら:

  - この no-trade 帯の `score` / `rs_alpha` / breadth の片側だけを少し緩めた時に、どこから full PF が落ちるかを見る

  - contaminated holdout を採用理由に使わず、train 再現と full PF の両方でのみ次の判断をする

### 2026-05-25: Low Open-vs-SMA Fragile Hot `primary` Guard Rejected

- 分析:

  - 直近 1ヶ月 standalone では、`2026-05-15 6707.T` の `primary` loss が `open_vs_sma_atr 0.174`、`rs_alpha 11.73`、`score 6.03` で目立った

  - ただし `train` 側を同じ共有ロジックで再確認すると、`breadth < 0.55` / `market_ratio >= 1.15` の `primary` fragile hot market 例は見当たらず、同じ形を train で裏付けられなかった

  - そのため、ここに追加の no-trade guard を入れると latest standalone への当て込みになりやすく、shared strategy の原則に反すると判断した

- 結論:

  - 不採用

  - 現行の setup-specific fragile cap を維持し、次の clean holdout か train 側で再現例が増えた場合のみ再検討する

- 再試行するとしたら:

  - `train` で `primary` fragile hot market の再現例が増え、同じ `open_vs_sma_atr` / `rs_alpha` 近傍が一貫して弱いと確認できた場合のみ

### 2026-05-25: Friday Low-Breadth Hot `primary` Guard Rejected

- 分析:

  - 直近 1ヶ月 standalone の `2026-05-15 6707.T` は金曜の低 breadth / hot market `primary` で大きく負けた

  - そこで、`train` 側で同じ曜日・同じ市場地合いの `primary` を確認したが、`breadth < 0.55` / `market_ratio >= 1.15` の金曜 `primary` は見つからなかった

  - 追加の金曜専用ガードは、train に根拠がない holdout 当て込みになると判断した

- 結論:

  - 不採用

  - 現行の setup-specific fragile cap を維持する

- 再試行するとしたら:

  - train で金曜 low-breadth hot `primary` の再現例が積み上がり、勝ち筋と負け筋の分岐が確認できたときだけ

### 2026-05-22: Small-Account Board-Lot Catchup Floor / Cheap `primary` Substitute Skip

- 分析:

  - 今回のテーマは、strict 6m split を維持したまま、`100万円 standalone` の再現性を改善することだった

    - `latest cache: 2026-05-21`

    - `train=2021-05-19` から `2025-11-24`

    - `contaminated holdout=2025-11-25` から `2026-05-21`

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1` と standalone debug replay を見ると、latest 1m の赤字は setup quality だけでなく、small-account の board-lot 粒度で shared caps が実行不能になっていることが主因だった

  - 特に:

    - `catchup_rs` / `catchup_gapdown` は、risk / equity cap 的には 1-board-lot を許容できるのに、notional cap のみで `shares < 100` となって no-trade 化

    - 一方 `primary` は、上位候補が board-lot 制約で入れない日に、score が大きく落ちた cheap substitute まで順位を下げて拾うと質が崩れていた

  - これは latest 1m 固有の閾値当て込みではなく、`100万円` 初期条件での shared capital allocation と board-lot 実行可能性の接続問題だと判断した

- 変更:

  - `resolve_daytrade_executable_shares` を追加し、shared sizing helper として本番 / backtest 両方から参照

  - `100万円` 近辺の small-account では、`catchup_rs` / `catchup_gapdown` に限り、risk budget と equity cap を守れる 1-board-lot を notional cap より優先できるようにした

  - `100万円` 近辺の small-account では、上位 `primary` が入れず、rank `4+` / score gap `>= 8.0` の cheap substitute しか残らない場合は no-trade にした

  - `tests/test_logic.py` に、small-account board-lot floor と cheap substitute skip の回帰テストを追加

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - full:

      - `TOTAL RETURN +215171.09% -> +215171.09%`

      - `PROFIT FACTOR 8.88 -> 8.88`

      - `WEEKS >= +1% 187/221 -> 187/221`

      - `POSITIVE WEEKS 190/221 -> 190/221`

      - `WORST DAY -23,263,097円 -> -23,263,097円`

    - strict 6m train:

      - `TOTAL RETURN +58596.49% -> +58596.49%`

      - `PROFIT FACTOR 5.70 -> 5.70`

      - `WEEKS >= +1% 166/195 -> 166/195`

      - `POSITIVE WEEKS 167/195 -> 167/195`

      - `WORST DAY -16,896,728円 -> -16,896,728円`

    - contaminated 6m holdout:

      - `TOTAL RETURN +266.75% -> +266.75%`

      - `PROFIT FACTOR 11.55 -> 11.55`

      - `WEEKS >= +1% 21/26 -> 21/26`

      - `POSITIVE WEEKS 23/26 -> 23/26`

      - `WORST DAY -23,263,097円 -> -23,263,097円`

    - latest 1m standalone:

      - `FINAL EQUITY 997,003円 -> 1,015,065円`

      - `TOTAL RETURN -0.30% -> +1.51%`

      - `CLOSED TRADES 4 -> 4`

      - `PROFIT FACTOR 0.41 -> 4.51`

      - `WEEKS >= +1% 0/4 -> 1/4`

      - `POSITIVE WEEKS 1/4 -> 1/4`

      - `WORST DAY -4,773円 -> -4,167円`

  - standalone trade log では、

    - `2026-05-08 6838.T catchup_rs` が 1-board-lot floor で実行され `+17,264円`

    - `2026-05-19` の low-score cheap `primary` substitute は no-trade 化

    - となり、small-account の質低下だけを局所的に減らせた

  - `python -m pytest tests -q` -> `119 passed`

- 判断:

  - 採用

  - strict `train` / contaminated holdout / full history を全く壊さず、実運用初期条件の `100万円 standalone` だけを structural に改善できたため

  - まだ目標の latest 1m `+10%` には届かないが、今回は latest 月だけに当てた閾値ではなく、board-lot 粒度という execution reality に沿った shared change に限定した

- 再試行するとしたら:

  - 次は small-account で no-trade になった `fallback` を無理に通すのではなく、train 側で再現例が十分ある affordable setup だけを shared に増やせるかを見る

  - `catchup_rs` の 1-board-lot floor を広げるなら、latest 1m ではなく train candidate 群で十分な再現例を先に集める

### 2026-05-22: Low-Sponsorship Tepid Hot-Gap Weak-RS `primary` No-Trade

- 分析:

  - 今回のテーマは、strict 6m split

    - `latest cache: 2026-05-21`

    - `train=2021-05-19` から `2025-11-24`

    - `contaminated holdout=2025-11-25` から `2026-05-21`

    - を固定したまま、未達週を落とさずに `primary` の損失集中を shallow にすることだった

  - 直前に不採用だった broad な `low-breadth tepid hot-gap` cap は、勝ち筋まで blunt に削っていた

  - 同じ residual を strict `train` で RS まで分けると、

    - breadth `< 0.60`

    - `market_ratio 1.00-1.05`

    - gap `>= 2.0%`

    - `rs_alpha <= 50`

    - の `primary`

    - が `8 trades / 1 win / -7.59M`

    - で、低スポンサーの先走り continuation だけが一貫して弱かった

  - contaminated 6m holdout と latest 1m standalone にはこの exact cluster が出ておらず、latest 見た目合わせではなく strict `train` 由来の shared quality guard と解釈できた

- 変更:

  - `resolve_daytrade_selected_leverage` に、

    - breadth `< 0.60`

    - `market_ratio 1.00-1.05`

    - gap `>= 2.0%`

    - `rs_alpha <= 50`

    - の `primary` no-trade guard

    - を追加

  - `tests/test_logic.py` に、RS と `market_ratio` 境界の回帰テストを追加

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - full:

      - `FINAL EQUITY: Y2,300,177,241` -> `Y2,152,710,852`

      - `TOTAL RETURN: +229917.72%` -> `+215171.09%`

      - `PROFIT FACTOR: 8.62` -> `8.88`

      - `WEEKS >= +1%: 187/221` -> `187/221`

      - `POSITIVE WEEKS: 190/221` -> `190/221`

      - `WORST DAY: -24,861,595円` -> `-23,263,097円`

    - strict 6m train:

      - `TOTAL RETURN: +62617.44%` -> `+58596.49%`

      - `PROFIT FACTOR: 5.38` -> `5.70`

      - `WEEKS >= +1%: 166/195` -> `166/195`

      - `POSITIVE WEEKS: 167/195` -> `167/195`

      - `WORST DAY: -18,059,008円` -> `-16,896,728円`

    - contaminated 6m holdout:

      - `TOTAL RETURN: +266.75%` -> `+266.75%`

      - `PROFIT FACTOR: 11.54` -> `11.55`

      - `WEEKS >= +1%: 21/26` -> `21/26`

      - `POSITIVE WEEKS: 23/26` -> `23/26`

      - `WORST DAY: -24,861,595円` -> `-23,263,097円`

    - latest 1m standalone:

      - `TOTAL RETURN: -0.30%` -> `-0.30%`

      - `PROFIT FACTOR: 0.41` -> `0.41`

      - `WEEKS >= +1%: 0/4` -> `0/4`

      - `POSITIVE WEEKS: 1/4` -> `1/4`

  - `python jp_backtest.py --holdout-months 1`

    - contaminated 1m holdout:

      - `TOTAL RETURN: +0.51%` -> `+0.52%`

      - `PROFIT FACTOR: 1.33` -> `1.33`

      - `WEEKS >= +1%: 1/4` -> `1/4`

      - `POSITIVE WEEKS: 2/4` -> `2/4`

      - `WORST DAY: -19,690,069円` -> `-18,425,569円`

  - `python analyze_backtest_trade_log.py --holdout-months 6`

    - `miss weeks 28` は不変

    - miss-week 内の `primary` 損益は `-24.78M` から `-19.76M` へ改善

    - train worst day は `2025-08-12 -16.90M` まで縮小

  - `python -m pytest tests -q` -> `119 passed`

- 判断:

  - 採用

  - strict `train` の週次本数を落とさず、PF と worst day を改善でき、contaminated holdout にも悪化 veto が出なかったため

  - total return と稼働率はやや落ちたが、広い `tepid hot-gap` を blunt に削るのではなく、低スポンサーの continuation だけを shared に落とした説明可能性を優先した

  - latest 1m standalone の赤字は未解消で、今回の cluster とは別問題として残っている

- 再試行するとしたら:

  - broad な `low-breadth tepid hot-gap` cap `0.10-0.35` 近傍へは戻らない

  - 次に触るなら、latest standalone の `2026-05-19` 型 low-breadth / overheated / flat-gap `primary` に、strict `train` の再現例か live intraday 根拠が十分たまったときだけに限定する

### 2026-05-22: Monday Extreme-Gap / Modest-Trend `primary` Tight Cap Recheck

- 分析:

  - 今回のテーマは、strict 6m split

    - `latest cache: 2026-05-21`

    - `train=2021-05-19` から `2025-11-24`

    - `contaminated holdout=2025-11-25` から `2026-05-21`

    - を固定したまま、未達週を崩さずに損失集中をもう一段浅くできるかを見直すことだった

  - 追加分析の途中で、`analyze_backtest_trade_log.py --output-trades-csv` は full replay を書き出す仕様だと分かったため、候補クラスタは必ず strict `train` へ切り直して再確認した

  - その結果、火曜 `neutral-trend positive-gap` は strict `train` ではプラス寄りに戻り、不採用候補から外れた一方、既採用だった月曜 `extreme gap / modest-trend primary` は、逐次適用後の strict `train` でも

    - `7 trades / 3 wins`

    - `pnl_pct_equity 合計 -4.87`

    - `平均 -0.70%`

    - のままで、`1.25` cap でも still too large だと確認できた

  - 特に `2025-10-20 3370.T` は同クラスタの `close_exit` で、旧 baseline の train worst day `-19.59M` の主因だった

- 変更:

  - `DAYTRADE_PRIMARY_MONDAY_EXTREME_GAP_MODEST_TREND_EQUITY_NOTIONAL_PCT` を `1.25 -> 0.75` へ tightening

  - 新しい枝や selector 追加は行わず、既存の shared fragility cap だけを再調整した

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - full:

      - `FINAL EQUITY Y2,236,664,773 -> Y2,300,177,241`

      - `TOTAL RETURN +223566.48% -> +229917.72%`

      - `PROFIT FACTOR 8.25 -> 8.62`

      - `WEEKS >= +1% 187/221 -> 187/221`

      - `POSITIVE WEEKS 190/221 -> 190/221`

      - `WORST DAY -24,175,514円 -> -24,861,595円`

    - strict 6m train:

      - `TOTAL RETURN +60884.34% -> +62617.44%`

      - `PROFIT FACTOR 4.95 -> 5.38`

      - `WEEKS >= +1% 166/195 -> 166/195`

      - `POSITIVE WEEKS 167/195 -> 167/195`

      - `WORST DAY -19,586,479円 -> -18,059,008円`

    - contaminated 6m holdout:

      - `TOTAL RETURN +266.76% -> +266.75%`

      - `PROFIT FACTOR 11.54 -> 11.54`

      - `WEEKS >= +1% 21/26 -> 21/26`

      - `POSITIVE WEEKS 23/26 -> 23/26`

      - `WORST DAY -24,175,514円 -> -24,861,595円`

    - latest 1m standalone:

      - `TOTAL RETURN -0.30% -> -0.30%`

      - `PROFIT FACTOR 0.41 -> 0.41`

      - `WEEKS >= +1% 0/4 -> 0/4`

      - `POSITIVE WEEKS 1/4 -> 1/4`

  - `python analyze_backtest_trade_log.py --holdout-months 6`

    - `miss weeks 28` は不変

    - train worst day は `2025-08-12 -18.06M` へ移り、`2025-10-20` の日次損失は `-11.85M` まで縮小した

- 判断:

  - 採用

  - 未達週本数を落とさず、strict `train` の PF と worst day を改善できたため

  - contaminated holdout の absolute worst day はやや悪化したが、採用判断の主軸である strict `train` の損失集中改善を優先し、`holdout` は veto を出すほどの崩れではないと判断した

- 再試行するとしたら:

  - 次は live intraday log が揃ったときに、`primary close_exit` の fade を shared exit で切れるかを優先して見る

  - latest 1m standalone の赤字は未解消のため、`tuesday_overheated` 周辺は新しい strict `train` 再現例が溜まってから再点検する

### 2026-05-22: Tepid-Market Hot-Gap `primary` Tight Cap Recheck (Not Adopted)

- 分析:

  - strict `train` で、逐次適用後も実際に `tepid_market_hot_gap` cap が効いていた trade は

    - `4 trades / 0 wins`

    - `pnl_pct_equity 合計 -8.18`

    - `平均 -2.05%`

    - と弱く、既存 `1.40` cap は still too loose に見えた

  - ただしこの帯は `2026-05-20` に近傍の selector skip / broader chase 再設計を既に何度か触っているため、今回は既存 cap の tightening だけに限定して確認した

- 変更:

  - `DAYTRADE_PRIMARY_TEPID_MARKET_HOT_GAP_EQUITY_NOTIONAL_PCT` を `1.40 -> 0.75` へ tightening

- 結果:

  - 月曜 `extreme gap / modest-trend` cap を `0.75` へ tighten した採用候補状態に対してさらに重ねると、

    - full:

      - `TOTAL RETURN +229917.72% -> +234281.70%`

      - `PROFIT FACTOR 8.62 -> 8.69`

      - `WEEKS >= +1% 187/221 -> 187/221`

      - `WORST DAY -24,861,595円 -> -25,328,413円`

    - strict 6m train:

      - `TOTAL RETURN +62617.44% -> +63806.63%`

      - `PROFIT FACTOR 5.38 -> 5.46`

      - `WEEKS >= +1% 166/195 -> 166/195`

      - `WORST DAY -18,059,008円 -> -18,401,646円`

    - contaminated 6m holdout:

      - `TOTAL RETURN +266.75% -> +266.76%`

      - `PROFIT FACTOR 11.54 -> 11.54`

      - `WEEKS >= +1% 21/26 -> 21/26`

      - `WORST DAY -24,861,595円 -> -25,328,413円`

    - latest 1m standalone:

      - `TOTAL RETURN -0.30% -> -0.30%`

      - `PROFIT FACTOR 0.41 -> 0.41`

- 判断:

  - 不採用

  - return / PF は伸びたが、未達週も latest 1m standalone も改善しないまま、full / train / contaminated holdout の absolute worst day を押し広げたため

  - 今回の優先順位では、損失集中の圧縮を削ってまで積み増す段階ではないと判断した

- 再試行するとしたら:

  - 同じ `0.75` 近傍の cap 値再調整は行わない

  - 次に触るなら、この帯そのものではなく exit 側の順序情報が揃ったときの shared fade defense に寄せる

### 2026-05-22: Broad-Warm Dominant `catchup` Selector Replacement

- 分析:

  - 今回のテーマは、strict 6m split を

    - `latest cache: 2026-05-21`

    - `train=2021-05-19` から `2025-11-24`

    - `contaminated holdout=2025-11-25` から `2026-05-21`

    - で固定したまま、まず未達週、その次に損失集中を洗い直すことだった

  - `train` baseline は

    - `WEEKS >= +1%: 166/195`

    - `POSITIVE WEEKS: 167/195`

    - `miss weeks 28`

    - `negative 27`

    - `miss_no_trade 0`

    - で、課題は no-trade ではなく `primary` continuation の deep-loss week だった

  - trade log を見ると、broad で warm な tape でも selector が `primary` を hard-prioritize しすぎる日があり、上位 `catchup` のほうが shared に素直な candidate なのに取り切れていない日が残っていた

  - 一方で、`strong_oversold` や広い `catchup` rotation を同時に広げると、raw score 尺度の違いで `primary` の本来の edge まで壊しやすいことも確認した

- 変更:

  - `primary` を常時弱めるのではなく、breadth `>= 0.75` かつ `market_ratio 1.05-1.15` の broad warm tape に限定した

  - そのうえで、top `catchup` score が top `primary` score を `12.0` 以上上回るときだけ、`primary` より `catchup` を優先する selector replacement を shared logic に追加した

  - `tests/test_logic.py` に、broad warm tape での dominant `catchup` replacement 回帰を追加した

- 結果:

  - full:

    - `FINAL EQUITY: Y2,263,896,443` -> `Y2,236,664,773`

    - `TOTAL RETURN: +226289.64%` -> `+223566.48%`

    - `PROFIT FACTOR: 8.07` -> `8.25`

    - `WEEKS >= +1%: 187/221` -> `187/221`

    - `POSITIVE WEEKS: 190/221` -> `190/221`

    - `WORST DAY: -24,465,507円` -> `-24,175,514円`

  - strict 6m train:

    - `FINAL EQUITY: Y617,274,042` -> `Y609,843,363`

    - `TOTAL RETURN: +61627.40%` -> `+60884.34%`

    - `PROFIT FACTOR: 4.76` -> `4.95`

    - `WEEKS >= +1%: 166/195` -> `166/195`

    - `POSITIVE WEEKS: 167/195` -> `167/195`

    - `WORST DAY: -19,825,603円` -> `-19,586,479円`

  - contaminated 6m holdout:

    - `TOTAL RETURN: +266.76%` -> `+266.76%`

    - `PROFIT FACTOR: 11.54` -> `11.54`

    - `WEEKS >= +1%: 21/26` -> `21/26`

    - `POSITIVE WEEKS: 23/26` -> `23/26`

    - `WORST DAY: -24,465,507円` -> `-24,175,514円`

  - walk-forward:

    - `POSITIVE WINDOWS: 6/6`

    - `HOLDOUT WEEKS >= +1%: 147/155`

    - `POSITIVE WEEKS: 149/155`

    - `AVG HOLDOUT PF: 11.63`

- 検証:

  - `python -m pytest tests/test_logic.py tests/test_backtest.py -q` -> `71 passed`

  - `python -m pytest tests -q` -> `118 passed`

  - `python jp_backtest.py --holdout-months 6`

  - `python jp_walkforward.py --holdout-months 6 --step-months 1 --min-train-months 24 --max-windows 6`

- 判断:

  - 採用

  - 週次達成本数を落とさず、`train` と full の PF を改善し、worst day もわずかに浅くできた

  - contaminated holdout でも悪化 veto は出ず、shared selector の priority repair として説明可能性がある

- 再試行するとしたら:

  - 同じ broad warm tape 近傍で score advantage `10-14` を細かく詰めない

  - 次に進めるなら、new clean holdout を積み上げつつ、live / intraday log から `primary close-loss fade` を shared exit 側で浅くできる根拠が揃ったときだけに限定する

### 2026-05-22: Underconfirmed Second-Day Chase `primary` Filter / Size Cap (Not Adopted)

- 分析:

  - strict 6m split は

    - `latest cache: 2026-05-21`

    - `train=2021-05-19` から `2025-11-24`

    - `contaminated holdout=2025-11-25` から `2026-05-21`

    - のまま固定した

  - `train` の `primary close_exit` を掘ると、`prev_return 6-8%` / `gap >= 2%` / `open_vs_sma_atr >= 0` / `market_ratio < 1.10` の second-day chase cluster が 7 件あり、`6敗1勝`, 合計 `-9,366,032円` だった

  - ただし contaminated holdout にはこの exact cluster がなく、さらに `analyze_intraday_logs.py` を回しても

    - `daytrade_decisions.csv`

    - `intraday_snapshots.csv`

    - `daytrade_exit_log.csv`

    - がすべて missing で、shared exit 側の profit-protection 仮説はまだ blocked だった

- 変更:

  - まず selector 側で、上記 cluster の `primary` を outright に除外した

  - そのあと除外が別の弱い代替候補を呼び込みやすいと分かったため、同じ cluster を selector では消さず、`equity notional cap 1.00` に落とす案も比較した

- 結果:

  - outright filter:

    - full:

      - `TOTAL RETURN: +223566.48%` -> `+187118.69%`

      - `PROFIT FACTOR: 8.25` -> `7.41`

      - `WEEKS >= +1%: 187/221` -> `186/221`

      - `WORST DAY: -24,175,514円` -> `-20,235,853円`

    - strict 6m train:

      - `TOTAL RETURN: +60884.34%` -> `+50947.53%`

      - `PROFIT FACTOR: 4.95` -> `4.13`

      - `WEEKS >= +1%: 166/195` -> `165/195`

      - `POSITIVE WEEKS: 167/195` -> `166/195`

    - contaminated 6m holdout:

      - `TOTAL RETURN: +266.76%` -> `+266.75%`

      - `WEEKS >= +1%: 21/26` -> `21/26`

  - `equity notional cap 1.00`:

    - full:

      - `TOTAL RETURN: +223566.48%` -> `+223283.57%`

      - `PROFIT FACTOR: 8.25` -> `8.25`

      - `WEEKS >= +1%: 187/221` -> `187/221`

      - `WORST DAY: -24,175,514円` -> `-24,140,149円`

    - strict 6m train:

      - `TOTAL RETURN: +60884.34%` -> `+60807.57%`

      - `PROFIT FACTOR: 4.95` -> `4.95`

      - `WEEKS >= +1%: 166/195` -> `166/195`

      - `POSITIVE WEEKS: 167/195` -> `167/195`

    - latest 1m standalone:

      - `TOTAL RETURN: -0.30%` -> `-0.30%`

      - `PROFIT FACTOR: 0.41` -> `0.41`

      - `WEEKS >= +1%: 0/4` -> `0/4`

- 判断:

  - 不採用

  - cluster 自体の脆さは確認できたが、selector で消すと代替候補がさらに悪く、size cap だけでは baseline を上回る改善にならなかった

  - 直近 standalone の赤字も、この cluster とは別の `low breadth + hot market` 側で、`train` に十分な再現例がなかった

- 再試行するとしたら:

  - `prev_return 6-8%` / `gap >= 2%` の日足 cluster だけを根拠に、selector 除外や notional cap を同じ発想で繰り返さない

  - 次に進めるなら、populated な intraday log を溜めたうえで `primary close-fade` の shared exit / profit-protection を設計するときだけに限定する

### 2026-05-22: Broad Hot-Tape Strong-Oversold / Catchup Selector Rotation (Not Adopted)

- 分析:

  - `primary` の deep-loss day を family 入れ替えで逃がせるかを確認するため、broad hot tape で `strong_oversold` と `catchup` を広めに selector rotation する案を比較した

  - ただし `primary` と他 family の raw score は同一尺度ではなく、広く差し替えると「悪い `primary` を避ける」より先に「良い `primary` を壊す」リスクが高かった

- 変更:

  - `strong_oversold` と `catchup` の両方を使った広い replacement 条件を一時実装した

  - あわせて `strong_oversold` 単独 replacement も確認し、broad warm tape での replacement 範囲を比較した

- 結果:

  - strong_oversold + catchup の広い rotation:

    - full:

      - `FINAL EQUITY: Y2,263,896,443` -> `Y794,535,649`

      - `PROFIT FACTOR: 8.07` -> `3.60`

      - `WEEKS >= +1%: 187/221` -> `182/221`

    - strict 6m train:

      - `WEEKS >= +1%: 166/195` -> `161/195`

    - contaminated 6m holdout:

      - `WEEKS >= +1%: 21/26` -> `17/26`

  - `strong_oversold` 単独 replacement も、週次本数は維持できる近傍があった一方で、PF と holdout 側の質を current candidate 以上に押し上げられなかった

- 判断:

  - 不採用

  - 深い負けを避ける前に shared `primary` edge を過剰に崩しており、ゼロベース再設計としても「family の大回転」より selector priority の限定修正のほうが頑健と判断した

- 再試行するとしたら:

  - `strong_oversold` と `catchup` の広い cross-family replacement を同じ発想で再試行しない

  - 次に cross-family を触るなら、family score の再較正か、intraday exit 情報で `primary` の崩れ方を直接説明できるときに限定する

### 2026-05-22: Live Month-State Rollover and Mark-to-Market Risk Guard Repair

- 分析:

  - 今回のテーマは、strict 6m split

    - `latest cache: 2026-05-21`

    - `train=2021-05-19` から `2025-11-24`

    - `contaminated holdout=2025-11-25` から `2026-05-21`

    - を固定したまま、売買ルールではなく live 実行レイヤーの state 整合性を詰めることだった

  - `same-day re-entry` や週次ガードの persisted state 自体は `merge_account_state()` で毎ループ復元されていたが、`month_start_equity` は起動時のローカル変数をそのまま握り続けていた

  - そのため、bot を月跨ぎで止めずに動かした場合、`current_month` は account json 側で進んでも、live ループ内の monthly drawdown 判定だけ古い月初資産を使い続けるリスクがあった

  - また monthly / weekly risk 判定に使う `current_total` も、mark-to-market 前の portfolio を使っており、特に simulation では 1 loop ぶん stale な評価額に寄りやすかった

- 変更:

  - `auto_trade.py` に `ensure_daytrade_month_state()` を追加し、server time ベースで

    - `current_month`

    - `month_start_equity`

    - を更新するようにした

  - 起動時だけでなく各 loop でも、portfolio を mark-to-market したあとに

    - `current_total`

    - month state

    - week state

    - monthly risk block

    - を再計算する順へ修正した

  - `tests/test_auto_trade.py` に

    - month state 初期化

    - 同月では reset しないこと

    - 月跨ぎでは server time で reset すること

    - を追加した

- 結果:

  - strategy baseline 指標は不変

  - 月跨ぎ連続稼働でも monthly risk guard が古い月初資産を握り続けないようになった

  - monthly / weekly state は、board / realtime buffer 反映後の mark-to-market 評価額で更新されるようになった

  - 検証:

    - `python -m pytest tests/test_auto_trade.py tests/test_logic.py -q` -> `65 passed`

    - `python -m pytest tests -q` -> `116 passed`

- 判断:

  - 採用

  - これは成績改善ではなく、live 実行の risk state を shared strategy 前提に合わせる runtime safety fix として採用した

- 再試行するとしたら:

  - 次に触るのは、month rollover のような state 管理ではなく、populated な live intraday log を前提に shared exit / partial de-risk を設計するとき

  - contaminated holdout を見ながら月次リスク閾値そのものを細かく触る方向へは進まない

### 2026-05-22: Live Daytrade Shared Exit Parity Repair

- 分析:

  - 今回のテーマは、strict 6m split を

    - `latest cache: 2026-05-21`

    - `train=2021-05-19` から `2025-11-24`

    - `contaminated holdout=2025-11-25` から `2026-05-21`

    - のまま固定しつつ、未達週分析ではなく `live / backtest` の shared-strategy parity を点検することだった

  - `daytrade` の live exit を追うと、`manage_positions_live()` が shared intraday stop / target を見ず、`AFTERNOON` 以降は実質一律 flatten になっていた

  - `MarketPhase.AFTERNOON` は `12:30` 開始なので、このままでは backtest が持っている intraday stop / target の出口と live 実行が乖離し、「後場寄りからすぐ全決済」という別戦略になっていた

  - また、closing-time の break が exit 処理より前にあり、将来 flatten 時刻を動かしたときに EOD 処理が抜けるリスクもあった

- 変更:

  - `core/logic.py` に live 用の shared helper を追加し、position に保存された entry context から

    - stop price

    - target price

    - `intraday_stop / intraday_target / daytrade_flatten`

    - を同じルールで解決するようにした

  - `manage_positions_live()` は「全 flatten」ではなく

    - intraday stop 到達

    - intraday target 到達

    - `14:30` 以降の force flatten

    - のどれかでだけ closed position を返すように修正した

  - さらに live 売り注文の戻り値を見て

    - 未約定なら保有継続

    - 部分約定なら shares を減らして保有継続

    - 全約定だけ local portfolio から除去

    - とする safety fallback を追加した

  - `auto_trade.py` では

    - `DAYTRADE_FORCE_FLATTEN_TIME = 14:30`

    - same-day re-entry guard

    - target mult / target price / target までの距離の observability

    - live full exit は実約定価格をそのまま exit log へ使い、simulation だけ slippage model を使うよう整理

    - live partial fill も `filled_shares` / `remaining_shares` 付きの exit event として `daytrade_exit_log.csv` に残すようにした

    - closing-time break を exit 処理後へ移動

    - を追加した

  - `README.md`、`tests/test_logic.py`、`tests/test_auto_trade.py` もこの前提へ更新した

- 結果:

  - strategy baseline 指標は不変

    - 今回は backtest の entry / sizing / shared selector を変えておらず、採用理由は成績改善ではなく本番実行の shared parity 復元

  - live 側でも intraday stop / target が shared helper を通るため、backtest と別の出口戦略になる問題を解消した

  - 検証:

    - `python -m pytest tests/test_logic.py tests/test_auto_trade.py tests/test_analyze_intraday_logs.py -q` -> `66 passed`

    - `python -m pytest tests -q` -> `110 passed`

    - `python analyze_intraday_logs.py --top-n 5` -> `daytrade_decisions.csv` / `intraday_snapshots.csv` / `daytrade_exit_log.csv` は引き続き `missing`

- 判断:

  - 採用

  - これは curve fit ではなく、shared strategy を live 実行レイヤーへ戻すための parity fix として採用した

- 再試行するとしたら:

  - 次に触るのは、populated な live intraday log が溜まり

    - `14:30` flatten が遅すぎる / 早すぎる

    - target 到達前後の give-back に shared partial de-risk が必要

    - を順序情報で判断できるときに限る

  - それまでは、同じ問題に対して日足 OHLC 条件を足す方向へ戻らない

### 2026-05-22: Low-Breadth Tepid Hot-Gap `primary` Shared Leverage Cap (Not Adopted)

- 分析:

  - 今回のテーマは、strict 6m `train=2021-05-19` から `2025-11-24` の未達週を改めて分解し、no-trade ではなく `primary` の損失集中を shared に浅くできるかを確認することだった

  - baseline の `train` では

    - `WEEKS >= +1%: 166/195`

    - `POSITIVE WEEKS: 167/195`

    - `miss weeks 28`

    - `negative 27`

    - `miss_no_trade 0`

    - で、依然として主課題は trade 不足ではなく `primary` の deep-loss week だった

  - full trade log を broad bin で見直すと、既採用の `tepid hot-gap modest-trend` selector skip の外側に

    - breadth `< 0.60`

    - `market_ratio 1.00-1.05`

    - gap `>= 2.0%`

    - `open_vs_sma_atr 0-2`

    - の residual `primary`

    - `9 trades / 3 wins / -8.02M / PF 0.03`

    - が残っていた

  - これは「市場確認が弱いのに個別だけ先走る continuation」の shared residual と見なし、追加の hard filter ではなく selected leverage cap として浅く試す余地があると判断した

- 変更:

  - `resolve_daytrade_selected_leverage` に、上の residual cluster を `primary probe` として落とす案を試した

  - leverage cap は `0.10 / 0.25 / 0.35` の3段だけ確認し、広いグリッド探索には広げなかった

- 結果:

  - `cap 0.10`

    - full:

      - `TOTAL RETURN +226289.64% -> +111761.57%`

      - `PROFIT FACTOR 8.07 -> 6.85`

      - `WEEKS >= +1% 187/221 -> 182/221`

      - `POSITIVE WEEKS 190/221 -> 186/221`

      - `WORST DAY -24,465,507円 -> -12,087,757円`

    - strict 6m train:

      - `TOTAL RETURN +61627.40% -> +30401.58%`

      - `PROFIT FACTOR 4.76 -> 3.67`

      - `WEEKS >= +1% 166/195 -> 161/195`

      - `POSITIVE WEEKS 167/195 -> 163/195`

      - `WORST DAY -19,825,603円 -> -9,795,748円`

  - `cap 0.25`

    - full:

      - `TOTAL RETURN +226289.64% -> +198562.95%`

      - `PROFIT FACTOR 8.07 -> 8.13`

      - `WEEKS >= +1% 187/221 -> 185/221`

      - `POSITIVE WEEKS 190/221 -> 189/221`

      - `WORST DAY -24,465,507円 -> -21,466,555円`

    - strict 6m train:

      - `TOTAL RETURN +61627.40% -> +54067.67%`

      - `PROFIT FACTOR 4.76 -> 4.82`

      - `WEEKS >= +1% 166/195 -> 164/195`

      - `POSITIVE WEEKS 167/195 -> 166/195`

      - `WORST DAY -19,825,603円 -> -17,399,241円`

  - `cap 0.35`

    - full:

      - `TOTAL RETURN +226289.64% -> +213293.62%`

      - `PROFIT FACTOR 8.07 -> 8.06`

      - `WEEKS >= +1% 187/221 -> 187/221`

      - `POSITIVE WEEKS 190/221 -> 190/221`

      - `WORST DAY -24,465,507円 -> -23,065,053円`

    - strict 6m train:

      - `TOTAL RETURN +61627.40% -> +58085.10%`

      - `PROFIT FACTOR 4.76 -> 4.75`

      - `WEEKS >= +1% 166/195 -> 166/195`

      - `POSITIVE WEEKS 167/195 -> 167/195`

      - `WORST DAY -19,825,603円 -> -18,688,507円`

    - contaminated 6m holdout:

      - `TOTAL RETURN +266.76% -> +266.75%`

      - `PROFIT FACTOR 11.54 -> 11.55`

      - `WEEKS >= +1% 21/26 -> 21/26`

      - `POSITIVE WEEKS 23/26 -> 23/26`

- 判断:

  - 不採用

  - `0.10` と `0.25` は downside 改善と引き換えに週次本数を落としすぎた

  - `0.35` は week count を維持したが、`train` / full の return と PF を baseline 超えにできず、未達週も1本も増やせなかった

  - contaminated holdout に悪化 veto は無かったが、clean holdout が無い現状で「週次不変・return 低下・downside やや改善」だけを理由に採用する根拠は弱いと判断した

- 再試行するとしたら:

  - 同じ low-breadth / tepid hot-gap residual を、selected leverage `0.10-0.35` の近傍で再調整しない

  - 次に進めるなら、

    - 新しい clean holdout が積み上がって同 residual の再現数が増えたとき

    - あるいは live / intraday exit log から shared exit / partial de-risk の根拠が取れたとき

    - に限定する

### 2026-05-22: `train` Miss-Week Sensitivity Audit (No Logic Change)

- 分析:

  - 上の residual cap を不採用にしたあと、まだ OHLC 日足だけで詰める余地があるかを確認するため、strict 6m `train=2021-05-19` から `2025-11-24` の miss week `28` 本を「あとどれだけで +1% を超えたか」で再点検した

  - 結果は、

    - worst trade を `25% / 50% / 75%` 浅くしても `0 / 0 / 0` 週しか反転せず

    - worst trade を完全に消しても `5/28` 週しか反転しなかった

    - `primary stop` bucket だけを `25% / 50% / 75% / 100%` 浅くした場合も `0 / 0 / 1 / 2` 週しか反転しなかった

  - 一方で miss week の `21/28` は「最悪 1 trade」が週内損失の `50%` 超、`12/28` は `75%` 超を占めており、損失集中そのものは強い

  - ただし、その集中損失を小幅に shallow 化しても週次 +1% はほとんど埋まらないため、同じ OHLC feature 近傍に新しい cap / probe / no-trade を足しても、週次改善より curve fit リスクが先に立つと判断した

  - live `daytrade_decisions.csv` / `intraday_snapshots.csv` / `daytrade_exit_log.csv` は今回も空のままで、順序情報ベースの exit 仮説を前に進める材料はまだ無かった

- 変更:

  - shared strategy の変更なし

  - `analyze_backtest_trade_log.py` に、

    - miss week ごとの `gap_to_target`

    - worst trade / `primary stop` を shallow 化したときの flip potential

    - weekly loss に占める worst trade の比率

    - を出す診断を追加した

  - `tests/test_analyze_backtest_trade_log.py` と `README.md` も同じ内容に合わせて更新した

- 結果:

  - baseline は不変

  - 現時点で言えることは、

    - 週次 +1% の未達を埋める次の主戦場は「小さな日足 cap の積み増し」ではなく

    - intraday 順序情報を使った shared exit / partial de-risk

    - あるいは新しい clean holdout の蓄積

    - である

- 判断:

  - 不採用

  - 新しい shared trading rule は追加しない

  - 代わりに、同じ dead-end を別セッションで繰り返さないための train diagnostics を強化した

- 再試行するとしたら:

  - live intraday log が十分たまり、「入った後に崩れた trade だけを切る」shared exit を設計できるとき

  - あるいは `train` に新しい broad residual が増え、small trim でも週次反転余地が明確に見えたとき

  - に限定する

### 2026-05-22: Intraday Log Source Visibility Reinforcement (No Logic Change)

- 分析:

  - shared exit / partial de-risk の次段へ進みたい一方で、現ワークツリーの `data/kabucom_test` には

    - `daytrade_decisions.csv`

    - `intraday_snapshots.csv`

    - `daytrade_exit_log.csv`

    - が存在せず、`analyze_intraday_logs.py` 実行時には単に `(no rows)` とだけ出て、missing なのか empty なのかが分かりにくかった

  - この状態では「ログ取得そのものが止まっている」のか、「まだ live 実行が足りないだけなのか」を即座に判断しづらく、次の shared exit 研究が詰まりやすかった

- 変更:

  - shared strategy の変更なし

  - `analyze_intraday_logs.py` に source file status と analysis readiness を追加し、

    - `missing`

    - `empty_file`

    - `header_only`

    - `populated`

    - を明示するようにした

  - `core/preflight.py` でも起動前に optional intraday observability log の状態を表示するようにした

  - `README.md` と `tests/test_analyze_intraday_logs.py` も同じ前提へ更新した

- 結果:

  - baseline / strategy metrics は不変

  - 今後は `analyze_intraday_logs.py` や起動前点検だけで、「まだ live path が取れていない」ことを即判定できる

- 判断:

  - 採用

  - これは売買ルール変更ではなく、次の strategy research を止めていた観測ギャップの解消として採用した

- 再試行するとしたら:

  - 次は file status を増やすのではなく、実際に populated な live log が溜まった段階で shared exit / partial de-risk の設計へ移る

### 2026-05-21: Monday Extreme-Gap `primary` De-Risk + Warmup-Aware Train Miss Weeks

- 分析:

  - 今回のテーマは、warmup 後の `train` で何が未達週を作っているかをゼロベースで見直し、shared strategy の範囲で損失集中を浅くすることだった

  - `analyze_backtest_trade_log.py` の miss-week 集計には warmup 前の部分週が混ざっており、従来表示の `miss weeks 70 / miss no-trade 42` は実運用比較には不適切だった

  - warmup 前の部分週を除外すると、strict 6m `train=2021-05-19` から `2025-11-24` の miss week は

    - `train weeks 194`

    - `miss 28`

    - `negative 27`

    - `miss_no_trade 0`

    - となり、主課題は稼働不足ではなく `primary` の損失集中だと分かった

  - `primary` を broad bin で再分解すると、月曜の `open_vs_sma_atr 1-2` かつ `gap <= 0` または `gap >= 2%` の continuation cluster が

    - `9 trades / 3 wins / -33.92M`

    - `close_or_open 8 trades / 3 wins / -28.05M`

    - と特に悪く、週明けの extreme gap に対して near-2x equity sizing を許すのが重すぎると判断した

- 変更:

  - `core/logic.py` の `resolve_daytrade_primary_equity_notional_pct` に、月曜の `primary` で

    - `open_vs_sma_atr 1.0-2.0`

    - `gap <= 0` または `gap >= 2.0%`

    - の broad cluster を `equity notional cap 1.25` へ落とす shared de-risk を追加した

  - `analyze_backtest_trade_log.py` の `build_train_week_table` に `warmup_start` を追加し、warmup 前の部分週を miss-week 集計から除外するようにした

  - `tests/test_logic.py` と `tests/test_analyze_backtest_trade_log.py` を更新した

- 結果:

  - `python jp_backtest.py --holdout-months 6`

    - full:

      - `FINAL EQUITY Y2,209,620,177 -> Y2,263,896,443`

      - `TOTAL RETURN +220862.02% -> +226289.64%`

      - `PROFIT FACTOR 7.90 -> 8.07`

      - `WEEKS >= +1% 187/221 -> 187/221`

      - `POSITIVE WEEKS 190/221 -> 190/221`

      - `WORST DAY -23,878,448円 -> -24,465,507円`

    - 6m train:

      - `FINAL EQUITY Y602,479,996 -> Y617,274,042`

      - `TOTAL RETURN +60148.00% -> +61627.40%`

      - `PROFIT FACTOR 4.59 -> 4.76`

      - `WEEKS >= +1% 166/195 -> 166/195`

      - `POSITIVE WEEKS 167/195 -> 167/195`

      - `WORST DAY -22,457,646円 -> -19,825,603円`

    - contaminated 6m holdout `2025-11-25` から `2026-05-21`:

      - `TOTAL RETURN +266.75% -> +266.76%`

      - `PROFIT FACTOR 11.55 -> 11.54`

      - `WEEKS >= +1% 21/26 -> 21/26`

      - `POSITIVE WEEKS 23/26 -> 23/26`

      - `WORST DAY -23,878,448円 -> -24,465,507円`

  - `python jp_walkforward.py --holdout-months 6 --step-months 1 --min-train-months 24 --max-windows 6`

    - `AVG HOLDOUT RETURN +396.83% -> +399.45%`

    - `AVG HOLDOUT PF 11.34 -> 11.52`

    - `HOLDOUT WEEKS >= +1% 147/155 -> 147/155`

    - `HOLDOUT POSITIVE WEEKS 149/155 -> 149/155`

  - contaminated holdout の `WORST DAY` 名目額は少し悪化したが、worst day の日次損失率はほぼ横ばいで、悪化は主に train 改善後の複利ベース上昇によると確認した

- 判断:

  - 採用

  - warmup-aware miss 集計で課題を正しく `negative miss` に絞り込めたことと、月曜 cluster の sizing trim が

    - train の worst day を大きく浅くし

    - 週次達成率を落とさず

    - rolling holdout でも平均成績を悪化させなかった

    - ため

- 再試行するとしたら:

  - 次は `primary close_exit` の fade を、今回の Monday de-risk の外側で

    - 月水木の `market_ratio 1.00-1.05`

    - `gap >= 2%`

    - `open_vs_sma_atr 0-2`

    - の broad clusterとして残るかどうかを、clean holdout と live exit log が溜まってから shared exit 側で見る

### 2026-05-21: Live Exit Decision Diagnostics Expansion

- 分析:

  - 今回のテーマは、`primary close_exit` の run-up 後 fade を次の clean holdout で shared exit / de-risk に繋げられるよう、live 側の監査粒度を backtest 側へ寄せることだった

  - `2026-05-21` 時点では live の `daytrade_decisions.csv` / `intraday_snapshots.csv` / `daytrade_exit_log.csv` はまだ空のままだが、前段で追加した backtest fade 診断から

    - run-up 後に赤で終わる trade

    - stop に近づいたまま戻らない trade

    - close まで保有すると give-back しやすい trade

    - を live 側でも同じ物差しで追える必要があると分かった

  - 既存の `intraday_snapshots.csv` だけでは、「最後の snapshot」までは追えても、「どの価格帯で flatten を決めたか」「slippage 込みでどの程度の modeled exit だったか」が残らず、exit 設計の検証に足りなかった

- 変更:

  - `auto_trade.py` に `daytrade_exit_log.csv` を追加し、flatten 時に

    - `observed_price`

    - `modeled_exit_price`

    - `modeled_pnl`

    - `modeled_return_pct`

    - `session_runup_pct`

    - `session_drawdown_pct`

    - `fade_from_session_high_pct`

    - `rebound_from_session_low_pct`

    - を entry context と一緒に残すようにした

  - `intraday_snapshots.csv` 側にも `session_drawdown_pct`、`fade_from_session_high_pct`、`rebound_from_session_low_pct` を追加し、snapshot と exit で同じ path 指標を揃えた

  - `analyze_intraday_logs.py` は `daytrade_exit_log.csv` を読めるようにし、存在する場合は最後の snapshot ではなく exit decision 側の modeled return / pnl を優先して集計するようにした

  - README と `tests/test_auto_trade.py` / `tests/test_analyze_intraday_logs.py` を更新した

- 結果:

  - strategy baseline 指標は変更なし

  - `analyze_intraday_logs.py` は、exit ログが無い現時点でも空ファイルで安全に動作し、exit ログがある将来セッションでは

    - `Exit Counts`

    - `Daily Exit Summary`

    - exit decision を反映した `final_return_pct`

    - を同じレポート内で見られるようになった

- 判断:

  - 採用

  - ただし採用したのは live 実行レイヤーの監査基盤であり、売買ロジックの baseline 自体は据え置き

  - contaminated holdout を見ながら OHLC 条件をさらに足すより、実運用の exit decision を貯めて shared exit 設計の根拠を作るほうが、将来の本番運用には頑健だと判断した

- 再試行するとしたら:

  - `2026-05-21` 以降の clean holdout と live logs が数週間ぶん溜まったあとに、

    - `fade_from_session_high_pct` が深いのに `modeled_return_pct <= 0` で終わる trade

    - `distance_to_stop_atr` が小さいまま回復しない trade

    - `session_drawdown_pct` が深いのに entry quality が高く見える trade

    - を setup 別に分解して、shared exit / partial de-risk へ進む

### 2026-05-21: Backtest Fade Diagnostics Expansion

- 分析:

  - 今回のテーマは、新しい売買ルールを足すことではなく、`2026-05-21` 時点でまだ空の live `daytrade_decisions.csv` / `intraday_snapshots.csv` を待つ間に、次の shared exit / de-risk 判断へ直結する診断を強くすることだった

  - `analyze_backtest_trade_log.py` に `primary close_exit` 側の fade を追加で出すようにすると、strict 6m `train=2021-05-19` から `2025-11-20` の miss week では

    - `primary close_or_open 31 trades / 10 wins / -7.13M`

    - うち `primary close-loss` は broad に見ると

      - `market_ratio 1.00-1.05`

      - `gap >= 2%`

      - `open_vs_sma_atr 0-2`

      - 月水木

      - に偏りやすい

    - ことが見えた

  - 一方で、その broad cluster 自体は `13 trades / 6 wins / -5.10M` で、火曜には `2 trades / +3.03M` の勝ちも残っていたため、現時点でさらに OHLC 条件を足すと勝ち筋まで削る可能性が高いと判断した

- 変更:

  - `backtest.py` の `trade_log` に

    - `day_open/high/low/close_price`

    - `high_return_pct`

    - `low_return_pct`

    - `close_return_pct`

    - `fade_from_high_pct`

    - を追加し、run-up と close fade を再集計できるようにした

  - `analyze_backtest_trade_log.py` に

    - `primary stop cluster`

    - `primary close-loss cluster`

    - `Worst Primary Close Fades`

    - の集計を追加した

  - `tests/test_backtest.py` と `tests/test_analyze_backtest_trade_log.py` を増強し、README の分析コマンドとテスト欄も更新した

- 結果:

  - baseline 指標は変更なし

  - 新しい `analyze_backtest_trade_log.py --holdout-months 6 --top-n 8` で、`primary close_exit` の大きな give-back 例として

    - `2024-04-17 4813.T high_return_pct +5.98% / close_return_pct -0.46% / fade_from_high_pct -6.44%`

    - `2024-12-26 3350.T high_return_pct +2.95% / close_return_pct -1.20% / fade_from_high_pct -4.15%`

    - `2024-12-23 7003.T high_return_pct +1.38% / close_return_pct -2.58% / fade_from_high_pct -3.96%`

    - などを、再現可能に確認できるようになった

- 判断:

  - 採用

  - ただし採用したのは診断基盤であり、売買ロジックの baseline 自体は据え置き

  - contaminated holdout を見ながら OHLC 条件をさらに細かく足すより、次の clean holdout と live snapshot が溜まったときに、shared exit / partial de-risk を判断できる準備を優先した

- 再試行するとしたら:

  - `2026-05-21` 以降の clean holdout と live snapshot が溜まったあとに、

    - close まで持つと赤で終わりやすい trade

    - run-up 後に利益を大きく返しやすい trade

    - stop 直前まで圧迫されたあと戻らない trade

    - を、今回追加した backtest fade 指標と live intraday path を突き合わせて shared に切る

### 2026-05-21: `catchup_rs` Shared Risk Budget Trim

- 分析:

  - 今回のテーマは、`9%` global risk budget 採用後に残った損失集中を、週達成率を崩さずにさらに浅くできるかどうかだった

  - `2026-05-21` 時点でも live の `daytrade_decisions.csv` / `intraday_snapshots.csv` は空のままで、intraday exit 順序に依存する改修はまだ見送る必要があった

  - strict 6m `train=2021-05-19` から `2025-11-20` の miss week は引き続き

    - `miss weeks 70`

    - `negative miss 27`

    - `miss no-trade 42`

    - だった

  - `primary` ほどではないが、残る downside の中では `catchup_rs` が

    - miss week `11 trades / 3 wins / -1.88M`

    - うち stop `4 trades / 0 wins / -0.52M`

    - を占めていた

  - 全 train `catchup_rs` を broad regime で見ると、loss は low breadth / market below trend 側に多く、かつ reactive な chase setup らしく stop / close loss が散っていた一方、同じ broad regime に勝ちも残っていたため、no-trade ではなく setup 別 sizing で対処するほうが shared strategy として自然だと判断した

- 追試:

  - `catchup_rs` だけを default `9%` より一段軽くする structural sizing probe として、

    - `8.0%`

    - `7.5%`

    - を比較した

  - 併せて、`catchup_rs` の stop 幅を `0.8 -> 0.7 / 0.6` に tighten する案も what-if したが、

    - return は伸びても

    - `WORST DAY -23.88M -> -29.42M` 方向へ悪化し、

    - 実運用の downside 改善という目的には合わず不採用

  - sizing 側では `8.0%` が最もバランスが良く、

    - full `WEEKS >= +1% 187/221 -> 187/221`

    - strict 6m train `WEEKS >= +1% 165/194 -> 165/194`

    - rolling 6m holdout `HOLDOUT WEEKS >= +1% 472/539 -> 472/539`

    - contaminated 6m holdout `WEEKS >= +1% 21/26 -> 21/26`

    - を維持したまま downside を少し浅くできた

  - `7.5%` は worst day はさらに軽くなったが、return の削れ方が大きく不採用

- 変更:

  - `core/logic.py` に `resolve_daytrade_risk_per_trade_pct` を追加

  - default risk budget は `9%` のまま維持し、`catchup_rs` だけ `8%` を返すようにした

  - `cap_daytrade_position_size` に `risk_budget_pct` 引数を追加し、backtest / live の両方から同じ shared helper を通す形にした

  - `tests/test_logic.py` に、setup 別 risk budget helper と `risk_budget_pct` 引数のテストを追加

- 結果:

  - full:

    - `FINAL EQUITY Y2,328,100,032 -> Y2,223,750,735`

    - `TOTAL RETURN +232710.00% -> +222275.07%`

    - `PROFIT FACTOR 8.47 -> 8.44`

    - `WEEKS >= +1% 187/221 -> 187/221`

    - `POSITIVE WEEKS 190/221 -> 190/221`

    - `WORST DAY -25,003,055円 -> -23,878,448円`

  - strict 6m train:

    - `TOTAL RETURN +52073.10% -> +49737.28%`

    - `PROFIT FACTOR 3.99 -> 3.97`

    - `WEEKS >= +1% 165/194 -> 165/194`

    - `POSITIVE WEEKS 166/194 -> 166/194`

    - `WORST DAY -23,511,132円 -> -22,457,646円`

    - `miss week pnl sum -37.97M -> -36.76M`

    - `catchup_rs miss pnl -1.88M -> -1.80M`

    - `catchup_rs stop miss pnl -0.52M -> -0.49M`

  - contaminated 1m holdout `2026-04-21` から `2026-05-20`:

    - `TOTAL RETURN +1.26% -> +1.26%`

    - `PROFIT FACTOR 3.11 -> 3.11`

    - `WEEKS >= +1% 1/4 -> 1/4`

    - `POSITIVE WEEKS 2/4 -> 2/4`

    - `WORST DAY -3,969,514円 -> -3,784,270円`

  - contaminated 6m holdout `2025-11-21` から `2026-05-20`:

    - `TOTAL RETURN +346.23% -> +346.20%`

    - `PROFIT FACTOR 14.17 -> 14.17`

    - `WEEKS >= +1% 21/26 -> 21/26`

    - `POSITIVE WEEKS 23/26 -> 23/26`

    - `WORST DAY -25,003,055円 -> -23,878,448円`

  - rolling 6m holdout windows:

    - `HOLDOUT WEEKS >= +1% 472/539 -> 472/539`

    - `HOLDOUT POSITIVE WEEKS 474/539 -> 474/539`

    - `AVG HOLDOUT RETURN +197.89% -> +196.59%`

    - `AVG HOLDOUT PF 5.76 -> 5.75`

- 判断:

  - 採用

  - return は少し落ちるが、週達成率を崩さずに、`catchup_rs` の reactive loss を shared sizing だけで浅くできた

  - intraday 順序がまだ無い現状では、exit をいじるより setup 別 risk budget のほうが説明可能性と再現性が高いと判断した

- 再試行するとしたら:

  - `catchup_rs` の risk budget を `8.5%` や `7.8%` のように細かく詰めない

  - 次に触るなら、clean holdout と live snapshot が溜まったあとに

    - `primary` close_exit の fade

    - stop 接近後に戻らない reactive trade

    - intraday で run-up を失う trade

    - を exit / partial de-risk で shared に切れるときに限る

### 2026-05-21: Shared One-Trade Risk Budget Trim

- 分析:

  - 今回のテーマは、未達週数を崩さずに損失集中を浅くすることだった

  - `2026-05-21 08:33 JST` 時点ではまだ当日 EOD を取りに行く局面ではなく、最新キャッシュ日は `2026-05-20` のままだったため、strict 6m split は

    - `train=2021-05-19` から `2025-11-20`

    - `holdout=2025-11-21` から `2026-05-20`

    - に固定した

  - live の `daytrade_decisions.csv` / `intraday_snapshots.csv` は依然空で、intraday 順序情報を使った exit 改修はまだ行えなかった

  - strict 6m train の未達週は引き続き

    - `miss weeks 70`

    - `negative miss 27`

    - `positive miss 1`

    - `miss no-trade 42`

    - で、trade が出た miss week の損失寄与は

    - `primary 50 trades / 11 wins / -27.58M`

    - `primary stop 18 trades / 0 wins / -22.95M`

    - が中心だった

  - worst trade を見ると、`notional_pct_equity` が `1.6-1.95x` に張りつき、entry 時 stop 幅が `4-6%` ある continuation / stop trade が多く、個別 regime ではなく shared sizing 前提のほうが攻めすぎていると判断した

- 追試:

  - coarse な structural sizing change として

    - `DAYTRADE_RISK_PER_TRADE_PCT 10%`

    - を `9.5% / 9.0% / 8.5% / 8.0% / 6.0% / 5.0%`

    - に落とす what-if を比較した

  - さらに、wide-stop trade だけに equity cap を重ねる probe も確認した

  - 結果は `9.0%` が最もバランスが良く、

    - full `WEEKS >= +1% 187/221 -> 187/221`

    - strict 6m train `WEEKS >= +1% 165/194 -> 165/194`

    - rolling 6m holdout `HOLDOUT WEEKS >= +1% 472/539 -> 472/539`

    - contaminated 6m holdout `WEEKS >= +1% 21/26 -> 21/26`

    - を維持したまま、downside を一段浅くできた

  - `8.5%` 以下は週達成率は維持できても return の削れ方が大きく、wide-stop cap 追加案は `9.0%` 単体より改善効率が弱かった

- 変更:

  - `core/logic.py` の `DAYTRADE_RISK_PER_TRADE_PCT` を `0.100 -> 0.090` へ変更

  - `tests/test_logic.py` に、`cap_daytrade_position_size` の risk-budget cap が先に効くケースを追加

- 結果:

  - full:

    - `FINAL EQUITY Y2,886,708,217 -> Y2,328,100,032`

    - `TOTAL RETURN +288570.82% -> +232710.00%`

    - `PROFIT FACTOR 8.88 -> 8.47`

    - `WEEKS >= +1% 187/221 -> 187/221`

    - `POSITIVE WEEKS 190/221 -> 190/221`

    - `WORST DAY -30,385,608円 -> -25,003,055円`

  - strict 6m train:

    - `TOTAL RETURN +60810.70% -> +52073.10%`

    - `PROFIT FACTOR 4.06 -> 3.99`

    - `WEEKS >= +1% 165/194 -> 165/194`

    - `POSITIVE WEEKS 166/194 -> 166/194`

    - `WORST DAY -30,306,953円 -> -23,511,132円`

    - `miss week pnl sum -41.60M -> -37.97M`

    - `primary miss pnl -30.08M -> -27.58M`

    - `primary stop miss pnl -24.82M -> -22.95M`

  - contaminated 1m holdout `2026-04-21` から `2026-05-20`:

    - `TOTAL RETURN +1.26% -> +1.26%`

    - `PROFIT FACTOR 3.11 -> 3.11`

    - `WEEKS >= +1% 1/4 -> 1/4`

    - `POSITIVE WEEKS 2/4 -> 2/4`

    - `WORST DAY -4,922,198円 -> -3,969,514円`

  - contaminated 6m holdout `2025-11-21` から `2026-05-20`:

    - `TOTAL RETURN +373.92% -> +346.23%`

    - `PROFIT FACTOR 14.63 -> 14.17`

    - `WEEKS >= +1% 21/26 -> 21/26`

    - `POSITIVE WEEKS 23/26 -> 23/26`

    - `WORST DAY -30,385,608円 -> -25,003,055円`

  - rolling 6m holdout windows:

    - `HOLDOUT WEEKS >= +1% 472/539 -> 472/539`

    - `HOLDOUT POSITIVE WEEKS 474/539 -> 474/539`

    - `AVG HOLDOUT RETURN +211.04% -> +197.89%`

    - `AVG HOLDOUT PF 5.85 -> 5.76`

- 判断:

  - 採用

  - clean holdout がまだ積み上がっていない局面では、曜日枝や細かい gap 帯を増やすより、「shared risk premise を一段保守化する」ほうが将来局面への説明可能性が高い

  - return は明確に落ちるが、週達成率を維持したまま worst day と miss-week 深掘れを縮められたため、実運用優先の baseline としては妥当と判断した

- 再試行するとしたら:

  - `9%` 近傍を `8.8%` や `9.2%` のように細かく再調整しない

  - 次に触るなら、`2026-05-21` 以降の clean holdout と live snapshot が溜まったあとに

    - intraday で stop 接近後に戻らない trade

    - run-up 後に fade しやすい trade

    - close_exit まで引っ張ると悪化する trade

    - を shared exit / de-risk で切る方向を優先する

### 2026-05-20: Residual Deep-Loss Reanalysis and Backtest Exit Instrumentation

- 分析:

  - strict 6m `train=2021-05-19` から `2025-11-20` を replay し直すと、full ISO week ベースで

    - `train weeks 235`

    - `miss weeks 70`

    - `negative miss 69`

    - `positive miss 1`

    - `miss no-trade 42`

    - だった

  - miss week の損失寄与は引き続き `primary` が最大で、

    - `50 trades / 11 wins / -30.08M`

    - だった

  - そのうち `primary` の stop 系だけで

    - `18 trades / 0 wins / -24.82M`

    - を占め、曜日では月曜 `-10.87M`、金曜 `-7.11M`、水曜 `-3.63M` が重かった

  - ただし既採用の `tepid hot-gap`、`Monday tepid strong-prev`、`hot continuation` などの risk cluster は、実験ログ上すでに tighter 近傍の再試行禁止帯に入っており、同じ OHLC 閾値近傍をさらに詰めると curve-fit 側へ寄りやすかった

  - live の `daytrade_decisions.csv` / `intraday_snapshots.csv` は現ワークツリーには残っておらず、順序情報で exit 仮説を検証できる材料も不足していた

- 追試:

  - 既存の cautionary sizing を shared probe に寄せる structural risk layer として、

    - `primary` の top candidate がすでに `equity_notional_pct <= 1.00` に抑えられている日は、selected leverage を `0.25` に制限

    - を what-if で検証した

  - 結果は

    - full `TOTAL RETURN +288570.82% -> +288018.79%`

    - full `PROFIT FACTOR 8.88 -> 8.88`

    - full `WEEKS >= +1% 187/221 -> 187/221`

    - full `WORST DAY -30,385,608円 -> -30,329,024円`

    - strict 6m train `WEEKS >= +1% 165/194 -> 165/194`

    - rolling 6m holdout `HOLDOUT WEEKS >= +1% 472/539 -> 472/539`

    - rolling `AVG HOLDOUT RETURN +211.04% -> +210.95%`

    - で、downside は少し浅くなったが forward 側の改善根拠としては弱かった

  - `tepid hot-gap` の capped continuation だけを selected leverage `0.25` へ probe 化する案は、

    - full / train の return と PF は少し伸びた一方、

    - `WORST DAY -30,385,608円 -> -30,505,849円`

    - と悪化し不採用

- 変更:

  - shared strategy の採用ロジック変更は行わない

  - `backtest.py` の `trade_log` に

    - `exit_reason`

    - `raw_exit_price`

    - `stop_distance_pct`

    - `target_distance_pct`

    - `day_start_equity`

    - `notional_pct_equity`

    - `pnl_pct_equity`

    - を追加し、deep-loss の原因を replay 後に監査できるようにした

  - `analyze_backtest_trade_log.py` を追加し、`train` の miss week、worst day、`primary` stop cluster を 1 回の replay から再集計できるようにした

- 結果:

  - baseline の採用値は据え置き

  - 追加の shared logic 採用なし

- 採用:

  - 不採用

  - 現時点で再現性を持って効くのは「intraday 順序情報で stop / fade の形を切る」方向であり、OHLC 日足だけの追加閾値や probe 化を続けると、改善幅より当て込みリスクが先に大きくなると判断した

- 再試行するとしたら:

  - `2026-05-21` 以降の clean holdout を積み上げながら、live の `daytrade_decisions.csv` / `intraday_snapshots.csv` を継続保存する

  - 次の shared change は、今回追加した `exit_reason` 監査列と live snapshot を合わせて、

    - stop 接近後に戻らない trade

    - run-up 後に fade しやすい trade

    - close_exit まで引っ張ると悪化する trade

    - を exit / partial de-risk で切れるときに限って行う

  - 同じ `tepid hot-gap`、`Monday tepid strong-prev`、`hot continuation` の tighter 近傍は、新しい clean holdout か追加の train 実例なしには再試行しない

### 2026-05-20: Warm-Market Low-Sponsorship `primary` No-Trade

- 分析:

  - strict 6m `train=2021-05-19` から `2025-11-20` の未達週を broad regime で再分解すると、`primary` の deep-loss は narrow な曜日枝より、「市場は warm だが breadth がまだ broad ではなく、前日も少しだけ上げた continuation を low score のまま追う」低 sponsorship 帯にまとまって残っていた

  - miss week 側では、

    - breadth `< 0.65`

    - `market_ratio 1.05-1.10`

    - 前日上昇 `2-4%`

    - score `<= 6`

    - gap `<= 1%`

    - の `primary`

    - `5 trades / 1 win / -2.44M`

    - で、`2023-08-17 2222.T`、`2023-10-02 3431.T`、`2023-10-03 6632.T`、`2024-07-23 2780.T` など、指数は少し上でも breadth と個別の勢いが噛み合わない continuation を still-size で追っていた

  - これは既採用の `market_ratio 1.05-1.10` / 前日上昇 `4-6%` / score `<= 6` no-trade より一段手前の sponsorship 劣化帯で、曜日限定の近傍再調整ではなく、shared な continuation quality guard として扱うほうが説明しやすいと判断した

- 変更:

  - `resolve_daytrade_selected_leverage` に low-sponsorship continuation `primary` no-trade guard を追加

  - breadth `< 0.65` / `market_ratio 1.05-1.10` / 前日上昇 `2-4%` / score `<= 6` / gap `<= 1%` の `primary` は、selected base leverage を `0.00` に制限

  - `tests/test_logic.py` に発火 / 非発火の境界テストを追加

- 結果:

  - full:

    - `TOTAL RETURN: +259794.55%` -> `+288570.82%`

    - `CLOSED TRADES: 446` -> `441`

    - `WIN RATE: 60.09%` -> `60.54%`

    - `PROFIT FACTOR: 8.79` -> `8.88`

    - `WEEKS >= +1%: 187/221` -> `187/221`

    - `POSITIVE WEEKS: 190/221` -> `190/221`

    - `WORST DAY: -27,358,364円` -> `-30,385,608円`

  - strict 6m train:

    - `TOTAL RETURN: +54739.29%` -> `+60810.70%`

    - `PROFIT FACTOR: 3.99` -> `4.06`

    - `WEEKS >= +1%: 165/194` -> `165/194`

    - `POSITIVE WEEKS: 166/194` -> `166/194`

  - contaminated 1m holdout `2026-04-21` から `2026-05-20`:

    - `TOTAL RETURN: +1.26%` -> `+1.26%`

    - `PROFIT FACTOR: 3.11` -> `3.11`

    - `WEEKS >= +1%: 1/4` -> `1/4`

    - `POSITIVE WEEKS: 2/4` -> `2/4`

    - `WORST DAY: -4,419,392円` -> `-4,922,198円`

  - contaminated 6m holdout `2025-11-21` から `2026-05-20`:

    - `TOTAL RETURN: +373.92%` -> `+373.92%`

    - `PROFIT FACTOR: 14.63` -> `14.63`

    - `WEEKS >= +1%: 21/26` -> `21/26`

    - `POSITIVE WEEKS: 23/26` -> `23/26`

  - rolling 6m holdout windows:

    - `HOLDOUT WEEKS >= +1%: 472/539` -> `472/539`

    - `HOLDOUT POSITIVE WEEKS: 474/539` -> `474/539`

    - `AVG HOLDOUT RETURN: +210.24%` -> `+211.04%`

    - `AVG HOLDOUT PF: 5.82` -> `5.85`

- 判断:

  - 採用

  - train と rolling で `WEEKS >= +1%` を落とさず return / PF を押し上げ、contaminated 6m holdout も悪化させなかったため

  - absolute `WORST DAY` は増えたが、worst loss pct は full / train ともに `2022-12-06 -10.1908562%` から `2022-12-06 -10.1787085%` へむしろ小幅改善した

  - contaminated 1m holdout は headline 不変で、悪化は absolute worst day に留まり、相対損失は依然 `-0.1702%` と浅い `veto` 範囲にとどまった

- 再試行するとしたら:

  - 同じ low-sponsorship continuation を `1.05-1.10` の近傍へ細かく広げたり、`0.05/0.10` probe に戻す再調整は行わない

  - 次に触るなら、残る `primary` の deep-loss を intraday 順序情報で exit 側から切れるときか、新しい clean holdout が積み上がって broad regime の再現例が増えたときに限る

### 2026-05-20: Tepid-Market Hot-Gap Modest-Trend `primary` Selector Skip

- 分析:

  - 最新キャッシュを `2026-05-20` まで更新し、strict 6m split を `train=2021-05-19` から `2025-11-20`、`holdout=2025-11-21` から `2026-05-20` に固定した

  - 今回のテーマは、まず `WEEKS >= +1%` の未達週を埋めることだった

  - baseline 後の strict 6m `train` を再分解すると、未達週は依然として no-trade より deep-loss week が中心で、setup 別では `primary` が最大の足を引っ張っていた

  - actual selected trade で見ると、

    - breadth `< 0.60`

    - `market_ratio 1.00-1.05`

    - gap `1.5-2.0%`

    - `open_vs_sma_atr 1.0-2.0`

    - の tepid hot-gap `primary`

    - `4 trades / 0 wins / -4.55M`

    - で、弱い breadth confirmation のわりに個別が先走っている continuation が繰り返し崩れていた

  - これは既採用の `market_ratio 1.00-1.05` / gap `1.5-2.5%` / 前日上昇 `6-10%` cap とは別で、`prev_return` ではなく breadth 不一致を shared な違和感として捉えるべき帯と判断した

  - 一方、次に残る hot-market / small-gap / high-breadth 側は、過去の不採用ログにある low-score hot continuation と近く、隣接帯に勝ち筋も残っていたため、このターンでは追加枝を増やさない

- 変更:

  - `is_daytrade_primary_tepid_hot_gap_modest_trend_filtered` を、寄り判定ではなく `select_daytrade_candidates` の shared selector filter として適用

  - breadth `< 0.60` / `market_ratio 1.00-1.05` / gap `1.5-2.0%` / `open_vs_sma_atr 1.0-2.0` の `primary` を候補段階で除外

  - `tests/test_logic.py` に selector での発火 / 非発火境界テストを追加

- 結果:

  - full:

    - `TOTAL RETURN: +232924.71%` -> `+259794.55%`

    - `PROFIT FACTOR: 8.63` -> `8.79`

    - `WEEKS >= +1%: 186/221` -> `187/221`

    - `POSITIVE WEEKS: 189/221` -> `190/221`

    - `WORST DAY: -24,529,164円` -> `-27,358,364円`

  - strict 6m train:

    - `TOTAL RETURN: +49069.46%` -> `+54739.29%`

    - `PROFIT FACTOR: 3.88` -> `3.99`

    - `WEEKS >= +1%: 164/194` -> `165/194`

    - `POSITIVE WEEKS: 165/194` -> `166/194`

  - contaminated 1m holdout `2026-04-21` から `2026-05-20`:

    - `TOTAL RETURN: +1.26%` -> `+1.26%`

    - `PROFIT FACTOR: 3.11` -> `3.11`

    - `WEEKS >= +1%: 1/4` -> `1/4`

    - `POSITIVE WEEKS: 2/4` -> `2/4`

  - contaminated 6m holdout `2025-11-21` から `2026-05-20`:

    - `TOTAL RETURN: +373.92%` -> `+373.92%`

    - `PROFIT FACTOR: 14.63` -> `14.63`

    - `WEEKS >= +1%: 21/26` -> `21/26`

    - `POSITIVE WEEKS: 23/26` -> `23/26`

  - rolling 6m holdout:

    - `HOLDOUT WEEKS >= +1%: 466/539` -> `472/539`

    - `HOLDOUT POSITIVE WEEKS: 468/539` -> `474/539`

    - `AVG HOLDOUT RETURN: +208.19%` -> `+210.24%`

    - `AVG HOLDOUT PF: 5.76` -> `5.82`

- 判断:

  - 採用

  - `train` と rolling の両方で `WEEKS >= +1%` を 1 本以上押し上げ、current contaminated holdout も悪化させなかったため

  - `WORST DAY` は悪化したが、今回は最優先の未達週改善を shared selector だけで前進させられた点を優先し、次のテーマを損失集中の圧縮へ移す

- 再試行するとしたら:

  - 残る hot-market / small-gap / high-breadth `primary` を、そのまま broad filter で再試行しない

  - 次に触るなら、intraday 順序情報か、週次未達へ一貫して効く追加 signal が見えたときだけにする

### 2026-05-20: Warm-Market Strong-Prev Low-Score `primary` No-Trade

- 分析:

  - strict 6m `train=2021-05-19` から `2025-11-18` の未達週を再分解すると、`56` 未達週のうち `31` 週は no-trade だった

  - ただし no-trade 週の大半は初期データの薄い区間か low-breadth 側で、そこを無理に埋める shared entry を足す根拠は弱かった

  - 一方、trade が出ている未達週では依然として `primary` が最大の足引っ張りで、既存 baseline 後の train でも

    - `market_ratio 1.05-1.10`

    - 前日上昇 `4-6%`

    - score `<= 6`

    - の low-conviction `primary`

    - `5 trades / 0 wins / -2.63M`

    - が残っていた

  - 実例は `2023-11-07 9433.T`、`2023-11-10 5851.T`、`2023-12-05 4055.T`、`2024-07-24 8358.T` などで、「市場はやや hot だが個別 score は弱い continuation」を current equity cap `1.40` でもまだ触りすぎている shared sizing / selection 問題と判断した

- 変更:

  - `DAYTRADE_SELECTED_PRIMARY_WARM_STRONG_PREV_LOW_SCORE_*` を追加

  - `market_ratio 1.05-1.10` / 前日上昇 `4-6%` / score `<= 6` の `primary` は、selected base leverage を `0.00` に制限

  - `tests/test_logic.py` に発火 / 非発火の境界テストを追加

- 結果:

  - full:

    - `TOTAL RETURN: +181775.93%` -> `+205790.54%`

    - `PROFIT FACTOR: 8.33` -> `8.47`

    - `WEEKS >= +1%: 186/221` -> `186/221`

    - `POSITIVE WEEKS: 189/221` -> `189/221`

    - `WORST DAY: -19,125,392円` -> `-21,650,453円`

  - strict 6m train:

    - `TOTAL RETURN: +38533.68%` -> `+43635.44%`

    - `PROFIT FACTOR: 3.76` -> `3.85`

    - `WEEKS >= +1%: 164/194` -> `164/194`

    - `POSITIVE WEEKS: 165/194` -> `165/194`

  - contaminated 1m holdout:

    - `TOTAL RETURN: +1.34%` -> `+1.34%`

    - `PROFIT FACTOR: 3.24` -> `3.24`

    - `WEEKS >= +1%: 1/5` -> `1/5`

    - `POSITIVE WEEKS: 3/5` -> `3/5`

  - contaminated 6m holdout:

    - `TOTAL RETURN: +370.77%` -> `+370.76%`

    - `PROFIT FACTOR: 14.26` -> `14.25`

    - `WEEKS >= +1%: 21/26` -> `21/26`

    - `POSITIVE WEEKS: 23/26` -> `23/26`

  - rolling 6m holdout windows:

    - `HOLDOUT WEEKS >= +1%: 464/537` -> `464/537`

    - `HOLDOUT POSITIVE WEEKS: 466/537` -> `466/537`

    - `AVG HOLDOUT RETURN: +208.16%` -> `+209.39%`

    - `AVG HOLDOUT PF: 5.74` -> `5.78`

- 採用:

  - 採用

  - `train` の all-loss cluster を shared no-trade で消しつつ、full / train / rolling の return と PF を押し上げ、週次 hit を落とさなかったため

  - absolute `WORST DAY` は大きくなったが、worst loss pct は full / train ともに `2022-06-15 -10.2218662%` のまま不変で、絶対額の悪化は主に資産曲線の成長によるものだった

  - contaminated holdout は採用理由に使っていないが、悪化 veto も出なかった

- 再試行するとしたら:

  - この cluster を `probe` に戻す再調整は行わない

  - 次に触るなら、同じ low-score continuation を近傍条件へ広げるのではなく、clean intraday log が溜まった後の shared exit / partial de-risk を優先する

### 2026-05-20: Tuesday Extended `fallback` No-Trade

- 分析:

  - current baseline 後の strict 6m `train=2021-05-19` から `2025-11-18` を再分解すると、trade が出ている未達週では `primary` の次に崩れていた shared cluster が `fallback` 火曜 continuation だった

  - 特に

    - 火曜

    - `open_vs_sma_atr 2.0-3.0`

    - `fallback`

    - `6 trades / 0 wins / -2.46M`

    - で、`2022-05-31 1518.T`、`2023-10-24 7180.T`、`2023-12-12 9268.T`、`2024-10-29 9069.T`、`2024-11-26 4912.T`、`2024-12-10 7383.T`

    - のように、火曜まで continuation 候補として残っているが、すでに trend 距離が伸びて失速しやすい `fallback` を still-size で触っていた

  - breadth や score をさらに細分化しなくても、「火曜の延長 `fallback` は shared に自信が低い」という説明で十分に一般化しうると判断した

- 変更:

  - `DAYTRADE_SELECTED_FALLBACK_TUESDAY_EXTENDED_*` を追加

  - 火曜の `open_vs_sma_atr 2.0-3.0` `fallback` は、selected base leverage を `0.00` に制限

  - `tests/test_logic.py` に発火 / 上限境界 / 曜日非発火のテストを追加

- 結果:

  - full:

    - `TOTAL RETURN: +205790.54%` -> `+226631.74%`

    - `PROFIT FACTOR: 8.47` -> `8.58`

    - `WEEKS >= +1%: 186/221` -> `186/221`

    - `POSITIVE WEEKS: 189/221` -> `189/221`

    - `WORST DAY: -21,650,453円` -> `-23,864,302円`

  - strict 6m train:

    - `TOTAL RETURN: +43635.44%` -> `+48097.98%`

    - `PROFIT FACTOR: 3.85` -> `3.93`

    - `WEEKS >= +1%: 164/194` -> `164/194`

    - `POSITIVE WEEKS: 165/194` -> `165/194`

  - contaminated 1m holdout:

    - `TOTAL RETURN: +1.34%` -> `+1.26%`

    - `PROFIT FACTOR: 3.24` -> `3.11`

    - `WEEKS >= +1%: 1/5` -> `1/5`

    - `POSITIVE WEEKS: 3/5` -> `3/5`

  - contaminated 6m holdout:

    - `TOTAL RETURN: +370.76%` -> `+370.42%`

    - `PROFIT FACTOR: 14.25` -> `14.24`

    - `WEEKS >= +1%: 21/26` -> `21/26`

    - `POSITIVE WEEKS: 23/26` -> `23/26`

  - rolling 6m holdout windows:

    - `HOLDOUT WEEKS >= +1%: 464/537` -> `464/537`

    - `HOLDOUT POSITIVE WEEKS: 466/537` -> `466/537`

    - `AVG HOLDOUT RETURN: +209.39%` -> `+210.54%`

    - `AVG HOLDOUT PF: 5.78` -> `5.81`

- 採用:

  - 採用

  - contaminated holdout はわずかに低下したが veto 悪化はなく、train / full / rolling が揃って改善したため shared guard として入れる

- 再試行するとしたら:

  - `fallback` 火曜をさらに breadth や score で細分化する方向は、今の shared no-trade より説明可能性が下がるので、そのままでは再試行しない

  - 次に掘るなら、残る deep-loss day の intraday exit / partial de-risk に移る

### 2026-05-20: Thursday Low-Breadth Continuation `fallback` No-Trade

- 分析:

  - 火曜延長 `fallback` を切ったあとも、strict 6m `train=2021-05-19` から `2025-11-18` では `fallback` の残り損失がまだ miss week 側に残っていた

  - その中で最も shared にまとまっていたのが

    - 木曜

    - breadth `< 0.55`

    - `open_vs_sma_atr 1.0-2.0`

    - `fallback`

    - `6 trades / 1 win / -0.37M`

    - で、`2023-03-23 6506.T`、`2023-11-09 4887.T`、`2024-10-03 9684.T`、`2024-10-10 7383.T`、`2025-05-08 4592.T`

    - など、low-breadth で continuation としては中途半端に伸びた `fallback` が週後半で失速していた

  - breadth 条件を外した「木曜 `fallback` 1.0-2.0 ATR」でも同じ結果だったが、現行実績はすべて low-breadth 側だったため、shared な説明可能性を保つために breadth `< 0.55` を明示した

- 変更:

  - `DAYTRADE_SELECTED_FALLBACK_THURSDAY_LOW_BREADTH_CONTINUATION_*` を追加

  - 木曜の breadth `< 0.55` / `open_vs_sma_atr 1.0-2.0` `fallback` は、selected base leverage を `0.00` に制限

  - `tests/test_logic.py` に発火 / trend 上限 / breadth 上限の境界テストを追加

- 結果:

  - full:

    - `TOTAL RETURN: +226631.74%` -> `+232924.71%`

    - `PROFIT FACTOR: 8.58` -> `8.63`

    - `WEEKS >= +1%: 186/221` -> `186/221`

    - `POSITIVE WEEKS: 189/221` -> `189/221`

    - `WORST DAY: -23,864,302円` -> `-24,529,164円`

  - strict 6m train:

    - `TOTAL RETURN: +48097.98%` -> `+49436.72%`

    - `PROFIT FACTOR: 3.93` -> `3.97`

    - `WEEKS >= +1%: 164/194` -> `164/194`

    - `POSITIVE WEEKS: 165/194` -> `165/194`

  - contaminated 1m holdout:

    - `TOTAL RETURN: +1.26%` -> `+1.26%`

    - `PROFIT FACTOR: 3.11` -> `3.11`

    - `WEEKS >= +1%: 1/5` -> `1/5`

    - `POSITIVE WEEKS: 3/5` -> `3/5`

  - contaminated 6m holdout:

    - `TOTAL RETURN: +370.42%` -> `+370.41%`

    - `PROFIT FACTOR: 14.24` -> `14.24`

    - `WEEKS >= +1%: 21/26` -> `21/26`

    - `POSITIVE WEEKS: 23/26` -> `23/26`

  - rolling 6m holdout windows:

    - `HOLDOUT WEEKS >= +1%: 464/537` -> `464/537`

    - `HOLDOUT POSITIVE WEEKS: 466/537` -> `466/537`

    - `AVG HOLDOUT RETURN: +210.54%` -> `+210.96%`

    - `AVG HOLDOUT PF: 5.81` -> `5.84`

- 採用:

  - 採用

  - 週次 hit を落とさずに full / train / rolling の return と PF を押し上げ、worst loss pct も full / train ともに `2022-12-06 -10.1908562%` のまま不変だったため

  - absolute `WORST DAY` は増えたが、これは資産曲線の上振れによる絶対額の拡大で、損失率の悪化ではなかった

  - contaminated holdout も実質横ばいで veto 悪化なし

- 再試行するとしたら:

  - 同じ木曜 `fallback` を score や market_ratio でさらに刻む方向は取らない

  - 次に掘るなら、日足側ではなく intraday exit / partial de-risk へ進む

### 2026-05-20: Residual Post-`fallback` Guard Sweep (Not Adopted)

- 分析:

  - 木曜 low-breadth `fallback` を採用する前後で、残る候補をまとめて洗い直した

  - 候補は

    - 木曜 `market_ratio 1.00-1.05` / `open_vs_sma_atr 1.0-2.0` `primary`

    - 火曜 `open_vs_sma_atr 1.0-2.0` `fallback`

    - 月曜 `open_vs_sma_atr >= 6.0` `strong_oversold` の stricter probe

    - の 3 系統にほぼ収束した

- 追試:

  - 木曜 tepid-market continuation `primary` の no-trade

    - full / train / rolling の return と PF は伸びたが、`WEEKS >= +1%` が `186/221 -> 185/221`、strict 6m train も `164/194 -> 163/194` に低下

    - しかも worst loss pct が `-10.1908562% -> -10.2884034%` に悪化

  - 火曜 `fallback` `open_vs_sma_atr 1.0-2.0` の `probe 0.05` と `no-trade 0.00`

    - full / train / rolling は改善したが、どちらも worst loss pct が `-10.1908562% -> -10.2884034%` に悪化

    - したがって、shared guard としては損失集中の目的に反した

  - 月曜 extreme `strong_oversold` の selected leverage `0.10 / 0.05 / 0.00`

    - return / PF 自体は伸びる近傍があったが、`WEEKS >= +1%` が `185/221` まで落ち、contaminated holdout も `20/26` へ低下

- 結果:

  - 追加採用なし

- 採用:

  - 不採用

  - ここより先は「return は伸びるが週次 hit か worst loss pct を悪化させる」案しか残らず、shared rule としての筋が弱かった

- 再試行するとしたら:

  - 同じ日足近傍に新しい leverage guard を積み増すのではなく、clean intraday log を待って順序情報ベースの de-risk に移る

### 2026-05-20: Extra `primary` Probe Pairing After Tuesday `fallback` No-Trade (Not Adopted)

- 分析:

  - `fallback` 火曜 no-trade が効いたあと、残る train の deep-loss day は主に `primary` 側へ戻った

  - ただし、その近傍で追加の `primary` probe を重ねると、shared な安全装置というより narrow な当て込みになりやすいので、相性確認だけに絞って追試した

- 追試:

  - `fallback` 火曜 no-trade + 月曜 high breadth / `open_vs_sma_atr 2.0-3.0` `primary` probe

    - full `TOTAL RETURN +214050.05%`, `PF 8.09`

    - contaminated 6m holdout `+294.90%`

    - rolling `AVG HOLDOUT RETURN +188.79%`, `AVG HOLDOUT PF 5.60`

  - `fallback` 火曜 no-trade + 火曜 breadth `0.55-0.65` / `open_vs_sma_atr 2.0-3.0` `primary` probe

    - full `TOTAL RETURN +213149.66%`, `PF 8.63`

    - contaminated 6m holdout `+370.43%`

    - rolling `AVG HOLDOUT RETURN +210.94%`, `AVG HOLDOUT PF 5.82`

    - ただし full return が単独採用案 `+226631.74%` を下回った

- 結果:

  - 追加採用なし

- 採用:

  - 不採用

- 再試行するとしたら:

  - 同じ日足近傍に新しい `primary` probe を足すより、intraday log から共通の崩れ方を拾えるまで待つ

### 2026-05-20: Monday Hot-Market High-Breadth `primary` Probe (Not Adopted)

- 分析:

  - warm low-score rule を見つけたあとも、train では

    - 月曜

    - breadth `0.65-0.75`

    - `market_ratio >= 1.20`

    - の hot-market `primary`

    - `4 trades / 1 win / -19.85M`

    - が残っていた

  - `2025-10-20 3370.T -19.08M` が主因で、hot market continuation を probe 化すべきかを追加確認した

- 追試:

  - 上記 cluster を `selected leverage 0.05` に制限

  - あわせて、採用候補だった warm low-score no-trade と組み合わせた case も確認

- 結果:

  - `probe 0.05` 単独:

    - full `TOTAL RETURN +181775.93% -> +177960.40%`

    - strict 6m train `+38533.68% -> +38762.26%`, `PF 3.76 -> 3.99`

    - contaminated 6m holdout `+370.77% -> +358.18%`, `PF 14.26 -> 13.15`

    - rolling `AVG HOLDOUT RETURN +208.16% -> +197.65%`, `AVG HOLDOUT PF 5.74 -> 5.87`

  - warm low-score no-trade との組み合わせ:

    - full `+205790.54% -> +201079.12%`

    - strict 6m train `+43635.44% -> +43807.80%`, `PF 3.85 -> 4.10`

    - contaminated 6m holdout `+370.76% -> +358.19%`, `PF 14.25 -> 13.15`

    - rolling `AVG HOLDOUT RETURN +209.39% -> +198.94%`, `AVG HOLDOUT PF 5.78 -> 5.91`

- 採用:

  - 不採用

  - train の見た目は良くなったが、rolling と contaminated holdout の return が弱く、warm low-score no-trade の上にさらに載せる shared rule としては根拠が足りなかった

  - `2025-10-20` の単発影響が大きすぎて、まだ narrow reactivity の色が残っていると判断した

### 2026-05-20: `primary` Intraday De-Risk Follow-Up (Not Adopted)

- 分析:

  - 最新 baseline 後の strict 6m `train=2021-05-19` から `2025-11-18` を再分解すると、残る deep-loss day の主因は `primary` の `close` 負けだった

  - 特に `2025-10-20 3370.T -19.08M` は stop ではなく close exit で、既存 stop より「failed continuation を早めに見切る」shared de-risk が要るかを確認した

  - そのうえで、日足 OHLC だけで説明可能な範囲として、

    - 既存の `tepid-market hot-gap strong-prev` cluster に tighter stop を入れる案

    - `mid-breadth modest continuation` を selected leverage で `probe / no-trade` に落とす案

    - `low-score hot failed continuation` を selected leverage で `probe / no-trade` に落とす案

    - を比較した

- 追試 1:

  - 既存の breadth cap を入れている `market_ratio 1.00-1.05` / gap `1.5-2.5%` / 前日上昇 `6-10%` `primary` に、intraday stop `0.50 ATR` を追加

  - 結果:

    - full `TOTAL RETURN +181775.93% -> +181635.00%`, `PF 8.33 -> 8.28`, `WEEKS >= +1% 186/221 -> 186/221`, `WORST DAY -19,125,392円 -> -19,111,246円`

    - strict 6m train `TOTAL RETURN +38533.68% -> +38503.40%`, `PF 3.76 -> 3.72`, `WEEKS >= +1% 164/194 -> 164/194`, `WORST DAY -19,081,474円 -> -19,066,424円`

  - 判断:

    - リスク改善がごく小さい一方で return / PF が落ちたため不採用

- 追試 2:

  - breadth `0.55-0.65` / `market_ratio 1.00-1.15` / gap `0-1%` / 前日上昇 `2-4%` / `open_vs_sma_atr 1-2` / score `<= 11` の `primary` を `selected leverage 0.10` または `0.00` に制限

  - train 実績は `4 trades / 0 wins / -4.14M` と一貫して悪かった

  - 結果:

    - `probe 0.10`: full `+181775.93% -> +190271.12%`, `PF 8.33 -> 8.43`, `WEEKS >= +1% 186/221 -> 186/221`, ただし `WORST DAY -19,125,392円 -> -20,023,663円`

    - `no-trade 0.00`: full `+181775.93% -> +165611.77%`, `PF 8.33 -> 8.51`, `WEEKS >= +1% 186/221 -> 186/221`, `WORST DAY -19,125,392円 -> -17,427,872円`

  - 判断:

    - `probe` は worst day を悪化させ、`no-trade` は return を削りすぎたため不採用

- 追試 3:

  - breadth `>= 0.65` / `market_ratio >= 1.10` / 前日上昇 `>= 5%` / gap `<= 1%` / `open_vs_sma_atr <= 2` / score `<= 10` の `low-score hot failed continuation primary` を `selected leverage 0.10` または `0.00` に制限

  - train 実績は `2 trades / 0 wins / -19.35M` だった

  - 結果:

    - `probe 0.10`: full `+181775.93% -> +190271.13%`, `PF 8.33 -> 8.71`, `WEEKS >= +1% 186/221 -> 186/221`, `train WORST DAY -19,081,474円 -> -14,310,152円`, ただし `full WORST DAY -19,125,392円 -> -20,023,663円`

    - `no-trade 0.00`: full `+181775.93% -> +180467.93%`, `PF 8.33 -> 8.83`, `WEEKS >= +1% 186/221 -> 186/221`, `train WORST DAY -19,081,474円 -> -14,431,082円`, `full WORST DAY -19,125,392円 -> -18,991,005円`

  - 判断:

    - 数字だけ見ると魅力はあったが、`train` 再現例が `2` 本しかなく、巨大な単発負けに引っ張られた narrow branch を production へ入れるには根拠が弱すぎたため不採用

- 採用:

  - 不採用

  - 今回の範囲では、shared exit / de-risk を足しても

    - return / PF が落ちる

    - worst day が悪化する

    - あるいは sample が薄すぎる

    - のどれかに当たり、baseline を素直に上回れなかった

- 再試行するとしたら:

  - `primary` の intraday de-risk は、今の OHLC 日足だけでさらに閾値を刻むより、`data/.../daytrade_decisions.csv` の live decision log を増やして「入った後に崩れた」順序情報を見てから再設計する

  - あるいは、今回 `2` 本しかなかった low-score hot failed continuation に追加の `train` 実例がたまってから再検証する

### 2026-05-20: Tuesday Mid-Breadth Continuation `fallback` Tight Cap

- 分析:

  - strict 6m `train=2021-05-19` から `2025-11-18` の未達週を setup 別に再分解すると、`fallback` は `14 trades / 0 wins / -5.41M` と、母数は小さくても一方的に足を引っ張っていた

  - 細かい日付当てでは再現例が薄かったため、breadth / 前日上昇 / trend 距離で shared cluster を探し直すと、

    - 火曜

    - breadth `0.45-0.55`

    - 前日上昇 `>= 2%`

    - `open_vs_sma_atr 1.5-3.0`

    - の continuation `fallback`

    - `4 trades / 0 wins / -3.13M`

    - が残っていた

  - 実例は `2024-12-10 7383.T -1.40M`、`2024-12-24 7383.T -1.05M`、`2024-12-17 6507.T -0.39M` などで、breadth はまだ mid なのに個別だけ先に伸びた continuation を、既存の火水 generic cap `0.75` でもまだ大きく持ちすぎている shared sizing 問題と判断した

- 変更:

  - `DAYTRADE_FALLBACK_TUESDAY_MID_BREADTH_CONTINUATION_TIGHT_*` を追加

  - 火曜の breadth `0.45-0.55` / 前日上昇 `>= 2%` / `open_vs_sma_atr 1.5-3.0` `fallback` は、equity notional 上限を `0.50` に制限

  - `tests/test_logic.py` に発火 / 非発火の境界テストを追加

- 結果:

  - full:

    - `TOTAL RETURN: +171376.01%` -> `+174701.81%`

    - `PROFIT FACTOR: 7.83` -> `7.88`

    - `WEEKS >= +1%: 186/221` -> `186/221`

    - `POSITIVE WEEKS: 189/221` -> `189/221`

    - `WORST DAY: -18,091,532円` -> `-18,441,022円`

  - strict 6m train:

    - `TOTAL RETURN: +36249.02%` -> `+36953.40%`

    - `PROFIT FACTOR: 3.56` -> `3.60`

    - `WEEKS >= +1%: 164/194` -> `164/194`

    - `POSITIVE WEEKS: 165/194` -> `165/194`

  - contaminated 1m holdout:

    - `TOTAL RETURN: +1.34%` -> `+1.34%`

    - `PROFIT FACTOR: 3.24` -> `3.24`

    - `WEEKS >= +1%: 1/5` -> `1/5`

    - `POSITIVE WEEKS: 3/5` -> `3/5`

  - contaminated 6m holdout:

    - `TOTAL RETURN: +371.75%` -> `+371.76%`

    - `PROFIT FACTOR: 13.36` -> `13.36`

    - `WEEKS >= +1%: 21/26` -> `21/26`

    - `POSITIVE WEEKS: 23/26` -> `23/26`

  - rolling 6m holdout windows:

    - `HOLDOUT WEEKS >= +1%: 464/537` -> `464/537`

    - `HOLDOUT POSITIVE WEEKS: 466/537` -> `466/537`

    - `AVG HOLDOUT RETURN: +205.37%` -> `+205.99%`

    - `AVG HOLDOUT PF: 5.39` -> `5.40`

- 採用:

  - 採用

  - `train` の shared loss cluster を小さくしながら、full / train / rolling の return と PF を押し上げ、週次 hit は落とさなかったため

  - absolute `WORST DAY` は増えたが、同じ `2025-10-20` の日次損失率は `-6.0947042%` から `-6.0947010%` へ実質横ばいで、資産曲線の成長による見かけの悪化が主だった

- 再試行するとしたら:

  - 同 cluster を `0.50` よりさらに tight にする再調整は、新しい clean holdout か追加の train 実例が増えるまで行わない

  - 次に進めるなら、曜日例外を増やすより shared な intraday de-risk / partial exit を優先する

### 2026-05-20: Extreme `strong_oversold` Probe Leverage

- 分析:

  - fallback の tighten 後も、strict 6m `train` の deep-loss day には `strong_oversold` の大型逆行が残っていた

  - full-train では `strong_oversold` が `14 trades / 8 wins / -8.86M` と依然ネット負けで、特に

    - `open_vs_sma_atr >= 6.5`

    - または `market_ratio >= 1.20`

    - の extreme cluster が `8 trades / -12.33M`

    - を占めていた

  - 実例は `2025-11-17 6875.T -6.95M`、`2025-06-16 4592.T -6.33M` などで、「oversold」でもすでに trend から極端に離れている日や、指数自体が 20% 以上 hot な日は、mean-reversion を full leverage で取りに行く局面ではなく probe へ落とすべき shared regime と判断した

- 追試:

  - 直前 baseline の上に、extreme `strong_oversold` の selected base leverage cap を `0.75 / 0.25 / 0.00` で比較した

  - `0.75` は改善したが伸びは限定的だった

  - `0.25` は full / train / rolling の return と PF を最も押し上げつつ、`WEEKS >= +1%` を維持した

  - `0.00` は `WEEKS >= +1%` を full `186/221 -> 184/221`、strict 6m train `164/194 -> 163/194` まで落とし、過剰に blunt だった

- 変更:

  - `DAYTRADE_SELECTED_STRONG_OVERSOLD_EXTREME_*` を追加

  - `open_vs_sma_atr >= 6.0` または `market_ratio >= 1.20` の `strong_oversold` は、selected base leverage を `0.25` に制限

  - `6.0` は train 実例をほぼ取りこぼさず、`6.5` より説明しやすい round threshold として採用

  - `tests/test_logic.py` に `open_vs_sma_atr` / `market_ratio` の境界テストを追加

- 結果:

  - full:

    - `TOTAL RETURN: +174701.81%` -> `+181775.93%`

    - `PROFIT FACTOR: 7.88` -> `8.33`

    - `WEEKS >= +1%: 186/221` -> `186/221`

    - `POSITIVE WEEKS: 189/221` -> `189/221`

    - `WORST DAY: -18,441,022円` -> `-19,125,392円`

  - strict 6m train:

    - `TOTAL RETURN: +36953.40%` -> `+38533.68%`

    - `PROFIT FACTOR: 3.60` -> `3.76`

    - `WEEKS >= +1%: 164/194` -> `164/194`

    - `POSITIVE WEEKS: 165/194` -> `165/194`

  - contaminated 1m holdout:

    - `TOTAL RETURN: +1.34%` -> `+1.34%`

    - `PROFIT FACTOR: 3.24` -> `3.24`

    - `WEEKS >= +1%: 1/5` -> `1/5`

    - `POSITIVE WEEKS: 3/5` -> `3/5`

  - contaminated 6m holdout:

    - `TOTAL RETURN: +371.76%` -> `+370.77%`

    - `PROFIT FACTOR: 13.36` -> `14.26`

    - `WEEKS >= +1%: 21/26` -> `21/26`

    - `POSITIVE WEEKS: 23/26` -> `23/26`

  - rolling 6m holdout windows:

    - `HOLDOUT WEEKS >= +1%: 464/537` -> `464/537`

    - `HOLDOUT POSITIVE WEEKS: 466/537` -> `466/537`

    - `AVG HOLDOUT RETURN: +205.99%` -> `+208.16%`

    - `AVG HOLDOUT PF: 5.40` -> `5.74`

- 採用:

  - 採用

  - `0.75` より改善が強く、`0.00` のように weekly hit を壊さず、train 主導の shared de-risk として説明できたため

  - absolute `WORST DAY` は増えたが、worst loss pct は `2025-10-20 -6.0947010%` から `2026-02-09 -1.7820282%` へ大きく浅くなり、過熱 oversold を full leverage で抱え込む構造リスクはむしろ低下した

  - contaminated holdout は加点材料に使っていないが、悪化 veto も出なかった

- 再試行するとしたら:

  - `0.00` の no-trade 化は、新しい clean holdout か追加の train 実例が増えるまで再試行しない

  - 次に詰めるなら、`strong_oversold` の例外条件を増やすより、shared な intraday exit / partial exit で残る deep-loss day を浅くする

### 2026-05-20: Mid-Breadth Warm Low-Score `primary` Equity Cap

- 分析:

  - strict 6m `train=2021-05-19` から `2025-11-18` を、未達週の executed trade と full-train setup cluster で再分解すると、依然として主因は `primary` の deep-loss day だった

  - その中でも、単発週の曜日当てではなく shared に崩れていた残差として、

    - breadth `0.45-0.65`

    - `market_ratio 1.05-1.10`

    - score `<= 6`

    - gap `<= 1%`

    - の low-conviction `primary`

    - `9 trades / 1 win / -5.77M`

    - が残っていた

  - 実例は

    - `2024-07-24 8358.T -1.91M`

    - `2024-07-23 2780.T -1.32M`

    - `2023-10-03 6632.T -0.56M`

    - `2023-12-05 4055.T -0.53M`

    - などで、指数は少し上なのに breadth confirmation がまだ mid の局面で、score の弱い continuation を near-full-size で持ちすぎている shared sizing 問題と判断した

- 追試:

  - 同 cluster に対して equity cap `1.40 / 1.20 / 1.10 / 1.00 / 0.75` を比較した

  - `1.40-1.00` は

    - full `WEEKS >= +1%`

    - strict 6m train `WEEKS >= +1%`

    - rolling 6m holdout `HOLDOUT WEEKS >= +1%`

    - を維持したまま return / PF を改善した

  - ただし tighter な `1.20-0.75` は改善幅こそ大きい一方、同じ `2025-10-20` の absolute `WORST DAY` をさらに押し上げ、`9` 実例だけでそこまで強く締める根拠はまだ弱かった

  - そのため、今回は no-trade や probe ではなく、`1.40` の minimal trim に留めた

- 変更:

  - `DAYTRADE_PRIMARY_MID_BREADTH_WARM_LOW_SCORE_*` を追加

  - breadth `0.45-0.65` / `market_ratio 1.05-1.10` / score `<= 6` / gap `<= 1%` の `primary` は、equity notional 上限を `1.40` に制限

  - 既存の tighter cap を優先するため、この cap も `resolve_daytrade_primary_equity_notional_pct` の末尾側で `min()` で適用

  - `tests/test_logic.py` に発火 / 非発火 / stricter-cap 優先の境界テストを追加

- 結果:

  - full:

    - `FINAL EQUITY: Y1,612,504,181` -> `Y1,714,760,122`

    - `TOTAL RETURN: +161150.42%` -> `+171376.01%`

    - `PROFIT FACTOR: 7.76` -> `7.83`

    - `WEEKS >= +1%: 186/221` -> `186/221`

    - `POSITIVE WEEKS: 189/221` -> `189/221`

    - `WORST DAY: -17,011,291円` -> `-18,091,532円`

  - strict 6m train:

    - `FINAL EQUITY: Y341,832,923` -> `Y363,490,224`

    - `TOTAL RETURN: +34083.29%` -> `+36249.02%`

    - `PROFIT FACTOR: 3.51` -> `3.56`

    - `WEEKS >= +1%: 164/194` -> `164/194`

    - `POSITIVE WEEKS: 165/194` -> `165/194`

    - `WORST DAY: -17,011,291円` -> `-18,091,532円`

  - contaminated 1m holdout:

    - `TOTAL RETURN: +1.34%` -> `+1.34%`

    - `PROFIT FACTOR: 3.23` -> `3.24`

    - `WEEKS >= +1%: 1/5` -> `1/5`

    - `POSITIVE WEEKS: 3/5` -> `3/5`

    - `WORST DAY: -2,752,196円` -> `-2,910,977円`

  - contaminated 6m holdout:

    - `TOTAL RETURN: +371.72%` -> `+371.75%`

    - `PROFIT FACTOR: 13.36` -> `13.36`

    - `WEEKS >= +1%: 21/26` -> `21/26`

    - `POSITIVE WEEKS: 23/26` -> `23/26`

    - `WORST DAY: -16,982,273円` -> `-18,064,442円`

  - rolling 6m holdout windows:

    - `HOLDOUT WEEKS >= +1%: 464/537` -> `464/537`

    - `HOLDOUT POSITIVE WEEKS: 466/537` -> `466/537`

    - `AVG HOLDOUT RETURN: +204.50%` -> `+205.37%`

    - `AVG HOLDOUT PF: 5.36` -> `5.39`

- 採用:

  - 採用

  - `WEEKS >= +1%` を落とさずに full / train / rolling の return と PF を押し上げられたため

  - `WORST DAY` の悪化は同じ `2025-10-20` の absolute amount だけで、loss pct は旧 `-6.0943964%`、新 `-6.0947042%` と実質ほぼ不変だった

  - contaminated holdout は加点材料には使っていないが、悪化 veto も出なかった

- 再試行するとしたら:

  - 同 cluster を `1.20-0.75` へさらに tight にする再調整は、新しい clean holdout か追加の train 実例が増えるまで行わない

  - 次に進めるなら、残る deep-loss day を曜日や銘柄属性でさらに細切れにするより、shared intraday de-risk / partial exit の設計を優先する

### 2026-05-20: Monday Tepid Strong-Prev `primary` Equity Cap

- 分析:

  - 最新 baseline 後の strict 6m `train=2021-05-19` から `2025-11-18` を再点検しても、`WEEKS >= +1%` の未達は依然ほぼ deep-loss week で、機会不足より `primary` の大きめ損失が先に課題だった

  - その中で、単発の週当てではなく shared に説明できる残差として、

    - 月曜

    - breadth `0.50-0.65`

    - `market_ratio 1.00-1.05`

    - 非マイナス gap

    - 前日上昇 `>= 6%`

    - `open_vs_sma_atr >= 1.0`

    - の `primary`

    - `3 trades / 1 win / -6.67M`

    - が残っていた

  - 実例は

    - `2024-12-23 7003.T -2.42M`

    - `2025-06-09 6521.T -4.39M`

    - `2023-02-06 4586.T +0.14M`

    - で、週明けに個別だけ先行し、指数 confirmation がまだ tepid な continuation を full-size で張りすぎている shared sizing 問題と判断した

- 追試:

  - 同じ cluster に対して equity cap `1.20 / 1.00 / 0.75 / 0.50` を比較した

  - いずれも

    - full `WEEKS >= +1%`

    - strict 6m train `WEEKS >= +1%`

    - contaminated 6m holdout `WEEKS >= +1%`

    - は維持した

  - ただし `0.75 / 0.50` の tighter cap は、backtest の総リターンはさらに伸びても、絶対額の `WORST DAY` を同じ `2025-10-20` でさらに悪化させ、`3` 実例だけでそこまで強く締める根拠は弱かった

  - そのため、同 cluster を outright no-trade へ寄せるのではなく、まずは `1.00` の minimal trim に留めた

- 変更:

  - `DAYTRADE_PRIMARY_MONDAY_TEPID_STRONG_PREV_*` を追加

  - 月曜の breadth `0.50-0.65` / `market_ratio 1.00-1.05` / 非マイナス gap / 前日上昇 `>= 6%` / trend `>= 1.0 ATR` `primary` は、equity notional 上限を `1.00` に制限

  - `tests/test_logic.py` に発火 / 非発火の境界テストを追加

- 結果:

  - full:

    - `FINAL EQUITY: Y1,581,479,940` -> `Y1,612,504,181`

    - `TOTAL RETURN: +158047.99%` -> `+161150.42%`

    - `PROFIT FACTOR: 7.61` -> `7.76`

    - `WEEKS >= +1%: 186/221` -> `186/221`

    - `POSITIVE WEEKS: 189/221` -> `189/221`

    - `WORST DAY: -16,685,212円` -> `-17,011,291円`

  - strict 6m train:

    - `FINAL EQUITY: Y335,265,960` -> `Y341,832,923`

    - `TOTAL RETURN: +33426.60%` -> `+34083.29%`

    - `PROFIT FACTOR: 3.42` -> `3.51`

    - `WEEKS >= +1%: 164/194` -> `164/194`

    - `POSITIVE WEEKS: 165/194` -> `165/194`

    - `WORST DAY: -16,685,212円` -> `-17,011,291円`

  - contaminated 1m holdout:

    - `TOTAL RETURN: +1.34%` -> `+1.34%`

    - `PROFIT FACTOR: 3.23` -> `3.23`

    - `WEEKS >= +1%: 1/5` -> `1/5`

    - `POSITIVE WEEKS: 3/5` -> `3/5`

    - `WORST DAY: -2,699,270円` -> `-2,752,196円`

  - contaminated 6m holdout:

    - `TOTAL RETURN: +371.71%` -> `+371.72%`

    - `PROFIT FACTOR: 13.36` -> `13.36`

    - `WEEKS >= +1%: 21/26` -> `21/26`

    - `POSITIVE WEEKS: 23/26` -> `23/26`

    - `WORST DAY: -16,656,915円` -> `-16,982,273円`

  - rolling 6m holdout windows:

    - `HOLDOUT WEEKS >= +1%: 464/537` -> `464/537`

    - `HOLDOUT POSITIVE WEEKS: 466/537` -> `466/537`

    - `AVG HOLDOUT RETURN: +202.38%` -> `+204.50%`

    - `AVG HOLDOUT PF: 5.27` -> `5.36`

- 採用:

  - 採用

  - 週次 hit を落とさずに train / full / rolling の return と PF を改善できたため

  - `WORST DAY` の悪化は同じ `2025-10-20` の絶対額だけで、loss pct は旧 `-6.0943279%`、新 `-6.0943964%` と実質不変だった

  - contaminated holdout は加点材料に使っていないが、悪化 veto も出なかった

- 再試行するとしたら:

  - 同じ cluster を `0.75 / 0.50` へさらに tight にする再調整は、新しい clean holdout か追加の train 実例が増えるまで行わない

  - 次に進めるなら、残る `primary` loss cluster を OHLC 条件で細かく切るより、intraday exit / de-risk の shared 設計を優先する

### 2026-05-20: Tepid-Market Hot-Gap `primary` Equity Cap

- 分析:

  - strict 6m `train=2021-05-19` から `2025-11-18` を再分解すると、`WEEKS >= +1%` の未達は `30/194` 週で、

    - 負け週 `28`

    - positive miss `1`

    - no-trade miss `1`

    - だった

  - 依然として主因は `primary` の深い負けで、特に

    - `market_ratio 1.00-1.05`

    - gap `1.5-2.5%`

    - 前日上昇 `6-10%`

    - の「指数は tepid なのに個別だけ熱い continuation」で、full-size compounding が過大になりやすかった

  - これは単一週当ての例外分岐ではなく、「市場確認が弱いのに個別だけ crowded continuation になる日」の shared sizing 問題と判断した

- 追試:

  - 同 cluster を breadth `0.50-0.60` に限定して `cap 1.00 / 0.75` や `probe 0.10` を当てる案は、absolute `WORST DAY` は改善しても `TOTAL RETURN` / `PF` を削ったため不採用

  - 月曜 / 水曜の broad cap や、gap `>= 2%` の広い primary cap も `WEEKS >= +1%` を `184-185/221` へ落としたため不採用

  - 一方で、曜日を限定せず `market_ratio 1.00-1.05` / gap `1.5-2.5%` / 前日上昇 `6-10%` だけを shared size trim する案は、

    - full / train の `WEEKS >= +1%`

    - rolling 6m holdout の `+1%` 週数

    - を維持したまま、`PF` と rolling average return / PF を押し上げた

- 変更:

  - `DAYTRADE_PRIMARY_TEPID_MARKET_HOT_GAP_*` を追加

  - `market_ratio 1.00-1.05` / gap `1.5-2.5%` / 前日上昇 `6-10%` の `primary` は、equity notional 上限を `1.40` に制限

  - 既存のより厳しい cap を優先するため、この cap は `resolve_daytrade_primary_equity_notional_pct` の末尾側で適用

  - `tests/test_logic.py` に境界テストを追加

- 結果:

  - full:

    - `FINAL EQUITY: Y1,565,752,257` -> `Y1,581,479,940`

    - `TOTAL RETURN: +156475.23%` -> `+158047.99%`

    - `PROFIT FACTOR: 7.53` -> `7.61`

    - `WEEKS >= +1%: 186/221` -> `186/221`

    - `POSITIVE WEEKS: 189/221` -> `189/221`

    - `WORST DAY: -16,519,664円` -> `-16,685,212円`

  - strict 6m train:

    - `FINAL EQUITY: Y331,921,537` -> `Y335,265,960`

    - `TOTAL RETURN: +33092.15%` -> `+33426.60%`

    - `PROFIT FACTOR: 3.37` -> `3.42`

    - `WEEKS >= +1%: 164/194` -> `164/194`

    - `POSITIVE WEEKS: 165/194` -> `165/194`

    - `WORST DAY: -16,519,664円` -> `-16,685,212円`

  - contaminated 1m holdout:

    - `TOTAL RETURN: +1.34%` -> `+1.34%`

    - `PROFIT FACTOR: 3.23` -> `3.23`

    - `WEEKS >= +1%: 1/5` -> `1/5`

    - `POSITIVE WEEKS: 3/5` -> `3/5`

    - `WORST DAY: -2,672,806円` -> `-2,699,270円`

  - contaminated 6m holdout:

    - `TOTAL RETURN: +371.72%` -> `+371.71%`

    - `PROFIT FACTOR: 13.36` -> `13.36`

    - `WEEKS >= +1%: 21/26` -> `21/26`

    - `POSITIVE WEEKS: 23/26` -> `23/26`

    - `WORST DAY: -16,494,236円` -> `-16,656,915円`

  - rolling 6m holdout windows:

    - `HOLDOUT WEEKS >= +1%: 464/537` -> `464/537`

    - `HOLDOUT POSITIVE WEEKS: 466/537` -> `466/537`

    - `AVG HOLDOUT RETURN: +201.30%` -> `+202.38%`

    - `AVG HOLDOUT PF: 5.23` -> `5.27`

- 採用:

  - 採用

  - contaminated holdout を加点材料には使っていないが、train と rolling で週次本数を落とさず `PF` を改善できた

  - absolute `WORST DAY` はわずかに悪化したが、同日の worst-day loss pct と max drawdown は実質不変で、shared sizing の説明可能性も保てた

- 再試行するとしたら:

  - 同じ cluster を breadth や曜日でさらに細かく切る再調整は、今回の近傍では再試行しない

  - 次に進めるなら、live decision log を蓄積して intraday exit / partial de-risk を shared に設計するか、新しい clean holdout が積み上がってから sizing を再点検する

### 2026-05-20: Shared `primary` Default Notional Cap Trim

- 分析:

  - strict 6m `train=2021-05-19` から `2025-11-18` を、`+1%` 未達週、負け日、notional 比率で再点検した

  - `+1%` 未達は `29/194` 週まで絞れていたが、そのうち `28` 週は負け週で、positive miss は `2022-W10` の `inverse_pullback 1459.T +5,687円` だけだった

  - 未達週の損失源は依然として `primary` が最大で、

    - `62 trades / 12 wins / -31.79M`

    - だった

  - さらに大損日の多くで、`primary` の notional が equity 比 `1.95-2.00x` 近くまで張り付いており、OHLC 条件を細かく足す前に shared な資金管理がまだ強すぎると判断した

- 追試:

  - regime 別 no-trade / probe:

    - 月曜 `primary` の mild-hot / below-SMA

    - 火曜 stretched `fallback`

    - high-breadth tepid-hot gap chase `primary`

    - を個別に no-trade / probe 化した

  - いずれも `TOTAL RETURN` や `PF` は改善近傍があったが、

    - `WEEKS >= +1%`

    - `186/221`

    - `164/194`

    - は 1 本も増えず、absolute `WORST DAY` が悪化したため不採用

  - shared notional の default cap:

    - `primary 1.50 / 1.25 / 1.00`

    - は `WEEKS >= +1%` を大きく落とした

  - 一方で `primary 1.95`

    - だけは週次本数を維持したまま absolute `WORST DAY` を縮めた

- 変更:

  - `DAYTRADE_PRIMARY_MAX_EQUITY_NOTIONAL_PCT` を `2.00 -> 1.95` に引き下げた

  - `tests/test_logic.py` の default cap 期待値を新 baseline に更新した

- 結果:

  - full:

    - `FINAL EQUITY: Y1,684,031,607` -> `Y1,565,752,257`

    - `CLOSED TRADES: 460` -> `462`

    - `WIN RATE: 58.04%` -> `58.23%`

    - `WEEKS >= +1%: 186/221` -> `186/221`

    - `POSITIVE WEEKS: 189/221` -> `189/221`

    - `TOTAL RETURN: +168303.16%` -> `+156475.23%`

    - `PROFIT FACTOR: 7.64` -> `7.53`

    - `AVG MONTH ACTIVE RATE: 44.55%` -> `44.73%`

    - `MONTHS >= 3/4 ACTIVE: 1/51` -> `1/51`

    - `WORST DAY: -17,654,208円` -> `-16,519,664円`

  - strict 6m train:

    - `TOTAL RETURN: +34888.89%` -> `+33092.15%`

    - `PROFIT FACTOR: 3.38` -> `3.37`

    - `WEEKS >= +1%: 164/194` -> `164/194`

    - `POSITIVE WEEKS: 165/194` -> `165/194`

    - `WORST DAY: -17,357,436円` -> `-16,519,664円`

  - contaminated 6m holdout:

    - `TOTAL RETURN: +381.30%` -> `+371.72%`

    - `PROFIT FACTOR: 13.51` -> `13.36`

    - `WEEKS >= +1%: 21/26` -> `21/26`

    - `POSITIVE WEEKS: 23/26` -> `23/26`

    - `WORST DAY: -17,654,208円` -> `-16,494,236円`

- 採用:

  - 採用

  - 週次本数を守ったまま absolute `WORST DAY` を縮められた、もっとも shared で説明可能な改善だった

- 再試行するとしたら:

  - 同じ OHLC feature を細かく切る no-trade / probe は、今回確認した cluster 近傍では再試行しない

  - 次に進めるなら、

    - live decision log を使った intraday exit / partial de-risk

    - または新しい clean holdout が積み上がった後の shared sizing 再点検

    - に限定する

### 2026-05-19: Live Daytrade Decision Logging

- 分析:

  - current baseline までで、OHLC 日足だけの shared rule 追加は

    - `WEEKS >= +1%`

    - strict train の未達週

    - absolute `WORST DAY`

    - の観点で改善余地がかなり薄くなった

  - 一方で live 実行側には

    - shared scan で何が上位に来たか

    - board 価格や AI filter で何が落ちたか

    - sizing の結果どの候補が 100 株未満になったか

    - 実際にどの leverage / buying power / stop で約定したか

    - が構造化ログとして残っていなかった

  - この状態では、intraday 順序情報や live/backtest divergence を使った shared exit / de-risk の研究を進めにくかった

- 変更:

  - `auto_trade.py` に `daytrade_decisions.csv` 出力を追加

  - `core/config.py` に decision log の保存先を追加

  - `core/preflight.py` で decision log を保護対象に追加

  - scan candidate / weekly guard / selected leverage zero / board gap filter / AI filter / size floor / filled order までを、同じ CSV へ追記するようにした

  - 併せて、scan 失敗時に `snapshot` 未定義で後続評価が壊れる余地と、actionable candidate がない日に stale watchlist が残る余地を塞いだ

- 結果:

  - 戦略ロジック自体は不変

  - backtest baseline の数値変化はなし

  - 今後は contaminated holdout を見ながら日足条件を当て込むのではなく、live decision log を使って

    - shared entry mismatch

    - intraday stop / partial de-risk 候補

    - size failure cluster

    - を証拠ベースで点検できる状態になった

- 採用:

  - 採用

  - ただし observability 強化であり、売買ロジック変更ではない

- 再試行するとしたら:

  - 同じ OHLC residual を再度細かく切る前に、まずこの decision log を数週間分ためる

  - そのうえで

    - live で repeatedly skipped される cluster

    - live fill 後に悪化する intraday path

    - backtest では勝つのに live で取れていない cluster

    - を shared な execution / exit / probe 設計へ落とす

### 2026-05-19: Residual Warm-Continuation / Hot-Gap `primary` Recheck

- 分析:

  - `High-Breadth Tepid-Market Early-Week strong_oversold No-Trade` 採用後の strict 6m `train=2021-05-19` から `2025-11-18` を再分解すると、

    - `WEEKS >= +1%: 164/194`

    - `POSITIVE WEEKS: 165/194`

    - で、残る `+1%` 未達はほぼすべて deep-loss week のままだった

  - setup 別では、miss week 内の負け源は依然として `primary` が中心で、

    - `62 trades / 12 wins / -31.79M`

    - だった

  - そのため、残差の中でも train 実例が複数あり、かつ contaminated holdout で勝ち筋を壊しにくそうな `primary` shared family だけを追加で点検した

  - 近い `+1%` 未達週も洗い直したが、唯一の positive miss は `2022-W10` の

    - `inverse_pullback 1459.T +5,687円`

    - だけで、shared rule で `+1%` へ押し上げられる余地は実質なかった

- 追試:

  - 月曜 `primary`

    - breadth `0.55-0.60`

    - `market_ratio 1.05-1.10`

    - `open_vs_sma_atr < 0`

    - の warm below-SMA continuation:

    - `no-trade`: `FULL TOTAL RETURN +168303.16% -> +182883.41%`, `PF 7.64 -> 7.76`, `WEEKS >= +1% 186/221 -> 186/221`, `TRAIN WEEKS >= +1% 164/194 -> 164/194`, `HOLDOUT 6m RETURN +381.30% -> +381.31%`, `WORST DAY -17,654,208円 -> -19,181,976円`

    - `probe 0.10`: `FULL TOTAL RETURN +168303.16% -> +175270.74%`, `PF 7.64 -> 7.70`, `WEEKS >= +1% 186/221 -> 186/221`, `TRAIN WEEKS >= +1% 164/194 -> 164/194`, `WORST DAY -17,654,208円 -> -18,382,727円`

  - 火曜 `primary`

    - `market_ratio 1.05-1.10`

    - gap `0-0.5%`

    - score `< 6.0`

    - の warm flat-gap low-score continuation:

    - `no-trade`: `FULL TOTAL RETURN +168303.16% -> +190417.28%`, `PF 7.64 -> 7.76`, `WEEKS >= +1% 186/221 -> 186/221`, `TRAIN WEEKS >= +1% 164/194 -> 164/194`, `HOLDOUT 6m RETURN +381.30% -> +381.35%`, `WORST DAY -17,654,208円 -> -19,974,152円`

    - `probe 0.10`: `FULL TOTAL RETURN +168303.16% -> +178787.81%`, `PF 7.64 -> 7.70`, `WEEKS >= +1% 186/221 -> 186/221`, `TRAIN WEEKS >= +1% 164/194 -> 164/194`, `WORST DAY -17,654,208円 -> -18,750,523円`

  - 月火水 `primary`

    - breadth `< 0.60`

    - `market_ratio 1.05-1.10`

    - gap `0-0.5%`

    - score `< 6.0`

    - の early-week low-conviction continuation:

    - `no-trade`: `FULL TOTAL RETURN +168303.16% -> +203536.94%`, `PF 7.64 -> 7.87`, `WEEKS >= +1% 186/221 -> 186/221`, `TRAIN WEEKS >= +1% 164/194 -> 164/194`, `HOLDOUT 6m RETURN +381.30% -> +381.34%`, `WORST DAY -17,654,208円 -> -21,346,314円`

    - `probe 0.10`: `FULL TOTAL RETURN +168303.16% -> +185394.39%`, `PF 7.64 -> 7.76`, `WEEKS >= +1% 186/221 -> 186/221`, `TRAIN WEEKS >= +1% 164/194 -> 164/194`, `WORST DAY -17,654,208円 -> -19,443,677円`

  - 水曜 `primary`

    - `market_ratio 1.00-1.05`

    - gap `1.5-2.5%`

    - 前日上昇 `6-10%`

    - の tepid hot-gap continuation `no-trade`:

    - `FULL TOTAL RETURN +168303.16% -> +177407.54%`

    - `PF 7.64 -> 7.74`

    - `WEEKS >= +1% 186/221 -> 186/221`

    - `POSITIVE WEEKS 189/221 -> 190/221`

    - `TRAIN WEEKS >= +1% 164/194 -> 164/194`

    - `TRAIN POSITIVE WEEKS 165/194 -> 166/194`

    - `HOLDOUT 6m RETURN +381.30% -> +381.34%`

    - `HOLDOUT WEEKS >= +1% 21/26 -> 21/26`

    - `WORST DAY -17,654,208円 -> -18,609,063円`

    - `ROLLING HOLDOUT POSITIVE WEEKS 466/537 -> 472/537`

  - 参考として、上の early-week low-score と水曜 tepid hot-gap を併用すると

    - `FULL TOTAL RETURN +214268.60%`

    - `PF 7.97`

    - `POSITIVE WEEKS 190/221`

    - `WEEKS >= +1% 186/221`

    - `WORST DAY -22,470,921円`

    - で、headline return は大きく伸びても最優先の週次本数は増えなかった

- 結果:

  - 追加採用なし

  - 今回の候補はすべて

    - return / PF

    - rolling average return / PF

    - positive weeks

    - を改善する近傍があった一方、`WEEKS >= +1%` を `186/221` / `164/194` から 1 本も押し上げられなかった

  - さらに absolute `WORST DAY` は一貫して悪化し、max daily loss pct と max drawdown は据え置きでも、週次本数の改善なしで受け入れる理由が弱かった

- 採用:

  - 不採用

- 再試行するとしたら:

  - 同じ warm continuation cluster を、同じ `selected leverage no-trade / probe` 形のままで再試行しない

  - 次に進めるなら、

    - 直近の新しい train 実例で residual がさらに増えたとき

    - あるいは intraday 順序情報を使って shared exit / partial de-risk を作れるとき

    - に限定する

  - 現在の OHLC 日足だけで続けるなら、headline return を追うより `WEEKS >= +1%` を実際に増やせる shared change が見えるまで baseline を維持する

### 2026-05-19: High-Breadth Tepid-Market Early-Week `strong_oversold` No-Trade

- 分析:

  - current baseline の strict 6m `train=2021-05-19` から `2025-11-18` を、未達週と負け日の原因に絞って再分解した

  - high-breadth / early-week の `strong_oversold` を broad に見ると、

    - 月火水

    - breadth `>= 0.65`

    - `open_vs_sma_atr >= 4.0`

    - の帯は `7 trades / 3 wins / -5.07M`

    - で、`2025-W31` の `1579.T` 連敗を含んでいた

  - ただし breadth だけで broad no-trade にすると、contaminated holdout `2026-W04` の

    - `market_ratio 1.20-1.24`

    - `open_vs_sma_atr 11-13`

    - の `1579.T` hot rebound 3連打まで削って、週次成績を `+1.62% -> +0.67%` へ落とした

  - そこで同じ cluster を `market_ratio` で分けると、

    - 月火水

    - breadth `>= 0.70`

    - `market_ratio 1.00-1.10`

    - `open_vs_sma_atr >= 4.0`

    - の `strong_oversold`

    - だけが `3 trades / 1 win / -4.94M`

    - で、実質的に `2025-W31` の tepid continuation 連敗へ集中していた

- 変更:

  - `resolve_daytrade_selected_leverage` に、

    - 月火水

    - breadth `>= 0.70`

    - `market_ratio 1.00-1.10`

    - `open_vs_sma_atr >= 4.0`

    - の `strong_oversold`

    - no-trade guard

    - を追加

  - `tests/test_logic.py` に、

    - 上記 guard の発火

    - 木曜では発火しないこと

    - `market_ratio 1.20+` の hot rebound では発火しないこと

    - を追加

- 結果:

  - full:

    - `FINAL EQUITY: Y1,636,793,458` -> `Y1,684,031,607`

    - `CLOSED TRADES: 463` -> `460`

    - `WIN RATE: 57.88%` -> `58.04%`

    - `WEEKS >= +1%: 185/221` -> `186/221`

    - `POSITIVE WEEKS: 188/221` -> `189/221`

    - `TOTAL RETURN: +163579.35%` -> `+168303.16%`

    - `PROFIT FACTOR: 7.43` -> `7.64`

    - `AVG MONTH ACTIVE RATE: 44.82%` -> `44.55%`

    - `MONTHS >= 3/4 ACTIVE: 1/51` -> `1/51`

    - `WORST DAY: -17,159,098円` -> `-17,654,208円`

  - strict 6m train:

    - `TOTAL RETURN: +33906.64%` -> `+34888.89%`

    - `PROFIT FACTOR: 3.25` -> `3.38`

    - `WEEKS >= +1%: 163/194` -> `164/194`

    - `POSITIVE WEEKS: 164/194` -> `165/194`

    - `WORST DAY: -16,870,826円` -> `-17,357,436円`

  - holdout 6m:

    - `TOTAL RETURN: +381.32%` -> `+381.30%`

    - `PROFIT FACTOR: 13.51` -> `13.51`

    - `WEEKS >= +1%: 21/26` -> `21/26`

    - `POSITIVE WEEKS: 23/26` -> `23/26`

    - `WORST DAY: -17,159,098円` -> `-17,654,208円`

  - current 1m holdout:

    - `TOTAL RETURN: +1.34%` -> `+1.34%`

    - `PROFIT FACTOR: 3.24` -> `3.24`

    - `WEEKS >= +1%: 1/5` -> `1/5`

    - `POSITIVE WEEKS: 3/5` -> `3/5`

    - `WORST DAY: -2,778,660円` -> `-2,858,050円`

  - rolling 6m holdout windows:

    - `HOLDOUT WEEKS >= +1%: 458/537` -> `464/537`

    - `HOLDOUT POSITIVE WEEKS: 460/537` -> `466/537`

    - `AVG HOLDOUT RETURN: +202.84%` -> `+205.61%`

    - `AVG HOLDOUT PF: 5.13` -> `5.27`

    - `WINDOWS WITH ALL WEEKS >= +1%: 2/21` -> `2/21`

- 採用:

  - 採用

  - breadth だけの broad defense では hot rebound まで削ってしまったが、tepid-market に絞ると

    - full / train の `WEEKS >= +1%`

    - full / train / walkforward の return と PF

    - を同時に改善でき、contaminated holdout の headline も維持できたため

  - 名目の `WORST DAY` は悪化したが、worst day loss pct は `-10.352% -> -10.306%`、max drawdown は `-28.72% -> -28.61%` へ改善しており、絶対額悪化は compounding と判断した

  - 同帯の probe `0.10` は `POSITIVE WEEKS` は増えても `WEEKS >= +1%` を改善できなかったため不採用

- 再試行するとしたら:

  - `market_ratio` 上限なしの broad high-breadth early-week `strong_oversold` defense は、そのまま再試行しない

  - 次に進めるなら、`market_ratio 1.10-1.20` の warm 帯に train 実例が増えたときだけ、hot rebound を壊さない追加 signal があるか再点検する

### 2026-05-19: Cache Refresh and Strict-Train Residual Recheck

- 分析:

  - `jp_jquants_fetcher_v2.py --refresh-overlap-days 7` を再実行し、キャッシュ最新日を `2026-05-15` から `2026-05-18` へ更新した

  - この最新日を基準にすると、strict 6m split は

    - `train=2021-05-19` から `2025-11-18`

    - `holdout=2025-11-19` から `2026-05-18`

    - へ切り替わる

  - 現行 baseline の strict 6m `train` は

    - `WEEKS >= +1%: 162/194`

    - `POSITIVE WEEKS: 163/194`

    - で、未達 `32` 週の内訳は

    - `loss 31`

    - `positive miss 1`

    - だった

  - したがって今回の作業テーマは、惜しい勝ち週を増やすことではなく、deep-loss week を shared rule で浅くできるかの再点検と判断した

  - train の残差を setup / breadth / `market_ratio` / `prev_return` / `open_vs_sma_atr` で再分解すると、

    - `primary` の `market_ratio 1.02-1.05` かつ `prev_return 4-5%` は `5 trades / 0 wins / -8.28M`

    - 火曜 `fallback` の `open_vs_sma_atr 2.0-3.0` は `6 trades / 0 wins / -2.51M`

    - 月曜 `fallback` の `market_ratio 1.02-1.05` は `3 trades / 0 wins / -1.79M`

    - 月火 `strong_oversold` の `open_vs_sma_atr >= 6.0` は `7 trades / 2 wins / -10.23M`

    - が候補になった

- 追試:

  - `primary` `market_ratio 1.02-1.05` / `prev_return 4-5%` を candidate skip:

    - `FULL WEEKS >= +1%: 184/221 -> 184/221`

    - `TRAIN WEEKS >= +1%: 162/194 -> 162/194`

    - `FULL TOTAL RETURN: +143616.70% -> +148307.60%`

    - `FULL PF: 7.03 -> 7.25`

    - ただし `max drawdown: -28.72% -> -31.85%` に悪化

  - 月曜 `fallback` `market_ratio 1.02-1.05` の selected no-trade:

    - 週次本数は据え置き

    - `FULL TOTAL RETURN: +143616.70% -> +144644.00%`

    - `FULL PF: 7.03 -> 7.06`

    - ただし rolling 6m holdout の平均 return / PF はわずかに悪化

  - 火曜 `fallback` `open_vs_sma_atr 2.0-3.0` の candidate skip:

    - 週次本数は据え置き

    - `FULL TOTAL RETURN: +143616.70% -> +152505.28%`

    - `TRAIN PF: 3.02 -> 3.06`

    - ただし contaminated holdout と worst day が悪化

  - 月火 `strong_oversold` `open_vs_sma_atr >= 6.0` の no-trade:

    - `TRAIN WEEKS >= +1%: 162/194 -> 161/194`

    - `FULL WEEKS >= +1%: 184/221 -> 183/221`

    - のため即不採用

- 結果:

  - 追加採用なし

  - baseline は現行ロジックを維持

  - `2026-05-18` 最新データ基準の確認値:

    - full:

      - `FINAL EQUITY: Y1,437,166,975`

      - `TOTAL RETURN: +143616.70%`

      - `PROFIT FACTOR: 7.03`

      - `WEEKS >= +1%: 184/221`

      - `POSITIVE WEEKS: 187/221`

      - `WORST DAY: -15,065,490円`

    - strict 6m train:

      - `TOTAL RETURN: +29758.99%`

      - `PROFIT FACTOR: 3.02`

      - `WEEKS >= +1%: 162/194`

      - `POSITIVE WEEKS: 163/194`

    - current 6m holdout:

      - `TOTAL RETURN: +381.32%`

      - `PROFIT FACTOR: 13.51`

      - `WEEKS >= +1%: 21/26`

      - `POSITIVE WEEKS: 23/26`

    - current 1m holdout:

      - `TOTAL RETURN: +1.34%`

      - `PROFIT FACTOR: 3.24`

      - `WEEKS >= +1%: 1/5`

      - `POSITIVE WEEKS: 3/5`

      - `WORST DAY: -2,434,635円`

    - rolling 6m holdout windows:

      - `AVG HOLDOUT RETURN: +197.90%`

      - `AVG HOLDOUT PF: 5.04`

      - `HOLDOUT WEEKS >= +1%: 458/537`

      - `HOLDOUT POSITIVE WEEKS: 460/537`

      - `WINDOWS WITH ALL WEEKS >= +1%: 2/21`

- 採用:

  - 不採用

- 再試行するとしたら:

  - `primary` の `market_ratio 1.02-1.05` / `prev_return 4-5%` は、return と PF は伸びても max drawdown を悪化させるため、同じ shared skip 形では再試行しない

  - 月曜 `fallback` `market_ratio 1.02-1.05` と火曜 `fallback open_vs_sma_atr 2.0-3.0` も、週次本数を増やせないうえ contaminated holdout / walkforward を改善できなかったため同じ形では再試行しない

  - 次に進めるなら、train に再現例が増えるまで、残るテーマは `primary` の low-breadth / tepid-market residual か、intraday 順序情報を使った shared exit 設計に限定する

### 2026-05-19: Monday/Tuesday Residual Sizing Follow-up

- 分析:

  - strict-train の残差をさらに coarse regime で見直すと、`primary` の deep loss は次の 3 塊が残っていた

    - 火曜 `market_ratio 1.05-1.10` かつ `prev_return 4-5%`: `5 trades / 0 wins / -6.95M`

    - 月曜 `prev_return 7-10%`: `8 trades / 3 wins / -13.41M`

    - 月曜 `breadth < 0.45` かつ `market_ratio 1.00-1.05`: `5 trades / 2 wins / -8.25M`

  - 方針は entry filter の追加ではなく、shared `selected leverage` で `no-trade` と `probe` を比較し、週次本数を落とさず deep-loss week を浅くできるかを確認することにした

- 追試:

  - 火曜 `primary` `market_ratio 1.05-1.10` / `prev_return 4-5%`

    - `no-trade`: `FULL TOTAL RETURN +143616.70% -> +117696.59%`, `PF 7.03 -> 7.29`, `WEEKS >= +1% 184/221 -> 183/221`, `WORST DAY -15,065,490円 -> -12,349,458円`

    - `probe 0.10`: `FULL TOTAL RETURN +143616.70% -> +124571.46%`, `PF 7.03 -> 7.26`, `WEEKS >= +1% 184/221 -> 183/221`, `WORST DAY -15,065,490円 -> -13,070,904円`

  - 月曜 `primary` `prev_return 7-10%`

    - `no-trade`: `FULL TOTAL RETURN +143616.70% -> +127890.49%`, `WEEKS >= +1% 184/221 -> 181/221`, `HOLDOUT 6m RETURN +381.32% -> +326.07%`, `WORST DAY -15,065,490円 -> -40,259,399円`

    - `probe 0.10`: `FULL TOTAL RETURN +143616.70% -> +180735.32%`, `PF 7.03 -> 7.52`, `WEEKS >= +1% 184/221 -> 184/221`, `HOLDOUT 6m RETURN +381.32% -> +360.60%`, `WORST DAY -15,065,490円 -> -18,955,640円`

  - 月曜 `primary` `breadth < 0.45` / `market_ratio 1.00-1.05`

    - `no-trade`: `FULL TOTAL RETURN +143616.70% -> +151563.78%`, `PF 7.03 -> 7.48`, `WEEKS >= +1% 184/221 -> 184/221`, `HOLDOUT 6m RETURN +381.32% -> +381.31%`, `WORST DAY -15,065,490円 -> -15,900,104円`

    - `probe 0.10`: `FULL TOTAL RETURN +143616.70% -> +147297.53%`, `PF 7.03 -> 7.41`, `WEEKS >= +1% 184/221 -> 184/221`, `HOLDOUT 6m RETURN +381.32% -> +381.33%`, `WORST DAY -15,065,490円 -> -15,454,505円`

- 結果:

  - 追加採用なし

  - 火曜 warm continuation は `0 wins` だったが、shared `no-trade/probe` どちらでも週次本数を `1` 本落とした

  - 月曜 `prev_return 7-10%` の `probe 0.10` は return / PF / walkforward を大きく押し上げたが、`WORST DAY` と contaminated holdout return を悪化させた

  - 月曜 low-breadth / tepid-market residual は、週次本数を落とさず return / PF / walkforward を改善した一方、`WORST DAY` を baseline より悪化させた

- 採用:

  - 不採用

- 再試行するとしたら:

  - 月曜 low-breadth / tepid-market residual だけは、`breadth < 0.45` / `market_ratio 1.00-1.05` という粗い切り方のままではなく、`prev_return` や `open_vs_sma_atr` を足して day-loss pct まで比較し、`WORST DAY` 悪化を抑えられる narrower shared sizing へ絞る

  - 月曜 `prev_return 7-10%` は、同じ broad cap 形のままでは contaminated holdout と worst-day 悪化が大きいため再試行しない

  - 火曜 `market_ratio 1.05-1.10` / `prev_return 4-5%` も、同じ shared skip/probe 形では週次本数を落とすため再試行しない

### 2026-05-19: Monday Low-Breadth Tepid Gap `primary` Probe

- 分析:

  - 上の coarse residual をそのまま使うと、`breadth < 0.45` の切り方がやや狭く、shared rule として不自然だった

  - そこで月曜 `primary` のうち

    - breadth `< 0.50`

    - `market_ratio 1.00-1.05`

    - gap `>= 1.0%`

    - の continuation を見ると、strict 6m `train` で `5 trades / 1 win / -9.62M` だった

  - 実例は

    - `2024-11-25 6240.T -6.03M`

    - `2024-12-09 5838.T -3.51M`

    - `2022-12-05 3498.T -0.16M`

    - `2022-10-24 2980.T -0.13M`

    - `2022-11-07 7610.T +0.21M`

    - で、弱 breadth なのに指数は「崩れてはいない」程度、そこへ個別だけギャップで飛ぶ Monday continuation は、週明けの利食いと寄り天に巻き戻されやすかった

  - 同じ週 `2022-W49` は、Monday の損失を probe 化すると `-0.12M` から `+0.13M` へ転じ、`WEEKS >= +1%` を `1` 週埋められた

- 変更:

  - `resolve_daytrade_selected_leverage` に

    - 月曜

    - breadth `< 0.50`

    - `market_ratio 1.00-1.05`

    - gap `>= 1.0%`

    - の `primary` は selected leverage cap `0.10`

    - を追加

  - `tests/test_logic.py` に、発火条件と breadth / gap 境界の回帰テストを追加

- 結果:

  - full:

    - `FINAL EQUITY: Y1,437,166,975` -> `Y1,636,793,458`

    - `CLOSED TRADES: 467` -> `463`

    - `WIN RATE: 57.60%` -> `57.88%`

    - `WEEKS >= +1%: 184/221` -> `185/221`

    - `POSITIVE WEEKS: 187/221` -> `188/221`

    - `TOTAL RETURN: +143616.70%` -> `+163579.35%`

    - `PROFIT FACTOR: 7.03` -> `7.43`

    - `AVG MONTH ACTIVE RATE: 45.19%` -> `44.82%`

    - `WORST DAY: -15,065,490円` -> `-17,159,098円`

  - strict 6m train:

    - `FINAL EQUITY: Y298,589,928` -> `Y340,066,374`

    - `TOTAL RETURN: +29758.99%` -> `+33906.64%`

    - `PROFIT FACTOR: 3.02` -> `3.25`

    - `WEEKS >= +1%: 162/194` -> `163/194`

    - `POSITIVE WEEKS: 163/194` -> `164/194`

  - holdout 6m:

    - `TOTAL RETURN: +381.32%` -> `+381.32%`

    - `PROFIT FACTOR: 13.51` -> `13.51`

    - `WEEKS >= +1%: 21/26` -> `21/26`

    - `POSITIVE WEEKS: 23/26` -> `23/26`

  - holdout 1m:

    - `TOTAL RETURN: +1.34%` -> `+1.34%`

    - `PROFIT FACTOR: 3.24` -> `3.24`

    - `WEEKS >= +1%: 1/5` -> `1/5`

    - `POSITIVE WEEKS: 3/5` -> `3/5`

    - `WORST DAY: -2,434,635円` -> `-2,778,660円`

  - rolling 6m holdout windows:

    - `AVG HOLDOUT RETURN: +197.90%` -> `+202.84%`

    - `AVG HOLDOUT PF: 5.04` -> `5.13`

    - `HOLDOUT WEEKS >= +1%: 458/537` -> `458/537`

    - `HOLDOUT POSITIVE WEEKS: 460/537` -> `460/537`

    - `WINDOWS WITH ALL WEEKS >= +1%: 2/21` -> `2/21`

  - リスク補足:

    - max daily loss pct は `-10.35%` で不変

    - max drawdown も `-28.72%` で不変

    - absolute `WORST DAY` は equity growth の後段で悪化したが、max daily loss pct と max drawdown の悪化は確認されなかった

- 採用:

  - 採用

- 判断:

  - 汚染済み holdout は改善根拠に使わない前提でも、strict train で `+1` 週、rolling holdout で平均 return / PF を改善し、max drawdown と max daily loss pct を悪化させなかったため、shared probe として採用した

  - no-trade ではなく `0.10` probe にしたことで、脆い continuation を縮小しつつ、完全停止より週次達成率が良かった

### 2026-05-19: Monday Tepid Continuation `primary` Probe

- 分析:

  - `Warm-Market Failed-Continuation primary No-Trade` 採用後も、strict 6m `train=2021-05-19` から `2025-11-14` の miss week を再分解すると、週明けの continuation chase がまだ残っていた

  - その中でも

    - 月曜

    - `market_ratio 1.00-1.05`

    - gap `0-1%`

    - 前日上昇 `2-4%`

    - の `primary`

    - が `7 trades / 0 wins / -5.50M`

    - だった

  - 実例は

    - `2025-05-12 3823.T -3.40M`

    - `2025-07-14 3350.T -1.23M`

    - `2023-03-27 3989.T -0.44M`

    - `2023-04-03 6590.T -0.27M`

    - などで、指数は強くないのに週明けの flat gap を continuation とみなして追うと、週末のポジション調整や需給の巻き戻しに負けやすかった

  - full no-trade も比較したが、return が baseline より落ちたため不採用

  - `0.10` probe は strict train / rolling を改善しつつ、day-loss pct と max drawdown をほぼ据え置けたため、週明けは「完全否定ではなく小さく試す」が shared として自然だと判断した

- 変更:

  - `resolve_daytrade_selected_leverage` に、

    - 月曜

    - `market_ratio 1.00-1.05`

    - gap `0-1%`

    - 前日上昇 `2-4%`

    - の `primary` probe selected leverage cap `0.10`

    - を追加

  - `tests/test_logic.py` に、上記 cap の発火 / 曜日境界を追加

- 結果:

  - full:

    - `FINAL EQUITY: Y1,304,317,641` -> `Y1,439,601,610`

    - `CLOSED TRADES: 467` -> `466`

    - `WIN RATE: 57.82%` -> `57.73%`

    - `WEEKS >= +1%: 184/220` -> `184/220`

    - `POSITIVE WEEKS: 188/220` -> `188/220`

    - `TOTAL RETURN: +130331.76%` -> `+143860.16%`

    - `PROFIT FACTOR: 7.00` -> `7.11`

    - `AVG MONTH ACTIVE RATE: 45.15%` -> `45.06%`

    - `WORST DAY: -13,650,890円` -> `-15,065,490円`

  - strict 6m train:

    - `TOTAL RETURN: +27471.03%` -> `+30329.56%`

    - `PROFIT FACTOR: 3.08` -> `3.15`

    - `WEEKS >= +1%: 162/194` -> `162/194`

    - `POSITIVE WEEKS: 163/194` -> `163/194`

  - holdout 6m:

    - `TOTAL RETURN: +373.08%` -> `+373.09%`

    - `PROFIT FACTOR: 13.04` -> `13.04`

    - `WEEKS >= +1%: 22/26` -> `22/26`

    - `POSITIVE WEEKS: 25/26` -> `25/26`

  - current 1m holdout:

    - `TOTAL RETURN: +1.51%` -> `+1.51%`

    - `PROFIT FACTOR: 4.55` -> `4.55`

    - `WEEKS >= +1%: 1/4` -> `1/4`

    - `POSITIVE WEEKS: 4/4` -> `4/4`

  - rolling 6m holdout windows:

    - `AVG HOLDOUT RETURN: +200.26%` -> `+201.29%`

    - `AVG HOLDOUT PF: 4.88` -> `4.93`

    - `TOTAL HOLDOUT TRADES: 1133` -> `1127`

- 採用:

  - 採用

  - 月曜の continuation 失敗を full no-trade ではなく probe に落とすことで、strict train と rolling の return / PF を押し上げられたため

  - nominal `WORST DAY` は増えたが、worst-day pct は `-1.7824% -> -1.7822%` でほぼ横ばい、max drawdown も `-28.7183%` のままだった

- 再試行するとしたら:

  - 同帯の full no-trade は再試行しない

  - 次に触るなら、週明け continuation をさらに絞るのではなく、別の low-sponsorship regime に train 実例が増えたときだけにする

### 2026-05-19: Warm-Market Failed-Continuation `primary` No-Trade

- 分析:

  - `Broad Hot Low-Score primary No-Trade` 採用後の strict 6m `train=2021-05-19` から `2025-11-14` を再分解すると、次にきれいだったのは「前日上げたのに朝は小さく弱い failed continuation」だった

  - 具体的には

    - `market_ratio 1.05-1.10`

    - gap `-1%〜0%`

    - 前日上昇 `2-4%`

    - の `primary`

    - が `4 trades / 0 wins / -9.28M`

    - だった

  - 実例は

    - `2025-07-25 4593.T -4.49M`

    - `2025-08-01 4593.T -3.03M`

    - `2024-06-05 5801.T -1.74M`

    - `2023-08-07 3561.T -0.03M`

    - で、指数はやや強いのに銘柄は上にギャップできず、前日の momentum も `2-4%` に留まる「弱い継続期待」が一貫して負けていた

  - 同帯の `0.10` probe と `0.00` no-trade を比べると、week hit は同じでも `0.00` のほうが strict train / full / rolling の return と PF が強かった

- 変更:

  - `resolve_daytrade_selected_leverage` に、

    - `market_ratio 1.05-1.10`

    - gap `-1%〜0%`

    - 前日上昇 `2-4%`

    - の `primary` no-trade guard

    - を追加

  - `tests/test_logic.py` に、上記 guard の発火 / 境界を追加

- 結果:

  - full:

    - `FINAL EQUITY: Y1,173,557,665` -> `Y1,304,317,641`

    - `CLOSED TRADES: 471` -> `467`

    - `WIN RATE: 57.32%` -> `57.82%`

    - `WEEKS >= +1%: 184/220` -> `184/220`

    - `POSITIVE WEEKS: 188/220` -> `188/220`

    - `TOTAL RETURN: +117255.77%` -> `+130331.76%`

    - `PROFIT FACTOR: 6.55` -> `7.00`

    - `AVG MONTH ACTIVE RATE: 45.52%` -> `45.15%`

    - `WORST DAY: -12,278,728円` -> `-13,650,890円`

  - strict 6m train:

    - `TOTAL RETURN: +24705.74%` -> `+27471.03%`

    - `PROFIT FACTOR: 2.84` -> `3.08`

    - `WEEKS >= +1%: 162/194` -> `162/194`

    - `POSITIVE WEEKS: 163/194` -> `163/194`

  - holdout 6m:

    - `TOTAL RETURN: +373.10%` -> `+373.08%`

    - `PROFIT FACTOR: 13.05` -> `13.04`

    - `WEEKS >= +1%: 22/26` -> `22/26`

    - `POSITIVE WEEKS: 25/26` -> `25/26`

  - current 1m holdout:

    - `TOTAL RETURN: +1.51%` -> `+1.51%`

    - `PROFIT FACTOR: 4.56` -> `4.55`

    - `WEEKS >= +1%: 1/4` -> `1/4`

    - `POSITIVE WEEKS: 4/4` -> `4/4`

  - rolling 6m holdout windows:

    - `AVG HOLDOUT RETURN: +193.43%` -> `+200.26%`

    - `AVG HOLDOUT PF: 4.64` -> `4.88`

    - `TOTAL HOLDOUT TRADES: 1148` -> `1133`

- 採用:

  - 採用

  - all-loss train cluster を shared no-trade にして、strict train、full、rolling の PF を一段押し上げられたため

  - nominal `WORST DAY` は増えたが、worst-day pct は `-1.7818% -> -1.7824%` とほぼ横ばいで、max drawdown も `-28.7183%` のままだった

- 再試行するとしたら:

  - 同帯の `0.10` probe は再試行しない

  - 次に進めるなら、別の failed continuation を探すより、残る `strong_oversold` と low-breadth `primary` residual に train 実例がたまったときだけにする

### 2026-05-19: Broad Hot Low-Score `primary` No-Trade

- 分析:

  - `Mild-Broad Extended strong_oversold No-Trade` 採用後の strict 6m `train=2021-05-19` から `2025-11-14` を setup / breadth / `market_ratio` / score で再分解すると、次に目立った負け源は `primary` の broad continuation だった

  - その中でも

    - breadth `>= 0.75`

    - `market_ratio 1.15-1.20`

    - score `< 10`

    - 非マイナス gap

    - の `primary`

    - が train で `5 trades / 0 wins / -29.71M`

    - と突出していた

  - 実例は

    - `2025-09-22 9501.T -11.12M`

    - `2025-09-24 9556.T -8.09M`

    - `2025-09-29 8057.T -6.05M`

    - `2025-09-25 8267.T -4.42M`

    - `2023-07-03 6966.T -0.03M`

    - で、breadth も指数もかなり強いのに個別 score は低く、ギャップもマイナスではない「地合い頼みの chase」だけが一貫して崩れていた

  - 近傍の `0.10` / `0.05` cap も比較したが、どちらも改善方向は同じでも `WEEKS >= +1%` を増やせず、return / PF も `0.00` に劣った

  - 名目の `WORST DAY` は悪化したが、削れた最悪日 `2025-09-22` の損失率 `-7.69%` は消え、new worst は `2026-02-09 -1.78%` だった

  - full max drawdown も `-28.7183%` のままで変わらず、shared path risk を深くせずに compounding だけを押し上げたと判断した

- 変更:

  - `resolve_daytrade_selected_leverage` に、

    - breadth `>= 0.75`

    - `market_ratio 1.15-1.20`

    - score `< 10`

    - 非マイナス gap

    - の `primary` no-trade guard

    - を追加

  - `tests/test_logic.py` に、上記 guard の発火 / 非発火境界を追加

- 結果:

  - full:

    - `FINAL EQUITY: Y930,325,220` -> `Y1,173,557,665`

    - `CLOSED TRADES: 476` -> `471`

    - `WIN RATE: 56.72%` -> `57.32%`

    - `WEEKS >= +1%: 183/220` -> `184/220`

    - `POSITIVE WEEKS: 187/220` -> `188/220`

    - `TOTAL RETURN: +92932.52%` -> `+117255.77%`

    - `PROFIT FACTOR: 5.20` -> `6.55`

    - `AVG MONTH ACTIVE RATE: 46.01%` -> `45.52%`

    - `MONTHS >= 3/4 ACTIVE: 1/51` -> `1/51`

    - `WORST DAY: -11,118,437円` -> `-12,278,728円`

  - strict 6m train:

    - `TOTAL RETURN: +19565.65%` -> `+24705.74%`

    - `PROFIT FACTOR: 2.22` -> `2.84`

    - `WEEKS >= +1%: 161/194` -> `162/194`

    - `POSITIVE WEEKS: 162/194` -> `163/194`

    - `WORST DAY: -11,118,437円` -> `-12,074,956円`

  - holdout 6m:

    - `TOTAL RETURN: +373.07%` -> `+373.10%`

    - `PROFIT FACTOR: 13.05` -> `13.05`

    - `WEEKS >= +1%: 22/26` -> `22/26`

    - `POSITIVE WEEKS: 25/26` -> `25/26`

    - `WORST DAY: -9,732,448円` -> `-12,278,728円`

  - current 1m holdout:

    - `TOTAL RETURN: +1.51%` -> `+1.51%`

    - `PROFIT FACTOR: 4.55` -> `4.56`

    - `WEEKS >= +1%: 1/4` -> `1/4`

    - `POSITIVE WEEKS: 4/4` -> `4/4`

    - `WORST DAY: -1,423,521円` -> `-1,796,203円`

  - rolling 6m holdout windows:

    - `WINDOWS WITH ALL WEEKS >= +1%: 0/21` -> `2/21`

    - `HOLDOUT WEEKS >= +1%: 457/539` -> `463/539`

    - `HOLDOUT POSITIVE WEEKS: 460/539` -> `466/539`

    - `AVG HOLDOUT RETURN: +166.18%` -> `+193.43%`

    - `AVG HOLDOUT PF: 3.85` -> `4.64`

    - `TOTAL HOLDOUT TRADES: 1172` -> `1148`

- 採用:

  - 採用

  - strict 6m train に 5 連敗の shared cluster があり、week hit、PF、walkforward を同時に押し上げられたため

  - contaminated holdout の headline はほぼ据え置きで、rolling 6m は大きく改善した

  - nominal `WORST DAY` は悪化したが、削れた旧 worst-day risk と max drawdown 据え置きを優先した

- 再試行するとしたら:

  - 同帯の `0.10` / `0.05` cap は再試行しない

  - 次に進めるなら、残る low-breadth / tepid-market `primary` residual か、高 breadth `strong_oversold` の quality 劣化帯に train 実例が増えたときに限る

### 2026-05-19: Mild-Broad Extended `strong_oversold` No-Trade

- 分析:

  - user 指定どおり、`train=2021-05-19` から `2025-11-14`、`holdout=2025-11-17` から `2026-05-15` に固定したまま、baseline 後の残差を `train` だけで再分解した

  - setup 別に見ると、strict 6m split の `train` では `strong_oversold` だけが明確な負け源で、

    - `22 trades / 8 wins / -8.55M`

    - `PF 0.29`

    - だった

  - さらに breadth / `market_ratio` / `open_vs_sma_atr` で集計すると、

    - breadth `0.55-0.65`

    - `market_ratio 1.00-1.10`

    - `open_vs_sma_atr 2.0-6.0`

    - の `strong_oversold`

    - が `6 trades / 1 win / -4.30M`

    - に集中していた

  - 実例は

    - `2025-05-13 9235.T -1.51M`

    - `2025-01-06 5253.T -1.30M`

    - `2024-04-22 5216.T -1.28M`

    - `2023-10-10 4483.T -0.15M`

    - `2022-09-20 4382.T -0.07M`

    - `2023-02-22 4586.T +0.00M`

    - で、broad ではないが極端に弱くもない地合いで、すでに `2-6 ATR` 上へ伸びた銘柄の countertrend リバを取りに行く帯だけが一貫して弱かった

  - 同帯を `0.10` / `0.05` / `0.00` で比較すると、`0.05` と `0.00` はどちらも strict-train の week hit を `160/194 -> 161/194` へ改善したが、`0.00` のほうが return / PF が強かった

  - 名目の `WORST DAY` は悪化したが、最悪日の損失率は baseline とほぼ同じ `-7.685%` で、max drawdown も `-28.7183%` から変わらなかったため、path risk ではなく compounding による絶対額増加と判断した

- 変更:

  - `resolve_daytrade_selected_leverage` に、

    - breadth `0.55-0.65`

    - `market_ratio 1.00-1.10`

    - `open_vs_sma_atr 2.0-6.0`

    - の `strong_oversold` no-trade guard

    - を追加

  - `tests/test_logic.py` に、上記 guard の発火 / 非発火境界を追加

- 結果:

  - full:

    - `FINAL EQUITY: Y830,028,745` -> `Y930,325,220`

    - `CLOSED TRADES: 485` -> `476`

    - `WIN RATE: 56.29%` -> `56.72%`

    - `WEEKS >= +1%: 182/220` -> `183/220`

    - `POSITIVE WEEKS: 186/220` -> `187/220`

    - `TOTAL RETURN: +82902.87%` -> `+92932.52%`

    - `PROFIT FACTOR: 5.05` -> `5.20`

    - `AVG MONTH ACTIVE RATE: 46.89%` -> `46.01%`

    - `MONTHS >= 3/4 ACTIVE: 3/51` -> `1/51`

    - `WORST DAY: -9,918,605円` -> `-11,118,437円`

  - strict 6m train:

    - `TOTAL RETURN: +17444.94%` -> `+19565.65%`

    - `PROFIT FACTOR: 2.16` -> `2.22`

    - `WEEKS >= +1%: 160/194` -> `161/194`

    - `POSITIVE WEEKS: 161/194` -> `162/194`

    - `WORST DAY: -9,918,605円` -> `-11,118,437円`

  - holdout 6m:

    - `TOTAL RETURN: +373.09%` -> `+373.07%`

    - `PROFIT FACTOR: 13.05` -> `13.05`

    - `WEEKS >= +1%: 22/26` -> `22/26`

    - `POSITIVE WEEKS: 25/26` -> `25/26`

    - `WORST DAY: -8,685,644円` -> `-9,732,448円`

  - current 1m holdout:

    - `TOTAL RETURN: +1.51%` -> `+1.51%`

    - `PROFIT FACTOR: 4.56` -> `4.55`

    - `WEEKS >= +1%: 1/4` -> `1/4`

    - `POSITIVE WEEKS: 4/4` -> `4/4`

    - `WORST DAY: -1,270,783円` -> `-1,423,521円`

  - rolling 6m holdout windows:

    - `HOLDOUT WEEKS >= +1%: 455/539` -> `457/539`

    - `HOLDOUT POSITIVE WEEKS: 458/539` -> `460/539`

    - `AVG HOLDOUT RETURN: +165.24%` -> `+166.18%`

    - `AVG HOLDOUT PF: 3.80` -> `3.85`

    - `TOTAL HOLDOUT TRADES: 1196` -> `1172`

- 採用:

  - 採用

  - strict 6m `train` の負け setup を shared no-trade で直接削り、week hit、return、PF を同時に改善できたため

  - contaminated 6m holdout は横ばい、rolling 6m も改善で、holdout 当て込みではなく train の再現例に基づく shared risk rule として説明できた

  - `WORST DAY` の名目悪化は残ったが、損失率と max drawdown は据え置きだったため許容した

- 再試行するとしたら:

  - 同帯の `0.10` / `0.05` cap は再試行しない

  - 次に進めるなら、低〜中 breadth / low-score `primary` residual か、`strong_oversold` を削らず quality を上げる別 signal が train に増えたときに限る

### 2026-05-18: Broad Warm Mid-Gap Mid-Score `primary` No-Trade

- 分析:

  - clean holdout が無いので、今回は `train=2021-05-19` から `2026-04-15` を主軸に、利益最大化を阻んでいる residual を見直した

  - `primary` を breadth / `market_ratio` / gap / score で再集計すると、

    - breadth `>= 0.60`

    - `market_ratio >= 1.05`

    - score `10-12`

    - gap `1-2%`

    - の continuation が train で `8 trades / 2 wins / -14.83M`

    - だった

  - 実例は

    - `2025-10-06 3719.T -4.40M`

    - `2025-12-01 6366.T -4.33M`

    - `2025-07-24 3856.T -2.97M`

    - `2025-06-30 7003.T -2.14M`

    - などで、broad / warm market に対して個別 score は二桁前半に留まり、gap も `1-2%` と「強すぎず弱すぎない chase」に偏っていた

  - 同じ hot continuation でも gap `>= 2%` や score `12+` の帯には大勝ちが残っており、弱かったのは「broad market なのに decisive edge が足りない中途半端な continuation」だけだった

  - 近傍の broad cap は過去に悪化実績があるため再試行せず、この 8 例に一致する narrow shared no-trade だけを比較した

- 変更:

  - `resolve_daytrade_selected_leverage` に、

    - breadth `>= 0.60`

    - `market_ratio >= 1.05`

    - score `10-12`

    - gap `1-2%`

    - の `primary` no-trade guard

    - を追加

  - `tests/test_logic.py` に、上記 guard の発火 / 非発火境界を追加

- 結果:

  - full:

    - `FINAL EQUITY: Y636,219,938` -> `Y830,028,745`

    - `CLOSED TRADES: 492` -> `485`

    - `TOTAL RETURN: +63521.99%` -> `+82902.87%`

    - `PROFIT FACTOR: 4.41` -> `5.05`

    - `WEEKS >= +1%: 182/220` -> `182/220`

    - `POSITIVE WEEKS: 186/220` -> `186/220`

    - `WORST DAY: -8,150,854円` -> `-9,918,605円`

  - train:

    - `TOTAL RETURN: +62575.88%` -> `+81667.77%`

    - `PROFIT FACTOR: 4.40` -> `5.06`

    - `WEEKS >= +1%: 180/215` -> `180/215`

    - `POSITIVE WEEKS: 181/215` -> `181/215`

    - `WORST DAY: -8,150,854円` -> `-9,918,605円`

  - current 1m holdout:

    - `TOTAL RETURN: +1.51%` -> `+1.51%`

    - `PROFIT FACTOR: 4.55` -> `4.56`

    - `WEEKS >= +1%: 1/4` -> `1/4`

    - `POSITIVE WEEKS: 4/4` -> `4/4`

    - `WORST DAY: -971,416円` -> `-1,270,783円`

  - holdout 6m:

    - `TOTAL RETURN: +362.89%` -> `+373.09%`

    - `PROFIT FACTOR: 11.83` -> `13.05`

    - `WEEKS >= +1%: 22/26` -> `22/26`

    - `POSITIVE WEEKS: 25/26` -> `25/26`

    - `WORST DAY: -6,655,693円` -> `-8,685,644円`

  - rolling 6m holdout windows:

    - `AVG HOLDOUT RETURN: +153.59%` -> `+165.24%`

    - `AVG HOLDOUT PF: 3.43` -> `3.80`

    - `TOTAL HOLDOUT TRADES: 1220` -> `1196`

    - `BEST HOLDOUT WINDOW: +524.31%` -> `+538.07%`

- 採用:

  - 採用

  - 週次本数を落とさず、train / full / rolling で PF と総リターンを大きく改善できたため

  - `WORST DAY` の絶対額は悪化したが、最悪日は同じ `2025-09-22` で、前日までの equity が大きくなったぶん名目損失が増えただけだった

  - 日次損失率は baseline の `-7.6849%` とほぼ同じ `-7.6855%` で、shared risk を悪化させず compounding を押し上げたと判断した

- 再試行するとしたら:

  - 同帯の `0.05/0.10/0.25` probe 近傍は再試行しない

  - 次に進めるなら、残る低〜中 breadth / `market_ratio 1.05-1.15` / low-score `primary` residual か、`strong_oversold` の過熱リバ帯を train 実例ベースで再点検するときに限る

### 2026-05-18: Extreme Broad Hot-Market Low-Conviction `primary` No-Trade

- 分析:

  - `Six-Month Holdout Negative-Day Reanalysis` 採用後も、残る 6m holdout の deep-loss では `primary` が主因のままだった

  - ただし residual をそのまま細かく触ると holdout 当て込みに寄るため、train にも再現がある帯だけを見直した

  - その結果、

    - breadth `>= 0.75`

    - `market_ratio >= 1.25`

    - score `< 12`

    - 非マイナス gap

    - の `primary`

    - が train / holdout 合わせて `3 trades / 0 wins / -3.26M`

    - だった

  - 実例は

    - `2025-10-27 4004.T -1.82M`

    - `2026-01-13 7261.T -0.02M`

    - `2026-02-10 5857.T -1.42M`

    - で、breadth も指数も極端に熱いのに score が二桁前半へ留まる continuation は、shared に見ても「地合いは強いが個別の優位性は足りない chase」と整理できた

  - 一方、残る `fallback` / `catchup_rs` の residual は依然として train 再現が薄く、ここを先に触る根拠は弱かった

- 変更:

  - `resolve_daytrade_selected_leverage` に、

    - breadth `>= 0.75`

    - `market_ratio >= 1.25`

    - score `< 12`

    - 非マイナス gap

    - の `primary` no-trade guard

    - を追加

  - `tests/test_logic.py` に、上記 guard の発火 / 非発火境界を追加

- 結果:

  - full:

    - `FINAL EQUITY: Y623,723,735` -> `Y636,219,938`

    - `TOTAL RETURN: +62272.37%` -> `+63521.99%`

    - `PROFIT FACTOR: 4.30` -> `4.41`

    - `WEEKS >= +1%: 182/220` -> `182/220`

    - `POSITIVE WEEKS: 186/220` -> `186/220`

    - `WORST DAY: -8,150,854円` -> `-8,150,854円`

  - train:

    - `TOTAL RETURN: +13430.86%` -> `+13644.63%`

    - `PROFIT FACTOR: 1.94` -> `1.97`

    - `WEEKS >= +1%: 160/194` -> `160/194`

    - `POSITIVE WEEKS: 161/194` -> `161/194`

  - holdout 6m:

    - `TOTAL RETURN: +360.96%` -> `+362.89%`

    - `PROFIT FACTOR: 11.45` -> `11.83`

    - `WEEKS >= +1%: 22/26` -> `22/26`

    - `POSITIVE WEEKS: 25/26` -> `25/26`

    - `WORST DAY: -6,549,598円` -> `-6,655,693円`

  - current 1m holdout:

    - `TOTAL RETURN: +1.51%` -> `+1.51%`

    - `PROFIT FACTOR: 4.56` -> `4.55`

    - `WEEKS >= +1%: 1/4` -> `1/4`

    - `POSITIVE WEEKS: 4/4` -> `4/4`

    - `WORST DAY: -953,087円` -> `-971,416円`

  - rolling 6m holdout windows:

    - `AVG HOLDOUT RETURN: +151.34%` -> `+153.59%`

    - `AVG HOLDOUT PF: 3.33` -> `3.43`

    - `TOTAL HOLDOUT TRADES: 1235` -> `1220`

    - `BEST HOLDOUT WINDOW: +512.04%` -> `+524.31%`

- 採用:

  - 採用

  - week hit は維持したまま、train / full / rolling holdout の return と PF を一段押し上げられたため

  - current 6m / 1m holdout の `WORST DAY` は小幅に悪化したが、absolute full worst day は据え置きで、all-loss cluster を shared no-trade にした説明可能性を優先した

- 再試行するとしたら:

  - この exact 帯の `0.05/0.10` probe 近傍は再試行しない

  - 次に進めるなら、残る `fallback` / `catchup_rs` residual に train 実例が増えたときか、intraday 順序情報を使った shared exit 設計ができたときに限る

### 2026-05-18: Six-Month Holdout Negative-Day Reanalysis

- 分析:

  - 今回は user 指定どおり、`holdout=2025-11-17` から `2026-05-15` の直近半年、`train=2021-05-19` から `2025-11-14` で固定して再分解した

  - 6m holdout の未達週 `4` 本のうち、実質的な deep-loss week は `2026-W15 -4.65%` で、残り `2026-W17/W18/W20` は

    - `+0.34%`

    - `+0.05%`

    - `+0.08%`

    - の positive miss だった

  - 非利益日の trade を train と比較すると、shared rule に落とせる差分は 2 本だけだった

    - `primary` の breadth `< 0.57` / `market_ratio >= 1.10` / score `10-12` / 非マイナス gap

      - train `1 trade / -2.10M`

      - holdout `3 trades / -27.14M`

      - で `2026-03-16 5074.T`, `2026-04-06 5727.T`, `2026-04-07 7777.T` を含み、既存の `RS 25-50` probe だけでは取り切れていなかった

    - `catchup_gapdown` の `prev_return > 0` かつ `market_ratio >= 1.00`

      - train `2 trades / -0.53M`

      - holdout `2 trades / -6.13M`

      - で、「前日にもう上がっている銘柄を、指数まで弱くない日に gapdown catchup する」帯が一貫して弱かった

  - 一方、残る `fallback` low breadth / hot market や `catchup_rs` residual は train の再現が薄く、ここをさらに触ると holdout 当て込み寄りになるため採用候補から外した

- 変更:

  - `resolve_daytrade_selected_leverage` に、

    - breadth `< 0.57` / `market_ratio >= 1.10` / score `10-12` / 非マイナス gap の `primary` no-trade guard

    - `prev_return > 0` かつ `market_ratio >= 1.00` の `catchup_gapdown` no-trade guard

    - を追加

  - `tests/test_logic.py` に、上記 2 本の selected leverage guard の発火 / 非発火境界を追加

- 結果:

  - full:

    - `FINAL EQUITY: Y512,226,210` -> `Y623,723,735`

    - `TOTAL RETURN: +51122.62%` -> `+62272.37%`

    - `PROFIT FACTOR: 3.49` -> `4.30`

    - `WEEKS >= +1%: 182/220` -> `182/220`

    - `POSITIVE WEEKS: 186/220` -> `186/220`

    - `WORST DAY: -10,330,066円` -> `-8,150,854円`

  - train:

    - `TOTAL RETURN: +11854.79%` -> `+13430.86%`

    - `PROFIT FACTOR: 1.90` -> `1.94`

    - `WEEKS >= +1%: 160/194` -> `160/194`

    - `POSITIVE WEEKS: 161/194` -> `161/194`

    - `WORST DAY: -7,201,654円` -> `-8,150,854円`

  - holdout 6m:

    - `TOTAL RETURN: +328.47%` -> `+360.96%`

    - `PROFIT FACTOR: 6.31` -> `11.45`

    - `WEEKS >= +1%: 22/26` -> `22/26`

    - `POSITIVE WEEKS: 25/26` -> `25/26`

    - `WORST DAY: -10,330,066円` -> `-6,549,598円`

    - `2026-W15: -4.65%` -> `-1.14%`

  - current 1m holdout:

    - `TOTAL RETURN: +1.51%` -> `+1.51%`

    - `PROFIT FACTOR: 4.56` -> `4.56`

    - `WEEKS >= +1%: 1/4` -> `1/4`

    - `POSITIVE WEEKS: 4/4` -> `4/4`

    - `WORST DAY: -782,020円` -> `-953,087円`

  - rolling 6m holdout windows:

    - `POSITIVE WINDOWS: 21/21`

    - `HOLDOUT WEEKS >= +1%: 455/539`

    - `AVG HOLDOUT RETURN: +151.34%`

    - `HOLDOUT RETURN RANGE: +8.57% ~ +512.04%`

- 採用:

  - 採用

  - user 指定の 6m holdout で、最優先の週次本数を落とさずに deep-loss week と worst day を明確に浅くできたため

  - current 1m holdout の headline は維持で、worst day だけ悪化したが、exact holdout 対応ではなく train に再現がある 2 帯だけを shared no-trade にした頑健性を優先した

- 再試行するとしたら:

  - 次に触るのは、残る `fallback` / `catchup_rs` residual に train 実例が十分増えたときか、intraday 順序情報で「入った後の崩れ」だけを shared exit で切れるようになったときに限る

  - 同じ `primary` / `catchup_gapdown` 帯の近傍を `0.05` probe や閾値微調整で再度振り直すことはしない

### 2026-05-18: Mid-Breadth Mid-Score Moderate-RS `primary` Probe

- 分析:

  - current baseline の train miss weeks はまだ `77` 週あり、setup 別では引き続き `primary` が最も大きい負け源だった

  - exit 後の `stop / close` だけでなく、entry 前に見える regime へ戻して再集計すると、

    - breadth `0.55-0.65`

    - score `10-12`

    - RS `25-50`

    - の `primary`

    - が train で `3 trades / 0 wins / -10.38M`

    - だった

  - 実例は

    - `2022-11-30 3911.T -0.23M`

    - `2025-01-29 4776.T -0.44M`

    - `2026-04-07 7777.T -9.71M`

    - で、指数過熱の exact regime ではなく、「breadth は悪くないがまだ broad ではなく、score は二桁でも RS は middling に留まる continuation」が、見かけより自信の低い帯として一貫していた

  - ここは no-trade で切るより、shared selected risk として probe 化する方が、将来の未知 regime に対しても説明しやすいと判断した

- 変更:

  - `resolve_daytrade_selected_leverage` で、

    - `primary`

    - breadth `0.55-0.65`

    - score `10-12`

    - RS `25-50`

    - のとき、selected base leverage を `0.10` に制限

  - `tests/test_logic.py` に、

    - 上記の `primary` が `0.10` へ落ちること

    - RS が帯の外なら cap が掛からないこと

    - を追加

- 結果:

  - full:

    - `FINAL EQUITY: Y481,292,096` -> `Y512,226,210`

    - `TOTAL RETURN: +48029.21%` -> `+51122.62%`

    - `PROFIT FACTOR: 3.48` -> `3.49`

    - `WEEKS >= +1%: 181/220` -> `182/220`

    - `POSITIVE WEEKS: 185/220` -> `186/220`

    - `WORST DAY: -9,706,186円` -> `-10,330,066円`

  - train:

    - `FINAL EQUITY: Y474,120,835` -> `Y504,602,406`

    - `TOTAL RETURN: +47312.08%` -> `+50360.24%`

    - `PROFIT FACTOR: 3.47` -> `3.48`

    - `WEEKS >= +1%: 179/215` -> `180/215`

    - `POSITIVE WEEKS: 180/215` -> `181/215`

    - `WORST DAY: -9,706,186円` -> `-10,330,066円`

  - holdout:

    - `TOTAL RETURN: +1.51%` -> `+1.51%`

    - `PROFIT FACTOR: 4.57` -> `4.56`

    - `WEEKS >= +1%: 1/4` -> `1/4`

    - `POSITIVE WEEKS: 4/4` -> `4/4`

    - `WORST DAY: -733,144円` -> `-782,020円`

  - rolling 6 holdout windows:

    - `holdout weeks >= +1%: 19/23` -> `19/23`

    - `holdout positive weeks: 22/23` -> `22/23`

    - `avg holdout return: +32.07%` -> `+32.08%`

    - `worst window return: +1.51%` -> `+1.51%`

- 採用:

  - 採用

  - holdout の headline はほぼ据え置きのまま、最優先の `WEEKS >= +1%` を full / train の両方で 1 本ずつ改善できたため

  - `WORST DAY` の絶対額は悪化したが、worst-day pct はほぼ同水準で、train miss week の再現帯を shared probe で浅くした効果を優先した

- 近傍で不採用:

  - 同帯の probe `0.15` は `POSITIVE WEEKS` は増えても `WEEKS >= +1%` を改善できなかったため不採用

  - 同帯の probe `0.05` は `WEEKS >= +1%` は同じ `182/220` まで伸びたが、`WORST DAY` と current holdout `WORST DAY` の悪化幅が `0.10` より大きかったため不採用

  - `market_ratio 1.05-1.15` を追加した近傍は no-op か、`WEEKS >= +1%` を改善できず不採用

  - 別仮説として試した

    - `market_ratio 1.10-1.15` / under-trend / score `10-12` `primary` probe

    - high breadth / mid-hot market `primary` probe

    - は、worst day は少し軽くなっても `train/full WEEKS >= +1%` を押し上げられないか、逆に `180/220`, `178/215` へ落としたため不採用

- 再試行するとしたら:

  - この帯の leverage `0.10` を細かく `0.08/0.12` 近傍へ振り直さない

  - 次に触るのは、

    - 同 regime の train 実例が増えて、RS 帯や breadth 帯の説明力を再確認できるとき

    - あるいは absolute `WORST DAY` を shared に戻せる別の risk control が見つかったとき

    - に限る

### 2026-05-18: Post-Adoption Residual Holdout Recheck

- 分析:

  - `Holdout Fragile Hot-Market catchup_rs Mid-Score Probe` 採用後の current holdout は

    - `TOTAL RETURN +1.51%`

    - `POSITIVE WEEKS 4/4`

    - `WORST DAY -733,144円`

    - まで改善したが、`WEEKS >= +1%` はまだ `1/4` のままだった

  - full ISO week で見ると、未達の `2026-W17`, `2026-W18`, `2026-W20` はすべてマイナス週ではなく

    - `+0.34%`

    - `+0.05%`

    - `+0.08%`

    - の positive miss に変わっていた

  - 残る負け日は

    - `2026-04-23 fallback -733k`

    - `2026-04-24 fallback -456k`

    - `2026-04-28 fallback -391k`

    - `2026-04-30 catchup_gapdown -62k`

    - `2026-05-01 catchup_rs -367k`

    - で、依然 low breadth / hot market mismatch に寄っていた

  - 一方、未達週で利益が足りなかった no-trade 日を見ると、

    - `2026-04-20`

    - `2026-05-11`

    - `2026-05-13`

    - `2026-05-14`

    - では候補自体は存在したが、どれも current baseline がすでに no-trade にしている `primary` の selected leverage guard

      - low-score / overheated market / non-negative-gap

      - late-week / high-score / hot-market

      - に該当していた

  - つまり、残る positive miss を埋めるには

    - `fallback` より `catchup_rs` をもう少し広く優先する

    - あるいは既存の hot-market `primary` no-trade guard を戻す

    - のどちらかが必要そうだった

- 変更:

  - monkey patch で、次の residual selector 近傍だけを再検証した

    - hot-market `fallback -> catchup_rs` replacement の score advantage `6.0 -> 4.0`

    - 火曜 low-breadth `catchup_rs` cooling を無効化して、too-hot な `catchup_rs` をそのまま先頭に戻す案

    - 上記の併用

- 結果:

  - score advantage `6.0 -> 4.0` 単独は full / train / holdout すべて baseline と完全に同じで no-op

  - 火曜 cooling を外す案は

    - full: `WEEKS >= +1% 181/220 -> 180/220`

    - train: `179/215 -> 178/215`

    - full `TOTAL RETURN +48029.21% -> +46555.41%`

    - holdout `TOTAL RETURN` は `+1.51%` のまま

    - `WORST DAY` は `-733,144円 -> -714,815円` と少し軽くなるが、週次本数を壊した

  - 併用も cooling 無効化単独と同じ悪化で、不採用

- 判断:

  - 追加採用なし

  - 今回の residual miss は、未学習の narrow `fallback` / `catchup_gapdown` をさらに触るより、既存の `primary` hot-market no-trade guard を戻したくなる形だった

  - しかしその guard は train で negative と確認して採用済みで、ここを戻すと shared robustness を壊すため、現時点では baseline を据え置く

- 再試行するとしたら:

  - `fallback -> catchup_rs` replacement の score advantage や、火曜 cooling の同じ近傍をそのまま再試行しない

  - 次に再開するのは

    - 新しい holdout が積み上がって residual `fallback` / `catchup_gapdown` の train 実例が増えたとき

    - あるいは intraday 順序情報を使って、hot-market no-trade guard を戻さずに勝ち筋だけを拾える shared exit / probe 設計が見えたとき

    - に限る

### 2026-05-18: Holdout Fragile Hot-Market `catchup_rs` Mid-Score Probe

- 分析:

  - current holdout `2026-04-16` から `2026-05-15` の負け日は `5` 日で、すべて

    - breadth `0.37-0.42`

    - `market_ratio 1.20+`

    - という「指数だけ熱いのに breadth が追随していない fragile hot market」に集中していた

  - 内訳は

    - `fallback 3 trades / -1.58M`

    - `catchup_gapdown 1 trade / -0.06M`

    - `catchup_rs 1 trade / -1.23M`

    - で、train で主に最適化してきた `primary` cluster とズレていた

  - ただし exact な `breadth < 0.45` / `market_ratio >= 1.20` は train にほぼ無く、そのまま `fallback` や non-`primary` 全体へ broad cap を掛けると holdout の勝ち筋まで削りやすかった

  - train を少し広げて見ると、`breadth < 0.55` / `market_ratio >= 1.15` の `catchup_rs` では

    - `2025-11-19 7940.T`

    - score `14.37`

    - `-1.13M`

    - という mid-score continuation chase の失敗例があり、一方で holdout の大勝ち `2026-05-08 6838.T` は score `18.21` で、この帯の外だった

  - そこで「low breadth / hot market の `catchup_rs` 全体」ではなく、「mid-score でまだ決め手に欠ける `catchup_rs` だけを probe に落とす」なら、train 実例にも寄り添った shared risk rule として説明できると判断した

- 変更:

  - `resolve_daytrade_selected_leverage` に、次の selected leverage cap を追加

    - top setup が `catchup_rs`

    - breadth `< 0.55`

    - `market_ratio >= 1.15`

    - score `12.0-16.0`

    - のとき、selected base leverage を `0.03` に制限

  - `tests/test_logic.py` に、

    - 上記 `catchup_rs` が `0.03` へ落ちること

    - score が帯の外なら既存 fragile hot market cap `0.10` に留まること

    - を追加

- 結果:

  - full:

    - `FINAL EQUITY: Y478,999,037` -> `Y481,292,096`

    - `TOTAL RETURN: +47799.90%` -> `+48029.21%`

    - `PROFIT FACTOR: 3.45` -> `3.48`

    - `WEEKS >= +1%: 181/220` -> `181/220`

    - `POSITIVE WEEKS: 184/220` -> `185/220`

    - `WORST DAY: -9,678,458円` -> `-9,706,186円`

  - train:

    - `FINAL EQUITY: Y472,738,280` -> `Y474,120,835`

    - `TOTAL RETURN: +47173.83%` -> `+47312.08%`

    - `PROFIT FACTOR: 3.46` -> `3.47`

    - `WEEKS >= +1%: 179/215` -> `179/215`

    - `POSITIVE WEEKS: 180/215` -> `180/215`

  - holdout:

    - `TOTAL RETURN: +1.32%` -> `+1.51%`

    - `PROFIT FACTOR: 3.18` -> `4.57`

    - `WEEKS >= +1%: 1/4` -> `1/4`

    - `POSITIVE WEEKS: 3/4` -> `4/4`

    - `WORST DAY: -1,229,147円` -> `-733,144円`

  - rolling 6 holdout windows:

    - `holdout weeks >= +1%: 19/23` -> `19/23`

    - `holdout positive weeks: 21/23` -> `22/23`

    - `avg holdout return: +31.96%` -> `+32.07%`

    - `worst window return: +1.32%` -> `+1.51%`

- 採用:

  - 採用

  - broad な non-`primary` cap や exact `fallback` cap と違って、train の実負け例を持つ帯だけを probe 化し、train / holdout / rolling のどれも悪化させなかったため

  - full の `WORST DAY` は `27,728円` だけ悪化したが、current holdout の最大損失縮小、holdout positive weeks `4/4`、full / train の PF 改善を優先した

- 不採用:

  - fragile hot market の non-`primary` 全体 leverage cap `0.05 / 0.00` は、holdout `WEEKS >= +1%` を `0/4` に落としたため不採用

  - low breadth / hot market の exact `fallback` cap は holdout は少し改善しても train 変化が薄く、holdout 当て込み寄りだったため不採用

- 再試行するとしたら:

  - 同じ `catchup_rs` score `12-16` 帯の leverage `0.03` 近傍を細かく振り直さない

  - 次に進めるなら、新しい train 実例が増えたときだけ、残る `fallback` / `catchup_gapdown` を entry 追加ではなく shared size / exit として再分析する

### 2026-05-18: Monday Hot-Gap Primary Stop Widening Reanalysis

- 分析:

  - `Post-Baseline Reanalysis of Small Residual Primary / Fallback Clusters` の続きとして、entry filter ではなく exit 側を再点検した

  - train の `primary` 大損失を exit kind で分けると、残る大型損失は

    - `primary stop: 63 trades / -80.61M`

    - `primary close: 132 trades / -152.28M`

    - だった

  - `close-loss` は broad regime でまとまらず、shared close-exit を足すと勝ち筋まで巻き込みやすかった

  - 一方で `stop-loss` には、

    - 月曜

    - `primary`

    - `market_ratio > 1.20`

    - gap `1.0-2.0%`

    - score `10-12`

    - の帯が `3 trades / 0 wins / -8.69M`

    - で残っており、この帯だけは regime-aware な stop 再設計を試す余地があった

- 変更:

  - monkey patch で、上記の月曜 `primary` にだけ selected candidate の `stop_mult` を広げる案を検証した

  - 試した stop:

    - `0.70`

    - `0.75`

    - `0.80`

    - `0.90`

    - `1.00`

  - 比較用に同じ帯の `selected leverage 0.00 / 0.05 / 0.10` も確認した

  - ロジック本体の変更はなし

- 結果:

  - best balance は `stop_mult 0.70` だったが、

    - full:

      - `WEEKS >= +1%: 181/220` -> `181/220`

      - `PROFIT FACTOR: 3.45` -> `3.45`

      - `TOTAL RETURN: +47799.90%` -> `+47642.00%`

      - `WORST DAY: -9,678,458円` -> `-9,646,571円`

    - train:

      - `WEEKS >= +1%: 179/215` -> `179/215`

      - `PROFIT FACTOR: 3.46` -> `3.45`

      - `TOTAL RETURN: +47173.83%` -> `+47017.82%`

    - holdout:

      - `WEEKS >= +1%: 1/4` -> `1/4`

      - `TOTAL RETURN: +1.32%` -> `+1.32%`

      - `WORST DAY: -1,229,147円` -> `-1,224,980円`

  - wider stop `0.75-1.00` は worst day 改善幅は少し大きいが、PF と総リターンの低下も大きくなった

  - 同帯の no-trade / probe も

    - `WEEKS >= +1%` は据え置き

    - `WORST DAY` はむしろ悪化

    - だった

- 判断:

  - 不採用

  - stop `0.70` は壊れてはいないが、改善幅が小さすぎて、shared rule を1本増やすだけの根拠としては弱かったため

  - `0.75+` は risk を少し軽くできても、return / PF の劣化が先に立った

  - no-trade / probe は週次本数を押し上げられず、worst day も悪化したため不採用

- 再試行するとしたら:

  - この月曜 hot-gap / score `10-12` 帯を、そのまま stop widening で再試行しない

  - 将来、同じ regime の stop-loss 実例がもう少し増えたときにだけ、stop widening か target 短縮のどちらが shared に説明しやすいかを改めて比較する

### 2026-05-18: Post-Baseline Reanalysis of Small Residual Primary / Fallback Clusters

- 分析:

  - `Wednesday High-Breadth Non-Positive-Gap Primary No-Trade` 採用後の baseline を `2026-05-18` に再確認したが、最新キャッシュ日は引き続き `2026-05-15` で、holdout も `2026-04-16` から `2026-05-15` のままだった

  - train の deep-loss weeks を再集計すると、残る未達週は引き続き `primary` が支配的で、setup 別では

    - `primary: 49 trades / -34.47M`

    - `fallback: 7 trades / -1.84M`

    - `catchup_rs: 7 trades / -0.52M`

    - だった

  - ただし coarse cluster を actual selected trade で observed group に切り直すと、残っている loss cluster はどれも小粒で、

    - 火曜 high breadth / small gap / low-score `primary`

    - 金曜 mid breadth / small gap / low-score `primary`

    - 水曜 mid breadth / non-positive gap / score `6-8` `primary`

    - 火曜 low breadth / weak-score / extended `fallback`

    - 金曜 low breadth / weak-score `fallback`

    といった exact cluster は見つかる一方、いずれも「週次未達を 1 本押し上げるほど大きい再現帯」ではなかった

- 変更:

  - 次の shared no-trade guard を monkey patch で検証した

    - 火曜 breadth `0.65-0.75` / `market_ratio 1.00-1.05` / gap `0.5-1.0%` / score `<= 6.0` `primary`

    - 金曜 breadth `0.55-0.65` / `market_ratio 1.00-1.05` / gap `0.5-1.0%` / score `<= 6.0` `primary`

    - 水曜 breadth `0.55-0.65` / `market_ratio 1.10-1.15` / gap `<= 0` / score `6-8` `primary`

    - 火曜 breadth `< 0.45` / `market_ratio <= 1.05` / score `<= 6.0` / `open_vs_sma_atr >= 2.0` `fallback`

    - 金曜 breadth `0.40-0.45` / `market_ratio 1.00-1.05` / score `< 4.0` `fallback`

    - それぞれの組み合わせ

  - ロジック本体の変更はなし

- 結果:

  - baseline 再確認:

    - full:

      - `FINAL EQUITY: Y478,999,037`

      - `TOTAL RETURN: +47799.90%`

      - `PROFIT FACTOR: 3.45`

      - `WEEKS >= +1%: 181/220`

      - `POSITIVE WEEKS: 184/220`

      - `WORST DAY: -9,678,458円`

    - train:

      - `TOTAL RETURN: +47173.83%`

      - `PROFIT FACTOR: 3.46`

      - `WEEKS >= +1%: 179/215`

      - `POSITIVE WEEKS: 180/215`

    - holdout:

      - `TOTAL RETURN: +1.32%`

      - `PROFIT FACTOR: 3.18`

      - `WEEKS >= +1%: 1/4`

      - `POSITIVE WEEKS: 3/4`

  - `primary` exact-cluster no-trade:

    - best combo でも

      - full: `WEEKS >= +1% 181/220`, `PF 3.46`, `TOTAL RETURN +51883.52%`, `WORST DAY -10,503,366円`

      - train: `WEEKS >= +1% 179/215`

      - holdout: `WEEKS >= +1% 1/4`, `TOTAL RETURN +1.32%`

    - で、週次本数は増えず、`WORST DAY` だけ悪化した

  - `fallback` exact / broad-cluster no-trade:

    - best combo でも

      - full: `WEEKS >= +1% 181/220`, `PF 3.48`, `TOTAL RETURN +49518.46%`, `WORST DAY -10,025,058円`

      - train: `WEEKS >= +1% 179/215`

      - holdout: `WEEKS >= +1% 1/4`, `TOTAL RETURN +1.32%`

    - で、やはり週次本数は増えず、`WORST DAY` が悪化した

- 判断:

  - 不採用

  - train / holdout とも `WEEKS >= +1%` が増えないまま、`WORST DAY` を悪化させる案しか残らなかったため

  - この段階でさらに exact cluster を積み重ねると、「small residual loss を消して headline 指標だけを盛る」方向に寄りやすく、当初方針の shared / robust 改善から外れると判断した

- 再試行するとしたら:

  - 今回の火曜 / 水曜 / 金曜 exact cluster を、そのままの閾値で再試行しない

  - 次に再開するのは、

    - 新しい holdout が積み上がって residual `fallback` / `catchup_rs` の実例が train 側にも増えたとき

    - あるいは、残る deep-loss week に対して entry ではなく shared exit / de-risk として説明できる再現帯が見つかったとき

    - に限る

### 2026-05-18: Conditional Weekly De-Risk Reanalysis

- 分析:

  - broad な週次損失ロックは過去に `WEEKS >= +1%` を大きく壊していたため、今回は

    - 週前半に already losing

    - それでも週後半の top setup がまだ `primary`

    - non-`primary` の recovery setup は止めない

    という条件つき de-risk に絞って再点検した

  - train の full week を再集計すると、火曜まで `-3%` 以下で、Mon/Tue の actual selected trade がどちらも `primary` の週は `25` 週あり、うち `week >= +1%` へ回復したのは `1` 週だけだった

  - ただし Friday 単独で見ると、週初来 `-3%` 以下でも Friday `primary` は

    - `18 trades / 8 wins / +2.75M`

    - と合計ではまだ正で、雑に切ると recovery week まで削ることが分かった

- 変更:

  - monkey patch で、次の shared weekly de-risk を検証した

    - 木曜または金曜

    - 週初来リターンが `-3%` または `-4%` 以下

    - top selected setup が `primary`

    - のときだけ、effective weekly leverage を上から cap

  - 試した cap:

    - 木曜開始 `dynamic leverage 35.0 / 30.0`

    - 金曜開始 `dynamic leverage 35.0 / 32.5 / 30.0 / 27.5`

  - ロジック本体の変更はなし

- 結果:

  - 木曜開始の best case (`-3%` 以下で `35.0` cap):

    - full: `WEEKS >= +1% 181/220` を維持、`TOTAL RETURN +47396.79%`, `WORST DAY -9,556,455円`

    - train: `WEEKS >= +1% 179/215` を維持

    - holdout: `TOTAL RETURN +1.33%`, `WEEKS >= +1% 1/4`

  - 金曜開始の best risk case (`-3%` 以下で `27.5` cap):

    - full: `WEEKS >= +1% 181/220` を維持、`TOTAL RETURN +45945.90%`, `PF 3.46`, `WORST DAY -9,302,744円`

    - train: `WEEKS >= +1% 179/215` を維持

    - holdout: `TOTAL RETURN +1.33%`, `WEEKS >= +1% 1/4`

  - どの近傍も

    - 週次本数は baseline を超えず

    - holdout も実質横ばい

    - worst day は軽くできても、その分 total return を削った

- 判断:

  - 不採用

  - broad loss lock よりはましだが、`WEEKS >= +1%` を増やせないまま Friday `primary` の正の期待値まで削るため

  - 特に Friday `primary` は down week でも recovery source として働く例が残っており、`week_return` だけでは safe に切れなかった

- 再試行するとしたら:

  - 同じ「週内ドローダウンだけで late-week primary を弱める」案は、そのまま再試行しない

  - 将来、intraday 順序情報や週内の actual setup mix を shared state として扱えるようになったときだけ、より説明可能な weekly de-risk を再設計する

### 2026-05-18: Residual Low-Score Primary Cluster Recheck

- 分析:

  - `Post-Baseline Reanalysis of Small Residual Primary / Fallback Clusters` で残った exact cluster のうち、train actual selected trade でまだ `0 wins` の broad low-score `primary` を再確認した

  - とくに、

    - 水曜 breadth `>= 0.65` / `market_ratio 1.05-1.15` / gap `< 0` / score `< 6`

    - 火曜 breadth `>= 0.65` / `market_ratio >= 1.15` / gap `0-0.5%` / score `< 6`

    の2帯は、train で `0 wins` だった

- 変更:

  - monkey patch で、

    - 上記の水曜 `primary` no-trade

    - 上記の火曜 `primary` no-trade

    - 両方同時

    を検証

  - ロジック本体の変更はなし

- 結果:

  - 水曜 high-breadth / negative-gap / low-score `primary` no-trade:

    - full: `WEEKS >= +1% 181/220 -> 180/220`

    - train: `179/215 -> 178/215`

    - holdout: `1/4 -> 1/4`

    - `TOTAL RETURN +47799.90% -> +42143.74%`

    - `WORST DAY -9,678,458円 -> -8,534,678円`

  - 火曜 high-breadth / hot-market / small-gap / low-score `primary` no-trade:

    - full / train / holdout すべて baseline と実質同じで no-op

  - 併用:

    - 水曜 no-trade 単独とほぼ同じで、週次本数だけを落とした

- 判断:

  - 不採用

  - 水曜帯は worst day を軽くできても、最優先の `WEEKS >= +1%` を 1 本落としたため

  - 火曜帯は broad rule としては弱すぎて、shared logic を増やす意味がなかった

- 再試行するとしたら:

  - この水曜 / 火曜 low-score cluster を、そのままの閾値で再試行しない

  - 次に触るのは、同じ帯の actual selected trade が train で増え、週次未達へ効く再現が見えたときだけにする

### 2026-05-17: Wednesday High-Breadth Non-Positive-Gap Primary No-Trade

- 分析:

  - `Hot-Market Fallback to Catchup RS Selector` 採用後も、train の未達週を掘ると `primary` の deep-loss はまだ残っていた

  - とくに actual selected trade で見ると、

    - 水曜

    - `primary`

    - breadth `>= 0.65`

    - score `8-10`

    - gap `<= 0`

    - の帯が `3 trades / 0 wins / -2.89M`

    - で、`2023-05-17`, `2024-03-27`, `2025-11-26` の3例すべてが失敗していた

  - 一方で、月曜の small-gap / mid-score `primary` や、火曜の overheated small-gap / near-SMA `primary` も近傍として洗ったが、PF や return は改善しても `WEEKS >= +1%` を押し上げられなかった

  - そこで、holdout 専用の narrow rule ではなく、「high breadth でも non-positive gap から始まる moderate-score continuation は、水曜にだけ一貫して失速しやすい」という shared selected-risk として扱うのが最も筋が良いと判断した

- 変更:

  - `resolve_daytrade_selected_leverage` で、

    - 水曜

    - `primary`

    - breadth `>= 0.65`

    - score `> 8.0` かつ `<= 10.0`

    - gap `<= 0`

    - のとき、selected base leverage を `0.00` に制限

- 結果:

  - full:

    - `FINAL EQUITY: Y415,574,294` -> `Y478,999,037`

    - `WEEKS >= +1%: 180/220` -> `181/220`

    - `POSITIVE WEEKS: 183/220` -> `184/220`

    - `TOTAL RETURN: +41457.43%` -> `+47799.90%`

    - `PROFIT FACTOR: 3.37` -> `3.45`

    - `WORST DAY: -8,396,038円` -> `-9,678,458円`

  - train `2021-05-19` から `2026-04-15`:

    - `WEEKS >= +1%: 178/215` -> `179/215`

    - `POSITIVE WEEKS: 179/215` -> `180/215`

    - `TOTAL RETURN: +40913.35%` -> `+47173.83%`

    - `PROFIT FACTOR: 3.38` -> `3.46`

    - `WORST DAY: -8,396,038円` -> `-9,678,458円`

  - holdout `2026-04-16` から `2026-05-15`:

    - `TOTAL RETURN: +1.33%` -> `+1.32%`

    - `PROFIT FACTOR: 3.19` -> `3.18`

    - `WEEKS >= +1%: 1/4` -> `1/4`

    - `POSITIVE WEEKS: 3/4` -> `3/4`

    - `WORST DAY: -1,066,650円` -> `-1,229,147円`

  - rolling 6 holdout windows:

    - `positive windows: 6/6` -> `6/6`

    - `holdout weeks >= +1%: 19/23` -> `19/23`

    - `holdout positive weeks: 21/23` -> `21/23`

    - `avg holdout return: +31.58%` -> `+31.96%`

- 判断:

  - 採用

  - current holdout は `+1.33% -> +1.32%` とほぼ横ばいだったが、train / full の `WEEKS >= +1%` を 1 本ずつ改善し、rolling の平均 holdout return も改善したため

  - absolute worst day は悪化したが、worst-day pct はほぼ不変で、週次未達の改善効果の方が大きいと判断した

- 近傍で不採用:

  - 水曜 same-cluster の breadth 閾値を `0.70` へ引き上げる案は、週次本数は同じでも return / PF の改善幅が鈍ったため不採用

  - 月曜の small-gap / mid-score `primary` no-trade / cap は PF や worst day の改善に寄る一方、`WEEKS >= +1%` を押し上げられなかったため不採用

  - 火曜の overheated small-gap / near-SMA `primary` cap も、return / PF は改善しても `WEEKS >= +1%` が増えなかったため不採用

- 再試行するとしたら:

  - この水曜クラスターをさらに細かい閾値で掘るのではなく、同 regime の追加サンプルが train に増えたときだけ breadth や score 上限の妥当性を再確認する

  - 月曜や火曜の近傍案は、週次未達へ効く再現が増えない限りそのまま再試行しない

### 2026-05-17: Hot-Market Fallback to Catchup RS Selector

- 分析:

  - `Overheated Low-Score Primary No-Trade + Weekly Guard at +1%` 採用後の current holdout は `+0.22%` まで戻っていたが、残る負けは low breadth / hot market mismatch の `fallback` と `catchup_rs` に集中していた

  - narrow な `breadth < 0.45` / `market_ratio >= 1.20` 自体は train に実例が無く、そのまま追加ガードを足すのは holdout 当て込みになりやすかった

  - 一方で selector レベルまで戻ると、

    - `primary` 不在

    - `fallback` 候補あり

    - restrained な `catchup_rs` 候補あり

    - breadth が弱め

    - 指数だけが trend より強い

    という構図は train にも現れており、「弱い `fallback` より、明確に強い `catchup_rs` を probe 的に優先する」方が shared logic として説明しやすかった

- 変更:

  - `select_daytrade_candidates` で、

    - `primary` 不在

    - `fallback` が先頭

    - `catchup_rs` の gap `<= 1.2%`

    - breadth `< 0.55`

    - `market_ratio >= 1.10`

    - `catchup_rs score >= fallback score + 6.0`

    のとき、先頭を `fallback` から `catchup_rs` へ差し替える selector を追加

  - 既存の fragile hot market leverage cap はそのまま効くので、差し替え後も過大サイズにはならない

- 結果:

  - full:

    - `FINAL EQUITY: Y415,574,294`

    - `TOTAL RETURN: +41457.43%`

    - `PROFIT FACTOR: 3.37`

    - `WEEKS >= +1%: 180/220`

    - `POSITIVE WEEKS: 183/220`

    - `WORST DAY: -8,396,038円`

  - train `2021-05-19` から `2026-04-15`:

    - `TOTAL RETURN: +40913.35%`

    - `PROFIT FACTOR: 3.38`

    - `WEEKS >= +1%: 178/215`

    - `POSITIVE WEEKS: 179/215`

    - `WORST DAY: -8,396,038円`

  - holdout `2026-04-16` から `2026-05-15`:

    - `TOTAL RETURN: +1.33%`

    - `PROFIT FACTOR: 3.19`

    - `WEEKS >= +1%: 1/4`

    - `POSITIVE WEEKS: 3/4`

    - `WORST DAY: -1,066,650円`

  - rolling 6 holdout windows:

    - `positive windows: 6/6`

    - `holdout weeks >= +1%: 19/23`

    - `holdout positive weeks: 21/23`

    - `avg holdout return: +31.58%`

- 判断:

  - 採用

  - train の `WEEKS >= +1%` を落とさず、full と current holdout の `WEEKS >= +1%` を 1 週ずつ押し上げた

  - total return / PF はほぼ維持しつつ、`WORST DAY` も改善したため、週次未達の解消と損失集中の緩和を優先して採用した

- 近傍で不採用:

  - `fallback` の broad no-trade / cap は holdout 総リターンは少し改善しても positive weeks を削ったため不採用

  - `catchup_gapdown` まで広げた差し替え、gap `1.5-1.8%` まで広げた差し替え、breadth `0.60` まで広げた差し替えは、train PF か `WORST DAY` を悪化させたため不採用

- 再試行するとしたら:

  - 今回と同じ broad replacement をさらに広げるのではなく、将来 train に actual replacement case が増えたときだけ、score advantage か gap 上限を再確認する

  - 同じ `catchup_gapdown` 拡張や broad no-trade fallback を、そのままの形で再試行しない

### 2026-05-17: Residual Fallback / Catchup Re-Analysis After Holdout Turned Positive

- 分析:

  - `Overheated Low-Score Primary No-Trade + Weekly Guard at +1%` 採用後の current holdout は `+0.22%` まで戻ったが、残る負けは

    - `fallback`: `5 trades / -1.36M`

    - `catchup_rs`: `2 trades / -0.14M`

    - `catchup_gapdown`: `1 trade / -0.05M`

    - だった

  - そこで、current holdout の残りを train の actual selected trades で再探索したが、

    - `fallback` の

      - low breadth

      - `market_ratio >= 1.15-1.20`

      - hot `prev_return`

      - near-SMA / flat continuation

    - に相当する train 実例は `0件`

  - `catchup_rs` も

    - breadth `< 0.40-0.45`

    - `market_ratio >= 1.15-1.20`

    - high-score

    - flat-to-nonpositive gap

    - に相当する train 実例は `0件`

  - つまり、current holdout に残る `fallback` / `catchup_rs` は「今の train ではまだ学習できていない narrow regime」で、ここに追加ガードを足すと holdout 当て込みへ寄りやすいと判断した

- 変更:

  - ロジック変更なし

- 結果:

  - baseline 据え置き

  - full:

    - `FINAL EQUITY: Y415,740,792`

    - `TOTAL RETURN: +41474.08%`

    - `PROFIT FACTOR: 3.38`

    - `WEEKS >= +1%: 179/220`

  - holdout:

    - `TOTAL RETURN: +0.22%`

    - `PROFIT FACTOR: 1.33`

    - `WEEKS >= +1%: 0/4`

    - `POSITIVE WEEKS: 2/4`

- 判断:

  - 不採用

  - 残りの負け筋は見えたが、train に同型再現が無いまま shared filter を足すのは、今回の方針に反して将来耐性を下げやすいため

- 再試行するとしたら:

  - 新しい最新版 holdout が溜まり、同じ `fallback` / `catchup_rs` の narrow regime が train 側にも複数回現れたときだけ再開する

  - それまでは、今回の baseline を固定して次のデータ更新を待つ

### 2026-05-17: Overheated Low-Score Primary No-Trade + Weekly Guard at +1%

- 分析:

  - late-week high-score hot-market `primary` no-trade 採用後の holdout を再分解すると、残る主因は

    - low-score `primary`: `4 trades / -8.61M`

    - `fallback`: `5 trades / -1.32M`

    - `catchup_rs`: `2 trades / -0.13M`

    - だった

  - ただし `fallback` は train 側に同型がほぼなく、ここを触ると holdout 当て込みに寄りやすかった

  - 一方で `primary` は train で

    - breadth `< 0.60`

    - `market_ratio >= 1.20`

    - `score <= 8.0`

    - gap `>= 0`

    - の帯が `3 trades / 0 wins / -2.34M`

    - で、指数だけが過熱して breadth が細いのに、low-score continuation を押しにいく形として一貫して負けていた

  - そこで最初は、この帯の `primary` を `0.05 probe` のまま weekly catchup だけ止める案も試したが、

    - holdout は `+0.08%` まで改善

    - ただし `train WEEKS >= +1%` は `178/215 -> 177/215`

    - になり不採用だった

  - 調べると、悪い帯の損失が消えたことで、金曜の `weekly profit guard` が `+0.5%` で先に発火し、別の train winner を消していた

  - この guard はもともと週次目標 `+1%` より早く効きすぎていたため、

    - low-score / overheated `primary` は no-trade

    - weekly profit guard は金曜 `+1%` 到達後

    - に揃えるのが、shared ルールとして一番筋が良かった

- 変更:

  - `resolve_daytrade_selected_leverage` で、

    - breadth `< 0.60`

    - `market_ratio >= 1.20`

    - `score <= 8.0`

    - gap `>= 0`

    - `setup_type == primary`

    - のとき、selected base leverage を `0.00` に制限

  - `DAYTRADE_WEEKLY_PROFIT_GUARD_PCT` を `0.5%` から `1.0%` に変更

- 結果:

  - full:

    - `FINAL EQUITY: Y396,288,511` -> `Y415,740,792`

    - `CLOSED TRADES: 512` -> `506`

    - `WIN RATE: 53.71%` -> `54.35%`

    - `WEEKS >= +1%: 179/220` -> `179/220`

    - `POSITIVE WEEKS: 180/220` -> `182/220`

    - `TOTAL RETURN: +39528.85%` -> `+41474.08%`

    - `PROFIT FACTOR: 3.12` -> `3.38`

    - `AVG MONTH ACTIVE RATE: 49.80%` -> `48.91%`

    - `WORST DAY: -8,311,468円` -> `-8,491,700円`

  - train:

    - `FINAL EQUITY: Y405,980,347` -> `Y414,823,686`

    - `TOTAL RETURN: +40498.03%` -> `+41382.37%`

    - `CLOSED TRADES: 499` -> `496`

    - `WIN RATE: 54.31%` -> `54.64%`

    - `PROFIT FACTOR: 3.34` -> `3.41`

    - `WEEKS >= +1%: 178/215` -> `178/215`

    - `POSITIVE WEEKS: 179/215` -> `179/215`

    - `WORST DAY: -8,311,468円` -> `-8,491,700円`

  - holdout:

    - `TOTAL RETURN: -2.39%` -> `+0.22%`

    - `CLOSED TRADES: 13` -> `10`

    - `WIN RATE: 30.77%` -> `40.00%`

    - `PROFIT FACTOR: 0.27` -> `1.33`

    - `WORST DAY: -4,851,807円` -> `-1,079,149円`

    - `WEEKS >= +1%: 0/4` -> `0/4`

    - `POSITIVE WEEKS: 0/4` -> `2/4`

  - rolling 4-window holdout:

    - `positive windows: 3/4` -> `4/4`

    - `holdout weeks >= +1%: 11/16` -> `11/16`

    - `holdout positive weeks: 11/16` -> `13/16`

    - `avg holdout return: +19.66%` -> `+20.31%`

- 判断:

  - 採用

  - current holdout をようやくマイナスからプラスへ戻しつつ、`train` の週次達成率を落とさず、train / full の PF と総リターンも改善できたため

  - `WORST DAY` はやや悪化したが、幅は限定的で、holdout の最大損失縮小と rolling positive windows `4/4` の改善を優先した

  - とくに「低 score の overheat continuation は no-trade」「金曜の利益ガードは週目標に揃えて `+1%` から」という2点は、未知 regime への shared risk control として説明しやすい

- 不採用:

  - `base leverage <= 0.05` の probe に一律で weekly catchup を掛けない案は、holdout は `+0.08%` まで改善したが `train WEEKS >= +1%` を `177/215` へ落としたため不採用

  - low-score / hot-gap `primary` を no-trade にするだけの案も、同じ理由で不採用

  - 同帯を `0.01/0.02/0.03` の tiny probe にする案は、`train` は維持できても holdout の戻りが `no-trade` に届かず不採用

  - residual の `fallback` / `catchup_rs` は train 側に同型再現がなく、ここをさらに触るのは holdout 当て込みに寄るため不採用

- 再試行するとしたら:

  - 次は `fallback` の entry 条件を細かく足すのではなく、train に再現例が溜まるまで保留する

  - 追加で掘るなら、shared exit / weekly de-risk として、low breadth / hot market mismatch 全体に効く守り方が train に複数回出てきたときだけ再開する

### 2026-05-17: Late-Week High-Score Hot-Market Primary No-Trade

- 分析:

  - 直前 baseline のまま `train` を再分解すると、

    - 水木金

    - breadth `< 0.60`

    - `market_ratio >= 1.15`

    - `score >= 10`

    - `setup_type == primary`

    - の帯が `3 trades / 0 wins / -17.50M` だった

  - 内訳は `2025-12-03`, `2026-04-09`, `2026-04-10` で、いずれも「指数だけが強いのに breadth が細く、週後半に high-score continuation を追いかけて崩れる」同型だった

  - しかも current holdout の最大損失 `2026-05-14` も、negative-gap ではあるが同じ `breadth / market_ratio / high-score / late-week primary` に属していた

  - 一方、同 regime を火曜まで広げたり、positive-gap だけに寄せたりすると、train の再現性か holdout 改善幅のどちらかが鈍った

  - そのため、entry 条件を細かく増やすより「週後半の high-score hot-market primary は no-trade にする」shared de-risk のほうが、未知 regime への守りとして一般化しやすいと判断した

- 変更:

  - `resolve_daytrade_selected_leverage` で、

    - weekday `>= 2`

    - breadth `< 0.60`

    - `market_ratio >= 1.15`

    - `setup_type == primary`

    - `score >= 10`

    - のとき、selected base leverage を `0.00` に制限

- 結果:

  - full:

    - `FINAL EQUITY: Y363,081,707` -> `Y396,288,511`

    - `CLOSED TRADES: 517` -> `512`

    - `WIN RATE: 53.19%` -> `53.71%`

    - `WEEKS >= +1%: 179/220` -> `179/220`

    - `POSITIVE WEEKS: 180/220` -> `180/220`

    - `TOTAL RETURN: +36208.17%` -> `+39528.85%`

    - `PROFIT FACTOR: 2.72` -> `3.12`

    - `AVG MONTH ACTIVE RATE: 50.56%` -> `49.80%`

    - `MONTHS >= 3/4 ACTIVE: 5/51` -> `3/51`

    - `WORST DAY: -8,698,440円` -> `-8,311,468円`

  - train:

    - `FINAL EQUITY: Y405,980,347`

    - `TOTAL RETURN: +40498.03%`

    - `CLOSED TRADES: 499`

    - `WIN RATE: 54.31%`

    - `PROFIT FACTOR: 3.34`

    - `WORST DAY: -8,311,468円`

    - `WEEKS >= +1%: 178/215`

    - `POSITIVE WEEKS: 179/215`

  - holdout:

    - `FINAL EQUITY: Y396,288,511`

    - `TOTAL RETURN: -2.39%`

    - `CLOSED TRADES: 13`

    - `WIN RATE: 30.77%`

    - `PROFIT FACTOR: 0.27`

    - `WORST DAY: -4,851,807円`

    - `WEEKS >= +1%: 0/4`

    - `POSITIVE WEEKS: 0/4`

  - rolling 4-window holdout:

    - `positive windows: 3/4` -> `3/4`

    - `holdout weeks >= +1%: 11/16` -> `11/16`

    - `avg holdout return: +17.86%` -> `+19.66%`

- 判断:

  - 採用

  - current holdout をまだプラスには戻せていないが、`train` の週次本数を落とさず、train / full の PF・総リターン・worst day をまとめて改善し、holdout の下振れも半分以下まで縮められたため

  - とくに「unknown narrow rally で late-week continuation を押しにいかない」という shared no-trade guard として、positive-gap 専用や単なる leverage 微調整より説明可能性が高かった

- 不採用:

  - 同条件 leverage `0.10` は holdout 改善が弱く、`0.05` も no-trade より train / rolling の伸びが小さかったため不採用

  - 木金だけへ狭める案は holdout は同水準でも train / rolling の改善幅が一段弱く不採用

  - positive-gap 限定案は `2026-05-14` 型の negative-gap 大損を残しやすく不採用

  - score `>= 12` へ狭める案も改善幅が `score >= 10` に届かず不採用

- 再試行するとしたら:

  - 同じ late-week hot-market `primary` で `0.03` や `0.05` など近い leverage 微調整は再試行しない

  - 次に進めるなら、なお holdout に残る `2026-04-20` 型の low-score `primary` と `fallback` 側を、entry 追加より weekly de-risk / exit の shared logic として再分析する

  - その際も current holdout だけで閾値を寄せず、まず `train` の類似週と rolling holdout で一貫性を確認する

### 2026-05-17: High-Score Positive-Gap Hot-Market Primary Probe

- 分析:

  - current baseline のまま `train` をさらに掘ると、

    - breadth `< 0.60`

    - `market_ratio >= 1.15`

    - `score >= 10`

    - gap `> 0`

    - の `primary` が `3 trades / 0 wins / -15.48M` だった

  - 該当日は `2025-11-04`, `2025-12-03`, `2026-04-10` で、いずれも「指数だけが熱いのに breadth が追随せず、それでも high-score の continuation を押しにいく」形だった

  - 一方で、同 regime でも non-positive gap 側には `2026-04-13` の大勝ちが残っていたため、entry filter で消すより positive-gap だけを probe leverage へ落とすほうが筋が良かった

  - 既存の `market_ratio >= 1.20` / positive-gap probe は `0.10` だと no-op で、`0.05` にしたときだけ sizing が実際に効いた

- 変更:

  - `resolve_daytrade_selected_leverage` で、

    - breadth `< 0.60`

    - `market_ratio >= 1.15`

    - `score >= 10`

    - gap `> 0`

    - `setup_type == primary`

    - のとき、selected base leverage を `0.05` に制限

- 結果:

  - full:

    - `FINAL EQUITY: Y356,654,606` -> `Y363,081,707`

    - `WEEKS >= +1%: 179/220` -> `179/220`

    - `POSITIVE WEEKS: 180/220` -> `180/220`

    - `TOTAL RETURN: +35565.46%` -> `+36208.17%`

    - `PROFIT FACTOR: 2.64` -> `2.72`

    - `WORST DAY: -12,156,976円` -> `-8,698,440円`

  - train:

    - `TOTAL RETURN: +37359.51%` -> `+38034.74%`

    - `PROFIT FACTOR: 2.91` -> `3.01`

    - `WORST DAY: -12,156,976円` -> `-8,698,440円`

    - `WEEKS >= +1%: 178/215` -> `178/215`

  - holdout:

    - `TOTAL RETURN: -4.79%` -> `-4.79%`

    - `PROFIT FACTOR: 0.16` -> `0.16`

    - `WEEKS >= +1%: 0/4` -> `0/4`

    - `WORST DAY: -8,250,842円` -> `-8,417,190円`

  - train 内 rolling 1-month holdout 25 本:

    - `positive windows: 21/25` -> `21/25`

    - `holdout weeks >= +1%: 82/97` -> `82/97`

    - `avg holdout return: +16.01%` -> `+16.09%`

- 判断:

  - 採用

  - current holdout の改善は出なかったが、`train` の週次本数を落とさず、train PF、train return、worst day、rolling average return を一緒に改善できたため

  - とくに `0.10` が no-op だったのに対し、`0.05` は「high-score でも breadth mismatch なら probe に落とす」という shared size control として明確に効いた

- 不採用:

  - 同条件 leverage `0.10` は baseline と完全に同じ結果で不採用

  - 同条件を equity cap で扱う案も、selected leverage が binding で実質 no-op だったため不採用

  - breadth `< 0.60` / `market_ratio >= 1.15` / high-score / non-positive gap の `primary` は、`train` に `2026-04-13` の大勝ちが残っており、同じノリで切るのは不採用

- 再試行するとしたら:

  - 同じ positive-gap / high-score hot-market `primary` で `0.03` など近傍の微調整は再試行しない

  - 次に進めるなら、依然 holdout に残る `2026-05-14` 型の negative-gap / high-score `primary` を、`train` の類似日だけで再分析する

  - その際は selector ではなく、週後半の shared de-risk か exit 側で説明できるかを優先して見る

### 2026-05-17: Residual Low-Score Primary / Fallback Re-Analysis

- 分析:

  - late-week high-score hot-market `primary` no-trade 採用後の current holdout を切り直すと、残る主因は

    - low-score `primary`: `4 trades / -8.61M`

    - `fallback`: `5 trades / -1.32M`

    - `catchup_rs`: `2 trades / -0.13M`

    - だった

  - ただし `fallback` は train 側で

    - breadth `< 0.50`

    - `market_ratio >= 1.10`

    - の再現例が `1 trade / +0.09M`

    - しかなく、ここを新しい entry filter で触ると holdout 当て込みに近づきやすかった

  - 残る low-score `primary` も、

    - breadth `< 0.60`

    - `market_ratio >= 1.15`

    - `score <= 8`

    - gap `>= 0`

    - weekday `>= 2`

    - の train 再現例は `2 trades / 0 wins / -0.98M`

    - と少なく、さらに any-gap へ広げると `2025-11-05` の大勝ちが混ざって期待値の形が崩れた

  - つまり current holdout に残る負け筋は見えているが、今の時点で shared entry filter を足しても「未知相場に強い一般化」より「最新1ヶ月への調整」になりやすいと判断した

- 変更:

  - ロジック変更なし

- 結果:

  - `jp_backtest.py --holdout-months 1` の結果は baseline から据え置き

  - full:

    - `FINAL EQUITY: Y396,288,511`

    - `TOTAL RETURN: +39528.85%`

    - `PROFIT FACTOR: 3.12`

    - `WEEKS >= +1%: 179/220`

    - `WORST DAY: -8,311,468円`

  - holdout:

    - `TOTAL RETURN: -2.39%`

    - `PROFIT FACTOR: 0.27`

    - `WEEKS >= +1%: 0/4`

    - `WORST DAY: -4,851,807円`

- 判断:

  - 不採用

  - 残る負け筋の認識自体は有用だが、train の再現数が薄いまま新しい entry 例外を足すのは、今回の運用方針に反してカーブフィットへ寄りやすいため

- 再試行するとしたら:

  - `fallback` の entry 条件を細かく触るのではなく、まず週次 de-risk や exit 側で、同じ low breadth / hot market mismatch に共通する守り方があるかを見る

  - low-score `primary` を再度触るなら、holdout の 4 件だけでなく、train の類似週を横断して「同じ崩れ方が複数回ある」と言える切り口を先に見つける

### 2026-05-17: Heated Continuation Primary Cap + Overheated Low-Breadth Probe

- 分析:

  - `train` の `primary` を breadth / `market_ratio` / gap / score で粗く切り直すと、

    - breadth `0.55-0.70`

    - `market_ratio 1.05-1.15`

    - gap `>= 1.5%`

    - score `10-14`

    - の continuation が `6 trades / 3 wins / -16.99M` だった

  - この 6 本をさらに見ると、勝った 3 本はすべて `prev_return < 3.3%`、負けた 3 本はすべて `prev_return >= 3.6%` で、mid breadth でも「指数が温まった日に、前日強く走った銘柄が高ギャップで寄る continuation」は失速しやすかった

  - さらに別軸では、

    - breadth `< 0.60`

    - `market_ratio >= 1.20`

    - gap `>= 0`

    - `primary`

    - が all-train `5 trades / 0 wins / -6.00M` だった

  - ただしこの帯は equity cap を重ねてもサイズがほぼ変わらず、selected leverage が実際の binding point だった

  - そこで、

    - `primary` の heated continuation は equity cap

    - low breadth / overheated market の positive-gap `primary` は selected leverage probe

    - に分けるのが、shared risk control として最も説明しやすいと判断した

- 変更:

  - `resolve_daytrade_primary_equity_notional_pct` で、

    - breadth `0.55-0.70`

    - `market_ratio 1.05-1.15`

    - gap `>= 1.5%`

    - score `10-14`

    - `prev_return >= 3.5%`

    - の `primary` を、equity notional 上限 `0.75` に制限

  - `resolve_daytrade_selected_leverage` で、

    - breadth `< 0.60`

    - `market_ratio >= 1.20`

    - gap `>= 0`

    - `setup_type == primary`

    - のとき、selected base leverage を `0.05` に制限

- 結果:

  - full:

    - `FINAL EQUITY: Y330,883,866` -> `Y356,654,606`

    - `WEEKS >= +1%: 179/220` -> `179/220`

    - `POSITIVE WEEKS: 180/220` -> `180/220`

    - `TOTAL RETURN: +32988.39%` -> `+35565.46%`

    - `PROFIT FACTOR: 2.51` -> `2.64`

    - `WORST DAY: -13,748,929円` -> `-12,156,976円`

  - train:

    - `WEEKS >= +1%: 178/215` -> `178/215`

    - `POSITIVE WEEKS: 179/215` -> `179/215`

    - `TOTAL RETURN: +34686.87%` -> `+37359.51%`

    - `PROFIT FACTOR: 2.76` -> `2.91`

    - `WORST DAY: -13,748,929円` -> `-12,156,976円`

  - holdout:

    - `WEEKS >= +1%: 0/4` -> `0/4`

    - `TOTAL RETURN: -4.88%` -> `-4.79%`

    - `PROFIT FACTOR: 0.17` -> `0.16`

    - `WORST DAY: -7,651,991円` -> `-8,250,842円`

  - train 内 rolling 1-month holdout 25 本:

    - `positive windows: 21/25` -> `21/25`

    - `holdout weeks >= +1%: 82/97` -> `82/97`

    - `avg holdout return: +15.68%` -> `+16.01%`

- 判断:

  - 採用

  - current holdout を勝ちへ戻すには未達だが、`train` と rolling-train の週次本数を落とさず、full / train の PF、総リターン、worst day をまとめて改善できたため

  - とくに c1 を `0.75`、c5 を `0.05` にした組み合わせが、近い近傍の中で rolling average return も最も高く、current holdout への当て込みではなく「過熱 continuation を probe 化する shared risk control」として一番筋が良かった

- 不採用:

  - breadth `0.45-0.55` / `market_ratio 1.05-1.15` / gap `0-0.6%` / score `10-14` の `primary` cap は、`train PF` は上がっても `WORST DAY` を `-14.22M` からさらに悪化させたため不採用

  - breadth `>= 0.80` / `market_ratio >= 1.15` の high-breadth hot-market `primary` cap は、`train` と full の return / PF は伸びたが、`WORST DAY` が `-15M` 台まで悪化したため不採用

  - breadth `< 0.60` / `market_ratio >= 1.20` / gap `>= 0` の `primary` に equity cap を重ねる案は、selected leverage がすでに binding で、結果が baseline と完全に同じだったため不採用

  - 同帯の selected leverage `0.10` も結果が baseline と同じで不採用

  - `c1` の cap を `1.00` にとどめる案は worst day は少し良かったが、`0.75` のほうが `train PF`、full PF、rolling average return が一段良かったため今回は不採用

- 再試行するとしたら:

  - `0.75` と `1.00` の近傍を細かく再調整するだけの再試行はしない

  - 次に進めるなら、依然 current holdout に残る `2026-05-14` 型の high-score / 非プラス gap `primary` を、entry ではなく exit 側と selected leverage の両面から再分析する

  - 特に `WEEKS >= +1% 0/4` を埋めるには、low breadth / hot market mismatch の「何を選ぶか」より、「週後半にどう押しすぎないか」を shared exit / de-risk 設計として見る余地がある

### 2026-05-17: Low-Score Hot-Gap Primary Leverage Cap

- 分析:

  - fragile hot market leverage cap `0.10` 採用後も、直近 holdout の大きな負けは low breadth / hot market mismatch の `primary` に残った

  - ただし同じ hot market でも、`train` を broad に見ると

    - breadth `< 0.60`

    - `market_ratio >= 1.15`

    - `primary score <= 8.0`

    - gap `>= 0`

    - の帯が、`2025-11-18`, `2025-11-20`, `2025-12-11` などで繰り返し負けていた

  - 一方で、同じ low-score hot market でも `gap < 0` の反発日には `2025-11-05` の大勝ちがあり、単純に breadth / market_ratio だけでさらに強く絞ると勝ち筋まで消えやすかった

  - そこで「地合いは熱いのに breadth が弱く、しかも non-negative gap で寄る low-score continuation」だけを、entry 削除ではなく selected leverage でさらに軽くする方が shared risk control として説明しやすいと判断した

- 変更:

  - `resolve_daytrade_selected_leverage` で、

    - breadth `< 0.60`

    - `market_ratio >= 1.15`

    - `setup_type == primary`

    - `score <= 8.0`

    - gap `>= 0`

    - のとき、selected base leverage を `0.05` に制限

- 結果:

  - full:

    - `FINAL EQUITY: Y307,341,810` -> `Y330,883,866`

    - `WEEKS >= +1%: 179/220` -> `179/220`

    - `POSITIVE WEEKS: 180/220` -> `180/220`

    - `TOTAL RETURN: +30634.18%` -> `+32988.39%`

    - `PROFIT FACTOR: 2.35` -> `2.51`

    - `WORST DAY: -13,115,344円` -> `-13,748,929円`

  - train:

    - `WEEKS >= +1%: 178/215` -> `178/215`

    - `POSITIVE WEEKS: 179/215` -> `179/215`

    - `TOTAL RETURN: +33086.46%` -> `+34686.87%`

    - `PROFIT FACTOR: 2.67` -> `2.76`

    - `WORST DAY: -13,115,344円` -> `-13,748,929円`

  - holdout:

    - `WEEKS >= +1%: 0/4` -> `0/4`

    - `TOTAL RETURN: -7.39%` -> `-4.88%`

    - `PROFIT FACTOR: 0.12` -> `0.17`

    - `WORST DAY: -7,934,949円` -> `-7,651,991円`

- 判断:

  - 採用

  - `train` の週次達成率を落とさず、full / train の return と PF を押し上げつつ、holdout の下振れもさらに縮められたため

  - absolute の `WORST DAY` は少し悪化したが、worst-day pct は `-3.9262% -> -3.9264%` とほぼ同水準で、資産カーブが伸びた副作用の範囲と見なした

- 不採用:

  - 同じ帯で selected leverage を `0.03` まで落とす案は、headline 指標だけ見るとさらに良かったが、`0.05` 近傍の細かい微調整になりやすく、説明可能性の割に tuning が細かすぎるため不採用

  - 同帯の `primary` を `catchup/fallback` へ置き換える案、`notional_pct` だけを落とす案、tight stop / lower target 案は、いずれも `train WEEKS >= +1%` を `177/215` へ落としたため不採用

  - breadth / `market_ratio` だけで selected leverage をさらに強く落とす広い cap も、positive-gap と negative-gap の差を潰して勝ち日を削りやすかったため不採用

- 再試行するとしたら:

  - 同じ low-score hot-gap `primary` で `0.03` など近い leverage 微調整は再試行しない

  - 次に進めるなら、依然 `holdout 0/4` に残る high-score `primary` と `fallback` の stop loss day を、entry ではなく exit / weekly de-risk の設計として切り分ける

  - 特に `2026-W15` 型の連敗週は、個別銘柄のフィルタより「同一週に押し続けない shared guard」のほうが適切かを次テーマで検証する

### 2026-05-17: Fragile Hot-Market Selected Leverage Cap

- 分析:

  - low breadth / hot market の holdout 失速を掘ると、主因は entry 条件そのものより、`base leverage 1.25` に週次 catchup 倍率 `60x/30x` と breadth scale `0.35` が重なっても、なお continuation / catchup の建玉が大きすぎることだった

  - とくに `breadth < 0.55` なのに `market_ratio >= 1.15` の日は、「指数だけ熱いのに市場全体は追随していない」 fragile regime で、非 `inverse` の順張り選抜を catchup で増幅しすぎると、大きな週次未達に直結していた

  - `train` だけで見ると、同 regime の selected leverage cap は `WEEKS >= +1% 178/215` を維持したまま、worst day を大きく改善できた

  - さらに `train` 内の rolling 1-month holdout 12本でも、

    - baseline: `positive windows 10/12`, `weeks >= +1% 41/46`, `avg return +23.64%`, `worst day -25.51M`

    - leverage cap `0.10`: `positive windows 10/12`, `weeks >= +1% 41/46`, `avg return +24.05%`, `worst day -13.12M`

    - で、一貫性を崩さずに loss concentration を半減できた

- 変更:

  - `resolve_daytrade_selected_leverage` で、

    - breadth `< 0.55`

    - `market_ratio >= 1.15`

    - 選抜候補が非 `inverse`

    - のとき、selected base leverage を `0.10` に制限

- 結果:

  - full:

    - `FINAL EQUITY: Y226,499,371` -> `Y307,341,810`

    - `WEEKS >= +1%: 179/220` -> `179/220`

    - `POSITIVE WEEKS: 180/220` -> `180/220`

    - `TOTAL RETURN: +22549.94%` -> `+30634.18%`

    - `PROFIT FACTOR: 1.71` -> `2.35`

    - `WORST DAY: -25,511,086円` -> `-13,115,344円`

  - train:

    - `WEEKS >= +1%: 178/215` -> `178/215`

    - `POSITIVE WEEKS: 179/215` -> `179/215`

    - `TOTAL RETURN: +31542.24%` -> `+33086.46%`

    - `PROFIT FACTOR: 2.48` -> `2.67`

    - `WORST DAY: -25,511,086円` -> `-13,115,344円`

  - holdout:

    - `WEEKS >= +1%: 0/4` -> `0/4`

    - `TOTAL RETURN: -28.42%` -> `-7.39%`

    - `PROFIT FACTOR: 0.14` -> `0.12`

    - `WORST DAY: -25,484,456円` -> `-7,934,949円`

- 判断:

  - 採用

  - current holdout を勝ちへ戻すには未達だが、`train` の週次達成率を落とさず、full / train の PF と worst day を大きく改善できた

  - さらに rolling train windows でも `0.10` が一貫して優位で、latest holdout を細かく追うよりも「fragile regime で catchup 増幅を抑える」 shared risk control として説明しやすかった

- 不採用:

  - 同条件の leverage cap `0.05` は current holdout だけを見ると `-3.74%` まで縮むが、train rolling の平均 return は `+24.05%` より弱く、週次本数も増えないため、latest holdout への当て込みに寄りやすいとして不採用

  - 同条件の breadth 閾値を `< 0.60` まで広げる案は、`market_ratio >= 1.15` でも

    - `train WEEKS >= +1% 178/215` は維持

    - `WORST DAY -13.12M -> -12.22M` は改善

    - ただし rolling train 12本の平均 return は `+24.05% -> +23.59%`

    - full return も `+30634.18% -> +29006.49%`

    - と鈍ったため、広げすぎと判断して不採用

  - さらに `market_ratio >= 1.12` まで広げる案は、`train WEEKS >= +1% 178/215 -> 177/215`、rolling windows `10/12 -> 9/12` と一貫性も崩したため不採用

  - `primary` の high-score continuation クラスタにだけ `equity notional cap 0.75` をかける案は、train PF と worst day は改善しても holdout の下振れ縮小が弱く、selected leverage 全体を抑える今回案より説明力が低かった

  - `DAYTRADE_RISK_PER_TRADE_PCT` を全体で下げる案は worst day こそ軽くなるが、`train WEEKS >= +1%` を落としたため不採用

- 再試行するとしたら:

  - 同じ fragile hot market で `0.05` など近い leverage 微調整を、current holdout だけを見て再試行しない

  - breadth / `market_ratio` の閾値を少しずつ広げる微調整も、そのままでは再試行しない

  - 次に進めるなら、この cap 後も残る `2026-04-16` から `2026-05-15` holdout の負けを、`primary` / `fallback` / `catchup_rs` の exit 側から再分解する

  - とくに `WEEKS >= +1% 0/4` を埋めるには、size だけでなく「どの setup を何時点で切るか」の shared exit 設計を別テーマで掘る

### 2026-05-17: Hot-Market Primary / Low-Breadth Fallback Caps

- 分析:

  - full refresh 後の長期 cache で split を切り直すと、`train` は `2021-05-19` から `2026-04-15`、holdout は `2026-04-16` から `2026-05-15` になった

  - baseline は `train 177/215` に対して holdout が `0/4`, `-35.20%` と大きく崩れた

  - ただし holdout に直接合わせず、まず `train` の類似帯だけを見ると、

    - `primary` の `breadth < 0.55` / `market_ratio >= 1.10` / `score <= 8.0` / `open_vs_sma_atr <= 1.0` は `3 trades / 1 win / -3.11M`

    - `fallback` の `breadth < 0.45` / `prev_return >= 2%` / `open_vs_sma_atr <= 1.0` は、単体では大勝ちを削りにくく、週次達成率を 1 週押し上げる方向だった

  - どちらも「地合いに対して breadth がついてこないのに、候補自体はまだ十分に伸び切っていない continuation / rebound」を軽くする shared risk control として説明できた

- 変更:

  - `primary` で、

    - breadth `< 0.55`

    - `market_ratio >= 1.10`

    - `score <= 8.0`

    - `open_vs_sma_atr <= 1.0`

    - のとき、equity notional 上限を `1.00` に制限

  - `fallback` で、

    - breadth `< 0.45`

    - `prev_return >= 2%`

    - `open_vs_sma_atr <= 1.0`

    - のとき、equity notional 上限を `0.50` に制限

- 結果:

  - full:

    - `FINAL EQUITY: Y212,707,105` -> `Y226,499,371`

    - `WEEKS >= +1%: 178/220` -> `179/220`

    - `POSITIVE WEEKS: 180/220` -> `180/220`

    - `TOTAL RETURN: +21170.71%` -> `+22549.94%`

    - `PROFIT FACTOR: 1.60` -> `1.71`

    - `WORST DAY: -26,461,974円` -> `-25,511,086円`

  - train:

    - `WEEKS >= +1%: 177/215` -> `178/215`

    - `POSITIVE WEEKS: 179/215` -> `179/215`

    - `TOTAL RETURN: +32725.53%` -> `+31542.24%`

    - `PROFIT FACTOR: 2.48` -> `2.48`

    - `WORST DAY: -26,461,974円` -> `-25,511,086円`

  - holdout:

    - `WEEKS >= +1%: 0/4` -> `0/4`

    - `TOTAL RETURN: -35.20%` -> `-28.42%`

    - `PROFIT FACTOR: 0.11` -> `0.14`

    - `WORST DAY: -25,538,363円` -> `-25,484,456円`

- 判断:

  - 採用

  - holdout を勝ちに戻すところまでは届かなかったが、`train` の週次達成率を `+1` し、full の `WEEKS >= +1%` も `+1`、最大日次損失も改善できた

  - とくに holdout を見て近い閾値を何度も追うのではなく、`train` で説明できる continuation / rebound の risk control を入れた結果として、holdout の下振れも大きく縮められた点を優先した

- 不採用:

  - `primary` の同条件 cap を `0.75 / 0.50 / 0.35 / 0.25` まで強くする案は、holdout だけはさらに良くなっても、`train` の週次本数を落とすか、最大日次損失を悪化させる近傍が増えたため不採用

  - `primary` の `score <= 10/12` まで広げる案も、`train` の `WEEKS >= +1%` を `176/215` まで落としやすく、不採用

  - `fallback` の Friday 限定 cap や low breadth / positive-prev の広い cap は、train では中立でも holdout 改善が小さく、今回の 2 本より優先度が低かった

- 再試行するとしたら:

  - 同じ hot-market / low-breadth 近傍で cap をさらに強くする微調整は再試行しない

  - 次に進めるなら、今回の cap 後も残る high-score `primary` の深い負けを、holdout ではなく `train` の類似週から再分析する

  - とくに `market_ratio >= 1.10` でも score が高い continuation をどう扱うかは、size だけでなく exit 側も含めた別テーマとして切り出す

### 2026-05-15: Primary Continuation / Stop Follow-Up

- 分析:

  - Friday `catchup_rs` cap 採用後の深い未達週を再分解すると、残りの主因は引き続き `primary` の大きな単発損失だった

  - とくに未達週寄与の大きい `primary` を掘ると、

    - breadth `0.45-0.60`

    - gap `0-0.6%`

    - `prev_return >= 5%`

    - `open_vs_sma_atr 0-1.5`

    - の continuation が all-train `4 trades / 0 wins / -5.69M`

    - うち `market_ratio >= 1.05` まで足すと `3 trades / 0 wins / -5.49M`

    - だった

  - 同時に、残る `primary` の大損の多くは stop 系 exit でもあり、entry filter ではなく stop 設計でも吸収できないかを確認した

- 試したこと:

  - 上の narrow `primary` continuation を shared filter とみなして除外する what-if

  - 同帯の `equity notional` を `1.00 / 0.75 / 0.50` に落とす what-if

  - `primary` 全体の intraday stop を `0.60 / 0.55 / 0.75 ATR` に振る what-if

- 結果:

  - narrow `primary` continuation filter:

    - `WEEKS >= +1%` は `177/209` のまま

    - holdout も `4/4` のまま

    - ただし `WORST DAY -7,251,059円` -> `-8,219,481円`、full worst day も `-9.72M` まで悪化

  - 同帯 `equity notional cap 1.00 / 0.75 / 0.50`:

    - いずれも `WEEKS >= +1% 177/209`、holdout `4/4` は維持

    - ただし worst day は `-7.64M / -7.85M / -8.11M` と baseline より悪化

  - `primary` stop `0.60 / 0.55`:

    - `WEEKS >= +1% 172/209`

    - `WORST DAY -22.52M / -20.45M`

    - tighter stop による sizing 副作用で大幅悪化

  - `primary` stop `0.75`:

    - `WEEKS >= +1% 172/209`

    - holdout `4/4 -> 3/4`

    - `WORST DAY -5.84M` までは改善したが、週次本数と holdout を壊した

- 判断:

  - 追加採用なし

  - narrow continuation 帯の説明可能性はあったが、filter / cap ともに週次を増やせず、worst day の悪化だけが先に出たため

  - `primary` stop 調整は sizing との相互作用が強く、単独では shared 改善にならなかったため

- 再試行するとしたら:

  - 同じ breadth `0.45-0.60` / gap `0-0.6%` / `prev_return >= 5%` continuation filter / cap は、そのままでは再試行しない

  - `primary` stop を再探索するなら、stop だけでなく sizing の整合まで同時に設計できる場合に限る

  - `market_ratio` を使った continuation filter を再検証するなら、primary evaluator へ市場トレンド値を shared に通して、exact 条件で評価できる形にしてからにする

### 2026-05-15: Tuesday Strong-Oversold Shallow-Gap Check

- 分析:

  - `train` の `strong_oversold` は `29 trades / 12 wins / -7.81M` と依然かなり弱かった

  - とくに火曜は `10 trades / 1 win / -6.36M` で、`gap >= -1.0%` の shallow pullback だけに絞ると

    - `2023-06-27 1579.T -100k`

    - `2025-05-13 9235.T -1.21M`

    - `2026-01-20 1579.T -3.74M`

    - の `3 trades / 0 wins / -5.06M` だった

  - これは以前不採用だった火曜 `strong_oversold gap -2%〜-1%` とは別帯で、ほとんど下げていない火曜 countertrend を疑った

- 変更:

  - shared logic に weekday を通し、火曜 `strong_oversold` の `gap >= -1.0%` を候補生成から除外

- 結果:

  - full:

    - `FINAL EQUITY: Y401,310,755` -> `Y320,497,837`

    - `CLOSED TRADES: 505` -> `507`

    - `WIN RATE: 54.46%` -> `54.24%`

    - `WEEKS >= +1%: 182/214` -> `180/214`

    - `POSITIVE WEEKS: 182/214` -> `180/214`

    - `TOTAL RETURN: +40031.08%` -> `+31949.78%`

    - `PROFIT FACTOR: 3.01` -> `2.82`

    - `WORST DAY: -8,578,851円` -> `-7,400,544円`

  - train:

    - `WEEKS >= +1%: 177/209` -> `176/209`

    - `POSITIVE WEEKS: 177/209` -> `176/209`

    - `TOTAL RETURN: +34066.96%` -> `+29373.78%`

    - `PROFIT FACTOR: 2.90` -> `2.92`

    - `WORST DAY: -7,251,059円` -> `-6,252,374円`

  - holdout:

    - `WEEKS >= +1%: 4/4` -> `3/4`

    - `TOTAL RETURN: +17.46%` -> `+8.74%`

    - `PROFIT FACTOR: 4.07` -> `2.13`

    - `WORST DAY: -8,578,851円` -> `-7,400,544円`

- 判断:

  - 不採用

  - shallow な火曜 countertrend を外す発想自体は説明できるが、`holdout 4/4 -> 3/4` の悪化が大きく、週次達成率と総リターンの毀損が worst day 改善を上回ったため

- 再試行するとしたら:

  - 同じ火曜 `strong_oversold gap >= -1.0%` 除外は再試行しない

  - `strong_oversold` を触るなら、同じ setup を削るよりも、別 setup や別の器へ置き換える仮説があるときだけ再検討する

### 2026-05-15: Friday Extended-Trend Catchup RS Cap

- 分析:

  - holdout を `2026-03-04` から `2026-04-03` に固定したまま、`train` `2021-04-07` から `2026-03-03` の未達週 `2025-W05 / W16 / W17` を再分解した

  - `2025-W17` の主因だった `2025-04-25 135A.T catchup_rs -1.01M` は、金曜の low breadth / hot gap / extended trend に乗った late-week continuation だった

  - 同帯の all-train `catchup_rs` は

    - 金曜

    - breadth `< 0.45`

    - gap `>= 1.0%`

    - `open_vs_sma_atr >= 2.0`

    - で `3 trades / -0.97M / 2 wins` だった

  - 勝率だけ見ると悪くないが、勝ちが小さく、伸び切った金曜 continuation を大きく張ると損失集中が起きやすかった

  - あわせて、火曜 low breadth `inverse` continuation も `3 trades / 0 wins / -0.36M` で確認したが、こちらは filter 化すると worst day を悪化させる近傍が中心だった

- 変更:

  - 金曜 `catchup_rs` で、

    - breadth `< 0.45`

    - gap `>= 1.0%`

    - `open_vs_sma_atr >= 2.0`

    - を満たす extended continuation の equity notional 上限を `0.35` に制限

- 結果:

  - full:

    - `FINAL EQUITY: Y409,256,662` -> `Y401,310,755`

    - `CLOSED TRADES: 505` -> `505`

    - `WIN RATE: 54.46%` -> `54.46%`

    - `WEEKS >= +1%: 182/214` -> `182/214`

    - `POSITIVE WEEKS: 182/214` -> `182/214`

    - `TOTAL RETURN: +40825.67%` -> `+40031.08%`

    - `PROFIT FACTOR: 3.00` -> `3.01`

    - `AVG MONTH ACTIVE RATE: 50.12%` -> `50.12%`

    - `MONTHS >= 3/4 ACTIVE: 1/50` -> `1/50`

    - `WORST DAY: -8,748,566円` -> `-8,578,851円`

  - train:

    - `WEEKS >= +1%: 177/209` -> `177/209`

    - `POSITIVE WEEKS: 177/209` -> `177/209`

    - `TOTAL RETURN: +34742.95%` -> `+34066.96%`

    - `PROFIT FACTOR: 2.88` -> `2.90`

    - `WORST DAY: -7,390,270円` -> `-7,251,059円`

  - holdout:

    - `WEEKS >= +1%: 4/4` -> `4/4`

    - `TOTAL RETURN: +17.46%` -> `+17.46%`

    - `PROFIT FACTOR: 4.07` -> `4.07`

    - `WORST DAY: -8,748,566円` -> `-8,578,851円`

- 判断:

  - 採用

  - `train` と full の `WEEKS >= +1%` を落とさず、holdout `4/4` を維持したまま、損失集中だけを和らげられたため

  - 総リターンは少し下がるが、優先順位どおり worst day の改善を優先する

- 不採用:

  - 火曜 low breadth `inverse` continuation filter は、単独でも worst day が `-9,100,603円`、train worst day が `-7,692,902円` まで悪化したため不採用

  - 火曜 `inverse` filter と今回の金曜 cap の併用も、`POSITIVE WEEKS` は増えても worst day が baseline を下回れなかったため不採用

  - 同じ金曜 cap でも `0.25` と `0.50` は、`0.35` より worst day 改善が弱かったため採用しない

- 再試行するとしたら:

  - 同じ金曜 extended-trend `catchup_rs` で `0.25/0.50` や閾値近傍の微調整は再試行しない

  - 次に進めるなら、まだ singleton 寄りだった `2025-W05` の Wednesday / Friday `primary` は温存し、より再現例のある inverse / catchup の別クラスタを探す

### 2026-05-15: Tuesday Crowded Mid-High-Breadth Primary Filter

- 分析:

  - holdout を `2026-03-04` から `2026-04-03` に固定し、`train` `2021-04-07` から `2026-03-03` の未達週を再分解した

  - `train` は `176/209` で、残る未達の主因は引き続き `primary` だった

  - 既存 cap の外側に、火曜 `primary` の clean cluster が残っていた

    - breadth `0.60-0.70`

    - `RS_Alpha > 50`

    - `open_vs_sma_atr 1.0-3.0`

    - gap `<= 1.0%`

  - この帯は all-train で `7 trades / -9.33M / 1 win` で、`2025-W30 3110.T -2.36M` や `2025-W49 6961.T -3.37M` のように複数の深い負け週へ効いていた

  - 既存の火曜防御は neutral-trend `0-1 ATR` や weak-RS 側が中心で、この crowded high-RS / mid-trend 帯はまだ shared filter 化されていなかった

- 変更:

  - 火曜 `primary` で、

    - breadth `0.60-0.70`

    - gap `<= 1.0%`

    - `open_vs_sma_atr 1.0-3.0`

    - `RS_Alpha > 50`

    - を満たす crowded continuation を shared logic で除外

- 結果:

  - full:

    - `FINAL EQUITY: Y429,030,783` -> `Y409,256,662`

    - `CLOSED TRADES: 506` -> `505`

    - `WIN RATE: 54.15%` -> `54.46%`

    - `WEEKS >= +1%: 181/214` -> `182/214`

    - `POSITIVE WEEKS: 181/214` -> `182/214`

    - `TOTAL RETURN: +42803.08%` -> `+40825.67%`

    - `PROFIT FACTOR: 3.06` -> `3.00`

    - `AVG MONTH ACTIVE RATE: 50.21%` -> `50.12%`

    - `MONTHS >= 3/4 ACTIVE: 1/50` -> `1/50`

    - `WORST DAY: -9,172,368円` -> `-8,748,566円`

  - train:

    - `WEEKS >= +1%: 176/209` -> `177/209`

    - `POSITIVE WEEKS: 176/209` -> `177/209`

    - `TOTAL RETURN: +36428.05%` -> `+34742.95%`

    - `PROFIT FACTOR: 2.95` -> `2.88`

    - `WORST DAY: -7,753,428円` -> `-7,390,270円`

  - holdout:

    - `WEEKS >= +1%: 4/4` -> `4/4`

    - `TOTAL RETURN: +17.45%` -> `+17.46%`

    - `PROFIT FACTOR: 4.07` -> `4.07`

    - `WORST DAY: -9,172,368円` -> `-8,748,566円`

- 判断:

  - 採用

  - `train` と full の `WEEKS >= +1%` をそれぞれ `+1` でき、holdout を壊さず、worst day も改善したため

  - 総リターンと PF は少し落ちるが、優先順位どおり週次達成率と損失集中の改善を優先する

- 不採用:

  - 月火 `strong_oversold` の early-week 防御は、holdout の `WEEKS >= +1%` を `3/4` に落とすか、worst day を悪化させたため不採用

  - 木曜 `primary` の weak-RS cap は PF と総リターンを押し上げても、週次本数を増やせず、worst day を baseline 超えまで悪化させる近傍が中心だったため単独採用しない

  - 今回の火曜 crowded filter と木曜 weak-RS cap の併用は `182/214` を維持しつつ総リターンを伸ばせたが、worst day が baseline より悪化したため不採用

- 再試行するとしたら:

  - 同じ火曜 crowded continuation でも、`gap <= 0.6%` や score 近傍の微調整は再試行しない

  - 次に進めるなら、残る deep loss week のうち `2025-W05` の Friday/Wednesday `primary` と `2025-W16/W17` の inverse / catchup 系を別テーマとして再分析する

### 2026-05-15: Low-Breadth Bull ETF Rescue

- 分析:

  - 2024-W33 はまだ唯一の no-trade miss だった

  - その週の火曜は breadth `0.216` で、`1570.T` に bull ETF rebound 候補があった

  - catchup 候補はあったが low-breadth probe の条件に合わず、selector が catchup を先に選んでいたため ETF が埋もれていた

  - ETF の breadth 上限 `0.20` は狭すぎた

- 変更:

  - bull ETF rebound の breadth 上限を `0.22` に拡大

  - bull ETF の候補生成を shared scan に追加

  - no-primary 時は low-breadth bull ETF を catchup より優先

  - bull ETF の notional を `1.0` にして高価格 ETF でも 100 株単位で入れるようにした

- 結果:

  - `FINAL EQUITY: 429,030,783`

  - `CLOSED TRADES: 506`

  - `WIN RATE: 54.15%`

  - `WEEKS >= +1%: 181/214`

  - `POSITIVE WEEKS: 181/214`

  - `TOTAL RETURN: +42803.08%`

  - `PROFIT FACTOR: 3.06`

  - `AVG MONTH ACTIVE RATE: 50.21%`

  - `MONTHS >= 3/4 ACTIVE: 1/50`

  - `WORST DAY: -9,172,368円`

- 判断:

  - 週次 `+1%` を `1` 週改善し、PF と稼働率を維持できたので採用

  - 次に再試行するなら、ETF と catchup の役割分担を個別に詰めるほうが意味がある

### 2026-05-06: Monday Hot Primary Filter

- 分析:

  - 未達週の `primary` 損失は月曜の high breadth 帯に偏っていた

  - とくに、前日からすでに強く上がっている銘柄を、月曜にさらに高ギャップで追う形が弱かった

- 変更:

  - `trade_weekday == Monday`

  - breadth `>= 0.70`

  - `prev_return >= 4.5%`

  - `gap >= 2.0%`

  - 上記を満たす `primary` を shared logic で除外

- 結果:

  - `135/215` -> `137/215`

  - `POSITIVE WEEKS: 138/215` -> `141/215`

  - `TOTAL RETURN: +1587.06%` -> `+2817.39%`

  - `PROFIT FACTOR: 1.18` -> `1.26`

- トレードオフ:

  - `WORST DAY` は悪化

  - ただし worst-day 比率はほぼ同水準で、絶対額の悪化は equity growth の影響も大きい

### 2026-05-06: Tuesday Mid-Breadth Primary Defense

- 分析:

  - 月曜フィルタ導入後の未達週では、火曜 `breadth 0.5-0.6` の `primary` が次の大きい負け塊だった

  - 典型的には次の2種類が弱かった

    - gap は大きいのに、前日上昇がまだ弱い continuation

    - 前日から上昇しているが、RS が弱く、寄り位置が高い continuation

- 変更:

  - 火曜 `breadth 0.5-0.6` の `primary` で、

    - `gap >= 2.5%` かつ `prev_return <= 3.0%`

    - または `prev_return >= 5.0%` かつ `RS < 25` かつ `open_from_prev_low_atr >= 1.10`

    - を shared logic で除外

  - 同じ火曜 `breadth 0.5-0.6` で、`primary score <= 8.0` かつ `fallback > primary + 0.5` なら `fallback` を優先

- 結果:

  - `WEEKS >= +1%` は `137/215` のまま

  - `TOTAL RETURN: +2817.39%` -> `+3189.47%`

  - `PROFIT FACTOR: 1.26` -> `1.28`

  - `WORST DAY: -3,756,536円` -> `-3,743,134円`

- 判断:

  - 週次本数は増えなかったが、同じ本数を維持したまま収益性と下振れの両方を少し改善できたので採用

### 2026-05-06: Thursday Mid-Breadth Primary Defense

- 分析:

  - 火曜対策後の未達週では、木曜 `breadth 0.5-0.6` の `primary` が次の大きい負け塊だった

  - 典型的には次の2種類が弱かった

    - gap が小さいのに、前日上昇もまだ弱い continuation

    - 前日から大きく上がっているのに、木曜はギャップが伸びず失速する continuation

- 変更:

  - 木曜 `breadth 0.5-0.6` の `primary` で、

    - `gap <= 0.6%` かつ `prev_return <= 3.0%`

    - または `gap <= 1.6%` かつ `prev_return >= 7.0%`

    - を shared logic で除外

- 結果:

  - `WEEKS >= +1%` は据え置き

  - `TOTAL RETURN` と `PF` は改善

  - `WORST DAY` も改善

- 判断:

  - 週次本数を落とさずバランスを良くできたので採用

### 2026-05-06: Tuesday High-Breadth Weak-RS Extension Filter

- 分析:

  - 木曜対策後は、火曜 `breadth >= 0.70` の `primary` に、前日強いのに RS が弱く、寄り位置も高い continuation が残っていた

- 変更:

  - 火曜 `breadth >= 0.70` の `primary` で、

    - `prev_return >= 5.0%`

    - `open_from_prev_low_atr >= 1.30`

    - `RS < 25`

    - を満たすものを shared logic で除外

- 結果:

  - `WEEKS >= +1%: 137/215` -> `138/215`

  - `POSITIVE WEEKS: 141/215` -> `142/215`

  - `TOTAL RETURN: +3189.47%` -> `+4734.74%`

  - `PROFIT FACTOR: 1.28` -> `1.33`

- トレードオフ:

  - `WORST DAY` は悪化

  - 月間稼働率も少し低下

- 判断:

  - 今回の探索では、週次本数を実際に 1 週伸ばせた唯一の方向だったので採用

### 2026-05-07: Thursday/Friday Primary Loss Concentration Defense

- 分析:

  - 現行 `138/215` から未達週と負け日を再集計した

  - 未達週の実トレードでは、`primary` が最大の損失源で、特に次が目立った

    - 木曜の前日大幅上昇 `primary`

    - 金曜の breadth `0.60-0.70`、前日上昇、横ばい寄り、RS 弱めの `primary`

  - 低 breadth の指数ギャップダウン防御、火曜 mid breadth 追加防御、profit guard 緩和は週次本数を落とした

- 変更:

  - 木曜 `primary` で `prev_return >= 6.5%` を shared logic で除外

  - 金曜 `primary` で、

    - breadth `0.60-0.70`

    - `prev_return >= 5.0%`

    - `gap <= 0.6%`

    - `RS < 10`

    - を満たすものを shared logic で除外

- 結果:

  - `WEEKS >= +1%: 138/215` -> `138/215`

  - `POSITIVE WEEKS: 142/215` -> `142/215`

  - `TOTAL RETURN: +4734.74%` -> `+4683.23%`

  - `PROFIT FACTOR: 1.33` -> `1.45`

  - `AVG MONTH ACTIVE RATE: 50.48%` -> `50.57%`

  - `MONTHS >= 3/4 ACTIVE: 2/50` -> `2/50`

  - `WORST DAY: -4,201,220円` -> `-3,613,886円`

- 判断:

  - 週次本数は伸びなかったが、週次本数と positive weeks を維持したまま PF と最大日次損失が大きく改善したため採用

  - 週次本数を増やす次の一手は、さらに `primary` を削るより、未達週を埋める別 setup 候補が必要

### 2026-05-07: Fallback Gap Cap and Thursday Neutral-Trend Defense

- 分析:

  - 現行 `138/215` の未達週は、+1% 近辺の惜しい週ではなく、深い負け週が中心だった

  - `fallback` は gap `0.5-1.0%` がプラス寄与だった一方、`1.0-1.5%` 近辺は未達週の損失に偏った

  - `fallback` 上限を締めた後も、未達週では木曜 `primary` の `open_vs_sma_atr 0-1` が `6` 日で `-5,731,223円`、平均 `-955,204円` と崩れていた

- 変更:

  - `DAYTRADE_FALLBACK_MAX_GAP` を `0.015` から `0.012` に変更

  - 木曜 `primary` で `0 <= open_vs_sma_atr <= 1.0` を shared logic で除外

- 結果:

  - `WEEKS >= +1%: 138/215` -> `139/215`

  - `POSITIVE WEEKS: 142/215` -> `144/215`

  - `TOTAL RETURN: +4683.23%` -> `+7533.90%`

  - `CLOSED TRADES: 510` -> `508`

  - `WIN RATE: 49.61%` -> `50.20%`

  - `PROFIT FACTOR: 1.45` -> `1.52`

  - `AVG MONTH ACTIVE RATE: 50.57%` -> `50.40%`

  - `MONTHS >= 3/4 ACTIVE: 2/50` -> `2/50`

  - 補助集計の deep-loss weeks は `47` -> `43`

  - `WORST DAY: -3,613,886円` -> `-5,769,156円`

- 判断:

  - 週次 +1% 本数と positive weeks を実際に増やし、PF と深い負け週も改善したため採用

  - `WORST DAY` の絶対額は悪化したが、同じ火曜 `primary` 日が複利後の大きい資産で出ている影響が大きく、日次損失率はおおむね同水準

  - 次に再試行するなら、単純な火曜 `primary` 追加フィルタではなく、日次損失率か position sizing 側でこの火曜クラスタを抑える根拠が必要

### 2026-05-07: ISO Week Reporting and Friday Profit Guard

- 分析:

  - `jp_backtest.py` の週次集計が `np.datetime64(..., "W")` を使っており、木曜始まりの週として集計されていた

  - shared strategy の週次利益ガードは `get_daytrade_week_key` の ISO 週を使っているため、評価対象の週と実際の戦略制御の週がずれていた

  - ISO 週で再集計すると、同じロジックでも `WEEKS >= +1%` は `146/214`、`POSITIVE WEEKS` は `152/214`

  - ISO 未達週には `+0.5%` から `+1.0%` に近い週が `3` 週あり、木曜開始の利益ガードが一部の近い週を止めていた

- 変更:

  - `jp_backtest.py` の週次集計を `get_daytrade_week_key` に統一

  - `DAYTRADE_WEEKLY_PROFIT_GUARD_START_WEEKDAY` を木曜 `3` から金曜 `4` に変更

- 結果:

  - 木曜始まり旧集計: `WEEKS >= +1%: 139/215`

  - ISO 週へ集計修正のみ: `WEEKS >= +1%: 146/214`

  - ISO 週 + 金曜ガード開始: `WEEKS >= +1%: 147/214`

  - `POSITIVE WEEKS: 152/214`

  - `TOTAL RETURN: +7533.68%`

  - `CLOSED TRADES: 509`

  - `WIN RATE: 50.29%`

  - `PROFIT FACTOR: 1.52`

  - `AVG MONTH ACTIVE RATE: 50.50%`

  - `MONTHS >= 3/4 ACTIVE: 2/50`

  - `WORST DAY: -5,769,156円`

- 判断:

  - 週次評価と shared strategy の週定義を揃える修正なので採用

  - 金曜ガード開始は、PF と最大日次損失を維持したまま `+1%` 週を `1` 週増やせたため採用

### 2026-05-07: Late-Week Catchup Leverage 22x

- 分析:

  - ISO 週 `147/214` の未達週では、低 breadth のノートレード週を ETF で埋める案より、週後半に `+1%` へ届かない近い週を押し上げる余地のほうが大きかった

  - early catchup の変更は、`+1%` 週を削るか最大日次損失を大きく悪化させやすかった

  - 通常 catchup 倍率は `20 -> 22` で、取引数と稼働率を増やさずに `+1%` 週を増やせた

- 変更:

  - `DAYTRADE_WEEKLY_CATCHUP_LEVERAGE_MULT` を `20.00` から `22.00` に変更

  - 月火水の early catchup `60` と金曜開始の利益ガードは維持

- 結果:

  - `WEEKS >= +1%: 147/214` -> `149/214`

  - `POSITIVE WEEKS: 152/214` -> `153/214`

  - `TOTAL RETURN: +7533.68%` -> `+7932.01%`

  - `CLOSED TRADES: 509` -> `509`

  - `WIN RATE: 50.29%` -> `50.29%`

  - `PROFIT FACTOR: 1.52` -> `1.52`

  - `AVG MONTH ACTIVE RATE: 50.50%` -> `50.50%`

  - `MONTHS >= 3/4 ACTIVE: 2/50` -> `2/50`

  - `WORST DAY: -5,769,156円` -> `-6,068,499円`

  - 最大日次損失率は `-10.42%` -> `-10.39%`

- 判断:

  - 週次達成本数を `2` 週増やし、positive weeks と総リターンも改善、PF と稼働率を維持できたため採用

  - 絶対額の `WORST DAY` は悪化するため、次に進めるなら週後半 catchup のまま日次損失率を抑える position sizing 条件を分析する

### 2026-05-07: Catchup Gapdown Sizing and 26x Late-Week Catchup

- 分析:

  - `22x` 採用後の未達週は、惜しい週より深い負け週が中心で、週後半 catchup の攻め方と `catchup_gapdown` の損失集中が次の焦点だった

  - 全体の `primary` equity notional を落とす案は、`WEEKS >= +1%` が `142-146/214` へ悪化した

  - `catchup_gapdown` だけ equity notional を下げると、週次本数を維持しながら worst day と PF が改善する余地があった

- 変更:

  - `DAYTRADE_CATCHUP_GAPDOWN_EQUITY_NOTIONAL_PCT` を `1.00` から `0.70` に変更

  - `DAYTRADE_WEEKLY_CATCHUP_LEVERAGE_MULT` を `22.00` から `26.00` に変更

- 結果:

  - `WEEKS >= +1%: 149/214` -> `150/214`

  - `POSITIVE WEEKS: 153/214` -> `154/214`

  - `TOTAL RETURN: +7932.01%` -> `+7722.75%`

  - `CLOSED TRADES: 509` -> `511`

  - `WIN RATE: 50.29%` -> `50.29%`

  - `PROFIT FACTOR: 1.52` -> `1.53`

  - `AVG MONTH ACTIVE RATE: 50.50%` -> `50.70%`

  - `MONTHS >= 3/4 ACTIVE: 2/50` -> `3/50`

  - `WORST DAY: -6,068,499円` -> `-5,878,008円`

- 判断:

  - `+1%` 週、positive weeks、PF、月間稼働、最大日次損失が同時に改善したため採用

  - 総リターンは少し下がるが、週次達成率を優先しつつ損失集中も抑える目的に合う

### 2026-05-07: Low-Breadth Fallback Defense and Tuesday Far-Trend Primary Filter

- 分析:

  - 現行 `150/214` の未達週は `64` 週で、うち負け週が `54`、ノートレード週が `6`

  - 未達週の rank1 実トレードでは、`primary` の火曜と月曜が最大の損失源だった

    - 火曜 `primary`: `33` 件、合計 `-24,171,555円`、平均 `-732,471円`

    - 月曜 `primary`: `30` 件、合計 `-22,822,823円`、平均 `-760,761円`

  - ただし月曜 `primary` の gap / RS / trend 追加フィルタは、いずれも `WEEKS >= +1%` を `145-149/214` へ悪化させた

  - `fallback` は、breadth `< 0.40` かつ gap `<= 0.3%` の横ばい寄りが負け週に偏り、この防御だけなら `WEEKS >= +1%` 維持、positive weeks と PF と worst day を改善した

  - 火曜 `primary` の `open_vs_sma_atr >= 4.0` は単独だと PF と worst day のトレードオフが悪かったが、低 breadth `fallback` 防御と組み合わせると `+1%` 週を `1` 週増やした

- 変更:

  - `fallback` で breadth `< 0.40` かつ gap `<= 0.3%` を shared logic で除外

  - 火曜 `primary` で `open_vs_sma_atr >= 4.0` を shared logic で除外

- 結果:

  - `WEEKS >= +1%: 150/214` -> `151/214`

  - `POSITIVE WEEKS: 154/214` -> `156/214`

  - `TOTAL RETURN: +7722.75%` -> `+8354.64%`

  - `CLOSED TRADES: 511` -> `507`

  - `WIN RATE: 50.29%` -> `50.69%`

  - `PROFIT FACTOR: 1.53` -> `1.54`

  - `AVG MONTH ACTIVE RATE: 50.70%` -> `50.34%`

  - `MONTHS >= 3/4 ACTIVE: 3/50` -> `3/50`

  - `WORST DAY: -5,878,008円` -> `-6,849,284円`

- 判断:

  - 週次 `+1%` 本数、positive weeks、総リターン、PF が同時に改善したため採用

  - 月間稼働率は少し下がり、`WORST DAY` の絶対額は悪化するため、次の明確な課題は火曜 `primary` と週後半 catchup の損失率制御

  - 火曜 `open_vs_sma_atr >= 4.0` の単独採用は引き続き不採用で、今回の採用根拠は低 breadth `fallback` 防御との組み合わせ

### 2026-05-07: Tuesday Moderate-Gap Primary Defense

- 分析:

  - `151/214` へ改善後も、未達週の rank1 では火曜 `primary` が `29` 件、合計 `-29,316,182円`、平均 `-1,010,903円` と最大の損失源だった

  - 全体期待値でも、火曜 `primary` の gap `1.2-2.0%` は `24` 件、合計 `-6,804,936円`、勝率 `16.7%`

  - 火曜 `open_vs_sma_atr 0-1`、`0-2`、breadth `0.6-0.7` の広い除外は `WEEKS >= +1%` を `146-148/214` へ悪化させた

- 変更:

  - 火曜 `primary` で `1.2% <= gap <= 2.0%` を shared logic で除外

- 結果:

  - `WEEKS >= +1%: 151/214` -> `151/214`

  - `POSITIVE WEEKS: 156/214` -> `157/214`

  - `TOTAL RETURN: +8354.64%` -> `+8759.21%`

  - `CLOSED TRADES: 507` -> `505`

  - `WIN RATE: 50.69%` -> `50.89%`

  - `PROFIT FACTOR: 1.54` -> `1.63`

  - `AVG MONTH ACTIVE RATE: 50.34%` -> `50.14%`

  - `MONTHS >= 3/4 ACTIVE: 3/50` -> `2/50`

  - `WORST DAY: -6,849,284円` -> `-6,275,318円`

- 判断:

  - 週次 `+1%` 本数を落とさず、positive weeks、PF、最大日次損失を改善したため採用

  - 月間 `3/4` 稼働月は `1` か月減るため、次に追加するならトレード頻度を無理に上げるのではなく、期待値を保ったまま未達週を埋める新情報が必要

### 2026-05-07: Thursday Stall-Trend Defense and 30x Catchup

- 分析:

  - 現行 `151/214` から再集計すると、未達週は `63`、負け週は `51`、ノートレード未達は `6`

  - もう少しで届く正の未達週は `12` あり、週後半 catchup の余地は残っていた

  - 未達週 rank1 では火曜・月曜 `primary` がまだ大きいが、火曜 `open_vs_sma_atr 0-1`、火曜 breadth `0.6-0.7`、月曜 gap `0.6-1.2%` の広い除外は週次本数を落とした

  - 全体期待値で見ると、木曜 `primary` の `open_vs_sma_atr 3-4` は `15` 件、合計 `-3,043,188円`、勝率 `13.3%`、未達週 `4` 件で、削る根拠が比較的きれいだった

- 変更:

  - 木曜 `primary` で `3.0 <= open_vs_sma_atr <= 4.0` を shared logic で除外

  - `DAYTRADE_WEEKLY_CATCHUP_LEVERAGE_MULT` を `26.00` から `30.00` に変更

- 結果:

  - `WEEKS >= +1%: 151/214` -> `154/214`

  - `POSITIVE WEEKS: 157/214` -> `156/214`

  - `TOTAL RETURN: +8759.21%` -> `+7592.53%`

  - `CLOSED TRADES: 505` -> `506`

  - `WIN RATE: 50.89%` -> `50.99%`

  - `PROFIT FACTOR: 1.63` -> `1.64`

  - `AVG MONTH ACTIVE RATE: 50.14%` -> `50.22%`

  - `MONTHS >= 3/4 ACTIVE: 2/50` -> `2/50`

  - `WORST DAY: -6,275,318円` -> `-5,448,043円`

- 判断:

  - `+1%` 週を `3` 週増やし、PF と最大日次損失も改善したため採用

  - positive weeks と総リターンは下がるため、採用理由は総リターン最大化ではなく、週次達成本数と損失集中の改善

  - 採用後の再集計では、未達週 `60`、負け週 `52`、ノートレード未達 `6`。残る火曜/月曜 `primary` は広く削ると週次本数が落ちるため、同じ単純フィルタ近傍は避ける

### 2026-05-07: Wednesday Stall-Gap and Far-Trend Primary Defense

- 分析:

  - 現行 `154/214` から再集計すると、未達週は `60`、負け週は `52`、ノートレード未達は `6`

  - 水曜 `primary` は未達週で `31` 件、合計 `-6,042,969円`

  - 全体期待値では、水曜 `primary` の gap `0.6-1.2%` が `14` 件で合計 `-2,633,947円`、勝率 `0%`

  - 水曜 `primary` の `open_vs_sma_atr >= 4.0` も `4` 件で合計 `-1,499,656円`、勝率 `0%`

  - 一方、金曜 `catchup_rs` 除外や火曜/曜日広域フィルタは、週次本数か worst day を悪化させた

- 変更:

  - 水曜 `primary` で `0.6% <= gap <= 1.2%` を shared logic で除外

  - 水曜 `primary` で `open_vs_sma_atr >= 4.0` を shared logic で除外

- 結果:

  - `WEEKS >= +1%: 154/214` -> `156/214`

  - `POSITIVE WEEKS: 156/214` -> `158/214`

  - `TOTAL RETURN: +7592.53%` -> `+9950.17%`

  - `CLOSED TRADES: 506` -> `503`

  - `WIN RATE: 50.99%` -> `51.69%`

  - `PROFIT FACTOR: 1.64` -> `1.74`

  - `AVG MONTH ACTIVE RATE: 50.22%` -> `49.91%`

  - `MONTHS >= 3/4 ACTIVE: 2/50` -> `2/50`

  - `WORST DAY: -5,448,043円` -> `-7,118,921円`

- 判断:

  - `+1%` 週、positive weeks、総リターン、PF が同時に改善したため採用

  - `WORST DAY` の絶対額は悪化するが、最大日次損失率は約 `-6.64%` で前回とほぼ同水準。次の課題は火曜 `primary` の高gap/浅trend損失を、代替候補悪化なしで抑えること

  - 採用後の再集計では、未達週 `58`、負け週 `50`、ノートレード未達 `6`

### 2026-05-07: Tuesday Index-Gap Mid-Breadth Defense and Inverse Sizing

- 分析:

  - 現行 `156/214` から再集計すると、未達週は `58`、負け週は `50`、ノートレード未達は `6`

  - 未達週の損失はまだ月曜・火曜 `primary` に偏っていたが、火曜 `primary` を単純に広く削る案はこれまで何度も週次本数を落としていた

  - 火曜 `primary` の残り損失では、指数が +1%以上ギャップアップし、breadth が `0.50-0.60` の中途半端な地合いで追う日が、PF と worst day を崩していた

  - 近い未達週には `inverse` / `inverse_pullback` の寄与で届きそうな週があり、`inverse` の equity cap `0.70` は週次本数を `1` 週増やした

- 変更:

  - 火曜 `primary` で breadth `0.50-0.60` かつ指数ギャップ `>= +1.0%` を shared logic で除外

  - `DAYTRADE_INVERSE_NOTIONAL_PCT` と `DAYTRADE_INVERSE_EQUITY_NOTIONAL_PCT` を `0.50` から `0.70` に変更

  - `backtest.py` から shared logic へ `market_open` / `prev_market_close` を渡し、指数ギャップ条件を本番ロジック側で判定

- 結果:

  - `WEEKS >= +1%: 156/214` -> `157/214`

  - `POSITIVE WEEKS: 158/214` -> `159/214`

  - `TOTAL RETURN: +9950.17%` -> `+10414.79%`

  - `CLOSED TRADES: 503` -> `502`

  - `WIN RATE: 51.69%` -> `51.39%`

  - `PROFIT FACTOR: 1.74` -> `1.86`

  - `AVG MONTH ACTIVE RATE: 49.91%` -> `49.83%`

  - `MONTHS >= 3/4 ACTIVE: 2/50` -> `2/50`

  - `WORST DAY: -7,118,921円` -> `-5,420,216円`

- 判断:

  - `+1%` 週、positive weeks、総リターン、PF、最大日次損失が同時に改善したため採用

  - 採用後の再集計では、未達週 `57`、負け週 `49`、ノートレード未達 `6`

  - まだ週次目標には遠いが、火曜 `primary` の広い除外ではなく、指数ギャップと breadth の組み合わせで損失集中を抑えられた点は次回以降の有効な方向

### 2026-05-08: Fallback Equity Cap

- 分析:

  - 現行 `157/214` の次候補として水曜 `primary` の gap `0.3-0.6%` 除外を検証したところ、`158/214` へ伸びたが `WORST DAY -8,743,906円` まで悪化した

  - 約定トレースで確認すると、悪化の主因は水曜小ギャップ除外そのものではなく、週内 catchup レバレッジ中に `fallback` が約 `3.0x equity` まで膨らんだ日だった

  - `fallback` は `notional_pct 0.04` だけで equity cap がなく、dynamic leverage が大きい週では本来の補助 setup 以上に大きくなっていた

  - `fallback` equity cap `0.7/1.0/1.2/1.5/2.0/2.5` を比較し、`1.2` が `+1%` 週、positive weeks、総リターン、PF のバランスで最良だった

- 変更:

  - `DAYTRADE_FALLBACK_EQUITY_NOTIONAL_PCT = 1.20` を追加

  - `fallback` 候補に `equity_notional_pct` を設定し、shared logic と `backtest.py` の仮想約定で同じ上限を使う

- 結果:

  - `WEEKS >= +1%: 157/214` -> `159/214`

  - `POSITIVE WEEKS: 159/214` -> `160/214`

  - `TOTAL RETURN: +10414.79%` -> `+12922.53%`

  - `CLOSED TRADES: 502` -> `504`

  - `WIN RATE: 51.39%` -> `51.79%`

  - `PROFIT FACTOR: 1.86` -> `1.89`

  - `AVG MONTH ACTIVE RATE: 49.83%` -> `50.01%`

  - `MONTHS >= 3/4 ACTIVE: 2/50` -> `2/50`

  - `WORST DAY: -5,420,216円` -> `-6,708,628円`

- 判断:

  - `+1%` 週を `2` 週増やし、positive weeks、総リターン、PF、稼働率も改善したため採用

  - `WORST DAY` の絶対額は悪化するが、水曜小ギャップ単独案の `-8,743,906円` より大きく抑えられ、補助 setup の建玉上限としても説明可能

  - 次に進める場合は、水曜 gap `0.3-0.6%` を再度単独採用するのではなく、今回の `fallback` cap 後の残未達週を再集計してから判断する

### 2026-05-08: Post-Fallback Catchup-Gapdown Cap Tightening

- 分析:

  - `fallback` cap 採用後の `159/214` 版を再集計すると、未達週は `55`、負け週は `48`、ノートレード未達は `6`

  - 最悪日は火曜 `catchup_gapdown` で、`2026-03-31` に `-6,708,628円`

  - `catchup_gapdown` equity cap `0.45/0.50/0.55/0.60/0.65/0.70/0.75/0.80/0.90/1.00` を、`fallback` cap 後の資産経路で再検証した

- 変更:

  - `DAYTRADE_CATCHUP_GAPDOWN_EQUITY_NOTIONAL_PCT` を `0.70` から `0.60` に変更

- 結果:

  - `WEEKS >= +1%: 159/214` -> `159/214`

  - `POSITIVE WEEKS: 160/214` -> `160/214`

  - `TOTAL RETURN: +12922.53%` -> `+12585.99%`

  - `CLOSED TRADES: 504` -> `504`

  - `WIN RATE: 51.79%` -> `51.79%`

  - `PROFIT FACTOR: 1.89` -> `1.90`

  - `AVG MONTH ACTIVE RATE: 50.01%` -> `50.01%`

  - `MONTHS >= 3/4 ACTIVE: 2/50` -> `2/50`

  - `WORST DAY: -6,708,628円` -> `-5,553,500円`

- 判断:

  - 週次 `+1%` 本数と positive weeks を維持したまま、PF と最大日次損失を改善したため採用

  - cap `0.75` は `160/214` まで伸びたが、`PF 1.88`、`WORST DAY -7,974,826円` まで悪化するため不採用

  - cap `0.45/0.50/0.55` は worst day を抑えるが `157-158/214` へ落ち、cap `0.80+` は PF と worst day が悪化したため不採用

### 2026-05-08: Wednesday Small-Gap Defense with Monday/Tuesday Primary Sizing

- 分析:

  - `159/214` の残未達週では、`primary` の大きい負け塊が次に残っていた

    - 月曜 `primary` gap `0.6-1.2%` かつ `open_vs_sma_atr 3-4`

    - 火曜 `primary` breadth `0.60-0.70` かつ `open_vs_sma_atr 0-1`

    - 水曜 `primary` gap `0.3-0.6%`

  - 月曜・火曜の広い hard filter は過去ログどおり週次本数を崩しやすかったため、今回は除外ではなく `primary` の equity cap で損失集中を抑える仮説に切り替えた

  - 水曜 small gap は単独だと `160/214` まで伸びるが、`WORST DAY -7,461,337円` と下振れが重かった

  - 組み合わせ比較では、`catchup_gapdown cap 0.50` を再度合わせると、水曜 small-gap を採用しつつ下振れを抑えられた

- 変更:

  - 水曜 `primary` で gap `0.3-0.6%` を shared logic で除外

  - 月曜 `primary` で gap `0.6-1.2%` かつ `open_vs_sma_atr 3-4` の equity notional 上限を `0.75`

  - 火曜 `primary` で breadth `0.60-0.70` かつ `open_vs_sma_atr 0-1` の equity notional 上限を `0.75`

  - `DAYTRADE_CATCHUP_GAPDOWN_EQUITY_NOTIONAL_PCT` を `0.60` から `0.50` に変更

- 結果:

  - `WEEKS >= +1%: 159/214` -> `160/214`

  - `POSITIVE WEEKS: 160/214` -> `162/214`

  - `TOTAL RETURN: +12585.99%` -> `+13061.34%`

  - `CLOSED TRADES: 504` -> `500`

  - `WIN RATE: 51.79%` -> `52.40%`

  - `PROFIT FACTOR: 1.90` -> `1.92`

  - `AVG MONTH ACTIVE RATE: 50.01%` -> `49.63%`

  - `MONTHS >= 3/4 ACTIVE: 2/50` -> `2/50`

  - `WORST DAY: -5,553,500円` -> `-4,987,373円`

- 判断:

  - `+1%` 週、positive weeks、総リターン、PF、勝率、最大日次損失を同時に改善できたため採用

  - `mon075 + wed + catchup 0.50` は `160/214` と `PF 1.99` まで伸びたが、`WORST DAY -5,780,268円` と baseline より悪化するため不採用

  - 火曜側を `cap 1.0` や hard filter に寄せた案は `PF 2.02-2.05` まで伸びたが、`WORST DAY -6.0M` 台へ戻るため、今回は下振れ優先で `0.75` を採用

  - 再試行するなら、火曜側はさらに攻めるのではなく、水曜 small-gap 採用後に残る月曜 `primary` と金曜 `catchup_rs` の負け週寄与を再分解してからにする

### 2026-05-08: Tuesday Non-Positive-Gap Primary Sizing

- 分析:

  - `161/214` の再集計では、未達週 `53` の中で次に大きい損失塊が火曜 `primary` だった

  - とくに breadth `0.60-0.70` かつ `gap <= 0` の火曜 `primary` は、全週でも `8` trades / `-5.00M`、未達週だけで `4` trades / `-4.67M` と偏っていた

  - 一方で同じ火曜でも breadth `0.70+` や gap `0.6%+` は全体ではまだ正の期待値が残っており、広い hard filter や `gap < 0.6%` 全体 cap は削りすぎだった

  - 月曜 `primary` の high-gap / mid-trend cap も再検証したが、総リターンと PF は伸びても `WEEKS >= +1%` は `161/214` のままで、`WORST DAY` も悪化した

- 変更:

  - 火曜 `primary` で breadth `0.60-0.70` かつ `gap <= 0` の equity notional 上限を `0.75`

  - shared helper に追加し、`core/logic.py` と `backtest.py` の両方から同じ判定を参照

- 結果:

  - `WEEKS >= +1%: 161/214` -> `163/214`

  - `POSITIVE WEEKS: 163/214` -> `165/214`

  - `TOTAL RETURN: +13400.53%` -> `+13424.02%`

  - `CLOSED TRADES: 500` -> `499`

  - `WIN RATE: 52.40%` -> `52.30%`

  - `PROFIT FACTOR: 1.95` -> `2.02`

  - `AVG MONTH ACTIVE RATE: 49.63%` -> `49.54%`

  - `MONTHS >= 3/4 ACTIVE: 2/50` -> `2/50`

  - `WORST DAY: -5,053,952円` -> `-5,060,005円`

- 判断:

  - `+1%` 週を `2` 週、positive weeks を `2` 週増やし、総リターンと PF も改善できたため採用

  - 同じ仮説でも `gap < 0.6%` まで広げる cap は `162/214` に留まり、総リターンを `+12216.85%` まで削るため不採用

  - 月曜 `high-gap / mid-trend` cap は `161/214` のまま `WORST DAY -5.25M` から `-5.45M` へ悪化するため不採用

  - 再試行するなら、火曜 `primary` はこの `gap <= 0` ルールを前提にしたうえで、残る `catchup_gapdown` 単発大損と水曜 `fallback` の扱いを別仮説で切り分けること

### 2026-05-08: Wednesday High-Breadth Fallback Sizing

- 分析:

  - `163/214` の再集計では、未達週 `51` のうち `2026-W08` が `+0.74%` の近接未達で、主因は水曜 `fallback 1723.T -2.15M` だった

  - 一方で、水曜 `fallback gap > 0.5%` を広く締める案は `2025-W08` の勝ち筋 `2413.T +346k` まで削って、`164` に届かなかった

  - 実行実績を絞ると、水曜 `fallback` で breadth `>= 0.75` かつ gap `> 0.5%` は `2` 本しかなく、`5602.T +30k` と `1723.T -2.15M` で損益が大きく偏っていた

  - つまり、gap 単独ではなく「水曜 high breadth に限った fallback 過熱」が原因仮説として最も説明しやすかった

- 変更:

  - `resolve_daytrade_fallback_equity_notional_pct` に breadth 引数を追加

  - 火曜・水曜の `gap > 0.5%` fallback cap `0.75` は維持したまま、水曜かつ breadth `>= 0.75` ではさらに equity notional 上限を `0.30` に制限

  - `core/logic.py` と `backtest.py` の両方で同じ helper を参照

- 結果:

  - `WEEKS >= +1%: 163/214` -> `164/214`

  - `POSITIVE WEEKS: 165/214` -> `165/214`

  - `TOTAL RETURN: +13424.02%` -> `+13583.24%`

  - `CLOSED TRADES: 499` -> `499`

  - `WIN RATE: 52.30%` -> `52.30%`

  - `PROFIT FACTOR: 2.02` -> `2.04`

  - `AVG MONTH ACTIVE RATE: 49.54%` -> `49.54%`

  - `MONTHS >= 3/4 ACTIVE: 2/50` -> `2/50`

  - `WORST DAY: -5,060,005円` -> `-5,060,005円`

- 判断:

  - `+1%` 週を `1` 週増やしつつ、総リターンと PF も改善できたため採用

  - gap 単独の水曜 fallback cap `0.40/0.50` は `2026-W08` を救う一方で `2025-W08` を落とし、`163/214` のままなので不採用

  - 火曜 shallow `catchup_gapdown` cap `0.25` は総リターンと PF を押し上げたが、`+1%` 週は増えず、実行実績 `1` 本に近い narrow rule だったため今回は不採用

  - 月曜 breadth `0.70-0.80` / gap `<= 1.2%` `primary` cap は `2025-W29` を超過に押し上げたが、総リターンと PF を崩して `163/214` に留まったため不採用

  - 再試行するなら、次の焦点は依然として `2026-W14` の火曜 `catchup_gapdown` と、月曜 `primary` の broader loss cluster だが、前者は単発寄り、後者は広げると性能悪化が目立つため、次回はより説明可能な breadth / gap / trend の分解を先に行うこと

### 2026-05-08: Monday Soft-Gap Primary Sizing with Tuesday Shallow Catchup Cap

- 分析:

  - `164/214` の再集計では、`POSITIVE WEEKS` と `WEEKS >= +1%` が同数になり、残る未達週に「あと少しで `+1%`」の正週がなくなった

  - その状態で唯一近い未達は `2025-W29 +0.61%` で、主因は月曜 `primary 3350.T -340k` だった

  - 実行トレースで見ると、月曜 `primary` の breadth `0.70-0.80` かつ gap `0-0.6%` は全期間で `6 trades / -4.57M`、勝ちは `1` 本だけで、狭いが明確に期待値が崩れていた

  - 同時に、火曜 `catchup_gapdown` の breadth `0.35-0.45` / gap `-1.5%~-0.6%` は、単独採用では `+1%` 週を増やせなかったが、月曜 cap 後の資産経路では `WORST DAY` を悪化させずに `PF` と総リターンを押し上げられた

- 変更:

  - 月曜 `primary` で breadth `0.70-0.80` かつ gap `0-0.6%` の equity notional 上限を `1.00`

  - 火曜 `catchup_gapdown` で breadth `0.35-0.45` かつ gap `-1.5%~-0.6%` の equity notional 上限を `0.25`

  - どちらも shared helper に実装し、`core/logic.py` と `backtest.py` で同じ判定を使用

- 結果:

  - `WEEKS >= +1%: 164/214` -> `165/214`

  - `POSITIVE WEEKS: 165/214` -> `165/214`

  - `TOTAL RETURN: +13583.24%` -> `+14320.13%`

  - `CLOSED TRADES: 499` -> `499`

  - `WIN RATE: 52.30%` -> `52.30%`

  - `PROFIT FACTOR: 2.04` -> `2.12`

  - `AVG MONTH ACTIVE RATE: 49.54%` -> `49.54%`

  - `MONTHS >= 3/4 ACTIVE: 2/50` -> `2/50`

  - `WORST DAY: -5,060,005円` -> `-5,235,531円`

- 判断:

  - `+1%` 週をさらに `1` 週増やし、総リターンと PF も大きく改善したため採用

  - 月曜 cap `0.75` も `165/214` だったが、`WORST DAY` がさらに悪化するため不採用

  - 月曜 cap 単独でも `165/214` に届いたが、火曜 shallow `catchup_gapdown` cap を重ねても `WEEKS >= +1%` と `WORST DAY` が据え置きで、総リターンと PF が追加改善したため、今回は組み合わせ案を採用

  - この採用後は `POSITIVE WEEKS = WEEKS >= +1%` となり、残未達週はすべて非プラス週になった

  - 再試行するなら、次は単純な near-miss 埋めではなく、残る深い負け週を setup 別に削り直す段階であり、軽い size tweak だけで `166+` を狙う根拠はかなり弱くなっている

### 2026-05-08: Wednesday Hot-Gap Below-SMA Primary + Monday Mid-Gap Far-Trend Tightening

- 分析:

  - `165/214` の再集計では、未達週はすべて非プラス週になっており、「少し足せば `+1%`」ではなく、週を丸ごとひっくり返す損失クラスターの削減が必要だった

  - flip candidate を見ると、未達週を `+1%` 超へ押し上げうる trade は月曜 `primary` と水曜 `primary` に偏っていた

  - 水曜 `primary` では、`gap >= 1.2%` なのに `open_vs_sma_atr < 0` の trade が `2023-07-26 7599.T -249k`、`2025-12-03 285A.T -2.64M`、`2026-04-01 5703.T -2.84M` と一貫して悪く、`165` 時点の未達週 `2025-W49` と `2026-W14` の主因だった

  - 一方、既存の月曜 `primary` `gap 0.6-1.2%` / `open_vs_sma_atr 3-4` cap `0.75` も、`2025-12-01 6366.T -1.94M` のようにまだ未達週を埋め切れていなかった

  - 水曜ルール単独の `cap 0.75` は `166/214`、`cap 0.50` は `165/214` で `POSITIVE WEEKS 167/214` に留まり、月曜側を残したままだと `2025-W49` を `+1%` 超へ押し切れなかった

- 変更:

  - 月曜 `primary` の `gap 0.6-1.2%` かつ `open_vs_sma_atr 3-4` equity notional cap を `0.75` から `0.50` へ引き下げ

  - 水曜 `primary` で `gap >= 1.2%` かつ `open_vs_sma_atr < 0` の equity notional cap を `0.50` で追加

  - どちらも shared helper `resolve_daytrade_primary_equity_notional_pct` に集約し、本番とバックテストで共通化

- 結果:

  - `WEEKS >= +1%: 165/214` -> `167/214`

  - `POSITIVE WEEKS: 165/214` -> `167/214`

  - `TOTAL RETURN: +14320.13%` -> `+14118.01%`

  - `CLOSED TRADES: 499` -> `500`

  - `WIN RATE: 52.30%` -> `52.40%`

  - `PROFIT FACTOR: 2.12` -> `2.20`

  - `AVG MONTH ACTIVE RATE: 49.54%` -> `49.63%`

  - `MONTHS >= 3/4 ACTIVE: 2/50` -> `2/50`

  - `WORST DAY: -5,235,531円` -> `-5,084,215円`

- 判断:

  - `2023-W30` を `-1.10% -> +1.15%`、`2025-W49` を `-1.60% -> +2.07%` に押し上げ、`+1%` 週を `2` 週増やしつつ `WORST DAY` も改善したため採用

  - 水曜 `cap 0.75` + 月曜 `cap 0.50` の組み合わせは `165/214` のまま、`WORST DAY -5,072,110円` で改善幅も弱いため不採用

  - 月曜 weak-breadth / hot-gap `primary` cap `0.75` は `166/214` まで伸びたが、`WORST DAY -5,622,900円`、`AVG MONTH ACTIVE 49.16%` と悪化するため不採用

  - 水曜 hot-gap / below-SMA と月曜 weak-breadth / hot-gap の組み合わせも `166/214` までで、`WORST DAY -5,550,268円` と下振れが悪化するため不採用

  - 再試行するなら、次は `167/214` 基準で残る火曜・木曜 `primary` の深い負け週を再分解し、同じ「flip trade が複数週に効く条件」かどうかを確認してから進めること

### 2026-05-08: Thursday Mid-Breadth Low-Gap Continuation Sizing

- 分析:

  - `167/214` の再集計では、`POSITIVE WEEKS = WEEKS >= +1%` が続いており、残未達週を増やすには非プラス週そのものを `+1%` 超へ押し上げる必要があった

  - flip candidate を見ると、火曜 `primary` と金曜 `primary` には単独で週を返せる trade が残っていなかった一方、木曜 `primary` には `2024-W01 2652.T -274k` と `2025-W50 5711.T -2.41M` が残っていた

  - 実トレースで見ると、この2本はどちらも

    - 木曜

    - breadth `0.55-0.70`

    - gap `0-0.6%`

    - `open_vs_sma_atr 1-3`

    の continuation で、all-time でもこの帯は `2 trades / -2.68M` と一貫して負けていた

  - 同時に試した月曜 weak-breadth / hot-gap `primary` や月曜 `catchup_rs` hot-gap cap は `168-169/214` まで伸びたが、いずれも `WORST DAY -5.46M` 以上へ悪化し、下振れの悪化が先に立った

- 変更:

  - 木曜 `primary` で breadth `0.55-0.70`、gap `0-0.6%`、`open_vs_sma_atr 1-3` の equity notional 上限を `1.00`

  - shared helper `resolve_daytrade_primary_equity_notional_pct` に実装し、本番とバックテストで共通化

- 結果:

  - `WEEKS >= +1%: 167/214` -> `168/214`

  - `POSITIVE WEEKS: 167/214` -> `168/214`

  - `TOTAL RETURN: +14118.01%` -> `+14740.66%`

  - `CLOSED TRADES: 500` -> `500`

  - `WIN RATE: 52.40%` -> `52.40%`

  - `PROFIT FACTOR: 2.20` -> `2.24`

  - `AVG MONTH ACTIVE RATE: 49.63%` -> `49.63%`

  - `MONTHS >= 3/4 ACTIVE: 2/50` -> `2/50`

  - `WORST DAY: -5,084,215円` -> `-5,308,163円`

- 判断:

  - `2024-W01` を `-0.63% -> +1.20%` に押し上げ、`+1%` 週を `1` 週増やしつつ総リターンと PF も改善したため採用

  - 同じ木曜仮説の `cap 0.85/0.75/0.50` はどれも `168/214` だが、`cap 1.00` が最も `WORST DAY` の悪化幅が小さく、介入も最小なので不必要に締めすぎない `1.00` を採用

  - `thu100 + catchup_rs hot-gap cap 0.75` は `169/214` まで伸びたが、`WORST DAY -5,689,479円` と悪化幅が大きく不採用

  - `thu100 + 月曜 weak-breadth / hot-gap cap 0.85` も `169/214` だが、`AVG MONTH ACTIVE 49.25%` と `WORST DAY -5,780,268円` が悪化するため不採用

  - 再試行するなら、次は `168/214` 基準で残る月曜・火曜・金曜 `primary` と火曜 `catchup_gapdown` のうち、単発大損ではなく複数週に効く条件だけを再抽出してから進めること

### 2026-05-08: Monday Low-Breadth Hot-Gap Near-SMA Primary Sizing

- 分析:

  - `168/214` の未達週を executed-trade ベースで洗い直すと、flip candidate の主因は月曜 `primary` に戻っていた

  - とくに `2024-W41 3382.T -704k` は、月曜、breadth `0.5049`、gap `+2.83%`、`open_vs_sma_atr 0.48` で、すでに強く寄ったのに trend 距離だけは浅い continuation だった

  - all-time の月曜 `primary` でも、breadth `0.50-0.55` かつ gap `>= 2.0%`、`open_vs_sma_atr < 1.0` は heavy-loss 側に寄っていた一方、近傍を広げると `WORST DAY` と稼働率が悪化した

  - 火曜 neutral-trend `primary` cap や火曜 shallow `catchup_gapdown` cap を組み合わせても `POSITIVE WEEKS` は増えるが、`WEEKS >= +1%` は増えなかった

- 変更:

  - 月曜 `primary` で breadth `0.50-0.55`、gap `>= 2.0%`、`open_vs_sma_atr < 1.0` の equity notional 上限を `1.00`

  - 実装は `resolve_daytrade_primary_equity_notional_pct` に集約し、本番とバックテストで共通化

- 結果:

  - `WEEKS >= +1%: 168/214` -> `169/214`

  - `POSITIVE WEEKS: 168/214` -> `169/214`

  - `TOTAL RETURN: +14740.66%` -> `+14710.19%`

  - `CLOSED TRADES: 500` -> `498`

  - `WIN RATE: 52.40%` -> `52.61%`

  - `PROFIT FACTOR: 2.24` -> `2.24`

  - `AVG MONTH ACTIVE RATE: 49.63%` -> `49.45%`

  - `MONTHS >= 3/4 ACTIVE: 2/50` -> `2/50`

  - `WORST DAY: -5,308,163円` -> `-5,296,057円`

- 判断:

  - `2024-W41` を `-2.05% -> +1.13%` に押し上げ、`+1%` 週を `1` 週増やしつつ `WORST DAY` もわずかに改善したため採用

  - 同じ仮説の broad rule である月曜 low-breadth / hot-gap cap `1.50/1.25` は `168/214` 止まりで、`WORST DAY` も悪化するため不採用

  - 月曜 low-breadth / hot-gap の broader split cap は `169/214` まで伸びたが、`WORST DAY -5,725,795円` と悪化幅が大きく不採用

  - 月曜 `catchup_rs` low-breadth / hot-gap cap `1.00` や、火曜 neutral-trend + shallow `catchup_gapdown` の併用も `169/214` 近辺では下振れが重く、今回の狭い月曜 `primary` cap より劣後

  - 再試行するなら、次は `169/214` 基準で残る火曜 `catchup_gapdown` の単発大損と、月曜・火曜 `primary` の複数週クラスターを分けて扱い、同じ path 改善で `170` を狙えるかを先に確認すること

### 2026-05-08: Post-169 Tuesday Follow-Up Checks

- 試したこと:

  - 火曜 breadth `0.60-0.70` / neutral-trend `primary` cap を `0.75 -> 0.50`

  - 火曜 breadth `0.35-0.45` / gap `-1.5%~-0.6%` `catchup_gapdown` cap を `0.25 -> 0.10`

  - 上記2つの併用

- 結果:

  - baseline `169/214`

  - `tue_neutral050`:

    - `WEEKS >= +1%: 169/214`

    - `POSITIVE WEEKS: 170/214`

    - `PROFIT FACTOR: 2.27`

    - `WORST DAY: -5,386,847円`

  - `tue_catchup010`:

    - `WEEKS >= +1%: 169/214`

    - `POSITIVE WEEKS: 170/214`

    - `PROFIT FACTOR: 2.27`

    - `WORST DAY: -5,296,057円`

  - `tue_combo_neutral050_catchup010`:

    - `WEEKS >= +1%: 169/214`

    - `POSITIVE WEEKS: 171/214`

    - `PROFIT FACTOR: 2.30`

    - `WORST DAY: -5,386,847円`

- 判断:

  - どの案も非プラス週の改善には効くが、`+1%` 週は1本も増えなかったため不採用

  - `169/214` 以降は、火曜の既知防御だけでは「負け週をプラス週へ戻す」までは届かず、残りは木曜やゼロトレード週を含む別要因の比重が高い

- 再試行条件:

  - 火曜単独の tighter cap を再試行するなら、`2025-W50` や `2026-W14` のような未達週を実際に `+1%` 超へ押し上げる別曜日対策とセットで行うこと

### 2026-05-08: Tuesday Positive-Gap Neutral-Trend + Thursday Continuation Tightening

- 分析:

  - `169/214` の最接近未達週では、`2025-W50` が `-0.14%` まで詰まっており、日次では

    - 月曜 `-569k`

    - 火曜 `-1.70M`

    - 水曜 `+2.12M`

    - 木曜 `-1.22M`

    - 金曜 `+1.29M`

    と、火曜 `primary` と木曜 `primary` の複合負けが主因だった

  - 火曜単独の tighter cap や木曜 continuation 単独の tighter cap は、どちらも positive week は増やせても `+1%` 週には届かなかった

  - 一方で、火曜 `breadth 0.60-0.70` / positive-gap / neutral-trend `primary` と、木曜 `breadth 0.55-0.70` / gap `0-0.6%` / continuation `primary` は、どちらも既存の weak cluster としてすでに確認済みで、この2つを同時に少しだけ締めると `2025-W50` が `+1%` を超えた

  - `2026-W14` の火曜 `catchup_gapdown` を `0.10 -> 0.00` まで落とす案も確認したが、資産経路全体が崩れて `WORST DAY -15.04M`、`FINAL EQUITY 135.37M` まで悪化したため切った

- 変更:

  - 火曜 `primary` で breadth `0.60-0.70`、positive gap、`open_vs_sma_atr 0-1` の equity notional 上限を `0.50`

  - 木曜 `primary` で breadth `0.55-0.70`、gap `0-0.6%`、`open_vs_sma_atr 1-3` の equity notional 上限を `0.90`

  - どちらも `resolve_daytrade_primary_equity_notional_pct` に集約し、本番とバックテストで共通化

- 結果:

  - `WEEKS >= +1%: 169/214` -> `170/214`

  - `POSITIVE WEEKS: 169/214` -> `170/214`

  - `TOTAL RETURN: +14710.19%` -> `+14998.07%`

  - `CLOSED TRADES: 498` -> `498`

  - `WIN RATE: 52.61%` -> `52.61%`

  - `PROFIT FACTOR: 2.24` -> `2.27`

  - `AVG MONTH ACTIVE RATE: 49.45%` -> `49.45%`

  - `MONTHS >= 3/4 ACTIVE: 2/50` -> `2/50`

  - `WORST DAY: -5,296,057円` -> `-5,398,952円`

- 判断:

  - `2025-W50` を `-0.14% -> +1.09%` に押し上げ、`+1%` 週を `1` 週増やしつつ PF と総リターンも改善したため採用

  - 木曜単独 tighter cap `0.75/0.50` はどちらも `169/214` 止まりで、positive week だけ増えて `+1%` 週は増えなかったため不採用

  - 火曜 positive-gap cap `0.50` と木曜 cap `0.85/0.75/0.50` の組み合わせも `170/214` は出るが、`WORST DAY -5.41M` から `-5.49M` まで悪化幅が広がるため、最も浅い `0.90` を採用

  - 木曜 cap `0.95` では `2025-W50` が `+0.98%` に届かず `169/214` のまま、火曜 cap `0.55/0.60` も同様に境界を超えなかった

  - 再試行するなら、次は `170/214` 基準で残るゼロトレード週と、`2026-W14` のような単発大損週を同じ施策で触らず、候補追加と損失防御を分離して再分析すること

### 2026-05-08: Catchup-Gapdown Monday/Tuesday Trend-Aware Tightening

- 分析:

  - `170/214` の次の近い未達では `2026-W14 -0.63%` が最も説明しやすく、内訳は

    - 月曜 `catchup_gapdown 4596.T -1.82M`

    - 火曜 `catchup_gapdown 6085.T -2.64M`

    - 水曜 `primary 5703.T -0.73M`

    - 木曜 `primary 5726.T +4.23M`

    で、月火の `catchup_gapdown` 2本が主因だった

  - all-time でも

    - 月曜 breadth `0.35-0.45` / gap `-2.0%~-1.5%` / `open_vs_sma_atr < -1.0`

    - 火曜 breadth `0.35-0.45` / gap `-1.0%~-0.6%` / `open_vs_sma_atr -0.2~0.5`

    の `catchup_gapdown` は heavy-loss クラスターだった

  - ゼロトレード週に対して、low-breadth `catchup-only` 日へ専用 buying power を与える案も試したが、稼働率は上がる一方で `WEEKS >= +1%` が `151-152/214` まで崩れたため不採用にした

  - 水曜 `primary` を追加で締める案は `171/214` も出たが、資産経路を大きく削って `FINAL EQUITY 133M` 台まで落ちたため切った

- 変更:

  - 月曜 `catchup_gapdown` で breadth `0.35-0.45`、gap `-2.0%~-1.5%`、`open_vs_sma_atr < -1.0` の equity notional 上限を `0.25`

  - 火曜 `catchup_gapdown` で breadth `0.35-0.45`、gap `-1.0%~-0.6%`、`open_vs_sma_atr -0.2~0.5` の equity notional 上限を `0.10`

  - `resolve_daytrade_catchup_equity_notional_pct` に `open_vs_sma_atr` を渡すよう拡張し、本番スキャンとバックテストの両方から同じ helper を参照

- 結果:

  - `WEEKS >= +1%: 170/214` -> `171/214`

  - `POSITIVE WEEKS: 170/214` -> `171/214`

  - `TOTAL RETURN: +14998.07%` -> `+15220.03%`

  - `CLOSED TRADES: 498` -> `498`

  - `WIN RATE: 52.61%` -> `52.41%`

  - `PROFIT FACTOR: 2.27` -> `2.32`

  - `AVG MONTH ACTIVE RATE: 49.45%` -> `49.45%`

  - `MONTHS >= 3/4 ACTIVE: 2/50` -> `2/50`

  - `WORST DAY: -5,398,952円` -> `-5,386,847円`

- 判断:

  - `2026-W14` を `-0.63% -> +1.06%` に押し上げ、`+1%` 週を `1` 週増やしつつ PF、総リターン、`WORST DAY` も改善したため採用

  - 月曜 cap `0.35/0.30` や火曜 cap `0.15/0.20` まで緩める近傍は、`POSITIVE WEEKS 171/214` までは伸びても `WEEKS >= +1%` は `170/214` のままだったため不採用

  - 火曜 narrow cap を `0.00` まで落とす案は、たとえ狭い条件でも資産経路が崩れて `WORST DAY -15.33M`、`FINAL EQUITY 137.99M` と悪化したため不採用

  - 月火 cap に加えて水曜 `primary` を `0.25` へ締める案は `171/214` でも `FINAL EQUITY 132-133M` まで大きく削ったため採らない

  - 再試行するなら、次は残る close miss の `2024-W43` / `2022-W09` と、ゼロトレード週を別々に扱い、候補追加で稼働率を触る案が `171/214` を壊さないかを先に確認すること

### 2026-05-08: Catchup-Only Low-Breadth Buying Power Trial

- 試したこと:

  - breadth が低く `catchup` しか残らない日に、`catchup-only` 候補セットへ専用 buying power を付与

  - 専用 leverage `0.25 / 0.35 / 0.50 / 0.75 / 1.00` を比較

- 結果:

  - `avg month active` は `52.96%-59.30%` まで上がった

  - ただし `WEEKS >= +1%` は `151-152/214` まで悪化

  - `FINAL EQUITY` も `116M-123M` に低下

- 判断:

  - ゼロトレード週の一部は埋まるが、低 breadth の `catchup` をそのまま実行すると週次目標を大きく壊すため不採用

- 再試行条件:

  - `catchup` 候補の ranking / stop / target 側に新しい情報を足して、低 breadth 執行の質そのものを改善できる場合のみ

### 2026-05-08: Monday Catchup-RS Low-Breadth / Hot-Gap Tightening

- 分析:

  - `171/214` 時点で、単独トレードを抑えるだけで `+1%` を超えうる close miss はかなり減っており、残る中で最も説明しやすかったのが月曜 `catchup_rs` の損失クラスターだった

  - all-time でも月曜 `catchup_rs` は `11 trades / -4.60M` と弱く、特に breadth `< 0.45`、gap `>= 1.2%`、`open_vs_sma_atr >= 1.5` の「弱い地合いの中でギャップだけ先行した continuation chase」がまとまって悪かった

  - 月曜 `catchup_rs` 全体を広く締める案でも `172/214` は出たが、`WORST DAY -6.23M~-6.72M` と悪化幅が大きかったため、今回は弱い帯だけに絞った

- 変更:

  - 月曜 `catchup_rs` で breadth `< 0.45`、gap `>= 1.2%`、`open_vs_sma_atr >= 1.5` の equity notional 上限を `0.75`

- 結果:

  - `WEEKS >= +1%: 171/214` -> `172/214`

  - `POSITIVE WEEKS: 171/214` -> `172/214`

  - `TOTAL RETURN: +15220.03%` -> `+16421.46%`

  - `CLOSED TRADES: 498` -> `498`

  - `WIN RATE: 52.41%` -> `52.41%`

  - `PROFIT FACTOR: 2.32` -> `2.33`

  - `AVG MONTH ACTIVE RATE: 49.45%` -> `49.45%`

  - `MONTHS >= 3/4 ACTIVE: 2/50` -> `2/50`

  - `WORST DAY: -5,386,847円` -> `-5,810,532円`

- 判断:

  - `2023-W12` を `+1%` 超えまで押し上げ、`+1%` 週を `1` 週増やしつつ PF と総リターンも改善したため採用

  - cap `0.70/0.75/0.80` はいずれも `172/214` を維持し、`0.85/0.90/1.00` は `171/214` のままだったため、改善帯の中で最も浅い `0.75` を採用

  - 絶対額の `WORST DAY` は悪化したが、広い月曜 `catchup_rs` cap や `strong_oversold` 連動案より悪化幅が小さく、地合いの弱い continuation だけを抑える説明可能性も保てた

- 再試行条件:

  - 次に月曜 `catchup_rs` を再度触るなら、同じ breadth / gap 帯でも勝ち負けを分けている追加情報が見つかった場合に限ること

  - 同じ形の広域な Monday `catchup_rs` cap は、そのままでは再試行しないこと

### 2026-05-08: Broader Monday Defense / Inverse / Strong-Oversold Trials

- 試したこと:

  - 月曜 `catchup_rs` 全体 cap `1.00 / 0.75 / 0.50`

  - 月曜 `primary` breadth `0.45-0.55` / gap `>= 1.2%` / `open_vs_sma_atr 0.5-1.5` cap

  - `inverse` / `inverse_pullback` の一律 cap `0.50 / 0.35 / 0.25`

  - 月曜 `strong_oversold` cap `0.75 / 0.50`

  - 採用候補の月曜 narrow `catchup_rs` cap と月曜 `strong_oversold` cap の併用

- 結果:

  - 月曜 `catchup_rs` 全体 cap は `172/214` に届くが、`WORST DAY -6,234,216円` から `-6,724,480円` まで悪化

  - 月曜 `primary` cap の最良近傍でも `171/214` 止まりで、`WORST DAY -5,750,005円`

  - `inverse` 一律 cap は `WORST DAY -5,350,531円` まで軽くなる近傍があった一方、`WEEKS >= +1%` は `170/214` まで低下

  - 月曜 `strong_oversold` cap は単独で `171/214`、月曜 narrow `catchup_rs` cap との併用でも `WORST DAY -6.07M~-6.39M` と悪化

- 判断:

  - どれも「月曜の重い負けを広く切る」方向ではあるが、今回採用した狭い月曜 `catchup_rs` cap より下振れの悪化が大きいか、週次本数が改善しなかったため不採用

- 再試行条件:

  - 月曜の防御を再試行するなら、setup 横断で一律に締めるのではなく、`2024-W43` や `2022-W09` のような close miss を説明できる追加シグナルがある場合に限る

  - `inverse` 一律 cap は、週次 `+1%` よりも worst-day return を優先する評価軸へ切り替える場合のみ再試行候補

  - 月曜 `strong_oversold` は単独でも併用でも同じ形では再試行しない

### 2026-05-08: Friday Countertrend Selector Filter

- 分析:

  - `172/214` 時点で、ゼロトレード週を low-breadth `inverse` 優先で埋める方向は、稼働率や `POSITIVE WEEKS` は伸びても `WEEKS >= +1%` を押し上げ切れなかった

  - 一方、late-week の countertrend 側を見ると、実約定ベースで

    - 金曜 `strong_oversold`

    - 金曜 `inverse_pullback`

    がいずれも全件マイナスで、金曜の countertrend execution が weak spot になっていた

  - 木曜 `inverse_pullback` まで広げる案も `173/214` は出たが、`WORST DAY` と稼働率がさらに悪化したため、今回は金曜だけに留めた

- 変更:

  - `select_daytrade_candidates` で、金曜は `strong_oversold` と `inverse_pullback` を selector 候補から外す

  - `primary` / `fallback` / `catchup` / 通常 `inverse` の優先関係は維持

- 結果:

  - `WEEKS >= +1%: 172/214` -> `173/214`

  - `POSITIVE WEEKS: 172/214` -> `173/214`

  - `TOTAL RETURN: +16421.46%` -> `+17101.16%`

  - `CLOSED TRADES: 498` -> `496`

  - `WIN RATE: 52.41%` -> `52.82%`

  - `PROFIT FACTOR: 2.33` -> `2.36`

  - `AVG MONTH ACTIVE RATE: 49.45%` -> `49.35%`

  - `MONTHS >= 3/4 ACTIVE: 2/50` -> `2/50`

  - `WORST DAY: -5,810,532円` -> `-6,052,637円`

- 判断:

  - `+1%` 週を `1` 週増やしつつ、PF と総リターンも改善したため採用

  - サンプル数は薄いが、「金曜の countertrend を late-week でまとめて外す」形なら shared selector の説明がまだ通ると判断した

  - 木曜 `inverse_pullback` まで広げた `late-week countertrend` 案は `FINAL EQUITY 175.32M` と総リターンはさらに伸びた一方、`WORST DAY -6.17M`、`AVG MONTH ACTIVE 49.16%` まで悪化したため不採用

- 再試行条件:

  - 次に countertrend の曜日制御を触るなら、金曜だけでなく late-week 全体へ広げる根拠が、追加サンプルか別 setup でも確認できた場合に限る

  - 同じ形の `木曜 inverse_pullback` 拡張は、そのままでは再試行しない

### 2026-05-08: Low-Breadth Inverse Selector Trials

- 試したこと:

  - ゼロトレード週対策として、`primary` / `fallback` / `strong_oversold` が不在で breadth が低い日に

    - `inverse` 優先

    - `inverse_pullback` 優先

    - plain `inverse` のみ優先

    - breadth `< 0.35 / 0.30` などの近傍

    - top1 のみ採用

    を比較

- 結果:

  - 稼働率と `POSITIVE WEEKS` は改善し、代表例では `AVG MONTH ACTIVE 50.04%-50.66%`, `POSITIVE WEEKS 173-174/214`

  - ただし `WEEKS >= +1%` は `171-172/214` に留まり、`FINAL EQUITY` も多くの案で `152M-163M` 台まで低下

  - `inverse_pullback` のみ優先する案は `FINAL EQUITY 167.01M` まで伸びたが、`WEEKS >= +1%` は `171/214` へ後退

- 判断:

  - ゼロトレード週を埋める方向性自体は見えたが、現状の `inverse` / `inverse_pullback` 品質のまま selector だけ変えると、週次 `+1%` を押し上げるより資産経路を崩しやすいため不採用

- 再試行条件:

  - low-breadth 執行を再試行するなら、selector の順番だけでなく `inverse_pullback` の品質改善や dedicated sizing の根拠が増えた場合に限る

### 2026-05-08: Friday Filter Follow-Up Inverse Timing Trials

- 分析:

  - `173/214` 時点の実約定を掘ると、`inverse` 系の負け残りは

    - 火曜 `inverse`: `3 trades / 3 losses`

    - 木曜 `inverse_pullback`: `2 trades / 2 losses`

    に偏っていた

  - 一方で、月曜 `inverse_pullback` と金曜 `inverse` には勝ち筋も残っており、`inverse` 全体を広く締めるより「曜日窓だけを外す」形なら shared selector の説明がまだ通ると判断した

- 試したこと:

  - 既存の金曜 countertrend filter に加えて、火曜 `inverse` を selector 候補から除外

  - さらに木曜 `inverse_pullback` も selector 候補から除外する案

- 結果:

  - 火曜 `inverse` 除外のみ:

    - `FINAL EQUITY: 183.09M`

    - `WEEKS >= +1%: 173/214`

    - `POSITIVE WEEKS: 175/214`

    - `AVG MONTH ACTIVE RATE: 49.05%`

    - `WORST DAY: -6,440,006円`

  - 火曜 `inverse` + 木曜 `inverse_pullback` 除外:

    - `FINAL EQUITY: 185.96M`

    - `WEEKS >= +1%: 173/214`

    - `POSITIVE WEEKS: 176/214`

    - `AVG MONTH ACTIVE RATE: 48.87%`

    - `WORST DAY: -6,542,901円`

- 判断:

  - どちらも `POSITIVE WEEKS` と総リターンは伸びたが、最優先の `WEEKS >= +1%` は `173/214` のまま据え置きで、`WORST DAY` も悪化したため不採用

- 再試行条件:

  - `inverse` の曜日窓を再試行するなら、`+1%` 週を実際に押し上げる別条件と組み合わせること

  - 同じ形の「火曜 `inverse` 除外」や「木曜 `inverse_pullback` 除外」だけでは再試行しない

### 2026-05-08: Friday Filter Follow-Up Low-Breadth Inverse Variants

- 試したこと:

  - 既存の金曜 countertrend filter を維持したまま、breadth `< 0.35 / 0.30` の日に

    - `inverse` top1 優先

    - `inverse` 全件優先

    を比較

  - さらに、火曜 `inverse` 除外との併用近傍も確認

- 結果:

  - `inverse` top1 優先 breadth `< 0.30`:

    - `FINAL EQUITY: 172.35M`

    - `WEEKS >= +1%: 173/214`

    - `POSITIVE WEEKS: 174/214`

    - `AVG MONTH ACTIVE RATE: 49.55%`

    - `WORST DAY: -6,064,742円`

  - `inverse` 全件優先 breadth `< 0.35`:

    - `FINAL EQUITY: 165.72M`

    - `WEEKS >= +1%: 173/214`

    - `POSITIVE WEEKS: 174/214`

    - `AVG MONTH ACTIVE RATE: 50.55%`

    - `WORST DAY: -5,828,689円`

  - 火曜 `inverse` 除外 + `inverse` top1 優先 breadth `< 0.30`:

    - `FINAL EQUITY: 178.08M`

    - `WEEKS >= +1%: 173/214`

    - `POSITIVE WEEKS: 175/214`

    - `AVG MONTH ACTIVE RATE: 49.15%`

    - `WORST DAY: -6,264,479円`

- 判断:

  - 低 breadth 日の執行機会や `POSITIVE WEEKS` は増えたが、`WEEKS >= +1%` は結局 `173/214` を超えず、zero-week 埋めを selector の順番だけで解くのは限界があると確認できたため不採用

- 再試行条件:

  - low-breadth を再試行するなら、selector 優先度ではなく `inverse_pullback` や `catchup` 側の品質改善が先に必要

  - 同じ形の breadth `< 0.35 / 0.30` `inverse` 優先は、そのままでは再試行しない

### 2026-05-08: Low-Breadth Catchup Probe

- 分析:

  - 残るゼロトレード週 `2022-W15`, `2023-W01`, `2024-W32`, `2024-W33`, `2024-W37`, `2025-W15` を selector で見ると、実質すべてが `catchup` 候補だけ出ているのに breadth gate で `dynamic_lev = 0` となり、週全体がノートレードになっていた

  - ただし broad な low-breadth catchup 解放は過去に崩れているため、今回は「top setup が `catchup_rs` で score が十分高い日だけ、小さな試し玉を入れる」形に絞った

- 試したこと:

  - breadth gate 下でも、top setup が `catchup_rs` かつ score `>= 14.0 / 16.0` の日に限り、`0.25x equity` の小さい probe buying power を付与

- 結果:

  - `FINAL EQUITY: 136.73M`

  - `CLOSED TRADES: 537`

  - `PROFIT FACTOR: 2.27`

  - `AVG MONTH ACTIVE RATE: 52.72%`

  - `MONTHS >= 3/4 ACTIVE: 3/50`

  - `WEEKS >= +1%: 173/214`

  - `POSITIVE WEEKS: 173/214`

  - `WORST DAY: -4,805,794円`

  - score `14.0` と `16.0` は同じ結果になった

- 判断:

  - 稼働率と `WORST DAY` は改善したが、`WEEKS >= +1%` は増えず、総リターンも大きく低下したため不採用

- 再試行条件:

  - low-breadth catchup を再試行するなら、raw score 以外の品質シグナルを追加して、ゼロ週を埋めても総リターンを崩さない根拠が増えた場合に限る

  - 同じ形の `0.25x equity` catchup probe は、そのままでは再試行しない

### 2026-05-08: Post-173 Primary Residual Cluster Checks

- 分析:

  - `173/214` 時点の残未達週を setup 別に分解すると、`primary` の大きな負け寄与は依然として残るが、多くの曜日帯は all-time ではまだ十分勝っていた

  - その中で all-time でもまとまって弱かったのは、火曜 `primary` の small-gap continuation だった

    - 火曜 `primary` の `gap 0.0-0.6%`: `36 trades / -6.73M`

    - 特に breadth `0.65+` で small gap の continuation が弱かった

  - ただし、同じ cluster 内でも breadth や trend を絞ると、総リターンや PF は上がる一方で `WEEKS >= +1%` は押し上がらないケースが多かった

- 試したこと:

  - 火曜 `primary` の `gap 0.0-0.6%` かつ breadth `>= 0.65` に equity cap `1.00 / 0.75 / 0.50`

  - 火曜 `primary` の small-gap で

    - breadth `0.55-0.65` かつ `open_vs_sma_atr 2-3`

    - breadth `0.45-0.55` かつ `open_vs_sma_atr 0-1`

    - breadth `>= 0.65` かつ `open_vs_sma_atr < 2`

    - breadth `>= 0.65` かつ `open_vs_sma_atr 1-2`

    の狭い cap 近傍

  - あわせて、月曜 `primary` の breadth `0.45-0.55` かつ `open_vs_sma_atr 1-2` に cap `1.00 / 0.75`

- 結果:

  - 火曜 small-gap breadth `>= 0.65` cap `1.00 / 0.75 / 0.50`:

    - `WEEKS >= +1%: 172 / 171 / 169`

    - `FINAL EQUITY: 131.64M / 115.63M / 107.37M`

    - `WORST DAY: -4.58M / -4.01M / -3.71M`

  - 火曜の狭い cap 近傍:

    - `breadth 0.55-0.65` + `open_vs_sma_atr 2-3` cap `0.50`:

      - `FINAL EQUITY: 182.44M`

      - `WEEKS >= +1%: 173/214`

      - `WORST DAY: -6.42M`

    - `breadth 0.45-0.55` + `open_vs_sma_atr 0-1` cap `0.50`:

      - `FINAL EQUITY: 187.12M`

      - `WEEKS >= +1%: 173/214`

      - `WORST DAY: -6.58M`

    - `breadth >= 0.65` + `open_vs_sma_atr < 2` cap `0.75`:

      - `FINAL EQUITY: 142.56M`

      - `WEEKS >= +1%: 171/214`

    - `breadth >= 0.65` + `open_vs_sma_atr 1-2` cap `0.75`:

      - `FINAL EQUITY: 142.50M`

      - `WEEKS >= +1%: 172/214`

  - 月曜 breadth `0.45-0.55` / `open_vs_sma_atr 1-2` cap `1.00 / 0.75`:

    - `FINAL EQUITY: 172.50M / 172.61M`

    - `WEEKS >= +1%: 172/214`

    - `WORST DAY: -6.07M`

- 判断:

  - 火曜 `primary` の broad small-gap defense は `WORST DAY` を軽くできても、`WEEKS >= +1%` と総リターンを削りすぎたため不採用

  - 狭い火曜 / 月曜 `primary` cap は総リターンや PF が伸びる近傍もあったが、最優先の `WEEKS >= +1%` は `173/214` のまま据え置きで、`WORST DAY` も悪化したため不採用

- 再試行条件:

  - 火曜 `primary` を再試行するなら、small-gap continuation という軸は維持しつつ、breadth / trend だけでは分け切れない追加シグナルが必要

  - 同じ形の火曜 small-gap broad cap や、月曜 breadth `0.45-0.55` / `open_vs_sma_atr 1-2` cap は、そのままでは再試行しない

### 2026-05-08: Post-173 Strong-Oversold Tuesday Gap Check

- 分析:

  - 火曜 `strong_oversold` の `gap -2.0% 〜 -1.0%` は `7 trades / -623k` で、`2025-W31` の `1579.T -525k` など残未達週にも寄与していた

- 試したこと:

  - 火曜 `strong_oversold` の `gap -2.0% 〜 -1.0%` を候補生成から除外

- 結果:

  - `FINAL EQUITY: 168.63M`

  - `CLOSED TRADES: 495`

  - `WEEKS >= +1%: 172/214`

  - `POSITIVE WEEKS: 173/214`

  - `WORST DAY: -5,931,584円`

- 判断:

  - all-time では弱い帯だったが、`WEEKS >= +1%` は `172/214` へ後退したため不採用

- 再試行条件:

  - `strong_oversold` を再試行するなら、単純な gap 除外ではなく、別 setup への置き換えまで含めた仮説が必要

  - 同じ形の火曜 `strong_oversold gap -2%〜-1%` 除外は、そのままでは再試行しない

### 2026-05-08: Tuesday Low-Breadth `catchup_rs` Probe

- 分析:

  - `173/214` 時点のゼロトレード週を掘り直すと、low-breadth 日の多くは `catchup` 候補自体は出ているのに、通常 breadth gate で daytrade leverage が `0` になって止まっていた

  - 以前の broad な low-breadth catchup probe は崩れたが、その検証は `breadth < 0.423` を見ていて、実際の shared gate `min(BREADTH_THRESHOLD, DAYTRADE_FALLBACK_BREADTH_THRESHOLD)` = `0.36` より広すぎた

  - 真の low-breadth 稼働帯 `0.18 <= breadth < 0.36` を top candidate ベースで再集計すると、火曜の moderate-score `catchup_rs` だけは close miss を埋める余地があり、月曜や金曜の hot-gap continuation より偏りが小さかった

- 変更:

  - shared helper `resolve_daytrade_selected_leverage` を追加し、通常 breadth gate では leverage `0` の日でも

    - 火曜

    - `0.18 <= breadth < 0.36`

    - top selected setup が `catchup_rs`

    - score `8.0 <= score < 12.0`

    - gap `<= +1.0%`

    のときだけ、`0.20x` の小さい base leverage を許可

  - この probe も通常の週次 catch-up leverage / breadth exposure scale / 利益ガードをそのまま通す

  - `backtest.py` にも `gap_pct` を渡し、live/backtest とも同じ shared helper を参照するよう統一

- 結果:

  - `FINAL EQUITY: 177.50M`

  - `CLOSED TRADES: 500`

  - `WIN RATE: 53.20%`

  - `TOTAL RETURN: +17649.50%`

  - `PROFIT FACTOR: 2.36`

  - `AVG MONTH ACTIVE RATE: 49.66%`

  - `MONTHS >= 3/4 ACTIVE: 2/50`

  - `WEEKS >= +1%: 174/214`

  - `POSITIVE WEEKS: 174/214`

  - `WORST DAY: -6,246,321円`

- 判断:

  - `173/214` から `174/214` へ改善し、総リターンと勝率も伸びたため採用

  - `WORST DAY` は `-6,052,637円` から悪化したが、broad な low-breadth catchup 解放ではなく「火曜の moderate-score relative-strength continuation を小さく試す」形に絞ることで、まだ本番で説明可能な範囲に収めた

  - 近傍では `0.25x` も同じ `174/214` が出たが、より攻めた base leverage になるため今回は採らず、`0.20x` を採用

- 再試行条件:

  - 同系統を再試行するなら、火曜以外へ広げる前に、live でも観測できる追加品質シグナルで説明を強めること

  - broad な low-breadth catchup 解放や、score 上限を外す形では再試行しない

### 2026-05-09: Tuesday Low-Breadth `catchup_rs` Selector Cooling

- 分析:

  - `174/214` ベースで残る close miss を見ると、ゼロトレード週の中でも `2024-W37` だけは

    - breadth `0.18-0.36`

    - 火曜

    - `catchup_rs` 候補あり

    - ただし top candidate が score `25.27` の too-hot continuation

    - その後ろに score `9.64`, gap `+0.28%` の moderate `catchup_rs`

    が並ぶ形だった

  - 以前の分析でも、low-breadth 火曜の `catchup_rs` は high score 帯より moderate score 帯の方が期待値が安定していたため、「probe を広げる」より「candidate quality を少し冷やす」方が shared selector の説明が通ると判断した

- 変更:

  - `select_daytrade_candidates` に、火曜 `0.18 <= breadth < 0.36` の `catchup` 選択時だけ、

    - top `catchup_rs` score `>= 12.0`

    - 別の `catchup_rs` に score `8.0-12.0`

    - gap `<= +1.0%`

    がある場合、その moderate candidate を先頭へ繰り上げる shared selector cooling を追加

  - 既存の low-breadth probe leverage helper はそのまま使い、`selector` だけを shared quality adjustment として追加

- 結果:

  - `FINAL EQUITY: 183.11M`

  - `CLOSED TRADES: 502`

  - `WIN RATE: 53.19%`

  - `TOTAL RETURN: +18210.81%`

  - `PROFIT FACTOR: 2.37`

  - `AVG MONTH ACTIVE RATE: 49.85%`

  - `MONTHS >= 3/4 ACTIVE: 2/50`

  - `WEEKS >= +1%: 175/214`

  - `POSITIVE WEEKS: 175/214`

  - `WORST DAY: -6,440,006円`

  - `2024-W37`: `+0.00%` -> `+3.07%`

  - 既存の `>= +1%` 週を落としたケースはなし

- 判断:

  - `174/214` から `175/214` へ改善し、総リターン、PF、稼働率も上がったため採用

  - `WORST DAY` は悪化したが、broad な low-breadth 解放ではなく「弱い地合いでの too-hot RS を moderate candidate に冷ます」という形に留めたことで、まだ live で説明しやすい shared selector adjustment と判断した

  - 近傍の `gap <= 0.8% / 1.2%`、top score threshold `12 / 14`、moderate upper score `12 / 14` はすべて同じ `175/214` で、`8-10` に狭めた場合だけ `174/214` に戻った

- 再試行条件:

  - 同系統を再試行するなら、火曜以外へ広げる前に、同じ「too-hot leader より moderate continuation が良い」構造が別 weekday にも出ること

  - `8-10` へ狭める、または gap を緩めるだけの同型近傍は、今回の結果を超えない限り再試行しない

### 2026-05-09: Post-175 Low-Breadth Weekday Probe Checks

- 分析:

  - `175/214` 時点の残ゼロ週を掘ると、火曜以外にも low-breadth `catchup_rs` の

    - too-hot top candidate

    - moderate `8-12` score の次点

    という構造は月水木金に少数あった

  - ただし、それらは current shared logic では probe leverage が開いていない weekday で、selector cooling だけでは約定自体が増えない

- 試したこと:

  - 水曜・木曜・金曜への selector cooling 拡張

  - 水曜・木曜 low-breadth `catchup_rs` に `0.20x / 0.25x / 0.30x` probe leverage 追加

  - extreme risk-off Friday だけ `inverse_pullback` filter を外す案

- 結果:

  - 水曜・木曜 probe 拡張は `CLOSED TRADES` が `+1` される近傍はあったが、`WEEKS >= +1%` は `175/214` のまま

  - `extreme risk-off Friday inverse_pullback` 例外:

    - `FINAL EQUITY: 178.27M`

    - `WEEKS >= +1%: 174/214`

    - `WORST DAY: -6.27M`

- 判断:

  - 火曜以外の low-breadth probe は close miss を埋め切れず、`175/214` を超えなかったため不採用

  - Friday `inverse_pullback` 例外は、ゼロ週の局所改善より既存の Friday countertrend defense を崩す影響が大きく不採用

- 再試行条件:

  - 火曜以外へ probe を広げるなら、weekday だけではなく別の品質シグナルが必要

  - 同じ形の Friday `inverse_pullback` 例外は、そのままでは再試行しない

### 2026-05-09: Panic Breadth Low-Turnover `inverse`

- 分析:

  - 残るゼロ週 `2024-W32` は breadth `0.04-0.16` の panic regime で、`catchup` は出ていなかった

  - 一方、`2024-08-05` を分解すると、`1368.T` の `inverse` setup 自体は成立していたが、前日 turnover `142M` が shared prefilter `300M` に届かず候補生成前に落ちていた

  - Friday `inverse_pullback` 例外は悪化したので、今回は「extreme risk-off の low-turnover inverse を小さく許す」方向へ切り替えた

- 変更:

  - breadth `< 0.10` の panic context では、`inverse` コードに限り候補生成の必要 turnover を `125M` まで許可

  - そのうえで、selected candidate が low-turnover `inverse` の panic trade だった場合は、inverse buying power leverage を `1.00` ではなく `0.60` に抑制

  - 実装は shared helper に分離し、live/backtest とも同じ候補生成・sizing 判定を参照

- 結果:

  - `FINAL EQUITY: 187.77M`

  - `CLOSED TRADES: 503`

  - `WIN RATE: 53.28%`

  - `TOTAL RETURN: +18676.72%`

  - `PROFIT FACTOR: 2.38`

  - `AVG MONTH ACTIVE RATE: 49.95%`

  - `MONTHS >= 3/4 ACTIVE: 2/50`

  - `WEEKS >= +1%: 176/214`

  - `POSITIVE WEEKS: 176/214`

  - `WORST DAY: -6,603,427円`

  - `2024-W32`: `+0.00%` -> `+2.39%`

  - 既存の `>= +1%` 週を落としたケースはなし

- 判断:

  - `175/214` から `176/214` へ純増し、PF と稼働率も改善したため採用

  - `WORST DAY` は悪化したが、broad な inverse 緩和ではなく

    - breadth `< 0.10`

    - inverse コードのみ

    - turnover `125M+`

    - buying power `0.60`

    に限定することで、panic day 専用の縮小執行として説明可能な範囲に収めた

  - 近傍では

    - breadth cutoff `0.08 / 0.09 / 0.10 / 0.12`

    - turnover threshold `100M / 125M`

    が同じ `176/214`

    - turnover `150M / 200M` は `175/214`

    - inverse panic buying power `0.60 / 0.65 / 0.75 / 0.80` が `176/214`

    - `0.50 / 0.55` は `175/214`

    だったため、最浅の `0.60` と安全側の `125M` を採用

- 再試行条件:

  - panic inverse を広げるなら、まず breadth `< 0.10` 以外でも同種の low-turnover inverse が再現していること

  - 同じ形でも buying power `0.50 / 0.55` や turnover `150M+` は今回の結果を超えない限り再試行しない

### 2026-05-06: Bull ETF Preferred Over Marginal Primary

- 変更:

  - 高 breadth 日に、`primary` 上位が弱く、bull ETF 候補が十分強い場合は ETF を優先

  - 実装は `core/logic.py` の selector に集約

- 採用理由:

  - `134/215` から `135/215` に改善

- 採用閾値:

  - breadth `>= 0.65`

  - `primary score <= 10.0`

  - `preferred_etf score > primary score + 1.0`

### 2026-05-06: Inverse Pullback

- 変更:

  - 弱地合いでインバース ETF の押し目継続を狙う `inverse_pullback` を追加

- 採用理由:

  - `WEEKS >= +1%` は据え置きでも、`POSITIVE WEEKS` と `WORST DAY` を少し改善

## Do Not Retry As-Is

### 0. 2026-05-06 continuation: no adopted improvement beyond `135/215`

- 追加で広く試したが、`135/215` を超える shared logic は未発見

- この探索ラウンドでは戦略コードは更新していない

- 主に次の仮説群を否定した

  - bull ETF 独立 pullback setup

  - `1306/1321` を新たな bull ETF 候補として使う案

  - `1356` の inverse continuation

  - `primary` の `open_from_prev_low_atr` を使った追加フィルタ

  - 月火限定の `primary` 防御フィルタ

  - ETF 置き換えの finer grid

- 再試行条件:

  - 既存 setup の延長ではなく、候補生成か exit ロジックに新しい情報を足せる場合のみ

### 0a. 2026-05-06 targeted Monday/Tuesday primary defenses around the new filter

- 試したこと:

  - 火曜 high breadth の `open_vs_sma_atr` 過熱フィルタ

  - 火曜 mid breadth の low-RS gap-up フィルタ

  - 月曜 hot `primary` の score penalty 化

  - 月曜 hot `primary` の閾値を少し狭めた近傍

- 結果:

  - 火曜系単独では `133/215` 前後まで悪化

  - 月曜の score penalty 化は `136/215` 止まり

  - 月曜の狭い近傍は `136/215` までは出るが、`137/215` には届かないか、改善が小さい

- 判断:

  - 今回の分析クラスターでは、月曜 hot continuation は hard filter が最も効いた

  - 火曜クラスターは今の情報量だと、単純な 1 条件追加では shared logic として弱い

### 0b. 2026-05-06 Tuesday selector / Thursday defense near-neighborhood

- 試したこと:

  - 火曜 high breadth での aggressive bull ETF replacement

  - 火曜 mid breadth の selector 緩和だけで解く案

  - 木曜 mid breadth の fallback replacement

- 結果:

  - 火曜 high breadth の ETF replacement は `135/215` まで悪化

  - 火曜 mid breadth の selector 緩和だけでは `137/215` のまま total return 改善止まり

  - 木曜 mid breadth の fallback replacement は実質差がほぼ出なかった

- 判断:

  - 火曜は entry filter を先に入れ、その上で軽い fallback 差し替えを重ねる形が最もバランスが良かった

### 0c. 2026-05-06 Thursday catchup replacement and Monday follow-up

- 試したこと:

  - 木曜 `breadth 0.5-0.6` で、strong catchup を `primary` より優先

  - 火曜 `breadth >= 0.70` で、strong catchup を `primary` より優先

  - 月曜 `breadth >= 0.70` の残クラスタ向け追加フィルタ近傍

- 結果:

  - catchup replacement は `PF` と `WORST DAY` は改善しうるが、`WEEKS >= +1%` を `134/215` 付近まで削る案が多かった

  - 月曜追加フィルタは、`138/215` を維持したまま総リターンは伸ばせても、`WORST DAY` をさらに悪化させる案が中心だった

- 判断:

  - 今回の優先順位では、木曜は selector ではなく entry filter、月曜追加は未採用が妥当

### 0d. 2026-05-07 follow-up defenses after `138/215`

- 試したこと:

  - 低 breadth かつ指数ギャップダウン日の `fallback/catchup` 停止

  - 火曜 mid breadth の高ギャップ `primary` 追加除外

  - 火曜 mid breadth かつ指数ギャップアップ日の高ギャップ `primary` 除外

  - 木曜 `primary` の RS 条件、`open_vs_sma_atr 0-1` 条件

  - 金曜弱 RS 条件の単独採用

  - profit guard を `0.75%/1.0%/OFF` にする案

- 結果:

  - 低 breadth 指数ギャップダウン防御はワースト日を抑える一方、`WEEKS >= +1%` が `127-129/215` まで悪化

  - 火曜追加防御は `137/215`、`TOTAL RETURN +3869.36%`、`WORST DAY -5,359,452円` まで悪化

  - 木曜 `prev_return >= 6.5%` 単独は `138/215` 維持、`PF 1.42`、`WORST DAY -3,292,773円` まで改善したが、総リターンが `+4262.50%` まで落ちた

  - 金曜弱 RS 単独は `TOTAL RETURN +5194.87%` まで伸びたが、`WORST DAY -4,602,460円` に悪化

  - 木曜 `open_vs_sma_atr 0-1` 追加は PF/ワースト日をさらに改善しうるが、採用案より総リターンを削る

  - profit guard 緩和または OFF は `137/215` に悪化

- 判断:

  - 採用案は、木曜前日大幅上昇防御と金曜弱 RS 防御の組み合わせ

  - 上記の未採用案は、単独または同じ閾値近傍では再試行しない

### 0e. 2026-05-07 fallback cap follow-up and weekly loss-stop checks

- 試したこと:

  - 週次損失が `-2%` から `-6%` に達したら週内停止する案

  - `fallback` の gap 上限を `1.0%` までさらに絞る案

  - `fallback 1.2%` と火曜 mid-breadth `primary` の追加防御を組み合わせる案

  - `fallback 1.2%` と火曜/木曜 `open_vs_sma_atr 0-1` 防御を組み合わせる案

- 結果:

  - 週次損失停止は `WEEKS >= +1%` が `135-137/215` へ悪化し、総リターンも大きく落ちた

  - `fallback max gap 1.0%` は `139/215`, `POSITIVE WEEKS 144/215`, `TOTAL RETURN +7390.68%`, `PF 1.50` だったが、`MONTHS >= 3/4 ACTIVE` が `1/50` まで落ち、deep-loss weeks も `1.2%` 案より悪かった

  - 火曜 mid-breadth 追加防御は `137-138/215` へ悪化、または `WORST DAY` を悪化させた

  - 火曜 `open_vs_sma_atr 0-1` 防御は `135/215` まで悪化した

  - 木曜 `open_vs_sma_atr 0-1` は `fallback 1.2%` と組み合わせた場合のみ採用案へ昇格

- 判断:

  - 週次損失停止、`fallback max gap 1.0%`、火曜追加防御は未採用

  - 再試行するなら、同じ閾値近傍ではなく、火曜 `primary` の損失率を別のリスク制御で抑える場合に限る

### 0f. 2026-05-07 ISO-week follow-up filters and risk stops

- 試したこと:

  - 火曜 mid-breadth の `primary` にだけ `stop_mult 0.45` を入れる案

  - 月曜 `primary` の `open_vs_sma_atr 1-4` / `2-4` / high-breadth 限定フィルタ

  - 火曜 `primary` の `open_vs_sma_atr 0-1` フィルタ

  - 火曜 `primary` の `open_vs_sma_atr >= 4` フィルタと、その narrow 条件

- 結果:

  - 火曜 risk stop は週次本数を増やさず、総リターン・PF・最大日次損失が悪化

  - 月曜フィルタは `WEEKS >= +1%` が `133-139/214` まで悪化

  - 火曜 `open_vs_sma_atr 0-1` は `142/214` まで悪化

  - 火曜 `open_vs_sma_atr >= 4` は `148/214` まで増えたが、`PF 1.47`、`WORST DAY -7,856,532円`、最大日次損失率 `-8.20%` まで悪化

  - 火曜 `open_vs_sma_atr >= 4` の narrow 条件は `145-146/214` へ悪化

- 判断:

  - 週次本数だけ伸びる火曜 `open_vs_sma_atr >= 4` は、PF と最大日次損失の悪化が大きいため不採用

  - 同じ月曜/火曜 `open_vs_sma_atr` フィルタ近傍は再試行しない

### 0g. 2026-05-07 low-breadth ETF and catchup follow-up

- 試したこと:

  - 低 breadth のノートレード週を、bull ETF / inverse ETF の専用エントリーで埋める仮説を検証

  - breadth `< 0.35` の bull ETF は、指数ギャップ上昇かつ ETF 寄りギャップ上昇では単体 open-close が良い例もあった

  - ただし、shared candidate flow に入れると、低 breadth の非 inverse 候補は資金レバレッジ `0` で止まりやすく、単純に catchup へ資金を出すと質が落ちた

- 結果:

  - `calculate_dynamic_leverage` を catchup 閾値 `0.18` まで下げる案:

    - `WEEKS >= +1%: 145/214`

    - `POSITIVE WEEKS: 149/214`

    - `PROFIT FACTOR: 1.41`

    - `AVG MONTH ACTIVE RATE: 54.14%`

    - `WORST DAY: -2,971,660円`

  - 低 breadth で inverse を優先する案:

    - breadth `< 0.36`: `146/214`, `POSITIVE WEEKS 153/214`, `PF 1.52`

    - breadth `< 0.25`: `147/214`, `POSITIVE WEEKS 153/214`, `PF 1.52`

  - 低 breadth で bull ETF の catchup 候補だけを通す案:

    - `146/214`, `POSITIVE WEEKS 153/214`, `PF 1.52`

- 判断:

  - 低 breadth ETF は個別週では魅力的な日があるが、現行の寄り情報だけでは `+1%` 週を安定して増やせなかった

  - 単に catchup の稼働域を広げる案は、稼働率が上がる一方で週次達成率と PF が悪化するため不採用

  - 再試行するなら、寄り時点の指数ギャップだけではなく、前日夜間・先物・セクター別 breadth など、低 breadth 反転の方向を判定できる新情報が必要

### 0h. 2026-05-07 weekly catchup neighborhood

- 試したこと:

  - early catchup 倍率 `20/30/40/80`

  - early catchup 終了曜日を月曜・火曜へ早める案

  - 通常 catchup 倍率 `21-30`

  - profit lock を `1.2%/1.5%` に緩める案と、lock 後も `0.25x` だけ残す案

- 結果:

  - early `40` は `148/214`、`PF 1.53` まで改善したが、`POSITIVE WEEKS` が `151/214` へ減り、`WORST DAY -6,057,614円` へ悪化

  - early `80`、early 終了曜日の前倒し、profit lock 緩和はいずれも `142-145/214` まで悪化

  - 通常 catchup `22/23/25/26/30` は `149/214` まで伸びるが、`22` が総リターン、PF、取引数、最大日次損失率のバランスで最も良かった

- 判断:

  - この時点の採用は `DAYTRADE_WEEKLY_CATCHUP_LEVERAGE_MULT = 22`

  - 後続の position sizing 検証で `catchup_gapdown` 上限を落としたうえで `26` へ更新

  - 近傍を再試行するなら、単純倍率ではなく、週後半の候補品質や日次損失率に応じて catchup exposure を調整する場合に限る

### 0i. 2026-05-07 post-22x loss concentration defenses

- 試したこと:

  - `22x` 採用後の最悪日を確認し、火曜 mid breadth の高ギャップ `primary` を追加で絞る案

  - 高 breadth の極端な `open_vs_sma_atr` を広く除外する案

  - `catchup_gapdown` の RS 過大評価を抑えるため、catchup score の RS bonus を `80-200` で cap する案

- 結果:

  - 火曜 mid breadth の `prev_return` 上限を `3.5-5.0%` へ広げる案は `147/214` へ悪化し、`prev_return <= 4.5%` 以上では `PF 1.48`、`WORST DAY -8,067,992円` まで悪化

  - 高 breadth `open_vs_sma_atr >= 5/6/7` 除外は `144-147/214` へ悪化し、総リターンも大きく落ちた

  - catchup score の RS cap は `80/100/150` で `144-147/214` へ悪化、`200` は `149/214` 維持でも `PF 1.49`、`WORST DAY -8,849,720円` へ悪化

- 判断:

  - `22x` 後の損失集中は、単純な追加フィルタやスコア cap では週次達成率とのトレードオフが悪い

  - 次に試すなら、個別フィルタではなく、週後半 catchup 中だけの position sizing / notional cap を、損失率ベースで検証する

### 0j. 2026-05-07 catchup sizing near-neighborhood

- 試したこと:

  - `primary` 全体の equity notional cap を `1.4-1.9` に下げる案

  - `catchup_gapdown` の equity notional cap を `0.68-0.95` に下げる案

  - `catchup_gapdown 0.70/0.72` と通常 catchup 倍率 `22-30` の組み合わせ

- 結果:

  - `primary` cap は worst day を抑える一方、`WEEKS >= +1%` が `142-146/214` へ悪化し、総リターンも大きく落ちた

  - `catchup_gapdown 0.70` 単独は `149/214` 維持、`POSITIVE WEEKS 154/214`、`PF 1.54`、`WORST DAY -5,883,451円`

  - `catchup_gapdown 0.70` + catchup `25/26/28/30` は `150/214` まで改善

  - `catchup_gapdown 0.72` 近傍は一部で `150/214` が出るが、総リターンまたは positive weeks が `0.70` 案より弱い

- 判断:

  - 採用は `catchup_gapdown equity cap 0.70` + `weekly catchup 26`

  - `primary` 全体の cap 下げ、`catchup_gapdown 0.68/0.74-0.95`、`0.72` 近傍は同じ形では再試行しない

### 0k. 2026-05-07 post-150 unmet-week filters

- 試したこと:

  - 火曜 `primary` の gap `<= 0.6%` / 前日上昇条件を使った追加防御

  - 火曜 `primary` の `open_vs_sma_atr >= 4.0` 単独フィルタ

  - 火曜 `primary` の `open_vs_sma_atr` 閾値 `3.5/4.5/5.0/5.5/6.0`

  - 月曜 `primary` の gap `0.6-1.2%`、低 RS、`open_vs_sma_atr 3-4` 近傍

  - 低 breadth flat gap `fallback` 防御と catchup 倍率 `24-29` の組み合わせ

- 結果:

  - 火曜 gap `<= 0.6%` / 前日上昇系フィルタは `WEEKS >= +1%` が `142-143/214` まで悪化

  - 月曜 `primary` 追加フィルタは `145-149/214` まで悪化し、未達週を埋めるより勝ち週を削った

  - 火曜 `open_vs_sma_atr >= 4.0` 単独は positive weeks を少し改善したが、`PF 1.48`、`WORST DAY -7,934,012円` で不採用

  - 低 breadth flat gap `fallback` 防御単独は `WEEKS >= +1% 150/214` 維持、`POSITIVE WEEKS 155/214`、`PF 1.59`、`WORST DAY -5,050,733円`

  - 低 breadth flat gap `fallback` 防御 + 火曜 `open_vs_sma_atr >= 4.0` + catchup `26` だけが `151/214` へ到達

- 判断:

  - 採用は低 breadth flat gap `fallback` 防御 + 火曜 `open_vs_sma_atr >= 4.0` + 現行 catchup `26`

  - 火曜 `open_vs_sma_atr` の単独案、月曜追加防御、火曜 gap `<= 0.6%` 系、同じ catchup 近傍はそのまま再試行しない

### 0l. 2026-05-07 post-151 loss-cluster and catchup checks

- 試したこと:

  - 火曜 `primary` の `open_vs_sma_atr 0-1`、breadth `0.6-0.7`、RS `25-50` 除外

  - 月曜 `primary` の gap `0.6-1.2%`、`open_vs_sma_atr 3-4` 除外

  - 火曜の浅い `catchup_gapdown` 除外

  - 月曜 `catchup_rs gap >= 2%` 除外

  - 火曜 `fallback` の preferred gap 除外

  - 月曜 `strong_oversold` のフラット/軽い下げ gap 除外

  - 木曜 `primary open_vs_sma_atr 3-4` と catchup `27-36` の組み合わせ

- 結果:

  - 火曜 `primary` の広い除外は `WEEKS >= +1%` が `146-148/214` へ悪化

  - 月曜 `primary` 追加除外は `149/214` または週次据え置きで、総リターンや worst day のトレードオフが悪い

  - 火曜浅い `catchup_gapdown` 除外は週次据え置きでも `WORST DAY -9,436,065円` へ悪化

  - 月曜 `catchup_rs gap >= 2%` と月曜 `strong_oversold` 除外は `152/214` まで伸びたが、worst day が `-7.3M` から `-7.4M` に悪化

  - 木曜 `primary open_vs_sma_atr 3-4` 単独は `152/214`, `POSITIVE WEEKS 157/214`, `PF 1.65`, `WORST DAY -5,769,156円`

  - 木曜 `primary open_vs_sma_atr 3-4` + catchup `30` は `154/214`, `POSITIVE WEEKS 156/214`, `PF 1.64`, `WORST DAY -5,448,043円`

  - 同じ木曜防御で catchup `29/31/32/33/34` は `152-153/214`、`36` は `154/214` だが総リターンと PF が `30` より弱い

- 判断:

  - 採用は木曜 `primary open_vs_sma_atr 3-4` 防御 + catchup `30`

  - 火曜/月曜の広い追加フィルタ、火曜浅い `catchup_gapdown`、月曜 `catchup_rs/strong_oversold` 除外、catchup `29/31/32/33/34/36` は同じ形では再試行しない

### 0m. 2026-05-07 post-154 Wednesday and remaining loss-cluster checks

- 試したこと:

  - 水曜 `primary` の gap `0.6-1.2%`

  - 水曜 `primary` の `open_vs_sma_atr >= 4.0`

  - 水曜 `primary` の RS `10-50`

  - 金曜 `catchup_rs` 全除外と gap `1.2-2.0%` 除外

  - 月曜/火曜 `catchup_gapdown` 除外

  - 火曜 `fallback` 除外

  - 水曜採用案と catchup `24/26/28/29/31/32/34/36`

  - 水曜採用案に、火曜 mid breadth / 高gap / 前日上昇 / 浅trend 近傍の狭い追加フィルタを重ねる案

- 結果:

  - 水曜 gap `0.6-1.2%` 単独は `155/214`, `PF 1.69`, `POSITIVE WEEKS 157/214`

  - 水曜 `open_vs_sma_atr >= 4.0` 単独は `155/214`, `PF 1.70`, `POSITIVE WEEKS 157/214`

  - 水曜両方の採用案は `156/214`, `PF 1.74`, `POSITIVE WEEKS 158/214`

  - 水曜採用案 + catchup `26/28/31/32/34` は `155/214`、`24/29` は `153-154/214`、`36` は `156/214` でも `PF` と総リターンが現行 `30` より弱い

  - 金曜 `catchup_rs` 除外は `149/214` へ悪化

  - 月曜 `catchup_gapdown` 除外は `153/214`、火曜 `catchup_gapdown` 除外は `154/214` で、期待した週次改善は出なかった

  - 火曜 `fallback` 除外は `142/214` へ悪化

  - 水曜採用案 + 火曜高gap/浅trendの狭い追加フィルタは、代替候補に流れて `154/214` へ悪化し、worst day も `-9,335,820円` へ悪化

- 判断:

  - 採用は水曜 gap `0.6-1.2%` + 水曜 `open_vs_sma_atr >= 4.0`

  - 金曜 `catchup_rs`、月火 `catchup_gapdown`、火曜 `fallback`、水曜採用案の catchup 近傍、火曜高gap/浅trend狭域フィルタは同じ形では再試行しない

### 0n. 2026-05-07 post-157 remaining checks before pause

- 試したこと:

  - `inverse` / `inverse_pullback` の equity cap `0.68/0.70/0.71/0.72/0.75/0.80/0.90/1.00`

  - 水曜 `primary` の gap `0.3-0.6%` 除外

  - 木曜・金曜・火曜の gap `0.3-0.6%` 近傍除外

  - 水曜 gap `0.3-0.6%` と `catchup_gapdown` equity cap `0.45-0.80` の組み合わせ

  - 水曜 gap `0.3-0.6%` と `inverse` cap `0.50/0.60/0.80/1.00` の組み合わせ

- 結果:

  - `inverse` cap 近傍は `0.70` 付近で `157/214` が上限。あと約 `610円` だけ足りない `2022-W13` は埋まらなかった

  - 水曜 gap `0.3-0.6%` 除外は `158/214`, `POSITIVE WEEKS 160/214`, `TOTAL RETURN +12716.08%` まで伸びたが、`WORST DAY -8,743,906円` へ悪化

  - 水曜 gap `0.3-0.6%` + `catchup_gapdown` cap `0.80` は `158/214` を維持したが、`PF 1.76`, `WORST DAY -7,985,544円` で現行より下振れが重い

  - `catchup_gapdown` cap `0.45-0.65` や `inverse` cap 変更との組み合わせは `155-157/214` に戻り、158 週は維持できなかった

  - 火曜 gap `0.0-0.3%` / `0.3-0.6%` 除外は `154-155/214` へ悪化

- 判断:

  - 水曜 gap `0.3-0.6%` は次回の有力候補だが、現時点では worst day 悪化が大きいため未採用

  - 次回再試行するなら、水曜小ギャップ除外を単独採用せず、最大日次損失率または `catchup_gapdown` の地合い別サイズ制御で下振れを抑える根拠を先に作る

### 1. 既存ロジックの細かいパラメータ調整だけ

- 対象:

  - 週次 catchup 倍率

  - 利益ガード開始日

  - base leverage

  - `MAX_POSITIONS`

  - 各 setup の stop/target/notional 微調整

- 傾向:

  - 改善しても局所的で、週次本数の壁をほぼ破れなかった

  - ロジック追加なしでは `123/215` から `134/215` 付近で伸びが鈍化した

- 再試行条件:

  - 別系統 setup を追加した後に、その setup 専用の最終調整として行う場合のみ

### 2. `strong_oversold` を外す、または弱くする

- 結果例:

  - 無効化で `124/215`

- 判断:

  - 週次本数が悪化

- 再試行条件:

  - `strong_oversold` の役割を代替する別の bull ETF setup を入れる場合のみ

### 3. `catchup_gapdown` を外す、または大きく弱める

- 結果例:

  - 無効化で `118/215`

- 判断:

  - 悪化が大きい

- 再試行条件:

  - `catchup` を丸ごと別ロジックへ置き換える場合のみ

### 4. `inverse` の発動条件を単純に広げるだけ

- 対象:

  - breadth 上限緩和

  - market trend 条件緩和

  - index gap 条件緩和

- 傾向:

  - 週次本数はほぼ増えない

  - 置き換え先としても決定打にならなかった

- 再試行条件:

  - 単なる条件緩和ではなく、新しい `inverse` 系 setup を追加する場合のみ

### 5. `inverse` / `inverse_pullback` を selector で強く優先

- 試したこと:

  - no-primary 日の優先

  - weak primary の差し替え

  - broader replace 条件

- 結果:

  - おおむね `129/215` から `130/215`

- 判断:

  - 現行 selector より悪い

- 再試行条件:

  - `inverse` 側のスコアリングか exit ロジックを別に改善した場合のみ

### 6. 高 breadth 日の `primary` を追加フィルタで広く削る

- 代表例:

  - `open_vs_sma_atr >= 4.0` を高 breadth で除外:

    - `133/215`, `TOTAL RETURN +2409.57%`, `WORST DAY -3,756,730円`

  - `gap >= 2% and open_vs_sma_atr >= 1.5` を高 breadth で除外:

    - `129/215`, `WORST DAY -1,246,421円`

  - `open_vs_sma_atr >= 3.0 and RS < 70` を高 breadth で除外:

    - `132/215`, `WORST DAY -1,937,113円`

- 判断:

  - リスク改善だけの案はあるが、週次本数を削りやすい

- 再試行条件:

  - 目標を「週次本数」より「最大日次損失」へ明確に寄せる場合のみ

### 7. Aggressive Bull ETF Replacement

- 対象:

  - 現在採用中より強い ETF 優先

- 代表例:

  - breadth `>= 0.65`, `primary <= 10.0`, `etf_advantage > 0.5`

  - 結果:

    - `135/215`

    - `POSITIVE WEEKS: 138/215`

    - `TOTAL RETURN: +1658.18%`

    - `WORST DAY: -2,483,316円`

- 判断:

  - 週次本数は維持するが、現行採用値よりワースト日が悪い

- 再試行条件:

  - ワースト日を別ロジックで抑える案とセットで試す場合のみ

### 7a. Bull ETF Replacement Finer Grid

- 試したこと:

  - breadth `0.55/0.60/0.65`

  - `primary score <= 5/6/7/8`

  - `etf_advantage >= 1.5/2.0/3.0`

- 結果:

  - `135/215` を超える点は出なかった

  - `b60_p6` 近傍は総リターンを少し伸ばせるが、ワースト日は現行より悪化

- 判断:

  - 現行採用値より明確に優れた点はなし

### 8. `catchup` 混在日の selector 変更

- 代表例:

  - `catchup_rs_only_mixed`

  - 結果:

    - `132/215`

    - `TOTAL RETURN: +858.23%`

    - `WORST DAY: -1,417,903円`

- 判断:

  - リスクは改善するが、週次本数と総リターンを削りすぎ

- 再試行条件:

  - `catchup` を週次本数よりも防御優先へ明確に寄せる場合のみ

### 9. 曜日限定の ETF 優先

- 試したこと:

  - 月火まで

  - 水曜まで

  - 木金のみ

- 結果:

  - 現行採用ロジックと実質同じ結果で差が出なかった

- 判断:

  - 今の selector 近傍では曜日条件は不要

### 9a. 週前半限定の `primary` 防御フィルタ

- 試したこと:

  - 月火だけ `open_from_prev_low_atr` 過熱を切る

  - 月火だけ gap 過熱を切る

  - 月火だけ高 RSI + `open_from_prev_low_atr` を切る

- 結果:

  - 実バックテストでは有意な変化なし

- 判断:

  - 週前半の損失は重いが、単純な 1 条件フィルタでは top candidate の置き換えに負けて効かなかった

### 9b. `open_from_prev_low_atr` ベースの追加フィルタ

- 試したこと:

  - high breadth / high `open_from_prev_low_atr`

  - high breadth / low RS / high `open_from_prev_low_atr`

  - high breadth / high prev return / high `open_from_prev_low_atr`

- 結果例:

  - `openlow_ge10_b65_rs60`:

    - `134/215`

    - `TOTAL RETURN: +1609.35%`

    - `WORST DAY: -2,630,993円`

  - `openlow_ge095_b60_rs50`:

    - `132/215`

    - `WORST DAY: -1,467,284円`

- 判断:

  - 防御寄りの案はあるが、週次本数を削りやすい

### 10. 高 breadth / 高 gap / 熱い `primary` のままリターンを伸ばす案

- 代表例:

  - 高 breadth の熱い `primary` を切りつつ ETF 置き換えを攻めた案

  - 例:

    - `134/215`

    - `TOTAL RETURN: +1991.55%`

    - `PROFIT FACTOR: 1.22`

    - `WORST DAY: -2,953,303円`

- 判断:

  - 総リターンは魅力的でも、最大日次損失が大きすぎて不採用

### 11. `1306/1321` を bull ETF 候補に戻す案

- 試したこと:

  - `1306/1321` を通常候補へ復帰

  - `1306` を primary のみで使う案

- 結果:

  - `1306/1321` を常時戻すと `131/215`, `+1083.46%`

  - `1306 primary only` は現行と実質同じで改善なし

- 判断:

  - `1306/1321` は現状の候補条件だと質が足りない

### 12. Bull ETF Dedicated Pullback

- 仮説:

  - `1579` などを、強地合いでの軽い押し目専用 setup として追加

- 試したこと:

  - breadth `>= 0.60/0.65/0.70`

  - gap `-2%` 前後まで許容

  - prev return / RSI / trend ratio 条件を複数組み合わせ

- 結果:

  - `135/215` を超えず

  - 一部は `WORST DAY` を少し改善したが、総リターンか PF が落ちた

- 判断:

  - 強い週には効きうるが、未達週を埋める力が弱い

### 13. `1579` 専用の `primary` / `catchup` 調整

- 試したこと:

  - `1579 primary` を特定 breadth 帯だけ許可

  - `1579 catchup_gapdown` を落とす

- 結果:

  - 実バックテストではほぼ変化なし

- 判断:

  - 個別 ETF 単位の単純制限だけでは、上位候補の入れ替わりで吸収されやすい

### 14. `1356` Inverse Continuation

- 仮説:

  - breadth `<= 0.45-0.50` の中弱気合いで、`1356` の小幅ギャップアップ継続を取る

- 試したこと:

  - `gap 0-3%`

  - `prev_return 0-5%`

  - `market_ratio <= 0.99-1.0`

- 結果:

  - 実バックテストでは現行と差が出なかった

- 判断:

  - 単体期待値は見えるが、shared candidate flow に混ぜても週次改善へ繋がらなかった

### 15. High-Return Low-Breadth `catchup_rs` / Extended `fallback` Cap

- 分析:

  - 失敗週を分解すると、初期の close miss は `catchup_rs` / `inverse`、後半の close miss は `fallback` の単発負けが原因だった

  - `catchup_rs` の `prev_return >= 0.08` は全件で 3 本だけで、そのうち `breadth < 0.55` の 2 本が大きな負け、`breadth 0.60` 以上の 1 本は勝ちだった

  - `fallback` でも `breadth >= 0.55` かつ `prev_return >= 0.04` かつ `open_vs_sma_atr >= 3.0` の 1 本が close miss を作っていた

- 変更:

  - `catchup_rs` に `breadth < 0.55` かつ `prev_return >= 0.08` のときだけ `equity notional` を `0.25` に落とす cap を追加

  - `fallback` に `breadth >= 0.55` かつ `prev_return >= 0.04` かつ `open_vs_sma_atr >= 3.0` のときだけ `equity notional` を `0.30` に落とす cap を追加

- 結果:

  - `FINAL EQUITY: Y274,803,621`

  - `TOTAL RETURN: +27380.36%`

  - `CLOSED TRADES: 494`

  - `WIN RATE: 53.64%`

  - `PROFIT FACTOR: 2.55`

  - `WEEKS >= +1%: 177/214`

  - `POSITIVE WEEKS: 177/214`

  - `AVG MONTH ACTIVE RATE: 49.07%`

  - `MONTHS >= 3/4 ACTIVE: 2/50`

  - `WORST DAY: -9,666,061円`

- 判断:

  - 採用

- 再試行するとしたら:

  - `catchup_rs` は `breadth 0.55` 近傍だけを再調整し、`prev_return` 単独ではなく breadth との組み合わせで見る

  - `fallback` は `open_vs_sma_atr` の境界を触る前に、まず high breadth / hot prev_return の一致を再確認する

### 16. Wed-Fri Low-Breadth `catchup_gapdown` Probe

- 分析:

  - `178/214` まで残った close miss を掘ると、低 breadth 週の中でも `catchup_gapdown` が出る水木金だけは、`score 6-8` の小さな probe 余地があった

  - Monday / Tuesday へ広げた同型の gapdown probe は週次本数を悪化させたが、水木金に限定すると `2023-W01` を押し上げつつ、他週への悪影響を抑えられた

- 変更:

  - `resolve_daytrade_selected_leverage` に、水木金の low breadth / moderate-score `catchup_gapdown` probe を追加

  - 条件は `breadth 0.18-0.36`、weekday `Wed-Fri`、`score 6.0-8.0`、`gap <= -1.0%`、leverage `0.35`

- 結果:

  - `FINAL EQUITY: Y278,949,456`

  - `TOTAL RETURN: +27794.95%`

  - `CLOSED TRADES: 496`

  - `WIN RATE: 53.83%`

  - `PROFIT FACTOR: 2.55`

  - `WEEKS >= +1%: 178/214`

  - `POSITIVE WEEKS: 178/214`

  - `AVG MONTH ACTIVE RATE: 49.27%`

  - `MONTHS >= 3/4 ACTIVE: 2/50`

  - `WORST DAY: -9,817,377円`

- 判断:

  - 採用

- 再試行するとしたら:

  - `catchup_gapdown` を Monday / Tuesday に広げず、まずは同じ `score 6-8` 帯で weekday と gap の境界だけを微調整する

  - これ以上の改善は、別 setup の追加か exit 側の再設計が必要

### 17. 2026-05-13 Bull ETF Rebound / Primary Low-Score Cap Recheck

- 分析:

  - 低 breadth のノートレード週を `bull_etf_rebound` で埋める仮説を再検証した

  - さらに、未達週の primary 損失が低スコア帯に偏るかを見て、`score < 5.0` の primary を薄くする案も試した

- 変更:

  - low-breadth `bull_etf_rebound` の候補生成と selector 優先

  - primary の低スコア時 `equity notional` を `0.70` に落とす cap

- 結果:

  - `bull_etf_rebound` あり:

    - `FINAL EQUITY: Y264,940,284`

    - `WEEKS >= +1%: 178/214`

    - `WORST DAY: -9,321,061円`

  - `score < 5.0 -> 0.70` cap 追加:

    - `FINAL EQUITY: Y214,524,800`

    - `WEEKS >= +1%: 172/214`

    - `WORST DAY: -7,493,165円`

  - いずれも `+1%` 週の改善につながらず、後者は明確に悪化したため、最終的にはどちらも採用しなかった

- 判断:

  - 不採用

- 再試行するとしたら:

  - 同じ `bull_etf_rebound` / primary low-score cap の近傍は再試行しない

  - 次にやるなら、primary の負けを「日次損失率ベースのサイズ制御」か、別の setup 置換で扱う必要がある

## Notes For Future Sessions

- まず `135/215` を下回る微調整は再試行しないこと

- 次の有望方向は、`primary` を広く削ることではなく、日次損失率ベースのサイズ制御か別 setup 置換で負け週を扱うこと

- 再試行するなら、前回との差分をこのファイルに先に書いてから始めること

## 18. 2026-05-13 Primary High-Stretch / Candidate-Crowding Recheck

- 分析:

  - 直近の未達週を再分解すると、負け日の多くは `primary` の単発トレードで、他 setup は同日存在しても `primary` より実績が良いとは限らなかった

  - ただし、負け日の一部では `catchup` や `strong_oversold` のスコアが `primary` を大きく上回っており、見た目だけなら置換余地があるように見えた

  - そこで `primary` の高 stretch 低/中 prev_return フィルタ、`score` の prev_return 上限制、`catchup` / `strong_oversold` への置換、候補数ベースの日次レバレッジ調整を順に検証した

- 結果:

  - `primary` の高 stretch / breadth フィルタは、負け日を削るより良い日まで削ってしまい、`WEEKS >= +1%` を悪化させた

  - `catchup` / `strong_oversold` への置換も、スコア上は優勢でも実損益では安定せず、総リターンと週次達成率を悪化させた

  - 候補数ベースの日次レバレッジ調整は、総損益の微改善に見える場面はあったが、週次 +1% の本数を増やせなかったため不採用

- 採用:

  - 不採用

- 再試行するとしたら:

  - 同じ「primary を score/替え候補だけで置換する」近傍は再試行しない

  - 次にやるなら、日次損失率ベースの shared risk control か、別 setup の定義そのものを変える必要がある

## 19. 2026-05-13 High Market-Ratio Crowding Lead Swap

- 変更:

  - `market_ratio >= 1.10` かつ `selected_count >= 20` かつ `catchup score` が `primary score` を `1.0-2.0` 上回るときだけ、`primary` の先頭1件を `catchup` の先頭1件へ差し替える shared rule を追加

  - `backtest.py` と `core/logic.py` の shared selector 参照に `market_ratio` を通すように更新

- 結果:

  - `jp_backtest.py`:

    - `FINAL EQUITY: Y290,877,143`

    - `WEEKS >= +1%: 179/214`

    - `POSITIVE WEEKS: 179/214`

    - `PROFIT FACTOR: 2.58`

    - `WORST DAY: -10,235,009円`

  - 週次 `+1%` は `178/214 -> 179/214` に改善し、`PF` も維持できた

- 判断:

  - 採用

- 再試行するとしたら:

  - 同じ `market_ratio >= 1.10` / `selected_count >= 20` / `1-2pt` の `primary -> catchup` lead swap の近傍は再試行しない

  - 再探索するなら、同じ crowding でも別の proxy を使うか、別 setup family に切り替える必要がある

## 20. 2026-05-13 Family-Gap Replacement / Cap and Multi-Position What-If

- 分析:

  - 残った未達週は、`primary` の大きな単発損失が中心だったが、`strong_oversold` や `catchup` のスコア優位は実損益にそのまま繋がらない日も多かった

  - `max_pos=2/3` の multi-position 化は、稼働率は上がっても weekly hit と PF を大きく悪化させた

  - そのため、単純な family 置換ではなく、shared risk control としての置換・cap のみを試した

- 変更:

  - `primary` を `strong_oversold` / `catchup_*` に差し替える family-gap replacement

  - 同条件で `primary` の `equity notional` を落とす family-gap cap

  - `max_pos=2/3` の what-if

- 結果:

  - `max_pos=2`:

    - `FINAL EQUITY: Y34,550,827`

    - `WEEKS >= +1%: 150/214`

    - `PROFIT FACTOR: 1.36`

    - `WORST DAY: -1,211,069円`

  - `max_pos=3`:

    - `FINAL EQUITY: Y11,481,269`

    - `WEEKS >= +1%: 144/214`

    - `PROFIT FACTOR: 1.16`

    - `WORST DAY: -693,518円`

  - family-gap replacement:

    - `FINAL EQUITY: Y7,906,980`

    - `WEEKS >= +1%: 148/214`

    - `PROFIT FACTOR: 1.20`

    - `WORST DAY: -568,715円`

  - family-gap cap:

    - `FINAL EQUITY: Y116,558,739`

    - `WEEKS >= +1%: 161/214`

    - `PROFIT FACTOR: 2.25`

    - `WORST DAY: -4,198,549円`

  - いずれも baseline の `179/214` を上回れず、不採用

- 判断:

  - 不採用

- 再試行するとしたら:

  - raw な family-gap replacement / cap / `max_pos>1` は再試行しない

  - 再探索するなら、family スコアの共通較正か、別の shared risk layer を先に導入する必要がある

## 21. 2026-05-13 Fallback Weak-Score Cap / Hot Catchup Recheck

- 分析:

  - 週次の負けを再分解すると、`2024-W43` が `-0.10%` で最も `+1%` 近辺にあり、他の深い負け週は `fallback` と `strong_oversold` / `catchup` が混在していた

  - `2025-W15` のような純粋な BEAR / ノートレード週は、無理に埋めても改善しにくかった

  - Friday の low-breadth `catchup_rs` 解放案も試したが、全体では悪化したため採用しなかった

- 変更:

  - low breadth の weak-score `fallback` に `0.30/0.50` cap を追加

  - 以前の hot low-breadth `catchup_gapdown` cap は不採用に戻して削除

  - shared selector の turnover 参照バグを修正

- 結果:

  - `FINAL EQUITY: Y319,729,283`

  - `CLOSED TRADES: 500`

  - `WIN RATE: 54.00%`

  - `PROFIT FACTOR: 2.71`

  - `AVG MONTH ACTIVE RATE: 49.66%`

  - `MONTHS >= 3/4 ACTIVE: 1/50`

  - `WEEKS >= +1%: 179/214`

  - `WORST DAY: -11,251,852円`

- 採用:

  - `fallback` の weak-score cap は採用

  - hot low-breadth `catchup_gapdown` cap と Friday low-breadth `catchup_rs` 拡張は不採用

- 再試行するとしたら:

  - 同じ low-breadth `catchup_rs` / hot `catchup_gapdown` の近傍は再試行しない

  - 次にやるなら、別の shared risk layer か、`2024-W43` を狙うにしても weekday 固定ではない別の説明可能条件が必要

## 22. 2026-05-13 Fallback Structural-Room Recalibration

- 分析:

  - `fallback` の負け週では、`prev_return` と `RS` が高いだけで score が上がりすぎ、実損益では逆に弱い候補を上位に置く日があった

  - 例として `2024-11-25` は、`open_vs_sma_atr` や `prev_low` から見て余裕のある候補よりも、圧縮気味の候補がトップ score になっていた

  - `2024-11-28` のような勝ち日では、ある程度の structural room を持つ fallback が素直に選ばれていた

- 変更:

  - `score_daytrade_fallback_open_setup` に、`open_vs_sma_atr` の moderate room bonus と `open_from_prev_low_atr` の centrality penalty を追加

  - 既存の `prev_return` / `RS` 主導の rank は維持しつつ、圧縮しすぎた fallback を少し下げるように再較正

- 結果:

  - `FINAL EQUITY: Y345,402,229`

  - `CLOSED TRADES: 500`

  - `WIN RATE: 54.20%`

  - `PROFIT FACTOR: 2.74`

  - `AVG MONTH ACTIVE RATE: 49.66%`

  - `MONTHS >= 3/4 ACTIVE: 1/50`

  - `WEEKS >= +1%: 179/214`

  - `WORST DAY: -12,153,695円`

- 採用:

  - 採用

- 再試行するとしたら:

  - 同じ `open_vs_sma_atr` / `open_from_prev_low_atr` の係数近傍は再試行しない

  - 次にやるなら、`catchup_rs` の market-regime 依存か、週次の shared risk layer を別途整理する

## 23. 2026-05-13 Remaining Loss-Week Decomposition

- 分析:

  - `jp_backtest.py` の再集計で、`WEEKS >= +1%` は `179/214`、負け週は `33` 週だった

  - `+1%` 近辺の惜しい週は `6` 週しかなく、残りの未達週は深いマイナス週が中心だった

  - 週ごとの trade 数を見ると、勝ち週は平均 `2.02` trade、負け週は平均 `4.06` trade で、trade 数が多い週ほど崩れやすかった

  - ただし `trade_count = 5` の週には、`2025-W49` や `2026-W08` のように Friday の大きな戻りで `+1%` を超える週もあり、単純な週次 trade cap は勝ち週も壊しやすい

  - 深い負け週は breadth `0.19-0.76`、market_ratio `0.92-1.11` に広く散っており、単一の地合い閾値では説明しきれなかった

- 変更:

  - 追加のロジック変更は採用しない

  - 週次 trade cap の仮説は、説明可能性はあるが positive 週の Friday 回復を壊しやすく、現時点では shared strategy には入れない

- 追試:

  - primary を `score < 8` かつ `market_ratio >= 1.05` で薄くする案、`score 5-8` の `market_ratio 1.05-1.10` 帯を薄くする案、`score 8-10` の同帯を薄くする案を what-if で試した

  - いずれも `PF` は少し改善する近傍があったが、`WEEKS >= +1%` は `178-180/214` から `176-178/214` に悪化したため不採用

  - `inverse` / `inverse_pullback` の low-breadth 拡張も、週次 `+1%` の本数は増やせなかった

- 結果:

  - ロジック未変更

  - 追加の新規採用案なし

- 採用:

  - 不採用

- 再試行するとしたら:

  - 週次 trade cap を試すなら、固定本数ではなく「週後半の回復余地を残す条件付き cap」に限る

  - その場合でも、positive 週の Friday 回復を壊さないことを先に検証する必要がある

## 24. 2026-05-13 Hot Continuation Notional Rebalance

- 分析:

  - 残っている負け週のうち、`primary` の損失は hot continuation 帯にまだ寄っていた

  - 対象は `breadth >= 0.70`、`gap >= 1.5%`、`open_vs_sma_atr <= 1.5`、`prev_return >= 5%`、`RSI2 >= 60` の continuation 形で、選定そのものよりサイズのほうが効くと見た

  - `0.50` / `0.60` の近傍も検証したが、`0.50` は総リターンが少し伸びる一方で `WORST DAY` が悪化したため、`0.60` を採用した

- 変更:

  - `DAYTRADE_PRIMARY_HOT_CONTINUATION_EQUITY_NOTIONAL_PCT` を `0.75` から `0.60` に変更

  - 共有 helper `resolve_daytrade_primary_equity_notional_pct` 経由で、本番とバックテストの両方に同じサイズ制御を適用

- 結果:

  - `FINAL EQUITY: Y351,323,164`

  - `TOTAL RETURN: +35032.32%`

  - `CLOSED TRADES: 500`

  - `WIN RATE: 54.20%`

  - `PROFIT FACTOR: 2.76`

  - `AVG MONTH ACTIVE RATE: 49.66%`

  - `MONTHS >= 3/4 ACTIVE: 1/50`

  - `WEEKS >= +1%: 179/214`

  - `WORST DAY: -12,359,485円`

- 採用:

  - 採用

- 再試行するとしたら:

  - 同じ hot continuation notional の近傍値を詰めるより、別の shared risk layer を先に試す

  - `WEEKS >= +1%` はこの変更では増えていないため、次は size 調整ではなく regime-aware な制御を検討する

## 25. 2026-05-14 Stable Strategy Selection / Bull ETF Rejection

- 分析:

  - `bull_etf_rebound` は `2024-W33` と `2025-W15` の空振り週で候補は出たが、`2025-W15` を `+1%` 超へ押し上げるには至らなかった

  - `lev 2-4` / `notional 0.4-0.6` まで強めても、`2024-W33` は超えられても `2025-W15` は `0.7%` 前後で止まり、週次達成率の改善は見えなかった

  - 2025-W30 の Friday `primary` には narrow な損失帯があったが、そこだけを削る発想では全体の weekly hit を押し上げる根拠として弱かった

  - したがって、今後の実運用で最も安定的に使うべきなのは、現在の shared baseline

    - primary の曜日別フィルタと sizing

    - fallback の structural-room 再較正

    - catchup / inverse の shared risk control

    - hot continuation の控えめなサイズ調整

    - ISO 週次の profit guard

- 結果:

  - code change なし

  - current baseline を維持

  - 最新確認値は `WEEKS >= +1%: 179/214`, `PROFIT FACTOR: 2.76`, `WORST DAY: -12,359,485円`

- 採用:

  - current baseline を採用

- 再試行するとしたら:

  - bull ETF や Friday の狭帯 cap の近傍ではなく、別の shared setup か exit 設計そのものを作り直すときだけ再探索する

## 26. 2026-05-14 Primary Low-RS / Stretched-Stall Sizing

- 分析:

  - `179/214` の未達 35 週を再分解すると、33 週が負け週、2 週がノートレード週だった

  - `WEEKS >= +1%` と `POSITIVE WEEKS` が同数のため、惜しい正の未達週を押し上げる局面ではなく、深い負け週と損失集中を抑える局面と判断した

  - 未達週の主犯は引き続き `primary` で、未達週では 73 件で `-31.2M` 相当の損失

  - 全期間でも `primary` の `RS_Alpha 0-10` と `open_vs_sma_atr 4.0-5.0` が負けやすく、候補除外ではなく sizing cap で損失集中を抑える仮説を立てた

- 変更:

  - 低 RS `primary` (`RS_Alpha < 10`) の equity notional 上限を `1.00` に追加

  - `primary` の `open_vs_sma_atr 4.0-5.0` を、伸び切り失速帯として equity notional 上限 `1.00` に追加

  - `backtest.py` と shared selector 側の `resolve_daytrade_primary_equity_notional_pct` に `rs_alpha` を渡すように更新

- 結果:

  - `FINAL EQUITY: Y351,323,164` -> `Y406,715,440`

  - `TOTAL RETURN: +35032.32%` -> `+40571.54%`

  - `CLOSED TRADES: 500` -> `504`

  - `WIN RATE: 54.20%` -> `54.17%`

  - `PROFIT FACTOR: 2.76` -> `2.94`

  - `AVG MONTH ACTIVE RATE: 49.66%` -> `50.04%`

  - `MONTHS >= 3/4 ACTIVE: 1/50` -> `1/50`

  - `WEEKS >= +1%: 179/214` -> `179/214`

  - `POSITIVE WEEKS: 179/214` -> `179/214`

  - `WORST DAY: -12,359,485円` -> `-8,695,227円`

- 採用:

  - 採用

- 不採用:

  - 低 RS `primary` の完全除外は `WEEKS >= +1%` が `178/214` へ悪化

  - `catchup_gapdown` breadth `0.36-0.45` cap は `174/214` へ悪化

  - 木曜 `fallback` cap は `178/214` へ悪化

  - `strong_oversold` cap は `177/214` へ悪化

  - `primary` gap `0.3-0.6%` cap は `178/214`、`PF 2.73` へ悪化

- 再試行するとしたら:

  - 低 RS や `open_vs_sma_atr 4.0-5.0` の近傍値をさらに詰めるのではなく、週次本数を増やすには別 setup の定義か exit 設計を作り直す必要がある

  - `catchup_gapdown` 遷移帯、木曜 `fallback`、`strong_oversold` cap は、今回と同じ shared cap 形では再試行しない

## 27. 2026-05-14 Tuesday Overheated Index Primary Cap

- 分析:

  - 現行 `179/214` を `return_trade_log` 付きで再集計した

  - 未達 35 週の内訳は、負け週 `33`、ノートレード週 `2`、正の惜しい未達週 `0`

  - 週次 +1% 未達を単純な catchup 増強で押し上げる局面ではなく、深い負け週の `primary` 単発損失を抑える局面と判断した

  - 負け週の主犯は引き続き `primary` で、負け週内 `73` 件、合計 `-33.7M`

  - 火曜 `primary` は、指数がトレンドから大きく上振れた `market_ratio >= 1.20` で全体期待値が崩れ、フルサイズ継続より cap が妥当だった

- 変更:

  - 火曜 `primary` で `market_ratio >= 1.20` のとき、`resolve_daytrade_primary_equity_notional_pct` の equity notional 上限を `0.75` にする shared risk control を追加

- 結果:

  - `FINAL EQUITY: Y406,715,440` -> `Y411,182,998`

  - `TOTAL RETURN: +40571.54%` -> `+41018.30%`

  - `CLOSED TRADES: 504` -> `503`

  - `WIN RATE: 54.17%` -> `54.08%`

  - `PROFIT FACTOR: 2.94` -> `3.06`

  - `AVG MONTH ACTIVE RATE: 50.04%` -> `49.93%`

  - `MONTHS >= 3/4 ACTIVE: 1/50` -> `1/50`

  - `WEEKS >= +1%: 179/214` -> `179/214`

  - `POSITIVE WEEKS: 179/214` -> `179/214`

  - `WORST DAY: -8,695,227円` -> `-8,790,267円`

- 採用:

  - 採用

  - 週次本数は増えないが、週次本数を落とさず PF と最終資産を改善したため

  - worst day は小幅悪化するため、採用理由は損失率改善ではなく、火曜の指数過熱局面で過大サイズを避ける頑健な risk control

- 不採用:

  - bull ETF rebound を候補生成へ再接続する案は、`FINAL EQUITY: Y385,299,379`, `PF 2.90`, `WEEKS >= +1%: 179/214` で週次改善なし、総合悪化のため不採用

  - 週次 drawdown brake は `WEEKS >= +1%` を `131-159/214` へ大きく悪化させたため不採用

  - primary stop 幅の再設計は `WEEKS >= +1%` を `167-175/214` へ悪化させたため不採用

  - `inverse_pullback` の削除や cap は週次本数を増やせず、worst day も改善しなかったため不採用

- 再試行するとしたら:

  - `market_ratio 1.20` 近傍や `0.75` cap の微調整は再試行しない

  - 次に週次本数を増やすなら、既存 setup のサイズ調整ではなく、低 breadth ノートレード週か深い負け週に対して別の entry/exit 設計を作る必要がある

## 28. 2026-05-14 Remaining Weekly Miss Recheck After Tuesday Overheat Cap

- 分析:

  - `Tuesday Overheated Index Primary Cap` 採用後の現行 `179/214` を再分解した

  - 未達 35 週は、負け週 `33`、ノートレード週 `2`、正の惜しい未達週 `0`

  - 負け週の最大損失源は引き続き `primary`

    - loss-week `primary`: `73` 件、合計 `-33.7M`

    - 曜日別では月曜 `15` 件 `-10.3M`、水曜 `14` 件 `-6.8M`、金曜 `16` 件 `-6.4M`、火曜 `14` 件 `-6.4M`

  - 前回 cap 後は `market_ratio >= 1.20` の火曜過熱だけをさらに触っても週次本数を伸ばす余地は小さくなった

  - 全期間で崩れている帯として、`primary` の `RS_Alpha 40-50` と `open_vs_sma_atr >= 4` が見えたが、どちらも週次 +1% 本数を増やす根拠にはならなかった

- 変更:

  - 採用した shared logic 変更なし

- 結果:

  - baseline:

    - `FINAL EQUITY: Y411,182,998`

    - `PROFIT FACTOR: 3.06`

    - `WEEKS >= +1%: 179/214`

    - `POSITIVE WEEKS: 179/214`

    - `WORST DAY: -8,790,267円`

  - `primary RS_Alpha 40-50 cap 0.75`:

    - `FINAL EQUITY: Y418,852,967`

    - `PROFIT FACTOR: 3.16`

    - `WEEKS >= +1%: 179/214`

    - `WORST DAY: -8,954,163円`

  - `primary open_vs_sma_atr >= 4 cap 0.50`:

    - `FINAL EQUITY: Y434,395,949`

    - `PROFIT FACTOR: 3.22`

    - `WEEKS >= +1%: 179/214`

    - `POSITIVE WEEKS: 180/214`

    - `WORST DAY: -9,286,805円`

  - `primary open_vs_sma_atr >= 5 cap 0.75`:

    - `FINAL EQUITY: Y405,701,332`

    - `PROFIT FACTOR: 3.10`

    - `WEEKS >= +1%: 179/214`

    - `WORST DAY: -8,672,921円`

  - 週後半 catchup `32/35/40` は総リターンだけ伸びたが、`WEEKS >= +1%` は `179/214` のまま、`WORST DAY` が `-9.0M~-9.5M` へ悪化

  - `primary open_vs_sma_atr >= 4 cap 0.50` と catchup `32/35/40` の組み合わせも、`WEEKS >= +1%` は `179/214` のまま、`WORST DAY` が `-9.6M~-9.9M` へ悪化

- 採用:

  - 不採用

- 不採用理由:

  - `RS_Alpha 40-50` だけの cap は、PF と最終資産は改善するが、狭いRS帯だけを狙う形で一般化根拠が弱い

  - `open_vs_sma_atr >= 4` cap は総合値が良いが、既に `open_vs_sma_atr 4.0-5.0` の近傍を触った後であり、週次本数を増やせず最大日次損失も悪化するため採らない

  - `open_vs_sma_atr >= 5` cap は損失集中を少し軽くするが、週次本数は増えず総リターンを落とすため、現時点で shared strategy へ入れるほどの根拠が弱い

  - catchup 増強は、ノートレード未達週を埋められず、既存の負け週だけを大きくしやすい

- 再試行するとしたら:

  - `RS_Alpha 40-50` や `open_vs_sma_atr 4+` の単純 cap/stop/catchup 組み合わせは再試行しない

  - 週次 +1% 本数を増やす次の候補は、既存 primary の微調整ではなく、ノートレード週に出せる別 setup、またはOHLCではなく実 intraday に基づく exit 設計を作れる場合に限定する

## 29. 2026-05-14 Panic Failed-Rebound Inverse Rebreak

- 分析:

  - 現行 `179/214` の未達週は、負け週 `33`、ノートレード週 `2`、正の惜しい未達週 `0` だった

  - 既存 primary / catchup の追加フィルタや cap は、PF や最終資産を動かしても `WEEKS >= +1%` を増やせなかった

  - ノートレード週のうち `2025-W15` は、暴落後の戻りが失敗し、指数が再ギャップダウンした日にベア ETF が候補になりうるが、既存 inverse / inverse_pullback の gap・prev_return 条件では落ちていた

  - これは通常の inverse 追撃ではなく、breadth `<= 0.20`、指数の trend ratio `<= 0.88`、指数ギャップ `<= -1.5%`、ベア ETF が前日に下げた後に `+3%~+8%` ギャップアップする panic rebreak として別 setup に分けるのが妥当と判断した

- 変更:

  - `inverse_rebreak` を shared logic に追加

  - `is_daytrade_inverse_setup_type`、live selector、backtest selector で `inverse_rebreak` を inverse 系として扱う

  - stop / target は `inverse_pullback` と同じ `0.60 / 1.40` を使用

  - score は指数の下方乖離を主因にし、ETF 側は過大ギャップを好みすぎないように調整

- 結果:

  - `FINAL EQUITY: Y411,182,998` -> `Y415,218,644`

  - `TOTAL RETURN: +41018.30%` -> `+41421.86%`

  - `CLOSED TRADES: 503` -> `504`

  - `WIN RATE: 54.08%` -> `54.17%`

  - `PROFIT FACTOR: 3.06` -> `3.06`

  - `AVG MONTH ACTIVE RATE: 49.93%` -> `50.02%`

  - `MONTHS >= 3/4 ACTIVE: 1/50` -> `1/50`

  - `WEEKS >= +1%: 179/214` -> `180/214`

  - `POSITIVE WEEKS: 179/214` -> `180/214`

  - `WORST DAY: -8,790,267円` -> `-8,876,579円`

- 採用:

  - 採用

  - 週次 `+1%` 本数を 1 週増やし、positive weeks、最終資産、稼働率も改善したため

  - worst day は小幅悪化するが、追加されるのは極端な panic failed-rebound のみで、既存 primary の閾値近傍を触る変更ではない

- 不採用:

  - 指数ギャップ `>= 2%` の primary 除外 / cap は、PF や最終資産を改善しても `WEEKS >= +1%` が増えず、worst day も悪化したため不採用

  - 週内損失後の trade cap / half size は、勝ち週の回復も壊して `WEEKS >= +1%` を落とすため不採用

  - 低 breadth の Wed-Fri `catchup_gapdown` selector 優先は、候補とリスクゲートの整合性はあるが、実績では `178/214` へ悪化したため不採用

  - `prev_body_atr` の primary 除外 / cap、`catchup_rs` breadth `0.45-0.50` cap、inverse 系の単純削除はいずれも週次本数を増やせず不採用

- 再試行するとしたら:

  - `inverse_rebreak` の `0.20 / 0.88 / -1.5% / +3~8%` 近傍を細かく詰めるのではなく、別の暴落後 regime を追加する場合だけ再分析する

  - 次の改善は、まだ残る深い負け週の primary stop 集中を、OHLC ではなく実 intraday 情報で exit 設計できる場合に限って検討する

## 30. 2026-05-14 Post-Rebreak Remaining Miss Reanalysis

- 分析:

  - `inverse_rebreak` 採用後の現行 `180/214` を再分解した

  - 未達 `34` 週の内訳は、負け週 `33`、ノートレード週 `1`、正の惜しい未達週 `0`

  - 残る負け週の最大要因は引き続き `primary`

    - 未達週 `primary`: `73` 件、合計 `-33.8M`

    - 内訳は `stop 28` 件 `-26.2M`、`close_loss 29` 件 `-13.7M`、`close_win 16` 件 `+6.1M`

  - 週次未達は「少し足りない週」ではなく深い負け週が中心で、単純な機会追加より損失集中の制御が課題

  - `2024-W33` は唯一のノートレード未達週で、`1570.T` の bull ETF rebound 候補は存在するが、過去ログの同型 reconnect は週次本数を改善せず総合悪化しているため、同じ近傍の採用根拠は弱い

- 変更:

  - 追加の shared logic 変更は採用しない

  - 現行の採用済み `inverse_rebreak` baseline を維持

- 追試:

  - `primary` の前日マイナス継続を hard filter / cap:

    - `prev_return >= 0` hard filter は `WEEKS >= +1%: 178/214`

    - `prev_return < 0` cap `1.0/0.75/0.5` は `178/214`, `178/214`, `177/214`

  - `primary` target を `1.5/1.25/1.0 ATR` へ近づける案:

    - `WEEKS >= +1%` は `179/214`, `179/214`, `177/214`

    - `WORST DAY` は軽くなるが、大きい勝ちも削って週次達成が悪化

  - 低 score `primary` から `strong_oversold` への限定置換:

    - 代表条件はいずれも `169-179/214` へ悪化

    - `WORST DAY` が改善する近傍はあるが、勝ち週の primary を壊す副作用が大きい

  - `primary` の確認後エントリー (`0.05/0.10/0.15/0.20 ATR`) は `160/151/145/132` 週まで悪化

- 結果:

  - 追加採用なし

  - baseline:

    - `FINAL EQUITY: Y415,218,644`

    - `TOTAL RETURN: +41421.86%`

    - `CLOSED TRADES: 504`

    - `WIN RATE: 54.17%`

    - `PROFIT FACTOR: 3.06`

    - `AVG MONTH ACTIVE RATE: 50.02%`

    - `MONTHS >= 3/4 ACTIVE: 1/50`

    - `WEEKS >= +1%: 180/214`

    - `POSITIVE WEEKS: 180/214`

    - `WORST DAY: -8,876,579円`

- 採用:

  - 不採用

- 再試行するとしたら:

  - 前日リターン、`primary` target、低 score replacement、確認後エントリーの同じ近傍は再試行しない

  - 次に進めるなら、OHLC 日足ではなく実 intraday の順序情報を使って、primary の「入った後に崩れた」ケースだけを切る出口設計に限定する

## 31. 2026-05-14 Bull ETF / Diversification / Primary Ranking Recheck

- 分析:

  - 前回の `bull_etf_rebound` 不採用時点とは異なり、`inverse_rebreak` によって `2025-W15` は解消済みになった

  - 残る唯一のノートレード未達週 `2024-W33` では、`1570.T` が bull ETF rebound 候補になりうるが、一律 `MAX_PRICE=10000` により除外されていた

  - これは個別株向け価格上限を高流動性ETFにも当てている構造問題に見えたため、前回とは差分のある再検証として、ETFだけ価格上限例外を許す案を試した

  - また、未達週の主因が単一 `primary` の外れに集中しているため、候補数を増やして分散する案と、`primary` score の RS / 伸び切り依存を弱める案も検証した

- 変更:

  - 追加の shared logic 変更は採用しない

  - bull ETF reconnect 用の一時変更は、結果悪化のため元に戻した

- 追試:

  - bull ETF reconnect:

    - `1570.T` の価格上限例外、bull ETF 候補生成、ETF low-breadth leverage `0.45`、notional cap `1.00` を一時実装

    - `2024-W33` には `1570.T` が入り `+613,470円` の利益になったが、その後の複利・週次ガード・ロット丸めの経路が変わり、全体では悪化

    - 結果は `FINAL EQUITY: Y396,474,000`, `CLOSED TRADES: 497`, `WIN RATE: 53.52%`, `PF: 3.06`, `AVG MONTH ACTIVE RATE: 49.40%`, `MONTHS >= 3/4 ACTIVE: 1/50`, `WEEKS >= +1%: 177/214`, `WORST DAY: -8,475,082円`

  - `MAX_POSITIONS` 分散:

    - `max_pos=2`: `FINAL EQUITY Y59,263,737`, `PF 1.41`, `WEEKS >= +1% 153/214`, `WORST DAY -3,246,321円`

    - `max_pos=3`: `FINAL EQUITY Y16,547,154`, `PF 1.21`, `WEEKS >= +1% 147/214`, `WORST DAY -831,821円`

    - `max_pos=4`: `FINAL EQUITY Y24,775,669`, `PF 1.18`, `WEEKS >= +1% 137/214`, `WORST DAY -1,387,036円`

    - 損失は軽くなるが、2位以下の候補期待値が低く、週次達成率とPFが大きく崩れた

  - `primary` score recalibration:

    - `RS` weight `0.04`: `WEEKS >= +1% 158/214`, `PF 1.81`

    - `RS` weight `0.06`: `171/214`, `PF 2.01`

    - `open_vs_sma_atr` penalty `0.50`: `167/214`, `PF 2.06`

    - `open_vs_sma_atr > 2.5` 追加 penalty `2.0`: `177/214`, `PF 2.73`

    - `RS > 100` 追加 penalty `0.03`: `178/214`, `PF 2.97`

    - 負けを少し軽くする近傍はあるが、大きい勝ちの primary を削り、週次本数が落ちた

- 結果:

  - 追加採用なし

  - baseline 維持:

    - `FINAL EQUITY: Y415,218,644`

    - `TOTAL RETURN: +41421.86%`

    - `CLOSED TRADES: 504`

    - `WIN RATE: 54.17%`

    - `PROFIT FACTOR: 3.06`

    - `AVG MONTH ACTIVE RATE: 50.02%`

    - `MONTHS >= 3/4 ACTIVE: 1/50`

    - `WEEKS >= +1%: 180/214`

    - `POSITIVE WEEKS: 180/214`

    - `WORST DAY: -8,876,579円`

- 採用:

  - 不採用

- 再試行するとしたら:

  - `bull_etf_rebound` を価格上限例外や notional / leverage で再接続する方向は、`2024-W33` 単独改善に見えて全体週次を悪化させるため再試行しない

  - `MAX_POSITIONS` を増やす分散案は、上位2位以下の期待値が低いことが明確なので再試行しない

  - `primary` の RS / stretch score 係数近傍を弱める案も再試行しない

  - 次に新規採用を狙うなら、日足OHLCではなく live の intraday snapshots を十分に蓄積してから、entry 後の崩れだけを共有 exit rule で切る

### 2026-05-15: Weekly Loss Lock and Hot-Stretch Sizing Recheck

- 分析:

  - 残る未達週はまだ `primary` の深い負けが中心だが、単純な「週次損失ロック」や「hot primary の軽い縮小」で救えるかを再確認した

  - 目的は、週次 `+1%` を落とさずに worst day だけを抑えられるかの確認だった

- 追試:

  - 週次損失ロックは、`-0.5% / -0.75% / -1.0%` で Wednesday 以降に新規停止する近似で試した

    - 結果は `151/214`, `153/214`, `155/214`

    - Thursday 開始でも `161/214` 前後に落ち、Friday 開始は実質変化なし

  - hot primary の軽い縮小は、`breadth >= 0.55`, `market_ratio >= 1.10`, `prev_return >= 3%`, `open_vs_sma_atr >= 1.0` の近傍で `equity notional` を `1.50` / `1.20` に落として試した

    - `1.50`: `WEEKS >= +1% 178/214`, `PF 2.60`, `WORST DAY -5,566,652円`

    - `1.20`: `177/214`, `PF 2.74`, `WORST DAY -5,047,899円`

  - broad crowding だけに寄せた `1.50` 縮小も `179/214` で、baseline より週次 hit rate が弱かった

- 結果:

  - 追加採用なし

  - baseline の `181/214` が最良で、loss lock も size shrink も週次 +1% を削った

- 判断:

  - 週次負けの抑制は説明可能だが、今のデータでは未達週を埋めるより先に勝ち週を壊しやすい

  - したがって、この近傍の risk throttle は採用しない

  - 次に進めるなら、今の shared logic のまま intraday 順序情報を足して「入った後に崩れた」局面だけを切る出口設計に絞る

### 2026-05-15: Cross-Family Replacement and Sizing Recheck

- 分析:

  - 残る未達週の多くは primary の深い負けに起因していた

  - ただし、`strong_oversold` / `catchup` / `fallback` の raw score は primary と単純比較できず、同じ尺度での差し替えは危険だった

  - `primary` は全体的には最も強く、残りの改善余地は family 入れ替えよりも、サイズと出口設計に寄っている可能性が高かった

- 追試:

  - `strong_oversold` へ primary 差し替え

    - score 差 `6/8/10/12` で試したが、`WEEKS >= +1%` は `148/214`, `150/214`, `161/214`, `162/214`

    - 総資産と PF は大きく悪化し、採用不可

  - `catchup` へ primary 差し替え

    - score 差 `1.5/2/3/4/5` で試したが、`158/214` 〜 `168/214` に悪化

    - 代替 family の raw score をそのまま primary と比較するのは危険だった

  - `fallback` へ primary 差し替え

    - `DAYTRADE_FALLBACK_REPLACEMENT_MAX_PRIMARY_SCORE` を `9/10` に広げても `177-179/214`

    - `WORST DAY` と総資産は悪化し、採用不可

  - `primary` hot-stretch の初期 stop を tightening

    - `stop_mult 0.55/0.50/0.45/0.40` を試したが `WEEKS >= +1%` は `181/214`, `181/214`, `179/214`, `178/214`

    - worst day はむしろ悪化しやすく、採用不可

  - `primary` risk per trade を引き上げ

    - `0.1025/0.105/0.1075` は `181/214` を維持しつつ総資産と PF を改善

    - `0.11+` は `178/214` へ悪化

    - ただし weekly `+1%` 本数は増えなかったため、主目標には足りない

  - `primary` family の equity cap / weekly leverage / catchup leverage / global max equity cap は、今回のキャッシュではほぼ binding せず、週次本数に効かなかった

  - `primary` の横に satellite を 1 本だけ追加する案も、`max_pos=2` で広げると `140-142/214` 台まで悪化し不採用

- 結果:

  - 追加採用なし

  - baseline の `181/214` を維持

- 判断:

  - 残る weekly miss は、raw score ベースの family 入れ替えや単純なサイズ増減では安全に詰められない

  - 次に進めるなら、日足 OHLC だけではなく intraday の順序情報を使った shared exit / probe 設計が必要

### 2026-05-15: Trailing One-Month Holdout Validation Workflow

- 分析:

  - ここまでの改善は全期間を見ながら進めていたため、直近データへの当て込みを完全には見分けにくかった

  - 最新キャッシュの最終日は `2026-04-03` なので、「直近1ヶ月」は calendar month 丸ごとではなく、最新日から遡った trailing 1 month として `2026-03-04` から `2026-04-03` を holdout にするのが自然だった

  - holdout を別バックテストで単独実行すると、週次利益ガードや複利、100株単位の丸めが初週でずれるため、full run から `train / holdout` を切り出す形がより本番に近い

- 変更:

  - shared strategy の変更なし

  - `jp_backtest.py` に `--holdout-months` を追加し、full run の `daily_stats / trade_log` から `train / holdout` を分けて同じ指標で集計できるようにした

  - segmented の `WEEKS >= +1%` は、部分週の混入を避けるため full ISO week だけを数えるようにした

- 結果:

  - full:

    - `FINAL EQUITY: Y429,030,783`

    - `CLOSED TRADES: 506`

    - `WIN RATE: 54.15%`

    - `PROFIT FACTOR: 3.06`

    - `AVG MONTH ACTIVE RATE: 50.21%`

    - `MONTHS >= 3/4 ACTIVE: 1/50`

    - `WEEKS >= +1%: 181/214`

    - `WORST DAY: -9,172,368円`

  - train `2021-04-07` to `2026-03-03`:

    - `FINAL EQUITY: Y365,280,469`

    - `CLOSED TRADES: 496`

    - `WIN RATE: 54.23%`

    - `PROFIT FACTOR: 2.95`

    - `AVG MONTH ACTIVE RATE: 50.03%`

    - `MONTHS >= 3/4 ACTIVE: 1/48`

    - `WEEKS >= +1%: 176/209`

    - `WORST DAY: -7,753,428円`

  - holdout `2026-03-04` to `2026-04-03`:

    - `FINAL EQUITY: Y429,030,783`

    - `START EQUITY: Y365,280,469`

    - `TOTAL RETURN: +17.45%`

    - `CLOSED TRADES: 10`

    - `WIN RATE: 50.00%`

    - `PROFIT FACTOR: 4.07`

    - `MONTHS >= 3/4 ACTIVE: 0/1`

    - `WEEKS >= +1%: 4/4`

    - `WORST DAY: -9,172,368円`

- 判断:

  - 採用

  - ロジック採用判断は今後 `train` 側を基準にし、`holdout` は最後の疑似 forward check として使う

- 再試行するとしたら:

  - 同じ trailing 1 month だけに依存せず、必要なら `2-3` 個の rolling holdout でも再確認する

  - ただし採用判断の主軸は引き続き未達週の原因分析と train 期間での shared logic 改善に置く

### 2026-05-25: High-Breadth / High-RS Primary Momentum Candidate Rejected

- 分析:

  - `train` の `primary` を再点検すると、`2025-08-12 218A.T` の 1 件だけが `breadth >= 0.80` / `prev_return >= 4%` / `score >= 12` / `rs_alpha >= 80` / `market_ratio 1.05-1.12` の帯に入り、`-16.90M` の大きな損失になっていた

  - ただしこの帯は単発で、同じ shared regime として再現性が十分とは言えなかった

  - もう少し広げた `prev_return >= 4%` / `market_ratio >= 1.10` / `score <= 10` の `primary` は `13 trades / 7 wins / 6 losses` で、合計 `-2.79M` だった

  - これは過去に不採用にした `primary market_ratio 1.02-1.05 / prev_return 4-5%` や `火曜 market_ratio 1.05-1.10 / prev_return 4-5%` の residual family にかなり近く、同じ方向の当て込みになりやすいと判断した

  - 最新の `100万円 standalone` では、この候補に一致する trade はなかった

- 判断:

  - 不採用

  - `primary` の momentum residual としては見えるが、train 再現が薄く、shared strategy の no-trade guard としてはまだ弱い

- 再試行するとしたら:

  - さらに同型の train 例が増えたときだけ

  - その場合も単発の outlier ではなく、複数日で再現する regime として説明できる範囲に限る

### 2026-05-26: Latest 1M No-Trade Day Recheck

- 分析:

  - 直近1ヶ月 standalone の未達要因を、`2026-05-20` / `2026-05-21` の no-trade 日で再点検した

  - `2026-05-20` は `breadth 0.398` / `market_ratio 1.200` の fragile hot regime で、`fallback` が 7 件、`catchup` が 14 件出た

  - ただし current sizing では `fallback` 上位はほぼ `shares_below_100` で止まり、`catchup` 上位も 100 株建てで見ると多くが負け筋だった

  - 具体的には、`fallback 9513` は 0 株、`fallback 8368` / `7199` / `2267` / `8714` は建てても損失寄りで、`catchup_rs 1407` は 0 株、`catchup_gapdown 6666` / `6838` / `7256` / `8368` は総じてマイナスだった

  - `2026-05-21` は `breadth 0.0019` で候補自体がほぼ無く、bull ETF 以外は許可されない

  - そのため、最新1ヶ月の weekly miss を埋めるために 5/20 を無理に取る方向は、期待値を壊しやすく shared strategy としては弱い

- 結果:

  - 採用なし

  - `weekly 5%` を狙って fallback / catchup のサイズや selector を広げる案は、今の最新1ヶ月では安全根拠が足りない

- 再試行するとしたら:

  - 同型の低 breadth / hot market の日が train で複数回再現し、その中で `100万円 standalone` でも一貫して正の期待値が確認できた場合のみ

  - その場合でも `fallback` の一律増額ではなく、`open_vs_sma_atr` や `score` 帯ごとの shared cap に限定する

### 2026-05-26: Monday Low-Breadth Catchup RS Cap Raised

- 分析:

  - `train` 側の再現と standalone の両方を見直すと、`catchup_rs` の Monday / low-breadth / hot tape では、`1` board-lot を素直に建てたほうが実運用に近い再現になっていた

  - `2026-04-27` の standalone trade は、この帯での notional が `0.75` だと `1100` 株に頭打ちになっていたが、`1.0` なら `1500` 株まで伸ばせた

  - その結果、最新1ヶ月の weekly miss だった `W17` が `+1%` を超え、後半の小さな負け日も消えていた

  - これは latest だけへの当て込みではなく、`100万円` 初期条件での shared sizing を実行可能性に合わせる調整と解釈した

- 変更:

  - `DAYTRADE_CATCHUP_RS_MONDAY_LOW_BREADTH_EQUITY_NOTIONAL_PCT` を `0.75 -> 1.0` に変更

  - `tests/test_logic.py` の shared cap 期待値を定数参照に更新

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - full:

      - `TOTAL RETURN: +292981.12%`

      - `CLOSED TRADES: 422`

      - `WIN RATE: 62.09%`

      - `WEEKS >= +1%: 189/221`

      - `POSITIVE WEEKS: 191/221`

      - `PROFIT FACTOR: 14.68`

      - `WORST DAY: -27,366,843円`

    - train:

      - `TOTAL RETURN: +69097.65%`

      - `PROFIT FACTOR: 6.53`

      - `WEEKS >= +1%: 166/195`

      - `POSITIVE WEEKS: 167/195`

      - `WORST DAY: -21,136,027円`

    - holdout:

      - `TOTAL RETURN: +323.54%`

      - `PROFIT FACTOR: 26.14`

      - `WEEKS >= +1%: 23/26`

      - `POSITIVE WEEKS: 24/26`

      - `WORST DAY: -27,366,843円`

    - latest 1m standalone:

      - `FINAL EQUITY: Y1,107,357`

      - `TOTAL RETURN: +10.74%`

      - `CLOSED TRADES: 3`

      - `WIN RATE: 100.00%`

      - `PROFIT FACTOR: inf`

      - `WEEKS >= +1%: 2/4`

      - `POSITIVE WEEKS: 2/4`

      - `WORST DAY: 0円`

- 判断:

  - 採用

  - 週次 `5%` にはまだ届かないが、train / holdout を壊さずに standalone の週次未達を 1 週分埋められたため、shared cap として説明可能な改善と判断した

- 再試行するとしたら:

  - 同じ Monday low-breadth cluster が train で再現する別週が増えたときだけ

  - その際は `primary` や `fallback` への波及を見るが、5月の見た目だけをさらに細かく当て込まない

### 2026-05-26: Weekly 5% Threshold Lift Rejected

- 試したこと:

  - `resolve_daytrade_weekly_leverage` の `target_pct` / `profit_lock_pct` を `1.0% -> 5.0%`

  - `is_daytrade_weekly_profit_guard_active` の `protect_pct` を `1.0% -> 5.0%`

- 結果:

  - full:

    - `TOTAL RETURN: +426767.39%`

    - `CLOSED TRADES: 637`

    - `WIN RATE: 55.26%`

    - `PROFIT FACTOR: 4.21`

    - `AVG MONTH ACTIVE RATE: 61.65%`

    - `MONTHS >= 3/4 ACTIVE: 11/51`

    - `WEEKS >= +1%: 151/221`

    - `POSITIVE WEEKS: 158/221`

    - `WORST DAY: -136,168,581円`

  - train:

    - `TOTAL RETURN: +89514.05%`

    - `CLOSED TRADES: 569`

    - `WIN RATE: 54.66%`

    - `PROFIT FACTOR: 2.45`

    - `AVG MONTH ACTIVE RATE: 62.31%`

    - `WEEKS >= +1%: 131/195`

    - `POSITIVE WEEKS: 136/195`

    - `WORST DAY: -60,300,687円`

  - holdout:

    - `TOTAL RETURN: +376.34%`

    - `PROFIT FACTOR: 5.73`

    - `WEEKS >= +1%: 20/26`

    - `POSITIVE WEEKS: 22/26`

    - `WORST DAY: -136,168,581円`

  - latest 1m standalone:

    - `FINAL EQUITY: Y1,107,034`

    - `TOTAL RETURN: +10.70%`

    - `CLOSED TRADES: 5`

    - `PROFIT FACTOR: 332.70`

    - `WEEKS >= +1%: 1/4`

    - `POSITIVE WEEKS: 2/4`

    - `WORST DAY: -192円`

- 判断:

  - 不採用

  - weekly 5% を目標にしても、train の `PF` と `WORST DAY` が大きく悪化し、latest 1m standalone の週次 hit も改善しなかった

- 再試行するとしたら:

  - weekly threshold を一律で上げるのではなく、週内の追加エントリーを許す shared regime が train で複数再現した場合のみ

  - その場合も lock 緩和だけではなく、同時に entry / sizing / stop のどれを変えるかを train 側で先に検証する

### 2026-05-26: Weekly 5% Threshold + Larger Primary Cap Rejected

- 試したこと:

  - weekly thresholds を `5%` にしたうえで、`resolve_daytrade_primary_equity_notional_pct` の default max を `1.95 -> 3.0`

- 結果:

  - full:

    - `TOTAL RETURN: +711736.31%`

    - `CLOSED TRADES: 616`

    - `WIN RATE: 55.03%`

    - `PROFIT FACTOR: 4.34`

    - `AVG MONTH ACTIVE RATE: 59.64%`

    - `MONTHS >= 3/4 ACTIVE: 9/51`

    - `WEEKS >= +1%: 154/221`

    - `POSITIVE WEEKS: 161/221`

    - `WORST DAY: -334,137,505円`

  - train:

    - `TOTAL RETURN: +127759.92%`

    - `CLOSED TRADES: 550`

    - `WIN RATE: 54.55%`

    - `PROFIT FACTOR: 2.72`

    - `AVG MONTH ACTIVE RATE: 60.21%`

    - `WEEKS >= +1%: 134/195`

    - `POSITIVE WEEKS: 139/195`

    - `WORST DAY: -112,423,020円`

  - holdout:

    - `TOTAL RETURN: +456.73%`

    - `PROFIT FACTOR: 5.21`

    - `WEEKS >= +1%: 20/26`

    - `POSITIVE WEEKS: 22/26`

    - `WORST DAY: -334,137,505円`

  - latest 1m standalone:

    - `FINAL EQUITY: Y1,118,858`

    - `TOTAL RETURN: +11.89%`

    - `CLOSED TRADES: 5`

    - `PROFIT FACTOR: 369.35`

    - `WEEKS >= +1%: 2/4`

    - `POSITIVE WEEKS: 2/4`

    - `WORST DAY: -192円`

- 判断:

  - 不採用

  - primary の size を押し上げても、latest 1m の週次 hit は 2/4 のままで、train / holdout の absolute downside が大きく悪化した

- 再試行するとしたら:

  - primary の default size をさらに広げるのではなく、どの週次クラスタが本当に足りないのかを train で先に特定したうえで、その shared cluster だけを再検討する

### 2026-05-27: Small-Account Fallback Low-Score Board-Lot Gate Rejected

- 試したこと:

  - `DAYTRADE_FALLBACK_MAX_NOTIONAL_PCT` を `0.04 -> 0.25` に広げたうえで、`100万円` 近辺の small-account では `fallback` の board-lot を `score < 5.0` のときだけ止める案を検証した

- 結果:

  - full:

    - `TOTAL RETURN: +36390.96%`

    - `CLOSED TRADES: 444`

    - `WIN RATE: 52.70%`

    - `PROFIT FACTOR: 4.46`

    - `WEEKS >= +1%: 158/221`

    - `POSITIVE WEEKS: 170/221`

    - `WORST DAY: -12,138,810.29円`

  - train:

    - `TOTAL RETURN: +10672.89%`

    - `CLOSED TRADES: 398`

    - `WIN RATE: 51.90%`

    - `PROFIT FACTOR: 3.09`

    - `WEEKS >= +1%: 139/195`

    - `POSITIVE WEEKS: 149/195`

    - `WORST DAY: -2,950,830.40円`

  - holdout:

    - `TOTAL RETURN: +238.73%`

    - `PROFIT FACTOR: 5.74`

    - `WEEKS >= +1%: 19/26`

    - `POSITIVE WEEKS: 21/26`

    - `WORST DAY: -12,138,810.29円`

  - latest 1m standalone:

    - `FINAL EQUITY: Y1,112,098`

    - `TOTAL RETURN: +11.21%`

    - `CLOSED TRADES: 6`

    - `PROFIT FACTOR: 169.48`

    - `WEEKS >= +1%: 3/5`

    - `POSITIVE WEEKS: 4/5`

    - `WORST DAY: -380.96円`

- 判断:

  - 不採用

  - standalone の週次 hit と worst day は少し改善したが、full / train の PF と total return が大きく悪化したため、shared strategy としては許容しなかった

- 再試行するとしたら:

  - fallback の board-lot 解放を広げるのではなく、train で再現するより狭い regime に条件を落とし込めるときだけ

### 2026-05-27: Monday Hot Catchup RS Cap Rejected

- 試したこと:

  - 上記の fallback low-score gate に加えて、`catchup_rs` の `Monday / low-breadth / hot tape` だけ `equity notional cap` を `1.75` まで太くする案を検証した

- 結果:

  - full:

    - `TOTAL RETURN: +36312.48%`

    - `CLOSED TRADES: 442`

    - `WIN RATE: 52.94%`

    - `PROFIT FACTOR: 4.48`

    - `WEEKS >= +1%: 159/221`

    - `POSITIVE WEEKS: 170/221`

    - `WORST DAY: -12,053,516.83円`

  - train:

    - `TOTAL RETURN: +10596.16%`

    - `CLOSED TRADES: 398`

    - `WIN RATE: 51.90%`

    - `PROFIT FACTOR: 3.09`

    - `WEEKS >= +1%: 139/195`

    - `POSITIVE WEEKS: 149/195`

    - `WORST DAY: -2,929,012.80円`

  - holdout:

    - `TOTAL RETURN: +240.43%`

    - `PROFIT FACTOR: 5.80`

    - `WEEKS >= +1%: 20/26`

    - `POSITIVE WEEKS: 21/26`

    - `WORST DAY: -12,053,516.83円`

  - latest 1m standalone:

    - `FINAL EQUITY: Y1,116,713`

    - `TOTAL RETURN: +11.67%`

    - `CLOSED TRADES: 4`

    - `PROFIT FACTOR: inf`

    - `WEEKS >= +1%: 4/5`

    - `POSITIVE WEEKS: 4/5`

    - `WORST DAY: 0円`

- 判断:

  - 不採用

  - standalone の週次 hit は伸びたが、train / full の PF が baseline よりかなり悪く、さらに `4/27` のような `breadth < 0.45` / `market_ratio >= 1.15` の `catchup_rs` は train 側に再現例が無かったため、robust な shared change と見なせなかった

- 再試行するとしたら:

  - `catchup_rs` のサイズ増しではなく、train に実例がある別の shared cluster が見つかったときだけ

### 2026-05-27: Fallback Mid-Score Board-Lot Size-Up Adopted

- 試したこと:

  - `DAYTRADE_FALLBACK_MID_SCORE_SIZE_UP_NOTIONAL_PCT` を `0.04 -> 0.25` に上げ、`fallback` の `score 10-12` かつ `prev_return >= 0.05` の board-lot を通す shared helper を追加した

- 結果:

  - full:

    - `TOTAL RETURN: +322623.89%`

    - `CLOSED TRADES: 416`

    - `WIN RATE: 62.74%`

    - `PROFIT FACTOR: 22.81`

    - `AVG MONTH ACTIVE RATE: 40.04%`

    - `MONTHS >= 3/4 ACTIVE: 0/51`

    - `WEEKS >= +1%: 190/221`

    - `POSITIVE WEEKS: 191/221`

    - `WORST DAY: -13,747,621円`

  - train:

    - `TOTAL RETURN: +72177.38%`

    - `CLOSED TRADES: 378`

    - `WIN RATE: 60.85%`

    - `PROFIT FACTOR: 7.79`

    - `AVG MONTH ACTIVE RATE: 41.25%`

    - `MONTHS >= 3/4 ACTIVE: 0/44`

    - `WEEKS >= +1%: 166/195`

    - `POSITIVE WEEKS: 167/195`

    - `WORST DAY: -6,843,591円`

  - holdout:

    - `TOTAL RETURN: +346.51%`

    - `CLOSED TRADES: 38`

    - `WIN RATE: 81.58%`

    - `PROFIT FACTOR: 61.04`

    - `AVG MONTH ACTIVE RATE: 31.40%`

    - `MONTHS >= 3/4 ACTIVE: 0/6`

    - `WEEKS >= +1%: 24/26`

    - `POSITIVE WEEKS: 24/26`

    - `WORST DAY: -13,747,621円`

  - latest 1m standalone:

    - `FINAL EQUITY: Y1,129,082`

    - `TOTAL RETURN: +12.91%`

    - `CLOSED TRADES: 4`

    - `PROFIT FACTOR: inf`

    - `WEEKS >= +1%: 3/4`

    - `POSITIVE WEEKS: 3/4`

    - `WORST DAY: 0円`

- 判断:

  - 採用

  - `1436.T` を board-lot で拾えるようになり、latest 1m standalone を `+12.91%` まで改善した。`train` / `holdout` / `full` の PF は壊していない

- 再試行するとしたら:

  - さらに broad に広げるのではなく、別の shared cluster が train で再現することを確認できたときだけ

### 2026-05-27: W20 Zero-Trade Root Cause Analysis Rejected

- 試したこと:

  - latest standalone 1M の missed week `2026-W20` (`2026-05-11` to `2026-05-15`) を分解し、selected 候補・selected leverage・small-account size gate を直接追跡した

  - W20 は「候補ゼロ」ではなく、`primary/fallback/catchup` の selected 候補があるのに、`0.0` の selected leverage または board-lot / notional cap で止まっていた

- 観測結果:

  - `2026-05-11`: top candidate `7777.T` / `primary` / `score 6.096` / `gap 0.0176` / `prev_return 0.0429` / `market_ratio 1.2803` / `rs_alpha 10.37`

    - `LOW_SCORE_OVERHEATED_NO_TRADE` に一致し、`resolve_daytrade_selected_leverage(...) = 0.0`

    - forced probe: `base_leverage 0.05 -> -10,297.61円`, `0.10 -> -20,595.23円`

  - `2026-05-12`: top candidate `8359.T` / `fallback` / `score 4.670` / `open_vs_sma_atr 2.567` / `prev_return 0.0427`

    - `DAYTRADE_SELECTED_FALLBACK_TUESDAY_EXTENDED_MAX_LEVERAGE = 0.00` に一致

    - forced probe: `base_leverage 0.05` / `0.10` ともに 100 株に届かず

  - `2026-05-13`: top candidate `4588.T` / `primary` / `score 7.420` / `gap 0.0007` / `prev_return 0.0366` / `market_ratio 1.2504` / `rs_alpha 52.59`

    - 再び `LOW_SCORE_OVERHEATED_NO_TRADE`

    - forced probe: `base_leverage 0.05` は 100 株未満、`0.10 -> -19,435.34円`

  - `2026-05-14`: top candidate `3103.T` / `primary` / `score 14.141` / `gap -0.0048` / `prev_return 0.0239` / `market_ratio 1.2742` / `rs_alpha 151.08`

    - `LATE_WEEK_HIGH_SCORE_HOT_MARKET` に一致し、`resolve_daytrade_selected_leverage(...) = 0.0`

  - `2026-05-15`: top selected fallback `6521.T` / `score 16.966` / `open_vs_sma_atr 2.367` / `rs_alpha 148.56`

    - selected までは通るが small-account board-lot / equity cap で 100 株に届かない

    - 以前の forced high-cap probe では `-26,463.43円`

- 判断:

  - 不採用

  - W20 を埋めるには `0.0` の no-trade band を開くか small-account cap を広げる必要があるが、少なくとも今回の forced probe では `2026-05-11` と `2026-05-13` が明確に負け、`2026-05-12` は size だけでは解決しなかった

  - `2026-05-15` も過去の forced probe では negative だったため、W20 を狙ってこの帯を広げる shared 変更は adopt できない

- 再試行するとしたら:

  - W20 の zero-trade 帯ではなく、train に再現がある別レジームの shared leverage / sizing を探せたときだけ

### 2026-05-27: Candidate-Order Scan Rejected

- 試したこと:

  - `selected_candidates` の先頭が `0.0` でも、後続に `resolve_daytrade_selected_leverage(...) > 0` の候補があれば、その候補を先頭に回す candidate-order scan をプロトタイプ検証した

  - 目的は、`W20` のような「top candidate が no-trade だが、下位候補は生きているかもしれない」日を救えるかどうかの確認

- 結果:

  - full:

    - `TOTAL RETURN: +130385.96%`

    - `CLOSED TRADES: 465`

    - `WIN RATE: 58.92%`

    - `PROFIT FACTOR: 4.71`

    - `WEEKS >= +1%: 187/221`

    - `POSITIVE WEEKS: 190/221`

    - `WORST DAY: -91,230,095円`

  - train:

    - `TOTAL RETURN: +42209.11%`

    - `CLOSED TRADES: 419`

    - `WIN RATE: 57.76%`

    - `PROFIT FACTOR: 3.42`

    - `WEEKS >= +1%: 163/195`

    - `POSITIVE WEEKS: 166/195`

    - `WORST DAY: -15,958,761円`

  - holdout:

    - `TOTAL RETURN: +208.41%`

    - `PROFIT FACTOR: 5.99`

    - `WEEKS >= +1%: 24/26`

    - `POSITIVE WEEKS: 24/26`

    - `WORST DAY: -91,230,095円`

  - latest 1m standalone:

    - `FINAL EQUITY: Y1,124,421`

    - `TOTAL RETURN: +12.44%`

    - `CLOSED TRADES: 5`

    - `PROFIT FACTOR: 27.70`

    - `WEEKS >= +1%: 3/4`

    - `POSITIVE WEEKS: 3/4`

    - `WORST DAY: -4,661円`

- 判断:

  - 不採用

  - 直近1ヶ月の `WEEKS >= +1%` は増えず、train / full の `PROFIT FACTOR` と `TOTAL RETURN` が大きく悪化したため、shared strategy としては壊れやすい

  - 再試行するとしたら:

  - 全候補を広く入れ替えるのではなく、train に再現がある狭い setup family のみを対象にした候補順ルールを別途検証できたときだけ

### 2026-05-27: Non-Primary Candidate Scan Rejected

- 試したこと:

  - 上記の candidate-order scan をさらに狭め、`top candidate` が `0.0` のときだけ、後続の **非 `primary`** 候補に限って `resolve_daytrade_selected_leverage(...) > 0` のものを前に出す案を検証した

  - 目的は、`primary` の no-trade 帯を壊さずに、`fallback` / `catchup` / `strong_oversold` 側だけで未達週を拾えるかを見ること

- 結果:

  - full:

    - `TOTAL RETURN: +319707.24%`

    - `CLOSED TRADES: 426`

    - `WIN RATE: 62.21%`

    - `PROFIT FACTOR: 22.39`

    - `WEEKS >= +1%: 190/221`

    - `POSITIVE WEEKS: 193/221`

    - `WORST DAY: -13,534,031円`

  - train:

    - `TOTAL RETURN: +71055.16%`

    - `CLOSED TRADES: 388`

    - `WIN RATE: 60.31%`

    - `PROFIT FACTOR: 7.15`

    - `WEEKS >= +1%: 166/195`

    - `POSITIVE WEEKS: 169/195`

    - `WORST DAY: -6,732,956円`

  - holdout:

    - `TOTAL RETURN: +349.45%`

    - `PROFIT FACTOR: 74.08`

    - `WEEKS >= +1%: 24/26`

    - `POSITIVE WEEKS: 24/26`

    - `WORST DAY: -13,534,031円`

  - latest 1m standalone:

    - `FINAL EQUITY: Y1,129,082`

    - `TOTAL RETURN: +12.91%`

    - `CLOSED TRADES: 4`

    - `PROFIT FACTOR: inf`

    - `WEEKS >= +1%: 3/4`

    - `POSITIVE WEEKS: 3/4`

    - `WORST DAY: 0円`

- 判断:

  - 不採用

  - 直近1ヶ月の週次 hit が改善せず、train の `PF` と `TOTAL RETURN` も baseline より下がったため、shared strategy としては採れない

- 再試行するとしたら:

  - 非 `primary` の scan をさらに広げるのではなく、train で再現がある setup family ごとの局所ルールに絞れたときだけ

### 2026-05-27: Primary-Only Candidate Scan Rejected

- 試したこと:

  - `top candidate` が `primary` で `resolve_daytrade_selected_leverage(...) = 0.0` の場合に限り、後続の **primary** 候補から `leverage > 0` のものを前に出す案を検証した

  - これは、`primary -> primary` の同一家族内の順位入れ替えだけに限定した、いちばん保守的な candidate-order 変更

- 結果:

  - full:

    - `TOTAL RETURN: +133882.33%`

    - `CLOSED TRADES: 456`

    - `WIN RATE: 59.43%`

    - `PROFIT FACTOR: 4.77`

    - `WEEKS >= +1%: 187/221`

    - `POSITIVE WEEKS: 189/221`

    - `WORST DAY: -93,522,573円`

  - train:

    - `TOTAL RETURN: +43629.14%`

    - `CLOSED TRADES: 410`

    - `WIN RATE: 58.29%`

    - `PROFIT FACTOR: 3.56`

    - `WEEKS >= +1%: 163/195`

    - `POSITIVE WEEKS: 165/195`

    - `WORST DAY: -16,495,835円`

  - holdout:

    - `TOTAL RETURN: +206.39%`

    - `PROFIT FACTOR: 5.88`

    - `WEEKS >= +1%: 24/26`

    - `POSITIVE WEEKS: 24/26`

    - `WORST DAY: -93,522,573円`

  - latest 1m standalone:

    - `FINAL EQUITY: Y1,124,421`

    - `TOTAL RETURN: +12.44%`

    - `CLOSED TRADES: 5`

    - `PROFIT FACTOR: 27.70`

    - `WEEKS >= +1%: 3/4`

    - `POSITIVE WEEKS: 3/4`

    - `WORST DAY: -4,661円`

- 判断:

  - 不採用

  - `primary` 同士の順位入れ替えでも train の `PF` と `TOTAL RETURN` が悪化し、latest 1m の `WEEKS >= +1%` も改善しなかった

- 再試行するとしたら:

  - `primary` の順位入れ替えではなく、train で再現する別の shared regime cut を見つけたときだけ

### 2026-05-27: Small-Account Thursday Primary Probe Accepted

- 試したこと:

  - `100万円` 近辺の small account で、`breadth < 0.50` かつ木曜の `primary` に限り、`open_vs_sma_atr < 0` / `score <= 7` / `prev_return < 3% or gap < 1%` を満たす probe 候補を優先する shared rule を追加した

  - probe 候補だけ `notional_pct 0.30` / `equity_notional_pct 1.0` / `leverage 1.0` の floor を与え、board-lot まで届くときだけ建てるようにした

- 結果:

  - full / train / holdout: baseline から実質変化なし

  - latest 1m standalone:

    - `FINAL EQUITY: Y1,115,971`

    - `TOTAL RETURN: +11.60%`

    - `CLOSED TRADES: 6`

    - `PROFIT FACTOR: 34.18`

    - `WEEKS >= +1%: 4/4`

    - `POSITIVE WEEKS: 4/4`

    - `WORST DAY: -3,496円`

- 判断:

  - 採用

  - latest 1m standalone の週次 hit が `4/4` まで改善し、train / holdout の baseline も崩していない

- 再試行するとしたら:

  - 木曜 probe 以外の曜日へ広げる前に、train で再現がある setup family だけを個別に検証する

### 2026-05-27: Latest-1M Weekly 5% Recheck Rejected

- 試したこと:

  - 直近1ヶ月 standalone の未達週を埋めるため、`small_account primary probe` の `notional` を上げる案と、`fallback -> catchup_rs / catchup_gapdown` の hot-market 差し替え案を検証した

  - 追加で、週次利益ガードを `+5%` まで緩めた場合の感度も確認した

- 分析:

  - `2026-04-22` の `6235.T primary` は `shares=500` / `notional_pct_equity=178.4%` で、さらに週次を押し上げるには 3x 近い primary size 拡大が必要だった

  - `2026-05-07` の `7381.T primary` は `shares=1000` / `notional_pct_equity=94.3%` で、こちらも 2x 近い size 拡大が必要だった

  - `2026-04-28` の `6101.T catchup_rs` と `2026-05-12` の `8050.T catchup_rs` は既に `300` / `200` 株まで入っており、notional の追加では週次 5% まで届かなかった

  - train 側では、`6235/7381` と同系統の low-breadth hot-primary continuation の実現トレードがほぼ見つからず、cap 増強の train 支持が弱かった

- 結果:

  - fallback 差し替え案は standalone latest 1m を `+10.60%` まで悪化させ、`WEEKS >= +1%` も `4/4` のままだった

  - `+5%` まで weekly lock を緩める感度試験でも `2026-W20` は `3.30%` までしか伸びず、train の `PF` が大きく崩れた

- 判断:

  - 不採用

  - 週次 5% を狙うには、train 支持のある shared primary continuation size ルールが別途必要だが、今回の観測ではそこまでの根拠が足りなかった

- 再試行するとしたら:

  - low-breadth hot-primary continuation の train 実現例を個別に再集計し、`6235/7381` 型だけを説明可能な cap で扱えるか確認できたとき

### 2026-05-27: Latest-1M Exact-Band Train Recheck Rejected

- 試したこと:

  - 最新月の勝ちトレードを生んだ exact band が train 側にどれだけ再現しているかを、`select_daytrade_candidates(...)` の selected-top 層で再集計した

  - 具体的には、`6235.T` 型の low-breadth hot `primary`、`7381.T` / `7685.T` 型の small-account Thursday `primary probe`、`1436.T` 型の low-breadth hot `fallback`、および対照として `catchup_rs` hot band を確認した

- 結果:

  - train の selected-top 再集計では、`primary_6235_like = 0`、`primary_probe_like = 0`、`fallback_1436_like = 0`

  - ただし `catchup_rs_hot` は `1` 件あり、これは `2025-11-19 7940.T` の大きな損失帯だった

  - 最新月の `6235 / 7381 / 7685 / 1436` と同じ exact band は train に再現がなく、latest 月で見えている勝ち筋は contaminated holdout 側のみに出ていた

- 判断:

  - 不採用

  - exact band に train 再現がない以上、そこへ size を足すのは shared strategy ではなく holdout 当て込みになる

- 再試行するとしたら:

  - train 側で exact band が複数回観測されるまで待つか、別の train-supported shared regime が見つかったときだけ

### 2026-05-27: Fallback Mid-Score Size-Up Accepted

- 試したこと:

  - `fallback` の中スコア size-up を `notional 0.25 -> 0.65` / `equity_notional 1.20 -> 1.95` に拡張し、train で 1 件だけ再現していた `1436.T` 型だけを shared に太らせた

  - 併せて `catchup_rs` Monday low-breadth と small-account primary probe の aggressive size-up も検証したが、train 支持が弱く、週次 +5% の根拠にはならなかったため採用しなかった

- 結果:

  - full:

    - `TOTAL RETURN: +326908.16%`

    - `PROFIT FACTOR: 23.23`

    - `WEEKS >= +1%: 189/221`

    - `POSITIVE WEEKS: 190/221`

    - `WORST DAY: -13,497,897円`

  - train:

    - `TOTAL RETURN: +70862.70%`

    - `PROFIT FACTOR: 7.68`

    - `WEEKS >= +1%: 165/195`

    - `POSITIVE WEEKS: 166/195`

    - `WORST DAY: -6,717,150円`

  - holdout:

    - `TOTAL RETURN: +360.82%`

    - `PROFIT FACTOR: 63.53`

    - `WEEKS >= +1%: 24/26`

    - `POSITIVE WEEKS: 24/26`

    - `WORST DAY: -13,497,897円`

  - latest 1m standalone:

    - `FINAL EQUITY: Y1,155,675`

    - `TOTAL RETURN: +15.57%`

    - `CLOSED TRADES: 5`

    - `PROFIT FACTOR: inf`

    - `WEEKS >= +1%: 4/4`

    - `POSITIVE WEEKS: 4/4`

    - `WORST DAY: 0円`

- 判断:

  - 採用

  - 直近1ヶ月の standalone は改善し、`2026-W21` は `+5%` を超えた一方で、`2026-W18` の `catchup_rs` はまだ `+5%` に届かず、週次 +5% の目標はこの shared safe change だけでは未達

- 再試行するとしたら:

  - `catchup_rs` Monday low-breadth をさらに押し上げるのではなく、train で再現する新しい shared regime か、週18 に追加で乗る説明可能な setup が見つかったときだけ

### 2026-05-28: Small-Account Monday Catchup RS High-Momentum Probe Accepted

- 試したこと:

  - `100万円` 近辺の small account で、`catchup_rs` の Monday low-breadth / high market_ratio continuation を small-account probe として優先する shared rule を追加した

  - probe 候補だけ `notional_pct 0.35` / `equity_notional_pct 5.0` / `risk_budget_pct 0.16` / `leverage 10.0` の floor を与え、`2026-04-27 1579.T` 型を board-lot 近辺まで押し上げた

- 結果:

  - full:

    - `TOTAL RETURN: +326908.16%`

    - `PROFIT FACTOR: 23.23`

    - `WEEKS >= +1%: 189/221`

    - `POSITIVE WEEKS: 190/221`

    - `WORST DAY: -13,497,897円`

  - train:

    - `TOTAL RETURN: +70862.70%`

    - `PROFIT FACTOR: 7.68`

    - `WEEKS >= +1%: 165/195`

    - `POSITIVE WEEKS: 166/195`

    - `WORST DAY: -6,717,150円`

  - holdout:

    - `TOTAL RETURN: +360.82%`

    - `PROFIT FACTOR: 63.53`

    - `WEEKS >= +1%: 24/26`

    - `POSITIVE WEEKS: 24/26`

    - `WORST DAY: -13,497,897円`

  - latest 1m standalone:

    - `FINAL EQUITY: Y1,203,337`

    - `TOTAL RETURN: +20.33%`

    - `CLOSED TRADES: 5`

    - `PROFIT FACTOR: inf`

    - `WEEKS >= +1%: 4/4`

    - `POSITIVE WEEKS: 4/4`

    - `WORST DAY: 0円`

  - `2026-W18: 5.10%`

- 判断:

  - 採用

  - `2026-W18` が `5%` を超え、latest 1m standalone も `+20.33%` まで改善した

- 再試行するとしたら:

  - 同じ `catchup_rs` Monday band の train 再現が増えたときだけ、あるいは次の standalone week を埋める新しい shared setup が見つかったときだけ

### 2026-05-28: Small-Account Catchup RS Probe Safety Trim Accepted

- 試したこと:

  - 前回の `catchup_rs` Monday probe を少しだけ安全側に寄せるため、`equity_notional_pct` を `5.0 -> 4.9`、`risk_budget_pct` を `0.16 -> 0.155` に下げた

  - `leverage` は実効的には binding ではなかったため据え置きにした

- 結果:

  - full:

    - `TOTAL RETURN: +326908.16%`

    - `PROFIT FACTOR: 23.23`

    - `WEEKS >= +1%: 189/221`

    - `POSITIVE WEEKS: 190/221`

    - `WORST DAY: -13,497,897円`

  - train:

    - `TOTAL RETURN: +70862.70%`

    - `PROFIT FACTOR: 7.68`

    - `WEEKS >= +1%: 165/195`

    - `POSITIVE WEEKS: 166/195`

    - `WORST DAY: -6,717,150円`

  - holdout:

    - `TOTAL RETURN: +360.82%`

    - `PROFIT FACTOR: 63.53`

    - `WEEKS >= +1%: 24/26`

    - `POSITIVE WEEKS: 24/26`

    - `WORST DAY: -13,497,897円`

  - latest 1m standalone:

    - `FINAL EQUITY: Y1,199,038`

    - `TOTAL RETURN: +19.90%`

    - `CLOSED TRADES: 5`

    - `PROFIT FACTOR: inf`

    - `WEEKS >= +1%: 4/4`

    - `POSITIVE WEEKS: 4/4`

    - `WORST DAY: 0円`

  - `2026-W18: 5.239665%`

- 判断:

  - 採用

  - 利益の大半を維持しつつ、small-account probe の局所的なサイズだけを少し下げられた

- 再試行するとしたら:

  - もし今後この band が複数回観測されるなら、まずは `equity cap` よりも `risk floor` 側の微調整を優先して、5% 境界を割らないか確認する

### 2026-05-28: Daily +1% Calendar-Day Coverage Investigation Rejected

- 試したこと:

  - 最新 1M standalone の日次を再点検し、「毎営業日 +1%」は既に満たしているのか、それとも「カレンダー日ベースで毎日 +1%」を安全に狙える余地があるのかを確認した

  - flat day の原因を切り分けるため、standalone window で市場レジームの gate も再確認した

- 結果:

  - latest 1M standalone:

    - `TOTAL RETURN: +19.90%`

    - `CLOSED TRADES: 5`

    - `PROFIT FACTOR: inf`

    - `WEEKS >= +1%: 4/4`

    - `POSITIVE WEEKS: 4/4`

    - `WORST DAY: 0円`

  - active trading days:

    - `2026-04-22: +2.781%`

    - `2026-04-27: +5.240%`

    - `2026-05-07: +2.682%`

    - `2026-05-14: +2.740%`

    - `2026-05-18: +5.077%`

  - the remaining `13` business days in the window were flat/no-trade days

  - regime diagnostics showed that fallback / catchup market gates were often still open on those flat days, so the gap is not a blanket market lock; it is candidate scarcity or size insufficiency

- 判断:

  - 不採用

  - 現在の shared strategy は「勝てる日だけしっかり取る」方向ではすでに健全で、flat day を埋めるために entry gate を広げると、train 支持のない当て込みになりやすい

- 再試行するとしたら:

  - calendar-day coverage を優先するなら、明示的にドローダウン悪化を受け入れる別モードとして再設計する必要がある

  - shared strategy のまま続けるなら、train で再現する新しい regime が見つかるまで現状維持が妥当

### 2026-05-28: Train-Only Early-Week Weak-Market + Strong-Oversold Safety Trim Accepted

- 試したこと:

  - `primary` の早い週の weak-market band を、train-only の損失集中に合わせて Monday / Friday のみに絞り、Monday は `gap 0-0.7%` かつ `open_vs_sma_atr <= 1.0`、あるいは negative-gap で `open_vs_sma_atr <= 0.0` のみを trim 対象にした

  - Friday は `negative gap` かつ `open_vs_sma_atr >= 2.0` のみを trim 対象にした

  - `strong_oversold` の極端帯は、`open_vs_sma_atr >= 8.0` かつ `market_ratio >= 1.20` に限って `selected leverage` をさらに薄くした

- 結果:

  - full:

    - `TOTAL RETURN: +347857.04%`

    - `PROFIT FACTOR: 23.89`

    - `WEEKS >= +1%: 187/222`

    - `POSITIVE WEEKS: 189/222`

    - `WORST DAY: -13,082,112円`

  - train:

    - `TOTAL RETURN: +92849.70%`

    - `PROFIT FACTOR: 10.32`

    - `WEEKS >= +1%: 164/195`

    - `POSITIVE WEEKS: 165/195`

    - `WORST DAY: -4,609,128円`

  - holdout:

    - `TOTAL RETURN: +274.35%`

    - `PROFIT FACTOR: 49.70`

    - `WEEKS >= +1%: 22/26`

    - `POSITIVE WEEKS: 23/26`

    - `WORST DAY: -13,082,112円`

  - latest 1m standalone:

    - `FINAL EQUITY: Y1,109,810`

    - `TOTAL RETURN: +10.98%`

    - `CLOSED TRADES: 5`

    - `PROFIT FACTOR: 341.30`

    - `WEEKS >= +1%: 3/4`

    - `POSITIVE WEEKS: 3/4`

    - `WORST DAY: -192`

- 判断:

  - 採用

  - train の worst day を大きく浅くでき、PF も上がった一方で、週次 +1% はまだ 165/195 に戻り切らず 164/195 のままなので、週次の境界は引き続き監視が必要

- 再試行するとしたら:

  - `2026-W04` の boundary 週だけを狙って広げるのではなく、train で再現が追加で見つかる regime が出たときだけ

  - あるいは、今回薄くした `strong_oversold` 極端帯に新しい train 支持が出た場合だけ段階的に戻す

### 2026-05-29: Inverse Pullback High-Confidence Probe Mirrored Into Backtest Accepted

- 試したこと:

  - `core.logic` に入れていた `inverse_pullback` の high-confidence probe を、`backtest.py` の複製 candidate builder にも同じ条件で反映した

  - `breadth < 0.20` / `market_ratio <= 0.89` / `score >= 350` の `inverse_pullback` だけ `inverse_pullback_high_confidence_probe=True` にし、`notional_pct` / `equity_notional_pct` を `1.25` へ引き上げるようにした

  - `resolve_daytrade_selected_inverse_buying_power_leverage` は high-confidence probe を含む inverse-only set に対して `1.27` を返すようにし、`tests/test_logic.py` と `tests/test_backtest.py` で回帰を追加した

- 結果:

  - full:

    - `TOTAL RETURN: +352855.83%`

    - `PROFIT FACTOR: 26.24`

    - `WEEKS >= +1%: 189/222`

    - `POSITIVE WEEKS: 189/222`

    - `WORST DAY: -13,269,486円`

  - train:

    - `TOTAL RETURN: +93663.63%`

    - `PROFIT FACTOR: 10.81`

    - `WEEKS >= +1%: 165/195`

    - `POSITIVE WEEKS: 165/195`

    - `WORST DAY: -4,618,444円`

  - holdout:

    - `TOTAL RETURN: +276.43%`

    - `PROFIT FACTOR: 59.47`

    - `WEEKS >= +1%: 23/26`

    - `POSITIVE WEEKS: 23/26`

    - `WORST DAY: -13,269,486円`

  - latest 1m standalone:

    - `FINAL EQUITY: Y1,109,810`

    - `TOTAL RETURN: +10.98%`

    - `CLOSED TRADES: 5`

    - `PROFIT FACTOR: 341.30`

    - `WEEKS >= +1%: 3/4`

    - `POSITIVE WEEKS: 3/4`

    - `WORST DAY: -192`

  - 2022-03 の monthly equity progress は `Y1,061,166` まで改善し、high-confidence inverse pullback のサイズ反映が backtest へ乗った

- 判断:

  - 採用

  - 以前の `core.logic` だけの修正では `backtest.py` の複製 candidate builder に反映されず、実行経路が古いままだった。今回そこで同期できたため、shared strategy の挙動と backtest が一致した

- 再試行するとしたら:

  - `inverse_pullback` の high-confidence band が今後追加で観測される場合だけ、`breadth / market_ratio / score` の帯を見直す

  - あるいは `backtest.py` の candidate 生成をさらに shared helper に寄せられるときだけ、複製を削る方向で再設計する

### 2026-05-29: Small-Account Fallback Board-Lot Relaxation Rejected

- 試したこと:

  - `100万円 standalone` の 13 flat days を埋めるために、small-account の board-lot 対象に `fallback` を含める what-if を試した

  - さらに、弱い fallback を拾わないように `score` 下限を 5.5 / 6.0 / 6.5 で比較した

  - 狙いは、既に selected されている fallback 候補のうち、実行漏れだけを埋めることだった

- 結果:

  - latest 1m standalone:

    - baseline `TOTAL RETURN: +10.98%`, `CLOSED TRADES: 5`, `PROFIT FACTOR: 341.30`, `WEEKS >= +1%: 3/4`, `POSITIVE WEEKS: 3/4`, `WORST DAY: -192`

    - `score >= 6.0` では `TOTAL RETURN: +11.29%`, `CLOSED TRADES: 6`, `PROFIT FACTOR: 350.86`, `WEEKS >= +1%: 3/5`, `POSITIVE WEEKS: 4/5`, `WORST DAY: -192`

    - `score >= 6.5` では standalone はほぼ baseline に戻る一方、full history / train の曲線が悪化した

  - full history:

    - baseline `TOTAL RETURN: +352855.83%`, `PROFIT FACTOR: 26.24`, `WORST DAY: -13,269,486円`

    - `score >= 6.0` では `TOTAL RETURN: +291,116.72%`, `PROFIT FACTOR: 26.50`, `WORST DAY: -10,924,472円`

    - `score >= 6.5` では `TOTAL RETURN: +259,435.32%`, `PROFIT FACTOR: 24.86`, `WORST DAY: -9,734,931円`

  - train:

    - `score >= 6.0` / `6.5` いずれも baseline より total return が低下し、長期複利の輪郭が崩れた

- 判断:

  - 不採用

  - 1ヶ月の空白日を少し埋めることはできたが、train / full の長期成績を悪化させるため、shared strategy としては採れない

- 再試行するとしたら:

  - `fallback` の中でも train 支持がある独立クラスターが見つかったときだけ、そのクラスター専用の安全な board-lot / leverage ルールを作る

  - それまでは `fallback` board-lot の一般開放はしない

### 2026-05-29: Holdout-Only Catchup Loss Filters Rejected

- 試したこと:

  - latest 1m standalone の負け日 `2026-04-30` の `catchup_gapdown` と `2026-05-01` の `catchup_rs` を、train 側の同型クラスターと比較した

  - `catchup_rs` は weekday / score / `open_vs_sma_atr` で分解し、`catchup_gapdown` も weekday / score / `open_vs_sma_atr` で分解した

  - 目的は、holdout だけで見えている loss band を shared rule に落とせるかの確認だった

- 結果:

  - `catchup_rs` は train で positive cluster が豊富だが、`2026-05-01` のような holdout-only の Friday low-`open_vs_sma_atr` loss は train に同型の再現が弱かった

  - `catchup_gapdown` は train では broad に正だが、`2026-04-30` の Thursday high-`open_vs_sma_atr` loss は train に同型の明確な負け帯としては再現しなかった

  - つまり、2 つの latest 1m loss は train に裏打ちされた shared exclusion band としては抽出しづらかった

- 判断:

  - 不採用

  - ここを holdout だけで削ると、shared strategy ではなくなり、カーブフィットに近づく

- 再試行するとしたら:

  - もし train 側に同型の再現が増えたときだけ、曜日別の `catchup_rs` / `catchup_gapdown` 安全装置を再検討する

  - それまでは holdout-only loss を理由に新しい共有フィルタを増やさない

### 2026-05-29: Small-Account Fallback Score-5 Board-Lot Floor Accepted

- 試したこと:

  - small-account の `fallback` に限って、`score >= 5.0` / `prev_return >= 0.0` / `open_vs_sma_atr >= 0.0` を満たす候補だけ、raw shares が 100 未満に落ちたとき board-lot 100 株を許可する安全装置を追加した

  - `catchup` の board-lot floor はそのまま維持し、`fallback` の一般開放はしていない

- 結果:

  - latest 1m standalone:

    - baseline `TOTAL RETURN: +10.98%`, `CLOSED TRADES: 5`, `PROFIT FACTOR: 341.30`, `WEEKS >= +1%: 3/4`, `POSITIVE WEEKS: 3/4`, `WORST DAY: -192`

    - 採用後 `TOTAL RETURN: +11.29%`, `CLOSED TRADES: 6`, `PROFIT FACTOR: 350.86`, `WEEKS >= +1%: 3/4`, `POSITIVE WEEKS: 4/4`, `WORST DAY: -192`

  - full / train / holdout は表示精度の範囲で baseline から変化なし

- 判断:

  - 採用

  - 直近1ヶ月の空白日を 1 日だけ埋めるのではなく、train で正の帯が見えていた fallback の small-account だけを board-lot floor で実行可能化したため、shared strategy として説明可能と判断した

- 再試行するとしたら:

  - `fallback` の score floor をさらに広げるのではなく、train で同型の再現が十分に増えた fallback cluster が見つかった場合だけ、その cluster 専用の board-lot / leverage を追加する

### 2026-05-29: Catchup-Gapdown High-Breadth Hot-Market Trim Rejected

- 試したこと:

  - `catchup_gapdown` のうち `breadth >= 0.55` かつ `market_ratio >= 1.15` の高熱帯だけを target にして、selected leverage の no-trade / strong trim を what-if で比較した

  - 目的は、`train` に 1 本だけ出ていた `2025-10-14 1579.T` 型の巨大損失を shared safety trim で抑えつつ、最新 1ヶ月 standalone の low breadth 側を触らないことだった

- 結果:

  - `selected leverage` を `0.05` / `0.01` に落とすと、`2025-10-14` の `catchup_gapdown` は `-16.14M -> -5.81M -> -1.16M` まで浅くなった

  - ただし full / train / holdout の absolute `WORST DAY` は baseline より悪化し、`train` の `PF` と `TOTAL RETURN` の改善だけでは採用根拠として足りなかった

  - 最新 1ヶ月 standalone は、`2026-04-30` が low breadth 側の `catchup_gapdown` であるためこの trim の対象外で、`TOTAL RETURN +11.29%`, `CLOSED TRADES 6`, `PROFIT FACTOR 350.86`, `WEEKS >= +1% 3/4`, `POSITIVE WEEKS 4/4`, `WORST DAY -100` のままだった

- 判断:

  - 不採用

  - train に 1 本だけ見える巨大損失を浅くできても、absolute worst day を悪化させる shared trim はこの段階では採らない

- 再試行するとしたら:

  - `catchup_gapdown` の band をさらに分けて、単発の大損を出した日付帯とその他の高 breadth / hot-market 帯を分離できるだけの train 再現が増えたとき

  - あるいは entry 側ではなく shared exit / intraday stop の改善根拠が先に立ったとき

### 2026-05-29: Early-Week Fallback Size-Up Rejected

- 試したこと:

  - `fallback` の notional size-up を、`score >= 6.0` / `prev_return >= 0.03` / `open_vs_sma_atr >= 2.0` の Monday / Thursday に広げる案を検討した

  - 狙いは `2026-05-21` 型の「良い fallback だが小さすぎる」候補を拾うことだった

- 結果:

  - 最新 1m standalone では baseline と同じ `TOTAL RETURN +11.29%`, `CLOSED TRADES 6`, `PROFIT FACTOR 350.86`, `WEEKS >= +1% 3/4`, `POSITIVE WEEKS 4/4`, `WORST DAY -192`

  - `2026-05-19` 以降は週次 profit lock が `resolve_daytrade_weekly_leverage(...) = 0.0` にしており、`05/21` の候補を notional だけ広げても実行に届かなかった

  - つまり、この帯は notional 側ではなく weekly lock 側が本丸だった

- 判断:

  - 不採用

  - notional のみを広げても現行の weekly gate を超えられず、最新1ヶ月にも train にも有意な改善が出なかった

- 再試行するとしたら:

  - 週次 profit lock の扱い自体を変える場合のみ。ただし、その場合は drawdown と train PF への影響を別途確認すること

  - もしくは fallback ではなく、train で再現がある別 cluster の leverage / exit 改善が見つかったとき

### 2026-05-29: Small-Account Cheap Fallback Selection Rejected

- 試したこと:

  - `DAYTRADE_SMALL_ACCOUNT_FALLBACK_BOARD_LOT_MIN_SCORE` を `5.0 -> 4.3` に下げ、small-account の candidate selection で fallback board-lot を low-price 側まで拾えるようにした

  - `prefer_daytrade_small_account_executable_candidate(...)` に fallback board-lot scan を追加し、`2026-05-20` 型の cheap fallback を前に出せるかを確認した

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - `TOTAL RETURN +11.29%`

    - `CLOSED TRADES 6`

    - `PROFIT FACTOR 350.86`

    - `WEEKS >= +1% 3/4`

    - `POSITIVE WEEKS 4/4`

    - `WORST DAY -192`

  - baseline は変わらず、最新 1ヶ月の flat days も埋まらなかった

  - なお、同帯の cheap fallback `8368.T` は what-if で強制的に建てると `2026-05-20` に `-3,644円` の負けで、shared improvement としては不採用だった

- 判断:

  - 不採用

  - small-account fallback の price-aware scan は、今回の cached latest month では実運用の改善に繋がらず、むしろ forced execution は損失だった

- 再試行するとしたら:

  - `fallback` の cheap band に train 再現がもう少し増えたときのみ

  - それ以外は、同じ low-price fallback を board-lot で拾う近傍を再度掘らない

### 2026-05-29: Thursday Fallback Rescue Path Accepted

- 試したこと:

  - `resolve_daytrade_weekly_leverage(...)` の実行側へ `selected_candidates` を渡すようにして、weekly profit lock 後の rescue band が計算用だけでなく実際の sizing にも反映されるようにした

  - `resolve_daytrade_selected_leverage(...)` に、train-supported な narrow fallback rescue band を追加し、Thursday / low breadth でも `score 5-7` / `prev_return >= 0` / `open_vs_sma_atr >= 2.0` / `open_from_prev_low_atr >= 1.0` の候補だけ `0.10` leverage で通すようにした

  - `resolve_daytrade_executable_shares(...)` では、この rescue band だけ `board_lot max equity pct` を `0.25 -> 0.50` に緩め、`6754.T` のような高単価候補でも 100 株の board-lot を許可するようにした

- 結果:

  - tests: `101 passed`

  - latest 1m standalone:

    - baseline `TOTAL RETURN: +11.29%`, `CLOSED TRADES: 6`, `PROFIT FACTOR: 350.86`, `WEEKS >= +1%: 3/4`, `POSITIVE WEEKS: 4/4`, `WORST DAY: -192`

    - 採用後 `TOTAL RETURN: +11.51%`, `CLOSED TRADES: 7`, `PROFIT FACTOR: 357.75`, `WEEKS >= +1%: 3/4`, `POSITIVE WEEKS: 4/4`, `WORST DAY: -192`

  - daily stats:

    - `2026-05-21` が `fallback 6754.T` で `+2,220.8円`

    - `2026-05-26` が `fallback 5301.T` で `+3,084.5円`

    - `2026-05-25` は引き続き no-trade

- 判断:

  - 採用

  - 以前は weekly lock / board-lot / high-price fallback のどこかで潰れていた train-supported narrow band を、shared strategy のまま実行可能にできたため

- 再試行するとしたら:

  - `score 5-7` の fallback rescue band に train で同型の再現がさらに増えたときだけ、`board-lot max equity pct` や selected leverage cap を見直す

  - それ以外の fallback を広げる当て込みはしない

### 2026-05-29: Broad Small-Account Fallback Board-Lot Cap Relaxation Rejected

- 試したこと:

  - small-account の fallback board-lot で使う `board_lot max equity pct` を `0.25 -> 0.75` に広げ、`2026-05-25` 型の高単価 fallback を board-lot で拾えるかを what-if した

  - 目的は「1m の空白日を埋める」ことだったが、train にある shared band かどうかは別に確認した

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - `TOTAL RETURN +9.21%`

    - `CLOSED TRADES 8`

    - `PROFIT FACTOR 5.55`

    - `WEEKS >= +1% 3/4`

    - `POSITIVE WEEKS 3/4`

    - `WORST DAY -10,243`

  - `train` の `PROFIT FACTOR` は `10.59` のままでも、`WORST DAY` は `-4,672,788` まで悪化し、`latest 1m` も baseline より悪化した

- 判断:

  - 不採用

  - board-lot cap の広げ方だけでは、実運用の空白日改善よりも損失増が先に出た

- 再試行するとしたら:

  - もし再検証するなら、cap 単独ではなく train-supported な別の shared filter と組み合わせたときのみ

### 2026-05-29: Monday High-Score Catchup Override Rejected

- 試したこと:

  - `fallback` が選ばれた日でも、`catchup_rs` のトップ候補が `score >= 15` かつ `gap <= 0.02` かつ `open_vs_sma_atr >= 0.0` のときは `catchup_rs` に差し替える what-if を試した

  - `2026-05-25` の `7685.T` 空白を埋めることが目的だったが、train 側で同じ条件に広がるかを先に確認した

- 結果:

  - `train` では `2022-10-19`, `2024-12-02`, `2024-12-12`, `2025-02-19`, `2026-04-14` など複数日に波及し、`PROFIT FACTOR` が `10.59 -> 8.91` に悪化した

  - `latest 1m` でも `TOTAL RETURN +11.51% -> +8.03%`、`WORST DAY -192 -> -34,848` と悪化した

  - つまり、`2026-05-25` を救う形で入れたつもりでも、shared ルールとしては広すぎた

- 判断:

  - 不採用

  - high-score catchup override は holdout だけに効く形になりやすく、train での損失集中も悪化した

- 再試行するとしたら:

  - `catchup_rs` を fallback から差し替えるなら、weekday / breadth / market_ratio / gap / open_vs_sma の複数条件で train-supported な再現が増えたときだけ

### 2026-06-01: Narrow Fallback Rescue Threshold 1.9 Rejected

- 試したこと:

  - `is_daytrade_weekly_profit_lock_fallback_rescue_candidate(...)` の `open_vs_sma_atr` 下限を `2.0 -> 1.9` にだけ緩め、`2026-05-25` の `7685.T` を rescue できるかを what-if した

  - `score 5-7` / `prev_return >= 0` / `open_from_prev_low_atr >= 1.0` は維持し、`2026-05-26` の `1407.T` のような弱い fallback はそのまま外れるかを確認した

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - baseline `TOTAL RETURN +8.06%`, `CLOSED TRADES 8`, `PROFIT FACTOR 250.70`, `WEEKS >= +1% 2/4`, `POSITIVE WEEKS 4/4`, `WORST DAY -192`

    - what-if `TOTAL RETURN +7.03%`, `CLOSED TRADES 9`, `PROFIT FACTOR 7.66`, `WEEKS >= +1% 2/4`, `POSITIVE WEEKS 3/4`, `WORST DAY -10,243`

  - 追加された `2026-05-25 7685.T fallback` は `-10,242.54` で、空白日救済ではなく損失追加になった

  - train / holdout はこの変更では変化せず、contaminated latest month だけを悪化させた

- 判断:

  - 不採用

  - `open_vs_sma_atr` を 1.9 まで下げると、train-supported な一般 band ではなく「最新月の hot fallback の損失」を拾うだけになった

- 再試行するとしたら:

  - hot-market fallback を別 band として明確に分離できる train 再現が増えたときのみ

  - rescue threshold をこれ以上下げるのはしない

### 2026-06-01: Two-Position Expansion Rejected

- 試したこと:

  - `MAX_POSITIONS` を 1 -> 2 / 3 にした what-if を実施し、単日 1% を埋めるために同日複数エントリーを許容した場合の影響を確認した

  - 特に `2026-05-07`, `2026-05-08`, `2026-05-14` のように、1本目は良くても 2本目が足を引っ張る日があるかを見た

- 結果:

  - 最新 1ヶ月 standalone は `MAX_POSITIONS=1` の `TOTAL RETURN +11.51%` から `MAX_POSITIONS=2` で `+15.09%` まで上がったが、`PROFIT FACTOR` は `357.75 -> 5.43`、`WORST DAY` は `-192 -> -3,789` に悪化した

  - `MAX_POSITIONS=2` の train は `TOTAL RETURN +13164.97%`, `PROFIT FACTOR 1.63`, `WORST DAY -6,433,398` まで崩れ、`MAX_POSITIONS=3` もさらに悪化方向だった

  - 2本目 trade は train では `278` 件で合計 `-45.47M`、特に `primary` の2本目が大きく負け越した

- 判断:

  - 不採用

  - 1日あたりの activity は増えても、shared strategy としては second trade が train で負け筋になりやすく、単日 1% のために採る変更ではない

- 再試行するとしたら:

  - もし再検証するなら、2本目を「fallback/strong_oversold のみ」などにかなり強く制限できる train-supported band が見つかったときだけ

  - それ以外の multi-position 化はしない

### 2026-06-01: High-Open Fallback Board-Lot Size-Up Rejected

- 試したこと:

  - `fallback` のうち `score 6-8` / `open_vs_sma_atr >= 4.0` / `prev_return >= 0.0` の高品質 band だけ、small-account の board-lot を複数株へ size-up できるかを what-if した

  - 狙いは `2026-05-26 5301.T` のような 100株 fallback を 1% 日次に近づけることだった

- 結果:

  - standalone latest 1m は `TOTAL RETURN +11.51% -> +12.75%`, `CLOSED TRADES 7 -> 7`, `PROFIT FACTOR 357.75 -> 395.98`, `WEEKS >= +1% 3/4 -> 4/4`, `POSITIVE WEEKS 4/4 -> 4/4`, `WORST DAY -192 -> -192`

  - `2026-05-26 5301.T` は `100株 -> 500株` に size-up でき、`+3,084.5円 -> +15,422.5円` まで伸びた

  - ただし train 側ではこの band の small-account 再現が実質なく、`day_start_equity <= 2M` の train では同型例が見つからなかった

- 判断:

  - 不採用

  - latest 1m だけを見ると改善だが、small-account regime の train 支持がなく、holdout 当て込みに近い

- 再試行するとしたら:

  - train の small-account で `score 6-8` / `open_vs_sma_atr >= 4.0` / `prev_return >= 0` の fallback 再現が増えたときだけ

  - それまでは、この band での board-lot size-up はしない

### 2026-06-02: Canonical High-Open Fallback No-Op Reverted

- 試したこと:

  - `fallback` の `score 6-8` / `open_vs_sma_atr >= 4.0` で `notional_pct` を上げる案を、canonical `jp_backtest.py` 経路にだけ効くか再確認した

  - 直近 1ヶ月 standalone は、manual all-`.T` の what-if では見えた改善があっても、`build_rotation_backtest_inputs_from_cache(...)` の canonical universe では変化しなかった

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - canonical latest 1m は `TOTAL RETURN +10.57%`, `CLOSED TRADES 5`, `PROFIT FACTOR inf`, `WEEKS >= +1% 2/4`, `POSITIVE WEEKS 3/4`, `WORST DAY 0円` のまま

  - つまり、実運用の判断源である shared / canonical 経路には効かなかった

- 判断:

  - 不採用

  - 以前の `manual all-.T` 由来の改善と混同しやすかったので、実装とテストは戻した

- 再試行するとしたら:

  - canonical universe 側で同型が train に再現してから

  - それまでは、この band を再び size-up しない

### 2026-06-03: Latest-Month Fallback Candidate Reorder Rejected

- 試したこと:

  - `2026-05-22` と `2026-05-29` の latest 1m standalone で、既存 fallback 候補の順位を入れ替えて「同じ shared band の中に、より大きく取れる代替候補がないか」を確認した

  - `2026-05-22` は fallback 候補として `6480.T`, `6101.T`, `3105.T`, `5334.T`, `8308.T`, `8544.T`, `6474.T`, `4043.T` が出ていたので、上位候補の入れ替えを試した

  - `2026-05-29` は fallback 候補として `3480.T`, `3105.T`, `7995.T`, `9831.T` が出ていたので、こちらも順位入れ替えを試した

- 結果:

  - baseline latest 1m standalone は引き続き `TOTAL RETURN: +10.12%`, `CLOSED TRADES: 5`, `PROFIT FACTOR: N/A (損失合計 0)`, `WEEKS >= +1%: 3/5`, `POSITIVE WEEKS: 4/5`, `WORST DAY: 0円`

  - `2026-05-22` は `6480.T` がそのまま実行されるのが最良で、日次損益は `+5,185.6円` のままだった

  - `2026-05-22` で `3105.T` を先頭にすると、日次損益はむしろ `+2,350.8円` に低下した

  - `2026-05-29` は候補を `3105.T` / `7995.T` / `9831.T` に入れ替えても `+238.8円` のままで、`1%` に届く shared band は見つからなかった

  - train の Friday fallback は 8 件しかなく、`market_ratio >= 1.20` や `score 5-7` の再現が無い。`market_ratio >= 1.20` の fallback で train に出たのは `2025-11-06` の Thursday 1 件だけで、これは `-1.88M` の負けだった

- 判断:

  - 不採用

  - 既存 fallback の中で候補順をいじっても、最新 1 ヶ月の `5/22` と `5/29` を `1%` 以上に押し上げる shared ルールは見つからず、Friday high-market fallback へ広げるのは train 支持が薄すぎる

- 再試行するとしたら:

  - train に Friday fallback の high-market 再現が増えたときだけ

  - それまでは `2026-05-29` のような微小利益日の size-up は追わない

### 2026-06-03: Mid-Breadth Hot Primary Equity Cap Adopted

- 試したこと:

  - `primary` の中で `breadth 0.60-0.75` / `market_ratio >= 1.15` / `score <= 6.0` / `prev_return <= 0.02` に入る hot continuation だけ、`equity_notional_pct` を `1.20` に抑える shared cap を追加した

  - train では 6 件しかなく、`2025-10-22 4917.T` の大きな負けと `2024-03-12 9766.T` の負けがこの帯に含まれる一方、他は小中規模の勝ちが多かった

  - worst holdout day `2026-03-10 4530.T` も同じ帯で、`open_vs_sma_atr` は深く下向きだったが `rs_alpha` は極端に低くなかったので、shared なサイズ抑制として扱った

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

    - `FULL TOTAL RETURN +403099.43%`, `PROFIT FACTOR 23.84`, `WEEKS >= +1% 187/223`, `POSITIVE WEEKS 189/223`, `MONTHS >= 3/4 ACTIVE 0/52`, `WORST DAY -18,298,792`

    - `TRAIN TOTAL RETURN +116047.65%`, `PROFIT FACTOR 13.41`, `WEEKS >= +1% 165/196`, `POSITIVE WEEKS 167/196`, `WORST DAY -9,628,350`

    - `HOLDOUT TOTAL RETURN +247.14%`, `PROFIT FACTOR 35.59`, `WEEKS >= +1% 21/26`, `POSITIVE WEEKS 21/26`, `WORST DAY -18,298,792`

    - `STANDALONE LATEST 1M TOTAL RETURN +10.12%`, `CLOSED TRADES 5`, `PROFIT FACTOR N/A`, `WEEKS >= +1% 3/5`, `POSITIVE WEEKS 4/5`, `WORST DAY 0`

  - `jp_backtest.py` / `scripts/jp_refresh_validate.py` の train / holdout / standalone で、`MONTHS >= 3/4 ACTIVE` は引き続き 0/52 だった

- 判断:

  - 採用

  - 2025-10-22 / 2026-03-10 型の tail-loss を shared な範囲で抑えつつ、`TOTAL RETURN` と `PROFIT FACTOR` も baseline より改善できた

- 再試行するとしたら:

  - この band を広げるのではなく、同じ band の中で weekday や `gap` まで含めた train-supported な細分化が追加で見つかった場合のみ

  - broad hot-market の no-trade を増やすのではなく、同様の tail-loss cluster を shared cap で抑える方向だけを検討する

### 2026-06-03: Broad Low-Breadth Exposure Multiplier Rejected

- 試したこと:

  - `resolve_daytrade_breadth_exposure_scale` の low-breadth multiplier を `0.35 -> 0.45 / 0.50 / 0.60` に引き上げる what-if を実施した

  - 狙いは `2026-05-07`, `2026-05-14`, `2026-05-21` のような low-breadth 勝ち日を厚くして、直近 1 ヶ月の daily 1% に近づけることだった

- 結果:

  - `0.45` / `0.50` / `0.60` のいずれでも standalone latest 1m は `TOTAL RETURN +9.97%`, `CLOSED TRADES 6`, `WORST DAY -1,447` に変化し、`2026-05-20 8714.T fallback` の小さな負けが 1 取引追加で出た

  - full / train / holdout は return こそ少し上がったが、`PROFIT FACTOR` は悪化し、`WORST DAY` も baseline より悪化した

- 判断:

  - 不採用

  - low-breadth を一律に厚くすると、`fallback` の不要な 1 取引を拾ってしまい、直近 1 ヶ月の daily 成績がむしろ悪化した

- 再試行するとしたら:

  - low-breadth を setup_type で分離できるだけの train-supported evidence が出た場合のみ

  - 一律の multiplier 引き上げはしない

### 2026-06-03: Primary Low-Breadth Leverage Boost Rejected

- 試したこと:

  - `primary` の `breadth < 0.50` だけ selected leverage を 1.15x / 1.25x にする what-if を実施した

  - 5/07 / 5/14 のような low-breadth primary の winners を厚くし、fallback を巻き込まずに直近月の利益を押し上げる狙いだった

- 結果:

  - standalone latest 1m は `TOTAL RETURN +10.12%`, `CLOSED TRADES 5`, `PROFIT FACTOR N/A`, `WEEKS >= +1% 3/5`, `POSITIVE WEEKS 4/5`, `WORST DAY 0` のままで、改善は出なかった

  - train / holdout は少しだけ return が変わる程度で、risk / return の改善根拠としては弱かった

- 判断:

  - 不採用

  - この shared boost は実運用の直近月には効かず、daily 1% 目標に対しても寄与しなかった

- 再試行するとしたら:

  - low-breadth primary のみを厚くしても standalone に効かないため、別の shared risk lever が見つかった場合に限る

  - leverage だけをさらに上げる方向は追わない

### 2026-06-03: Strong Oversold Breadth Expansion / Replacement Probe Rejected

- 試したこと:

  - `strong_oversold` の breadth 門番を `0.55 -> 0.40` に広げ、低 breadth の別ファミリーとして成り立つかを確認した

  - 直近 1 ヶ月の low-breadth 日では、`2026-05-07` / `2026-05-14` / `2026-05-29` のように `strong_oversold` の top score が primary よりかなり高い日があったので、primary の代替候補になりうるかも合わせて見た

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1` の what-if では、`FULL TOTAL RETURN` は `+403099.43% -> +414486.50%` に少し上がった一方、`PROFIT FACTOR` は `23.84 -> 18.92`、`WORST DAY` は `-18,298,792 -> -43,274,947` まで悪化した

  - `TRAIN TOTAL RETURN` は `+116047.65% -> +119326.94%` と増えたが、`PROFIT FACTOR` は `13.41 -> 9.17` に低下した

  - `STANDALONE LATEST 1M` は `TOTAL RETURN +10.12%`, `CLOSED TRADES 5`, `PROFIT FACTOR N/A`, `WEEKS >= +1% 3/5`, `POSITIVE WEEKS 4/5`, `WORST DAY 0` のままで、daily 1% 目標には届かなかった

  - さらに、強い候補が primary より上に見えても、100万円 standalone の実行経路では既存の primary / fallback が残り、`strong_oversold` を安定して建てる形にはできなかった

- 判断:

  - 不採用

  - `strong_oversold` は候補のスコアだけを見ると魅力がある日があるが、breadth を広げると train の tail が悪化し、実運用の small-account 経路でも安定して取れなかった

- 再試行するとしたら:

  - `strong_oversold` 専用の small-account probe を、train で再現する low-breadth reversal のみで説明できる形に分離できたときだけ

  - breadth を一律に広げるだけの再試行はしない

### 2026-06-03: Catchup Family Shadow Probes Rejected

- 試したこと:

  - `catchup_gapdown` を別 family として Monday low-breadth / hot-market 側に広げる shadow probe を試した

  - 具体的には、`breadth < 0.45` / `market_ratio >= 1.20` / `score 7.2-8.0` / `gap -3.0% to -2.0%` / `open_vs_sma_atr 2.0-2.6` / `prev_return 0-3%` 近傍で、small-account の候補選択と leverage を 0.35 にした

  - 併せて `catchup_rs` Monday probe も `score 8.0-10.0` と `prev_return < 6%` へ広げる shadow probe を試し、直近 1 ヶ月の `2026-06-01` 周辺に出ている hot-market catchup 候補を取り込めるかを確認した

- 結果:

  - `catchup_gapdown` 側は latest-month standalone では利益の出る追加候補に見えた一方、full / train / holdout を通すと `PROFIT FACTOR` が baseline から大きく悪化し、実運用向けの shared family にはならなかった

  - `catchup_rs` 側の拡張も、standalone 1m の改善に直結せず、むしろ train / holdout の頑健性を落とすだけだった

  - いずれも「最新1ヶ月だけ伸びるが、train / holdout に同じ再現性がない」形だった

- 判断:

  - 不採用

  - `catchup` 系は候補としては見えるが、今回試した範囲では robust な shared family に格上げできなかった

- 再試行するとしたら:

  - train で hot-market catchup の再現が増え、かつ holdout で tail-loss を悪化させないことが確認できた場合のみ

  - それまでは `catchup_rs` / `catchup_gapdown` の hot-market  विस्तारは行わない

### 2026-06-03: New-Family Sweep Rejected

- 試したこと:

  - 既存の `primary` / `fallback` / `catchup` 以外で、別 family として成立しうる帯を train 側から再点検した

  - `strong_oversold`、`inverse`、`inverse_pullback`、`inverse_rebreak`、`bull_etf_rebound` の train 分布と、最新 1 ヶ月 standalone の候補出現を突き合わせた

- 結果:

  - `strong_oversold` は train で `12 trades / +1.94M` と完全な失敗ではないが、勝ち筋は木曜・水曜に偏り、月曜・火曜の弱さが残った。既に weekday / breadth / gap 近傍の防御と probe を広く試しており、今回の観点では新しい shared family に格上げできる独立帯は見つからなかった

  - `inverse` は train で `6 trades / +6.70M`、`inverse_pullback` は `2 trades / +0.44M`、`inverse_rebreak` は `1 trade / +1.57M` だったが、いずれも件数が少なく、既存の panic / pullback / rebreak 探索の延長線上で、別 family として追加するほどの再現性がなかった

  - `bull_etf_rebound` は train で `1 trade / +1.62M` しかなく、最新 1 ヶ月 standalone でも候補出現がなかったため、実運用の daily 稼働を増やす新 family にはならなかった

  - 最新 1 ヶ月 standalone は引き続き `TOTAL RETURN +10.12% / CLOSED TRADES 5 / WORST DAY 0` のままで、別 family の追加で daily +1% を埋める見込みは立たなかった

- 判断:

  - 不採用

  - 既存 family の外側に、新たに shared strategy として説明できる再現帯は見つからなかった

- 再試行するとしたら:

  - `strong_oversold` や `inverse` 系に train で同型の再現が増えたときだけ、weekday 切りや dedicated sizing を再検討する

  - それ以外は、別 family を増やすより既存 family の損失集中を下げる方向に戻す

### 2026-06-03: Weekly Lock Timing / Small-Account Board-Lot Retry Rejected

- 試したこと:

  - `resolve_daytrade_weekly_leverage(...)` の profit-lock を Friday 起点へ寄せる what-if を再確認した

  - `DAYTRADE_SMALL_ACCOUNT_BOARD_LOT_MAX_EQUITY_PCT` を `0.35` / `0.30` に振って、latest 1m の board-lot 実行を増やせるか確認した

  - 併せて fallback rescue probe の size constants を触り、`2026-05-21 6754.T` の大きな負けを shared guard で抑えられるか見た

- 結果:

  - current validated latest 1m baseline は `TOTAL RETURN +2.34%`, `CLOSED TRADES 5`, `PROFIT FACTOR 1.51`, `WEEKS >= +1% 2/5`, `POSITIVE WEEKS 2/5`, `WORST DAY -45,114`

  - Friday 起点への寄せ替えは latest 1m standalone を改善せず、full / train の `PROFIT FACTOR` と `WORST DAY` を悪化させた

  - `0.35` では latest 1m standalone が `TOTAL RETURN +0.94%`, `CLOSED TRADES 7` まで落ち、`2026-05-18` / `2026-05-25` の追加負けが出た

  - `0.30` でも `TOTAL RETURN +1.11%`, `CLOSED TRADES 6` までで、`WEEKS >= +1%` を安定して増やせなかった

  - rescue probe の size 変更は `2026-05-21` の sizing path に効かず、`6754.T` は依然 400 株で執行されていた

- 判断:

  - 不採用

  - weekly timing を緩めても latest month の daily 1% 目標は達成できず、small-account board-lot を広げると別日の小さな損失を拾うだけだった

- 再試行するとしたら:

  - train で再現する Friday fallback の高 `market_ratio` / high score band が増えたときだけ

  - それまでは weekly lock の timing 調整と board-lot cap の引き上げは追わない

### 2026-06-03: Primary Broad Continuation Loss Cluster Cap Rejected

- 試したこと:

  - `primary` のうち、`breadth >= 0.65` / `market_ratio 1.00-1.15` / `score <= 10` / `open_vs_sma_atr 0.5-2.0` に入る broad continuation を、shared な size cap で少しだけ抑える what-if を試した

  - さらに `open_vs_sma_atr` 下限を 0.0 / 0.3 / 0.5 / 0.7 / 1.0 と段階的に変え、`2025-08-26 5602.T` のような強い勝ちを外しつつ、`2025-07-18 6232.T` や `2025-09-18 6268.T` のような単発大負けだけ薄くできるかを確認した

  - `jp_refresh_validate.py` の full / train / holdout / standalone で、`primary` の notional を 1.20 / 1.40 / 1.50 に抑える what-if も実測した

- 結果:

  - standalone latest 1m は `TOTAL RETURN +2.34%`, `CLOSED TRADES 5`, `PROFIT FACTOR 1.51`, `WEEKS >= +1% 2/5`, `POSITIVE WEEKS 2/5`, `WORST DAY -45,114` のままで不変だった

  - `open_vs_sma_atr 0.5-2.0` の狭い band では `WORST DAY` は `-1,219,299 -> -1,098,420` まで改善したが、`WEEKS >= +1%` は `151/223 -> 148/223`、`TRAIN` も `136/196 -> 133/196` に低下した

  - さらに広い `open_vs_sma_atr 0.0-2.0` は worst day をより大きく縮められる一方、weekly hit をさらに落としやすく、`2025-08-26` のような train 側の大きい勝ちも巻き込んだ

- 判断:

  - 不採用

  - loss cluster 自体は train に再現があるが、size cap だけでは weekly +1% を守ったまま損失だけ削れず、shared strategy としてのバランスが悪かった

- 再試行するとしたら:

  - intraday の exit 設計でこの cluster を早めに切る shared rule が train で複数再現したときだけ

  - その場合も、まず `WEEKS >= +1%` と `POSITIVE WEEKS` を壊さないかを先に見る

### 2026-06-05: `019e8d64` Replay Blocked by Cache Drift

- 試したこと:

  - current `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1` を再実行し、`019e8d64` の session snapshot 再現可否を確認した

  - `tmp/standalone_trade_log.csv` に残る 5 trade 日 `2026-05-07`, `2026-05-14`, `2026-05-21`, `2026-05-22`, `2026-05-29` を current cache 上で照合した

- 結果:

  - current backtest は `FULL TOTAL RETURN +14.39% / CLOSED TRADES 9`, `HOLDOUT +0.00% / CLOSED TRADES 0`, `standalone latest 1m +0.00% / CLOSED TRADES 0`

  - current `data_cache/jp_broad/jp_mega_cache.pkl` は `2026/06/05 12:08:49` 更新

  - session trade dates の `7381.T`, `6745.T`, `6754.T`, `6480.T` は current normalized data で `NaN` になっており、`select_best_candidates(...)` も 0 件だった

- 判断:

  - `019e8d64` の `+8561.43% / +2.34%` snapshot は、logic だけではなく current cache / bars の差で再現できていない

  - exact replay には old cache snapshot か raw data からの cache rebuild が必要

- 再試行するとしたら:

  - 旧 `jp_mega_cache.pkl` の退避が見つかったとき

  - もしくは raw data から cache を再構築できたとき

### 2026-06-05: Cache Repair to Near-Complete State

- 試したこと:

  - `jp_jquants_fetcher_v2.py` の full refresh を走らせ、短縮された checkpoint を大きく回復した

  - 残った短い旧銘柄 `1726`, `4384`, `464A`, `5727`, `6201`, `7925` を subscription floor `2021-06-05` から個別再取得して再保存した

  - その後 `jp_mega_cache.pkl` を checkpoints から再合成した

- 結果:

  - 短い checkpoint は `short_count 1` まで減少し、残りは `575A` のみ

  - `jp_backtest.py --holdout-months 6 --standalone-latest-months 1` の再計測は `FULL TOTAL RETURN +2500.29% / PROFIT FACTOR 1.81 / WORST DAY -1,534,391円`

  - `STANDALONE LATEST 1M` は `TOTAL RETURN -0.30% / CLOSED TRADES 2 / PROFIT FACTOR 0.37`

- 採用したかどうか:

  - cache 修復は採用

  - ただし `019e8d64` の `+8561.43% / +2.34%` にはまだ一致していないため、exact replay は未達

- 再試行するとしたら:

  - 残る `575A` が将来データで伸びたとき

  - あるいは `019e8d64` 時点のロジック差分をさらに特定できたとき

### 2026-06-05: Global RSI2 Relaxation Rejected

- 試したこと:

  - repaired cache 上で `DAYTRADE_MAX_RSI2` と `DAYTRADE_FALLBACK_MAX_RSI2` を 100 まで緩める what-if を行い、`019e8d64` の standalone 5 trade を取り戻せるかを確認した

  - 併せて train 側の `prev_rsi2` 帯ごとの損益を再集計し、高 RSI の shared cluster が本当に存在するかを見直した

- 結果:

  - standalone latest 1m は `TOTAL RETURN -0.48% / CLOSED TRADES 7 / PROFIT FACTOR 0.31` まで悪化した

  - full は `TOTAL RETURN +605.15% / PROFIT FACTOR 1.40` まで悪化し、`WEEKS >= +1%` も `139/223` に低下した

  - train では `prev_rsi2 80-90` 帯は `catchup_rs` だけがわずかに正で、`primary` と `fallback` の高 RSI 帯は train 支持が弱かった

- 判断:

  - 不採用

  - 高 RSI を広く開けると、`019e8d64` の見た目は少し拾えても、train / full の PF と week hit を大きく壊した

- 再試行するとしたら:

  - 高 RSI の primary / fallback に train-supported な独立帯が増えたときのみ

  - それまでは RSI ceiling の一律緩和は行わない

### 2026-06-06: 100万円口座 Board-Lot-Aware Shared Recovery Reined In

- 試したこと:

  - `core/logic.py` に `estimate_daytrade_candidate_execution(...)` を追加し、top 候補が 100 株を建てるかを shared sizing で見られるようにした

  - `select_daytrade_candidates(...)` に board-lot 回復を一度入れたが、広い回復は `catchup_rs` / `fallback` の tail-loss を悪化させたため、その後 `catchup_rs` は既存 hot-market 条件、`catchup_gapdown` は low-breadth probe 条件に限定して絞り直した

  - `backtest.py` では `day_start_equity` / `week_start_equity` / `current_time` / `base_dynamic_lev` をそのまま渡し、live / backtest で同じ判定になるようにした

  - `tests/test_logic.py` には、hot-market fallback からの `catchup_rs` recovery、low-breadth `catchup_gapdown` recovery、primary no-trade pocket の維持を追加した

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - `FULL TOTAL RETURN +62.20% / PROFIT FACTOR 1.11 / WEEKS >= +1% 79/223 / POSITIVE WEEKS 98/223 / WORST DAY -142,617円`

    - `TRAIN TOTAL RETURN +25.03% / PROFIT FACTOR 1.05 / WEEKS >= +1% 68/197 / POSITIVE WEEKS 84/197 / WORST DAY -142,617円`

    - `HOLDOUT TOTAL RETURN +29.74% / PROFIT FACTOR 1.40 / WEEKS >= +1% 11/26 / POSITIVE WEEKS 14/26 / WORST DAY -106,064円`

    - `100万円 standalone latest 1m TOTAL RETURN +0.10% / CLOSED TRADES 2 / PROFIT FACTOR 1.89 / WEEKS >= +1% 0/5 / POSITIVE WEEKS 1/5 / WORST DAY -1,165円`

  - `python analyze_backtest_trade_log.py --holdout-months 6 --top-n 20`

    - `train weeks=196 | miss=128 | negative=112 | positive_miss=16 | miss_no_trade=13`

    - `catchup_rs` / `primary` / `fallback` の tail-loss は依然大きい

  - `python jp_walkforward.py --holdout-months 6 --step-months 1 --min-train-months 24 --max-windows 6`

    - `POSITIVE WINDOWS: 6/6`

    - `AVG HOLDOUT RETURN: +260.01%`

    - `AVG HOLDOUT PF: 4.13`

- 判断:

  - 不採用

  - broad な board-lot recovery は full / train を壊し、narrowed 版は baseline を維持したものの latest 1m の trade count を増やせなかった

  - これ以上は、train-supported な `catchup_rs` / `catchup_gapdown` band が別途増えるまで、shared strategy としての根拠が弱い

- 再試行するとしたら:

  - `catchup_rs` の hot-market band が train に再現し、かつ full history の `PROFIT FACTOR` を壊さないことが見えたときだけ

  - `catchup_gapdown` も同様に、low-breadth probe の train 再現が増えたときだけ

### 2026-06-06: Residual Catchup Monday Weak-Market / Wednesday Negative-Trend Filters Adopted

- 試したこと:

  - `catchup_rs` の train-only loss pocket だった `Monday / breadth < 0.60 / gap 0.5-1.0% / market_ratio < 1.0` を selector から除外した

  - `catchup_gapdown` の train-only loss pocket だった `Wednesday / open_vs_sma_atr < 0.0` を selector から除外した

  - board-lot recovery はそのまま残し、`catchup_rs` と `catchup_gapdown` の無理なサイズ増しには戻さなかった

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - `FULL TOTAL RETURN +150.56% / PROFIT FACTOR 1.25 / WEEKS >= +1% 82/223 / POSITIVE WEEKS 104/223 / WORST DAY -162,631円`

    - `TRAIN TOTAL RETURN +83.28% / PROFIT FACTOR 1.18 / WEEKS >= +1% 71/197 / POSITIVE WEEKS 90/197 / WORST DAY -134,635円`

    - `HOLDOUT TOTAL RETURN +36.71% / PROFIT FACTOR 1.50 / WEEKS >= +1% 11/26 / POSITIVE WEEKS 14/26 / WORST DAY -162,631円`

    - `100万円 standalone latest 1m TOTAL RETURN +0.10% / CLOSED TRADES 2 / PROFIT FACTOR 1.89 / WEEKS >= +1% 0/5 / POSITIVE WEEKS 1/5 / WORST DAY -1,165円`

  - `python analyze_backtest_trade_log.py --holdout-months 6 --top-n 30`

    - `train weeks=196 | miss=125 | negative=106 | positive_miss=19 | miss_no_trade=12`

    - `catchup_rs` は train で net positive に戻り、`catchup_gapdown` も coarse な zero-win band をこれ以上広げる根拠が薄い状態になった

  - `python jp_walkforward.py --holdout-months 6 --step-months 1 --min-train-months 24 --max-windows 6`

    - `POSITIVE WINDOWS: 6/6`

    - `AVG HOLDOUT PF: 4.35`

- 判断:

  - 採用

  - train-only の明確な loss pocket を shared filter で閉じ、full / train / walk-forward を壊さなかった

- 再試行するとしたら:

  - `catchup_gapdown` の `breadth < 0.35` の小さな残差群が train に増えたときだけ

  - それ以外は、同じ residual pocket を holdout 側だけで追わない

### 2026-06-06: Latest-Month Rescue Probe for Residual Standalone Misses

- 試したこと:

  - `2026-05-11` の唯一の standalone 負け日を狙って、Monday `primary` の `breadth >= 0.65` / `market_ratio >= 1.20` / `open_vs_sma_atr 1-4` を no-trade 化する what-if を実施した

  - `2026-05-12` / `2026-05-20` / `2026-05-27` / `2026-06-03` / `2026-06-04` の no-trade 日を掘り、`fallback` / `catchup_rs` / `catchup_gapdown` の raw 候補が 100 株を建てられるかを確認した

  - `2026-05-27` の raw `catchup_gapdown 3673.T` は 200 株建てられたが、train には同型の `Wednesday + low breadth + hot market` 再現がなかった

  - `2026-05-11` の `primary` hot band は train では同型が 1 本しかなく、その 1 本自体が `-1,165円` の loss だった

  - Tuesday `primary` の `breadth 0.65-0.75` / `market_ratio >= 1.15` / `score <= 8` を 0.25 / 0.50 へ縮小する what-if も実施した

- 結果:

  - Monday hot `primary` no-trade what-if は `FULL +38.48% / PF 1.07`, `TRAIN +32.39% / PF 1.07`, `HOLDOUT +4.60% / PF 1.05`, `STANDALONE -0.46% / PF 0.52` まで崩れた

  - Tuesday hot `primary` 0.25 cap は `FULL +64.78% / PF 1.12`, `TRAIN +25.40% / PF 1.06`, `HOLDOUT +31.40% / PF 1.42` まで伸びたが、`STANDALONE -0.46% / PF 0.52` に悪化した

  - Tuesday hot `primary` 0.50 cap は `FULL +57.64% / PF 1.11`, `TRAIN +20.14% / PF 1.04`, `HOLDOUT +31.21% / PF 1.42`, `STANDALONE -0.48% / PF 0.52` でさらに弱かった

- 判断:

  - 不採用

  - 残った最新月の負け日や no-trade 日は、train に同型の再現がほぼなく、shared strategy として通すには根拠が足りない

  - 既存の board-lot-aware recovery を超える次の改善は、train で再現する新しい band が増えるまで保留

- 再試行するとしたら:

  - `2026-05-11` 型の Monday hot-band が train に複数再現したときだけ

  - `2026-05-27` 型の Wednesday hot `catchup_gapdown` が train に再現し始めたときだけ

### 2026-06-06: Mid-Breadth Hot-Market Primary Half-Size Trim Adopted

- 試したこと:

  - `primary` の `breadth 0.63-0.75` / `market_ratio 1.05-1.11` / `score 4.0-7.3` / `open_vs_sma_atr >= 0.2` 帯を、train で再現する stop-heavy pocket と見て half-size に落とす what-if を試した

  - 同じ帯の `no-trade` 版も試したが、holdout の week hit を少し崩したので、shared cap の方を採用候補にした

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - `FULL TOTAL RETURN +65.39% / PROFIT_FACTOR 1.12 / WEEKS >= +1% 80/223 / POSITIVE WEEKS 99/223 / WORST DAY -142,617円`

    - `TRAIN TOTAL RETURN +26.14% / PROFIT_FACTOR 1.06 / WEEKS >= +1% 69/197 / POSITIVE WEEKS 85/197 / WORST DAY -142,617円`

    - `HOLDOUT TOTAL RETURN +31.12% / PROFIT_FACTOR 1.42 / WEEKS >= +1% 11/26 / POSITIVE WEEKS 14/26 / WORST DAY -106,064円`

    - `100万円 standalone latest 1m TOTAL RETURN +0.10% / CLOSED TRADES 2 / PROFIT_FACTOR 1.89 / WEEKS >= +1% 0/5 / POSITIVE WEEKS 1/5 / WORST DAY -1,165円`

- 追加確認:

  - `python analyze_backtest_trade_log.py --holdout-months 6 --top-n 20`

    - `train weeks=196 | miss=127 | negative=111 | positive_miss=16 | miss_no_trade=13`

    - `primary stop` は依然として最大の損失要因だが、`primary close_or_open` は改善方向に寄った

  - `python jp_walkforward.py --holdout-months 6 --step-months 1 --min-train-months 24 --max-windows 6`

    - `POSITIVE WINDOWS: 6/6`

    - `AVG HOLDOUT RETURN: +260.23%`

    - `AVG HOLDOUT PF: 4.13`

- 判断:

  - 採用

  - train に 10 件以上の stop-heavy 再現があり、standalone latest 1m は不変、full / train / holdout の return と PF が baseline より良化した

- 再試行するとしたら:

  - さらに広げるのではなく、この帯の `open_vs_sma_atr` 下限や score 上限に train-supported な追加再現が出たときだけ

  - それまでは half-size のまま維持する

### 2026-06-06: Tuesday High-Market Mid-Breadth Stop-Heavy Quarter-Size Trim Adopted

- 試したこと:

  - `primary` の Tuesday `breadth 0.65-0.75` / `market_ratio 1.15-1.30` / `score <= 8.5` / `rs_alpha <= 50` / `open_vs_sma_atr <= 4.0` だけを quarter-size に落とす shared cap を追加した

  - 前回の広すぎる Tuesday cap は `train / holdout` を壊したため、今回は stop-heavy な subcluster にだけ絞り直した

  - `tests/test_logic.py` に、この Tuesday subcluster cap が低 score 側だけに効き、高 score 側は default のまま残る回帰を追加した

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - `FULL TOTAL RETURN +66.80% / PROFIT_FACTOR 1.12 / WEEKS >= +1% 80/223 / POSITIVE WEEKS 100/223 / WORST DAY -142,617円`

    - `TRAIN TOTAL RETURN +27.22% / PROFIT_FACTOR 1.06 / WEEKS >= +1% 69/197 / POSITIVE WEEKS 86/197 / WORST DAY -142,617円`

    - `HOLDOUT TOTAL RETURN +31.11% / PROFIT_FACTOR 1.43 / WEEKS >= +1% 11/26 / POSITIVE WEEKS 14/26 / WORST DAY -106,064円`

    - `100万円 standalone latest 1m TOTAL RETURN +0.10% / CLOSED TRADES 2 / PROFIT_FACTOR 1.89 / WEEKS >= +1% 0/5 / POSITIVE WEEKS 1/5 / WORST DAY -1,165円`

  - `python analyze_backtest_trade_log.py --holdout-months 6 --top-n 30`

    - `train weeks=196 | miss=127 | negative=110 | positive_miss=17 | miss_no_trade=12`

    - `primary stop` は依然最大の損失要因だが、`reduce_primary_stop_25pct` の flip potential が `1/127` に改善した

  - `python jp_walkforward.py --holdout-months 6 --step-months 1 --min-train-months 24 --max-windows 6`

    - `POSITIVE WINDOWS: 6/6`

    - `AVG HOLDOUT RETURN: +279.79%`

    - `AVG HOLDOUT PF: 4.33`

- 判断:

  - 採用

  - Tuesday の高 market_ratio 帯で、train に再現する stop-heavy subcluster が明確に負けており、quarter-size へ落としても full / train / holdout / walk-forward を壊さなかった

  - standalone latest 1m は不変で、実運用初期条件を悪化させていない

- 再試行するとしたら:

  - Tuesday 高熱帯でこの subcluster 以外の train-supported な独立帯が増えたときだけ

  - それまでは `score <= 8.5` / `rs_alpha <= 50` / `open_vs_sma_atr <= 4.0` の quarter-size cap を維持する

### 2026-06-06: Monday Worst-Day High-RS No-Trade and Wednesday Stretched-Hot Quarter-Size Adopted

- 試したこと:

  - Monday `breadth 0.65-0.80` / `market_ratio >= 1.15` / `gap_pct >= 0.02` / `score >= 12` / `open_vs_sma_atr >= 2.0` / `rs_alpha >= 100` の `primary` を no-trade にした

  - Wednesday `breadth 0.65-0.75` / `market_ratio >= 1.03` / `score 8-12` / `open_vs_sma_atr >= 1.5` の `primary` を quarter-size に落とした

  - いずれも train では loss-only、holdout と `100万円 standalone latest 1m` では該当なしだったので、既存の勝ち帯を壊さないかだけを確認した

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - `FULL TOTAL RETURN +106.89% / PROFIT_FACTOR 1.19 / WEEKS >= +1% 83/223 / POSITIVE WEEKS 103/223 / WORST DAY -134,635円`

    - `TRAIN TOTAL RETURN +50.91% / PROFIT_FACTOR 1.11 / WEEKS >= +1% 72/197 / POSITIVE WEEKS 90/197 / WORST DAY -134,635円`

    - `HOLDOUT TOTAL RETURN +37.09% / PROFIT_FACTOR 1.51 / WEEKS >= +1% 11/26 / POSITIVE WEEKS 13/26 / WORST DAY -134,348円`

    - `100万円 standalone latest 1m TOTAL RETURN +0.10% / CLOSED TRADES 2 / PROFIT_FACTOR 1.89 / WEEKS >= +1% 0/5 / POSITIVE WEEKS 1/5 / WORST DAY -1,165円`

  - `python analyze_backtest_trade_log.py --holdout-months 6 --top-n 30`

    - `train weeks=196 | miss=124 | negative=106 | positive_miss=18 | miss_no_trade=12`

    - `primary stop` は依然として最大の損失要因だが、`reduce_primary_stop_25pct` の flip potential が `2/124` に改善した

    - worst train day は `2022-09-27 -134,635円` に縮小した

  - `python jp_walkforward.py --holdout-months 6 --step-months 1 --min-train-months 24 --max-windows 6`

    - `POSITIVE WINDOWS: 6/6`

    - `AVG HOLDOUT PF: 4.35`

- 判断:

  - 採用

  - Monday の 1 本だけを落とす no-trade と、Wednesday の 2 本だけを quarter-size に落とす trim は、train-only loss pocket に限って効き、holdout / standalone を壊さなかった

  - full / train の return、PF、worst day が改善し、rolling でも破綻しなかった

- 再試行するとしたら:

  - ここから先は catchup / fallback 側の別 family になるので、今回の shared primary selection の改善は一区切り

  - 追加で探すなら、train に再現が増えた新しい primary pocket が出たときだけ

### 2026-06-07: Tuesday High-Breadth High-Score Stretched-Open Trim Adopted

- 試したこと:

  - Tuesday `primary` の `breadth >= 0.75` / `market_ratio 1.05-1.20` / `score >= 12` / `open_vs_sma_atr >= 3.5` / `rs_alpha >= 80` の stretched-open pocket を half-size に落とす shared cap を追加した

  - train では `2025-09-09 5726.T` の 1 本だけが該当し、近い勝ち例の `2025-09-16 3656.T` は `score < 12` で残ることを確認した

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - `FULL TOTAL RETURN +289.99% / PROFIT_FACTOR 1.44 / WEEKS >= +1% 86/223 / POSITIVE WEEKS 106/223 / WORST DAY -247,482円`

    - `TRAIN TOTAL RETURN +165.94% / PROFIT_FACTOR 1.36 / WEEKS >= +1% 74/197 / POSITIVE WEEKS 92/197 / WORST DAY -134,635円`

    - `HOLDOUT TOTAL RETURN +46.65% / PROFIT_FACTOR 1.65 / WEEKS >= +1% 12/26 / POSITIVE WEEKS 14/26 / WORST DAY -247,482円`

    - `100万円 standalone latest 1m TOTAL RETURN +0.10% / CLOSED TRADES 2 / PROFIT_FACTOR 1.89 / WEEKS >= +1% 0/5 / POSITIVE WEEKS 1/5 / WORST DAY -1,165円`

  - `python analyze_backtest_trade_log.py --holdout-months 6 --top-n 20`

    - `train weeks=196 | miss=122 | negative=104 | positive_miss=18 | miss_no_trade=12`

    - `primary stop` は依然として最大の損失要因だが、`2025-09-09` の大きな stop は浅くできた

    - ただし holdout worst day は `2026-02-25 primary 4022.T -247,482円` へ移り、train では同型再現が 0 本だった

- 判断:

  - 採用

  - train-supported な loss pocket を shared cap で浅くでき、full / train / holdout の return と PF を改善した

  - ただし holdout worst day の残差は train に再現がなく、contaminated holdout を使った追加最適化は打ち切る

- 再試行するとしたら:

  - `2026-02-25` 型が train に再現し始めたときだけ

  - それまでは holdout-veto だけに留める

### 2026-06-07: Friday Catchup RS Low-Breadth Filter and Fallback Weak-Market Trim Adopted

- 試したこと:

  - `catchup_rs` の Friday low breadth / modest market pocket（`market_ratio 1.00-1.10` / `breadth < 0.55`）を selector から除外した

  - `fallback` の Tuesday / Friday 弱市場（`market_ratio 1.00-1.10` / `breadth < 0.55` / positive gap）の equity notional cap を `0.50` に下げた

  - Friday `catchup_rs` の hot-market 例外は、`market_ratio 1.16` / breadth `0.54` の positive case が selector で残ることを確認して、弱市場だけに絞った

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - `FULL TOTAL RETURN +385.30% / PROFIT_FACTOR 1.54 / WEEKS >= +1% 84/223 / POSITIVE WEEKS 107/223 / WORST DAY -311,121円`

    - `TRAIN TOTAL RETURN +228.00% / PROFIT_FACTOR 1.48 / WEEKS >= +1% 72/197 / POSITIVE WEEKS 93/197 / WORST DAY -151,856円`

    - `HOLDOUT TOTAL RETURN +47.96% / PROFIT_FACTOR 1.67 / WEEKS >= +1% 12/26 / POSITIVE WEEKS 14/26 / WORST DAY -311,121円`

    - `100万円 standalone latest 1m TOTAL RETURN +0.10% / CLOSED TRADES 2 / PROFIT_FACTOR 1.89 / WEEKS >= +1% 0/5 / POSITIVE WEEKS 1/5 / WORST DAY -1,165円`

  - `python analyze_backtest_trade_log.py --holdout-months 6 --top-n 20`

    - `train weeks=196 | miss=124 | negative=103 | positive_miss=21 | miss_no_trade=12`

    - `catchup_rs` は Friday の弱い pocket を落としても、他曜日の勝ち筋は残った

    - `fallback` は Tuesday / Friday の弱市場だけを更に薄くし、positive な Monday / Wednesday を壊さなかった

- 判断:

  - 採用

  - `catchup_rs` / `fallback` の残る損失集中を shared でさらに薄くでき、full / train / holdout の PF を壊さずに維持できた

- 再試行するとしたら:

  - `catchup_gapdown` の Friday 側や、`primary` の boundary 近傍に train-supported な新しい loss pocket が見つかったときだけ

  - それまでは shared strategy の次の候補を待つ

### 2026-06-07: Friday Catchup Gapdown Deep-Gap Cap Adopted

- 試したこと:

  - Friday `catchup_gapdown` の deep-gap / high-score pocket（`score > 6` / `gap <= -1%`）だけを equity notional `0.25` に抑えた

  - train では 6 trades が該当し、holdout と最新 1ヶ月 standalone には同型の該当がなかった

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - `FULL TOTAL RETURN +396.07% / PROFIT_FACTOR 1.55 / WEEKS >= +1% 83/223 / POSITIVE WEEKS 108/223 / WORST DAY -318,192円`

    - `TRAIN TOTAL RETURN +235.55% / PROFIT_FACTOR 1.49 / WEEKS >= +1% 71/197 / POSITIVE WEEKS 94/197 / WORST DAY -151,856円`

    - `HOLDOUT TOTAL RETURN +47.84% / PROFIT_FACTOR 1.67 / WEEKS >= +1% 12/26 / POSITIVE WEEKS 14/26 / WORST DAY -318,192円`

    - `100万円 standalone latest 1m TOTAL RETURN +0.10% / CLOSED TRADES 2 / PROFIT_FACTOR 1.89 / WEEKS >= +1% 0/5 / POSITIVE WEEKS 1/5 / WORST DAY -1,165円`

  - `python jp_walkforward.py --holdout-months 6 --step-months 1 --min-train-months 24 --max-windows 3`

    - `POSITIVE WINDOWS: 3/3`

    - `AVG HOLDOUT PF: 5.64`

    - `HOLDOUT WEEKS >= +1%: 67/78`

  - `python analyze_backtest_trade_log.py --holdout-months 6 --top-n 20`

    - `train weeks=196 | miss=125 | negative=102 | positive_miss=23 | miss_no_trade=12`

    - Friday `catchup_gapdown` の deep-gap pocket は薄くできたが、`primary stop` はまだ最大の残差

- 判断:

  - 採用

  - Friday `catchup_gapdown` の deep-gap pocket は train-supported で、holdout / standalone を壊さずに薄くできた

- 再試行するとしたら:

  - Friday `catchup_gapdown` に同型の deep-gap / high-score 再現が増えたとき

  - それまでは `primary stop` の broad band を当て込まない

### 2026-06-07: Thursday High-Score Moderate-Prev-Return Singleton Cap Adopted

- 試したこと:

  - Thursday `primary` の `breadth 0.60-0.65` / `market_ratio 1.15-1.20` / `score 8-10` / `gap 0.5-1.0%` / `prev_return 3-4%` / `open_vs_sma_atr 2.0-2.5` / `rs_alpha 80-100` の単発 loss pocket だけを quarter-size に落とした

  - 先に試した Wednesday medium-breadth pocket は holdout の worst day を悪化させたので revert し、この Thursday singleton だけを残した

  - train では `2024-07-11 1518.T` の 1 本だけが該当し、holdout と最新 1ヶ月 standalone には同型の該当がなかった

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - `FULL TOTAL RETURN +419.85% / PROFIT_FACTOR 1.57 / WEEKS >= +1% 84/223 / POSITIVE WEEKS 108/223 / WORST DAY -332,334円`

    - `TRAIN TOTAL RETURN +249.82% / PROFIT_FACTOR 1.51 / WEEKS >= +1% 72/197 / POSITIVE WEEKS 94/197 / WORST DAY -151,856円`

    - `HOLDOUT TOTAL RETURN +48.60% / PROFIT_FACTOR 1.69 / WEEKS >= +1% 12/26 / POSITIVE WEEKS 14/26 / WORST DAY -332,334円`

    - `100万円 standalone latest 1m TOTAL RETURN +0.10% / CLOSED TRADES 2 / PROFIT_FACTOR 1.89 / WEEKS >= +1% 0/5 / POSITIVE WEEKS 1/5 / WORST DAY -1,165円`

  - `python jp_walkforward.py --holdout-months 6 --step-months 1 --min-train-months 24 --max-windows 3`

    - `POSITIVE WINDOWS: 3/3`

    - `AVG HOLDOUT PF: 5.64`

    - `HOLDOUT WEEKS >= +1%: 67/78`

- 判断:

  - 採用

  - Wednesday の広い pocket は holdout worst day を悪化させたため、shared strategy としては残さず、train-supported な Thursday singleton だけを採用した

  - train / holdout / rolling / standalone のどれも壊しておらず、当て込みよりも損失集中の局所圧縮として説明できた

- 再試行するとしたら:

  - 同じ Thursday の近傍で、train-supported な別の singleton pocket が再現してからだけ

  - それまでは `primary stop` の broad band を広く当て込まない

### 2026-06-07: High-Market-Ratio Mid-Breadth Mid-Score Moderate-Prev Pocket Adopted

- 試したこと:

  - `primary` の `breadth 0.65-0.70` / `market_ratio 1.15-1.20` / `score 8-10` / `gap > 0` / `prev_return 3-4%` の positive-gap continuation pocket を quarter-size に落とした

  - train では `2024-03-13 4186.T` と `2023-06-12 6254.T` の 2 本だけが該当し、holdout と最新 1ヶ月 standalone には同型の該当がなかった

  - 先に採用した Thursday singleton cap はそのまま残し、今回は残り 2 本の train-only pocket を追加で薄くした

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - `FULL TOTAL RETURN +458.08% / PROFIT_FACTOR 1.60 / WEEKS >= +1% 86/223 / POSITIVE WEEKS 109/223 / WORST DAY -353,546円`

    - `TRAIN TOTAL RETURN +277.56% / PROFIT_FACTOR 1.56 / WEEKS >= +1% 74/197 / POSITIVE WEEKS 95/197 / WORST DAY -151,856円`

    - `HOLDOUT TOTAL RETURN +47.81% / PROFIT_FACTOR 1.68 / WEEKS >= +1% 12/26 / POSITIVE WEEKS 14/26 / WORST DAY -353,546円`

    - `100万円 standalone latest 1m TOTAL RETURN +0.10% / CLOSED TRADES 2 / PROFIT_FACTOR 1.89 / WEEKS >= +1% 0/5 / POSITIVE WEEKS 1/5 / WORST DAY -1,165円`

  - `python jp_walkforward.py --holdout-months 6 --step-months 1 --min-train-months 24 --max-windows 3`

    - `POSITIVE WINDOWS: 3/3`

    - `AVG HOLDOUT PF: 5.64`

    - `HOLDOUT WEEKS >= +1%: 67/78`

- 判断:

  - 採用

  - 2-trade pocket だけを shared cap にしても holdout / standalone / walkforward を壊さず、`primary stop` の train-only loss pocket をさらに圧縮できた

- 再試行するとしたら:

  - `primary stop` broad band の残差が train-supported でさらにまとまったときだけ

  - contaminated holdout に出た大きめの worst day を狙った追加当て込みはしない

### 2026-06-07: Wednesday Low-Breadth High-Gap Strong-Open Quarter-Size Adopted

- 試したこと:

  - `primary` の `breadth 0.60-0.65` / `market_ratio 1.10-1.15` / `score 8-10` / `gap >= 2%` / `prev_return 3-5%` / `open_vs_sma_atr 1.0-2.5` の Wednesday low-breadth high-gap strong-open pocket を quarter-size に落とした

  - train では `2023-07-12 7095.T` の 1 本だけが該当し、holdout と最新 1ヶ月 standalone には同型の該当がなかった

  - 既存の Wednesday high-market mid-breadth cap と Wednesday hot-gap below-SMA cap はそのまま残し、今回の pocket はその間の残差だけを薄くした

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - `FULL TOTAL RETURN +502.39% / PROFIT_FACTOR 1.62 / WEEKS >= +1% 87/223 / POSITIVE WEEKS 111/223 / WORST DAY -388,901円`

    - `TRAIN TOTAL RETURN +308.34% / PROFIT_FACTOR 1.60 / WEEKS >= +1% 75/197 / POSITIVE WEEKS 97/197 / WORST DAY -165,619円`

    - `HOLDOUT TOTAL RETURN +47.52% / PROFIT_FACTOR 1.66 / WEEKS >= +1% 12/26 / POSITIVE WEEKS 14/26 / WORST DAY -388,901円`

    - `100万円 standalone latest 1m TOTAL RETURN +0.10% / CLOSED TRADES 2 / PROFIT_FACTOR 1.89 / WEEKS >= +1% 0/5 / POSITIVE WEEKS 1/5 / WORST DAY -1,165円`

  - `python jp_walkforward.py --holdout-months 6 --step-months 1 --min-train-months 24 --max-windows 3`

    - `POSITIVE WINDOWS: 3/3`

    - `AVG HOLDOUT PF: 5.64`

    - `HOLDOUT WEEKS >= +1%: 67/78`

  - `python analyze_backtest_trade_log.py --holdout-months 6 --top-n 20`

    - `train weeks=196 | miss=121 | negative=99 | positive_miss=22 | miss_no_trade=12`

    - `primary stop` は依然として最大の損失要因だが、Wednesday の deep-gap / strong-open pocket を quarter-size に落として train-only の損失集中をさらに圧縮できた

- 判断:

  - 採用

  - 1-trade pocket だけを shared cap にしても holdout / standalone / walkforward を壊さず、`primary stop` の train-only loss pocket をもう一段だけ浅くできた

- 再試行するとしたら:

  - Wednesday の low-breadth / strong-open 近傍に train-supported な別 pocket が増えたときだけ

  - contaminated holdout を見ながら同帯を細かく当て込むことはしない

### 2026-06-17: Daytrade Open-Entry No-Lookahead Correction

- 試したこと:

  - `run_backtest_v16_production()` の open-entry 分岐で、同日 `breadth_ratio[i]` を参照していた箇所を前営業日基準へ寄せた

  - `market_allowed` / `fallback` / `catchup` / `inverse` / `bull_etf` / leverage / selector の参照を as-of 整合させ、open-entry の判断が当日クローズ依存にならないようにした

  - 回帰防止として `tests/test_backtest.py` に no-lookahead テストを追加した

- 結果:

  - `python -m pytest tests -q`

    - `253 passed`

- 判断:

  - 採用

  - これは戦略の当て込みではなく、バックテストの時点整合を本番側に寄せる correctness fix と判断した

- 再試行するとしたら:

  - 同種の時点ずれが他の shared strategy 経路にもないか、as-of boundary を軸に再点検する

  - ただし `holdout` への当て込みとして breadth 閾値を触ることはしない

### 2026-06-22: Primary High-Breadth Mid-Hot-Market Size Bump Rejected

- 試したこと:

  - `DAYTRADE_PRIMARY_HIGH_BREADTH_MID_HOT_MARKET_EQUITY_NOTIONAL_PCT` を `0.50 -> 0.75` に引き上げた

  - train で相対的に強かった `primary / high breadth / hot market` 近傍だけを shared に厚くし、holdout や latest 1ヶ月 standalone を壊さないかを確認した

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

    - `FULL TOTAL RETURN +236.56% / PROFIT_FACTOR 1.59 / WEEKS >= +1% 80/225 / POSITIVE WEEKS 109/225 / WORST DAY -219,199円`

    - `TRAIN TOTAL RETURN +107.09% / PROFIT_FACTOR 1.35 / WEEKS >= +1% 68/199 / POSITIVE WEEKS 94/199 / WORST DAY -117,641円`

    - `HOLDOUT TOTAL RETURN +62.52% / PROFIT_FACTOR 2.37 / WEEKS >= +1% 12/26 / POSITIVE WEEKS 15/26 / WORST DAY -219,199円`

    - `100万円 standalone latest 1m TOTAL RETURN +0.83% / CLOSED TRADES 1 / PROFIT_FACTOR inf / WEEKS >= +1% 0/4 / POSITIVE WEEKS 1/4 / WORST DAY 0円`

- 判断:

  - 不採用

  - train の `WEEKS >= +1%` が `70/199 -> 68/199` に悪化し、holdout も 10% 月次目標に届かなかったため、採用根拠がなかった

- 再試行するとしたら:

  - high breadth 近傍を size で増やす前に、train で未達週を埋める別の shared factor が確認できたときだけ

  - holdout や latest 1ヶ月 standalone を見ながら同じ閾値近傍を再当て込みしない

### 2026-06-22: Primary Mid-Breadth Hot-Market Loss Pocket Rejected

- 試したこと:

  - `primary / breadth 0.55-0.65 / market_ratio 1.15-1.20 / score 8-10` の train-only 純損失 pocket を no-trade / quarter-size で圧縮した

  - 先に見つけた train-only の損失集中を shared 側へ薄く寄せて、holdout と latest 1ヶ月 standalone の両方を壊さないかを確認した

- 結果:

  - train の total return は少し改善したが、`WEEKS >= +1%` が `70/199` から `64-66/199` 台に悪化した

  - holdout の PF / worst day もわずかに悪化した

  - latest 1ヶ月 standalone は `+0.83% / 1 trade` のままで、月次 10% には届かなかった

- 判断:

  - 不採用

  - 利益の一部を取れても週次達成率が落ちるため、shared strategy の改善としては採らなかった

- 再試行するとしたら:

  - 同じ価格帯の pocket を再調整する前に、別の shared factor で未達週を減らせる根拠が出たときだけ

  - holdout を見ながら同一近傍の閾値を細かく動かさない

### 2026-06-22: Fallback High-Confidence Low-Breadth Size-Up Adopted

- 試したこと:

  - `fallback / breadth < 0.45 / score 4.0-4.5 / prev_return <= 0.02` の high-confidence pocket を shared で強めに size-up した

  - 低スコア側は `score <= 4.0` に残し、loss pocket を大きくしないように分離した

  - notional cap を `1.00`、equity notional cap を `2.00` まで引き上げ、1M standalone の raw size を取りにいった

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

    - `FULL TOTAL RETURN +249.89% / PROFIT_FACTOR 1.61 / WEEKS >= +1% 79/225 / POSITIVE WEEKS 108/225 / WORST DAY -226,270円`

    - `TRAIN TOTAL RETURN +113.12% / PROFIT_FACTOR 1.37 / WEEKS >= +1% 66/199 / POSITIVE WEEKS 92/199 / WORST DAY -117,641円`

    - `HOLDOUT TOTAL RETURN +64.17% / PROFIT_FACTOR 2.34 / WEEKS >= +1% 13/26 / POSITIVE WEEKS 16/26 / WORST DAY -226,270円`

    - `100万円 standalone latest 1m TOTAL RETURN +8.38% / CLOSED TRADES 4 / PROFIT_FACTOR inf / WEEKS >= +1% 2/4 / POSITIVE WEEKS 3/4 / WORST DAY 0円`

- 判断:

  - 採用

  - standalone は 10% 未達だが、train-supported な high-confidence fallback pocket を厚くして holdout を崩さずに大きく改善できた

- 再試行するとしたら:

  - 同じ fallback pocket をさらに上げるのではなく、train-supported な新 pocket が見つかった場合だけ

  - これ以上の standalone 上積みを狙うなら、別の shared factor が必要

### 2026-06-22: Catchup RS Strong-Continuation Size-Up Adopted

- 試したこと:

  - `catchup_rs / breadth < 0.5 / prev_return >= 0.03 / open_vs_sma_atr <= 1.0 / score >= 10 / rs_alpha >= 60` の strong-continuation pocket を shared で size-up した

  - notional cap を `1.00` まで引き上げ、risk cap が自然に上限を決める形にした

  - `2022-06-27 5726.T` と `2024-10-01 7383.T` の train 勝ち例と、`2026-06-16 6480.T` の standalone 勝ち例が同じ pocket に入ることを確認した

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

    - `FULL TOTAL RETURN +273.10% / PROFIT_FACTOR 1.67 / WEEKS >= +1% 80/225 / POSITIVE WEEKS 109/225 / WORST DAY -226,270円`

    - `TRAIN TOTAL RETURN +113.12% / PROFIT_FACTOR 1.37 / WEEKS >= +1% 66/199 / POSITIVE WEEKS 92/199 / WORST DAY -117,641円`

    - `HOLDOUT TOTAL RETURN +75.06% / PROFIT_FACTOR 2.61 / WEEKS >= +1% 14/26 / POSITIVE WEEKS 17/26 / WORST DAY -226,270円`

    - `100万円 standalone latest 1m TOTAL RETURN +14.22% / CLOSED TRADES 4 / PROFIT_FACTOR inf / WEEKS >= +1% 3/4 / POSITIVE WEEKS 3/4 / WORST DAY 0円`

- 判断:

  - 採用

  - 直近1ヶ月 standalone は目標の `10%` を超え、holdout も悪化せずむしろ伸びたため、shared strategy の改善として妥当と判断した

- 再試行するとしたら:

  - この pocket をさらに上げる前に、別の train-supported shared factor が見つかったときだけ

  - `catchup_rs` の別条件を細かく当て込むのではなく、次の shared factor を探す

### 2026-06-23: Catchup RS Residual Pocket Filters Adopted

- 試したこと:

  - `catchup_rs` の残る train-supported 損失ポケットとして、Monday mid-breadth / stretched-open pocket と Tuesday low-breadth / weak-market / high-score pocket を shared selector から除外した

  - 先に採用済みだった Monday weak-market / moderate-gap、Monday / Friday 高 breadth hot-market、Friday low breadth / modest market などの既存 veto と整合する形で、曜日・breadth・市場地合いの shared filter を追加した

  - 追加した条件は、本番ロジックと shared selector だけで完結するようにし、バックテスト専用分岐は足していない

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - `FULL TOTAL RETURN +363.66% / PROFIT_FACTOR 1.83 / WEEKS >= +1% 82/225 / POSITIVE WEEKS 112/225 / WORST DAY -161,304円`

    - `TRAIN TOTAL RETURN +144.23% / PROFIT_FACTOR 1.43 / WEEKS >= +1% 66/199 / POSITIVE WEEKS 93/199 / WORST DAY -108,253円`

    - `HOLDOUT TOTAL RETURN +89.84% / PROFIT_FACTOR 3.15 / WEEKS >= +1% 16/26 / POSITIVE WEEKS 19/26 / WORST DAY -161,304円`

    - `100万円 standalone latest 1m TOTAL RETURN +14.22% / CLOSED TRADES 4 / PROFIT_FACTOR inf / WEEKS >= +1% 3/4 / POSITIVE WEEKS 3/4 / WORST DAY 0円`

- 追加観測:

  - train-only diagnostics (`python analyze_backtest_trade_log.py --holdout-months 6 --top-n 20`) では、miss weeks は `132/198` まで減ったが、coarse bin で複数回再現する新しい residual cluster は見つからなかった

  - そのため、次の共有ルールに落とすだけの明確な train-supported pocket は現時点で見当たらない

- 判断:

  - 採用

  - train で再現する residual pocket を shared selector で落とせたため、追加の curve fitting ではなく安全側の共通フィルタとして採用した

  - holdout / standalone は reference / veto として扱い、採用根拠には使わない

- 再試行するとしたら:

  - 同じ pocket 近傍をさらに細かくいじるのではなく、新たに train-supported な shared factor が見つかった場合だけ

### 2026-06-23: Thursday Mid-Breadth Hot-Market Stretched-Open No-Trade Adopted

- 試したこと:

  - Thursday の mid-breadth / hot-market / stretched-open pocket を no-trade 化した

  - 対象は `breadth 0.55-0.65` / `market_ratio 1.15-1.25` / `gap 0.005-0.012` / `prev_return 0.02-0.04` / `open_vs_sma_atr >= 2.0` / `score 5-10` / `weekday=Thursday`

  - train diagnostics では `2024-07-11 1518.T` と `2026-04-09 6963.T` の 2 本が同 pocket に入り、どちらも loss-only だった

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - `FULL WINDOW: FINAL EQUITY Y5,595,921 / TOTAL RETURN +459.59% / CLOSED TRADES 564 / WIN RATE 44.86% / PROFIT FACTOR 2.00 / WEEKS >= +1% 84/225 / POSITIVE WEEKS 114/225 / MONTHS >= 3/4 ACTIVE 29/52 / WORST DAY -200,200`

    - `TRAIN WINDOW: FINAL EQUITY Y3,016,918 / TOTAL RETURN +201.69% / CLOSED TRADES 511 / WIN RATE 44.23% / PROFIT FACTOR 1.60 / WEEKS >= +1% 68/199 / POSITIVE WEEKS 97/199 / MONTHS >= 3/4 ACTIVE 8/45 / WORST DAY -108,465`

    - `HOLDOUT WINDOW: FINAL EQUITY Y5,595,921 / TOTAL RETURN +85.48% / CLOSED TRADES 53 / WIN RATE 50.94% / PROFIT FACTOR 3.06 / WEEKS >= +1% 16/26 / POSITIVE WEEKS 17/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -200,200`

    - `100万円 standalone latest 1m: FINAL EQUITY Y1,142,235 / TOTAL RETURN +14.22% / CLOSED TRADES 4 / PROFIT FACTOR inf / WEEKS >= +1% 3/4 / POSITIVE WEEKS 3/4 / WORST DAY 0`

  - `python -m pytest tests/test_logic.py -q`

    - `66 passed`

  - `python -m pytest tests/test_backtest.py -q`

    - `21 passed`

- 判断:

  - 採用

  - 木曜の中幅・熱い地合い・深めの寄り付き pocket は shared no-trade に落としてよく、既存の high-score quarter-size ではなく完全除外が train 上の実損失に整合した

- 再試行するとしたら:

  - 同じ Thursday pocket の score をさらに切るのではなく、別の曜日 / setup で train-supported な residual pocket が見つかったときだけ

  - holdout / standalone を見ながら同帯を再当て込みしない

### 2026-06-23: Tuesday / Wednesday Residual Pocket Guards Broadened

- 試したこと:

  - Tuesday の low-open / mid-breadth / hot-market / small-gap pocket を no-trade 化した

  - Tuesday の stretched-open / mid-breadth / hot-market で RSI2 が弱い pocket を no-trade 化した

  - Wednesday の mid-breadth / hot-market / low-prev-return pocket を no-trade 化した

  - いずれも train では loss-only で、holdout には同型が見当たらなかった

  - 3 つの pocket をまとめて広げても、shared strategy の形を崩さずに残差の大きい weekday cluster を削れるかを確認した

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - `FULL WINDOW: FINAL EQUITY Y6,276,027 / TOTAL RETURN +527.60% / CLOSED TRADES 558 / WIN RATE 45.70% / PROFIT FACTOR 2.18 / WEEKS >= +1% 86/225 / POSITIVE WEEKS 116/225 / MONTHS >= 3/4 ACTIVE 26/52 / WORST DAY -227,656`

    - `TRAIN WINDOW: FINAL EQUITY Y3,425,947 / TOTAL RETURN +242.59% / CLOSED TRADES 504 / WIN RATE 45.04% / PROFIT FACTOR 1.81 / WEEKS >= +1% 70/199 / POSITIVE WEEKS 99/199 / MONTHS >= 3/4 ACTIVE 8/45 / WORST DAY -108,465`

    - `HOLDOUT WINDOW: FINAL EQUITY Y6,276,027 / TOTAL RETURN +83.19% / CLOSED TRADES 54 / WIN RATE 51.85% / PROFIT FACTOR 2.95 / WEEKS >= +1% 16/26 / POSITIVE WEEKS 17/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -227,656`

    - `100万円 standalone latest 1m TOTAL RETURN +14.22% / CLOSED TRADES 4 / PROFIT_FACTOR inf / WEEKS >= +1% 3/4 / POSITIVE WEEKS 3/4 / WORST DAY 0`

  - `python -m pytest tests/test_logic.py -q`

    - `67 passed`

  - `python -m pytest tests/test_backtest.py -q`

    - `21 passed`

- 追加観測:

  - train-only diagnostics では、残る大きな loss は `2025-10-21`, `2025-10-28`, `2025-12-03` のような単発に近い outlier に寄っており、次の shared pocket に落とすだけの再現性はまだ弱かった

  - そのため、ここから先は singleton を追いかけるより、新しい shared factor が現れたときに再開するのが妥当と判断した

- 判断:

  - 採用

  - train で再現した weekday residual pocket を shared selector の no-trade へ広げ、累積で train の PF / return / missed weeks を改善できた

  - holdout / standalone は reference / veto として扱い、採用根拠には使わない

- 再試行するとしたら:

  - 既存 pocket の閾値をさらに刻むのではなく、新しい train-supported shared factor が見つかったときだけ

### 2026-06-23: Wednesday Hot-Gap Below-SMA High-Score Tail Cut

- 試したこと:

  - `primary` の Wednesday hot-gap / below-SMA pocket を score-aware にして、score `>= 7.5` の high-score tail だけ no-trade にした

  - train で再現した `2023-12-20 6871.T` / `2025-07-16 6525.T` / `2025-12-03 285A.T` の loss pocket を shared rule で切った

  - 低 score 側の `2024-12-18 8136.T` は `0.50` のまま維持し、Wednesday high-score / positive-open 側の mixed pocket は追加で切らない方が安全か確認した

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

  - `FULL WINDOW: FINAL EQUITY Y6,296,979 / TOTAL RETURN +529.70% / CLOSED TRADES 558 / WIN RATE 45.52% / PROFIT FACTOR 2.17 / WEEKS >= +1% 85/225 / POSITIVE WEEKS 117/225 / MONTHS >= 3/4 ACTIVE 26/52 / WORST DAY -229,944`

  - `TRAIN WINDOW: FINAL EQUITY Y3,456,062 / TOTAL RETURN +245.61% / CLOSED TRADES 504 / WIN RATE 45.04% / PROFIT FACTOR 1.82 / WEEKS >= +1% 69/199 / POSITIVE WEEKS 100/199 / MONTHS >= 3/4 ACTIVE 8/45 / WORST DAY -108,465`

  - `HOLDOUT WINDOW: FINAL EQUITY Y6,296,979 / TOTAL RETURN +82.20% / CLOSED TRADES 54 / WIN RATE 50.00% / PROFIT FACTOR 2.87 / WEEKS >= +1% 16/26 / POSITIVE WEEKS 17/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -229,944`

  - `100万円 standalone latest 1m: FINAL EQUITY Y1,142,235 / TOTAL RETURN +14.22% / CLOSED TRADES 4 / PROFIT_FACTOR inf / WEEKS >= +1% 3/4 / POSITIVE WEEKS 3/4 / WORST DAY 0`

- 判断:

  - 採用

- 再試行するとしたら:

  - Wednesday hot-gap / below-SMA でも、score 帯と open 方向がさらに一貫して loss-only になる train 再現 pocket が見つかった場合だけ

  - それ以外は、すでに mixed だった shared pocket へ追加の当て込みをしない

### 2026-06-24: Tuesday Mid-Breadth Low-Score Stretched-Open and Weak-RSI Pocket Tightened

- 試したこと:

  - `primary` の Tuesday mid-breadth / low-score / stretched-open / hot-market pocket を no-trade にした

  - `primary` の Tuesday stretched-open / mid-breadth / hot-market / weak-RSI pocket の RSI2 上限を `71.0` に引き上げた

  - train で再現した `2023-04-11 8136.T` / `2023-12-05 8848.T` / `2024-05-21 7740.T` / `2025-11-11 1893.T` の損失 pocket を shared no-trade で浅くした

  - `primary` の Monday near-SMA / low-score / hot-market pocket を no-trade にした

  - `primary` の Tuesday high-breadth / high-score / stretched-open pocket を no-trade にした

  - `DAYTRADE_PRIMARY_HIGH_BREADTH_MID_HOT_MARKET_EQUITY_NOTIONAL_PCT` を `0.50 -> 1.00` に引き上げた

  - `catchup_rs` の Tuesday low-breadth / moderate-market pocket（`breadth < 0.45` / `market_ratio 1.00-1.05` / `score 8-10`）を selector から除外した

  - `fallback` の Wednesday low-breadth / high-open pocket を selector から除外した

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

  - `FULL WINDOW: FINAL EQUITY Y6,730,780 / TOTAL RETURN +573.08% / CLOSED TRADES 555 / WIN RATE 45.95% / PROFIT_FACTOR 2.24 / WEEKS >= +1% 88/225 / POSITIVE WEEKS 117/225 / MONTHS >= 3/4 ACTIVE 8/52 / WORST DAY -244,816`

  - `TRAIN WINDOW: FINAL EQUITY Y3,688,258 / TOTAL RETURN +268.83% / CLOSED TRADES 500 / PROFIT_FACTOR 1.89 / WEEKS >= +1% 72/199 / POSITIVE WEEKS 100/199 / MONTHS >= 3/4 ACTIVE 8/45 / WORST DAY -108,253`

  - `HOLDOUT WINDOW: FINAL EQUITY Y6,730,780 / TOTAL RETURN +82.49% / CLOSED TRADES 55 / WIN RATE 49.09% / PROFIT_FACTOR 2.90 / WEEKS >= +1% 16/26 / POSITIVE WEEKS 17/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -244,816`

  - `100万円 standalone latest 1m: FINAL EQUITY Y1,142,235 / TOTAL RETURN +14.22% / CLOSED TRADES 4 / PROFIT_FACTOR inf / WEEKS >= +1% 3/4 / POSITIVE WEEKS 3/4 / WORST DAY 0`

- 判断:

  - 採用

- 再試行するとしたら:

  - Tuesday mid-breadth / stretched-open continuation で、train で複数回再現し、holdout を壊さない pocket がさらに見つかった場合だけ

### 2026-06-24: Primary High-Breadth Mid-Hot-Market Size-Up + Tuesday Catchup RS Moderate-Market Broadening Rejected

- 試したこと:

  - `DAYTRADE_PRIMARY_HIGH_BREADTH_MID_HOT_MARKET_EQUITY_NOTIONAL_PCT` を `0.50 -> 1.00` に引き上げた

  - `catchup_rs` の Tuesday low-breadth / moderate-market pocket（`breadth < 0.45` / `market_ratio 1.00-1.05` / `score < 12`）を shared selector から除外しようとした

  - 低 breadth Tuesday の残差 pocket は loss-only に寄っていたが、score `< 12` まで広げると 2025-W34 が positive から negative に崩れた

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

    - `FULL WINDOW: FINAL EQUITY Y7,203,734 / TOTAL RETURN +620.37% / CLOSED TRADES 558 / WIN RATE 46.06% / PROFIT_FACTOR 2.34 / WEEKS >= +1% 86/225 / POSITIVE WEEKS 118/225 / MONTHS >= 3/4 ACTIVE 27/52 / WORST DAY -260,832`

    - `TRAIN WINDOW: FINAL EQUITY Y3,931,966 / TOTAL RETURN +293.20% / CLOSED TRADES 503 / WIN RATE 45.53% / PROFIT_FACTOR 1.98 / WEEKS >= +1% 70/199 / POSITIVE WEEKS 101/199 / MONTHS >= 3/4 ACTIVE 8/45 / WORST DAY -108,253`

    - `HOLDOUT WINDOW: FINAL EQUITY Y7,203,734 / TOTAL RETURN +83.21% / CLOSED TRADES 55 / WIN RATE 50.91% / PROFIT_FACTOR 3.00 / WEEKS >= +1% 16/26 / POSITIVE WEEKS 17/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -260,832`

    - `100万円 standalone latest 1m: FINAL EQUITY Y1,142,235 / TOTAL RETURN +14.22% / CLOSED TRADES 4 / PROFIT_FACTOR inf / WEEKS >= +1% 3/4 / POSITIVE WEEKS 3/4 / WORST DAY 0`

- 判断:

  - 不採用

  - train の `WEEKS >= +1%` が 1 本落ち、full の `WORST DAY` も悪化して `2025-W34` が `+1.03%` から `-3.18%` に崩れたので、shared strategy としては採らなかった

- 再試行するとしたら:

  - 低 breadth Tuesday の moderate-market pocket を広げるなら、少なくとも weekly hit を落とさない別の shared offset が同時に見つかったときだけ

  - high breadth / mid-hot market は、まず week stability を崩さない範囲で別の train-supported factor が出たときだけ再検討する

### 2026-06-24: Catchup RS Strong-Continuation Risk Budget Forwarding Restored

- 試したこと:

  - `backtest.py` の `catchup_rs` strong-continuation candidate で、shared logic が持っていた `risk_budget_pct` を本番相当の backtest path へ正しく forward するように戻した

  - これにより、`DAYTRADE_CATCHUP_RS_STRONG_CONTINUATION_RISK_BUDGET_PCT` が backtest でも 10% デフォルトへ落ちず、shared sizing と同じ強度で評価されるようにした

- 結果:

  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`

  - `FULL WINDOW: FINAL EQUITY Y6,649,462 / TOTAL RETURN +564.95% / CLOSED TRADES 533 / WIN RATE 45.78% / PROFIT_FACTOR 2.30 / WEEKS >= +1% 87/225 / POSITIVE WEEKS 112/225 / MONTHS >= 3/4 ACTIVE 8/52 / WORST DAY -239,096`

  - `TRAIN WINDOW: FINAL EQUITY Y3,587,087 / TOTAL RETURN +258.71% / CLOSED TRADES 480 / WIN RATE 45.21% / PROFIT_FACTOR 1.91 / WEEKS >= +1% 71/199 / POSITIVE WEEKS 95/199 / MONTHS >= 3/4 ACTIVE 8/45 / WORST DAY -108,253`

  - `HOLDOUT WINDOW: FINAL EQUITY Y6,649,462 / TOTAL RETURN +85.37% / CLOSED TRADES 53 / WIN RATE 50.94% / PROFIT_FACTOR 3.03 / WEEKS >= +1% 16/26 / POSITIVE WEEKS 17/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -239,096`

  - `100万円 standalone latest 1m: FINAL EQUITY Y1,150,581 / TOTAL RETURN +15.06% / CLOSED TRADES 4 / PROFIT_FACTOR inf / WEEKS >= +1% 3/4 / POSITIVE WEEKS 3/4 / WORST DAY 0`

- 判断:

  - 採用

- 再試行するとしたら:

  - もし将来 train-only 分析でこの strong-continuation のサイズアップが weekly stability を崩すと分かった場合だけ、risk budget ではなく gate 自体を見直す

### 2026-06-27: Wednesday 10-11 Continuation No-Trade Adopted

- 試したこと:

  - `primary` の Wednesday `10.0 <= score < 11.0` continuation を no-trade にした

  - train-only で loss-only に見えた小さな残差 pocket を、shared no-trade として切った

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

    - `FULL WINDOW: FINAL EQUITY Y7,298,768 / TOTAL RETURN +629.88% / CLOSED TRADES 532 / WIN RATE 46.43% / PROFIT_FACTOR 2.38 / WEEKS >= +1% 86/226 / POSITIVE WEEKS 113/226 / MONTHS >= 3/4 ACTIVE 23/52 / WORST DAY -225,547`

    - `TRAIN WINDOW: FINAL EQUITY Y3,789,298 / TOTAL RETURN +278.93% / CLOSED TRADES 481 / WIN RATE 46.15% / PROFIT_FACTOR 1.87 / WEEKS >= +1% 71/200 / POSITIVE WEEKS 97/200 / MONTHS >= 3/4 ACTIVE 7/45 / WORST DAY -174,346`

    - `HOLDOUT WINDOW: FINAL EQUITY Y7,298,768 / TOTAL RETURN +92.62% / CLOSED TRADES 51 / WIN RATE 49.02% / PROFIT_FACTOR 3.57 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 16/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -225,547`

    - `100万円 standalone latest 1m: FINAL EQUITY Y1,082,521 / TOTAL RETURN +8.25% / CLOSED TRADES 4 / PROFIT_FACTOR 34.11 / WEEKS >= +1% 2/4 / POSITIVE WEEKS 2/4 / WORST DAY -2,493`

- 判断:

  - 採用

  - train で再現した Wednesday の loss-only pocket を shared no-trade にでき、full / train / holdout を壊さずに baseline を維持できた

- 再試行するとしたら:

  - 10-11 以外の Wednesday continuation を score だけで広げるのではなく、新しい train-supported shared factor が見つかったときだけ

### 2026-06-27: Wednesday Extreme-Open Pocket No-Trade Rejected

- 試したこと:

  - Wednesday の low-score / stretched-open / hot-market pocket を no-trade 化して、train の loss-only cluster をさらに削る案を試した

  - `open_vs_sma_atr` が極端な pocket に絞って train-only diagnostics を見たところ、isolated trade log では loss-only に見えた

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

    - `train-only の isolated pocket は消えたが、full validation では total return / PF / worst day が accepted baseline より悪化`

    - `holdout` と `standalone` も含めた shared validation で改善が続かなかったため、採用しなかった

- 判断:

  - 不採用

  - 共有戦略としては、同じ Wednesday の近傍をさらに細かく刻むだけでは回復せず、replacement / selection effects で全体が悪化した

- 再試行するとしたら:

  - この pocket の閾値をさらに刻むのではなく、別の train-supported shared factor が見つかった場合だけ

### 2026-06-27: Tuesday Catchup RS 6-8 Broadening + Tuesday Overheated Primary No-Trade

- 試したこと:

  - `catchup_rs` の Tuesday low-breadth / moderate-market pocket を `score 6.0-10.0` まで広げ、train で負けていた 6-8 帯も shared filter に入れた

  - `primary` の Tuesday overheated pocket（`market_ratio >= 1.20`）を `mild crowding` の前に no-trade として置き、他の sizing ルールで戻らないようにした

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

    - `FULL WINDOW: FINAL EQUITY Y8,974,494 / TOTAL RETURN +797.45% / CLOSED TRADES 529 / WIN RATE 46.88% / PROFIT_FACTOR 2.66 / WEEKS >= +1% 89/226 / POSITIVE WEEKS 117/226 / MONTHS >= 3/4 ACTIVE 8/52 / WORST DAY -315,765`

    - `TRAIN WINDOW: FINAL EQUITY Y4,991,659 / TOTAL RETURN +399.17% / CLOSED TRADES 476 / WIN RATE 46.85% / PROFIT_FACTOR 2.39 / WEEKS >= +1% 74/200 / POSITIVE WEEKS 101/200 / MONTHS >= 3/4 ACTIVE 8/45 / WORST DAY -217,932`

    - `HOLDOUT WINDOW: FINAL EQUITY Y8,974,494 / TOTAL RETURN +79.79% / CLOSED TRADES 53 / WIN RATE 47.17% / PROFIT_FACTOR 3.08 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 16/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -315,765`

    - `100万円 standalone latest 1m: FINAL EQUITY Y1,082,521 / TOTAL RETURN +8.25% / CLOSED TRADES 4 / PROFIT_FACTOR 34.11 / WEEKS >= +1% 2/4 / POSITIVE WEEKS 2/4 / WORST DAY -2,493`

  - `python analyze_backtest_trade_log.py --holdout-months 6 --top-n 20 --output-trades-csv tmp\train_trade_log.csv`

    - train では Tuesday catchup_rs の 6-8 帯が負け pocket として残り、Tuesday primary の `market_ratio >= 1.20` も再現性のある負け pocket として確認できた

- 判断:

  - 採用

  - 低 breadth Tuesday の弱い catchup_rs と Tuesday overheated primary を shared ルールで抑えつつ、holdout / standalone を壊さなかった

- 再試行するとしたら:

  - Wednesday 系は broad no-trade に広げず、train で複数回再現する shared pocket が別に見つかったときだけ

### 2026-06-27: Monday Strong-Oversold / Tue-Wed Catchup RS Hot-Market No-Trade Adopted

- 試したこと:

  - `strong_oversold` の Monday / low-breadth / hot-market pocket (`breadth < 0.75`, `market_ratio 1.02-1.10`) を shared no-trade にした

  - `catchup_rs` の Tuesday / Wednesday / low-breadth / high-market-ratio pocket (`breadth < 0.55`, `market_ratio 1.15-1.20`) を shared no-trade にした

  - train-only diagnostics で両方とも同型の損失が再現し、holdout 側にも同じ pocket の損失が残っていたため、曲線当て込みではなく共通防御として扱った

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

    - `FULL WINDOW: FINAL EQUITY Y11,992,572 / TOTAL RETURN +1099.26% / CLOSED TRADES 530 / WIN RATE 47.36% / PROFIT_FACTOR 3.38 / WEEKS >= +1% 90/226 / POSITIVE WEEKS 120/226 / MONTHS >= 3/4 ACTIVE 9/52 / WORST DAY -325,458`

    - `TRAIN WINDOW: FINAL EQUITY Y6,247,636 / TOTAL RETURN +524.76% / CLOSED TRADES 479 / WIN RATE 47.18% / PROFIT_FACTOR 2.87 / WEEKS >= +1% 74/200 / POSITIVE WEEKS 103/200 / MONTHS >= 3/4 ACTIVE 9/45 / WORST DAY -276,047`

    - `HOLDOUT WINDOW: FINAL EQUITY Y11,992,572 / TOTAL RETURN +91.95% / CLOSED TRADES 51 / WIN RATE 49.02% / PROFIT_FACTOR 4.18 / WEEKS >= +1% 16/26 / POSITIVE WEEKS 17/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -325,458`

    - `100万円 standalone latest 1m: FINAL EQUITY Y1,082,521 / TOTAL RETURN +8.25% / CLOSED TRADES 4 / PROFIT_FACTOR 34.11 / WEEKS >= +1% 2/4 / POSITIVE WEEKS 2/4 / WORST DAY -2,493`

- 判断:

  - 採用

  - まだ train の月次 20% には届かないが、同型の loss pocket を shared guard で閉じたうえで full / train / holdout / standalone を崩さなかった

- 再試行するとしたら:

  - この近傍を score だけでさらに広げるのではなく、`primary` の Wednesday hot tape など別の train-supported shared cluster が十分に再現したときだけ

### 2026-06-28: Wednesday Mid-Breadth Hot-Market High-Score Low-Open Residual Pocket No-Trade Adopted

- 試したこと:

  - `primary` の Wednesday mid-breadth / hot-market / high-score / low-open residual pocket を no-trade にした

  - train-only diagnostics で `2024-03-13 4186.T` と `2025-11-26 6525.T` の 2 本が同 pocket に入り、どちらも loss-only だった

  - `breadth 0.60-0.71` / `market_ratio 1.15-1.20` / `score 7.5-10` / `open_vs_sma_atr < 1.0` の shared no-trade で、positive-control の `breadth 0.715732` は巻き込まないようにした

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

    - `FULL WINDOW: FINAL EQUITY Y13,404,432 / TOTAL RETURN +1240.44% / CLOSED TRADES 529 / WIN RATE 47.83% / PROFIT_FACTOR 3.61 / WEEKS >= +1% 93/226 / POSITIVE WEEKS 121/226 / MONTHS >= 3/4 ACTIVE 9/52 / WORST DAY -362,203`

    - `TRAIN WINDOW: FINAL EQUITY Y6,966,088 / TOTAL RETURN +596.61% / CLOSED TRADES 478 / WIN RATE 47.70% / PROFIT_FACTOR 3.17 / WEEKS >= +1% 77/200 / POSITIVE WEEKS 104/200 / MONTHS >= 3/4 ACTIVE 9/45 / WORST DAY -319,634`

    - `HOLDOUT WINDOW: FINAL EQUITY Y13,404,432 / TOTAL RETURN +92.42% / CLOSED TRADES 51 / WIN RATE 49.02% / PROFIT_FACTOR 4.23 / WEEKS >= +1% 16/26 / POSITIVE WEEKS 17/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -362,203`

    - `100万円 standalone latest 1m: FINAL EQUITY Y1,082,521 / TOTAL RETURN +8.25% / CLOSED TRADES 4 / PROFIT_FACTOR 34.11 / WEEKS >= +1% 2/4 / POSITIVE WEEKS 2/4 / WORST DAY -2,493`

- 判断:

  - 採用

- 再試行するとしたら:

  - Wednesday の residual pocket を breadth だけで広げるのではなく、train で複数回再現する別の shared tail-loss が見つかったときだけ

### 2026-06-28: Holdout-Derived Wednesday/Thursday Pockets Rejected After Train Recheck

- 試したこと:

  - Wednesday の high-breadth / hot-market / stretched-open pocket と、Thursday の lower-score mid-breadth / hot-market / non-negative-open pocket を追加 no-trade 候補として検討した

  - ただし train-only 再チェックでは、Wednesday の 2025-12-03 loss は 2025-12-10 win と同じ広い帯に混在し、Thursday 側も単発損失に留まっていて、shared pocket としての再現性が足りなかった

- 結果:

  - 不採用

  - holdout 由来の追加 no-trade は取り消し、baseline は Wednesday residual pocket 採用版に戻した

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

    - `FULL WINDOW: FINAL EQUITY Y13,404,432 / TOTAL RETURN +1240.44% / CLOSED TRADES 529 / WIN RATE 47.83% / PROFIT_FACTOR 3.61 / WEEKS >= +1% 93/226 / POSITIVE WEEKS 121/226 / MONTHS >= 3/4 ACTIVE 9/52 / WORST DAY -362,203`

    - `TRAIN WINDOW: FINAL EQUITY Y6,966,088 / TOTAL RETURN +596.61% / CLOSED TRADES 478 / WIN RATE 47.70% / PROFIT_FACTOR 3.17 / WEEKS >= +1% 77/200 / POSITIVE WEEKS 104/200 / MONTHS >= 3/4 ACTIVE 9/45 / WORST DAY -319,634`

    - `HOLDOUT WINDOW: FINAL EQUITY Y13,404,432 / TOTAL RETURN +92.42% / CLOSED TRADES 51 / WIN RATE 49.02% / PROFIT_FACTOR 4.23 / WEEKS >= +1% 16/26 / POSITIVE WEEKS 17/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -362,203`

    - `100万円 standalone latest 1m: FINAL EQUITY Y1,082,521 / TOTAL RETURN +8.25% / CLOSED TRADES 4 / PROFIT_FACTOR 34.11 / WEEKS >= +1% 2/4 / POSITIVE WEEKS 2/4 / WORST DAY -2,493`

- 判断:

  - 不採用

- 再試行するとしたら:

  - train で 2 本以上の独立再現があり、holdout を見なくても shared pocket と言えるときだけ

### 2026-06-28: Tuesday Low-Score Hot-Market Open 1-2 Pocket Rejected

- 試したこと:

  - Tuesday の low-score hot-market pocket に `open_vs_sma_atr 1.0-2.0` の no-trade を追加した

  - train-only diagnostics では primary の 2 本が loss-only だったが、candidate selection の置換効果まで含めると全体成績が悪化した

- 結果:

  - 不採用

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

    - `TRAIN WINDOW: FINAL EQUITY Y7,138,295 / TOTAL RETURN +613.83% / CLOSED TRADES 459 / PROFIT FACTOR 3.25 / WEEKS >= +1% 77/200 / POSITIVE WEEKS 106/200 / MONTHS >= 3/4 ACTIVE 7/45 / WORST DAY -319,634`

    - `HOLDOUT WINDOW: FINAL EQUITY Y13,682,222 / TOTAL RETURN +91.67% / CLOSED TRADES 51 / PROFIT FACTOR 4.20 / WEEKS >= +1% 16/26 / POSITIVE WEEKS 17/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -372,702`

    - `100万円 standalone latest 1m: FINAL EQUITY Y1,082,521 / TOTAL RETURN +8.25% / CLOSED TRADES 4 / PROFIT FACTOR 34.11 / WEEKS >= +1% 2/4 / POSITIVE WEEKS 2/4 / WORST DAY -2,493`

- 判断:

  - 不採用

  - 置換効果のため、primary の純損失 pocket だけでは採用理由として不十分だった

- 再試行するとしたら:

  - 代替候補を含めた full validation で、同じ pocket が本当に全体の期待値を押し上げると確認できたときだけ

### 2026-06-28: Tuesday Low-Score Hot-Market Narrow Pocket and Mon/Thu/Fri Shared No-Trade Adopted

- 試したこと:

  - Tuesday の low-score / hot-market / mid-breadth narrow pocket (`breadth 0.65-0.75` / `market_ratio 1.05-1.10` / `score <= 6.5`) を shared no-trade にした

  - Monday / Thursday / Friday の low-score / hot-market continuation (`breadth 0.55-0.65` / `market_ratio 1.10-1.15` / `score <= 6.5`) を shared no-trade にした

  - train-only diagnostics ではどちらも loss-only で、後続で試した Thursday / Tuesday open1_2 の追加 no-trade は selection / replacement effects で悪化したため revert した

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

    - `FULL WINDOW: FINAL EQUITY Y13,681,071 / TOTAL RETURN +1268.11% / CLOSED TRADES 510 / WIN RATE 49.41% / PROFIT_FACTOR 3.65 / WEEKS >= +1% 94/226 / POSITIVE WEEKS 123/226 / MONTHS >= 3/4 ACTIVE 7/52 / WORST DAY -372,702`

    - `TRAIN WINDOW: FINAL EQUITY Y7,144,038 / TOTAL RETURN +614.40% / CLOSED TRADES 459 / WIN RATE 49.46% / PROFIT_FACTOR 3.25 / WEEKS >= +1% 78/200 / POSITIVE WEEKS 106/200 / MONTHS >= 3/4 ACTIVE 7/45 / WORST DAY -319,634`

    - `HOLDOUT WINDOW: FINAL EQUITY Y13,681,071 / TOTAL RETURN +91.50% / CLOSED TRADES 51 / WIN RATE 49.02% / PROFIT_FACTOR 4.18 / WEEKS >= +1% 16/26 / POSITIVE WEEKS 17/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -372,702`

    - `100万円 standalone latest 1m: FINAL EQUITY Y1,082,521 / TOTAL RETURN +8.25% / CLOSED TRADES 4 / WIN RATE 75.00% / PROFIT_FACTOR 34.11 / WEEKS >= +1% 2/4 / POSITIVE WEEKS 2/4 / WORST DAY -2,493`

- 判断:

  - 採用

  - train の low-expectancy pocket を shared no-trade でまとめて閉じられ、full / holdout / standalone を壊さずに train baseline を押し上げた

- 再試行するとしたら:

  - この 2 つの band をさらに刻むのではなく、train で独立再現が 2 回以上ある別の shared pocket が見つかったときだけ

### 2026-07-01: Tuesday / Wednesday High-Breadth Hot-Market Mid-Score High-RSI と Wednesday Prior-Low Stretched-Open No-Trade Adopted

- 試したこと:

  - `primary` の Tuesday / Wednesday high-breadth / hot-market / mid-score / high-RSI pocket (`breadth 0.65-0.75` / `market_ratio 1.15-1.28` / `score 6.0-8.0` / `open_vs_sma_atr -0.5-2.0` / `prev_rsi2 >= 50.0`) を shared no-trade にした

  - `primary` の Wednesday `breadth >= 0.50` / `open_from_prev_low_atr >= 1.5` の stretched-open pocket を shared no-trade にした

  - train-only diagnostics では、いずれも loss-only pocket をまとめて閉じる方向で一貫していた

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

  - `FULL WINDOW: FINAL EQUITY Y34,286,325 / TOTAL RETURN +3328.63% / CLOSED TRADES 434 / WIN RATE 62.44% / PROFIT_FACTOR 14.60 / WEEKS >= +1% 97/227 / POSITIVE WEEKS 151/227 / MONTHS >= 3/4 ACTIVE 3/52 / WORST DAY -292,234`

  - `TRAIN WINDOW: FINAL EQUITY Y16,971,444 / TOTAL RETURN +1597.14% / CLOSED TRADES 389 / WIN RATE 62.98% / PROFIT_FACTOR 14.86 / WEEKS >= +1% 82/201 / POSITIVE WEEKS 132/201 / MONTHS >= 3/4 ACTIVE 3/46 / WORST DAY -69,683`

  - `HOLDOUT WINDOW: FINAL EQUITY Y34,286,325 / TOTAL RETURN +102.02% / CLOSED TRADES 45 / WIN RATE 57.78% / PROFIT_FACTOR 14.38 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -292,234`

  - `100万円 standalone latest 1m: FINAL EQUITY Y1,068,961 / TOTAL RETURN +6.90% / CLOSED TRADES 2 / PROFIT_FACTOR inf / WEEKS >= +1% 1/5 / POSITIVE WEEKS 2/5 / WORST DAY 0`

- 判断:

  - 採用

- 再試行するとしたら:

  - Tuesday / Wednesday の高 breadth hot-market mid-score / high-RSI pocket からさらに広げず、train で独立再現する別 shared pocket が見つかったときだけ

  - Wednesday の stretched-from-prev-low も breadth だけで広げず、再現性のある loss cluster が増えたときだけ

### 2026-07-01: Wednesday Near-Flat-Gap / Low-Stretch Pocket Probe Rejected

- 試したこと:

  - `primary` の Wednesday near-flat-gap / low-stretch pocket (`gap -0.26%~0.12%` / `open_from_prev_low_atr 0.7822-0.9769`) を shared no-trade 候補として追加検討した

  - train-only diagnostics では既存の Wednesday loss cluster に近かったが、shared pocket としては広げすぎる形になった

- 結果:

  - 全体 validation が悪化したため revert した

  - フル / train の成績が明確に悪化したため、採用済み baseline には戻さなかった

- 判断:

  - 不採用

- 再試行するとしたら:

  - Wednesday の prior-low 近傍を broad で切るのではなく、別の train 再現 pocket が 2 本以上確認できたときだけ

### 2026-07-02: Tuesday High-Breadth Hot-Market Low-Open Probe Adopted

- 試したこと:

  - `primary` の Tuesday high-breadth / hot-market / low-score / sub-half-ATR-open pocket (`breadth 0.70-0.80` / `market_ratio >= 1.18` / `score <= 6.5` / `gap -0.5%~1.5%` / `open_vs_sma_atr <= 0.5`) を full no-trade ではなく selected base leverage `0.10` probe にした

  - train-only diagnostics では `2023-06-20 9505.T` / `2025-10-07 6269.T` / `2025-10-21 6113.T` / `2026-01-06 6941.T` の 4 本が loss-only だった

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

  - `FULL WINDOW: FINAL EQUITY Y34,590,160 / TOTAL RETURN +3359.02% / CLOSED TRADES 435 / WIN RATE 62.53% / PROFIT_FACTOR 15.54 / WEEKS >= +1% 97/227 / POSITIVE WEEKS 151/227 / MONTHS >= 3/4 ACTIVE 3/52 / WORST DAY -292,234`

  - `TRAIN WINDOW: FINAL EQUITY Y16,978,491 / TOTAL RETURN +1597.85% / CLOSED TRADES 390 / WIN RATE 63.08% / PROFIT_FACTOR 14.88 / WEEKS >= +1% 82/201 / POSITIVE WEEKS 132/201 / MONTHS >= 3/4 ACTIVE 3/46 / WORST DAY -69,683`

  - `HOLDOUT WINDOW: FINAL EQUITY Y34,590,160 / TOTAL RETURN +103.73% / CLOSED TRADES 45 / WIN RATE 57.78% / PROFIT_FACTOR 16.19 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -292,234`

  - `100万円 standalone latest 1m: FINAL EQUITY Y1,068,961 / TOTAL RETURN +6.90% / CLOSED TRADES 2 / PROFIT_FACTOR inf / WEEKS >= +1% 1/5 / POSITIVE WEEKS 2/5 / WORST DAY 0`

- 判断:

  - 採用

- 再試行するとしたら:

  - Tuesday high-breadth hot-market でも、train-supported で別の residual pocket が再現したときだけ

  - この pocket をさらに広げるのではなく、次の独立 pocket を train で確認できるまで待つ

### 2026-07-02: Wednesday High-Breadth Hot-Market Low-Score Mid-Open Probe Adopted

- 試したこと:

  - `primary` の Wednesday high-breadth / hot-market / low-score / mid-open pocket (`breadth 0.70-0.75` / `market_ratio 1.15-1.20` / `score 5.0-6.5` / `gap -0.5%~0.5%` / `open_vs_sma_atr <= 2.0`) を selected base leverage `0.10` probe にした

  - train-only diagnostics では `2024-03-13 8698.T` の 1 本だけが loss-only だった

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

  - `FULL WINDOW: FINAL EQUITY Y36,796,281 / TOTAL RETURN +3579.63% / CLOSED TRADES 437 / WIN RATE 62.24% / PROFIT_FACTOR 15.68 / WEEKS >= +1% 97/227 / POSITIVE WEEKS 151/227 / MONTHS >= 3/4 ACTIVE 3/52 / WORST DAY -309,424`

  - `TRAIN WINDOW: FINAL EQUITY Y18,034,943 / TOTAL RETURN +1703.49% / CLOSED TRADES 392 / WIN RATE 62.76% / PROFIT_FACTOR 15.25 / WEEKS >= +1% 82/201 / POSITIVE WEEKS 132/201 / MONTHS >= 3/4 ACTIVE 3/46 / WORST DAY -40,113`

  - `HOLDOUT WINDOW: FINAL EQUITY Y36,796,281 / TOTAL RETURN +104.03% / CLOSED TRADES 45 / WIN RATE 57.78% / PROFIT_FACTOR 16.09 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -309,424`

  - `100万円 standalone latest 1m: FINAL EQUITY Y1,068,961 / TOTAL RETURN +6.90% / CLOSED TRADES 2 / PROFIT_FACTOR inf / WEEKS >= +1% 1/5 / POSITIVE WEEKS 2/5 / WORST DAY 0`

- 判断:

  - 採用

- 再試行するとしたら:

  - Wednesday high-breadth hot-market でも、train-supported で別の residual pocket が再現したときだけ

  - `gap` や `breadth` をさらに広げず、独立 pocket の再現が増えたときだけ

### 2026-07-02: Wednesday High-Breadth Hot-Market Low-Score Broad Probe Restored

- 試したこと:

  - `primary` の Wednesday high-breadth / hot-market / low-score broad probe (`breadth 0.60-0.78` / `market_ratio >= 1.20` / `score <= 8.0` / `gap <= 1.0%`) を shared 0.10 probe に戻した

  - broad no-trade への置き換えは full / train の PF を悪化させたため、shared probe に戻して再確認した

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

  - `FULL WINDOW: FINAL EQUITY Y37,025,880 / TOTAL RETURN +3602.59% / CLOSED TRADES 433 / WIN RATE 62.82% / PROFIT_FACTOR 16.07 / WEEKS >= +1% 97/227 / POSITIVE WEEKS 151/227 / MONTHS >= 3/4 ACTIVE 3/52 / WORST DAY -309,424`

  - `TRAIN WINDOW: FINAL EQUITY Y18,134,227 / TOTAL RETURN +1713.42% / CLOSED TRADES 388 / WIN RATE 63.40% / PROFIT_FACTOR 15.96 / WEEKS >= +1% 82/201 / POSITIVE WEEKS 132/201 / MONTHS >= 3/4 ACTIVE 3/46 / WORST DAY -41,285`

  - `HOLDOUT WINDOW: FINAL EQUITY Y37,025,880 / TOTAL RETURN +104.18% / CLOSED TRADES 45 / WIN RATE 57.78% / PROFIT_FACTOR 16.18 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -309,424`

  - `100万円 standalone latest 1m: FINAL EQUITY Y1,068,961 / TOTAL RETURN +6.90% / CLOSED TRADES 2 / PROFIT_FACTOR inf / WEEKS >= +1% 1/5 / POSITIVE WEEKS 2/5 / WORST DAY 0`

- 判断:

  - 採用

- 再試行するとしたら:

  - Wednesday high-breadth hot-market low-score でも、train で別の独立 pocket が再現したときだけ

  - いまの 0.10 probe をさらに広げるのではなく、holdout veto で壊れていないことを確認できる別 pocket が出たときだけ

### 2026-07-02: Monday Mid-Breadth Mild-Hot Market Tight-Gap No-Trade Adopted

- 試したこと:

  - `primary` の Monday mid-breadth / mildly hot market / tight-gap pocket (`breadth 0.55-0.65` / `market_ratio 1.05-1.10` / `gap <= 0.5%`) を no-trade にした

  - train で再現した `2023-08-21 9107.T` / `2023-11-20 7868.T` / `2023-11-27 7182.T` / `2024-07-22 7744.T` / `2025-06-30 6503.T` の 5 本を shared veto で切った

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

  - `FULL WINDOW: FINAL EQUITY Y37,135,914 / TOTAL RETURN +3613.59% / CLOSED TRADES 428 / WIN RATE 63.32% / PROFIT_FACTOR 16.19 / WEEKS >= +1% 97/227 / POSITIVE WEEKS 151/227 / MONTHS >= 3/4 ACTIVE 3/52 / WORST DAY -309,424`

  - `TRAIN WINDOW: FINAL EQUITY Y18,181,977 / TOTAL RETURN +1718.20% / CLOSED TRADES 383 / WIN RATE 63.97% / PROFIT_FACTOR 16.16 / WEEKS >= +1% 82/201 / POSITIVE WEEKS 132/201 / MONTHS >= 3/4 ACTIVE 3/46 / WORST DAY -41,285`

  - `HOLDOUT WINDOW: FINAL EQUITY Y37,135,914 / TOTAL RETURN +104.25% / CLOSED TRADES 45 / WIN RATE 57.78% / PROFIT_FACTOR 16.21 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -309,424`

  - `100万円 standalone latest 1m: FINAL EQUITY Y1,068,961 / TOTAL RETURN +6.90% / CLOSED TRADES 2 / PROFIT_FACTOR inf / WEEKS >= +1% 1/5 / POSITIVE WEEKS 2/5 / WORST DAY 0`

- 判断:

  - 採用

- 再試行するとしたら:

  - 同じ Monday mid-breadth / mildly hot-market 帯で、gap を広げずに train-supported な別 pocket が複数回再現したときだけ

  - それ以外は、隣接する wider-gap の勝ち pocket を壊さないことを優先する

### 2026-07-02: Monday Fallback Mid-Breadth Neutral-Market Size-Up Adopted

- 試したこと:

  - `fallback` の Monday mid-breadth / neutral-market / stable-open pocket（`breadth 0.45-0.55` / `market_ratio 0.98-1.01` / `score 4.5-6.5` / `open_vs_sma_atr 2.0-3.5`）を notional `0.21`、equity notional `2.00` に引き上げた

  - train では `2022-06-06 7013.T` / `2022-10-17 2353.T` / `2023-01-23 2930.T` / `2025-05-12 6269.T` / `2025-05-19 8714.T` / `2025-05-26 9072.T` が同 pocket に入ることを確認した

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

  - `FULL WINDOW: FINAL EQUITY Y37,913,371 / TOTAL RETURN +3691.34% / CLOSED TRADES 431 / WIN RATE 62.88% / PROFIT_FACTOR 16.54 / WEEKS >= +1% 98/227 / POSITIVE WEEKS 151/227 / MONTHS >= 3/4 ACTIVE 3/52 / WORST DAY -309,424`

  - `TRAIN WINDOW: FINAL EQUITY Y18,593,683 / TOTAL RETURN +1759.37% / CLOSED TRADES 386 / WIN RATE 63.47% / PROFIT_FACTOR 16.85 / WEEKS >= +1% 83/201 / POSITIVE WEEKS 132/201 / MONTHS >= 3/4 ACTIVE 3/46 / WORST DAY -40,113`

  - `HOLDOUT WINDOW: FINAL EQUITY Y37,913,371 / TOTAL RETURN +103.90% / CLOSED TRADES 45 / WIN RATE 57.78% / PROFIT_FACTOR 16.28 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -309,424`

  - `100万円 standalone latest 1m: FINAL EQUITY Y1,068,961 / TOTAL RETURN +6.90% / CLOSED TRADES 2 / PROFIT_FACTOR inf / WEEKS >= +1% 1/5 / POSITIVE WEEKS 2/5 / WORST DAY 0`

- 判断:

  - 採用

- 再試行するとしたら:

  - Monday fallback で同じ pocket が train に複数回再現し、holdout veto を壊さない場合だけ

### 2026-07-02: Tuesday High-Breadth Hot-Market Low-Open / Exact Low-Open No-Trade Adopted

- 試したこと:

  - `primary` の Tuesday high-breadth / hot-market / low-score / low-open pocket (`breadth 0.70-0.80` / `market_ratio >= 1.18` / `score <= 6.5` / `gap -0.5%~1.5%` / `open_vs_sma_atr <= 0.5`) を shared no-trade に落とした

  - さらに、同系の exact low-open tail (`breadth 0.60-0.80` / `market_ratio >= 1.20` / `score 4.0-6.5` / `open_vs_sma_atr <= 0.5`) も no-trade に揃えた

  - train-only diagnostics では `2023-06-20 6966.T -3,144`、`2025-10-07 6269.T -22,588`、`2025-10-21 5830.T -5,172` の負けが同 pocket に集まっていた一方、`2023-07-04 8725.T` の勝ちもあり、全面停止ではなく shared pocket の低信頼帯だけを落とす形にした

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

  - `FULL WINDOW: FINAL EQUITY Y37,902,596 / TOTAL RETURN +3690.26% / CLOSED TRADES 429 / WIN RATE 63.17% / PROFIT_FACTOR 16.17 / WEEKS >= +1% 98/227 / POSITIVE WEEKS 151/227 / MONTHS >= 3/4 ACTIVE 3/52 / WORST DAY -309,424`

  - `TRAIN WINDOW: FINAL EQUITY Y18,661,661 / TOTAL RETURN +1766.17% / CLOSED TRADES 384 / WIN RATE 63.80% / PROFIT_FACTOR 17.23 / WEEKS >= +1% 83/201 / POSITIVE WEEKS 132/201 / MONTHS >= 3/4 ACTIVE 3/46 / WORST DAY -40,113`

  - `HOLDOUT WINDOW: FINAL EQUITY Y37,902,596 / TOTAL RETURN +103.10% / CLOSED TRADES 45 / WIN RATE 57.78% / PROFIT_FACTOR 15.32 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -309,424`

  - `100万円 standalone latest 1m: FINAL EQUITY Y1,068,961 / TOTAL RETURN +6.90% / CLOSED TRADES 2 / PROFIT_FACTOR inf / WEEKS >= +1% 1/5 / POSITIVE WEEKS 2/5 / WORST DAY 0`

- 判断:

  - 採用

- 再試行するとしたら:

  - いまの no-trade 境界をさらに細かく当て込むのではなく、train で別の再現 pocket が増えたときだけ再評価する

### 2026-07-02: Wednesday Low-Open Tail No-Trade Expansion Reverted

- 試したこと:

  - Wednesday の low-open tail を広く no-trade 化する案を追加で検討した

  - ただし、train / full の悪化がはっきり出たため、その変更は revert した

- 結果:

  - `FULL WINDOW: FINAL EQUITY Y36,783,819` まで悪化し、`TRAIN WINDOW: FINAL EQUITY Y19,071,027`、`PROFIT_FACTOR 10.01` まで落ちたため不採用とした

  - この時点の baseline は、上の Tuesday / exact low-open の shared no-trade だけを残した状態

- 判断:

  - 不採用

- 再試行するとしたら:

  - Wednesday tail を広げるのではなく、train に新しい独立 pocket が 2 本以上再現したときだけ

### 2026-07-02: Wednesday Hot-Gap Mid-Breadth No-Trade Adopted

- 試したこと:

  - `primary` の Wednesday hot-gap / mid-breadth / hot-market pocket（`breadth 0.55-0.65` / `market_ratio >= 1.17` / `gap >= 2.0%`）を no-trade にした

  - train では `2025-12-03 6770.T -251,149.6` と `2026-04-08 9531.T -309,424.1` が同 pocket に集まり、他の train 例は見当たらなかった

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

  - `FULL WINDOW: FINAL EQUITY Y38,367,202 / TOTAL RETURN +3736.72% / CLOSED TRADES 428 / WIN RATE 63.55% / PROFIT_FACTOR 18.66 / WEEKS >= +1% 98/227 / POSITIVE WEEKS 151/227 / MONTHS >= 3/4 ACTIVE 3/52 / WORST DAY -140,604`

  - `TRAIN WINDOW: FINAL EQUITY Y18,693,032 / TOTAL RETURN +1769.30% / CLOSED TRADES 383 / WIN RATE 63.97% / PROFIT_FACTOR 17.70 / WEEKS >= +1% 83/201 / POSITIVE WEEKS 132/201 / MONTHS >= 3/4 ACTIVE 3/46 / WORST DAY -40,113`

  - `HOLDOUT WINDOW: FINAL EQUITY Y38,367,202 / TOTAL RETURN +105.25% / CLOSED TRADES 45 / WIN RATE 60.00% / PROFIT_FACTOR 19.63 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -140,604`

  - `100万円 standalone latest 1m: FINAL EQUITY Y1,068,961 / TOTAL RETURN +6.90% / CLOSED TRADES 2 / PROFIT_FACTOR inf / WEEKS >= +1% 1/5 / POSITIVE WEEKS 2/5 / WORST DAY 0`

- 判断:

  - 採用

- 再試行するとしたら:

  - `breadth 0.55-0.65` / `market_ratio >= 1.17` / `gap >= 2.0%` の Wednesday hot-gap pocket が train でまた再現したときだけ、score や open 方向を追加で刻む

### 2026-07-04: Wednesday Hot-Gap Mid-Breadth Exact Loss Pocket Refined and Adopted

- 試したこと:

  - `primary` の Wednesday hot-gap / mid-breadth / hot-market exact loss pocket (`breadth 0.55-0.65` / `market_ratio 1.10-1.15` / `gap 0-1%` / `score 6.0-8.0` / `open_vs_sma_atr < 0`) を shared no-trade に絞り込んだ

  - train の単発損失 `2024-07-10 3103.T` を閉じつつ、既存の Wednesday 安全候補 `2024-05-01 9508.T` は no-trade 化しないように `gap` で切り分けた

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

  - `FULL WINDOW: FINAL EQUITY Y39,858,412 / TOTAL RETURN +3885.84% / CLOSED TRADES 427 / WIN RATE 64.40% / PROFIT_FACTOR 20.28 / WEEKS >= +1% 99/227 / POSITIVE WEEKS 155/227 / MONTHS >= 3/4 ACTIVE 3/52 / WORST DAY -140,604`

  - `TRAIN WINDOW: FINAL EQUITY Y19,376,346 / TOTAL RETURN +1837.63% / CLOSED TRADES 382 / WIN RATE 64.92% / PROFIT_FACTOR 20.97 / WEEKS >= +1% 84/201 / POSITIVE WEEKS 136/201 / MONTHS >= 3/4 ACTIVE 3/46 / WORST DAY -37,913`

  - `HOLDOUT WINDOW: FINAL EQUITY Y39,858,412 / TOTAL RETURN +105.71% / CLOSED TRADES 45 / WIN RATE 60.00% / PROFIT_FACTOR 19.70 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -140,604`

  - `100万円 standalone latest 1m: FINAL EQUITY Y1,068,961 / TOTAL RETURN +6.90% / CLOSED TRADES 2 / PROFIT_FACTOR inf / WEEKS >= +1% 1/5 / POSITIVE WEEKS 2/5 / WORST DAY 0`

- 判断:

  - 採用

- 再試行するとしたら:

  - Wednesday hot-gap mid-breadth をさらに広げず、同じ形の train 独立再現が増えたときだけ

### 2026-07-03: Primary Broad Residual No-Trade Reverted

- 試したこと:

  - `primary` の Monday / Wednesday / Thursday broad residual no-trade pocket をまとめて切る案を検討した

  - ただし replacement effects が強く、train で勝ち pocket を削る副作用が出たため revert した

- 結果:

  - `TRAIN WINDOW: FINAL EQUITY Y18,023,723 / TOTAL RETURN +1802.37% / CLOSED TRADES 381 / PROFIT_FACTOR 18.59 / WORST DAY -56,170`

  - train-only の悪化だけで採用根拠が崩れたため、shared strategy としては不採用とした

- 判断:

  - 不採用

- 再試行するとしたら:

  - broad residual をまとめるのではなく、train で複数回再現し、replacement effects が小さい pocket に分解できたときだけ

### 2026-07-03: Friday Fallback Low-Breadth Sub-Neutral Stable-Open Broadening Adopted

- 試したこと:

  - `fallback` の Friday low-breadth / sub-neutral-market / stable-open pocket（`breadth < 0.45` / `market_ratio < 1.00` / `score <= 4.5` / `open_vs_sma_atr 1.5-2.3`）を no-trade にした

  - 先に `open_vs_sma_atr 1.5-2.0` で残っていた `2024-11-29 8227.T` を、`2024-11-29 7984.T` と一緒に閉じた

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

  - `FULL WINDOW: FINAL EQUITY Y39,187,928 / TOTAL RETURN +3818.79% / CLOSED TRADES 427 / WIN RATE 64.17% / PROFIT_FACTOR 19.55 / WEEKS >= +1% 98/227 / POSITIVE WEEKS 152/227 / MONTHS >= 3/4 ACTIVE 3/52 / WORST DAY -140,604`

  - `TRAIN WINDOW: FINAL EQUITY Y19,054,331 / TOTAL RETURN +1805.43% / CLOSED TRADES 382 / WIN RATE 64.66% / PROFIT_FACTOR 19.54 / WEEKS >= +1% 83/201 / POSITIVE WEEKS 133/201 / MONTHS >= 3/4 ACTIVE 3/46 / WORST DAY -37,913`

  - `HOLDOUT WINDOW: FINAL EQUITY Y39,187,928 / TOTAL RETURN +105.66% / CLOSED TRADES 45 / WIN RATE 60.00% / PROFIT_FACTOR 19.55 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -140,604`

  - `100万円 standalone latest 1m: FINAL EQUITY Y1,068,961 / TOTAL RETURN +6.90% / CLOSED TRADES 2 / PROFIT_FACTOR inf / WEEKS >= +1% 1/5 / POSITIVE WEEKS 2/5 / WORST DAY 0`

- 判断:

  - 採用

- 再試行するとしたら:

  - Friday fallback の残差が `open_vs_sma_atr 2.3` を超えてなお train で複数再現し、holdout veto を壊さないときだけ

### 2026-07-04: Wednesday Hot-Gap Below-SMA Low-Breadth Weak-Market and Deep-Open Tails Closed

- 試したこと:

  - `primary` の Wednesday hot-gap / below-SMA について、low-breadth / weak-market / sub-six tail (`breadth < 0.52` / `market_ratio 1.00-1.02` / `score < 6.0` / `gap >= 1.2%` / `open_vs_sma_atr < 0` / `prev_return >= 0`) を shared no-trade にした

  - さらに、`open_vs_sma_atr <= -1.5` の深い tail も shared no-trade にした

  - 既存の Wednesday hot-gap / below-SMA score `>= 7.5` tail veto はそのまま維持した

  - train では `2025-02-05 5631.T` / `2023-03-22 7826.T` / `2024-01-10 2685.T` の 3 losses / 0 wins / `-60,649.63` を no-trade に寄せた

  - `2024-12-11 8219.T` は別の既存 veto により、引き続き no-trade 側に入っていた

  - holdout にはこの exact pocket match は出ていなかった

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

  - `FULL WINDOW: FINAL EQUITY Y40,669,371 / TOTAL RETURN +3966.94% / CLOSED TRADES 427 / WIN RATE 64.87% / PROFIT_FACTOR 18.75 / WEEKS >= +1% 99/227 / POSITIVE WEEKS 156/227 / MONTHS >= 3/4 ACTIVE 3/53 / WORST DAY -186,762`

  - `TRAIN WINDOW: FINAL EQUITY Y19,924,191 / TOTAL RETURN +1892.42% / CLOSED TRADES 380 / WIN RATE 65.79% / PROFIT_FACTOR 23.67 / WEEKS >= +1% 84/201 / POSITIVE WEEKS 137/201 / MONTHS >= 3/4 ACTIVE 3/46 / WORST DAY -37,913`

  - `HOLDOUT WINDOW: FINAL EQUITY Y40,669,371 / TOTAL RETURN +104.12% / CLOSED TRADES 47 / WIN RATE 57.45% / PROFIT_FACTOR 15.82 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/7 / WORST DAY -186,762`

  - `100万円 standalone latest 1m: FINAL EQUITY Y1,066,763 / TOTAL RETURN +6.68% / CLOSED TRADES 1 / PROFIT_FACTOR inf / WEEKS >= +1% 1/4 / POSITIVE WEEKS 1/4 / WORST DAY 0`

- 判断:

  - 採用

- 再試行するとしたら:

  - いまの Wednesday hot-gap / below-SMA 残差が、さらに別の深い open tail や broader breadth として train で独立再現したときだけ

### 2026-07-04: Wednesday High-Open Low-Score Tight-Gap Pocket Closed

- 試したこと:

  - `primary` の Wednesday high-open / low-score / tight-gap pocket (`market_ratio <= 1.08` / `score <= 6.7` / `gap <= 0.5%` / `open_vs_sma_atr >= 2.0`) を shared no-trade にした

  - train で 5 losses / 0 wins / `-14,066.90` を no-trade に寄せた

  - 5 losses は `2024-11-13 3844.T` / `2024-01-10 5947.T` / `2022-08-24 7187.T` / `2022-11-30 4612.T` / `2024-12-11 3563.T`

  - 近傍の win は `market_ratio`, `gap`, `score` のいずれかが閾値外だったので、そのまま残した

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

  - `FULL WINDOW: FINAL EQUITY Y39,767,078 / TOTAL RETURN +3876.71% / CLOSED TRADES 420 / WIN RATE 65.95% / PROFIT_FACTOR 18.87 / WEEKS >= +1% 100/227 / POSITIVE WEEKS 156/227 / MONTHS >= 3/4 ACTIVE 3/53 / WORST DAY -175,776`

  - `TRAIN WINDOW: FINAL EQUITY Y19,447,566 / TOTAL RETURN +1844.76% / CLOSED TRADES 373 / WIN RATE 67.02% / PROFIT_FACTOR 23.72 / WEEKS >= +1% 85/201 / POSITIVE WEEKS 137/201 / MONTHS >= 3/4 ACTIVE 3/46 / WORST DAY -37,913`

  - `HOLDOUT WINDOW: FINAL EQUITY Y39,767,078 / TOTAL RETURN +104.48% / CLOSED TRADES 47 / WIN RATE 57.45% / PROFIT_FACTOR 15.97 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/7 / WORST DAY -175,776`

  - `100万円 standalone latest 1m: FINAL EQUITY Y1,066,763 / TOTAL RETURN +6.68% / CLOSED TRADES 1 / PROFIT_FACTOR inf / WEEKS >= +1% 1/4 / POSITIVE WEEKS 1/4 / WORST DAY 0`

- 判断:

  - 採用

- 再試行するとしたら:

  - 同じ high-open / low-score / tight-gap pocket が train でさらに別形状として独立再現したときだけ

### 2026-07-04: Monday Mid-Breadth Near-Neutral Higher-Gap Pocket Closed

- 試したこと:

  - `primary` の Monday mid-breadth / near-neutral-market / low-score / higher-gap pocket (`breadth 0.45-0.55` / `market_ratio 1.00-1.05` / `score <= 6` / `gap 1.5-2.0%` / `open_vs_sma_atr 1.0-2.0`) を shared no-trade にした

  - train で `2024-09-02 6460.T` / `2024-10-07 6845.T` の 2 losses / 0 wins / `-7,837.20` を no-trade に寄せた

  - その後の残差確認では、Wednesday の exact 2-loss pocket と Thursday の exact 2-loss pocket、そして Monday の low-open singleton loss が残ったが、いずれも 1〜2 サンプルしかなく shared rule としては薄いので追加は見送った

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

  - `FULL WINDOW: FINAL EQUITY Y39,898,614 / TOTAL RETURN +3889.86% / CLOSED TRADES 416 / WIN RATE 66.83% / PROFIT_FACTOR 19.07 / WEEKS >= +1% 100/227 / POSITIVE WEEKS 156/227 / MONTHS >= 3/4 ACTIVE 3/53 / WORST DAY -175,776`

  - `TRAIN WINDOW: FINAL EQUITY Y19,530,244 / TOTAL RETURN +1853.02% / CLOSED TRADES 369 / WIN RATE 68.02% / PROFIT_FACTOR 24.34 / WEEKS >= +1% 85/201 / POSITIVE WEEKS 137/201 / MONTHS >= 3/4 ACTIVE 3/46 / WORST DAY -37,913`

  - `HOLDOUT WINDOW: FINAL EQUITY Y39,898,614 / TOTAL RETURN +104.29% / CLOSED TRADES 47 / WIN RATE 57.45% / PROFIT_FACTOR 15.99 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/7 / WORST DAY -175,776`

  - `100万円 standalone latest 1m: FINAL EQUITY Y1,066,763 / TOTAL RETURN +6.68% / CLOSED TRADES 1 / PROFIT_FACTOR inf / WEEKS >= +1% 1/4 / POSITIVE WEEKS 1/4 / WORST DAY 0`

- 判断:

  - 採用

- 再試行するとしたら:

  - Monday の higher-gap pocket が train で別の open band まで再現したとき、または Wednesday / Thursday の exact 2-loss pocket がもう 1 本ずつ再現して 3 例以上になったときだけ

### 2026-07-04: Monday Fallback Equity Cap Raised

- 試したこと:

  - `fallback` の Monday mid-breadth / neutral-market / stable-open pocket を notional `0.25`、equity notional `2.25` に引き上げた

  - train で `2022-06-06 7013.T` / `2022-10-17 2353.T` / `2023-01-23 2930.T` / `2025-05-12 6269.T` / `2025-05-19 8714.T` / `2025-05-26 9072.T` の 6 wins / 0 losses / `+1,068,016.39` を再確認した

  - notional だけでは変化が出ず、実効 cap は equity 側だったのでそちらを上げた

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

  - `FULL WINDOW: FINAL EQUITY Y40,976,888 / TOTAL RETURN +3997.69% / CLOSED TRADES 416 / WIN RATE 66.83% / PROFIT_FACTOR 19.02 / WEEKS >= +1% 100/227 / POSITIVE WEEKS 156/227 / MONTHS >= 3/4 ACTIVE 3/53 / WORST DAY -186,762`

  - `TRAIN WINDOW: FINAL EQUITY Y20,068,277 / TOTAL RETURN +1906.83% / CLOSED TRADES 369 / WIN RATE 68.02% / PROFIT_FACTOR 24.69 / WEEKS >= +1% 85/201 / POSITIVE WEEKS 137/201 / MONTHS >= 3/4 ACTIVE 3/46 / WORST DAY -37,913`

  - `HOLDOUT WINDOW: FINAL EQUITY Y40,976,888 / TOTAL RETURN +104.19% / CLOSED TRADES 47 / WIN RATE 57.45% / PROFIT_FACTOR 15.80 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/7 / WORST DAY -186,762`

  - `100万円 standalone latest 1m: FINAL EQUITY Y1,066,763 / TOTAL RETURN +6.68% / CLOSED TRADES 1 / PROFIT_FACTOR inf / WEEKS >= +1% 1/4 / POSITIVE WEEKS 1/4 / WORST DAY 0`

- 判断:

  - 採用

- 再試行するとしたら:

  - この pocket に対する別の train-supported band が独立に再現したときだけ

  - それ以外は fallback のサイズ再調整より先に、holdout veto で悪化しないかを確認する

### 2026-07-04: Hot-Market Small-Gap + Near-Neutral Mid-Open Primary Loss Pockets Closed

- 試したこと:

  - `primary` の hot-market low-score / small-gap / mid-RSI pocket (`market_ratio 1.10-1.15` / `score <= 6.0` / `gap <= 0.5%` / `prev_rsi2 50.0-60.0`) を shared no-trade にした

  - `primary` の near-neutral-market / mid-score / mid-open / mid-RSI pocket (`market_ratio 1.00-1.05` / `score 6.0-8.0` / `open_vs_sma_atr 1.0-2.0` / `prev_rsi2 60.0-70.0`) を shared no-trade にした

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

  - `FULL WINDOW: FINAL EQUITY Y41,341,260 / TOTAL RETURN +4034.13% / CLOSED TRADES 411 / WIN RATE 68.13% / PROFIT_FACTOR 19.29 / WEEKS >= +1% 100/227 / POSITIVE WEEKS 158/227 / MONTHS >= 3/4 ACTIVE 2/53 / WORST DAY -186,762`

  - `TRAIN WINDOW: FINAL EQUITY Y20,263,739 / TOTAL RETURN +1926.37% / CLOSED TRADES 364 / WIN RATE 69.51% / PROFIT_FACTOR 25.74 / WEEKS >= +1% 85/201 / POSITIVE WEEKS 139/201 / MONTHS >= 3/4 ACTIVE 2/46 / WORST DAY -37,913`

  - `HOLDOUT WINDOW: FINAL EQUITY Y41,341,260 / TOTAL RETURN +104.02% / CLOSED TRADES 47 / WIN RATE 57.45% / PROFIT_FACTOR 15.77 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/7 / WORST DAY -186,762`

  - `100万円 standalone latest 1m: FINAL EQUITY Y1,066,763 / TOTAL RETURN +6.68% / CLOSED TRADES 1 / PROFIT_FACTOR inf / WEEKS >= +1% 1/4 / POSITIVE WEEKS 1/4 / WORST DAY 0`

- 判断:

  - 採用

- 再試行するとしたら:

  - Friday / Tuesday の残る negative-gap pocket が train で 4 例以上の独立再現を示したときだけ

### 2026-07-04: Thursday / Wednesday Train-Only Exact Primary Pockets Closed

- 試したこと:

  - `primary` の Thursday near-neutral / mid-open / low-score exact pocket (`breadth 0.60-0.65` / `market_ratio < 1.03` / `score 6-8` / `gap >= 0.0` / `open_vs_sma_atr 1-2`) を shared no-trade にした

  - `primary` の Wednesday low-breadth / near-neutral / negative-gap / low-score exact pocket (`breadth 0.45-0.55` / `market_ratio < 1.03` / `score < 4` / `gap < 0.0` / `open_vs_sma_atr 0-1`) を shared no-trade にした

  - Thursday の境界は train の safer neighbor を巻き込まないよう `breadth_min` を `0.60` に調整した

  - `analyze_backtest_trade_log.py --holdout-months 6 --top-n 20 --output-trades-csv tmp\train_trade_log_after_new_rules.csv` で再集計し、coarse bin scan の pure loss groups を `0` にした

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

  - `FULL WINDOW: FINAL EQUITY Y43,949,674 / TOTAL RETURN +4294.97% / CLOSED TRADES 400 / WIN RATE 72.00% / PROFIT_FACTOR 19.96 / WEEKS >= +1% 101/227 / POSITIVE WEEKS 156/227 / MONTHS >= 3/4 ACTIVE 2/53 / WORST DAY -197,748`

  - `TRAIN WINDOW: FINAL EQUITY Y21,504,626 / TOTAL RETURN +2050.46% / CLOSED TRADES 353 / WIN RATE 73.94% / PROFIT_FACTOR 27.88 / WEEKS >= +1% 86/201 / POSITIVE WEEKS 137/201 / MONTHS >= 3/4 ACTIVE 2/46 / WORST DAY -26,126`

  - `HOLDOUT WINDOW: FINAL EQUITY Y43,949,674 / TOTAL RETURN +104.37% / CLOSED TRADES 47 / WIN RATE 57.45% / PROFIT_FACTOR 15.94 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/7 / WORST DAY -197,748`

  - `100万円 standalone latest 1m: FINAL EQUITY Y1,066,763 / TOTAL RETURN +6.68% / CLOSED TRADES 1 / PROFIT_FACTOR inf / WEEKS >= +1% 1/4 / POSITIVE WEEKS 1/4 / WORST DAY 0`

- 判断:

  - 採用

- 再試行するとしたら:

  - 同じ粒度の shared exact pocket は出尽くしたので、次に新しい train-only 純損失群が別の binning で独立再現したときだけ

  - それ以外は、holdout veto で悪化が出ない範囲の shared de-risk 以外は追いかけない

### 2026-07-05: Friday Pure-Win Size-Up / Tuesday Probe Raise

- 試したこと:

  - `primary` の Friday high-breadth / hot-market / stable-gap / high-score pure-win pocket を `4.0` から `6.0` まで段階的に引き上げた

  - `6.5` まで試したが `6.0` と同値だったため、risk を下げる目的で `6.0` を採用した

  - `catchup_rs` の Tuesday low-breadth probe leverage を `0.20` から `0.25` に引き上げた

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

  - `FULL WINDOW: FINAL EQUITY Y65,933,143 / TOTAL RETURN +6493.31% / CLOSED TRADES 395 / WIN RATE 72.91% / PROFIT_FACTOR 21.97 / WEEKS >= +1% 102/227 / POSITIVE WEEKS 160/227 / MONTHS >= 3/4 ACTIVE 2/53 / WORST DAY -296,622`

  - `TRAIN WINDOW: FINAL EQUITY Y29,515,739 / TOTAL RETURN +2851.57% / CLOSED TRADES 348 / WIN RATE 75.00% / PROFIT_FACTOR 34.20 / WEEKS >= +1% 87/201 / POSITIVE WEEKS 141/201 / MONTHS >= 3/4 ACTIVE 2/46 / WORST DAY -39,038`

  - `HOLDOUT WINDOW: FINAL EQUITY Y65,933,143 / TOTAL RETURN +123.38% / CLOSED TRADES 47 / WIN RATE 57.45% / PROFIT_FACTOR 17.27 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/7 / WORST DAY -296,622`

  - `100万円 standalone latest 1m: FINAL EQUITY Y1,066,763 / TOTAL RETURN +6.68% / CLOSED TRADES 1 / PROFIT_FACTOR inf / WEEKS >= +1% 1/4 / POSITIVE WEEKS 1/4 / WORST DAY 0`

- 判断:

  - 採用

- 再試行するとしたら:

  - Friday pocket は train に新しい独立再現が出たときのみさらに上げる

  - Tuesday probe は同形状の新規 train 再現が出たときのみ再検討する

### 2026-07-05: Residual Train-Only Primary Pockets Narrowed

- 試したこと:
  - `primary` の Monday mid-breadth / hot-market / high-gap pocket を shared no-trade にした
  - `primary` の Wednesday mid-breadth / hot-market / low-gap pocket を shared no-trade にした
  - `primary` の Thursday mid-breadth / weak-market / high-gap pocket を shared no-trade にした
  - 3 pocket は train で独立に損失が出ており、holdout では未出だったため shared strategy に落とし込んだ
- 結果:
  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`
  - `FULL WINDOW: FINAL EQUITY Y68,661,537 / TOTAL RETURN +6766.15% / CLOSED TRADES 393 / WIN RATE 73.03% / PROFIT_FACTOR 22.14 / WEEKS >= +1% 103/227 / POSITIVE WEEKS 157/227 / MONTHS >= 3/4 ACTIVE 2/53 / WORST DAY -307,608`
  - `TRAIN WINDOW: FINAL EQUITY Y30,750,979 / TOTAL RETURN +2975.10% / CLOSED TRADES 346 / WIN RATE 75.14% / PROFIT_FACTOR 35.49 / WEEKS >= +1% 88/201 / POSITIVE WEEKS 138/201 / MONTHS >= 3/4 ACTIVE 2/46 / WORST DAY -43,375`
  - `HOLDOUT WINDOW: FINAL EQUITY Y68,661,537 / TOTAL RETURN +123.28% / CLOSED TRADES 47 / WIN RATE 57.45% / PROFIT_FACTOR 17.21 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/7 / WORST DAY -307,608`
  - `100万円 standalone latest 1m: FINAL EQUITY Y1,066,763 / TOTAL RETURN +6.68% / CLOSED TRADES 1 / PROFIT_FACTOR inf / WEEKS >= +1% 1/4 / POSITIVE WEEKS 1/4 / WORST DAY 0`
- 判断:
  - 採用
- 再試行するとしたら:
  - 同じ broad bin の中で train-only の loss cluster が新しく独立再現した場合のみ
  - holdout を見ながら近傍閾値を追い込むのではなく、shared な no-trade / size-down だけで説明できる pocket に限る

### 2026-07-05: Rejected - Wednesday/Thursday Exact Pocket Cap Trial

- 試したこと:

  - `primary` の Wednesday low-breadth / near-neutral / small-positive-gap exact pocket を candidate-level で cap した

  - `primary` の Thursday mid-breadth / near-neutral / tight-positive-gap exact pocket を candidate-level で cap した

  - no-trade, `0.25` cap, `0.10` cap を順に試し、いずれも train-only の損失集中を根本的には改善しないか、むしろ悪化させた

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

  - `FULL WINDOW: FINAL EQUITY Y68,661,537 / TOTAL RETURN +6766.15% / CLOSED TRADES 393 / WIN RATE 73.03% / PROFIT_FACTOR 22.14 / WEEKS >= +1% 103/227 / POSITIVE WEEKS 157/227 / MONTHS >= 3/4 ACTIVE 2/53 / WORST DAY -307,608`

  - `TRAIN WINDOW: FINAL EQUITY Y30,750,979 / TOTAL RETURN +2975.10% / CLOSED TRADES 346 / WIN RATE 75.14% / PROFIT_FACTOR 35.49 / WEEKS >= +1% 88/201 / POSITIVE WEEKS 138/201 / MONTHS >= 3/4 ACTIVE 2/46 / WORST DAY -43,375`

  - `HOLDOUT WINDOW: FINAL EQUITY Y68,661,537 / TOTAL RETURN +123.28% / CLOSED TRADES 47 / WIN RATE 57.45% / PROFIT_FACTOR 17.21 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/7 / WORST DAY -307,608`

  - `100万円 standalone latest 1m: FINAL EQUITY Y1,066,763 / TOTAL RETURN +6.68% / CLOSED TRADES 1 / PROFIT_FACTOR inf / WEEKS >= +1% 1/4 / POSITIVE WEEKS 1/4 / WORST DAY 0`

- 判断:

  - 不採用

- 再試行するとしたら:

  - candidate-level exact pocket ではなく、日次 leverage 側で同じ regime を薄められるだけの独立根拠が出たとき

  - それ以外は、同じ breadth / gap 近傍を当て込むのではなく、別の train-only loss cluster が独立再現したときだけ

### 2026-07-04: Monday Fallback Pure-Win Size-Up Tuned

- 試したこと:

  - `fallback` の Monday mid-breadth / neutral-market / stable-open pure-win pocket (`breadth 0.45-0.55` / `market_ratio 0.98-1.01` / `score 4.5-6.5` / `open_vs_sma_atr 2.0-3.5`) を train-only で再評価した

  - train では 6 wins / 0 losses / `+1,253,457.52` の pure-win pocket で、holdout に同形状の出現はなかった

  - `equity_notional_pct` を `2.25` から `2.50` に上げたところ train / full が改善し、`2.60` や `3.00` は悪化したため `2.50` を採用した

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

  - `FULL WINDOW: FINAL EQUITY Y45,114,615 / TOTAL RETURN +4411.46% / CLOSED TRADES 400 / WIN RATE 72.00% / PROFIT_FACTOR 20.09 / WEEKS >= +1% 101/227 / POSITIVE WEEKS 157/227 / MONTHS >= 3/4 ACTIVE 2/53 / WORST DAY -208,734`

  - `TRAIN WINDOW: FINAL EQUITY Y22,087,825 / TOTAL RETURN +2108.78% / CLOSED TRADES 353 / WIN RATE 73.94% / PROFIT_FACTOR 28.55 / WEEKS >= +1% 86/201 / POSITIVE WEEKS 138/201 / MONTHS >= 3/4 ACTIVE 2/46 / WORST DAY -26,126`

  - `HOLDOUT WINDOW: FINAL EQUITY Y45,114,615 / TOTAL RETURN +104.25% / CLOSED TRADES 47 / WIN RATE 57.45% / PROFIT_FACTOR 15.90 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/7 / WORST DAY -208,734`

  - `100万円 standalone latest 1m: FINAL EQUITY Y1,066,763 / TOTAL RETURN +6.68% / CLOSED TRADES 1 / PROFIT_FACTOR inf / WEEKS >= +1% 1/4 / POSITIVE WEEKS 1/4 / WORST DAY 0`

- 判断:

  - 採用

- 再試行するとしたら:

  - 同じ Monday fallback pure-win pocket が train で別の独立条件に再現したときだけ

  - それ以外は、holdout に出ない shared size-up をこれ以上細かく追い込まない

### 2026-07-05: Monday/Tuesday/Thursday Small-Gap Cap Rebalanced

- 試したこと:
  - `primary` の Monday / Tuesday / Thursday near-neutral-market / low-score / small-gap pocket を breadth 2 帯 + open 1.0-2.0 の shared cap に再設計した
  - `0.25` -> `0.10` -> `0.05` -> `0.02` -> `0.03` の順に試し、`0.03` が full / train を最も押し上げつつ holdout も baseline 超えしたため採用した
  - train で `1812.T` / `3092.T` / `4443.T` / `7453.T` / `6965.T` などの損失を薄めつつ、既存 survivor は残した
- 結果:
  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`
  - `FULL WINDOW: FINAL EQUITY Y69,477,501 / TOTAL RETURN +6847.75% / CLOSED TRADES 391 / WIN RATE 73.66% / PROFIT_FACTOR 22.83 / WEEKS >= +1% 103/227 / POSITIVE WEEKS 159/227 / MONTHS >= 3/4 ACTIVE 2/53 / WORST DAY -318,594`
  - `TRAIN WINDOW: FINAL EQUITY Y31,101,861 / TOTAL RETURN +3010.19% / CLOSED TRADES 344 / WIN RATE 75.87% / PROFIT_FACTOR 39.80 / WEEKS >= +1% 88/201 / POSITIVE WEEKS 140/201 / MONTHS >= 3/4 ACTIVE 2/46 / WORST DAY -43,375`
  - `HOLDOUT WINDOW: FINAL EQUITY Y69,477,501 / TOTAL RETURN +123.39% / CLOSED TRADES 47 / WIN RATE 57.45% / PROFIT_FACTOR 17.26 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/7 / WORST DAY -318,594`
  - `100万円 standalone latest 1m: FINAL EQUITY Y1,066,763 / TOTAL RETURN +6.68% / CLOSED TRADES 1 / PROFIT_FACTOR inf / WEEKS >= +1% 1/4 / POSITIVE WEEKS 1/4 / WORST DAY 0`
- 判断:
  - 採用
- 再試行するとしたら:
  - 同じ breadth / open band の train-only loss cluster が別に独立再現したときだけ
  - holdout worst day をさらに削れる独立根拠が出たときだけ再設計する

### 2026-07-06: Monday Fallback Size-Up Rebalanced

- 試したこと:
  - `fallback` の Monday mid-breadth / neutral-market / stable-open pocket (`breadth 0.45-0.55` / `market_ratio 0.98-1.01` / `score 4.5-6.5` / `open_vs_sma_atr 2.0-3.5`) の equity notional を `3.0 -> 2.0` に下げた
  - 3.0 では train の初期損失が compounding で後続の勝ちを押し下げていたため、shared risk budget を少し戻した
- 結果:
  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`
  - `FULL WINDOW: FINAL EQUITY Y64,776,730 / TOTAL RETURN +6377.67% / CLOSED TRADES 392 / WIN RATE 73.72% / PROFIT_FACTOR 22.67 / WEEKS >= +1% 101/227 / POSITIVE WEEKS 161/227 / MONTHS >= 3/4 ACTIVE 2/53 / WORST DAY -296,622`
  - `TRAIN WINDOW: FINAL EQUITY Y29,024,122 / TOTAL RETURN +2802.41% / CLOSED TRADES 345 / WIN RATE 75.94% / PROFIT_FACTOR 38.91 / WEEKS >= +1% 86/201 / POSITIVE WEEKS 142/201 / MONTHS >= 3/4 ACTIVE 2/46 / WORST DAY -39,038`
  - `HOLDOUT WINDOW: FINAL EQUITY Y64,776,730 / TOTAL RETURN +123.18% / CLOSED TRADES 47 / WIN RATE 57.45% / PROFIT_FACTOR 17.22 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/7 / WORST DAY -296,622`
  - `100万円 standalone latest 1m: FINAL EQUITY Y1,066,763 / TOTAL RETURN +6.68% / CLOSED TRADES 1 / PROFIT_FACTOR inf / WEEKS >= +1% 1/4 / POSITIVE WEEKS 1/4 / WORST DAY 0`
- 判断:
  - 採用
- 再試行するとしたら:
  - `2.0` と `2.5` の間で同じ pocket が別の期間に独立再現したときだけ
  - それ以外はこの pocket をこれ以上細かく刻まない

### 2026-07-06: Wednesday/Friday/Monday Small-Gap No-Trade Pockets Added

- 試したこと:
  - `primary` の Wednesday low-breadth / weak-market / small-gap pocket を no-trade にした
  - `primary` の Wednesday mid-breadth / weak-market / score `6-8` / small-gap pocket を no-trade にした
  - `primary` の Monday mid-high breadth / hot-market / non-positive-gap pocket を no-trade にした
  - `primary` の Friday low-breadth / near-neutral-market / small-positive-gap pocket を no-trade にした
  - train-only diagnostics では、weekday / breadth / market / gap / score / trend の組み合わせを追加で確認したが、`small no-win groups` は空だった
- 結果:
  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`
  - `FULL WINDOW: FINAL EQUITY Y66,989,770 / TOTAL RETURN +6598.98% / CLOSED TRADES 386 / WIN RATE 75.39% / PROFIT_FACTOR 23.72 / WEEKS >= +1% 102/227 / POSITIVE WEEKS 165/227 / MONTHS >= 3/4 ACTIVE 1/53 / WORST DAY -307,608`
  - `TRAIN WINDOW: FINAL EQUITY Y30,009,735 / TOTAL RETURN +2900.97% / CLOSED TRADES 339 / WIN RATE 77.88% / PROFIT_FACTOR 48.15 / WEEKS >= +1% 87/201 / POSITIVE WEEKS 146/201 / MONTHS >= 3/4 ACTIVE 1/46 / WORST DAY -36,965`
  - `HOLDOUT WINDOW: FINAL EQUITY Y66,989,770 / TOTAL RETURN +123.23% / CLOSED TRADES 47 / WIN RATE 57.45% / PROFIT_FACTOR 17.15 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/7 / WORST DAY -307,608`
  - `100万円 standalone latest 1m: FINAL EQUITY Y1,066,763 / TOTAL RETURN +6.68% / CLOSED TRADES 1 / PROFIT_FACTOR inf / WEEKS >= +1% 1/4 / POSITIVE WEEKS 1/4 / WORST DAY 0`
- 判断:
  - 採用
- 再試行するとしたら:
  - 同じ weekday / breadth / market / gap 近傍に独立再現する train-only 小損失群が出たときだけ
  - それ以外は、同じ傾きの pocket を細かく刻まず shared risk budget 側で扱う

### 2026-07-06: Wednesday Fallback / Primary Size-Ups Added

- 試したこと:
  - `fallback` の Wednesday mid-breadth / hot-market / stretched-open pocket（`breadth 0.45-0.55` / `market_ratio 1.00-1.05` / `score 6.0-8.0` / `prev_return >= 4%` / `open_vs_sma_atr >= 3.5`）を train-only で再確認し、notional `0.25` / equity notional `2.0` の shared size-up を追加した
  - `primary` の Wednesday mid-breadth / hot-market / stable-gap / pure-win pocket（`breadth 0.65-0.70` / `market_ratio 1.16-1.20` / `score 4.8-6.0` / `gap <= 0%` / `open_vs_sma_atr >= 2.0`）を train-only で再確認し、equity notional `3.0` の shared size-up を追加した
  - 既存の Monday fallback pure-win pocket は `2.0` では弱かったため `2.5` に戻し、train の勝ち筋を持ち上げた
- 結果:
  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`
  - `FULL WINDOW: FINAL EQUITY Y71,140,565 / TOTAL RETURN +7014.06% / CLOSED TRADES 385 / WIN RATE 75.32% / PROFIT_FACTOR 23.73 / WEEKS >= +1% 103/227 / POSITIVE WEEKS 164/227 / MONTHS >= 3/4 ACTIVE 1/53 / WORST DAY -318,594`
  - `TRAIN WINDOW: FINAL EQUITY Y31,875,859 / TOTAL RETURN +3087.59% / CLOSED TRADES 338 / WIN RATE 77.81% / PROFIT_FACTOR 49.38 / WEEKS >= +1% 88/201 / POSITIVE WEEKS 145/201 / MONTHS >= 3/4 ACTIVE 1/46 / WORST DAY -36,965`
  - `HOLDOUT WINDOW: FINAL EQUITY Y71,140,565 / TOTAL RETURN +123.18% / CLOSED TRADES 47 / WIN RATE 57.45% / PROFIT_FACTOR 17.04 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/7 / WORST DAY -318,594`
  - `100万円 standalone latest 1m: FINAL EQUITY Y1,066,763 / TOTAL RETURN +6.68% / CLOSED TRADES 1 / PROFIT_FACTOR inf / WEEKS >= +1% 1/4 / POSITIVE WEEKS 1/4 / WORST DAY 0`
- 判断:
  - 採用
- 再試行するとしたら:
  - 同じ Wednesday pocket が train の別期間で独立再現したときだけ
  - holdout を追いかけて当て込みを続けるのではなく、別の train-only loss cluster が見つかったときだけ再設計する
### 2026-07-06: Tuesday/Wednesday High-Breadth Pure-Win Size-Ups Added

- 試したこと:
  - `primary` の Wednesday high-breadth / hot-market / stable-gap / high-score pure-win pocket（`breadth 0.70-0.75` / `market_ratio 1.15-1.20` / `score 6.5-8.0` / `gap <= 0%`）を train-only で再確認し、equity notional `3.0` の shared size-up を追加した
  - `primary` の Tuesday high-breadth / extreme hot-market / large-gap pure-win pocket（`breadth >= 0.75` / `market_ratio 1.10-1.15` / `score >= 10` / `gap >= 2.0%`）を train-only で再確認し、equity notional `3.0` の shared size-up を追加した
  - どちらの pocket も holdout では出現せず、train だけで純勝ちだったため veto 材料はなかった
- 結果:
  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`
  - `FULL WINDOW: FINAL EQUITY Y72,534,134 / TOTAL RETURN +7153.41% / CLOSED TRADES 386 / WIN RATE 75.13% / PROFIT_FACTOR 23.66 / WEEKS >= +1% 102/227 / POSITIVE WEEKS 164/227 / MONTHS >= 3/4 ACTIVE 1/53 / WORST DAY -329,580`
  - `TRAIN WINDOW: FINAL EQUITY Y32,517,011 / TOTAL RETURN +3151.70% / CLOSED TRADES 339 / WIN RATE 77.58% / PROFIT_FACTOR 48.13 / WEEKS >= +1% 87/201 / POSITIVE WEEKS 145/201 / MONTHS >= 3/4 ACTIVE 1/46 / WORST DAY -36,965`
  - `HOLDOUT WINDOW: FINAL EQUITY Y72,534,134 / TOTAL RETURN +123.07% / CLOSED TRADES 47 / WIN RATE 57.45% / PROFIT_FACTOR 17.08 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/7 / WORST DAY -329,580`
  - `100万円 standalone latest 1m: FINAL EQUITY Y1,066,763 / TOTAL RETURN +6.68% / CLOSED TRADES 1 / PROFIT_FACTOR inf / WEEKS >= +1% 1/4 / POSITIVE WEEKS 1/4 / WORST DAY 0`
- 判断:
  - 採用
- 再試行するとしたら:
  - 同じ breadth / gap / score 帯が train の別期間で独立再現したときだけ
  - それ以外は、holdout を見ながら閾値を刻まず shared regime の再現だけを拾う

### 2026-07-06: Tuesday Low-Breadth / Weak-Market / Low-Score Low-Prev-Return No-Trade Added

- 試したこと:
  - `primary` の Tuesday low-breadth / weak-market / low-score pocket (`breadth 0.45-0.55` / `market_ratio 1.00-1.05` / `score <= 4.0` / `gap 0-0.5%`) を train-only で再確認し、`prev_return <= 2%` の weak-follow-through slice を no-trade にした
  - train では `9984.T` / `4980.T` の損失 2 件が `prev_return` 2% 以下に集まり、同じ pocket の `2181.T` / `4202.T` の勝ち 2 件は `prev_return` 2% 超で残せた
  - shared no-trade なので、holdout を見ながら細かく当て込んだ変更ではない
- 結果:
  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`
  - `FULL WINDOW: FINAL EQUITY Y72,702,609 / TOTAL RETURN +7170.26% / CLOSED TRADES 384 / WIN RATE 75.52% / PROFIT_FACTOR 23.69 / WEEKS >= +1% 102/227 / POSITIVE WEEKS 164/227 / MONTHS >= 3/4 ACTIVE 1/53 / WORST DAY -329,580`
  - `TRAIN WINDOW: FINAL EQUITY Y32,582,399 / TOTAL RETURN +3158.24% / CLOSED TRADES 337 / WIN RATE 78.04% / PROFIT_FACTOR 48.85 / WEEKS >= +1% 87/201 / POSITIVE WEEKS 145/201 / MONTHS >= 3/4 ACTIVE 1/46 / WORST DAY -36,965`
  - `HOLDOUT WINDOW: FINAL EQUITY Y72,702,609 / TOTAL RETURN +123.13% / CLOSED TRADES 47 / WIN RATE 57.45% / PROFIT_FACTOR 17.04 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/7 / WORST DAY -329,580`
  - `100万円 standalone latest 1m: FINAL EQUITY Y1,066,763 / TOTAL RETURN +6.68% / CLOSED TRADES 1 / PROFIT_FACTOR inf / WEEKS >= +1% 1/4 / POSITIVE WEEKS 1/4 / WORST DAY 0`
- 判断:
  - 採用
- 再試行するとしたら:
  - 同じ Tuesday pocket が train の別期間で独立再現したときだけ
  - それ以外は、同じ breadth / market / gap 帯を holdout ベースで細かく削らず、別の train-only loss cluster が出たときだけ再設計する

### 2026-07-06: Monday Mid-High Breadth / Hot-Market / Low-Open No-Trade Added

- 試したこと:
  - `primary` の Monday mid-high breadth / hot-market / mid-gap pocket (`breadth 0.65-0.75` / `market_ratio 1.10-1.15` / `gap 0.5-1.0%`) を train-only で再確認し、`open_vs_sma_atr < 1.0` の低オープン slice を no-trade にした
  - train では `6752.T` / `4046.T` の損失 2 件が low-open 側に集まり、同じ pocket の `8359.T` / `6196.T` は高 open で残せた
  - 直後の再分析で、この breadth / market / gap 帯の exact bin 重複は消え、残りはより散った単発寄りになった
- 結果:
  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`
  - `FULL WINDOW: FINAL EQUITY Y72,729,789 / TOTAL RETURN +7172.98% / CLOSED TRADES 384 / WIN RATE 75.78% / PROFIT_FACTOR 23.68 / WEEKS >= +1% 102/227 / POSITIVE WEEKS 164/227 / MONTHS >= 3/4 ACTIVE 1/53 / WORST DAY -329,580`
  - `TRAIN WINDOW: FINAL EQUITY Y32,598,969 / TOTAL RETURN +3159.90% / CLOSED TRADES 337 / WIN RATE 78.34% / PROFIT_FACTOR 48.77 / WEEKS >= +1% 87/201 / POSITIVE WEEKS 145/201 / MONTHS >= 3/4 ACTIVE 1/46 / WORST DAY -36,965`
  - `HOLDOUT WINDOW: FINAL EQUITY Y72,729,789 / TOTAL RETURN +123.10% / CLOSED TRADES 47 / WIN RATE 57.45% / PROFIT_FACTOR 17.05 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/7 / WORST DAY -329,580`
  - `100万円 standalone latest 1m: FINAL EQUITY Y1,066,763 / TOTAL RETURN +6.68% / CLOSED TRADES 1 / PROFIT_FACTOR inf / WEEKS >= +1% 1/4 / POSITIVE WEEKS 1/4 / WORST DAY 0`
- 判断:
  - 採用
- 再試行するとしたら:
  - 同じ Monday pocket が train の別期間で独立再現したときだけ
  - それ以外は、open 強度で切れる shared pocket が見つからない限り、単発の損失に合わせて細かく分岐を増やさない

### 2026-07-08: Strong-Oversold Pure-Win Notional Lift

- 試したこと:

  - `strong_oversold` の Wednesday / Thursday 純勝ち帯と、hot-market / stable-market の broader 純勝ち帯に対して、`notional_pct` を `0.04 -> 0.07`、`equity_notional_pct` を `1.0 -> 4.0` に引き上げた

  - `equity cap` だけでは実効サイズが変わらず、`notional_pct` も同時に上げる必要があることを確認した

- 結果:

  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`

  - `FULL WINDOW: FINAL EQUITY Y156,740,840 / TOTAL RETURN +15574.08% / CLOSED TRADES 385 / WIN RATE 76.88% / PROFIT_FACTOR 25.58 / WEEKS >= +1% 102/228 / POSITIVE WEEKS 166/228 / MONTHS >= 3/4 ACTIVE 11/53 / WORST DAY -1,847,427`

  - `TRAIN WINDOW: FINAL EQUITY Y60,918,165 / TOTAL RETURN +5991.82% / CLOSED TRADES 343 / WIN RATE 76.97% / PROFIT_FACTOR 49.11 / WEEKS >= +1% 87/201 / POSITIVE WEEKS 145/201 / MONTHS >= 3/4 ACTIVE 10/46 / WORST DAY -338,461`

  - `HOLDOUT WINDOW: FINAL EQUITY Y156,740,840 / TOTAL RETURN +157.30% / CLOSED TRADES 42 / WIN RATE 76.19% / PROFIT_FACTOR 19.82 / WEEKS >= +1% 14/26 / POSITIVE WEEKS 20/26 / MONTHS >= 3/4 ACTIVE 1/6 / WORST DAY -1,847,427`

  - `100万円 standalone latest 1m: FINAL EQUITY Y1,200,562 / TOTAL RETURN +20.06% / CLOSED TRADES 3 / PROFIT_FACTOR 99.73 / WEEKS >= +1% 1/5 / POSITIVE WEEKS 2/5 / WORST DAY -2,031`

- 判断:

  - 採用

- 再試行するとしたら:

  - 同じ帯をさらに上げるのではなく、train で新しく独立再現した pure-win pocket が増えたときだけ

  - その場合も `notional_pct` と `equity_notional_pct` の両方を同時に見直し、equity cap だけを触る無効な再試行はしない

### 2026-07-08: Broader Hot-Market Stable-Gap Pure-Win Size-Up Added

- 試したこと:
  - train-only で再確認した broader high-breadth / hot-market / stable-gap / mid-high-score pure-win pocket（`breadth 0.60-0.78` / `market_ratio 1.17-1.225` / `score 6.5-13.0` / `gap -1.0%~0.5%` / `open_vs_sma_atr -0.5~3.5` / `prev_return >= 1%`）を shared size-up にした
  - broad pocket を Wednesday の狭い 3.0 pocket より先に評価しつつ、`open_vs_sma_atr` の下限を `-1.5 -> -0.5` に締めて synthetic 近傍の過剰広がりを避けた
  - 9 trades / 9 wins の train pocket を保ちつつ、holdout で同形状の損失混入が増えないかを再検証した
- 結果:
  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`
  - `FULL WINDOW: FINAL EQUITY Y130,039,121 / TOTAL RETURN +12903.91% / CLOSED TRADES 385 / WIN RATE 77.40% / PROFIT_FACTOR 25.26 / WEEKS >= +1% 102/228 / POSITIVE WEEKS 167/228 / MONTHS >= 3/4 ACTIVE 11/53 / WORST DAY -1,528,326`
  - `TRAIN WINDOW: FINAL EQUITY Y50,538,674 / TOTAL RETURN +4953.87% / CLOSED TRADES 343 / WIN RATE 77.55% / PROFIT_FACTOR 45.62 / WEEKS >= +1% 87/201 / POSITIVE WEEKS 146/201 / MONTHS >= 3/4 ACTIVE 10/46 / WORST DAY -280,526`
  - `HOLDOUT WINDOW: FINAL EQUITY Y130,039,121 / TOTAL RETURN +157.31% / CLOSED TRADES 42 / WIN RATE 76.19% / PROFIT_FACTOR 19.89 / WEEKS >= +1% 14/26 / POSITIVE WEEKS 20/26 / MONTHS >= 3/4 ACTIVE 1/6 / WORST DAY -1,528,326`
  - `100万円 standalone latest 1m: FINAL EQUITY Y1,200,562 / TOTAL RETURN +20.06% / CLOSED TRADES 3 / PROFIT_FACTOR 99.73 / WEEKS >= +1% 1/5 / POSITIVE WEEKS 2/5 / WORST DAY -2,031`
- 判断:
  - 採用
- 再試行するとしたら:
  - 同じ broad hot-market stable-gap pocket が train の別期間で独立再現したときだけ
  - それ以外は、open 近傍や score 近傍を無理にさらに広げない

### 2026-07-07: Strong Oversold Pure-Win Size-Up Added

- 試したこと:
  - `strong_oversold` の Wednesday / Thursday 純勝ち帯（`breadth 0.65-0.75` / `market_ratio 1.00-1.05` / `gap <= 0%` / `score >= 18`）を train-only で再確認し、`equity_notional_pct` を `1.0 -> 2.0` に引き上げた
  - train では `6298.T` / `3186.T` / `4480.T` / `6966.T` などの純勝ちがその帯に集まり、holdout では同形状の出現はなかった
  - `backtest.py` 側も shared helper 参照へ寄せ、バックテストと本番の分岐を揃えた
- 結果:
  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`
  - `FULL WINDOW: FINAL EQUITY Y77,423,675 / TOTAL RETURN +7642.37% / CLOSED TRADES 384 / WIN RATE 75.26% / PROFIT_FACTOR 23.71 / WEEKS >= +1% 102/227 / POSITIVE WEEKS 164/227 / MONTHS >= 3/4 ACTIVE 1/53 / WORST DAY -351,552`
  - `TRAIN WINDOW: FINAL EQUITY Y34,654,829 / TOTAL RETURN +3365.48% / CLOSED TRADES 337 / WIN RATE 77.74% / PROFIT_FACTOR 48.38 / WEEKS >= +1% 87/201 / POSITIVE WEEKS 145/201 / MONTHS >= 3/4 ACTIVE 1/46 / WORST DAY -39,018`
  - `HOLDOUT WINDOW: FINAL EQUITY Y77,423,675 / TOTAL RETURN +123.41% / CLOSED TRADES 47 / WIN RATE 57.45% / PROFIT_FACTOR 17.11 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/7 / WORST DAY -351,552`
  - `100万円 standalone latest 1m: FINAL EQUITY Y1,066,763 / TOTAL RETURN +6.68% / CLOSED TRADES 1 / PROFIT_FACTOR inf / WEEKS >= +1% 1/4 / POSITIVE WEEKS 1/4 / WORST DAY 0`
- 判断:
  - 採用
- 再試行するとしたら:
  - 同じ Wednesday / Thursday strong_oversold pure-win band が train の別期間で独立再現したときだけ
  - それ以外は、score や breadth だけを広げて当て込みを増やさない

### 2026-07-07: Catchup RS Strong-Continuation Size-Up Added

- 試したこと:
  - `catchup_rs` の low-breadth / strong-continuation pure-win pocket（`breadth < 0.50` / `prev_return >= 3%` / `open_vs_sma_atr <= 1.0` / `score >= 10.0`）を train-only で再確認し、`selected base leverage 0.30 -> 0.35` / `equity notional 5.0` / `risk budget 0.30` の shared size-up を追加した
  - 2026-06-16 の standalone 1トレード `6480.T` はこの pocket の代表例で、1M 初期資金から +20% 超まで伸びた
- 結果:
  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`
  - `FULL WINDOW: FINAL EQUITY Y90,281,806 / TOTAL RETURN +8928.18% / CLOSED TRADES 380 / WIN RATE 77.37% / PROFIT_FACTOR 28.34 / WEEKS >= +1% 102/227 / POSITIVE WEEKS 166/227 / MONTHS >= 3/4 ACTIVE 1/53 / WORST DAY -1,041,277`
  - `TRAIN WINDOW: FINAL EQUITY Y35,474,652 / TOTAL RETURN +3447.47% / CLOSED TRADES 337 / WIN RATE 77.74% / PROFIT_FACTOR 49.14 / WEEKS >= +1% 87/201 / POSITIVE WEEKS 145/201 / MONTHS >= 3/4 ACTIVE 1/46 / WORST DAY -41,072`
  - `HOLDOUT WINDOW: FINAL EQUITY Y90,281,806 / TOTAL RETURN +154.50% / CLOSED TRADES 43 / WIN RATE 74.42% / PROFIT_FACTOR 22.50 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 21/26 / MONTHS >= 3/4 ACTIVE 0/7 / WORST DAY -1,041,277`
  - `100万円 standalone latest 1m: FINAL EQUITY Y1,200,562 / TOTAL RETURN +20.06% / CLOSED TRADES 3 / PROFIT_FACTOR 99.73 / WEEKS >= +1% 1/4 / POSITIVE WEEKS 2/4 / WORST DAY -2,031`
- 判断:
  - 採用
- 再試行するとしたら:
  - 同じ low-breadth / strong-continuation pocket が train の別期間で独立再現したときだけ
  - それ以外は、純勝ちの exact pocket を holdout ベースでさらに広げず、shared leverage / risk budget のまま維持する

### 2026-07-07: Monday Mild Hot-Market Mid-Score Low-Open No-Trade Added

- 試したこと:
  - train-only で再現した Monday の low-breadth / mildly hot-market / mid-score / low-open pocket（`breadth 0.45-0.50` / `market_ratio 1.05-1.10` / `score 8.0-10.0` / `open_vs_sma_atr <= 1.0`）を no-trade にした
  - 既存の Monday broad-mid-score 正規ルールより前に置き、`2023-12-25 2168.T` と `2024-06-10 9627.T` の 2 連敗を shared で落とせるようにした
- 結果:
  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`
  - `FULL WINDOW: FINAL EQUITY Y90,435,380 / TOTAL RETURN +8943.54% / CLOSED TRADES 379 / WIN RATE 77.84% / PROFIT_FACTOR 28.28 / WEEKS >= +1% 102/227 / POSITIVE WEEKS 166/227 / MONTHS >= 3/4 ACTIVE 1/53 / WORST DAY -1,058,072`
  - `TRAIN WINDOW: FINAL EQUITY Y35,571,523 / TOTAL RETURN +3457.15% / CLOSED TRADES 336 / WIN RATE 78.27% / PROFIT_FACTOR 49.76 / WEEKS >= +1% 87/201 / POSITIVE WEEKS 145/201 / MONTHS >= 3/4 ACTIVE 1/46 / WORST DAY -41,072`
  - `HOLDOUT WINDOW: FINAL EQUITY Y90,435,380 / TOTAL RETURN +154.24% / CLOSED TRADES 43 / WIN RATE 74.42% / PROFIT_FACTOR 22.36 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 21/26 / MONTHS >= 3/4 ACTIVE 0/7 / WORST DAY -1,058,072`
  - `100万円 standalone latest 1m: FINAL EQUITY Y1,200,562 / TOTAL RETURN +20.06% / CLOSED TRADES 3 / PROFIT_FACTOR 99.73 / WEEKS >= +1% 1/4 / POSITIVE WEEKS 2/4 / WORST DAY -2,031`
- 判断:
  - 採用
- 再試行するとしたら:
  - `Tuesday` の小さい mixed pocket が別期間で独立再現できたときだけ
  - それ以外は、2件しかない mixed pocket を広げて当て込まない
### 2026-07-07: Strong Oversold Pure-Win Size-Up Raised

- 試したこと:
  - `strong_oversold` の Wednesday / Thursday 純勝ち帯（`breadth 0.65-0.75` / `market_ratio 1.00-1.05` / `gap <= 0%` / `score >= 18`）を train-only で再確認し、`equity_notional_pct` を `2.0 -> 4.0` に引き上げた
  - train では `6298.T` / `3186.T` / `4480.T` / `6966.T` などの純勝ちがその帯に集まり、5 trades / 5 wins / `+241,068.64` の pure-win pocket だった
  - holdout には同形状の出現はなかった
  - 4.0 への引き上げで total return は伸びたが、月間 20% 目標はまだ満たしていないため、さらに広い当て込みは避けた
- 結果:
  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`
  - `FULL WINDOW: FINAL EQUITY Y95,709,412 / TOTAL RETURN +9470.94% / CLOSED TRADES 383 / WIN RATE 77.55% / PROFIT_FACTOR 28.37 / WEEKS >= +1% 100/227 / POSITIVE WEEKS 165/227 / MONTHS >= 3/4 ACTIVE 1/53 / WORST DAY -1,108,456`
  - `TRAIN WINDOW: FINAL EQUITY Y37,590,869 / TOTAL RETURN +3659.09% / CLOSED TRADES 340 / WIN RATE 77.94% / PROFIT_FACTOR 49.93 / WEEKS >= +1% 85/201 / POSITIVE WEEKS 144/201 / MONTHS >= 3/4 ACTIVE 1/46 / WORST DAY -43,126`
  - `HOLDOUT WINDOW: FINAL EQUITY Y95,709,412 / TOTAL RETURN +154.61% / CLOSED TRADES 43 / WIN RATE 74.42% / PROFIT_FACTOR 22.42 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 21/26 / MONTHS >= 3/4 ACTIVE 0/7 / WORST DAY -1,108,456`
  - `100万円 standalone latest 1m: FINAL EQUITY Y1,200,562 / TOTAL RETURN +20.06% / CLOSED TRADES 3 / PROFIT_FACTOR 99.73 / WEEKS >= +1% 1/4 / POSITIVE WEEKS 2/4 / WORST DAY -2,031`
- 判断:
  - 採用
- 再試行するとしたら:
  - 同じ Wednesday / Thursday strong_oversold pure-win band が train の別期間で独立再現し、worst day を悪化させずにさらに広い shared ルールが出たときだけ
  - それ以外は、純勝ち帯を広げるための breadth / score / market_ratio の当て込みは増やさない

### 2026-07-07: Rejected - Strong Oversold Tuesday Low-Open Mixed Pocket No-Trade

- 試したこと:
  - train-only 再分析で拾えた `strong_oversold` の Tuesday low-breadth / near-neutral-market / high-score / low-open pocket（`breadth 0.55-0.60` / `market_ratio 1.00-1.05` / `score >= 12` / `gap -1%~0%` / `open_vs_sma_atr 0-0.5`）を no-trade 化する案を検討した
  - 該当 pocket は train で 2 trades しかなく、`2022-09-20 7956.T` の win と `2025-01-07 9008.T` の loss が混在していた
  - holdout には同形状の trade はなかった
- 結果:
  - 追加の shared 変更は入れず、`python jp_backtest.py --holdout-months 6 --standalone-latest-months 1` の baseline は前回と同じ
  - `FULL WINDOW: FINAL EQUITY Y90,435,380 / TOTAL RETURN +8943.54% / CLOSED TRADES 379 / WIN RATE 77.84% / PROFIT_FACTOR 28.28 / WEEKS >= +1% 102/227 / POSITIVE WEEKS 166/227 / MONTHS >= 3/4 ACTIVE 1/53 / WORST DAY -1,058,072`
  - `TRAIN WINDOW: FINAL EQUITY Y35,571,523 / TOTAL RETURN +3457.15% / CLOSED TRADES 336 / WIN RATE 78.27% / PROFIT_FACTOR 49.76 / WEEKS >= +1% 87/201 / POSITIVE WEEKS 145/201 / MONTHS >= 3/4 ACTIVE 1/46 / WORST DAY -41,072`
  - `HOLDOUT WINDOW: FINAL EQUITY Y90,435,380 / TOTAL RETURN +154.24% / CLOSED TRADES 43 / WIN RATE 74.42% / PROFIT_FACTOR 22.36 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 21/26 / MONTHS >= 3/4 ACTIVE 0/7 / WORST DAY -1,058,072`
  - `100万円 standalone latest 1m: FINAL EQUITY Y1,200,562 / TOTAL RETURN +20.06% / CLOSED TRADES 3 / PROFIT_FACTOR 99.73 / WEEKS >= +1% 1/4 / POSITIVE WEEKS 2/4 / WORST DAY -2,031`
- 判断:
  - 不採用
- 再試行するとしたら:
  - `strong_oversold` の Tuesday low-open pocket が別期間で 3 件以上独立再現し、親集合が負の期待値を保つときだけ
  - 2 件しかない mixed pocket を単独で no-trade に広げない

### 2026-07-07: Rejected - Strong Oversold Pure-Win Band Broadening

- 試したこと:
  - `strong_oversold` の Wednesday / Thursday size-up 帯を `breadth 0.65-0.75` から `0.58-0.75` に広げ、train で増えていた `2023-02-09` / `2023-02-16` の追加 wins を取りにいった
  - holdout 側には同形状の trade はなかった
- 結果:
  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`
  - `FULL WINDOW: FINAL EQUITY Y76,286,719 / TOTAL RETURN +7528.67% / CLOSED TRADES 384 / WIN RATE 75.26% / PROFIT_FACTOR 23.52 / WEEKS >= +1% 101/227 / POSITIVE WEEKS 163/227 / MONTHS >= 3/4 ACTIVE 1/53 / WORST DAY -351,552`
  - `TRAIN WINDOW: FINAL EQUITY Y34,193,126 / TOTAL RETURN +3319.31% / CLOSED TRADES 337 / WIN RATE 77.74% / PROFIT_FACTOR 47.25 / WEEKS >= +1% 86/201 / POSITIVE WEEKS 144/201 / MONTHS >= 3/4 ACTIVE 1/46 / WORST DAY -39,018`
  - `HOLDOUT WINDOW: FINAL EQUITY Y76,286,719 / TOTAL RETURN +123.11% / CLOSED TRADES 47 / WIN RATE 57.45% / PROFIT_FACTOR 17.03 / WEEKS >= +1% 15/26 / POSITIVE WEEKS 19/26 / MONTHS >= 3/4 ACTIVE 0/7 / WORST DAY -351,552`
  - `100万円 standalone latest 1m: FINAL EQUITY Y1,066,763 / TOTAL RETURN +6.68% / CLOSED TRADES 1 / PROFIT_FACTOR inf / WEEKS >= +1% 1/4 / POSITIVE WEEKS 1/4 / WORST DAY 0`
- 判断:
  - 不採用
- 再試行するとしたら:
  - `strong_oversold` の breadth 下限を広げるなら、train の複利後成績が落ちないことを別期間で独立確認できたときだけ
### 2026-07-08: Rejected - Monday Fallback / Catchup RS Local Search

- 試したこと:
  - `fallback` の Monday mid-breadth / neutral-market / stable-open pocket の equity notional を `2.5 -> 2.7 -> 2.8 -> 2.9 -> 3.0` と局所探索した
  - `catchup_rs` の low-breadth / strong-continuation pocket は、score 下限を `10.0 -> 8.0` に広げて `6 trades / 6 wins / +1,058,066.94` まで増やした
  - さらに Monday fallback と `catchup_rs` score 8.0 を併用し、`2022-06` の落ち込みを補いながら `2025-05` を 20% 超にできるかも確認した
- 結果:
  - Monday fallback 単独では `2025-05` は `20.49%` まで伸びたが、`2022-06` が `27.83% -> 14.40%` まで落ち、train 全体の return は `3659.09% -> 3392.19%` に悪化した
  - `catchup_rs` score 8.0 単独では `2022-06` は `23.59%` まで戻ったが、`months >= 20%` は `2/56` のままで、train 全体 return は `3486.33%` だった
  - Monday fallback と `catchup_rs` score 8.0 の併用でも `months >= 20%` は増えず、`2024-01` は `19.67%` 付近で頭打ちだった
- 判断:
  - 不採用
- 再試行するとしたら:
  - `2022-06` を落とさずに `2025-05` を 20% 超へ押し上げられる、別の shared family が train に十分な再現数を持ったときだけ
  - それ以外は、月次 20% を狙って size-up を積み増すより、既存の高品質 pocket を維持して worst day を悪化させない方を優先する
### 2026-07-08: Rejected - Primary Size-Up Search

- 試したこと:
  - `catchup_rs` の low-breadth / strong-continuation pure-win pocket を `selected base leverage 0.35 -> 0.50` へ増やす what-if を確認した
  - `primary` の default notional を `0.15 -> 0.20` にした what-if を確認した
  - `primary` の default equity notional を `2.5 -> 3.0`、default risk budget を `0.10 -> 0.12` にした what-if を確認した
  - train-only の `high_breadth_mid_hot_market` pure-win pocket（10 trades / 10 wins）を `1.0 -> 2.0` にした what-if も確認したが、月次の押し上げは限定的だった
  - `5801.T` みたいな Tuesday default-like winner は 1 sample しかなく、Tuesday 専用 pocket はまだ作らない方がよいと判断した
- 結果:
  - combined what-if の best case は `FULL TOTAL RETURN +16312.28% / PROFIT_FACTOR 25.57 / WORST DAY -1,931,401円`
  - `TRAIN TOTAL RETURN +5645.99% / PROFIT_FACTOR 48.24 / WORST DAY -318,641円`
  - `HOLDOUT TOTAL RETURN +185.63% / PROFIT_FACTOR 20.59 / WORST DAY -1,931,401円`
  - `100万円 standalone latest 1m TOTAL RETURN +20.06% / CLOSED TRADES 3 / PROFIT_FACTOR 99.73`
  - month-by-month では `2025-08` が `~17.2%`、`2025-12` が `~14.2%` までで、`20% / month` の目標には届かなかった
- 判断:
  - 不採用
- 再試行するとしたら:
  - broad default equity / risk をさらに上げるのではなく、train で複数回再現する shared pocket が見つかったときだけ
  - 単発の Tuesday default-like winner を理由に曜日専用 pocket を増やさない
### 2026-07-08: Rejected - Further Pure-Win Size-Up Lift

- 試したこと:
  - `primary` の Wednesday mid/hot stable-gap size-up を `3.0 -> 4.0` にした what-if を確認した
  - `primary` の Wednesday high-breadth / hot-market / stable-gap size-up を `3.0 -> 4.0` にした what-if を確認した
  - `primary` の Friday high-breadth / hot-market / stable-gap size-up を `6.0 -> 7.0` にした what-if を確認した
  - `strong_oversold` の Wednesday / Thursday pure-win size-up を `4.0 -> 5.0` にした what-if を確認した
  - `primary` の high-breadth / hot-market / large-gap high-score size-up を `3.0 -> 4.0`、さらに stronger band を `4.0 -> 5.0` にした what-if を確認した
- 結果:
  - `FULL RETURN +12117.42% / FINAL EQUITY 122,174,229 / WORST DAY -1,427,556円`
  - `TRAIN RETURN +4649.49% / FINAL EQUITY 47,494,905 / WORST DAY -248,510円`
  - `HOLDOUT RETURN +157.24% / FINAL EQUITY 122,174,229 / WORST DAY -1,427,556円`
  - `2025-08 +15.27% / 2025-10 +8.09% / 2025-11 +21.62% / 2025-12 +12.23%`
  - `train の MONTHS >= 20% は 6/55 のままで、月次 20% 目標を埋め切れなかった`
- 判断:
  - 不採用
- 再試行するとしたら:
  - 2〜3 件以上の shared repetition がある pocket だけを対象にする
  - 5801.T / 8550.T / 4446.T のような単発 large-winner を個別に太らせる方向は採らない
### 2026-07-08: Rejected - Narrow B Pure-Win Size-Up

- 試したこと:
  - `primary` の 2025-11〜2025-12 pure-win box（`breadth 0.60-0.69` / `market_ratio 1.19-1.22` / `score 5.5-8.5` / `gap -0.5%~0.5%` / `open_vs_sma_atr 1.8-3.0`）だけを `equity notional 5.0` に引き上げる shared size-up を確認した
- 結果:
  - `TRAIN RETURN +4624.55% / PROFIT_FACTOR 44.74 / MONTHS >= 20% 6/55`
  - `2025-12 17.93%` まで改善したが、`20% / month` には届かなかった
  - `HOLDOUT RETURN +157.33% / WORST DAY -1,427,557円`
  - `100万円 standalone +18.16%`
- 判断:
  - 不採用
- 再試行するとしたら:
  - 2025-12 の pure-win 5 本に対して、独立した追加因子が train で再現したときだけ
### 2026-07-08: Rejected - A3/B5 Retrim

- 試したこと:
  - August 側の pure-win box を `equity notional 3.0` に弱め、上記 B-box は維持した shared retrim を確認した
- 結果:
  - `TRAIN RETURN +4798.62% / PROFIT_FACTOR 45.96 / MONTHS >= 20% 6/55`
  - `2025-08 15.90%`、`2025-12 17.92%` までで、月次 20% の本筋には届かなかった
- 判断:
  - 不採用
- 再試行するとしたら:
  - August の crowding-out を起こさない独立した pure-win subfamily が train で増えたときだけ

### 2026-07-08: Primary High-Confidence Notional Floor Lift Adopted

- 試したこと:
  - `primary` の `equity_notional_pct >= 3.0` に入る高信頼 continuation family に対して、`notional_pct` の下限を `0.15 -> 0.20` に引き上げた
  - 既存の `primary` 高信頼 size-up family はそのまま維持し、generic な notional floor だけを共有ロジックへ追加した
- 結果:
  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`
  - `FULL WINDOW: FINAL EQUITY Y159,485,234 / TOTAL RETURN +15848.52% / CLOSED TRADES 385 / WIN RATE 76.88% / PROFIT_FACTOR 25.75 / WEEKS >= +1% 102/228 / POSITIVE WEEKS 166/228 / MONTHS >= 3/4 ACTIVE 1/53 / WORST DAY -1,864,221`
  - `TRAIN WINDOW: FINAL EQUITY Y61,970,270 / TOTAL RETURN +6097.03% / CLOSED TRADES 343 / WIN RATE 76.97% / PROFIT_FACTOR 49.78 / WEEKS >= +1% 87/201 / POSITIVE WEEKS 145/201 / MONTHS >= 3/4 ACTIVE 1/46 / WORST DAY -343,035`
  - `HOLDOUT WINDOW: FINAL EQUITY Y159,485,234 / TOTAL RETURN +157.36% / CLOSED TRADES 42 / WIN RATE 76.19% / PROFIT_FACTOR 19.92 / WEEKS >= +1% 14/26 / POSITIVE WEEKS 20/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -1,864,221`
  - `100万円 standalone latest 1m: FINAL EQUITY Y1,200,562 / TOTAL RETURN +20.06% / CLOSED TRADES 3 / PROFIT_FACTOR 99.73 / WEEKS >= +1% 1/5 / POSITIVE WEEKS 2/5 / WORST DAY -2,031`
- 判断:
  - 採用
- 再試行するとしたら:
  - `primary_equity_notional_pct >= 3.0` の shared family が train の別期間で独立再現したときだけ
  - それ以外は、曜日専用の単発 winner を理由にさらに細分化しない

### 2026-07-08: Rejected - Primary High-Confidence Floor / Broad Family Sensitivity Check

- 試したこと:
  - `primary` の high-confidence continuation family（`primary_equity_notional_pct >= 3.0`）の `notional_pct` 下限を `0.20 -> 0.25 -> 0.30` と引き上げた what-if を確認した
  - `primary` の broader high-breadth / hot-market / stable-gap / mid-high-score pure-win pocket の `equity_notional_pct` を `6.0 -> 7.0` にした what-if も確認した
- 結果:
  - `0.25` では `FULL RETURN +16075.67% / TRAIN RETURN +6186.76% / HOLDOUT RETURN +157.30%`
  - `0.30` では `FULL RETURN +16313.60% / TRAIN RETURN +6279.14% / HOLDOUT RETURN +157.30%`
  - `2025-11` は `25.26% -> 27.11%` まで改善したが、`2025-12` は `17.71%` のままで、`MONTHS >= 20%` は `6/47` のままだった
  - broad family の `equity_notional_pct 6.0 -> 7.0` は current cap stack では実効変化が出ず、月次改善にもつながらなかった
  - holdout の worst day は `-1,864,221円 -> -1,931,401円` まで悪化した
- 判断:
  - 不採用
- 再試行するとしたら:
  - 月次 20% を本当に押し上げるために、単純な notional floor / equity cap の上積みではなく、train で複数回再現する別の shared subfamily が見つかったときだけ
  - `4446.T` のような単発 large-winner を個別に太らせる方向は採らない
### 2026-07-08: Primary High-Confidence Tue-Fri Risk Budget Lift Adopted

- 試したこと:
  - `primary` の high-confidence continuation family（`primary_equity_notional_pct >= 3.0`）に対して、Tue-Fri の risk budget を `0.10 -> 0.25` に引き上げた
  - `primary_equity_notional_pct` を shared helper へ渡し、Monday singleton は除外した
  - 既存の Thu/Fri high-confidence notional floor `0.25` は維持した
- 結果:
  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`
  - `FULL WINDOW: FINAL EQUITY Y221,631,494 / TOTAL RETURN +22063.15% / CLOSED TRADES 387 / WIN RATE 76.74% / PROFIT_FACTOR 26.35 / WEEKS >= +1% 102/228 / POSITIVE WEEKS 166/228 / MONTHS >= 3/4 ACTIVE 1/53 / WORST DAY -2,603,192`
  - `TRAIN WINDOW: FINAL EQUITY Y82,688,127 / TOTAL RETURN +8168.81% / CLOSED TRADES 345 / WIN RATE 76.81% / PROFIT_FACTOR 54.17 / WEEKS >= +1% 87/201 / POSITIVE WEEKS 145/201 / MONTHS >= 3/4 ACTIVE 1/46 / WORST DAY -458,905`
  - `HOLDOUT WINDOW: FINAL EQUITY Y221,631,494 / TOTAL RETURN +168.03% / CLOSED TRADES 42 / WIN RATE 76.19% / PROFIT_FACTOR 20.38 / WEEKS >= +1% 14/26 / POSITIVE WEEKS 20/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -2,603,192`
  - `100万円 standalone latest 1m: FINAL EQUITY Y1,200,562 / TOTAL RETURN +20.06% / CLOSED TRADES 3 / PROFIT_FACTOR 99.73 / WEEKS >= +1% 1/5 / POSITIVE WEEKS 2/5 / WORST DAY -2,031`
  - `train full months >=20%: 8/55`
- 判断:
  - 採用
- 再試行するとしたら:
  - `primary_equity_notional_pct >= 3.0` の Tue-Fri shared family が別期間で独立再現したときだけ
  - Monday singleton を含めた広げ方や、score / breadth / gap の細分化で当て込みを増やさない

### 2026-07-08: Friday High-Breadth Hot-Market Stable-Gap Pure-Win Size-Up Adopted

- 試したこと:
  - `primary` の Friday high-breadth / hot-market / stable-gap / high-score pure-win pocket を `6.0 -> 7.0` に引き上げた
  - 既存の high-confidence notional floor と Tue-Fri risk budget の stack を維持したまま、train-supported な Friday の pure-win family だけを太らせた
  - 4 件の独立再現がある shared pocket で、単発勝ちの個別当て込みではないことを確認した
- 結果:
  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`
  - `FULL WINDOW: FINAL EQUITY Y225,095,514 / TOTAL RETURN +22409.55% / CLOSED TRADES 387 / WIN RATE 76.74% / PROFIT_FACTOR 26.42 / WEEKS >= +1% 103/228 / POSITIVE WEEKS 166/228 / MONTHS >= 3/4 ACTIVE 1/53 / WORST DAY -2,636,782`
  - `TRAIN WINDOW: FINAL EQUITY Y83,980,336 / TOTAL RETURN +8298.03% / CLOSED TRADES 345 / WIN RATE 76.81% / PROFIT_FACTOR 54.75 / WEEKS >= +1% 88/201 / POSITIVE WEEKS 145/201 / MONTHS >= 3/4 ACTIVE 1/46 / WORST DAY -466,528`
  - `HOLDOUT WINDOW: FINAL EQUITY Y225,095,514 / TOTAL RETURN +168.03% / CLOSED TRADES 42 / WIN RATE 76.19% / PROFIT_FACTOR 20.41 / WEEKS >= +1% 14/26 / POSITIVE WEEKS 20/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -2,636,782`
  - `100万円 standalone latest 1m: FINAL EQUITY Y1,200,562 / TOTAL RETURN +20.06% / CLOSED TRADES 3 / PROFIT_FACTOR 99.73 / WEEKS >= +1% 1/5 / POSITIVE WEEKS 2/5 / WORST DAY -2,031`
  - `train full months >=20%: 9/55`
  - `2023-06` が `20.25%`、`2025-05` が `20.48%`、`2025-12` が `20.63%` まで上がった
- 判断:
  - 採用
- 再試行するとしたら:
  - `primary_equity_notional_pct >= 3.0` の高信頼 stack の下で、さらに独立再現が増えた shared subfamily が見つかったときだけ
  - Friday 単独の単発 winner を理由に、score / breadth / gap を細かく切り過ぎない


### 2026-07-09: Rejected - Fallback / Strong Oversold Month-Count Search

- 試したこと:
  - `strong_oversold` の weekday pure-win / Monday hot-stable の shared size-up と、`fallback` の high-confidence / Monday neutral-market / Wednesday hot-open size-up を current replay で what-if 評価した
  - 早い月の強い勝ちを少し抑えながら、後半の fallback / strong_oversold の月次を押し上げる組み合わせも含めて、`months >= 20%` の件数を直接最適化した
- 結果:
  - current replay の full-month simulation では `MONTHS >= 20%` は `14/55` から改善しなかった
  - aggressive size-up は `2023-04` や `2025-01` を押し上げる一方で、他の later months を 20% 未満へ押し下げ、総件数の改善にはつながらなかった
  - holdout overlap がない train-only fallback pockets はあったが、月次 20% の count 目標にはまだ届かなかった
- 判断:
  - 不採用
- 再試行するとしたら:
  - train で別の shared pocket が 2〜3 回以上独立再現し、かつ later-month の分母を崩しにくい形で見つかったときだけ
  - 既存の強い shared pocket を単純に太らせるだけの再探索はしない

### 2026-07-09: Current Baseline Revalidate

- 確認したこと:
  - `python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1`
  - `python analyze_backtest_trade_log.py --holdout-months 6 --top-n 20 --output-trades-csv tmp\train_trade_log_current.csv`
  - train の full calendar months では `MONTHS >= 20%` が `17/55`
  - 20% 超の月は `2022-06 27.83%`, `2022-09 30.92%`, `2023-02 25.62%`, `2023-04 22.49%`, `2023-06 26.46%`, `2024-01 35.39%`, `2024-02 26.59%`, `2024-03 31.31%`, `2024-05 41.62%`, `2024-07 25.70%`, `2025-05 20.50%`, `2025-06 22.87%`, `2025-08 22.39%`, `2025-09 56.67%`, `2025-10 23.63%`, `2025-11 23.48%`, `2025-12 23.60%`
  - 閾値直下の月は `2022-12 12.48%`, `2025-01 9.52%`, `2024-10 8.36%`
- 結果:
  - `FULL WINDOW: FINAL EQUITY Y566,879,383 / TOTAL RETURN +56587.94% / CLOSED TRADES 402 / WIN RATE 74.38% / PROFIT_FACTOR 27.07 / WEEKS >= +1% 105/228 / POSITIVE WEEKS 160/228 / MONTHS >= 3/4 ACTIVE 1/53 / WORST DAY -6,667,531`
  - `TRAIN WINDOW: FINAL EQUITY Y211,114,042 / TOTAL RETURN +21011.40% / CLOSED TRADES 360 / WIN RATE 74.17% / PROFIT_FACTOR 64.18 / WEEKS >= +1% 90/201 / POSITIVE WEEKS 139/201 / MONTHS >= 3/4 ACTIVE 1/46 / WORST DAY -1,172,417`
  - `HOLDOUT WINDOW: FINAL EQUITY Y566,879,383 / TOTAL RETURN +168.52% / CLOSED TRADES 42 / WIN RATE 76.19% / PROFIT_FACTOR 20.36 / WEEKS >= +1% 14/26 / POSITIVE WEEKS 20/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -6,667,531`
  - `100万円 standalone latest 1m: FINAL EQUITY Y1,200,562 / TOTAL RETURN +20.06% / CLOSED TRADES 3 / PROFIT_FACTOR 99.73 / WEEKS >= +1% 1/5 / POSITIVE WEEKS 2/5 / WORST DAY -2,031`
- 判断:
  - current baseline の再確認
- 再試行するとしたら:
  - `2022-12` など 20% から遠い月を単独で狙わず、train で 2〜3 回以上独立再現する shared pocket が見つかったときだけ

### 2026-07-10: Catchup RS Size Multiplier Wiring Adopted

- 試したこと:
  - 最新キャッシュを `2026-07-09` まで更新し、直近6ヶ月を `2026-01-13` から `2026-07-09` の reference / veto holdout として切り直した
  - 既存の `resolve_daytrade_catchup_size_multiplier()` が unit test では確認済みだった一方、実際の `catchup_rs` 候補 dict に `size_multiplier` が渡っていなかったため、共有戦略候補生成と backtest 実行側の両方に配線した
  - 新しい backtest 専用条件や個別銘柄条件は追加せず、既存の Tuesday low-breadth / high-RS shared helper を実際の sizing に反映させた
- 結果:
  - `python -m pytest tests\test_logic.py -q`: `143 passed`
  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`
  - `FULL WINDOW: FINAL EQUITY Y651,856,198 / TOTAL RETURN +65085.62% / CLOSED TRADES 403 / WIN RATE 73.95% / PROFIT_FACTOR 20.28 / WEEKS >= +1% 105/228 / POSITIVE WEEKS 161/228 / MONTHS >= 3/4 ACTIVE 1/53 / WORST DAY -8,549,403`
  - `TRAIN WINDOW: FINAL EQUITY Y260,106,451 / TOTAL RETURN +25910.65% / CLOSED TRADES 361 / WIN RATE 73.96% / PROFIT_FACTOR 69.65 / WEEKS >= +1% 91/202 / POSITIVE WEEKS 141/202 / MONTHS >= 3/4 ACTIVE 1/46 / WORST DAY -1,366,042`
  - `HOLDOUT WINDOW: FINAL EQUITY Y651,856,198 / TOTAL RETURN +150.61% / CLOSED TRADES 42 / WIN RATE 73.81% / PROFIT_FACTOR 14.07 / WEEKS >= +1% 14/26 / POSITIVE WEEKS 20/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -8,549,403`
  - `100万円 standalone latest 1m: FINAL EQUITY Y1,200,562 / TOTAL RETURN +20.06% / CLOSED TRADES 3 / PROFIT_FACTOR 99.73 / WEEKS >= +1% 1/4 / POSITIVE WEEKS 2/4 / WORST DAY -2,031`
  - train full calendar months の `MONTHS >= 20%` は `17/55 -> 19/55` に改善した
  - `2022-12` と `2024-10` が 20% 超へ乗った一方、train worst day は `-1,172,417円 -> -1,366,042円` に悪化した
- 判断:
  - 採用
  - 理由は、新規の当て込み条件ではなく、既存の共有 helper が実候補に届いていなかった根本的な配線漏れの修正であり、train の月次20%件数、総リターン、positive weeks が改善したため
  - ただし損失集中は悪化しているため、次の改善はさらなる size-up ではなく、未達月・未達週の候補不足や warmup / no-trade 原因の分析を優先する
- 再試行するとしたら:
  - `catchup_rs` をさらに太らせるのではなく、未選択候補を含む train-only 分布で複数月に再現する別の shared edge が見つかったときだけ
  - holdout の見た目改善を理由に閾値を詰めない

### 2026-07-10: Rejected - Residual Selected-Trade Broad Size-Up

- 試したこと:
  - 修正後の train trade log から、残る 20% 未達月に効きうる selected-trade の曜日、setup、breadth、gap、market_ratio、score、RS family を再集計した
  - `primary Wednesday gap 1.5%-2.0%`、`primary market_ratio 1.0-1.05 / prev_return 3%-5%`、`fallback Monday`、`catchup_rs Tuesday` などの候補を確認した
- 結果:
  - `primary Wednesday gap 1.5%-2.0%` は `12 trades / 11 wins / net +6,353,309` と強いが、既に Wednesday hot-gap 系は過去に探索済みで、残る月次20%未達の大半を解決するには不足していた
  - `fallback Monday` と広めの `catchup_rs Tuesday` は過去ログで近傍探索済み、または broad 化すると既存の損失も同時に太るため、今回の配線修正後に重ねる根拠が弱かった
  - 残る未達月には `2021-06` から `2022-02` の warmup / 集計除外影響が強い月と、`2022-03` 以降の実 no-trade / 低頻度月が混在し、現在の 200 日系指標と backtest warmup 前提では sizing だけで到達できない
- 判断:
  - 不採用
  - selected-trade の追加 size-up は、月次20%件数を大きく増やすよりも損失集中と既探索の重複を増やすリスクが高い
- 再試行するとしたら:
  - 未選択候補を含めた train-only candidate log を作り、warmup 後の no-trade 月や未達月に共通する entry quality の欠落を確認してから
  - 早期 warmup 月を評価対象に含めるなら、過去データ開始を前倒しして signal 用の前史を確保する

### 2026-07-10: Rejected - Candidate Log Broad Expansion / Loss Guard Search

- 試したこと:
  - `run_backtest_v16_production(..., return_candidate_log=True)` を追加し、戦略挙動を変えずに日次 reason と generated candidate の `selected / not_selected / opened / blocked` を記録できるようにした
  - `analyze_daytrade_candidate_log.py --holdout-months 6 --top-n 30` で train-only の未選択候補、blocked 候補、no-trade day reason を確認した
  - 事前に観測できる `setup_type`、曜日、breadth、market_ratio、gap、prev_return、RSI、RS、score、open_vs_sma_atr だけで粗い regime bin を作り、複数月に再現する shared edge が残っているか確認した
- 結果:
  - train 診断: `TRAIN DAYS 946 / TRAIN CANDIDATES 28,554 / TRAIN TRADES 361`
  - 日次 reason: `opened 361`, `selected_not_opened 208`, `selected_leverage_blocked 206`, `no_candidates 82`, `weekly_profit_guard 71`, `market_gate_blocked 18`
  - broad な未選択候補はすべて平均マイナス: `strong_oversold not_selected avg -1,224円/100株`, `catchup_rs not_selected avg -1,603円/100株`, `fallback not_selected avg -1,606円/100株`, `primary not_selected avg -568円/100株`
  - 粗い bin で唯一それらしいプラス群は `catchup_rs / Thursday / score 8-10 / RS 40-60` の `40 candidates / 22 months / avg +383円/100株 / win 55.0% / worst -13,165円/100株` 程度で、月次20%を押し上げるには弱く、損失側も浅くない
  - opened trade の損失集中は `2026-01-06 primary -1,366,042円` が突出したが、同じ hot-market primary family は train 全体で大きな利益源でもあり、火曜 hot-market を broad に削ると利益側を壊す可能性が高かった
  - `python -m pytest tests\test_logic.py tests\test_backtest.py tests\test_analyze_backtest_trade_log.py tests\test_jp_backtest.py -q`: `178 passed`
  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1` は採用 baseline と同じ `FULL RETURN +65085.62% / TRAIN RETURN +25910.65% / HOLDOUT RETURN +150.61% / standalone +20.06%`
- 判断:
  - 不採用
  - 未選択候補を broad に足す案は、期待値が崩れている候補を大量に拾うため、月次20%より損失集中を増やすリスクが高い
  - 損失集中 guard も、現時点の粗い shared regime では利益源を削る副作用の方が大きく、採用できない
- 再試行するとしたら:
  - same-day の結果を条件に使わず、未選択候補の中で事前特徴だけから `min 2-3 independent months` 以上、かつ平均損益・worst trade・negative month が明確に改善する shared subfamily が出たときだけ
  - no-candidate / market-gate 月をさらに掘る場合は、scan 前の reject reason と market gate の内訳を別ログ化して、候補生成以前に何が欠けているかを見る

### 2026-07-10: Rejected - No-Candidate Broad ETF Probe

- 試したこと:
  - `candidate_log` の日次 summary に `scan_*` と `setup_*` counters を追加し、`no_candidates` / `market_gate_blocked` の内訳を train-only で確認した
  - `no_candidates` 日に既存 ETF universe（inverse ETF と bull ETF）を open-close で仮に入れた場合の方向性を確認した
  - 実装前の仮説確認として、1321.T を `no_candidates` 日だけ `10% / 25% / 50% / 100%` equity で足した場合の概算月次も確認した
- 結果:
  - `no_candidates` は流動性だけで全滅しているわけではなく、多くの日で `600-900` 銘柄程度が scan を通ったあと、既存 setup quality に届いていなかった
  - no-trade 日の主な内訳は `scan_turnover_blocked 410,714`, `setup_no_setup_candidate_after_scan 336,567`, `scan_raw_nan 16,832`, `scan_price_blocked 9,797`
  - `market_gate_blocked` は `2022-03` の warmup / market_ratio NaN が中心で、戦略拡張対象ではなかった
  - `no_candidates` 日の inverse ETF は平均マイナスだった: 例 `1459.T avg -0.66%`, `1360.T avg -0.67%`, `1357.T avg -0.52%`
  - bull ETF は平均プラスだったが、レバ ETF は worst が深く、低ボラの `1321.T` でも `avg +0.28% / worst -6.92%`
  - `1321.T` を `no_candidates` 日に足す概算では、`10% / 25% / 50% / 100%` equity のいずれも train full months `>=20%` は `19/47` のまま改善せず、`2022-04` や `2023-12` の低リターン月を悪化させた
- 判断:
  - 不採用
  - ETF probe は総資産を少し押し上げる可能性はあるが、月次20%件数の改善にはつながらず、目的に対してリスク対効果が弱い
  - inverse ETF は no-candidate 日の broad fallback としては期待値が崩れており、採用不可
- 再試行するとしたら:
  - no-candidate 日を一律に埋めるのではなく、setup quality に届かなかった銘柄群の中で、事前特徴だけから複数月に再現する明確な intraday edge が出たときだけ
  - それが出ない限り、低頻度月を無理に埋めるより、既存 selected trade の risk-adjusted sizing と損失集中抑制を優先する

### 2026-07-10: Rejected - Setup-Miss Near-Candidate Expansion

- 試したこと:
  - `no_candidates` 日だけを対象に、scan は通過したが primary / fallback / strong_oversold / catchup / ETF / inverse setup に届かなかった銘柄を train-only で再構成した
  - 事前に観測可能な `weekday`、`breadth`、`market_ratio`、`gap_pct`、`prev_return`、`prev_rsi2`、`rs_alpha`、`open_vs_sma_atr`、既存 score proxy で粗い bin を作り、同日 open entry / 当日 exit の保守的な損益ラベルを確認した
  - same-day 損益は条件には使わず、entry 前特徴で説明できる shared edge があるかだけを見た
- 結果:
  - 対象は `no_candidate_days 82` のうち train 内 `setup_miss_rows 56,891`
  - 全体は `avg -724.6円/100株 / total -41,222,719円/100株 / win 42.6% / worst -47,979円/100株`
  - 一部の曜日 / breadth / gap bin は平均プラスだったが、`days 4-9` 程度の単発寄りで、厳しめ条件 `n>=25 / months>=5 / avg>200円 / worst>-12,000円` では採用候補なし
  - 既存 score proxy で日別 top 1 を選んでも、`primary_proxy top: 81日 / avg -2,395円 / win 33.3% / worst -28,878円`、`fallback_proxy top: 81日 / avg -1,000円 / win 44.4% / worst -28,878円`
- 判断:
  - 不採用
  - setup に届かなかった scan 通過銘柄は、薄い日を埋める候補ではなく、品質基準で正しく落ちている側だった
  - 月次20%未達を埋めるためにここを広げると、候補数は増えるが損失期待値を大量に足す可能性が高い
- 再試行するとしたら:
  - setup miss 全体ではなく、外部から説明できる新しい pre-entry regime 指標が追加され、その指標だけで複数月・複数日・浅い worst を満たすときだけ
  - 今回見た粗い `breadth / market_ratio / gap / RS / RSI / open_vs_sma` 近傍を同じ形で再探索しない

### 2026-07-10: Rejected - Selected-Blocked / Weekly-Lock Rescue Recheck

- 試したこと:
  - `selected_not_opened` / `selected_leverage_blocked` 日について、選ばれたが約定しなかった候補の modeled 損益を train-only で再確認した
  - `block_reason`、setup、曜日、月、`market_ratio`、score bin で、board-lot rescue や weekly lock 解除に値する shared edge が残っているかを確認した
  - 20%未達月を月次で分解し、`no_candidates`、weekly guard、selected blocked、opened trade、worst day のどれが主因かを確認した
- 結果:
  - selected blocked は全体として弱い: `not_reached_after_prior_break 2,516件 avg -969円/100株`, `capped_lot_below_100 1,537件 avg -2,667円/100株`, `selected_leverage_zero 1,314件 avg -1,445円/100株`, `max_positions_reached 304件 avg -1,368円/100株`
  - 一見プラスだった `primary / Tuesday / selected_leverage_zero` は候補単位 `78件 / avg +1,037円` だったが、日別 rank1 では `8日 / avg -2,117円 / win 25.0% / worst -8,371円` に崩れた
  - 実現 trade の損失側で見える broad な悪化帯は `primary / Tuesday / market_ratio 1.20+` と `primary / Tuesday / score 5-6` だが、前者は `5 trades / 4 months / total -908,952円` のうち `2026-01-06` 単日損失の寄与が大きく、同じ high market family の別曜日は大きな利益源でもあった
  - train post-warmup 月次は `47ヶ月中 19ヶ月 >= +20%`。20%未達月に `10%-20%` の近接月はなく、多くは `0%-9%` 台かマイナスで、週次 profit guard が主因ではなかった
- 判断:
  - 不採用
  - selected blocked を rescue する broad 施策は、約定しなかったことで避けられている負け候補を戻す形になりやすい
  - 火曜 high-market primary の単発損失だけを消す guard は train 1日への当て込み色が強く、同じ family の profit source を削るリスクが高い
- 再試行するとしたら:
  - selected blocked 側ではなく、実現 trade の損失集中に対して、複数年・複数月に再現する pre-entry risk feature が見つかったときだけ
  - 月次20%全月化を狙うなら、既存 gate 緩和ではなく、別の独立した intraday edge を追加できるデータソースや特徴量が必要

### 2026-07-10: Adopted - Primary Breakeven Failed-Runup Exit

- 試したこと:
  - `primary` の failed-runup exit を、従来の「entry 後に `+2.0%` 以上走ってから建値以下へ戻ったら撤退」から、「一度でも建値を上回った後に建値以下へ戻ったら撤退」へ変更した
  - これは個別銘柄や特定月の条件ではなく、全 `primary` に共通する intraday risk management として扱った
  - daily OHLC backtest では stop / target を先に優先し、stop に触れた日は従来通り stop を採用するため、損失側を都合よく消す専用分岐にはしていない
- 結果:
  - `python -m pytest tests\test_logic.py tests\test_backtest.py -q`: `166 passed`
  - `python -m pytest tests -q`: `397 passed, 38 subtests passed`
  - `python jp_backtest.py --holdout-months 6 --standalone-latest-months 1`
  - `FULL WINDOW: FINAL EQUITY Y708,232,830 / TOTAL RETURN +70723.28% / CLOSED TRADES 404 / WIN RATE 74.01% / PROFIT_FACTOR 25.18 / WEEKS >= +1% 105/228 / POSITIVE WEEKS 166/228 / MONTHS >= 3/4 ACTIVE 1/53 / WORST DAY -9,278,045`
  - `TRAIN WINDOW: FINAL EQUITY Y279,561,337 / TOTAL RETURN +27856.13% / CLOSED TRADES 362 / WIN RATE 74.03% / PROFIT_FACTOR 118.20 / WEEKS >= +1% 91/202 / POSITIVE WEEKS 146/202 / MONTHS >= 3/4 ACTIVE 1/46 / WORST DAY -396,859`
  - `HOLDOUT WINDOW: FINAL EQUITY Y708,232,830 / TOTAL RETURN +153.34% / CLOSED TRADES 42 / WIN RATE 73.81% / PROFIT_FACTOR 16.95 / WEEKS >= +1% 14/26 / POSITIVE WEEKS 20/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -9,278,045`
  - `100万円 standalone latest 1m: FINAL EQUITY Y1,200,562 / TOTAL RETURN +20.06% / CLOSED TRADES 3 / PROFIT_FACTOR 99.73 / WEEKS >= +1% 1/4 / POSITIVE WEEKS 2/4 / WORST DAY -2,031`
  - train full calendar months の `MONTHS >= 20%` は `19/55` のまま、目標の全月20%には未達
  - train の `negative full calendar months` は `3 -> 1`、train `WORST DAY` は `-1,366,042円 -> -396,859円`、train PF は `69.65 -> 118.20` に改善
- 判断:
  - 採用
  - 理由は、特定銘柄・特定月に合わせた entry 条件ではなく、建値を一度上回った primary が再び建値割れしたら損失を浅くするという本番監視でも再現可能な shared exit であり、train の損失集中と PF を大きく改善したため
  - holdout は contaminated / veto 用だが、PF と total return は改善し、悪化 veto には該当しない。ただし full / holdout の absolute worst day は資産増加に伴って大きくなっているため、次は absolute notional / drawdown の抑制を別途見る
- 再試行するとしたら:
  - failed-runup 閾値を細かく `0.5%`, `0.75%`, `1.0%` などで追わない。今回の採用理由は閾値最適化ではなく、建値回復後の損失化を避ける shared risk rule として説明できる点にある
  - さらに改善するなら、entry 条件ではなく、absolute notional cap / volatility-aware size / 大資産時の損失額制御を train-only で見る

### 2026-07-10: Rejected - Tuesday Primary Residual Hot-Market Guard

- 試したこと:
  - 廉価 explorer と並行して、realized losing trades を train post-warmup で再分解し、`primary / Tuesday` の残余損失 pocket を確認した
  - 候補条件は `primary AND Tuesday AND score 4-7 AND gap_pct 0-1% AND prev_rsi2 50-75`、またはより hot-market 寄りの `market_ratio >= 1.1` 追加
- 結果:
  - 広い pocket は `22 trades / 19 months / total -1,108,792円` だが、損失の大半は `2026-01-06` の単日事故に寄っていた
  - `market_ratio >= 1.1` 追加では `11 trades / 9 months / total -1,228,133円` と利益側副作用は小さいが、trade 数が薄く、既存 Tuesday guard のすき間をさらに細かく埋める形になる
  - failed-runup exit 採用後は、同じ `2026-01-06` の損失集中が大きく浅くなり、この pocket を entry 側で削る必要性が下がった
- 判断:
  - 不採用
  - 火曜 primary の残余 guard は説明可能性はあるが、採用根拠が単日損失に寄りすぎており、既存 Tuesday guard 群への細かい追加としてカーブフィット色が強い
- 再試行するとしたら:
  - 同じ条件をさらに細かく詰めない
  - 複数年・複数局面で同じ pre-entry risk が、failed-runup exit 適用後にも再現する場合だけ再検討する

### 2026-07-10: Rejected - Broad Absolute Notional Cap

- 試したこと:
  - failed-runup exit 採用後の残課題として、資産増加後の absolute worst day を抑えるため、全 setup に broad な trade notional cap を仮に追加した what-if を確認した
  - cap は `500M / 300M / 200M / 100M / 50M` 円で比較し、entry 条件や exit 条件は変えなかった
- 結果:
  - cap なし baseline: `FULL RETURN +70723.28% / TRAIN RETURN +27856.13% / HOLDOUT RETURN +153.34% / FULL PF 25.18 / TRAIN PF 118.20 / HOLDOUT PF 16.95 / FULL WORST DAY -9,278,045 / TRAIN WORST DAY -396,859`
  - `500M cap`: `FULL RETURN +41718.83% / TRAIN RETURN +23077.76% / HOLDOUT RETURN +80.43% / HOLDOUT PF 12.63 / FULL WORST DAY -5,464,817 / TRAIN WORST DAY -330,647`
  - `300M cap`: `FULL RETURN +30581.39% / TRAIN RETURN +18845.16% / HOLDOUT RETURN +61.95% / HOLDOUT PF 6.27 / FULL WORST DAY -10,631,120`
  - `100M cap`: `FULL RETURN +14940.99% / TRAIN RETURN +10569.34% / HOLDOUT RETURN +40.97% / FULL WORST DAY -3,542,388`
  - cap を厳しくすると absolute worst は下がる局面があるが、利益源と compounding を大きく削り、holdout PF / return も明確に悪化した
- 判断:
  - 不採用
  - broad notional cap は「最小限のマイナス」には効くが、月次20%目標と最大利益の主目的を大きく壊す。特に `500M cap` でも holdout return がほぼ半減し、採用するには副作用が大きすぎる
  - absolute loss control をやるなら、全 setup 一律 cap ではなく、setup / regime / liquidity / volatility に応じた risk-adjusted cap を train-only で別途設計する必要がある
- 再試行するとしたら:
  - 全体 cap ではなく、損失寄与が大きく、かつ利益源ではない narrow shared regime に限定できるときだけ
  - cap の目的を「absolute worst day」だけにせず、月次20%件数、PF、positive weeks、holdout veto を同時に満たせるかで判断する

### 2026-07-10: Rejected - Zero-Base Sizing Dependency Audit

- 試したこと: 現行 entry 候補は固定し、primary の個別 equity/notional/risk/size 例外と selected leverage の個別例外を、既定の shared sizing に置き換えた診断 replay を train-only で実施した。
- 結果:
  - 簡素化 replay は `TRAIN RETURN +556.43% / PF 1.96 / WEEKS >= +1% 76/202 / POSITIVE WEEKS 100/202 / WORST DAY -203,415 / CLOSED TRADES 554` となった。
  - 現行 baseline は `TRAIN RETURN +27856.13% / PF 118.20 / WEEKS >= +1% 91/202 / POSITIVE WEEKS 146/202 / WORST DAY -396,859 / CLOSED TRADES 362` であり、成績差は細分化した sizing / leverage 例外への依存が大きいことを示した。
- 判断:
  - 不採用。簡素化はカーブフィットを下げる方向だが、現在の daily OHLC データと既存 entry のままでは、月次20%目標や週次目標に届かない。
- 再試行するとしたら:
  - 個別例外を少しずつ復活させない。分足・約定・板などの新しい事前情報を追加し、独立した edge をゼロベースで構築できる場合だけ再設計する。

### 2026-07-10: Rejected - Post-Size Liquidity Participation Cap

- 試したこと: 本番・backtest 共通の `cap_daytrade_position_size()` に、前日売買代金の `2.5%` を board lot 単位で上限化する generic な post-size cap を追加して検証した。
- 結果:
  - `python -m pytest tests\\test_logic.py tests\\test_backtest.py -q`: `166 passed`。
  - `TRAIN RETURN +7595.37% / PF 15.14 / WEEKS >= +1% 86/202 / POSITIVE WEEKS 145/202 / WORST DAY -2,213,221 / CLOSED TRADES 370` と baseline を大きく下回り、最悪日も悪化した。standalone 最新1ヶ月は `+20.06%` のまま。
- 判断:
  - 不採用。流動性制約は実運用上正しいが、lot 未満になった上位候補を次順位候補へ差し替える既存 shared selection と相互作用し、経路を悪化させた。
- 再試行するとしたら:
  - 上位候補が participation cap を満たさない日は lower-ranked candidate へ差し替えず no-trade にする、という shared execution policy を独立に検証する場合だけ。ただしこれは稼働率を下げるため、月次20%目標への寄与を先に train-only で確認する。
### 2026-07-10: Data Capability Audit / Future Clean-Holdout Instrumentation

- 試したこと:
  - J-Quants 取得器、kabu.com の quote / broker 実装、日中ログ、注文ジャーナルを監査し、ゼロベースの intraday edge を検証できる履歴の有無を確認した。
  - 将来の観測用に、shared strategy が生成した候補、sizing 対象、board lot 不成立、simulation / live の実エントリーを `daytrade_decisions.csv` へ記録するようにした。
  - テスト時は decision / exit / snapshot の runtime log を一時ディレクトリへ隔離した。
- 結果:
  - キャッシュは日足 OHLCV のみで、分足、約定、板、注文イベントの時系列履歴はない。
  - 既存の intraday exit log は test fixture 由来で、実トレードを分析できる記録ではない。decision / snapshot の実観測ログも未蓄積である。
  - 追加した判断ログは `trade_mode` と `is_simulation` を必須記録し、KABUCOM_TEST と simulation を将来の KABUCOM_LIVE clean holdout から分離する。
  - `python -m pytest tests -q`: `398 passed, 38 subtests passed`。
- 判断:
  - 戦略変更は不採用。履歴日足だけから日中 execution edge を再設計すると、現行の細分化 sizing を別のカーブフィットで置き換えるだけになる。
  - 次の clean holdout は `2026-07-10` 以降の実観測として固定し、KABUCOM_LIVE かつ非 simulation の判断・注文・約定・保有中 quote を蓄積してから train-only で再設計する。
- 再試行するとしたら:
  - 同一銘柄・同一時刻帯の分足 OHLCV、best bid/ask と数量、注文送信・取消・部分約定・手数料を時系列で取得できる外部履歴を導入する場合。
  - または上記の本番観測を十分な件数で蓄積し、日中の実際の adverse selection、slippage、exit path を train にだけ含められる場合。

### 2026-07-11: Adopted - JPX Tick-Normalized Backtest Execution

- 試したこと:
  - v16 の候補モデル約定と実約定について、買値を上方向、売値を下方向へ `normalize_tick_size()` で丸めるようにした。
  - JPX の呼値単位を確認し、銘柄区分を持たない現行日足データでは、`core.logic` の一般銘柄向け保守的 ladder を共通利用した。
  - entry / exit 条件や資金配分は変更せず、連続価格で都合よく約定できる楽観だけを除いた。
- 結果:
  - `python -m pytest tests\\test_backtest.py tests\\test_logic.py -q`: `167 passed`。
  - `python -m pytest tests -q`: `399 passed, 38 subtests passed`。
  - `FULL WINDOW: FINAL EQUITY Y476,117,832 / TOTAL RETURN +47511.78% / CLOSED TRADES 403 / WIN RATE 67.00% / PROFIT_FACTOR 21.48 / WEEKS >= +1% 103/228 / POSITIVE WEEKS 159/228 / MONTHS >= 3/4 ACTIVE 1/53 / WORST DAY -6,425,000`。
  - `TRAIN WINDOW: FINAL EQUITY Y192,641,350 / TOTAL RETURN +19164.13% / CLOSED TRADES 361 / WIN RATE 66.76% / PROFIT_FACTOR 49.63 / WEEKS >= +1% 89/202 / POSITIVE WEEKS 139/202 / MONTHS >= 3/4 ACTIVE 1/46 / WORST DAY -1,130,500`。
  - `HOLDOUT WINDOW: FINAL EQUITY Y476,117,832 / TOTAL RETURN +147.15% / CLOSED TRADES 42 / WIN RATE 69.05% / PROFIT_FACTOR 15.72 / WEEKS >= +1% 14/26 / POSITIVE WEEKS 20/26 / MONTHS >= 3/4 ACTIVE 0/6 / WORST DAY -6,425,000`。
  - `100万円 standalone latest 1m: FINAL EQUITY Y1,197,033 / TOTAL RETURN +19.70% / CLOSED TRADES 3 / PROFIT_FACTOR 94.83 / WEEKS >= +1% 1/4 / POSITIVE WEEKS 2/4 / WORST DAY -2,100`。
  - train full calendar months の `MONTHS >= 20%` は `19/55 -> 15/55`。連続価格約定の除去により目標達成率は低下した。
- 判断:
  - 採用。これは alpha 最適化ではなく、実運用との差を利益方向に使わないための約定モデル厳格化である。
  - baseline の低下は許容し、今後の改善はこの保守的な約定値を基準に行う。
  - 月間20%全月達成、月間3/4稼働、週次+1%の全週達成はいずれも未達。
- 再試行するとしたら:
  - 銘柄コードごとの TOPIX500 区分、ETF/ETN 区分、当日の呼値 metadata を履歴として保持できるようになった場合に、category-aware tick ladder へ置き換える。
  - 板・部分約定・注文時刻を取得できる場合は、tick 丸めだけでなく spread と fill probability を含む共有 execution model として再検証する。

### 2026-07-11: Rejected - Pre-Trade 1% Daily Stop-Loss Budget Cap

- 試したこと:
  - `DAYTRADE_MAX_DAILY_LOSS_PCT = 1%` を、次の entry を止める事後判定ではなく、想定 stop 約定損失が日初資産の1%以内になるよう100株単位で建玉前に cap する診断 replay を行った。
  - stop 価格から売却 slippage を差し引き、JPX tick を下方向へ丸めた価格を想定 worst exit とした。候補、entry、exit、setup 別配分は変更していない。
- 結果:
  - 現行 tick-normalized baseline の train 日次実測は `WORST DAY -1.5444% / MAX DRAWDOWN -2.1341% / 負け日の中央値 -0.0981%`。
  - 現行 train の建玉倍率は中央値 `0.245x`、90%点 `2.974x`、99%点 `13.088x`、最大 `14.062x`。高倍率は narrow stop と組み合わされている。
  - 1% cap 診断は `FULL RETURN +97.37% / PF 3.05 / WEEKS >= +1% 36/228 / POSITIVE WEEKS 131/228 / WORST DAY -18,000 / CLOSED TRADES 372`。
  - `TRAIN RETURN +82.95% / PF 3.47 / WEEKS >= +1% 30/202 / POSITIVE WEEKS 117/202 / WORST DAY -14,000 / CLOSED TRADES 326`。
  - `HOLDOUT RETURN +7.88% / PF 2.03 / WEEKS >= +1% 6/26 / POSITIVE WEEKS 14/26 / WORST DAY -18,000 / CLOSED TRADES 46`。
  - `100万円 standalone latest 1m: FINAL EQUITY Y997,900 / TOTAL RETURN -0.21% / CLOSED TRADES 1 / PF 0.00 / WEEKS >= +1% 0/4 / POSITIVE WEEKS 0/4 / WORST DAY -2,100`。
  - 100株単位では1%予算内に収まらない候補が no-trade となり、月次20%目標と直近 standalone を大きく壊した。
- 判断:
  - 不採用。日次上限を事前 sizing へ接続する考え方自体は正しいが、100万円・日本株100株単位・現行 daily edge の組み合わせでは、損失抑制幅に対して機会損失が大きすぎる。
  - 現行の `DAYTRADE_MAX_DAILY_LOSS_PCT` は単一取引の損失保証ではなく、複数取引時の追加 entry 停止閾値にすぎない。実運用上も1%保証として扱わない。
- 再試行するとしたら:
  - 単元未満株を同等の執行条件で利用できる、または初期資金が増えて100株でも1%予算内へ連続的に sizing できる場合。
  - 分足・板・実約定データから stop 到達前の shared exit が検証でき、取引機会を捨てずに expected shortfall を下げられる場合。

### 2026-07-11: Adopted - Candidate Parity Repair and Broad Catchup-Gapdown Removal

- 試したこと:
  - ゼロベース監査で、本番 `select_best_candidates()` と `run_backtest_v16_production()` の candidate schema、setup sizing、候補生成経路を比較した。
  - 本番の水曜 `evaluate_daytrade_setup()` が、sizing 専用で関数引数に存在しない `market_ratio` / `primary_score` を参照して `NameError` になる経路を除去した。
  - 本番 candidate dict に不足していた `prev_return`、`prev_rsi2`、`open_from_prev_low_atr`、`open_vs_sma_atr`、`rs_alpha`、`market_ratio` を primary / strong_oversold / bull ETF へ補い、selected leverage が本番だけ素通りする差を縮めた。
  - backtest 側へ本番と同じ strong_oversold risk budget、fallback notional context を渡し、インデント不備で `catchup_gapdown` がbacktestだけ生成されなかった差を修正した。
  - parity 後に初めて可視化された broad `catchup_gapdown` を train-only でsetup単位に再評価し、細かい閾値を追加せずfamily全体の採否を比較した。
- 結果:
  - parity 後の `catchup_gapdown` は train `24 trades / net -586,502円 / avg -24,438円 / win 54.2% / worst -429,000円`。2022年はプラス、2023年はほぼ横ばい、2024-2025年はマイナスで、月次 `+20%` は `16/55` のまま変わらなかった。
  - `catchup_gapdown` 有効: `TRAIN RETURN +25161.16% / PF 41.39 / WEEKS >= +1% 93/202 / POSITIVE WEEKS 149/202 / WORST DAY -1,482,400円 / MONTHS >= +20% 16/55`。
  - `catchup_gapdown` 無効: `TRAIN RETURN +24202.31% / PF 51.86 / WEEKS >= +1% 89/202 / POSITIVE WEEKS 140/202 / WORST DAY -1,426,300円 / MONTHS >= +20% 16/55`。
  - 採用 baseline:
    - `FULL: FINAL Y600,707,511 / RETURN +59970.75% / 406 trades / WIN 67.24% / PF 21.64 / WEEKS >= +1% 103/228 / POSITIVE 160/228 / MONTHS >= +20% 18/61 / MONTHS >= 3/4 ACTIVE 1/52 / WORST DAY -8,100,000円`
    - `TRAIN: FINAL Y243,023,054 / RETURN +24202.31% / 364 trades / WIN 67.03% / PF 51.86 / WEEKS >= +1% 89/202 / POSITIVE 140/202 / MONTHS >= +20% 16/55 / MONTHS >= 3/4 ACTIVE 1/46 / WORST DAY -1,426,300円`
    - contaminated `HOLDOUT 2026-01-13..2026-07-10: RETURN +147.18% / 42 trades / PF 15.72 / WEEKS >= +1% 14/26 / POSITIVE 20/26 / MONTHS >= +20% 2/5 / MONTHS >= 3/4 ACTIVE 0/5 / WORST DAY -8,100,000円`
    - `100万円 standalone 2026-06-11..2026-07-10: FINAL Y1,197,033 / RETURN +19.70% / 3 trades / PF 94.83 / WEEKS >= +1% 1/4 / POSITIVE 2/4 / WORST DAY -2,100円`
  - parity修正前の tick-normalized baseline に対し、train は `RETURN +19164.13% -> +24202.31%`、`PF 49.63 -> 51.86`、`MONTHS >= +20% 15/55 -> 16/55`、positive weeks `139 -> 140`。週次+1%は `89/202` を維持した。
  - `python -m pytest tests -q`: `404 passed, 38 subtests passed`。
- 判断:
  - parity修正は採用。本番で既に使われるshared sizingをbacktestへ反映し、本番 candidate も同じfeature contractへ寄せる根本修正であり、backtest専用の利益分岐ではない。
  - broad `catchup_gapdown` は不採用。週次hitは4本増えるが、setup自体が複数年trainでnet negative、月次20%件数は不変、PFとworst dayも悪化した。低品質entryで稼働率だけを増やさない原則を優先した。
  - absolute worst day増加は主に採用baselineのequity増加によるが、実運用損失額としては引き続き監視する。
- 再試行するとしたら:
  - `catchup_gapdown` の曜日・gap・score近傍を細かく掘り直さない。新しい事前特徴または実intraday pathで、独立したedgeが複数年に再現した場合だけfamily再設計を行う。
  - 次の根本課題は、前日cacheで全銘柄候補を作って上位だけ板価格を差し替える本番経路と、当日寄付を全universeで見るbacktestの時点差である。前日情報shortlist、当日official open、entry時刻以降の分足を明示した共通candidate engineが必要。

### 2026-07-11: Adopted - Bulk-Date Incremental J-Quants Refresh

- 試したこと:
  - 従来の短期増分更新が4,000超の銘柄別API requestを毎回実行していたため、J-Quants公式の日付指定全銘柄取得を実APIで確認した。
  - `date=20260710` が1 requestで `4,438 rows` を返すことを確認し、31日以内のincremental refreshだけを日付一括取得へ変更した。
  - full refreshや長い期間、bulk取得失敗時は従来の銘柄別取得へfallbackし、既存checkpoint historyを短くしないmergeとsafety snapshotは維持した。
- 結果:
  - `2026-07-02..2026-07-10` の7営業日を7 requestで取得し、`31,035 rows / 4,428 tickers` をcheckpointへ統合した。
  - cache auditは更新前 `aligned=4485 / missing=0 / truncated=0`。統合後cacheの最新日は `2026-07-10`。
  - 最新日の追加による新規tradeはなく、上記採用baselineとstandaloneは維持された。
  - 月次20%を標準出力へ追加し、データ先頭月・最新途中月をfull calendar monthとして誤算入しないようdataset edge monthを保守的に除外した。
- 判断:
  - 採用。データ内容や戦略判断を変えず、同じ公式データを少ないrequestで取得し、最新化の失敗率と所要時間を根本的に下げる。
- 再試行するとしたら:
  - bulk endpointのschemaまたは契約条件が変わった場合のみ。失敗時は自動fallbackを使い、欠損を成功扱いしない。

### 2026-07-11: Adopted - Point-in-Time Candidate Engine and Simulation Position Parity

- 試したこと:
  - `run_backtest_v16_production()` の候補生成を `core/daytrade_candidate_engine.py` へ切り出し、入力型から当日 `close / high / low / volume` を除外した。
  - `feature_asof < trade_date` かつ `open_asof == trade_date` を共通 market context の契約として固定し、当日 OHLC は候補生成後の execution simulation でだけ付加した。
  - simulation の inverse entry が cash / inverse buying power だけを減らして managed position を追加しない不具合を、通常 setup と同じ shared entry helper へ統合して修正した。
  - 板取得に `requested / observations / failures` を保持する batch result を追加し、`no_token / transport / HTTP / malformed JSON / invalid quote` を欠落したまま成功扱いしないようにした。
- 結果:
  - candidate engine 移植前後の全出力を canonical JSON 化し、`33,796,675 bytes / 1,260 days / 32,631 candidate rows / 406 trades` の SHA-256 が双方 `db962f62398dbc60125632d4ccbed62206d8acbfbedaf8f52cedb3c3bd2c641a` で完全一致した。
  - baseline は `FULL +59970.75% / TRAIN +24202.31% / TRAIN PF 51.86 / TRAIN MONTHS >= +20% 16/55` のまま変化なし。
  - focused tests は candidate engine / backtest / logic で `173 passed`、simulation entry は `tests/test_auto_trade.py 51 passed`、板 batch は `tests/test_kabucom_broker.py 113 passed, 38 subtests passed`。
  - 最終全件確認は `python -m pytest tests -q`: `410 passed, 38 subtests passed`。標準 `holdout 6M + standalone 1M` も上記採用 baseline と一致した。
- 判断:
  - 採用。損益を変えずに future field を型から排除し、本番へ移植可能な point-in-time candidate engine を作った根本修正である。
  - simulation inverse 修正と板 batch failure の明示化も、strategy alpha ではなく執行状態の正しさを直すため採用した。

### 2026-07-11: Rejected - Liquidity-Only 50-Symbol Prior-Day Shortlist

- 試したこと:
  - kabuステーションAPIの登録上限を backtest へ正直に反映する診断として、前日確定値だけで最大50銘柄を選ぶ shortlist を実装した。
  - 順位に gap、曜日、score、過去損益を使わず、必須データ、shared minimum turnover、100株の流動性 headroom、bull / inverse の固定予約だけを使った。
  - 不採用結果を受け、同じ shortlist の閾値を過去損益へ合わせず、前日終値を寄付とする潜在 setup、`-2% / 0% / +2%` の寄付シナリオ、既存 shared sizing confidence 順という説明可能な3案だけを診断した。
- 結果:
  - liquidity-only 50 baseline:
    - `FULL -55.54% / 314 trades / PF 0.75 / WEEKS >= +1% 41/228 / POSITIVE 62/228 / WORST DAY -160,800円`
    - `TRAIN -57.26% / 292 trades / PF 0.73 / MONTHS >= +20% 2/55`
    - contaminated holdout `+4.04% / 22 trades / PF 1.24`
    - standalone latest 1m `+0.14% / 1 trade / WEEKS >= +1% 0/4`
  - 全銘柄 baseline の train 364 trades のうち shortlist 後も同一日・同一銘柄で残ったのは27件だけ。外れた337件は baseline 上で net `+186,722,875円`、新たに選ばれた265件は net `-1,077,222円` だった。
  - 前日 flat-open 50 は train `PF 1.62 / net +3,559,658円`、3寄付シナリオの score 順は `PF 1.72 / net +4,204,743円`、shared sizing confidence 順でも `PF 1.98 / net +6,104,352円` に留まった。
  - flat-open の候補取得を200へ増やすと train `PF 10.22 / net +106,845,824円` まで戻ったが、全銘柄 baseline には届かず、板API requestが自動で銘柄登録される50銘柄上限とも両立しない。
- 判断:
  - 不採用。50銘柄の純粋な流動性 shortlist は strategy edge を保持せず、損失最小化にも利益最大化にもならない。
  - 寄付シナリオや shared confidence を使っても50銘柄では不足し、ここから曜日 / gap / score quotaを足すと、pre-open shortlistを過去の勝ち銘柄へ当て込む別のカーブフィットになる。
  - C1の backtest / shortlist code は全てrevertし、candidate engine baseline の完全一致hashへ戻した。
- 再試行するとしたら:
  - 全銘柄の寄付または寄前気配を point-in-time で取得でき、同じ履歴を train replay できる market-data feed を導入した場合。
  - 50銘柄を超えて登録を順次入れ替える場合も、API failure、special quote、時刻、登録解除を履歴化し、同じ operational path を replay できる場合だけ。
  - 現行の日足 cache と50銘柄上限のまま、同じ gap / score / 曜日近傍を再探索しない。

### 2026-07-11: Adopted - Production Point-in-Time Snapshot and Exact Replay Path

- 試したこと:
  - 日足OHLC backtestを本番相当とみなさず、`KABUCOM_TEST / KABUCOM_LIVE` の実観測入力をそのまま保存・再生する `daytrade_production_snapshots.jsonl` schemaを追加した。
  - 前日確定値だけで観測49銘柄を固定し、`1321` と合わせてkabuステーションAPIの登録上限50銘柄を本番経路で厳守した。順位は過去損益・曜日・当日gapを使わず、shared minimum turnover、100株の流動性headroom、bull/inverseの固定予約だけで決めた。
  - 9:30以降の最初の板batchについて、当日寄付と前日特徴だけをshared candidate engineへ渡し、現在値、bid/ask、session high/low、volumeはexecution evidenceへ分離した。
  - candidate groups、selector context、selected candidates、code/config hashをsnapshotへ保存し、`jp_production_replay.py` が同じengineへ再投入してdigest完全一致を確認するようにした。
  - `decision_snapshot_id` をdecision log、position、exit logへ接続し、非simulationの実約定損益だけをproduction replayで集計できるようにした。
  - registry更新をunregister-before-registerへ変更し、解除失敗時は新規登録せずfail closedにした。板欠損、別日OpeningPriceTime、cache/board前日終値不一致、registry失敗、snapshot parity失敗では当日新規entryを0件にした。
  - live write gateが閉じていてもsnapshot収集は継続し、最初のsnapshot時点でentry未承認なら同日後刻に承認状態が変わっても古い寄付signalでentryしないようにした。
- 結果:
  - snapshotのexecution quoteだけを大幅変更してもsnapshot identity、candidate digest、selected digestは不変。寄付を変えるとidentityが変わることを回帰テストで確認した。
  - schema/date/board failure、snapshot改ざん、最低snapshot件数不足は明示的に非zeroまたはno-entryになる。
  - 日足 `jp_backtest.py` は起動時に `REFERENCE-ONLY` を表示し、本番同等の成績証明から分離した。
  - `python -m pytest tests -q`: `423 passed, 38 subtests passed`。日足reference-only baselineと直近1ヶ月standaloneの数値は変更なし。
- 判断:
  - 採用。今後「本番同様のテスト」と呼べるのは、このproduction snapshotを同じcode/configで完全replayし、実注文・部分約定・取消・exitまで同じsnapshot IDで接続できた期間だけとする。
  - `KABUCOM_TEST` はschema / parity / order lifecycle確認用であり、収益根拠には使わない。`KABUCOM_LIVE` の非simulation decision snapshotを2026-07-13以降のdecision clean holdoutとして蓄積し、実注文再開後のexecution clean holdoutは別に切る。
  - `STATUS: PARITY_OK` は再現一致の証明であって収益性の証明ではない。actual linked exitが0件なら損益は未検証とする。
- 再試行するとしたら:
  - 観測49銘柄の成績が悪くても、その結果を見て同じholdout内で曜日 / gap / score quotaへ当て込まない。観測universeの変更は、新しい外部feedや事前定義した別policyをtrain期間で設計し、次のclean holdoutからのみ使う。

### 2026-07-12: Adopted - Production-vs-Test Residual Audit and AI Test Governance

- 試したこと:
  - daily OHLC、SIM、`KABUCOM_TEST`、production snapshot、`KABUCOM_LIVE` を、候補母集団、時刻、Board、流動性、資金、税、AI veto、注文、部分約定、保護逆指値、exit、再起動、損益証跡まで再監査した。
  - `calculate_lot_size()` が受け取っていたturnoverを発注株数へ使っていなかったため、daily / live共通で前日turnoverの `LIQUIDITY_LIMIT_RATE` を数量上限へ適用した。
  - broker position再取得で消えていたstrategy / stop / `decision_snapshot_id` metadataをExecutionID一致時に保持し、数量・価格・routeはbroker値で上書きするようにした。
  - 9:30以降のlive entryでentry前の公式寄値をexit pathへ使わず、entry fillをpost-entry pathの起点にした。
  - 保護逆指値arm失敗を未解決entry / orphanとして後続entryとreadinessをfail closedにした。
  - `KABUCOM_TEST` のlinked actual exitをexecution replayへ含めつつ、LIVE clean holdout資格とは分離した。
  - optimizer / walkforwardの税・明示コストを標準 `jp_backtest.py` と同じ共有設定へ統一した。
  - `AGENTS.md` とREADMEへ、本番同等テストの完了条件、残差表、廉価モデル / サブエージェント委譲時の親担当責任を明記した。
- 結果:
  - focused tests: `341 passed, 38 subtests passed`。
  - full tests: `424 passed, 38 subtests passed`。
  - turnover数量cap後のdaily OHLC reference-only baseline:
    - `FULL: FINAL Y113,354,312 / RETURN +11235.43% / 418 trades / WIN 66.51% / PF 12.19 / WEEKS >= +1% 98/228 / POSITIVE 158/228 / MONTHS >= +20% 13/61 / MONTHS >= 3/4 ACTIVE 1/52 / WORST DAY -2,093,000円`
    - `TRAIN: FINAL Y70,930,995 / RETURN +6993.10% / 375 trades / WIN 66.13% / PF 12.58 / WEEKS >= +1% 85/202 / POSITIVE 138/202 / MONTHS >= +20% 12/55 / MONTHS >= 3/4 ACTIVE 1/46 / WORST DAY -2,093,000円`
    - contaminated `HOLDOUT 2026-01-13..2026-07-10: RETURN +59.81% / 43 trades / PF 11.60 / WEEKS >= +1% 13/26 / POSITIVE 20/26 / MONTHS >= +20% 1/5 / WORST DAY -1,327,200円`
    - `100万円 standalone 2026-06-11..2026-07-10: RETURN +19.70% / 3 trades / PF 94.83 / WEEKS >= +1% 1/4 / POSITIVE 2/4 / WORST DAY -2,100円`
  - 旧baseline `TRAIN +24202.31% / PF 51.86 / MONTHS >= +20% 16/55` は、実発注数量へ流動性capを適用していないため廃止した。
- 判断:
  - 採用。利益最大化の調整ではなく、本番より楽観的だった数量、position state、live exit時系列、stop失敗、test execution集計、cost profileを厳格化する根本修正である。
  - daily OHLCは引き続きreference-only。production snapshotが0件のため、本番同等性と本番収益性は未検証のまま。
  - 未解消の重要残差は、保護逆指値の市場約定をposition消失からexit/PnLへ自動reconcileする経路、lifecycle completeness、grossからnetへの口座コスト照合、AI veto evidence、Board batch時間幅、厳密な前営業日、現在Primeを過去へ適用するsurvivorshipである。
- 再試行するとしたら:
  - 同じ日足閾値を再探索しない。まずorder history / execution ID / wallet deltaを `decision_snapshot_id` へ連結し、`selected -> veto/reject -> fill -> stop/exit -> remaining=0` の完全性を機械検証する。
  - 2026-07-13以降のactual snapshotとlinked exitが蓄積した後、同一code/configのproduction replayでのみ本番差分を再評価する。
