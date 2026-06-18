from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

from core.config import RUNTIME_LIVE_ORDER_CONFIG_HASH
from core.kabucom_contracts import (
    TEST_CONTRACT_FIXTURE_PATH,
    compute_contract_fixture_manifest_hash,
    hash_contract_fixture,
    load_contract_fixture,
)
from core.live_approval_manifest import compute_live_approval_manifest_hash, read_git_commit_sha


LIVE_WRITE_ATTESTATION_SCHEMA_VERSION = 1
LIVE_WRITE_ATTESTATION_TEST_COMMAND = "python -m pytest tests -q"
LIVE_WRITE_ATTESTATION_DIGEST_SUFFIX = ".sha256"


@dataclass(frozen=True)
class LiveWriteAttestation:
    schema_version: int
    code_commit_sha: str | None
    approval_manifest_hash: str | None
    approved_config_hash: str | None
    runtime_config_hash: str | None
    contract_fixture_manifest_hash: str | None
    test_fixture_hash: str | None
    test_fixture_captured_from_kabucom_test: bool
    captured_at: str | None
    sanitized_fields: tuple[str, ...]
    redaction_policy: str | None
    provenance_note: str | None
    ci_run_id: str | None
    ci_run_url: str | None
    ci_head_sha: str | None
    repository_full_name: str | None
    test_command: str | None
    generated_at: str | None = None


@dataclass(frozen=True)
class LiveWriteAttestationValidationResult:
    valid: bool
    reason: str
    normalized_payload: dict[str, Any] | None = None


def _normalize_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize_json_value(item) for key, item in sorted(value.items(), key=lambda entry: str(entry[0]))}
    if isinstance(value, list):
        return [_normalize_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_json_value(item) for item in value]
    if isinstance(value, set):
        return [_normalize_json_value(item) for item in sorted(value, key=lambda item: repr(item))]
    if isinstance(value, Path):
        return str(value)
    return value


