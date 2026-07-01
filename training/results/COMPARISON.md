# Atlas P6 — base vs fine-tuned (QLoRA) comparison

Candidate **hf://venkat2393/atlas-citation-adapter** vs base **Qwen/Qwen2.5-7B-Instruct** over 30 eval cases.

### Metrics (candidate Δ vs base)

| Metric | base | ft | Δ | P7 target (reported, not gated in P6) |
|---|---|---|---|---|
| faithfulness | 0.7763 | 0.6742 | -0.1021 | FT ≥ base − 0.05 (no-regression band, baseline floor 0.656) |
| format_validity | 0.0000 | 0.9545 | +0.9545 | FT ≥ 0.95 |
| refusal_correctness | 0.3750 | 0.3750 | +0.0000 | FT ≥ base |

### Statistical rigor (report-only, not gated — D8/ADR-0082)

Method: **paired_bootstrap_10k** CIs; significance **wilcoxon+mcnemar** (Wilcoxon = continuous faithfulness, McNemar = binary format/refusal). `significant` ⇔ the 95% CI excludes 0.

| Metric | Δ | 95% CI (Δ) | test | p-value | significant |
|---|---|---|---|---|---|
| format_validity | +0.9545 | [+0.8636, +1.0000] | mcnemar | 0.0000 | yes |
| refusal_correctness | +0.0000 | [+0.0000, +0.0000] | mcnemar | 1.0000 | no |

### Serving cost/latency per request (same GPU: L4)

| Side | cost_units/req | latency p50 (ms) | latency p95 (ms) |
|---|---|---|---|
| base | 0.177224 | 15190.6 | 15190.6 |
| ft | 0.036938 | 3166.1 | 3166.1 |

**Cost/req Δ:** -79.16% vs base (promotion band ≤ 10%, ADR-0077; p95 latency report-only).

**Training cost:** 44.8663 INR (3845.681s wall-clock @ 42.0/hr).

### Provenance

- dataset size: 30
- base model: Qwen/Qwen2.5-7B-Instruct
- ft adapter: hf://venkat2393/atlas-citation-adapter
- git: a696108
- recorded: 2026-07-01T11:24:04.511450+00:00
