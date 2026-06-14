"""Golden eval dataset: (question, ground_truth, expected_source_docs) tuples.

Layer-1 tuples are seeded from authoritative FinanceBench rows; Layer-2 tuples are authored
against the Northwind/AML overlay. Loading validates every tuple — crucially that each
``expected_source_docs`` id resolves to a real corpus doc (no dangling references).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from atlas_evals.datasets.corpus import CLEARANCES, DATA_DIR, known_doc_ids

DEFAULT_PATH = DATA_DIR / "golden.jsonl"


@dataclass(frozen=True)
class GoldenTuple:
    id: str
    layer: int
    clearance: str
    question: str
    ground_truth: str
    expected_source_docs: list[str] = field(default_factory=list)
    source: str = ""

    def validate(self) -> None:
        if not self.id:
            raise ValueError("golden tuple missing id")
        if self.layer not in (1, 2):
            raise ValueError(f"{self.id}: layer must be 1 or 2, got {self.layer}")
        if self.clearance not in CLEARANCES:
            raise ValueError(f"{self.id}: invalid clearance '{self.clearance}'")
        if not self.question.strip():
            raise ValueError(f"{self.id}: empty question")
        if not self.ground_truth.strip():
            raise ValueError(f"{self.id}: empty ground_truth")
        if not self.expected_source_docs:
            raise ValueError(f"{self.id}: expected_source_docs must be non-empty")
        valid = known_doc_ids()
        for doc in self.expected_source_docs:
            if doc not in valid:
                raise ValueError(f"{self.id}: expected_source_doc '{doc}' is not a real corpus doc")


def load_golden(path: Path = DEFAULT_PATH) -> list[GoldenTuple]:
    """Parse + validate the golden JSONL. Raises ValueError on any invalid/dangling tuple."""
    tuples: list[GoldenTuple] = []
    seen: set[str] = set()
    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"{path.name}:{lineno}: invalid JSON: {e}") from None
        t = GoldenTuple(
            id=obj.get("id", ""),
            layer=obj.get("layer", 0),
            clearance=obj.get("clearance", ""),
            question=obj.get("question", ""),
            ground_truth=obj.get("ground_truth", ""),
            expected_source_docs=list(obj.get("expected_source_docs", [])),
            source=obj.get("source", ""),
        )
        t.validate()
        if t.id in seen:
            raise ValueError(f"{path.name}:{lineno}: duplicate id '{t.id}'")
        seen.add(t.id)
        tuples.append(t)
    return tuples
