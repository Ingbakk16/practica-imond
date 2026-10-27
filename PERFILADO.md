# Línea base y perfilado de fuentes — fases 0 y 1

Resultados sobre los CSV versionados de `raw/`, con Python 3.10.12 y DuckDB 1.5.5. Corte del origen: **2025-09-30 23:59:59** (hora de Argentina). Pedidos del 2024-01-01 al 2025-09-30, importes en ARS; precios de lista sin IVA. Fuente de verdad: `raw/`; relaciones de origen: [`assets/DER.png`](assets/DER.png).

## Repetir la línea base

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 generator/validate_raw.py
python3 run_sql.py --explorar
git diff --exit-code -- raw/
```

Si `python3 -m venv` falla por ausencia de `ensurepip`, instalar `python3-venv` o, si está disponible, ejecutar `virtualenv .venv` antes de activar el entorno. En esta ejecución se usó `virtualenv` por esa razón. `--explorar` no ejecuta `sql/` ni crea `dw/`; sin acceso a la interfaz web ofrece consola SQL (salir con `salir`).

**Resultado:** `generator/validate_raw.py` terminó con «Todas las reglas OK»: PK, FK, dominios, importes, pagos, envíos y fechas coherentes. Se cargaron y describieron **13 vistas `raw.*`** en DuckDB. `git diff --exit-code -- raw/` no mostró cambios. La referencia mensual del validador figura abajo.

## Inventario de las 13 fuentes

Tipos de `DESCRIBE raw.<tabla>`: `B` = `BIGINT`, `V` = `VARCHAR`, `T` = `TIMESTAMP`, `D` = `DOUBLE`. Los importes `D` son la inferencia de lectura de CSV: usar `DECIMAL(12, 2)` al modelar el warehouse. Los nulos son celdas vacías del CSV; las columnas no mencionadas en «Nulos» tienen cero. Todas las PK tienen tantos valores distintos como filas y cero nulos.

| Tabla / grano (una fila por…) | Filas | PK | Columnas (nombre: tipo) | Nulos |
|---|---:|---|---|---|
| `channel` / canal | 2 | `channel_id` | `channel_id:B`, `code:V`, `name:V` | — |
| `province` / provincia | 4 | `province_id` | `province_id:B`, `name:V`, `code:V` | — |
| `product_category` / categoría o familia | 3 | `category_id` | `category_id:B`, `name:V`, `parent_id:B` | `parent_id`: 1 |
| `product` / producto | 2 | `product_id` | `product_id:B`, `sku:V`, `name:V`, `category_id:B`, `list_price:D`, `status:V`, `created_at:T` | — |
| `store` / tienda | 4 | `store_id` | `store_id:B`, `name:V`, `address_id:B` | — |
| `customer` / cliente | 3.471 | `customer_id` | `customer_id:B`, `email:V`, `first_name:V`, `last_name:V`, `phone:V`, `status:V`, `created_at:T` | `phone`: 276 |
| `address` / dirección | 3.829 | `address_id` | `address_id:B`, `line1:V`, `line2:V`, `city:V`, `province_id:B`, `postal_code:B`, `country_code:V`, `created_at:T` | `line2`: 2.096 |
| `sales_order` / pedido | 11.969 | `order_id` | `order_id:B`, `customer_id:B`, `channel_id:B`, `store_id:B`, `order_date:T`, `billing_address_id:B`, `shipping_address_id:B`, `status:V`, `currency_code:V`, `subtotal:D`, `tax_amount:D`, `shipping_fee:D`, `total_amount:D` | `store_id`: 7.286; `billing_address_id`: 2.073 |
| `sales_order_item` / línea de producto de un pedido | 14.573 | `order_item_id` | `order_item_id:B`, `order_id:B`, `product_id:B`, `quantity:B`, `unit_price:D`, `discount_amount:D`, `line_total:D` | — |
| `payment` / pago de un pedido | 11.969 | `payment_id` | `payment_id:B`, `order_id:B`, `method:V`, `status:V`, `amount:D`, `paid_at:T`, `transaction_ref:V` | `paid_at`: 566; `transaction_ref`: 2.337 |
| `shipment` / envío de un pedido | 7.009 | `shipment_id` | `shipment_id:B`, `order_id:B`, `carrier:V`, `tracking_number:V`, `status:V`, `shipped_at:T`, `delivered_at:T` | `tracking_number`: 102; `shipped_at`: 102; `delivered_at`: 153 |
| `web_session` / sesión web | 100.363 | `session_id` | `session_id:B`, `customer_id:B`, `started_at:T`, `ended_at:T`, `source:V`, `device:V` | `customer_id`: 70.751; `ended_at`: 3.024 |
| `nps_response` / respuesta de encuesta | 3.083 | `nps_id` | `nps_id:B`, `customer_id:B`, `channel_id:B`, `score:B`, `comment:V`, `responded_at:T` | `customer_id`: 122; `comment`: 1.102 |

`postal_code` se infiere como `BIGINT`: si se requiere conservar ceros iniciales, cargarlo explícitamente como texto. Mantener también las claves naturales (`*_id`) en las dimensiones para trazabilidad.

## Relaciones y cardinalidades observadas

Para cada FK se comprobaron valores no nulos, destinos distintos y filas sin correspondencia: **cero huérfanos en todas las relaciones**. Una FK nula es opcional, no huérfana.

| FK → destino | No nulas | Destinos distintos | Nulas / interpretación |
|---|---:|---:|---|
| `address.province_id` → `province` | 3.829 | 4 | 0 |
| `store.address_id` → `address` | 4 | 4 | 0 |
| `product.category_id` → `product_category` | 2 | 2 | 0 |
| `product_category.parent_id` → `product_category` | 2 | 1 | 1; familia raíz |
| `sales_order.customer_id` → `customer` | 11.969 | 3.257 | 0 |
| `sales_order.channel_id` → `channel` | 11.969 | 2 | 0 |
| `sales_order.store_id` → `store` | 4.683 | 4 | 7.286; pedidos online |
| `sales_order.billing_address_id` → `address` | 9.896 | 3.096 | 2.073; facturación opcional |
| `sales_order.shipping_address_id` → `address` | 11.969 | 2.981 | 0; puede ser la dirección de la tienda |
| `sales_order_item.order_id` → `sales_order` | 14.573 | 11.969 | 0 |
| `sales_order_item.product_id` → `product` | 14.573 | 2 | 0 |
| `payment.order_id` → `sales_order` | 11.969 | 11.969 | 0; un pago por pedido |
| `shipment.order_id` → `sales_order` | 7.009 | 7.009 | 0; máximo un envío por pedido |
| `web_session.customer_id` → `customer` | 29.612 | 3.077 | 70.751; sesiones anónimas |
| `nps_response.customer_id` → `customer` | 2.961 | 1.802 | 122; respuestas anónimas |
| `nps_response.channel_id` → `channel` | 3.083 | 2 | 0 |

Hay **9.365 pedidos con un ítem** y **2.604 con dos**. Los 11.969 pedidos tienen ítems y pago; 7.009 tienen envío (6.774 online y 235 de tienda). No sumar `sales_order.total_amount` después de unir pedidos con ítems: se duplicaría el importe de pedidos de dos líneas. `nps_response` no tiene `order_id`: no atribuir cada respuesta a un pedido concreto.

## Dominios, nulos y reglas de negocio

| Campo | Valores observados (cantidad) |
|---|---|
| `channel.code` | `ONLINE` 1, `OFFLINE` 1; pedidos online 7.286, offline 4.683 |
| `province.code` | `BA`, `CBA`, `MZA`, `SF` (1 cada una) |
| `product_category.name` | `Bottles`, `Classic`, `Sport` (1 cada una; las últimas dos dependen de `Bottles`) |
| `product.status` | `A` 2 |
| `customer.status` | `A` 3.167, `I` 304; las compras previas de inactivos siguen siendo ventas |
| `sales_order.status` | `FULFILLED` 10.938, `PAID` 60, `CANCELLED` 658, `REFUNDED` 312, `CREATED` 1 |
| `payment.method` | `CARD` 6.561, `CASH` 1.771, `GATEWAY` 3.093, `TRANSFER` 544 |
| `payment.status` | `PAID` 10.998, `FAILED` 565, `REFUNDED` 405, `PENDING` 1 |
| `shipment.status` | `DELIVERED` 6.856, `SHIPPED` 51, `READY` 9, `CANCELLED` 93 |
| `web_session.source` | `ads` 25.165, `direct` 30.466, `organic` 26.417, `referral` 18.315 |
| `web_session.device` | `desktop` 32.428, `mobile` 62.117, `tablet` 5.818 |
| `nps_response.channel_id` | `ONLINE` 1.991, `OFFLINE` 1.092; puntaje entero entre 0 y 10 |

- **Venta y ticket:** filtrar pedidos `PAID` o `FULFILLED`, contar cada `order_id` una vez y sumar `total_amount` (incluye IVA y envío). `CREATED`, `CANCELLED` y `REFUNDED` no cuentan. Referencia: **10.998 pedidos**, **$382.410.636,00** de total y $309.891.600,00 de subtotal (sin IVA ni envío). Para venta por producto, sumar `line_total` de ítems de pedidos válidos: no es el mismo importe que el total con IVA y envío.
- **Fechas:** ventas por `sales_order.order_date` (2024-01-01 00:58:42 a 2025-09-30 23:27:43); actividad web por `web_session.started_at` (2024-01-01 a 2025-09-30); NPS por `nps_response.responded_at` (2024-01-03 a 2025-09-30), no por fecha de compra. Para métricas operativas usar `payment.paid_at` y `shipment.shipped_at` / `delivered_at` según el evento.
- **Clientes / usuarios activos:** la referencia mensual del validador cuenta `DISTINCT customer_id` de sesiones identificadas por `started_at`. Las **70.751 sesiones sin cliente** son sesiones, no personas únicas; se conservan con clave de cliente desconocido `-1` en `fact_web_session`. Lo mismo ocurre con las **122 respuestas NPS anónimas** en `fact_nps_response`.
- **NPS:** `100 × (promotores, score 9–10 − detractores, score 0–6) / total de respuestas`; 7–8 son pasivos. NPS global **30,0**. Agrupar por `responded_at` y opcionalmente `channel_id`, sin unir respuestas a pedidos por cliente.
- **Provincia:** `sales_order.shipping_address_id → address.province_id → province`. En compras en tienda sin envío, esa dirección es la de la tienda; la dirección de facturación puede faltar. Distinguir destino del pedido y ubicación de tienda según la pregunta de negocio.
- **Conciliación monetaria:** `line_total = quantity × unit_price − discount_amount`; `subtotal = SUM(line_total)`; IVA = 21 % del subtotal; `total_amount = subtotal + tax_amount + shipping_fee`. El validador comprueba estas reglas y la coherencia de estados de pedido, pago y envío.

### KPIs mensuales de referencia

Salida de `python3 generator/validate_raw.py`: ventas en **millones** de ARS y ticket en **miles** de ARS, redondeados a un decimal. Clientes = clientes identificados con sesión; anónimas = sesiones sin cliente. NPS por fecha de respuesta.

| Mes | Pedidos | Ventas $M | Ticket $K | Clientes | Anónimas | NPS | Producto líder |
|---|---:|---:|---:|---:|---:|---:|---|
| 2024-01 | 460 | 16,0 | 34,7 | 424 | 3.226 | 37,6 | Sport B Bottle |
| 2024-02 | 513 | 18,4 | 35,8 | 475 | 3.011 | 28,4 | Sport B Bottle |
| 2024-03 | 482 | 17,1 | 35,5 | 526 | 3.103 | 28,5 | Classic A Bottle |
| 2024-04 | 438 | 15,2 | 34,8 | 521 | 2.784 | 22,6 | Classic A Bottle |
| 2024-05 | 474 | 16,3 | 34,5 | 571 | 3.256 | 30,6 | Sport B Bottle |
| 2024-06 | 555 | 19,7 | 35,6 | 625 | 3.176 | 32,9 | Sport B Bottle |
| 2024-07 | 387 | 13,6 | 35,2 | 625 | 2.645 | 15,5 | Classic A Bottle |
| 2024-08 | 444 | 15,0 | 33,8 | 651 | 2.810 | 5,0 | Classic A Bottle |
| 2024-09 | 443 | 14,9 | 33,7 | 677 | 2.958 | 11,9 | Classic A Bottle |
| 2024-10 | 539 | 18,3 | 33,9 | 728 | 3.286 | 34,6 | Sport B Bottle |
| 2024-11 | 572 | 18,7 | 32,8 | 769 | 3.906 | 37,9 | Sport B Bottle |
| 2024-12 | 785 | 28,4 | 36,2 | 913 | 4.972 | 30,4 | Sport B Bottle |
| 2025-01 | 591 | 20,6 | 34,8 | 876 | 3.813 | 31,9 | Sport B Bottle |
| 2025-02 | 608 | 21,7 | 35,6 | 882 | 3.463 | 42,6 | Sport B Bottle |
| 2025-03 | 581 | 20,0 | 34,4 | 936 | 3.693 | 33,5 | Classic A Bottle |
| 2025-04 | 495 | 17,1 | 34,5 | 955 | 3.251 | 36,8 | Classic A Bottle |
| 2025-05 | 588 | 19,6 | 33,3 | 1.017 | 3.863 | 36,1 | Sport B Bottle |
| 2025-06 | 562 | 21,2 | 37,7 | 971 | 3.581 | 38,0 | Sport B Bottle |
| 2025-07 | 443 | 14,7 | 33,2 | 983 | 3.102 | 28,0 | Classic A Bottle |
| 2025-08 | 551 | 19,2 | 34,9 | 1.029 | 3.332 | 29,7 | Classic A Bottle |
| 2025-09 | 487 | 16,6 | 34,2 | 1.041 | 3.520 | 27,1 | Sport B Bottle |

## Consultas de comprobación reproducibles

Ejecutar en `python3 run_sql.py --explorar`. Repetir `DESCRIBE`, recuento/PK y nulos con las columnas de cada tabla del inventario; el validador automatiza las comprobaciones de todas las PK, FK y reglas del origen.

```sql
DESCRIBE raw.sales_order;
SELECT COUNT(*) AS filas, COUNT(DISTINCT order_id) AS claves_distintas,
       COUNT(*) FILTER (WHERE order_id IS NULL) AS claves_nulas
