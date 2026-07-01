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

> **Status: committed (real run, 2026-06-30).** `comparison.json` / `COMPARISON.md` are the
> evidence from the episodic L4 run (gpt-oss:20b teacher, bake-in). Headline: **format-validity
> 0.000 → 0.955** (the FT guarantees the `[doc:ID]` schema the base cannot produce unprompted).
> faithfulness −0.109 / refusal +0.000 (ft above the 0.656 floor). A two-teacher experiment
> (qwen2.5:14b vs gpt-oss:20b) showed the format win is **robust across teachers** and the
> faithfulness dip is a **structural trade-off of concise cited answers**, not a teacher-quality
> gap (qwen2.5:14b was marginally better, −0.062) — see `docs/PORTFOLIO.md`.
