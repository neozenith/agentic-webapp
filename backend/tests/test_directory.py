"""The pseudonymous-id directory: /api/directory exposes id -> {email, name}, and
/api/admin/users is enriched with email + name when the id is known. Real managers, no mocks."""

from datetime import datetime, timezone

from agentic_core.database import InMemoryDatabaseManager, LlmUsageManager
from agentic_core.models import LlmUsageRecord

from agentic_webapp.api import deps
from agentic_webapp.identity import mask_user_id

NINA_EMAIL = "nina.analyst@example.com"
NINA_ID = mask_user_id(NINA_EMAIL)


def test_directory_maps_persona_ids_to_name_and_email(client):
    body = client.get("/api/directory").json()
    assert body[NINA_ID] == {"email": NINA_EMAIL, "name": "Nina — Analyst"}


def _usage(user_id: str) -> LlmUsageRecord:
    return LlmUsageRecord(
        request_id="r1",
        app_name="assistant",
        user_id=user_id,
        session_id="s1",
        model_id="gemini-2.5-flash-lite",
        prompt_tokens=10,
        output_tokens=5,
        total_tokens=15,
        est_cost_usd=0.0001,
        timestamp=datetime.now(timezone.utc),
    )


def test_admin_users_enriched_with_email_and_name(admin_client, run):
    manager = LlmUsageManager(InMemoryDatabaseManager(), table="llm_usage")
    run(manager.record(_usage(NINA_ID)))  # known persona id
    run(manager.record(_usage("unknown-pseudonymous-id")))  # not in the directory
    admin_client.app.dependency_overrides[deps.get_llm_usage_manager] = lambda: manager

    rows = {r["user_id"]: r for r in admin_client.get("/api/admin/users").json()}
    assert rows[NINA_ID]["email"] == NINA_EMAIL
    assert rows[NINA_ID]["name"] == "Nina — Analyst"
    assert rows["unknown-pseudonymous-id"]["email"] is None
    assert rows["unknown-pseudonymous-id"]["name"] is None
