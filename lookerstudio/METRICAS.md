# Campos y medidas de Looker Studio

Crear estos campos calculados en su fuente correspondiente. Las fórmulas con
agregaciones quedan en **Auto**. No usar el conteo de registros predeterminado
para pedidos: incluye pedidos no vendidos.

## Pedidos — `looker_ventas`

| Nombre visible | Fórmula | Formato |
|---|---|---|
| Ventas ARS | `SUM(ventas_ars)` | ARS, 2 decimales |
| Pedidos | `SUM(pedidos_venta)` | Entero |
| Clientes compradores | `COUNT_DISTINCT(cliente_comprador)` | Entero |
| Ticket promedio ARS | Fórmula debajo | ARS, 2 decimales |

```text
CASE
  WHEN SUM(pedidos_venta) = 0 THEN NULL
  ELSE SUM(ventas_ars) / SUM(pedidos_venta)
END
```

`cliente_comprador` es NULL en pedidos no vendidos; el distinto ignora esos nulos.
No usar `COUNT_DISTINCT(customer_key)` sin filtrar ventas. `estado_cliente` es
el estado de la foto de origen, no un historial de cambios.

## Productos — `looker_productos`

| Nombre | Fórmula | Formato |
|---|---|---|
| Ventas por producto ARS | `SUM(ventas_producto_ars)` | ARS, 2 decimales |
| Unidades vendidas | `SUM(unidades_vendidas)` | Entero |

No incluir IVA/envío ni contar pedidos a partir de líneas. El importe total del
pedido no está en esta fuente por diseño.

## Adquisición — `looker_sesiones`

| Nombre | Fórmula | Formato |
|---|---|---|
| Sesiones | `SUM(sesiones)` | Entero |
| Sesiones anónimas | `SUM(sesiones_anonimas)` | Entero |
| Usuarios activos | `COUNT_DISTINCT(usuario_identificado)` | Entero |
| Duración media (s) | `AVG(duracion_segundos)` | Número, 1 decimal |

El promedio excluye duraciones NULL; no reemplazarlas por cero. Los usuarios se
deduplican en el período seleccionado, no sumando distintos de meses/días.

## Satisfacción — `looker_nps`

| Nombre | Fórmula | Formato |
|---|---|---|
| Respuestas NPS | `SUM(respuestas)` | Entero |
| Promotores | `SUM(promotores)` | Entero |
| Pasivos | `SUM(pasivos)` | Entero |
| Detractores | `SUM(detractores)` | Entero |
| NPS | Fórmula debajo | Número, 1 decimal; **no porcentaje** |

```text
CASE
  WHEN SUM(respuestas) = 0 THEN NULL
  ELSE 100 * (SUM(promotores) - SUM(detractores)) / SUM(respuestas)
END
```

Promotores: 9–10; pasivos: 7–8; detractores: 0–6. No promediar NPS mensuales ni
aplicar la fecha de pedido. Sin respuestas, mostrar sin datos, no NPS cero. Lo
mismo aplica al ticket sin ventas y a la duración sin cierres.
