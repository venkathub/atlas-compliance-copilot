"""Roll back an MLflow model's ``@champion`` to the prior version (P7 Task 6, ADR-0079).

GPU-free, laptop-side. Re-points ``@champion`` to ``@previous_champion`` (the last good version)
and swaps the outgoing champion into ``@previous_champion`` so the rollback is itself reversible.
Because the router resolves ``@champion`` indirectly, the rollback takes effect on the next
resolution — no redeploy. Run after the MLflow service is up:

    docker compose -f infra/docker-compose.yml up -d mlflow
    MLFLOW_TRACKING_URI=http://localhost:5000 \
        uv run --directory training --group train python scripts/rollback.py

See docs/RUNBOOK.md (rollback section). Exits non-zero if there is nothing to roll back to.
"""

from __future__ import annotations

import argparse

REGISTERED_NAME = "atlas-citation-adapter"


def main(argv: list[str] | None = None) -> int:
    from atlas_training.tracking import MlflowRegistry, TrackingError, rollback

    ap = argparse.ArgumentParser(description="Roll back an MLflow model's @champion alias.")
    ap.add_argument("--name", default=REGISTERED_NAME, help="registered model name")
    args = ap.parse_args(argv)

    try:
        outcome = rollback(MlflowRegistry(), args.name)
    except TrackingError as exc:
        print(f"ROLLBACK FAILED: {exc}")
        return 1
    print(
        f"rolled back {args.name}: @champion -> v{outcome.champion} "
        f"(outgoing v{outcome.previous} -> @previous_champion)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
