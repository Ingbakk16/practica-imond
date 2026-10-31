select s.store_id as store_key, s.store_id, s.name, s.address_id, a.city, p.code as province_code
from {{ ref('stg_store') }} as s
join {{ ref('stg_address') }} as a on a.address_id = s.address_id
join {{ ref('stg_province') }} as p on p.province_id = a.province_id
union all
select -1, cast(null as int64), 'Sin tienda', cast(null as int64),
    cast(null as string), cast(null as string)
