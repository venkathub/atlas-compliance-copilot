"""Deterministic citation-correctness signal (report-only, vision: "answers with citations").

The *deterministic* component checked here: does every inline ``[n]`` marker in the answer resolve
to an actually-retrieved context chunk (index 1..N)? A marker pointing at a non-existent source is a
broken citation. The harder "does the cited chunk actually *support* the claim" judgment is an
LLM-judge concern layered on later; this gives a cheap, judge-free regression signal now.
"""

from __future__ import annotations

import re

_MARKER = re.compile(r"\[(\d+)\]")


def cited_markers(answer: str) -> list[int]:
    """Distinct citation marker numbers appearing in the answer text, in first-seen order."""
    seen: dict[int, None] = {}
    for m in _MARKER.findall(answer or ""):
        seen.setdefault(int(m), None)
    return list(seen)


def citation_resolution_rate(answer: str, num_contexts: int) -> float:
    """Fraction of distinct ``[n]`` markers that resolve to a real context index (1..N).

    Returns 1.0 when the answer has no citations (vacuously unbroken) — the gate treats this metric
    as report-only, and grounded refusals legitimately carry no markers.
    """
    markers = cited_markers(answer)
    if not markers:
        return 1.0
    resolved = sum(1 for m in markers if 1 <= m <= num_contexts)
    return resolved / len(markers)
