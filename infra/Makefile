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

.PHONY: up down clean health psql redis-cli logs ps

up:
	@cat docker-compose.yml | $(DC) up -d
	@echo "Waiting for Postgres to report healthy..."
	@until [ "$$(docker inspect -f '{{.State.Health.Status}}' atlas-postgres 2>/dev/null)" = "healthy" ]; do sleep 1; done
	@echo "Applying DB init (pgvector + pg_trgm)..."
	@docker exec -i atlas-postgres psql -v ON_ERROR_STOP=1 -U $(POSTGRES_USER) -d $(POSTGRES_DB) < db/init/01-extensions.sql
	@echo "✅ Infra up (postgres + redis healthy, extensions loaded)."

down:
	@cat docker-compose.yml | $(DC) down

clean:
	@cat docker-compose.yml | $(DC) down -v

health:
	@echo "== container health =="
	@docker inspect -f '{{.Name}} -> {{.State.Health.Status}}' atlas-postgres atlas-redis
	@echo "== postgres + pgvector =="
	@docker exec -i atlas-postgres psql -tAc "SELECT 'vector ' || extversion FROM pg_extension WHERE extname='vector';" -U $(POSTGRES_USER) -d $(POSTGRES_DB)
	@echo "== redis =="
	@docker exec atlas-redis redis-cli ping

psql:
	@docker exec -it atlas-postgres psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)

redis-cli:
	@docker exec -it atlas-redis redis-cli

logs:
	@cat docker-compose.yml | $(DC) logs -f

ps:
	@cat docker-compose.yml | $(DC) ps
