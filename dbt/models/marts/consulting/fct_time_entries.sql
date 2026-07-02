-- Time-entry fact table. One row per logged time entry.
with time_entries as (

    select * from {{ ref('stg_consulting__time_entries') }}

)

select
    time_entry_id,
    entry_date,
    consultant,
    engagement,
    role,
    hours,
    billable,
    cost
from time_entries
