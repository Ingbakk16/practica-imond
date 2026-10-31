select * from {{ source('raw', 'web_session') }}
union all
select d.* except(batch_id) from {{ source('raw', 'daily_web_session') }} as d
join {{ source('ops', 'daily_batches') }} as b on b.batch_id = d.batch_id and b.status = 'complete'
