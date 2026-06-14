import json

from atlas_evals.baseline import Baseline, MetricThreshold
from atlas_evals.datasets.golden import load_golden
from atlas_evals.gate import GateResult
from atlas_evals.langfuse_sync import build_dataset_items, sync_dataset
from atlas_evals.metrics.adversarial_scorer import AdversarialReport, CaseResult, Violation
from atlas_evals.metrics.ragas_runner import MetricReport
from atlas_evals.report import build_metrics, build_summary, write_report


def _fixture():
    baseline = Baseline(
        metrics={
            "faithfulness": MetricThreshold(baseline=0.9, floor=0.85, max_regression=0.05),
            "citation_correctness": MetricThreshold(baseline=1.0, report_only=True),
        },
        judge_model="llama3.1:8b-instruct",
    )
    metric_report = MetricReport(
        scores={"faithfulness": 0.88, "citation_correctness": 1.0}, n_samples=22
    )
    adv = AdversarialReport(results=[CaseResult("a", "injection")])
    return baseline, metric_report, adv


def test_build_metrics_shape():
    baseline, mr, adv = _fixture()
    m = build_metrics(GateResult(True, []), mr, adv, baseline)
    assert m["gate"]["passed"] is True
    assert m["n_samples"] == 22
    assert m["scores"]["faithfulness"] == 0.88
    assert m["adversarial"]["pass_rate"] == 1.0
    assert m["judge_model"] == "llama3.1:8b-instruct"


def test_build_summary_marks_pass_and_fail():
    baseline, mr, adv = _fixture()
    ok = build_summary(build_metrics(GateResult(True, []), mr, adv, baseline))
    assert "PASS" in ok and "faithfulness" in ok
    bad_case = CaseResult("a", "injection", [Violation("a", "leaked_string", "x")])
    bad_adv = AdversarialReport(results=[bad_case])
    fail = build_summary(build_metrics(GateResult(False, ["faithfulness: 0.80 < floor 0.85"]),
                                       mr, bad_adv, baseline))
    assert "FAIL" in fail and "Gate failures" in fail


def test_write_report_emits_files(tmp_path):
    baseline, mr, adv = _fixture()
    write_report(tmp_path, GateResult(True, []), mr, adv, baseline)
    metrics = json.loads((tmp_path / "metrics.json").read_text())
    assert metrics["scores"]["faithfulness"] == 0.88
    assert (tmp_path / "summary.md").exists()


def test_langfuse_dataset_items_from_real_golden():
    items = build_dataset_items(load_golden())
    assert len(items) == 22
    assert all("query" in it["input"] and it["expected_output"] for it in items)


def test_sync_dataset_with_fake_client():
    calls = {"datasets": [], "items": 0}

    class FakeLangfuse:
        def create_dataset(self, name):
            calls["datasets"].append(name)

        def create_dataset_item(self, dataset_name, input, expected_output, metadata):
            calls["items"] += 1

    n = sync_dataset(FakeLangfuse(), load_golden())
    assert n == 22
    assert calls["items"] == 22
    assert calls["datasets"] == ["atlas-golden"]
