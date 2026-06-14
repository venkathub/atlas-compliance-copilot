from atlas_evals.baseline import Baseline, MetricThreshold, calibrate
from atlas_evals.gate import evaluate_gate
from atlas_evals.metrics.adversarial_scorer import AdversarialReport, CaseResult, Violation


def _baseline():
    return Baseline(
        metrics={
            "faithfulness": MetricThreshold(baseline=0.90, floor=0.85, max_regression=0.05),
            "answer_relevancy": MetricThreshold(baseline=0.86, floor=0.81, max_regression=0.05),
            "context_recall": MetricThreshold(baseline=0.82, floor=0.75, max_regression=0.07),
            "context_precision": MetricThreshold(baseline=0.78, report_only=True),
        },
        adversarial_must_pass_rate=1.0,
    )


def _adv(passed=True):
    if passed:
        return AdversarialReport(results=[CaseResult("a", "injection")])
    bad = CaseResult("a", "injection", [Violation("a", "leaked_string", "x")])
    return AdversarialReport(results=[bad])


def test_gate_passes_when_all_above_floor_and_adversarial_clean():
    scores = {"faithfulness": 0.90, "answer_relevancy": 0.86, "context_recall": 0.82,
              "context_precision": 0.5}  # report-only, ignored
    result = evaluate_gate(scores, _adv(True), _baseline())
    assert result.passed
    assert result.failures == []


def test_gate_fails_below_floor():
    scores = {"faithfulness": 0.80, "answer_relevancy": 0.86, "context_recall": 0.82}
    result = evaluate_gate(scores, _adv(True), _baseline())
    assert not result.passed
    assert any("faithfulness" in f and "floor" in f for f in result.failures)


def test_gate_fails_on_regression_band_even_above_floor():
    # context_recall floor 0.75, but baseline 0.82 and max_regression 0.07 -> 0.74 drop is 0.08
    scores = {"faithfulness": 0.90, "answer_relevancy": 0.86, "context_recall": 0.74}
    result = evaluate_gate(scores, _adv(True), _baseline())
    # 0.74 < floor 0.75 AND regressed 0.08 > 0.07 -> fails (either reason)
    assert not result.passed


def test_regression_band_catches_slide_while_above_floor():
    b = Baseline(metrics={
        "faithfulness": MetricThreshold(baseline=0.95, floor=0.80, max_regression=0.05),
    })
    # 0.88 is above floor 0.80 but dropped 0.07 > 0.05 -> regression failure
    result = evaluate_gate({"faithfulness": 0.88}, _adv(True), b)
    assert not result.passed
    assert any("regressed" in f for f in result.failures)


def test_gate_fails_when_adversarial_not_perfect():
    scores = {"faithfulness": 0.90, "answer_relevancy": 0.86, "context_recall": 0.82}
    result = evaluate_gate(scores, _adv(False), _baseline())
    assert not result.passed
    assert any("adversarial" in f for f in result.failures)


def test_missing_gating_metric_fails():
    scores = {"answer_relevancy": 0.86, "context_recall": 0.82}  # faithfulness missing
    result = evaluate_gate(scores, _adv(True), _baseline())
    assert not result.passed
    assert any("faithfulness" in f and "missing" in f for f in result.failures)


def test_calibrate_sets_floor_below_recorded():
    scores = {"faithfulness": 0.90, "answer_relevancy": 0.84, "context_recall": 0.80,
              "context_precision": 0.7, "citation_correctness": 1.0}
    b = calibrate(scores, judge_model="llama3.1:8b-instruct", rag_model="qwen2.5:3b-instruct",
                  embed_model="nomic-embed-text", rag_fingerprint="fp",
                  ragas_fingerprint="ragas:0.2")
    assert b.metrics["faithfulness"].floor == 0.85  # 0.90 - 0.05
    assert b.metrics["faithfulness"].baseline == 0.90
    assert b.metrics["faithfulness"].report_only is False
    assert b.metrics["context_precision"].report_only is True  # not a gating metric
    assert b.metrics["context_precision"].floor is None
    assert b.judge_model == "llama3.1:8b-instruct"
    assert b.adversarial_must_pass_rate == 1.0
