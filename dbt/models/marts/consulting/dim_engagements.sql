-- Engagement dimension. Stable projection of the staging model that a semantic
-- model binds to; do not rename columns.
with engagements as (

    select * from {{ ref('stg_consulting__engagements') }}

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
    start_date,
    end_date,
    contract_value,
    revenue_to_date,
    margin_pct
from engagements
