-- Inner joins must not silently discard source facts or duplicate their rows.
{% for fact, source_name in [
    ('fact_sales_order', 'stg_sales_order'),
    ('fact_sales_order_item', 'stg_sales_order_item'),
    ('fact_web_session', 'stg_web_session'),
    ('fact_nps_response', 'stg_nps_response')
] %}
select '{{ fact }}' as issue
from (select 1) as singleton
where (select count(*) from {{ ref(fact) }}) != (select count(*) from {{ ref(source_name) }})
{% if not loop.last %}union all{% endif %}
{% endfor %}
