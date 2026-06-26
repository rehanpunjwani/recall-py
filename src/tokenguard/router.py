"""Routing policy: escalation keywords, rough token caps, and confidence scoring."""

from __future__ import annotations

LOW_CONFIDENCE_PHRASES = (
    "escalate",
    "don't know",
    "do not know",
    "insufficient",
    "not enough",
    "cannot answer",
    "can't answer",
    "i'm not sure",
    "i am not sure",
    "unable to",
    "no context",
)


def should_force_escalate(query: str, keywords: list[str]) -> tuple[bool, str | None]:
    q = query.lower()
    for kw in keywords:
        k = kw.strip().lower()
        if not k:
            continue
        if k in q:
            return True, kw
    return False, None


def draft_confidence(query: str, draft: str) -> float:
    q = query.strip().lower()
    d = draft.strip()

    if not d:
        return 0.0

    d_lower = d.lower()

    for phrase in LOW_CONFIDENCE_PHRASES:
        if phrase in d_lower:
            return max(0.0, 0.3 - (0.05 * d_lower.count(phrase)))

    query_len = len(q)
    draft_len = len(d)

    if draft_len < 10:
        return 0.1

    length_ratio = draft_len / max(query_len, 1)
    length_score = min(length_ratio / 3.0, 1.0)

    overlap = sum(1 for word in set(q.split()) if word in d_lower and len(word) > 2)
    relevance = overlap / max(len(set(q.split())), 1) if q.split() else 0.0

    score = 0.4 * length_score + 0.6 * relevance
    return min(max(score, 0.0), 1.0)


def rough_token_count(text: str) -> int:
    return max(1, len(text) // 4)
