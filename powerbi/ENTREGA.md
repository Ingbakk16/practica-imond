# Entrega del dashboard EcoBottle AR

Reporte construido y revisado en Power BI Desktop para Windows el 28/10/2026.

El PBIX final se guardó con datos, se actualizó desde los CSV y se volvió a abrir en una instancia nueva de Desktop. La reapertura conserva la portada sin filtros y los totales de ventas y pedidos. Su contenedor pasó la comprobación de integridad ZIP y contiene las cinco páginas y los 53 objetos visuales.

## Archivos

- `EcoBottle_AR.pbix`: reporte nativo con datos importados.
- `EcoBottle_AR.pbip`, `EcoBottle_AR.Report/` y `EcoBottle_AR.SemanticModel/`: definición editable del reporte y del modelo.
- `build_project.py`: generador del proyecto inicial a partir de los contratos de importación y las medidas del repositorio. Ejecutarlo con Power BI cerrado; después abrir el proyecto, actualizar y guardar en Desktop. No reemplaza el guardado nativo del PBIX.

El reporte contiene cinco páginas: **Resumen**, **Ventas**, **Clientes**, **Adquisición web** y **Satisfacción**. Usa seis dimensiones, cuatro hechos, dieciséis relaciones unidireccionales y diecisiete medidas. Las claves técnicas están ocultas.

## Controles realizados

Se revisaron visualmente las cinco páginas en Desktop, sin errores de visualización. Se comprobaron los siguientes resultados:

| Indicador o selección | Resultado |
|---|---:|
| Ventas totales | $382.410.636,00 |
| Pedidos de venta | 10.998 |
| Ticket promedio | $34.770,93 |
| Clientes compradores | 3.194 |
| Ventas por producto, sin IVA ni envío | $309.891.600,00 |
| Unidades vendidas | 23.545 |
| Sesiones web | 100.363 |
| Usuarios identificados con sesión | 3.077 |
| Sesiones anónimas | 70.751 |
| Duración media, excluyendo sesiones sin cierre | 435,3 segundos |
| Respuestas NPS | 3.083 |
| Promotores / detractores | 1.428 / 503 |
| NPS global | 30,0 puntos |
| Selección del canal ONLINE en satisfacción | NPS 24,0 puntos |
| Selección de enero de 2024 en resumen | 460 pedidos y $15.965.464,50 |

El ranking mensual por producto muestra posiciones 1 y 2. Se corrigió `Ranking Producto` para usar `ALLSELECTED(dim_product)`: liberar únicamente la clave dejaba activo el filtro por nombre y podía devolver posición 1 para ambos productos.

Se comprobó la selección de Buenos Aires en el gráfico de provincias y la selección de Classic A Bottle en el segmentador de productos. Esta última reduce las ventas de líneas a $147.174.600,00 y mantiene las ventas de pedidos en $382.410.636,00, como corresponde al alcance del modelo. Todos los filtros de prueba se restablecieron antes del guardado. La actualización del PBIX desde `RutaDW` terminó sin errores.

También se contrastaron los totales de pedidos, ventas y NPS directamente con los CSV usando precisión decimal para los importes. Una comprobación estática del proyecto verificó las referencias de campos de los 53 objetos visuales, sus posiciones dentro del lienzo y las 16 relaciones entre hechos y dimensiones.

## Actualización y alcance

Los archivos de `raw/` y `dw/` no se modificaron. El parámetro **RutaDW** apunta a la carpeta `dw` de este repositorio. En otra computadora, cambiar ese parámetro en **Transformar datos → Administrar parámetros** y ejecutar **Actualizar**.

Fecha y cliente filtran los cuatro hechos. Canal filtra ventas y NPS; provincia y tienda filtran ventas. Producto filtra solamente los ítems, por lo que no reduce el total de pedidos ni atribuye NPS o sesiones a productos. Las sesiones anónimas no representan personas únicas. NPS usa fecha de respuesta y se expresa en puntos.

La publicación en Power BI Service no forma parte de esta entrega local.
