#!/usr/bin/env python3
"""Valida que los CSV de raw/ respeten las reglas del sistema de origen de EcoBottle.

Uso:
    python generator/validate_raw.py              # valida raw/
    python generator/validate_raw.py --dir tmp/   # valida otra carpeta

Imprime cada regla con OK/FALLA y, al final, los KPIs mensuales esperados
(útiles para comparar contra el dashboard). Sale con código 1 si algo falla.
Solo usa la biblioteca estándar (Python 3.9+).
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from generate_raw import END, FREE_SHIPPING_FROM, HOLIDAYS, SHIPPING_FEE, SNAPSHOT, START_DT, TAX_RATE

TABLES = {
    "channel": "channel_id", "province": "province_id", "product_category": "category_id",
    "customer": "customer_id", "address": "address_id", "store": "store_id", "product": "product_id",
    "sales_order": "order_id", "sales_order_item": "order_item_id", "payment": "payment_id",
    "shipment": "shipment_id", "web_session": "session_id", "nps_response": "nps_id",
}
FOREIGN_KEYS = [
    ("address", "province_id", "province"), ("store", "address_id", "address"),
    ("product", "category_id", "product_category"), ("product_category", "parent_id", "product_category"),
    ("sales_order", "customer_id", "customer"), ("sales_order", "channel_id", "channel"),
    ("sales_order", "store_id", "store"), ("sales_order", "billing_address_id", "address"),
    ("sales_order", "shipping_address_id", "address"), ("sales_order_item", "order_id", "sales_order"),
    ("sales_order_item", "product_id", "product"), ("payment", "order_id", "sales_order"),
    ("shipment", "order_id", "sales_order"), ("web_session", "customer_id", "customer"),
    ("nps_response", "customer_id", "customer"), ("nps_response", "channel_id", "channel"),
]
DOMAINS = [
    ("customer", "status", {"A", "I"}), ("product", "status", {"A", "I"}),
    ("sales_order", "status", {"CREATED", "PAID", "CANCELLED", "FULFILLED", "REFUNDED"}),
    ("sales_order", "currency_code", {"ARS"}), ("address", "country_code", {"AR"}),
    ("payment", "method", {"CASH", "CARD", "TRANSFER", "GATEWAY"}),
    ("payment", "status", {"PENDING", "PAID", "FAILED", "REFUNDED"}),
    ("shipment", "status", {"READY", "SHIPPED", "DELIVERED", "CANCELLED"}),
]
# (estado pedido, estado pago, estado envío) válidos. None = sin envío.
VALID_STATES = {
    ("CREATED", "PENDING", None),
    ("CANCELLED", "FAILED", None),
    ("CANCELLED", "REFUNDED", "CANCELLED"),
    ("PAID", "PAID", "READY"),
    ("PAID", "PAID", "SHIPPED"),
    ("FULFILLED", "PAID", "DELIVERED"),
    ("FULFILLED", "PAID", None),       # venta en tienda
    ("REFUNDED", "REFUNDED", "DELIVERED"),
    ("REFUNDED", "REFUNDED", None),    # devolución en tienda
}


def ts(value: str) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def num(value: str) -> float:
    return float(value)


def iid(value: str) -> int | None:
    return int(value) if value else None


class Report:
    def __init__(self) -> None:
        self.failures = 0

    def check(self, rule: str, bad: list) -> None:
        if bad:
            self.failures += 1
            sample = ", ".join(str(b) for b in bad[:5])
            print(f"  [FALLA] {rule}: {len(bad)} casos (ej.: {sample})")
        else:
            print(f"  [OK]    {rule}")


def load(folder: Path) -> dict:
    data = {}
    for name in TABLES:
        with open(folder / f"{name}.csv", newline="", encoding="utf-8") as f:
            data[name] = list(csv.DictReader(f))
    return data


def validate(d: dict, r: Report, snapshot: datetime = SNAPSHOT, end=None) -> None:
    end = end or END
    by_id = {name: {row[pk]: row for row in d[name]} for name, pk in TABLES.items()}
    orders, items, pays, ships = d["sales_order"], d["sales_order_item"], d["payment"], d["shipment"]
    customers, addresses, sessions, nps = by_id["customer"], by_id["address"], d["web_session"], d["nps_response"]
    store_address = {s["store_id"]: s["address_id"] for s in d["store"]}
    list_price = {p["product_id"]: num(p["list_price"]) for p in d["product"]}

    print("\nIntegridad")
    for name, pk in TABLES.items():
        values = [row[pk] for row in d[name]]
        dup = [v for v, n in Counter(values).items() if n > 1 or not v]
        r.check(f"PK única y no nula: {name}.{pk}", dup)
    for table, col, ref in FOREIGN_KEYS:
        orphans = [row[col] for row in d[table] if row[col] and row[col] not in by_id[ref]]
        r.check(f"FK {table}.{col} -> {ref}", orphans)
    for table, col, allowed in DOMAINS:
        r.check(f"Dominio {table}.{col}", [row[col] for row in d[table] if row[col] not in allowed])
    r.check("nps_response.score entre 0 y 10", [n["nps_id"] for n in nps if not 0 <= int(n["score"]) <= 10])
    r.check("sales_order_item.quantity > 0", [i["order_item_id"] for i in items if int(i["quantity"]) <= 0])
    for table, col in [("customer", "email"), ("product", "sku"), ("province", "code"), ("channel", "code")]:
        dup = [v for v, n in Counter(row[col] for row in d[table]).items() if n > 1]
        r.check(f"UNIQUE {table}.{col}", dup)
    r.check("Emails en ASCII", [c["email"] for c in d["customer"] if not c["email"].isascii()])

    print("\nMontos")
    lines = defaultdict(list)
    for i in items:
        lines[i["order_id"]].append(i)
    r.check("line_total = quantity * unit_price - discount_amount",
            [i["order_item_id"] for i in items
             if abs(int(i["quantity"]) * num(i["unit_price"]) - num(i["discount_amount"]) - num(i["line_total"])) > 0.01])
    r.check("unit_price = product.list_price",
            [i["order_item_id"] for i in items if num(i["unit_price"]) != list_price[i["product_id"]]])
    r.check("Una línea por producto en cada pedido",
            [k for k, n in Counter((i["order_id"], i["product_id"]) for i in items).items() if n > 1])
    r.check("Todo pedido tiene ítems", [o["order_id"] for o in orders if o["order_id"] not in lines])
    r.check("subtotal = suma de line_total",
            [o["order_id"] for o in orders
             if abs(sum(num(i["line_total"]) for i in lines[o["order_id"]]) - num(o["subtotal"])) > 0.01])
    r.check(f"tax_amount = {TAX_RATE:.0%} del subtotal",
            [o["order_id"] for o in orders if abs(round(num(o["subtotal"]) * TAX_RATE, 2) - num(o["tax_amount"])) > 0.01])
    r.check("total_amount = subtotal + tax_amount + shipping_fee",
            [o["order_id"] for o in orders
             if abs(num(o["subtotal"]) + num(o["tax_amount"]) + num(o["shipping_fee"]) - num(o["total_amount"])) > 0.01])

    print("\nPedidos, pagos y envíos")
    pay_by_order = defaultdict(list)
    for p in pays:
        pay_by_order[p["order_id"]].append(p)
    ship_by_order = defaultdict(list)
    for s in ships:
        ship_by_order[s["order_id"]].append(s)
    r.check("store_id nulo solo en ONLINE",
            [o["order_id"] for o in orders if (o["channel_id"] == "1") != (o["store_id"] == "")])
    in_store = [o for o in orders if o["store_id"] and o["shipping_address_id"] == store_address[o["store_id"]]]
    r.check("Venta en tienda (envío = dirección de la tienda): sin costo ni registro de envío",
            [o["order_id"] for o in in_store if num(o["shipping_fee"]) != 0 or ship_by_order[o["order_id"]]])
    in_store_ids = {o["order_id"] for o in in_store}
    r.check("ONLINE nunca envía a la dirección de una tienda",
            [o["order_id"] for o in orders if o["channel_id"] == "1" and o["shipping_address_id"] in store_address.values()])
    fee_bad = []
    for o in orders:
        if o["order_id"] in in_store_ids:
            continue
        fee, expected = num(o["shipping_fee"]), SHIPPING_FEE[int(addresses[o["shipping_address_id"]]["province_id"])]
        if fee not in (0, expected) or (num(o["subtotal"]) >= FREE_SHIPPING_FROM and fee != 0):
            fee_bad.append(o["order_id"])
    r.check(f"shipping_fee según provincia destino (gratis desde ${FREE_SHIPPING_FROM:,.0f} o en campañas)", fee_bad)
    r.check("Un pago por pedido", [k for k in by_id["sales_order"] if len(pay_by_order[k]) != 1])
    r.check("Como máximo un envío por pedido", [k for k, v in ship_by_order.items() if len(v) > 1])
    r.check("payment.amount = total_amount",
            [p["payment_id"] for p in pays if num(p["amount"]) != num(by_id["sales_order"][p["order_id"]]["total_amount"])])
    states = []
    for o in orders:
        pay = pay_by_order[o["order_id"]][0]
        ship = ship_by_order[o["order_id"]][0]["status"] if ship_by_order[o["order_id"]] else None
        if (o["status"], pay["status"], ship) not in VALID_STATES:
            states.append((o["order_id"], o["status"], pay["status"], ship))
    r.check("Estados coherentes entre pedido, pago y envío", states)
    r.check("ONLINE pagado siempre tiene envío",
            [o["order_id"] for o in orders if o["channel_id"] == "1"
             and o["status"] in ("PAID", "FULFILLED", "REFUNDED") and not ship_by_order[o["order_id"]]])
    r.check("paid_at y transaction_ref solo si el pago se concretó",
            [p["payment_id"] for p in pays
             if bool(p["paid_at"]) != (p["status"] in ("PAID", "REFUNDED"))
             or (p["transaction_ref"] and not p["paid_at"])
             or (p["paid_at"] and p["method"] != "CASH" and not p["transaction_ref"])])
    methods = {"1": {"CARD", "GATEWAY"}, "2": {"CASH", "CARD", "TRANSFER"}}
    r.check("Métodos de pago: ONLINE tarjeta o Mercado Pago, tienda efectivo/tarjeta/transferencia",
            [p["payment_id"] for p in pays if p["method"] not in methods[by_id["sales_order"][p["order_id"]]["channel_id"]]])
    r.check("paid_at >= order_date",
            [p["payment_id"] for p in pays if p["paid_at"] and ts(p["paid_at"]) < ts(by_id["sales_order"][p["order_id"]]["order_date"])])
    r.check("En tienda el pago es inmediato (< 5 min)",
            [p["payment_id"] for p in pays if p["paid_at"] and by_id["sales_order"][p["order_id"]]["channel_id"] == "2"
             and ts(p["paid_at"]) - ts(by_id["sales_order"][p["order_id"]]["order_date"]) > timedelta(minutes=5)])
    bad_ship = []
    for s in ships:
        shipped, delivered = ts(s["shipped_at"]), ts(s["delivered_at"])
        expected = {"READY": (False, False), "SHIPPED": (True, False),
                    "DELIVERED": (True, True), "CANCELLED": (False, False)}[s["status"]]
        paid_at = ts(pay_by_order[s["order_id"]][0]["paid_at"])
        if ((shipped is not None, delivered is not None) != expected
                or bool(s["tracking_number"]) != (shipped is not None)
                or (shipped and paid_at and shipped < paid_at)
                or (delivered and delivered <= shipped)):
            bad_ship.append(s["shipment_id"])
    r.check("Fechas y tracking del envío coherentes con su estado (despacho después del pago)", bad_ship)

    print("\nCoherencia temporal")
    all_ts = [(name, row[col]) for name, cols in [
        ("customer", ["created_at"]), ("address", ["created_at"]), ("sales_order", ["order_date"]),
        ("payment", ["paid_at"]), ("shipment", ["shipped_at", "delivered_at"]),
        ("web_session", ["started_at", "ended_at"]), ("nps_response", ["responded_at"])]
        for row in d[name] for col in cols if row[col] and ts(row[col]) > snapshot]
    r.check(f"Nada posterior al corte ({snapshot})", all_ts)
    r.check("Pedidos dentro del período",
            [o["order_id"] for o in orders if not START_DT <= ts(o["order_date"]) <= snapshot or ts(o["order_date"]).date() > end])
    r.check("Pedido posterior al alta del cliente",
            [o["order_id"] for o in orders if ts(o["order_date"]) < ts(customers[o["customer_id"]]["created_at"])])
    r.check("Direcciones del pedido creadas antes del pedido",
            [o["order_id"] for o in orders for col in ("billing_address_id", "shipping_address_id")
             if o[col] and ts(addresses[o[col]]["created_at"]) > ts(o["order_date"])])
    r.check("Sesiones identificadas posteriores al alta del cliente",
            [s["session_id"] for s in sessions if s["customer_id"] and ts(s["started_at"]) < ts(customers[s["customer_id"]]["created_at"])])
    r.check("ended_at >= started_at",
            [s["session_id"] for s in sessions if s["ended_at"] and ts(s["ended_at"]) < ts(s["started_at"])])
    r.check("Ventas en tienda en horario comercial (lun a sáb, 10 a 21 h, sin feriados)",
            [o["order_id"] for o in orders if o["channel_id"] == "2"
             and (ts(o["order_date"]).weekday() == 6 or not 10 <= ts(o["order_date"]).hour <= 20
                  or ts(o["order_date"]).date() in HOLIDAYS)])
    owners = defaultdict(set)
    for o in orders:
        for col in ("billing_address_id", "shipping_address_id"):
            if o[col] and int(o[col]) > 1000:
                owners[o[col]].add(o["customer_id"])
    r.check("Cada dirección de cliente pertenece a un solo cliente", [a for a, c in owners.items() if len(c) > 1])
    sess_by_customer = defaultdict(list)
    for s in sessions:
        if s["customer_id"]:
            sess_by_customer[s["customer_id"]].append((ts(s["started_at"]), ts(s["ended_at"])))
    no_session = []
    for o in orders:
        if o["channel_id"] != "1":
            continue
        t = ts(o["order_date"])
        if not any(start <= t and (end is None or t <= end) for start, end in sess_by_customer[o["customer_id"]]):
            no_session.append(o["order_id"])
    r.check("Cada pedido ONLINE ocurre dentro de una sesión web del cliente", no_session)
    delivered = defaultdict(list)
    for o in orders:
        if o["status"] in ("FULFILLED", "REFUNDED"):
            s = ship_by_order[o["order_id"]]
            done = ts(s[0]["delivered_at"]) if s else ts(o["order_date"])
            wait = timedelta(days=7) if s else timedelta(days=1)  # la encuesta sale a las 10 h de ese día
            delivered[(o["customer_id"], o["channel_id"])].append(done.date() + wait)
    r.check("NPS respondido después de la entrega (7 días) o de la compra en tienda (día siguiente)",
            [n["nps_id"] for n in nps if n["customer_id"]
             and not any(t <= ts(n["responded_at"]).date() for t in delivered[(n["customer_id"], n["channel_id"])])])
    last_order = {}
    for o in orders:
        last_order[o["customer_id"]] = max(last_order.get(o["customer_id"], ts(o["order_date"])), ts(o["order_date"]))
    r.check("Clientes inactivos sin compras en los últimos 90 días",
            [c for c, row in customers.items() if row["status"] == "I" and c in last_order
              and last_order[c] > snapshot - timedelta(days=90)])


def summary(d: dict) -> None:
    """KPIs mensuales según las definiciones de la consigna."""
    month = lambda value: value[:7]
    orders = {o["order_id"]: o for o in d["sales_order"]}
    sales = defaultdict(float)
    count = Counter()
    for o in orders.values():
        if o["status"] in ("PAID", "FULFILLED"):
            sales[month(o["order_date"])] += num(o["total_amount"])
            count[month(o["order_date"])] += 1
    users, anon = defaultdict(set), Counter()
    for s in d["web_session"]:
        if s["customer_id"]:
            users[month(s["started_at"])].add(s["customer_id"])
        else:
            anon[month(s["started_at"])] += 1
    nps = defaultdict(list)
    for n in d["nps_response"]:
        nps[month(n["responded_at"])].append(int(n["score"]))
    product_sales = defaultdict(Counter)
    names = {p["product_id"]: p["name"] for p in d["product"]}
    for i in d["sales_order_item"]:
        o = orders[i["order_id"]]
        if o["status"] in ("PAID", "FULFILLED"):
            product_sales[month(o["order_date"])][names[i["product_id"]]] += num(i["line_total"])

    print("\nKPIs mensuales (pedidos PAID/FULFILLED; NPS por fecha de respuesta)")
    print(f"  {'mes':<8}{'pedidos':>8}{'ventas $M':>11}{'ticket $K':>11}{'clientes':>10}{'anónimas':>10}{'NPS':>7}  top producto")
    for m in sorted(set(sales) | set(nps)):
        scores = nps.get(m, [])
        nps_value = ((sum(s >= 9 for s in scores) - sum(s <= 6 for s in scores)) / len(scores) * 100) if scores else 0
        top = product_sales[m].most_common(1)[0][0] if product_sales[m] else "-"
        ticket = sales[m] / count[m] / 1e3 if count[m] else 0
        print(f"  {m:<8}{count[m]:>8}{sales[m] / 1e6:>11.1f}{ticket:>11.1f}"
              f"{len(users[m]):>10}{anon[m]:>10}{nps_value:>7.1f}  {top}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", type=Path, default=Path(__file__).resolve().parent.parent / "raw",
                        help="carpeta con los CSV (default: raw/)")
    parser.add_argument("--snapshot", type=datetime.fromisoformat, default=SNAPSHOT,
                        help="corte para validar una combinación de histórico y lotes diarios")
    args = parser.parse_args()
    data = load(args.dir)
    report = Report()
    validate(data, report, snapshot=args.snapshot, end=args.snapshot.date())
    summary(data)
    if report.failures:
        print(f"\n{report.failures} reglas con fallas")
        sys.exit(1)
    print("\nTodas las reglas OK")


if __name__ == "__main__":
    main()
