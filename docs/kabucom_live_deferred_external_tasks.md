# KABUCOM_LIVE Deferred External Tasks

このファイルは、レビュー上は妥当だが、現時点では repo に捏造して実装せず、外部状態の実取得または人間の承認を待つ項目を整理する runbook です。

`KABUCOM_LIVE` の financial write は、下の 4 件がすべて complete になるまで closed のままにします。
README の live gate 説明からはこのファイルを 1 クリックで辿れるようにしています。

方針:

- 未取得・未確認・未承認のものは、必ず fail closed のままにする
- コード側に「都合のよい成功値」を置かない
- 取得できるようになったら、実データを入れてから gate を開く
- 不明な owner や担当者は、個人名を推測せず `human/operator` または `TBD` を使う

## Current state

- Status: blocked / closed
- Owner: human/operator
- Why deferred: actual external evidence is still missing for at least one of the four tasks below
- Fail-closed behavior while incomplete: `KABUCOM_LIVE` financial write remains blocked; monitoring, protective stops, exits, and journal reconciliation stay unchanged
- LIVE restart condition: all four task sections below are `Status: complete` and the matching repo files / hashes have been refreshed

## Overview

| Task | Status | Owner | Evidence location | Repo files to update |
| --- | --- | --- | --- | --- |
| Actual `KABUCOM_TEST` stop-confirmation fixture | deferred | human/operator | repo external secure storage + `contracts/kabucom_test_contract_fixture.json` | `contracts/kabucom_test_contract_fixture.json`, `contracts/kabucom_live_write_attestation.json`, `contracts/kabucom_live_write_attestation.json.sha256`, `README.md` |
| Actual GitHub Actions run-state acquisition | deferred | human/operator | GitHub Actions run page / API + attestation bundle | `contracts/kabucom_live_write_attestation.json`, `contracts/kabucom_live_write_attestation.json.sha256`, `README.md`, `docs/kabucom_live_deferred_external_tasks.md` |
| Authoritative JPX calendar source | deferred | human/operator | source record + `contracts/jpx_trading_calendar.json` | `contracts/jpx_trading_calendar.json`, `README.md`, `docs/kabucom_live_deferred_external_tasks.md` |
| Broad live-risk constants / strategy review | deferred | human/operator | review packet + `contracts/live_risk_review.json` | `contracts/live_risk_review.json`, `README.md`, `STRATEGY_EXPERIMENT_LOG.md` |

## 1. Actual `KABUCOM_TEST` stop-confirmation fixture

- Status: deferred
- Owner: human/operator
- Why deferred: only an actual `KABUCOM_TEST` order / cancel / terminal-status / fill path can prove the stop-confirmation behavior; a hand-written sanitized fixture is not evidence
- Human procedure:
  1. Use `KABUCOM_TEST` with the minimum quantity needed for the target instrument.
  2. Submit the order and confirm the orders API returns `accepted`.
  3. Issue an immediate cancel.
  4. Confirm the terminal state is `cancel accepted` or `canceled`.
  5. Confirm whether any fill occurred.
  6. If the order partially fills, record the filled and remaining quantities, cancel the remainder, and keep the run closed until the operator manually resolves the state and re-runs the capture.
  7. If the order submission, cancel, or terminal-status confirmation fails, stop and keep the gate closed; do not synthesize a fixture from the failed run.
- Required evidence:
  - raw response capture, stored outside the repo
  - sanitized fixture
  - `captured_at`
  - `redaction_policy`
  - `captured_from_kabucom_test=true` provenance
  - fixture hash
  - attestation bundle hash reflected in the repo-side attestation
- Evidence location:
  - raw capture: `TBD` (repo external, human/operator managed secure storage)
  - sanitized fixture: `contracts/kabucom_test_contract_fixture.json`
  - attestation bundle: `contracts/kabucom_live_write_attestation.json` and `contracts/kabucom_live_write_attestation.json.sha256`
- Repository files to update after completion:
  - `contracts/kabucom_test_contract_fixture.json`
  - `contracts/kabucom_live_write_attestation.json`
  - `contracts/kabucom_live_write_attestation.json.sha256`
  - `README.md`
  - tests that assert fixture provenance / attestation validity
- Hashes/artifacts to refresh:
  - test fixture hash
  - contract fixture manifest hash
  - live write attestation hash
  - attestation digest sidecar
- Fail-closed behavior while incomplete:
  - `get_kabucom_live_financial_write_gate_status()` keeps `test_contract_fixture_not_captured_from_kabucom_test` and/or `ci_artifact_attestation_missing` in the blocking reasons
  - live financial write stays closed
- Do not:
  - hand-write `captured_from_kabucom_test=true`
  - invent a fake capture, cancel terminal state, or partial-fill outcome
  - open LIVE without actual capture
- LIVE restart condition:
  - the sanitized fixture matches the raw capture provenance, the attestation hash matches, and the repo test asserting the fixture passes

## 2. Actual GitHub Actions run-state acquisition

