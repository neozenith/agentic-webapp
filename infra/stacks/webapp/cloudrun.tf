# Dedicated least-privilege runtime identity for the service, distinct from the
# deployer SA. No project roles are granted by default — add only what the app
# actually needs (e.g. BigQuery read) as the app grows, so a compromised app can't
# act as the all-powerful deployer.
resource "google_service_account" "runtime" {
  account_id   = "${var.service_name}-run"
  display_name = "Cloud Run runtime SA for ${var.service_name} (${var.environment})"
  description  = "Identity the ${var.service_name} Cloud Run container runs as."
}

resource "google_cloud_run_v2_service" "app" {
  name     = var.service_name
  location = var.region

  # Guard prod against accidental `terraform destroy`; keep dev/test disposable.
  deletion_protection = var.environment == "prod"

  # IAP fronts the run.app URL directly, so traffic may arrive from all ingress
  # paths. (IAP authenticates every request before it reaches the container.)
  ingress = "INGRESS_TRAFFIC_ALL"

  # Direct IAP on Cloud Run (GA) — no load balancer, serverless NEG, managed SSL
  # cert, or custom domain required. This is the "bare" path to an IAP-protected,
  # scale-to-zero service. Gated by local.iap_enabled: when off, the service is made
  # publicly invocable below so the URL works without the OAuth consent screen
  # (which is a manual, org-only step for these no-org projects — see README.md).
  iap_enabled = local.iap_enabled

  template {
    service_account = google_service_account.runtime.email

    # Scale to zero: zero idle instances => zero idle cost. The trade-off is a
    # cold start on the first request after a quiet period.
    scaling {
      min_instance_count = 0
      max_instance_count = var.max_instances
    }

    containers {
      image = var.container_image

      # Surfaces the environment in the app UI/health payload (read as ENVIRONMENT
      # by the FastAPI Settings). K_REVISION is set by Cloud Run automatically.
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }

      # Wire the backend to its GCP implementations (see backend/ config.py).
      env {
        name  = "STORAGE_BACKEND"
        value = "gcs"
      }
      env {
        name  = "DATABASE_BACKEND"
        value = "bigquery"
      }
      env {
        name  = "GCP_PROJECT"
        value = local.project_id
      }
      env {
        name  = "ASSETS_BUCKET"
        value = google_storage_bucket.assets.name
      }
      env {
        name  = "BIGQUERY_DATASET"
        value = google_bigquery_dataset.app.dataset_id
      }
      env {
        name  = "ASSET_METADATA_TABLE"
        value = google_bigquery_table.asset_metadata.table_id
      }
      # SA used to sign V4 asset URLs via IAM (no key file on Cloud Run).
      env {
        name  = "SIGNING_SERVICE_ACCOUNT"
        value = google_service_account.runtime.email
      }
      # download_to_temp scratch dir — /app/tmp inside the container.
      env {
        name  = "TEMP_DIR"
        value = "tmp"
      }

      ports {
        container_port = var.container_port
      }

      resources {
        # cpu_idle = true means CPU is only allocated during request processing —
        # the correct setting for a scale-to-zero, request-driven web service.
        cpu_idle = true
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
      }
    }
  }

  depends_on = [google_project_service.run]
}

# When IAP is off, allow unauthenticated invocation so the run.app URL is usable
# in a browser. When IAP is on, access is governed by IAP (iap.tf) instead and
# this is not created.
resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  count    = local.iap_enabled ? 0 : 1
  name     = google_cloud_run_v2_service.app.name
  location = google_cloud_run_v2_service.app.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
