#!/usr/bin/env python3
"""
Throwaway corpus-prep helper (NOT a runtime dependency, NOT run in CI).

Regenerates / extends the Layer-1 (D1) FinanceBench snippet corpus that Atlas
ingests as its RAG substrate. The committed `.txt` files next to this script are
faithful (lightly whitespace-/table-cleaned for readability) `evidence_text`
excerpts from PatronusAI/financebench (CC-BY-NC-4.0, public SEC-filing text),
pinned by `manifest.json`. Figures are preserved exactly. They are committed so
tests and ingestion are deterministic and offline; this script documents how they
were produced and lets you refresh or add documents. Note: `--write` overwrites
with the raw (uncleaned) HF `evidence_text`.

The app NEVER calls this — Atlas talks only to pgvector + Ollama at runtime
(ADR-0017: the HF corpus is download-time data, never a runtime dependency).

Usage:
    python fetch_layer1.py --check     # verify each manifest entry resolves on HF
    python fetch_layer1.py --write     # (re)write <financebench_id>.txt from HF

Requires network access to the public HF datasets-server (no auth/token).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAYER1 = HERE.parent / "layer1"
MANIFEST = LAYER1 / "manifest.json"
ROWS_API = (
    "https://datasets-server.huggingface.co/rows"
    "?dataset=PatronusAI/financebench&config=default&split=train"
)


def _fetch_row(financebench_id: str) -> dict | None:
    """Linear scan of the 150-row split for the matching financebench_id."""
    for offset in range(0, 150, 50):
        url = f"{ROWS_API}&offset={offset}&length=50"
        with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310
            payload = json.load(resp)
        for row in payload["rows"]:
            if row["row"]["financebench_id"] == financebench_id:
                return row["row"]
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="verify entries resolve on HF")
    ap.add_argument("--write", action="store_true", help="(re)write .txt snippet files")
    args = ap.parse_args()
    if not (args.check or args.write):
        ap.print_help()
        return 2

    manifest = json.loads(MANIFEST.read_text())
    missing = 0
    for doc in manifest["documents"]:
        fid = doc["financebench_id"]
        row = _fetch_row(fid)
        if row is None:
            print(f"MISSING on HF: {fid}", file=sys.stderr)
            missing += 1
            continue
        if args.write:
            evidence = row["evidence"][0]["evidence_text"].strip()
            (LAYER1 / doc["file"]).write_text(evidence + "\n")
            print(f"wrote {doc['file']}  ({len(evidence)} chars)")
        else:
            print(f"ok  {fid}  -> {doc['doc_name']}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
