"""Exercise the portable dbt singular tests without a BigQuery connection."""

from pathlib import Path
import unittest

import duckdb
from jinja2 import Environment
from sqlglot import parse


TESTS = Path(__file__).resolve().parents[2] / "dbt" / "tests"


def render(name):
    return Environment().from_string((TESTS / name).read_text()).render(
        ref=lambda model: f'"{model}"'
    )


class DbtSqlTests(unittest.TestCase):
    def test_unknown_members(self):
        sql = render("unknown_members.sql")
        parse(sql, read="bigquery")
        with duckdb.connect(":memory:") as con:
            con.execute("create table dim_customer (customer_key integer, customer_id integer)")
            con.execute("create table dim_store (store_key integer, store_id integer)")
            con.execute("create table fact_nps_response (nps_id integer, customer_key integer)")
            con.execute("create table stg_nps_response (nps_id integer, customer_id integer)")
            con.execute("create table fact_sales_order (channel_key integer, store_key integer)")
            con.execute("create table dim_channel (channel_key integer, code varchar)")
            con.execute("insert into dim_customer values (-1, null)")
            con.execute("insert into dim_store values (-1, null)")
            self.assertEqual(con.execute(sql).fetchall(), [])
            con.execute("delete from dim_customer")
            self.assertEqual(con.execute(sql).fetchall(), [("customer",)])

    def test_source_row_preservation(self):
        sql = render("source_row_preservation.sql")
        parse(sql, read="bigquery")
        with duckdb.connect(":memory:") as con:
            for table in (
                "fact_sales_order", "stg_sales_order", "fact_sales_order_item", "stg_sales_order_item",
                "fact_web_session", "stg_web_session", "fact_nps_response", "stg_nps_response",
            ):
                con.execute(f'create table "{table}" (id integer)')
            self.assertEqual(con.execute(sql).fetchall(), [])
            con.execute("insert into fact_sales_order values (1)")
            self.assertEqual(con.execute(sql).fetchall(), [("fact_sales_order",)])


if __name__ == "__main__":
    unittest.main()
