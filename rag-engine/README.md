# rag-engine (Spring AI)

Permission-aware retrieval core: chunking, embeddings, hybrid (HNSW dense +
`tsvector` sparse) search, reranking, inline citations, prompt-injection guardrails,
and RBAC filtering at retrieval time.

**Full engine built in P1.** In **P0** this module hosts only the **Ollama connectivity
probe** — proof that the Spring AI ↔ remote Ollama path works end-to-end (one chat
completion + one embedding via `OLLAMA_BASE_URL`). No retrieval logic yet.

## Stack
- Spring Boot 3.4.7 · Spring AI 1.0.0 (`spring-ai-starter-model-ollama`) · Java 21
- Versions centralized in the root `pom.xml` (monorepo BOM/plugin management).

## Configuration (all env-swappable — `.env` at repo root)
| Property | Env var | Default |
|---|---|---|
| `spring.ai.ollama.base-url` | `OLLAMA_BASE_URL` | `http://localhost:11434` |
| `spring.ai.ollama.chat.options.model` | `OLLAMA_CHAT_MODEL` | `qwen2.5:3b-instruct` |
| `spring.ai.ollama.embedding.options.model` | `OLLAMA_EMBED_MODEL` | `nomic-embed-text` |
| `server.port` | `RAG_ENGINE_PORT` | `8081` |

`spring.ai.ollama.init.pull-model-strategy=never` (the remote endpoint already hosts the
models) and `chat.options.keep-alive=30m` (keep the model resident to avoid GPU cold starts).

## Run

```bash
# Unit tests only — no GPU needed (runs in CI on every PR):
mvn -pl rag-engine test

# Live smoke test against the real remote Ollama (the P0 exit gate) — needs OLLAMA_BASE_URL:
set -a && . ./.env && set +a && mvn -P live -pl rag-engine verify

# 30-second demo: boot the app and hit the probe endpoint
set -a && . ./.env && set +a && mvn -pl rag-engine spring-boot:run
curl -s localhost:8081/probe/connectivity | jq      # chat reply + embeddingDim=768, ok=true
curl -s localhost:8081/actuator/health | jq         # liveness (does NOT call the GPU)
```

## Tests
- `OllamaConnectivityProbeTest` — pure unit (mocked models), CI-safe.
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
