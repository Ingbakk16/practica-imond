# Dashboard EcoBottle AR — Power BI Desktop

Los diez CSV validados de [`dw/`](../dw) son la fuente del reporte. Este directorio contiene la función de importación [`fnCsv.m`](fnCsv.m) y las medidas propuestas en [`medidas.dax`](medidas.dax). El modelo y los controles reproducibles se documentan en [`VALIDACION.md`](../VALIDACION.md).

## 1. Importar en Windows

1. Abrí Power BI Desktop y creá un reporte vacío. En **Transformar datos → Administrar parámetros**, agregá `RutaDW` (tipo **Texto**) con la ruta absoluta de la carpeta `dw` del repositorio clonado en Windows, **sin barra final**; por ejemplo, `C:\Repos\practica-imond\dw`.
2. En Power Query, creá una consulta en blanco llamada **`fnCsv`**. Abrí su **Editor avanzado** y pegá [`fnCsv.m`](fnCsv.m). Lee los CSV como UTF-8, convierte celdas vacías en `null` y fija la cultura `en-US` para interpretar el punto decimal de los archivos.
3. Creá diez consultas en blanco. Para cada nombre de la tabla siguiente, pegá **solo su expresión** en el Editor avanzado y nombrá la consulta exactamente como figura en el encabezado. Dejá la carga habilitada para estas diez consultas; la función `fnCsv` no se carga como tabla.
4. Seleccioná **Cerrar y aplicar**. Verificá los recuentos de [`VALIDACION.md`](../VALIDACION.md). Los campos de importe usan `Currency.Type` (decimal fijo de cuatro posiciones de Power BI); mostralos como ARS con dos decimales. Las fechas y claves se asignan explícitamente.

### `dim_date`

```powerquery
fnCsv("dim_date", {{"date_key", Int64.Type}, {"date_value", type date}, {"year", Int64.Type}, {"month", Int64.Type}, {"month_name", type text}, {"day", Int64.Type}, {"day_name", type text}})
```

### `dim_channel`

```powerquery
fnCsv("dim_channel", {{"channel_key", Int64.Type}, {"channel_id", Int64.Type}, {"code", type text}, {"name", type text}})
```

### `dim_province`

```powerquery
fnCsv("dim_province", {{"province_key", Int64.Type}, {"province_id", Int64.Type}, {"code", type text}, {"name", type text}})
```

### `dim_product`

```powerquery
fnCsv("dim_product", {{"product_key", Int64.Type}, {"product_id", Int64.Type}, {"sku", type text}, {"name", type text}, {"category", type text}, {"family", type text}, {"list_price", Currency.Type}, {"status", type text}})
```

### `dim_customer`

```powerquery
fnCsv("dim_customer", {{"customer_key", Int64.Type}, {"customer_id", Int64.Type}, {"email", type text}, {"first_name", type text}, {"last_name", type text}, {"status", type text}, {"created_at", type datetime}})
```

### `dim_store`

```powerquery
fnCsv("dim_store", {{"store_key", Int64.Type}, {"store_id", Int64.Type}, {"name", type text}, {"address_id", Int64.Type}, {"city", type text}, {"province_code", type text}})
```

### `fact_sales_order`

```powerquery
fnCsv("fact_sales_order", {{"order_id", Int64.Type}, {"date_key", Int64.Type}, {"channel_key", Int64.Type}, {"customer_key", Int64.Type}, {"store_key", Int64.Type}, {"province_key", Int64.Type}, {"order_date", type datetime}, {"status", type text}, {"es_venta", type logical}, {"subtotal", Currency.Type}, {"tax_amount", Currency.Type}, {"shipping_fee", Currency.Type}, {"total_amount", Currency.Type}, {"venta_neta", Currency.Type}})
```

### `fact_sales_order_item`

```powerquery
fnCsv("fact_sales_order_item", {{"order_item_id", Int64.Type}, {"order_id", Int64.Type}, {"date_key", Int64.Type}, {"channel_key", Int64.Type}, {"customer_key", Int64.Type}, {"store_key", Int64.Type}, {"province_key", Int64.Type}, {"product_key", Int64.Type}, {"es_venta", type logical}, {"quantity", Int64.Type}, {"unit_price", Currency.Type}, {"discount_amount", Currency.Type}, {"line_total", Currency.Type}, {"venta_neta", Currency.Type}})
```

### `fact_web_session`

```powerquery
fnCsv("fact_web_session", {{"session_id", Int64.Type}, {"date_key", Int64.Type}, {"customer_key", Int64.Type}, {"started_at", type datetime}, {"ended_at", type datetime}, {"source", type text}, {"device", type text}, {"duration_seconds", Int64.Type}})
```

### `fact_nps_response`

```powerquery
fnCsv("fact_nps_response", {{"nps_id", Int64.Type}, {"date_key", Int64.Type}, {"channel_key", Int64.Type}, {"customer_key", Int64.Type}, {"responded_at", type datetime}, {"score", Int64.Type}, {"comment", type text}})
```

