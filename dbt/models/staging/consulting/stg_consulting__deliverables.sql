-- Typed deliverable rows. One row per engagement deliverable.
with source as (

    select * from {{ source('consulting_raw', 'raw_deliverables') }}

)

select
    deliverable_id,
    engagement,
    name,
    status,
    rag,
    cast(due_date as date) as due_date,
    cast(progress as int64) as progress
from source
