"""Run-API surface tests (FastAPI TestClient; runner overridden — no DB, no graph build)."""

from fastapi.testclient import TestClient

from app.api import app, get_runner
from app.models import ProposedAction, RunResponse

client = TestClient(app)


class StubRunner:
    def __init__(self, response: RunResponse):
        self.response = response
        self.calls = []

    def start(self, query, account, period, bearer):
        self.calls.append((query, account, period, bearer))
        return self.response


def _override(runner):
    app.dependency_overrides[get_runner] = lambda: runner


def teardown_function():
    app.dependency_overrides.clear()


def test_healthz_ok():
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] in ("up", "down")


def test_start_run_breach_returns_awaiting_approval():
    runner = StubRunner(
        RunResponse(
            runId="run_1",
            status="AWAITING_APPROVAL",
            proposedAction=ProposedAction(tool="open_draft_sar", args={"citations": [1]}),
        )
    )
    _override(runner)
    r = client.post(
        "/v1/agent/runs",
        headers={"Authorization": "Bearer tok-123"},
        json={"query": "aml?", "account": "Northwind", "period": "2026-Q2"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "AWAITING_APPROVAL"
    assert runner.calls == [("aml?", "Northwind", "2026-Q2", "tok-123")]


def test_start_run_requires_bearer():
    _override(StubRunner(RunResponse(runId="x", status="COMPLETED")))
    r = client.post(
        "/v1/agent/runs",
        json={"query": "q", "account": "Northwind", "period": "2026-Q2"},
    )
    assert r.status_code == 401


def test_start_run_validates_period():
    _override(StubRunner(RunResponse(runId="x", status="COMPLETED")))
    r = client.post(
        "/v1/agent/runs",
        headers={"Authorization": "Bearer tok"},
        json={"query": "q", "account": "Northwind", "period": "2026Q2"},
    )
    assert r.status_code == 422


def test_resume_not_wired_yet():
    assert client.post("/v1/agent/runs/run_1/resume", json={"approved": True}).status_code == 501


def test_get_run_not_wired_yet():
    assert client.get("/v1/agent/runs/run_1").status_code == 501
