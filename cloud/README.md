# Histórico en BigQuery con dbt (fase 2)

Este circuito agrega una ejecución cloud manual sin reemplazar la práctica local. Genera la base original con semilla 42, valida los CSV, carga las 13 fuentes una sola vez y construye las seis dimensiones y cuatro hechos con dbt Core. No genera días nuevos ni actualiza Power BI todavía.

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
