"""Module 6 graph wiring smoke tests."""

import pytest

from agent.graph import build_graph, initialize_graph


def test_graph_builds():
    """Confirm the graph compiles without errors."""
    graph = build_graph()
    compiled = graph.compile()
    assert compiled is not None


def test_graph_nodes():
    """Confirm all expected nodes are registered."""
    graph = build_graph()
    expected_nodes = {
        "parse_input",
        "extract_preference_constraints",
        "select_destination",
        "city_selection_hitl",
        "dynamic_tool_selection",
        "parallel_data_fetch",
        "budget_analysis",
        "search_hotel",
        "run_itinerary_node",
        "compute_fairness",
        "assemble_output",
    }
    assert expected_nodes.issubset(set(graph.nodes.keys()))


@pytest.mark.asyncio
async def test_graph_initializes():
    """Confirm graph compiles with MongoDB checkpointer."""
    await initialize_graph()
    from agent.graph import orchestrator_graph

    assert orchestrator_graph is not None
