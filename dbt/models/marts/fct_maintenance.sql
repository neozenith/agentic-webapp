-- Maintenance fact table. A thin, stable projection of the staging model so
-- downstream semantic models bind to mart names, not staging.
with maintenance as (

    select * from {{ ref('stg_maintenance') }}

)

select
    maintenance_id,
    serviced_at,
    vehicle,
    category,
    vendor,
    total_cost
from maintenance
