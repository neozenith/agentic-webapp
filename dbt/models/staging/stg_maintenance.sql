-- Typed vehicle-maintenance rows unpacked from extractions.fields_json.
-- One row per maintenance extraction.
with source as (

    select *
    from {{ source('raw', 'extractions') }}
    where doc_type = 'maintenance'

)

select
    extraction_id                                            as maintenance_id,
    cast(json_value(fields_json, '$.serviced_at') as date)   as serviced_at,
    json_value(fields_json, '$.vehicle')                     as vehicle,
    json_value(fields_json, '$.category')                    as category,
    json_value(fields_json, '$.vendor')                      as vendor,
    cast(json_value(fields_json, '$.total_cost') as float64) as total_cost
from source
