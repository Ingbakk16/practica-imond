#!/usr/bin/env python3
"""Rebuild dbt after terminal BigQuery backend errors, with bounded retries.

Each attempt is a full build so publication receives a complete run_results.
Never retry data-test failures, SQL errors, configuration errors or stale results.
"""

import argparse
import json
from pathlib import Path
import re
import subprocess
import time


TRANSIENT = re.compile(
    r"\b(?:backendError|internalError)\b|"
    r"\b(?:500|502|503|504)\s+(?:Error|Internal Server Error|Bad Gateway|Service Unavailable|Gateway Timeout)",
    re.IGNORECASE,
)


def retryable_results(path, started):
    try:
        path = Path(path)
        if path.stat().st_mtime < started:
            return False
        results = json.loads(path.read_text(encoding="utf-8"))["results"]
    except (OSError, ValueError, KeyError, TypeError):
        return False
    if not isinstance(results, list) or not all(isinstance(row, dict) for row in results):
        return False
    errors = [row for row in results if row.get("status") == "error"]
    if not errors or any(row.get("status") not in ("success", "pass", "skipped", "error") for row in results):
        return False
    return all(TRANSIENT.search(row.get("message") or "") for row in errors)


def build(project_dir="dbt", *, attempts=3, runner=subprocess.run, sleep=time.sleep, clock=time.time):
    if attempts < 1 or attempts > 3:
        raise ValueError("Use between one and three attempts")
    results = Path(project_dir) / "target" / "run_results.json"
    for attempt in range(1, attempts + 1):
        started = clock()
        print(f"dbt full build attempt {attempt}/{attempts}", flush=True)
        result = runner(["dbt", "build"], cwd=project_dir)
        if result.returncode == 0:
            return 0
        if attempt == attempts or not retryable_results(results, started):
            return result.returncode
        delay = 15 * (2 ** (attempt - 1))
        print(f"BigQuery backend failure; retrying full build in {delay}s with new jobs.", flush=True)
        sleep(delay)
    raise AssertionError("Unreachable")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", default="dbt")
    args = parser.parse_args()
    raise SystemExit(build(args.project_dir))