- Status: deferred
- Owner: human/operator
- Why deferred: workflow run id, conclusion, artifact digest, and ZIP contents are external state and must be observed, not guessed
- Human procedure:
  1. Open the GitHub Actions run page or API for the exact commit.
  2. Confirm the run head SHA matches the current commit.
  3. Confirm the workflow command is `python -m pytest tests -q`.
  4. Confirm the conclusion is success.
  5. Confirm artifact name, artifact id, artifact digest, and artifact expiration.
  6. Download the artifact ZIP and confirm it contains the attestation bundle and the digest sidecar.
- Required evidence:
  - Actions URL
  - workflow run id
  - head SHA
  - artifact id
  - artifact name
  - artifact digest
  - attestation hash
  - ZIP content check result
- Evidence location:
  - GitHub Actions run page / API JSON
  - repo-side attestation bundle: `contracts/kabucom_live_write_attestation.json` and `contracts/kabucom_live_write_attestation.json.sha256`
  - external audit note: `TBD`
- Repository files to update after completion:
  - `contracts/kabucom_live_write_attestation.json`
  - `contracts/kabucom_live_write_attestation.json.sha256`
  - `README.md`
  - `docs/kabucom_live_deferred_external_tasks.md`
- Hashes/artifacts to refresh:
  - attestation hash
  - artifact digest
  - run metadata recorded in the attestation
- Fail-closed behavior while incomplete:
  - `verify_live_write_attestation_artifact_source()` returns `github_token_missing`, `workflow_run_request_failed`, or another generic failure
  - live write gate remains closed
- Do not:
  - fill in run id / digest / artifact id by guesswork
  - treat local pytest success as CI evidence
  - log raw token or response body into repo files
- LIVE restart condition:
  - a real GitHub Actions run matching the current commit and attestation bundle has been verified end-to-end

## 3. Authoritative JPX calendar source

- Status: deferred
- Owner: human/operator
- Why deferred: `KABUCOM_LIVE` must use an authoritative calendar source, not a local weekday heuristic
- Human procedure:
  1. Obtain the authoritative JPX calendar source.
  2. Record the source URL and source hash.
  3. Generate `closed_dates`, `trading_dates`, and `half_day_dates`.
  4. Record `generated_at`, `coverage_start`, and `coverage_end`.
  5. Verify stale and coverage-gap detection before publishing.
- Required evidence:
  - source URL
  - source hash
  - generated_at
  - coverage_start
  - coverage_end
  - closed_dates
  - trading_dates
  - half_day_dates
- Evidence location:
  - source record: `TBD` (human/operator managed)
  - generated calendar: `contracts/jpx_trading_calendar.json`
- Repository files to update after completion:
  - `contracts/jpx_trading_calendar.json`
  - `README.md`
  - `docs/kabucom_live_deferred_external_tasks.md`
  - tests if the schema changes
- Hashes/artifacts to refresh:
  - calendar file hash
  - source hash
  - generated_at
- Fail-closed behavior while incomplete:
  - `get_jpx_trading_day_status(require_source=True)` returns `jpx_calendar_missing`, `jpx_calendar_invalid`, or `jpx_calendar_coverage_gap`
  - `KABUCOM_LIVE` stays closed
- Do not:
  - generate the calendar from `jpholiday` fallback and call it authoritative
  - open LIVE on a coverage gap or fallback date
- LIVE restart condition:
  - the authoritative calendar exists, is valid, and fully covers the intended live date range

## 4. Broad live-risk constants / strategy review

- Status: deferred
- Owner: human/operator
- Why deferred: broad risk constants must come from a proper strategy review, not from a gate-circumvention patch
- Human procedure:
  1. Split train / validation / untouched holdout.
  2. Run walk-forward review.
  3. Run transaction cost stress, slippage stress, and capacity / liquidity stress.
  4. Review rule complexity and no-lookahead audit.
  5. Have the reviewer sign off on the artifact.
- Required evidence:
  - reviewed_at
  - reviewer
  - code_commit_sha
  - runtime_config_hash
  - approval_manifest_hash
  - no_lookahead_audit_hash
  - train_holdout_review
  - walk_forward_review
  - transaction_cost_stress
  - slippage_stress
  - capacity_liquidity_stress
  - rule_complexity_report
- Evidence location:
  - review packet: `TBD` (human/operator managed)
  - repo-side review artifact: `contracts/live_risk_review.json`
- Repository files to update after completion:
  - `contracts/live_risk_review.json`
  - `README.md`
  - `STRATEGY_EXPERIMENT_LOG.md`
- Hashes/artifacts to refresh:
  - `contracts/live_risk_review.json` hash
  - `runtime_config_hash`
  - `approval_manifest_hash`
  - `no_lookahead_audit_hash`
- Fail-closed behavior while incomplete:
  - `risk_readiness` stays `not_verified` or `blocked`
  - `no_lookahead_audit` is not `ready`
- Do not:
  - tweak broad constants only to make the gate green
  - reuse an outdated review artifact
  - collapse holdout or skip the audit
- LIVE restart condition:
  - the review artifact matches the current code / config state and the reviewer explicitly approves it

## Reopen rule

`KABUCOM_LIVE` の financial write は、上の 4 セクションがすべて complete になったときだけ再開可能です。1 つでも incomplete なら closed のままにします。
