"""Table-driven tests for the deterministic format-validity validator (P6 Task 6, reused by P7)."""

from __future__ import annotations

import pytest

from atlas_evals.metrics.format_validity import (
    cited_doc_ids,
    classify,
    is_grounded_refusal,
    score,
)

ALLOWED = {"financebench_id_03029", "l2-aml-policy-overview"}


def test_cited_doc_ids_distinct_in_order():
    out = "A [doc:financebench_id_03029] and again [doc:financebench_id_03029] then [doc:x1]."
    assert cited_doc_ids(out) == ["financebench_id_03029", "x1"]
    assert cited_doc_ids("") == []


@pytest.mark.parametrize(
    "out",
    [
        "I can't answer that from the provided sources.",
        "I cannot answer from the provided context; the FY2021 figure is missing.",
        "The context does not contain Activision Blizzard revenue.",
        "There is not enough information in the provided sources to answer.",
    ],
)
def test_grounded_refusal_detected(out):
    assert is_grounded_refusal(out)


@pytest.mark.parametrize(
    "out",
    [
        "",
        "No.",  # a bare negation is a normal answer, not a grounded refusal
        "The answer is 1,577 million.",
        "I cannot attend the meeting.",  # 'cannot' but not about answering from sources
    ],
)
def test_non_refusals(out):
    assert not is_grounded_refusal(out)


# ── score: cited answers ─────────────────────────────────────────────────────────────────────────


def test_valid_cited_answer():
    out = "FY2018 capex was $1,577 million [doc:financebench_id_03029]."
    assert classify(out, ALLOWED) == "answer"
    assert score(out, ALLOWED) is True


def test_answer_without_citation_invalid():
    assert score("FY2018 capex was $1,577 million.", ALLOWED) is False


def test_answer_with_unresolvable_id_invalid():
    out = "Revenue was $10B [doc:financebench_id_99999]."
    assert classify(out, ALLOWED) == "invalid"
    assert score(out, ALLOWED) is False


def test_answer_with_unknown_id_ok_when_no_allowed_ids():
    # Without an allow-list, a well-formed marker is accepted (syntactic validity only).
    out = "Revenue was $10B [doc:some_id]."
    assert score(out) is True


def test_markers_only_no_text_invalid():
    assert score("[doc:financebench_id_03029]", ALLOWED) is False


# ── score: refusals ──────────────────────────────────────────────────────────────────────────────


def test_valid_grounded_refusal():
    out = "I can't answer that from the provided sources: FY2021 net income is missing."
    assert classify(out, ALLOWED) == "refusal"
    assert score(out, ALLOWED) is True


def test_refusal_that_cites_is_invalid():
    out = "I can't answer from the provided sources [doc:financebench_id_03029]."
    assert classify(out, ALLOWED) == "invalid"
    assert score(out, ALLOWED) is False


def test_empty_is_invalid():
    assert score("") is False
    assert score(None) is False  # type: ignore[arg-type]
