# rag-engine (Spring AI)

Permission-aware retrieval core: chunking, embeddings, hybrid (HNSW dense +
`tsvector` sparse) search, reranking, inline citations, prompt-injection guardrails,
and RBAC filtering at retrieval time.

**Full engine built in P1.** In **P0 (Increment 3)** this module hosts only the
**Ollama connectivity probe** — a `/health` endpoint plus a smoke test that asserts
a chat completion + an embedding come back via `OLLAMA_BASE_URL` (no real RAG yet).
