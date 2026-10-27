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


-- Controles: si alguno falla, error() detiene la carga antes de exportar a dw/.

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

-- Fases 4 y 5: filas, claves y relaciones opcionales de sesiones y NPS.
SELECT CASE WHEN
    (SELECT COUNT(*) FROM fact_web_session) = 100363
    AND (SELECT COUNT(*) FROM fact_nps_response) = 3083
    AND (SELECT COUNT(*) FROM fact_sales_order WHERE customer_key = -1) = 0
    AND (SELECT COUNT(*) FROM fact_sales_order_item WHERE customer_key = -1) = 0
    AND (SELECT COUNT(*) FROM fact_web_session WHERE customer_key = -1) = 70751
    AND (SELECT COUNT(*) FROM fact_nps_response WHERE customer_key = -1) = 122
    AND (SELECT COUNT(*) FROM fact_web_session WHERE ended_at IS NULL AND duration_seconds IS NULL) = 3024
    AND (SELECT COUNT(*) FROM fact_web_session WHERE ended_at IS NOT NULL AND duration_seconds IS NULL) = 0
    AND (SELECT COUNT(*) FROM fact_web_session WHERE duration_seconds < 0) = 0
    AND (SELECT COUNT(*) FROM fact_nps_response WHERE score NOT BETWEEN 0 AND 10) = 0
    AND (SELECT COUNT(*) FROM duckdb_constraints()
         WHERE schema_name = 'main' AND constraint_type = 'FOREIGN KEY') = 16
    THEN 'OK: hechos digitales, anónimos y claves foráneas'
    ELSE error('Sesiones/NPS: revisar filas, anónimos, duración o claves') END AS control_digital;

-- Una clave -1 corresponde únicamente a un customer_id nulo en raw.
-- Verificar también fecha, canal y atributos conservados en los hechos.
SELECT CASE WHEN
    (SELECT COUNT(*) FROM raw.web_session AS r
     LEFT JOIN fact_web_session AS s ON s.session_id = r.session_id
     LEFT JOIN dim_customer AS c ON c.customer_key = s.customer_key
     WHERE s.session_id IS NULL OR s.started_at IS DISTINCT FROM r.started_at
        OR s.ended_at IS DISTINCT FROM r.ended_at
        OR s.source IS DISTINCT FROM r.source OR s.device IS DISTINCT FROM r.device
        OR s.date_key IS DISTINCT FROM CAST(strftime(r.started_at, '%Y%m%d') AS INTEGER)
        OR s.duration_seconds IS DISTINCT FROM date_diff('second', r.started_at, r.ended_at)
        OR c.customer_id IS DISTINCT FROM r.customer_id) = 0
    AND (SELECT COUNT(*) FROM raw.nps_response AS r
         LEFT JOIN fact_nps_response AS n ON n.nps_id = r.nps_id
         LEFT JOIN dim_customer AS c ON c.customer_key = n.customer_key
         LEFT JOIN dim_channel AS ch ON ch.channel_key = n.channel_key
         WHERE n.nps_id IS NULL OR n.responded_at IS DISTINCT FROM r.responded_at
            OR n.date_key IS DISTINCT FROM CAST(strftime(r.responded_at, '%Y%m%d') AS INTEGER)
            OR n.score IS DISTINCT FROM r.score OR n.comment IS DISTINCT FROM r.comment
            OR c.customer_id IS DISTINCT FROM r.customer_id
            OR ch.channel_id IS DISTINCT FROM r.channel_id) = 0
    THEN 'OK: fechas y clientes anónimos fieles al origen'
    ELSE error('Sesiones/NPS: hay filas faltantes o relaciones incorrectas') END AS control_origen_digital;

-- Conteo auditable de cada tabla del warehouse.
SELECT 'dim_date' AS tabla, COUNT(*) AS filas FROM dim_date
UNION ALL SELECT 'dim_channel', COUNT(*) FROM dim_channel
UNION ALL SELECT 'dim_province', COUNT(*) FROM dim_province
UNION ALL SELECT 'dim_product', COUNT(*) FROM dim_product
UNION ALL SELECT 'dim_customer', COUNT(*) FROM dim_customer
UNION ALL SELECT 'dim_store', COUNT(*) FROM dim_store
UNION ALL SELECT 'fact_sales_order', COUNT(*) FROM fact_sales_order
UNION ALL SELECT 'fact_sales_order_item', COUNT(*) FROM fact_sales_order_item
UNION ALL SELECT 'fact_web_session', COUNT(*) FROM fact_web_session
UNION ALL SELECT 'fact_nps_response', COUNT(*) FROM fact_nps_response
ORDER BY tabla;

