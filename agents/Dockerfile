# syntax=docker/dockerfile:1
#
# Atlas agents runtime image (P4, hardened P6 Task 2) — Python / LangGraph Agent Orchestrator.
#
# Multi-stage: (1) a builder resolves a lockfile-reproducible virtualenv with uv; (2) a slim,
# NON-ROOT, DIGEST-PINNED runtime carries only the venv + app code (no uv, no build tools).
# Base pinned by digest (OWASP LLM03 / ASI04 supply-chain — resolve with
# `docker buildx imagetools inspect python:3.12-slim-bookworm`). Build context = repo root.

# ── stage 1: build a locked virtualenv ────────────────────────────────────────
FROM python:3.12-slim-bookworm@sha256:8a7e7cc04fd3e2bd787f7f24e22d5d119aa590d429b50c95dfe12b3abe52f48b AS builder
ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv
RUN pip install --no-cache-dir uv
WORKDIR /build
# Install deps first (layer-cached until the lockfile changes). Build context = repo root.
COPY agents/pyproject.toml agents/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
# App code (run from source; not installed as a distributable package).
COPY agents/app ./app

# ── stage 2: minimal non-root runtime ─────────────────────────────────────────
FROM python:3.12-slim-bookworm@sha256:8a7e7cc04fd3e2bd787f7f24e22d5d119aa590d429b50c95dfe12b3abe52f48b AS runtime
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
# Drop root: a fixed system uid/gid so the container never runs privileged.
RUN groupadd --system --gid 10001 atlas \
 && useradd --system --uid 10001 --gid atlas --no-create-home --home-dir /app atlas
WORKDIR /app
# The venv and app are world-readable; ownership left to root (read-only at runtime).
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /build/app ./app
USER 10001:10001
EXPOSE 8083
# Liveness via the app's own /healthz (stdlib urllib — no extra packages, runs as non-root).
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8083/healthz', timeout=4).status==200 else 1)"]
ENTRYPOINT ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8083"]
