# Workflow del proyecto

Este documento describe el ciclo de trabajo para construir y revisar el data warehouse de EcoBottle AR.

## 1. Preparar el entorno

Crear y activar un entorno virtual una sola vez:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

En Windows, usar `.venv\Scripts\activate` y `python` en lugar de `python3` cuando corresponda.

## 2. Conocer los datos de origen

Los CSV de `raw/` son la fuente de verdad y no deben modificarse. El script los expone como vistas del esquema `raw`.

Abrir el explorador:

```bash
python3 run_sql.py --explorar
```

Consultas iniciales recomendadas:

```sql
SHOW ALL TABLES;
DESCRIBE raw.sales_order;
SELECT * FROM raw.sales_order LIMIT 10;
SELECT status, COUNT(*) FROM raw.sales_order GROUP BY status ORDER BY status;
```

Antes de modelar una tabla, documentar:

- El grano: qué representa una fila.
- La clave natural disponible en `raw`.
- Las relaciones con otras tablas.
- Las columnas obligatorias y los posibles `NULL`.
- Las métricas y su unidad monetaria.
- La definición de negocio que debe respetarse.

## 3. Definir el modelo

Diseñar primero las dimensiones y los hechos en papel o en una tabla breve. Para cada tabla decidir:

- Nombre de la tabla.
- Grano.
- Clave primaria.
- Claves foráneas.
- Métricas.
- Reglas de inclusión, por ejemplo, qué estados cuentan como venta.

Usar claves sustitutas en las dimensiones (`*_key`) y conservar la clave natural del origen (`*_id`) para trazabilidad.

Agregar una fila `Desconocido` con clave `-1` cuando una relación pueda ser nula y el hecho deba conservarse. Esto aplica especialmente a clientes anónimos, direcciones faltantes y respuestas NPS anónimas.

## 4. Construir las dimensiones

Editar `sql/01_dimensiones.sql`.

Orden recomendado:

1. `dim_date`.
2. `dim_channel`.
3. `dim_province`.
4. `dim_product` y su jerarquía de categoría.
5. `dim_customer`.
6. `dim_store`.

Cada dimensión debe seguir este patrón:

```sql
CREATE TABLE dim_example (...);

INSERT INTO dim_example
SELECT ...
FROM raw.source_table;
```

Las dimensiones deben ser legibles, contener atributos útiles para segmentar y evitar duplicar métricas de los hechos.

## 5. Construir los hechos

Editar `sql/02_hechos.sql`.

Crear los hechos después de que todas las dimensiones necesarias existan. Cada carga debe:

- Unir la fuente `raw` con las dimensiones para obtener las claves sustitutas.
- Convertir valores nulos a `-1` cuando exista una fila desconocida.
- Mantener el grano declarado.
- Usar `DECIMAL(12, 2)` para importes.
- Declarar `PRIMARY KEY` y `FOREIGN KEY`.
- Excluir pedidos que no correspondan a la métrica cuando la definición indique ventas netas.

Hechos recomendados:

- `fact_sales_order`: una fila por pedido.
- `fact_sales_order_item`: una fila por producto dentro de un pedido.
- `fact_web_session`: una fila por sesión web.
- `fact_nps_response`: una fila por respuesta NPS.

No mezclar hechos de distinto grano en una misma tabla. Esto evita duplicar el total de un pedido al unirlo con sus ítems.

## 6. Crear consultas de control y KPIs

Editar `sql/03_consultas.sql`.

Incluir consultas que permitan verificar:

- Cantidad de filas de cada dimensión y hecho.
- Claves huérfanas o nulas inesperadas.
- Ventas por mes, canal, provincia y producto.
- Pedidos y ticket promedio.
- Clientes o usuarios activos.
- Sesiones por fuente y dispositivo.
- NPS, promotores, pasivos y detractores.

Definiciones base del dataset:

- Venta: pedidos `PAID` o `FULFILLED`.
- Venta neta: excluir `CREATED`, `CANCELLED` y `REFUNDED`.
- NPS: `((promotores - detractores) / respuestas) * 100`.
- Fecha de ventas: `sales_order.order_date`.
- Fecha de NPS: `nps_response.responded_at`.

## 7. Ejecutar y revisar

Validar primero los datos de origen:

```bash
python3 generator/validate_raw.py
```

Construir el warehouse desde cero:

```bash
python3 run_sql.py
```

Revisar los archivos generados en `dw/`:

- Un CSV por tabla creada.
- `modelo_estrella.md` con el diagrama de relaciones.

Para explorar el resultado junto con las fuentes:

```bash
python3 run_sql.py --ui
```

Si el navegador no está disponible, el script ofrece una consola SQL en la terminal.

## 8. Ciclo de iteración

Para cada cambio:

1. Formular una pregunta de negocio.
2. Explorar las tablas de origen involucradas.
3. Confirmar el grano y la regla de inclusión.
4. Implementar el cambio en el archivo SQL correspondiente.
5. Ejecutar `generator/validate_raw.py` si se modificó el generador o los datos.
6. Ejecutar `run_sql.py`.
7. Comparar los resultados con las reglas de `README.md` y los KPIs esperados.
8. Revisar `dw/` y el diagrama.
9. Revisar el diff y guardar un commit pequeño y descriptivo.

## 9. Criterios antes de cerrar una iteración

- `raw/` no fue modificado accidentalmente.
- Las claves primarias son únicas y no nulas.
- No existen claves foráneas huérfanas.
- Los totales no se duplican al unir hechos.
- Los importes usan precisión decimal.
- Los estados y fechas respetan las reglas del negocio.
- `python3 run_sql.py` termina sin errores.
- Las tablas exportadas y el diagrama representan el modelo actual.
- Las consultas KPI tienen una definición explícita y reproducible.

## 10. Validación automática en GitHub Actions

El workflow [`.github/workflows/validate.yml`](.github/workflows/validate.yml) valida la práctica histórica en Ubuntu con Python 3.12 y la versión de DuckDB fijada en `requirements.txt`. Se ejecuta en pull requests, pushes a `main` o `feature/big-query` y de forma manual. No requiere credenciales de Google Cloud ni otros secretos.

Controles, en orden:

1. Generar el histórico con semilla 42 en una carpeta temporal del runner y validarlo con `generator/validate_raw.py --dir ...`, sin sobrescribir `raw/`.
2. Validar los CSV históricos versionados en `raw/`.
3. Ejecutar `python run_sql.py` y `python validate_warehouse.py` sobre esos CSV.
4. Comprobar que no se modificaron ni agregaron archivos de origen, incluso si falló un control anterior.

Los comandos guardan logs sin ocultar sus códigos de error: si falla un control, falla el job. Las exportaciones de `dw/` se reconstruyen solo en el runner descartable y no se guardan mediante commits automáticos.

Para lanzarlo manualmente, abrir **Actions → Validate historical pipeline → Run workflow** y seleccionar la rama. GitHub solo ofrece el botón cuando el workflow también existe en la rama predeterminada; antes de integrarlo, el push a `feature/big-query` y los pull requests permiten probarlo.

El resumen de la ejecución muestra el resultado de cada control. Los logs y una copia del resumen se publican como artifact **validation-logs**, con retención de siete días, también si fallan las validaciones. Una cancelación puede impedir la publicación de diagnósticos. No se publica la base completa ni se cambia el circuito local de la práctica.
