"""Environment-driven configuration for the Atlas Agent Orchestrator (CLAUDE.md: never hardcode).

All knobs are 12-factor env vars. Models, endpoints, thresholds, and caps are swappable; nothing
about the LLM or infra is baked into code. Fields whose env name is ATLAS_-prefixed use an explicit
validation alias; the rest map from their upper-cased field name.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Agent service settings (read from the environment / a local .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- HTTP server ---
    agent_port: int = 8083

    # --- Upstream services (agent calls the Gateway for retrieval, the MCP server for actions) ---
    gateway_base_url: str = "http://localhost:8080"
    mcp_base_url: str = "http://localhost:8082/mcp"

    # --- Reasoning model (routed to an existing self-hosted tier; ADR-0042). Used in task 7. ---
    agent_model: str = Field("qwen2.5:7b-instruct", validation_alias="ATLAS_AGENT_MODEL")
    ollama_base_url: str = "http://localhost:11434"

    # --- Durable checkpointer (LangGraph Postgres, ADR-0047) over the shared `agent` schema. ---
    # Full libpq URL, e.g. postgresql://atlas:atlas@localhost:5432/atlas (wins over the parts).
    agent_db_url: str | None = None
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "atlas"
    postgres_user: str = "atlas"
    postgres_password: str = "atlas"
    agent_schema: str = "agent"

    # --- Safety / scaling caps (ASI10). Consumed by the graph in task 7. ---
    agent_max_steps: int = Field(12, validation_alias="ATLAS_AGENT_MAX_STEPS")
    # Bounded retries for the governed tool call — only on connect errors (no duplicate write).
    agent_tool_retries: int = Field(2, validation_alias="ATLAS_AGENT_TOOL_RETRIES")

    # --- Deterministic breach rule (ADR-0049 Q5). Consumed by the assess node in task 7. ---
    sar_reporting_threshold: float = Field(
        10_000.0, validation_alias="ATLAS_SAR_REPORTING_THRESHOLD"
    )

    # --- Observability (ADR-0030). OTel spans export OPT-IN (default off) so tests/CI never reach
    # Langfuse; spans are still created in-process. Reuses the rag-engine/gateway env-var names. ---
    otel_traces_export_enabled: bool = Field(False, validation_alias="OTEL_TRACES_EXPORT_ENABLED")
    otel_exporter_otlp_traces_endpoint: str = Field(
        "http://localhost:3000/api/public/otel/v1/traces",
        validation_alias="OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
    )
    langfuse_otel_auth_header: str = Field("", validation_alias="LANGFUSE_OTEL_AUTH_HEADER")

    # --- Structured logging (P6 Task 3). `plain` (dev) | `json` (prod). Level is standard. ---
    log_format: str = Field("plain", validation_alias="ATLAS_LOG_FORMAT")
    log_level: str = Field("INFO", validation_alias="ATLAS_LOG_LEVEL")

    def db_url(self) -> str:
        """Resolve the libpq connection URL for the checkpointer (explicit URL wins over parts)."""
        if self.agent_db_url:
            return self.agent_db_url
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor (one instance per process)."""
    return Settings()
