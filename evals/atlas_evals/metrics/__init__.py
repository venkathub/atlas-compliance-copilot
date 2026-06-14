"""Metric computation for the eval harness.

Split so the *orchestration* (sample-building, the deterministic citation metric, the runner) is
RAGAS-free and unit-testable offline, while the heavy RAGAS integration lives in `ragas_scorer`
(lazy imports) and is exercised against the live judge during calibration (Task 8).
"""
