select * from {{ source('raw', 'sales_order_item') }}
