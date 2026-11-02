# Power BI + BigQuery: preparación y pasos manuales

**Estado al integrar las ramas (02/11/2026):** ya existe una entrega conectada,
publicada en el workspace `EcoBottle AR` y con refresh manual verificado; ver
[`bigquery/README.md`](bigquery/README.md). Esta guía describe cómo generar y
validar otra copia con parámetros y medidas de frescura. El generador no
sobrescribe el PBIX entregado. La actualización automática al terminar Actions
está implementada en [`../cloud/POWERBI.md`](../cloud/POWERBI.md), pero sigue
deshabilitada hasta recuperar MFA y configurar la identidad de Microsoft Entra.

## Preparado en el repositorio

`build_bigquery_project.py` copia el proyecto editable existente a una carpeta separada y cambia sus diez fuentes CSV por el conector Google BigQuery, en modo Import. Conserva columnas, medidas, 16 relaciones y las cinco páginas; agrega medidas de frescura y elimina el texto de corte histórico fijo. No modifica el `.pbix` ni el proyecto CSV y rechaza sobrescribir una carpeta existente.

El resultado del generador es **un proyecto preparado, no un reporte conectado y validado**: no contiene datos importados ni credenciales. Python no ejecuta Power Query ni puede certificar su actualización en Desktop o Service. La entrega existente de `bigquery/` sí se conectó y publicó mediante Desktop y la web; un proyecto recién generado debe repetir esos controles.

## 1. Accesos y proyecto (manual)

- Confirmar el **project ID** de GCP, no su nombre visible ni número, y el billing project (normalmente el mismo).
- Usar una cuenta Google con `roles/bigquery.jobUser` en el billing project y `roles/bigquery.dataViewer` en `ecobottle_analytics`. Para navegar proyectos puede hacer falta Browser o Metadata Viewer a nivel proyecto; conceder solo lo necesario.
- El conector usa Storage API por defecto: verificar que esté habilitada y conceder `roles/bigquery.readSessionUser` donde corresponda. Consultar las particularidades de ADBC si aparece un error de permisos.
- Usar inicio de sesión OAuth; no agregar claves privadas al repositorio ni reutilizar la identidad escritora de Actions para el reporte.
- Confirmar que la cuenta universitaria permita publicar en **Mi área de trabajo** y configurar actualización programada. La licencia gratuita no garantiza que el administrador haya habilitado estas funciones; compartir con terceros tiene otras restricciones.

## 2. Generar la copia cloud (local)

Desde la raíz del repositorio, sustituir `TU-PROJECT-ID` por el ID real:

```bash
python powerbi/build_bigquery_project.py --project TU-PROJECT-ID
```

Salida: `powerbi/.build/bigquery/EcoBottle_AR_BigQuery.pbip`. `.build/` está ignorado por Git. Si el proyecto de facturación difiere, agregar `--billing-project OTRO-PROJECT-ID`. Si la carpeta ya existe, usar `--out RUTA-NUEVA`: no borrar una copia editada en Desktop para regenerarla. El script requiere solo Python estándar.

## 3. Conectar y validar en Windows (manual)

1. Abrir el `.pbip` generado con Power BI Desktop de 64 bits actualizado (habilitar proyectos PBIP si la versión lo requiere).
2. Revisar los parámetros `BQProject` y `BQBillingProject` en **Transformar datos → Administrar parámetros**. El dataset está fijado a `ecobottle_analytics`; no importar staging, raw ni ops.
3. Iniciar sesión Google desde las credenciales de origen y ejecutar **Actualizar**. Se usa `Implementation="2.0"` (ADBC); si hay un problema del conector, revisar la documentación oficial y no cambiar permisos o drivers a ciegas.
4. Confirmar diez tablas analíticas, más `refresh_info` desconectada. Mantener las 16 relaciones unidireccionales y no autodetectar uniones entre hechos. Verificar claves enteras, fechas y moneda decimal fija; el grano y las medidas no cambian.
5. Revisar las cinco páginas y sus filtros. Para conciliar con los valores históricos de `README.md`, filtrar **2024-01-01 a 2025-09-30**; los totales sin filtro ahora incluyen lotes nuevos. Comparar además ventas/pedidos de una fecha diaria contra BigQuery y verificar que el slicer muestra fechas nuevas.
6. Agregar tarjetas con `Última fecha de pedidos`, `Última fecha de actividad` y `Actualización del modelo (UTC)`. Las primeras dos dependen del contexto de filtro; la actividad usa el máximo de la dimensión fecha. La última registra la evaluación de la consulta de refresh, no una confirmación del éxito del pipeline ni la hora de finalización de Service.
7. Sustituir el pie “Actualización automática pendiente de configurar” solo después de comprobar la automatización. Guardar como **`EcoBottle_AR_BigQuery.pbix`**, sin sobrescribir el histórico.

