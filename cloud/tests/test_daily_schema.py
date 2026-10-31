"""Do not reinterpret already-loaded daily batches with a new ID namespace."""

import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from google.cloud import bigquery

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from setup_daily import setup


class DailySchemaTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.config = Mock(project="demo-project")
        self.config.client.return_value = self.client
        marker_schema = [
            bigquery.SchemaField("batch_id", "STRING"), bigquery.SchemaField("fingerprint", "STRING"),
            bigquery.SchemaField("manifest", "STRING"), bigquery.SchemaField("status", "STRING"),
            bigquery.SchemaField("completed_at", "TIMESTAMP"),
        ]
        self.client.get_table.return_value = SimpleNamespace(schema=marker_schema)

    def test_prior_generator_version_fails_before_any_table_write(self):
        self.config.query.return_value = [SimpleNamespace(
            batch_id="2025-10-01", manifest=json.dumps({"version": 1})
        )]
        with self.assertRaisesRegex(ValueError, "migrate it explicitly"):
            setup(self.config)
        self.client.create_table.assert_not_called()

    def test_invalid_manifest_fails_closed(self):
        self.config.query.return_value = [SimpleNamespace(batch_id="2025-10-01", manifest="invalid")]
        with self.assertRaisesRegex(ValueError, "Invalid manifest"):
            setup(self.config)
        self.client.create_table.assert_not_called()


if __name__ == "__main__":
    unittest.main()
