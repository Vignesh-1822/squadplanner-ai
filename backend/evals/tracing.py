"""Optional LangSmith callbacks with email redaction at the client boundary."""

from __future__ import annotations

import copy
import json
import os
import re
from typing import Any

from config import settings
from evals.modes import EvalMode, llm_mode, tool_mode
from evals.telemetry.usage import UsageTracker


def redact_member_emails(payload: dict, emails: list[str]) -> dict:
    """Replace exact known member emails without altering unrelated @ text."""
    serialised = json.dumps(copy.deepcopy(payload), default=str)
    for email in sorted({email for email in emails if email}, key=len, reverse=True):
        serialised = re.sub(re.escape(email), "[REDACTED_EMAIL]", serialised, flags=re.IGNORECASE)
    return json.loads(serialised)


def member_emails_from_trip(trip: dict[str, Any] | None) -> list[str]:
    trip = trip or {}
    emails = {
        str(member.get("email", "")).strip()
        for member in trip.get("invited_members", [])
        if isinstance(member, dict)
    }
    emails.update(str(email).strip() for email in trip.get("invited_emails", []))
    emails.add(str(trip.get("created_by", "")).strip())
    return sorted(email for email in emails if email)


def build_callbacks(
    trip_id: str,
    member_emails: list[str] | None = None,
    usage_tracker: UsageTracker | None = None,
) -> tuple[list[Any], UsageTracker]:
    tracker = usage_tracker or UsageTracker()
    callbacks: list[Any] = [tracker]
    if os.getenv("PYTEST_CURRENT_TEST"):
        return callbacks, tracker
    if tool_mode() is EvalMode.REPLAY or llm_mode() is EvalMode.REPLAY:
        return callbacks, tracker
    if settings.langchain_tracing_v2.lower() != "true" or not settings.langchain_api_key:
        return callbacks, tracker

    try:
        from langchain_core.tracers.langchain import LangChainTracer
        from langsmith import Client

        emails = list(member_emails or [])
        client = Client(
            api_key=settings.langchain_api_key,
            anonymizer=lambda payload: redact_member_emails(payload, emails),
        )
        callbacks.append(
            LangChainTracer(
                project_name=settings.langchain_project,
                client=client,
                tags=[f"trip_id:{trip_id}"],
                metadata={"trip_id": trip_id},
            )
        )
    except Exception:
        # Observability must never become a boot or trip-generation dependency.
        pass
    return callbacks, tracker
