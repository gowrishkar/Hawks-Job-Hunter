from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Literal

FreshnessLabel = Literal["fresh", "recent", "stale", "unknown"]


@dataclass(frozen=True)
class FreshnessSignal:
    """Inspectable posting-age signal for scout ranking and review.

    Freshness is not allowed to rescue a weak role, but it helps Hawks explain
    whether a high-fit lead is timely enough for daily public scouting.
    """

    label: FreshnessLabel
    days_old: int | None
    reason: str

    @property
    def is_actionable(self) -> bool:
        return self.label in {"fresh", "recent"}


def evaluate_freshness(raw_date: str, *, today: dt.date | None = None) -> FreshnessSignal:
    """Classify a job posting date into a deterministic freshness signal.

    Accepted inputs intentionally match common job-board text:
    - ISO dates: ``2026-06-03``
    - month dates: ``Jun 3, 2026`` or ``June 3 2026``
    - relative ages: ``2 days ago`` or ``today``
    """

    text = " ".join((raw_date or "").strip().split()).lower()
    today = today or dt.date.today()
    if not text or text == "unknown":
        return FreshnessSignal("unknown", None, "posting date unavailable")

    relative = _parse_relative_age(text)
    if relative is not None:
        return _label(relative, f"posted {relative} day(s) ago")

    parsed = _parse_absolute_date(text)
    if parsed is None:
        return FreshnessSignal("unknown", None, f"unparsed posting date: {raw_date}")

    days_old = max(0, (today - parsed).days)
    return _label(days_old, f"posted on {parsed.isoformat()}")


def _parse_relative_age(text: str) -> int | None:
    if text in {"today", "just posted", "new"}:
        return 0
    if text == "yesterday":
        return 1
    match = re.search(r"\b(\d+)\s+days?\s+ago\b", text)
    if match:
        return int(match.group(1))
    return None


def _parse_absolute_date(text: str) -> dt.date | None:
    for fmt in ("%Y-%m-%d", "%b %d, %Y", "%b %d %Y", "%B %d, %Y", "%B %d %Y"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _label(days_old: int, reason: str) -> FreshnessSignal:
    if days_old <= 7:
        label: FreshnessLabel = "fresh"
    elif days_old <= 30:
        label = "recent"
    else:
        label = "stale"
    return FreshnessSignal(label, days_old, reason)
