# Estado del proyecto — 02/11/2026

La entrega local está terminada. La extensión BigQuery funciona con Power BI
publicado y actualización manual. La actualización automática de Power BI al
finalizar GitHub Actions está implementada, pero no habilitada ni probada de
punta a punta: falta recuperar el acceso MFA a Microsoft Entra y configurar
la identidad y sus permisos. No considerar el proyecto totalmente automatizado.

## Entregables vigentes

| Uso | Archivo o ubicación |
|---|---|
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
