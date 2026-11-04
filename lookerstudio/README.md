# EcoBottle AR — BigQuery → Looker Studio

**Entrega oficial desde el 04/11/2026:** Looker Studio reemplaza Power BI.
El [plan de cierre](../PLAN_CIERRE.md) concentra los criterios y la evidencia.
No se necesita recuperar MFA de Microsoft ni habilitar refresh de Power BI.

La carga diaria existente se conserva. dbt construye cuatro fuentes de presentación
y `cloud/publish_looker.py` publica una copia validada para el reporte. No se
importan CSV en Looker ni se necesita Power BI Service.

**Estado revisado el 04/11/2026:** dataset publicado y cinco fuentes BigQuery
conectadas al [informe EcoBottle AR — Reporte comercial](https://datastudio.google.com/u/0/reporting/dfabaac0-911f-4735-b1b9-52733368cff9/page/93oCG).
El informe tiene cinco páginas y tema Eucalipto. Se conciliaron los principales
KPIs históricos en la interfaz. Las visualizaciones que no cargaban en el
navegador integrado se reemplazaron por tablas con barras y valores visibles.
La revisión de cierre incorporó ranking SQL, controles agrupados de Ventas y
Clientes, detalle de productos y acceso Público — Lector. Ver la [evidencia y
los pendientes operativos](../ESTADO_PROYECTO.md).
En la revisión de cierre se observó el schedule activo y fallido del 04/11
([run #21](https://github.com/Ingbakk16/practica-imond/actions/runs/41849903528)).
La publicación visible conserva el lote 02/11; todavía no acredita continuidad.
No se inspeccionaron IAM ni las variables privadas de GitHub.

Las secciones siguientes son la guía de configuración y el diseño objetivo,
no una certificación de que cada paso se haya ejecutado en esta revisión.

## 1. Activar la publicación una sola vez

El proyecto de la ejecución verificada del 03/11/2026 es `marketing-513302`, en `US`.
Si usás otro proyecto, sustituí ese ID en los ejemplos. Desde Cloud Shell con una
cuenta administradora:

```bash
export PROJECT_ID="marketing-513302"
export BQ_LOCATION="US"
bq --location="$BQ_LOCATION" mk --dataset "$PROJECT_ID:ecobottle_looker"
```

Si el dataset ya existe, no lo borres: comprobá su ubicación y contenido. En
**BigQuery → ecobottle_looker → Sharing / Permissions**, otorgar a
`ecobottle-actions@marketing-513302.iam.gserviceaccount.com` el rol **BigQuery Data
Editor**, solo en ese dataset. Los accesos actuales a analytics, ops y ejecución
de jobs se reutilizan. El script no crea datasets ni concede permisos.

En GitHub, environment **bigquery**, agregar `LOOKER_PUBLISH_ENABLED=true`.
Integrar estos cambios en `main` para que los use el schedule. Para probar antes,
la rama `feature/big-query` ya está autorizada para ejecución manual y OIDC.
Ejecutar **Actions → Build BigQuery warehouse → Run workflow** con `daily_date`
vacío: reconstruye con todo el origen ya cargado, incluido el diario existente;
no genera un día adicional. Comprobar el paso **Publish validated sources for
Looker Studio** y `looker-publication.log` en el artifact `bigquery-diagnostics`.

El workflow revisado agrega **Verify published Looker delivery** después de la
publicación. Valida los conteos y KPIs históricos de la copia publicada,
identificadores y fechas de publicación coherentes, ausencia de lotes sin validar
y concordancia de la marca de lote. En schedule exige el día anterior en
Argentina. Revisar `looker-acceptance.json` y `looker-acceptance.log` en el mismo
artifact. Un resultado omitido no equivale a una aceptación exitosa.

La ventana de dos horas del verificador se aplica inmediatamente después de
publicar. No es un monitor para ejecutar sobre una publicación antigua ni una
promesa de ingesta cada dos horas. Para una verificación manual nueva:

```bash
python cloud/verify_looker.py --expected-date YYYY-MM-DD --out looker-acceptance.json
```

Usar la fecha real esperada para ese run; las ejecuciones manuales sin carga de
días pueden omitir `--expected-date` y seguir conciliando histórico y publicación.

En `ecobottle_looker` deben aparecer:

| Tabla | Grano / fecha |
|---|---|
| `looker_ventas` | Un pedido / fecha del pedido. |
| `looker_productos` | Una línea / fecha del pedido. |
| `looker_sesiones` | Una sesión / fecha de inicio. |
| `looker_nps` | Una respuesta / fecha de respuesta. |
| `actualizacion` | Una fila por fuente; conteo, período, lote y publicación. |

**Conectar solo a este dataset**, no a los candidatos `ecobottle_analytics.looker_*`.

## 2. Conectar en Looker Studio

1. Crear un informe en [Looker Studio](https://lookerstudio.google.com/).
2. **Añadir datos → BigQuery → proyecto marketing-513302 → ecobottle_looker**.
3. Crear una fuente por cada una de las cinco tablas, con nombres legibles.
4. Elegir **credenciales del propietario**. La cuenta propietaria necesita
   `roles/bigquery.jobUser` en el proyecto de facturación y
   `roles/bigquery.dataViewer` en `ecobottle_looker`. No otorgar escritura al lector
   del informe ni usar las credenciales de GitHub en Looker.
5. Configurar la frescura de las cinco fuentes en **1 hora**.
6. Revisar tipos: `fecha` como Fecha, `published_at` como Fecha y hora,
   montos como moneda ARS, conteos como números enteros. No sumar IDs técnicos ni
   `publication_id`; ocultarlos de los gráficos.
7. Agregar los campos de [METRICAS.md](METRICAS.md). No sumar promedios ni distintos.

No se publican nombres, emails, direcciones ni comentarios NPS. Las claves de
cliente son identificadores sintéticos para conteos distintos. No hacer públicos
los datasets BigQuery: el reporte usa las credenciales del propietario. El costo
de las consultas queda en su proyecto, no en el docente.

## 3. Construir las cinco páginas

Usar formato español/Argentina, moneda ARS y una paleta común. Cada gráfico tiene
una sola fuente: **no combinar hechos con blends** para calcular los KPIs.

| Página | Fuente y objetos | Controles |
|---|---|---|
| **Resumen** | Ventas: tarjetas Ventas ARS, Pedidos y Ticket; serie mensual; barras por canal. | Fecha y canal sobre ventas. |
| **Ventas** | Ventas: provincia y tienda. Productos: importe/unidades, barras por producto y tabla mes/producto. | Fecha; canal/provincia/tienda por grupo de fuente; producto solo en líneas. |
| **Clientes** | Ventas: compradores y tendencia. Sesiones: usuarios activos y tendencia, en gráficos separados. Ventas: compradores por estado actual del cliente. | Fecha para ambos; canal solo para compradores. |
| **Adquisición web** | Sesiones: sesiones, anónimas, usuarios activos, duración media; tendencia; fuente y dispositivo. | Fecha, fuente y dispositivo; sin canal/provincia. |
| **Satisfacción** | NPS: tarjetas NPS/respuestas; promotores/pasivos/detractores; evolución y canal. | Fecha de respuesta y canal; sin producto/provincia. |

Elegir `fecha` como dimensión del intervalo de fechas en cada gráfico. Para las
series mensuales usar Año-Mes, no el nombre de mes sin año.

Los controles de categorías de fuentes distintas **no se propagan automáticamente**
solo porque tengan nombres iguales. Agrupar cada control con los gráficos de su
fuente y rotularlos (por ejemplo, «Canal — pedidos» y «Canal — productos»).
Probar el selector de fecha en cada fuente. Un filtro de producto jamás debe
reducir la tarjeta de ventas totales de pedidos.

Para el ranking mensual exacto usar [`ranking_mensual.sql`](ranking_mensual.sql)
como fuente BigQuery adicional: reemplazar `PROJECT_ID` y habilitar los parámetros
de fecha `@DS_START_DATE` y `@DS_END_DATE` del conector. Mostrar mes, producto, ventas
y posición. **Es ranking global por mes dentro del intervalo seleccionado**:
no conectarle controles de canal, provincia, tienda ni producto. No sumar posición.

Período inicial recomendado: **01/01/2024 hasta la fecha de entrega**, para mostrar
histórico y nuevos lotes. Existe un salto entre septiembre de 2025 y el inicio de
la demo; no presentar meses sin registros como ventas conocidas de cero. Agregar
la nota «Datos sintéticos; histórico + lotes de demostración».

### Frescura no es lo mismo que actividad

Agregar una tabla pequeña de `actualizacion` con `fuente`, `ultima_fecha`,
`ultimo_lote_validado` y `published_at`. No asociarla al selector de fechas de
negocio. `published_at` se almacena en UTC; rotularlo así o verificar la conversión
a Argentina. No usar `NOW()` como si fuera fecha de carga.

El lote del 02/11/2026 contiene 100 pedidos y **cero sesiones, envíos y respuestas
NPS nuevos**. Una publicación reciente con una fecha NPS antigua no implica fallo.
Si no hay respuestas nuevas, Satisfacción seguirá usando el histórico.

## 4. Actualización y recuperación

### Automática

El schedule existente (`17 6 * * *`, 03:17 Argentina, sujeto a demoras de Actions)
selecciona días pendientes, genera/carga, ejecuta dbt y concilia. **Después**
de esos controles y de comprobar que `raw/` sigue intacto, publica Looker.
No hay una API de refresh de Power BI involucrada en esta conexión.

La frescura de una hora es una política de cache: al consultar el reporte Looker
puede reutilizar resultados o volver a BigQuery. No es un cron de ingesta ni
garantiza que una pestaña abierta se redibuje sola. Para comprobar inmediatamente
una publicación, el editor usa **Más opciones → Actualizar datos**; recargar la
página puede seguir usando cache. Esta conexión/frescura no requiere Pro.

### Manual desde origen

En el mismo workflow indicar `daily_date=YYYY-MM-DD` (y opcionalmente `daily_end`,
máximo siete días). Se reutilizan generación determinista, carga idempotente y
validaciones existentes. No editar las tablas publicadas ni volver a cargar el
histórico para agregar días. Repetir un día no debe agregar otras 100 ventas.

### Ante fallos

- Un fallo anterior a la publicación deja la copia anterior disponible.
- Se verifica que todos los lotes estén completos y tengan una validación con el
  mismo fingerprint. Un lote incompleto/no validado bloquea la publicación,
  incluso en una ejecución manual sin fechas.
- Las cuatro tablas y sus metadatos se reemplazan con DML en **una transacción**.
  Un error antes del commit no deja una publicación parcial. Las tablas se crean
  vacías solo la primera vez, fuera de la transacción; no hay copia previa en ese
  primer arranque.
- Los candidatos pueden cambiar durante dbt: por eso no son fuentes del reporte.
  Un cambio de esquema publicado requiere migración explícita; no se borran ni
  recrean automáticamente tablas existentes.
- Corregir y reejecutar el mismo día/rango o schedule. No ejecutar publicaciones
  simultáneas por fuera de la exclusión de concurrencia del workflow.
- `LOOKER_PUBLISH_ENABLED=false` pausa solo esta publicación, no el pipeline diario.

La transacción no unifica las consultas separadas de una página: justo durante un
commit, gráficos/cache pueden mostrar publicaciones distintas temporalmente.
`publication_id` permite auditarlo; actualizar los datos después del commit
homogeneiza la lectura.

## 5. Validar y entregar el enlace

1. Filtrar **01/01/2024–30/09/2025** (el total global incluye lotes nuevos):
   ventas **$382.410.636,00**, pedidos **10.998**, ticket **$34.770,93**,
   compradores **3.194**, productos **$309.891.600,00**, unidades **23.545**,
   sesiones **100.363**, usuarios identificados **3.077**, anónimas **70.751**,
   respuestas **3.083**, NPS **30,0**.
2. Enero 2024: pedidos **460**, ventas **$15.965.464,50**, compradores **431**,
   usuarios activos **424**, NPS **37,6**. Son dos poblaciones diferentes.
3. NPS histórico por canal: ONLINE **24,0**, OFFLINE **40,9**.
4. Seleccionar un producto: cambian sus líneas, no las ventas de pedidos.
5. Verificar `actualizacion` y un lote diario contra los logs de Actions.
6. Repetir el lote: mismo número de pedidos, sin duplicados. Puede cambiar la hora
   de publicación, no el contenido del lote.
7. **Compartir → acceso al enlace como lector**, según las políticas de la cuenta.
   Probar en incógnito y confirmar que no pide permisos de BigQuery. Si se
   restringe acceso público, compartir con el correo del docente y probar con él.
8. Registrar el enlace definitivo y la fecha de revisión en la entrega.

No prometer costo cero: frescura, filtros, ranking y lectores disparan consultas.
El límite `BQ_MAX_BYTES_BILLED` del pipeline **no limita consultas de Looker Studio**.
Revisar cuotas por usuario/proyecto, presupuesto y Job history, y conservar el
proyecto activo hasta que se evalúe la entrega.

## Comprobaciones locales (sin credenciales)

Con las dependencias de `cloud/requirements.txt` instaladas:

```bash
python -m unittest discover -s cloud/tests -v
GCP_PROJECT_ID=demo-project dbt parse --project-dir dbt --profiles-dir dbt
```

Los tests ejecutan las fuentes sobre DuckDB en memoria, contrastan KPIs históricos,
detectan duplicación de joins y revisan protecciones de publicación. No sustituyen
la primera ejecución BigQuery ni la revisión visual del reporte.

Referencias: [conector BigQuery](https://docs.cloud.google.com/looker/docs/studio/connect-to-google-bigquery),
[frescura](https://docs.cloud.google.com/looker/docs/studio/manage-data-freshness).
