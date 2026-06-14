import json
import tempfile
from pathlib import Path
import unittest

from core.file_io import append_jsonl


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
