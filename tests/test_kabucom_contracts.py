import json
import tempfile
import unittest
from pathlib import Path

from core.kabucom_contracts import (
    CONTRACT_FIXTURE_PATH,
    CONTRACT_MANIFEST_PATH,
    build_contract_fixture_manifest,
    compute_contract_fixture_manifest_hash,
    hash_contract_fixture,
    load_contract_fixture,
    load_contract_fixture_manifest,
    validate_cancel_order_request_payload,
    validate_market_order_request_payload,
    validate_orders_list_response,
    validate_official_contract_fixture,
    validate_stop_order_request_payload,
    validate_wallet_balance_response,
)


class TestKabucomContracts(unittest.TestCase):
    def test_contract_fixture_matches_validators(self):
        fixture = load_contract_fixture(CONTRACT_FIXTURE_PATH)
        self.assertIsInstance(fixture, dict)
        self.assertEqual(fixture["fixture_kind"], "OFFICIAL_OPENAPI")
        self.assertEqual(fixture["api_spec_version"], "1.5")
        self.assertEqual(fixture["api_spec_commit_sha"], "0119077f1647b7c3ff64460b862c1978142df43d")
        self.assertEqual(fixture["api_spec_acquired_at"], "2026-06-12")
        self.assertNotIn("Password", fixture["requests"]["market_order"])
        self.assertNotIn("Password", fixture["requests"]["stop_order"])
        self.assertNotIn("Password", fixture["requests"]["cancel_order"])

        self.assertTrue(validate_official_contract_fixture(fixture).valid)
        self.assertTrue(validate_market_order_request_payload(fixture["requests"]["market_order"]).valid)
        self.assertTrue(validate_stop_order_request_payload(fixture["requests"]["stop_order"]).valid)
        self.assertTrue(validate_cancel_order_request_payload(fixture["requests"]["cancel_order"]).valid)
        self.assertTrue(validate_wallet_balance_response(fixture["responses"]["wallet_cash"], required_key="StockAccountWallet").valid)
        self.assertTrue(validate_wallet_balance_response(fixture["responses"]["wallet_margin"], required_key="MarginAccountWallet").valid)
        self.assertTrue(validate_orders_list_response(fixture["responses"]["orders"]).valid)
        self.assertIsNotNone(hash_contract_fixture(CONTRACT_FIXTURE_PATH))
        self.assertIsNotNone(compute_contract_fixture_manifest_hash())

        manifest = build_contract_fixture_manifest()
        loaded_manifest = load_contract_fixture_manifest(CONTRACT_MANIFEST_PATH)
        self.assertEqual(manifest, loaded_manifest)
        self.assertEqual(manifest.official_fixture_hash, hash_contract_fixture(CONTRACT_FIXTURE_PATH))
        self.assertEqual(manifest.api_spec_version, "1.5")
        self.assertEqual(manifest.api_spec_commit_sha, "0119077f1647b7c3ff64460b862c1978142df43d")
        self.assertEqual(manifest.api_spec_acquired_at, "2026-06-12")
        self.assertEqual(manifest.official_fixture_kind, "OFFICIAL_OPENAPI")
        self.assertEqual(manifest.test_fixture_kind, "KABUCOM_TEST")
        self.assertEqual(manifest.password_policy, "api_password_fallback_allowed")

    def test_wallet_balance_validator_allows_zero(self):
        self.assertTrue(validate_wallet_balance_response({"StockAccountWallet": 0}, required_key="StockAccountWallet").valid)
        self.assertTrue(validate_wallet_balance_response({"MarginAccountWallet": 0.0}, required_key="MarginAccountWallet").valid)

    def test_contract_fixture_hash_changes_when_payload_changes(self):
        fixture = load_contract_fixture(CONTRACT_FIXTURE_PATH)
        self.assertIsInstance(fixture, dict)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "fixture.json"
            path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8")
            base_hash = hash_contract_fixture(path)

            mutated = dict(fixture)
            mutated["responses"] = dict(fixture["responses"])
            mutated["responses"]["wallet_cash"] = {"StockAccountWallet": 222222.0}
            path.write_text(json.dumps(mutated, ensure_ascii=False, indent=2), encoding="utf-8")
            changed_hash = hash_contract_fixture(path)

        self.assertNotEqual(base_hash, changed_hash)

    def test_official_contract_fixture_rejects_test_only_password_field(self):
        fixture = load_contract_fixture(CONTRACT_FIXTURE_PATH)
        self.assertIsInstance(fixture, dict)
        mutated = json.loads(json.dumps(fixture))
        mutated["requests"]["market_order"]["Password"] = "<redacted>"

        self.assertFalse(validate_official_contract_fixture(mutated).valid)


if __name__ == "__main__":
    unittest.main()
