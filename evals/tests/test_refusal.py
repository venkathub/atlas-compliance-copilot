"""Table-driven tests for the deterministic refusal-correctness scorer (P6 Task 6, reused by P7)."""

from __future__ import annotations

import pytest

from atlas_evals.metrics.refusal import RefusalCase, did_refuse, score, score_rate

REFUSE_CASE = RefusalCase(id="r1", question="FY2021 net income?", should_refuse=True,
                          reason="out-of-context")
ANSWER_CASE = RefusalCase(id="a1", question="FY2018 capex?", should_refuse=False)

REFUSAL_OUT = "I can't answer that from the provided sources; FY2021 is missing."
ANSWER_OUT = "FY2018 capex was $1,577 million [doc:financebench_id_03029]."


def test_from_dict():
    c = RefusalCase.from_dict(
        {"id": "x", "question": "q", "should_refuse": 1, "clearance": "public"}
    )
    assert c.should_refuse is True and c.clearance == "public"


def test_from_dict_missing_field():
    with pytest.raises(ValueError, match="missing"):
        RefusalCase.from_dict({"id": "x", "question": "q"})


def test_did_refuse():
    assert did_refuse(REFUSAL_OUT) is True
    assert did_refuse(ANSWER_OUT) is False


@pytest.mark.parametrize(
    "case,output,expected",
    [
        (REFUSE_CASE, REFUSAL_OUT, True),    # correctly refused
        (REFUSE_CASE, ANSWER_OUT, False),    # under-refusal (should have refused)
        (ANSWER_CASE, ANSWER_OUT, True),     # correctly answered
        (ANSWER_CASE, REFUSAL_OUT, False),   # over-refusal
    ],
)
def test_score(case, output, expected):
    assert score(case, output) is expected


def test_score_rate():
    cases = [REFUSE_CASE, ANSWER_CASE]
    assert score_rate(cases, [REFUSAL_OUT, ANSWER_OUT]) == 1.0
    assert score_rate(cases, [ANSWER_OUT, ANSWER_OUT]) == 0.5
    assert score_rate([], []) == 1.0


def test_score_rate_length_mismatch():
    with pytest.raises(ValueError, match="!="):
        score_rate([REFUSE_CASE], [REFUSAL_OUT, ANSWER_OUT])
