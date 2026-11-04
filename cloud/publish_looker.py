#!/usr/bin/env python3
"""Publish the last validated build for Looker Studio, with atomic data replacement.

Run only after dbt build AND historical/daily reconciliation. This command does
not create datasets, change IAM, or authenticate on behalf of report viewers.
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import uuid

from google.cloud import bigquery

from config import Config


SOURCES = {
    "looker_ventas": (
        "order_id", "fecha", "customer_key", "canal", "provincia", "tienda",
        "estado_cliente", "estado_pedido", "ventas_ars", "pedidos_venta", "cliente_comprador",
    ),
    "looker_productos": (
        "order_item_id", "order_id", "fecha", "canal", "provincia", "tienda", "producto",
        "categoria", "familia", "ventas_producto_ars", "unidades_vendidas",
    ),
    "looker_sesiones": (
        "session_id", "fecha", "fuente", "dispositivo", "usuario_identificado",
        "sesiones", "sesiones_anonimas", "duracion_segundos",
    ),
    "looker_nps": (
        "nps_id", "fecha", "canal", "puntaje", "respuestas", "promotores", "detractores", "pasivos",
    ),
}
PUBLICATION_FIELDS = [
    bigquery.SchemaField("publication_id", "STRING"),
    bigquery.SchemaField("published_at", "TIMESTAMP"),
]
STATUS_SCHEMA = [
    bigquery.SchemaField("fuente", "STRING"),
    bigquery.SchemaField("filas", "INTEGER"),
    bigquery.SchemaField("primera_fecha", "DATE"),
    bigquery.SchemaField("ultima_fecha", "DATE"),
    bigquery.SchemaField("ultimo_lote_validado", "DATE"),
    *PUBLICATION_FIELDS,
]


def check_build(path, now=None):
    """Fail closed on missing/stale/failed dbt artifacts, before any cloud write."""
    artifact = json.loads(Path(path).read_text())
    generated = datetime.fromisoformat(artifact["metadata"]["generated_at"].replace("Z", "+00:00"))
    now = now or datetime.now(timezone.utc)
    if generated.tzinfo is None or not timedelta(0) <= now - generated <= timedelta(hours=2):
        raise ValueError("dbt run_results must be from the successful build in the last two hours")
    results = artifact["results"]
    if not results or any(result["status"] not in ("success", "pass") for result in results):
        raise ValueError("dbt build contains failures, warnings, or skipped nodes")
    passed = {result["unique_id"] for result in results}
    required = {f"model.ecobottle.{name}" for name in SOURCES} | {"test.ecobottle.looker_contracts"}
    if not required <= passed:
        raise ValueError("Run a full dbt build including all Looker sources and looker_contracts")


def schema_signature(schema):
    return [(field.name, field.field_type, field.mode) for field in schema]


def publication_sql(project):
    """All four datasets of rows and their freshness metadata commit together."""
    ops = f"{project}.ecobottle_ops"
    target = f"{project}.ecobottle_looker"
    statements = [f"""
BEGIN TRANSACTION;
ASSERT NOT EXISTS (
    SELECT b.batch_id
    FROM `{ops}.daily_batches` AS b
    LEFT JOIN `{ops}.daily_validations` AS v
      ON v.batch_id = b.batch_id AND v.fingerprint = b.fingerprint
    GROUP BY b.batch_id
    HAVING COUNT(*) <> 1 OR COUNTIF(b.status = 'complete' AND v.validated_at IS NOT NULL) <> 1
) AS 'Every daily batch must be uniquely complete and reconciled before publication';
DELETE FROM `{target}.actualizacion` WHERE TRUE;
"""]
    for name, fields in SOURCES.items():
        candidate = f"{project}.ecobottle_analytics.{name}"
        columns = ", ".join(f"`{field}`" for field in fields)
        statements.append(f"""
DELETE FROM `{target}.{name}` WHERE TRUE;
INSERT INTO `{target}.{name}` ({columns}, publication_id, published_at)
SELECT {columns}, @publication_id, CURRENT_TIMESTAMP() FROM `{candidate}`;
INSERT INTO `{target}.actualizacion`
    (fuente, filas, primera_fecha, ultima_fecha, ultimo_lote_validado, publication_id, published_at)
SELECT '{name}', COUNT(*), MIN(fecha), MAX(fecha),
    (SELECT MAX(SAFE_CAST(batch_id AS DATE)) FROM `{ops}.daily_validations`),
    @publication_id, CURRENT_TIMESTAMP()
FROM `{candidate}`;
""")
    statements.append("COMMIT TRANSACTION;")
    return "\n".join(statements)


def publish(config, run_results):
    check_build(run_results)
    client = config.client()
    # Provision explicitly outside the transaction: BigQuery doesn't allow
    # permanent table DDL within it. Existing data is never cleared here.
    for dataset in ("ecobottle_analytics", "ecobottle_looker", "ecobottle_ops"):
        if client.get_dataset(f"{config.project}.{dataset}").location.upper() != config.location.upper():
            raise ValueError(f"Dataset {dataset} must be in {config.location}")
    schemas = {}
    for name, fields in SOURCES.items():
        table = client.get_table(f"{config.project}.ecobottle_analytics.{name}")
        if tuple(field.name for field in table.schema) != fields:
            raise ValueError(f"Unexpected candidate columns: {name}; migrate the contract explicitly")
        schemas[name] = [*table.schema, *PUBLICATION_FIELDS]
    schemas["actualizacion"] = STATUS_SCHEMA
    # Check every existing target before issuing any CREATE. No schema autodrift.
    existing = {table.table_id for table in client.list_tables(f"{config.project}.ecobottle_looker")}
    for name, schema in schemas.items():
        if name in existing:
            table = client.get_table(f"{config.project}.ecobottle_looker.{name}")
            if table.table_type != "TABLE" or schema_signature(table.schema) != schema_signature(schema):
                raise ValueError(f"Unexpected published schema: {name}; no data was replaced")
    for name, schema in schemas.items():
        if name not in existing:
            client.create_table(bigquery.Table(f"{config.project}.ecobottle_looker.{name}", schema=schema))
    publication_id = str(uuid.uuid4())
    config.query(client, publication_sql(config.project), [
        bigquery.ScalarQueryParameter("publication_id", "STRING", publication_id),
    ])
    print(f"Looker publication {publication_id} committed to {config.project}.ecobottle_looker")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-results", default="dbt/target/run_results.json")
    args = parser.parse_args()
    publish(Config.from_env(), args.run_results)
