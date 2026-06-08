locals {
  # Project ID convention: dbt-<env>-jaffleshop — the SAME projects the dbt
  # platform uses. This stack coexists via a distinct state prefix + distinctly
  # named resources (see infra/README.md "Coexistence").
  project_id = "dbt-${var.environment}-jaffleshop"

  # IAP policy per environment:
  #   - dev  : OFF — public, IAP-free fast-iteration space (matches local containers).
  #   - test : OFF — public testing space for now (may flip to true later; needs its
  #            own OAuth consent screen in the test project when it does).
  #   - prod : ON  — IAP-gated; its OAuth consent screen is configured manually.
  # var.enable_iap (default null) overrides this for a single apply if ever needed.
  iap_default_by_env = {
    dev  = false
    test = false
    prod = true
  }
  iap_enabled = var.enable_iap != null ? var.enable_iap : local.iap_default_by_env[var.environment]
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
