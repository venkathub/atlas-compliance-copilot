"""One-shot, seeded model-quality DRIFT emitter (P7 Task 10, D7/ADR-0081).

Pushes a **version-tagged** degraded eval score + its registered baseline to the Pushgateway so the
``AtlasModelQualityDrift`` Prometheus rule fires — the honest, minimal demonstration of the
drift-alert plumbing for a registered model version (R6/R7). Deliberately simple: a
threshold-vs-registered-baseline check with a ``for:`` window; the windowed statistical-test upgrade
(PSI/KS/CUSUM) is future work (P7_SPEC §8/W5), NOT a production drift service.

Stdlib-only (urllib), mirroring ``atlas_evals.report.push_to_prometheus``: no prometheus_client dep,
so it stays CI-light and infra-free unless a Pushgateway URL is supplied.

Metrics emitted (both version-tagged, so the rule matches on ``(metric, model_version)`` and never
collides with the gate's unversioned ``atlas_eval_metric_score``):
  * ``atlas_eval_metric_score{metric, model_version}``       — the (degraded) current score
  * ``atlas_model_quality_baseline{metric, model_version}``  — the registered last-good baseline
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable

DEFAULT_JOB = "atlas_model_drift"


def drift_exposition(metric: str, model_version: str, score: float, baseline: float) -> str:
    """Prometheus exposition text for a version-tagged score + its baseline (pure, unit-tested)."""
    if not metric or not model_version:
        raise ValueError("drift_exposition requires non-empty metric and model_version")
    labels = f'{{metric="{metric}",model_version="{model_version}"}}'
    return (
        "# TYPE atlas_eval_metric_score gauge\n"
        f"atlas_eval_metric_score{labels} {float(score)}\n"
        "# TYPE atlas_model_quality_baseline gauge\n"
        f"atlas_model_quality_baseline{labels} {float(baseline)}\n"
    )


def drop(score: float, baseline: float) -> float:
    """The regression the rule keys on: baseline − score (positive == a drop below baseline)."""
    return round(float(baseline) - float(score), 6)


def push_drift(
    text: str,
    gateway_url: str,
    *,
    job: str = DEFAULT_JOB,
    opener: Callable | None = None,
) -> None:
    """PUT the exposition text to a Pushgateway job group (replaces the group's series).

    ``opener`` is injectable for tests (defaults to urllib); real use needs only the gateway URL.
    """
    import urllib.request

    url = gateway_url.rstrip("/") + f"/metrics/job/{job}"
    req = urllib.request.Request(url, data=text.encode("utf-8"), method="PUT")
    req.add_header("Content-Type", "text/plain")
    _open = opener or (lambda r: urllib.request.urlopen(r, timeout=10))  # noqa: S310
    resp = _open(req)
    close = getattr(resp, "close", None)
    if callable(close):
        close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="atlas_evals.drift",
        description="Seed a one-shot, version-tagged model-quality drift sample (P7 D7/ADR-0081)",
    )
    ap.add_argument("--model-version", required=True, help="registered model version (drift label)")
    ap.add_argument("--metric", default="faithfulness", help="metric name (default: faithfulness)")
    ap.add_argument("--score", type=float, required=True, help="the (degraded) current score")
    ap.add_argument("--baseline", type=float, required=True, help="registered last-good baseline")
    ap.add_argument("--gateway", default=None, help="Pushgateway URL (else PUSHGATEWAY_URL env)")
    ap.add_argument("--job", default=DEFAULT_JOB)
    args = ap.parse_args(argv)

    import os

    gateway = args.gateway or os.environ.get("PUSHGATEWAY_URL")
    text = drift_exposition(args.metric, args.model_version, args.score, args.baseline)
    d = drop(args.score, args.baseline)
    seeded_at = int(time.time())
    print(
        f"drift seed: {args.metric} v={args.model_version} score={args.score} "
        f"baseline={args.baseline} drop={d:+.3f} (rule fires when drop > 0.05)"
    )
    if not gateway:
        print("PUSHGATEWAY_URL not set — printing exposition only (dry run):")
        print(text)
        return 0
    push_drift(text, gateway, job=args.job)
    print(f"pushed to {gateway} (job={args.job}) at epoch {seeded_at} — watch the drift alert")
    return 0


if __name__ == "__main__":
    sys.exit(main())