FROM raw.sales_order;

SELECT COUNT(*) AS pedidos,
       COUNT(*) FILTER (WHERE store_id IS NULL) AS sin_tienda,
       COUNT(*) FILTER (WHERE billing_address_id IS NULL) AS sin_facturacion
FROM raw.sales_order;

SELECT status, channel_id, COUNT(*) AS pedidos
FROM raw.sales_order GROUP BY status, channel_id ORDER BY status, channel_id;

SELECT source, device, COUNT(*) AS sesiones,
       COUNT(*) FILTER (WHERE customer_id IS NULL) AS anonimas,
       COUNT(*) FILTER (WHERE ended_at IS NULL) AS sin_cierre
FROM raw.web_session GROUP BY source, device ORDER BY source, device;

SELECT COUNT(*) AS respuestas,
       COUNT(*) FILTER (WHERE customer_id IS NULL) AS anonimas,
       COUNT(*) FILTER (WHERE comment IS NULL) AS sin_comentario
FROM raw.nps_response;

SELECT lineas, COUNT(*) AS pedidos
FROM (SELECT order_id, COUNT(*) AS lineas FROM raw.sales_order_item GROUP BY order_id)
GROUP BY lineas ORDER BY lineas;

-- Ejemplo de FK; repetir con las relaciones de la tabla anterior.
SELECT COUNT(*) AS huerfanos
FROM raw.sales_order_item AS i
LEFT JOIN raw.sales_order AS o ON o.order_id = i.order_id
WHERE i.order_id IS NOT NULL AND o.order_id IS NULL;

SELECT COUNT(*) AS pedidos, SUM(total_amount) AS ventas
FROM raw.sales_order WHERE status IN ('PAID', 'FULFILLED');

SELECT DATE_TRUNC('month', order_date) AS mes, COUNT(*) AS pedidos,
       SUM(total_amount) AS ventas
FROM raw.sales_order WHERE status IN ('PAID', 'FULFILLED')
GROUP BY mes ORDER BY mes;
```

`python3 generator/validate_raw.py` vuelve a comprobar el perfil completo del origen y reproduce la tabla mensual de referencia. Las consultas anteriores permiten inspeccionar las fuentes antes de construir las dimensiones.
