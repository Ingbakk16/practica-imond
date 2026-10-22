# Roadmap de construcción

Plan incremental para pasar de las tablas transaccionales al data warehouse y a un conjunto de KPIs listo para analizar en Power BI.

## Resultado objetivo

Construir un modelo estrella reproducible que permita analizar ventas, clientes, comportamiento web y satisfacción, sin modificar los datos de origen y con resultados auditables desde las claves naturales.

## Fase 0: Línea base

**Objetivo:** confirmar que el repositorio puede reproducir el estado inicial.

- [ ] Crear el entorno virtual e instalar `requirements.txt`.
- [ ] Ejecutar `python3 generator/validate_raw.py`.
- [ ] Explorar las 13 tablas del esquema `raw`.
- [ ] Registrar las definiciones de venta, NPS y sesiones.
- [ ] Confirmar que `raw/` no se modifica durante el trabajo.

**Entregable:** entorno funcional y reglas de negocio identificadas.

## Fase 1: Perfilado de fuentes

**Objetivo:** conocer las columnas, relaciones, cardinalidades y nulos antes de modelar.

- [ ] Revisar el esquema de cada tabla con `DESCRIBE`.
- [ ] Medir filas, valores nulos y valores distintos de las columnas relevantes.
- [ ] Comprobar las relaciones indicadas por el DER.
- [ ] Identificar estados que cuentan y no cuentan como venta.
- [ ] Definir las columnas de fecha que usará cada KPI.

**Entregable:** inventario de fuentes y reglas de transformación.

## Fase 2: Dimensiones

**Objetivo:** crear las dimensiones reutilizables del modelo estrella.

- [ ] Completar `dim_product`, incluyendo categoría y familia.
- [ ] Crear `dim_date` para el período 2024-01-01 a 2025-09-30.
- [ ] Crear `dim_channel`.
- [ ] Crear `dim_province`.
- [ ] Crear `dim_customer`.
- [ ] Crear `dim_store`.
- [ ] Resolver nulos con filas `Desconocido` cuando sea necesario.
- [ ] Mantener las claves naturales para trazabilidad.

**Entregable:** `sql/01_dimensiones.sql` completo y validado.

## Fase 3: Hechos de ventas

**Objetivo:** representar correctamente el proceso comercial sin duplicar importes.

- [ ] Crear `fact_sales_order` con grano de un pedido.
- [ ] Crear `fact_sales_order_item` con grano de una línea de producto por pedido.
- [ ] Incorporar canal, cliente, tienda, fechas y provincia.
- [ ] Incluir subtotal, IVA, envío, total, cantidades, descuentos y ventas netas.
- [ ] Definir claramente cómo tratar `PAID`, `FULFILLED`, `CANCELLED` y `REFUNDED`.
- [ ] Comprobar que la suma de los ítems coincide con el subtotal del pedido.
- [ ] Comprobar que el total del pedido no se multiplica al unirlo con ítems.

**Entregable:** hechos de ventas con claves foráneas y controles de conciliación.

## Fase 4: Hechos de interacción y satisfacción

**Objetivo:** incorporar el comportamiento digital y la experiencia del cliente.

- [ ] Crear `fact_web_session` con una fila por sesión.
- [ ] Crear `fact_nps_response` con una fila por respuesta.
- [ ] Relacionar sesiones con cliente cuando esté identificado.
- [ ] Conservar sesiones y respuestas anónimas con clave `-1`.
- [ ] Incorporar fuente, dispositivo, duración y puntaje.
- [ ] Documentar la diferencia entre fecha de respuesta y fecha de compra.

**Entregable:** hechos de sesiones y NPS listos para segmentación.

## Fase 5: KPIs y controles

**Objetivo:** demostrar que el modelo responde las preguntas de negocio.

- [ ] Crear control de filas por tabla.
- [ ] Crear control de claves huérfanas y dimensiones desconocidas.
- [ ] Calcular ventas mensuales y cantidad de pedidos.
- [ ] Calcular ticket promedio.
- [ ] Calcular clientes y usuarios activos.
- [ ] Calcular ventas por canal y provincia.
- [ ] Crear ranking mensual por producto.
- [ ] Calcular NPS total y por canal.
- [ ] Analizar sesiones por fuente y dispositivo.
- [ ] Comparar los resultados con los KPIs de `validate_raw.py`.

**Entregable:** `sql/03_consultas.sql` con consultas reproducibles y verificables.

## Fase 6: Validación integral

**Objetivo:** asegurar que el proceso completo sea repetible.

- [ ] Ejecutar la validación del origen.
- [ ] Ejecutar `python3 run_sql.py` desde un estado limpio.
- [ ] Revisar todos los CSV de `dw/`.
- [ ] Revisar `dw/modelo_estrella.md`.
- [ ] Confirmar que cada hecho tiene el grano documentado.
- [ ] Comparar totales entre origen, hechos y consultas KPI.
- [ ] Probar casos con `NULL`, pedidos cancelados, devoluciones y clientes anónimos.

**Entregable:** warehouse generado sin errores y con resultados conciliados.

## Fase 7: Consumo en Power BI

**Objetivo:** preparar una capa analítica clara para el dashboard.

- [ ] Importar los CSV de `dw/`.
- [ ] Reproducir las relaciones del modelo estrella.
- [ ] Ocultar claves técnicas en la vista del reporte.
- [ ] Crear medidas para ventas, pedidos, ticket, usuarios y NPS.
- [ ] Crear páginas para resumen, ventas, clientes, adquisición y satisfacción.
- [ ] Verificar que los filtros de fecha, canal, provincia y producto funcionen.
- [ ] Documentar las medidas y sus reglas de inclusión.

**Entregable:** dashboard conectado al modelo exportado y consistente con SQL.

## Definición de terminado

El proyecto está listo cuando:

- El origen pasa todas las validaciones.
- El warehouse se puede regenerar desde cero con un único comando.
- Las dimensiones y hechos tienen claves y grano documentados.
- Las consultas KPI no duplican pedidos ni importes.
- Los resultados principales concilian con las reglas del generador.
- `dw/modelo_estrella.md` describe las relaciones implementadas.
- Los CSV de `dw/` pueden consumirse directamente en Power BI.
