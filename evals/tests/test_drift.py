"""Unit tests for the version-tagged drift emitter (P7 Task 10, D7/ADR-0081)."""

import pytest

from atlas_evals.drift import DEFAULT_JOB, drift_exposition, drop, main, push_drift


def test_exposition_is_version_tagged():
    text = drift_exposition("faithfulness", "3", 0.60, 0.79)
    assert 'atlas_eval_metric_score{metric="faithfulness",model_version="3"} 0.6' in text
    assert 'atlas_model_quality_baseline{metric="faithfulness",model_version="3"} 0.79' in text
    # both TYPE lines present (valid exposition)
    assert text.count("# TYPE ") == 2


def test_exposition_requires_labels():
    with pytest.raises(ValueError, match="non-empty"):
        drift_exposition("", "3", 0.6, 0.79)
    with pytest.raises(ValueError, match="non-empty"):
        drift_exposition("faithfulness", "", 0.6, 0.79)


def test_drop_matches_rule_threshold_semantics():
    # rule fires when (baseline - score) > 0.05
    assert drop(0.60, 0.79) == 0.19            # clearly fires
    assert drop(0.76, 0.79) == pytest.approx(0.03)  # within band, no fire
    assert drop(0.79, 0.79) == 0.0             # flat


def test_push_drift_puts_to_job_group():
    captured = {}

    def fake_opener(req):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["body"] = req.data.decode()

        class _R:
            def close(self):
                captured["closed"] = True

        return _R()

    text = drift_exposition("faithfulness", "3", 0.6, 0.79)
    push_drift(text, "http://pg:9091", opener=fake_opener)
    assert captured["url"] == f"http://pg:9091/metrics/job/{DEFAULT_JOB}"
    assert captured["method"] == "PUT"
    assert "atlas_eval_metric_score" in captured["body"]
    assert captured["closed"] is True


def test_cli_dry_run_without_gateway(capsys, monkeypatch):
    monkeypatch.delenv("PUSHGATEWAY_URL", raising=False)
    rc = main(["--model-version", "3", "--score", "0.60", "--baseline", "0.79"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "drop=+0.190" in out
    assert "dry run" in out
    assert 'model_version="3"' in out
