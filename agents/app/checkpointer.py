"""Durable LangGraph checkpointer over the shared Postgres `agent` schema (ADR-0047).

The checkpointer is what makes a run survive an interrupt or a process restart: graph state is
persisted per thread (run) so a paused run can resume. Checkpoint tables live in the dedicated
`agent` schema (isolated from rag-engine's public schema, and alongside mcp-tools' sar_draft /
tool_audit — no name collisions). This module ensures the schema exists and pins the connection's
search_path so LangGraph creates/uses its tables there.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import sql

from app.config import Settings


def ensure_schema(conn_url: str, schema: str) -> None:
    """Create the target schema if absent (so /agents need not depend on mcp-tools migrations)."""
    with psycopg.connect(conn_url, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))


def _with_search_path(conn_url: str, schema: str) -> str:
    """Append a libpq options param pinning the connection's search_path to {schema}."""
    sep = "&" if "?" in conn_url else "?"
    return f"{conn_url}{sep}options=-c%20search_path%3D{schema}"


@contextmanager
def open_checkpointer(settings: Settings) -> Iterator[PostgresSaver]:
    """Open a set-up Postgres checkpointer bound to the `agent` schema."""
    url = settings.db_url()
    ensure_schema(url, settings.agent_schema)
    with PostgresSaver.from_conn_string(_with_search_path(url, settings.agent_schema)) as saver:
        saver.setup()
        yield saver


def ping_db(settings: Settings) -> bool:
    """Best-effort connectivity check for readiness/health (never raises)."""
    try:
        with psycopg.connect(settings.db_url(), connect_timeout=2) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False
