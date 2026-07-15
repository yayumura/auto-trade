# 次セッション戦略開発方針

最終更新: 2026-07-15

この文書は、次セッションで過去の探索を繰り返さず、カーブフィッティングを避けながら日本株デイトレ戦略を改善するための開始点とする。

## 1. 現在地

- 確定cache最新日: `2026-07-14`
- train評価期間: `2022-03-01..2026-01-09`
- frozen holdout開始日: `2026-01-13`
- 現行holdoutは `contaminated / veto-only`。閾値設計へ戻さない
- actual `KABUCOM_TEST / KABUCOM_LIVE` production snapshot: `0`
- linked actual exit: `0`
- 本番同等未検証・本番収益性未検証

標準baseline:

| Window | Return | Trades | Win | PF | Weeks >= +1% | Positive weeks | Months >= +20% | Months >= 3/4 active | Worst day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| full | +3801.47% | 379 | 70.45% | 22.13 | 99/228 | 167/228 | 4/52 | 1/52 | -525,000円 |
| train | +1996.83% | 335 | 70.75% | 35.90 | 85/201 | 146/201 | 3/46 | 1/46 | -122,400円 |
| contaminated holdout | +86.07% | 44 | 68.18% | 15.71 | 14/27 | 21/27 | 1/5 | 0/5 | -525,000円 |
| standalone `2026-06-15..2026-07-14` | +2.62% | 5 | 60.00% | 13.47 | 1/5 | 3/5 | N/A | N/A | -2,100円 |

再検証コマンド:

```bash
python scripts/jp_refresh_validate.py --validate-only --holdout-months 6 --standalone-latest-months 1
python -B -m pytest tests -q -p no:cacheprovider
python -B jp_production_replay.py --trade-mode KABUCOM_TEST --min-snapshots 1
python -B jp_production_replay.py --trade-mode KABUCOM_LIVE --min-snapshots 1
```

直近のfull testは `541 passed, 41 subtests passed`。runtime hashは `sha256:c510b6f0ccd30c1be0b8300d5ef9c151865c5019fad6643c8a78dc7266eecdd7`。

## 2. 月20%未達の根本原因

train 46完全月の実現可能性監査では、実績月利の平均は `7.10%`、中央値は `3.70%`、月間取引数は平均 `7.22`、中央値 `7`、active rate中央値は `32.58%` だった。

重要な上限:

- 各月の負けtradeを事前に完全判別して損失を0円にする非現実的なoracleでも、月20%到達は `3/46` のまま
- `43/46`か月はgross profit自体が月初資産の20%未満
- 正だが20%未満の月を既存損益の共通scaleだけで20%へ上げる必要倍率は中央値 `5.56x`、最大 `570.90x`
- train最悪日率は `-1.554%`。日次損失を1%以内へ抑える線形scale上限は `0.64x`

したがって、損失削減、既存tradeのsize増加、既存gate緩和だけでは月20%全月化に届かない。必要なのは、既存edgeと低相関な独立edgeと、現在の約7件/月を大幅に上回る高品質な取引機会である。

月20%は採用候補を選ぶ目的関数にしない。各月へ直接合わせると、月固有の曜日、gap、銘柄、regimeを記憶する。月20%はportfolio-levelのstretch KPIとしてのみ観測する。

## 3. 戦略の方向

現行の `primary / fallback / catchup / strong_oversold` は、主に寄付時点の日足、gap、breadth、RSへ依存しており、情報源と時間軸の相関が高い。次は同じ特徴量の閾値違いではなく、情報源または時間軸が異なるedgeを追加する。

優先候補:

1. 寄前・寄付の板不均衡、spread、quote persistenceを使うopening microstructure edge
2. 決算、業績修正、自社株買いなど、発表時刻を保持したevent/catalyst edge
3. 寄付後のVWAP回復・失敗、failed breakout、出来高加速を使うintraday path edge
4. sector-relative strength / mean reversionと、実行可能な場合の指数・ETF hedge
5. actual pathを使うshared partial de-risk / trailing exit。日足OHLCの有利な順序補完は禁止

各edgeは独立した判断engineとして検証し、最終的に共有risk allocatorへ接続する。月間期待値は概ね `取引機会数 × 1取引risk × net R期待値` で決まるため、単一edgeのriskを増やすより、低相関edgeの機会数を増やす。

## 4. API停止中に進めること

API停止中はalpha条件を追加せず、次の評価・データ基盤を整備する。

### 4.1 Trial registry

全仮説・全試行を機械可読に記録する。

最低項目:

- `hypothesis_id`
- 経済的仮説と失敗条件
- 使用featureとfeature availability time
- train期間、fold、purge / embargo
- 試した全parameterと試行順
- cost / slippage / liquidity / fill前提
- train、rolling、vetoの結果
- 採用・不採用理由
- 再試行可能になる外部条件

`STRATEGY_EXPERIMENT_LOG.md` は人間向けの判断記録として維持し、trial registryを数値監査の一次情報にする。

