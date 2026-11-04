#!/usr/bin/env python3
"""Read-only acceptance checks for the published Looker sources.

Run after publish_looker.py. A failed check exits nonzero and preserves the
published data. --expected-date checks the scheduled business-day watermark.
"""

import argparse
from datetime import date
import json
from pathlib import Path

from google.cloud import bigquery

from config import Config
from publish_looker import SOURCES


def acceptance_sql(project, expected_date=False):
    dataset = f"{project}.ecobottle_looker"
    status = f"`{dataset}.actualizacion`"
    checks = []

    def check(name, condition):
        checks.append(f"SELECT '{name}' AS control FROM (SELECT 1) AS singleton WHERE {condition}")

    sources = ", ".join(f"'{name}'" for name in SOURCES)
    check("publication_metadata", f"""
        (SELECT COUNT(*) FROM {status}) <> 4
        OR (SELECT COUNT(DISTINCT fuente) FROM {status} WHERE fuente IN ({sources})) <> 4
        OR (SELECT COUNT(DISTINCT publication_id) FROM {status}) <> 1
        OR (SELECT COUNT(*) FROM {status} WHERE publication_id IS NULL OR published_at IS NULL) <> 0
        OR (SELECT COUNT(DISTINCT published_at) FROM {status}) <> 1
        OR (SELECT MIN(published_at) FROM {status}) < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 2 HOUR)
        OR (SELECT MAX(published_at) FROM {status}) > CURRENT_TIMESTAMP()
    """)
    for name, fields in SOURCES.items():
        table = f"`{dataset}.{name}`"
        check(f"published_{name}", f"""
            (SELECT COUNT(*) - COUNT(DISTINCT {fields[0]}) FROM {table}) <> 0
            OR (SELECT COUNT(*) FROM {table}) IS DISTINCT FROM
                (SELECT filas FROM {status} WHERE fuente = '{name}' LIMIT 1)
            OR (SELECT MIN(fecha) FROM {table}) IS DISTINCT FROM
                (SELECT primera_fecha FROM {status} WHERE fuente = '{name}' LIMIT 1)
            OR (SELECT MAX(fecha) FROM {table}) IS DISTINCT FROM
                (SELECT ultima_fecha FROM {status} WHERE fuente = '{name}' LIMIT 1)
            OR EXISTS (
                SELECT 1 FROM {table} AS t
                WHERE t.publication_id IS DISTINCT FROM
                    (SELECT publication_id FROM {status} WHERE fuente = '{name}' LIMIT 1)
                   OR t.published_at IS DISTINCT FROM
                    (SELECT published_at FROM {status} WHERE fuente = '{name}' LIMIT 1)
            )
        """)

    historical = "fecha BETWEEN DATE '2024-01-01' AND DATE '2025-09-30'"
    metrics = {
        "looker_ventas": {
            "COUNT(*)": "11969",
            "SUM(ventas_ars)": "382410636.00",
            "SUM(pedidos_venta)": "10998",
            "COUNT(DISTINCT cliente_comprador)": "3194",
        },
        "looker_productos": {
            "COUNT(*)": "14573",
            "SUM(ventas_producto_ars)": "309891600.00",
            "SUM(unidades_vendidas)": "23545",
        },
        "looker_sesiones": {
            "COUNT(*)": "100363",
            "SUM(sesiones)": "100363",
            "SUM(sesiones_anonimas)": "70751",
            "COUNT(DISTINCT usuario_identificado)": "3077",
        },
        "looker_nps": {
            "COUNT(*)": "3083",
            "SUM(respuestas)": "3083",
            "SUM(promotores)": "1428",
            "SUM(detractores)": "503",
        },
    }
    for name, expressions in metrics.items():
        conditions = [
            f"(SELECT {expression} FROM `{dataset}.{name}` WHERE {historical}) IS DISTINCT FROM {expected}"
            for expression, expected in expressions.items()
        ]
        check(f"historical_{name}", " OR ".join(conditions))

    ops = f"{project}.ecobottle_ops"
    check("unvalidated_batches", f"""EXISTS (
        SELECT b.batch_id FROM `{ops}.daily_batches` AS b
        LEFT JOIN `{ops}.daily_validations` AS v
          ON b.batch_id = v.batch_id AND b.fingerprint = v.fingerprint
        GROUP BY b.batch_id
        HAVING COUNT(*) <> 1 OR COUNTIF(b.status = 'complete' AND v.validated_at IS NOT NULL) <> 1
    )""")
    check("published_watermark", f"""EXISTS (
        SELECT 1 FROM {status}
        WHERE ultimo_lote_validado IS DISTINCT FROM
            (SELECT MAX(SAFE_CAST(batch_id AS DATE)) FROM `{ops}.daily_validations`)
    )""")
    if expected_date:
        check("expected_business_date", f"""
            (SELECT MIN(ultimo_lote_validado) FROM {status}) IS DISTINCT FROM @expected_date
        """)
    return "\nUNION ALL\n".join(checks)


def verify(config, expected_date=None, output=None):
    parameters = []
    if expected_date is not None:
        parameters.append(bigquery.ScalarQueryParameter("expected_date", "DATE", expected_date))
    rows = config.query(config.client(), acceptance_sql(config.project, expected_date is not None), parameters)
    failures = [row["control"] for row in rows]
    report = {"project": config.project, "expected_date": str(expected_date) if expected_date else None,
              "passed": not failures, "failed_controls": failures}
    if output:
        Path(output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if failures:
        raise ValueError("Looker acceptance failed: " + ", ".join(failures))
    print("Looker acceptance OK: publication metadata, historical KPIs and validated batches.")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-date", type=date.fromisoformat)
    parser.add_argument("--out", help="Write the acceptance result as JSON for the workflow artifact")
    args = parser.parse_args()
    verify(Config.from_env(), args.expected_date, args.out)
