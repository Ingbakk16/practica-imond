# EcoBottle AR

Proyecto de análisis comercial con datos sintéticos de ventas, clientes, actividad web y satisfacción. Integra un data warehouse, un pipeline diario y un informe en Looker Studio.

[Abrir el informe](https://datastudio.google.com/reporting/dfabaac0-911f-4735-b1b9-52733368cff9/page/93oCG)

## Qué permite analizar

El informe tiene cinco páginas: Resumen, Ventas, Clientes, Satisfacción y Adquisición web. Incluye ventas, pedidos, ticket promedio, compradores, ranking de productos, sesiones y NPS, con filtros de fecha y los desgloses correspondientes a cada fuente.

Los datos históricos abarcan del 1 de enero de 2024 al 30 de septiembre de 2025. Los lotes diarios agregan datos de demostración. Los importes se expresan en pesos argentinos; todos los datos son sintéticos.

## Cómo funciona

```text
CSV históricos y lotes diarios
           |
           v
        BigQuery
           |
           v
   Modelos y pruebas dbt
           |
           v
Conciliación y publicación validada
           |
           v
      Looker Studio
```

1. GitHub Actions valida las fuentes y carga los lotes diarios en BigQuery. Repetir una fecha con los mismos parámetros no duplica registros.
2. dbt construye las dimensiones, los hechos y las fuentes de presentación. Las conciliaciones contrastan los resultados con DuckDB y con cada lote generado.
3. Si los controles aprueban, se publican las cuatro fuentes y sus metadatos en una transacción. Una verificación posterior comprueba la publicación disponible para el informe.
4. Looker Studio consulta las fuentes publicadas. La tabla de actualización muestra hasta qué fecha hay datos, el último lote validado y la publicación en UTC.

El pipeline está programado para las 03:17 de Argentina y procesa el día anterior, con recuperación de fechas pendientes. GitHub puede demorar la ejecución. Las fuentes del informe tienen frescura de una hora; una página abierta puede requerir la opción **Actualizar datos**.

## Reglas principales

- Las ventas consideran pedidos pagados o entregados. El importe de venta de los pedidos incluye IVA y envío; las ventas por producto corresponden a las líneas sin esos conceptos.
- Los compradores y los usuarios web son poblaciones diferentes. Las sesiones anónimas no se cuentan como personas identificadas.
- El NPS se calcula sobre respuestas recibidas, según su fecha de respuesta.
- Cada fuente conserva su grano para evitar duplicar importes al relacionar pedidos, productos, sesiones y encuestas.

Las definiciones completas están en [Métricas](lookerstudio/METRICAS.md).

## Ejecutar y validar localmente

La versión local utiliza Python y DuckDB y permite reproducir el histórico sin una cuenta de Google Cloud.

```bash
python -m venv .venv
```

Activar el entorno con `.venv\Scripts\activate` en Windows o `source .venv/bin/activate` en Linux y macOS. Luego ejecutar:

```bash
python -m pip install -r requirements.txt
python generator/validate_raw.py
python run_sql.py
python validate_warehouse.py
```

La ejecución genera `warehouse.duckdb`, las tablas CSV de `dw/` y el diagrama del modelo. Los archivos de `raw/` son las fuentes originales y deben conservarse sin cambios.

Para configurar o ejecutar el circuito cloud, seguir la [guía de BigQuery y dbt](cloud/README.md). Requiere un proyecto de Google Cloud y autenticación federada desde GitHub Actions.

## Estructura

| Ubicación | Contenido |
|---|---|
| `raw/` | Fuentes históricas en CSV. |
| `sql/`, `run_sql.py`, `dw/` | Construcción local y resultados del warehouse. |
| `generator/` | Generación de datos sintéticos y validaciones de origen. |
| `dbt/` | Modelos y pruebas de BigQuery. |
| `cloud/`, `.github/workflows/` | Carga, conciliación, publicación y automatización. |
| `lookerstudio/` | Métricas, configuración del informe y evidencia de validación. |

## Documentación y estado

- [Guía del informe](lookerstudio/README.md).
- [Diagrama de origen](assets/DER.png), [modelo estrella](dw/modelo_estrella.md) y [validación del warehouse](VALIDACION.md).
- [Estado verificado](ESTADO_PROYECTO.md) y [plan de cierre](PLAN_CIERRE.md).
- [Registro de operación y consumo](lookerstudio/OPERACION.md).

La entrega funcional fue validada el 4 de noviembre de 2026, incluida la lectura pública y la reejecución de un lote sin duplicación. Queda observar siete ejecuciones programadas para completar la comprobación de continuidad. Los límites de consumo actuales se mantienen por decisión del propietario.
