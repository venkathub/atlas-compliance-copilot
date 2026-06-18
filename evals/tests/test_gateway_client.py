import json

from atlas_evals.cassettes import CassetteStore, Mode
from atlas_evals.client import CassettingClient
from atlas_evals.gateway_client import GatewayRagClient


def _transport(calls):
    """A fake transport recording (method, url, headers, body); fakes token + query responses."""

    def fake(method, url, headers, body):
        calls.append({"method": method, "url": url, "headers": headers,
                      "body": json.loads(body) if body else None})
        if url.endswith("/v1/auth/token"):
            return {"token": "jwt-for-" + json.loads(body)["user"], "tokenType": "Bearer"}
        return {"answer": "ok", "citations": [], "contexts": [], "cost": {"costUnits": 0.01}}

    return fake


def test_mints_token_for_mapped_user_and_sends_bearer():
    calls = []
    client = GatewayRagClient(base_url="http://gw:8080", transport=_transport(calls))

    client.query("aml?", "compliance", top_k=6)

    token_call, query_call = calls[0], calls[1]
    assert token_call["url"] == "http://gw:8080/v1/auth/token"
    assert token_call["body"] == {"user": "priya"}  # compliance → priya (sim-IdP dev user)
    assert query_call["url"] == "http://gw:8080/v1/query"
    assert query_call["headers"]["Authorization"] == "Bearer jwt-for-priya"
    assert query_call["body"] == {"query": "aml?", "includeContexts": True, "topK": 6}


def test_token_is_cached_per_clearance():
    calls = []
    client = GatewayRagClient(base_url="http://gw:8080", transport=_transport(calls))

    client.query("q1", "compliance")
    client.query("q2", "compliance")

    token_calls = [c for c in calls if c["url"].endswith("/v1/auth/token")]
    assert len(token_calls) == 1  # second query reuses the cached token


def test_each_clearance_maps_to_its_dev_user():
    expected = {"public": "guest-public", "analyst": "analyst-bob",
                "compliance": "priya", "restricted": "bsa-admin"}
    for clearance, user in expected.items():
        calls = []
        client = GatewayRagClient(base_url="http://gw:8080", transport=_transport(calls))
        client.query("q", clearance)
        assert calls[0]["body"] == {"user": user}


def test_replay_through_gateway_client_serves_cassette_without_calling_it(tmp_path):
    # In REPLAY the cassette is served by key — the Gateway client's transport is never invoked,
    # so the through-Gateway gate runs offline (no Gateway/GPU needed in CI).
    store = CassetteStore(tmp_path, Mode.REPLAY)
    store.put(
        __cassette_key(),
        {"answer": "cached", "citations": [], "contexts": []},
        meta={},
    )
    calls = []
    cassetting = CassettingClient(
        GatewayRagClient(base_url="http://gw:8080", transport=_transport(calls)),
        store,
        fingerprint="fp",
    )
    resp = cassetting.query("aml?", "compliance", top_k=6, include_contexts=True)
    assert resp["answer"] == "cached"
    assert calls == []  # transport untouched in REPLAY


def __cassette_key():
    from atlas_evals.cassettes import cassette_key

    return cassette_key("v1/query", "fp", "aml?", "compliance", 6, True)
