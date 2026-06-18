from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.config import RUNTIME_LIVE_ORDER_CONFIG_HASH
from core.kabucom_contracts import (
    TEST_CONTRACT_FIXTURE_PATH,
    compute_contract_fixture_manifest_hash,
    hash_contract_fixture,
    load_contract_fixture,
)
from core.live_approval_manifest import compute_live_approval_manifest_hash, read_git_commit_sha
from core.live_write_attestation import (
    LIVE_WRITE_ATTESTATION_TEST_COMMAND,
    build_live_write_attestation,
    read_git_remote_repository_full_name,
    validate_live_write_attestation,
    write_live_write_attestation,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the structured live write attestation artifact used by KABUCOM_LIVE gating."
    )
    parser.add_argument(
        "--fixture-path",
        default=str(TEST_CONTRACT_FIXTURE_PATH),
        help="Path to the KABUCOM_TEST contract fixture used for attestation.",
    )
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "contracts" / "kabucom_live_write_attestation.json"),
        help="Destination JSON file for the attestation artifact.",
    )
    parser.add_argument(
        "--test-command",
        default=LIVE_WRITE_ATTESTATION_TEST_COMMAND,
        help="Command that produced the CI artifact evidence.",
    )
    parser.add_argument(
        "--ci-run-id",
        default=os.getenv("GITHUB_RUN_ID", ""),
        help="GitHub Actions run ID.",
    )
    parser.add_argument(
        "--ci-run-url",
        default="",
        help="GitHub Actions run URL. Defaults to the current repository run when omitted.",
    )
    parser.add_argument(
        "--ci-head-sha",
        default=os.getenv("GITHUB_SHA", ""),
        help="Commit SHA under test.",
    )
    parser.add_argument(
        "--repository-full-name",
        default=os.getenv("GITHUB_REPOSITORY", ""),
        help="GitHub repository full name such as owner/name.",
    )
    parser.add_argument(
        "--approved-config-hash",
        default=os.getenv("APPROVED_CONFIG_HASH", "").strip(),
        help="Approved config hash to record in the attestation. Required for actual KABUCOM_TEST captures.",
    )
    parser.add_argument(
        "--runtime-config-hash",
        default=RUNTIME_LIVE_ORDER_CONFIG_HASH,
        help="Runtime config hash to record in the attestation.",
    )
    parser.add_argument(
        "--approval-manifest-hash",
        default=compute_live_approval_manifest_hash(),
        help="Approval manifest hash to record in the attestation.",
    )
    return parser.parse_args()


def _resolve_ci_run_url(args: argparse.Namespace) -> str:
    if args.ci_run_url:
        return str(args.ci_run_url).strip()
    repository_full_name = str(args.repository_full_name or "").strip()
    ci_run_id = str(args.ci_run_id or "").strip()
    if repository_full_name and ci_run_id:
        server_url = os.getenv("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
        return f"{server_url}/{repository_full_name}/actions/runs/{ci_run_id}"
    return ""


def _validate_required_inputs(args: argparse.Namespace) -> None:
    missing = []
    if not str(args.ci_run_id or "").strip():
        missing.append("GITHUB_RUN_ID")
    if not str(args.ci_head_sha or "").strip():
        missing.append("GITHUB_SHA")
    if not str(args.repository_full_name or "").strip():
        missing.append("GITHUB_REPOSITORY")
    if missing:
        raise SystemExit(f"Missing required CI context: {', '.join(missing)}")


def _require_approved_config_hash(args: argparse.Namespace) -> str:
    approved_config_hash = str(args.approved_config_hash or "").strip()
    if not approved_config_hash:
        raise SystemExit(
            "Missing required APPROVED_CONFIG_HASH. Set it before building a live write attestation from an actual "
            "KABUCOM_TEST capture."
        )
    return approved_config_hash


def main() -> int:
    args = parse_args()
    fixture_path = Path(args.fixture_path)
    output_path = Path(args.output)
    fixture = load_contract_fixture(fixture_path)
    if not isinstance(fixture, dict):
        print(f"Skipping live write attestation build because fixture is missing: {fixture_path}")
        return 0
    if not bool(fixture.get("captured_from_kabucom_test")):
        print(
            "Skipping live write attestation build because the fixture is not an actual "
            "KABUCOM_TEST capture yet."
        )
        return 0

    _validate_required_inputs(args)
    ci_run_url = _resolve_ci_run_url(args)
    if not ci_run_url:
        raise SystemExit("Unable to resolve CI run URL.")
    approved_config_hash = _require_approved_config_hash(args)

    attestation = build_live_write_attestation(
        fixture_path=fixture_path,
        code_commit_sha=str(args.ci_head_sha).strip() or None,
        approval_manifest_hash=str(args.approval_manifest_hash).strip() or None,
        approved_config_hash=approved_config_hash,
        runtime_config_hash=str(args.runtime_config_hash).strip() or None,
        contract_fixture_manifest_hash=compute_contract_fixture_manifest_hash(),
        ci_run_id=str(args.ci_run_id).strip() or None,
        ci_run_url=ci_run_url,
        ci_head_sha=str(args.ci_head_sha).strip() or None,
        repository_full_name=str(args.repository_full_name).strip() or None,
        test_command=str(args.test_command).strip() or None,
    )
    write_live_write_attestation(output_path, attestation)

    validation = validate_live_write_attestation(
        attestation,
        expected_runtime_config_hash=str(args.runtime_config_hash).strip() or None,
        expected_approved_config_hash=approved_config_hash,
        expected_approval_manifest_hash=str(args.approval_manifest_hash).strip() or None,
        expected_code_commit_sha=str(args.ci_head_sha).strip() or None,
        expected_contract_fixture_manifest_hash=compute_contract_fixture_manifest_hash(),
        expected_test_fixture_hash=hash_contract_fixture(fixture_path),
        expected_repository_full_name=str(args.repository_full_name).strip() or None,
        expected_test_command=str(args.test_command).strip() or None,
        expected_captured_from_kabucom_test=True,
        expected_captured_at=fixture.get("captured_at"),
        expected_sanitized_fields=fixture.get("sanitized_fields"),
        expected_redaction_policy=fixture.get("redaction_policy"),
    )
    if not validation.valid:
        raise SystemExit(f"Generated attestation failed validation: {validation.reason}")

    digest_path = output_path.with_name(output_path.name + ".sha256")
    print(f"Wrote live write attestation bundle: {output_path} and {digest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
