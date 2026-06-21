-- Typed fuel-receipt rows unpacked from extractions.fields_json.
-- One row per fuel-receipt extraction.
with source as (

    select *
    from {{ source('raw', 'extractions') }}
    where doc_type = 'fuel_receipt'

)

select
    extraction_id                                                as purchase_id,
    cast(json_value(fields_json, '$.purchased_at') as date)      as purchased_at,
    json_value(fields_json, '$.vehicle')                         as vehicle,
    json_value(fields_json, '$.station')                         as station,
    json_value(fields_json, '$.fuel_type')                       as fuel_type,
    cast(json_value(fields_json, '$.litres') as float64)         as litres,
    cast(json_value(fields_json, '$.price_per_litre') as float64) as price_per_litre,
    cast(json_value(fields_json, '$.total_cost') as float64)     as total_cost,
    cast(json_value(fields_json, '$.odometer_km') as int64)      as odometer_km
from source
