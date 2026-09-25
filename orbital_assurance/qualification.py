"""Runtime uncertainty, distribution-shift, and qualification calculations."""
from __future__ import annotations

import math
from typing import Any

from .core import features, require

# Training-domain reference values for the synthetic feature vector. They are
# explicit evaluation assumptions, not claims about spacecraft sensor physics.
REFERENCE_MEAN = (0.20, 0.33, 0.16, 0.35)
REFERENCE_SCALE = (0.80, 0.65, 0.75, 0.55)


def uncertainty(score: float) -> float:
    """Return 0 at confident extremes and 1 at the 0.5 decision boundary."""
    require(math.isfinite(score) and 0.0 <= score <= 1.0, "invalid score")
    return round(1.0 - abs(score - 0.5) * 2.0, 6)


def drift_score(observation: dict[str, Any]) -> float:
    vector = features(observation)
    z = [abs((x - mu) / scale) for x, mu, scale in zip(vector, REFERENCE_MEAN, REFERENCE_SCALE)]
    # RMS standardized displacement makes multi-feature shifts more meaningful
    # than a single unbounded coordinate while remaining deterministic.
    value = math.sqrt(sum(x * x for x in z) / len(z))
    return round(value, 6)


def qualification_state(*, score: float, drift: float, policy: dict[str, Any]) -> str:
    u = uncertainty(score)
    if drift >= policy["drift_fallback"]:
        return "fallback"
    if drift >= policy["drift_degrade"]:
        return "degraded"
    if u >= policy["uncertainty_review"]:
        return "review"
    if u >= policy["uncertainty_abstain"]:
        return "abstain"
    return "qualified"
