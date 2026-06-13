# infra (Docker · CI)

Local + deployment plumbing for Atlas.

## Local stack (P0 · delivered)
- `docker-compose.yml` — **Postgres+pgvector** (`pg16`) and **Redis** (`7-alpine`), **digest-pinned**, healthchecked.
- `db/init/01-extensions.sql` — enables `vector` + `pg_trgm` (idempotent).
- `Makefile` — operator targets.

```bash
make -C infra up       # start, wait for healthy, apply pgvector init
make -C infra health   # container health + pgvector version + redis PONG
make -C infra down      # stop (keeps data volumes)
make -C infra clean     # stop + delete data volumes
make -C infra psql      # psql shell into atlas-postgres
make -C infra ps|logs   # status / follow logs
```

Config comes from the repo-root `.env` (see `.env.example`). Defaults: Postgres on
`:5432` (db/user `atlas`), Redis on `:6379`.

## Snap-Docker confinement (important)
This host runs **Canonical's snap Docker**, whose binaries are AppArmor-confined and
**cannot read files under `/data`** (our workspace lives outside `$HOME`). Verified:
a bind mount of `/data/...` appears **empty** in-container, and `docker compose -f
/data/...yml` fails with *no such file or directory*.

We therefore **never hand a `/data` path to a snap docker binary**:
- the compose file is **piped via stdin** (`cat docker-compose.yml | docker compose -f -`),
- config is passed through **exported env vars** (not `--env-file`),
- DB init SQL is streamed via **`docker exec` stdin** (not a bind mount),
- data persists in **named volumes** (not host binds).

Images are kept **stock** (no custom build) so the upstream **multi-arch** manifest is
preserved for the Oracle Ampere A1 (arm64) prod target. Rationale recorded as an ADR
in `docs/DECISIONS.md`.

## Coming later in P0
- Multi-arch (amd64 + arm64) image builds. *(Increment 4)*
- GitHub Actions CI + supply-chain scanning (gitleaks / Trivy / Syft SBOM). *(Increment 4)*
