"""Assemble chat-format SFT examples + a deterministic, reproducible train/val split (GPU-free).

Turns `SyntheticPair`s (Task 4) into the SFT chat unit of §2.3 — a shared pinned system prompt,
a user turn (question + trusted context carrying `[doc:<id>]` markers), and the cited-answer /
grounded-refusal assistant turn — then splits them train/val by a seed-stable, id-ordered rule.
The split sizes come from `synth.planned_split`, so they always match the committed manifest.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

from atlas_training.data.synth import SyntheticPair, planned_split
from atlas_training.data.synth import read_jsonl as read_pairs

# The PINNED Atlas system instruction the fine-tune teaches (citation-bound answer / grounded
# refusal). Kept here as the single source of truth for the assistant's target behaviour.
SYSTEM_PROMPT = (
    "You are Atlas, an enterprise financial and compliance assistant. Answer the user's question "
    "using ONLY the provided context. Cite every supporting fact inline with a [doc:<id>] marker, "
    "using the id from the context's [doc:<id>] header. If the context does not contain the "
    "answer, refuse: state plainly that you cannot answer from the provided sources and name the "
    "missing information. Never fabricate facts, citations, or document ids."
)

VALID_LABELS = ("answer", "refusal")


@dataclass(frozen=True)
class SFTExample:
    messages: tuple[dict[str, str], ...]  # system, user, assistant
    label: str
    provenance_ref: str

    def to_dict(self) -> dict:
        return {
            "messages": [dict(m) for m in self.messages],
            "label": self.label,
            "provenance_ref": self.provenance_ref,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> SFTExample:
        return cls(
            messages=tuple(dict(m) for m in raw["messages"]),
            label=raw["label"],
            provenance_ref=raw["provenance_ref"],
        )


def to_example(pair: SyntheticPair) -> SFTExample:
    """Build one chat-format SFT example from a synthetic pair."""
    if pair.label not in VALID_LABELS:
        raise ValueError(f"unknown label {pair.label!r} (expected one of {VALID_LABELS})")
    return SFTExample(
        messages=(
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"{pair.question}\n\n{pair.context}"},
            {"role": "assistant", "content": pair.answer},
        ),
        label=pair.label,
        provenance_ref=pair.provenance_ref,
    )


def _stable_key(pair: SyntheticPair) -> tuple[str, str]:
    return (pair.provenance_ref, pair.question)


def split_dataset(
    pairs: list[SyntheticPair], seed: int
) -> tuple[list[SFTExample], list[SFTExample]]:
    """Deterministic (train, val) split of SFT examples.

    Ordering is *deterministic-by-id*: pairs are stably sorted by (provenance_ref, question) then
    shuffled with a seeded RNG, so the split is reproducible from the committed seed and the two
    sides are disjoint. Sizes come from `planned_split`, matching the provenance manifest.
    """
    ordered = sorted(pairs, key=_stable_key)
    random.Random(seed).shuffle(ordered)
    _, n_val = planned_split(len(ordered))
    val_pairs = ordered[:n_val]
    train_pairs = ordered[n_val:]
    return [to_example(p) for p in train_pairs], [to_example(p) for p in val_pairs]


def write_jsonl(examples: list[SFTExample], path: str | Path) -> None:
    with Path(path).open("w", encoding="utf-8") as fh:
        for ex in examples:
            fh.write(json.dumps(ex.to_dict(), ensure_ascii=False) + "\n")


def read_jsonl(path: str | Path) -> list[SFTExample]:
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(SFTExample.from_dict(json.loads(line)))
    return out


def build_and_write(
    pairs: list[SyntheticPair], seed: int, out_dir: str | Path
) -> tuple[Path, Path]:
    """Split `pairs` and write train.jsonl + val.jsonl into `out_dir`. Returns the two paths."""
    train, val = split_dataset(pairs, seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    train_path, val_path = out / "train.jsonl", out / "val.jsonl"
    write_jsonl(train, train_path)
    write_jsonl(val, val_path)
    return train_path, val_path


def load_pairs(path: str | Path) -> list[SyntheticPair]:
    """Convenience re-export: read a synthetic.jsonl pair file."""
    return read_pairs(path)
