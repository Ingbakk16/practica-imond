select 'customer' as issue
where (select count(*) from {{ ref('dim_customer') }} where customer_key = -1 and customer_id is null) != 1
union all
select 'store'
where (select count(*) from {{ ref('dim_store') }} where store_key = -1 and store_id is null) != 1
union all
select 'anonymous_nps'
where exists (
    select 1 from {{ ref('fact_nps_response') }} as f
    join {{ ref('stg_nps_response') }} as n on n.nps_id = f.nps_id
    where n.customer_id is null and f.customer_key != -1
)
union all
select 'online_store'
where exists (
    select 1 from {{ ref('fact_sales_order') }} as f
    join {{ ref('dim_channel') }} as c on c.channel_key = f.channel_key
    where c.code = 'ONLINE' and f.store_key != -1
)
