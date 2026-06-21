# syntax=docker/dockerfile:1
#
# Atlas agents runtime image (P4) — Python / LangGraph Agent Orchestrator.
#
# NOTE: pin the base image by digest in CI/prod (OWASP LLM03 / ASI04 supply-chain) — resolve with
# `docker buildx imagetools inspect python:3.12-slim-bookworm`. Left as a tag here so the build is
# reproducible without a registry round-trip during local dev.
FROM python:3.12-slim-bookworm AS base

WORKDIR /app

# uv for fast, lockfile-reproducible installs.
RUN pip install --no-cache-dir uv

# Install deps first (layer-cached until the lockfile changes). Build context = repo root.
COPY agents/pyproject.toml agents/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# App code.
COPY agents/app ./app

EXPOSE 8083
ENTRYPOINT ["uv", "run", "--no-dev", "uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8083"]
