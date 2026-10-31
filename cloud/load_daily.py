#!/usr/bin/env python3
"""Load one validated daily batch; replace only incomplete batches on retry."""

import argparse
import hashlib
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from google.cloud import bigquery

from config import Config
from load_historical import schema_for
from setup_daily import setup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "generator"))
from generate_daily import HEADERS
from validate_daily import validate_batch


def batch_fingerprint(manifest):
    return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()


def load(directory, historical, config):
    manifest = validate_batch(directory, historical)
    day = manifest["date"]
    fingerprint = batch_fingerprint(manifest)
    client = config.client()
    for name in ("ecobottle_raw", "ecobottle_analytics", "ecobottle_ops"):
        dataset = client.get_dataset(f"{config.project}.{name}")
        if dataset.location.lower() != config.location.lower():
            raise ValueError(f"Dataset {name} must be in {config.location}")
    bootstrap = f"{config.project}.ecobottle_ops.historical_bootstrap"
    state = config.query(client, f"SELECT status FROM `{bootstrap}`")
    if len(state) != 1 or state[0].status != "complete":
        raise ValueError("Complete the historical bootstrap before loading daily data")
    setup(config)

    marker = f"{config.project}.ecobottle_ops.daily_batches"
    existing = config.query(client, f"SELECT fingerprint, status FROM `{marker}` WHERE batch_id = @day", [
        bigquery.ScalarQueryParameter("day", "STRING", day),
    ])
    if existing:
        if len(existing) != 1 or existing[0].fingerprint != fingerprint:
            raise ValueError("Date already has a different or ambiguous batch; refusing to change it")
        if existing[0].status == "complete":
            print(f"Daily batch {day} already complete; no source tables were written")
            return
        if existing[0].status != "loading":
            raise ValueError("Unexpected batch status")
    else:
        # A missing row is not safe if a previous attempt wrote this date.
        for table in HEADERS:
            table_id = f"{config.project}.ecobottle_raw.daily_{table}"
            try:
                client.get_table(table_id)
            except NotFound:
                continue
            if config.query(client, f"SELECT 1 FROM `{table_id}` WHERE batch_id = @day LIMIT 1", [
                bigquery.ScalarQueryParameter("day", "STRING", day),
            ]):
                raise ValueError("Daily rows exist without a batch marker; refusing to overwrite")
        config.query(client, f"INSERT INTO `{marker}` (batch_id, fingerprint, manifest, status) "
                     "VALUES (@day, @fingerprint, @manifest, 'loading')", [
            bigquery.ScalarQueryParameter("day", "STRING", day),
            bigquery.ScalarQueryParameter("fingerprint", "STRING", fingerprint),
            bigquery.ScalarQueryParameter("manifest", "STRING", json.dumps(manifest, sort_keys=True)),
        ])

    # The marker remains 'loading' until all seven tables and counts are verified.
    for table, fields in HEADERS.items():
        table_id = f"{config.project}.ecobottle_raw.daily_{table}"
        config.query(client, f"DELETE FROM `{table_id}` WHERE batch_id = @day", [
            bigquery.ScalarQueryParameter("day", "STRING", day),
        ])
        # The load job writes only to an isolated temporary table. A failed job
        # never exposes a partial batch; completed batches are filtered in dbt.
        temp_id = f"{config.project}.ecobottle_raw.daily_upload_{table}_{day.replace('-', '')}"
        try:
            with (directory / f"{table}.csv").open("rb") as file:
                job = client.load_table_from_file(file, temp_id, job_config=bigquery.LoadJobConfig(
                    schema=schema_for(table), source_format=bigquery.SourceFormat.CSV,
                    skip_leading_rows=1, write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
                    allow_quoted_newlines=True,
                ))
                job.result(timeout=300)
            # A single INSERT SELECT is atomic at the table level.
            columns = ", ".join(f"`{field}`" for field in fields)
            config.query(client, f"INSERT INTO `{table_id}` ({columns}, batch_id) "
                         f"SELECT {columns}, @day FROM `{temp_id}`", [
                bigquery.ScalarQueryParameter("day", "STRING", day),
            ])
            rows = config.query(client, f"SELECT COUNT(*) AS rows FROM `{table_id}` WHERE batch_id = @day", [
                bigquery.ScalarQueryParameter("day", "STRING", day),
            ])[0].rows
            if rows != manifest["files"][table]["rows"]:
                raise ValueError(f"{table}: expected {manifest['files'][table]['rows']} rows, got {rows}")
            print(f"Daily {day} {table}: {rows} rows")
        finally:
            client.delete_table(temp_id, not_found_ok=True)
    config.query(client, f"UPDATE `{marker}` SET status = 'complete', completed_at = CURRENT_TIMESTAMP() "
                 "WHERE batch_id = @day AND fingerprint = @fingerprint AND status = 'loading'", [
        bigquery.ScalarQueryParameter("day", "STRING", day),
        bigquery.ScalarQueryParameter("fingerprint", "STRING", fingerprint),
    ])
    print(f"Daily batch {day} complete")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, required=True)
    parser.add_argument("--range", action="store_true", help="--dir contains date-named batch subdirectories")
    parser.add_argument("--historical", type=Path, default=Path(__file__).resolve().parents[1] / "raw")
    args = parser.parse_args()
    config = Config.from_env()
    if args.range:
        batches = sorted(args.dir.iterdir())
        try:
            days = [date.fromisoformat(path.name) for path in batches]
        except ValueError:
            parser.error("Range directory must contain only date-named batch directories")
        if not batches or any(not path.is_dir() or path.name != day.isoformat() for path, day in zip(batches, days)) or any(
            current - previous != timedelta(days=1) for previous, current in zip(days, days[1:])
        ):
            parser.error("Range directory must contain consecutive date-named batch directories")
        for path in batches:
            load(path, args.historical, config)
    else:
        load(args.dir, args.historical, config)


if __name__ == "__main__":
    main()
