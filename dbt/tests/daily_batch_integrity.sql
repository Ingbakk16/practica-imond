-- Complete batches must be unique, preserve row counts and have matching payments.
with complete as (
    select batch_id from {{ source('ops', 'daily_batches') }} where status = 'complete'
), issues as (
    select 'duplicate marker' as issue from {{ source('ops', 'daily_batches') }}
    group by batch_id having count(*) != 1
    {% for table in ['address', 'customer', 'sales_order', 'sales_order_item', 'payment', 'shipment', 'web_session'] %}
    union all
    select '{{ table }} batch count' from {{ source('ops', 'daily_batches') }} as b
    left join (
        select batch_id, count(*) as n from {{ source('raw', 'daily_' ~ table) }} group by batch_id
    ) as d on d.batch_id = b.batch_id
    where b.status = 'complete'
        and coalesce(d.n, 0) != safe_cast(json_value(b.manifest, '$.files.{{ table }}.rows') as int64)
    {% endfor %}
    union all
    select 'daily order without exactly one payment' from {{ source('raw', 'daily_sales_order') }} as o
    join complete as b on b.batch_id = o.batch_id
    left join {{ source('raw', 'daily_payment') }} as p on p.batch_id = o.batch_id and p.order_id = o.order_id
    group by o.batch_id, o.order_id having count(p.payment_id) != 1
    union all
    select 'daily order without items' from {{ source('raw', 'daily_sales_order') }} as o
    join complete as b on b.batch_id = o.batch_id
    left join {{ source('raw', 'daily_sales_order_item') }} as i on i.batch_id = o.batch_id and i.order_id = o.order_id
    group by o.batch_id, o.order_id having count(i.order_item_id) = 0
    union all
    select 'daily payment mismatch' from {{ source('raw', 'daily_payment') }} as p
    join complete as b on b.batch_id = p.batch_id
    left join {{ source('raw', 'daily_sales_order') }} as o
        on o.batch_id = p.batch_id and o.order_id = p.order_id
    where o.order_id is null or p.amount != o.total_amount or p.status != 'PAID'
    union all
    select 'daily shipment mismatch' from {{ source('raw', 'daily_shipment') }} as s
    join complete as b on b.batch_id = s.batch_id
    left join {{ source('raw', 'daily_sales_order') }} as o
        on o.batch_id = s.batch_id and o.order_id = s.order_id
    where o.order_id is null or o.channel_id != 1 or s.status != 'READY'
    union all
    select 'daily row without a marker' from {{ source('raw', 'daily_sales_order') }} as o
    left join {{ source('ops', 'daily_batches') }} as b on b.batch_id = o.batch_id
    where b.batch_id is null
)
select * from issues
