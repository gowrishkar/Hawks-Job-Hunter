"""Scout-as-Code primitives for Hawks OS."""

from .contracts import JobLead, ScoutDecision
from .scorer import score_lead

__all__ = ["JobLead", "ScoutDecision", "score_lead"]
