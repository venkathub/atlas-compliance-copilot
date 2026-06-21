"""OpenTelemetry tracing for agent runs (ADR-0030, OWASP/ROADMAP §7.3).

A root `agent.run` span with child `agent.node.*` spans (retrieve / assess / approve / act_sar) ties
`run_id` to the trace. Export is OPT-IN (`OTEL_TRACES_EXPORT_ENABLED`, default off) and fail-soft —
when disabled (tests/CI) the global tracer provider is left untouched, so spans become cheap no-ops
and never ship to Langfuse. The OTLP endpoint + auth header reuse the rag-engine/gateway env names
so all three services stitch into one trace view.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.config import Settings

_TRACER_NAME = "atlas.agents"
_configured = False


def setup_tracing(settings: Settings) -> None:
    """Install an OTLP-exporting TracerProvider ONLY when export is enabled (fail-soft).

    When export is disabled (tests/CI/dev default) we intentionally leave the global TracerProvider
    untouched — spans become cheap no-ops, and tests remain free to install their own provider.
    """
    global _configured
    if _configured or not settings.otel_traces_export_enabled:
        return
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider = TracerProvider(resource=Resource.create({"service.name": "atlas-agents"}))
        headers = {}
        if settings.langfuse_otel_auth_header:
            headers["Authorization"] = settings.langfuse_otel_auth_header
        exporter = OTLPSpanExporter(
            endpoint=settings.otel_exporter_otlp_traces_endpoint, headers=headers
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _configured = True
    except Exception:  # noqa: BLE001 - observability must never break the service
        pass


def get_tracer():
    return trace.get_tracer(_TRACER_NAME)


@contextmanager
def run_span(run_id: str, **attrs: Any):
    """Root span for an agent run/resume; node spans nest under it via the active context."""
    with get_tracer().start_as_current_span("agent.run") as span:
        span.set_attribute("atlas.run_id", run_id)
        for key, value in attrs.items():
            if value is not None:
                span.set_attribute(f"atlas.{key}", value)
        yield span


def instrument_node(name: str, fn: Callable[[dict], dict]) -> Callable[[dict], dict]:
    """Wrap a graph node so each execution is a child span `agent.node.{name}`."""

    def wrapped(state: dict) -> dict:
        with get_tracer().start_as_current_span(f"agent.node.{name}"):
            return fn(state)

    return wrapped
