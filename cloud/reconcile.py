#!/usr/bin/env python3
"""Compare historical BigQuery counts and KPIs with a read-only DuckDB reference."""

import argparse
from pathlib import Path

import duckdb

from config import Config


TABLES = (
    "dim_date", "dim_channel", "dim_province", "dim_product", "dim_customer", "dim_store",
    "fact_sales_order", "fact_sales_order_item", "fact_web_session", "fact_nps_response",
)


def queries(table, historical=False):
    """Portable SQL; compare natural labels rather than regenerated surrogate keys."""
    month = "substr(cast(f.date_key as string), 1, 6)"
    def scope(name):
        if not historical:
            return ""
        if name == "dim_date":
            return " where date_key <= 20250930"
        if name == "dim_customer":
            return " where customer_key < 1000000000"
        if name.startswith("fact_"):
            key = {"fact_sales_order": "order_id", "fact_sales_order_item": "order_item_id",
                   "fact_web_session": "session_id", "fact_nps_response": "nps_id"}[name]
            return f" where {key} < 1000000000"
        return ""
    counts = " union all ".join(f"select '{name}' as name, count(*) as row_count from {table(name)}{scope(name)}" for name in TABLES)
    sales_scope = "where f.order_id < 1000000000" if historical else ""
    items_scope = "where f.order_item_id < 1000000000" if historical else ""
    sessions_scope = "where f.session_id < 1000000000" if historical else ""
    return {
        "table_counts": counts + " order by name",
        "monthly_sales": f"""
            select {month} as month, c.code, count(*) as orders,
                sum(case when f.es_venta then 1 else 0 end) as sales,
                sum(f.venta_neta) as revenue,
                count(distinct case when f.es_venta then f.customer_key end) as buyers
            from {table('fact_sales_order')} as f
            join {table('dim_channel')} as c on c.channel_key = f.channel_key
            {sales_scope}
            group by month, c.code order by month, c.code""",
        "monthly_products": f"""
            select {month} as month, p.sku, sum(f.venta_neta) as revenue,
                sum(case when f.es_venta then f.quantity else 0 end) as units
            from {table('fact_sales_order_item')} as f
            join {table('dim_product')} as p on p.product_key = f.product_key
            {items_scope}
            group by month, p.sku order by month, p.sku""",
        "monthly_sessions": f"""
            select {month} as month, f.source, f.device, count(*) as sessions,
                sum(case when f.customer_key = -1 then 1 else 0 end) as anonymous,
                count(distinct case when f.customer_key != -1 then f.customer_key end) as users,
                count(f.duration_seconds) as closed_sessions,
                sum(f.duration_seconds) as duration_seconds
            from {table('fact_web_session')} as f
            {sessions_scope}
            group by month, f.source, f.device order by month, f.source, f.device""",
        "monthly_nps": f"""
            select {month} as month, c.code, count(*) as responses,
                sum(case when f.score >= 9 then 1 else 0 end) as promoters,
                sum(case when f.score between 7 and 8 then 1 else 0 end) as passives,
                sum(case when f.score <= 6 then 1 else 0 end) as detractors,
                sum(case when f.customer_key = -1 then 1 else 0 end) as anonymous
            from {table('fact_nps_response')} as f
            join {table('dim_channel')} as c on c.channel_key = f.channel_key
            group by month, c.code order by month, c.code""",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args()
    config = Config.from_env()
    client = config.client()
    local = queries(lambda name: f'main."{name}"')
    remote = queries(lambda name: f"`{config.project}.ecobottle_analytics.{name}`", historical=True)
    failures = []
    with duckdb.connect(str(args.database), read_only=True) as con:
        for name, sql in remote.items():
            expected = con.execute(local[name]).fetchall()
            actual = [tuple(row) for row in config.query(client, sql)]
            if actual != expected:
                failures.append(name)
                print(f"FAIL {name}: expected {len(expected)} groups, got {len(actual)}")
                for index, (left, right) in enumerate(zip(expected, actual)):
                    if left != right:
                        print(f"First difference at {index}: DuckDB={left}, BigQuery={right}")
                        break
            else:
                print(f"OK {name}: {len(actual)} groups")
    if failures:
        raise SystemExit(f"Historical reconciliation failed: {', '.join(failures)}")
    print("Historical reconciliation OK (decimal amounts compared without float conversion).")


if __name__ == "__main__":
    main()
