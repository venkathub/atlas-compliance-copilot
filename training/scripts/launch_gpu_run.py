"""Laptop-side launcher: create a JarvisLabs GPU that runs the P6 pipeline unattended (Task 11).
"""
# ruff: noqa: E501 — this module embeds a bash boot script whose line length is bash's concern.

from __future__ import annotations

import argparse
import os
import sys

REPO_URL = "https://github.com/venkathub/atlas-compliance-copilot.git"
DEFAULT_BRANCH = "docs/p6-p7-finetuning-mlops-roadmap"

# Boot script template. Tokens (@@NAME@@) are replaced in Python so bash ${}/$() are untouched.
# The heavy pipeline is backgrounded (nohup) so the JarvisLabs init returns fast; it logs to
# /var/log/atlas-train.log on the box and lands the adapter + results/ on the HF Hub.
_BOOT = r"""#!/bin/bash
set -u
export HOME=/root
export PATH=/usr/local/bin:/usr/bin:/bin:/opt/conda/bin:$HOME/.local/bin:$HOME/.cargo/bin:$PATH
cat > /root/atlas_run.sh <<'RUNEOF'
#!/bin/bash
set -x
exec > /var/log/atlas-train.log 2>&1
export HOME=/root
export PATH=/usr/local/bin:/usr/bin:/bin:/opt/conda/bin:$HOME/.local/bin:$HOME/.cargo/bin:$PATH
export OLLAMA_HOST=0.0.0.0:11434
command -v ollama >/dev/null 2>&1 || (curl -fsSL https://ollama.com/install.sh | sh)
pgrep -x ollama >/dev/null 2>&1 || (nohup ollama serve >/var/log/ollama.log 2>&1 &)
for i in $(seq 1 30); do curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break; sleep 2; done
ollama pull @@JUDGE_MODEL@@
ollama pull nomic-embed-text
command -v uv >/dev/null 2>&1 || (curl -LsSf https://astral.sh/uv/install.sh | sh)
rm -rf /root/atlas
git clone --branch @@BRANCH@@ --depth 1 @@REPO_URL@@ /root/atlas
cd /root/atlas/training
cat > .env <<'ENVEOF'
HF_TOKEN=@@HF_TOKEN@@
ATLAS_HF_ADAPTER_REPO=@@HF_REPO@@
HF_PRIVATE=@@HF_PRIVATE@@
ATLAS_GPU_COST_PER_HOUR=@@COST_RATE@@
ATLAS_GPU_COST_CURRENCY=@@COST_CCY@@
ATLAS_EVAL_JUDGE_MODEL=@@JUDGE_MODEL@@
ATLAS_EVAL_JUDGE_BASE_URL=http://localhost:11434
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=nomic-embed-text
ATLAS_SYNTH_GENERATOR_MODEL=@@TEACHER_MODEL@@
ATLAS_SYNTH_BASE_URL=http://localhost:11434
ENVEOF
uv sync --group train
timeout @@TIMEOUT@@ uv run --env-file .env --group train python scripts/run_episodic.py \
    --config @@CONFIG@@ @@EXTRA_ARGS@@ --hf-only --upload-results "@@HF_REPO@@"
echo "[atlas] pipeline finished rc=$?"
RUNEOF
chmod +x /root/atlas_run.sh
nohup bash /root/atlas_run.sh >/var/log/atlas-boot.log 2>&1 &
echo "[atlas] P6 training launched in background; results -> HF repo @@HF_REPO@@"
"""


def _require(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        print(f"error: {name} is unset (load your .env)", file=sys.stderr)
        raise SystemExit(2)
    return val


def build_boot_script(config: str, branch: str, timeout_s: int, *, generate: int,
                      teacher_model: str) -> str:
    extra = f"--generate-data {generate}" if generate > 0 else ""
    repl = {
        "@@BRANCH@@": branch,
        "@@REPO_URL@@": REPO_URL,
        "@@CONFIG@@": config,
        "@@TIMEOUT@@": str(timeout_s),
        "@@EXTRA_ARGS@@": extra,
        "@@TEACHER_MODEL@@": teacher_model,
        "@@HF_TOKEN@@": _require("HF_TOKEN"),
        "@@HF_REPO@@": _require("ATLAS_HF_ADAPTER_REPO"),
        "@@HF_PRIVATE@@": os.environ.get("HF_PRIVATE", "true"),
        "@@COST_RATE@@": _require("ATLAS_GPU_COST_PER_HOUR"),
        "@@COST_CCY@@": os.environ.get("ATLAS_GPU_COST_CURRENCY", "INR"),
        "@@JUDGE_MODEL@@": os.environ.get("ATLAS_EVAL_JUDGE_MODEL", "llama3.1:8b"),
    }
    script = _BOOT
    for k, v in repl.items():
        script = script.replace(k, v)
    return script


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Launch an unattended P6 GPU run (boot-script).")
    ap.add_argument("--config", default="configs/qlora_qwen3b_smoke.yaml")
    ap.add_argument("--branch", default=DEFAULT_BRANCH)
    ap.add_argument("--timeout", type=int, default=7200, help="box-side hard cap (s) on the run")
    ap.add_argument("--generate", type=int, default=0, metavar="ANSWERS_PER_DOC",
                    help="generate a trusted-corpus dataset (N answers/doc) via the local teacher")
    ap.add_argument("--teacher-model", default=os.environ.get("ATLAS_EVAL_JUDGE_MODEL",
                                                              "llama3.1:8b"),
                    help="local Ollama model used to generate the dataset")
    ap.add_argument("--destroy", metavar="MACHINE_ID", help="destroy an instance and exit")
    args = ap.parse_args(argv)

    from pathlib import Path

    # atlas_gpu (the jarvislabs SDK seam) lives in infra/gpu — add it to the path.
    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root / "infra" / "gpu"))
    from atlas_gpu.providers import make_provider

    provider = make_provider()

    if args.destroy:
        provider.instance_id = args.destroy
        provider.destroy()
        print(f"destroyed instance {args.destroy}")
        return 0

    # contains secrets — never print
    boot = build_boot_script(args.config, args.branch, args.timeout,
                             generate=args.generate, teacher_model=args.teacher_model)
    script_id = provider.client.add_script(script=boot, name="atlas-p6-train")
    info = provider.client.create_instance(
        gpu_type=provider.create_spec.gpu_type,
        num_gpus=provider.create_spec.num_gpus,
        template=provider.create_spec.template,
        storage=provider.create_spec.storage_gb,
        name="atlas-p6-train",
        http_ports="11434",
        script_id=script_id,
        region=provider.create_spec.region,
    )
    mid = info.machine_id
    repo = os.environ.get("ATLAS_HF_ADAPTER_REPO", "<repo>")
    print("=" * 64)
    print(f"machine_id   : {mid}")
    print(f"config       : {args.config}")
    print(f"results land : https://huggingface.co/{repo}/tree/main/results  (poll this)")
    print("box log      : /var/log/atlas-train.log (on the instance)")
    print("track/destroy (run from infra/gpu with .env):")
    print(f"  python ../../training/scripts/launch_gpu_run.py --destroy {mid}")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
