#!/usr/bin/env python3
"""Generate one deterministic, append-only business-day batch (Argentina local time)."""

import argparse
import csv
import hashlib
import json
import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from generate_raw import CITIES, FIRST_NAMES, LAST_NAMES, PRODUCTS, SHIPPING_FEE, STORES, STREETS


VERSION = 2
FIRST_DAY = date(2025, 10, 1)
MAX_ORDERS = 10000
# Above every historical ID (the largest NPS ID is 13,000,003,082).
# Do not change this namespace without migrating already-completed batches.
FIRST_DAILY_ID = 20_000_000_000
IDS_PER_DAY = 100_001
HEADERS = {
    "address": "address_id line1 line2 city province_id postal_code country_code created_at",
    "customer": "customer_id email first_name last_name phone status created_at",
    "sales_order": "order_id customer_id channel_id store_id order_date billing_address_id shipping_address_id status currency_code subtotal tax_amount shipping_fee total_amount",
    "sales_order_item": "order_item_id order_id product_id quantity unit_price discount_amount line_total",
    "payment": "payment_id order_id method status amount paid_at transaction_ref",
    "shipment": "shipment_id order_id carrier tracking_number status shipped_at delivered_at",
    "web_session": "session_id customer_id started_at ended_at source device",
}
HEADERS = {table: columns.split() for table, columns in HEADERS.items()}


def batch_base(day):
    return FIRST_DAILY_ID + (day - FIRST_DAY).days * IDS_PER_DAY


def generate(day, seed, count, directory):
    if day < FIRST_DAY or day >= date(2200, 1, 1):
        raise ValueError(f"Date must be between {FIRST_DAY} and 2199-12-31")
    if count < 1 or count > MAX_ORDERS:
        raise ValueError(f"Order count must be between 1 and {MAX_ORDERS}")
    if directory.exists() and any(directory.iterdir()):
        raise ValueError("Output directory must be empty; refusing to overwrite a batch")
    directory.mkdir(parents=True, exist_ok=True)
    rng = random.Random(f"ecobottle-daily-v{VERSION}:{day.isoformat()}:{seed}")
    # One namespace per date, 10 IDs per order per table. Separate from historical IDs.
    base = batch_base(day)
    rows = {name: [] for name in HEADERS}
    online = day.weekday() == 6 or (day.month, day.day) in {(1, 1), (5, 1), (12, 25)}
    # Shops are closed on Sundays and the fixed holidays covered by the historical generator.
    for index in range(count):
        ident = base + index * 10
        store_id = rng.choice(list(STORES))
        _, province_id, _, _, _, _ = STORES[store_id]
        city = rng.choice(CITIES[province_id])
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        hour = rng.randint(10, 19) if not online else rng.randint(1, 21)
        ordered = datetime.combine(day, time(hour, rng.randrange(60), rng.randrange(60)))
        created = ordered - timedelta(minutes=20 if online else 4)
        session_start = ordered - timedelta(minutes=10)
        if online and created.date() != day:
            raise ValueError("Customer registration must be on the batch date")
        stamp = lambda value: value.strftime("%Y-%m-%d %H:%M:%S")
        rows["customer"].append([ident, f"daily-{day:%Y%m%d}-{index}@example.com", first, last, "", "A", stamp(created)])
        rows["address"].append([ident, f"{rng.choice(STREETS)} {rng.randint(100, 4999)}", "", city[0],
                                province_id, city[1], "AR", stamp(created)])
        products = rng.sample(PRODUCTS, rng.randint(1, len(PRODUCTS)))
        subtotal = Decimal("0.00")
        for item_index, product in enumerate(products):
            product_id, _, _, _, price = product
            quantity = rng.randint(1, 3)
            unit_price = Decimal(str(price)).quantize(Decimal("0.01"))
            line = unit_price * quantity
            subtotal += line
            rows["sales_order_item"].append([ident + item_index, ident, product_id, quantity,
                                             f"{unit_price:.2f}", "0.00", f"{line:.2f}"])
        tax = (subtotal * Decimal("0.21")).quantize(Decimal("0.01"))
        fee = Decimal(str(SHIPPING_FEE[province_id])) if online and subtotal < 45000 else Decimal("0.00")
        total = subtotal + tax + fee
        rows["sales_order"].append([ident, ident, 1 if online else 2, "" if online else store_id,
                                    stamp(ordered), ident, ident if online else store_id,
                                    "PAID" if online else "FULFILLED", "ARS", f"{subtotal:.2f}",
                                    f"{tax:.2f}", f"{fee:.2f}", f"{total:.2f}"])
        paid = ordered + timedelta(minutes=1)
        rows["payment"].append([ident, ident, "GATEWAY" if online else "CASH", "PAID",
                                f"{total:.2f}", stamp(paid), f"DAILY-{day:%Y%m%d}-{index}" if online else ""])
        if online:
            rows["web_session"].append([ident, ident, stamp(session_start),
                                        stamp(paid + timedelta(minutes=1)), "direct", "desktop"])
            rows["shipment"].append([ident, ident, "Correo Argentino", "", "READY", "", ""])

    files = {}
    for table, header in HEADERS.items():
        path = directory / f"{table}.csv"
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(rows[table])
        files[table] = {"rows": len(rows[table]), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    manifest = {"date": day.isoformat(), "seed": seed, "version": VERSION, "orders": count, "files": files}
    (directory / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return manifest


def generate_range(start, end, seed, count, directory):
    if end < start or (end - start).days > 30:
        raise ValueError("Range must cover 1 to 31 days")
    return [generate(day, seed, count, directory / day.isoformat())
            for day in (start + timedelta(days=offset) for offset in range((end - start).days + 1))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    days = parser.add_mutually_exclusive_group(required=True)
    days.add_argument("--date", type=date.fromisoformat)
    days.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat, help="inclusive end date, with --start")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--orders", type=int, default=100)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.start:
        if not args.end or args.end < args.start or (args.end - args.start).days > 30:
            parser.error("--start requires --end within 30 days (inclusive)")
        for manifest in generate_range(args.start, args.end, args.seed, args.orders, args.out):
            print(json.dumps(manifest, sort_keys=True))
    else:
        if args.end:
            parser.error("--end requires --start")
        print(json.dumps(generate(args.date, args.seed, args.orders, args.out), sort_keys=True))


if __name__ == "__main__":
    main()
