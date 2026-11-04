select
    n.nps_id, date(n.responded_at) as fecha, ch.code as canal, n.score as puntaje,
    1 as respuestas,
    case when n.score >= 9 then 1 else 0 end as promotores,
    case when n.score <= 6 then 1 else 0 end as detractores,
    case when n.score between 7 and 8 then 1 else 0 end as pasivos
from {{ ref('fact_nps_response') }} as n
join {{ ref('dim_channel') }} as ch on ch.channel_key = n.channel_key
