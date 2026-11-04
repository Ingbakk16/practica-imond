# Estado del proyecto — 04/11/2026

La entrega final es **BigQuery + Looker Studio**. Power BI fue reemplazado por
decisión del propietario; sus archivos se conservan como antecedentes.
Microsoft Entra, MFA, licencias y refresh Power BI dejaron de ser requisitos.

**Estado: entrega funcional terminada y publicada; observación operativa pendiente.**
El código está integrado en `main`, el pipeline cloud publicó y verificó el lote
del 03/11/2026 y el informe funciona para un lector externo. Queda observar siete
ejecuciones diarias. El propietario decidió conservar los límites de consumo actuales.

## Evidencia comprobada

- Fuentes históricas: todas las reglas de `generator/validate_raw.py` aprobadas.
- Warehouse existente: auditoría aprobada, diez CSV iguales a DuckDB, 16 relaciones
  íntegras; ventas históricas ARS 382.410.636,00 y 10.998 pedidos de venta.
- Informe actualizado mediante **Actualizar datos** después del run #22:
  cinco páginas y metadatos visibles. Ventas del período completo:
  ARS 431.786.916,00; pedidos 11.998; ticket 35.988,24.
- Metadatos visibles: último lote validado 03/11/2026, publicación
  04/11/2026 19:45:24 UTC, después del segundo intento. NPS conserva el corte histórico; eso por sí solo no es
  un error: los lotes no tienen necesariamente respuestas nuevas.
