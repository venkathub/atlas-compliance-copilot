import json

from atlas_evals.client import AtlasRagClient


def test_query_sets_clearance_header_and_include_contexts():
    captured = {}

    def fake_transport(method, url, headers, body):
        captured.update(method=method, url=url, headers=headers, body=json.loads(body))
        return {"answer": "ok", "citations": [], "contexts": []}

    client = AtlasRagClient(base_url="http://rag:8081", transport=fake_transport)
    client.query("revenue?", "compliance", user="priya", top_k=6)

    assert captured["method"] == "POST"
    assert captured["url"] == "http://rag:8081/v1/query"
    assert captured["headers"]["X-Atlas-Clearance"] == "compliance"
    assert captured["headers"]["X-Atlas-User"] == "priya"
    assert captured["body"] == {"query": "revenue?", "includeContexts": True, "topK": 6}


def test_query_omits_user_and_topk_when_unset():
    captured = {}

    def fake_transport(method, url, headers, body):
        captured.update(headers=headers, body=json.loads(body))
        return {}

    AtlasRagClient(base_url="http://rag:8081", transport=fake_transport).query(
        "q", "public", include_contexts=False
    )
    assert "X-Atlas-User" not in captured["headers"]
    assert "topK" not in captured["body"]
    assert captured["body"]["includeContexts"] is False
