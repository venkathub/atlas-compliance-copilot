# infra/gpu — GPU lifecycle + from-scratch provisioner

Two capabilities behind one tool:

1. **Lifecycle** — resume an existing GPU, health-poll, discover the serving endpoint, run
   work, then **GUARANTEED pause** (`finally`/trap) + a detached idle-timeout watchdog.
   (ADR-0029 / D-P2-9, RUNBOOK §2.4 / §6.)
2. **From-scratch provisioning (Task 0)** — `create` a GPU instance via the official
   `jarvislabs` SDK, install + serve **Ollama and/or vLLM** (OpenAI-compatible), discover +
   write the endpoint env vars, and leave it running under the watchdog. (ADR-0066.)

> **Cardinal invariant:** automation that can *start* the GPU must never be able to leave it
> *running*. Every entry point pauses in a `finally`; a detached watchdog pauses on a
> deadline even if the parent process is killed.

## Why the SDK, and the dependency tradeoff
Provisioning from scratch (create instance, attach startup script, manage filesystems) is
exactly what the official `jarvislabs` SDK does well, so `JarvisLabsProvider` is now SDK-backed
(replacing the previous raw-`urllib` driver). That **ends the old "stdlib-only" guarantee** —
mitigated as follows (ADR-0066):
- The SDK is **lazy-imported** (only inside `sdk.RealJlClient`), so importing `atlas_gpu` and
  the **guaranteed-pause watchdog path never require the package**.
- All logic sits behind the `JlClient` Protocol, so unit tests inject a `FakeJlClient` and run
  with **no SDK install and no network**.
- The SDK version is pinned; `--dry-run` provisions nothing.

Auth is unchanged: the token is read from **`GPU_API_KEY`** and passed as `Client(api_key=...)`
— no dependence on `jl setup` / `JL_API_KEY`.

## Usage

### Provision a serving GPU from nothing
```bash
# Ollama (default), write the discovered endpoint into .env, arm the watchdog:
uv run --directory infra/gpu python -m atlas_gpu provision --serve ollama --write-env ./.env

# Both Ollama + vLLM on one A100 (for the serving benchmark) — they share VRAM:
uv run --directory infra/gpu python -m atlas_gpu provision \
    --serve both --gpu A100 --storage 120 --write-env ./.env

# See the exact create plan + startup script WITHOUT touching the account / spending money:
uv run --directory infra/gpu python -m atlas_gpu provision --serve both --dry-run

# Tear down when done (keeps data) — or --destroy to delete entirely:
uv run --directory infra/gpu python -m atlas_gpu teardown            # pause
uv run --directory infra/gpu python -m atlas_gpu teardown --destroy  # delete
```
`provision` writes `OLLAMA_BASE_URL`, `ATLAS_VLLM_BASE_URL` (when `vllm`/`both`), and the live
`GPU_INSTANCE_ID` back to `--write-env`.

### Resume / run against an already-provisioned instance
```bash
make -C infra gpu-up                 # resume + discover + arm watchdog
set -a && . ./.env && set +a
make -C infra gpu-down               # GUARANTEED pause + cancel watchdog

# One-shot calibration-job path: resume -> run -> pause no matter what.
uv run --directory infra/gpu python -m atlas_gpu run -- <your command>
```

## How "from scratch E2E" works
```
build idempotent startup script (provision.py)
  → client.scripts.add(...)            upload it
  → instances.create(http_ports=...)   blocks until Running
  → wait_for_roles(...)                health-poll /api/tags (ollama) & /v1/models (vllm)
                                       until the script finishes installing/pulling
  → classify_endpoints(probe)          label which public URL is which (order NOT assumed)
  → write OLLAMA_BASE_URL / ATLAS_VLLM_BASE_URL / GPU_INSTANCE_ID
  → arm watchdog                       second-net auto-pause
```
The startup script is **idempotent** (install guarded by `command -v`/import checks, servers by
`pgrep`, `ollama pull` is a no-op when present), so it is safe on every launch *and* resume.

