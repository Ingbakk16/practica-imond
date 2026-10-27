-- =====================================================================
-- 01_dimensiones.sql — Tablas de DIMENSIONES del modelo estrella
-- =====================================================================
-- Para cada dimensión:
--   1. CREATE TABLE con sus columnas, tipos y PRIMARY KEY.
--   2. INSERT INTO ... SELECT para cargarla desde las tablas de origen.
--
-- Las tablas de origen (los CSV de raw/) están en el esquema raw:
--     FROM raw.product
-- Para ver qué columnas y tipos tiene una:  DESCRIBE raw.product;
-- Para explorarlas antes de escribir nada:  python run_sql.py --explorar
-- =====================================================================


-- ---------------------------------------------------------------------
-- Producto: una fila por producto, con la jerarquía aplanada.
-- ---------------------------------------------------------------------
-- En raw/ la categoría está en otra tabla y tiene jerarquía
-- (Bottles -> Classic / Sport). En la dimensión la "aplanamos":
-- cada producto queda en una sola fila con su categoría y su familia.
--
-- product_key es la clave SUBROGADA: un número propio del data warehouse.
-- product_id es la clave NATURAL: el ID que viene del sistema de origen.
-- Las tablas de hechos usan product_key; product_id sirve para encontrarla.

CREATE TABLE dim_product (
    product_key INTEGER PRIMARY KEY,
    product_id  INTEGER NOT NULL UNIQUE,
    sku         VARCHAR NOT NULL UNIQUE,
    name        VARCHAR NOT NULL,
    category    VARCHAR,             -- Classic / Sport
    family      VARCHAR,             -- Bottles
    list_price  DECIMAL(12, 2),
    status      VARCHAR NOT NULL
);

INSERT INTO dim_product
SELECT
    ROW_NUMBER() OVER (ORDER BY p.product_id) AS product_key,
    p.product_id,
    p.sku,
    p.name,
    c.name AS category,
    f.name AS family,
    CAST(p.list_price AS DECIMAL(12, 2)),
    p.status
FROM raw.product AS p
LEFT JOIN raw.product_category AS c ON c.category_id = p.category_id   -- categoría
LEFT JOIN raw.product_category AS f ON f.category_id = c.parent_id;    -- familia (categoría padre)


-- ---------------------------------------------------------------------
-- Fecha: una fila por día del período de análisis (639 días).
-- ---------------------------------------------------------------------
CREATE TABLE dim_date (
    date_key   INTEGER PRIMARY KEY,   -- YYYYMMDD
    date_value DATE NOT NULL UNIQUE,
    year       INTEGER NOT NULL,
    month      INTEGER NOT NULL,
    month_name VARCHAR NOT NULL,
    day        INTEGER NOT NULL,
    day_name   VARCHAR NOT NULL
);

INSERT INTO dim_date
SELECT
    CAST(strftime(day_value, '%Y%m%d') AS INTEGER),
    CAST(day_value AS DATE),
    year(day_value),
    month(day_value),
    monthname(day_value),
    day(day_value),
    dayname(day_value)
FROM range(DATE '2024-01-01', DATE '2025-10-01', INTERVAL 1 DAY) AS days(day_value);


-- ---------------------------------------------------------------------
-- Catálogos: claves sustitutas estables según la clave natural.
-- ---------------------------------------------------------------------
CREATE TABLE dim_channel (
    channel_key INTEGER PRIMARY KEY,
    channel_id  INTEGER NOT NULL UNIQUE,
    code        VARCHAR NOT NULL UNIQUE,
    name        VARCHAR NOT NULL
);

INSERT INTO dim_channel
SELECT ROW_NUMBER() OVER (ORDER BY channel_id), channel_id, code, name
FROM raw.channel;

CREATE TABLE dim_province (
    province_key INTEGER PRIMARY KEY,
    province_id  INTEGER NOT NULL UNIQUE,
    code         VARCHAR NOT NULL UNIQUE,
    name         VARCHAR NOT NULL
);

INSERT INTO dim_province
SELECT ROW_NUMBER() OVER (ORDER BY province_id), province_id, code, name
FROM raw.province;


-- ---------------------------------------------------------------------
-- Cliente: conservar inactivos para analizar sus compras históricas.
-- La fila -1 permitirá conservar sesiones y respuestas NPS anónimas.
-- ---------------------------------------------------------------------
CREATE TABLE dim_customer (
    customer_key INTEGER PRIMARY KEY,
    customer_id  INTEGER UNIQUE,
    email        VARCHAR,
    first_name   VARCHAR NOT NULL,
    last_name    VARCHAR,
    status       VARCHAR,
    created_at   TIMESTAMP
);

INSERT INTO dim_customer VALUES (-1, NULL, NULL, 'Desconocido', NULL, NULL, NULL);

INSERT INTO dim_customer
SELECT
    ROW_NUMBER() OVER (ORDER BY customer_id),
    customer_id, email, first_name, last_name, status, created_at
FROM raw.customer;


-- ---------------------------------------------------------------------
-- Tienda: -1 es "Sin tienda" (canal ONLINE), no una tienda faltante.
-- La ciudad y provincia describen la ubicación física de la tienda.
-- ---------------------------------------------------------------------
CREATE TABLE dim_store (
    store_key     INTEGER PRIMARY KEY,
    store_id      INTEGER UNIQUE,
    name          VARCHAR NOT NULL,
    address_id    INTEGER,
    city          VARCHAR,
    province_code VARCHAR
);

INSERT INTO dim_store VALUES (-1, NULL, 'Sin tienda', NULL, NULL, NULL);

INSERT INTO dim_store
SELECT
    ROW_NUMBER() OVER (ORDER BY s.store_id),
    s.store_id, s.name, s.address_id, a.city, p.code
FROM raw.store AS s
JOIN raw.address AS a ON a.address_id = s.address_id
JOIN raw.province AS p ON p.province_id = a.province_id;
