# Atlas P6 — base vs fine-tuned (QLoRA) comparison

Candidate **hf://venkat2393/atlas-citation-adapter@386e3d3b9a1742e1ce631ae47dab799f32247c93** vs base **Qwen/Qwen2.5-7B-Instruct** over 30 eval cases.

### Metrics (candidate Δ vs base)

| Metric | base | ft | Δ | P7 target (reported, not gated in P6) |
|---|---|---|---|---|
| faithfulness | 0.7870 | 0.6780 | -0.1090 | FT ≥ base − 0.05 (no-regression band, baseline floor 0.656) |
| format_validity | 0.0000 | 0.9545 | +0.9545 | FT ≥ 0.95 |
| refusal_correctness | 0.3750 | 0.3750 | +0.0000 | FT ≥ base |

**Training cost:** 49.8986 INR (4277.019s wall-clock @ 42.0/hr).

### Provenance

- dataset size: 30
- base model: Qwen/Qwen2.5-7B-Instruct
- ft adapter: hf://venkat2393/atlas-citation-adapter@386e3d3b9a1742e1ce631ae47dab799f32247c93
- git: 9db1409
- recorded: 2026-06-30T15:57:50.098720+00:00
