# Strategy Experiment Log

このファイルは、日本株デイトレード戦略の探索ログである。
別セッションで同じ仮説をそのまま再試行しないため、主要な採用案と不採用案だけを残す。

## Current Baseline

- As of 2026-05-06
- 採用中ロジック:
  - 月曜の高 breadth / 高ギャップ / 前日過熱 `primary` を除外
  - 火曜の mid breadth で、失速しやすい `primary` を2種類だけ除外
  - 火曜の mid breadth で、弱い `primary` より少し強い `fallback` がある場合は差し替え
  - 木曜の mid breadth で、失速しやすい `primary` を2種類だけ除外
  - 火曜の high breadth で、前日強いのに RS が弱く、寄り位置が高い `primary` を除外
  - `inverse_pullback` 追加
  - 高 breadth 日に、弱めの `primary` より明確に強い bull ETF 候補がある場合だけ ETF 優先
- 最新確認値:
  - `WEEKS >= +1%: 138/215`
  - `POSITIVE WEEKS: 142/215`
  - `TOTAL RETURN: +4734.74%`
  - `PROFIT FACTOR: 1.33`
  - `AVG MONTH ACTIVE RATE: 50.48%`
  - `MONTHS >= 3/4 ACTIVE: 2/50`
  - `WORST DAY: -4,201,220円`

## Adopted Logic

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

## Notes For Future Sessions

- まず `135/215` を下回る微調整は再試行しないこと
- 次の有望方向は、`primary` をさらに削ることではなく、bull ETF 側の独立 setup を増やすこと
- 再試行するなら、前回との差分をこのファイルに先に書いてから始めること
