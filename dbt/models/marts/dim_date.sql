with bounds as (
    select max(date_value) as last_date
    from (
        select date(order_date) as date_value from {{ ref('stg_sales_order') }}
        union all
        select date(started_at) from {{ ref('stg_web_session') }}
        union all
        select date(responded_at) from {{ ref('stg_nps_response') }}
    )
)
select
    cast(format_date('%Y%m%d', day_value) as int64) as date_key,
    day_value as date_value,
    extract(year from day_value) as year,
    extract(month from day_value) as month,
    format_date('%B', day_value) as month_name,
    extract(day from day_value) as day,
    format_date('%A', day_value) as day_name
from bounds, unnest(generate_date_array(date '2024-01-01', last_date)) as day_value
