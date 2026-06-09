output "project_id" {
  description = "The GCP project this stack deployed into."
  value       = data.google_project.this.project_id
}

output "project_number" {
  value = data.google_project.this.number
}

output "service_name" {
  value = google_cloud_run_v2_service.app.name
}

output "service_uri" {
  description = "The run.app URL. Reaching it requires passing IAP as an authorized member (var.iap_members)."
  value       = google_cloud_run_v2_service.app.uri
}

output "runtime_service_account" {
  description = "Identity the container runs as — grant it any data-plane roles the app needs."
  value       = google_service_account.runtime.email
}

output "iap_enabled" {
  description = "Whether the service is protected by IAP."
  value       = local.iap_enabled
}

output "iap_service_agent" {
  description = "The IAP service agent that holds run.invoker on the service (null when IAP is off)."
  value       = local.iap_enabled ? google_project_service_identity.iap[0].email : null
}

output "iap_members" {
  description = "Principals allowed through IAP (only meaningful when iap_enabled = true)."
  value       = local.iap_enabled ? var.iap_members : []
}

output "image_base" {
  description = "Fully-qualified Artifact Registry image base — append :<tag> when pushing."
  value       = local.image_base
}

output "artifact_registry_repo" {
  description = "Artifact Registry repository resource name."
  value       = google_artifact_registry_repository.app.name
}

output "assets_bucket" {
  description = "GCS bucket for webapp asset blobs."
  value       = google_storage_bucket.assets.name
}

output "bigquery_dataset" {
  description = "BigQuery dataset the webapp interfaces against."
  value       = google_bigquery_dataset.app.dataset_id
}

output "firestore_database" {
  description = "Firestore (named) database backing durable ADK sessions + app data (default tabular store)."
  value       = google_firestore_database.app.name
}
