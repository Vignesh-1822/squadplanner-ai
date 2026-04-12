"""compute_fairness + score_compatibility — deterministic fairness math."""

from agent.state import TripState


def compute_fairness(state: TripState) -> dict:
    """Split costs and fairness metrics across travelers."""
    return {}


def score_compatibility(state: TripState) -> dict:
    """Compatibility scores between preference vectors (dot product, etc.)."""
    return {}
