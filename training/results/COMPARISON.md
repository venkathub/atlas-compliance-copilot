# Atlas P6 — base vs fine-tuned (QLoRA) comparison

> **PLACEHOLDER — pending the episodic GPU run (Task 11).**
> This file is overwritten by `scripts/run_episodic.py` on the JarvisLabs L4. Until then the
> numbers below are intentionally blank; **no fabricated metrics are committed** (CLAUDE.md honesty).

### Metrics (candidate Δ vs base)

| Metric | base | ft | Δ | P7 target (reported, not gated in P6) |
|---|---|---|---|---|
| faithfulness | — | — | — | FT ≥ base − 0.05 (no-regression band, baseline floor 0.656) |
| format_validity | — | — | — | FT ≥ 0.95 |
| refusal_correctness | — | — | — | FT ≥ base |

### Provenance
- base model: Qwen/Qwen2.5-7B-Instruct
- ft adapter: _pending HF push (`hf://<repo>@<rev>`)_
- training cost: _pending_
- recorded: _pending_

Run it: see `docs/RUNBOOK.md` §12 ("Fine-tuning — P6: episodic train + benchmark").
