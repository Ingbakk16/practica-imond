import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_bigquery_project import NAME, ROOT, TABLES, build


class BigQueryProjectTests(unittest.TestCase):
    def test_build_preserves_report_and_model_contract(self):
        original_path = ROOT / "EcoBottle_AR.SemanticModel/model.bim"
        original_bytes = original_path.read_bytes()
        original = json.loads(original_bytes)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "cloud"
            project = build(output, "ecobottle-demo", "ecobottle-billing")
            self.assertTrue(project.exists())
            model = json.loads((output / f"{NAME}.SemanticModel/model.bim").read_text())
            self.assertEqual(model["model"]["relationships"], original["model"]["relationships"])
            analytical = [t for t in model["model"]["tables"] if t["name"] in TABLES]
            self.assertEqual(len(analytical), 10)
            for old, new in zip(original["model"]["tables"], analytical):
                self.assertEqual(old["name"], new["name"])
                self.assertEqual(old["columns"], new["columns"])
                for measure in old.get("measures", []):
                    self.assertIn(measure, new["measures"])
                source = new["partitions"][0]
                self.assertEqual(source["mode"], "import")
                self.assertIn("GoogleBigQuery.Database", source["source"]["expression"])
                self.assertIn("ecobottle_analytics", source["source"]["expression"])
                self.assertIn('Name="' + old["name"] + '"', source["source"]["expression"])
            serialized = json.dumps(model)
            self.assertNotIn("File.Contents", serialized)
            self.assertNotIn("RutaDW", serialized)
            self.assertIn("ecobottle-billing", serialized)
            self.assertIn("DateTimeZone.FixedUtcNow", serialized)
            report = output / f"{NAME}.Report"
            for path in (ROOT / "EcoBottle_AR.Report/definition").rglob("*.json"):
                expected = path.read_text().replace("Corte: 30/09/2025", "Fuente: BigQuery · Actualización automática pendiente de configurar")
                self.assertEqual((report / "definition" / path.relative_to(ROOT / "EcoBottle_AR.Report/definition")).read_text(), expected)
            reference = json.loads((report / "definition.pbir").read_text())
            self.assertEqual(reference["datasetReference"]["byPath"]["path"], f"../{NAME}.SemanticModel")
            with self.assertRaises(FileExistsError):
                build(output, "ecobottle-demo")
        self.assertEqual(original_path.read_bytes(), original_bytes)

    def test_invalid_project_is_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "cloud"
            for value in ("", "Project Display Name", 'bad"project', "123456789"):
                with self.assertRaises(ValueError):
                    build(output, value)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