## 2. Modelo de relaciones

En **Vista de modelo**, quitá las relaciones automáticas que no coincidan con esta lista y creá las **16** relaciones siguientes. Todas: **uno a muchos**, dimensión (`1`) → hecho (`*`), **activas** y con **dirección de filtro única**. Nunca relaciones directamente dos hechos ni relaciones por las claves naturales `*_id`.

| Dimensión (`1`) | Hechos (`*`) con la misma clave |
|---|---|
| `dim_date[date_key]` | `fact_sales_order`, `fact_sales_order_item`, `fact_web_session`, `fact_nps_response` |
| `dim_customer[customer_key]` | `fact_sales_order`, `fact_sales_order_item`, `fact_web_session`, `fact_nps_response` |
| `dim_channel[channel_key]` | `fact_sales_order`, `fact_sales_order_item`, `fact_nps_response` |
| `dim_province[province_key]` | `fact_sales_order`, `fact_sales_order_item` |
| `dim_store[store_key]` | `fact_sales_order`, `fact_sales_order_item` |
| `dim_product[product_key]` | `fact_sales_order_item` |

Ocultá `*_key`, `*_id` y `order_id` en la **vista de reporte** (no en el modelo). Ordená `dim_date[month_name]` por `dim_date[month]`; usá `dim_date[date_value]` o el par año/mes como eje en lugar de la jerarquía automática de los timestamps.

**Alcance de filtros:** fecha y cliente afectan a los cuatro hechos; canal afecta ventas y NPS, pero no sesiones web; provincia afecta ventas y líneas, no sesiones ni NPS; producto afecta **solo ítems**. Mantener los filtros unidireccionales evita atribuir NPS, sesiones o el total de un pedido a un producto por una coincidencia de cliente.

## 3. Medidas y páginas

En **Modelado → Nueva medida**, creá cada medida de [`medidas.dax`](medidas.dax) por separado. Si la configuración regional del editor DAX usa `;` como separador de argumentos, reemplazá las comas de las funciones por `;`. Mostrar `Ventas ARS`, `Ventas por Producto ARS` y `Ticket Promedio ARS` como moneda ARS; `NPS` como **número con un decimal**, en puntos (no porcentaje). `Ventas ARS` incluye IVA y envío, mientras que `Ventas por Producto ARS` usa líneas sin IVA ni envío. Los compradores son clientes con pedido de venta; los usuarios activos son clientes identificados con sesión, sin contar `-1`.

| Página | Visualizaciones sugeridas | Filtros pertinentes |
|---|---|---|
| **Resumen** | Tarjetas de ventas, pedidos y ticket; ventas mensuales; ventas por canal. | Fecha y canal. |
| **Ventas** | Ventas por provincia de destino; tabla de ventas por producto y ranking mensual (líneas sin IVA ni envío); compras por tienda. | Fecha, canal, provincia; producto solo sobre visuales de líneas. |
| **Clientes** | Clientes compradores y usuarios activos por mes, en series diferenciadas; estado del cliente como dato de la foto del origen. | Fecha; indicar que ambas métricas miden actividades diferentes. |
| **Adquisición web** | Sesiones por fuente y dispositivo, anónimas, duración media en segundos. | Fecha, fuente y dispositivo; no canal ni provincia. |
| **Satisfacción** | NPS y respuestas, evolución mensual, promotores/detractores y desglose por canal. | Fecha de respuesta y canal; no fecha de compra. |

Para evitar que un segmentador de producto afecte tarjetas de importe de pedido: ponelo únicamente en las visualizaciones de líneas de producto o deshabilitá su interacción con las tarjetas de `Ventas ARS` y `Pedidos` mediante **Formato → Editar interacciones**. No interpretes una sesión anónima como usuario único.

## 4. Comprobación y entrega del `.pbix`

Sin filtros, las tarjetas deben mostrar: **Ventas ARS = $382.410.636,00**, **Pedidos = 10.998**, **Sesiones = 100.363**, **Sesiones Anonimas = 70.751**, **Respuestas NPS = 3.083**, **NPS = 30,0** y **Ventas por Producto ARS = $309.891.600,00**. Con enero de 2024 seleccionado: **460 pedidos**, **$15.965.464,50** de ventas, **424 usuarios activos**, **3.226 sesiones anónimas** y **NPS 37,6**. Por canal, el NPS es **ONLINE 24,0** y **OFFLINE 40,9**. Compará los otros meses con [`PERFILADO.md`](../PERFILADO.md) o `sql/03_consultas.sql`.

Guardá el reporte como `powerbi/EcoBottle_AR.pbix` y volvé a abrirlo en Power BI Desktop para comprobar relaciones, medidas y **Actualizar** con `RutaDW`. La fase 7 del [`ROADMAP.md`](../ROADMAP.md) se cierra cuando el `.pbix` esté incorporado y se hayan verificado las cinco páginas y sus filtros en Windows.
