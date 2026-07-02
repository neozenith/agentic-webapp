# Dedicated BigQuery dataset + tables the webapp interfaces against. Namespaced
# (dataset "agentic_webapp") so it sits beside the dbt datasets without colliding.
resource "google_bigquery_dataset" "app" {
  dataset_id  = "agentic_webapp"
  location    = var.region
  description = "agentic-webapp application data (${var.environment})."

  # Allow non-prod datasets (and their tables) to be torn down with the stack.
  delete_contents_on_destroy = var.environment != "prod"

  depends_on = [google_project_service.bigquery]
}

# The first table: the asset-metadata catalogue managed via AssetMetadataManager.
# Schema is intentionally simple + portable; nested tags live in metadata_json.
resource "google_bigquery_table" "asset_metadata" {
  dataset_id          = google_bigquery_dataset.app.dataset_id
  table_id            = "asset_metadata"
  deletion_protection = var.environment == "prod"

  schema = jsonencode([
    { name = "asset_id", type = "STRING", mode = "REQUIRED" },
    { name = "storage_key", type = "STRING", mode = "REQUIRED" },
    { name = "filename", type = "STRING", mode = "NULLABLE" },
    { name = "content_type", type = "STRING", mode = "NULLABLE" },
    { name = "size_bytes", type = "INTEGER", mode = "NULLABLE" },
    { name = "created_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "updated_at", type = "TIMESTAMP", mode = "NULLABLE" },
    # RBAC: pseudonymous owner, the folder it lives in (inherits the folder's sharing), and
    # JSON arrays of the user_ids / group_ids the asset is directly shared with.
    { name = "owner_id", type = "STRING", mode = "NULLABLE" },
    { name = "folder_id", type = "STRING", mode = "NULLABLE" },
    { name = "shared_user_ids_json", type = "STRING", mode = "NULLABLE" },
    { name = "shared_group_ids_json", type = "STRING", mode = "NULLABLE" },
    { name = "metadata_json", type = "STRING", mode = "NULLABLE" },
  ])
}

# Real named folders for the Asset Manager (managed via FolderManager). Folders nest via
# parent_id and carry their own sharing; contained assets + sub-folders inherit that access.
resource "google_bigquery_table" "folders" {
  dataset_id          = google_bigquery_dataset.app.dataset_id
  table_id            = "folders"
  deletion_protection = var.environment == "prod"

  schema = jsonencode([
    { name = "folder_id", type = "STRING", mode = "REQUIRED" },
    { name = "name", type = "STRING", mode = "NULLABLE" },
    { name = "parent_id", type = "STRING", mode = "NULLABLE" },
    { name = "owner_id", type = "STRING", mode = "NULLABLE" },
    { name = "shared_user_ids_json", type = "STRING", mode = "NULLABLE" },
    { name = "shared_group_ids_json", type = "STRING", mode = "NULLABLE" },
    { name = "created_at", type = "TIMESTAMP", mode = "NULLABLE" },
  ])
}

# Custom user groups (admin-managed, via GroupManager). Assets/folders can be shared with a
# group; a member then inherits that access. member_ids are pseudonymous user_ids.
resource "google_bigquery_table" "groups" {
  dataset_id          = google_bigquery_dataset.app.dataset_id
  table_id            = "groups"
  deletion_protection = var.environment == "prod"

  schema = jsonencode([
    { name = "group_id", type = "STRING", mode = "REQUIRED" },
    { name = "name", type = "STRING", mode = "NULLABLE" },
    { name = "member_ids_json", type = "STRING", mode = "NULLABLE" },
    { name = "created_at", type = "TIMESTAMP", mode = "NULLABLE" },
  ])
}

# Bookkeeping inventory: one itemised row per LLM call (written by the agent's ADK
# callback via LlmUsageManager; read by the backend admin panel).
resource "google_bigquery_table" "llm_usage" {
  dataset_id          = google_bigquery_dataset.app.dataset_id
  table_id            = "llm_usage"
  deletion_protection = var.environment == "prod"

  schema = jsonencode([
    { name = "request_id", type = "STRING", mode = "REQUIRED" },
    { name = "app_name", type = "STRING", mode = "NULLABLE" },
    { name = "user_id", type = "STRING", mode = "NULLABLE" },
    { name = "session_id", type = "STRING", mode = "NULLABLE" },
    { name = "model_id", type = "STRING", mode = "NULLABLE" },
    { name = "prompt_tokens", type = "INTEGER", mode = "NULLABLE" },
    { name = "output_tokens", type = "INTEGER", mode = "NULLABLE" },
    { name = "total_tokens", type = "INTEGER", mode = "NULLABLE" },
    { name = "est_cost_usd", type = "FLOAT", mode = "NULLABLE" },
    { name = "timestamp", type = "TIMESTAMP", mode = "NULLABLE" },
  ])
}

# Extraction analytics: one row per structured extraction pulled from an asset by an
# agent tool (written via AnalyticsManager — the BigQuery-backed analytics space, separate
# from the Firestore operational stores). The common envelope is typed columns; the
# variable per-doc-type payload rides in fields_json, so new extraction tool types need
# no schema change — query them with JSON_VALUE(fields_json, '$.field').
resource "google_bigquery_table" "extractions" {
  dataset_id          = google_bigquery_dataset.app.dataset_id
  table_id            = "extractions"
  deletion_protection = var.environment == "prod"

  schema = jsonencode([
    { name = "extraction_id", type = "STRING", mode = "REQUIRED" },
    { name = "asset_id", type = "STRING", mode = "NULLABLE" },
    { name = "doc_type", type = "STRING", mode = "NULLABLE" },
    { name = "user_id", type = "STRING", mode = "NULLABLE" },
    { name = "session_id", type = "STRING", mode = "NULLABLE" },
    { name = "fields_json", type = "STRING", mode = "NULLABLE" },
    { name = "model_id", type = "STRING", mode = "NULLABLE" },
    { name = "created_at", type = "TIMESTAMP", mode = "NULLABLE" },
  ])
}

# App-managed semantic-layer store: one row per semantic model the webapp defines
# (entities/metrics the dbt MARTS are described against). definition_json carries a JSON
# array of entities so the shape can evolve without a schema change.
resource "google_bigquery_table" "semantic_models" {
  dataset_id          = google_bigquery_dataset.app.dataset_id
  table_id            = "semantic_models"
  deletion_protection = var.environment == "prod"

  schema = jsonencode([
    { name = "model_id", type = "STRING", mode = "REQUIRED" },
    { name = "name", type = "STRING", mode = "NULLABLE" },
    { name = "description", type = "STRING", mode = "NULLABLE" },
    { name = "definition_json", type = "STRING", mode = "NULLABLE" },
    { name = "created_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "updated_at", type = "TIMESTAMP", mode = "NULLABLE" },
  ])
}

# App-managed dashboard store: one row per dashboard the webapp defines. charts_json is a
# JSON array of chart specs; semantic_model_id (nullable) links a dashboard to the
# semantic model it reads. These plus semantic_models are the app's semantic-layer +
# dashboard stores.
#
# NOTE: the dbt MARTS (fct_fuel_purchases, fct_maintenance, agg_vehicle_costs_yearly) are
# deliberately NOT declared here — dbt creates them at runtime via the sidecar container
# (see cloudrun.tf). The runtime SA's dataset-scoped dataEditor + project-scoped jobUser
# grants below already cover any table dbt materialises in this dataset, including these.
resource "google_bigquery_table" "dashboards" {
  dataset_id          = google_bigquery_dataset.app.dataset_id
  table_id            = "dashboards"
  deletion_protection = var.environment == "prod"

  schema = jsonencode([
    { name = "dashboard_id", type = "STRING", mode = "REQUIRED" },
    { name = "name", type = "STRING", mode = "NULLABLE" },
    { name = "description", type = "STRING", mode = "NULLABLE" },
    { name = "semantic_model_id", type = "STRING", mode = "NULLABLE" },
    { name = "charts_json", type = "STRING", mode = "NULLABLE" },
    { name = "created_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "updated_at", type = "TIMESTAMP", mode = "NULLABLE" },
  ])
}

# Raw source tables for the Consulting Engagement domain (the second worked example). dbt
# staging/marts read these (source `consulting_raw`) and materialise dim_engagements +
# fct_time_entries/financials/deliverables/invoices, which the semantic layer binds to.
# Columns mirror the dbt mart outputs so staging is a thin cast/passthrough.
resource "google_bigquery_table" "raw_engagements" {
  dataset_id          = google_bigquery_dataset.app.dataset_id
  table_id            = "raw_engagements"
  deletion_protection = var.environment == "prod"
  schema = jsonencode([
    { name = "engagement_id", type = "STRING", mode = "REQUIRED" },
    { name = "name", type = "STRING", mode = "NULLABLE" },
    { name = "client", type = "STRING", mode = "NULLABLE" },
    { name = "service_line", type = "STRING", mode = "NULLABLE" },
    { name = "lead_consultant", type = "STRING", mode = "NULLABLE" },
    { name = "phase", type = "STRING", mode = "NULLABLE" },
    { name = "status", type = "STRING", mode = "NULLABLE" },
    { name = "rag_overall", type = "STRING", mode = "NULLABLE" },
    { name = "start_date", type = "DATE", mode = "NULLABLE" },
    { name = "end_date", type = "DATE", mode = "NULLABLE" },
    { name = "contract_value", type = "NUMERIC", mode = "NULLABLE" },
    { name = "revenue_to_date", type = "NUMERIC", mode = "NULLABLE" },
    { name = "margin_pct", type = "FLOAT", mode = "NULLABLE" },
  ])
}

resource "google_bigquery_table" "raw_time_entries" {
  dataset_id          = google_bigquery_dataset.app.dataset_id
  table_id            = "raw_time_entries"
  deletion_protection = var.environment == "prod"
  schema = jsonencode([
    { name = "time_entry_id", type = "STRING", mode = "REQUIRED" },
    { name = "entry_date", type = "DATE", mode = "NULLABLE" },
    { name = "consultant", type = "STRING", mode = "NULLABLE" },
    { name = "engagement", type = "STRING", mode = "NULLABLE" },
    { name = "role", type = "STRING", mode = "NULLABLE" },
    { name = "hours", type = "FLOAT", mode = "NULLABLE" },
    { name = "billable", type = "BOOLEAN", mode = "NULLABLE" },
    { name = "cost", type = "NUMERIC", mode = "NULLABLE" },
  ])
}

resource "google_bigquery_table" "raw_financials" {
  dataset_id          = google_bigquery_dataset.app.dataset_id
  table_id            = "raw_financials"
  deletion_protection = var.environment == "prod"
  schema = jsonencode([
    { name = "financial_id", type = "STRING", mode = "REQUIRED" },
    { name = "period", type = "DATE", mode = "NULLABLE" },
    { name = "engagement", type = "STRING", mode = "NULLABLE" },
    { name = "client", type = "STRING", mode = "NULLABLE" },
    { name = "revenue", type = "NUMERIC", mode = "NULLABLE" },
    { name = "cost", type = "NUMERIC", mode = "NULLABLE" },
    { name = "margin", type = "NUMERIC", mode = "NULLABLE" },
  ])
}

resource "google_bigquery_table" "raw_deliverables" {
  dataset_id          = google_bigquery_dataset.app.dataset_id
  table_id            = "raw_deliverables"
  deletion_protection = var.environment == "prod"
  schema = jsonencode([
    { name = "deliverable_id", type = "STRING", mode = "REQUIRED" },
    { name = "engagement", type = "STRING", mode = "NULLABLE" },
    { name = "name", type = "STRING", mode = "NULLABLE" },
    { name = "status", type = "STRING", mode = "NULLABLE" },
    { name = "rag", type = "STRING", mode = "NULLABLE" },
    { name = "due_date", type = "DATE", mode = "NULLABLE" },
    { name = "progress", type = "INTEGER", mode = "NULLABLE" },
  ])
}

resource "google_bigquery_table" "raw_invoices" {
  dataset_id          = google_bigquery_dataset.app.dataset_id
  table_id            = "raw_invoices"
  deletion_protection = var.environment == "prod"
  schema = jsonencode([
    { name = "invoice_id", type = "STRING", mode = "REQUIRED" },
    { name = "engagement", type = "STRING", mode = "NULLABLE" },
    { name = "client", type = "STRING", mode = "NULLABLE" },
    { name = "issued_at", type = "DATE", mode = "NULLABLE" },
    { name = "due_date", type = "DATE", mode = "NULLABLE" },
    { name = "amount", type = "NUMERIC", mode = "NULLABLE" },
    { name = "status", type = "STRING", mode = "NULLABLE" },
  ])
}

# Elementary observability dataset — dbt's Elementary package materialises its metadata
# tables (dbt_invocations, dbt_run_results, …) here via on-run-end hooks. Pre-created by
# Terraform (NOT by dbt) so the runtime SA only needs dataEditor, not dataset-create.
# The dbt sidecar reads it for the run-history gantt/overview (ELEMENTARY_DATASET env).
resource "google_bigquery_dataset" "elementary" {
  dataset_id                 = "${google_bigquery_dataset.app.dataset_id}_elementary"
  location                   = var.region
  description                = "Elementary dbt observability metadata (${var.environment})."
  delete_contents_on_destroy = var.environment != "prod"
  depends_on                 = [google_project_service.bigquery]
}

resource "google_bigquery_dataset_iam_member" "runtime_elementary_data_editor" {
  dataset_id = google_bigquery_dataset.elementary.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.runtime.email}"
}

# Runtime SA can read/write rows in this dataset (dataset-scoped: covers the app-managed
# tables above AND any MART the dbt sidecar materialises at runtime — no per-table IAM is
# needed)...
resource "google_bigquery_dataset_iam_member" "runtime_data_editor" {
  dataset_id = google_bigquery_dataset.app.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.runtime.email}"
}

# ...and run query jobs (a project-level capability, additive — does not affect dbt).
resource "google_project_iam_member" "runtime_job_user" {
  project = local.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}
