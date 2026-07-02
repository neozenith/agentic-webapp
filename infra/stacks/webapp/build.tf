# The image builds are first-class nodes in the Terraform DAG: each `depends_on` the AR
# repo, and Cloud Run `depends_on` both (cloudrun.tf), so Terraform sequences
# repo -> build(s) (push images) -> Cloud Run itself, and a fresh project deploys in one
# apply.
#
# Each build is replaced only when its source hash changes — the AWS-Lambda
# zip-and-upload pattern (terraform_data + a source hash), applied to a container.
# Cloud Build does the Docker build REMOTELY, so the apply host needs gcloud + creds
# (CI has them via WIF; locally `tfs apply` uses your gcloud) but NO Docker daemon.
# Skipped (count = 0) when the matching var pins an explicit image — then Cloud Run uses
# the pin and no build runs (e.g. a rollback to a known tag).

# Backend image: FastAPI + the bundled React SPA + libs/core. Built from the repo root so
# backend/cloudbuild.yaml's Dockerfile sees frontend/ and libs/core in the build context.
resource "terraform_data" "image" {
  count            = var.container_image == "" ? 1 : 0
  triggers_replace = local.backend_src_hash

  provisioner "local-exec" {
    working_dir = "${path.module}/../../.." # repo root = Docker build context
    command     = "gcloud builds submit . --project ${local.project_id} --config backend/cloudbuild.yaml --substitutions=_IMAGE=${local.image_base}:${local.backend_src_hash}"
  }

  depends_on = [google_artifact_registry_repository.app]
}

# dbt sidecar image: dbt-core + the FastAPI health/run shim + libs/core. Same repo-root
# context, its own cloudbuild.yaml and source hash. NOTE: dbt/cloudbuild.yaml and
# dbt/Dockerfile are produced by the separate dbt/ subproject — this build wires to the
# agreed path; it will fail loudly at apply if those files are absent (by design).
resource "terraform_data" "dbt_image" {
  count            = var.dbt_image == "" ? 1 : 0
  triggers_replace = local.dbt_src_hash

  provisioner "local-exec" {
    working_dir = "${path.module}/../../.."
    command     = "gcloud builds submit . --project ${local.project_id} --config dbt/cloudbuild.yaml --substitutions=_IMAGE=${local.dbt_image_base}:${local.dbt_src_hash}"
  }

  depends_on = [google_artifact_registry_repository.app]
}

# Agent sidecar image: the ADK agent + libs/core. Same repo-root context, its own
# cloudbuild.yaml and its own source hash, so it rebuilds independently of the backend.
resource "terraform_data" "agent_image" {
  count            = var.agent_image == "" ? 1 : 0
  triggers_replace = local.agent_src_hash

  provisioner "local-exec" {
    working_dir = "${path.module}/../../.."
    command     = "gcloud builds submit . --project ${local.project_id} --config agent/cloudbuild.yaml --substitutions=_IMAGE=${local.agent_image_base}:${local.agent_src_hash}"
  }

  depends_on = [google_artifact_registry_repository.app]
}
