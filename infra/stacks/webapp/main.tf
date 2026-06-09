locals {
  # Project ID convention: dbt-<env>-jaffleshop — the SAME projects the dbt
  # platform uses. This stack coexists via a distinct state prefix + distinctly
  # named resources (see infra/README.md "Coexistence").
  project_id = "dbt-${var.environment}-jaffleshop"

  # IAP is enabled when a custom OAuth client is supplied — no-org projects require
  # one (ADR-0002), so its presence IS the on/off switch. In CI the client comes
  # from a per-environment GitHub secret (TF_VAR_iap_oauth_client_id); an env with
  # no such secret runs public. dev is public by design (no sensitive data, ADR-0003);
  # prod has the secret so IAP is on; test flips on the moment its secret is added.
  # var.enable_iap (default null) can still force a value for a one-off apply.
  iap_enabled = var.enable_iap != null ? var.enable_iap : (var.iap_oauth_client_id != "")
}

data "google_project" "this" {}

# APIs this stack needs. Enabling is idempotent and additive, so this is safe
# alongside the dbt_platform stack in the same project. disable_on_destroy=false
# means `terraform destroy` of this stack won't yank an API the dbt platform (or
# anything else) might also rely on.
resource "google_project_service" "run" {
  service            = "run.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "iap" {
  service            = "iap.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "artifactregistry" {
  service            = "artifactregistry.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "bigquery" {
  service            = "bigquery.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "aiplatform" {
  service            = "aiplatform.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "firestore" {
  service            = "firestore.googleapis.com"
  disable_on_destroy = false
}
