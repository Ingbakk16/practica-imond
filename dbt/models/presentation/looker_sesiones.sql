-- One row per session. NULL identified user is intentionally ignored by COUNT_DISTINCT.
select
    session_id, date(started_at) as fecha, source as fuente, device as dispositivo,
    case when customer_key <> -1 then customer_key end as usuario_identificado,
    1 as sesiones,
    case when customer_key = -1 then 1 else 0 end as sesiones_anonimas,
    duration_seconds as duracion_segundos
from {{ ref('fact_web_session') }}
