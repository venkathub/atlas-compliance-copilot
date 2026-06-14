"""GPU provider drivers (JarvisLabs real API; E2E generic seam fallback).

``JarvisLabsProvider`` speaks the **actual** Jarvislabs backend API (verified against a
live account, 2026-06-14): region-aware base URL, ``Authorization: Bearer`` auth,
``users/fetch`` for status/endpoint, ``misc/pause?machine_id=`` to pause, and
``templates/{framework}/resume`` with a rebuilt config payload. ``E2EProvider`` keeps the
generic, env-configurable REST seam (its exact paths confirmed at first E2E calibration).

No third-party deps: HTTP is stdlib ``urllib``. An injectable ``transport`` lets tests
drive the provider without a network.
"""

from __future__ import annotations

import ast
import json
import logging
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

log = logging.getLogger("atlas_gpu")


def _is_success(v: object) -> bool:
    """JarvisLabs returns success as bool True OR the string "True"."""
    return v is True or (isinstance(v, str) and v.strip().lower() == "true")


class GpuProviderError(RuntimeError):
    """Raised when a provider API call fails (never contains the API key)."""


@runtime_checkable
class GpuProvider(Protocol):
    """Minimal contract every provider driver must satisfy."""

    name: str

    def resume(self) -> None:
        """Resume (start) the instance and block until it is Running. Idempotent."""

    def pause(self) -> None:
        """Pause (stop) the instance. MUST be safe to call repeatedly."""

    def status(self) -> str:
        """Return a coarse status string, e.g. 'Running' | 'Paused' | 'unknown'."""

    def endpoint(self) -> str:
        """Return the instance's current public Ollama base URL (may change on resume)."""


# Transport: (method, base_url, func, body, query) -> parsed JSON dict.
Transport = Callable[[str, str, str, dict | None, dict | None], dict]


def _bearer_transport(timeout_s: float, api_key: str) -> Transport:
    """Stdlib urllib transport with Bearer auth. The key is never logged."""

    def _call(method: str, base: str, func: str, body: dict | None, query: dict | None) -> dict:
        url = base.rstrip("/") + "/" + func.lstrip("/")
        if query:
            from urllib.parse import urlencode

            url += "?" + urlencode(query)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                raw = resp.read().decode("utf-8") or "{}"
        except urllib.error.HTTPError as e:  # pragma: no cover - network shape
            raise GpuProviderError(f"{method} {func} -> HTTP {e.code}") from None
        except urllib.error.URLError as e:  # pragma: no cover - network shape
            raise GpuProviderError(f"{method} {func} unreachable: {e.reason}") from None
        try:
            return json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            return {}

    return _call


def _first_endpoint(eps: object) -> str:
    """Normalise the JarvisLabs ``endpoints`` field (list, or stringified list) → str."""
    if isinstance(eps, list):
        return str(eps[0]) if eps else ""
    if isinstance(eps, str) and eps.strip().startswith("["):
        try:
            parsed = ast.literal_eval(eps)
            return str(parsed[0]) if parsed else ""
        except (ValueError, SyntaxError):
            return ""
    return str(eps or "")


def _err_msg(resp: object) -> str:
    if isinstance(resp, dict):
        return str(resp.get("detail") or resp.get("message") or resp.get("error") or resp)
    return str(resp)


