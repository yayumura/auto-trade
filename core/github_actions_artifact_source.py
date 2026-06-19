from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import io
import json
import os
import time
from pathlib import Path
from typing import Any
import zipfile

import requests

from core.live_write_attestation import compute_live_write_attestation_hash


GITHUB_API_VERSION = "2022-11-28"
GITHUB_API_BASE_URL = "https://api.github.com"
LIVE_WRITE_ATTESTATION_ARTIFACT_NAME = "live-write-attestation"
DEFAULT_GITHUB_ARTIFACT_SOURCE_CACHE_TTL_SEC = 600


@dataclass(frozen=True)
class GitHubArtifactSourceVerificationResult:
    valid: bool
    reason: str
    workflow_run_id: int | None = None
    workflow_run_status: str | None = None
    workflow_run_conclusion: str | None = None
    artifact_id: int | None = None
    artifact_name: str | None = None
    artifact_digest: str | None = None
    downloaded_archive_digest: str | None = None


@dataclass(frozen=True)
class GitHubArtifactSourceCacheEntry:
    stored_at: float
    result: GitHubArtifactSourceVerificationResult


_GITHUB_ARTIFACT_SOURCE_CACHE: dict[tuple[str, ...], GitHubArtifactSourceCacheEntry] = {}


def _failure(reason: str, **kwargs: Any) -> GitHubArtifactSourceVerificationResult:
    return GitHubArtifactSourceVerificationResult(valid=False, reason=reason, **kwargs)


def _success(reason: str, **kwargs: Any) -> GitHubArtifactSourceVerificationResult:
    return GitHubArtifactSourceVerificationResult(valid=True, reason=reason, **kwargs)


def _read_json_file(path: str | Path) -> dict[str, Any] | None:
    file_path = Path(path)
    if not file_path.exists():
        return None
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _read_text_file(path: str | Path) -> str | None:
    file_path = Path(path)
    if not file_path.exists():
        return None
    try:
        return file_path.read_text(encoding="utf-8").strip()
    except Exception:
        return None


def _extract_zip_entry_text(archive: zipfile.ZipFile, expected_name: str) -> str | None:
    exact_matches = [name for name in archive.namelist() if name == expected_name or name.endswith(f"/{expected_name}")]
    if not exact_matches:
        return None
    try:
        return archive.read(exact_matches[0]).decode("utf-8").strip()
    except Exception:
        return None


def _get_token(explicit_token: str | None = None) -> str | None:
    if explicit_token is not None:
        token = str(explicit_token).strip()
        return token or None
    for env_name in ("GITHUB_TOKEN", "GH_TOKEN"):
        raw = os.getenv(env_name)
        if raw and raw.strip():
            return raw.strip()
    return None


def _coerce_int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except Exception:
        return None


def clear_live_write_attestation_artifact_source_cache() -> None:
    _GITHUB_ARTIFACT_SOURCE_CACHE.clear()


def _get_cache_ttl_sec() -> float:
    raw = os.getenv("GITHUB_ARTIFACT_SOURCE_CACHE_TTL_SEC")
    if raw is None or not raw.strip():
        return float(DEFAULT_GITHUB_ARTIFACT_SOURCE_CACHE_TTL_SEC)
    try:
        ttl = float(raw)
    except ValueError:
        return 0.0
    return max(0.0, ttl)


def _session_cache_fingerprint(session: requests.Session | None) -> str:
    if session is None:
        return "default_session"
    return f"{session.__class__.__module__}.{session.__class__.__qualname__}:{id(session)}"


def _token_cache_fingerprint(token: str | None) -> str:
    if token is None:
        return "missing"
    return sha256(token.encode("utf-8")).hexdigest()


def _build_cache_key(
    *,
    repository_full_name: str,
    workflow_run_id: str,
    head_sha: str,
    artifact_name: str,
    local_attestation_hash: str,
    local_digest_text: str,
    token: str | None,
    session: requests.Session | None,
) -> tuple[str, ...]:
    return (
        repository_full_name,
        workflow_run_id,
        head_sha,
        artifact_name,
        local_attestation_hash,
        local_digest_text,
        _token_cache_fingerprint(token),
        _session_cache_fingerprint(session),
    )


def _get_cached_verification_result(cache_key: tuple[str, ...], ttl_sec: float) -> GitHubArtifactSourceVerificationResult | None:
    if ttl_sec <= 0:
        return None
    cache_entry = _GITHUB_ARTIFACT_SOURCE_CACHE.get(cache_key)
    if cache_entry is None:
        return None
    if time.monotonic() - cache_entry.stored_at > ttl_sec:
        _GITHUB_ARTIFACT_SOURCE_CACHE.pop(cache_key, None)
        return None
    return cache_entry.result


