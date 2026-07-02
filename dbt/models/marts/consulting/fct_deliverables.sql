-- Deliverables fact table. One row per engagement deliverable.
with deliverables as (

    select * from {{ ref('stg_consulting__deliverables') }}

)

select
    deliverable_id,
    engagement,
    name,
    status,
    rag,
    due_date,
    progress
from deliverables
