# Atlas — RUNBOOK

> Operational guide for running Atlas locally and operating its remote dependencies.
> Companion docs: `CLAUDE.md`, `docs/ROADMAP.md`, `docs/DECISIONS.md`.
> Status: **bootstrap** — sections grow as phases land. Today this covers the dev host + Cloud Ollama.

---

## 1. Local developer host

### 1.1 Required toolchain (verified versions)
| Tool | Version on host | Install source |
|---|---|---|
| Git | system | apt |
| Docker Engine | 29.x (Canonical **snap**) | snap |
| Docker Compose v2 | v5.x | bundled with Docker |
| Docker Buildx | v0.31+ | bundled with Docker |
| JDK | OpenJDK **21** | apt (`openjdk-21-jdk`) |
| Maven | **3.9.x** | apt (`maven`) |
| Python | 3.11/3.12 | system |
| uv | latest | `~/.local/bin/uv` |
| Node.js | 24 LTS (via nvm) | nvm |
| curl / jq | system | apt |

> The LLM, Postgres, Redis, Langfuse, Grafana/Prometheus do **not** run as host packages — they are
> remote (Ollama) or Docker containers.

### 1.2 One-time Docker setup (rootless access)
The snap Docker socket is owned by `root:docker`. To use Docker without `sudo`:
```bash
sudo groupadd -f docker
sudo usermod -aG docker "$USER"
sudo snap disable docker && sudo snap enable docker   # snap picks up the new group
```
**Then log out and back in** (or reboot) so your login session joins the `docker` group.
`newgrp`/`sg` are not installed on this host, so a fresh login is the clean path.

Verify after re-login:
```bash
docker run --rm hello-world          # must succeed WITHOUT sudo
docker compose version
docker buildx ls
```

### 1.3 Multi-arch builds (for ARM prod target)
Prod runs on Oracle Cloud Ampere A1 (**arm64**). One-time, to enable cross-builds from this amd64 host:
```bash
docker run --privileged --rm tonistiigi/binfmt --install all
docker buildx create --name atlas-builder --driver docker-container --use --bootstrap
docker buildx ls          # should list linux/amd64 and linux/arm64
```
**Snap-Docker note (this host):** the snap docker CLI can't read `/data` (ADR-0009), so feed the build
context via **stdin** instead of a path:
```bash
# build rag-engine for both arches (jar first: mvn -pl rag-engine -am package)
tar --exclude=./.git -C /data/aiTrack/Atlas -cf - . | \
  docker buildx build --builder atlas-builder --platform linux/amd64,linux/arm64 \
    -f rag-engine/Dockerfile -t atlas/rag-engine:dev --output type=oci,dest="$HOME/img.tar" -
```
(In GitHub Actions the runner is not confined, so the `image` job uses a normal path context — see §5.)

### 1.4 Toolchain verification (copy-paste)
```bash
git --version; docker --version; docker compose version; docker buildx version
java -version; mvn -version; python3 --version; uv --version; node --version; npm --version
curl --version | head -1; jq --version
```

---

## 2. Cloud Ollama (remote LLM endpoint)

The LLM **never runs on the laptop**. It lives on a rented Indian-cloud GPU and is reached via
`OLLAMA_BASE_URL`. Default platform: **JarvisLabs.ai** (INR/UPI, per-minute billing, pause/resume with
persistent storage). Fallback: **E2E Networks** (Indian, INR + GST).

**Sizing:** our dev model is small — an **L4 / RTX A5000 (16–24 GB VRAM)** is plenty (no H100), with
**~30–50 GB storage**. Persistent storage survives pause/resume, so pulled models stay put when paused.

