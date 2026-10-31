-- Grain: one order item. Revenue excludes tax and shipping.
select
    i.order_item_id, i.order_id, o.date_key, o.channel_key, o.customer_key,
    o.store_key, o.province_key, p.product_key, o.es_venta,
    i.quantity, i.unit_price, i.discount_amount, i.line_total,
    case when o.es_venta then i.line_total else cast(0 as numeric) end as venta_neta
from {{ ref('stg_sales_order_item') }} as i
join {{ ref('fact_sales_order') }} as o on o.order_id = i.order_id
join {{ ref('dim_product') }} as p on p.product_id = i.product_id
