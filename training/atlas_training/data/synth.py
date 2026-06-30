"""Synthetic (context -> cited-answer | grounded-refusal) pair generation (GPU-free).

The frontier answer-pair generator sits behind a **mockable seam** (`Generator` protocol): unit
tests inject a fake, so no network/secret is touched in CI (ADR-0071/D3). The grounded-refusal
edge cases — the safety-critical ones — are **hand-authored** so they are authoritative. Every
pair is grounded ONLY in the committed trusted corpus (LLM04) and tagged with a `provenance_ref`.

Citation format note: the Atlas *fine-tuned* format uses `[doc:<id>]` markers (the marker carries
the resolvable doc id, which is what Task 6's deterministic format-validity scorer checks). This
intentionally differs from the production extractor's positional `[n]` markers (CitationExtractor);
reconciling the two at serve time is a P7 router/serving concern.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from atlas_training.data.corpus import Corpus, TrustedDoc
from atlas_training.data.manifest import Manifest, Source, Split, SyntheticMeta, build

CONTEXT_EXCERPT_CHARS = 700

# The PINNED generation prompt. Its sha is recorded in the manifest for reproducibility (ADR-0071).
PROMPT_TEMPLATE = (
    "You are Atlas, an enterprise financial/compliance assistant. Answer the QUESTION using ONLY "
    "the CONTEXT. Cite every supporting source inline with a [doc:<id>] marker using the id shown "
    "in the context header. If the context does not contain the answer, refuse and say which "
    "information is missing — never guess.\n\n"
    "CONTEXT:\n[doc:{doc_id}] {context}\n\nQUESTION: {question}\n\nANSWER:"
)


def prompt_template_sha() -> str:
    """sha256 of the pinned prompt template (recorded in the provenance manifest)."""
    return hashlib.sha256(PROMPT_TEMPLATE.encode("utf-8")).hexdigest()


def excerpt(text: str, limit: int = CONTEXT_EXCERPT_CHARS) -> str:
    """A compact, deterministic context excerpt (keeps committed synthetic.jsonl small)."""
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rstrip() + " …"


@dataclass(frozen=True)
class SyntheticPair:
    question: str
    context: str  # trusted excerpt, prefixed with a [doc:<id>] header
    answer: str
    label: str  # "answer" | "refusal"
    provenance_ref: str  # corpus doc id this pair is grounded in
    generator: str  # model id, or "hand-authored"

    def to_dict(self) -> dict:
        return asdict(self)


# ── generator seam ───────────────────────────────────────────────────────────────────────────────


@runtime_checkable
class Generator(Protocol):
    """A text generator. `FrontierGenerator` is the real impl; tests inject a fake callable."""

    model_id: str

    def __call__(self, prompt: str) -> str: ...


class FrontierGenerator:
    """OpenAI-compatible frontier generator, fully env-driven (no hardcoded model/endpoint/secret).

    Only used for the one-off offline answer-pair generation; `openai` is lazy-imported and lives in
    the optional `synth` dependency group, so CI/unit tests never import it.
    """

    def __init__(
        self,
        model_id: str,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        provider: str = "openai-compatible",
        temperature: float = 0.2,
    ) -> None:
        self.model_id = model_id
        self.base_url = base_url
        self.api_key = api_key
        self.provider = provider
        self.temperature = temperature

    @classmethod
    def from_env(cls) -> FrontierGenerator:
        try:
            model_id = os.environ["ATLAS_SYNTH_GENERATOR_MODEL"]
        except KeyError as exc:
            raise RuntimeError(
                "ATLAS_SYNTH_GENERATOR_MODEL is unset — configure the synthetic generator in .env"
            ) from exc
        return cls(
            model_id=model_id,
            base_url=os.environ.get("ATLAS_SYNTH_BASE_URL"),
            api_key=os.environ.get("ATLAS_SYNTH_API_KEY"),
            provider=os.environ.get("ATLAS_SYNTH_GENERATOR_PROVIDER", "openai-compatible"),
        )

    def __call__(self, prompt: str) -> str:  # pragma: no cover - exercised only in the live one-off
        import openai  # lazy: optional `synth` group, never needed by CI

        client = openai.OpenAI(base_url=self.base_url, api_key=self.api_key)
        resp = client.chat.completions.create(
            model=self.model_id,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
        )
        return (resp.choices[0].message.content or "").strip()


def build_prompt(doc: TrustedDoc, question: str) -> str:
    return PROMPT_TEMPLATE.format(
        doc_id=doc.doc_id, context=excerpt(doc.text), question=question
    )


def generate_answer_pair(doc: TrustedDoc, question: str, generator: Generator) -> SyntheticPair:
    """Generate one cited-answer pair grounded in `doc`, via the injected generator."""
    answer = generator(build_prompt(doc, question)).strip()
    return SyntheticPair(
        question=question,
        context=f"[doc:{doc.doc_id}] {excerpt(doc.text)}",
        answer=answer,
        label="answer",
        provenance_ref=doc.doc_id,
        generator=generator.model_id,
    )


# ── hand-authored seed (provenance-honest; frontier expansion is the Task 11 one-off) ─────────────

# (doc_id, question, cited answer) — figures verbatim from the committed corpus / golden set.
AUTHORED_ANSWERS: tuple[tuple[str, str, str], ...] = (
    (
        "financebench_id_03029",
        "What was 3M's FY2018 capital expenditure (USD millions)?",
        "3M's FY2018 capital expenditure (purchases of property, plant and equipment) was "
        "$1,577 million [doc:financebench_id_03029].",
    ),
    (
        "financebench_id_04672",
        "What was 3M's year-end FY2018 net property, plant and equipment (USD billions)?",
        "3M's year-end FY2018 net property, plant and equipment was about $8.70 billion "
        "[doc:financebench_id_04672].",
    ),
    (
        "financebench_id_05718",
        "How much did American Water Works pay in cash dividends in FY2020 (USD billions)?",
        "American Water Works paid approximately $0.40 billion in cash dividends in FY2020 "
        "[doc:financebench_id_05718].",
    ),
    (
        "financebench_id_01351",
        "How did American Express's effective tax rate change from FY2021 to FY2022?",
        "American Express's effective tax rate fell from 24.6% in FY2021 to 21.6% in FY2022 "
        "[doc:financebench_id_01351].",
    ),
    (
        "l2-aml-policy-overview",
        "What is the SAR filing threshold and deadline under the AML policy?",
        "A SAR is filed when a transaction or pattern aggregating $5,000 or more is suspected of "
        "involving illegal funds or BSA evasion, and it must be filed within 30 calendar days of "
        "initial detection [doc:l2-aml-policy-overview].",
    ),
    (
        "l2-bsa-regulatory-reference",
        "How long must records supporting CTRs and SARs be retained?",
        "Records supporting CTRs and SARs must be retained for five years "
        "[doc:l2-bsa-regulatory-reference].",
    ),
)

# (doc_id, question, grounded refusal) — the question is NOT answerable from that doc's context.
AUTHORED_REFUSALS: tuple[tuple[str, str, str], ...] = (
    (
        "financebench_id_03029",
        "What was 3M's net income in FY2021?",
        "I can't answer that from the provided sources: the 3M cash-flow context covers FY2016–"
        "FY2018 only and does not contain FY2021 net income.",
    ),
    (
        "financebench_id_04672",
        "What was Activision Blizzard's total revenue in FY2019?",
        "I can't answer that from the provided sources: the context is 3M's FY2018 balance sheet "
        "and contains no Activision Blizzard revenue figures.",
    ),
    (
        "l2-aml-policy-overview",
        "What are the open AML exceptions on the Northwind Trading account this quarter?",
        "I can't answer that from the provided sources: the AML policy overview defines thresholds "
        "and procedures but contains no account-specific exception data for Northwind Trading.",
    ),
    (
        "l2-bsa-regulatory-reference",
        "What is the current OFAC sanctions status of Northwind Trading LLC?",
        "I can't answer that from the provided sources: the BSA regulatory reference does not "
        "include any OFAC screening results for a specific customer.",
    ),
)


def authored_answers(corpus: Corpus) -> list[SyntheticPair]:
    pairs = []
    for doc_id, question, answer in AUTHORED_ANSWERS:
        doc = corpus.resolve(doc_id)
        pairs.append(
            SyntheticPair(
                question=question,
                context=f"[doc:{doc.doc_id}] {excerpt(doc.text)}",
                answer=answer,
                label="answer",
                provenance_ref=doc.doc_id,
                generator="hand-authored",
            )
        )
    return pairs


def authored_refusals(corpus: Corpus) -> list[SyntheticPair]:
    pairs = []
    for doc_id, question, refusal in AUTHORED_REFUSALS:
        doc = corpus.resolve(doc_id)
        pairs.append(
            SyntheticPair(
                question=question,
                context=f"[doc:{doc.doc_id}] {excerpt(doc.text)}",
                answer=refusal,
                label="refusal",
                provenance_ref=doc.doc_id,
                generator="hand-authored",
            )
        )
    return pairs


def build_seed(corpus: Corpus) -> list[SyntheticPair]:
    """The committed, provenance-honest seed dataset (answers + grounded refusals)."""
    return authored_answers(corpus) + authored_refusals(corpus)


# ── jsonl IO + manifest assembly ──────────────────────────────────────────────────────────────────


def write_jsonl(pairs: list[SyntheticPair], path: str | Path) -> None:
    with Path(path).open("w", encoding="utf-8") as fh:
        for p in pairs:
            fh.write(json.dumps(p.to_dict(), ensure_ascii=False) + "\n")


def read_jsonl(path: str | Path) -> list[SyntheticPair]:
    pairs = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            pairs.append(SyntheticPair(**json.loads(line)))
    return pairs


def provenance_refs(pairs: list[SyntheticPair]) -> list[str]:
    return [p.provenance_ref for p in pairs]


def planned_split(n: int, *, val_frac: float = 0.2, min_val: int = 1) -> tuple[int, int]:
    """Deterministic (train, val) sizes. Shared with the Task 5 builder so the manifest matches."""
    if n <= 0:
        return (0, 0)
    val = max(min_val, round(n * val_frac))
    val = min(val, n - 1) if n > 1 else 0
    return (n - val, val)


def build_manifest(
    pairs: list[SyntheticPair],
    corpus: Corpus,
    *,
    dataset_version: str,
    seed: int,
    generator_model: str,
    generator_provider: str,
) -> Manifest:
    """Assemble the provenance manifest for a synthetic pair set, grouped by corpus layer."""
    fb_ids, l2_ids = [], []
    for ref in dict.fromkeys(provenance_refs(pairs)):  # de-dup, preserve order
        doc = corpus.resolve(ref)
        (fb_ids if doc.layer == 1 else l2_ids).append(ref)

    sources: list[Source] = []
    if fb_ids:
        sources.append(Source(kind="financebench", license="CC-BY-NC-4.0",
                              count=len(fb_ids), ids=tuple(fb_ids)))
    if l2_ids:
        sources.append(Source(kind="layer2_overlay", license="authored-internal",
                              count=len(l2_ids), docs=tuple(l2_ids)))

    n_answer = sum(1 for p in pairs if p.label == "answer")
    n_refusal = sum(1 for p in pairs if p.label == "refusal")
    train, val = planned_split(len(pairs))

    return build(
        dataset_version=dataset_version,
        seed=seed,
        sources=sources,
        synthetic=SyntheticMeta(
            generator_model=generator_model,
            generator_provider=generator_provider,
            prompt_template_sha=prompt_template_sha(),
            count=len(pairs),
            answer_pairs=n_answer,
            refusal_pairs=n_refusal,
        ),
        split=Split(train=train, val=val),
    )
