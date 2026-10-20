"""Usage, pricing and persistence-shape tests."""

from uuid import uuid4

from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from evals.telemetry.pricing import calculate_cost
from evals.telemetry.usage import UsageTracker, merge_telemetry, telemetry_inc_fields
from api.trips import get_trip_telemetry


def test_pricing_separates_cached_input():
    priced = calculate_cost("claude-haiku-4-5", 1000, 100, 400)
    assert priced["priced"] is True
    assert priced["cost_usd"] == 0.00114
    assert calculate_cost("unpriced-model", 1, 1)["cost_usd"] is None


def test_usage_tracker_attributes_tokens_to_node():
    tracker = UsageTracker()
    run_id = uuid4()
    tracker.on_chat_model_start({}, [], run_id=run_id, metadata={"langgraph_node": "build_itinerary"})
    message = AIMessage(
        content="ok",
        usage_metadata={
            "input_tokens": 100,
            "output_tokens": 20,
            "total_tokens": 120,
            "input_token_details": {"cache_read": 10},
        },
        response_metadata={"model": "claude-haiku-4-5"},
    )
    tracker.on_llm_end(
        LLMResult(generations=[[ChatGeneration(message=message)]]),
        run_id=run_id,
    )
    node = tracker.snapshot()["nodes"]["build_itinerary"]
    assert node["input_tokens"] == 100
    assert node["output_tokens"] == 20
    assert node["cache_read_tokens"] == 10
    assert node["llm_calls"] == 1


def test_telemetry_merges_hitl_and_refinement_segments():
    first = {"nodes": {"a": {"input_tokens": 2}}, "totals": {"input_tokens": 2}}
    second = {"nodes": {"a": {"input_tokens": 3}, "b": {"input_tokens": 1}}, "totals": {"input_tokens": 4}}
    merged = merge_telemetry(first, second)
    assert merged["nodes"]["a"]["input_tokens"] == 5
    assert merged["nodes"]["b"]["input_tokens"] == 1
    assert merged["totals"]["input_tokens"] == 6


def test_telemetry_flattens_to_atomic_increments():
    fields = telemetry_inc_fields(
        {
            "nodes": {"build.itinerary": {"input_tokens": 3, "cost_usd": 0.01}},
            "totals": {"input_tokens": 3, "cost_usd": 0.01},
        }
    )
    assert fields["telemetry.nodes.build_itinerary.input_tokens"] == 3
    assert fields["telemetry.totals.cost_usd"] == 0.01


def test_member_scoped_handler_returns_persisted_telemetry():
    import asyncio

    telemetry = {"nodes": {}, "totals": {"input_tokens": 4}}
    result = asyncio.run(
        get_trip_telemetry("trip-1", trip={"trip_id": "trip-1", "telemetry": telemetry})
    )
    assert result == {"trip_id": "trip-1", "telemetry": telemetry}
