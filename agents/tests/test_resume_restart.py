"""Durable resume-after-restart IT (G8 / ADR-0047) — Testcontainers Postgres.

Proves a run interrupted at the HITL gate resumes correctly from a *fresh* graph instance
(simulating a process restart) against the durable Postgres checkpointer — no lost state, no
duplicate write.
"""

import base64
import json

import pytest

try:
    from testcontainers.postgres import PostgresContainer

    _HAS_DOCKER = True
except Exception:  # pragma: no cover
    _HAS_DOCKER = False

from app.checkpointer import open_checkpointer
from app.config import Settings
from app.graph import build_graph
from app.runner import GraphRunner

pytestmark = pytest.mark.skipif(not _HAS_DOCKER, reason="testcontainers not available")

THRESHOLD = 10_000.0
BREACH_PAYLOAD = {
    "answer": "1 open AML exception for Northwind; amount $12,500.00",
    "citations": [
        {"n": 1, "documentId": "l2-nw", "clearance": "compliance", "snippet": "$12,500.00"}
    ],
}


def fake_jwt(sub="priya"):
    payload = base64.urlsafe_b64encode(json.dumps({"sub": sub}).encode()).decode().rstrip("=")
    return f"hdr.{payload}.sig"


class StubGateway:
    def query(self, query, top_k, bearer):
        return BREACH_PAYLOAD


class FakeMcp:
    def __init__(self):
        self.calls = []

    def open_draft_sar(self, bearer, run_id, account, period, rationale, citations):
        self.calls.append(run_id)
        return {"draftRef": "SAR-2026-000042", "status": "DRAFT", "createdAt": "t"}


def _runner(saver, mcp):
    graph = build_graph(
        StubGateway(), THRESHOLD, saver, mcp_client=mcp, token_provider=lambda u: "aud-tok"
    )
    return GraphRunner(graph, max_steps=12)


def test_run_interrupted_at_gate_resumes_after_restart():
    mcp = FakeMcp()
    with PostgresContainer("postgres:16") as pg:
        url = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")
        settings = Settings(agent_db_url=url, agent_schema="agent")

        # Instance #1: start the run → pauses at the durable interrupt (state persisted).
        with open_checkpointer(settings) as saver1:
            start = _runner(saver1, mcp).start("aml?", "Northwind", "2026-Q2", fake_jwt("priya"))
            assert start.status == "AWAITING_APPROVAL"
            run_id = start.runId

        # Instance #2: a brand-new graph + checkpointer (fresh connection) resumes the SAME run.
        with open_checkpointer(settings) as saver2:
            final = _runner(saver2, mcp).resume(run_id, approved=True, note=None)
            assert final.status == "COMPLETED"
            assert final.action["draftRef"] == "SAR-2026-000042"

    assert mcp.calls == [run_id]  # exactly one write, attributed to the originating run
