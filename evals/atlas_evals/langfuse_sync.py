"""Push the golden set to a Langfuse dataset + attach run scores (ADR-0025).

Langfuse-managed datasets drive regression runs (P2 roadmap exit criterion). This is opt-in: it runs
only when Langfuse keys are configured, and the client is injectable so payload shaping is tested
without a live Langfuse. Kept thin on purpose — the gate (not Langfuse) is the authority.
"""

from __future__ import annotations

import os
from typing import Protocol

from atlas_evals.datasets.golden import GoldenTuple

DATASET_NAME = "atlas-golden"


def build_dataset_items(tuples: list[GoldenTuple]) -> list[dict]:
    """One Langfuse dataset item per golden tuple (input + expected output + metadata)."""
    return [
        {
            "input": {"query": t.question, "clearance": t.clearance},
            "expected_output": t.ground_truth,
            "metadata": {
                "id": t.id,
                "layer": t.layer,
                "expected_source_docs": t.expected_source_docs,
                "source": t.source,
            },
        }
        for t in tuples
    ]


class LangfuseLike(Protocol):
    def create_dataset(self, name: str) -> object: ...
    def create_dataset_item(self, dataset_name: str, input: dict, expected_output: str,
                            metadata: dict) -> object: ...


def sync_dataset(
    client: LangfuseLike, tuples: list[GoldenTuple], dataset_name: str = DATASET_NAME
) -> int:
    """Create the dataset (idempotent) and upsert one item per tuple. Returns item count."""
    try:
        client.create_dataset(name=dataset_name)
    except TypeError:
        client.create_dataset(dataset_name)  # tolerate positional-only stubs
    items = build_dataset_items(tuples)
    for item in items:
        client.create_dataset_item(
            dataset_name=dataset_name,
            input=item["input"],
            expected_output=item["expected_output"],
            metadata=item["metadata"],
        )
    return len(items)


def langfuse_enabled() -> bool:
    return bool(os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"))
