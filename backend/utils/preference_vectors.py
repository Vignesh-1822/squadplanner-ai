"""5D preference vectors, dot-product compatibility scoring."""

from typing import Sequence


def dot_score(a: Sequence[float], b: Sequence[float]) -> float:
    """Dot product between two equal-length vectors."""
    return sum(x * y for x, y in zip(a, b, strict=True))
