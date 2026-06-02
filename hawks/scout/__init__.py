"""Scout-as-Code primitives for Hawks OS."""

from .contracts import JobLead, ScoutDecision
from .dedupe import dedupe_decisions
from .scorer import score_lead

__all__ = ["JobLead", "ScoutDecision", "dedupe_decisions", "score_lead"]
