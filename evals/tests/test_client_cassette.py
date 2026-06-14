import pytest

from atlas_evals.cassettes import CassetteMiss, CassetteStore, Mode
from atlas_evals.client import AtlasRagClient, CassettingClient


def _client(response):
    def fake_transport(method, url, headers, body):
        return response

    return AtlasRagClient(base_url="http://rag:8081", transport=fake_transport)


def test_record_then_replay_offline(tmp_path):
    resp = {"answer": "grounded [1]", "contexts": [{"text": "ctx"}]}
    rec = CassettingClient(_client(resp), CassetteStore(tmp_path, Mode.RECORD), fingerprint="fp1")
    assert rec.query("q", "compliance", top_k=6)["answer"] == "grounded [1]"

    # Replay with a client that would explode if called live — proves it's served from cassette.
    def boom(*a):
        raise AssertionError("live call during replay")

    replay = CassettingClient(
        AtlasRagClient(base_url="http://rag:8081", transport=boom),
        CassetteStore(tmp_path, Mode.REPLAY),
        fingerprint="fp1",
    )
    assert replay.query("q", "compliance", top_k=6) == resp


def test_fingerprint_change_busts_cassette(tmp_path):
    resp = {"answer": "x"}
    CassettingClient(_client(resp), CassetteStore(tmp_path, Mode.RECORD), fingerprint="fp1").query(
        "q", "public", top_k=6
    )
    # different model/corpus fingerprint -> different key -> miss in replay
    replay = CassettingClient(
        _client(resp), CassetteStore(tmp_path, Mode.REPLAY), fingerprint="fp2"
    )
    with pytest.raises(CassetteMiss):
        replay.query("q", "public", top_k=6)
