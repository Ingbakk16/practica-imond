# Roadmap — Generación diaria, BigQuery y dbt

## Objetivo

Extender la práctica de EcoBottle AR con datos sintéticos diarios y un pipeline en GitHub Actions: generar, cargar en BigQuery, transformar y validar con dbt Core, y consultar desde Power BI.

Este roadmap complementa, sin reemplazar, [`ROADMAP.md`](ROADMAP.md). Las reglas de referencia siguen siendo [`README.md`](README.md), [`WORKFLOW.md`](WORKFLOW.md) y [`generator/README.md`](generator/README.md); los controles históricos están en [`PERFILADO.md`](PERFILADO.md) y [`VALIDACION.md`](VALIDACION.md).

## Alcance y reglas que se conservan

- No modificar los CSV históricos de `raw/`, ni sobrescribirlos al probar generadores en CI. Usar una carpeta temporal de salida.
- Mantener el generador original y el circuito local `run_sql.py` → DuckDB → `dw/` como referencia reproducible de la práctica.
- Conservar las seis dimensiones, los cuatro hechos y el grano de cada tabla. No unir hechos de forma que se dupliquen importes.
- Venta: pedidos `PAID` o `FULFILLED`. Los demás estados tienen `venta_neta = 0`.
- En pedidos, `venta_neta` incluye IVA y envío; en ítems, no. Mantener importes decimales, no flotantes, en el warehouse.
- Ventas por fecha del pedido; sesiones por `started_at`; NPS por `responded_at`. Usar fechas de negocio de Argentina y documentar la conversión a UTC cuando corresponda.
- Conservar clientes anónimos con clave `-1` y compras online con tienda `-1`. No atribuir NPS a un pedido ni sesiones anónimas a personas únicas.
- Mantener las cinco páginas de Power BI y sus reglas de filtros y medidas.
- Conservar los estados e importes del histórico, incluidos los pedidos pendientes. Esta extensión solo agrega registros: no simula la evolución de pedidos existentes ni introduce otro modelo contable.

## Arquitectura inicial: lo mínimo necesario

```text
GitHub Actions (manual / diario)
  → Python: generar aproximadamente 100 pedidos nuevos y sus registros relacionados
  → Python: cargar un lote completo en BigQuery
  → dbt Core: staging → dimensiones y hechos → tests
  → Power BI: importar las tablas del warehouse
```

Usar tres datasets de BigQuery, en una misma ubicación:

| Dataset | Contenido |
|---|---|
| `ecobottle_raw` | Base histórica y nuevos registros de origen, identificados por lote. |
| `ecobottle_analytics` | Modelos de staging y las diez tablas analíticas. |
| `ecobottle_ops` | Un registro sencillo de lotes completos y resultados de ejecución. Sin estado del simulador ni eventos pendientes. |

Python genera e ingiere; dbt transforma y prueba. Ejecutar dbt Core en Actions, sin contratar dbt Cloud. Cargar archivos locales del runner mediante jobs batch de BigQuery: no hace falta un bucket ni streaming para empezar.

Reconstruir las tablas analíticas completas cada día. Por el volumen de la práctica, esto facilita la conciliación sin lógica incremental. Los datos de origen son append-only: repetir una ejecución no debe duplicarlos.

## Fase 0 — Decisiones y requisitos de acceso

- [x] Usar la cuenta GCP Free Trial disponible, con USD 300 de crédito informados por el usuario. No confundir el crédito de una sola vez con una franquicia gratuita permanente.
- [x] Ejecutar el pipeline en GitHub Actions; el repositorio es público.
- [x] Crear la base una sola vez con el generador existente, en una carpeta temporal y sin sobrescribir `raw/`. Conservar la semilla original para poder conciliar con la práctica.
- [x] Agregar aproximadamente 100 pedidos por día con el segundo generador, más sus clientes, direcciones, ítems y pagos relacionados. Son 100 pedidos, no 100 filas totales.
- [x] No modificar registros existentes. El objetivo es demostrar el workflow con datos sintéticos, no simular un sistema transaccional completo.
- [x] Usar Power BI Desktop con refresh manual inicialmente. La automatización de la visualización es opcional y no bloquea el pipeline.
- [ ] Confirmar que el proyecto elegido está vinculado a la cuenta de facturación de la prueba y registrar su fecha de vencimiento. Los créditos se informaron, pero el vínculo del proyecto y el vencimiento todavía no se verificaron.
- [ ] Configurar BigQuery on-demand, sin reservas de capacidad. Revisar antes del vencimiento si continuar requiere activar facturación de pago o detener la demo.
- [ ] Configurar alertas de presupuesto, cuotas de consultas y límites de bytes por consulta donde sea posible. Las alertas no bloquean cargos; no prometer costo cero.
- [ ] Registrar la fecha de inicio de los lotes diarios y revisar el almacenamiento de la demo periódicamente.

