import contextlib
import csv
import io
import json
import hashlib
from datetime import date, datetime, timedelta
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from generate_daily import FIRST_DAILY_ID, FIRST_DAY, HEADERS, VERSION, generate, generate_range
from validate_daily import validate_batch
from validate_raw import Report, load, validate


HISTORICAL = Path(__file__).resolve().parents[2] / "raw"


class DailyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def check(self, path):
        with contextlib.redirect_stdout(io.StringIO()):
            return validate_batch(path, HISTORICAL)

    def test_reproducible_and_valid_weekday(self):
        day = date(2026, 10, 31)
        left, right = self.root / "left", self.root / "right"
        self.assertEqual(generate(day, 42, 100, left), generate(day, 42, 100, right))
        self.assertEqual(self.check(left)["orders"], 100)
        for table in HEADERS:
            self.assertEqual((left / f"{table}.csv").read_bytes(), (right / f"{table}.csv").read_bytes())
        with self.assertRaises(ValueError):
            generate(day, 42, 100, left)  # never overwrite existing outputs

    def test_sunday_online_with_sessions_and_ready_shipments(self):
        folder = self.root / "sunday"
        generate(date(2026, 11, 1), 42, 100, folder)
        self.check(folder)
        for table in ("web_session", "shipment"):
            with (folder / f"{table}.csv").open(newline="") as file:
                self.assertEqual(sum(1 for _ in csv.DictReader(file)), 100)

    def test_fixed_holiday_has_no_store_sales(self):
        folder = self.root / "holiday"
        generate(date(2025, 12, 25), 42, 100, folder)
        self.check(folder)
        with (folder / "sales_order.csv").open(newline="") as file:
            self.assertEqual({row["channel_id"] for row in csv.DictReader(file)}, {"1"})

    def test_tampered_csv_is_rejected(self):
        folder = self.root / "tampered"
        generate(date(2026, 11, 2), 42, 100, folder)
        with (folder / "customer.csv").open("a") as file:
            file.write("invalid\n")
        with self.assertRaises(ValueError):
            self.check(folder)

    def test_first_possible_day_is_above_every_historical_id(self):
        folder = self.root / "first-day"
        manifest = generate(FIRST_DAY, 42, 100, folder)
        self.assertEqual(manifest["version"], VERSION)
        self.assertEqual(VERSION, 2)
        self.check(folder)
        historical_ids = {
            "address": "address_id", "customer": "customer_id", "sales_order": "order_id",
            "sales_order_item": "order_item_id", "payment": "payment_id", "shipment": "shipment_id",
            "web_session": "session_id", "nps_response": "nps_id",
        }
        largest_historical = 0
        for table, key in historical_ids.items():
            with (HISTORICAL / f"{table}.csv").open(encoding="utf-8", newline="") as file:
                largest_historical = max(largest_historical, *(int(row[key]) for row in csv.DictReader(file)))
        self.assertLess(largest_historical, FIRST_DAILY_ID)
        for table, key in historical_ids.items():
            if table not in HEADERS:
                continue
            with (folder / f"{table}.csv").open(encoding="utf-8", newline="") as file:
                self.assertTrue(all(int(row[key]) >= FIRST_DAILY_ID for row in csv.DictReader(file)))

    def test_validator_rejects_old_ids_even_if_checksum_matches(self):
        folder = self.root / "old-ids"
        manifest = generate(FIRST_DAY, 42, 100, folder)
        path = folder / "sales_order.csv"
        content = path.read_text(encoding="utf-8")
        path.write_text(content.replace(str(FIRST_DAILY_ID), "1000000000", 1), encoding="utf-8")
        manifest["files"]["sales_order"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        (folder / "manifest.json").write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "outside the batch namespace"):
            self.check(folder)

    def test_seven_days_independent_and_combined(self):
        combined = load(HISTORICAL)
        all_ids = set()
        ranged = generate_range(date(2026, 10, 31), date(2026, 11, 6), 42, 100, self.root / "range")
        for offset in range(7):
            day = date(2026, 10, 31) + timedelta(days=offset)
            folder = self.root / str(offset)
            manifest = generate(day, 42, 100, folder)
            ranged_day = self.root / "range" / day.isoformat()
            self.assertEqual(manifest, ranged[offset])
            for table in HEADERS:
                self.assertEqual((folder / f"{table}.csv").read_bytes(), (ranged_day / f"{table}.csv").read_bytes())
            self.check(folder)
            self.assertEqual(manifest["files"]["sales_order"]["rows"], 100)
            for table in HEADERS:
                with (folder / f"{table}.csv").open(newline="") as file:
                    rows = list(csv.DictReader(file))
                combined[table].extend(rows)
                if table == "sales_order":
                    ids = {r["order_id"] for r in rows}
                    self.assertFalse(all_ids & ids)
                    all_ids.update(ids)
        self.assertEqual(len(all_ids), 700)
        report = Report()
        with contextlib.redirect_stdout(io.StringIO()):
            validate(combined, report, snapshot=datetime(2026, 11, 6, 23, 59, 59), end=date(2026, 11, 6))
        self.assertEqual(report.failures, 0)


if __name__ == "__main__":
    unittest.main()
