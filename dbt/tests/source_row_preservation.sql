-- Inner joins must not silently discard source facts or duplicate their rows.
{% for fact, source_name in [
    ('fact_sales_order', 'sales_order'),
    ('fact_sales_order_item', 'sales_order_item'),
    ('fact_web_session', 'web_session'),
    ('fact_nps_response', 'nps_response')
] %}
select '{{ fact }}' as issue
where (select count(*) from {{ ref(fact) }}) != (select count(*) from {{ source('raw', source_name) }})
{% if not loop.last %}union all{% endif %}
{% endfor %}
