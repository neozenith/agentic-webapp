# Agent sidecar IAM. The sidecar runs as the SHARED service runtime SA (Cloud Run
# allows one service account per service), so the agent's Vertex access is granted
# to the runtime SA. A dedicated agent SA would require the dual-service model.
resource "google_project_iam_member" "runtime_vertex_user" {
  project = local.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.runtime.email}"

  depends_on = [google_project_service.aiplatform]
}
