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

    def resume(self, run_id, approved, note):
        self.calls.append(("resume", run_id, approved, note))
        return self.response

    def get(self, run_id):
        self.calls.append(("get", run_id))
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


def test_resume_returns_run_state():
    resp = RunResponse(runId="run_1", status="COMPLETED", action={"draftRef": "SAR-1"})
    _override(StubRunner(resp))
    r = client.post("/v1/agent/runs/run_1/resume", json={"approved": True, "note": "ok"})
    assert r.status_code == 200
    assert r.json()["status"] == "COMPLETED"


def test_resume_unknown_run_is_404():
    class NoneRunner(StubRunner):
        def resume(self, run_id, approved, note):
            return None

    _override(NoneRunner(RunResponse(runId="x", status="COMPLETED")))
    r = client.post("/v1/agent/runs/missing/resume", json={"approved": True})
    assert r.status_code == 404


def test_get_run_returns_state():
    _override(StubRunner(RunResponse(runId="run_1", status="AWAITING_APPROVAL")))
    r = client.get("/v1/agent/runs/run_1")
    assert r.status_code == 200
    assert r.json()["status"] == "AWAITING_APPROVAL"
