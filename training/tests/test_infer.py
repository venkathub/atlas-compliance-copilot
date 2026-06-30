"""GPU-free tests for the pure helpers in infer.py (P6 Task 10b).

The heavy generate()/score_outputs() paths are GPU/episodic (pragma: no cover); these cover the
pure prompt helpers, which CI can exercise with no torch/transformers/evals import.
"""

from __future__ import annotations

from atlas_training.data.builder import build_and_write
from atlas_training.data.corpus import load_corpus
from atlas_training.data.synth import build_seed
from atlas_training.infer import Candidate, build_prompt, prompts_from_jsonl


def test_build_prompt_combines_question_and_context():
    p = build_prompt("SYS", "What is X?", "[doc:a] context text")
    assert "What is X?" in p
    assert "[doc:a] context text" in p


def test_build_prompt_without_context():
    assert build_prompt("SYS", "Q?", "") == "Q?"


def test_candidate_dataclass():
    c = Candidate(case_id="c1", prompt="p", output="o [doc:a]", allowed_ids=["a"])
    assert c.allowed_ids == ["a"]
    assert c.output == "o [doc:a]"


def test_prompts_from_jsonl_roundtrips_user_turns(tmp_path):
    pairs = build_seed(load_corpus())
    tp, _ = build_and_write(pairs, seed=42, out_dir=tmp_path)
    prompts = prompts_from_jsonl(tp)
    assert len(prompts) >= 1
    # each prompt is the user turn: question + [doc:ID] context
    assert all("[doc:" in p for p in prompts)


def test_no_torch_imported_at_module_load():
    import sys

    import atlas_training.infer  # noqa: F401

    assert "torch" not in sys.modules
    assert "transformers" not in sys.modules
