# Atlas P1 corpus + fixtures (D1/D2) and test fixtures (D3/D4/D7)

The Atlas knowledge base is a **two-layer corpus** (ADR-0004) plus small authored
fixture sets. This directory holds the data the RAG engine ingests; the test-only
fixtures (D3 shim aside) live under `src/test/resources/fixtures/`.

```
corpus/
  layer1/                # D1 — RAG substrate (real finance text)
    manifest.json        #   pins the FinanceBench subset + clearance + provenance
    financebench_id_*.txt#   committed evidence snippets (verbatim figures)
  layer2/                # D2 — authored AML/compliance overlay (Northwind story)
    l2-*.md              #   Markdown + YAML front-matter (clearance, doc_id, …)
  scripts/
    fetch_layer1.py      #   throwaway HF prep/refresh helper (NOT used at runtime/CI)
../../test/resources/fixtures/
  dev (../../main/resources/dev/clearance-users.json)  # D3 — dev user→clearance shim
  negative_access.json   # D4 — negative-access golden set (RBAC hard gate)
  poisoned/              # D7 — prompt-injection fixtures + expectations.json
```

## Layer 1 (D1) — FinanceBench
- **Source:** `PatronusAI/financebench` (Hugging Face). **License: CC-BY-NC-4.0**
  (non-commercial) — acceptable for this portfolio; raw EDGAR (public domain) is the
  commercial-clean fallback (ADR-0004/0017).
- **Form:** committed **evidence snippets** (the dataset's `evidence_text`, lightly
  whitespace-cleaned, figures preserved), not full 10-K PDFs — deterministic, offline,
  cheap to embed, and aligned with the P2 golden eval set (ADR-0020).
- **Clearance:** real SEC filings are public, so financial-statement excerpts are
  `public`; interpretive MD&A/narrative excerpts are `analyst` (gives Layer-1 a
  public↔analyst boundary; the full gradient lives in Layer 2).
- **Refresh/extend:** `python layer1/../scripts/fetch_layer1.py --check|--write`.

## Layer 2 (D2) — authored AML/compliance overlay
~12 synthetic narrative docs centered on the **Northwind Trading LLC** account (the
forcing story), tagged across all four clearance levels (`public` < `analyst` <
`compliance` < `restricted`). The restricted set (draft SAR, OFAC screening, EDD,
investigation summary) carries **synthetic PII** for the P3 redaction work. All
identifiers are fake test data.

## Fixtures
- **D3** (`src/main/resources/dev/clearance-users.json`) — P1-only dev user→clearance
  shim (ADR-0016); active only under the `local`/test profile.
- **D4** (`fixtures/negative_access.json`) — negative-access golden cases; the P1 hard
  gate (0 cross-clearance leaks).
- **D7** (`fixtures/poisoned/`) — prompt-injection docs + `expectations.json` (LLM01).

`FixtureCatalogTest` validates the integrity of all of the above on every build.
