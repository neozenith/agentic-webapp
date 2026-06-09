"""mask_user_id: deterministic, normalised, opaque (no mocks — pure function)."""

import uuid

from agentic_webapp.identity import APP_NAMESPACE, mask_user_id


def test_deterministic_same_email_same_id():
    assert mask_user_id("alice@example.com") == mask_user_id("alice@example.com")


def test_normalises_case_and_whitespace():
    assert mask_user_id("Alice@Example.com") == mask_user_id("  alice@example.com  ")


def test_different_emails_differ():
    assert mask_user_id("alice@example.com") != mask_user_id("bob@example.com")


def test_is_a_uuid_not_the_email():
    masked = mask_user_id("alice@example.com")
    assert uuid.UUID(masked)  # parses as a UUID
    assert "alice" not in masked
    assert masked == str(uuid.uuid5(APP_NAMESPACE, "alice@example.com"))
