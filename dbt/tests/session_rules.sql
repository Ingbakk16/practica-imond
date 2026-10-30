select f.session_id
from {{ ref('fact_web_session') }} as f
join {{ ref('stg_web_session') }} as s on s.session_id = f.session_id
where f.duration_seconds < 0
    or (f.ended_at is null and f.duration_seconds is not null)
    or (f.ended_at is not null and f.duration_seconds is null)
    or (s.customer_id is null and f.customer_key != -1)
