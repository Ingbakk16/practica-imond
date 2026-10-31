select * from {{ source('raw', 'customer') }}
union all
select d.* except(batch_id) from {{ source('raw', 'daily_customer') }} as d
join {{ source('ops', 'daily_batches') }} as b on b.batch_id = d.batch_id and b.status = 'complete'
