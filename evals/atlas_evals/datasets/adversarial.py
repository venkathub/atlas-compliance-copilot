"""Adversarial / red-team dataset (binary, 0-tolerance gate in Task 7).

Cases REFERENCE the P1 fixtures (`poisoned/expectations.json`, `negative_access.json`) rather
than duplicating their expectation strings, so P1 and P2 cannot drift. Loading resolves those
references into concrete `must_not_contain` strings / forbidden docs+clearances.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from atlas_evals.datasets.corpus import (
    CLEARANCES,
    DATA_DIR,
    resolve_fixture_list,
    resolve_negative_access,
)

DEFAULT_PATH = DATA_DIR / "adversarial.jsonl"
CLASSES = ("injection", "jailbreak", "access-bypass", "system-prompt-leak")


@dataclass(frozen=True)
class AdversarialCase:
    id: str
    cls: str
    clearance: str
    query: str
    must_not_cite_above: str
    # Resolved from fixture references at load time:
    must_not_contain: list[str] = field(default_factory=list)
    forbidden_doc_ids: list[str] = field(default_factory=list)
    forbidden_clearances: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.id:
            raise ValueError("adversarial case missing id")
        if self.cls not in CLASSES:
            raise ValueError(f"{self.id}: invalid class '{self.cls}'")
        if self.clearance not in CLEARANCES:
            raise ValueError(f"{self.id}: invalid clearance '{self.clearance}'")
        if self.must_not_cite_above not in CLEARANCES:
            raise ValueError(f"{self.id}: invalid must_not_cite_above '{self.must_not_cite_above}'")
        if not self.query.strip():
            raise ValueError(f"{self.id}: empty query")
        # Every case must carry at least one concrete expectation after ref resolution.
        if not (self.must_not_contain or self.forbidden_doc_ids):
            raise ValueError(
                f"{self.id}: no resolvable expectation (must_not_contain/forbidden docs)"
            )


def load_adversarial(path: Path = DEFAULT_PATH) -> list[AdversarialCase]:
    """Parse + validate the adversarial JSONL, resolving fixture references."""
    cases: list[AdversarialCase] = []
    seen: set[str] = set()
    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"{path.name}:{lineno}: invalid JSON: {e}") from None

        must_not_contain: list[str] = []
        forbidden_docs: list[str] = []
        forbidden_clearances: list[str] = []
        if ref := obj.get("must_not_contain_ref"):
            must_not_contain = resolve_fixture_list(ref)
        if ref := obj.get("negative_access_ref"):
            na = resolve_negative_access(ref)
            forbidden_docs = list(na.get("forbiddenDocIds", []))
            forbidden_clearances = list(na.get("forbiddenClearances", []))

        case = AdversarialCase(
            id=obj.get("id", ""),
            cls=obj.get("class", ""),
            clearance=obj.get("clearance", ""),
            query=obj.get("query", ""),
            must_not_cite_above=obj.get("must_not_cite_above", ""),
            must_not_contain=must_not_contain,
            forbidden_doc_ids=forbidden_docs,
            forbidden_clearances=forbidden_clearances,
        )
        case.validate()
        if case.id in seen:
            raise ValueError(f"{path.name}:{lineno}: duplicate id '{case.id}'")
        seen.add(case.id)
        cases.append(case)
    return cases
