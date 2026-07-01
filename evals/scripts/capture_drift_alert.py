"""Capture the fired AtlasModelQualityDrift alert as committed evidence (P7 Task 10, D7/ADR-0081).

Opt-in / live: run after seeding the drift sample (`python -m atlas_evals.drift ...`) against a
running observability stack (Prometheus + Pushgateway + Alertmanager). Polls Alertmanager for the
fired `AtlasModelQualityDrift` alert, computes the **lead-time** (fire time − seed time), and writes
`evals/report/drift-alert.json` — the committed one-shot drift artifact.

Stdlib only (urllib). NOT run in CI (needs the live stack). The Alertmanager receiver stays the
documented no-op stub (ADR-0063); the demo captures the *fired* alert, not an external page.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

ALERTNAME = "AtlasModelQualityDrift"
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "report" / "drift-alert.json"


def _get_json(url: str, timeout_s: float = 10.0) -> object:
    with urllib.request.urlopen(url, timeout=timeout_s) as resp:  # noqa: S310
        return json.loads(resp.read())


def fetch_firing(alertmanager_url: str) -> list[dict]:
    """Return the currently-firing AtlasModelQualityDrift alerts from Alertmanager (v2 API)."""
    url = alertmanager_url.rstrip("/") + "/api/v2/alerts?active=true&silenced=false&inhibited=false"
    alerts = _get_json(url)
    out = []
    for a in alerts if isinstance(alerts, list) else []:
        if a.get("labels", {}).get("alertname") == ALERTNAME:
            out.append(a)
    return out


def poll(alertmanager_url: str, *, seeded_at: float, timeout_s: float, interval_s: float) -> dict:
    """Poll until the alert fires or the timeout elapses. Returns the capture record."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        firing = fetch_firing(alertmanager_url)
        if firing:
            fired_at = time.time()
            return {
                "alertname": ALERTNAME,
                "captured_at": int(fired_at),
                "seeded_at": int(seeded_at),
                "lead_time_seconds": round(fired_at - seeded_at, 1),
                "alerts": firing,
            }
        time.sleep(interval_s)
    raise SystemExit(f"{ALERTNAME} did not fire within {timeout_s:.0f}s — is the stack up/seeded?")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Capture the fired model-drift alert (P7).")
    ap.add_argument(
        "--alertmanager",
        default=os.environ.get("ATLAS_ALERTMANAGER_URL", "http://localhost:9093"),
    )
    ap.add_argument("--seeded-at", type=float, default=time.time(),
                    help="epoch seconds when the drift was seeded (for lead-time)")
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args(argv)

    record = poll(args.alertmanager, seeded_at=args.seeded_at,
                  timeout_s=args.timeout, interval_s=args.interval)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2) + "\n")
    print(f"captured {ALERTNAME}: lead-time {record['lead_time_seconds']}s → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
