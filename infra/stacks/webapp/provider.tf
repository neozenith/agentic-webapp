terraform {
  required_providers {
    # Pinned to >= 7.21 (GA) for `iap_enabled` on google_cloud_run_v2_service —
    # the GA field landed in provider 7.21.0 (Feb 2026). This is intentionally a
    # newer major than the dbt_platform stack's `~> 6.0`; stacks lock providers
    # independently, so the bump is isolated to this stack.
    google = {
      source  = "hashicorp/google"
      version = "~> 7.21"
    }
    # google-beta is required for google_project_service_identity (used to
    # force-create the IAP service agent so we can grant it run.invoker).
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 7.21"
    }
  }
}

provider "google" {
  project = local.project_id
  region  = var.region
}

provider "google-beta" {
  project = local.project_id
  region  = var.region
}