**Port model (important):** in **template/instance mode** JarvisLabs publishes **port 6006** as the public
API endpoint (click the instance's **API** button for the URL). In **VM mode** you expose any port with
`--http-ports`. Pick the matching path below.

### 2.1 Provision — choose ONE path

#### Path A — Ollama template (recommended, zero-setup)
1. Launch an instance from the **Ollama framework template**: `jarvislabs.ai/templates/ollama`
   (GPU: L4 / A5000; Storage ~30–50 GB). Ollama is pre-installed and already serving.
2. Pull the dev models from the JupyterLab/SSH terminal:
   ```bash
   ollama pull qwen2.5:3b-instruct     # chat — dev default
   ollama pull nomic-embed-text        # embeddings — 768-dim
   ```
   (or via API: `curl https://<instance>.jarvislabs.net/api/pull -d '{"name":"qwen2.5:3b-instruct"}'`)
3. Click the **API** button on the instance in the dashboard and copy the public endpoint, e.g.
   `https://<instance>.jarvislabs.net` — the Ollama template maps it to Ollama. That URL is your `OLLAMA_BASE_URL`.

#### Path B — PyTorch template or VM (more control)
1. Launch a **PyTorch** template instance, **or** a **VM** (SSH-only; register a key first with `jl ssh-key add`):
   ```bash
   jl create --gpu A5000 --vm --http-ports "11434"     # VM: expose Ollama's native port
   ```
2. Install Ollama:
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```
3. Serve it so it's publicly reachable — **match your mode**:
   - **Instance/template mode** → run Ollama on the public port **6006**:
     ```bash
     OLLAMA_HOST=0.0.0.0:6006 ollama serve &
     ```
     Then copy the public URL via the dashboard **API** button → that's `OLLAMA_BASE_URL`.
   - **VM mode** → run on the port you exposed (e.g. 11434):
     ```bash
     OLLAMA_HOST=0.0.0.0:11434 ollama serve &
     ```
     The custom-port URL appears under the instance's **endpoints** → that's `OLLAMA_BASE_URL`.
   - **Private alternative (any mode)** → SSH tunnel, no public exposure:
     ```bash
     ssh -L 11434:localhost:11434 -o StrictHostKeyChecking=no -p <ssh-port> root@sshd.jarvislabs.ai
     # then OLLAMA_BASE_URL=http://localhost:11434
     ```
4. Pull the dev models:
   ```bash
   ollama pull qwen2.5:3b-instruct
   ollama pull nomic-embed-text
   ```

> The two model choices fix the **pgvector embedding dimension (768)** used in P1 — see `DECISIONS.md` ADR-0005.
> Ollama serve logs live at `/home/ollama.log` (handy for debugging).

### 2.2 Wire it into Atlas
Set in your local `.env` (never commit real values; `.env.example` carries placeholders):
```bash
# template/instance mode: URL maps to port 6006 (or Ollama template's mapping); VM mode: your --http-ports URL
OLLAMA_BASE_URL=https://<your-jarvislabs-endpoint>
OLLAMA_CHAT_MODEL=qwen2.5:3b-instruct
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_EMBED_DIM=768
```
All model config is env-swappable — never hardcode a model or URL.

### 2.3 Connectivity smoke test (this is the P0 exit gate, run manually anytime)
```bash
# 1) list models served
curl -s "$OLLAMA_BASE_URL/api/tags" | jq '.models[].name'

# 2) OpenAI-compatible chat completion
curl -s "$OLLAMA_BASE_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$OLLAMA_CHAT_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}]}" \
  | jq '.choices[0].message.content'

# 3) embedding (assert vector length == OLLAMA_EMBED_DIM)
curl -s "$OLLAMA_BASE_URL/api/embeddings" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$OLLAMA_EMBED_MODEL\",\"prompt\":\"hello\"}" \
  | jq '.embedding | length'
```
All three returning sane values = endpoint is healthy and ready for the RAG engine.

### 2.4 Cost discipline — pause/resume
- **Pause the instance** at the end of each dev/demo session → per-minute GPU billing stops; models persist on
  the instance's persistent storage.
- **Resume** before a session; the public endpoint may change on resume → update `OLLAMA_BASE_URL`.
- **Automated (P2, ADR D-P2-9, preferred):** `make -C infra gpu-up` / `gpu-down` (or the calibration job)
  drives resume/pause via the provider API with a **guaranteed pause** (`finally`/trap) + idle-timeout
  watchdog, and auto-discovers the fresh `OLLAMA_BASE_URL`. Manual pause/resume below is the fallback.
- Reserve the larger/frontier model only for final demos (P5); default to the small model in dev.
- Rough outlook: a disciplined pause/resume cadence keeps GPU spend to a few hundred ₹/month.

### 2.5 Security notes
- Ollama has **no auth** by default; the exposed JarvisLabs URL is obscure but not secret. Acceptable for dev.
- Do not put real data through the endpoint until it is fronted by the gateway.
- Hardening option (P3): front the endpoint with an API-key check at the gateway; log decision in `DECISIONS.md`.

---

## 3. Local service stack (Postgres+pgvector, Redis) — P0
Defined in `infra/docker-compose.yml` (stock images, **digest-pinned**, healthchecked, **named volumes**).
Snap-Docker-safe operation (ADR-0009): the Makefile pipes compose via stdin and applies init via `exec` —
no `/data` path is ever handed to a snap docker binary.
```bash
make -C infra up        # start; wait healthy; load pgvector + pg_trgm
make -C infra health    # container health + pgvector version + redis PONG
make -C infra down      # stop (keep data volumes)
make -C infra clean     # stop + delete volumes
make -C infra psql      # psql shell into atlas-postgres
make -C infra logs|ps   # follow logs / status
```
Defaults (from repo-root `.env`): Postgres `localhost:5432` (db/user `atlas`), Redis `localhost:6379`.
Verified: pgvector **0.8.2** + pg_trgm on `pg16`; both containers healthy.

## 4. Build, test & run — P0/P1
**Java (`rag-engine`):**
```bash
mvn -B verify                       # build + unit tests (surefire) + Testcontainers ITs (failsafe)
mvn -pl rag-engine test             # unit tests only (no Docker, no GPU)
mvn -pl rag-engine spring-boot:run  # boot the app (needs Postgres up — runs Flyway on start)
curl -s localhost:8081/probe/connectivity | jq   # 30s demo: chat reply + embeddingDim=768, ok=true
curl -s localhost:8081/actuator/health | jq      # liveness (does NOT call the GPU)
```
> **`verify` needs Docker** (not a GPU): from P1 the Failsafe ITs use Testcontainers to spin up
> `pgvector/pgvector:pg16` (e.g. `SchemaMigrationIT` runs the Flyway migration and asserts the schema).

**Testcontainers ↔ modern Docker daemon (api.version):** Docker daemons ≥28 (e.g. local dev on
29.x) drop support for the legacy Docker API version that Testcontainers' bundled docker-java
negotiates by default, so ITs fail with *"client version 1.32 is too old; minimum supported API
version is 1.40."* docker-java ignores the `DOCKER_API_VERSION` env var, so the build pins its
`api.version` config property via the parent-pom property **`docker.api.version`** (default `1.43`
= Docker 24/2023) and forwards it to the Failsafe-forked JVM. Override if your daemon's *max* API
is older:
```bash
mvn -B verify -Ddocker.api.version=1.41
```

**Live Ollama smoke test (P0 exit gate — needs a *resumed* JarvisLabs instance):**
```bash
set -a && . ./.env && set +a && mvn -P live -pl rag-engine verify
```
> If it returns an nginx `404`, the JarvisLabs instance is **paused** — resume it (§2.4) and re-check
> `OLLAMA_BASE_URL` (a resumed instance may publish a new URL).

**Python (`evals` scaffold):**
```bash
uvx ruff check evals
uvx --with pytest pytest evals -q
```

**Corpus (P1):** the two-layer corpus lives in `rag-engine/src/main/resources/corpus/`(`layer1/` = committed FinanceBench evidence snippets + `manifest.json`; `layer2/` = authored
AML/compliance overlay). Test fixtures (D3 shim, D4 negative-access, D7 poisoned docs) are under
`rag-engine/src/test/resources/fixtures/`. To refresh/extend Layer-1 from Hugging Face (no auth):
```bash
python rag-engine/src/main/resources/corpus/scripts/fetch_layer1.py --check   # verify entries resolve
python rag-engine/src/main/resources/corpus/scripts/fetch_layer1.py --write   # rewrite snippet files
```
See `rag-engine/src/main/resources/corpus/README.md` for provenance + license (CC-BY-NC-4.0).

**Ingest + query (P1, needs `make -C infra up` + a live Ollama; app runs with `SPRING_PROFILES_ACTIVE=local`):**
```bash
set -a && . ./.env && set +a && mvn -pl rag-engine spring-boot:run      # boots + runs Flyway
curl -sX POST localhost:8081/v1/admin/ingest -H 'X-Atlas-User: bsa-admin' | jq     # full rebuild (admin only)
curl -sX POST localhost:8081/v1/query -H 'X-Atlas-User: priya' -H 'Content-Type: application/json' \
  -d '{"query":"Summarize the open AML exceptions for the Northwind account this quarter."}' | jq
```
Clearance is supplied by the **P1-only** dev shim (ADR-0016): header `X-Atlas-User` (mapped via
`dev/clearance-users.json`) or `X-Atlas-Clearance` directly. The same Northwind query as
`X-Atlas-User: guest-public` returns no compliance/restricted citations (RBAC). Live ITs (incl.
`QueryLiveIT`) need infra up + a resumed GPU: `mvn -P live -pl rag-engine verify`.

## 5. CI & supply-chain — P0
GitHub Actions (`.github/workflows/ci.yml`) on push/PR to `main`. Five jobs (= the required status checks):

| Job (display name) | What it does |
|---|---|
| **Java build & test** | `mvn -B verify` (unit tests + Testcontainers ITs on the runner's Docker; live IT excluded) |
| **Python lint & test** | `ruff` + `pytest` on `evals` |
| **Secret scan (gitleaks)** | full-history secret scan |
| **Vuln scan & SBOM** | Trivy fs scan (vuln+misconfig+secret, **report-only for now**) + Syft CycloneDX SBOM artifact |
| **Multi-arch image build** | buildx amd64+arm64; pushes `ghcr.io/<repo>/rag-engine` on `main` only |

**Branch protection (one-time, repo owner):** Settings → Branches → protect `main` → require a PR + require
the five checks above + block force-pushes. Checks appear in the picker only after one green run.
**TODO:** flip Trivy to blocking (`exit-code 1`) once the CVE baseline is triaged; consider SHA-pinning actions.

## 6. Eval & observability harness — P2
The P2 harness lives in `/evals` (Python/RAGAS) + Langfuse/Grafana/Prometheus in `infra/docker-compose.yml`.
**Key principle (ADR D-P2-1): the CI merge gate replays committed cassettes — it needs NO GPU and NO live
Ollama.** A live GPU is only needed when you *record* cassettes or run the *live calibration* job.

### 6.1 Bring up the observability stack
```bash
make -C infra up                 # data stores + langfuse, grafana, prometheus (staged, Snap-safe)
make -C infra health             # postgres/redis/clickhouse health + langfuse/grafana/prometheus reachability
open http://localhost:3000       # Langfuse (traces + eval datasets)
open http://localhost:3001       # Grafana (eval-score / latency / trace-volume panels)
open http://localhost:9090       # Prometheus (Status → Targets shows the rag-engine scrape)
```
Langfuse is **headless-bootstrapped**: `make up` auto-creates the `atlas`/`atlas-rag`
org+project and wires the API keys straight from `.env` (`LANGFUSE_PUBLIC_KEY` /
`LANGFUSE_SECRET_KEY`) — no manual "create a project" step. Log into the UI with
`LANGFUSE_INIT_USER_EMAIL` / `LANGFUSE_INIT_USER_PASSWORD` only if you want to browse traces.
Footprint note: Langfuse v3 **reuses** `atlas-postgres` (db `langfuse`) + `atlas-redis`,
adding only ClickHouse + MinIO (owner-confirmed, D-P2-5).

`rag-engine` exports OTel `gen_ai.*` spans to `OTEL_EXPORTER_OTLP_ENDPOINT`; one `/v1/query` → one trace.
Prometheus scrapes `rag-engine` at `host.docker.internal:${RAG_ENGINE_PORT}/actuator/prometheus`
(the engine runs on the host, not in the Compose network); its target shows **down** until
the engine is running — that is expected.

**Enabling trace export to Langfuse (opt-in, ADR-0030).** Export is OFF by default so tests/CI never
reach Langfuse. To stream traces in dev, set in `.env`:
```bash
OTEL_TRACES_EXPORT_ENABLED=true
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://localhost:3000/api/public/otel/v1/traces
LANGFUSE_OTEL_AUTH_HEADER=$(printf 'Basic %s' "$(printf '%s:%s' "$LANGFUSE_PUBLIC_KEY" "$LANGFUSE_SECRET_KEY" | base64 -w0)")
```
Trace **content** stays metadata-only unless `ATLAS_TRACE_CONTENT=full` (local dev only — redaction-gated).

### 6.2 Pull the judge model (one-time, on the resumed GPU)
The routine LLM-as-judge is `llama3.1:8b-instruct` — a **cross-family** judge (llama judging the qwen RAG
subject) to reduce self-bias — served on the **same** Cloud Ollama endpoint as the RAG model (co-resident
footprint ≈ 8 GB VRAM — fits the L4/A5000, no upgrade needed):
```bash
make -C infra gpu-up                          # auto-resume + health-poll + export OLLAMA_BASE_URL (ADR D-P2-9)
ssh/console into the Ollama instance, then:  ollama pull llama3.1:8b-instruct
```

### 6.3 Run the eval gate locally
```bash
# (a) OFFLINE — the CI gate. Replays committed cassettes; NO GPU, NO Ollama needed:
uv run -m atlas_evals.gate                 # → metrics report + green/red verdict (exit code)

# (b) LIVE record/calibrate — needs infra up + a RESUMED GPU with both models pulled.
#     gpu-up resumes + discovers OLLAMA_BASE_URL; gpu-down GUARANTEES the pause afterwards:
make -C infra gpu-up
set -a && . ./.env && set +a
mvn -pl rag-engine spring-boot:run &        # boot rag-engine; ingest the corpus (admin)
curl -sX POST localhost:8081/v1/admin/ingest -H 'X-Atlas-User: bsa-admin' | jq
uv run -m atlas_evals.record               # records cassettes vs live RAG + llama3.1 judge
uv run -m atlas_evals.gate --recalibrate   # rewrites data/baseline.json from the live run
make -C infra gpu-down                       # pause the GPU (also auto-paused on idle-timeout)
```
> Cassette key = hash(prompt + model + inputs); a **miss fails loudly** (never a silent live call). Refresh
> cassettes whenever the prompt, model tag, corpus, or golden set changes — then pause the GPU again (§2.4).

### 6.4 Live calibration job (periodic, not the PR gate)
A manual `workflow_dispatch` GitHub Actions workflow calls the GPU helper end-to-end: **resume → record →
`--recalibrate` → guaranteed pause** against the live endpoint (optionally the frontier judge
`ATLAS_EVAL_JUDGE_FRONTIER_MODEL`), committing refreshed cassettes + baseline and recording drift. The
per-PR `evals` job stays GPU-free.

## 7. Production deploy — *added in P5*
Oracle Cloud Ampere A1 (arm64) deploy steps; Hetzner fallback. The P0 multi-arch image already targets arm64.
