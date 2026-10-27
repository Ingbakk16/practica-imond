# Validación integral del warehouse (fase 6)

Ejecutada desde una rama `main` sin cambios locales, con Python 3.10.12 y DuckDB 1.5.5. Fecha de corte del conjunto de datos: **2025-09-30 23:59:59**.

## Reproducir

Desde la raíz del repositorio, con las dependencias de `requirements.txt` instaladas:

```bash
python3 generator/validate_raw.py
python3 run_sql.py
python3 validate_warehouse.py
git diff --exit-code -- raw/
git diff --exit-code -- dw/
```

`run_sql.py` reconstruye `warehouse.duckdb`, regenera `dw/` y ejecuta los controles SQL de `sql/03_consultas.sql`. `validate_warehouse.py` abre la base en **solo lectura** y coteja los CSV con sus tablas mediante diferencia de conjuntos con multiplicidad (`EXCEPT ALL`) en ambas direcciones: se comparan columnas, tipos, nulos y valores, sin depender del orden de filas. Revisa las claves y relaciones declaradas, el diagrama, los estados y los casos anónimos.

## Resultados

| Control | Resultado |
|---|---|
| Origen | `generator/validate_raw.py`: todas las reglas OK (PK/FK, dominios, montos, ciclo de vida y fechas). |
| Construcción desde cero | `run_sql.py`: 14 sentencias de dimensiones, 8 de hechos y 21 controles/consultas; sin errores. |
| Exportaciones | 10 tablas, 10 CSV: mismos encabezados y tipos, filas faltantes = 0 y sobrantes = 0 en cada archivo. |
| Modelo | 10 PK y 16 FK; 0 claves huérfanas; las relaciones y entidades aparecen en `dw/modelo_estrella.md`. |
| Conciliación mensual | Ventas, sesiones y usuarios activos en 21 meses; NPS por mes/canal y ventas por producto por mes coinciden con `raw/` (controles SQL OK). |
| Reproducibilidad | Tras reconstruir, `raw/` y los CSV/diagrama versionados de `dw/` no presentan diferencias en Git. |

| Tabla | Filas |
|---|---:|
| `dim_channel` | 2 |
| `dim_customer` | 3.472, incluida la fila `-1` |
| `dim_date` | 639 |
| `dim_product` | 2 |
| `dim_province` | 4 |
| `dim_store` | 5, incluida la fila `-1` |
| `fact_sales_order` | 11.969 |
| `fact_sales_order_item` | 14.573 |
| `fact_web_session` | 100.363 |
| `fact_nps_response` | 3.083 |

## Granos y casos límite

| Hecho | Una fila por | Clave primaria |
|---|---|---|
| `fact_sales_order` | Pedido | `order_id` |
| `fact_sales_order_item` | Línea de producto de un pedido | `order_item_id` |
| `fact_web_session` | Sesión web | `session_id` |
| `fact_nps_response` | Respuesta de encuesta | `nps_id` |

- **Ventas:** 10.998 pedidos `PAID`/`FULFILLED` y **$382.410.636,00** de `venta_neta`. Los 658 `CANCELLED`, el pedido `CREATED` y los 312 `REFUNDED` siguen en el hecho, pero tienen `venta_neta = 0`. Los totales de pedido no se multiplican al analizar ítems.
- **Sesiones:** 70.751 con cliente desconocido (`customer_key = -1`); 3.024 sin `ended_at` tienen `duration_seconds = NULL`, no cero.
- **NPS:** 3.083 respuestas, 122 anónimas (`customer_key = -1`); 1.428 promotores y 503 detractores dan **NPS 30,0**. La fecha analítica es `responded_at`, no la fecha de pedido.
- **Clientes y tienda:** los pedidos e ítems no tienen clientes desconocidos; 7.286 pedidos online usan `store_key = -1` (sin tienda). Las fechas y claves de los cuatro hechos son congruentes con el origen según los controles SQL.

La referencia mensual completa del origen y sus definiciones se encuentran en [`PERFILADO.md`](PERFILADO.md). Para consumo en Power BI, seguir [`powerbi/README.md`](powerbi/README.md).
