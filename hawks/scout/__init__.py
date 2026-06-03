"""Scout-as-Code primitives for Hawks OS."""

from .contracts import JobLead, ScoutDecision
from .dedupe import dedupe_decisions
from .freshness import FreshnessSignal, evaluate_freshness
from .scorer import score_lead

__all__ = [
    "FreshnessSignal",
    "JobLead",
    "ScoutDecision",
    "dedupe_decisions",
    "evaluate_freshness",
    "score_lead",
]
