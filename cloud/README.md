# Histórico en BigQuery con dbt (fase 2)

Este circuito agrega una ejecución cloud manual sin reemplazar la práctica local. Genera la base original con semilla 42, valida los CSV, carga las 13 fuentes una sola vez y construye las seis dimensiones y cuatro hechos con dbt Core. Puede cargar opcionalmente un lote diario por ejecución manual (ver fase 3 abajo); no actualiza Power BI todavía.

## 1. Preparar el proyecto una sola vez

Realizar estos pasos con una cuenta administradora propia, en Google Cloud Console / Cloud Shell. El workflow no crea cuentas, permisos ni datasets por su cuenta.

1. Elegir el proyecto y confirmar en **Billing → My projects** que está vinculado al Free Trial. Registrar la fecha de vencimiento del crédito; USD 300 de prueba no es una franquicia permanente.
2. Usar BigQuery **on-demand**, sin reservas. Crear un presupuesto pequeño con alertas y configurar una cuota diaria de consultas acorde a la demo. Las alertas no detienen el gasto; el límite de bytes por consulta tampoco limita almacenamiento ni el total mensual.
3. Elegir una ubicación (por defecto `US`) y usarla en los tres datasets y en GitHub. No cambiar la ubicación después de cargar tablas.

En Cloud Shell, reemplazar el valor del proyecto:

```bash
export PROJECT_ID="tu-project-id"
export BQ_LOCATION="US"
gcloud config set project "$PROJECT_ID"
export PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"

gcloud services enable bigquery.googleapis.com iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com

bq --location="$BQ_LOCATION" mk --dataset "$PROJECT_ID:ecobottle_raw"
bq --location="$BQ_LOCATION" mk --dataset "$PROJECT_ID:ecobottle_analytics"
bq --location="$BQ_LOCATION" mk --dataset "$PROJECT_ID:ecobottle_ops"

gcloud iam service-accounts create ecobottle-actions --display-name="EcoBottle GitHub Actions"
export SERVICE_ACCOUNT="ecobottle-actions@$PROJECT_ID.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$SERVICE_ACCOUNT" --role="roles/bigquery.jobUser"
```

En **BigQuery → cada dataset → Sharing / Permissions**, agregar esa cuenta de servicio con **BigQuery Data Editor** (`roles/bigquery.dataEditor`) en **cada uno de los tres datasets**, no en todo el proyecto. Necesita crear vistas/tablas y leer/escribir las fuentes y el marcador de carga. No otorgar Owner ni BigQuery Admin a la cuenta del workflow.

## 2. Autenticación de GitHub sin clave privada

Crear un pool/provider dedicado. La condición siguiente usa los IDs numéricos de `Ingbakk16/practica-imond` y de su propietario, y admite solo `main` y `feature/big-query`. Si se transfiere el repositorio, revisar los IDs y la condición; no quitarla para resolver errores.

```bash
gcloud iam workload-identity-pools create github-ecobottle \
  --location=global --display-name="GitHub EcoBottle"

gcloud iam workload-identity-pools providers create-oidc github \
  --location=global --workload-identity-pool=github-ecobottle \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository_id=assertion.repository_id" \
  --attribute-condition="assertion.repository_owner_id == '144849991' && assertion.repository_id == '1398809175' && (assertion.ref == 'refs/heads/main' || assertion.ref == 'refs/heads/feature/big-query')"

gcloud iam service-accounts add-iam-policy-binding "$SERVICE_ACCOUNT" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github-ecobottle/attribute.repository_id/1398809175"
```

No descargar archivos de clave de la cuenta de servicio. El action `google-github-actions/auth` crea credenciales temporales ignoradas por Git; los artifacts no incluyen esos archivos. La configuración IAM puede tardar unos minutos en propagarse.

## 3. Configurar GitHub

En **Settings → Environments**, crear el environment **`bigquery`**. Restringir sus ramas de despliegue a `main` y `feature/big-query`; agregar aprobación manual si se desea.

Agregar estas **environment variables**, que son identificadores de configuración, no claves privadas:

