-- Conservation checks catch both fanout and row loss in presentation joins.
select 'ventas' as control
from (select 1) as singleton
where (select count(*) from {{ ref('looker_ventas') }}) <> (select count(*) from {{ ref('fact_sales_order') }})
   or (select coalesce(sum(ventas_ars), 0) from {{ ref('looker_ventas') }}) <> (select coalesce(sum(venta_neta), 0) from {{ ref('fact_sales_order') }})
   or (select coalesce(sum(pedidos_venta), 0) from {{ ref('looker_ventas') }}) <> (select count(*) from {{ ref('fact_sales_order') }} where es_venta)
union all
select 'productos'
from (select 1) as singleton
where (select count(*) from {{ ref('looker_productos') }}) <> (select count(*) from {{ ref('fact_sales_order_item') }})
   or (select coalesce(sum(ventas_producto_ars), 0) from {{ ref('looker_productos') }}) <> (select coalesce(sum(venta_neta), 0) from {{ ref('fact_sales_order_item') }})
   or (select coalesce(sum(unidades_vendidas), 0) from {{ ref('looker_productos') }}) <> (select coalesce(sum(quantity), 0) from {{ ref('fact_sales_order_item') }} where es_venta)
union all
select 'sesiones'
from (select 1) as singleton
where (select count(*) from {{ ref('looker_sesiones') }}) <> (select count(*) from {{ ref('fact_web_session') }})
   or (select count(distinct usuario_identificado) from {{ ref('looker_sesiones') }}) <> (select count(distinct customer_key) from {{ ref('fact_web_session') }} where customer_key <> -1)
   or (select coalesce(sum(sesiones_anonimas), 0) from {{ ref('looker_sesiones') }}) <> (select count(*) from {{ ref('fact_web_session') }} where customer_key = -1)
union all
select 'nps'
from (select 1) as singleton
where (select count(*) from {{ ref('looker_nps') }}) <> (select count(*) from {{ ref('fact_nps_response') }})
   or (select coalesce(sum(promotores), 0) from {{ ref('looker_nps') }}) <> (select count(*) from {{ ref('fact_nps_response') }} where score >= 9)
   or (select coalesce(sum(detractores), 0) from {{ ref('looker_nps') }}) <> (select count(*) from {{ ref('fact_nps_response') }} where score <= 6)
