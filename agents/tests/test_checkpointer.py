"""Durable checkpointer IT — proves the LangGraph Postgres checkpointer is wired against the `agent`
schema and round-trips state (the foundation for resume-after-restart, G8 / ADR-0047).

Needs Docker (Testcontainers Postgres), like the Java ITs. No GPU, no model.
"""

import pytest

try:
    from testcontainers.postgres import PostgresContainer

    _HAS_DOCKER = True
except Exception:  # pragma: no cover - import guard
    _HAS_DOCKER = False

from app.checkpointer import ensure_schema, open_checkpointer
from app.config import Settings

pytestmark = pytest.mark.skipif(not _HAS_DOCKER, reason="testcontainers not available")


def _settings_for(container: "PostgresContainer") -> Settings:
    return Settings(
        agent_db_url=container.get_connection_url().replace("postgresql+psycopg2://", "postgresql://"),
        agent_schema="agent",
    )


def test_checkpointer_sets_up_and_round_trips_in_agent_schema():
    with PostgresContainer("postgres:16") as pg:
        settings = _settings_for(pg)

        with open_checkpointer(settings) as saver:
            config = {"configurable": {"thread_id": "run_ckpt_1", "checkpoint_ns": ""}}
            checkpoint = {
                "v": 1,
                "id": "ckpt-1",
                "ts": "2026-06-21T10:00:00+00:00",
                "channel_values": {"step": "assess", "breach": True},
                "channel_versions": {},
                "versions_seen": {},
                "pending_sends": [],
            }
            saved_config = saver.put(config, checkpoint, {"source": "test", "step": 1}, {})
            assert saved_config["configurable"]["thread_id"] == "run_ckpt_1"

            loaded = saver.get_tuple(config)
            assert loaded is not None
            assert loaded.checkpoint["channel_values"]["breach"] is True


def test_checkpoint_tables_live_in_the_agent_schema():
    import psycopg

    with PostgresContainer("postgres:16") as pg:
        url = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")
        settings = Settings(agent_db_url=url, agent_schema="agent")

        ensure_schema(url, "agent")
        with open_checkpointer(settings):
            pass  # setup() creates the checkpoint tables

        with psycopg.connect(url) as conn:
            rows = conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'agent'"
            ).fetchall()
        tables = {r[0] for r in rows}
        assert any("checkpoint" in t for t in tables), tables
