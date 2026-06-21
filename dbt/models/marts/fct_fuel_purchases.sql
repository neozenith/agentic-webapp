-- Fuel-purchase fact table. Adds per-vehicle distance travelled between
-- consecutive fill-ups (derived from the odometer reading).
with fuel as (

    select * from {{ ref('stg_fuel_receipts') }}

)

select
    purchase_id,
    purchased_at,
    vehicle,
    station,
    fuel_type,
    litres,
    price_per_litre,
    total_cost,
    odometer_km,
    coalesce(
        odometer_km - lag(odometer_km) over (
            partition by vehicle
            order by purchased_at
        ),
        0
    ) as distance_km
from fuel
