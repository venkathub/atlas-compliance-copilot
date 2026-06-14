"""The CI merge gate (the phase's headline deliverable).

`evaluate_gate` is a pure function (unit-tested): given metric means, the adversarial report, and
the baseline, it decides pass/fail. The CLI replays the committed cassettes (no GPU, no judge, no
RAGAS), runs the RAGAS runner + adversarial scorer, applies the gate, writes a report, and exits
non-zero on any breach so it **blocks merge** (D-P2-4 + the 0-tolerance adversarial gate).
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from atlas_evals.baseline import (
    Baseline,
    calibrate,
    load_baseline,
    save_baseline,
)
from atlas_evals.cassettes import CassetteStore, Mode
from atlas_evals.client import AtlasRagClient, CassettingClient
from atlas_evals.datasets.adversarial import load_adversarial
from atlas_evals.datasets.corpus import DATA_DIR
from atlas_evals.datasets.golden import load_golden
from atlas_evals.fingerprint import rag_fingerprint, ragas_fingerprint
from atlas_evals.metrics.adversarial_scorer import AdversarialReport, score_adversarial
from atlas_evals.metrics.ragas_runner import MetricReport, RagasRunner
from atlas_evals.metrics.ragas_scorer import RagasScorer

RAG_CASSETTES = DATA_DIR / "cassettes" / "rag"
JUDGE_CASSETTES = DATA_DIR / "cassettes" / "judge"


@dataclass
class GateResult:
    passed: bool
    failures: list[str] = field(default_factory=list)


def evaluate_gate(
    scores: dict[str, float], adversarial: AdversarialReport, baseline: Baseline
) -> GateResult:
    """Pure gate decision: floors + no-regression band on gating metrics + 100% adversarial."""
    failures: list[str] = []
    for name, thr in baseline.metrics.items():
        if thr.report_only or thr.floor is None:
            continue
        score = scores.get(name)
        if score is None:
            failures.append(f"{name}: missing from run (no score produced)")
            continue
        if score < thr.floor:
            failures.append(f"{name}: {score:.3f} < floor {thr.floor:.3f}")
        if thr.baseline is not None and thr.max_regression is not None:
            drop = thr.baseline - score
            if drop > thr.max_regression:
                failures.append(
                    f"{name}: regressed {drop:.3f} > {thr.max_regression:.3f} "
                    f"(baseline {thr.baseline:.3f} -> {score:.3f})"
                )
    if adversarial.pass_rate < baseline.adversarial_must_pass_rate:
        failures.append(
            f"adversarial: pass-rate {adversarial.pass_rate:.3f} < "
            f"{baseline.adversarial_must_pass_rate:.3f} "
            f"({len(adversarial.violations)} violation(s))"
        )
    return GateResult(passed=not failures, failures=failures)


def _run(recalibrate: bool) -> tuple[MetricReport, AdversarialReport, Baseline]:
    tuples = load_golden()
    adv_cases = load_adversarial()
    baseline = None if recalibrate else load_baseline()

    # The RAG fingerprint is recomputed LIVE from the checked-out code (model tags + behaviour hash)
    # so a rag-engine change busts the cassette -> loud miss -> re-record. The RAGAS fingerprint +
    # judge model come from baseline (CI replay has no RAGAS installed and can't recompute them).
    rag_fp = rag_fingerprint()
    ragas_fp = baseline.ragas_fingerprint if baseline else ragas_fingerprint()
    judge_model = baseline.judge_model if baseline else os.environ.get(
        "ATLAS_EVAL_JUDGE_MODEL", "llama3.1:8b"
    )
    embed_model = baseline.embed_model if baseline else os.environ.get(
        "OLLAMA_EMBED_MODEL", "nomic-embed-text"
    )

    rag = CassettingClient(
        AtlasRagClient(base_url=os.environ.get("RAG_ENGINE_URL", "http://localhost:8081")),
        CassetteStore(RAG_CASSETTES, Mode.REPLAY),
        fingerprint=rag_fp,
    )
    responses = {
        t.id: rag.query(t.question, t.clearance, top_k=6, include_contexts=True) for t in tuples
    }
    scorer = RagasScorer(
        store=CassetteStore(JUDGE_CASSETTES, Mode.REPLAY),
        judge_model=judge_model,
        embed_model=embed_model,
        base_url="",  # unused in replay
        fingerprint=ragas_fp,
    )
    metric_report = RagasRunner(scorer).run(tuples, responses)

    adv_responses = {
        c.id: rag.query(c.query, c.clearance, top_k=6, include_contexts=True) for c in adv_cases
    }
    adv_report = score_adversarial(adv_cases, adv_responses)

    if recalibrate:
        baseline = calibrate(
            metric_report.scores,
            judge_model=judge_model,
            rag_model=os.environ.get("OLLAMA_CHAT_MODEL", "qwen2.5:3b-instruct"),
            embed_model=embed_model,
            rag_fingerprint=rag_fp,
            ragas_fingerprint=ragas_fp,
            semconv_optin=os.environ.get("OTEL_SEMCONV_STABILITY_OPT_IN", ""),
            git_sha=os.environ.get("GIT_SHA", ""),
        )
        save_baseline(baseline)
    return metric_report, adv_report, baseline


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="atlas_evals.gate", description="Atlas eval merge gate")
    ap.add_argument("--recalibrate", action="store_true", help="rewrite baseline.json from the run")
    ap.add_argument("--report-dir", default=str(DATA_DIR.parent / "report"))
    args = ap.parse_args(argv)

    from atlas_evals.report import push_to_prometheus, write_report

    metric_report, adv_report, baseline = _run(args.recalibrate)
    result = evaluate_gate(metric_report.scores, adv_report, baseline)
    metrics = write_report(Path(args.report_dir), result, metric_report, adv_report, baseline)

    gateway = os.environ.get("PUSHGATEWAY_URL")
    if gateway:
        try:
            push_to_prometheus(metrics, gateway)
            print(f"pushed eval metrics to {gateway}")
        except Exception as e:  # never let a metrics push fail the gate
            print(f"warning: pushgateway push failed: {e}")

    if args.recalibrate:
        print("baseline recalibrated; gate verdict below is informational")
    print("GATE:", "PASS" if result.passed else "FAIL")
    for f in result.failures:
        print("  -", f)
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
