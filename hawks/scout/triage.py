from __future__ import annotations

from dataclasses import dataclass

from .contracts import ScoutDecision
from .freshness import FreshnessSignal

FRESHNESS_BONUS = {
    "fresh": 8,
    "recent": 4,
    "stale": -12,
    "unknown": -6,
}


@dataclass(frozen=True)
class TriageRecommendation:
    """Human-review priority for a scored lead.

    Scout scoring answers whether a role fits Gowrishkar's target profile.
    Triage answers what should be reviewed first today by combining fit,
    evidence quality, and posting freshness without hiding the underlying
    score or risks.
    """

    decision: ScoutDecision
    freshness: FreshnessSignal
    priority_score: int
    badges: tuple[str, ...]

    @property
    def is_actionable(self) -> bool:
        return self.decision.decision != "reject" and self.freshness.is_actionable


def triage_decision(
    decision: ScoutDecision,
    freshness: FreshnessSignal,
) -> TriageRecommendation:
    """Create an inspectable review-priority recommendation.

    The priority score is clamped to 0..100. Freshness can nudge a strong fit
    ahead of another, but it cannot turn a rejected or weak-fit role into an
    application recommendation.
    """

    priority_score = max(
        0,
        min(100, decision.score + FRESHNESS_BONUS[freshness.label]),
    )
    badges = _badges(decision, freshness)
    return TriageRecommendation(
        decision=decision,
        freshness=freshness,
        priority_score=priority_score,
        badges=badges,
    )


def _badges(decision: ScoutDecision, freshness: FreshnessSignal) -> tuple[str, ...]:
    badges: list[str] = [f"fit:{decision.decision}", f"freshness:{freshness.label}"]
    if decision.lead.source in {"official", "ats"}:
        badges.append(f"trusted-source:{decision.lead.source}")
    if freshness.is_actionable and decision.decision == "shortlist":
        badges.append("review-now")
    if decision.risks:
        badges.append("risk-review")
    return tuple(badges)
