"""Provenance manifest — the LLM03/LLM04 trust artifact for the training dataset.

`build()` assembles a typed manifest (§2.3 schema); `validate(manifest, corpus)` is the trusted
-corpus-only guard: every listed source id must resolve in the committed `Corpus`, per-source
counts must be consistent, and the synthetic block must declare `grounded_in ==
"trusted-corpus-only"`. When the synthetic record provenance refs are available (Task 4), pass
them as `synthetic_refs` to additionally assert each pair is grounded only in a listed source.

Pure stdlib + the Task 2 corpus loader: no network, no GPU.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from atlas_training.data.corpus import Corpus, CorpusError

GROUNDED_INVARIANT = "trusted-corpus-only"
DEFAULT_SPLIT_STRATEGY = "deterministic-by-id"


class ManifestError(ValueError):
    """Raised when a manifest is malformed or violates the trusted-corpus invariant."""


@dataclass(frozen=True)
class Source:
    """A provenance source: a set of trusted corpus ids/docs under one license."""

    kind: str
    license: str
    count: int
    ids: tuple[str, ...] = ()   # FinanceBench financebench_id values
    docs: tuple[str, ...] = ()  # Layer-2 overlay doc ids

    def members(self) -> tuple[str, ...]:
        return tuple(self.ids) + tuple(self.docs)


@dataclass(frozen=True)
class SyntheticMeta:
    generator_model: str
    generator_provider: str
    prompt_template_sha: str
    count: int
    answer_pairs: int
    refusal_pairs: int
    grounded_in: str = GROUNDED_INVARIANT


@dataclass(frozen=True)
class Split:
    train: int
    val: int
    strategy: str = DEFAULT_SPLIT_STRATEGY


@dataclass(frozen=True)
class Manifest:
    dataset_version: str
    seed: int
    sources: tuple[Source, ...]
    synthetic: SyntheticMeta
    split: Split
    generated_at: str
    git_sha: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_version": self.dataset_version,
            "seed": self.seed,
            "sources": [
                {k: (list(v) if isinstance(v, tuple) else v)
                 for k, v in asdict(s).items() if not (k in ("ids", "docs") and not v)}
                for s in self.sources
            ],
            "synthetic": asdict(self.synthetic),
            "split": asdict(self.split),
            "generated_at": self.generated_at,
            "git_sha": self.git_sha,
        }


def current_git_sha() -> str:
    """Short git SHA of HEAD, or 'unknown' if git is unavailable (keeps tests git-independent)."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5, check=True,
        )
        return out.stdout.strip() or "unknown"
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def build(
    *,
    dataset_version: str,
    seed: int,
    sources: list[Source],
    synthetic: SyntheticMeta,
    split: Split,
    generated_at: str | None = None,
    git_sha: str | None = None,
) -> Manifest:
    """Assemble a Manifest. `generated_at`/`git_sha` default to now (UTC) / current HEAD."""
    return Manifest(
        dataset_version=dataset_version,
        seed=seed,
        sources=tuple(sources),
        synthetic=synthetic,
        split=split,
        generated_at=generated_at or datetime.now(UTC).isoformat(),
        git_sha=git_sha or current_git_sha(),
    )


def from_dict(raw: dict[str, Any]) -> Manifest:
    try:
        sources = tuple(
            Source(
                kind=s["kind"],
                license=s["license"],
                count=s["count"],
                ids=tuple(s.get("ids", ())),
                docs=tuple(s.get("docs", ())),
            )
            for s in raw["sources"]
        )
        synthetic = SyntheticMeta(**raw["synthetic"])
        split = Split(**raw["split"])
        return Manifest(
            dataset_version=raw["dataset_version"],
            seed=raw["seed"],
            sources=sources,
            synthetic=synthetic,
            split=split,
            generated_at=raw["generated_at"],
            git_sha=raw["git_sha"],
        )
    except (KeyError, TypeError) as exc:
        raise ManifestError(f"malformed manifest: {exc}") from exc


def load(path: str | Path) -> Manifest:
    p = Path(path)
    if not p.is_file():
        raise ManifestError(f"manifest not found: {p}")
    return from_dict(json.loads(p.read_text(encoding="utf-8")))


def save(manifest: Manifest, path: str | Path) -> None:
    Path(path).write_text(json.dumps(manifest.to_dict(), indent=2) + "\n", encoding="utf-8")


def listed_source_ids(manifest: Manifest) -> frozenset[str]:
    """Union of every id/doc declared across all sources (the trusted allow-list)."""
    ids: set[str] = set()
    for s in manifest.sources:
        ids.update(s.members())
    return frozenset(ids)


def validate(
    manifest: Manifest,
    corpus: Corpus,
    synthetic_refs: list[str] | None = None,
) -> None:
    """Enforce the trusted-corpus-only invariant. Raises ManifestError on any violation.

    * seed is an int; dataset_version non-empty.
    * synthetic.grounded_in == "trusted-corpus-only".
    * every source id/doc resolves in `corpus`; each source.count == number of members.
    * synthetic.count == answer_pairs + refusal_pairs; all counts >= 0; split sizes >= 0.
    * if `synthetic_refs` given, every ref is a listed source id (synthetic grounded only in
      listed sources — wired by Task 4 once the record shape exists).
    """
    if not isinstance(manifest.seed, int) or isinstance(manifest.seed, bool):
        raise ManifestError(f"seed must be an int, got {type(manifest.seed).__name__}")
    if not manifest.dataset_version.strip():
        raise ManifestError("dataset_version must be a non-empty string")

    if manifest.synthetic.grounded_in != GROUNDED_INVARIANT:
        raise ManifestError(
            f"synthetic.grounded_in must be {GROUNDED_INVARIANT!r}, "
            f"got {manifest.synthetic.grounded_in!r}"
        )

    if not manifest.sources:
        raise ManifestError("manifest lists no sources")
    for s in manifest.sources:
        members = s.members()
        if s.count != len(members):
            raise ManifestError(
                f"source {s.kind!r} count={s.count} != {len(members)} listed members"
            )
        for member in members:
            try:
                corpus.resolve(member)
            except CorpusError as exc:
                raise ManifestError(
                    f"source {s.kind!r} references id not in trusted corpus: {member!r}"
                ) from exc

    syn = manifest.synthetic
    if min(syn.count, syn.answer_pairs, syn.refusal_pairs) < 0:
        raise ManifestError("synthetic counts must be non-negative")
    if syn.count != syn.answer_pairs + syn.refusal_pairs:
        raise ManifestError(
            f"synthetic.count={syn.count} != answer_pairs({syn.answer_pairs}) + "
            f"refusal_pairs({syn.refusal_pairs})"
        )

    if manifest.split.train < 0 or manifest.split.val < 0:
        raise ManifestError("split sizes must be non-negative")
    if not manifest.split.strategy.strip():
        raise ManifestError("split.strategy must be a non-empty string")

    if synthetic_refs is not None:
        allowed = listed_source_ids(manifest)
        ungrounded = sorted({r for r in synthetic_refs if r not in allowed})
        if ungrounded:
            raise ManifestError(
                f"synthetic pair(s) grounded in non-listed source(s): {ungrounded}"
            )