def _require_mapping(payload: Any) -> Mapping[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    return payload


def _normalize_string_sequence(values: Sequence[Any] | None) -> tuple[str, ...]:
    normalized = []
    if values is None:
        return ()
    for value in values:
        text = str(value or "").strip()
        if text:
            normalized.append(text)
    return tuple(sorted(normalized))


def _validation_failure(reason: str) -> LiveWriteAttestationValidationResult:
    return LiveWriteAttestationValidationResult(valid=False, reason=reason, normalized_payload=None)


def _validation_success(reason: str, payload: Mapping[str, Any]) -> LiveWriteAttestationValidationResult:
    return LiveWriteAttestationValidationResult(valid=True, reason=reason, normalized_payload=dict(payload))


def _parse_github_repository_full_name(remote_url: str) -> str | None:
    url = str(remote_url or "").strip()
    if not url:
        return None

    patterns = (
        r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$",
        r"git@github\.com:(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$",
    )
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            owner = match.group("owner").strip()
            repo = match.group("repo").strip()
            if owner and repo:
                return f"{owner}/{repo}"
    return None


@lru_cache(maxsize=1)
def read_git_remote_repository_full_name(repo_root: str | Path | None = None) -> str | None:
    root = Path(__file__).resolve().parents[1] if repo_root is None else Path(repo_root)
    try:
        completed = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None

    if completed.returncode != 0:
        return None
    return _parse_github_repository_full_name(completed.stdout)


def load_live_write_attestation(path: str | Path) -> dict[str, Any] | None:
    attestation_path = Path(path)
    if not attestation_path.exists():
        return None
    try:
        raw = json.loads(attestation_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    return raw


def _live_write_attestation_digest_path(path: str | Path) -> Path:
    attestation_path = Path(path)
    return attestation_path.with_name(attestation_path.name + LIVE_WRITE_ATTESTATION_DIGEST_SUFFIX)


def load_live_write_attestation_digest(path: str | Path) -> str | None:
    digest_path = _live_write_attestation_digest_path(path)
    if not digest_path.exists():
        return None
    try:
        digest_text = digest_path.read_text(encoding="utf-8")
    except Exception:
        return None
    digest = digest_text.strip().splitlines()[0].strip() if digest_text.strip() else ""
    return digest or None


def write_live_write_attestation_digest(
    path: str | Path,
    *,
    hash_value: str | None = None,
    attestation: LiveWriteAttestation | Mapping[str, Any] | None = None,
) -> Path:
    if hash_value is None:
        if attestation is None:
            raise ValueError("Either hash_value or attestation is required to write the digest sidecar")
        hash_value = compute_live_write_attestation_hash(attestation)
    digest_path = _live_write_attestation_digest_path(path)
    digest_path.parent.mkdir(parents=True, exist_ok=True)
    digest_path.write_text(f"{str(hash_value).strip()}\n", encoding="utf-8")
    return digest_path


def build_live_write_attestation(
    *,
    fixture_path: str | Path = TEST_CONTRACT_FIXTURE_PATH,
    code_commit_sha: str | None = None,
    approval_manifest_hash: str | None = None,
    approved_config_hash: str | None = None,
    runtime_config_hash: str | None = None,
    contract_fixture_manifest_hash: str | None = None,
    ci_run_id: str | None = None,
    ci_run_url: str | None = None,
    ci_head_sha: str | None = None,
    repository_full_name: str | None = None,
    test_command: str | None = None,
    generated_at: str | None = None,
) -> LiveWriteAttestation:
    fixture_path = Path(fixture_path)
    fixture = load_contract_fixture(fixture_path)
    code_commit_sha = read_git_commit_sha() if code_commit_sha is None else str(code_commit_sha).strip() or None
    repository_full_name = (
        read_git_remote_repository_full_name() if repository_full_name is None else str(repository_full_name).strip() or None
    )
    runtime_config_hash = RUNTIME_LIVE_ORDER_CONFIG_HASH if runtime_config_hash is None else str(runtime_config_hash).strip() or None
    approved_config_hash = None if approved_config_hash is None else str(approved_config_hash).strip() or None
    approval_manifest_hash = (
        compute_live_approval_manifest_hash() if approval_manifest_hash is None else str(approval_manifest_hash).strip() or None
    )
    contract_fixture_manifest_hash = (
        compute_contract_fixture_manifest_hash() if contract_fixture_manifest_hash is None else str(contract_fixture_manifest_hash).strip() or None
    )
    test_fixture_hash = hash_contract_fixture(fixture_path)
    captured_from_test = bool(fixture.get("captured_from_kabucom_test")) if isinstance(fixture, Mapping) else False
    captured_at = None
    if isinstance(fixture, Mapping):
        captured_at = str(fixture.get("captured_at") or "").strip() or None
    sanitized_fields = _normalize_string_sequence(fixture.get("sanitized_fields")) if isinstance(fixture, Mapping) else ()
    redaction_policy = None
    provenance_note = None
    if isinstance(fixture, Mapping):
        redaction_policy = str(fixture.get("redaction_policy") or "").strip() or None
        provenance_note = str(fixture.get("provenance_note") or "").strip() or None
    ci_head_sha = code_commit_sha if ci_head_sha is None else str(ci_head_sha).strip() or None
    test_command = LIVE_WRITE_ATTESTATION_TEST_COMMAND if test_command is None else str(test_command).strip() or None

    return LiveWriteAttestation(
        schema_version=LIVE_WRITE_ATTESTATION_SCHEMA_VERSION,
        code_commit_sha=code_commit_sha,
        approval_manifest_hash=approval_manifest_hash,
        approved_config_hash=approved_config_hash,
        runtime_config_hash=runtime_config_hash,
        contract_fixture_manifest_hash=contract_fixture_manifest_hash,
        test_fixture_hash=test_fixture_hash,
        test_fixture_captured_from_kabucom_test=captured_from_test,
        captured_at=captured_at,
        sanitized_fields=sanitized_fields,
        redaction_policy=redaction_policy,
        provenance_note=provenance_note,
        ci_run_id=ci_run_id,
        ci_run_url=ci_run_url,
        ci_head_sha=ci_head_sha,
        repository_full_name=repository_full_name,
        test_command=test_command,
        generated_at=generated_at,
    )


def write_live_write_attestation(path: str | Path, attestation: LiveWriteAttestation | None = None) -> Path:
    if attestation is None:
        raise ValueError("live write attestation is required")
    payload = asdict(attestation) if isinstance(attestation, LiveWriteAttestation) else dict(attestation)
    approved_config_hash = str(payload.get("approved_config_hash") or "").strip()
    if not approved_config_hash:
        raise ValueError("Cannot write live write attestation without approved_config_hash")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(_normalize_json_value(payload), sort_keys=True, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_live_write_attestation_digest(target, hash_value=compute_live_write_attestation_hash(payload))
    return target


def compute_live_write_attestation_hash(
    attestation: LiveWriteAttestation | Mapping[str, Any] | None = None,
) -> str:
    if attestation is None:
        attestation = build_live_write_attestation()
    if isinstance(attestation, LiveWriteAttestation):
        payload = asdict(attestation)
    else:
        payload = dict(attestation)
    payload.pop("generated_at", None)
    raw = json.dumps(_normalize_json_value(payload), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def validate_live_write_attestation(
    attestation: Any,
    *,
    expected_runtime_config_hash: str | None = None,
    expected_approved_config_hash: str | None = None,
    expected_approval_manifest_hash: str | None = None,
    expected_code_commit_sha: str | None = None,
    expected_contract_fixture_manifest_hash: str | None = None,
    expected_test_fixture_hash: str | None = None,
    expected_repository_full_name: str | None = None,
    expected_test_command: str | None = None,
    expected_captured_from_kabucom_test: bool | None = None,
    expected_captured_at: str | None = None,
    expected_sanitized_fields: Sequence[Any] | None = None,
    expected_redaction_policy: str | None = None,
) -> LiveWriteAttestationValidationResult:
    mapping = _require_mapping(attestation)
    if mapping is None:
        return _validation_failure("live_write_attestation_not_mapping")

    required_keys = (
        "schema_version",
        "code_commit_sha",
        "approval_manifest_hash",
        "approved_config_hash",
        "runtime_config_hash",
        "contract_fixture_manifest_hash",
        "test_fixture_hash",
        "test_fixture_captured_from_kabucom_test",
        "captured_at",
        "sanitized_fields",
        "redaction_policy",
        "ci_run_id",
        "ci_run_url",
        "ci_head_sha",
        "repository_full_name",
        "test_command",
    )
    missing = [key for key in required_keys if key not in mapping]
    if missing:
        return _validation_failure(f"live_write_attestation_missing:{','.join(missing)}")

    try:
        schema_version = int(mapping["schema_version"])
    except (TypeError, ValueError):
        return _validation_failure("live_write_attestation_schema_version_invalid")
    if schema_version != LIVE_WRITE_ATTESTATION_SCHEMA_VERSION:
        return _validation_failure("live_write_attestation_schema_version_mismatch")

    code_commit_sha = str(mapping.get("code_commit_sha") or "").strip()
    approval_manifest_hash = str(mapping.get("approval_manifest_hash") or "").strip()
    approved_config_hash = str(mapping.get("approved_config_hash") or "").strip()
    runtime_config_hash = str(mapping.get("runtime_config_hash") or "").strip()
    contract_fixture_manifest_hash = str(mapping.get("contract_fixture_manifest_hash") or "").strip()
    test_fixture_hash = str(mapping.get("test_fixture_hash") or "").strip()
    captured_at = str(mapping.get("captured_at") or "").strip()
    redaction_policy = str(mapping.get("redaction_policy") or "").strip()
    provenance_note = str(mapping.get("provenance_note") or "").strip()
    ci_run_id = str(mapping.get("ci_run_id") or "").strip()
    ci_run_url = str(mapping.get("ci_run_url") or "").strip()
    ci_head_sha = str(mapping.get("ci_head_sha") or "").strip()
    repository_full_name = str(mapping.get("repository_full_name") or "").strip()
    test_command = str(mapping.get("test_command") or "").strip()
    sanitized_fields = _normalize_string_sequence(mapping.get("sanitized_fields"))

    if not code_commit_sha:
        return _validation_failure("live_write_attestation_code_commit_sha_missing")
    if not approval_manifest_hash:
        return _validation_failure("live_write_attestation_approval_manifest_hash_missing")
    if not approved_config_hash:
        return _validation_failure("live_write_attestation_approved_config_hash_missing")
    if not runtime_config_hash:
        return _validation_failure("live_write_attestation_runtime_config_hash_missing")
    if not contract_fixture_manifest_hash:
        return _validation_failure("live_write_attestation_contract_fixture_manifest_hash_missing")
    if not test_fixture_hash:
        return _validation_failure("live_write_attestation_test_fixture_hash_missing")
    if not captured_at:
        return _validation_failure("live_write_attestation_captured_at_missing")
    if not redaction_policy:
        return _validation_failure("live_write_attestation_redaction_policy_missing")
    if not ci_run_id:
        return _validation_failure("live_write_attestation_ci_run_id_missing")
    if not ci_run_url:
        return _validation_failure("live_write_attestation_ci_run_url_missing")
    if not ci_head_sha:
        return _validation_failure("live_write_attestation_ci_head_sha_missing")
    if not repository_full_name:
        return _validation_failure("live_write_attestation_repository_full_name_missing")
    if not test_command:
        return _validation_failure("live_write_attestation_test_command_missing")
    if not sanitized_fields:
        return _validation_failure("live_write_attestation_sanitized_fields_missing")
    if bool(mapping.get("test_fixture_captured_from_kabucom_test")) is not True:
        return _validation_failure("live_write_attestation_not_captured_from_kabucom_test")

    if expected_code_commit_sha is not None and code_commit_sha != str(expected_code_commit_sha).strip():
        return _validation_failure("live_write_attestation_code_commit_sha_mismatch")
    if expected_runtime_config_hash is not None and runtime_config_hash != str(expected_runtime_config_hash).strip():
        return _validation_failure("live_write_attestation_runtime_config_hash_mismatch")
    if expected_approved_config_hash is not None and approved_config_hash != str(expected_approved_config_hash).strip():
        return _validation_failure("live_write_attestation_approved_config_hash_mismatch")
    if expected_approval_manifest_hash is not None and approval_manifest_hash != str(expected_approval_manifest_hash).strip():
        return _validation_failure("live_write_attestation_approval_manifest_hash_mismatch")
    if expected_contract_fixture_manifest_hash is not None and contract_fixture_manifest_hash != str(expected_contract_fixture_manifest_hash).strip():
        return _validation_failure("live_write_attestation_contract_fixture_manifest_hash_mismatch")
    if expected_test_fixture_hash is not None and test_fixture_hash != str(expected_test_fixture_hash).strip():
        return _validation_failure("live_write_attestation_test_fixture_hash_mismatch")
    if expected_repository_full_name is not None and repository_full_name != str(expected_repository_full_name).strip():
        return _validation_failure("live_write_attestation_repository_full_name_mismatch")
    if expected_test_command is not None and test_command != str(expected_test_command).strip():
        return _validation_failure("live_write_attestation_test_command_mismatch")
    if expected_captured_from_kabucom_test is not None and bool(mapping.get("test_fixture_captured_from_kabucom_test")) != bool(expected_captured_from_kabucom_test):
        return _validation_failure("live_write_attestation_capture_flag_mismatch")
    if expected_captured_at is not None and captured_at != str(expected_captured_at).strip():
        return _validation_failure("live_write_attestation_captured_at_mismatch")
    if expected_sanitized_fields is not None and sanitized_fields != _normalize_string_sequence(expected_sanitized_fields):
        return _validation_failure("live_write_attestation_sanitized_fields_mismatch")
    if expected_redaction_policy is not None and redaction_policy != str(expected_redaction_policy).strip():
        return _validation_failure("live_write_attestation_redaction_policy_mismatch")

    run_url_prefix = f"https://github.com/{repository_full_name}/actions/runs/{ci_run_id}"
    if not ci_run_url.startswith(run_url_prefix):
        return _validation_failure("live_write_attestation_ci_run_url_mismatch")
    if ci_head_sha != code_commit_sha:
        return _validation_failure("live_write_attestation_ci_head_sha_mismatch")

    normalized_payload = dict(mapping)
    normalized_payload["sanitized_fields"] = list(sanitized_fields)
    if provenance_note:
        normalized_payload["provenance_note"] = provenance_note
    return _validation_success("live_write_attestation_ok", normalized_payload)
