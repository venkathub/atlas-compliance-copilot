"""P7 episodic orchestrator (laptop-side): launch → poll HF → retrieve → GUARANTEED teardown.

Drives the ONE bounded GPU window that produces P7's cost-extended base-vs-FT evidence, reusing the
proven P6 launcher (`launch_gpu_run.build_boot_script`, `--benchmark-only`: reuse the committed HF
adapter, no retrain). The box self-runs `run_episodic.py` (which now emits the P7 cost/latency +
report-only CIs/significance, Task 5) and uploads `results/` to the HF repo. This orchestrator polls
HF for the fresh `results/comparison.json`, downloads it into `training/results/`, and — in a
`finally` — **destroys the instance** so a bug or timeout can never leak GPU cost (belt-and-braces
with the box watchdog, ADR-0066).

Run from the repo root with the P7 .env loaded (GPU_API_KEY, HF_TOKEN, ATLAS_HF_ADAPTER_REPO,
ATLAS_GPU_COST_PER_HOUR, …):

    uv run --directory training --group train python scripts/p7_episodic_run.py \
        --config configs/qlora_qwen7b.yaml --faithfulness -1 --timeout 5400

``--keep`` skips the destroy (debug only — you then MUST teardown manually). GPU-free itself; only
the JarvisLabs API + HF are touched here.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "training" / "results"


def _log(msg: str) -> None:
    ts = datetime.now(UTC).strftime("%H:%M:%S")
    print(f"[p7-run {ts}] {msg}", flush=True)


def _hf_comparison_recorded_at(repo: str, token: str) -> str | None:
    """Return results/comparison.json's `recorded_at` on HF, or None if absent/unreadable."""
    from huggingface_hub import hf_hub_download
    from huggingface_hub.utils import EntryNotFoundError

    try:
        path = hf_hub_download(
            repo_id=repo, filename="results/comparison.json", repo_type="model",
            token=token, force_download=True,
        )
    except (EntryNotFoundError, Exception):  # noqa: BLE001 - absent yet / transient → keep polling
        return None
    try:
        return json.loads(Path(path).read_text()).get("recorded_at")
    except Exception:  # noqa: BLE001
        return None


def _download_results(repo: str, token: str) -> None:
    from huggingface_hub import snapshot_download

    snap = snapshot_download(
        repo_id=repo, repo_type="model", token=token,
        allow_patterns=["results/*"], force_download=True,
    )
    src = Path(snap) / "results"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():
        if f.is_file():
            (RESULTS_DIR / f.name).write_bytes(f.read_bytes())
    _log(f"downloaded results/ → {RESULTS_DIR}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P7 episodic GPU run with guaranteed teardown.")
    ap.add_argument("--config", default="configs/qlora_qwen7b.yaml")
    ap.add_argument("--faithfulness", type=int, default=-1, help="RAGAS faithfulness N (-1=all)")
    ap.add_argument("--bake-in", action="store_true",
                    help="eval under the minimal system prompt (matches the committed P6 regime: "
                         "base can't cite -> format 0.0, FT cites -> ~0.95; the format-jump story)")
    ap.add_argument("--timeout", type=int, default=5400, help="box-side hard cap (s)")
    ap.add_argument("--poll-timeout", type=int, default=6000, help="laptop-side poll cap (s)")
    ap.add_argument("--poll-interval", type=int, default=60)
    ap.add_argument("--keep", action="store_true", help="do NOT destroy (debug; teardown manually)")
    args = ap.parse_args(argv)

    sys.path.insert(0, str(REPO_ROOT / "infra" / "gpu"))
    sys.path.insert(0, str(REPO_ROOT / "training" / "scripts"))
    from atlas_gpu.providers import make_provider
    from launch_gpu_run import build_boot_script

    repo = os.environ["ATLAS_HF_ADAPTER_REPO"]
    token = os.environ["HF_TOKEN"]
    branch = os.environ.get("ATLAS_BRANCH", "docs/p6-p7-finetuning-mlops-roadmap")

    launch_epoch = time.time()
    baseline_recorded = _hf_comparison_recorded_at(repo, token)
    _log(f"pre-run HF comparison recorded_at = {baseline_recorded}")

    boot = build_boot_script(
        args.config, branch, args.timeout,
        generate=0, teacher_model=os.environ.get("ATLAS_EVAL_JUDGE_MODEL", "llama3.1:8b"),
        faithfulness=args.faithfulness, benchmark_only=repo, bake_in=args.bake_in,
    )
    provider = make_provider()
    script_id = provider.client.add_script(script=boot, name="atlas-p7-bench")
    info = provider.client.create_instance(
        gpu_type=provider.create_spec.gpu_type, num_gpus=provider.create_spec.num_gpus,
        template=provider.create_spec.template, storage=provider.create_spec.storage_gb,
        name="atlas-p7-bench", http_ports="11434", script_id=script_id,
        region=provider.create_spec.region,
    )
    mid = info.machine_id
    provider.instance_id = mid
    _log(f"created instance {mid} ({provider.create_spec.gpu_type}); log:/var/log/atlas-train.log")
    _log(f"benchmark-only reuse adapter {repo}; results land at hf.co/{repo}/tree/main/results")

    ok = False
    try:
        deadline = launch_epoch + args.poll_timeout
        while time.time() < deadline:
            time.sleep(args.poll_interval)
            recorded = _hf_comparison_recorded_at(repo, token)
            if recorded and recorded != baseline_recorded:
                _log(f"NEW results detected (recorded_at={recorded}) — downloading")
                _download_results(repo, token)
                ok = True
                break
            _log(f"…still running (elapsed {int(time.time() - launch_epoch)}s) rec={recorded}")
        if not ok:
            _log(f"TIMEOUT after {args.poll_timeout}s — no fresh results; tearing down anyway")
    finally:
        if args.keep:
            _log(f"--keep set: instance {mid} LEFT RUNNING — teardown manually (cost accruing!)")
        else:
            try:
                provider.destroy()
                _log(f"destroyed instance {mid} (guaranteed teardown — cost stopped)")
            except Exception as exc:  # noqa: BLE001
                _log(f"!! DESTROY FAILED for {mid}: {exc} — destroy MANUALLY NOW to stop cost")
                raise

    if ok:
        _log("SUCCESS: cost-extended base-vs-FT evidence in training/results/. Commit it, then "
             "register+promote in MLflow (scripts/register_adapter.py → scripts/promote.py).")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
