# infra/gpu — fail-safe GPU lifecycle helper

Programmatic **resume / health-poll / discover `OLLAMA_BASE_URL` / GUARANTEED pause** for
the Cloud Ollama GPU, so cost discipline (ADR-0006) is *enforced*, not remembered.
See **ADR-0029 (D-P2-9)** and RUNBOOK §2.4 / §6.

> **Cardinal invariant:** automation that can *resume* the GPU must never be able to leave
> it *running*. Every entry point pauses in a `finally`; a detached watchdog pauses on a
> deadline even if the parent process is killed.

## Why Python + stdlib only
The helper guards money, so its pause path must be **unit-testable** (a bash+curl wrapper
is not) and must run in CI with **zero third-party deps** (no fragile env between the GPU
and the guaranteed pause). Runtime uses only `urllib`.

## Usage
```bash
# Interactive session: resume, write the fresh URL into .env, arm the idle watchdog.
make -C infra gpu-up
set -a && . ./.env && set +a        # pick up the discovered OLLAMA_BASE_URL
#   ... record cassettes / recalibrate ...
make -C infra gpu-down              # GUARANTEED pause + cancel watchdog

# One-shot (the calibration-job path): resume -> run -> pause no matter what.
uv run --directory infra/gpu python -m atlas_gpu run -- <your command>

# See the ordering without touching a real GPU:
uv run --directory infra/gpu python -m atlas_gpu run --dry-run -- echo work
```

## Layout
| File | Role |
|---|---|
| `atlas_gpu/providers.py` | `Provider` protocol + **`JarvisLabsProvider`** (real backend API, verified live) + `E2EProvider` (generic seam fallback) + `make_provider` factory. |
| `atlas_gpu/lifecycle.py` | `GpuSession` (resume→poll→discover→**pause in `finally`**, and pause-on-failed-`__enter__`), `poll_until_ready`, `run_with_gpu`, `Watchdog`. |
| `atlas_gpu/__main__.py` | CLI: `up` / `down` / `run` / `_watchdog`. |
| `tests/` | pytest (24): guaranteed-pause-on-exception/timeout/failed-resume, watchdog deadline, real JarvisLabs flow via injectable transport. |

## JarvisLabs driver (verified live 2026-06-14)
`JarvisLabsProvider` speaks the real backend API, learned from the `jlclient` source and
**proven against a live account** with a full resume→health→pause cycle:
- **Auth/base:** `Authorization: Bearer $GPU_API_KEY`; region-aware base
  (`backendprod`/`backendn`/`backendeu`) — pause/resume MUST hit the instance's region.
- **Status/endpoint:** `GET users/fetch` (the by-id route 404s) → filter by `machine_id`;
  the Ollama URL comes from the instance `endpoints` field.
- **Pause:** `POST misc/pause?machine_id={id}` (success returns the string `"True"`).
- **Resume:** `POST templates/{framework}/resume` with a rebuilt config payload.
- **machine_id drifts on resume:** JarvisLabs assigns a *new* `machine_id` each resume. The
  driver **adopts the new id** from the resume response, and `_fetch` falls back to the sole
  instance if the configured id has drifted — so the live GPU is never lost track of (and can
  always be paused). `make gpu-up --write-env` persists the live id back to `.env`.

> The `E2EProvider` generic REST seam keeps its paths as a calibration-time TODO (confirmed
> on first live E2E run); JarvisLabs is the verified default.

## Configuration (env, never hardcoded)
`GPU_PROVIDER` (jarvislabs\|e2e) · `GPU_API_BASE` (optional override) · `GPU_API_KEY`
(managed secret, never logged — OWASP LLM03) · `GPU_INSTANCE_ID` · `GPU_IDLE_TIMEOUT_MIN`.

## Test
```bash
make -C infra gpu-test     # or: uv run --directory infra/gpu --with pytest pytest -q
```
