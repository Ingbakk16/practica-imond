# Práctica — Introducción al Marketing Online y los Negocios Digitales

Este repositorio tiene los datos de **EcoBottle AR** para la práctica.

**Dashboard:** [`powerbi/EcoBottle_AR.pbix`](powerbi/EcoBottle_AR.pbix), con cinco páginas, modelo y datos importados. Ver los [controles de la entrega](powerbi/ENTREGA.md) y la [guía de actualización](powerbi/README.md).

- **Consigna:** [Práctica](https://docs.google.com/document/d/15RNP3FVqLjO4jzh80AAkK6mUR5DOLqPxLjQxqvdzrYg/edit?usp=sharing)
- **Diagrama de las tablas de origen (DER):** [ver más abajo](#diagrama-de-las-tablas-de-origen-der)

## ¿Qué hay en el repositorio?

```
raw/               los datos de origen: un archivo CSV por tabla (en SQL: raw.<tabla>)
sql/               acá escribís tus transformaciones en SQL        ← tu trabajo va acá
run_sql.py         ejecuta tus archivos SQL y arma el data warehouse
requirements.txt   lo que hay que instalar (DuckDB)
dw/                el data warehouse: se crea solo al ejecutar run_sql.py
generator/         el programa que creó los datos de raw/ (no hace falta usarlo)
assets/            el diagrama de tablas de origen (DER)
WORKFLOW.md        el flujo de trabajo para construir y validar el warehouse
ROADMAP.md         las fases y entregables de la construcción
PERFILADO.md        línea base, perfilado de las 13 fuentes y KPIs de referencia
VALIDACION.md       auditoría integral del warehouse y sus exportaciones
validate_warehouse.py  compara los CSV de dw/ con DuckDB y revisa las relaciones
powerbi/            importación parametrizada, medidas y guía del dashboard
```

> ⚠️ **No modifiques los archivos de `raw/`.** Son los datos de origen. Tus consultas SQL los leen y el resultado queda en `dw/`.

**Extensión cloud opcional:** el [roadmap BigQuery](ROADMAP_BIGQUERY.md) y la [guía de configuración](cloud/README.md) describen la carga histórica y los lotes diarios manuales con GitHub Actions y dbt. El circuito local de esta práctica sigue funcionando sin cuenta de Google Cloud.

## Los datos en un minuto

- Son una **foto del sistema de ventas** de EcoBottle, tomada el **30/09/2025 a las 23:59:59**.
- Tienen los pedidos del **01/01/2024 al 30/09/2025**.
- Los montos están en **pesos argentinos**, y los precios de lista **no incluyen IVA**.
- Las fechas y horas están en **hora de Argentina**.
- Una **celda vacía** en un CSV significa que ese dato no existe. En SQL aparece como `NULL`.

## Las tablas

| Archivo | Qué guarda | Filas |
|---|---|---:|
| `channel.csv` | Los 2 canales de venta: `ONLINE` (web) y `OFFLINE` (tiendas) | 2 |
| `province.csv` | Las 4 provincias donde opera la empresa | 4 |
| `product_category.csv` | Categorías de producto: *Bottles* → *Classic* y *Sport* | 3 |
| `product.csv` | Los 2 productos: Classic A y Sport B | 2 |
| `store.csv` | Las 4 tiendas físicas | 4 |
| `customer.csv` | Los clientes | ~3.500 |
| `address.csv` | Las direcciones de clientes y tiendas | ~3.800 |
| `sales_order.csv` | Los pedidos: quién compró, cuándo, por qué canal y cuánto pagó | ~12.000 |
| `sales_order_item.csv` | Los productos de cada pedido (una fila por producto) | ~14.500 |
| `payment.csv` | El pago de cada pedido | ~12.000 |
| `shipment.csv` | Los envíos por correo | ~7.000 |
| `web_session.csv` | Las visitas a la web | ~100.000 |
| `nps_response.csv` | Las respuestas a la encuesta de satisfacción (NPS) | ~3.000 |

En SQL, cada archivo es una tabla del esquema `raw`: `raw/sales_order.csv` se consulta como `raw.sales_order`.

### Diagrama de las tablas de origen (DER)

Cada caja es una tabla (un CSV de `raw/`) y cada línea une una clave foránea (FK) con la clave primaria (PK) a la que apunta.

![Diagrama entidad-relación de las tablas de origen](./assets/DER.png)

## Cómo leer los datos

### Pedidos
- **Pedido online:** `store_id` está vacío.
- **Compra en tienda:** `store_id` indica la tienda, y la "dirección de envío" es la dirección de la tienda (el cliente se lleva el producto en el momento).
- **Las cuentas siempre cierran:**
  - `line_total` = cantidad × precio − descuento
  - `subtotal` = suma de los `line_total` del pedido
  - `tax_amount` = 21 % del subtotal (IVA)
  - `total_amount` = subtotal + IVA + costo de envío

### Estados de un pedido (`sales_order.status`)

| Estado | Qué significa | ¿Cuenta como venta? |
|---|---|:---:|
| `CREATED` | Se hizo el pedido pero todavía no se pagó | No |
| `PAID` | Está pagado pero todavía no se entregó | Sí |
| `FULFILLED` | Ya se entregó (o se compró en la tienda) | Sí |
| `CANCELLED` | Se canceló: el pago fue rechazado, no se pagó a tiempo o el cliente se arrepintió | No |
| `REFUNDED` | Se entregó, pero después se devolvió el dinero | No |

### Pagos y envíos
- Cada pedido tiene **un pago**. Si el pago no se concretó, `paid_at` está vacío.
- **Solo tienen envío** (`shipment`) los pedidos que viajan por correo: los online y algunos que la tienda manda a domicilio. Las compras en tienda no tienen envío.
- **Estados del envío:**
  - `READY`: se está preparando.
  - `SHIPPED`: está viajando.
  - `DELIVERED`: se entregó.
  - `CANCELLED`: no salió.

### Clientes y visitas a la web
- Un cliente con `status = 'I'` dio de baja su cuenta. Sus compras anteriores siguen en los datos.
- En `web_session`, un `customer_id` vacío es un visitante que no inició sesión.
- **Origen de la visita** (`source`):
  - `ads`: publicidad en redes.
  - `direct`: entró directo o desde el newsletter.
  - `referral`: vino de otro sitio o del newsletter.
  - `organic`: buscadores.

### Encuesta NPS
- **Cuándo se manda:**
  - Pedidos entregados por correo: **7 días después de la entrega**.
  - Compras en tienda: **al día siguiente**.
- El puntaje va de 0 a 10. Un `customer_id` vacío es una respuesta anónima.
- La encuesta **no tiene número de pedido**: se relaciona con el cliente (`customer_id`) y con el canal (`channel_id`).

## Para empezar

Vas a escribir las transformaciones en **SQL** usando **DuckDB**, una base de datos que se instala con Python. No necesita servidor ni crear cuentas.

### 1. Preparar tu computadora (una sola vez)

Necesitás tener instalado Python 3.9 o más nuevo y Git. Primero hacé un **fork** de este repositorio en GitHub y después, en la terminal:

```bash
git clone URL-DE-TU-FORK
cd NOMBRE-DE-LA-CARPETA
python -m venv .venv
```

Activá el entorno virtual:

- **Mac / Linux:** `source .venv/bin/activate`
- **Windows:** `.venv\Scripts\activate`

Instalá DuckDB:

```bash
pip install -r requirements.txt
```

> En Mac, si el comando `python` no existe, usá `python3`. Cada vez que abras una terminal nueva, volvé a activar el entorno.

### 2. Explorar las tablas de origen

```bash
python run_sql.py --explorar
```

Abre DuckDB en el navegador con las 13 tablas de origen cargadas. Hacé clic en una tabla para ver sus columnas y datos, y escribí consultas para conocerla:

```sql
SELECT * FROM raw.sales_order LIMIT 10;
DESCRIBE raw.sales_order;
```

- **No ejecuta tus archivos de `sql/`**, así que funciona aunque todavía no hayas escrito nada o tengas errores.
- **Necesita internet.** Sin conexión se abre una consola SQL en la terminal: terminás cada consulta con `;` y salís escribiendo `salir`.
- **Para cerrar,** volvé a la terminal y presioná Enter.

### 3. Revisar y ampliar las transformaciones en SQL

| Archivo | Qué va adentro |
|---|---|
| `sql/01_dimensiones.sql` | Dimensiones de fecha, canal, provincia, producto, cliente y tienda. |
| `sql/02_hechos.sql` | Hechos de pedidos, ítems, sesiones web y respuestas NPS, con claves foráneas hacia las dimensiones. |
| `sql/03_consultas.sql` | Controles de conciliación y KPIs de ventas, clientes, tráfico y NPS. |

Cada ejecución vuelve a construir estas tablas desde los CSV. Para ampliar el modelo, pasá las consultas que probaste al archivo correspondiente. Podés agregar más archivos: se ejecutan en orden alfabético (`01_...`, `02_...`, `03_...`).

Los hechos conservan todos los pedidos y sus ítems. La columna `es_venta` identifica pedidos `PAID` y `FULFILLED`; `venta_neta` es cero para `CREATED`, `CANCELLED` y `REFUNDED`. En `fact_sales_order`, `venta_neta` incluye IVA y envío; en `fact_sales_order_item`, es el importe de la línea sin IVA ni envío. Para ventas totales usá **solo** el hecho de pedidos: al unirlo con los ítems, un pedido de dos líneas multiplicaría su total. Las compras online usan la fila `Sin tienda` (`store_key = -1`).

Cada fila de `fact_web_session` representa una sesión: `date_key` corresponde a `started_at` y `duration_seconds` queda `NULL` si no hay `ended_at`. Cada fila de `fact_nps_response` representa una respuesta: su fecha es `responded_at`, **no** la fecha de compra. Las sesiones y respuestas anónimas usan `customer_key = -1`; no se pueden atribuir a un cliente concreto ni a un pedido por coincidencia de canal o fecha.

**Cómo se calculan los indicadores:** pedidos y ventas mensuales usan `fact_sales_order` con `es_venta`; ticket promedio = suma de `venta_neta` / cantidad de pedidos de venta; clientes compradores = clientes distintos con pedidos de venta en el mes. Usuarios web activos = clientes distintos con sesiones iniciadas ese mes, excluyendo `-1`; las sesiones anónimas se cuentan aparte, sin considerarlas personas únicas. Ventas por producto usan `fact_sales_order_item.venta_neta` (sin IVA ni envío). NPS = 100 × (promotores con puntaje 9–10 − detractores con puntaje 0–6) / total de respuestas; 7–8 son pasivos. La duración promedio excluye sesiones sin cierre. Para comparar el desglose mensual con el origen, consultá [`PERFILADO.md`](PERFILADO.md).

Para validar toda la construcción y contrastar cada CSV con su tabla de DuckDB, ejecutá `python validate_warehouse.py` después de `python run_sql.py`. Los resultados se detallan en [`VALIDACION.md`](VALIDACION.md). Para llevar el modelo a Power BI Desktop, seguí la [guía de importación y medidas](powerbi/README.md).

### 4. Armar el data warehouse

```bash
python run_sql.py
```

Esto hace cuatro cosas:

1. Crea la base de datos `warehouse.duckdb` desde cero.
2. Ejecuta tus archivos de `sql/` en orden y muestra en la terminal el resultado de cada `SELECT`.
3. Guarda cada tabla que creaste como CSV en `dw/`. **Esos CSV son los que después abrís en Power BI.**
4. Dibuja tu modelo estrella en `dw/modelo_estrella.md`.

Si hay un error, te dice en qué archivo y en qué sentencia está y por qué falló. Lo corregís y volvés a ejecutar. Como todo se arma desde cero cada vez, no hace falta borrar tablas a mano.

> La base `warehouse.duckdb` no se sube a GitHub (está en `.gitignore`): cualquiera la vuelve a crear con `python run_sql.py`.

### 5. Ver tu modelo

- **El diagrama:** abrí `dw/modelo_estrella.md` en GitHub y vas a ver el modelo dibujado, con las claves y las relaciones. Podés copiarlo en tu README. En VS Code se ve con la extensión *Markdown Preview Mermaid Support*.
- **Tus tablas en el navegador:** `python run_sql.py --ui` arma el data warehouse y después abre DuckDB con tus tablas y las de origen, para revisar resultados y armar gráficos rápidos.

### Mini guía de SQL en DuckDB

```sql
-- Ver las primeras filas de una tabla de origen
SELECT * FROM raw.sales_order LIMIT 10;

-- Ver sus columnas y tipos
DESCRIBE raw.sales_order;

-- Agrupar por mes
SELECT DATE_TRUNC('month', order_date) AS mes, COUNT(*) AS pedidos
FROM raw.sales_order
GROUP BY mes
ORDER BY mes;
```

- **Datos vacíos:** se buscan con `IS NULL`, y `COALESCE(columna, valor)` reemplaza un vacío por un valor.
- **Más ayuda:** [documentación de SQL de DuckDB](https://duckdb.org/docs/current/sql/introduction.html).

## ¿Y la carpeta `generator/`?

Es el programa que **inventó estos datos** simulando el negocio: clientes que se registran, compran, pagan, reciben el envío y responden la encuesta. **No lo necesitás para la práctica.** Si te interesa ver cómo se arma un conjunto de datos de prueba, podés leerlo; el detalle está en [`generator/README.md`](./generator/README.md).

Si alguna vez querés volver a generar los datos o comprobar que están bien:

```bash
python generator/generate_raw.py     # vuelve a crear los CSV de raw/ (salen idénticos)
python generator/validate_raw.py     # revisa que los datos cumplan todas las reglas
```
