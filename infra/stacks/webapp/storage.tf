# Dedicated GCS bucket the webapp uses for asset blobs (images, PDFs, etc.).
# Namespaced so it never collides with the dbt platform or the tfstate bucket.
resource "google_storage_bucket" "assets" {
  name     = "${local.project_id}-agentic-webapp-assets"
  location = var.region

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }

  # Let non-prod buckets be torn down with the stack; protect prod.
  force_destroy = var.environment != "prod"

  depends_on = [google_project_service.run]
}

# The Cloud Run runtime SA reads/writes asset blobs.
resource "google_storage_bucket_iam_member" "runtime_object_admin" {
  bucket = google_storage_bucket.assets.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

# Signing V4 URLs on Cloud Run has no key file, so the runtime SA signs via the IAM
# SignBlob API — which requires Token Creator ON ITSELF. (See GCSStorageManager.)
resource "google_service_account_iam_member" "runtime_self_token_creator" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.runtime.email}"
}
