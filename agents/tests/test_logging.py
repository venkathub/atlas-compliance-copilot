"""Structured logging + request-correlation tests (P6 Task 3)."""

import json
import logging

import httpx
from fastapi.testclient import TestClient

from app.api import app
from app.gateway_client import GatewayClient
from app.logging_config import (
    REQUEST_ID_HEADER,
    _JsonFormatter,
    new_request_id,
    request_id_var,
)

client = TestClient(app)


def test_new_request_id_reuses_wellformed_and_rejects_malicious():
    assert new_request_id("gw-propagated.1_AB") == "gw-propagated.1_AB"
    # newline / spaces / control chars -> a fresh safe UUID instead (anti log-injection)
    minted = new_request_id("evil\ninjected log line")
    assert "\n" not in minted
    assert minted != "evil\ninjected log line"
    # absent -> minted
    assert new_request_id(None)


def test_json_formatter_emits_request_id():
    token = request_id_var.set("req-abc.123")
    try:
        record = logging.LogRecord(
            name="app.test", level=logging.INFO, pathname=__file__, lineno=1,
            msg="hello %s", args=("world",), exc_info=None,
        )
        record.request_id = request_id_var.get()
        line = _JsonFormatter().format(record)
    finally:
        request_id_var.reset(token)
    parsed = json.loads(line)
    assert parsed["message"] == "hello world"
    assert parsed["request_id"] == "req-abc.123"
    assert parsed["log.level"] == "INFO"


def test_healthz_response_carries_request_id_header():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.headers.get(REQUEST_ID_HEADER)  # minted when none inbound


def test_inbound_request_id_is_echoed():
    r = client.get("/healthz", headers={REQUEST_ID_HEADER: "client-supplied.42"})
    assert r.headers.get(REQUEST_ID_HEADER) == "client-supplied.42"


def test_gateway_client_forwards_request_id_downstream():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["rid"] = request.headers.get(REQUEST_ID_HEADER)
        return httpx.Response(200, json={"answer": "ok"})

    gw = GatewayClient("http://gw.test", transport=httpx.MockTransport(handler))
    token = request_id_var.set("run-7.abc")
    try:
        gw.query("q", top_k=3, bearer="tok")
    finally:
        request_id_var.reset(token)
    assert seen["rid"] == "run-7.abc"
