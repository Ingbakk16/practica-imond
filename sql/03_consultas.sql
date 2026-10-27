-- =====================================================================
-- 03_consultas.sql — Consultas para revisar el modelo y calcular KPIs
-- =====================================================================
-- Cada SELECT de este archivo se muestra en la terminal al ejecutar
-- run_sql.py. Usalo para:
--   * comprobar que las tablas se cargaron bien (cantidad de filas, nulos...)
--   * escribir las consultas clave de los KPIs que pide la consigna
--     (ventas, usuarios activos, ticket promedio, NPS, ventas por provincia,
--     ranking mensual por producto) usando las tablas del modelo estrella.
-- =====================================================================


-- Ejemplo: revisar la dimensión producto
SELECT product_key, name, category, family, list_price
FROM dim_product
ORDER BY product_key;


-- Controles de las fases 2 y 3. Si falla alguno, error() detiene la carga
-- antes de exportar a dw/. Los KPIs de sesiones y NPS se agregan en fase 5.

SELECT CASE WHEN
    (SELECT COUNT(*) FROM dim_date) = 639
    AND (SELECT MIN(date_value) FROM dim_date) = DATE '2024-01-01'
    AND (SELECT MAX(date_value) FROM dim_date) = DATE '2025-09-30'
    AND (SELECT COUNT(*) FROM dim_channel) = 2
    AND (SELECT COUNT(*) FROM dim_province) = 4
    AND (SELECT COUNT(*) FROM dim_product) = 2
    AND (SELECT COUNT(*) FROM dim_customer) = 3472
    AND (SELECT COUNT(*) FROM dim_customer WHERE customer_key = -1 AND customer_id IS NULL) = 1
    AND (SELECT COUNT(*) FROM dim_store) = 5
    AND (SELECT COUNT(*) FROM dim_store WHERE store_key = -1 AND store_id IS NULL) = 1
    AND (SELECT COUNT(*) FROM dim_product WHERE category IS NULL OR family IS NULL) = 0
    THEN 'OK: dimensiones y jerarquía producto'
    ELSE error('Dimensiones: revisar filas, fechas, claves -1 o categorías') END AS control_dimensiones;

SELECT CASE WHEN
    (SELECT COUNT(*) FROM fact_sales_order) = 11969
    AND (SELECT COUNT(*) FROM fact_sales_order_item) = 14573
    AND (SELECT COUNT(*) FROM fact_sales_order WHERE es_venta) = 10998
    AND (SELECT COUNT(*) FROM fact_sales_order WHERE store_key = -1) = 7286
    AND (SELECT COUNT(*) FROM fact_sales_order WHERE store_key = -1 AND channel_key <> (SELECT channel_key FROM dim_channel WHERE code = 'ONLINE')) = 0
    AND (SELECT COUNT(*) FROM fact_sales_order_item WHERE store_key = -1) =
        (SELECT COUNT(*) FROM raw.sales_order_item AS i
         JOIN raw.sales_order AS o ON o.order_id = i.order_id WHERE o.store_id IS NULL)
    THEN 'OK: granos de pedidos e ítems'
    ELSE error('Hechos: revisar recuentos, estados o tienda online') END AS control_granos;

-- Cada ítem mantiene el mismo contexto dimensional y estado que su pedido.
SELECT CASE WHEN COUNT(*) = 0 THEN 'OK: ítems asociados a pedidos'
    ELSE error('Ítems: pedido ausente o dimensiones/estado inconsistentes') END AS control_items
FROM fact_sales_order_item AS i
LEFT JOIN fact_sales_order AS o ON o.order_id = i.order_id
WHERE o.order_id IS NULL OR i.date_key <> o.date_key OR i.channel_key <> o.channel_key
   OR i.customer_key <> o.customer_key OR i.store_key <> o.store_key
   OR i.province_key <> o.province_key OR i.es_venta <> o.es_venta;

-- La suma de líneas concilia con el subtotal SIN duplicar el total del pedido.
WITH lines AS (
    SELECT order_id, COUNT(*) AS line_count, SUM(line_total) AS subtotal,
           SUM(venta_neta) AS venta_neta
    FROM fact_sales_order_item GROUP BY order_id
)
SELECT CASE WHEN COUNT(*) = 0 THEN 'OK: subtotales, IVA, envío y ventas por ítem'
    ELSE error('Ventas: un pedido no concilia con sus ítems o importes') END AS control_importes
