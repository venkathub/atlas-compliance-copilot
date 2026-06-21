"""Observability tests: Prometheus /metrics endpoint + OTel run/node spans (in-memory exporter)."""

import base64
import json

from langgraph.checkpoint.memory import MemorySaver
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.graph import build_graph
from app.runner import GraphRunner

THRESHOLD = 10_000.0
BREACH = {
    "answer": "1 exception $12,500.00",
    "citations": [{"n": 1, "documentId": "d", "clearance": "compliance", "snippet": "$12,500.00"}],
}


def fake_jwt(sub="priya"):
    payload = base64.urlsafe_b64encode(json.dumps({"sub": sub}).encode()).decode().rstrip("=")
    return f"hdr.{payload}.sig"


class StubGateway:
    def query(self, query, top_k, bearer):
        return BREACH


class FakeMcp:
    def open_draft_sar(self, bearer, run_id, account, period, rationale, citations):
        return {"draftRef": "SAR-1", "status": "DRAFT", "createdAt": "t"}


def _runner():
    graph = build_graph(
        StubGateway(), THRESHOLD, MemorySaver(), mcp_client=FakeMcp(), token_provider=lambda u: "t"
    )
    return GraphRunner(graph, max_steps=12)


def test_metrics_endpoint_exposes_agent_metrics():
    from fastapi.testclient import TestClient

    from app.api import app

    r = TestClient(app).get("/metrics")
    assert r.status_code == 200
    assert "atlas_agent_runs_started_total" in r.text


def test_run_increments_metrics():
    from app import metrics

    started = metrics.RUNS_STARTED._value.get()
    runner = _runner()
    start = runner.start("aml?", "Northwind", "2026-Q2", fake_jwt())
    runner.resume(start.runId, approved=True, note=None)
    assert metrics.RUNS_STARTED._value.get() == started + 1
    assert metrics.RUNS_TOTAL.labels(status="COMPLETED")._value.get() >= 1
    assert metrics.TOOL_CALLS.labels(outcome="ok")._value.get() >= 1


def test_run_emits_root_and_node_spans():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)  # in-memory provider so spans are captured

    runner = _runner()
    runner.start("aml?", "Northwind", "2026-Q2", fake_jwt())

    names = {s.name for s in exporter.get_finished_spans()}
    assert "agent.run" in names
    assert "agent.node.retrieve" in names
    assert "agent.node.assess" in names
