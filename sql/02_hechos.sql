-- =====================================================================
-- 02_hechos.sql — Tablas de HECHOS del modelo estrella
-- =====================================================================
-- Este archivo se ejecuta después de 01_dimensiones.sql porque los hechos
-- apuntan a las dimensiones con FOREIGN KEY (REFERENCES).
--
-- Para cada tabla de hechos:
--   1. Definí el GRANO: ¿qué representa UNA fila?
--      (ej.: un producto dentro de un pedido, una sesión web, una respuesta NPS)
--   2. CREATE TABLE con:
--        - PRIMARY KEY
--        - una FOREIGN KEY por cada dimensión:  product_key INTEGER REFERENCES dim_product (product_key)
--        - las métricas (cantidades, importes, puntajes...)
--   3. INSERT INTO ... SELECT uniendo las tablas de origen (raw.) con las dimensiones
--      para obtener las claves.
--
-- Patrón para obtener la clave de una dimensión:
--
--   SELECT i.order_item_id, p.product_key, i.quantity, i.line_total
--   FROM raw.sales_order_item AS i
--   JOIN dim_product AS p ON p.product_id = i.product_id
--
-- Si una FOREIGN KEY apunta a una clave que no existe en la dimensión,
-- DuckDB rechaza la carga y run_sql.py te muestra el error.
-- =====================================================================


-- Grano: un pedido, incluso si fue creado, cancelado o reembolsado.
-- total_amount es el importe original; venta_neta solo cuenta PAID/FULFILLED.
-- La provincia es la de shipping_address_id (en tienda, la de la tienda).
CREATE TABLE fact_sales_order (
    order_id      BIGINT PRIMARY KEY,       -- clave natural del pedido
    date_key      INTEGER NOT NULL REFERENCES dim_date (date_key),
    channel_key   INTEGER NOT NULL REFERENCES dim_channel (channel_key),
    customer_key  INTEGER NOT NULL REFERENCES dim_customer (customer_key),
    store_key     INTEGER NOT NULL REFERENCES dim_store (store_key),
    province_key  INTEGER NOT NULL REFERENCES dim_province (province_key),
    order_date    TIMESTAMP NOT NULL,
    status        VARCHAR NOT NULL,
    es_venta      BOOLEAN NOT NULL,
    subtotal      DECIMAL(12, 2) NOT NULL,
    tax_amount    DECIMAL(12, 2) NOT NULL,
    shipping_fee  DECIMAL(12, 2) NOT NULL,
    total_amount  DECIMAL(12, 2) NOT NULL,
    venta_neta    DECIMAL(12, 2) NOT NULL
);

INSERT INTO fact_sales_order
SELECT
    o.order_id,
    d.date_key,
    ch.channel_key,
    c.customer_key,
    COALESCE(s.store_key, -1),             -- ONLINE no tiene tienda
    p.province_key,
    o.order_date,
    o.status,
    o.status IN ('PAID', 'FULFILLED'),
    CAST(o.subtotal AS DECIMAL(12, 2)),
    CAST(o.tax_amount AS DECIMAL(12, 2)),
    CAST(o.shipping_fee AS DECIMAL(12, 2)),
    CAST(o.total_amount AS DECIMAL(12, 2)),
    CASE WHEN o.status IN ('PAID', 'FULFILLED')
         THEN CAST(o.total_amount AS DECIMAL(12, 2))
         ELSE CAST(0 AS DECIMAL(12, 2)) END
FROM raw.sales_order AS o
JOIN dim_date AS d ON d.date_value = CAST(o.order_date AS DATE)
JOIN dim_channel AS ch ON ch.channel_id = o.channel_id
JOIN dim_customer AS c ON c.customer_id = o.customer_id
LEFT JOIN dim_store AS s ON s.store_id = o.store_id
JOIN raw.address AS a ON a.address_id = o.shipping_address_id
JOIN dim_province AS p ON p.province_id = a.province_id;


-- Grano: una línea de producto de un pedido. Mantener order_id para
-- trazabilidad; no sumar total_amount después de unir estos dos hechos.
-- line_total y venta_neta son importes SIN IVA ni costo de envío.
CREATE TABLE fact_sales_order_item (
    order_item_id    BIGINT PRIMARY KEY,    -- clave natural de la línea
    order_id         BIGINT NOT NULL,       -- clave natural del pedido
    date_key         INTEGER NOT NULL REFERENCES dim_date (date_key),
    channel_key      INTEGER NOT NULL REFERENCES dim_channel (channel_key),
    customer_key     INTEGER NOT NULL REFERENCES dim_customer (customer_key),
    store_key        INTEGER NOT NULL REFERENCES dim_store (store_key),
    province_key     INTEGER NOT NULL REFERENCES dim_province (province_key),
    product_key      INTEGER NOT NULL REFERENCES dim_product (product_key),
    es_venta         BOOLEAN NOT NULL,
    quantity         BIGINT NOT NULL,
    unit_price       DECIMAL(12, 2) NOT NULL,
    discount_amount  DECIMAL(12, 2) NOT NULL,
    line_total       DECIMAL(12, 2) NOT NULL,
    venta_neta       DECIMAL(12, 2) NOT NULL
);

INSERT INTO fact_sales_order_item
SELECT
    i.order_item_id,
    i.order_id,
    o.date_key,
    o.channel_key,
    o.customer_key,
    o.store_key,
    o.province_key,
    p.product_key,
    o.es_venta,
    i.quantity,
    CAST(i.unit_price AS DECIMAL(12, 2)),
    CAST(i.discount_amount AS DECIMAL(12, 2)),
    CAST(i.line_total AS DECIMAL(12, 2)),
    CASE WHEN o.es_venta
         THEN CAST(i.line_total AS DECIMAL(12, 2))
         ELSE CAST(0 AS DECIMAL(12, 2)) END
FROM raw.sales_order_item AS i
JOIN fact_sales_order AS o ON o.order_id = i.order_id
JOIN dim_product AS p ON p.product_id = i.product_id;
