-- Grain: one response, dated by response time; no order attribution.
select
    n.nps_id, d.date_key, ch.channel_key,
    case when n.customer_id is null then -1 else c.customer_key end as customer_key,
    n.responded_at, n.score, n.comment
from {{ ref('stg_nps_response') }} as n
join {{ ref('dim_date') }} as d on d.date_value = date(n.responded_at)
join {{ ref('dim_channel') }} as ch on ch.channel_id = n.channel_id
left join {{ ref('dim_customer') }} as c on c.customer_id = n.customer_id
