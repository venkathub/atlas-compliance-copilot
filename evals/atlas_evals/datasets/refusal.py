"""Labeled refusal subset: cases the FT model must refuse (out-of-context / unanswerable /
out-of-clearance) vs answerable controls it must NOT over-refuse.

The refusal-correctness metric (P6, reused by P7) scores model outputs against these labels via
`atlas_evals.metrics.refusal.score`. Loading validates each case so the committed set can't drift
(empty fields, bad clearance). `RefusalCase` is the same type the scorer uses — one definition.
"""

from __future__ import annotations

import json
from pathlib import Path

from atlas_evals.datasets.corpus import CLEARANCES, DATA_DIR
from atlas_evals.metrics.refusal import RefusalCase

DEFAULT_PATH = DATA_DIR / "refusal.jsonl"


def _validate(case: RefusalCase) -> None:
    if not case.id:
        raise ValueError("refusal case missing id")
    if not case.question.strip():
        raise ValueError(f"{case.id}: empty question")
    if not isinstance(case.should_refuse, bool):
        raise ValueError(f"{case.id}: should_refuse must be a bool")
    if case.clearance is not None and case.clearance not in CLEARANCES:
        raise ValueError(f"{case.id}: invalid clearance '{case.clearance}'")


def load_refusal(path: Path = DEFAULT_PATH) -> list[RefusalCase]:
    """Parse + validate the labeled refusal JSONL. Raises ValueError on invalid/duplicate cases."""
    cases: list[RefusalCase] = []
    seen: set[str] = set()
    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"{path.name}:{lineno}: invalid JSON: {e}") from None
        case = RefusalCase.from_dict(obj)
        _validate(case)
        if case.id in seen:
            raise ValueError(f"{path.name}:{lineno}: duplicate case id '{case.id}'")
        seen.add(case.id)
        cases.append(case)
    if not cases:
        raise ValueError(f"{path}: no refusal cases")
    return cases
