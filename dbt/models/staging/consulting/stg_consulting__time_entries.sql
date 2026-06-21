-- Typed time-entry rows. One row per logged time entry.
with source as (

    select * from {{ source('consulting_raw', 'raw_time_entries') }}

)

select
    time_entry_id,
    cast(entry_date as date) as entry_date,
    consultant,
    engagement,
    role,
    cast(hours as float64)   as hours,
    cast(billable as bool)   as billable,
    cast(cost as numeric)    as cost
from source
