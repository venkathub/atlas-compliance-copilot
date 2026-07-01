"""Deterministic, GPU-free **format-validity** validator for the Atlas fine-tuned output format.

The FT target format (P6, ADR-0074) is one of:
  * a **cited answer** — non-empty answer text with >=1 `[doc:<id>]` marker; when the caller passes
    the context's `allowed_ids`, every marker must resolve to one (no fabricated doc ids); or
  * a **grounded refusal** — a plain statement that the answer is not in the provided sources, with
    NO fabricated citation.

Anything else (empty, an answer with no citation, a "refusal" that still cites) is invalid.

This validator is intentionally deterministic and judge-free so it runs in a **GPU-free CI gate** —
P6 commits the base-vs-FT format-validity numbers, and **P7 reuses this module verbatim** as part of
its model-promotion gate. Keep it dependency-light and stable.
"""

from __future__ import annotations

import re

_DOC_MARKER = re.compile(r"\[doc:([A-Za-z0-9_-]+)\]")

# Deterministic grounded-refusal cues. A refusal must explicitly disclaim answering from the
# provided sources/context (not merely contain a negation), to avoid counting normal answers that
# happen to say "no".
_REFUSAL_CUES = (
    re.compile(r"\b(can('?t|not)|could\s+not|cannot|unable\s+to|not\s+able\s+to)\s+answer", re.I),
    re.compile(r"\bdoes\s+not\s+contain\b", re.I),
    re.compile(r"\b(no|not\s+enough|insufficient)\s+(information|context|data)\b", re.I),
    re.compile(
        r"\bnot\s+(found|present|available)\s+in\s+the\s+(provided\s+)?(sources|context)\b", re.I
    ),
)
_GROUNDING_REF = re.compile(r"\b(provided\s+)?(sources?|context|documents?)\b", re.I)


def cited_doc_ids(output: str) -> list[str]:
    """Distinct `[doc:<id>]` ids in first-seen order."""
    seen: dict[str, None] = {}
    for m in _DOC_MARKER.findall(output or ""):
        seen.setdefault(m, None)
    return list(seen)


def is_grounded_refusal(output: str) -> bool:
    """True iff `output` reads as a grounded refusal (disclaims answering from the sources)."""
    text = (output or "").strip()
    if not text:
        return False
    has_cue = any(cue.search(text) for cue in _REFUSAL_CUES)
    return has_cue and bool(_GROUNDING_REF.search(text))


def _answer_text_without_markers(output: str) -> str:
    return _DOC_MARKER.sub("", output or "").strip()


def classify(output: str, allowed_ids: set[str] | None = None) -> str:
    """Classify `output` as ``"answer"`` | ``"refusal"`` | ``"invalid"``.

    A refusal that carries a `[doc:<id>]` marker is invalid (a refusal must not fabricate a
    citation). An answer is valid only if it has citation markers AND, when `allowed_ids` is given,
    every marker resolves to an allowed id.
    """
    text = (output or "").strip()
    if not text:
        return "invalid"

    ids = cited_doc_ids(text)
    refusal = is_grounded_refusal(text)

    if ids:
        if refusal:
            return "invalid"  # a refusal must not cite
        if allowed_ids is not None and not all(i in allowed_ids for i in ids):
            return "invalid"  # fabricated / unresolvable doc id
        if not _answer_text_without_markers(text):
            return "invalid"  # markers only, no actual answer text
        return "answer"

    return "refusal" if refusal else "invalid"


def score(output: str, allowed_ids: set[str] | None = None) -> bool:
    """True iff `output` conforms to the cited-answer or grounded-refusal schema."""
    return classify(output, allowed_ids) != "invalid"
