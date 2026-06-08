# Partial backend configuration for the GCS backend.
# https://developer.hashicorp.com/terraform/language/backend#partial-configuration
#
# Populated at init time, never edited directly:
#   terraform -chdir=stacks/webapp init -backend-config=./backends/<env>.config -reconfigure
#
# State lives in the SAME per-project tfstate bucket as the dbt platform, isolated
# by the prefix terraform/state/webapp — that prefix is what prevents collision.
terraform {
  required_version = ">= 1.10.0"

  backend "gcs" {
    bucket = ""
    prefix = ""
  }
}
