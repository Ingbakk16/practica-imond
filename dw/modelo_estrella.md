# Modelo estrella

Generado por `run_sql.py` a partir de las tablas de `warehouse.duckdb`.

```mermaid
erDiagram
    dim_channel ||--o{ fact_nps_response : "channel_key"
    dim_channel ||--o{ fact_sales_order : "channel_key"
    dim_channel ||--o{ fact_sales_order_item : "channel_key"
    dim_customer ||--o{ fact_nps_response : "customer_key"
    dim_customer ||--o{ fact_sales_order : "customer_key"
    dim_customer ||--o{ fact_sales_order_item : "customer_key"
    dim_customer ||--o{ fact_web_session : "customer_key"
    dim_date ||--o{ fact_nps_response : "date_key"
    dim_date ||--o{ fact_sales_order : "date_key"
    dim_date ||--o{ fact_sales_order_item : "date_key"
    dim_date ||--o{ fact_web_session : "date_key"
    dim_product ||--o{ fact_sales_order_item : "product_key"
    dim_province ||--o{ fact_sales_order : "province_key"
    dim_province ||--o{ fact_sales_order_item : "province_key"
    dim_store ||--o{ fact_sales_order : "store_key"
    dim_store ||--o{ fact_sales_order_item : "store_key"
    dim_channel {
        INTEGER channel_key PK
        INTEGER channel_id
        VARCHAR code
        VARCHAR name
    }
    dim_customer {
        INTEGER customer_key PK
        INTEGER customer_id
        VARCHAR email
        VARCHAR first_name
        VARCHAR last_name
        VARCHAR status
        TIMESTAMP created_at
    }
    dim_date {
        INTEGER date_key PK
        DATE date_value
        INTEGER year
        INTEGER month
        VARCHAR month_name
        INTEGER day
        VARCHAR day_name
    }
    dim_product {
        INTEGER product_key PK
        INTEGER product_id
        VARCHAR sku
        VARCHAR name
        VARCHAR category
        VARCHAR family
        DECIMAL list_price
        VARCHAR status
    }
    dim_province {
        INTEGER province_key PK
        INTEGER province_id
        VARCHAR code
        VARCHAR name
    }
    dim_store {
        INTEGER store_key PK
        INTEGER store_id
        VARCHAR name
        INTEGER address_id
        VARCHAR city
        VARCHAR province_code
    }
    fact_nps_response {
        BIGINT nps_id PK
        INTEGER date_key FK
        INTEGER channel_key FK
        INTEGER customer_key FK
        TIMESTAMP responded_at
        INTEGER score
        VARCHAR comment
    }
    fact_sales_order {
        BIGINT order_id PK
        INTEGER date_key FK
        INTEGER channel_key FK
        INTEGER customer_key FK
        INTEGER store_key FK
        INTEGER province_key FK
        TIMESTAMP order_date
        VARCHAR status
        BOOLEAN es_venta
        DECIMAL subtotal
        DECIMAL tax_amount
        DECIMAL shipping_fee
        DECIMAL total_amount
        DECIMAL venta_neta
    }
    fact_sales_order_item {
        BIGINT order_item_id PK
        BIGINT order_id
        INTEGER date_key FK
        INTEGER channel_key FK
        INTEGER customer_key FK
        INTEGER store_key FK
        INTEGER province_key FK
        INTEGER product_key FK
        BOOLEAN es_venta
        BIGINT quantity
        DECIMAL unit_price
        DECIMAL discount_amount
        DECIMAL line_total
        DECIMAL venta_neta
    }
    fact_web_session {
        BIGINT session_id PK
        INTEGER date_key FK
        INTEGER customer_key FK
        TIMESTAMP started_at
        TIMESTAMP ended_at
        VARCHAR source
        VARCHAR device
        BIGINT duration_seconds
    }
```
