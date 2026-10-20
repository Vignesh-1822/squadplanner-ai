"""Stable JSON fixture storage for replayed external calls."""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Iterator

_FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
_MISSES: ContextVar[list[str] | None] = ContextVar("evals_replay_misses", default=None)


class ReplayMiss(LookupError):
    """Raised when replay mode cannot find the exact recorded request."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def request_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class ReplayStore:
    def __init__(self, namespace: str, root: Path | None = None) -> None:
        self.namespace = namespace
        self.root = (root or _FIXTURE_ROOT) / namespace

    def path_for(self, operation: str, request: Any) -> Path:
        return self.root / operation / f"{request_hash(request)}.json"

    def load(self, operation: str, request: Any) -> Any:
        path = self.path_for(operation, request)
        if not path.is_file():
            message = (
                f"No replay fixture for {self.namespace}.{operation} "
                f"(key={path.stem}, path={path})"
            )
            misses = _MISSES.get()
            if misses is not None:
                misses.append(message)
            raise ReplayMiss(message)
        envelope = json.loads(path.read_text(encoding="utf-8"))
        expected = canonical_json(request)
        if canonical_json(envelope.get("request")) != expected:
            raise ReplayMiss(f"Replay request mismatch in {path}")
        return envelope["response"]

    def load_if_present(self, operation: str, request: Any) -> Any | None:
        if not self.path_for(operation, request).is_file():
            return None
        return self.load(operation, request)

    def contains(self, operation: str, request: Any) -> bool:
        return self.path_for(operation, request).is_file()

    def save(self, operation: str, request: Any, response: Any) -> Path:
        path = self.path_for(operation, request)
        path.parent.mkdir(parents=True, exist_ok=True)
        envelope = {
            "operation": operation,
            "request": request,
            "response": response,
            "request_sha256": path.stem,
        }
        path.write_text(json.dumps(envelope, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        return path


@contextmanager
def capture_replay_misses() -> Iterator[list[str]]:
    misses: list[str] = []
    token = _MISSES.set(misses)
    try:
        yield misses
    finally:
        _MISSES.reset(token)
