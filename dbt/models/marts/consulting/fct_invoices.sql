-- Invoices fact table. One row per invoice issued for an engagement.
with invoices as (

    select * from {{ ref('stg_consulting__invoices') }}

)

select
    invoice_id,
    engagement,
    client,
    issued_at,
    due_date,
    amount,
    status
from invoices
