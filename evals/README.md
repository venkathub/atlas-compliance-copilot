# evals (Python · RAGAS/DeepEval) — CI-gated eval & observability harness

The harness makes RAG quality **measurable and non-regressable** (CLAUDE.md: *evals before
agents*). It talks to `rag-engine` **only over HTTP** (`POST /v1/query`) — the same clean seam
the Gateway (P3) and Agents (P4) consume; it never imports Java internals.

## Layout
```
atlas_evals/
  client.py              # thin /v1/query client (+ CassettingClient for the RAG-side cassette)
  cassettes.py           # CassetteStore: record/replay/off; key=sha256(inputs); miss-fails-loud
  record.py              # live RECORD entrypoint (run in the GPU calibration session, Task 8)
  datasets/
    corpus.py            # resolves doc-ids/fixtures against the REAL corpus (no P1↔P2 drift)
    golden.py            # GoldenTuple + load_golden() + schema validation
    adversarial.py       # AdversarialCase + load_adversarial() (references P1 fixtures)
    refusal.py           # RefusalCase + load_refusal() — labeled refusal subset (P6, reused by P7)
  metrics/
    samples.py           # (golden tuple + /v1/query response) -> EvalSample (RAGAS-free)
    citation.py          # deterministic citation-resolution signal (report-only)
    ragas_runner.py      # RAGAS-free orchestration: build samples -> Scorer -> MetricReport
    ragas_scorer.py      # concrete RAGAS scorer (lazy import) + per-sample judge cassettes
    adversarial_scorer.py# binary red-team scorer (LLM07): leaked-string / above-clearance / forbidden-doc
    format_validity.py   # deterministic FT format validator: cited-answer / grounded-refusal (P6, reused by P7)
    refusal.py           # deterministic refusal-correctness scorer over a labeled subset (P6, reused by P7)
  ab.py                  # A/B two cassette sets (eval-gated reranker/sparse decision, ADR-0027)
data/
  golden.jsonl           # committed golden set (versioned)
  adversarial.jsonl      # committed red-team set (references P1 fixtures by ref)
  refusal.jsonl          # committed labeled refusal subset (out-of-context/unanswerable/out-of-clearance; P6)
  cassettes/{rag,judge}/ # committed cassettes that drive the offline gate (recorded in Task 8)
tests/                   # pytest: loaders, cassettes, client, samples, citation, runner, scorer-replay
```
> The merge **gate** + baseline + Langfuse sync (Task 8) and the adversarial scorer (Task 7) land in
> subsequent P2 commits.

## Cassette-replay gate (D-P2-1c)
The PR gate is **offline, deterministic, and free**: every LLM-dependent call is served from a
committed cassette (a **miss fails loudly** — it never silently calls a live endpoint). Two boundaries
are cassetted:
- **RAG answers** — `/v1/query` responses, keyed by `(query, clearance, topK, includeContexts, rag_fingerprint)`
  where `rag_fingerprint` = RAG/embed model tags **+ a hash of the rag-engine behaviour source**
  (prompts, guardrail, retrieval/fusion/rerank). The gate **recomputes this live from the checked-out
  code**, so a PR that changes how answers/contexts are produced → new key → **loud miss → re-record**
  (catches a RAG-behaviour regression on the PR, not just at calibration time).
- **Judge scores** — RAGAS metrics are cassetted **per sample**, keyed by
  `(judge_model, ragas_version, question, answer, contexts, ground_truth)`. Consequence: **REPLAY needs
  neither RAGAS nor a judge installed** (the gate just reads committed scores), and a changed RAG answer
  → new key → loud miss → re-record. Live computation (RECORD) runs the real judge at **temperature 0**.

Cassettes are (re)recorded by the periodic **live calibration** job (GPU on); the PR gate only replays.