## 4. Publicar y programar (manual)

1. Publicar la copia cloud en el workspace **EcoBottle AR** si va a utilizarse el refresh por API con la aplicación. **Mi área de trabajo** puede usarse para una copia personal manual, pero no es el destino de la automatización documentada en `cloud/POWERBI.md`.
2. En la configuración del **modelo semántico**, configurar la conexión cloud Google BigQuery y sus credenciales OAuth. Las credenciales Desktop no bastan para Service. Si solo quedan estas consultas cloud y la tabla constante, normalmente no hace falta un gateway local.
3. Ejecutar **Actualizar ahora** y comprobar el historial, los totales y las tarjetas desde el navegador.
4. Para actualizar al finalizar Actions, seguir `cloud/POWERBI.md` y verificar el job posterior `powerbi`. Mientras siga pendiente la identidad Entra, usar **Actualizar ahora** después de comprobar el éxito del pipeline. Un horario independiente es una alternativa opcional, no el disparador solicitado; Actions corre a las **03:17 Argentina**.
5. Habilitar avisos de error y revisar también las notificaciones de Actions. Cerrar Desktop/apagar la computadora y verificar que Service actualiza sin ella.

**Limitación importante:** un horario de Service independiente de Actions puede refrescar datos atrasados o tablas parcialmente reconstruidas si dbt falla. El job de refresh por API de esta rama depende del éxito de la carga y los controles, pero aún no está habilitado ni probado contra el servicio. Hasta completar esa configuración, comprobar el éxito del pipeline antes del refresh manual. No guardar un token personal permanente en Actions como atajo.

## Pendientes manuales / criterio de aceptación

- [ ] Confirmar project ID, billing project, cuenta Google y permisos de lectura/consulta.
- [ ] Generar la copia con IDs reales; abrir, autenticar y actualizar en Desktop.
- [ ] Conciliar histórico y lotes diarios, relaciones y las cinco páginas.
- [ ] Agregar tarjetas de frescura y guardar el `.pbix` cloud separado.
- [ ] Confirmar publicación y refresh programado permitidos para la cuenta gratuita universitaria.
- [ ] Publicar, configurar credenciales y probar **Actualizar ahora** en Service.
- [ ] Configurar horario y avisos; verificar una actualización con Desktop cerrado.
- [ ] Observar siete refreshes diarios y revisar costos de BigQuery (el límite de bytes del pipeline no limita las consultas del conector).
- [ ] Evaluar refresh condicionado al éxito vía API si se necesita esa garantía y existen permisos.

Los cambios de autenticación, publicación y programación deben hacerse interactivamente por el usuario. No se consideran completados por generar archivos ni por aprobar tests offline.

## Comprobaciones automatizadas

```bash
python -m unittest discover -s powerbi/tests -v
```

Comprueban preservación del modelo y reporte, fuentes cloud, separación de archivos y rechazo de sobrescritura. No prueban el motor M, credenciales, Power BI Desktop ni refresh en Service.

## Referencias

- [Conector Google BigQuery y permisos](https://learn.microsoft.com/en-us/power-query/connectors/google-bigquery)
- [Actualización de datos en Power BI](https://learn.microsoft.com/en-us/power-bi/connect-data/refresh-data)
- [Configurar actualización programada](https://learn.microsoft.com/en-us/power-bi/connect-data/refresh-scheduled-refresh)