def _store_cached_verification_result(
    cache_key: tuple[str, ...],
    result: GitHubArtifactSourceVerificationResult,
    ttl_sec: float,
) -> GitHubArtifactSourceVerificationResult:
    if ttl_sec > 0 and result.valid:
        _GITHUB_ARTIFACT_SOURCE_CACHE[cache_key] = GitHubArtifactSourceCacheEntry(
            stored_at=time.monotonic(),
            result=result,
        )
    return result


def verify_live_write_attestation_artifact_source(
    *,
    repository_full_name: str,
    workflow_run_id: str | int,
    head_sha: str,
    local_attestation_path: str | Path,
    artifact_name: str = LIVE_WRITE_ATTESTATION_ARTIFACT_NAME,
    token: str | None = None,
    session: requests.Session | None = None,
    timeout_sec: float = 15.0,
) -> GitHubArtifactSourceVerificationResult:
    repository = str(repository_full_name or "").strip()
    if "/" not in repository:
        return _failure("repository_full_name_invalid")

    run_id_text = str(workflow_run_id or "").strip()
    if not run_id_text:
        return _failure("workflow_run_id_missing")

    expected_head_sha = str(head_sha or "").strip()
    if not expected_head_sha:
        return _failure("head_sha_missing")

    attestation_payload = _read_json_file(local_attestation_path)
    if attestation_payload is None:
        return _failure("local_attestation_missing_or_invalid")

    attestation_text = Path(local_attestation_path).read_text(encoding="utf-8").strip()
    local_digest_path = Path(local_attestation_path).with_name(Path(local_attestation_path).name + ".sha256")
    local_digest_text = _read_text_file(local_digest_path)
    if local_digest_text is None:
        return _failure("local_attestation_digest_missing")

    resolved_token = _get_token(token)
    ttl_sec = _get_cache_ttl_sec()
    cache_key = _build_cache_key(
        repository_full_name=repository,
        workflow_run_id=run_id_text,
        head_sha=expected_head_sha,
        artifact_name=artifact_name,
        local_attestation_hash=compute_live_write_attestation_hash(attestation_payload),
        local_digest_text=local_digest_text,
        token=resolved_token,
        session=session,
    )
    cached_result = _get_cached_verification_result(cache_key, ttl_sec)
    if cached_result is not None:
        return cached_result

    if not resolved_token:
        return _failure("github_token_missing")

    http = session or requests.Session()
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {resolved_token}",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }

    run_url = f"{GITHUB_API_BASE_URL}/repos/{repository}/actions/runs/{run_id_text}"
    try:
        run_response = http.get(run_url, headers=headers, timeout=timeout_sec)
    except requests.RequestException:
        return _failure("workflow_run_request_failed")
    if run_response.status_code != 200:
        return _failure(f"workflow_run_http_{run_response.status_code}")
    try:
        run_payload = run_response.json()
    except Exception:
        return _failure("workflow_run_invalid_json")
    if not isinstance(run_payload, dict):
        return _failure("workflow_run_not_mapping")

    run_status = str(run_payload.get("status") or "").strip()
    run_conclusion = str(run_payload.get("conclusion") or "").strip()
    run_head_sha = str(run_payload.get("head_sha") or "").strip()
    if run_status != "completed":
        return _failure(
            f"workflow_run_not_completed:{run_status or 'missing'}",
            workflow_run_id=_coerce_int(run_id_text),
            workflow_run_status=run_status or None,
            workflow_run_conclusion=run_conclusion or None,
        )
    if run_conclusion != "success":
        return _failure(
            f"workflow_run_conclusion_{run_conclusion or 'missing'}",
            workflow_run_id=_coerce_int(run_id_text),
            workflow_run_status=run_status or None,
            workflow_run_conclusion=run_conclusion or None,
        )
    if run_head_sha != expected_head_sha:
        return _failure(
            "workflow_run_head_sha_mismatch",
            workflow_run_id=_coerce_int(run_id_text),
            workflow_run_status=run_status or None,
            workflow_run_conclusion=run_conclusion or None,
        )

    artifacts_url = f"{GITHUB_API_BASE_URL}/repos/{repository}/actions/runs/{run_id_text}/artifacts"
    try:
        artifacts_response = http.get(artifacts_url, headers=headers, timeout=timeout_sec)
    except requests.RequestException:
        return _failure(
            "workflow_run_artifacts_request_failed",
            workflow_run_id=_coerce_int(run_id_text),
            workflow_run_status=run_status or None,
            workflow_run_conclusion=run_conclusion or None,
        )
    if artifacts_response.status_code != 200:
        return _failure(
            f"workflow_run_artifacts_http_{artifacts_response.status_code}",
            workflow_run_id=_coerce_int(run_id_text),
            workflow_run_status=run_status or None,
            workflow_run_conclusion=run_conclusion or None,
        )
    try:
        artifacts_payload = artifacts_response.json()
    except Exception:
        return _failure("workflow_run_artifacts_invalid_json", workflow_run_id=_coerce_int(run_id_text))
    artifacts = artifacts_payload.get("artifacts") if isinstance(artifacts_payload, dict) else None
    if not isinstance(artifacts, list):
        return _failure("workflow_run_artifacts_not_list", workflow_run_id=_coerce_int(run_id_text))

    matching_artifacts = [artifact for artifact in artifacts if isinstance(artifact, dict) and str(artifact.get("name") or "").strip() == artifact_name]
    if not matching_artifacts:
        return _failure(
            "workflow_artifact_name_missing",
            workflow_run_id=_coerce_int(run_id_text),
            workflow_run_status=run_status or None,
            workflow_run_conclusion=run_conclusion or None,
        )

    artifact = matching_artifacts[0]
    artifact_id = artifact.get("id")
    artifact_id_int = _coerce_int(artifact_id)
    artifact_digest = str(artifact.get("digest") or "").strip() or None
    if not artifact_digest or not artifact_digest.startswith("sha256:"):
        return _failure(
            "workflow_artifact_digest_missing",
            workflow_run_id=_coerce_int(run_id_text),
            workflow_run_status=run_status or None,
            workflow_run_conclusion=run_conclusion or None,
            artifact_id=artifact_id_int,
            artifact_name=artifact_name,
        )
    if bool(artifact.get("expired")):
        return _failure(
            "workflow_artifact_expired",
            workflow_run_id=_coerce_int(run_id_text),
            workflow_run_status=run_status or None,
            workflow_run_conclusion=run_conclusion or None,
            artifact_id=artifact_id_int,
            artifact_name=artifact_name,
            artifact_digest=artifact_digest,
        )

    workflow_run = artifact.get("workflow_run")
    if not isinstance(workflow_run, dict):
        return _failure(
            "workflow_artifact_missing_run_metadata",
            workflow_run_id=_coerce_int(run_id_text),
            workflow_run_status=run_status or None,
            workflow_run_conclusion=run_conclusion or None,
            artifact_id=artifact_id_int,
            artifact_name=artifact_name,
            artifact_digest=artifact_digest,
        )
    workflow_run_head_sha = str(workflow_run.get("head_sha") or "").strip()
    if workflow_run_head_sha != expected_head_sha:
        return _failure(
            "workflow_artifact_head_sha_mismatch",
            workflow_run_id=_coerce_int(run_id_text),
            workflow_run_status=run_status or None,
            workflow_run_conclusion=run_conclusion or None,
            artifact_id=artifact_id_int,
            artifact_name=artifact_name,
            artifact_digest=artifact_digest,
        )

    archive_url = str(artifact.get("archive_download_url") or "").strip()
    if not archive_url:
        return _failure(
            "workflow_artifact_archive_url_missing",
            workflow_run_id=_coerce_int(run_id_text),
            workflow_run_status=run_status or None,
            workflow_run_conclusion=run_conclusion or None,
            artifact_id=artifact_id_int,
            artifact_name=artifact_name,
            artifact_digest=artifact_digest,
        )

    try:
        archive_response = http.get(archive_url, headers=headers, timeout=timeout_sec, allow_redirects=True)
    except requests.RequestException:
        return _failure(
            "workflow_artifact_download_request_failed",
            workflow_run_id=_coerce_int(run_id_text),
            workflow_run_status=run_status or None,
            workflow_run_conclusion=run_conclusion or None,
            artifact_id=artifact_id_int,
            artifact_name=artifact_name,
            artifact_digest=artifact_digest,
        )
    if archive_response.status_code != 200:
        return _failure(
            f"workflow_artifact_download_http_{archive_response.status_code}",
            workflow_run_id=_coerce_int(run_id_text),
            workflow_run_status=run_status or None,
            workflow_run_conclusion=run_conclusion or None,
            artifact_id=artifact_id_int,
            artifact_name=artifact_name,
            artifact_digest=artifact_digest,
        )
    archive_bytes = archive_response.content
    archive_bytes_digest = f"sha256:{sha256(archive_bytes).hexdigest()}"
    if archive_bytes_digest != artifact_digest:
        return _failure(
            "workflow_artifact_archive_digest_mismatch",
            workflow_run_id=_coerce_int(run_id_text),
            workflow_run_status=run_status or None,
            workflow_run_conclusion=run_conclusion or None,
            artifact_id=artifact_id_int,
            artifact_name=artifact_name,
            artifact_digest=artifact_digest,
            downloaded_archive_digest=archive_bytes_digest,
        )

    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            local_attestation_name = Path(local_attestation_path).name
            local_digest_name = f"{local_attestation_name}.sha256"
            artifact_attestation_text = _extract_zip_entry_text(archive, local_attestation_name)
            artifact_digest_text = _extract_zip_entry_text(archive, local_digest_name)
    except zipfile.BadZipFile:
        return _failure(
            "workflow_artifact_not_zip",
            workflow_run_id=_coerce_int(run_id_text),
            workflow_run_status=run_status or None,
            workflow_run_conclusion=run_conclusion or None,
            artifact_id=artifact_id_int,
            artifact_name=artifact_name,
            artifact_digest=artifact_digest,
            downloaded_archive_digest=archive_bytes_digest,
        )

    if artifact_attestation_text is None:
        return _failure(
            "workflow_artifact_attestation_missing",
            workflow_run_id=_coerce_int(run_id_text),
            workflow_run_status=run_status or None,
            workflow_run_conclusion=run_conclusion or None,
            artifact_id=artifact_id_int,
            artifact_name=artifact_name,
            artifact_digest=artifact_digest,
            downloaded_archive_digest=archive_bytes_digest,
        )
    if artifact_digest_text is None:
        return _failure(
            "workflow_artifact_digest_sidecar_missing",
            workflow_run_id=_coerce_int(run_id_text),
            workflow_run_status=run_status or None,
            workflow_run_conclusion=run_conclusion or None,
            artifact_id=artifact_id_int,
            artifact_name=artifact_name,
            artifact_digest=artifact_digest,
            downloaded_archive_digest=archive_bytes_digest,
        )

    try:
        artifact_attestation_payload = json.loads(artifact_attestation_text)
    except Exception:
        return _failure(
            "workflow_artifact_attestation_invalid_json",
            workflow_run_id=_coerce_int(run_id_text),
            workflow_run_status=run_status or None,
            workflow_run_conclusion=run_conclusion or None,
            artifact_id=artifact_id_int,
            artifact_name=artifact_name,
            artifact_digest=artifact_digest,
            downloaded_archive_digest=archive_bytes_digest,
        )
    if artifact_attestation_payload != attestation_payload:
        return _failure(
            "workflow_artifact_attestation_payload_mismatch",
            workflow_run_id=_coerce_int(run_id_text),
            workflow_run_status=run_status or None,
            workflow_run_conclusion=run_conclusion or None,
            artifact_id=artifact_id_int,
            artifact_name=artifact_name,
            artifact_digest=artifact_digest,
            downloaded_archive_digest=archive_bytes_digest,
        )
    if artifact_digest_text != local_digest_text:
        return _failure(
            "workflow_artifact_digest_sidecar_mismatch",
            workflow_run_id=_coerce_int(run_id_text),
            workflow_run_status=run_status or None,
            workflow_run_conclusion=run_conclusion or None,
            artifact_id=artifact_id_int,
            artifact_name=artifact_name,
            artifact_digest=artifact_digest,
            downloaded_archive_digest=archive_bytes_digest,
        )

    return _success(
        "github_actions_artifact_source_verified",
        workflow_run_id=_coerce_int(run_id_text),
        workflow_run_status=run_status or None,
        workflow_run_conclusion=run_conclusion or None,
        artifact_id=artifact_id_int,
        artifact_name=artifact_name,
        artifact_digest=artifact_digest,
        downloaded_archive_digest=archive_bytes_digest,
    ) if ttl_sec <= 0 else _store_cached_verification_result(
        cache_key,
        _success(
            "github_actions_artifact_source_verified",
            workflow_run_id=_coerce_int(run_id_text),
            workflow_run_status=run_status or None,
            workflow_run_conclusion=run_conclusion or None,
            artifact_id=artifact_id_int,
            artifact_name=artifact_name,
            artifact_digest=artifact_digest,
            downloaded_archive_digest=archive_bytes_digest,
        ),
        ttl_sec,
    )
