from __future__ import annotations

from collections.abc import Iterable

from .contracts import ScoutDecision

SOURCE_TRUST_RANK = {
    "official": 4,
    "ats": 3,
    "reputed_board": 2,
    "unknown": 1,
}


def dedupe_decisions(decisions: Iterable[ScoutDecision]) -> tuple[ScoutDecision, ...]:
    """Return one best decision per company/title/location key.

    Hawks often sees the same role from an official page, ATS page, and job
    board mirror. Keep the strongest evidence trail instead of letting mirrors
    inflate the shortlist. Selection is deterministic: higher score wins,
    then stronger source trust wins, then the earlier input item wins.
    """

    best_by_key: dict[str, tuple[int, ScoutDecision]] = {}
    for index, decision in enumerate(decisions):
        key = decision.lead.normalized_key()
        incumbent = best_by_key.get(key)
        if incumbent is None or _is_better(decision, incumbent[1]):
            best_by_key[key] = (index, decision)

    return tuple(
        decision
        for _, decision in sorted(best_by_key.values(), key=lambda item: item[0])
    )


def _is_better(candidate: ScoutDecision, incumbent: ScoutDecision) -> bool:
    if candidate.score != incumbent.score:
        return candidate.score > incumbent.score
    return SOURCE_TRUST_RANK[candidate.lead.source] > SOURCE_TRUST_RANK[incumbent.lead.source]
