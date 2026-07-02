-- Typed invoice rows. One row per invoice issued for an engagement.
with source as (

    select * from {{ source('consulting_raw', 'raw_invoices') }}

)

select
    invoice_id,
    engagement,
    client,
    cast(issued_at as date) as issued_at,
    cast(due_date as date)  as due_date,
    cast(amount as numeric) as amount,
    status
from source
