"""Offline tests: no Google credentials or network requests are needed."""

import csv
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from google.api_core.exceptions import NotFound

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from load_historical import SCHEMAS, load, manifest, schema_for


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        for table in SCHEMAS:
            with (self.directory / f"{table}.csv").open("w", newline="") as file:
                csv.writer(file).writerow([field.name for field in schema_for(table)])
        self.client = Mock()
        self.client.get_dataset.return_value = SimpleNamespace(location="US")
        self.client.list_tables.return_value = []
        self.config = Mock(project="demo-project", location="US")
        self.config.client.return_value = self.client

    def fingerprint(self):
        import hashlib
        import json
        return hashlib.sha256(json.dumps(manifest(self.directory), sort_keys=True).encode()).hexdigest()

    def test_manifest_rejects_unknown_files(self):
        (self.directory / "extra.csv").write_text("id\n1\n")
        with self.assertRaises(ValueError):
            manifest(self.directory)

    def test_manifest_rejects_bad_header(self):
        (self.directory / "channel.csv").write_text("wrong\n")
        with self.assertRaises(ValueError):
            manifest(self.directory)

    def test_manifest_is_reproducible(self):
        self.assertEqual(self.fingerprint(), self.fingerprint())

    def test_completed_bootstrap_is_not_written_again(self):
        self.config.query.return_value = [SimpleNamespace(fingerprint=self.fingerprint(), status="complete")]
        load(self.directory, self.config)
        self.client.load_table_from_file.assert_not_called()
        self.assertEqual(self.config.query.call_count, 1)

    def test_different_data_fails_closed(self):
        self.config.query.return_value = [SimpleNamespace(fingerprint="different", status="complete")]
        with self.assertRaises(ValueError):
            load(self.directory, self.config)
        self.client.load_table_from_file.assert_not_called()

    def test_existing_raw_without_marker_is_protected(self):
        self.client.get_table.side_effect = NotFound("no marker")
        self.client.list_tables.return_value = ["sales_order"]
        with self.assertRaises(ValueError):
            load(self.directory, self.config)
        self.client.load_table_from_file.assert_not_called()

    def test_missing_marker_row_with_existing_raw_is_protected(self):
        self.config.query.return_value = []
        self.client.list_tables.return_value = ["sales_order"]
        with self.assertRaises(ValueError):
            load(self.directory, self.config)
        self.client.load_table_from_file.assert_not_called()

    def test_partial_bootstrap_can_retry(self):
        self.config.query.return_value = [SimpleNamespace(fingerprint=self.fingerprint(), status="loading")]
        self.client.get_table.return_value = SimpleNamespace(num_rows=0)
        load(self.directory, self.config)
        self.assertEqual(self.client.load_table_from_file.call_count, 13)
        self.assertIn("UPDATE", self.config.query.call_args.args[1])

    def test_first_load_creates_marker_and_completes(self):
        self.client.get_table.side_effect = [NotFound("no marker")] + [SimpleNamespace(num_rows=0)] * 13
        self.config.query.return_value = []
        load(self.directory, self.config)
        self.client.create_table.assert_called_once()
        self.assertEqual(self.client.load_table_from_file.call_count, 13)
        statements = [call.args[1] for call in self.config.query.call_args_list]
        self.assertTrue(statements[0].startswith("SELECT"))
        self.assertTrue(statements[1].startswith("INSERT"))
        self.assertTrue(statements[2].startswith("UPDATE"))

    def test_unexpected_status_is_protected(self):
        self.config.query.return_value = [SimpleNamespace(fingerprint=self.fingerprint(), status="unknown")]
        with self.assertRaises(ValueError):
            load(self.directory, self.config)
        self.client.load_table_from_file.assert_not_called()

    def test_duplicate_markers_are_protected(self):
        marker = SimpleNamespace(fingerprint=self.fingerprint(), status="complete")
        self.config.query.return_value = [marker, marker]
        with self.assertRaises(ValueError):
            load(self.directory, self.config)
        self.client.load_table_from_file.assert_not_called()

    def test_load_failure_does_not_mark_complete(self):
        self.config.query.return_value = [SimpleNamespace(fingerprint=self.fingerprint(), status="loading")]
        self.client.load_table_from_file.return_value.result.side_effect = RuntimeError("load failed")
        with self.assertRaises(RuntimeError):
            load(self.directory, self.config)
        self.assertEqual(self.config.query.call_count, 1)

    def test_count_mismatch_does_not_mark_complete(self):
        self.config.query.return_value = [SimpleNamespace(fingerprint=self.fingerprint(), status="loading")]
        self.client.get_table.return_value = SimpleNamespace(num_rows=9)
        with self.assertRaises(ValueError):
            load(self.directory, self.config)
        self.assertEqual(self.config.query.call_count, 1)

    def test_wrong_location_fails_before_loading(self):
        self.client.get_dataset.return_value = SimpleNamespace(location="EU")
        with self.assertRaises(ValueError):
            load(self.directory, self.config)
        self.client.load_table_from_file.assert_not_called()


if __name__ == "__main__":
    unittest.main()
