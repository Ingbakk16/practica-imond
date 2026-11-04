-- Looker Studio custom query. Replace PROJECT_ID and enable date parameters.
-- Global ranking: only date controls, not channel/province/product controls.
with ventas as (
    select date_trunc(fecha, month) as mes, producto,
        sum(ventas_producto_ars) as ventas_producto_ars
    from `PROJECT_ID.ecobottle_looker.looker_productos`
    where fecha between parse_date('%Y%m%d', @DS_START_DATE)
                    and parse_date('%Y%m%d', @DS_END_DATE)
    group by mes, producto
)
select mes, producto, ventas_producto_ars,
    dense_rank() over (partition by mes order by ventas_producto_ars desc) as posicion
from ventas
