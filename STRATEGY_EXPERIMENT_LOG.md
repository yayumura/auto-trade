# Strategy Experiment Log

このファイルは、日本株デイトレード戦略の探索ログである。
別セッションで同じ仮説をそのまま再試行しないため、主要な採用案と不採用案だけを残す。

## Current Baseline

- As of 2026-05-18
- 採用中ロジック:
  - 月曜の高 breadth / 高ギャップ / 前日過熱 `primary` を除外
  - 火曜の mid breadth で、失速しやすい `primary` を2種類だけ除外
  - 火曜の mid breadth で、弱い `primary` より少し強い `fallback` がある場合は差し替え
  - 火曜の中途半端な寄りギャップ `primary` を除外
  - 火曜の trend 距離が遠すぎる `primary` を除外
  - 火曜の mid breadth で指数が +1%以上ギャップアップしている `primary` を除外
  - 水曜の小さすぎる寄りギャップ、中途半端な寄りギャップ、または trend 距離が遠すぎる `primary` を除外
  - 木曜の mid breadth で、失速しやすい `primary` を2種類だけ除外
  - 木曜の前日大幅上昇 `primary` を除外
  - 木曜の trend 距離が中途半端または失速しやすい `primary` を除外
  - 金曜の mid-high breadth / 弱 RS / 横ばいギャップ `primary` を除外
  - 月曜の mid-gap / far-trend `primary` の equity notional 上限は `0.50`
  - 月曜の breadth `0.50-0.55` / gap `>= 2.0%` / near-SMA `primary` の equity notional 上限は `1.00`
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
  - 水曜の high breadth / gap `> 0.5%` `fallback` の equity notional 上限は `0.30`
  - 週次利益ガードは金曜、週次 `+1%` 到達後に開始
  - 週後半の catchup レバレッジ倍率は `30`
  - `catchup_gapdown` の equity notional 上限は `0.50`
  - 月曜の breadth `0.35-0.45` / gap `-2.0%~-1.5%` / below-SMA `catchup_gapdown` の equity notional 上限は `0.25`
  - 火曜の breadth `0.35-0.45` / gap `-1.0%~-0.6%` / neutral-trend `catchup_gapdown` の equity notional 上限は `0.10`
  - 火曜の breadth `0.35-0.45` / gap `-1.5%~-0.6%` `catchup_gapdown` の equity notional 上限は `0.25`
  - 火曜の high breadth で、前日強いのに RS が弱く、寄り位置が高い `primary` を除外
  - `market_ratio >= 1.10` かつ `selected_count >= 20` かつ `catchup score` が `primary score` を `1.0-2.0` 上回るときだけ、`primary` の先頭1件を `catchup` の先頭1件へ差し替える
  - `primary` が不在で、breadth `< 0.55` かつ `market_ratio >= 1.10` かつ restrained `catchup_rs` が弱い `fallback` を score で `6.0` 以上上回るときだけ、`fallback` より `catchup_rs` を優先
  - `inverse_pullback` 追加
  - panic breadth / failed rebound の `inverse_rebreak` 追加
  - `inverse` / `inverse_pullback` / `inverse_rebreak` の equity notional 上限は `0.70`
  - 高 breadth / hot continuation `primary` の equity notional 上限は `0.60`
  - 低 RS `primary` の equity notional 上限は `1.00`
  - `open_vs_sma_atr 4.0-5.0` の伸び切り失速帯 `primary` の equity notional 上限は `1.00`
  - 火曜の指数過熱 `market_ratio >= 1.20` `primary` の equity notional 上限は `0.75`
  - low breadth / 過熱指数 / low-score / near-SMA `primary` の equity notional 上限は `1.00`
  - 高 breadth 日に、弱めの `primary` より明確に強い bull ETF 候補がある場合だけ ETF 優先
  - low breadth では bull ETF を catchup より優先
  - low breadth / 前日プラス / near-SMA `fallback` の equity notional 上限は `0.50`
  - 水木金の low breadth / moderate-score `catchup_gapdown` probe は `0.35`
  - 金曜の low breadth / hot gap / extended trend `catchup_rs` の equity notional 上限は `0.35`
  - breadth `< 0.55` / `market_ratio >= 1.15` の fragile hot market では、非 `inverse` 選抜の base leverage を `0.10` に制限
  - breadth `< 0.60` / `market_ratio >= 1.20` / `score <= 8.0` / 非マイナス gap の `primary` は、selected base leverage を `0.00` に制限
  - 水木金の breadth `< 0.60` / `market_ratio >= 1.15` / score `>= 10` の `primary` は、selected base leverage を `0.00` に制限
  - 水曜の high breadth / 非プラス gap / score `8-10` `primary` は、selected base leverage を `0.00` に制限
  - breadth `< 0.60` / `market_ratio >= 1.15` / `score <= 8.0` / 非マイナス gap の `primary` は、selected base leverage を `0.05` に制限
  - breadth `< 0.60` / `market_ratio >= 1.15` / score `>= 10` / プラス gap の `primary` は、selected base leverage を `0.05` に制限
  - breadth `< 0.60` / `market_ratio >= 1.20` / 非マイナス gap の `primary` は、selected base leverage を `0.05` に制限
  - breadth `0.55-0.70` / `market_ratio 1.05-1.15` / gap `>= 1.5%` / score `10-14` / 前日上昇 `>= 3.5%` の `primary` は、equity notional 上限を `0.75` に制限
- 最新確認値:
  - `FINAL EQUITY: Y478,999,037`
  - `CLOSED TRADES: 503`
  - `WIN RATE: 54.67%`
  - `WEEKS >= +1%: 181/220`
  - `POSITIVE WEEKS: 184/220`
  - `TOTAL RETURN: +47799.90%`
  - `PROFIT FACTOR: 3.45`
  - `AVG MONTH ACTIVE RATE: 48.60%`
  - `MONTHS >= 3/4 ACTIVE: 3/51`
  - `WORST DAY: -9,678,458円`

## Adopted Logic

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
