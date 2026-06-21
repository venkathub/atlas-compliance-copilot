"""Unit tests for currency-amount extraction (deterministic, no I/O)."""

from app.amounts import extract_amounts


def test_extracts_plain_and_grouped_amounts():
    assert extract_amounts("exception of $12,500.00 flagged") == [12500.0]
    assert extract_amounts("amounts $1,000 and $250") == [1000.0, 250.0]
    assert extract_amounts("$10000") == [10000.0]


def test_handles_no_amounts_and_none():
    assert extract_amounts("no money here") == []
    assert extract_amounts(None) == []
    assert extract_amounts("") == []
