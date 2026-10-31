-- Grain: one order, including non-sales. Revenue includes tax and shipping.
select
    o.order_id, d.date_key, ch.channel_key, c.customer_key,
    coalesce(s.store_key, -1) as store_key, p.province_key,
    o.order_date, o.status, o.status in ('PAID', 'FULFILLED') as es_venta,
    o.subtotal, o.tax_amount, o.shipping_fee, o.total_amount,
    case when o.status in ('PAID', 'FULFILLED') then o.total_amount
        else cast(0 as numeric) end as venta_neta
from {{ ref('stg_sales_order') }} as o
join {{ ref('dim_date') }} as d on d.date_value = date(o.order_date)
join {{ ref('dim_channel') }} as ch on ch.channel_id = o.channel_id
join {{ ref('dim_customer') }} as c on c.customer_id = o.customer_id
left join {{ ref('dim_store') }} as s on s.store_id = o.store_id
join {{ ref('stg_address') }} as a on a.address_id = o.shipping_address_id
join {{ ref('dim_province') }} as p on p.province_id = a.province_id