## Cost-regression gate (P6, ADR-0064)
`python -m atlas_evals.cost_gate` validates the committed cost evidence (`data/gateway-baseline.json`,
produced live by `atlas_evals.cost_report`, RUNBOOK §7.4) against its reduction target: it fails if
`cost_reduction_pct < target_reduction_pct`, if `meets_target` is false, or if `cost_on_units` exceeds an
optional `max_cost_on_units` ceiling. Wired into the CI `evals-gate` job (and the `deploy` workflow's gate),
so a merge/deploy is blocked on **quality OR cost** regression. Offline + GPU-free, like the RAGAS gate.

## Datasets (committed, versioned — ADR-0028)
- **`golden.jsonl` — 22 Q/A tuples:** 12 **Layer-1** seeded from authoritative **FinanceBench**
  rows (`question`/`answer` pulled from the dataset, mapped to the 12 committed snippets) +
  10 **Layer-2** authored against the `l2-*` Northwind/AML overlay (the Priya story). Each tuple:
  `{id, layer, clearance, question, ground_truth, expected_source_docs[], source}`.
- **`adversarial.jsonl` — 10 cases:** injection / jailbreak / system-prompt-leak (reference
  `poisoned/expectations.json#answerMustNotContain`) + the 6 access-bypass cases (reference the
  `negative_access.json` cases). **Referenced, not duplicated**, so P1 and P2 can't drift.

Loading **validates every reference**: each `expected_source_docs` id must resolve to a real corpus
doc, and every adversarial fixture ref must resolve — a dangling reference fails the tests.

## Run the harness tests
```bash
uv run --directory evals --with pytest pytest -q
uvx ruff check evals
```
Requires no GPU, no Ollama, no running rag-engine (datasets, cassettes, loaders, and the
metric orchestration are pure-Python; RAGAS is a lazy dep only for live RECORD/calibration).

## Run the merge gate (offline, replays committed cassettes)
```bash
uv run --directory evals python -m atlas_evals.gate     # exit 0 = pass, non-zero blocks merge
```
Reads `data/baseline.json` + the committed `data/cassettes/`, runs RAGAS-replay + the adversarial
scorer, writes `report/metrics.json` + `report/summary.md`. **No GPU, no RAGAS install needed.**
First calibrated baseline (qwen2.5:3b RAG + llama3.1:8b judge, 22 tuples): faithfulness 0.80 /
answer_relevancy 0.70 / context_recall 0.78 gating; adversarial 1.00 (0 violations).

## Refresh the UI eval/cost snapshot (P5 admin artifact)
```bash
python evals/scripts/refresh_eval_summary.py    # writes ui/public/{eval-summary,cost-summary}.json
```
Snapshots the **real** gate outputs into two committed, camelCase JSON files the P5 UI Admin page
serves and reads (D-P5-3 / ADR-0053): it reads `report/metrics.json` (run the gate first), runs the
deterministic agent gate, and reads `data/gateway-baseline.json`. **Changes no eval logic** — it only
normalizes existing results. Re-run + commit whenever the gates are re-recorded.

## Record cassettes (live, GPU on — calibration session)
```bash
make -C infra gpu-up                      # resume + discover OLLAMA_BASE_URL (then re-source .env)
mvn -pl rag-engine spring-boot:run &      # rag-engine up + ingested
uv run --directory evals --group ragas python -m atlas_evals.record
make -C infra gpu-down                     # GUARANTEED pause
```

## Eval-through-Gateway + cost-delta (P3, R2/R3)
The SAME merge gate, with the harness pointed at the **Gateway** path (auth + route + cache +
redaction) instead of rag-engine directly — proving routing/caching/redaction never drop quality
below the floor (R2). It replays the committed cassettes (keyed by question/clearance/fingerprint,
not client path), so it is offline/GPU-free and runs in CI:
```bash
ATLAS_EVAL_THROUGH_GATEWAY=true GATEWAY_URL=http://localhost:8080 \
  uv run --directory evals python -m atlas_evals.gate
```
The **cost-delta** ("X% cheaper at equal eval score", R3) is a **live calibration job** (GPU on, not
the PR gate): it runs the golden set through the Gateway with caching+routing on vs off, reads the
per-response `cost.costUnits` (ADR-0040), and writes `data/gateway-baseline.json`:
```bash
make -C infra gpu-up && set -a && . ./.env && set +a
mvn -pl gateway spring-boot:run & mvn -pl rag-engine spring-boot:run &   # full stack + Redis up
GATEWAY_URL=http://localhost:8080 uv run --directory evals python -m atlas_evals.cost_report
make -C infra gpu-down
```
`gateway-baseline.json` ships as a placeholder until that live run populates the measured numbers
(target band: **≥30% cheaper** at equal eval score, §8.3). The pure delta math is unit-tested offline.
