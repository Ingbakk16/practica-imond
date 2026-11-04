from decimal import Decimal
from pathlib import Path
import sys
import unittest

import duckdb
from jinja2 import Environment
from sqlglot import exp, parse_one, transpile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from run_sql import create_raw_views


def render(path):
    sql = Environment().from_string(path.read_text()).render(ref=lambda name: f'"{name}"')
    return transpile(sql, read="bigquery", write="duckdb")[0]


class LookerModelTests(unittest.TestCase):
    def test_bigquery_where_clauses_have_a_from_source(self):
        sql = Environment().from_string((ROOT / "dbt/tests/looker_contracts.sql").read_text()).render(
            ref=lambda name: f'`{name}`'
        )
        for select in parse_one(sql, read="bigquery").find_all(exp.Select):
            if select.args.get("where"):
                self.assertIsNotNone(select.args.get("from_"))

    @classmethod
    def setUpClass(cls):
        cls.con = duckdb.connect(":memory:")
        create_raw_views(cls.con)
        for name in ("01_dimensiones.sql", "02_hechos.sql"):
            cls.con.execute((ROOT / "sql" / name).read_text())
        for path in sorted((ROOT / "dbt/models/presentation").glob("*.sql")):
            cls.con.execute(f'create table "{path.stem}" as {render(path)}')
        cls.contracts = render(ROOT / "dbt/tests/looker_contracts.sql")

    @classmethod
    def tearDownClass(cls):
        cls.con.close()

    def test_historical_metrics_and_null_distinct_semantics(self):
        self.assertEqual(self.con.execute(self.contracts).fetchall(), [])
        self.assertEqual(self.con.execute("""
            select sum(ventas_ars), sum(pedidos_venta), count(distinct cliente_comprador)
            from looker_ventas
        """).fetchone(), (Decimal("382410636.00"), 10998, 3194))
        self.assertEqual(self.con.execute("""
            select sum(ventas_producto_ars), sum(unidades_vendidas) from looker_productos
        """).fetchone(), (Decimal("309891600.00"), 23545))
        self.assertEqual(self.con.execute("""
            select sum(sesiones), sum(sesiones_anonimas), count(distinct usuario_identificado)
            from looker_sesiones
        """).fetchone(), (100363, 70751, 3077))
        self.assertEqual(self.con.execute("""
            select sum(respuestas), sum(promotores), sum(detractores),
                round(100.0 * (sum(promotores) - sum(detractores)) / sum(respuestas), 1)
            from looker_nps
        """).fetchone(), (3083, 1428, 503, 30.0))

    def test_january_and_channel_filters(self):
        self.assertEqual(self.con.execute("""
            select sum(pedidos_venta), sum(ventas_ars), count(distinct cliente_comprador)
            from looker_ventas where fecha between '2024-01-01' and '2024-01-31'
        """).fetchone(), (460, Decimal("15965464.50"), 431))
        self.assertEqual(self.con.execute("""
            select canal, round(100.0 * (sum(promotores) - sum(detractores)) / sum(respuestas), 1)
            from looker_nps group by canal order by canal
        """).fetchall(), [("OFFLINE", 40.9), ("ONLINE", 24.0)])

    def test_join_fanout_and_modified_amount_fail_contracts(self):
        self.con.execute("begin transaction")
        try:
            self.con.execute("insert into looker_ventas select * from looker_ventas limit 1")
            self.assertIn(("ventas",), self.con.execute(self.contracts).fetchall())
        finally:
            self.con.execute("rollback")
        self.con.execute("begin transaction")
        try:
            self.con.execute("update looker_productos set ventas_producto_ars = ventas_producto_ars + 1")
            self.assertIn(("productos",), self.con.execute(self.contracts).fetchall())
        finally:
            self.con.execute("rollback")

    def test_no_personal_information_is_exposed(self):
        for name in ("looker_ventas", "looker_productos", "looker_sesiones", "looker_nps"):
            fields = {row[0] for row in self.con.execute(f'describe "{name}"').fetchall()}
            self.assertTrue(fields.isdisjoint({"email", "first_name", "last_name", "comment", "address_id"}))

    def test_monthly_ranking_query_uses_selected_dates(self):
        sql = (ROOT / "lookerstudio/ranking_mensual.sql").read_text()
        sql = sql.replace("`PROJECT_ID.ecobottle_looker.looker_productos`", "`looker_productos`")
        sql = sql.replace("@DS_START_DATE", "'20240101'").replace("@DS_END_DATE", "'20240131'")
        query = transpile(sql, read="bigquery", write="duckdb")[0]
        rows = self.con.execute(query).fetchall()
        self.assertEqual(
            sorted((row[1], row[2], row[3]) for row in rows),
            [("Classic A Bottle", Decimal("5236200.00"), 2),
             ("Sport B Bottle", Decimal("7706250.00"), 1)],
        )


if __name__ == "__main__":
    unittest.main()
