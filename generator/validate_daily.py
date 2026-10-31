#!/usr/bin/env python3
"""Validate a daily batch against the immutable historical CSVs without writing them."""

import argparse
import csv
import hashlib
import json
from datetime import datetime, time
from pathlib import Path

from generate_daily import FIRST_DAY, HEADERS, IDS_PER_DAY, VERSION, batch_base
from validate_raw import Report, TABLES, load, validate


def validate_batch(directory, historical):
    if {p.name for p in directory.iterdir()} != {"manifest.json"} | {f"{t}.csv" for t in HEADERS}:
        raise ValueError("Batch must contain exactly seven CSVs and manifest.json")
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if set(manifest) != {"date", "seed", "version", "orders", "files"} or manifest["version"] != VERSION:
        raise ValueError("Unexpected batch manifest/version")
    day = datetime.fromisoformat(manifest["date"]).date()
    if day < FIRST_DAY or day >= datetime(2200, 1, 1).date() or manifest["date"] != day.isoformat() or set(manifest["files"]) != set(HEADERS):
        raise ValueError("Unexpected batch date or files")
    if not isinstance(manifest["seed"], int) or not isinstance(manifest["orders"], int) or not 1 <= manifest["orders"] <= 10000:
        raise ValueError("Invalid seed/order count")
    data = load(historical)
    base = batch_base(day)
    keys = {"address": "address_id", "customer": "customer_id", "sales_order": "order_id",
            "sales_order_item": "order_item_id", "payment": "payment_id",
            "shipment": "shipment_id", "web_session": "session_id"}
    for table, header in HEADERS.items():
        path = directory / f"{table}.csv"
        with path.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames != header:
                raise ValueError(f"Unexpected {table} header")
            rows = list(reader)
        if manifest["files"][table] != {"rows": len(rows), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}:
            raise ValueError(f"Batch checksum/count mismatch: {table}")
        if any(not base <= int(row[keys[table]]) < base + IDS_PER_DAY for row in rows):
            raise ValueError(f"IDs outside the batch namespace: {table}")
        if table in ("sales_order", "customer", "address", "payment", "shipment", "web_session"):
            column = {"sales_order": "order_date", "customer": "created_at", "address": "created_at",
                      "payment": "paid_at", "shipment": "shipped_at", "web_session": "started_at"}[table]
            if any(row[column] and datetime.fromisoformat(row[column]).date() != day for row in rows):
                raise ValueError(f"Records outside batch date: {table}")
        data[table].extend(rows)
    if manifest["files"]["sales_order"]["rows"] != manifest["orders"]:
        raise ValueError("Batch order count mismatch")
    report = Report()
    validate(data, report, snapshot=datetime.combine(day, time(23, 59, 59)), end=day)
    if report.failures:
        raise ValueError(f"Daily batch violates {report.failures} source rules")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, required=True)
    parser.add_argument("--historical", type=Path, default=Path(__file__).resolve().parent.parent / "raw")
    args = parser.parse_args()
    manifest = validate_batch(args.dir, args.historical)
    print(f"Daily batch {manifest['date']} OK: {manifest['orders']} orders")


if __name__ == "__main__":
    main()
