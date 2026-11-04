# Estado del proyecto — 04/11/2026

La entrega local está terminada. La extensión BigQuery funciona con Power BI
publicado y actualización manual. La actualización automática de Power BI al
finalizar GitHub Actions está implementada, pero no habilitada ni probada de
punta a punta: falta recuperar el acceso MFA a Microsoft Entra y configurar
la identidad y sus permisos. No considerar el proyecto totalmente automatizado.

## Entregables vigentes

**Ampliación Looker Studio (04/11/2026):** se implementaron cuatro modelos de
presentación dbt y una publicación transaccional opt-in al final del pipeline
diario existente. Ver [conexión y entrega web](lookerstudio/README.md). El log del
03/11 aportado por el propietario confirma carga y validación programadas del
lote 02/11 en `marketing-513302`. No se volvió a configurar ni activar el cron.
La revisión web del 04/11 confirmó que `marketing-513302.ecobottle_looker`
existe y contiene las cinco tablas publicadas. El
[informe EcoBottle AR](https://datastudio.google.com/u/0/reporting/dfabaac0-911f-4735-b1b9-52733368cff9/page/93oCG)
quedó editado y guardado con cinco páginas y cinco fuentes BigQuery.
No se inspeccionaron IAM, la variable `LOOKER_PUBLISH_ENABLED` ni ejecuciones
nuevas de Actions: la existencia de datos publicados no certifica la continuidad
de la automatización. Las comprobaciones anteriores se conservan como historial.

### Revisión web de Looker Studio — 04/11/2026

- Páginas: Resumen, Ventas, Clientes, Satisfacción y Adquisición web.
- Diseño blanco con acentos verdes (tema Eucalipto), encabezado común y vista
  ajustada al ancho. Las series y barras que aparecían vacías en el navegador
  integrado se sustituyeron por tablas con barras y cifras visibles.
- Medidas explícitas de ventas, pedidos vendidos, compradores distintos, ticket,
  usuarios identificados, duración media y NPS. Fuentes de hechos separadas.
- Selector de fechas común, canal en Resumen y Satisfacción, fuente y dispositivo
  en Adquisición web. Tabla de publicación en Resumen con fuente, última fecha,
  lote validado, publicación UTC y filas. Su intervalo personalizado quedó en
  01/01/2024–04/11/2026, separado del filtro de negocio; ampliar ese intervalo
  técnico si cambia el período cubierto por las fuentes.
- Corte histórico 01/01/2024–30/09/2025 comprobado en la interfaz: ventas
  $382.410.636,00; pedidos 10.998; ticket $34.770,93; compradores 3.194;
  sesiones 100.363; usuarios identificados 3.077; sesiones anónimas 70.751.
  NPS global 30 y 3.083 respuestas; por canal, OFFLINE 40,93 y ONLINE 24,01.
- Período completo observado: ventas $426.585.126,00; pedidos 11.898;
  ticket $35.853,52. Metadatos: 12.869 pedidos, 15.931 líneas, 100.563 sesiones
  y 3.083 respuestas; último lote validado 02/11/2026. Son conteos de filas,
  no todos equivalentes a ventas.
- El informe vive en el servicio web: no hay una exportación editable del diseño
  versionada en este repositorio.

**Diferencias pendientes respecto de la guía completa:** ranking mensual SQL
adicional; controles agrupados de canal/provincia/tienda para Ventas y de canal
para Clientes; prueba del enlace con un lector externo o en incógnito; revisión
de permisos, cuotas y continuidad de la publicación automática. No se cambiaron
permisos de acceso ni se verificó una nueva ejecución de ingesta.

Verificación local de la ampliación: suite cloud (incluye modelos y rollback de
publicación en DuckDB), siete tests del generador, dos tests de Power BI,
`dbt parse` (25 modelos, 87 tests) y `actionlint` 1.7.12 sin ShellCheck aprobados.
La verificación offline anterior no hizo escrituras cloud. La revisión web del
04/11 sí modificó el informe de Looker Studio; no modificó tablas BigQuery ni
la configuración de acceso compartido.

| Uso | Archivo o ubicación |
|---|---|
| Informe web de Looker Studio | [EcoBottle AR — Reporte comercial](https://datastudio.google.com/u/0/reporting/dfabaac0-911f-4735-b1b9-52733368cff9/page/93oCG) |
| Entrega histórica, sin servicios cloud | [powerbi/EcoBottle_AR.pbix](powerbi/EcoBottle_AR.pbix) |
| Entrega conectada a BigQuery | [powerbi/bigquery/EcoBottle_AR.pbix](powerbi/bigquery/EcoBottle_AR.pbix) |
| Reporte publicado | [EcoBottle AR en Power BI](https://app.powerbi.com/groups/bb832d0d-c96f-4b2f-b6a5-83de54073a14/reports/5d15139a-8010-47d5-8142-f594f9c46f8b) |
| Construcción y pruebas cloud | [.github/workflows/bigquery.yml](.github/workflows/bigquery.yml), `cloud/` y `dbt/` |
| Pendientes de automatización | [cloud/POWERBI.md](cloud/POWERBI.md) |

Ambas versiones del reporte tienen cinco páginas, diez tablas, dieciséis
relaciones, diecisiete medidas y cincuenta y tres objetos visuales. Son dos
circuitos útiles con fuentes y cortes distintos; no son copias descartables.
Los proyectos PBIP y sus carpetas Report/SemanticModel son sus fuentes editables.

La actualización manual del modelo publicado terminó correctamente el
02/11/2026 a las 11:27:07 según la interfaz del servicio. Se conserva una
[captura del historial](powerbi/bigquery/actualizacion-web-completada.png).
La prueba de Power BI vuelve a licencia gratuita el 01/01/2027, según el servicio.

## Comprobaciones de esta revisión

- Datos históricos: `generator/validate_raw.py`, todas las reglas OK.
- Warehouse: `validate_warehouse.py`, auditoría OK; diez CSV coinciden con DuckDB,
  claves íntegras y KPIs históricos conciliados.
- Generador diario: siete tests offline aprobados.
- Actualización por API: ocho tests offline aprobados.
- Ambos PBIX: integridad ZIP comprobada; definiciones JSON de los 106 objetos
  visuales válidas y estructura de los dos modelos comprobada.
- Suite cloud completa: no ejecutable en los entornos Python locales actuales
  por falta de dependencias (`google-cloud-bigquery`, Jinja2 y sqlglot, entre
  otras). Esto es una limitación de la verificación local, no una prueba de fallo
  del pipeline. El workflow instala `cloud/requirements.txt` antes de probar.

No se hicieron escrituras ni consultas nuevas a BigQuery durante esta revisión.
Tampoco se modificaron `raw/`, `dw/` ni el contenido del warehouse.

## Pendientes para el cierre cloud completo

1. Recuperar MFA de la cuenta de la universidad con soporte de la institución.
2. Configurar la federación Entra y el acceso al workspace, integrar el cambio
   de la rama `codex/powerbi-after-bigquery` y habilitar `POWERBI_REFRESH_ENABLED`.
3. Observar una actualización automática real completada, después de una carga
   validada. Hasta entonces usar **Actualizar ahora** sobre el modelo semántico.
4. Completar la evidencia de conciliación cloud, siete ejecuciones consecutivas
   y consumo previstos en [ROADMAP_BIGQUERY.md](ROADMAP_BIGQUERY.md).

## Limpieza realizada

Se eliminaron 92 archivos regenerables o transitorios (aproximadamente 4,6 MiB):

- `powerbi/.build/`: copia auxiliar antigua utilizada durante la exportación.
- `powerbi/bigquery/prueba-powerbi.png` y `reporte-publicado.png`: capturas
  transitorias redundantes con la entrega y el registro de actualización.
- Cuatro carpetas `__pycache__` de `cloud/` y `generator/`.

Se conservaron los scripts de reconstrucción, los tests, el entorno `marketing`,
las fuentes originales, el warehouse, los proyectos editables y sus cachés de
Power BI, que permiten abrirlos con datos sin una nueva importación.
