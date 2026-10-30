select province_id as province_key, province_id, code, name
from {{ ref('stg_province') }}
