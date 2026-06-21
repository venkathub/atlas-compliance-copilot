"""Config parsing tests (no DB, no network)."""

import importlib

from app.config import Settings


def test_defaults():
    s = Settings()
    assert s.agent_port == 8083
    assert s.gateway_base_url.startswith("http")
    assert s.mcp_base_url.endswith("/mcp")
    assert s.agent_max_steps > 0
    assert s.agent_schema == "agent"


def test_env_override(monkeypatch):
    monkeypatch.setenv("GATEWAY_BASE_URL", "http://gw:9000")
    monkeypatch.setenv("ATLAS_AGENT_MAX_STEPS", "5")
    monkeypatch.setenv("ATLAS_SAR_REPORTING_THRESHOLD", "25000")
    s = Settings()
    assert s.gateway_base_url == "http://gw:9000"
    assert s.agent_max_steps == 5
    assert s.sar_reporting_threshold == 25000.0


def test_db_url_explicit_wins(monkeypatch):
    monkeypatch.setenv("AGENT_DB_URL", "postgresql://u:p@h:5432/d")
    assert Settings().db_url() == "postgresql://u:p@h:5432/d"


def test_db_url_from_parts(monkeypatch):
    monkeypatch.delenv("AGENT_DB_URL", raising=False)
    monkeypatch.setenv("POSTGRES_HOST", "pg")
    monkeypatch.setenv("POSTGRES_USER", "atlas")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    url = Settings().db_url()
    assert url == "postgresql://atlas:secret@pg:5432/atlas"


def test_config_module_imports():
    importlib.import_module("app.config")
