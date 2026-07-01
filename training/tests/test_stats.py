"""GPU-free unit tests for the report-only statistics module (P7 Task 5, D8/ADR-0082).

Pure stdlib math — no numpy/scipy, no GPU. Deterministic bootstrap via fixed seed.
"""

from __future__ import annotations

from atlas_training.stats import (
    mcnemar_p,
    p50_p95,
    paired_bootstrap_ci,
    paired_stats,
    wilcoxon_signed_rank_p,
)


def test_bootstrap_ci_brackets_the_mean_delta():
    base = [0.5] * 20
    ft = [0.7] * 20  # constant +0.2 delta -> CI collapses on 0.2
    lo, hi = paired_bootstrap_ci(base, ft, n_resamples=2000, seed=1)
    assert lo == hi == 0.2


def test_bootstrap_ci_is_deterministic_with_seed():
    base = [0.1 * i for i in range(30)]
    ft = [0.1 * i + 0.05 for i in range(30)]
    a = paired_bootstrap_ci(base, ft, n_resamples=3000, seed=7)
    b = paired_bootstrap_ci(base, ft, n_resamples=3000, seed=7)
    assert a == b


def test_bootstrap_ci_excludes_zero_for_a_clear_shift():
    base = [0.60 + 0.001 * i for i in range(30)]
    ft = [0.75 + 0.001 * i for i in range(30)]  # ~+0.15 everywhere
    lo, hi = paired_bootstrap_ci(base, ft, n_resamples=4000, seed=3)
    assert lo > 0.0 and hi > 0.0


def test_wilcoxon_significant_for_consistent_shift():
    base = [0.5 + 0.01 * i for i in range(25)]
    ft = [b + 0.2 for b in base]  # every pair increases -> very small p
    p = wilcoxon_signed_rank_p(base, ft)
    assert 0.0 <= p < 0.05


def test_wilcoxon_p_is_one_for_no_difference():
    base = [0.4, 0.5, 0.6, 0.7]
    assert wilcoxon_signed_rank_p(base, list(base)) == 1.0


def test_mcnemar_significant_when_ft_fixes_many_and_breaks_none():
    # base all wrong (0), ft all right (1): 20 discordant pairs, all one direction -> tiny p.
    base = [0.0] * 20
    ft = [1.0] * 20
    p = mcnemar_p(base, ft)
    assert 0.0 <= p < 0.001


def test_mcnemar_p_is_one_with_no_discordant_pairs():
    base = [1.0, 0.0, 1.0, 0.0]
    assert mcnemar_p(base, list(base)) == 1.0


def test_mcnemar_symmetric_discordance_not_significant():
    # 3 fixed, 3 broken -> balanced discordance -> p == 1.0 (two-sided exact at k=3,n=6)
    base = [1, 1, 1, 0, 0, 0]
    ft = [0, 0, 0, 1, 1, 1]
    p = mcnemar_p([float(x) for x in base], [float(x) for x in ft])
    assert p == 1.0


def test_paired_stats_continuous_shape():
    base = [0.5 + 0.01 * i for i in range(30)]
    ft = [b + 0.2 for b in base]
    s = paired_stats(base, ft, kind="continuous", seed=0)
    assert s["test"] == "wilcoxon"
    assert set(s) == {"ci95_delta", "p_value", "significant", "test"}
    assert s["significant"] is True
    assert len(s["ci95_delta"]) == 2


def test_paired_stats_binary_uses_mcnemar():
    base = [0.0] * 15
    ft = [1.0] * 15
    s = paired_stats(base, ft, kind="binary", seed=0)
    assert s["test"] == "mcnemar"
    assert s["significant"] is True


def test_faithfulness_regression_not_significant_when_ci_crosses_zero():
    # A noisy -0.109-ish mean whose bootstrap CI straddles 0 -> reported NOT significant (the honest
    # small-N signal the D8 narrative needs).
    base = [0.8, 0.6, 0.9, 0.5, 0.7, 0.85, 0.55, 0.75, 0.65, 0.95]
    ft = [0.5, 0.7, 0.6, 0.8, 0.4, 0.9, 0.5, 0.6, 0.7, 0.6]
    s = paired_stats(base, ft, kind="continuous", seed=0)
    lo, hi = s["ci95_delta"]
    assert lo < 0 < hi
    assert s["significant"] is False


def test_p50_p95():
    lat = [float(x) for x in range(1, 101)]  # 1..100
    p50, p95 = p50_p95(lat)
    assert p50 == 50.5
    assert 95.0 <= p95 <= 96.0
