"""Episodic P6 driver — the one-off GPU run that produces the committed evidence (Task 11).

Runs **on the JarvisLabs L4** (it loads the model with torch/CUDA locally), so it does NOT create or
destroy the instance itself. The instance lifecycle is driven from the laptop by `infra/gpu`
(ADR-0066): `atlas_gpu provision` (create) / `up` (resume) beforehand, and `teardown --destroy`
(zero residual cost) / `down` (pause) afterward — a watchdog auto-*pauses* as a safety net. Because
this driver pushes the adapter to the HF Hub BEFORE teardown, destroying the box loses nothing.
See docs/RUNBOOK.md §12.3 for the exact create→run→destroy commands. Inside a CostMeter window:

  1. (optional) rebuild train/val from the committed synthetic seed   (builder, deterministic)
  2. QLoRA SFT fine-tune from the pinned config                       (train.run_training)
  3. push adapter → HF Hub + register the MLflow version              (tracking.register_adapter)
  4. generate base + FT candidate outputs over golden + refusal sets  (infer.generate)
  5. score faithfulness (RAGAS) + format-validity + refusal           (infer.score_outputs + RAGAS)
  6. write results/base.json, ft.json, comparison.json, COMPARISON.md, cost.json  (report)

Everything here is heavy/episodic (lazy imports, no CI coverage). Run with the `train` group:

    uv run --group train python scripts/run_episodic.py --config configs/qlora_qwen7b.yaml

Requires env: HF_TOKEN, ATLAS_HF_ADAPTER_REPO, MLFLOW_TRACKING_URI, ATLAS_GPU_COST_PER_HOUR,
ATLAS_EVAL_JUDGE_MODEL, OLLAMA_BASE_URL (judge), OLLAMA_EMBED_MODEL. See .env.example + RUNBOOK.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

from atlas_training.config import load
from atlas_training.cost import CostMeter, gpu_rate_from_env
from atlas_training.report import build_comparison, write_comparison

log = logging.getLogger("atlas_training.episodic")

HERE = Path(__file__).resolve().parent.parent  # training/
CONTEXT_CHARS = 700


def _excerpt(text: str, limit: int = CONTEXT_CHARS) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rstrip() + " …"


def _golden_prompts(golden, corpus):
    """Build (case_id, prompt, allowed_ids, contexts, ground_truth) for the golden set."""
    rows = []
    for t in golden:
        ctx_docs = [corpus.resolve(d) for d in t.expected_source_docs]
        context = "\n".join(f"[doc:{d.doc_id}] {_excerpt(d.text)}" for d in ctx_docs)
        prompt = f"{t.question}\n\n{context}"
        rows.append({
            "case_id": t.id,
            "prompt": prompt,
            "allowed_ids": list(t.expected_source_docs),
            "contexts": [d.text for d in ctx_docs],
            "ground_truth": t.ground_truth,
            "question": t.question,
        })
    return rows


def _faithfulness(rows, outputs):  # pragma: no cover - episodic (RAGAS + judge)
    """RAGAS faithfulness mean over (question, model output, contexts, ground_truth)."""
    try:
        from atlas_evals.metrics.ragas_scorer import RagasScorer
        from atlas_evals.metrics.samples import EvalSample

        samples = [
            EvalSample(id=r["case_id"], question=r["question"], answer=out,
                       contexts=r["contexts"], ground_truth=r["ground_truth"])
            for r, out in zip(rows, outputs, strict=True)
        ]
        scorer = RagasScorer(
            judge_model=os.environ["ATLAS_EVAL_JUDGE_MODEL"],
            embed_model=os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
            base_url=os.environ.get("ATLAS_EVAL_JUDGE_BASE_URL", os.environ["OLLAMA_BASE_URL"]),
        )
        return float(scorer.score(samples).get("faithfulness", float("nan")))
    except Exception:  # noqa: BLE001 - faithfulness is best-effort; never lose the run over it
        log.exception("faithfulness (RAGAS) failed — recording NaN; fill in from a judge re-run")
        return None


def _candidates(rows, outputs):  # pragma: no cover - episodic
    from atlas_training.infer import Candidate

    return [
        Candidate(case_id=r["case_id"], prompt=r["prompt"], output=out,
                  allowed_ids=r["allowed_ids"])
        for r, out in zip(rows, outputs, strict=True)
    ]


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - episodic GPU entrypoint
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser(description="Atlas P6 episodic train+benchmark driver (GPU).")
    ap.add_argument("--config", required=True)
    ap.add_argument("--data-dir", default=str(HERE / "data"))
    ap.add_argument("--out", default=str(HERE / "out" / "adapter"))
    ap.add_argument("--results", default=str(HERE / "results"))
    ap.add_argument("--build-data", action="store_true",
                    help="regenerate train/val from the committed synthetic.jsonl first")
    ap.add_argument("--no-register", action="store_true", help="skip the HF push + MLflow register")
    ap.add_argument("--hf-only", action="store_true",
                    help="push adapter to HF WITHOUT MLflow (box mode; register from laptop later)")
    ap.add_argument("--upload-results", default=None, metavar="HF_REPO",
                    help="after writing results/, upload them to this HF repo (box retrieval)")
    args = ap.parse_args(argv)

    config = load(args.config)
    data_dir = Path(args.data_dir)

    # 1. (optional) deterministic dataset rebuild
    if args.build_data:
        from atlas_training.data import builder

        pairs = builder.load_pairs(data_dir / "synthetic.jsonl")
        builder.build_and_write(pairs, seed=config.seed, out_dir=data_dir)
        log.info("rebuilt train/val from synthetic seed (seed=%d)", config.seed)

    # lazy heavy imports
    from atlas_evals.datasets.golden import load_golden
    from atlas_evals.datasets.refusal import load_refusal

    from atlas_training.data.corpus import load_corpus as load_training_corpus
    from atlas_training.infer import generate, score_outputs
    from atlas_training.train import run_training

    rate, currency = gpu_rate_from_env()
    meter = CostMeter()
    with meter:
        # 2. train
        tracker = None
        if not args.no_register and not args.hf_only:
            from atlas_training.tracking import HfHubClient, MlflowRegistry, Tracker

            tracker = Tracker.from_env(MlflowRegistry(), HfHubClient())
        result = run_training(config, data_dir, args.out, tracker=tracker)
        log.info("train done: %s", result)

        # 3. register / push (HF push happens BEFORE teardown)
        ft_model_id = args.out
        if tracker is not None:
            mv = tracker.register_adapter(
                result.run_id, result.adapter_path, config.mlflow.register_as)
            ft_model_id = mv.source
            log.info("registered %s v%s <- %s", mv.name, mv.version, mv.source)
        elif args.hf_only:
            # Box mode: push the adapter to HF (durable) without MLflow; register from the laptop.
            from atlas_training.tracking import HfHubClient, hf_source_uri

            repo = os.environ["ATLAS_HF_ADAPTER_REPO"]
            private = os.environ.get("HF_PRIVATE", "true").lower() not in ("false", "0", "no")
            rev = HfHubClient().push(
                result.adapter_path, repo, private=private, token=os.environ["HF_TOKEN"])
            ft_model_id = hf_source_uri(repo, rev)
            log.info("pushed adapter to HF: %s", ft_model_id)

        # 4. generate base + FT candidates
        golden = load_golden()
        refusal_cases = load_refusal()
        rows = _golden_prompts(golden, load_training_corpus())
        golden_prompts = [r["prompt"] for r in rows]
        refusal_prompts = [c.question for c in refusal_cases]

        base_golden = generate(config.base_model, golden_prompts)
        base_refusal = generate(config.base_model, refusal_prompts)
        ft_golden = generate(config.base_model, golden_prompts, adapter_path=result.adapter_path)
        ft_refusal = generate(config.base_model, refusal_prompts, adapter_path=result.adapter_path)

        # 5. score
        base_scores = score_outputs(
            _candidates(rows, base_golden), refusal_cases, base_refusal,
            faithfulness=_faithfulness(rows, base_golden),
        )
        ft_scores = score_outputs(
            _candidates(rows, ft_golden), refusal_cases, ft_refusal,
            faithfulness=_faithfulness(rows, ft_golden),
        )

    cost = meter.record(rate, currency=currency, teardown_recorded=True)

    # 6. write evidence
    results_dir = Path(args.results)
    results_dir.mkdir(parents=True, exist_ok=True)
    dataset_size = len(rows) + len(refusal_cases)
    (results_dir / "base.json").write_text(
        json.dumps({"model": config.base_model, "scores": base_scores,
                    "golden": base_golden, "refusal": base_refusal}, indent=2) + "\n")
    (results_dir / "ft.json").write_text(
        json.dumps({"model": ft_model_id, "scores": ft_scores,
                    "golden": ft_golden, "refusal": ft_refusal}, indent=2) + "\n")
    cost.save(results_dir / "cost.json")

    comparison = build_comparison(
        base_scores, ft_scores,
        model_ids={"base": config.base_model, "ft": ft_model_id},
        dataset_size=dataset_size, training_cost=cost.to_dict(),
    )
    jp, mp = write_comparison(comparison, results_dir)
    log.info("wrote %s and %s", jp, mp)

    # 7. (box mode) upload results/ to HF so the laptop can retrieve them without SSH
    if args.upload_results:
        from huggingface_hub import HfApi

        HfApi(token=os.environ["HF_TOKEN"]).upload_folder(
            repo_id=args.upload_results, folder_path=str(results_dir),
            path_in_repo="results", repo_type="model",
            commit_message="Atlas P6: episodic base-vs-FT results",
        )
        log.info("uploaded results/ to HF repo %s", args.upload_results)

    print(f"cost: {cost.cost} {cost.currency} over {cost.wall_seconds}s")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