La base conserva el corte original al 30/09/2025. Los lotes diarios comienzan desde la fecha de puesta en marcha, procesando normalmente el día anterior en Argentina. No hace falta completar el intervalo histórico hasta la puesta en marcha: documentar ese salto como parte de la demo. Permitir rangos manuales solo para pruebas o recuperación de días omitidos desde su inicio.

Las franquicias publicadas de BigQuery incluyen 10 GiB de almacenamiento y 1 TiB mensual de consultas on-demand. Revisarlas al configurar el proyecto; también cuentan las consultas de dbt, sus tests y Power BI. El sandbox sin facturación tiene otras restricciones, incluida la expiración de tablas/particiones a los 60 días, y no es el objetivo inicial.

**Criterio de cierre:** decisiones registradas, proyecto y vencimiento verificados, y controles básicos de consumo configurados. No marcar la configuración cloud como completada solo por disponer de créditos.

## Fase 1 — Validar el proyecto actual en GitHub Actions

**Objetivo:** tener una línea base automática antes de migrar SQL o agregar simulación diaria.

- [x] Crear un workflow para pull requests y ejecución manual, con Python y dependencias fijadas.
- [x] Generar una copia temporal con el generador original y validarla sin escribir en `raw/`.
- [x] Ejecutar `run_sql.py` y `validate_warehouse.py` sobre el dataset histórico del repositorio.
- [x] Configurar logs y resúmenes de controles como artifacts de diagnóstico; no guardar datos generados mediante commits automáticos.
- [ ] Confirmar una ejecución exitosa en GitHub Actions y la descarga del artifact `validation-logs`.

