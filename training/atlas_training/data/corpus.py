"""Load the committed **trusted** corpus as the only sanctioned training-context substrate.

P6 trains on trusted-corpus-only inputs (LLM04). This module is the single source of truth for
"what is a real, committed corpus doc" on the training side — it loads:

  * **Layer-1** — FinanceBench evidence snippets (`layer1/*.txt` + `layer1/manifest.json`),
    keyed by `financebench_id`, clearance from the manifest (ADR-0017/0020).
  * **Layer-2** — the authored AML/compliance overlay (`layer2/*.md` with YAML front-matter),
    keyed by front-matter `doc_id`, clearance from front-matter (ADR-0004).

`load_corpus()` returns a `Corpus` whose `resolve(id)` raises on any unknown id — the guard
Task 3's `manifest.validate` uses to enforce the trusted-corpus-only invariant. Pure stdlib +
PyYAML: no network, no GPU. Mirrors the root-resolution + clearance conventions of
`evals/atlas_evals/datasets/corpus.py`.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

# training/atlas_training/data/corpus.py -> parents[3] == repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CORPUS_DIR = REPO_ROOT / "rag-engine" / "src" / "main" / "resources" / "corpus"

# Clearance gradient (ADR-0004); identical ordering to evals + rag-engine.
CLEARANCES = ("public", "analyst", "compliance", "restricted")


class CorpusError(ValueError):
    """Raised when the committed corpus is malformed or a requested id does not resolve."""


@dataclass(frozen=True)
class TrustedDoc:
    """A single committed, trusted training-context document."""

    doc_id: str
    layer: int  # 1 (FinanceBench) | 2 (authored overlay)
    clearance: str
    text: str
    source: str  # provenance tag, e.g. "financebench:financebench_id_03029" / "layer2:l2-..."
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Corpus:
    """Immutable id -> TrustedDoc map with a fail-fast `resolve`."""

    docs: dict[str, TrustedDoc]

    def __contains__(self, doc_id: object) -> bool:
        return doc_id in self.docs

    def __len__(self) -> int:
        return len(self.docs)

    def ids(self) -> frozenset[str]:
        return frozenset(self.docs)

    def get(self, doc_id: str) -> TrustedDoc | None:
        return self.docs.get(doc_id)

    def resolve(self, doc_id: str) -> TrustedDoc:
        """Return the doc for `doc_id`, or raise CorpusError (the trusted-corpus guard)."""
        doc = self.docs.get(doc_id)
        if doc is None:
            raise CorpusError(f"unknown corpus doc id (not in trusted corpus): {doc_id!r}")
        return doc

    def by_layer(self, layer: int) -> list[TrustedDoc]:
        return [d for d in self.docs.values() if d.layer == layer]


def _resolve_root(root: str | os.PathLike[str] | None) -> Path:
    if root is not None:
        return Path(root)
    env = os.environ.get("ATLAS_CORPUS_ROOT")
    return Path(env) if env else DEFAULT_CORPUS_DIR


def _split_front_matter(raw: str, path: Path) -> tuple[dict, str]:
    """Split a `---`-delimited YAML front-matter block from a markdown body."""
    if not raw.startswith("---"):
        raise CorpusError(f"layer-2 doc missing YAML front-matter: {path}")
    parts = raw.split("---", 2)
    if len(parts) < 3:
        raise CorpusError(f"layer-2 doc has malformed front-matter: {path}")
    meta = yaml.safe_load(parts[1]) or {}
    if not isinstance(meta, dict):
        raise CorpusError(f"layer-2 front-matter is not a mapping: {path}")
    return meta, parts[2].lstrip("\n")


def _load_layer1(corpus_dir: Path) -> dict[str, TrustedDoc]:
    manifest_path = corpus_dir / "layer1" / "manifest.json"
    if not manifest_path.is_file():
        raise CorpusError(f"layer-1 manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    docs: dict[str, TrustedDoc] = {}
    for entry in manifest.get("documents", []):
        doc_id = entry["financebench_id"]
        file_path = corpus_dir / "layer1" / entry["file"]
        if not file_path.is_file():
            raise CorpusError(f"layer-1 manifest references missing file: {file_path}")
        text = file_path.read_text(encoding="utf-8").strip()
        if not text:
            raise CorpusError(f"layer-1 doc is empty: {file_path}")
        clearance = entry.get("clearance")
        if clearance not in CLEARANCES:
            raise CorpusError(f"layer-1 doc {doc_id} has invalid clearance: {clearance!r}")
        meta = {k: v for k, v in entry.items() if k not in ("financebench_id", "file", "clearance")}
        docs[doc_id] = TrustedDoc(
            doc_id=doc_id,
            layer=1,
            clearance=clearance,
            text=text,
            source=f"financebench:{doc_id}",
            metadata=meta,
        )
    if not docs:
        raise CorpusError(f"layer-1 manifest lists no documents: {manifest_path}")
    return docs


def _load_layer2(corpus_dir: Path) -> dict[str, TrustedDoc]:
    layer2_dir = corpus_dir / "layer2"
    if not layer2_dir.is_dir():
        raise CorpusError(f"layer-2 directory not found: {layer2_dir}")
    docs: dict[str, TrustedDoc] = {}
    for md in sorted(layer2_dir.glob("*.md")):
        meta, body = _split_front_matter(md.read_text(encoding="utf-8"), md)
        doc_id = meta.get("doc_id") or md.stem
        clearance = meta.get("clearance")
        if clearance not in CLEARANCES:
            raise CorpusError(f"layer-2 doc {doc_id} has invalid clearance: {clearance!r}")
        body = body.strip()
        if not body:
            raise CorpusError(f"layer-2 doc is empty: {md}")
        extra = {k: v for k, v in meta.items() if k not in ("doc_id", "clearance")}
        docs[doc_id] = TrustedDoc(
            doc_id=doc_id,
            layer=2,
            clearance=clearance,
            text=body,
            source=f"layer2:{doc_id}",
            metadata=extra,
        )
    if not docs:
        raise CorpusError(f"layer-2 directory has no .md docs: {layer2_dir}")
    return docs


def load_corpus(root: str | os.PathLike[str] | None = None) -> Corpus:
    """Load the trusted corpus (Layer-1 + Layer-2).

    `root` (or the `ATLAS_CORPUS_ROOT` env var) overrides the default committed corpus dir;
    no absolute path is hardcoded. Raises CorpusError on any malformed/missing input.
    """
    corpus_dir = _resolve_root(root)
    if not corpus_dir.is_dir():
        raise CorpusError(f"corpus root not found: {corpus_dir}")
    docs = _load_layer1(corpus_dir)
    layer2 = _load_layer2(corpus_dir)
    overlap = docs.keys() & layer2.keys()
    if overlap:
        raise CorpusError(f"doc id collision across layers: {sorted(overlap)}")
    docs.update(layer2)
    return Corpus(docs=docs)


@lru_cache(maxsize=1)
def default_corpus() -> Corpus:
    """Cached load of the default committed corpus (the common read-only path)."""
    return load_corpus()
