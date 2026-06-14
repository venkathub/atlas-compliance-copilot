"""Concrete RAGAS scorer with per-sample judge cassettes.

Cassette granularity decision (D-P2-1c): we cassette **per-sample metric scores** keyed by
(judge_model, ragas_fingerprint, question, answer, contexts, ground_truth). This is the judge-side
half of the offline gate and has two payoffs:
  * **REPLAY needs neither RAGAS nor a judge** — the gate reads committed per-sample scores, so the
    CI merge gate is light and never imports the heavy LLM stack.
  * a changed RAG answer / judge model / metric set changes the key → a **loud miss** demanding a
    re-record (never silently scoring stale answers).
Live metric computation (RECORD) lazily imports RAGAS and runs the real judge at **temperature 0**.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import fmean

from atlas_evals.cassettes import CassetteStore, cassette_key
from atlas_evals.metrics.samples import EvalSample

# Gating + report-only metrics computed by RAGAS (the gate decides which gate — Task 8).
DEFAULT_METRICS = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
    "context_entity_recall",
    "noise_sensitivity",
)


@dataclass
class RagasScorer:
    """RAGAS metric computation with per-sample cassettes (judge pinned, temp 0)."""

    store: CassetteStore
    judge_model: str
    embed_model: str
    base_url: str
    fingerprint: str = ""  # ragas version + any metric-config id, recorded in baseline.json
    metrics: tuple[str, ...] = DEFAULT_METRICS
    judge_temperature: float = 0.0
    _per_sample: dict[str, dict] = field(default_factory=dict, repr=False)

    def key(self, sample: EvalSample) -> str:
        return cassette_key(
            "ragas",
            self.judge_model,
            self.fingerprint,
            tuple(self.metrics),
            sample.question,
            sample.answer,
            tuple(sample.contexts),
            sample.ground_truth,
        )

    def score(self, samples: list[EvalSample]) -> dict[str, float]:
        self._per_sample = {}
        for s in samples:
            scores = self.store.record_or_replay(
                self.key(s), lambda s=s: self._evaluate_one(s), meta={"id": s.id}
            )
            self._per_sample[s.id] = scores
        means: dict[str, float] = {}
        for metric in self.metrics:
            vals = [
                self._per_sample[sid][metric]
                for sid in self._per_sample
                if self._per_sample[sid].get(metric) is not None
            ]
            if vals:
                means[metric] = fmean(vals)
        return means

    def _evaluate_one(self, sample: EvalSample) -> dict:  # pragma: no cover - live (Task 8)
        """Run RAGAS over a single sample with the live judge. Imported lazily (RECORD only)."""
        from langchain_ollama import ChatOllama, OllamaEmbeddings
        from ragas import EvaluationDataset, SingleTurnSample, evaluate
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import (
            AnswerRelevancy,
            ContextEntityRecall,
            ContextPrecision,
            ContextRecall,
            Faithfulness,
            NoiseSensitivity,
        )

        judge = LangchainLLMWrapper(
            ChatOllama(
                model=self.judge_model,
                base_url=self.base_url,
                temperature=self.judge_temperature,
            )
        )
        embeddings = LangchainEmbeddingsWrapper(
            OllamaEmbeddings(model=self.embed_model, base_url=self.base_url)
        )
        metric_objs = {
            "faithfulness": Faithfulness(),
            "answer_relevancy": AnswerRelevancy(),
            "context_precision": ContextPrecision(),
            "context_recall": ContextRecall(),
            "context_entity_recall": ContextEntityRecall(),
            "noise_sensitivity": NoiseSensitivity(),
        }
        chosen = [metric_objs[m] for m in self.metrics if m in metric_objs]
        dataset = EvaluationDataset(samples=[SingleTurnSample(
            user_input=sample.question,
            response=sample.answer,
            retrieved_contexts=sample.contexts or [""],
            reference=sample.ground_truth,
        )])
        result = evaluate(dataset, metrics=chosen, llm=judge, embeddings=embeddings)
        row = result.to_pandas().iloc[0].to_dict()
        return {m: _as_float(row.get(m)) for m in self.metrics}


def _as_float(value) -> float | None:  # pragma: no cover - live (Task 8)
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if f != f else f  # drop NaN
