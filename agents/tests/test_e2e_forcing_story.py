"""End-to-end forcing-story IT (P4_SPEC §2.5, §4.3) — through the REAL graph + checkpointer + the
real GatewayClient/McpClient (their HTTP boundary faked with httpx.MockTransport), against a
Testcontainers Postgres. Consolidates the safety hard gates as explicit end-to-end assertions:

  * happy path: retrieve → breach → interrupt → approve → audited write
  * rejection: approve=false → no write
  * no unapproved write: a started-but-unresumed run performs no write
  * single-use approval (ASI07): a second resume does not write again
  * durable resume-after-restart (G8): a fresh graph instance resumes the run
  * defense-in-depth: a tool-side DENY ends the run FAILED with no draft
  * no breach: under-threshold retrieval completes with no action
"""

import base64
import json

import httpx
import pytest

try:
    from testcontainers.postgres import PostgresContainer

    _HAS_DOCKER = True
except Exception:  # pragma: no cover
    _HAS_DOCKER = False

from app.checkpointer import open_checkpointer
from app.config import Settings
from app.gateway_client import GatewayClient
from app.graph import build_graph
from app.mcp_client import McpClient
from app.runner import GraphRunner

pytestmark = pytest.mark.skipif(not _HAS_DOCKER, reason="testcontainers not available")

THRESHOLD = 10_000.0


def fake_jwt(sub="priya"):
    payload = base64.urlsafe_b64encode(json.dumps({"sub": sub}).encode()).decode().rstrip("=")
    return f"hdr.{payload}.sig"


class FakeBackend:
    """Single httpx.MockTransport handler for the Gateway (/v1/query, /v1/auth/resource-token) and
    the MCP server (/mcp). Records calls so the tests can assert the hard gates."""

    def __init__(self, breach: bool = True, deny: bool = False):
        self.breach = breach
        self.deny = deny
        self.mcp_calls: list[dict] = []
        self.resource_token_calls: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/v1/query":
            assert request.headers.get("authorization", "").startswith("Bearer ")
            amount = "$12,500.00" if self.breach else "$250.00"
            return httpx.Response(
                200,
                json={
                    "answer": f"1 AML exception; amount {amount}",
                    "citations": [
                        {
                            "n": 1,
                            "documentId": "l2-nw",
                            "clearance": "compliance",
                            "snippet": amount,
                        }
                    ],
                },
            )
        if path == "/v1/auth/resource-token":
            user = json.loads(request.content)["user"]
            self.resource_token_calls.append(user)
            return httpx.Response(200, json={"token": f"aud-{user}", "audience": "atlas-mcp-tools"})
        if path == "/mcp":
            body = json.loads(request.content)
            if body["method"] == "initialize":
                return httpx.Response(
                    200,
                    json={"jsonrpc": "2.0", "id": 1, "result": {}},
                    headers={"Mcp-Session-Id": "s"},
                )
            assert request.headers["authorization"].startswith("Bearer aud-")
            self.mcp_calls.append(body["params"]["arguments"])
            if self.deny:
                result = {"isError": True, "content": [{"type": "text", "text": "DENIED"}]}
            else:
                result = {
                    "structuredContent": {
                        "draftRef": "SAR-2026-000099",
                        "status": "DRAFT",
                        "createdAt": "t",
                    },
                    "isError": False,
                }
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": result})
        return httpx.Response(404)


@pytest.fixture(scope="module")
def pg_url():
    with PostgresContainer("postgres:16") as pg:
        yield pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")


def _runner(backend, saver):
    transport = httpx.MockTransport(backend)
    gw = GatewayClient("http://gw", transport=transport)
    mcp = McpClient("http://mcp/mcp", transport=transport)
    graph = build_graph(gw, THRESHOLD, saver, mcp_client=mcp, token_provider=gw.resource_token)
    return GraphRunner(graph, max_steps=12)


def test_happy_path_breach_to_audited_write(pg_url):
    backend = FakeBackend(breach=True)
    with open_checkpointer(Settings(agent_db_url=pg_url, agent_schema="agent")) as saver:
        runner = _runner(backend, saver)
        start = runner.start("aml?", "Northwind", "2026-Q2", fake_jwt("priya"))
        assert start.status == "AWAITING_APPROVAL"
        assert backend.mcp_calls == []  # no write before approval

        final = runner.resume(start.runId, approved=True, note="reviewed")
        assert final.status == "COMPLETED"
        assert final.action["draftRef"] == "SAR-2026-000099"

    assert backend.resource_token_calls == ["priya"]
    assert len(backend.mcp_calls) == 1
    assert backend.mcp_calls[0]["runId"] == start.runId
    assert backend.mcp_calls[0]["citations"] == [1]


def test_rejection_performs_no_write(pg_url):
    backend = FakeBackend(breach=True)
    with open_checkpointer(Settings(agent_db_url=pg_url, agent_schema="agent")) as saver:
        runner = _runner(backend, saver)
        start = runner.start("aml?", "Northwind", "2026-Q2", fake_jwt("priya"))
        final = runner.resume(start.runId, approved=False, note="not warranted")
        assert final.status == "REJECTED"
    assert backend.mcp_calls == []


def test_single_use_approval_no_duplicate_write(pg_url):
    backend = FakeBackend(breach=True)
    with open_checkpointer(Settings(agent_db_url=pg_url, agent_schema="agent")) as saver:
        runner = _runner(backend, saver)
        start = runner.start("aml?", "Northwind", "2026-Q2", fake_jwt("priya"))
        runner.resume(start.runId, approved=True, note=None)
        again = runner.resume(start.runId, approved=True, note=None)
        assert again.status == "COMPLETED"
    assert len(backend.mcp_calls) == 1


def test_resume_after_restart(pg_url):
    backend = FakeBackend(breach=True)
    settings = Settings(agent_db_url=pg_url, agent_schema="agent")
    with open_checkpointer(settings) as saver1:
        start = _runner(backend, saver1).start("aml?", "Northwind", "2026-Q2", fake_jwt("priya"))
        assert start.status == "AWAITING_APPROVAL"
    with open_checkpointer(settings) as saver2:
        final = _runner(backend, saver2).resume(start.runId, approved=True, note=None)
        assert final.status == "COMPLETED"
    assert len(backend.mcp_calls) == 1


def test_tool_side_denial_fails_run_with_no_draft(pg_url):
    backend = FakeBackend(breach=True, deny=True)
    with open_checkpointer(Settings(agent_db_url=pg_url, agent_schema="agent")) as saver:
        runner = _runner(backend, saver)
        start = runner.start("aml?", "Northwind", "2026-Q2", fake_jwt("priya"))
        final = runner.resume(start.runId, approved=True, note=None)
        assert final.status == "FAILED"
        assert final.action is None


def test_no_breach_completes_without_action(pg_url):
    backend = FakeBackend(breach=False)
    with open_checkpointer(Settings(agent_db_url=pg_url, agent_schema="agent")) as saver:
        runner = _runner(backend, saver)
        final = runner.start("aml?", "Northwind", "2026-Q2", fake_jwt("priya"))
        assert final.status == "COMPLETED"
        assert final.proposedAction is None
    assert backend.mcp_calls == []
