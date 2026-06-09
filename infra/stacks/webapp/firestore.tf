# Firestore (Native) database backing durable ADK sessions + (by default) asset
# metadata and LLM bookkeeping. A NAMED database (not "(default)") so it can't collide
# with any existing Firestore/Datastore-mode database in the shared dbt-<env>-jaffleshop
# projects — named databases are independent and each carries its own location.
resource "google_firestore_database" "app" {
  name        = "agentic-webapp"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  # Protect prod (destroy abandons the DB from state rather than deleting it); let
  # non-prod be torn down with the stack.
  deletion_policy = var.environment == "prod" ? "ABANDON" : "DELETE"

  depends_on = [google_project_service.firestore]
}

# Runtime SA can read/write documents (Firestore authorises via Datastore IAM).
# Project-level and additive — does not affect the dbt platform.
resource "google_project_iam_member" "runtime_datastore_user" {
  project = local.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}
