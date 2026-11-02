# EcoBottle AR conectado a BigQuery

Abrir `EcoBottle_AR.pbip` en Power BI Desktop y usar **Actualizar**.
También está disponible `EcoBottle_AR.pbix`, guardado con datos desde Desktop.

Las diez tablas se leen en modo Import desde
`marketing-513302.ecobottle_analytics`, con `marketing-513302` como proyecto
de ejecución de las consultas. No utiliza CSV, `RutaDW` ni rutas de datos locales.
Las credenciales se administran en Power BI y no se incluyen en el proyecto.

El reporte conserva las cinco páginas, los 53 objetos visuales, las 17 medidas
y las 16 relaciones del dashboard original. Las conversiones de tipos conservan
las claves enteras, los importes decimales fijos y las fechas del modelo local.

## Validación en Desktop (01/11/2026)

La importación de las diez tablas terminó sin errores y se revisaron las cinco
páginas. Resultados observados sin filtros:

| Indicador | Resultado |
|---|---:|
| Ventas ARS | $416.705.526,00 |
| Pedidos | 11.698 |
| Ticket promedio ARS | $35.621,95 |
| Clientes compradores | 3.894 |
| Ventas por producto ARS | $338.160.600,00 |
| Unidades vendidas | 25.638 |
| Sesiones web | 100.463 |
| Usuarios activos | 3.177 |
| Sesiones anónimas | 70.751 |
| Respuestas NPS | 3.083 |
| NPS | 30,0 puntos |

BigQuery incluye registros adicionales respecto de la entrega CSV original;
sus totales no deben compararse como si ambos tuvieran el mismo corte.
Las leyendas de las páginas indican ahora `Fuente: BigQuery`.
Se comprobó la reapertura del proyecto con datos y la integridad ZIP del PBIX.

## Actualización al finalizar BigQuery

Estado al 02/11/2026: reporte y modelo publicados desde la web en `EcoBottle AR`
(workspace `bb832d0d-c96f-4b2f-b6a5-83de54073a14`).
Modelo semántico: `9e92ffa2-012c-4f75-8ac8-1f1d5dab48ba`.
Google BigQuery autenticado en el servicio y actualización a petición completada
correctamente el 02/11/2026 (11:27:07 según la interfaz de Power BI).
La actualización automática todavía no está configurada. El usuario solicitó
dispararla al finalizar la carga nocturna de BigQuery, sin un horario fijo.
El pipeline identificado es `.github/workflows/bigquery.yml` de este repositorio.
El job posterior `powerbi` y su script están preparados localmente; configuración
y aceptación pendientes documentadas en [cloud/POWERBI.md](../../cloud/POWERBI.md).

La conexión en Desktop permite actualizar manualmente. Para ejecutar sin abrir
Desktop, publicar en Power BI Service y configurar el modelo semántico:

1. Asociar o autenticar la conexión de Google BigQuery en el servicio.
2. Ejecutar **Actualizar ahora** y revisar el historial de actualización.
3. Configurar la identidad federada de Microsoft y los identificadores del
   modelo en el environment `bigquery` de GitHub según `cloud/POWERBI.md`.
4. Integrar y habilitar el job posterior `powerbi` mediante la variable de
   repositorio `POWERBI_REFRESH_ENABLED=true`. El workflow corre a las 03:17
   Argentina y solicita la actualización por API al finalizar correctamente
   la carga y sus controles.
5. Verificar en el historial que Power BI haya terminado correctamente la
   actualización. La aceptación de la solicitud API no implica finalización.

No disparar una actualización por cada tabla o archivo recibido: el reporte
debe leer las diez tablas después de completar una misma carga. El despliegue
del disparador depende del proceso de carga existente y del modelo publicado.

La actualización de Power BI lee las tablas de BigQuery: no ejecuta la carga
del warehouse ni actualiza los datos de origen por sí misma.

Referencias: [conector BigQuery](https://learn.microsoft.com/en-us/power-query/connectors/google-bigquery)
y [actualización programada](https://learn.microsoft.com/en-us/power-bi/connect-data/refresh-scheduled-refresh).
Para el disparo al finalizar: [notificaciones de BigQuery](https://docs.cloud.google.com/bigquery/docs/transfer-run-notifications)
y [API de actualización de Power BI](https://learn.microsoft.com/en-us/rest/api/power-bi/datasets/refresh-dataset-in-group).

## Regeneración

Con este proyecto cerrado en Desktop, ejecutar desde la raíz del repositorio:

```powershell
python powerbi/build_bigquery_project.py
```

El generador vuelve a copiar el diseño del proyecto original y sustituye sus
consultas CSV por consultas BigQuery. Sobrescribe las definiciones de esta
variante; conservar antes cualquier cambio propio en sus páginas o medidas.
