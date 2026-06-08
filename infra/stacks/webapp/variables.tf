variable "environment" {
  description = "Deployment environment — one of dev / test / prod."
  type        = string
  nullable    = false
  validation {
    condition     = contains(["dev", "test", "prod"], var.environment)
    error_message = "environment must be one of 'dev', 'test', 'prod'."
  }
}

variable "region" {
  description = "Default region for regional resources (Cloud Run location)."
  type        = string
  default     = "australia-southeast1"
}

variable "service_name" {
  description = "Cloud Run service name."
  type        = string
  default     = "agentic-webapp"
}

variable "repository_id" {
  description = "Artifact Registry repository ID for the app image."
  type        = string
  default     = "agentic-webapp"
}

variable "agent_image" {
  description = "Container image for the ADK agent sidecar. Built by CI; defaults to the hello sample so plans work pre-build."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "agent_model" {
  description = "Gemini model the agent uses by default (cheapest by default)."
  type        = string
  default     = "gemini-2.5-flash-lite"
}

variable "vertex_location" {
  description = "Vertex AI model-serving region (independent of the app's GCS/BQ region)."
  type        = string
  default     = "us-central1"
}

variable "container_image" {
  description = <<-EOT
    Container image to deploy. Defaults to Google's hello sample so the stack is
    deployable BEFORE the app's own image exists. The application CD pipeline
    overrides this (e.g. -var container_image=...) once it pushes a real image to
    Artifact Registry.
  EOT
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "container_port" {
  description = "Port the container listens on."
  type        = number
  default     = 8080
}

variable "cpu" {
  description = "CPU limit per instance."
  type        = string
  default     = "1"
}

variable "memory" {
  description = "Memory limit per instance."
  type        = string
  default     = "512Mi"
}

variable "max_instances" {
  description = "Maximum number of Cloud Run instances. The minimum is pinned to 0 (scale to zero) in cloudrun.tf."
  type        = number
  default     = 2
}

variable "enable_iap" {
  description = <<-EOT
    Optional per-apply OVERRIDE for IAP protection. Leave null (the default) and IAP
    turns on automatically iff a custom OAuth client is supplied (var.iap_oauth_client_id
    is non-empty) — see ADR-0002. So an environment is public until its OAuth client
    secret is provided (in CI, a per-environment GitHub secret). Set true/false to
    force a value for one apply regardless.
  EOT
  type        = bool
  default     = null
}

variable "iap_oauth_client_id" {
  description = <<-EOT
    Custom OAuth 2.0 client ID for IAP. Its presence is the IAP on/off switch
    (see var.enable_iap / ADR-0002): non-empty ⇒ IAP enabled, empty ⇒ public.
    REQUIRED for IAP in projects with NO GCP organization — IAP's Google-managed
    client only works inside an org, so without a custom client IAP returns HTTP
    502 "Empty OAuth client ID/secret". Created manually in the Console (APIs &
    Services → Credentials → Create OAuth client ID → Web application); in CI it is
    supplied per-environment via a GitHub secret.
  EOT
  type        = string
  default     = ""
}

variable "iap_oauth_client_secret" {
  description = "Secret paired with iap_oauth_client_id. Sensitive — supply via a gitignored <env>.tfvars or TF_VAR_iap_oauth_client_secret, never commit it."
  type        = string
  default     = ""
  sensitive   = true
}

variable "iap_members" {
  description = <<-EOT
    Principals allowed THROUGH IAP (granted roles/iap.httpsResourceAccessor).
    Locked to a single Google identity by default. Each entry is a full IAM member
    string, e.g. "user:someone@example.com" or "group:team@example.com".
  EOT
  type        = list(string)
  default     = ["user:joshpeak05@gmail.com"]

  validation {
    condition     = length(var.iap_members) > 0
    error_message = "iap_members must list at least one principal, otherwise nobody can reach the service."
  }
}
