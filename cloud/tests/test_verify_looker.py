"""Execute delivery acceptance checks locally, including deliberate corruption."""

from datetime import date
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import Mock

import duckdb
from sqlglot import transpile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cloud"))
sys.path.insert(0, str(ROOT))
from run_sql import create_raw_views
from test_looker_models import render
from verify_looker import acceptance_sql, verify
from publish_looker import SOURCES


class VerifyLookerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.con = duckdb.connect(":memory:")
        create_raw_views(cls.con)
        for name in ("01_dimensiones.sql", "02_hechos.sql"):
            cls.con.execute((ROOT / "sql" / name).read_text())
        for path in sorted((ROOT / "dbt/models/presentation").glob("*.sql")):
            cls.con.execute(f'CREATE TABLE "{path.stem}" AS {render(path)}')
        cls.con.execute("""CREATE TABLE actualizacion (
            fuente VARCHAR, filas BIGINT, primera_fecha DATE, ultima_fecha DATE,
            ultimo_lote_validado DATE, publication_id VARCHAR, published_at TIMESTAMPTZ)""")
        for name in SOURCES:
            cls.con.execute(f"ALTER TABLE {name} ADD COLUMN publication_id VARCHAR DEFAULT 'publication-1'")
            cls.con.execute(f"ALTER TABLE {name} ADD COLUMN published_at TIMESTAMPTZ")
        cls.con.execute("""CREATE TABLE daily_batches AS
            SELECT '2026-11-03' batch_id, 'fingerprint' fingerprint, 'complete' status""")
        cls.con.execute("""CREATE TABLE daily_validations AS
            SELECT '2026-11-03' batch_id, 'fingerprint' fingerprint, CURRENT_TIMESTAMP validated_at""")

    @classmethod
    def tearDownClass(cls):
        cls.con.close()

    def setUp(self):
        self.con.execute("BEGIN TRANSACTION")
        for name in SOURCES:
            self.con.execute(f"UPDATE {name} SET published_at = CURRENT_TIMESTAMP")
            self.con.execute(f"""INSERT INTO actualizacion
                SELECT '{name}', COUNT(*), MIN(fecha), MAX(fecha), DATE '2026-11-03',
                    'publication-1', CURRENT_TIMESTAMP FROM {name}""")

    def tearDown(self):
        self.con.execute("ROLLBACK")

    def failures(self, expected=None):
        sql = acceptance_sql("demo-project", expected is not None)
        sql = re.sub(r'`demo-project.ecobottle_(?:looker|ops)\.([a-z_]+)`', r'"\1"', sql)
        if expected:
            sql = sql.replace("@expected_date", f"DATE '{expected}'")
        return {row[0] for row in self.con.execute(transpile(sql, read="bigquery", write="duckdb")[0]).fetchall()}

    def test_published_historical_metrics_and_watermark_pass(self):
        self.assertEqual(self.failures("2026-11-03"), set())
        self.assertEqual(self.failures("2026-11-04"), {"expected_business_date"})

    def test_stale_or_mixed_publication_is_rejected(self):
        self.con.execute("UPDATE looker_ventas SET publication_id = 'other' WHERE order_id = (SELECT MIN(order_id) FROM looker_ventas)")
        self.assertIn("published_looker_ventas", self.failures())
        self.con.execute("UPDATE actualizacion SET published_at = published_at - INTERVAL '3 hours'")
        self.assertIn("publication_metadata", self.failures())

    def test_missing_metadata_and_tampered_historical_amount_fail(self):
        self.con.execute("DELETE FROM actualizacion WHERE fuente = 'looker_nps'")
        self.con.execute("UPDATE looker_ventas SET ventas_ars = ventas_ars + 1 WHERE order_id = (SELECT MIN(order_id) FROM looker_ventas)")
        self.assertTrue({"publication_metadata", "historical_looker_ventas"} <= self.failures())

    def test_unvalidated_batch_and_incorrect_watermark_fail(self):
        self.con.execute("UPDATE daily_validations SET fingerprint = 'wrong'")
        self.con.execute("UPDATE actualizacion SET ultimo_lote_validado = DATE '2026-11-02'")
        self.assertTrue({"unvalidated_batches", "published_watermark"} <= self.failures())

    def test_failed_acceptance_writes_evidence_and_raises(self):
        config = Mock(project="demo-project")
        config.query.return_value = [{"control": "expected_business_date"}]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "acceptance.json"
            with self.assertRaisesRegex(ValueError, "expected_business_date"):
                verify(config, date(2026, 11, 3), output)
            self.assertFalse(json.loads(output.read_text())["passed"])
        self.assertEqual(config.query.call_args.args[2][0].value, date(2026, 11, 3))


if __name__ == "__main__":
    unittest.main()
