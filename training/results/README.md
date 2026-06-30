# training/results — base-vs-FT evidence (committed)

These artifacts are produced by the **episodic GPU run** (`scripts/run_episodic.py`, P6 Task 11)
and committed as the phase's evidence — the same discipline as `infra/bench/results`:

| File | Produced by | Contents |
|---|---|---|
| `base.json` | `infer.generate` (base) + `score_outputs` | base model id, scores, raw golden/refusal outputs |
| `ft.json` | `infer.generate` (base+adapter) + `score_outputs` | FT (HF) source id, scores, raw outputs |
| `cost.json` | `cost.CostMeter` | per-run training cost (rate × wall-clock) |
| `comparison.json` | `report.build_comparison` | per-metric `{base, ft, delta}` (the P7-gate schema) |
| `COMPARISON.md` | `report.comparison_markdown` | headline base-vs-FT table |

> **Status: PLACEHOLDER.** The committed `comparison.json` / `COMPARISON.md` below are stubs with
> `null` metrics and `status: "placeholder"`. The real numbers land when the episodic run executes
> on the L4 (see `docs/RUNBOOK.md` §P6). No fabricated metrics are committed.
