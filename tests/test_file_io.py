import json
import tempfile
from pathlib import Path
import unittest

import pandas as pd

from core.file_io import append_csv_rows, append_jsonl


class TestFileIO(unittest.TestCase):
    def test_append_jsonl_appends_records_line_by_line(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "audit.jsonl"

            append_jsonl(path, {"event": "first", "value": 1})
            append_jsonl(path, {"event": "second", "value": 2})

            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["event"], "first")
            self.assertEqual(json.loads(lines[1])["event"], "second")


class TestCsvAppendSchemaMigration(unittest.TestCase):
    def test_append_csv_rows_migrates_existing_header_before_adding_columns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "events.csv"

            append_csv_rows(path, [{"event": "first", "value": 1}])
            append_csv_rows(
                path,
                [{"event": "second", "value": 2, "decision_snapshot_id": "snapshot-1"}],
            )
            append_csv_rows(path, [{"event": "third"}])

            frame = pd.read_csv(path, encoding="utf-8-sig")
            self.assertEqual(
                list(frame.columns),
                ["event", "value", "decision_snapshot_id"],
            )
            self.assertEqual(frame["event"].tolist(), ["first", "second", "third"])
            self.assertEqual(frame.loc[1, "decision_snapshot_id"], "snapshot-1")
            self.assertTrue(pd.isna(frame.loc[0, "decision_snapshot_id"]))
            self.assertTrue(pd.isna(frame.loc[2, "value"]))
