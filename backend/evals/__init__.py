"""Offline and live evaluation support for SquadPlanner.

Importing the evaluation package must work in a clean CI process. Production
settings remain strict; placeholder values are installed only when importing
``config`` fails because the required environment is absent.
"""

from __future__ import annotations

import os

try:
    import config as _config  # noqa: F401
except Exception as exc:
    # Avoid masking programming/import errors. Pydantic's settings failure is
    # the only expected reason for this compatibility path.
    if exc.__class__.__name__ != "ValidationError":
        raise
    for _name, _value in {
        "MONGODB_URI": "mongodb://127.0.0.1:27017/squadplanner-evals",
        "JWT_SECRET": "evals-only-placeholder",
        "ANTHROPIC_API_KEY": "",
        "SERPAPI_KEY": "",
        "GOOGLE_PLACES_API_KEY": "",
        "GOOGLE_ROUTES_API_KEY": "",
    }.items():
        os.environ.setdefault(_name, _value)
    import config as _config  # noqa: F401,E402