FROM fact_sales_order AS o
LEFT JOIN lines AS i ON i.order_id = o.order_id
WHERE i.order_id IS NULL OR i.line_count NOT BETWEEN 1 AND 2
   OR i.subtotal <> o.subtotal
   OR o.total_amount <> o.subtotal + o.tax_amount + o.shipping_fee
   OR (o.es_venta AND (o.venta_neta <> o.total_amount OR i.venta_neta <> o.subtotal))
   OR (NOT o.es_venta AND (o.venta_neta <> 0 OR i.venta_neta <> 0));

SELECT CASE WHEN
    (SELECT SUM(venta_neta) FROM fact_sales_order) = 382410636.00
    AND (SELECT SUM(venta_neta) FROM fact_sales_order_item) = 309891600.00
    AND (SELECT COUNT(*) FROM fact_sales_order WHERE status IN ('CREATED', 'CANCELLED', 'REFUNDED') AND es_venta) = 0
    AND (SELECT COUNT(*) FROM fact_sales_order WHERE status IN ('PAID', 'FULFILLED') AND NOT es_venta) = 0
    THEN 'OK: ventas del corte y estados'
    ELSE error('Ventas: totales o reglas de inclusión distintos del origen') END AS control_ventas;

-- Unir pedidos con ítems SOLO después de agruparlos a una fila por pedido.
-- Si se sumara o.venta_neta directamente en el join con líneas, se duplicaría
-- el total de los 2.604 pedidos que tienen dos ítems.
WITH item_counts AS (
    SELECT order_id, COUNT(*) AS line_count
    FROM fact_sales_order_item GROUP BY order_id
), reconciled AS (
    SELECT COUNT(*) AS orders, SUM(o.venta_neta) AS sales
    FROM fact_sales_order AS o JOIN item_counts AS i ON i.order_id = o.order_id
)
SELECT CASE WHEN
    (SELECT COUNT(*) FROM item_counts WHERE line_count = 1) = 9365
    AND (SELECT COUNT(*) FROM item_counts WHERE line_count = 2) = 2604
    AND (SELECT orders FROM reconciled) = 11969
    AND (SELECT sales FROM reconciled) = 382410636.00
    THEN 'OK: total por pedido no multiplicado por sus ítems'
    ELSE error('Grano: al unir hechos se duplicó o se perdió un pedido') END AS control_union;

-- Conciliar los 21 meses con raw, sumando el total solo a grano de pedido.
WITH origin AS (
    SELECT DATE_TRUNC('month', order_date) AS month_start,
           COUNT(*) AS orders, CAST(SUM(total_amount) AS DECIMAL(18, 2)) AS sales
    FROM raw.sales_order WHERE status IN ('PAID', 'FULFILLED')
    GROUP BY 1
), warehouse AS (
    SELECT DATE_TRUNC('month', d.date_value) AS month_start,
           COUNT(*) AS orders, SUM(o.venta_neta) AS sales
    FROM fact_sales_order AS o
    JOIN dim_date AS d ON d.date_key = o.date_key
    WHERE o.es_venta GROUP BY 1
), comparison AS (
    SELECT origin.month_start AS origin_month, warehouse.month_start AS warehouse_month,
           origin.orders AS origin_orders, warehouse.orders AS warehouse_orders,
           origin.sales AS origin_sales, warehouse.sales AS warehouse_sales
    FROM origin FULL OUTER JOIN warehouse USING (month_start)
)
SELECT CASE WHEN COUNT(*) = 21
    AND COUNT(*) FILTER (WHERE origin_month IS NULL OR warehouse_month IS NULL
        OR origin_orders <> warehouse_orders OR origin_sales <> warehouse_sales) = 0
    THEN 'OK: 21 meses conciliados con raw'
    ELSE error('Ventas mensuales: discrepancia entre raw y fact_sales_order') END AS control_meses
FROM comparison;

SELECT d.year, d.month, COUNT(*) AS pedidos, SUM(o.venta_neta) AS ventas_ars
FROM fact_sales_order AS o
JOIN dim_date AS d ON d.date_key = o.date_key
WHERE o.es_venta
GROUP BY d.year, d.month
ORDER BY d.year, d.month;
