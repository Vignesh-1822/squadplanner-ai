"""Model pricing checked against published rates on 2026-09-05."""

from __future__ import annotations

from typing import Any

PRICING_USD_PER_MTOK = {
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00, "cache_read": 0.10},
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00, "cache_read": 0.10},
    "claude-sonnet-5": {"input": 2.00, "output": 10.00, "cache_read": 0.20},
}
PRICING_CHECKED_DATE = "2026-09-05"


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
) -> dict[str, Any]:
    rates = PRICING_USD_PER_MTOK.get(model)
    if rates is None:
        return {"cost_usd": None, "priced": False}
    uncached_input = max(input_tokens - cache_read_tokens, 0)
    cost = (
        uncached_input * rates["input"]
        + output_tokens * rates["output"]
        + cache_read_tokens * rates["cache_read"]
    ) / 1_000_000
    return {"cost_usd": round(cost, 8), "priced": True}
