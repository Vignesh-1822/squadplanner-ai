"""Make the offline evaluation gate hermetic before application imports."""

from __future__ import annotations

import os
import socket

import pytest

# These assignments are intentionally unconditional: a developer's loaded
# credentials must never turn an offline pytest run into a paid live run.
os.environ.update(
    {
        "MONGODB_URI": "mongodb://127.0.0.1:27017/squadplanner-evals",
        "JWT_SECRET": "evals-only-placeholder",
        "ANTHROPIC_API_KEY": "",
        "SERPAPI_KEY": "",
        "GOOGLE_PLACES_API_KEY": "",
        "GOOGLE_ROUTES_API_KEY": "",
        "LANGCHAIN_API_KEY": "",
        "LANGCHAIN_TRACING_V2": "false",
        "LANGSMITH_TRACING": "false",
        "EVALS_TOOL_MODE": "replay",
        "EVALS_LLM_MODE": "replay",
    }
)


@pytest.fixture(autouse=True)
def block_external_network(monkeypatch):
    """Fail immediately if replay accidentally falls through to a socket."""

    def denied(*args, **kwargs):
        raise AssertionError("Offline eval attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