-- Reconciliar por mes el número de sesiones, usuarios identificados y anónimas.
WITH origin AS (
    SELECT DATE_TRUNC('month', started_at) AS month_start, COUNT(*) AS sessions,
           COUNT(DISTINCT customer_id) AS active_users,
           COUNT(*) FILTER (WHERE customer_id IS NULL) AS anonymous
    FROM raw.web_session GROUP BY 1
), warehouse AS (
    SELECT DATE_TRUNC('month', d.date_value) AS month_start, COUNT(*) AS sessions,
           COUNT(DISTINCT NULLIF(s.customer_key, -1)) AS active_users,
           COUNT(*) FILTER (WHERE s.customer_key = -1) AS anonymous
    FROM fact_web_session AS s JOIN dim_date AS d ON d.date_key = s.date_key
    GROUP BY 1
)
SELECT CASE WHEN COUNT(*) = 21 AND COUNT(*) FILTER (WHERE
    o.month_start IS NULL OR w.month_start IS NULL
    OR o.sessions <> w.sessions OR o.active_users <> w.active_users
    OR o.anonymous <> w.anonymous) = 0
    THEN 'OK: sesiones y usuarios activos en 21 meses'
    ELSE error('Sesiones: discrepancia mensual frente a raw') END AS control_sesiones
FROM origin AS o FULL OUTER JOIN warehouse AS w USING (month_start);

-- Comparar NPS por mes y canal usando los recuentos, antes de dividir.
WITH origin AS (
    SELECT DATE_TRUNC('month', responded_at) AS month_start, channel_id,
           COUNT(*) AS responses, COUNT(*) FILTER (WHERE score >= 9) AS promoters,
           COUNT(*) FILTER (WHERE score <= 6) AS detractors
    FROM raw.nps_response GROUP BY 1, 2
), warehouse AS (
    SELECT DATE_TRUNC('month', d.date_value) AS month_start, ch.channel_id,
           COUNT(*) AS responses, COUNT(*) FILTER (WHERE n.score >= 9) AS promoters,
           COUNT(*) FILTER (WHERE n.score <= 6) AS detractors
    FROM fact_nps_response AS n
    JOIN dim_date AS d ON d.date_key = n.date_key
    JOIN dim_channel AS ch ON ch.channel_key = n.channel_key
    GROUP BY 1, 2
)
SELECT CASE WHEN COUNT(*) = 42 AND COUNT(*) FILTER (WHERE
    o.month_start IS NULL OR w.month_start IS NULL
    OR o.channel_id IS NULL OR w.channel_id IS NULL
    OR o.responses <> w.responses OR o.promoters <> w.promoters
    OR o.detractors <> w.detractors) = 0
    THEN 'OK: NPS mensual por canal conciliado con raw'
    ELSE error('NPS: discrepancia mensual frente a raw') END AS control_nps
FROM origin AS o FULL OUTER JOIN warehouse AS w
    ON w.month_start = o.month_start AND w.channel_id = o.channel_id;

-- El ranking usa line_total sin IVA ni envío, igual que validate_raw.py.
WITH origin AS (
    SELECT DATE_TRUNC('month', o.order_date) AS month_start, i.product_id,
           CAST(SUM(i.line_total) AS DECIMAL(18, 2)) AS sales
    FROM raw.sales_order_item AS i
    JOIN raw.sales_order AS o ON o.order_id = i.order_id
    WHERE o.status IN ('PAID', 'FULFILLED') GROUP BY 1, 2
), warehouse AS (
    SELECT DATE_TRUNC('month', d.date_value) AS month_start, p.product_id,
           SUM(i.venta_neta) AS sales
    FROM fact_sales_order_item AS i
    JOIN dim_date AS d ON d.date_key = i.date_key
    JOIN dim_product AS p ON p.product_key = i.product_key
    GROUP BY 1, 2
)
SELECT CASE WHEN COUNT(*) = 42 AND COUNT(*) FILTER (WHERE
    o.month_start IS NULL OR w.month_start IS NULL
    OR o.product_id IS NULL OR w.product_id IS NULL OR o.sales <> w.sales) = 0
    THEN 'OK: ventas por producto en 21 meses'
    ELSE error('Productos: discrepancia mensual frente a raw') END AS control_productos
