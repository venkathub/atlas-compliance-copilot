"""RagasScorer REPLAY-path test — proves the gate reads per-sample cassettes WITHOUT importing RAGAS
or calling a judge (the offline-gate guarantee). RECORD/live RAGAS is exercised in Task 8."""

import pytest

from atlas_evals.cassettes import CassetteMiss, CassetteStore, Mode
from atlas_evals.metrics.ragas_scorer import RagasScorer
from atlas_evals.metrics.samples import EvalSample


def _scorer(tmp_path, mode):
    return RagasScorer(
        store=CassetteStore(tmp_path, mode),
        judge_model="llama3.1:8b-instruct",
        embed_model="nomic-embed-text",
        base_url="http://gpu:11434",
        fingerprint="ragas:0.2.0",
        metrics=("faithfulness", "context_recall"),
    )


def test_replay_reads_per_sample_cassettes_and_aggregates(tmp_path):
    samples = [
        EvalSample("s1", "q1", "a1", ["c1"], "g1"),
        EvalSample("s2", "q2", "a2", ["c2"], "g2"),
    ]
    # Seed cassettes under each sample's key (what RECORD would have written).
    rec = _scorer(tmp_path, Mode.RECORD)
    store = CassetteStore(tmp_path, Mode.RECORD)
    store.put(rec.key(samples[0]), {"faithfulness": 0.9, "context_recall": 0.7})
    store.put(rec.key(samples[1]), {"faithfulness": 0.7, "context_recall": 0.9})

    means = _scorer(tmp_path, Mode.REPLAY).score(samples)
    assert means["faithfulness"] == pytest.approx(0.8)
    assert means["context_recall"] == pytest.approx(0.8)


def test_replay_miss_fails_loud(tmp_path):
    samples = [EvalSample("s1", "q1", "a1", ["c1"], "g1")]
    with pytest.raises(CassetteMiss):
        _scorer(tmp_path, Mode.REPLAY).score(samples)


def test_changed_answer_changes_key(tmp_path):
    s = _scorer(tmp_path, Mode.REPLAY)
    k1 = s.key(EvalSample("s1", "q", "answer-v1", ["c"], "g"))
    k2 = s.key(EvalSample("s1", "q", "answer-v2", ["c"], "g"))
    assert k1 != k2  # a new RAG answer busts the judge cassette (loud re-record)
