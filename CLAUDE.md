# CLAUDE.md — Atlas Engineering Operating Agreement

## Mission
Build Atlas: a production-grade enterprise AI operations copilot for a financial/compliance
domain. An employee asks a question; Atlas retrieves only documents they are cleared to see,
answers with citations, and — on request — executes governed actions through agents, with
every model call evaluated and traced. The goal is a deployed, demonstrable system that proves
production AI engineering depth (RAG, agents/MCP, evals, cost-aware infra, observability).

## Audience for this codebase
A senior backend engineer (10+ yrs Java full-stack) transitioning into AI engineering. Code,
READMEs, and decisions must read as the work of someone who can take AI from prototype to
reliable production. Favour clarity and correctness over cleverness.

## Architecture (6 subsystems)
1. React UI — chat + admin, citations, traces visible to the user.
2. API Gateway (Spring Boot) — auth, cost-aware model router, caching, rate limiting.
3. RAG Engine (Spring AI) — permission-aware retrieval: chunking, embeddings, hybrid
   search, reranking, citation/source attribution, prompt-injection guardrails.
4. Vector Store (pgvector) — embeddings + role-tagged metadata for RBAC filtering.
5. Agent Orchestrator (Python / LangGraph) — planner-executor agents, memory, human-in-
   the-loop checkpoints, calling tools via MCP.
6. MCP Tool Servers (Spring Boot) — governed enterprise actions exposed over MCP.
Cross-cutting: Evals & Observability (RAGAS/DeepEval + Langfuse + Grafana), CI-gated.

## Tech stack (polyglot by design)
- Java/Spring Boot + Spring AI: gateway, RAG engine, MCP tool servers (the core; my moat).
- Python + LangGraph: agent orchestration. Python + RAGAS/DeepEval: evaluation harness.
- Postgres + pgvector; Redis (cache); Docker; GitHub Actions (CI); Langfuse + Grafana/Prometheus.
- Model serving: cloud-hosted Ollama (OpenAI-compatible endpoint) on a rented GPU; a small
  cloud-frontier budget reserved only for final multimodal demos.

## Environment constraints
- Developer laptop is low-spec. It runs only Claude Code + editor + Docker for app services.
  The LLM NEVER runs locally — it lives on a remote Ollama GPU endpoint set via env var
  `OLLAMA_BASE_URL`. All model config is swappable by env, never hardcoded.
- Cost discipline is a first-class feature, not an afterthought. Default to small/quantized
  models in dev; reserve the larger model for demos. The gateway must expose token/cost/latency
  dashboards — the cost story is part of the portfolio.

## Working agreement (how you, Claude Code, must operate)
- **One subsystem per session**, built in dependency order. Do not scaffold everything at once.
- **Evals before agents.** The evaluation harness is built in Phase 2, before agentic features,
  and gates every later change. Never ship a RAG/agent change without an eval result.
- **Plan before code.** For any non-trivial task, first output a short plan (files to touch,
  approach, test strategy, risks) and WAIT for my approval before writing code.
- **Test-backed.** Every feature ships with tests. A phase is not done until its tests and its
  eval thresholds pass in CI.
- **Small, reviewable diffs.** Prefer incremental commits with clear messages over giant drops.
- **Decisions are logged.** Any architectural choice (chunk size, embedding model, vector store,
  routing thresholds, framework picks) gets a dated entry in `docs/DECISIONS.md` with options
  considered + rationale. This is also my interview prep — be thorough on the "why."
- **No secrets in code.** Use env vars + `.env.example`. Never print real keys.
- **Ask, don't assume.** If a requirement is ambiguous, ask one focused question rather than
  guessing. State any assumption you do make, inline.
- **Honesty over agreeableness.** If my idea is weak or a shortcut creates tech debt, say so and
  propose the better path.

## Repo conventions
- `/gateway` (Spring Boot), `/rag-engine` (Spring AI), `/mcp-tools` (Spring Boot),
  `/agents` (Python/LangGraph), `/evals` (Python), `/ui` (React), `/infra` (Docker/CI/compose),
  `/docs` (ROADMAP.md, DECISIONS.md, RUNBOOK.md, per-phase specs).
- Each module has its own README: purpose, architecture, setup, how to run tests, results/metrics.
- Conventional commit messages. Feature branches; CI must pass before merge to main.

## Definition of Done (every phase)
- [ ] Code complete and matches the approved phase spec.
- [ ] Unit + integration tests written and passing.
- [ ] Eval thresholds met (where the phase touches RAG/agents) and recorded.
- [ ] Module README + `docs/DECISIONS.md` updated.
- [ ] Runs cleanly from scratch via documented setup (fresh clone + `.env`).
- [ ] A 30-second demo path I can click/run.
- [ ] A resume-ready, quantified bullet drafted for `docs/PORTFOLIO.md`.