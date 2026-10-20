"""Mode parsing shared by tool and LLM replay."""

from __future__ import annotations

import os
from enum import Enum


class EvalMode(str, Enum):
    OFF = "off"
    REPLAY = "replay"
    RECORD = "record"


def _mode(name: str) -> EvalMode:
    raw_value = os.getenv(name)
    if raw_value is None:
        try:
            from config import settings

            raw_value = str(getattr(settings, name.lower()))
        except (ImportError, AttributeError):
            raw_value = "off"
    raw = raw_value.strip().lower()
    try:
        return EvalMode(raw)
    except ValueError as exc:
        allowed = ", ".join(mode.value for mode in EvalMode)
        raise ValueError(f"{name} must be one of: {allowed}; got {raw!r}") from exc


def tool_mode() -> EvalMode:
    return _mode("EVALS_TOOL_MODE")


def llm_mode() -> EvalMode:
    return _mode("EVALS_LLM_MODE")
