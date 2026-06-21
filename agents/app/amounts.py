"""Deterministic currency-amount extraction (used by the assess node, ADR-0049).

Pulls `$12,500(.00)` style amounts out of retrieved text so the breach decision is a pure
function of the retrieved citations — not an LLM judgement (ASI01 resistance).
"""

from __future__ import annotations

import re

_CURRENCY = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)")


def extract_amounts(text: str | None) -> list[float]:
    """Return all USD amounts found in {text} as floats (commas stripped)."""
    if not text:
        return []
    return [float(m.replace(",", "")) for m in _CURRENCY.findall(text)]
