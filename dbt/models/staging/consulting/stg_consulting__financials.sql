-- Typed engagement-financial rows. One row per engagement per period.
with source as (

    select * from {{ source('consulting_raw', 'raw_financials') }}

)

select
    financial_id,
    cast(period as date)   as period,
    engagement,
    client,
    cast(revenue as numeric) as revenue,
    cast(cost as numeric)    as cost,
    cast(margin as numeric)  as margin
from source
