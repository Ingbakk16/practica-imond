# Registro de operación de la entrega

El informe final es [EcoBottle AR — Reporte comercial](https://datastudio.google.com/reporting/dfabaac0-911f-4735-b1b9-52733368cff9/page/93oCG).
Última revisión: 04/11/2026. El propietario confirmó que abre en incógnito y
muestra los gráficos. Las seis fuentes tienen frescura de una hora.

## Recuperación comprobada

| Ejecución | Lote | Resultado | Publicación UTC | Evidencia |
|---|---|---|---|---|
| #21, programada | 03/11/2026 esperado | Error interno 500 de BigQuery | Se conservó la anterior | [Log](https://github.com/Ingbakk16/practica-imond/actions/runs/41849903528) |
| #22, intento 1, manual | 03/11/2026, semilla 42, 100 pedidos | Build, conciliaciones, publicación y aceptación aprobados | 04/11/2026 19:39:37 | [Run](https://github.com/Ingbakk16/practica-imond/actions/runs/41898269009/attempts/1) |
| #22, intento 2, reejecución | Mismas entradas | Aprobado; mismos importes y filas, sin duplicación | 04/11/2026 19:45:24 | [Run](https://github.com/Ingbakk16/practica-imond/actions/runs/41898269009/attempts/2) |

Tras actualizar datos en Looker: ARS 431.786.916,00, 11.998 pedidos,
ticket ARS 35.988,24. Filas publicadas: ventas 12.969, productos 16.087,
sesiones 100.563 y NPS 3.083. La consulta de aceptación procesó 10.944.462 bytes;
ese valor corresponde solo a esa consulta, no al total de la ejecución.

## Observación de siete ejecuciones programadas

El cron solicita ejecución a las 06:17 UTC (03:17 Argentina). GitHub puede
demorarlo. Cada ejecución debe validar el día anterior de Argentina. Completar
esta tabla con evidencia real; no contar reejecuciones manuales como días distintos.

| Fecha de ejecución esperada | Lote esperado | Run / resultado | Publicación UTC | Bytes procesados/facturados |
|---|---|---|---|---|
| 05/11/2026 | 04/11/2026 | Pendiente | Pendiente | Pendiente |
| 06/11/2026 | 05/11/2026 | Pendiente | Pendiente | Pendiente |
| 07/11/2026 | 06/11/2026 | Pendiente | Pendiente | Pendiente |
| 08/11/2026 | 07/11/2026 | Pendiente | Pendiente | Pendiente |
| 09/11/2026 | 08/11/2026 | Pendiente | Pendiente | Pendiente |
| 10/11/2026 | 09/11/2026 | Pendiente | Pendiente | Pendiente |
| 11/11/2026 | 10/11/2026 | Pendiente | Pendiente | Pendiente |

Guardar `bigquery-diagnostics` antes de que venza su retención de siete días.
El JSON `looker-acceptance.json` registra los controles aprobados y el job de
aceptación. Consultar el historial de jobs de BigQuery para consumo total,
incluidas consultas de Looker; el resumen de facturación puede demorar más de 24 h.
Ante un fallo, recuperar las mismas fechas, semilla y cantidad de pedidos;
mantener las fuentes publicadas hasta que todos los controles aprueben.

## Vigencia y consumo observados

La cuenta vinculada permanece en prueba gratuita hasta el 29/12/2026, con USD 300
de crédito restantes. La consola muestra USD 0,00 del 1 al 4 de noviembre, sujeto
a demora de facturación. No se activó facturación pagada.

No hay presupuesto configurado. La cuota observada de consultas es 200 TiB/día
por proyecto y sin límite por usuario; uso mostrado 5,088 GiB antes de terminar
la reejecución. El propietario decidió **conservar los límites actuales** el
04/11/2026; no se creó presupuesto ni se cambiaron cuotas. Las alertas de presupuesto
no detienen cargos. `BQ_MAX_BYTES_BILLED` protege consultas del pipeline,
pero no limita las consultas del conector de Looker ni el gasto mensual total.
