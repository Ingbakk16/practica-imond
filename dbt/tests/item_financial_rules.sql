select i.order_item_id
from {{ ref('fact_sales_order_item') }} as i
join {{ ref('fact_sales_order') }} as o on o.order_id = i.order_id
where i.quantity is null or i.quantity <= 0 or i.unit_price is null
    or i.discount_amount is null or i.line_total is null or i.venta_neta is null
    or i.es_venta is null or i.es_venta != o.es_venta
    or i.line_total != i.quantity * i.unit_price - i.discount_amount
    or i.venta_neta != case when o.es_venta then i.line_total else cast(0 as numeric) end
