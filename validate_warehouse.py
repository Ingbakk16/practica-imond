#!/usr/bin/env python3
"""Audita el warehouse ya construido sin modificar la base ni los CSV.

Uso: python validate_warehouse.py
Primero ejecutar generator/validate_raw.py y run_sql.py desde un estado limpio.
"""

from __future__ import annotations

import csv
import sys
from decimal import Decimal
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parent
EXPECTED = {
    "dim_channel": 2,
    "dim_customer": 3472,
    "dim_date": 639,
    "dim_product": 2,
    "dim_province": 4,
    "dim_store": 5,
    "fact_nps_response": 3083,
    "fact_sales_order": 11969,
    "fact_sales_order_item": 14573,
    "fact_web_session": 100363,
}


def sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


class Audit:
    def __init__(self, con: duckdb.DuckDBPyConnection) -> None:
        self.con = con
        self.failures = 0

    def check(self, description: str, valid: bool, detail: str = "") -> None:
        print(f"[{'OK' if valid else 'FALLA'}] {description}{': ' + detail if detail else ''}")
        if not valid:
            self.failures += 1

    def scalar(self, query: str):
        return self.con.sql(query).fetchone()[0]

    def exports(self) -> None:
        tables = [r[0] for r in self.con.sql(
            "SELECT table_name FROM duckdb_tables() "
            "WHERE database_name = current_database() AND schema_name = 'main' AND NOT internal "
            "ORDER BY table_name"
        ).fetchall()]
        self.check("Diez tablas del modelo", set(tables) == set(EXPECTED), ", ".join(tables))
        files = {p.stem for p in (ROOT / "dw").glob("*.csv")}
        self.check("Un CSV por tabla, sin archivos extra", files == set(tables))

        for table in tables:
            if table not in EXPECTED:
                continue
            path = ROOT / "dw" / f"{table}.csv"
            if not path.is_file():
                self.check(f"Exportación {table}", False, "falta el CSV")
                continue
            columns = self.con.sql(
                "SELECT column_name, data_type FROM duckdb_columns() "
                "WHERE database_name = current_database() AND schema_name = 'main' "
                f"AND table_name = {sql_string(table)} ORDER BY column_index"
            ).fetchall()
            with path.open(newline="", encoding="utf-8") as file:
                header = next(csv.reader(file), [])
            if header != [name for name, _ in columns]:
                self.check(f"Exportación {table}", False, "columnas u orden diferentes")
                continue
            mapping = "{" + ", ".join(
                f"{sql_string(name)}: {sql_string(data_type)}" for name, data_type in columns
            ) + "}"
            csv_query = (
                f"read_csv({sql_string(path.as_posix())}, header = true, "
                f"columns = {mapping}, nullstr = '')"
            )
            db_query = f"main.{identifier(table)}"
            try:
                count = self.scalar(f"SELECT COUNT(*) FROM {db_query}")
                csv_count = self.scalar(f"SELECT COUNT(*) FROM {csv_query}")
                missing = self.scalar(
                    f"SELECT COUNT(*) FROM (SELECT * FROM {db_query} EXCEPT ALL "
                    f"SELECT * FROM {csv_query})"
                )
                extra = self.scalar(
                    f"SELECT COUNT(*) FROM (SELECT * FROM {csv_query} EXCEPT ALL "
                    f"SELECT * FROM {db_query})"
                )
            except duckdb.Error as error:
                self.check(f"Exportación {table}", False, str(error).splitlines()[0])
                continue
            self.check(
                f"Exportación {table}",
                count == EXPECTED[table] and csv_count == count and missing == extra == 0,
                f"BD={count}, CSV={csv_count}, faltantes={missing}, sobrantes={extra}",
            )

    def constraints_and_diagram(self) -> None:
        constraints = self.con.sql(
            "SELECT table_name, constraint_type, constraint_column_names, "
            "referenced_table, referenced_column_names FROM duckdb_constraints() "
            "WHERE database_name = current_database() AND schema_name = 'main' "
            "AND constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY')"
        ).fetchall()
        pks = [row for row in constraints if row[1] == "PRIMARY KEY"]
        fks = [row for row in constraints if row[1] == "FOREIGN KEY"]
        self.check("PK en las diez tablas y 16 FK declaradas", len(pks) == 10 and len(fks) == 16)

        path = ROOT / "dw" / "modelo_estrella.md"
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        self.check("Diagrama con entidades y relaciones", bool(text) and all(
            f"    {name} {{" in text for name in EXPECTED
        ) and all(
            f'    {ref} ||--o{{ {table} : "{", ".join(cols)}"' in text
            for table, kind, cols, ref, target in fks
        ))

        for table, kind, cols, ref, target in fks:
            join = " AND ".join(
                f"f.{identifier(column)} = d.{identifier(parent)}"
                for column, parent in zip(cols, target)
            )
            missing = self.scalar(
                f"SELECT COUNT(*) FROM main.{identifier(table)} AS f "
                f"LEFT JOIN main.{identifier(ref)} AS d ON {join} "
                f"WHERE d.{identifier(target[0])} IS NULL"
            )
            self.check(f"Sin huérfanos: {table}.{', '.join(cols)} → {ref}", missing == 0)

    def business_rules(self) -> None:
        con = self.con
        summary = con.sql(
            "SELECT COUNT(*), COUNT(*) FILTER (WHERE es_venta), SUM(venta_neta) "
            "FROM fact_sales_order"
        ).fetchone()
        self.check("Ventas del origen y del warehouse", summary == (
            11969, 10998, Decimal("382410636.00")
        ), str(summary))
        cases = con.sql(
            "SELECT status, COUNT(*), SUM(venta_neta) FROM fact_sales_order "
            "GROUP BY status ORDER BY status"
        ).fetchall()
        counts = {status: count for status, count, total in cases}
        expected_counts = {
            "CANCELLED": 658, "CREATED": 1, "FULFILLED": 10938,
            "PAID": 60, "REFUNDED": 312,
        }
        self.check("Estados cancelados, creados y reembolsados sin venta",
                   counts == expected_counts and all(
                       total == 0 for status, count, total in cases
                       if status in ("CANCELLED", "CREATED", "REFUNDED")
                   ), str(cases))

        sessions = con.sql(
            "SELECT COUNT(*) FILTER (WHERE customer_key = -1), "
            "COUNT(*) FILTER (WHERE ended_at IS NULL AND duration_seconds IS NULL), "
            "COUNT(*) FILTER (WHERE ended_at IS NOT NULL AND duration_seconds IS NULL) "
            "FROM fact_web_session"
        ).fetchone()
        self.check("Sesiones anónimas y sin cierre", sessions == (70751, 3024, 0), str(sessions))
        responses = con.sql(
            "SELECT COUNT(*), COUNT(*) FILTER (WHERE customer_key = -1), "
            "COUNT(*) FILTER (WHERE score >= 9), COUNT(*) FILTER (WHERE score <= 6) "
            "FROM fact_nps_response"
        ).fetchone()
        self.check("NPS y respuestas anónimas", responses == (3083, 122, 1428, 503), str(responses))
        unknowns = con.sql(
            "SELECT (SELECT COUNT(*) FROM fact_sales_order WHERE customer_key = -1), "
            "(SELECT COUNT(*) FROM fact_sales_order_item WHERE customer_key = -1), "
            "(SELECT COUNT(*) FROM fact_sales_order WHERE store_key = -1)"
        ).fetchone()
        self.check("Clientes conocidos en ventas y tienda nula online", unknowns == (0, 0, 7286))


def main() -> int:
    database = ROOT / "warehouse.duckdb"
    if not database.is_file():
        print("Falta warehouse.duckdb: ejecutá primero python run_sql.py")
        return 1
    try:
        con = duckdb.connect(str(database), read_only=True)
        audit = Audit(con)
        audit.exports()
        audit.constraints_and_diagram()
        audit.business_rules()
        con.close()
    except (duckdb.Error, OSError) as error:
        print(f"ERROR de auditoría: {error}")
        return 1
    print(f"\n{'Auditoría OK' if audit.failures == 0 else f'{audit.failures} controles fallaron'}")
    return 1 if audit.failures else 0


if __name__ == "__main__":
    sys.exit(main())
