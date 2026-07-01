"""GPU-free unit tests for alias-based promote/rollback (P7 Task 6, ADR-0079).

mlflow is never imported — the registry is a fake with in-memory alias storage.
"""

from __future__ import annotations

import pytest

from atlas_training.tracking import (
    CHAMPION,
    PREVIOUS,
    TrackingError,
    promote,
    rollback,
)

NAME = "atlas-citation-adapter"


class FakeAliasRegistry:
    """In-memory alias store implementing the RegistryClient alias surface."""

    def __init__(self):
        self.aliases: dict[str, str] = {}
        self.sets: list[tuple[str, str]] = []  # (alias, version) call log

    def set_alias(self, name, alias, version):
        self.aliases[alias] = str(version)
        self.sets.append((alias, str(version)))

    def get_version_by_alias(self, name, alias):
        return self.aliases.get(alias)


def test_promote_first_version_sets_champion_no_previous():
    reg = FakeAliasRegistry()
    out = promote(reg, NAME, "1")
    assert out.action == "promote"
    assert reg.aliases[CHAMPION] == "1"
    assert PREVIOUS not in reg.aliases
    assert out.previous is None


def test_promote_replacing_champion_records_previous():
    reg = FakeAliasRegistry()
    promote(reg, NAME, "1")
    out = promote(reg, NAME, "2")
    assert reg.aliases[CHAMPION] == "2"
    assert reg.aliases[PREVIOUS] == "1"
    assert out.previous == "1"


def test_promote_is_idempotent_and_preserves_rollback_target():
    reg = FakeAliasRegistry()
    promote(reg, NAME, "1")
    promote(reg, NAME, "2")  # champion=2, previous=1
    out = promote(reg, NAME, "2")  # re-promote the sitting champion
    assert out.action == "noop"
    assert reg.aliases[CHAMPION] == "2"
    assert reg.aliases[PREVIOUS] == "1"  # NOT clobbered to 2


def test_promote_accepts_int_version():
    reg = FakeAliasRegistry()
    out = promote(reg, NAME, 5)
    assert reg.aliases[CHAMPION] == "5"
    assert out.champion == "5"


def test_rollback_restores_prior_version():
    reg = FakeAliasRegistry()
    promote(reg, NAME, "1")
    promote(reg, NAME, "2")  # champion=2, previous=1
    out = rollback(reg, NAME)
    assert out.action == "rollback"
    assert reg.aliases[CHAMPION] == "1"  # restored
    assert out.champion == "1"


def test_rollback_is_reversible_swaps_previous():
    reg = FakeAliasRegistry()
    promote(reg, NAME, "1")
    promote(reg, NAME, "2")
    rollback(reg, NAME)                 # champion=1, previous=2
    assert reg.aliases[PREVIOUS] == "2"
    out = promote(reg, NAME, "2")       # roll forward again
    assert reg.aliases[CHAMPION] == "2"
    assert out.previous == "1"


def test_rollback_without_prior_raises():
    reg = FakeAliasRegistry()
    promote(reg, NAME, "1")  # no previous champion recorded
    with pytest.raises(TrackingError, match="nothing was promoted over"):
        rollback(reg, NAME)


def test_rollback_on_empty_registry_raises():
    reg = FakeAliasRegistry()
    with pytest.raises(TrackingError, match="cannot roll back"):
        rollback(reg, NAME)
