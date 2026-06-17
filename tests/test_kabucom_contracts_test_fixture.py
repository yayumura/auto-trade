import unittest

from core.kabucom_contracts import (
    TEST_CONTRACT_FIXTURE_PATH,
    build_contract_fixture_manifest,
    hash_contract_fixture,
    load_contract_fixture,
    validate_contract_fixture,
    validate_cancel_order_request_payload,
    validate_market_order_request_payload,
    validate_orders_list_response,
    validate_test_contract_fixture,
    validate_stop_order_request_payload,
    validate_wallet_balance_response,
)


class TestKabucomTestContractFixture(unittest.TestCase):
    def test_test_fixture_matches_validators_and_documents_password_policy(self):
        fixture = load_contract_fixture(TEST_CONTRACT_FIXTURE_PATH)
        self.assertIsInstance(fixture, dict)
        self.assertEqual(fixture["fixture_kind"], "KABUCOM_TEST")
        self.assertFalse(fixture["captured_from_kabucom_test"])
        self.assertEqual(fixture["captured_at"], "2026-06-12T00:00:00+09:00")
        self.assertEqual(fixture["redaction_policy"], "manual_sanitized_fixture_v1")
        self.assertIn("Password", fixture["sanitized_fields"])
        self.assertIn("Token", fixture["sanitized_fields"])
        self.assertIn("Actual KABUCOM_TEST capture is still pending", fixture["provenance_note"])
        self.assertEqual(fixture["password_policy"], "api_password_fallback_allowed")
        self.assertEqual(fixture["api_spec_version"], "1.5")
        self.assertEqual(fixture["api_spec_commit_sha"], "0119077f1647b7c3ff64460b862c1978142df43d")
        self.assertEqual(fixture["api_spec_acquired_at"], "2026-06-12")

        self.assertTrue(validate_test_contract_fixture(fixture).valid)
        self.assertTrue(validate_contract_fixture(fixture).valid)
        self.assertTrue(validate_market_order_request_payload(fixture["requests"]["market_order"]).valid)
        self.assertTrue(validate_stop_order_request_payload(fixture["requests"]["stop_order"]).valid)
        self.assertTrue(validate_cancel_order_request_payload(fixture["requests"]["cancel_order"]).valid)
        self.assertTrue(validate_wallet_balance_response(fixture["responses"]["wallet_cash"], required_key="StockAccountWallet").valid)
        self.assertTrue(validate_wallet_balance_response(fixture["responses"]["wallet_margin"], required_key="MarginAccountWallet").valid)
        self.assertTrue(validate_orders_list_response(fixture["responses"]["orders"]).valid)
        self.assertIsNotNone(hash_contract_fixture(TEST_CONTRACT_FIXTURE_PATH))
        manifest = build_contract_fixture_manifest()
        self.assertEqual(manifest.test_fixture_hash, hash_contract_fixture(TEST_CONTRACT_FIXTURE_PATH))
        self.assertEqual(manifest.password_policy, "api_password_fallback_allowed")

    def test_test_fixture_still_includes_password_fields_but_keeps_them_sanitized(self):
        fixture = load_contract_fixture(TEST_CONTRACT_FIXTURE_PATH)
        self.assertIsInstance(fixture, dict)
        self.assertEqual(fixture["requests"]["market_order"]["Password"], "<redacted>")
        self.assertEqual(fixture["requests"]["stop_order"]["Password"], "<redacted>")
        self.assertEqual(fixture["requests"]["cancel_order"]["Password"], "<redacted>")

    def test_test_fixture_rejects_missing_password_policy(self):
        fixture = load_contract_fixture(TEST_CONTRACT_FIXTURE_PATH)
        self.assertIsInstance(fixture, dict)
        mutated = dict(fixture)
        mutated.pop("password_policy", None)

        self.assertFalse(validate_test_contract_fixture(mutated).valid)

    def test_test_fixture_rejects_missing_provenance_metadata(self):
        fixture = load_contract_fixture(TEST_CONTRACT_FIXTURE_PATH)
        self.assertIsInstance(fixture, dict)
        mutated = dict(fixture)
        mutated.pop("captured_from_kabucom_test", None)

        self.assertFalse(validate_test_contract_fixture(mutated).valid)


if __name__ == "__main__":
    unittest.main()
