# Actualizar Power BI al finalizar el pipeline

> **Archivado el 04/11/2026.** Looker Studio reemplaza Power BI por decisión del
> propietario. El job de refresh fue retirado del workflow. Los pasos siguientes
> describen la implementación anterior; no son requisitos de entrega ni deben
> habilitarse para cerrar este proyecto. Ver [PLAN_CIERRE.md](../PLAN_CIERRE.md).

`bigquery.yml` incorpora el job `powerbi`, dependiente de `historical`. Solo se
ejecuta después de una carga, dbt, conciliaciones y controles exitosos. Hace una
sola solicitud de actualización y espera hasta 30 minutos a que esa misma
solicitud figure como `Completed` en el historial. Fallo o espera agotada dejan
el workflow en rojo; un HTTP 202 por sí solo no cuenta como éxito.

El cron permanece en 03:17 Argentina. Power BI se dispara al terminar el job,
sin otro horario fijo. También funciona con ejecuciones manuales históricas o
diarias. La concurrencia existente serializa carga y actualización del modelo.

## Estado y configuración pendiente

Implementación probada sin conexión y subida a la rama
`codex/powerbi-after-bigquery` (commit `943f4f1`). Todavía no está integrada en
`main`, habilitada ni verificada mediante una ejecución automática real.

Avance del 02/11/2026: prueba de Power BI activada con autorización del usuario
(el servicio indica regreso a licencia gratuita el 01/01/2027). Workspace
`EcoBottle AR` creado y PBIX importado con reporte y modelo semántico:

- Workspace: `bb832d0d-c96f-4b2f-b6a5-83de54073a14`.
- Modelo (`POWERBI_DATASET_ID`): `9e92ffa2-012c-4f75-8ac8-1f1d5dab48ba`.
- Reporte: `5d15139a-8010-47d5-8142-f594f9c46f8b`.
- OAuth de Google BigQuery completado por el usuario. Actualización a petición
  del 02/11/2026 completada correctamente: el servicio indica última actualización
  correcta a las 11:27:07, según la hora mostrada en su interfaz.
- Pendiente: identidad federada Entra, permisos, integración y activación del job.
- Microsoft Entra solicita verificación de Authenticator para acceder al portal.
  El usuario informó que perdió el dispositivo; la recuperación MFA queda
  pendiente con el soporte de su institución. El refresh manual del modelo ya
  funciona con la sesión de Power BI y las credenciales Google actuales.

[Abrir reporte publicado](https://app.powerbi.com/groups/bb832d0d-c96f-4b2f-b6a5-83de54073a14/reports/5d15139a-8010-47d5-8142-f594f9c46f8b?experience=power-bi).

1. Publicar `powerbi/bigquery/EcoBottle_AR.pbix` en un workspace de Power BI
   compartido. No usar **Mi área de trabajo** para este circuito con aplicación.
   Configurar allí la conexión OAuth de Google BigQuery y probar una
   actualización manual satisfactoria. La autenticación de GitHub para invocar
   la API es independiente de las credenciales con que el modelo lee BigQuery.
2. Registrar una aplicación dedicada en Microsoft Entra y crear una credencial
   federada para GitHub Actions:

   - Emisor: `https://token.actions.githubusercontent.com`.
   - Audiencia: `api://AzureADTokenExchange`.
   - Sujeto estándar: `repo:Ingbakk16/practica-imond:environment:bigquery`.
     Confirmar el `sub` real si el repositorio usa claims OIDC personalizados
     o inmutables; no ampliar la confianza a otros repositorios para corregirlo.
   - Mantener el environment `bigquery` restringido a las ramas autorizadas.

3. Un administrador debe habilitar el acceso a las APIs de Power BI/Fabric
   para el grupo de seguridad que contiene esa aplicación y darle acceso de
   miembro al workspace de destino. No se requiere un secreto de cliente ni
   agregar permisos delegados de Power BI a esta aplicación.
4. Configurar las siguientes **variables del environment `bigquery`**. Son
   identificadores UUID, no credenciales secretas:

   | Variable | Valor |
   |---|---|
   | `POWERBI_TENANT_ID` | Directory (tenant) ID de Microsoft Entra |
   | `POWERBI_CLIENT_ID` | Application (client) ID de la aplicación federada |
   | `POWERBI_WORKSPACE_ID` | ID del workspace publicado |
   | `POWERBI_DATASET_ID` | ID del modelo semántico, no del reporte |

5. Tras integrar el cambio y configurar el servicio, establecer la variable
   **del repositorio** `POWERBI_REFRESH_ENABLED=true`. Es de repositorio porque
   el `if` del job se evalúa antes de cargar las variables del environment.
   Si no está habilitada, BigQuery continúa igual y el job de Power BI se omite.
6. Ejecutar manualmente el workflow y comprobar el job `powerbi`, su resumen,
   el historial del modelo y los indicadores del reporte. Verificar después
   una ejecución nocturna. Desactivar otro schedule redundante de Power BI si
   se desea una sola actualización por carga.

Las altas de identidad, permisos, publicación y configuración del servicio
deben completarse con la cuenta autorizada del propietario. Este código no
crea accesos ni modifica la configuración del tenant.

## Diagnóstico

- 401/403: revisar federación, tenant, acceso de la aplicación al workspace y
  habilitación de APIs. No registrar tokens en los logs.
- Fallo de credenciales BigQuery: corregir la conexión del modelo en Service;
  autenticar GitHub en Microsoft no configura el origen Google del modelo.
- 429, error de red o espera agotada: revisar el historial antes de reintentar;
  la primera solicitud puede seguir activa. El script no reenvía el POST.
- Capacidad compartida: las actualizaciones por API cuentan para el límite de
  ocho solicitudes diarias, junto con las programadas. La configuración de
  capacidad y permisos debe permitir el uso de la API.

Pruebas offline, sin credenciales ni llamadas externas:

```powershell
python -m unittest discover -s cloud/tests -p test_powerbi_refresh.py -v
```

Referencias: [actualizar modelo](https://learn.microsoft.com/en-us/rest/api/power-bi/datasets/refresh-dataset-in-group),
[historial de actualización](https://learn.microsoft.com/en-us/rest/api/power-bi/datasets/get-refresh-history-in-group),
[aplicaciones en Power BI](https://learn.microsoft.com/en-us/power-bi/developer/embedded/embed-service-principal),
[federación con GitHub](https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation-create-trust?pivots=identity-wif-app-reg-github-actions).
