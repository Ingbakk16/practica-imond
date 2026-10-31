select
    customer_id as customer_key, customer_id, email, first_name,
    last_name, status, created_at
from {{ ref('stg_customer') }}
union all
select -1, cast(null as int64), cast(null as string), 'Desconocido',
    cast(null as string), cast(null as string), cast(null as datetime)
