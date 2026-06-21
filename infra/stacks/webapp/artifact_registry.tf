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
  # Fully-qualified image bases (append :<tag> when pushing). Both images live in the
  # one repo; they differ only by the trailing image name.
  #   backend: <region>-docker.pkg.dev/<project>/<repo>/<service>
  #   agent:   <region>-docker.pkg.dev/<project>/<repo>/agent
  image_base       = "${var.region}-docker.pkg.dev/${local.project_id}/${google_artifact_registry_repository.app.repository_id}/${var.service_name}"
  agent_image_base = "${var.region}-docker.pkg.dev/${local.project_id}/${google_artifact_registry_repository.app.repository_id}/agent"
  dbt_image_base   = "${var.region}-docker.pkg.dev/${local.project_id}/${google_artifact_registry_repository.app.repository_id}/dbt"

  # Content-addressed tags: a hash of each image's REAL Docker-context inputs, so an
  # image rebuilds (build.tf) and Cloud Run gets a new revision only on a real source
  # change — the container analogue of AWS Lambda's source_code_hash. The hashed dirs
  # mirror each Dockerfile's COPY set:
  #   backend image = backend/ + frontend/ (SPA bundled in) + libs/ (shared core)
  #   agent image   = agent/ + libs/ (shared core)
  #   dbt image     = dbt/ (the dbt project + FastAPI sidecar) + libs/ (shared core)
  # Generated dirs (node_modules, dist, .venv, __pycache__, .terraform) are excluded so
  # they never perturb the hash.
  backend_src_hash = substr(sha1(join("", [
    for f in sort(flatten([
      for d in ["backend", "frontend", "libs"] : [
        for p in fileset("${path.module}/../../../${d}", "**") :
        filesha1("${path.module}/../../../${d}/${p}")
        if length(regexall("(^|/)(node_modules|dist|[.]venv|__pycache__|[.]terraform)(/|$)", p)) == 0
      ]
    ])) : f
  ])), 0, 12)

  agent_src_hash = substr(sha1(join("", [
    for f in sort(flatten([
      for d in ["agent", "libs"] : [
        for p in fileset("${path.module}/../../../${d}", "**") :
        filesha1("${path.module}/../../../${d}/${p}")
        if length(regexall("(^|/)(node_modules|dist|[.]venv|__pycache__|[.]terraform)(/|$)", p)) == 0
      ]
    ])) : f
  ])), 0, 12)

  dbt_src_hash = substr(sha1(join("", [
    for f in sort(flatten([
      for d in ["dbt", "libs"] : [
        for p in fileset("${path.module}/../../../${d}", "**") :
        filesha1("${path.module}/../../../${d}/${p}")
        if length(regexall("(^|/)(node_modules|dist|[.]venv|__pycache__|[.]terraform)(/|$)", p)) == 0
      ]
    ])) : f
  ])), 0, 12)

  # The images Cloud Run runs: the freshly-built source-hash image by default; the
  # matching var.* can pin a specific tag instead (a rollback), which also skips that
  # image's build (see build.tf count).
  app_image   = var.container_image != "" ? var.container_image : "${local.image_base}:${local.backend_src_hash}"
  agent_image = var.agent_image != "" ? var.agent_image : "${local.agent_image_base}:${local.agent_src_hash}"
  dbt_image   = var.dbt_image != "" ? var.dbt_image : "${local.dbt_image_base}:${local.dbt_src_hash}"
}
