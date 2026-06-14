import pytest

from atlas_evals.cassettes import CassetteMiss, CassetteStore, Mode, cassette_key


def test_key_is_stable_and_order_sensitive():
    assert cassette_key("a", 1, True) == cassette_key("a", 1, True)
    assert cassette_key("a", 1) != cassette_key(1, "a")


def test_record_then_replay_round_trips(tmp_path):
    rec = CassetteStore(tmp_path, Mode.RECORD)
    calls = {"n": 0}

    def produce():
        calls["n"] += 1
        return {"answer": "hi"}

    key = cassette_key("q", "public")
    assert rec.record_or_replay(key, produce) == {"answer": "hi"}
    assert calls["n"] == 1

    rep = CassetteStore(tmp_path, Mode.REPLAY)
    assert rep.record_or_replay(key, produce) == {"answer": "hi"}
    assert calls["n"] == 1  # replay did NOT call produce


def test_replay_miss_fails_loud(tmp_path):
    rep = CassetteStore(tmp_path, Mode.REPLAY)
    with pytest.raises(CassetteMiss):
        rep.record_or_replay(cassette_key("missing"), lambda: {"x": 1})


def test_off_mode_always_calls_live(tmp_path):
    off = CassetteStore(tmp_path, Mode.OFF)
    calls = {"n": 0}

    def produce():
        calls["n"] += 1
        return calls["n"]

    key = cassette_key("k")
    assert off.record_or_replay(key, produce) == 1
    assert off.record_or_replay(key, produce) == 2  # not cached
    assert not list(tmp_path.glob("*.json"))  # nothing written


def test_mode_from_value_defaults_to_replay():
    assert Mode.from_value(None) is Mode.REPLAY
    assert Mode.from_value("record") is Mode.RECORD
