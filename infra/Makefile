# Atlas — local infra (Postgres+pgvector, Redis).
#
# Snap-Docker safe: the snap `docker` binary is AppArmor-confined and CANNOT read
# files under /data (our workspace). So we never pass it a /data path:
#   - the compose file is piped in via stdin (`cat ... | docker compose -f -`),
#   - config is passed through exported env vars (not --env-file),
#   - DB init SQL is streamed via `docker exec` stdin (not a bind mount),
#   - data persists in named volumes (not host binds).
#
# Usage (from anywhere):  make -C infra up | health | down | clean
ENV_FILE ?= ../.env

# Load POSTGRES_* / REDIS_* / ports into make AND export them so `docker compose`
# (reading the piped file) can interpolate ${...} from its environment.
include $(ENV_FILE)
export

DC := docker compose -p atlas -f -

.PHONY: up down clean health psql redis-cli logs ps seed-config obs-health gpu-up gpu-down gpu-test

up:
	@echo "Starting data stores (postgres, redis, clickhouse, minio)..."
	@cat docker-compose.yml | $(DC) up -d postgres redis clickhouse minio
	@echo "Waiting for Postgres to report healthy..."
	@until [ "$$(docker inspect -f '{{.State.Health.Status}}' atlas-postgres 2>/dev/null)" = "healthy" ]; do sleep 1; done
	@echo "Applying DB init (pgvector + pg_trgm)..."
	@docker exec -i atlas-postgres psql -v ON_ERROR_STOP=1 -U $(POSTGRES_USER) -d $(POSTGRES_DB) < db/init/01-extensions.sql
	@echo "Applying Langfuse DB init..."
	@docker exec -i atlas-postgres psql -v ON_ERROR_STOP=1 -U $(POSTGRES_USER) -d $(POSTGRES_DB) < db/init/02-langfuse-db.sql
	@echo "Seeding observability configs into named volumes (Snap-Docker safe)..."
	@$(MAKE) --no-print-directory seed-config
	@echo "Starting observability stack (langfuse, prometheus, grafana)..."
	@cat docker-compose.yml | $(DC) up -d
	@echo "✅ Infra up (data stores + langfuse + prometheus + grafana)."

# Stream Prometheus + Grafana config from repo files into named volumes. Snap-Docker
# cannot bind-mount /data, so `make` (running as the user, which CAN read /data) reads
# the files and pipes them to a throwaway busybox over stdin — same trick as the DB init.
seed-config:
	@docker volume create atlas-prometheus-config >/dev/null
	@docker volume create atlas-grafana-config >/dev/null
	@sed 's/$${RAG_ENGINE_PORT}/$(RAG_ENGINE_PORT)/g; s/$${GATEWAY_PORT}/$(GATEWAY_PORT)/g' prometheus/prometheus.yml \
		| docker run --rm -i -v atlas-prometheus-config:/dest busybox sh -c 'cat > /dest/prometheus.yml'
	@tar -C grafana -cf - . | docker run --rm -i -v atlas-grafana-config:/dest busybox tar -C /dest -xf -

down:
	@cat docker-compose.yml | $(DC) down

clean:
	@cat docker-compose.yml | $(DC) down -v
	@docker volume rm -f atlas-prometheus-config atlas-grafana-config >/dev/null 2>&1 || true

health:
	@echo "== container health =="
	@docker inspect -f '{{.Name}} -> {{.State.Health.Status}}' atlas-postgres atlas-redis atlas-clickhouse 2>/dev/null || true
	@echo "== postgres + pgvector =="
	@docker exec -i atlas-postgres psql -tAc "SELECT 'vector ' || extversion FROM pg_extension WHERE extname='vector';" -U $(POSTGRES_USER) -d $(POSTGRES_DB)
	@echo "== langfuse db =="
	@docker exec -i atlas-postgres psql -tAc "SELECT datname FROM pg_database WHERE datname='langfuse';" -U $(POSTGRES_USER) -d $(POSTGRES_DB)
	@echo "== redis =="
	@docker exec atlas-redis redis-cli ping
	@$(MAKE) --no-print-directory obs-health

# Observability reachability from the host (Langfuse/Grafana have no in-image healthcheck).
obs-health:
	@echo "== langfuse web ($(LANGFUSE_HOST)) =="
	@curl -fsS -o /dev/null -w 'HTTP %{http_code}\n' "$(LANGFUSE_HOST)/api/public/health" || echo "unreachable (still booting? run: make -C infra logs)"
	@echo "== prometheus targets =="
	@curl -fsS "http://localhost:$(PROMETHEUS_PORT)/api/v1/targets" 2>/dev/null \
		| sed 's/.*"job":"\(rag-engine\)".*"health":"\([a-z]*\)".*/  rag-engine target: \2/' | head -1 \
		&& echo "" \
		|| echo "  prometheus unreachable"
	@echo "== grafana =="
	@curl -fsS -o /dev/null -w 'HTTP %{http_code}\n' "http://localhost:$(GRAFANA_PORT)/api/health" || echo "unreachable"

psql:
	@docker exec -it atlas-postgres psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)

redis-cli:
	@docker exec -it atlas-redis redis-cli

# ── GPU lifecycle (P2, ADR-0029 / D-P2-9) ───────────────────────────────────
# Fail-safe resume/pause of the Cloud Ollama GPU. `gpu-up` resumes + discovers the
# fresh OLLAMA_BASE_URL (written back into $(ENV_FILE)) + arms the idle watchdog;
# `gpu-down` GUARANTEES a pause. Stdlib-only Python helper in infra/gpu.
gpu-up:
	@uv run --directory gpu python -m atlas_gpu up --write-env $(abspath $(ENV_FILE))
	@echo "↻ re-source env to pick up the new endpoint:  set -a && . $(ENV_FILE) && set +a"

gpu-down:
	@uv run --directory gpu python -m atlas_gpu down

gpu-test:
	@uv run --directory gpu --with pytest pytest -q

logs:
	@cat docker-compose.yml | $(DC) logs -f

ps:
	@cat docker-compose.yml | $(DC) ps
