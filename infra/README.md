# infra (Docker · CI)

Local + deployment plumbing for Atlas.

## Local stack (P0 · delivered)
- `docker-compose.yml` — **Postgres+pgvector** (`pg16`) and **Redis** (`7-alpine`), **digest-pinned**, healthchecked.
- `db/init/01-extensions.sql` — enables `vector` + `pg_trgm` (idempotent).
- `Makefile` — operator targets.

## Observability stack (P2 · delivered)
Added to the same `docker-compose.yml` (all **digest-pinned**):

| Service | Image | Host port | Purpose |
|---|---|---|---|
| `langfuse-web` | `langfuse/langfuse:3` | `${LANGFUSE_PORT}` (3000) | Trace UI + OTLP ingest (`/api/public/otel`) + eval datasets |
| `langfuse-worker` | `langfuse/langfuse-worker:3` | — | Async ingestion/processing |
| `clickhouse` | `clickhouse/clickhouse-server:24.8` | — (internal) | Langfuse analytics store |
| `minio` | `minio/minio` | — (internal) | Langfuse S3 event/blob store (`langfuse` bucket auto-created) |
| `prometheus` | `prom/prometheus:v3.4.1` | `${PROMETHEUS_PORT}` (9090) | Scrapes rag-engine `/actuator/prometheus` |
| `grafana` | `grafana/grafana:11.6.1` | `${GRAFANA_PORT}` (3001) | Eval-score / latency / trace-volume dashboard |

- Langfuse v3 **reuses** `atlas-postgres` (separate `langfuse` db, created by
  `db/init/02-langfuse-db.sql`) and `atlas-redis` (db index 0); only ClickHouse + MinIO are new
  containers (owner-confirmed footprint, D-P2-5).
- Langfuse is **headless-bootstrapped** via `LANGFUSE_INIT_*` — `make up` creates the
  `atlas`/`atlas-rag` project and wires the `.env` API keys; no manual first-run setup.
- Prometheus + Grafana config live as **repo files** under `infra/prometheus/` and
  `infra/grafana/`; `make up` **seeds them into named volumes** (see Snap-Docker note) rather than
  bind-mounting. Grafana's Prometheus datasource + the `Atlas — Eval & Observability (P2)` dashboard
  are auto-provisioned.

```bash
make -C infra up       # start, wait for healthy, apply pgvector + langfuse init, seed obs config
make -C infra health   # container health + pgvector version + redis PONG + langfuse/grafana/prometheus
make -C infra down      # stop (keeps data volumes)
make -C infra clean     # stop + delete data + config volumes
make -C infra psql      # psql shell into atlas-postgres
make -C infra ps|logs   # status / follow logs
make -C infra gpu-up    # resume Cloud Ollama GPU + discover OLLAMA_BASE_URL + arm watchdog
make -C infra gpu-down  # GUARANTEED pause + cancel watchdog
make -C infra gpu-test  # unit tests for the fail-safe pause path
```

The **GPU lifecycle helper** lives in `infra/gpu/` (stdlib-only Python, ADR-0029) — see
`infra/gpu/README.md`. It enforces ADR-0006 cost discipline: resume → health-poll →
discover the fresh `OLLAMA_BASE_URL` → run → **guaranteed pause** (`finally`/trap) + an
idle-timeout watchdog, so the GPU is never left billing.

Config comes from the repo-root `.env` (see `.env.example`). Defaults: Postgres on
`:5432` (db/user `atlas`), Redis on `:6379`, Langfuse on `:3000`, Grafana on `:3001`,
Prometheus on `:9090`.

## Snap-Docker confinement (important)
This host runs **Canonical's snap Docker**, whose binaries are AppArmor-confined and
**cannot read files under `/data`** (our workspace lives outside `$HOME`). Verified:
a bind mount of `/data/...` appears **empty** in-container, and `docker compose -f
/data/...yml` fails with *no such file or directory*.

We therefore **never hand a `/data` path to a snap docker binary**:
- the compose file is **piped via stdin** (`cat docker-compose.yml | docker compose -f -`),
- config is passed through **exported env vars** (not `--env-file`),
- DB init SQL is streamed via **`docker exec` stdin** (not a bind mount),
- Prometheus/Grafana config is **streamed into named volumes** (`make seed-config`: `tar`/`cat`
  the repo files on the host and pipe into a throwaway `busybox` — never a `/data` bind mount),
- data persists in **named volumes** (not host binds).

Images are kept **stock** (no custom build) so the upstream **multi-arch** manifest is
preserved for the Oracle Ampere A1 (arm64) prod target. Rationale recorded as an ADR
in `docs/DECISIONS.md`.

## Coming later in P0
- Multi-arch (amd64 + arm64) image builds. *(Increment 4)*
- GitHub Actions CI + supply-chain scanning (gitleaks / Trivy / Syft SBOM). *(Increment 4)*
