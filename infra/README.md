# infra (Docker · CI)

Local + deployment plumbing for Atlas.

**P0 scope:**
- `docker-compose.yml` — Postgres+pgvector and Redis (digest-pinned, healthchecked). *(Increment 2)*
- `db/init/` — pgvector extension bootstrap. *(Increment 2)*
- `Makefile` — `up` / `down` / `health` targets. *(Increment 2)*
- Multi-arch (amd64 + arm64) image builds for the Oracle Ampere A1 prod target. *(Increment 4)*
- GitHub Actions CI + supply-chain scanning (gitleaks / Trivy / Syft SBOM). *(Increment 4)*

Currently a placeholder — files land in P0 Increments 2 and 4.
