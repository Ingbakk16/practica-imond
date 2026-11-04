select
    o.order_id, date(o.order_date) as fecha, o.customer_key,
    ch.code as canal, p.name as provincia, s.name as tienda,
    c.status as estado_cliente, o.status as estado_pedido,
    o.venta_neta as ventas_ars,
    case when o.es_venta then 1 else 0 end as pedidos_venta,
    case when o.es_venta then o.customer_key end as cliente_comprador
from {{ ref('fact_sales_order') }} as o
join {{ ref('dim_channel') }} as ch on ch.channel_key = o.channel_key
join {{ ref('dim_province') }} as p on p.province_key = o.province_key
join {{ ref('dim_store') }} as s on s.store_key = o.store_key
join {{ ref('dim_customer') }} as c on c.customer_key = o.customer_key
