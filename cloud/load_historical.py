#!/usr/bin/env python3
"""Load the seed-42 historical CSVs once; never overwrite a completed bootstrap."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from config import Config


# Explicit CSV order and types. Local Argentina times remain DATETIME, not UTC.
SCHEMAS = {
    "address": "address_id:INTEGER line1:STRING line2:STRING city:STRING province_id:INTEGER postal_code:STRING country_code:STRING created_at:DATETIME",
    "channel": "channel_id:INTEGER code:STRING name:STRING",
    "customer": "customer_id:INTEGER email:STRING first_name:STRING last_name:STRING phone:STRING status:STRING created_at:DATETIME",
    "nps_response": "nps_id:INTEGER customer_id:INTEGER channel_id:INTEGER score:INTEGER comment:STRING responded_at:DATETIME",
    "payment": "payment_id:INTEGER order_id:INTEGER method:STRING status:STRING amount:NUMERIC paid_at:DATETIME transaction_ref:STRING",
    "product": "product_id:INTEGER sku:STRING name:STRING category_id:INTEGER list_price:NUMERIC status:STRING created_at:DATETIME",
    "product_category": "category_id:INTEGER name:STRING parent_id:INTEGER",
    "province": "province_id:INTEGER name:STRING code:STRING",
    "sales_order": "order_id:INTEGER customer_id:INTEGER channel_id:INTEGER store_id:INTEGER order_date:DATETIME billing_address_id:INTEGER shipping_address_id:INTEGER status:STRING currency_code:STRING subtotal:NUMERIC tax_amount:NUMERIC shipping_fee:NUMERIC total_amount:NUMERIC",
    "sales_order_item": "order_item_id:INTEGER order_id:INTEGER product_id:INTEGER quantity:INTEGER unit_price:NUMERIC discount_amount:NUMERIC line_total:NUMERIC",
    "shipment": "shipment_id:INTEGER order_id:INTEGER carrier:STRING tracking_number:STRING status:STRING shipped_at:DATETIME delivered_at:DATETIME",
    "store": "store_id:INTEGER name:STRING address_id:INTEGER",
    "web_session": "session_id:INTEGER customer_id:INTEGER started_at:DATETIME ended_at:DATETIME source:STRING device:STRING",
}


def schema_for(table):
    return [bigquery.SchemaField(*field.split(":")) for field in SCHEMAS[table].split()]


def manifest(directory):
    actual = {path.stem for path in directory.glob("*.csv")}
    if actual != set(SCHEMAS):
        raise ValueError(f"Expected exactly 13 source CSVs; found: {sorted(actual)}")
    result = {}
    for table in sorted(SCHEMAS):
        path = directory / f"{table}.csv"
        with path.open(newline="", encoding="utf-8") as file:
            reader = csv.reader(file)
            if next(reader) != [field.name for field in schema_for(table)]:
                raise ValueError(f"Unexpected CSV header: {table}")
            count = sum(1 for _ in reader)
        result[table] = {"rows": count, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return result


def load(directory, config):
    files = manifest(directory)
    serialized = json.dumps(files, sort_keys=True)
    fingerprint = hashlib.sha256(serialized.encode()).hexdigest()
    client = config.client()
    # Provision datasets manually, so this identity needs no project-wide admin role.
    for name in ("ecobottle_raw", "ecobottle_analytics", "ecobottle_ops"):
        dataset = client.get_dataset(f"{config.project}.{name}")
        if dataset.location.lower() != config.location.lower():
            raise ValueError(f"Dataset {name} must be in {config.location}")
    marker_id = f"{config.project}.ecobottle_ops.historical_bootstrap"
    try:
        client.get_table(marker_id)
    except NotFound:
        if list(client.list_tables(f"{config.project}.ecobottle_raw")):
            raise ValueError("Raw dataset is not empty and has no bootstrap marker; refusing to overwrite it.")
        client.create_table(bigquery.Table(marker_id, schema=[
            bigquery.SchemaField("fingerprint", "STRING"),
            bigquery.SchemaField("manifest", "STRING"),
            bigquery.SchemaField("status", "STRING"),
            bigquery.SchemaField("completed_at", "TIMESTAMP"),
        ]))
    existing = config.query(client, f"SELECT * FROM `{marker_id}`")
    if existing:
        if len(existing) != 1 or existing[0].fingerprint != fingerprint:
            raise ValueError("Bootstrap fingerprint differs; refusing to replace historical data.")
        if existing[0].status == "complete":
            print("Historical bootstrap already complete; no source tables were written.")
            return
        if existing[0].status != "loading":
            raise ValueError("Unexpected bootstrap status; investigate before loading.")
    else:
        # A marker table without a row is safe only before any source table was loaded.
        if list(client.list_tables(f"{config.project}.ecobottle_raw")):
            raise ValueError("Missing bootstrap state with existing raw tables; refusing to overwrite.")
        config.query(client, f"INSERT INTO `{marker_id}` VALUES (@fingerprint, @manifest, 'loading', NULL)", [
            bigquery.ScalarQueryParameter("fingerprint", "STRING", fingerprint),
            bigquery.ScalarQueryParameter("manifest", "STRING", serialized),
        ])
    # Only an unfinished, matching bootstrap may replace its own partial tables.
    for table, info in files.items():
        table_id = f"{config.project}.ecobottle_raw.{table}"
        with (directory / f"{table}.csv").open("rb") as file:
            job = client.load_table_from_file(file, table_id, job_config=bigquery.LoadJobConfig(
                schema=schema_for(table), source_format=bigquery.SourceFormat.CSV,
                skip_leading_rows=1, write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
                allow_quoted_newlines=True,
            ))
            job.result(timeout=300)
        actual = client.get_table(table_id).num_rows
        if actual != info["rows"]:
            raise ValueError(f"{table}: expected {info['rows']} rows, got {actual}")
        print(f"Loaded {table}: {actual} rows")
    config.query(client, f"UPDATE `{marker_id}` SET status = 'complete', completed_at = CURRENT_TIMESTAMP() WHERE fingerprint = @fingerprint", [
        bigquery.ScalarQueryParameter("fingerprint", "STRING", fingerprint),
    ])
    print("Historical bootstrap complete.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, required=True)
    args = parser.parse_args()
    load(args.dir, Config.from_env())


if __name__ == "__main__":
    main()
