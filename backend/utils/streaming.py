"""SSE helpers and node id → user-facing progress labels."""

NODE_PROGRESS_MAP: dict[str, str] = {
    "parse_input": "Parsing your trip request",
    "select_destination": "Choosing a destination",
    "dynamic_tool_selection": "Selecting data sources",
    "budget_analysis": "Checking the budget",
    "search_hotel": "Finding hotels",
    "compute_fairness": "Balancing costs fairly",
    "score_compatibility": "Scoring group fit",
    "assemble_output": "Building your itinerary",
}


def format_sse(data: str, event: str | None = None) -> str:
    """Format a single SSE frame."""
    lines = []
    if event:
        lines.append(f"event: {event}")
    lines.append(f"data: {data}")
    lines.append("")
    return "\n".join(lines)
