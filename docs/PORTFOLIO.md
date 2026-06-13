# Atlas — Portfolio Highlights

Resume-ready, quantified outcomes per phase. Atlas is a permission-aware, cost-routed, evaluated enterprise
AI copilot for a financial/compliance domain (**Spring AI + LangGraph + MCP**).
Repo: <https://github.com/venkathub/atlas-compliance-copilot>

---

## P0 — Foundations (complete · 2026-06-13)

**One-liner:** Stood up a reproducible, secure, CI-gated polyglot monorepo and proved an env-swappable
remote-LLM integration — the production scaffolding before any AI logic.

**Resume bullets (draft):**
- Bootstrapped a polyglot **Java/Spring + Python** monorepo with a **5-job GitHub Actions** gate
  (build/test, `ruff`/`pytest`, **gitleaks** secret scan, **Trivy** dependency/config scan, **Syft** SBOM),
  green on `main` — supply-chain controls mapped to **OWASP LLM03**.
- Built and validated a **multi-arch (amd64 + arm64) distroless** container image with a **digest-pinned**
  base for the **Oracle Ampere A1 ARM** target, layering the architecture-independent Spring Boot jar to
  build arm64 with **zero QEMU emulation**.
- Integrated **Spring AI 1.0 ↔ remote Ollama** with fully **env-swappable** model config and an automated
  **live smoke test** asserting a chat completion + a **768-dim** embedding, **gated out of CI** to keep the
  pipeline GPU-free.
- Engineered a **snap-Docker-confinement-safe** local stack (Postgres + pgvector, Redis) via stdin/exec
  patterns (no host bind mounts), reproducible with a single `make up`.

**Evidence:** CI run #2 green (5/5 jobs) · `mvn verify` + live IT (3/3) green · multi-arch manifest verified
(amd64 + arm64) · ADR-0008–0010.

**Quantified:** 6 commits · 5 CI jobs · 2 healthchecked services · pgvector 0.8.2 · warm chat ~0.75 s ·
embedding 768-dim · distroless image (no shell, nonroot).

---

## P1 — Permission-aware RAG (pending)
## P2 — Evaluation & observability (pending)
## P3 — Cost-aware gateway (pending)
## P4 — Agent orchestrator + MCP (pending)
## P5 — UI + production deploy (pending)
_Each populated as the phase lands, per the CLAUDE.md Definition of Done._
