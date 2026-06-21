-- Typed consulting-engagement rows. One row per engagement.
with source as (

    select * from {{ source('consulting_raw', 'raw_engagements') }}

)

select
    engagement_id,
    name,
    client,
    service_line,
    lead_consultant,
    phase,
    status,
    rag_overall,
    cast(start_date as date)        as start_date,
    cast(end_date as date)          as end_date,
    cast(contract_value as numeric) as contract_value,
    cast(revenue_to_date as numeric) as revenue_to_date,
    cast(margin_pct as float64)     as margin_pct
from source
