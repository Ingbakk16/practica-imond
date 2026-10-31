"""Keep the historical count query portable between DuckDB and BigQuery."""

import re
import sys
import unittest
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reconcile import FIRST_DAILY_ID, TABLES, queries


class ReconcileQueryTests(unittest.TestCase):
    def test_queries_do_not_use_reserved_rows_alias(self):
        for historical in (False, True):
            for sql in queries(lambda name: f"`demo.ecobottle_analytics.{name}`", historical).values():
                self.assertIsNone(re.search(r"\bas\s+rows\b", sql, re.IGNORECASE))

    def test_historical_counts_execute_in_duckdb(self):
        columns = {
            "dim_date": "20250930 AS date_key",
            "dim_customer": "3471::bigint AS customer_key",
            "fact_sales_order": "1000000000::bigint AS order_id",
            "fact_sales_order_item": "5000000000 AS order_item_id",
            "fact_web_session": "11000000000 AS session_id",
            "fact_nps_response": "13000000000 AS nps_id",
        }
        with duckdb.connect(":memory:") as con:
            for name in TABLES:
                con.execute(f'CREATE TABLE "{name}" AS SELECT {columns.get(name, "1 AS id")}')
            for name, column in (("dim_customer", "customer_key"),
                                 ("fact_sales_order", "order_id"),
                                 ("fact_sales_order_item", "order_item_id"),
                                 ("fact_web_session", "session_id"),
                                 ("fact_nps_response", "nps_id")):
                con.execute(f'INSERT INTO "{name}" VALUES (?)', [FIRST_DAILY_ID])
            sql = queries(lambda name: f'main."{name}"', historical=True)["table_counts"]
            result = con.execute(sql).fetchall()
            self.assertEqual(result, [(name, 1) for name in sorted(TABLES)])
            self.assertEqual(con.execute(sql).description[1][0], "row_count")

    def test_historical_monthly_kpis_keep_high_historical_ids_only(self):
        with duckdb.connect(":memory:") as con:
            con.execute("create table dim_channel as select 1 as channel_key, 'ONLINE' as code")
            con.execute("create table dim_product as select 1 as product_key, 'ECO' as sku")
            con.execute("""create table fact_sales_order as
                select 1000000000::bigint as order_id, 20250930 as date_key, 1 as channel_key,
                    true as es_venta, 100::decimal(12,2) as venta_neta, 1 as customer_key""")
            con.execute("""create table fact_sales_order_item as
                select 5000000000::bigint as order_item_id, 20250930 as date_key, 1 as product_key,
                    true as es_venta, 1 as quantity, 100::decimal(12,2) as venta_neta""")
            con.execute("""create table fact_web_session as
                select 11000000000::bigint as session_id, 20250930 as date_key, 'direct' as source,
                    'desktop' as device, 1 as customer_key, 10 as duration_seconds""")
            con.execute("""create table fact_nps_response as
                select 13000000000::bigint as nps_id, 20250930 as date_key, 1 as channel_key,
                    9 as score, 1 as customer_key""")
            for table, key in (("fact_sales_order", "order_id"),
                               ("fact_sales_order_item", "order_item_id"),
                               ("fact_web_session", "session_id"), ("fact_nps_response", "nps_id")):
                con.execute(f'insert into "{table}" select * replace (? as {key}) from "{table}" limit 1',
                            [FIRST_DAILY_ID])
            for name, sql in queries(lambda name: f'main."{name}"', historical=True).items():
                if name == "table_counts":
                    continue
                result = con.execute(sql).fetchall()
                self.assertEqual(len(result), 1, name)
                self.assertEqual(result[0][0], "202509", name)
                count_index = 3 if name == "monthly_sessions" else 2
                self.assertEqual(result[0][count_index], 100 if name == "monthly_products" else 1, name)


if __name__ == "__main__":
    unittest.main()
