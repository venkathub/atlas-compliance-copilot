"""Cassette record/replay — the heart of the offline, deterministic PR gate (D-P2-1c).

A cassette captures a live LLM/embedding/HTTP response keyed by a hash of its inputs. The merge
gate runs in ``REPLAY`` mode: every call is served from a committed cassette, so it is offline,
free, and reproducible — and a **miss fails loudly** (a changed prompt/model/corpus) rather than
silently calling out to a live endpoint. A separate live job re-records (``RECORD``) periodically.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class Mode(StrEnum):
    OFF = "off"  # pass-through: always call live, never touch cassettes
    RECORD = "record"  # call live, then persist the response (overwrites)
    REPLAY = "replay"  # serve from cassette only; a miss is a hard error
    FILL = "fill"  # serve existing cassettes; record only the missing ones (resumable record)

    @classmethod
    def from_value(cls, value: str | None) -> Mode:
        return cls(value) if value else cls.REPLAY


class CassetteMiss(RuntimeError):
    """Raised in REPLAY mode when no cassette exists for a key (fail loud, never call live)."""


def cassette_key(*parts: Any) -> str:
    """Stable sha256 (truncated) over canonicalised inputs. Order-sensitive by design."""
    canon = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:32]


@dataclass
class CassetteStore:
    """A directory of ``<key>.json`` cassettes with a record/replay policy."""

    directory: Path
    mode: Mode = Mode.REPLAY

    def _path(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def get(self, key: str) -> Any:
        path = self._path(key)
        if not path.exists():
            raise CassetteMiss(
                f"cassette miss for key {key} in {self.directory} — "
                "re-record cassettes (prompt/model/corpus changed?)"
            )
        return json.loads(path.read_text())["response"]

    def put(self, key: str, response: Any, meta: dict | None = None) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        self._path(key).write_text(
            json.dumps({"meta": meta or {}, "response": response}, ensure_ascii=False, indent=2)
        )

    def record_or_replay(
        self, key: str, produce: Callable[[], Any], meta: dict | None = None
    ) -> Any:
        """Replay if available/required; record from ``produce`` when live; OFF = pass-through."""
        if self.mode is Mode.REPLAY:
            return self.get(key)  # miss -> CassetteMiss (loud)
        if self.mode is Mode.OFF:
            return produce()
        if self.mode is Mode.FILL and self._path(key).exists():
            return self.get(key)  # resumable record: keep what we already have
        response = produce()  # RECORD, or a FILL miss
        self.put(key, response, meta)
        return response
