"""Structured logging + request correlation for the Agent Orchestrator (P6 Task 3).

The service previously had no application logging at all. This adds, with **no extra dependency**
(stdlib `logging` + `json`):

* JSON (prod) or human-readable (dev) logs, selected by ``ATLAS_LOG_FORMAT`` (``json`` | ``plain``);
* a per-request correlation id held in a :class:`~contextvars.ContextVar`, injected into every log
  record and forwarded on the ``X-Request-Id`` header to the gateway / MCP hops, so a single agent
  run stitches across services in the trace/log view.

Inbound ids are validated against a strict allow-list before use (untrusted input — anti
log-injection), mirroring the Spring ``RequestIdFilter``.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
import sys
import uuid
from contextvars import ContextVar

REQUEST_ID_HEADER = "X-Request-Id"
_SAFE_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")

# The current request's correlation id (None outside a request).
request_id_var: ContextVar[str | None] = ContextVar("atlas_request_id", default=None)


def new_request_id(inbound: str | None = None) -> str:
    """Reuse a well-formed inbound id (propagated from the gateway) else mint a fresh UUID."""
    if inbound and _SAFE_ID.fullmatch(inbound):
        return inbound
    return str(uuid.uuid4())


def current_request_id() -> str | None:
    return request_id_var.get()


class _RequestIdFilter(logging.Filter):
    """Attach the contextvar request id to every record (so formatters can render it)."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003 - logging API name
        record.request_id = request_id_var.get() or "-"
        return True


class _JsonFormatter(logging.Formatter):
    """Compact one-line JSON suitable for a log shipper (ECS-ish shape)."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.datetime.fromtimestamp(
            record.created, tz=datetime.UTC
        ).isoformat()
        payload: dict[str, object] = {
            "@timestamp": timestamp,
            "log.level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(fmt: str = "plain", level: str = "INFO") -> None:
    """Install a single stdout handler with the request-id filter and the chosen formatter.

    Idempotent: replaces existing root handlers so repeated calls (e.g. tests) don't duplicate.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_RequestIdFilter())
    if fmt.lower() in ("json", "ecs"):  # 'ecs' is the Spring services' value — treat as JSON here
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-5s %(name)s [%(request_id)s] %(message)s")
        )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    # Tame noisy third-party loggers a touch in prod JSON mode.
    logging.getLogger("httpx").setLevel(logging.WARNING)
