"""Publication guards and workflow ordering; no Google credentials or writes."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from google.cloud import bigquery
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from publish_looker import SOURCES, STATUS_SCHEMA, PUBLICATION_FIELDS, check_build, publication_sql, publish


class PublishLookerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "run_results.json"
        self.now = datetime.now(timezone.utc)
        self.artifact = {
            "metadata": {"generated_at": self.now.isoformat()},
            "results": [
                *({"unique_id": f"model.ecobottle.{name}", "status": "success"} for name in SOURCES),
                {"unique_id": "test.ecobottle.looker_contracts", "status": "pass"},
            ],
        }
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.artifact))

    def config(self):
        config = Mock(project="demo-project", location="US")
        client = config.client.return_value
        client.get_dataset.return_value = SimpleNamespace(location="US")
        client.list_tables.return_value = []
        client.get_table.side_effect = lambda name: SimpleNamespace(schema=[
            bigquery.SchemaField(field, "DATE" if field == "fecha" else "STRING")
            for field in SOURCES[name.rsplit(".", 1)[1]]
        ])
        return config

    def test_only_fresh_successful_complete_builds_are_accepted(self):
        check_build(self.path, self.now)
        for status in ("error", "fail", "skipped", "warn"):
            self.artifact["results"][0]["status"] = status
            self.save()
            with self.assertRaises(ValueError):
                check_build(self.path, self.now)
        self.artifact["results"][0]["status"] = "success"
        self.artifact["results"].pop()
        self.save()
        with self.assertRaises(ValueError):
            check_build(self.path, self.now)

    def test_stale_and_future_results_fail_before_cloud_access(self):
        for delta in (timedelta(hours=-3), timedelta(hours=1)):
            self.artifact["metadata"]["generated_at"] = (self.now + delta).isoformat()
            self.save()
            config = self.config()
            with self.assertRaises(ValueError):
                publish(config, self.path)
            config.client.assert_not_called()

    def test_single_transaction_includes_guard_all_sources_and_metadata(self):
        sql = publication_sql("demo-project")
        self.assertEqual(sql.count("BEGIN TRANSACTION;"), 1)
        self.assertEqual(sql.count("COMMIT TRANSACTION;"), 1)
        self.assertLess(sql.index("ASSERT NOT EXISTS"), sql.index("DELETE FROM"))
        self.assertIn("v.fingerprint = b.fingerprint", sql)
        self.assertIn("v.validated_at IS NOT NULL", sql)
        for name in SOURCES:
            self.assertIn(f"INSERT INTO `demo-project.ecobottle_looker.{name}`", sql)
        self.assertEqual(sql.count("INSERT INTO `demo-project.ecobottle_looker.actualizacion`"), 4)

    def test_provision_then_submit_one_atomic_publication(self):
        config = self.config()
        publish(config, self.path)
        self.assertEqual(config.client.return_value.create_table.call_count, 5)
        config.query.assert_called_once()
        self.assertEqual(config.query.call_args.args[2][0].name, "publication_id")

    def test_location_and_candidate_schema_drift_never_publish(self):
        config = self.config()
        config.client.return_value.get_dataset.return_value.location = "EU"
        with self.assertRaises(ValueError):
            publish(config, self.path)
        config.query.assert_not_called()
        config.client.return_value.create_table.assert_not_called()
        config = self.config()
        config.client.return_value.get_table.side_effect = None
        config.client.return_value.get_table.return_value.schema = []
        with self.assertRaises(ValueError):
            publish(config, self.path)
        config.query.assert_not_called()

    def test_existing_tables_are_not_recreated_or_truncated_outside_transaction(self):
        config = self.config()
        client = config.client.return_value
        schemas = {
            name: [bigquery.SchemaField(field, "DATE" if field == "fecha" else "STRING") for field in fields]
            for name, fields in SOURCES.items()
        }
        client.list_tables.return_value = [SimpleNamespace(table_id=name) for name in (*SOURCES, "actualizacion")]
        def table(name):
            dataset, name = name.split(".")[-2:]
            schema = STATUS_SCHEMA if name == "actualizacion" else schemas[name]
            if dataset == "ecobottle_looker" and name != "actualizacion":
                schema = [*schema, *PUBLICATION_FIELDS]
            return SimpleNamespace(schema=schema, table_type="TABLE")
        client.get_table.side_effect = table
        publish(config, self.path)
        client.create_table.assert_not_called()
        self.assertEqual(config.query.call_count, 1)

    def test_workflow_opt_in_after_reconciliation_and_source_preservation(self):
        path = Path(__file__).resolve().parents[2] / ".github/workflows/bigquery.yml"
        steps = yaml.safe_load(path.read_text())["jobs"]["historical"]["steps"]
        names = [step["name"] for step in steps]
        index = names.index("Publish validated sources for Looker Studio")
        self.assertGreater(index, names.index("Rebuild and reconcile after daily load"))
        self.assertGreater(index, names.index("Verify source preservation"))
        self.assertIn("success()", steps[index]["if"])
        self.assertIn("LOOKER_PUBLISH_ENABLED == 'true'", steps[index]["if"])


if __name__ == "__main__":
    unittest.main()
