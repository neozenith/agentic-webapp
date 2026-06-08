# Docker repository the app image is pushed to. Namespaced (var.repository_id,
# default "agentic-webapp") so it never collides with anything in the shared
# project. The runtime SA is granted read so Cloud Run can pull.
resource "google_artifact_registry_repository" "app" {
  location      = var.region
  repository_id = var.repository_id
  format        = "DOCKER"
  description   = "Container images for the ${var.service_name} Cloud Run service."

  depends_on = [google_project_service.artifactregistry]
}

# Cloud Run pulls the image as the runtime SA — give it read on the repo.
resource "google_artifact_registry_repository_iam_member" "runtime_reader" {
  location   = google_artifact_registry_repository.app.location
  repository = google_artifact_registry_repository.app.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.runtime.email}"
}

locals {
  # Convenience: the fully-qualified image base. Append :<tag> when pushing.
  #   <region>-docker.pkg.dev/<project>/<repo>/<service>
  image_base = "${var.region}-docker.pkg.dev/${local.project_id}/${google_artifact_registry_repository.app.repository_id}/${var.service_name}"
}
