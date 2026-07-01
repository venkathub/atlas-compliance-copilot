"""Promote an MLflow model version to production via the ``@champion`` alias (P7 Task 6, ADR-0079).

GPU-free, laptop-side. Points ``@champion`` at the given version and stashes the outgoing champion
under ``@previous_champion`` (the rollback target). The router resolves ``@champion`` indirectly
(via ``atlas.router.ft-tier-model``), never a version number — so promotion/rollback are instant.
Run after the MLflow service is up:

    docker compose -f infra/docker-compose.yml up -d mlflow
    MLFLOW_TRACKING_URI=http://localhost:5000 \
        uv run --directory training --group train python scripts/promote.py --version 3

See docs/RUNBOOK.md (rollback section). Idempotent: re-promoting the sitting champion is a no-op.
"""

from __future__ import annotations

import argparse

REGISTERED_NAME = "atlas-citation-adapter"


def main(argv: list[str] | None = None) -> int:
    from atlas_training.tracking import MlflowRegistry, promote

    ap = argparse.ArgumentParser(description="Promote an MLflow model version (@champion alias).")
    ap.add_argument("--name", default=REGISTERED_NAME, help="registered model name")
    ap.add_argument("--version", required=True, help="model version to promote to @champion")
    args = ap.parse_args(argv)

    outcome = promote(MlflowRegistry(), args.name, args.version)
    if outcome.action == "noop":
        print(f"{args.name}: v{outcome.champion} is already @champion — no change")
    else:
        prev = (
            f" (prior @champion v{outcome.previous} -> @previous_champion)"
            if outcome.previous
            else ""
        )
        print(f"promoted {args.name}: @champion -> v{outcome.champion}{prev}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
