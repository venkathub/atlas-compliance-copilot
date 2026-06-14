"""Resolve dataset references against the *real* committed corpus + P1 fixtures.

The golden/adversarial sets must never reference a doc id or fixture that does not exist
(P1↔P2 drift). This module is the single source of truth for "what is a valid doc id" and
for reading the P1 red-team fixtures the adversarial set references (rather than duplicating
their expectation strings).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

# evals/atlas_evals/datasets/corpus.py -> parents[3] == repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
CORPUS_DIR = REPO_ROOT / "rag-engine" / "src" / "main" / "resources" / "corpus"
FIXTURES_DIR = REPO_ROOT / "rag-engine" / "src" / "test" / "resources" / "fixtures"
DATA_DIR = REPO_ROOT / "evals" / "data"

CLEARANCES = ("public", "analyst", "compliance", "restricted")


@lru_cache(maxsize=1)
def known_doc_ids() -> frozenset[str]:
    """All valid corpus doc ids: Layer-1 FinanceBench ids + Layer-2 ``l2-*`` doc stems."""
    ids: set[str] = set()
    manifest = json.loads((CORPUS_DIR / "layer1" / "manifest.json").read_text())
    for doc in manifest["documents"]:
        ids.add(doc["financebench_id"])
    for md in (CORPUS_DIR / "layer2").glob("*.md"):
        ids.add(md.stem)
    return frozenset(ids)


@lru_cache(maxsize=1)
def poisoned_expectations() -> dict:
    """The P1 poisoned-doc expectations (`answerMustNotContain`, `injectionPhrases`, …)."""
    return json.loads((FIXTURES_DIR / "poisoned" / "expectations.json").read_text())


@lru_cache(maxsize=1)
def negative_access_cases() -> dict[str, dict]:
    """The P1 negative-access cases keyed by id (forbidden docs/clearances per case)."""
    root = json.loads((FIXTURES_DIR / "negative_access.json").read_text())
    return {c["id"]: c for c in root["cases"]}


def resolve_fixture_list(ref: str) -> list[str]:
    """Resolve a ``file#json_key`` fixture reference to its list value.

    Supported: ``poisoned/expectations.json#answerMustNotContain`` (and other top-level keys).
    """
    file_part, _, key = ref.partition("#")
    if file_part == "poisoned/expectations.json":
        value = poisoned_expectations().get(key)
    else:
        raise ValueError(f"unsupported fixture reference: {ref}")
    if not isinstance(value, list):
        raise ValueError(f"fixture ref {ref} did not resolve to a list")
    return list(value)


def resolve_negative_access(ref: str) -> dict:
    """Resolve a ``negative_access.json#<case-id>`` reference to that case dict."""
    file_part, _, case_id = ref.partition("#")
    if file_part != "negative_access.json":
        raise ValueError(f"unsupported negative-access reference: {ref}")
    case = negative_access_cases().get(case_id)
    if case is None:
        raise ValueError(f"negative-access case not found: {case_id}")
    return case
