#!/usr/bin/env python3
"""Mark one daily batch only after dbt and both reconciliations succeed."""

import argparse

from google.cloud import bigquery

from config import Config


def mark(day, config):
    client = config.client()
    marker = f"{config.project}.ecobottle_ops.daily_batches"
    validations = f"{config.project}.ecobottle_ops.daily_validations"
    params = [bigquery.ScalarQueryParameter("day", "STRING", day)]
    rows = config.query(client, f"SELECT fingerprint FROM `{marker}` WHERE batch_id = @day AND status = 'complete'", params)
    if len(rows) != 1:
        raise ValueError(f"Batch {day} is not uniquely complete")
    fingerprint = rows[0].fingerprint
    config.query(client, f"""
        MERGE `{validations}` AS target
        USING (SELECT @day AS batch_id, @fingerprint AS fingerprint) AS source
        ON target.batch_id = source.batch_id
        WHEN MATCHED THEN UPDATE SET fingerprint = source.fingerprint, validated_at = CURRENT_TIMESTAMP()
        WHEN NOT MATCHED THEN INSERT (batch_id, fingerprint, validated_at)
          VALUES (source.batch_id, source.fingerprint, CURRENT_TIMESTAMP())
    """, [*params, bigquery.ScalarQueryParameter("fingerprint", "STRING", fingerprint)])
    print(f"Daily batch {day} validated after dbt and reconciliation")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    mark(args.date, Config.from_env())
