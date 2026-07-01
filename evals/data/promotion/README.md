# Promotion gate fixtures — proof-it-bites (P7 Task 3)

Two committed `comparison.json` fixtures the CI **"Model promotion gate"** check (P7 Task 4) runs the
GPU-free gate (`python -m atlas_evals.promotion_gate`) over, to prove the gate actually **bites**:

| Fixture | Expected | Why |
|---|---|---|
| `pass/comparison.json` | **PROMOTE** (exit 0) | A **copy** of the real committed P6 result (`training/results/comparison.json`, L4 run 2026-06-30). Faithfulness 0.787→0.678 (Δ −0.109, above the 0.656 floor) is tolerated by the hybrid policy because format-validity **jumped** 0.000→0.955 (ADR-0076). |
| `blocked/comparison.json` | **BLOCK** (exit 1) | A hand-authored **sub-floor** adapter: faithfulness `ft` 0.590 **< abs_floor 0.656** — below floor, so it is never promotable even with the same format jump. Isolates the block to the load-bearing faithfulness-floor rule. |

`pass/` is a **copy** (not a symlink) of the real result so the fixture is self-contained and robust
across fresh clones / CI checkouts. Regenerate it by re-copying `training/results/comparison.json`
after a new episodic run (P7 Task 11).

The pass/block contract is also locked into the test suite (`evals/tests/test_promotion_fixtures.py`)
so it cannot silently rot if the gate policy or floors change.
