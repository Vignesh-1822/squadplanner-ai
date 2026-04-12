"""Proximity-based clustering for activities / stops."""

from typing import Any


def cluster_by_proximity(points: list[dict[str, Any]], radius_km: float) -> list[list[dict[str, Any]]]:
    """Group points within radius_km of each other (simple placeholder)."""
    return [points] if points else []
