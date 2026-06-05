---
name: jp-refresh-latest
description: 日本株キャッシュの最新更新、標準JPバックテスト再検証、直近1ヶ月の standalone 日次損益表の出力を行う skill。ユーザーが「最新日まで更新して」「日付を更新して」「日付を最新にして」「最新データで検証して」のような依頼をしたとき、holdout / standalone の切り直しをしたいとき、直近1ヶ月の各日成績を確認したいとき、または更新後に README / STRATEGY_EXPERIMENT_LOG を直す必要があるときに使う。
---

# JP 最新更新

## ワークフロー

1. `python scripts/jp_refresh_validate.py --holdout-months 6 --standalone-latest-months 1` を実行して最新キャッシュを更新し、標準検証を回す。
2. 既に最新なら `--validate-only` を付けて更新を飛ばし、検証だけ再実行する。
3. 出力から次を必ず拾う。
   - 最新キャッシュ日
   - full / train / holdout の結果
   - 直近1ヶ月 standalone の結果
   - 直近1ヶ月の日次損益表
4. 検証した日付範囲は絶対日付で報告する。「今日」「昨日」は使わず、キャッシュ日で表現する。ユーザーの「日付更新」「最新日まで更新」といった短い指示も、この skill の対象として扱う。
5. baseline が変わったら、同じターンで `README.md` と `STRATEGY_EXPERIMENT_LOG.md` も更新する。
6. 判断ロジックは `jp_backtest.py` と shared strategy に置き、更新フローに戦略専用ロジックを足さない。

## ガードレール

- holdout への当て込みは禁止。
- ユーザーが戦略変更を明示しない限り `core/logic.py` は変更しない。
- この skill は実行手順だけを担い、売買判断は持たせない。
- 使い終わった一時ファイルは片付ける。
