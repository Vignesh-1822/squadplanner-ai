"""Tracing-boundary PII tests."""

import json

from evals.tracing import member_emails_from_trip, redact_member_emails


def test_known_member_email_never_reaches_serialised_trace():
    payload = {
        "input": {
            "members": [{"email": "member@example.com", "name": "Member"}],
            "notes": "Relaxed mornings",
        }
    }
    redacted = redact_member_emails(payload, ["member@example.com"])
    assert "@" not in json.dumps(redacted)
    assert redacted["input"]["members"][0]["email"] == "[REDACTED_EMAIL]"


def test_unrelated_at_sign_in_note_survives():
    payload = {"notes": "Meet @ the lobby", "email": "member@example.com"}
    redacted = redact_member_emails(payload, ["member@example.com"])
    assert redacted["notes"] == "Meet @ the lobby"


def test_redaction_is_case_insensitive_and_includes_legacy_members():
    emails = member_emails_from_trip(
        {
            "created_by": "leader@example.com",
            "invited_emails": ["guest@example.com"],
            "invited_members": [{"email": "member@example.com"}],
        }
    )
    payload = {"identity": "LEADER@EXAMPLE.COM", "guest": "guest@example.com"}
    redacted = redact_member_emails(payload, emails)
    assert redacted == {
        "identity": "[REDACTED_EMAIL]",
        "guest": "[REDACTED_EMAIL]",
    }
