"""Keep the historical count query portable between DuckDB and BigQuery."""

import re
import sys
import unittest
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reconcile import TABLES, queries


class ReconcileQueryTests(unittest.TestCase):
    def test_queries_do_not_use_reserved_rows_alias(self):
        for historical in (False, True):
            for sql in queries(lambda name: f"`demo.ecobottle_analytics.{name}`", historical).values():
                self.assertIsNone(re.search(r"\bas\s+rows\b", sql, re.IGNORECASE))

    def test_historical_counts_execute_in_duckdb(self):
        columns = {
            "dim_date": "20250930 AS date_key",
            "dim_customer": "1 AS customer_key",
            "fact_sales_order": "1 AS order_id",
            "fact_sales_order_item": "1 AS order_item_id",
            "fact_web_session": "1 AS session_id",
            "fact_nps_response": "1 AS nps_id",
        }
        with duckdb.connect(":memory:") as con:
            for name in TABLES:
                con.execute(f'CREATE TABLE "{name}" AS SELECT {columns.get(name, "1 AS id")}')
            sql = queries(lambda name: f'main."{name}"', historical=True)["table_counts"]
            result = con.execute(sql).fetchall()
            self.assertEqual(result, [(name, 1) for name in sorted(TABLES)])
            self.assertEqual(con.execute(sql).description[1][0], "row_count")


if __name__ == "__main__":
    unittest.main()