- [PR #10 integrado](https://github.com/Ingbakk16/practica-imond/pull/10)
  en `main`, merge `e14f7e0`.
- [CI de los cambios](https://github.com/Ingbakk16/practica-imond/actions/runs/41897779682): exitosa.
- [Run cloud #22, primer intento](https://github.com/Ingbakk16/practica-imond/actions/runs/41898269009/attempts/1):
  exitoso en 5m23s. Fecha manual 2026-11-03, semilla 42, 100 pedidos.
  Publicación y aceptación exitosas; el log confirma metadatos, KPIs históricos y
  lotes validados. La consulta de aceptación procesó 10.944.462 bytes.
- [Run #22, segundo intento](https://github.com/Ingbakk16/practica-imond/actions/runs/41898269009/attempts/2):
  exitoso en 5m14s, repitiendo las mismas entradas. Publicación y aceptación
  aprobadas. El informe actualizado conserva exactamente ventas, pedidos,
  ticket y filas de las cuatro fuentes: no se duplicó el lote.
- [Run programado #21](https://github.com/Ingbakk16/practica-imond/actions/runs/41849903528):
  fallido el 04/11/2026, job `historical`, paso 13 (Build and test BigQuery models).
  El log aportado por el propietario identifica un error interno 500
  `backendError` de BigQuery en `looker_sesiones`, job
  `96c37ef2-c4ce-4472-945e-29977bb1e6d7`. No es evidencia de SQL inválido.
  `cloud/build_dbt.py` agrega hasta tres builds completos con nuevos jobs y
  esperas de 15/30 segundos, solo si todos los errores son transitorios.
  Los errores SQL, permisos y tests fallidos no se reintentan.
- La revisión web anterior concilió ventas, compradores, sesiones y NPS del
  histórico. No se presenta como una conciliación nueva de todos los gráficos.

## Implementación de cierre en el repositorio

Verificación local del cambio: **64 tests cloud aprobados**, incluidos los nuevos
controles de aceptación; `dbt parse` aprobado y ambos workflows parseados como
YAML. La auditoría histórica y los siete tests del generador también pasaron
durante esta conversación. Estas pruebas no consultan ni escriben BigQuery.

- Looker pasa a ser la entrega oficial en las guías.
- Se retira el job Power BI del workflow, aunque sus variables antiguas existan.
- Se conserva la publicación transaccional después de dbt y las conciliaciones.
- Se agrega `cloud/verify_looker.py`: comprueba la publicación realmente disponible,
  sus metadatos, KPIs históricos y lotes validados. En schedule exige el día de
  negocio anterior de Argentina. Un fallo deja el workflow en rojo y genera
  `looker-acceptance.json`, sin modificar tablas.
- Se agregan pruebas con publicaciones mezcladas, importes alterados, metadatos
  ausentes, lotes sin validar y fecha esperada incorrecta.
- Plan, criterios de aceptación y pendientes: [PLAN_CIERRE.md](PLAN_CIERRE.md).

## Cierre web realizado en esta revisión

- Se agregó la sexta fuente BigQuery con `ranking_mensual.sql`, parámetros de
  fechas habilitados, orden mes/posición ascendente y posición agregada con MAX.
  Enero de 2024 muestra Sport B 1 (ARS 7.706.250) y Classic A 2 (ARS 5.236.200).
- Ventas tiene dos grupos independientes: pedidos (canal/provincia/tienda y sus
  dos tablas), y líneas (producto/canal/provincia/tienda y detalle mensual con
  ventas y unidades SUM). El ranking global queda fuera de ambos grupos.
- Clientes agrupa el canal con compradores, tendencia y estado; usuarios web
  quedan fuera. ONLINE reduce compradores de 4.094 a 2.497 y conserva 3.277 usuarios.
- Se comprobó que elegir Classic A no cambia las dos tablas de pedidos ni el
  ranking; filtrar pedidos por canal tampoco modifica líneas ni ranking.
- Corte histórico conciliado en la interfaz: ARS 382.410.636,00; 10.998 pedidos;
  ticket 34.770,93; compradores 3.194; usuarios identificados 3.077; NPS 30.
  Metadatos de publicación siguen mostrando noviembre de 2026 con ese filtro.
- Inicio comercial fijo 01/01/2024 y fin relativo a hoy; el intervalo técnico
  de metadatos permanece personalizado, con fin relativo a hoy.
- Se verificó acceso **Público — Lector** después de la autorización del propietario.
  El propietario probó el enlace en incógnito y confirmó: «Abre y muestra los gráficos».
- Las seis fuentes tienen frescura de una hora y credenciales del propietario.
  La fuente del ranking se denomina `Ranking mensual productos`.
- Evidencia visual: [resumen histórico](lookerstudio/evidencias/resumen-historico.png)
  y [ranking histórico](lookerstudio/evidencias/ventas-ranking-historico.png).

## Cuenta cloud y pendientes operativos reales

La consola confirmó que el proyecto tiene una cuenta vinculada en prueba gratuita:
USD 300 de crédito restantes, 55 días, finalización el 29/12/2026. El resumen del
1 al 4 de noviembre muestra USD 0,00, con advertencia de demora de facturación.
La página de presupuestos ofrece crear el primero; no hay presupuesto configurado.
Cuota de consultas: 200 TiB/día por proyecto y sin límite por usuario; uso mostrado
5,088 GiB. Son valores observados, no límites adecuados para esta demo.
No se activó una cuenta pagada ni se modificaron cuotas. Consultado por presupuesto
y cuotas, el propietario indicó **«Conservar los límites actuales»** el 04/11/2026.

1. Registrar continuidad diaria y consumo durante siete ejecuciones programadas;
   los tests offline y las reejecuciones manuales no sustituyen ese período.
2. Conservar el proyecto activo hasta la evaluación; la prueba tiene vencimiento.

Registro de ejecución y próximos siete días: [lookerstudio/OPERACION.md](lookerstudio/OPERACION.md).
Evidencia del informe actualizado: [publicación validada](lookerstudio/evidencias/publicacion-validada-2026-11-04.png).

## Entregables

| Uso | Ubicación |
|---|---|
| Informe final | [EcoBottle AR — Reporte comercial](https://datastudio.google.com/u/0/reporting/dfabaac0-911f-4735-b1b9-52733368cff9/page/93oCG) |
| Guía de fuentes, métricas y actualización | [lookerstudio/README.md](lookerstudio/README.md), [METRICAS.md](lookerstudio/METRICAS.md) |
| Ranking mensual para el conector | [ranking_mensual.sql](lookerstudio/ranking_mensual.sql) |
| Pipeline | [.github/workflows/bigquery.yml](.github/workflows/bigquery.yml), `cloud/`, `dbt/` |
| Referencia local reproducible | `raw/` → `sql/` → DuckDB → `dw/` |
| Antecedentes Power BI | `powerbi/`, [cloud/POWERBI.md](cloud/POWERBI.md) |
