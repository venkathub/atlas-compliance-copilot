"""Run-API surface tests (FastAPI TestClient; no DB, no graph)."""

from fastapi.testclient import TestClient

from app.api import app

client = TestClient(app)


def test_healthz_ok():
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "agents"
    assert body["db"] in ("up", "down")  # best-effort; no DB required for liveness


def test_start_run_not_wired_yet():
    r = client.post(
        "/v1/agent/runs",
        json={"query": "summarize AML exceptions", "account": "Northwind", "period": "2026-Q2"},
    )
    assert r.status_code == 501


def test_resume_not_wired_yet():
    r = client.post("/v1/agent/runs/run_1/resume", json={"approved": True})
    assert r.status_code == 501


def test_get_run_not_wired_yet():
    r = client.get("/v1/agent/runs/run_1")
    assert r.status_code == 501


def test_start_run_validates_period():
    # Bad period pattern → 422 before reaching the (unimplemented) handler.
    r = client.post(
        "/v1/agent/runs",
        json={"query": "q", "account": "Northwind", "period": "2026Q2"},
    )
    assert r.status_code == 422


def test_start_run_requires_fields():
    r = client.post("/v1/agent/runs", json={"query": "q"})
    assert r.status_code == 422
