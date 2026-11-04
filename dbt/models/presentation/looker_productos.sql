-- One row per item. Revenue excludes VAT and shipping, unlike looker_ventas.
select
    i.order_item_id, i.order_id, date(o.order_date) as fecha,
    ch.code as canal, p.name as provincia, s.name as tienda,
    pr.name as producto, pr.category as categoria, pr.family as familia,
    i.venta_neta as ventas_producto_ars,
    case when i.es_venta then i.quantity else 0 end as unidades_vendidas
from {{ ref('fact_sales_order_item') }} as i
join {{ ref('fact_sales_order') }} as o on o.order_id = i.order_id
join {{ ref('dim_channel') }} as ch on ch.channel_key = i.channel_key
join {{ ref('dim_province') }} as p on p.province_key = i.province_key
join {{ ref('dim_store') }} as s on s.store_key = i.store_key
join {{ ref('dim_product') }} as pr on pr.product_key = i.product_key