FROM origin AS o FULL OUTER JOIN warehouse AS w
    ON w.month_start = o.month_start AND w.product_id = o.product_id;

-- Ventas, pedidos, ticket y clientes compradores: grano de un pedido.
SELECT d.year, d.month, COUNT(*) AS pedidos, SUM(o.venta_neta) AS ventas_ars,
       ROUND(SUM(o.venta_neta) / COUNT(*), 2) AS ticket_promedio_ars,
       COUNT(DISTINCT o.customer_key) AS clientes_compradores
FROM fact_sales_order AS o
JOIN dim_date AS d ON d.date_key = o.date_key
WHERE o.es_venta
GROUP BY d.year, d.month
ORDER BY d.year, d.month;

-- Ventas por canal y provincia de destino del pedido (IVA y envío incluidos).
SELECT ch.code AS canal, p.code AS provincia, COUNT(*) AS pedidos,
       SUM(o.venta_neta) AS ventas_ars
FROM fact_sales_order AS o
JOIN dim_channel AS ch ON ch.channel_key = o.channel_key
JOIN dim_province AS p ON p.province_key = o.province_key
WHERE o.es_venta
GROUP BY ch.code, p.code ORDER BY ch.code, p.code;

-- Ranking mensual de productos: venta de línea sin IVA ni envío.
WITH sales AS (
    SELECT d.year, d.month, p.name AS producto, p.product_id,
           SUM(i.venta_neta) AS ventas_ars
    FROM fact_sales_order_item AS i
    JOIN dim_date AS d ON d.date_key = i.date_key
    JOIN dim_product AS p ON p.product_key = i.product_key
    GROUP BY d.year, d.month, p.name, p.product_id
)
SELECT year, month, producto, ventas_ars,
       ROW_NUMBER() OVER (PARTITION BY year, month
                          ORDER BY ventas_ars DESC, product_id) AS posicion
FROM sales ORDER BY year, month, posicion;

-- Usuarios activos = clientes identificados con sesión iniciada en el mes.
-- Sesiones anónimas no se interpretan como usuarios únicos.
SELECT d.year, d.month, COUNT(*) AS sesiones,
       COUNT(DISTINCT NULLIF(s.customer_key, -1)) AS usuarios_activos,
       COUNT(*) FILTER (WHERE s.customer_key = -1) AS sesiones_anonimas
FROM fact_web_session AS s
JOIN dim_date AS d ON d.date_key = s.date_key
GROUP BY d.year, d.month ORDER BY d.year, d.month;

-- AVG ignora los NULL: las sesiones sin cierre no sesgan la duración media.
SELECT source, device, COUNT(*) AS sesiones,
       COUNT(duration_seconds) AS sesiones_con_cierre,
       ROUND(AVG(duration_seconds), 1) AS duracion_media_segundos
FROM fact_web_session GROUP BY source, device ORDER BY source, device;

-- NPS global y por canal: pasivos (7-8) quedan en el denominador.
SELECT CASE WHEN GROUPING(ch.code) = 1 THEN 'TOTAL' ELSE ch.code END AS canal,
       COUNT(*) AS respuestas,
       COUNT(*) FILTER (WHERE n.score >= 9) AS promotores,
       COUNT(*) FILTER (WHERE n.score BETWEEN 7 AND 8) AS pasivos,
       COUNT(*) FILTER (WHERE n.score <= 6) AS detractores,
       ROUND(100.0 * (COUNT(*) FILTER (WHERE n.score >= 9)
           - COUNT(*) FILTER (WHERE n.score <= 6)) / COUNT(*), 1) AS nps
FROM fact_nps_response AS n
JOIN dim_channel AS ch ON ch.channel_key = n.channel_key
GROUP BY ROLLUP(ch.code) ORDER BY GROUPING(ch.code) DESC, canal;

-- NPS mensual por fecha de respuesta; nunca por fecha de compra.
SELECT d.year, d.month, COUNT(*) AS respuestas,
       ROUND(100.0 * (COUNT(*) FILTER (WHERE n.score >= 9)
           - COUNT(*) FILTER (WHERE n.score <= 6)) / COUNT(*), 1) AS nps
FROM fact_nps_response AS n
JOIN dim_date AS d ON d.date_key = n.date_key
GROUP BY d.year, d.month ORDER BY d.year, d.month;
