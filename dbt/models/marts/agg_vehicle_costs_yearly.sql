-- Per-vehicle, per-year cost rollup combining fuel and maintenance spend.
-- Full join on (vehicle, year) so a year with only one cost type still appears.
with fuel as (

    select
        vehicle,
        extract(year from purchased_at) as year,
        sum(total_cost)                 as fuel_cost
    from {{ ref('fct_fuel_purchases') }}
    group by 1, 2

),

maintenance as (

    select
        vehicle,
        extract(year from serviced_at) as year,
        sum(total_cost)                as maintenance_cost
    from {{ ref('fct_maintenance') }}
    group by 1, 2

),

joined as (

    select
        coalesce(fuel.vehicle, maintenance.vehicle)     as vehicle,
        coalesce(fuel.year, maintenance.year)           as year,
        coalesce(fuel.fuel_cost, 0)                     as fuel_cost,
        coalesce(maintenance.maintenance_cost, 0)       as maintenance_cost
    from fuel
    full join maintenance
        on fuel.vehicle = maintenance.vehicle
        and fuel.year = maintenance.year

)

select
    vehicle,
    year,
    fuel_cost,
    maintenance_cost,
    fuel_cost + maintenance_cost as total_cost
from joined
