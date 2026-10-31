"""Offline tests of the daily loader's no-duplicate and retry guards."""

from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from load_daily import batch_fingerprint, load
from generate_daily import HEADERS


class DailyLoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        for table in HEADERS:
            (self.directory / f"{table}.csv").write_text(",".join(HEADERS[table]) + "\n")
        self.manifest = {"date": "2026-11-01", "seed": 42, "version": 1, "orders": 100,
                         "files": {table: {"rows": 0, "sha256": "x"} for table in HEADERS}}
        self.client = Mock()
        self.client.get_dataset.return_value = SimpleNamespace(location="US")
        self.config = Mock(project="demo-project", location="US")
        self.config.client.return_value = self.client
        self.setup = patch("load_daily.setup").start()
        self.addCleanup(patch.stopall)
        self.validation = patch("load_daily.validate_batch", return_value=self.manifest).start()

    def test_completed_batch_skips_all_writes(self):
        self.config.query.side_effect = [
            [SimpleNamespace(status="complete")],
            [SimpleNamespace(fingerprint=batch_fingerprint(self.manifest), status="complete")],
        ]
        load(self.directory, self.directory, self.config)
        self.client.load_table_from_file.assert_not_called()
        self.assertEqual(self.config.query.call_count, 2)

    def test_changed_seed_or_version_cannot_replace_date(self):
        self.config.query.side_effect = [
            [SimpleNamespace(status="complete")],
            [SimpleNamespace(fingerprint="different", status="complete")],
        ]
        with self.assertRaises(ValueError):
            load(self.directory, self.directory, self.config)
        self.client.load_table_from_file.assert_not_called()

    def test_historical_bootstrap_must_be_complete(self):
        self.config.query.return_value = [SimpleNamespace(status="loading")]
        with self.assertRaises(ValueError):
            load(self.directory, self.directory, self.config)
        self.setup.assert_not_called()

    def test_partial_retry_never_marks_complete_on_failure(self):
        self.config.query.side_effect = [
            [SimpleNamespace(status="complete")],
            [SimpleNamespace(fingerprint=batch_fingerprint(self.manifest), status="loading")],
            [],
        ]
        self.client.load_table_from_file.return_value.result.side_effect = RuntimeError("load failed")
        with self.assertRaises(RuntimeError):
            load(self.directory, self.directory, self.config)
        self.assertEqual(self.config.query.call_count, 3)  # read, read, DELETE only
        self.client.delete_table.assert_called_once()

    def test_partial_retry_replaces_only_its_date_then_completes(self):
        def query(client, sql, params=()):
            if "historical_bootstrap" in sql:
                return [SimpleNamespace(status="complete")]
            if sql.startswith("SELECT fingerprint"):
                return [SimpleNamespace(fingerprint=batch_fingerprint(self.manifest), status="loading")]
            if sql.startswith("SELECT COUNT"):
                return [SimpleNamespace(rows=0)]
            self.assertIn("@day", sql)
            return []

        self.config.query.side_effect = query
        load(self.directory, self.directory, self.config)
        statements = [call.args[1] for call in self.config.query.call_args_list]
        self.assertEqual(sum(sql.startswith("DELETE") for sql in statements), 7)
        self.assertEqual(sum(sql.startswith("INSERT INTO") for sql in statements), 7)
        self.assertEqual(sum(sql.startswith("UPDATE") for sql in statements), 1)
        self.assertEqual(self.client.load_table_from_file.call_count, 7)
        self.assertEqual(self.client.delete_table.call_count, 7)


if __name__ == "__main__":
    unittest.main()
