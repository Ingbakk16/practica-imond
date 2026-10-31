-- Return any order whose totals, sale flag or net revenue violate the source rules.
select o.order_id
from {{ ref('fact_sales_order') }} as o
left join (
    select order_id, sum(line_total) as item_subtotal
    from {{ ref('fact_sales_order_item') }}
    group by order_id
) as i on i.order_id = o.order_id
where o.subtotal is null or o.tax_amount is null or o.shipping_fee is null
    or o.total_amount is null or o.venta_neta is null or o.es_venta is null
    or i.item_subtotal is null or o.subtotal != i.item_subtotal
    or o.tax_amount != round(o.subtotal * cast('0.21' as numeric), 2)
    or o.total_amount != o.subtotal + o.tax_amount + o.shipping_fee
    or o.es_venta != (o.status in ('PAID', 'FULFILLED'))
    or o.venta_neta != case when o.es_venta then o.total_amount else cast(0 as numeric) end
