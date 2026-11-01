#!/usr/bin/env python3
"""Provision empty daily tables for dbt; never truncate or modify existing data."""

import json
import sys
from pathlib import Path

from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from config import Config
from load_historical import schema_for

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "generator"))
from generate_daily import HEADERS, VERSION


def setup(config):
    client = config.client()
    marker = f"{config.project}.ecobottle_ops.daily_batches"
    marker_schema = [
        bigquery.SchemaField("batch_id", "STRING"),
        bigquery.SchemaField("fingerprint", "STRING"),
        bigquery.SchemaField("manifest", "STRING"),
        bigquery.SchemaField("status", "STRING"),
        bigquery.SchemaField("completed_at", "TIMESTAMP"),
    ]
    try:
        existing_marker = client.get_table(marker)
    except NotFound:
        existing = {t.table_id for t in client.list_tables(f"{config.project}.ecobottle_raw")}
        if any(f"daily_{table}" in existing for table in HEADERS):
            raise ValueError("Daily tables exist without batch marker; investigate before provisioning")
        client.create_table(bigquery.Table(marker, schema=marker_schema))
    else:
        if [(f.name, f.field_type) for f in existing_marker.schema] != [(f.name, f.field_type) for f in marker_schema]:
            raise ValueError("Unexpected daily batch marker schema")
        for batch in config.query(client, f"SELECT batch_id, manifest FROM `{marker}`"):
            try:
                version = json.loads(batch.manifest)["version"]
            except (TypeError, ValueError, KeyError) as error:
                raise ValueError(f"Invalid manifest for daily batch {batch.batch_id}") from error
            if version != VERSION:
                raise ValueError(
                    f"Daily batch {batch.batch_id} uses generator version {version}; "
                    "migrate it explicitly before using the new ID namespace"
                )
    for table in HEADERS:
        table_id = f"{config.project}.ecobottle_raw.daily_{table}"
        expected = [*schema_for(table), bigquery.SchemaField("batch_id", "STRING")]
        try:
            existing = client.get_table(table_id)
        except NotFound:
            complete = config.query(client, f"SELECT 1 FROM `{marker}` WHERE status = 'complete' LIMIT 1")
            if complete:
                raise ValueError(f"Missing daily table {table_id} despite completed batches")
            client.create_table(bigquery.Table(table_id, schema=expected))
        else:
            if [(f.name, f.field_type) for f in existing.schema] != [(f.name, f.field_type) for f in expected]:
                raise ValueError(f"Unexpected schema for {table_id}")
    validation_id = f"{config.project}.ecobottle_ops.daily_validations"
    validation_schema = [
        bigquery.SchemaField("batch_id", "STRING"),
        bigquery.SchemaField("fingerprint", "STRING"),
        bigquery.SchemaField("validated_at", "TIMESTAMP"),
    ]
    try:
        validation = client.get_table(validation_id)
    except NotFound:
        client.create_table(bigquery.Table(validation_id, schema=validation_schema))
    else:
        if [(f.name, f.field_type) for f in validation.schema] != [(f.name, f.field_type) for f in validation_schema]:
            raise ValueError(f"Unexpected schema for {validation_id}")
    print("Daily batch tables ready (existing data was not changed)")


if __name__ == "__main__":
    setup(Config.from_env())