### 4.2 Overfitting audit

候補数を含めて以下を評価できるharnessを用意する。

- purged rolling / walk-forward
- combinatorially symmetric cross-validationによるPBO
- Deflated Sharpe Ratio
- block bootstrapによるexpectancyとworst-foldの信頼区間
- parameter plateau。単一best pointではなく、近傍で符号とriskが安定すること
- 既存edgeとの日次・週次PnL相関

通常のholdout 1本だけで多数の候補を選ばない。試行数と非正規性を補正する。

### 4.3 Future data contract

API復旧前に、将来取得するintraday datasetのschemaとfail-closed条件を固定する。

必須情報:

- broker verified clock、request / receive / exchange timestamps
- symbol、observation policy、registry batch identity
- current、bid、ask、bid/ask quantity、spread、volume、VWAPに必要な約定情報
- candidate / selected digestとfeature availability time
- order ID、execution ID、partial fill、cancel、protective stop、exit、remaining quantity
- commission、commission tax、credit cost、gross / execution-net / final-netの区別
- missing / stale / schema mismatchを補完せずno-entryにするreason

日足OHLC、固定slippage、有利な約定価格で欠損intraday stateを補完しない。

### 4.4 As-of event data inventory

決算・業績修正・自社株買い・指数採用などについて、発表時刻と訂正履歴を含むpoint-in-time sourceを調査する。現在から見た最終値だけのデータは採用しない。データが揃うまでevent alphaをbacktestへ追加しない。

## 5. API復旧後の順序

1. 同一code/runtimeで `KABUCOM_TEST` schema/parityを確認する
2. verified broker clock、`1321 + observation batches`、fresh entry quoteをactual snapshotへ保存する
3. candidate / selected digestを完全一致させる
4. zero fill、partial fill、cancel、protective stop、exit、remaining quantity 0までを連結する
5. 少なくとも複数regimeを含むforward observationを蓄積する。単日成功で収益性を判断しない
6. intraday edgeはtrain設計し、汚染済みholdoutはveto-only、新しい未観測期間をclean holdoutとして一度だけ確認する
7. actual execution cost後に合格したedgeだけを共有risk allocatorへ接続する

`KABUCOM_TEST` はschema、signal parity、order lifecycleの検証用であり、収益性の証拠にしない。非simulationの `KABUCOM_LIVE` snapshotとlinked actual exitだけを本番損益証拠とする。

## 6. 採用ゲート

新edgeは、バックテスト総returnが上がっただけでは採用しない。最低限、次を事前に固定して満たす。

- entry前に利用可能なfeatureだけを使う
- 複数年・複数regime・複数foldで期待値の符号が安定する
- 保守的なspread、slippage、liquidity、partial / zero fill後もnet期待値が正
- parameter近傍で壊れない
- trial countを含めたPBO / DSRが失格水準でない
- 既存edgeと低相関でportfolioのworst day / worst weekを悪化させない
- small account `100万円 standalone`を赤字のまま放置しない
- production snapshotとlinked lifecycleが無い場合は「本番同等未検証」と明記する

## 7. 再試行しない項目

新しい情報が増えない限り、以下は再探索しない。

- 曜日 × breadth × gap × scoreの狭いbox
- 同じ閾値近傍のgrid search
- pure-win日だけを拡大するsize-up
- 既存tradeの共通leverage引上げ
- `MAX_POSITIONS=2/3/4` の単純なmulti-position化
- no-candidate / selected-blocked / weekly-lock候補の広いrescue
- 日足OHLCだけでのpartial exit順序推定
- contaminated holdoutを見てからのthreshold / size / exit調整

既存検証では2本目trade 278件が合計 `-45.47M円`、multi-position trainは `PF 1.63 / WORST DAY -6,433,398円`まで悪化した。no-candidate setup miss、selected blocked、曜日なし候補、粗い単一因子にも時系列再現可能なedgeは無かった。

## 8. 次セッションの開始手順

1. この文書と `STRATEGY_EXPERIMENT_LOG.md` の末尾を読む
2. cache最新日、frozen holdout、baseline、standaloneを再確認する
3. API状態を確認する。利用不可なら接続再試行に時間を使わず、trial registry / overfitting audit / future data contractへ進む
4. 新しい仮説は既存仮説との差分、経済的理由、必要データ、失敗条件を先に記録する
5. 新しいデータまたは未検証の独立edgeが無ければ、日足thresholdを追加しない
6. 変更後は標準backtest、standalone、全test、strict production replay、README、探索ログを同じターンで更新する

## 9. 参考資料

- [The Probability of Backtest Overfitting](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253)
- [The Deflated Sharpe Ratio](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)
- [Harvey, Liu, Zhu: ... and the Cross-Section of Expected Returns](https://www.nber.org/papers/w20592)

これらは、候補を大量に試した後の通常のholdoutや単純なSharpeだけでは、selection biasを除けないことを扱っている。