## Layout
| File | Role |
|---|---|
| `atlas_gpu/sdk.py` | `JlClient` Protocol + lazy `RealJlClient` adapter over `jarvislabs.Client`; `InstanceInfo`; `make_client` (reads `GPU_API_KEY`). The only SDK import. |
| `atlas_gpu/provision.py` | `ServeTarget`, `ProvisionConfig`, idempotent `build_startup_script`, port mapping, and probe-based `classify_endpoints`. Pure / offline. |
| `atlas_gpu/providers.py` | `GpuProvider` Protocol + SDK-backed `JarvisLabsProvider` (`resume`/`pause`/`status`/`endpoint` + `create`/`destroy`/`discover_endpoints`) + `make_provider`. |
| `atlas_gpu/bootstrap.py` | `provision_from_scratch` E2E orchestration + `wait_for_roles` + `write_env`. |
| `atlas_gpu/lifecycle.py` | `GpuSession` (pause in `finally`), `poll_until_ready`, `run_with_gpu`, `Watchdog`. |
| `atlas_gpu/__main__.py` | CLI: `provision` / `teardown` / `up` / `down` / `run` / `_watchdog`. |
| `tests/` | pytest (41): guaranteed-pause invariants, watchdog, SDK provider flow + create, startup-script builder, endpoint classify, E2E provision — all offline via `FakeJlClient`. |

## Endpoint discovery — why we probe, not index
JarvisLabs exposes each custom `http_port` as a separate HTTPS URL in the instance's
`endpoints` list, but does **not** publish a port→URL mapping and the order is not contractual.
So `classify_endpoints` **probes** each URL (`/api/tags` ⇒ Ollama, `/v1/models` ⇒ vLLM) to label
it, rather than trusting position.

## ⚠️ `--serve both` shares one GPU
Ollama and vLLM compete for the same VRAM. `both` is opt-in, prints a warning, and is intended
for the benchmark on a larger GPU (A100). For dev, default to `ollama`.

## Configuration (env, never hardcoded)
Auth/lifecycle: `GPU_PROVIDER` (`jarvislabs`) · `GPU_API_KEY` (secret, never logged) ·
`GPU_INSTANCE_ID` · `GPU_IDLE_TIMEOUT_MIN`.
Create defaults: `GPU_TYPE` (e.g. `A100`, `L4`) · `GPU_STORAGE_GB` · `GPU_NUM_GPUS` ·
`GPU_TEMPLATE` · `GPU_REGION` · `GPU_INSTANCE_NAME`.
Serving/models: `OLLAMA_CHAT_MODEL` · `OLLAMA_EMBED_MODEL` · `ATLAS_VLLM_MODEL` ·
`ATLAS_VLLM_MAX_MODEL_LEN`; outputs `OLLAMA_BASE_URL` / `ATLAS_VLLM_BASE_URL`.

## Test
```bash
make -C infra gpu-test     # or: uv run --directory infra/gpu pytest -q
uvx ruff check infra/gpu
```
> **Live-verified 2026-06-29** on JarvisLabs **L4** (IN2), every JarvisLabs use case Atlas
> uses, total cost ≈ **₹30**:
> - **create** → Running in 7s; **status**; **pause** → Paused; **resume** → Running with
>   **machine_id drift (436272→436273) correctly adopted**; **Watchdog**-driven pause; **destroy**.
> - **`provision --serve ollama`** → install + model pull → public endpoint classified → a
>   **chat completion through the JarvisLabs HTTPS proxy** returned `ATLAS_OK`. **Ollama confirmed
>   on GPU**: `ollama ps` → `100% GPU`, `nvidia-smi` → `llama-server` using ~2.3 GB VRAM.
> - **`provision --serve vllm`** → vLLM 0.23.0 served `/v1/models`; the **default
>   `Qwen2.5-7B-Instruct-AWQ` loads on L4** (~20.5 GB / 24 GB, `VLLM::EngineCore`) and chat
>   returned `ATLAS_OK`. The box log confirmed probe order on the real proxy
>   (`/api/tags`→404 then `/v1/models`→200), i.e. `classify_endpoints` distinguishes the two.
> - **`teardown --destroy`** CLI cleaned up; `jl list` → `[]` after every run.
>
> The run surfaced **three real bugs**, all fixed + regression-tested:
> 1. **Ollama never installed headlessly** — JarvisLabs' startup shell has a minimal PATH that
>    omits `/usr/local/bin` *and* the system `curl`, so `curl | sh` silently no-op'd and
>    `set -u` (not `-e`) let it continue. Fixed: broaden PATH
>    (`/usr/local/bin:/usr/bin:/bin:/opt/conda/bin`), retry the install until the binary
>    appears, and `exec >` all output to `/var/log/atlas-provision.log` for diagnosability.
> 2. **Startup scripts accumulated** until the account cap rejected `scripts.add` — now
>    **upserted by name** (reuse/refresh, never duplicate).
> 3. (earlier) endpoint classification must **probe**, not assume port order.
>
> The 42 offline tests use a `FakeJlClient` (no SDK/network); `--dry-run` provisions nothing.
