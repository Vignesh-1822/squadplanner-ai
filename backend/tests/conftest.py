"""Suite-wide settings: the deterministic tests need no real secrets.

config.py refuses to import without MONGODB_URI and JWT_SECRET. Placeholders set here let the suite
run with no backend/.env and no Infisical login, and they override real values when present, so a
test can never quietly reach the real cluster — every test swaps Mongo for fakes anyway.
"""

import os

# The live integration test is the one place real credentials are wanted; leave the environment
# alone for it so `infisical run --env=dev -- pytest tests/test_integration.py` still works.
if os.getenv("RUN_LIVE_INTEGRATION", "").lower() != "true":
    os.environ["MONGODB_URI"] = "mongodb://127.0.0.1:27017/squadplanner_test"
    os.environ["JWT_SECRET"] = "test-only-secret-not-used-outside-the-suite"
