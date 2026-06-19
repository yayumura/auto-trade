# KABUCOM_LIVE Deferred External Tasks

このファイルは、レビュー上は妥当だが、現時点ではコードへ捏造して実装せず、外部状態の実取得または別途承認を待つ項目を整理するためのものです。

方針:

- 未取得・未確認・未承認のものは、必ず fail closed のままにする
- コード側に「都合のよい成功値」を置かない
- 取得できるようになったら、実データを入れてから gate を開く

## 1. Actual `KABUCOM_TEST` stop-confirmation fixture

Status: deferred

妥当な理由:

- 実注文、即時取消、取消確認、約定確認の実地取得が必要
- 手で作った sanitized fixture を actual capture と偽るべきではない
- `captured_from_kabucom_test=false` の fixture は、ライブ証跡としては使わないのが正しい

現状のガード:

- `core/kabucom_contracts.py`
- `core/live_order_gate.py`
- `tests/test_kabucom_contracts_test_fixture.py`

運用ルール:

- actual capture が入るまで `KABUCOM_LIVE` の financial write gate は閉じたままにする
- fixture をコードで捏造しない

## 2. Actual GitHub Actions run-state acquisition

Status: deferred

妥当な理由:

- workflow run の成功、head SHA、artifact digest、artifact ZIP 内容は外部状態
- 未確認の run を成功扱いにするのは危険

現状のガード:

- `core/github_actions_artifact_source.py`
- `core/live_order_gate.py`
- `tests/test_kabucom_broker.py`

運用ルール:

- `GITHUB_TOKEN` / `GH_TOKEN` があっても、run / artifact の照合に失敗したら fail closed を維持する
- digest や archive contents を推測で埋めない

## 3. Authoritative JPX calendar source

Status: deferred

妥当な理由:

- 休日・半日・coverage gap は外部の正しい source が必要
- カレンダーをローカル推定だけで埋めると、LIVE の gate 安全性を損なう

現状のガード:

- `core/jpx_calendar.py`
- `core/live_order_gate.py`
- `tests/test_kabucom_broker.py`

運用ルール:

- `contracts/jpx_trading_calendar.json` が無い / invalid / coverage gap の場合は fail closed にする
- fallback 営業日判定で `KABUCOM_LIVE` を開けない

## 4. Broad live-risk constants changes

Status: not for this review

妥当な理由:

- `risk_readiness` に関係する broad な定数変更は、別の train / validation / untouched holdout / walk-forward review を要する
- このレビューの外部依存整理とは別で、コード差分として機械的に入れるべきではない

現状のガード:

- `core/live_readiness_report.py`
- `README.md` の risk strategy review セクション

運用ルール:

- 変更するなら、戦略レビューを通したうえで shared logic として更新する
- 単なる gate 回避のために広い定数を触らない

## 5. まとめ

上の項目は、いずれも「妥当だが今は未取得・未確認なので閉じたままにする」が正解です。
今後、実地取得や外部確認が完了したら、このファイルを更新し、必要なら README とテストも追従させます。
