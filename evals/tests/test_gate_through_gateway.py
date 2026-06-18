from atlas_evals.client import AtlasRagClient
from atlas_evals.gate import _sut_client
from atlas_evals.gateway_client import GatewayRagClient


def test_sut_defaults_to_rag_engine(monkeypatch):
    monkeypatch.delenv("ATLAS_EVAL_THROUGH_GATEWAY", raising=False)
    assert isinstance(_sut_client(), AtlasRagClient)


def test_sut_through_gateway_when_enabled(monkeypatch):
    monkeypatch.setenv("ATLAS_EVAL_THROUGH_GATEWAY", "true")
    monkeypatch.setenv("GATEWAY_URL", "http://gw:8080")
    client = _sut_client()
    assert isinstance(client, GatewayRagClient)
    assert client.base_url == "http://gw:8080"
