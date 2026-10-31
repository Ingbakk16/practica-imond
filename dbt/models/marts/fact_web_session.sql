-- Grain: one session, dated by its start; missing end means unknown duration.
select
    s.session_id, d.date_key,
    case when s.customer_id is null then -1 else c.customer_key end as customer_key,
    s.started_at, s.ended_at, s.source, s.device,
    datetime_diff(s.ended_at, s.started_at, second) as duration_seconds
from {{ ref('stg_web_session') }} as s
join {{ ref('dim_date') }} as d on d.date_value = date(s.started_at)
left join {{ ref('dim_customer') }} as c on c.customer_id = s.customer_id
