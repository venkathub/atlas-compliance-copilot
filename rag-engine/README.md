# rag-engine (Spring AI)

Permission-aware retrieval core: chunking, embeddings, hybrid (HNSW dense +
`tsvector` sparse) search, reranking, inline citations, prompt-injection guardrails,
and RBAC filtering at retrieval time.

**Full engine built in P1.** In **P0** this module hosts only the **Ollama connectivity
probe** — proof that the Spring AI ↔ remote Ollama path works end-to-end (one chat
completion + one embedding via `OLLAMA_BASE_URL`). No retrieval logic yet.

## Stack
- Spring Boot 3.4.7 · Spring AI 1.0.0 (`spring-ai-starter-model-ollama`) · Java 21
- Postgres 16 + **pgvector** (vector store + RBAC metadata), schema managed by **Flyway**
- Versions centralized in the root `pom.xml` (monorepo BOM/plugin management).

## Configuration (all env-swappable — `.env` at repo root)
| Property | Env var | Default |
|---|---|---|
| `spring.ai.ollama.base-url` | `OLLAMA_BASE_URL` | `http://localhost:11434` |
| `spring.ai.ollama.chat.options.model` | `OLLAMA_CHAT_MODEL` | `qwen2.5:3b-instruct` |
| `spring.ai.ollama.embedding.options.model` | `OLLAMA_EMBED_MODEL` | `nomic-embed-text` |
| `spring.datasource.url` | `SPRING_DATASOURCE_URL` (else derived from `POSTGRES_*`) | `jdbc:postgresql://localhost:5432/atlas` |
| `spring.datasource.username` / `.password` | `POSTGRES_USER` / `POSTGRES_PASSWORD` | `atlas` / — |
| `server.port` | `RAG_ENGINE_PORT` | `8081` |

`spring.ai.ollama.init.pull-model-strategy=never` (the remote endpoint already hosts the
models) and `chat.options.keep-alive=30m` (keep the model resident to avoid GPU cold starts).

## Persistence & schema (P1)
The retrieval store is a **custom pgvector schema** (not Spring AI's stock `vector_store`
table), because the hybrid sparse `tsvector` column + the hard RBAC `clearance` predicate
aren't expressible through the stock store. Two tables, migrated by Flyway
(`src/main/resources/db/migration/V1__atlas_rag_schema.sql`):

- **`atlas_document`** — one row per source document: provenance (`source_uri`, `source_layer`),
  `clearance`, `content_sha256` + `trusted` (LLM04 ingestion integrity).
- **`atlas_chunk`** — the retrieval unit: `content`, `embedding vector(768)` (ADR-0005),
  generated `content_tsv` (full-text), `clearance` (denormalized RBAC key), `metadata` JSONB.

Indexes: `atlas_chunk_hnsw` (HNSW cosine, dense) · `atlas_chunk_tsv` (GIN, sparse) ·
`atlas_chunk_clear` (btree, RBAC pre-filter). Flyway runs automatically on app startup against
the configured datasource; `vector(768)` is fixed by ADR-0005 and must match `EMBED_DIM`.

## Run

```bash
# Unit tests only — no Docker/GPU needed:
mvn -pl rag-engine test

# Unit tests + Testcontainers ITs (schema, …) — needs Docker, no GPU (this is what CI runs):
mvn -pl rag-engine verify

# Live smoke test against the real remote Ollama (the P0 exit gate) — needs OLLAMA_BASE_URL:
set -a && . ./.env && set +a && mvn -P live -pl rag-engine verify

# 30-second demo: boot the app and hit the probe endpoint
set -a && . ./.env && set +a && mvn -pl rag-engine spring-boot:run
curl -s localhost:8081/probe/connectivity | jq      # chat reply + embeddingDim=768, ok=true
curl -s localhost:8081/actuator/health | jq         # liveness (does NOT call the GPU)
```

> **Testcontainers + modern Docker:** the ITs talk to a `pgvector/pgvector:pg16` container via
> Testcontainers. Docker daemons ≥28 reject the legacy API version that Testcontainers' bundled
> docker-java negotiates by default. The build pins docker-java's `api.version` (parent pom
> `docker.api.version`, default `1.43`) and forwards it to the Failsafe JVM. If your daemon's
> max API is older than 1.43, run with `-Ddocker.api.version=<your-version>`. See RUNBOOK §4.

## Tests
- `OllamaConnectivityProbeTest` — pure unit (mocked models), CI-safe.
- `SchemaMigrationIT` — Testcontainers `pgvector/pgvector:pg16`; runs the Flyway V1 migration
  and asserts the tables, the three indexes, the `vector(768)` column, and the generated
  `content_tsv` column exist. Needs Docker, **not** a GPU — runs in CI.
- `OllamaConnectivityLiveIT` — `@Tag("live")`, **gated behind the `live` Maven profile** so
  normal CI never needs a GPU. Asserts a chat completion returns text and the embedding
  dimension equals `EMBED_DIM` (768).

## Known quirk (R5)
If the **JarvisLabs instance is paused**, its nginx proxy still answers but the Ollama
upstream is down, so requests return `404 <html>` (nginx), not a connection error.
**Resume the instance before running the live test.** Also remember a resumed instance may
publish a new endpoint URL → update `OLLAMA_BASE_URL` (see RUNBOOK §2). Spring AI's retry
handles transient 5xx but not 404; a short client-side retry is a candidate hardening
(revisited with the P3 circuit-breaker work).
