"""Shared configuration for the small BigQuery demo (Application Default Credentials)."""

import os
import re
from dataclasses import dataclass

from google.cloud import bigquery


@dataclass(frozen=True)
class Config:
    project: str
    location: str
    maximum_bytes_billed: int

    @classmethod
    def from_env(cls):
        project = os.environ.get("GCP_PROJECT_ID", "")
        if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", project):
            raise ValueError("Set GCP_PROJECT_ID to your Google Cloud project ID.")
        return cls(
            project,
            os.environ.get("BQ_LOCATION", "US"),
            int(os.environ.get("BQ_MAX_BYTES_BILLED", "1000000000")),
        )

    def client(self):
        return bigquery.Client(project=self.project, location=self.location)

    def query(self, client, sql, parameters=()):
        job = client.query(sql, job_config=bigquery.QueryJobConfig(
            maximum_bytes_billed=self.maximum_bytes_billed,
            query_parameters=list(parameters),
        ))
        rows = list(job.result(timeout=300))
        print(f"BigQuery job {job.job_id}: {job.total_bytes_processed or 0} bytes processed")
        return rows
