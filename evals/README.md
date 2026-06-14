# evals (Python · RAGAS/DeepEval) — CI-gated eval & observability harness

The harness makes RAG quality **measurable and non-regressable** (CLAUDE.md: *evals before
agents*). It talks to `rag-engine` **only over HTTP** (`POST /v1/query`) — the same clean seam
the Gateway (P3) and Agents (P4) consume; it never imports Java internals.

## Layout
```
atlas_evals/
  client.py              # thin /v1/query HTTP client (clearance header + includeContexts)
  datasets/
    corpus.py            # resolves doc-ids/fixtures against the REAL corpus (no P1↔P2 drift)
    golden.py            # GoldenTuple + load_golden() + schema validation
    adversarial.py       # AdversarialCase + load_adversarial() (references P1 fixtures)
data/
  golden.jsonl           # committed golden set (versioned)
  adversarial.jsonl      # committed red-team set (references P1 fixtures by ref)
tests/                   # pytest: loaders, schema, ref-resolution, client shaping
```
> RAGAS runner + judge + cassettes (Task 6), adversarial scorer (Task 7), and the merge **gate**
> + baseline + Langfuse sync (Task 8) land in subsequent P2 commits.

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
Requires no GPU, no Ollama, no running rag-engine (datasets + loaders are pure-Python).
