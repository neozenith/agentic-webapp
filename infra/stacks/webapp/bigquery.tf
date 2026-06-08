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
    { name = "metadata_json", type = "STRING", mode = "NULLABLE" },
  ])
}

# Runtime SA can read/write rows in this dataset...
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
