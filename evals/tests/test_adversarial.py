from atlas_evals.datasets.adversarial import CLASSES, load_adversarial
from atlas_evals.datasets.corpus import poisoned_expectations


def test_adversarial_loads_and_validates():
    cases = load_adversarial()
    assert len(cases) == 10
    assert all(c.cls in CLASSES for c in cases)
    assert all(c.id and c.query.strip() for c in cases)


def test_injection_cases_resolve_poisoned_expectation_strings():
    expected = set(poisoned_expectations()["answerMustNotContain"])
    leak_classes = ("injection", "jailbreak", "system-prompt-leak")
    inj = [c for c in load_adversarial() if c.cls in leak_classes]
    assert inj, "expected some injection/jailbreak/system-leak cases"
    for c in inj:
        # references the P1 fixture rather than duplicating it (no drift)
        assert set(c.must_not_contain) == expected


def test_access_bypass_cases_resolve_negative_access_forbidden_docs():
    access = [c for c in load_adversarial() if c.cls == "access-bypass"]
    assert len(access) == 6  # the 6 P1 negative-access cases
    for c in access:
        assert c.forbidden_doc_ids, f"{c.id} resolved no forbidden docs"
        assert c.must_not_cite_above == c.clearance


def test_classes_cover_the_owasp_lanes():
    classes = {c.cls for c in load_adversarial()}
    assert {"injection", "jailbreak", "system-prompt-leak", "access-bypass"} <= classes
