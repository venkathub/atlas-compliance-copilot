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
docker buildx create --name atlas --driver docker-container --use
docker buildx inspect --bootstrap        # should list linux/amd64 and linux/arm64
```
Build multi-arch images with `docker buildx build --platform linux/amd64,linux/arm64 ...` (added in P0/P5).

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
- Reserve the larger/frontier model only for final demos (P5); default to the small model in dev.
- Rough outlook: a disciplined pause/resume cadence keeps GPU spend to a few hundred ₹/month.

### 2.5 Security notes
- Ollama has **no auth** by default; the exposed JarvisLabs URL is obscure but not secret. Acceptable for dev.
- Do not put real data through the endpoint until it is fronted by the gateway.
- Hardening option (P3): front the endpoint with an API-key check at the gateway; log decision in `DECISIONS.md`.

---

## 3. Local service stack (Docker Compose) — *added in P0*
Postgres+pgvector, Redis, and (later) Langfuse/Grafana/Prometheus run via `infra/docker-compose.yml`.
Commands and ports will be documented here when P0 lands the compose file.

## 4. Build & test — *added per phase*
Per-module build/test commands (Maven for Java modules, `uv` for Python) documented as each module is built.

## 5. Production deploy — *added in P5*
Oracle Cloud Ampere A1 (arm64) deploy steps; Hetzner fallback.
