"""Exercise publication DML/guards in DuckDB; BigQuery acceptance remains separate."""

from pathlib import Path
import re
import sys
import unittest

import duckdb
from sqlglot import transpile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from publish_looker import SOURCES, publication_sql


def portable_publication():
    sql = publication_sql("demo-project").replace("@publication_id", "'new-publication'")
    # ASSERT is BigQuery scripting, not supported by sqlglot's parser. Preserve
    # its predicate as an executable fail-closed expression for this local test.
    sql = re.sub(
        r"ASSERT (.*?) AS 'Every daily batch[^']*';",
        r"SELECT CASE WHEN \1 THEN 1 ELSE ERROR('Unvalidated batch') END;",
        sql, flags=re.S,
    )
    sql = sql.replace("demo-project.", "")
    return ";\n".join(transpile(sql, read="bigquery", write="duckdb"))


class LookerTransactionTests(unittest.TestCase):
    def setUp(self):
        self.con = duckdb.connect(":memory:")
        self.addCleanup(self.con.close)
        for schema in ("ecobottle_analytics", "ecobottle_looker", "ecobottle_ops"):
            self.con.execute(f"create schema {schema}")
        self.con.execute("""
            create table ecobottle_ops.daily_batches (batch_id varchar, fingerprint varchar, status varchar);
            create table ecobottle_ops.daily_validations (batch_id varchar, fingerprint varchar, validated_at timestamp);
            create table ecobottle_looker.actualizacion (
                fuente varchar, filas bigint, primera_fecha date, ultima_fecha date,
                ultimo_lote_validado date, publication_id varchar, published_at timestamp
            );
        """)
        for name, fields in SOURCES.items():
            columns = ", ".join(f'"{field}" {"date" if field == "fecha" else "bigint"}' for field in fields)
            values = ", ".join("DATE '2026-11-02'" if field == "fecha" else "2" for field in fields)
            self.con.execute(f"create table ecobottle_analytics.{name} ({columns})")
            self.con.execute(f"insert into ecobottle_analytics.{name} values ({values})")
            self.con.execute(f"""
                create table ecobottle_looker.{name} (
                    {columns}, publication_id varchar, published_at timestamp,
                    check ("{fields[0]}" >= 0)
                )
            """)
        self.sql = portable_publication()

    def snapshot(self):
        return {
            name: self.con.execute(f"select * from ecobottle_looker.{name}").fetchall()
            for name in (*SOURCES, "actualizacion")
        }

    def test_commit_replaces_all_sources_and_metadata_with_one_version(self):
        self.con.execute(self.sql)
        self.assertEqual(self.con.execute("select count(*) from ecobottle_looker.actualizacion").fetchone(), (4,))
        times = set()
        for name in SOURCES:
            version, timestamp = self.con.execute(
                f"select publication_id, published_at from ecobottle_looker.{name}"
            ).fetchone()
            self.assertEqual(version, "new-publication")
            times.add(timestamp)
        self.assertEqual(len(times), 1)

    def test_mid_publication_failure_preserves_previous_snapshot_on_rollback(self):
        self.con.execute(self.sql)
        before = self.snapshot()
        self.con.execute("update ecobottle_analytics.looker_ventas set pedidos_venta = 99")
        self.con.execute("update ecobottle_analytics.looker_productos set order_item_id = -10")
        with self.assertRaises(duckdb.Error):
            self.con.execute(self.sql)
        self.con.execute("rollback")
        self.assertEqual(self.snapshot(), before)

    def test_unvalidated_incomplete_duplicate_or_changed_batches_block_publication(self):
        self.con.execute(self.sql)
        before = self.snapshot()
        self.con.execute("insert into ecobottle_ops.daily_batches values ('2026-11-02', 'sha', 'complete')")
        for validation in (None, "wrong-fingerprint", "sha"):
            if validation:
                self.con.execute(
                    "insert into ecobottle_ops.daily_validations values ('2026-11-02', ?, current_timestamp)",
                    [validation],
                )
            if validation == "sha":
                # More than one validation record is ambiguous, even if one matches.
                self.con.execute("insert into ecobottle_ops.daily_validations values ('2026-11-02', 'sha', current_timestamp)")
            with self.assertRaises(duckdb.Error):
                self.con.execute(self.sql)
            self.con.execute("rollback")
            self.assertEqual(self.snapshot(), before)
        self.con.execute("delete from ecobottle_ops.daily_validations")
        self.con.execute("insert into ecobottle_ops.daily_validations values ('2026-11-02', 'sha', current_timestamp)")
        self.con.execute("update ecobottle_ops.daily_batches set status = 'loading'")
        with self.assertRaises(duckdb.Error):
            self.con.execute(self.sql)
        self.con.execute("rollback")
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