| Variable | Valor |
|---|---|
| `GCP_PROJECT_ID` | El ID del proyecto, no el número. |
| `BQ_LOCATION` | La ubicación elegida, por ejemplo `US`. |
| `GCP_SERVICE_ACCOUNT` | `ecobottle-actions@PROJECT_ID.iam.gserviceaccount.com` |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-ecobottle/providers/github` |

El workflow solo admite el repositorio original y esas ramas. No se dispara en pull requests, no corre SQL cloud desde forks y no agrega permisos OIDC al workflow local de fase 1.

## 4. Ejecutar y comprobar

Una vez integrado el workflow en la rama predeterminada, abrir **Actions → Build historical BigQuery warehouse → Run workflow** y seleccionar una rama autorizada. GitHub requiere que un workflow manual exista en la rama predeterminada para mostrar el botón. No hay push ni schedule automático para el circuito cloud.

Orden de ejecución:

1. Instalar dependencias cloud fijadas y ejecutar tests offline del loader.
2. Generar CSV temporales con semilla 42 y validarlos. Comprobar igualdad byte a byte con `raw/` para asegurar una referencia histórica idéntica.
3. Reconstruir y auditar el warehouse DuckDB en el runner descartable.
4. Autenticar, cargar o reconocer la inicialización histórica y ejecutar `dbt build`.
5. Comparar BigQuery con DuckDB: diez conteos de tablas y KPIs mensuales por canal, producto, fuente/dispositivo y NPS. Los importes se comparan como decimales, no como flotantes; ticket, duración promedio y NPS pueden derivarse de los numeradores y denominadores conciliados.

El artifact **`bigquery-diagnostics`** conserva logs, resumen, `manifest.json` y `run_results.json` de dbt durante siete días, incluso ante fallos no cancelados. Los scripts Python informan bytes procesados por sus consultas; dbt registra sus resultados y los jobs pueden revisarse en BigQuery Job history. La concurrencia del workflow impide dos cargas simultáneas de esta demo.

**Comprobación después de corregir errores de acceso o SQL:** ejecutar primero el workflow con `daily_date` vacío. Un resultado verde debe implicar que carga, `dbt build` y conciliación terminaron sin errores (el shell ahora usa `pipefail`, para que `tee` no oculte fallos). Ejecutarlo por segunda vez y confirmar en `load.log` que el bootstrap histórico se omite. Solo después probar una fecha diaria. Los runs anteriores a esta corrección podían figurar verdes aunque los comandos cloud fallaran: no constituyen aceptación de la fase 2.

No hay publicación atómica de todo el warehouse: si dbt falla, corregir y volver a construir antes de consumirlo. No refrescar Power BI en esta fase.

## 5. Reintentos y protección de los datos

`cloud/load_historical.py` guarda en `ecobottle_ops.historical_bootstrap` los checksums y conteos de origen, un fingerprint conjunto y el estado de la carga.

- Mismo fingerprint y estado `complete`: omitir toda escritura en las fuentes. dbt y conciliación sí vuelven a ejecutarse.
- Mismo fingerprint y estado `loading`: repetir únicamente la inicialización incompleta, reemplazando sus 13 tablas. La fase diaria futura no debe comenzar hasta que el bootstrap esté completo.
- Fingerprint diferente, estado inesperado o tablas raw sin marcador: detenerse sin sobrescribirlas. Investigar el origen del conflicto; no borrar el marcador para forzar una carga.
- Si falla una tabla o su conteo, no marcar el bootstrap como completo. Si dbt falla después de cargar, el reintento no vuelve a cargar las fuentes.

La marca completa identifica el archivo cargado, no verifica por sí sola cada valor remoto en cada reintento. Los tests dbt y la conciliación detectan discrepancias posteriores; no se reparan fuentes automáticamente. El loader no es un comando de restauración ni un reseteo y nunca debe usarse para eliminar datos diarios.

## 6. Desarrollo local opcional

Usar Python 3.12 en un entorno virtual separado del circuito de práctica:

```bash
python3.12 -m venv .venv-cloud
source .venv-cloud/bin/activate
pip install -r cloud/requirements.txt
python -m unittest discover -s cloud/tests -v