**Estado:** workflow implementado en [`.github/workflows/validate.yml`](.github/workflows/validate.yml), validado con `actionlint`. Los comandos de validación, construcción y auditoría pasaron localmente en una copia temporal con Python 3.12 y DuckDB 1.5.5, sin modificar los CSV de `raw/` ni las exportaciones locales de `dw/`. Se verificó que la captura de logs conserva el código de error de un comando fallido. La [ejecución alojada en GitHub](https://github.com/Ingbakk16/practica-imond/actions/runs/41140959822) terminó exitosamente y publicó `validation-logs`; falta confirmar su descarga por el usuario. Ver [`WORKFLOW.md`](WORKFLOW.md#10-validación-automática-en-github-actions).

**Criterio de cierre:** la construcción y los controles existentes pasan en un runner limpio, sin modificar las fuentes históricas.

## Fase 2 — Cargar el histórico y migrar las transformaciones a dbt

**Objetivo:** reproducir el warehouse actual en BigQuery antes de cambiar sus datos.

- [x] Preparar el workflow manual y la guía de permisos OIDC / Workload Identity Federation, sin claves privadas de Google almacenadas en GitHub.
- [ ] Configurar realmente el proyecto GCP, los datasets, permisos y variables de GitHub, y verificar autenticación cloud.
- [x] Implementar generación temporal y validación de la base histórica, y su carga manual única con esquemas explícitos y protección contra duplicados.
- [x] Crear el proyecto dbt con `dbt-bigquery`: sources, staging, dimensiones y hechos basados en los SQL actuales.
- [x] Adaptar funciones y tipos de DuckDB a BigQuery, conservando los nombres de tablas/columnas del reporte.
- [x] Usar IDs numéricos de origen como claves estables en lugar de `ROW_NUMBER()`, conservando claves naturales y filas `-1`.
- [x] Extender `dim_date` hasta la última fecha de actividad de pedidos, sesiones y respuestas.
- [x] Agregar tests de unicidad, nulos, relaciones, estados válidos, importes, conciliación de ítems y rango de NPS. BigQuery no aplica las FK como DuckDB: los tests controlan esas relaciones.
- [x] Implementar la conciliación de diez conteos de tablas y KPIs históricos mensuales contra DuckDB.
- [ ] Ejecutar `dbt build` y la conciliación en BigQuery; repetir el workflow y confirmar que la carga se omite sin duplicados.

**Estado:** código y configuración en [`cloud/`](cloud/README.md), [`dbt/`](dbt/) y [`.github/workflows/bigquery.yml`](.github/workflows/bigquery.yml). Las comprobaciones locales incluyen tests offline del loader, `dbt parse` (21 modelos y 73 tests), `actionlint` y ejecución de los modelos y cinco tests SQL de negocio traducidos a DuckDB. Los resultados traducidos coinciden con los conteos y KPIs de la base histórica de referencia. Esa comprobación local no sustituye ejecutar los modelos en BigQuery. La configuración del proyecto y la aceptación cloud siguen pendientes: todavía no se proporcionó el project ID ni se verificaron permisos GCP.

**Criterio de cierre:** un workflow manual carga el histórico y ejecuta `dbt build`; los resultados concilian con la práctica original.

## Fase 3 — Agregar el segundo generador, solo de registros nuevos

**Objetivo:** agregar un lote diario pequeño y reproducible sin cambiar registros anteriores.

- [x] Agregar un generador diario con fecha, semilla y cantidad de pedidos explícitas (100 por defecto); reutilizar catálogos y reglas del original cuando sea práctico.
- [x] Usar IDs deterministas derivados de fecha y posición, en un rango separado del histórico y compatible con los tipos existentes. No mantener contadores ni un estado mutable entre runners.
- [x] Crear pedidos nuevos con sus clientes/direcciones, ítems y pagos necesarios. Usar operaciones ya finalizadas al corte del lote, sin actualizaciones futuras; las ventas presenciales con pago inmediato permiten empezar sin simular logística.
- [x] Si se agregan ventas online o sesiones, respetar sus relaciones y tiempos. No inventar encuestas NPS ni entregas con fechas incoherentes para completar todas las tablas: el histórico ya alimenta las cinco páginas.
- [x] Mantener intactos todos los registros anteriores, incluidos los pedidos históricos pendientes. No implementar eventos pendientes, devoluciones posteriores ni cambios de estado.
- [x] Identificar cada lote por fecha, semilla y versión del generador, con cantidades por tabla. Repetir la misma entrada debe producir la misma salida; un cambio de versión no debe agregar otro lote para una fecha ya cargada.
- [x] Implementar carga por lote sin duplicados. Ante una carga parcial, reemplazar o limpiar únicamente los registros de ese lote incompleto antes de repetirlo; nunca volver a anexarlos a ciegas.
- [x] Marcar un lote completo solo cuando sus tablas hayan sido cargadas y validadas. dbt debe leer únicamente lotes completos. Guardar ese registro en BigQuery, no depender de cache o artifacts de Actions.
- [x] Adaptar los controles del generador a fechas variables sin cambiar las expectativas del dataset histórico.
- [ ] Probar repetición del mismo día, siete días consecutivos y ejecución equivalente por rango en BigQuery; comprobar que los registros históricos no cambian. Los tests offline de repetición, siete días y equivalencia por rango ya pasan.

**Estado:** código de fase 3 implementado en [`generator/`](generator/), [`cloud/`](cloud/README.md), [`dbt/`](dbt/) y el workflow manual cloud. El workflow de PR valida ahora generador, loader y `dbt parse` sin credenciales; todavía falta confirmar esa nueva versión en GitHub Actions. Los tests offline locales pasan; el cierre cloud sigue bloqueado por la aceptación pendiente de fase 2 y la ausencia del workflow cloud en la rama predeterminada. Ver [`cloud/README.md`](cloud/README.md#fase-3-un-lote-diario-manual-sin-schedule).

**Criterio de cierre:** cada lote predeterminado agrega 100 pedidos; repetirlo no duplica registros; siete días juntos o por separado dan el mismo resultado y preservan el histórico.

## Fase 4 — Programar el pipeline y su recuperación

**Objetivo:** operación diaria sencilla, observable y recuperable.

- [ ] Agregar schedule diario y ejecución manual con rango de fechas. Procesar días completos según Argentina, no la hora accidental del runner.
- [ ] Detectar días faltantes desde la fecha de inicio de la demo y completarlos. El cron de Actions puede demorarse u omitirse; no asumir ejecución puntual.
- [ ] Impedir cargas concurrentes para la misma demo. Configurar timeout y reintentos acotados para errores transitorios.
- [ ] Separar progreso de generación/carga y progreso de dbt: si falla la transformación, repetirla sobre el mismo lote sin volver a generar datos distintos.
- [ ] Ejecutar validación del lote, controles de frescura y `dbt build`. Registrar filas, fechas procesadas, errores y bytes de consultas.
- [ ] Activar notificaciones de fallos y documentar cómo reintentar y completar días faltantes.
- [ ] Probar un fallo durante la carga y otro después de cargar, antes de terminar dbt.

**Criterio de cierre:** recuperar un día omitido o una ejecución fallida no requiere editar registros a mano ni borrar el warehouse.

## Fase 5 — Conectar Power BI y cerrar la entrega

**Objetivo:** conservar el dashboard, cambiando su fuente de CSV a BigQuery.

- [ ] Sustituir `RutaDW` / importación CSV por el conector de BigQuery en modo Import, con proyecto explícito y permisos de lectura/consulta necesarios.
- [ ] Revisar tipos monetarios, fechas, relaciones y medidas; conciliar las cinco páginas contra los KPIs del warehouse.
- [ ] Mostrar fecha de datos y última actualización exitosa.
- [ ] Si hay Power BI Service disponible, configurar credenciales cloud y solicitar el refresh solo después de que todos los controles pasen; verificar que el refresh termine correctamente.
- [ ] Si no hay Service, documentar actualización manual en Desktop como alcance inicial. Un warehouse actualizado no actualiza por sí solo el `.pbix` local.
- [ ] Como alternativa opcional de visualización web, evaluar Looker Studio con su conector BigQuery. Requiere recrear el reporte, respeta su propia política de frescura/cache y sus consultas cuentan para el consumo de BigQuery; no es requisito de cierre.
- [ ] Actualizar las guías de ejecución, validación y Power BI con ambos circuitos: práctica local y extensión cloud.
- [ ] Observar al menos siete ejecuciones diarias consecutivas y revisar el consumo real.

**Limitación inicial aceptada:** `dbt build` no es una transacción de todo el warehouse; si falla, algunas tablas pueden haberse actualizado. Con Power BI Import, no refrescar tras un fallo conserva la última copia importada. Evitar refreshes independientes durante la construcción y reconstruir antes de reintentar. La publicación atómica de múltiples tablas queda fuera del alcance inicial.

**Criterio de cierre:** datos diarios visibles en las cinco páginas, resultados conciliados, recuperación probada y consumo dentro del presupuesto acordado.

## Fuera del alcance inicial

- Airflow, Kubernetes, Terraform, streaming, buckets y servicios adicionales sin una necesidad concreta.
- Modelos incrementales, SCD tipo 2 y capas de publicación versionadas/atómicas.
- Actualizaciones de registros, simulación de ciclos de vida, colas de eventos y estado persistente del generador.
- Backfill obligatorio entre el corte histórico y la puesta en marcha de la demo.
- DirectQuery y automatización de Power BI Desktop con un runner Windows.
- Reemplazar o eliminar la práctica local y sus entregables históricos.

Revisar estas opciones solo si el volumen, costo o uso real lo exige. La primera entrega debe demostrar generación, carga, transformación y validación automáticas; no necesita comportarse como un sistema de producción.

## Referencias de configuración

- [Sandbox y restricciones de BigQuery](https://cloud.google.com/bigquery/docs/sandbox)
- [Precios y franquicias de BigQuery](https://cloud.google.com/bigquery/pricing)
- [Conector BigQuery para Power BI](https://learn.microsoft.com/en-us/power-query/connectors/google-bigquery)
- [Actualización de datos en Power BI](https://learn.microsoft.com/en-us/power-bi/connect-data/refresh-data)
- [Schedules de GitHub Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
