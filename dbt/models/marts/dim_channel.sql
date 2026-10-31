select channel_id as channel_key, channel_id, code, name
from {{ ref('stg_channel') }}
