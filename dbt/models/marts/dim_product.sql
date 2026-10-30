select
    p.product_id as product_key, p.product_id, p.sku, p.name,
    c.name as category, f.name as family, p.list_price, p.status
from {{ ref('stg_product') }} as p
left join {{ ref('stg_product_category') }} as c on c.category_id = p.category_id
left join {{ ref('stg_product_category') }} as f on f.category_id = c.parent_id
