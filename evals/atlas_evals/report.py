"""Eval report writers: machine-readable metrics.json + a human markdown PR summary."""

from __future__ import annotations

import json
from pathlib import Path

from atlas_evals.baseline import Baseline
from atlas_evals.metrics.adversarial_scorer import AdversarialReport
from atlas_evals.metrics.ragas_runner import MetricReport


def build_metrics(
    result, metric_report: MetricReport, adversarial: AdversarialReport, baseline: Baseline
) -> dict:
    return {
        "gate": {"passed": result.passed, "failures": result.failures},
        "n_samples": metric_report.n_samples,
        "scores": {k: round(v, 4) for k, v in metric_report.scores.items()},
        "thresholds": {
            k: {"floor": t.floor, "baseline": t.baseline, "max_regression": t.max_regression,
                "report_only": t.report_only}
            for k, t in baseline.metrics.items()
        },
        "adversarial": {
            "pass_rate": round(adversarial.pass_rate, 4),
            "passed": adversarial.passed,
            "violations": [
                {"case": v.case_id, "kind": v.kind, "detail": v.detail}
                for v in adversarial.violations
            ],
        },
        "judge_model": baseline.judge_model,
        "judge_temperature": baseline.judge_temperature,
        "recorded_at": baseline.recorded_at,
        "git_sha": baseline.git_sha,
    }


def build_summary(metrics: dict) -> str:
    g = metrics["gate"]
    lines = [
        f"## Atlas eval gate — {'✅ PASS' if g['passed'] else '❌ FAIL'}",
        "",
        f"Golden samples: {metrics['n_samples']} · judge: `{metrics['judge_model']}` (temp "
        f"{metrics['judge_temperature']})",
        "",
        "| Metric | Score | Floor | Baseline | Gating |",
        "|---|---|---|---|---|",
    ]
    thr = metrics["thresholds"]
    for name, score in metrics["scores"].items():
        t = thr.get(name, {})
        gating = "no" if t.get("report_only", True) else "**yes**"
        floor = "—" if t.get("floor") is None else f"{t['floor']:.3f}"
        base = "—" if t.get("baseline") is None else f"{t['baseline']:.3f}"
        lines.append(f"| {name} | {score:.3f} | {floor} | {base} | {gating} |")
    adv = metrics["adversarial"]
    lines += [
        "",
        f"Adversarial pass-rate: **{adv['pass_rate']:.3f}** "
        f"({'PASS' if adv['passed'] else 'FAIL'}, 0-tolerance) — "
        f"{len(adv['violations'])} violation(s)",
    ]
    if not g["passed"]:
        lines += ["", "### Gate failures", *[f"- {f}" for f in g["failures"]]]
    return "\n".join(lines) + "\n"


def write_report(
    out_dir: Path, result, metric_report: MetricReport, adversarial: AdversarialReport,
    baseline: Baseline,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics = build_metrics(result, metric_report, adversarial, baseline)
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    (out_dir / "summary.md").write_text(build_summary(metrics))
    return metrics
