#!/usr/bin/env python3
"""Check one completed daily batch against its manifest and the dbt facts."""

import argparse
import sys
from decimal import Decimal
from pathlib import Path

from google.cloud import bigquery

from config import Config

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "generator"))
from validate_daily import validate_batch


def reconcile(directory, historical, config):
    manifest = validate_batch(directory, historical)
    day = manifest["date"]
    client = config.client()
    raw = lambda name: f"`{config.project}.ecobottle_raw.daily_{name}`"
    mart = lambda name: f"`{config.project}.ecobottle_analytics.{name}`"
    params = [bigquery.ScalarQueryParameter("day", "STRING", day)]
    marker = f"{config.project}.ecobottle_ops.daily_batches"
    state = config.query(client, f"SELECT status FROM `{marker}` WHERE batch_id = @day", params)
    if len(state) != 1 or state[0].status != "complete":
        raise ValueError(f"Batch {day} is not uniquely complete")
    for table, expected in manifest["files"].items():
        rows = config.query(client, f"SELECT COUNT(*) AS n FROM {raw(table)} WHERE batch_id = @day", params)[0].n
        if rows != expected["rows"]:
            raise ValueError(f"Daily {table}: expected {expected['rows']} rows, got {rows}")
    for table, key in (("sales_order", "order_id"), ("sales_order_item", "order_item_id"),
                       ("web_session", "session_id")):
        fact = f"fact_{table}"
        amount = {"sales_order": "total_amount", "sales_order_item": "line_total"}.get(table)
        sql = f"""
            SELECT count(*) AS n,
                {f'sum(r.{amount})' if amount else 'cast(0 as numeric)'} AS source_amount,
                {"sum(f.venta_neta)" if amount else 'cast(0 as numeric)'} AS mart_amount
            FROM {raw(table)} AS r
            JOIN {mart(fact)} AS f ON f.{key} = r.{key}
            WHERE r.batch_id = @day
        """
        result = config.query(client, sql, params)[0]
        if result.n != manifest["files"][table]["rows"]:
            raise ValueError(f"Daily {fact}: fact count differs from batch")
        if table != "web_session" and Decimal(result.source_amount or 0) != Decimal(result.mart_amount or 0):
            raise ValueError(f"Daily {fact}: revenue differs from source")
        print(f"OK {fact}: {result.n} rows")
    customers = config.query(client, f"SELECT COUNT(*) AS n FROM {mart('dim_customer')} "
                                    f"WHERE customer_id IN (SELECT customer_id FROM {raw('customer')} WHERE batch_id = @day)", params)[0].n
    if customers != manifest["files"]["customer"]["rows"]:
        raise ValueError("Daily customers missing from dim_customer")
    print(f"Daily batch {day} reconciled")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, required=True)
    parser.add_argument("--historical", type=Path, default=Path(__file__).resolve().parents[1] / "raw")
    args = parser.parse_args()
    reconcile(args.dir, args.historical, Config.from_env())
