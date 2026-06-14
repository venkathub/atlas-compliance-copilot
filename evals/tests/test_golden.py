from atlas_evals.datasets.corpus import known_doc_ids
from atlas_evals.datasets.golden import GoldenTuple, load_golden


def test_golden_loads_and_validates():
    tuples = load_golden()
    assert len(tuples) == 22
    assert sum(1 for t in tuples if t.layer == 1) == 12
    assert sum(1 for t in tuples if t.layer == 2) == 10


def test_every_expected_source_doc_resolves_to_real_corpus_doc():
    valid = known_doc_ids()
    for t in load_golden():
        for doc in t.expected_source_docs:
            assert doc in valid, f"{t.id} references non-existent corpus doc {doc}"


def test_ids_are_unique_and_clearances_valid():
    tuples = load_golden()
    assert len({t.id for t in tuples}) == len(tuples)
    assert all(t.clearance in ("public", "analyst", "compliance", "restricted") for t in tuples)


def test_layer1_tuples_are_financebench_sourced():
    for t in load_golden():
        if t.layer == 1:
            assert t.source.startswith("financebench:")
            assert t.expected_source_docs[0].startswith("financebench_id_")


def test_validate_rejects_dangling_doc_reference():
    bad = GoldenTuple(
        id="x", layer=1, clearance="public", question="q", ground_truth="a",
        expected_source_docs=["financebench_id_does_not_exist"], source="x",
    )
    try:
        bad.validate()
        raise AssertionError("expected ValueError for dangling doc ref")
    except ValueError as e:
        assert "not a real corpus doc" in str(e)
