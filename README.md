# Atlas

> Production-grade, permission-aware enterprise AI operations copilot for a financial/compliance domain.
>
> An employee asks a question → Atlas retrieves **only** documents they are cleared to see → answers **with
> citations** → and, on request, executes **governed actions** behind a human-in-the-loop checkpoint. Every
> model call is **cost-routed, evaluated, and traced**.

**Status:** P0 (foundations) in progress. See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the phase plan.

---

## Architecture (6 subsystems + cross-cutting evals/observability)

| Module        | Stack                | Responsibility                                                       | Phase |
|---------------|----------------------|----------------------------------------------------------------------|-------|
| `ui/`         | React                | Chat + admin; streamed answers, inline citations, agent trace        | P5    |
| `gateway/`    | Spring Boot          | Auth, cost-aware model router, semantic cache, rate limiting         | P3    |
| `rag-engine/` | Spring AI            | Permission-aware retrieval: chunk/embed, hybrid search, citations    | P1    |
| (pgvector)    | Postgres + pgvector  | Embeddings + role-tagged metadata (RBAC), agent checkpoints          | P1/P4 |
| `agents/`     | Python / LangGraph   | Planner–executor agents, memory, human-in-the-loop                   | P4    |
| `mcp-tools/`  | Spring Boot          | Governed enterprise actions exposed over MCP                         | P4    |
| `evals/`      | Python / RAGAS/DeepEval | Eval harness (CI-gated) + Langfuse/Grafana observability           | P2    |
| `infra/`      | Docker / CI          | Compose stack, multi-arch images, GitHub Actions                     | P0    |

The **LLM never runs locally** — it lives on a remote Ollama GPU endpoint set via `OLLAMA_BASE_URL`
(see [`docs/RUNBOOK.md`](docs/RUNBOOK.md)). All model config is env-swappable.

## Quickstart (P0 — fills in as increments land)

```bash
cp .env.example .env        # then edit values (never commit .env)
# docker compose up         # (Increment 2) Postgres+pgvector + Redis
# make health               # (Increment 2) assert services healthy
# mvn -pl rag-engine test   # (Increment 3) unit tests; live smoke test is @Tag("live")
```

## Documentation
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — vision, phase plan P0–P5, risks, skills map, security baseline
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — architectural decision log (ADRs)
- [`docs/RUNBOOK.md`](docs/RUNBOOK.md) — local host + cloud Ollama (JarvisLabs) operations
- [`docs/PORTFOLIO.md`](docs/PORTFOLIO.md) — quantified, resume-ready outcomes per phase
- [`CLAUDE.md`](CLAUDE.md) — engineering operating agreement

## License
[Apache-2.0](LICENSE) © 2026 Venkatesh.
Note: the FinanceBench dataset used from P1 stays under its own **CC-BY-NC-4.0** license
(see `docs/DECISIONS.md` ADR-0004) — that covers data, not this code.
