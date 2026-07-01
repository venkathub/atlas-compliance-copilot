"""Base-vs-FT candidate-output generation + scoring (P6 Task 10b) — episodic, GPU window only.

`generate` loads the base model once and the base+adapter once (PEFT), producing candidate answers
over the reused eval prompts (golden + the labeled refusal subset). `score_outputs` turns those
outputs into the three comparison metrics — RAGAS **faithfulness** (LLM-judge, computed here in the
GPU window) plus the deterministic **format-validity** + **refusal-correctness** evals scorers (the
ones P7 reuses). The numbers feed `report.build_comparison`, which writes the committed evidence.

Everything here imports heavy/eval deps lazily and is marked no-cover: it runs once on the L4, not
in CI. The pure report generator (`report.py`) is the CI-tested deliverable. Candidate path is
Transformers/PEFT (ADR-0073); vLLM multi-LoRA serving is P7.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Shared decode settings for a fair base-vs-FT comparison (greedy, bounded). No temperature: with
# do_sample=False recent transformers errors on temperature=0.0.
GEN_KWARGS = {"max_new_tokens": 320, "do_sample": False}


@dataclass(frozen=True)
class Candidate:
    """One model's output for a prompt, with the doc ids it was allowed to cite."""

    case_id: str
    prompt: str
    output: str
    allowed_ids: list[str]


def build_prompt(system: str, question: str, context: str) -> str:
    """The eval prompt mirrors the SFT user turn (question + [doc:ID] context)."""
    return f"{question}\n\n{context}" if context else question


def generate(  # pragma: no cover - GPU window only
    base_model: str,
    prompts: list[str],
    *,
    adapter_path: str | None = None,
    gen_kwargs: dict | None = None,
    system: str | None = None,
) -> list[str]:
    """Generate outputs for `prompts`. With `adapter_path`, load base+LoRA (the FT candidate).

    `system` prepends a system turn — pass the SAME system prompt the model was fine-tuned with,
    or the FT never sees the citation instruction it was trained under (train/inference mismatch).
    """
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(base_model)
    model = AutoModelForCausalLM.from_pretrained(base_model, device_map="auto",
                                                 torch_dtype=torch.bfloat16)
    if adapter_path:
        model = PeftModel.from_pretrained(model, adapter_path)
    model.eval()

    outputs: list[str] = []
    for prompt in prompts:
        msgs = ([{"role": "system", "content": system}] if system else []) + \
            [{"role": "user", "content": prompt}]
        inputs = tokenizer.apply_chat_template(
            msgs, add_generation_prompt=True, return_tensors="pt", return_dict=True
        ).to(model.device)
        with torch.no_grad():
            gen = model.generate(**inputs, **(gen_kwargs or GEN_KWARGS))
        prompt_len = inputs["input_ids"].shape[1]
        text = tokenizer.decode(gen[0][prompt_len:], skip_special_tokens=True)
        outputs.append(text.strip())
    return outputs


def free_gpu() -> None:  # pragma: no cover - GPU window only
    """Release torch's cached GPU memory back to the driver so a co-located process (the Ollama
    RAGAS judge) can load on the GPU. Call after base/FT generation, before faithfulness."""
    import gc

    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
    except Exception:  # noqa: BLE001 - best-effort; never fail the run on cleanup
        pass


def score_outputs(  # pragma: no cover - GPU window only (lazy evals scorers, not in CI install)
    candidates: list[Candidate],
    refusal_cases: list,
    refusal_outputs: list[str],
    *,
    faithfulness: float | None = None,
) -> dict[str, float]:
    """Score a candidate set into {faithfulness, format_validity, refusal_correctness}.

    format-validity + refusal-correctness are deterministic (the evals scorers P7 reuses);
    `faithfulness` is the RAGAS value the episodic driver computed separately (NaN if absent —
    we never invent a number). This keeps infer.py free of the RAGAS API surface.
    """
    from atlas_evals.metrics.format_validity import score as fmt_score
    from atlas_evals.metrics.refusal import score_rate as refusal_rate

    fmt_ok = sum(1 for c in candidates if fmt_score(c.output, set(c.allowed_ids)))
    format_validity = fmt_ok / len(candidates) if candidates else 0.0

    return {
        "faithfulness": float("nan") if faithfulness is None else round(float(faithfulness), 4),
        "format_validity": round(format_validity, 4),
        "refusal_correctness": round(refusal_rate(refusal_cases, refusal_outputs), 4),
    }


def prompts_from_jsonl(path: str | Path) -> list[str]:
    """Read SFT chat rows (builder output) back into user-turn prompts for re-generation."""
    import json

    prompts: list[str] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        msgs = json.loads(line)["messages"]
        user = next(m["content"] for m in msgs if m["role"] == "user")
        prompts.append(user)
    return prompts
