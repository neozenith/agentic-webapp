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

    # --- Ingress container: FastAPI backend. Serves the SPA + APIs and proxies to
    # the agent sidecar on localhost (single public ingress). ---
    containers {
      name  = "backend"
      image = local.app_image # built in-DAG by terraform_data.image (build.tf), or var.container_image pin

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
      # Firestore is the default tabular store; BIGQUERY_DATASET is kept below so an
      # env can revert by flipping this back to "bigquery" (no code/infra change).
      env {
        name  = "DATABASE_BACKEND"
        value = "firestore"
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
        name  = "FIRESTORE_DATABASE"
        value = google_firestore_database.app.name
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
      # The agent sidecar listens on localhost:8081 in the same instance.
      env {
        name  = "AGENT_BASE_URL"
        value = "http://localhost:8081"
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

      # Boot the agent sidecar first so the proxy is ready on cold start.
      depends_on = ["agent"]
    }

    # --- Sidecar container: the ADK agent (keyless Vertex via the shared runtime SA;
    # Cloud Run uses ONE service account per service, so a dedicated agent SA needs
    # the dual-service model). No ports block: localhost-only, reached via the proxy. ---
    containers {
      name  = "agent"
      image = local.agent_image # built in-DAG by terraform_data.agent_image (build.tf), or var.agent_image pin

      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "True"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = local.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.vertex_location
      }
      env {
        name  = "AGENT_MODEL"
        value = var.agent_model
      }
      # Durable ADK sessions in Firestore (services.py maps firestore:// to the custom
      # FirestoreSessionService; DB id from FIRESTORE_DATABASE). Unset => in-memory.
      env {
        name  = "SESSION_SERVICE_URI"
        value = "firestore://"
      }
      # Bookkeeping target (LlmUsageManager writes here via agentic-core). Firestore by
      # default; BIGQUERY_DATASET kept so an env can revert via DATABASE_BACKEND.
      env {
        name  = "DATABASE_BACKEND"
        value = "firestore"
      }
      env {
        name  = "GCP_PROJECT"
        value = local.project_id
      }
      env {
        name  = "FIRESTORE_DATABASE"
        value = google_firestore_database.app.name
      }
      env {
        name  = "BIGQUERY_DATASET"
        value = google_bigquery_dataset.app.dataset_id
      }
      env {
        name  = "LLM_USAGE_TABLE"
        value = google_bigquery_table.llm_usage.table_id
      }

      resources {
        cpu_idle = true
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }

      # Required because the backend container depends_on this one: Cloud Run needs a
      # startup probe to know the agent is ready before starting the backend. adk web
      # can take a while to import, so allow a generous window.
      startup_probe {
        tcp_socket {
          port = 8081
        }
        period_seconds    = 5
        timeout_seconds   = 3
        failure_threshold = 30
      }
    }
  }

  # Both image builds must push BEFORE the service is created/updated, so the source-hash
  # tags Cloud Run references already exist in Artifact Registry. terraform_data.*[0] is
  # safe: when a var pins an image the build is count=0, but then var.* != "" so app_image
  # / agent_image resolve to the pin and the (empty) depends_on list is simply skipped.
  depends_on = [
    google_project_service.run,
    google_project_service.aiplatform,
    terraform_data.image,
    terraform_data.agent_image,
  ]
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
