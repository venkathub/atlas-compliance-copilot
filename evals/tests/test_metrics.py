import pytest

from atlas_evals.datasets.golden import GoldenTuple
from atlas_evals.metrics.citation import citation_resolution_rate, cited_markers
from atlas_evals.metrics.ragas_runner import MetricReport, RagasRunner
from atlas_evals.metrics.samples import build_samples


def _tuple(tid, q="q", gt="a"):
    return GoldenTuple(id=tid, layer=2, clearance="public", question=q, ground_truth=gt,
                       expected_source_docs=["l2-aml-policy-overview"], source="x")


def test_build_samples_joins_response_contexts():
    tuples = [_tuple("t1", q="revenue?", gt="rose")]
    responses = {"t1": {"answer": "up [1]", "contexts": [{"text": "ctx-a"}, {"text": "ctx-b"}]}}
    samples = build_samples(tuples, responses)
    assert samples[0].question == "revenue?"
    assert samples[0].answer == "up [1]"
    assert samples[0].contexts == ["ctx-a", "ctx-b"]
    assert samples[0].ground_truth == "rose"


def test_build_samples_missing_response_raises():
    with pytest.raises(KeyError):
        build_samples([_tuple("t1")], {})


def test_citation_resolution_rate():
    assert citation_resolution_rate("see [1] and [2]", 2) == 1.0
    assert citation_resolution_rate("see [1] and [3]", 2) == 0.5  # [3] dangles
    assert citation_resolution_rate("no citations here", 2) == 1.0  # vacuous
    assert cited_markers("[2] then [2] then [1]") == [2, 1]  # distinct, first-seen order


def test_runner_adds_citation_correctness_and_n_samples():
    class FakeScorer:
        def score(self, samples):
            return {"faithfulness": 0.9, "context_recall": 0.8}

    tuples = [_tuple("t1"), _tuple("t2")]
    responses = {
        "t1": {"answer": "grounded [1]", "contexts": [{"text": "c"}]},
        "t2": {"answer": "bad [5]", "contexts": [{"text": "c"}]},  # [5] dangles
    }
    report = RagasRunner(FakeScorer()).run(tuples, responses)
    assert isinstance(report, MetricReport)
    assert report.n_samples == 2
    assert report.scores["faithfulness"] == 0.9
    # citation_correctness = mean(1.0 for t1, 0.0 for t2) = 0.5
    assert report.scores["citation_correctness"] == 0.5