@dataclass
class JarvisLabsProvider:
    """Drive a Jarvislabs instance via its real backend API (default provider)."""

    name: str
    api_key: str
    instance_id: str
    api_base: str = "https://backendprod.jarvislabs.net/"
    timeout_s: float = 30.0
    resume_ready_timeout_s: float = 300.0
    transport: Transport | None = None
    # sleep/now injectable for deterministic tests of the resume wait-loop.
    _sleep: Callable[[float], None] = time.sleep
    _now: Callable[[], float] = time.monotonic
    _instance: dict = field(default_factory=dict, repr=False)

    # Region → region-specific backend (pause/resume must hit the instance's region).
    REGION_API_URLS = {
        "india-01": "https://backendprod.jarvislabs.net/",
        "india-noida-01": "https://backendn.jarvislabs.net/",
        "europe-01": "https://backendeu.jarvislabs.net/",
    }

    def _http(self, method: str, base: str, func: str, *, body=None, query=None) -> dict:
        t = self.transport or _bearer_transport(self.timeout_s, self.api_key)
        return t(method, base, func, body, query)

    def _fetch(self) -> dict:
        """Fetch fresh instance details (prod base lists all regions).

        The by-id route (``users/fetch/{id}``) 404s on the current backend, so we treat it
        as best-effort and fall back to the list route, which is the verified path.
        """
        inst = None
        try:
            resp = self._http("GET", self.api_base, f"users/fetch/{self.instance_id}")
            if isinstance(resp, dict) and resp.get("success"):
                inst = resp.get("instance")
        except GpuProviderError:
            inst = None
        if inst is None:  # verified path: list all instances and filter
            resp = self._http("GET", self.api_base, "users/fetch")
            instances = resp.get("instances", []) if isinstance(resp, dict) else []
            for i in instances:
                if str(i.get("machine_id")) == str(self.instance_id):
                    inst = i
                    break
            # machine_id changes on resume (JarvisLabs assigns a new id). If the configured
            # id has drifted but the account holds exactly ONE instance, adopt it so we never
            # lose track of a running GPU (and can always pause it).
            if inst is None and len(instances) == 1:
                inst = instances[0]
                adopted = str(inst.get("machine_id"))
                log.warning(
                    "configured instance %s not found; adopting the only instance %s",
                    self.instance_id,
                    adopted,
                )
                self.instance_id = adopted
        if inst is None:
            raise GpuProviderError(f"jarvislabs: instance {self.instance_id} not found")
        self._instance = inst
        return inst

    def _region_base(self) -> str:
        region = self._instance.get("region")
        return self.REGION_API_URLS.get(region, self.api_base)

    def status(self) -> str:
        return str(self._fetch().get("status", "unknown"))

    def endpoint(self) -> str:
        inst = self._instance or self._fetch()
        url = _first_endpoint(inst.get("endpoints")) or str(inst.get("url", ""))
        if not url:
            raise GpuProviderError("jarvislabs: instance has no endpoint url")
        return url

    def pause(self) -> None:
        inst = self._fetch()
        func = "templates/vm/pause" if inst.get("framework") == "vm" else "misc/pause"
        resp = self._http(
            "POST", self._region_base(), func, body={}, query={"machine_id": self.instance_id}
        )
        if not (isinstance(resp, dict) and _is_success(resp.get("success"))):
            raise GpuProviderError(f"jarvislabs: pause failed: {_err_msg(resp)}")

    def resume(self) -> None:
        inst = self._fetch()
        if str(inst.get("status")) == "Running":
            return
        framework = inst.get("framework") or "pytorch"
        req = {
            "machine_id": self.instance_id,
            "hdd": inst.get("hdd"),
            "name": inst.get("instance_name") or inst.get("name") or "",
            "script_id": inst.get("script_id", ""),
            "script_args": inst.get("script_args", ""),
            "duration": _normalize_duration(inst.get("frequency")),
            "http_ports": inst.get("http_ports") or "",
            "gpu_type": inst.get("gpu_type"),
            "num_gpus": inst.get("num_gpus"),
            "is_reserved": inst.get("is_reserved", True),
            "fs_id": inst.get("fs_id"),
        }
        resp = self._http("POST", self._region_base(), f"templates/{framework}/resume", body=req)
        new_id = resp.get("machine_id") if isinstance(resp, dict) else None
        if not new_id:
            raise GpuProviderError(f"jarvislabs: resume failed: {_err_msg(resp)}")
        # CRITICAL: machine_id changes on resume — adopt the new id so the rest of the
        # session (wait/endpoint/PAUSE) targets the live machine, never a dead id.
        self.instance_id = str(new_id)
        self._wait_until_running()

    def _wait_until_running(self) -> None:
        deadline = self._now() + self.resume_ready_timeout_s
        while True:
            st = str(self._fetch().get("status"))
            if st == "Running":
                return
            if st == "Failed":
                raise GpuProviderError("jarvislabs: instance reached Failed during resume")
            if self._now() >= deadline:
                raise GpuProviderError("jarvislabs: timed out waiting for Running")
            self._sleep(10.0)


def _normalize_duration(raw: object) -> str:
    mapping = {"hourly": "hour", "weekly": "week", "monthly": "month"}
    if isinstance(raw, str):
        return mapping.get(raw.lower(), raw)
    return "hour"


@dataclass
class E2EProvider:
    """Generic env-configurable REST seam (E2E Networks fallback).

    Concrete paths are confirmed at first live E2E calibration (TODO); the value here is
    the abstraction + Bearer secret handling that ``lifecycle.py`` enforces pause on top of.
    """

    name: str
    api_base: str
    api_key: str
    instance_id: str
    timeout_s: float = 30.0
    resume_path: str = "/instances/{id}/resume"
    pause_path: str = "/instances/{id}/pause"
    status_path: str = "/instances/{id}"
    status_field: str = "status"
    endpoint_field: str = "url"
    transport: Transport | None = None
    _last_status: dict = field(default_factory=dict, repr=False)

    def _http(self, method: str, func: str) -> dict:
        t = self.transport or _bearer_transport(self.timeout_s, self.api_key)
        return t(method, self.api_base, func.format(id=self.instance_id), None, None)

    def resume(self) -> None:
        self._http("POST", self.resume_path)

    def pause(self) -> None:
        self._http("POST", self.pause_path)

    def status(self) -> str:
        self._last_status = self._http("GET", self.status_path)
        return str(self._last_status.get(self.status_field, "unknown"))

    def endpoint(self) -> str:
        if not self._last_status:
            self.status()
        url = self._last_status.get(self.endpoint_field, "")
        if not url:
            raise GpuProviderError(f"{self.name}: status response had no '{self.endpoint_field}'")
        return str(url)


def make_provider(name: str | None = None, *, env: dict | None = None) -> GpuProvider:
    """Build a provider from ``GPU_*`` env vars.

    ``GPU_PROVIDER`` (jarvislabs|e2e), ``GPU_API_BASE`` (optional override), ``GPU_API_KEY``,
    ``GPU_INSTANCE_ID``. An unknown provider fails loudly so a typo never silently skips the
    pause.
    """
    env = os.environ if env is None else env
    name = (name or env.get("GPU_PROVIDER") or "jarvislabs").strip().lower()
    api_key = env.get("GPU_API_KEY", "")
    instance_id = env.get("GPU_INSTANCE_ID", "")
    if name == "jarvislabs":
        base = env.get("GPU_API_BASE", "https://backendprod.jarvislabs.net/")
        return JarvisLabsProvider(
            name=name, api_key=api_key, instance_id=instance_id, api_base=base
        )
    if name == "e2e":
        base = env.get("GPU_API_BASE", "https://api.e2enetworks.com")
        return E2EProvider(
            name=name, api_base=base, api_key=api_key, instance_id=instance_id
        )
    raise GpuProviderError(
        f"unknown GPU_PROVIDER '{name}' (expected one of: e2e, jarvislabs)"
    )