export GCP_PROJECT_ID="tu-project-id"
export BQ_LOCATION="US"
export BQ_MAX_BYTES_BILLED="1000000000"
export DBT_SEND_ANONYMOUS_USAGE_STATS="false"
dbt parse --project-dir dbt --profiles-dir dbt
```

Los tests offline y `dbt parse` no necesitan autenticación. Para ejecutar consultas localmente, usar `gcloud auth application-default login` con una cuenta autorizada, sin exportar claves al repositorio. **Los siguientes comandos escriben en BigQuery y pueden consumir crédito**:

```bash
export GENERATED_RAW="$(mktemp -d)"
python generator/generate_raw.py --seed 42 --out "$GENERATED_RAW"
python generator/validate_raw.py --dir "$GENERATED_RAW"
python cloud/load_historical.py --dir "$GENERATED_RAW"
dbt build --project-dir dbt --profiles-dir dbt
```

Para conciliar: `python cloud/reconcile.py --database /ruta/a/warehouse.duckdb`, usando una base histórica ya construida y validada. El script abre DuckDB en modo solo lectura. La conciliación histórica deja de ser una referencia de totales válida cuando se agreguen lotes diarios; adaptarla por alcance histórico en la fase siguiente, no modificar los CSV de referencia.

## Decisiones del modelo

- Staging usa vistas sobre fuentes con esquemas explícitos del loader; no se autodetectan importes ni IDs.
- Los IDs numéricos de origen son las claves estables de las dimensiones; no se recalculan con `ROW_NUMBER()`. Se conservan `*_id`, `*_key` y las filas `-1` de la práctica.
- Las seis dimensiones y los cuatro hechos se reconstruyen como tablas. `dim_date` llega hasta la última fecha de actividad de pedidos, sesiones o respuestas, sin usar la fecha de hoy como límite histórico.
- Los horarios sin zona del origen permanecen como `DATETIME` de Argentina. No convertirlos implícitamente en timestamps UTC. Importes: `NUMERIC` de BigQuery; los valores conservan los centavos del origen.
- Los tests dbt controlan las relaciones (BigQuery no aplica FK), unicidad, nulos, estados, puntajes, importes, miembros anónimos y conservación de filas.
- No se necesitan buckets, streaming, dbt Cloud, modelos incrementales ni servicios de IA. Algunas dependencias del adaptador dbt incluyen clientes de otros servicios, pero este proyecto no los utiliza ni necesita habilitar sus APIs.

## Aceptación de fase 2

- [ ] Proyecto, permisos, ubicación y límites configurados por el propietario.
- [ ] Workflow cloud exitoso y artifact revisado.
- [ ] BigQuery concilia con el histórico DuckDB.
- [ ] Segundo run omite la carga y no agrega duplicados.
- [ ] Ninguna fuente local ni reporte Power BI fue modificado.

Hasta ejecutar los controles cloud, la fase está implementada pero no verificada de punta a punta. Ver [`ROADMAP_BIGQUERY.md`](../ROADMAP_BIGQUERY.md).

## Fase 3: un lote diario manual (sin schedule)

**Primero cerrar la aceptación de la fase 2.** La ejecución manual de GitHub requiere que el workflow exista en la rama predeterminada; mientras siga solo en `feature/big-query`, no aparecerá el botón «Run workflow». Un PR sin fusionar ejecuta el workflow de validación local, **no** prueba la autenticación OIDC de BigQuery. Para probar cloud antes de fusionar, usar credenciales locales autorizadas y los comandos siguientes; esto puede consumir crédito GCP.

El generador original y los 13 CSV de `raw/` no cambian. Cada día usa fecha Argentina, semilla 42 y 100 pedidos por defecto. En días de apertura genera ventas presenciales completas; los domingos y feriados fijos del generador original (01/01, 01/05, 25/12), tiendas cerradas, genera pedidos online `PAID`, envío `READY` y una sesión web por pedido. No inventa entregas ni encuestas. En ambas variantes crea clientes y direcciones nuevos; `shipment.csv` y `web_session.csv` diarios están vacíos los días presenciales. La fecha elegida es explícita, desde el 01/10/2025 en adelante; el salto desde el histórico no se rellena automáticamente. Otros feriados móviles no se modelan en esta demo.

**IDs y compatibilidad:** el histórico ya usa IDs de hasta 13.000 millones; la versión 2 del generador diario reserva IDs desde 20.000 millones, incluso para el primer día permitido (01/10/2025). El validador rechaza IDs diarios fuera de ese rango. Antes de cargar un lote, consultar `ecobottle_ops.daily_batches` en BigQuery para comprobar si hay lotes anteriores; `cloud/setup_daily.py` detiene el workflow si encuentra manifiestos de otra versión. No borrar marcadores ni tablas para sortear ese bloqueo: cualquier migración de lotes ya cargados requiere un plan específico. La conciliación histórica compara exclusivamente IDs anteriores al nuevo rango diario.

En el editor SQL de BigQuery (sustituir `PROJECT_ID`), verificar antes de habilitar lotes diarios:

```sql
SELECT batch_id, status, JSON_VALUE(manifest, '$.version') AS generator_version
FROM `PROJECT_ID.ecobottle_ops.daily_batches`
ORDER BY batch_id;
```

Si aparecen lotes de versión 1, detenerse y pedir una migración explícita; no volver a generar o eliminar datos históricos.

Comprobación **sin cloud** (usar un directorio nuevo cada vez):

```bash
python -m unittest discover -s generator/tests -v
python generator/generate_daily.py --date 2026-11-01 --seed 42 --orders 100 --out /tmp/ecobottle-day
python generator/validate_daily.py --dir /tmp/ecobottle-day
```

Para generar hasta 31 días consecutivos de manera independiente (la misma fecha y semilla producen exactamente el mismo lote, se ejecute sola o dentro del rango): `python generator/generate_daily.py --start 2026-11-01 --end 2026-11-07 --out /tmp/ecobottle-week`. Validar cada subcarpeta con `generator/validate_daily.py`; para cargar todas, `python cloud/load_daily.py --range --dir /tmp/ecobottle-week`. Si falla una fecha, repetir el mismo comando omite las completas y reintenta solo la incompleta. Después, ejecutar `dbt build` y conciliar cada subcarpeta. No hay schedule ni carga automática de días faltantes.

Con el histórico ya cargado, los datasets provisionados y las variables GCP de la sección 6 configuradas, una carga **manual** y su comprobación usan:

```bash
python cloud/setup_daily.py
python cloud/load_daily.py --dir /tmp/ecobottle-day
dbt build --project-dir dbt --profiles-dir dbt
python cloud/reconcile.py --database /ruta/al/warehouse.duckdb
python cloud/reconcile_daily.py --dir /tmp/ecobottle-day
```

`cloud/setup_daily.py` crea tablas vacías antes del primer `dbt build`, incluso si solo se quiere reconstruir el histórico. La carga diaria se niega a comenzar sin bootstrap histórico completo, mantiene registros nuevos en `ecobottle_raw.daily_*` (no trunca las fuentes históricas), e identifica cada día con un manifiesto y fingerprint en `ecobottle_ops.daily_batches`. Solo los lotes `complete` son visibles para dbt. Repetir un lote completo con la misma entrada no escribe; cambiar semilla, versión o contenido para una fecha existente se rechaza. Repetir uno `loading` reemplaza únicamente sus propias filas; las tablas analíticas se reconstruyen con dbt después. Ejecutar **un solo escritor cloud a la vez**: el workflow serializa sus ejecuciones, pero los comandos locales simultáneos no están coordinados.

El workflow `Build historical BigQuery warehouse` admite opcionalmente `daily_date`, `daily_seed` y `daily_orders`. Con la fecha vacía solo ejecuta el histórico, como en fase 2. Con fecha, valida primero el histórico, luego genera y carga ese día, ejecuta dbt nuevamente y concilia tanto el histórico como el lote. No hay ejecución programada ni refresh Power BI (fase 4/5). Un fallo después de marcar `complete`, pero antes de dbt, se recupera repitiendo la misma fecha y semilla: la carga se omite y dbt se reconstruye. No refrescar Power BI tras fallos de dbt.
