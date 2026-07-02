-- Engagement-financials fact table. One row per engagement per period.
with financials as (

    select * from {{ ref('stg_consulting__financials') }}

)

select
    financial_id,
    period,
    engagement,
    client,
    revenue,
    cost,
    margin
from financials
