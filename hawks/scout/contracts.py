from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Decision = Literal["shortlist", "watch", "reject"]
SourceTrust = Literal["official", "ats", "reputed_board", "unknown"]


@dataclass(frozen=True)
class JobLead:
    """Validated job lead used by Scout-as-Code.

    The contract is intentionally small and inspectable. Hawks should reject
    or downgrade leads that cannot produce enough evidence for a human to
    trust the recommendation.
    """

    title: str
    company: str
    url: str
    location: str
    source: SourceTrust
    summary: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    def normalized_key(self) -> str:
        return "|".join(
            part.strip().lower()
            for part in (self.company, self.title, self.location)
            if part.strip()
        )


@dataclass(frozen=True)
class ScoutDecision:
    lead: JobLead
    decision: Decision
    score: int
    reasons: tuple[str, ...]
    risks: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict:
        return {
            "decision": self.decision,
            "score": self.score,
            "reasons": list(self.reasons),
            "risks": list(self.risks),
            "lead": {
                "title": self.lead.title,
                "company": self.lead.company,
                "url": self.lead.url,
                "location": self.lead.location,
                "source": self.lead.source,
                "summary": self.lead.summary,
                "tags": list(self.lead.tags),
            },
        }
