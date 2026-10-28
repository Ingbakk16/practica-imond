# Roadmap de construcción

Plan incremental para pasar de las tablas transaccionales al data warehouse y a un conjunto de KPIs listo para analizar en Power BI.

## Resultado objetivo

Construir un modelo estrella reproducible que permita analizar ventas, clientes, comportamiento web y satisfacción, sin modificar los datos de origen y con resultados auditables desde las claves naturales.

## Fase 0: Línea base

**Objetivo:** confirmar que el repositorio puede reproducir el estado inicial.

- [x] Crear el entorno virtual e instalar `requirements.txt`.
- [x] Ejecutar `python3 generator/validate_raw.py`.
- [x] Explorar las 13 tablas del esquema `raw`.
- [x] Registrar las definiciones de venta, NPS y sesiones.
- [x] Confirmar que `raw/` no se modifica durante el trabajo.

**Entregable:** entorno funcional y reglas de negocio identificadas en [`PERFILADO.md`](PERFILADO.md).

## Fase 1: Perfilado de fuentes

**Objetivo:** conocer las columnas, relaciones, cardinalidades y nulos antes de modelar.

- [x] Revisar el esquema de cada tabla con `DESCRIBE`.
- [x] Medir filas, valores nulos y valores distintos de las columnas relevantes.
- [x] Comprobar las relaciones indicadas por el DER.
- [x] Identificar estados que cuentan y no cuentan como venta.
- [x] Definir las columnas de fecha que usará cada KPI.

**Entregable:** inventario de fuentes y reglas de transformación en [`PERFILADO.md`](PERFILADO.md).

## Fase 2: Dimensiones

**Objetivo:** crear las dimensiones reutilizables del modelo estrella.

- [x] Completar `dim_product`, incluyendo categoría y familia.
- [x] Crear `dim_date` para el período 2024-01-01 a 2025-09-30.
- [x] Crear `dim_channel`.
- [x] Crear `dim_province`.
- [x] Crear `dim_customer`.
- [x] Crear `dim_store`.
- [x] Resolver nulos con filas `Desconocido` cuando sea necesario.
- [x] Mantener las claves naturales para trazabilidad.

**Entregable:** `sql/01_dimensiones.sql` completo y validado.

## Fase 3: Hechos de ventas

**Objetivo:** representar correctamente el proceso comercial sin duplicar importes.

- [x] Crear `fact_sales_order` con grano de un pedido.
- [x] Crear `fact_sales_order_item` con grano de una línea de producto por pedido.
- [x] Incorporar canal, cliente, tienda, fechas y provincia.
- [x] Incluir subtotal, IVA, envío, total, cantidades, descuentos y ventas netas.
- [x] Definir claramente cómo tratar `PAID`, `FULFILLED`, `CANCELLED` y `REFUNDED`.
- [x] Comprobar que la suma de los ítems coincide con el subtotal del pedido.
- [x] Comprobar que el total del pedido no se multiplica al unirlo con ítems.

**Entregable:** hechos de ventas con claves foráneas y controles de conciliación.

## Fase 4: Hechos de interacción y satisfacción

**Objetivo:** incorporar el comportamiento digital y la experiencia del cliente.

- [x] Crear `fact_web_session` con una fila por sesión.
- [x] Crear `fact_nps_response` con una fila por respuesta.
- [x] Relacionar sesiones con cliente cuando esté identificado.
- [x] Conservar sesiones y respuestas anónimas con clave `-1`.
- [x] Incorporar fuente, dispositivo, duración y puntaje.
- [x] Documentar la diferencia entre fecha de respuesta y fecha de compra.

**Entregable:** hechos de sesiones y NPS listos para segmentación.

## Fase 5: KPIs y controles

**Objetivo:** demostrar que el modelo responde las preguntas de negocio.

- [x] Crear control de filas por tabla.
- [x] Crear control de claves huérfanas y dimensiones desconocidas.
- [x] Calcular ventas mensuales y cantidad de pedidos.
- [x] Calcular ticket promedio.
- [x] Calcular clientes y usuarios activos.
- [x] Calcular ventas por canal y provincia.
- [x] Crear ranking mensual por producto.
- [x] Calcular NPS total y por canal.
- [x] Analizar sesiones por fuente y dispositivo.
- [x] Comparar los resultados con los KPIs de `validate_raw.py`.

**Entregable:** `sql/03_consultas.sql` con consultas reproducibles y verificables.

## Fase 6: Validación integral

**Objetivo:** asegurar que el proceso completo sea repetible.

- [x] Ejecutar la validación del origen.
- [x] Ejecutar `python3 run_sql.py` desde un estado limpio.
- [x] Revisar todos los CSV de `dw/`.
- [x] Revisar `dw/modelo_estrella.md`.
- [x] Confirmar que cada hecho tiene el grano documentado.
- [x] Comparar totales entre origen, hechos y consultas KPI.
- [x] Probar casos con `NULL`, pedidos cancelados, devoluciones y clientes anónimos.

**Entregable:** warehouse generado sin errores y con resultados conciliados en [`VALIDACION.md`](VALIDACION.md); auditoría reproducible con `python validate_warehouse.py`.

## Fase 7: Consumo en Power BI

**Objetivo:** preparar una capa analítica clara para el dashboard.

- [x] Importar los CSV de `dw/`.
- [x] Reproducir las relaciones del modelo estrella.
- [x] Ocultar claves técnicas en la vista del reporte.
- [x] Crear medidas para ventas, pedidos, ticket, usuarios y NPS.
- [x] Crear páginas para resumen, ventas, clientes, adquisición y satisfacción.
- [x] Verificar que los filtros de fecha, canal, provincia y producto funcionen.
- [x] Documentar las medidas y sus reglas de inclusión en [`powerbi/`](powerbi/).

**Entregable:** [`powerbi/EcoBottle_AR.pbix`](powerbi/EcoBottle_AR.pbix), construido y comprobado en Power BI Desktop. Incluye cinco páginas y datos importados; proyecto editable y controles en [`powerbi/ENTREGA.md`](powerbi/ENTREGA.md).

## Definición de terminado

El proyecto está listo cuando:

- El origen pasa todas las validaciones.
- El warehouse se puede regenerar desde cero con un único comando.
- Las dimensiones y hechos tienen claves y grano documentados.
- Las consultas KPI no duplican pedidos ni importes.
- Los resultados principales concilian con las reglas del generador.
- `dw/modelo_estrella.md` describe las relaciones implementadas.
- Los CSV de `dw/` pueden consumirse directamente en Power BI.
