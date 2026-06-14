from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from core.kabucom_contracts import CONTRACT_FIXTURE_PATH, hash_contract_fixture, load_contract_fixture


MANIFEST_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class LiveApprovalManifest:
    schema_version: int
    code_commit_sha: str | None
    api_spec_version: str | None
    api_spec_commit_sha: str | None
    api_spec_acquired_at: str | None
    config_snapshot: dict[str, Any]
    strategy_snapshot: dict[str, Any]
    rotation_snapshot: dict[str, Any]
    code_file_hashes: dict[str, str]
    api_contract_fixture_hash: str | None = None
    generated_at: str | None = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _git_dir(repo_root: Path | None = None) -> Path | None:
    root = _repo_root() if repo_root is None else Path(repo_root)
    git_path = root / ".git"
    if git_path.is_dir():
        return git_path
    if git_path.is_file():
        try:
            content = git_path.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        prefix = "gitdir:"
        if content.lower().startswith(prefix):
            git_dir = content[len(prefix):].strip()
            if git_dir:
                candidate = Path(git_dir)
                if not candidate.is_absolute():
                    candidate = (root / candidate).resolve()
                return candidate
    return None


def _resolve_git_ref(git_dir: Path, ref_name: str) -> str | None:
    ref_path = git_dir / ref_name
    try:
        if ref_path.is_file():
            content = ref_path.read_text(encoding="utf-8").strip()
            if content:
                return content
    except OSError:
        pass

    packed_refs = git_dir / "packed-refs"
    try:
        if packed_refs.is_file():
            target = f" {ref_name}"
            for line in packed_refs.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or stripped.startswith("^"):
                    continue
                if stripped.endswith(target) or stripped.endswith(f" {ref_name}"):
                    return stripped.split(" ", 1)[0]
    except OSError:
        pass
    return None


def read_git_commit_sha(repo_root: Path | None = None) -> str | None:
    git_dir = _git_dir(repo_root)
    if git_dir is None:
        return None

    head_path = git_dir / "HEAD"
    try:
        head_text = head_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not head_text:
        return None

    if head_text.startswith("ref:"):
        ref_name = head_text.split(":", 1)[1].strip()
        if not ref_name:
            return None
        resolved = _resolve_git_ref(git_dir, ref_name)
        if resolved:
            return resolved
        return None

    return head_text


def _hash_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _hash_file(path: Path) -> str:
    try:
        payload = path.read_bytes()
    except OSError:
        return "missing"
    return sha256(payload).hexdigest()


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
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _collect_strategy_snapshot(logic_module: Any) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for name, value in vars(logic_module).items():
        if not name.startswith("DAYTRADE_"):
            continue
        if callable(value):
            continue
        if name.startswith("__"):
            continue
        snapshot[name] = value
    return dict(sorted(snapshot.items()))


def _collect_code_file_hashes(repo_root: Path | None = None) -> dict[str, str]:
    root = _repo_root() if repo_root is None else Path(repo_root)
    rel_paths = [
        "core/config.py",
        "core/logic.py",
        "core/monthly_rotation_strategy.py",
        "core/live_order_gate.py",
        "core/kabucom_broker.py",
        "auto_trade.py",
    ]
    return {rel_path: _hash_file(root / rel_path) for rel_path in rel_paths}


def build_live_approval_manifest(
    *,
    repo_root: Path | None = None,
    config_module: Any | None = None,
    logic_module: Any | None = None,
    generated_at: str | None = None,
) -> LiveApprovalManifest:
    if config_module is None:
        from core import config as config_module  # type: ignore
    if logic_module is None:
        from core import logic as logic_module  # type: ignore

    config_snapshot = _normalize_json_value(dict(config_module.build_runtime_live_order_config_snapshot()))
    strategy_snapshot = _normalize_json_value(_collect_strategy_snapshot(logic_module))
    code_commit_sha = read_git_commit_sha(repo_root=repo_root)
    contract_fixture = load_contract_fixture(CONTRACT_FIXTURE_PATH)
    api_spec_version = None
    api_spec_commit_sha = None
    api_spec_acquired_at = None
    if isinstance(contract_fixture, dict):
        api_spec_version = contract_fixture.get("api_spec_version")
        api_spec_commit_sha = contract_fixture.get("api_spec_commit_sha")
        api_spec_acquired_at = contract_fixture.get("api_spec_acquired_at")
    manifest_generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    code_file_hashes = _normalize_json_value(_collect_code_file_hashes(repo_root=repo_root))
    rotation_snapshot = _normalize_json_value(
        {
            "module_file_hash": code_file_hashes.get("core/monthly_rotation_strategy.py", "missing"),
        }
    )
    return LiveApprovalManifest(
        schema_version=MANIFEST_SCHEMA_VERSION,
        code_commit_sha=code_commit_sha,
        api_spec_version=None if api_spec_version is None else str(api_spec_version),
        api_spec_commit_sha=None if api_spec_commit_sha is None else str(api_spec_commit_sha),
        api_spec_acquired_at=None if api_spec_acquired_at is None else str(api_spec_acquired_at),
        config_snapshot=config_snapshot,
        strategy_snapshot=strategy_snapshot,
        rotation_snapshot=rotation_snapshot,
        code_file_hashes=code_file_hashes,
        api_contract_fixture_hash=hash_contract_fixture(CONTRACT_FIXTURE_PATH),
        generated_at=manifest_generated_at,
    )


def manifest_to_canonical_payload(manifest: LiveApprovalManifest | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(manifest, LiveApprovalManifest):
        payload = asdict(manifest)
    else:
        payload = dict(manifest)
    payload.pop("generated_at", None)
    return _normalize_json_value(payload)


def compute_live_approval_manifest_hash(
    manifest: LiveApprovalManifest | Mapping[str, Any] | None = None,
) -> str:
    if manifest is None:
        manifest = build_live_approval_manifest()
    payload = manifest_to_canonical_payload(manifest)
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256(raw).hexdigest()}"


def write_live_approval_manifest(path: str | Path, manifest: LiveApprovalManifest | None = None) -> Path:
    manifest = build_live_approval_manifest() if manifest is None else manifest
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(_normalize_json_value(asdict(manifest)), sort_keys=True, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target


def load_live_approval_manifest(path: str | Path) -> LiveApprovalManifest:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return LiveApprovalManifest(
        schema_version=int(raw["schema_version"]),
        code_commit_sha=raw.get("code_commit_sha"),
        api_spec_version=raw.get("api_spec_version"),
        api_spec_commit_sha=raw.get("api_spec_commit_sha"),
        api_spec_acquired_at=raw.get("api_spec_acquired_at"),
        config_snapshot=dict(raw.get("config_snapshot") or {}),
        strategy_snapshot=dict(raw.get("strategy_snapshot") or {}),
        rotation_snapshot=dict(raw.get("rotation_snapshot") or {}),
        code_file_hashes=dict(raw.get("code_file_hashes") or {}),
        api_contract_fixture_hash=raw.get("api_contract_fixture_hash"),
        generated_at=raw.get("generated_at"),
    )
