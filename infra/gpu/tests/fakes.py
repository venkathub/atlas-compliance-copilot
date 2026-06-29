"""Shared offline test doubles: a fake JarvisLabs SDK client + a deterministic probe."""

from __future__ import annotations

from atlas_gpu.sdk import InstanceInfo


class FakeJlClient:
    """In-memory ``JlClient`` — records calls, returns ``InstanceInfo``, no network/SDK."""

    def __init__(self, *, endpoints: list[str] | None = None, status: str = "Running"):
        # Two endpoints by default: a generic :6006 URL + a serving URL.
        self._endpoints = endpoints if endpoints is not None else [
            "https://gen-6006.example",
            "https://srv-ollama.example",
        ]
        self._status = status
        self.instances: dict[str, InstanceInfo] = {}
        self.scripts: list[tuple[str, str, str]] = []  # (name, id, body)
        self.created: dict | None = None
        self.paused: list[str] = []
        self.resumed: list[tuple[str, str]] = []
        self.destroyed: list[str] = []
        self._next_id = 1000
        self._next_script = 1

    def seed(self, machine_id: str, status: str) -> None:
        self.instances[machine_id] = InstanceInfo(
            machine_id=machine_id, status=status, endpoints=list(self._endpoints)
        )

    def create_instance(self, **kw) -> InstanceInfo:
        self.created = kw
        mid = str(self._next_id)
        self._next_id += 1
        info = InstanceInfo(
            machine_id=mid, status=self._status, endpoints=list(self._endpoints),
            http_ports=kw.get("http_ports"),
        )
        self.instances[mid] = info
        return info

    def get_instance(self, machine_id: str) -> InstanceInfo:
        return self.instances.get(
            str(machine_id),
            InstanceInfo(
                machine_id=str(machine_id), status=self._status, endpoints=list(self._endpoints)
            ),
        )

    def list_instances(self) -> list[InstanceInfo]:
        return list(self.instances.values())

    def resume_instance(self, machine_id: str) -> InstanceInfo:
        new = str(self._next_id)  # JarvisLabs assigns a new id on resume
        self._next_id += 1
        info = InstanceInfo(machine_id=new, status="Running", endpoints=list(self._endpoints))
        self.instances[new] = info
        self.resumed.append((str(machine_id), new))
        return info

    def pause_instance(self, machine_id: str) -> None:
        self.paused.append(str(machine_id))

    def destroy_instance(self, machine_id: str) -> None:
        self.destroyed.append(str(machine_id))

    def add_script(self, *, script: str, name: str) -> str:
        # Upsert by name (mirrors RealJlClient): refresh an existing script, don't duplicate.
        for i, (n, sid, _body) in enumerate(self.scripts):
            if n == name:
                self.scripts[i] = (n, sid, script)
                return sid
        sid = str(self._next_script)
        self._next_script += 1
        self.scripts.append((name, sid, script))
        return sid


def role_probe(mapping: dict[str, str]):
    """Build a probe that returns the role for any URL containing one of the keys."""

    def _probe(url: str) -> str | None:
        for needle, role in mapping.items():
            if needle in url:
                return role
        return None

    return _probe


# Default probe: classify the example endpoints by substring.
DEFAULT_PROBE = role_probe({"ollama": "ollama", "vllm": "vllm"})
