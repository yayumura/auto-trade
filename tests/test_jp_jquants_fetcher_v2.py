import os
import pickle
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

import jp_jquants_fetcher_v2 as fetcher


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


class _Always429Client:
    def get_list(self):
        raise RuntimeError("too many 429 error responses")


class TestJpJquantsFetcherV2(unittest.TestCase):
    def test_extract_subscription_floor_date_from_text_parses_api_message(self):
        text = (
            '{"message": "Your subscription covers the following dates: 2021-05-16 ~ . '
            'If you want more data, please check other plans:https://jpx-jquants.com/#dataset"}'
        )

        floor_date = fetcher._extract_subscription_floor_date_from_text(text)

        self.assertEqual(floor_date, "2021-05-16")

    def test_resolve_refresh_start_date_uses_cached_latest_day_with_overlap(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "jp_mega_cache.pkl")
            cached = pd.DataFrame(
                {"Close": [100.0, 101.0]},
                index=pd.to_datetime(["2026-05-14", "2026-05-15"]),
            )
            with open(output_path, "wb") as handle:
                pickle.dump(cached, handle)

            start_date = fetcher.resolve_refresh_start_date(
                output_path=output_path,
                refresh_overlap_days=7,
            )

        self.assertEqual(start_date, "20260508")

    def test_resolve_incremental_target_tickers_prefers_cached_universe_plus_missing_codes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "jp_mega_cache.pkl")
            cached = pd.DataFrame(
                [[100.0, 200.0], [101.0, 201.0]],
                index=pd.to_datetime(["2026-05-14", "2026-05-15"]),
                columns=pd.MultiIndex.from_tuples(
                    [
                        ("1301.T", "Close"),
                        ("7203.T", "Close"),
                    ]
                ),
            )
            with open(output_path, "wb") as handle:
                pickle.dump(cached, handle)

            target_tickers = fetcher.resolve_incremental_target_tickers(
                output_path=output_path,
                ticker_codes=["13010", "72030", "67580"],
                checkpointed_tickers={"1301", "7203"},
            )

        self.assertEqual(target_tickers, ["1301", "6758", "7203"])

    def test_resolve_incremental_target_tickers_normalizes_legacy_five_digit_checkpoint_names(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "jp_mega_cache.pkl")
            cached = pd.DataFrame(
                [[100.0, 200.0], [101.0, 201.0]],
                index=pd.to_datetime(["2026-05-14", "2026-05-15"]),
                columns=pd.MultiIndex.from_tuples(
                    [
                        ("1301.T", "Close"),
                        ("7203.T", "Close"),
                    ]
                ),
            )
            with open(output_path, "wb") as handle:
                pickle.dump(cached, handle)

            target_tickers = fetcher.resolve_incremental_target_tickers(
                output_path=output_path,
                ticker_codes=["1301", "7203", "6758"],
                checkpointed_tickers={"13010", "72030"},
            )

        self.assertEqual(target_tickers, ["1301", "6758", "7203"])

    def test_fetch_ticker_turbo_merges_overlapping_rows_into_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            existing = pd.DataFrame(
                [
                    {"Date": "2026-05-14", "Code": "72030", "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.5, "Volume": 1000},
                    {"Date": "2026-05-15", "Code": "72030", "Open": 101.0, "High": 102.0, "Low": 100.0, "Close": 101.5, "Volume": 1100},
                ]
            )
            existing.to_pickle(os.path.join(temp_dir, "7203.pkl"))

            payload = {
                "data": [
                    {"Date": "2026-05-15", "Code": "72030", "AdjO": 201.0, "AdjH": 202.0, "AdjL": 200.0, "AdjC": 201.5, "AdjVo": 2100},
                    {"Date": "2026-05-16", "Code": "72030", "AdjO": 202.0, "AdjH": 203.0, "AdjL": 201.0, "AdjC": 202.5, "AdjVo": 2200},
                ]
            }

            with patch.object(fetcher, "CHECKPOINT_DIR", temp_dir), patch.object(
                fetcher,
                "_ensure_jquants_no_proxy",
            ) as ensure_no_proxy, patch.object(
                fetcher.requests,
                "get",
                return_value=_FakeResponse(200, payload),
            ):
                result = fetcher.fetch_ticker_turbo("7203", "dummy-token", "20260515", "20260516")

            ensure_no_proxy.assert_called_once()
            self.assertEqual(result, "SUCCESS:7203")
            merged = pd.read_pickle(os.path.join(temp_dir, "7203.pkl")).sort_values("Date").reset_index(drop=True)
            self.assertEqual(list(pd.to_datetime(merged["Date"]).dt.strftime("%Y-%m-%d")), ["2026-05-14", "2026-05-15", "2026-05-16"])
            self.assertEqual(float(merged.loc[1, "Open"]), 201.0)
            self.assertEqual(float(merged.loc[2, "Close"]), 202.5)

    def test_fetch_daily_quotes_for_date_uses_bulk_date_query(self):
        payload = {
            "data": [
                {
                    "Date": "2026-07-10",
                    "Code": "72030",
                    "AdjO": 201.0,
                    "AdjH": 202.0,
                    "AdjL": 200.0,
                    "AdjC": 201.5,
                    "AdjVo": 2100,
                },
                {
                    "Date": "2026-07-10",
                    "Code": "13010",
                    "AdjO": 101.0,
                    "AdjH": 102.0,
                    "AdjL": 100.0,
                    "AdjC": 101.5,
                    "AdjVo": 1100,
                },
            ]
        }
        with patch.object(fetcher, "_ensure_jquants_no_proxy"), patch.object(
            fetcher.requests,
            "get",
            return_value=_FakeResponse(200, payload),
        ) as get_mock:
            frame = fetcher.fetch_daily_quotes_for_date("dummy-token", "20260710")

        self.assertEqual(len(frame), 2)
        self.assertEqual(list(frame["Open"]), [201.0, 101.0])
        self.assertIn("date=20260710", get_mock.call_args.args[0])

    def test_refresh_incremental_checkpoints_by_date_merges_each_ticker_once(self):
        def _daily_frame(_api_key, target_date):
            date_text = pd.Timestamp(target_date).strftime("%Y-%m-%d")
            return pd.DataFrame(
                [
                    {
                        "Date": date_text,
                        "Code": "72030",
                        "Open": 200.0,
                        "High": 201.0,
                        "Low": 199.0,
                        "Close": 200.5,
                        "Volume": 2000,
                    },
                    {
                        "Date": date_text,
                        "Code": "99990",
                        "Open": 900.0,
                        "High": 901.0,
                        "Low": 899.0,
                        "Close": 900.5,
                        "Volume": 9000,
                    },
                ]
            )

        saved = {}

        def _save(ticker_code, frame):
            saved[ticker_code] = frame.copy()

        with patch.object(
            fetcher,
            "fetch_daily_quotes_for_date",
            side_effect=_daily_frame,
        ) as fetch_mock, patch.object(
            fetcher,
            "_save_checkpoint_frame",
            side_effect=_save,
        ):
            summary = fetcher.refresh_incremental_checkpoints_by_date(
                api_key="dummy-token",
                start_date="20260514",
                end_date="20260517",
                target_tickers=["7203"],
            )

        self.assertEqual(fetch_mock.call_count, 2)
        self.assertEqual(summary, {"requested_dates": 2, "rows": 2, "tickers": 1})
        self.assertEqual(list(saved), ["7203"])
        self.assertEqual(len(saved["7203"]), 2)

    def test_save_checkpoint_frame_keeps_existing_history_when_candidate_is_shorter(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            existing = pd.DataFrame(
                [
                    {"Date": "2026-05-14", "Code": "72030", "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.5, "Volume": 1000},
                    {"Date": "2026-05-15", "Code": "72030", "Open": 101.0, "High": 102.0, "Low": 100.0, "Close": 101.5, "Volume": 1100},
                ]
            )
            existing.to_pickle(os.path.join(temp_dir, "7203.pkl"))
            shorter = pd.DataFrame(
                [
                    {"Date": "2026-05-15", "Code": "72030", "Open": 301.0, "High": 302.0, "Low": 300.0, "Close": 301.5, "Volume": 3100},
                ]
            )

            with patch.object(fetcher, "CHECKPOINT_DIR", temp_dir):
                fetcher._save_checkpoint_frame("7203", shorter)

            saved = pd.read_pickle(os.path.join(temp_dir, "7203.pkl")).sort_values("Date").reset_index(drop=True)

        self.assertEqual(list(pd.to_datetime(saved["Date"]).dt.strftime("%Y-%m-%d")), ["2026-05-14", "2026-05-15"])
        self.assertEqual(float(saved.loc[1, "Close"]), 301.5)

    def test_fetch_ticker_turbo_returns_failure_detail_for_non_200_response(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(fetcher, "CHECKPOINT_DIR", temp_dir), patch.object(
                fetcher.requests,
                "get",
                return_value=_FakeResponse(400, {"message": "bad request"}),
            ):
                result = fetcher.fetch_ticker_turbo("7203", "dummy-token", "20210405", "20260516")

        self.assertIn("FAIL:7203:status=400", result)

    def test_fetch_ticker_turbo_returns_range_error_when_subscription_floor_is_hit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            message = {
                "message": "Your subscription covers the following dates: 2021-05-16 ~ . "
                "If you want more data, please check other plans:https://jpx-jquants.com/#dataset"
            }
            with patch.object(fetcher, "CHECKPOINT_DIR", temp_dir), patch.object(
                fetcher.requests,
                "get",
                return_value=_FakeResponse(400, message),
            ):
                result = fetcher.fetch_ticker_turbo("7203", "dummy-token", "20210405", "20260516")

        self.assertEqual(result, "RANGE_ERROR:7203:min_date=2021-05-16")

    def test_seed_missing_checkpoints_from_output_cache_restores_history_when_checkpoint_dir_is_empty(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "jp_mega_cache.pkl")
            cached = pd.DataFrame(
                [[100.0, 101.0, 99.0, 100.5, 1000], [101.0, 102.0, 100.0, 101.5, 1100]],
                index=pd.to_datetime(["2026-05-14", "2026-05-15"]),
                columns=pd.MultiIndex.from_tuples(
                    [
                        ("7203.T", "Open"),
                        ("7203.T", "High"),
                        ("7203.T", "Low"),
                        ("7203.T", "Close"),
                        ("7203.T", "Volume"),
                    ]
                ),
            )
            with open(output_path, "wb") as handle:
                pickle.dump(cached, handle)

            with patch.object(fetcher, "CHECKPOINT_DIR", temp_dir):
                seeded = fetcher.seed_missing_checkpoints_from_output_cache(output_path, ["72030"])

            self.assertEqual(seeded, 1)
            restored = pd.read_pickle(os.path.join(temp_dir, "7203.pkl")).sort_values("Date").reset_index(drop=True)
            self.assertEqual(list(pd.to_datetime(restored["Date"]).dt.strftime("%Y-%m-%d")), ["2026-05-14", "2026-05-15"])
            self.assertEqual(float(restored.loc[0, "Open"]), 100.0)
            self.assertEqual(float(restored.loc[1, "Close"]), 101.5)

    def test_seed_missing_checkpoints_from_output_cache_repairs_short_checkpoint_when_cache_has_longer_history(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "jp_mega_cache.pkl")
            dates = pd.date_range("2026-01-02", periods=120, freq="B")
            cached = pd.DataFrame(
                {
                    ("7203.T", "Open"): [100.0 + i for i in range(len(dates))],
                    ("7203.T", "High"): [101.0 + i for i in range(len(dates))],
                    ("7203.T", "Low"): [99.0 + i for i in range(len(dates))],
                    ("7203.T", "Close"): [100.5 + i for i in range(len(dates))],
                    ("7203.T", "Volume"): [1000 + i for i in range(len(dates))],
                },
                index=dates,
            )
            with open(output_path, "wb") as handle:
                pickle.dump(cached, handle)
            short = pd.DataFrame(
                [
                    {"Date": "2026-06-01", "Code": "72030", "Open": 201.0, "High": 202.0, "Low": 200.0, "Close": 201.5, "Volume": 2100},
                    {"Date": "2026-06-02", "Code": "72030", "Open": 202.0, "High": 203.0, "Low": 201.0, "Close": 202.5, "Volume": 2200},
                ]
            )
            short.to_pickle(os.path.join(temp_dir, "7203.pkl"))

            with patch.object(fetcher, "CHECKPOINT_DIR", temp_dir):
                seeded = fetcher.seed_missing_checkpoints_from_output_cache(output_path, ["72030"])

            self.assertEqual(seeded, 1)
            restored = pd.read_pickle(os.path.join(temp_dir, "7203.pkl")).sort_values("Date").reset_index(drop=True)
            self.assertEqual(len(restored), len(cached))
            expected_dates = list(pd.to_datetime(cached.index).strftime("%Y-%m-%d"))
            restored_dates = list(pd.to_datetime(restored["Date"]).dt.strftime("%Y-%m-%d"))
            self.assertEqual(restored_dates[:2], expected_dates[:2])
            self.assertEqual(restored_dates[-2:], expected_dates[-2:])
            self.assertEqual(float(restored.loc[0, "Open"]), 100.0)
            self.assertEqual(float(restored.loc[len(restored) - 1, "Close"]), 100.5 + len(cached) - 1)

    def test_full_snapshot_can_be_restored_back_to_live_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            checkpoint_dir = os.path.join(temp_dir, "checkpoints")
            os.makedirs(checkpoint_dir, exist_ok=True)
            output_path = os.path.join(temp_dir, "jp_mega_cache.pkl")
            original_checkpoint = pd.DataFrame(
                [
                    {"Date": "2026-05-14", "Code": "72030", "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.5, "Volume": 1000},
                    {"Date": "2026-05-15", "Code": "72030", "Open": 101.0, "High": 102.0, "Low": 100.0, "Close": 101.5, "Volume": 1100},
                ]
            )
            original_output = pd.DataFrame(
                [[100.0, 101.0, 99.0, 100.5, 1000], [101.0, 102.0, 100.0, 101.5, 1100]],
                index=pd.to_datetime(["2026-05-14", "2026-05-15"]),
                columns=pd.MultiIndex.from_tuples(
                    [
                        ("7203.T", "Open"),
                        ("7203.T", "High"),
                        ("7203.T", "Low"),
                        ("7203.T", "Close"),
                        ("7203.T", "Volume"),
                    ]
                ),
            )
            original_checkpoint.to_pickle(os.path.join(checkpoint_dir, "7203.pkl"))
            with open(output_path, "wb") as handle:
                pickle.dump(original_output, handle)

            mutated_checkpoint = pd.DataFrame(
                [{"Date": "2026-05-15", "Code": "72030", "Open": 301.0, "High": 302.0, "Low": 300.0, "Close": 301.5, "Volume": 3100}]
            )
            mutated_output = pd.DataFrame(
                [[301.0, 302.0, 300.0, 301.5, 3100]],
                index=pd.to_datetime(["2026-05-15"]),
                columns=pd.MultiIndex.from_tuples(
                    [
                        ("7203.T", "Open"),
                        ("7203.T", "High"),
                        ("7203.T", "Low"),
                        ("7203.T", "Close"),
                        ("7203.T", "Volume"),
                    ]
                ),
            )

            with patch.object(fetcher, "CHECKPOINT_DIR", checkpoint_dir):
                snapshot_root = fetcher._snapshot_current_cache_state(output_path=output_path, snapshot_tag="snap1")
                self.assertTrue(os.path.exists(os.path.join(snapshot_root, "manifest.json")))

                mutated_checkpoint.to_pickle(os.path.join(checkpoint_dir, "7203.pkl"))
                with open(output_path, "wb") as handle:
                    pickle.dump(mutated_output, handle)

                restored = fetcher._restore_snapshot("snap1", output_path=output_path)

            self.assertEqual(restored["snapshot_tag"], "snap1")
            restored_checkpoint = pd.read_pickle(os.path.join(checkpoint_dir, "7203.pkl")).sort_values("Date").reset_index(drop=True)
            restored_output = pd.read_pickle(output_path)
            self.assertEqual(list(pd.to_datetime(restored_checkpoint["Date"]).dt.strftime("%Y-%m-%d")), ["2026-05-14", "2026-05-15"])
            self.assertEqual(float(restored_checkpoint.loc[1, "Close"]), 101.5)
            self.assertEqual(list(restored_output.index.strftime("%Y-%m-%d")), ["2026-05-14", "2026-05-15"])
            self.assertEqual(float(restored_output.loc[pd.Timestamp("2026-05-15"), ("7203.T", "Close")]), 101.5)

    def test_refresh_runs_preflight_audit_before_ticker_master(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            checkpoint_dir = os.path.join(temp_dir, "checkpoints")
            os.makedirs(checkpoint_dir, exist_ok=True)
            output_path = os.path.join(temp_dir, "jp_mega_cache.pkl")

            checkpoint = pd.DataFrame(
                [
                    {"Date": "2026-05-14", "Code": "72030", "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.5, "Volume": 1000},
                    {"Date": "2026-05-15", "Code": "72030", "Open": 101.0, "High": 102.0, "Low": 100.0, "Close": 101.5, "Volume": 1100},
                ]
            )
            checkpoint.to_pickle(os.path.join(checkpoint_dir, "7203.pkl"))

            output = pd.DataFrame(
                [[100.0, 101.0, 99.0, 100.5, 1000], [101.0, 102.0, 100.0, 101.5, 1100]],
                index=pd.to_datetime(["2026-05-14", "2026-05-15"]),
                columns=pd.MultiIndex.from_tuples(
                    [
                        ("7203.T", "Open"),
                        ("7203.T", "High"),
                        ("7203.T", "Low"),
                        ("7203.T", "Close"),
                        ("7203.T", "Volume"),
                    ]
                ),
            )
            with open(output_path, "wb") as handle:
                pickle.dump(output, handle)

            call_order = []

            def _audit_stub(**_kwargs):
                call_order.append("audit")
                return {"missing": 0, "truncated": 0, "aligned": 1, "repaired": 0}

            def _master_stub(**_kwargs):
                call_order.append("master")
                return ["7203"], False

            with patch.object(fetcher, "CHECKPOINT_DIR", checkpoint_dir), patch.object(
                fetcher,
                "_run_cache_audit_only",
                side_effect=_audit_stub,
            ), patch.object(
                fetcher,
                "fetch_ticker_master_with_fallback",
                side_effect=_master_stub,
            ), patch.object(
                fetcher.os,
                "getenv",
                side_effect=lambda key: "dummy-token" if key in {"JQUANTS_REFRESH_TOKEN", "JQUANTS_API_KEY"} else None,
            ):
                fetcher.fetch_jquants_v2_turbo_revelation(output_path=output_path, debug_failure_samples=0)

            self.assertEqual(call_order, ["audit", "master"])

    def test_fetch_ticker_master_with_fallback_uses_cached_universe_after_rate_limit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "jp_mega_cache.pkl")
            cached = pd.DataFrame(
                [[100.0, 200.0], [101.0, 201.0]],
                index=pd.to_datetime(["2026-05-14", "2026-05-15"]),
                columns=pd.MultiIndex.from_tuples(
                    [
                        ("1301.T", "Close"),
                        ("7203.T", "Close"),
                    ]
                ),
            )
            with open(output_path, "wb") as handle:
                pickle.dump(cached, handle)

            with patch.object(fetcher, "_ensure_jquants_no_proxy") as ensure_no_proxy, patch.object(
                fetcher.jquantsapi, "ClientV2", return_value=_Always429Client()), patch.object(
                fetcher.time,
                "sleep",
                return_value=None,
            ):
                ticker_codes, used_fallback = fetcher.fetch_ticker_master_with_fallback(
                    output_path=output_path,
                    checkpointed_tickers={"67580"},
                    api_key="dummy-token",
                    max_retries=2,
                )

        ensure_no_proxy.assert_called_once()
        self.assertTrue(used_fallback)
        self.assertEqual(ticker_codes, ["1301", "6758", "7203"])

    def test_fetch_jquants_v2_turbo_revelation_refreshes_cached_universe_when_master_falls_back(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            checkpoint_dir = os.path.join(temp_dir, "checkpoints")
            os.makedirs(checkpoint_dir, exist_ok=True)
            output_path = os.path.join(temp_dir, "jp_mega_cache.pkl")
            cached = pd.DataFrame(
                {
                    ("1301.T", "Open"): [100.0, 101.0],
                    ("1301.T", "High"): [101.0, 102.0],
                    ("1301.T", "Low"): [99.0, 100.0],
                    ("1301.T", "Close"): [100.5, 101.5],
                    ("1301.T", "Volume"): [1000, 1100],
                    ("7203.T", "Open"): [200.0, 201.0],
                    ("7203.T", "High"): [201.0, 202.0],
                    ("7203.T", "Low"): [199.0, 200.0],
                    ("7203.T", "Close"): [200.5, 201.5],
                    ("7203.T", "Volume"): [2000, 2100],
                },
                index=pd.to_datetime(["2026-05-14", "2026-05-15"]),
            )
            with open(output_path, "wb") as handle:
                pickle.dump(cached, handle)

            for ticker_code, base_price in [("1301", 100.0), ("7203", 200.0)]:
                frame = pd.DataFrame(
                    [
                        {
                            "Date": "2026-05-14",
                            "Code": ticker_code,
                            "Open": base_price,
                            "High": base_price + 1.0,
                            "Low": base_price - 1.0,
                            "Close": base_price + 0.5,
                            "Volume": 1000,
                        },
                        {
                            "Date": "2026-05-15",
                            "Code": ticker_code,
                            "Open": base_price + 1.0,
                            "High": base_price + 2.0,
                            "Low": base_price,
                            "Close": base_price + 1.5,
                            "Volume": 1100,
                        },
                    ]
                )
                frame.to_pickle(os.path.join(checkpoint_dir, f"{ticker_code}.pkl"))

            fetched_codes = []

            def _fetch_stub(ticker_code, api_key, from_date, to_date):
                fetched_codes.append(ticker_code)
                return f"SUCCESS:{ticker_code}"

            with patch.object(fetcher, "CHECKPOINT_DIR", checkpoint_dir), patch.object(
                fetcher,
                "fetch_ticker_master_with_fallback",
                return_value=(["1301", "7203"], True),
            ), patch.object(
                fetcher,
                "fetch_ticker_turbo",
                side_effect=_fetch_stub,
            ), patch.object(
                fetcher.os,
                "getenv",
                side_effect=lambda key: "dummy-token" if key in {"JQUANTS_REFRESH_TOKEN", "JQUANTS_API_KEY"} else None,
            ), patch.object(
                fetcher.time,
                "sleep",
                return_value=None,
            ):
                fetcher.fetch_jquants_v2_turbo_revelation(output_path=output_path, debug_failure_samples=0)

        self.assertEqual(sorted(fetched_codes), ["1301", "7203"])

    def test_load_existing_checkpoint_merges_legacy_and_normalized_names(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            normalized = pd.DataFrame(
                [{"Date": "2026-05-15", "Code": "7203", "Open": 101.0, "High": 102.0, "Low": 100.0, "Close": 101.5, "Volume": 1100}]
            )
            legacy = pd.DataFrame(
                [{"Date": "2026-05-14", "Code": "72030", "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.5, "Volume": 1000}]
            )
            normalized.to_pickle(os.path.join(temp_dir, "7203.pkl"))
            legacy.to_pickle(os.path.join(temp_dir, "72030.pkl"))

            with patch.object(fetcher, "CHECKPOINT_DIR", temp_dir):
                merged = fetcher._load_existing_checkpoint("7203")

            self.assertEqual(list(pd.to_datetime(merged["Date"]).dt.strftime("%Y-%m-%d")), ["2026-05-14", "2026-05-15"])

    def test_resolve_full_refresh_target_tickers_skips_already_backfilled_checkpoints(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            complete = pd.DataFrame(
                [
                    {"Date": "2021-04-05", "Code": "1301", "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.5, "Volume": 1000},
                    {"Date": "2026-05-15", "Code": "1301", "Open": 200.0, "High": 201.0, "Low": 199.0, "Close": 200.5, "Volume": 2000},
                ]
            )
            incomplete = pd.DataFrame(
                [
                    {"Date": "2026-03-27", "Code": "7203", "Open": 101.0, "High": 102.0, "Low": 100.0, "Close": 101.5, "Volume": 1100},
                    {"Date": "2026-05-15", "Code": "7203", "Open": 201.0, "High": 202.0, "Low": 200.0, "Close": 201.5, "Volume": 2100},
                ]
            )
            complete.to_pickle(os.path.join(temp_dir, "1301.pkl"))
            incomplete.to_pickle(os.path.join(temp_dir, "7203.pkl"))

            with patch.object(fetcher, "CHECKPOINT_DIR", temp_dir):
                target_tickers = fetcher.resolve_full_refresh_target_tickers(
                    ticker_codes=["1301", "7203", "6758"],
                    start_date="20210405",
                )

        self.assertEqual(target_tickers, ["6758", "7203"])


if __name__ == "__main__":
    unittest.main()
