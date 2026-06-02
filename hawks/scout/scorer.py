from __future__ import annotations

from .contracts import JobLead, ScoutDecision

TARGET_SIGNALS = {
    "ai architect": 22,
    "solutions architect": 22,
    "ai product": 20,
    "agent": 18,
    "automation": 14,
    "workflow": 12,
    "mcp": 12,
    "llm": 10,
    "strategy": 10,
}

REJECT_SIGNALS = {
    "sales intern": 40,
    "junior": 25,
    "local only": 25,
    "door to door": 40,
}

SOURCE_BONUS = {
    "official": 18,
    "ats": 14,
    "reputed_board": 9,
    "unknown": -15,
}


def score_lead(lead: JobLead) -> ScoutDecision:
    """Score a lead with explicit reasons and risks.

    This is deliberately deterministic for the public repo. LLM-assisted
    scoring can sit behind the same contract later, but the trust model starts
    with rules that are easy to test and explain.
    """

    text = " ".join([lead.title, lead.company, lead.location, lead.summary, " ".join(lead.tags)]).lower()
    score = 35 + SOURCE_BONUS[lead.source]
    reasons: list[str] = [f"source trust: {lead.source}"]
    risks: list[str] = []

    for signal, points in TARGET_SIGNALS.items():
        if signal in text:
            score += points
            reasons.append(f"target signal: {signal}")

    for signal, penalty in REJECT_SIGNALS.items():
        if signal in text:
            score -= penalty
            risks.append(f"reject signal: {signal}")

    if "remote" in text or "india" in text or "global" in text:
        score += 8
        reasons.append("location fit: remote/global/India")

    if not lead.url.startswith(("https://", "http://")):
        score -= 30
        risks.append("missing valid URL")

    score = max(0, min(100, score))
    if score >= 75 and not any(r.startswith("reject signal") for r in risks):
        decision = "shortlist"
    elif score >= 55:
        decision = "watch"
    else:
        decision = "reject"

    return ScoutDecision(
        lead=lead,
        decision=decision,
        score=score,
        reasons=tuple(reasons),
        risks=tuple(risks),
    )
