from dataclasses import replace
import unittest
from unittest.mock import patch

from core.live_approval_manifest import (
    LiveApprovalManifest,
    build_live_approval_manifest,
    compute_live_approval_manifest_hash,
    load_live_approval_manifest,
    write_live_approval_manifest,
)
from core.kabucom_contracts import CONTRACT_FIXTURE_PATH, hash_contract_fixture


class TestLiveApprovalManifest(unittest.TestCase):
    def test_manifest_hash_changes_when_strategy_constant_changes(self):
        base_hash = compute_live_approval_manifest_hash()

        with patch("core.logic.DAYTRADE_PRIMARY_MID_BREADTH_MAX", 0.571):
            changed_hash = compute_live_approval_manifest_hash()

        self.assertNotEqual(base_hash, changed_hash)

    def test_manifest_hash_ignores_generated_at_metadata(self):
        manifest = build_live_approval_manifest(generated_at="2026-06-12T00:00:00Z")
        base_hash = compute_live_approval_manifest_hash(manifest)

        mutated = replace(manifest, generated_at="2026-06-13T00:00:00Z")
        self.assertEqual(base_hash, compute_live_approval_manifest_hash(mutated))

    def test_manifest_roundtrips_through_json_file(self):
        manifest = build_live_approval_manifest(generated_at="2026-06-12T00:00:00Z")
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "live_approval_manifest.json"
            written_path = write_live_approval_manifest(path, manifest)
            loaded = load_live_approval_manifest(written_path)

        self.assertIsInstance(loaded, LiveApprovalManifest)
        self.assertEqual(loaded.schema_version, manifest.schema_version)
        self.assertEqual(loaded.code_commit_sha, manifest.code_commit_sha)
        self.assertEqual(loaded.api_spec_version, manifest.api_spec_version)
        self.assertEqual(loaded.api_spec_commit_sha, manifest.api_spec_commit_sha)
        self.assertEqual(loaded.api_spec_acquired_at, manifest.api_spec_acquired_at)
        self.assertEqual(loaded.config_snapshot, manifest.config_snapshot)
        self.assertEqual(loaded.strategy_snapshot, manifest.strategy_snapshot)
        self.assertEqual(loaded.rotation_snapshot, manifest.rotation_snapshot)
        self.assertEqual(loaded.code_file_hashes, manifest.code_file_hashes)
        self.assertEqual(loaded.api_contract_fixture_hash, manifest.api_contract_fixture_hash)
        self.assertEqual(loaded.generated_at, manifest.generated_at)

    def test_manifest_includes_contract_fixture_hash(self):
        manifest = build_live_approval_manifest(generated_at="2026-06-12T00:00:00Z")
        self.assertEqual(manifest.api_contract_fixture_hash, hash_contract_fixture(CONTRACT_FIXTURE_PATH))
        self.assertIsNotNone(manifest.api_contract_fixture_hash)
        self.assertEqual(manifest.api_spec_version, "1.5")
        self.assertEqual(manifest.api_spec_commit_sha, "0119077f1647b7c3ff64460b862c1978142df43d")
        self.assertEqual(manifest.api_spec_acquired_at, "2026-06-12")
