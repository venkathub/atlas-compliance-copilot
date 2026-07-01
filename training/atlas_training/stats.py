"""Report-only statistical rigor for the base-vs-FT delta (P7 Task 5, D8/ADR-0082).

With **N≈30** paired eval cases, deciding on point deltas alone is underpowered (2026 LLM-eval
consensus). This module adds, as **report-only** evidence (the hybrid promotion gate is unchanged),
per-metric **paired-bootstrap 95% confidence intervals** on the delta plus a **paired significance
test**: Wilcoxon signed-rank for the continuous faithfulness metric, McNemar (exact binomial on
discordant pairs) for the binary format-validity / refusal-correctness metrics.

Deliberately **pure stdlib** (``random`` + ``math`` only — no numpy/scipy) so it runs in the
dependency-light GPU-free ``training`` CI job (PyYAML is training's only always-on dep). The
Wilcoxon p-value uses the standard **normal approximation** with continuity + tie correction, which
is accurate at N≈30; the exact permutation variant is a documented fast-follow (ADR-0082).
"""

from __future__ import annotations

import math
import random
from statistics import median

CI_METHOD = "paired_bootstrap_10k"
SIG_TEST = "wilcoxon+mcnemar"  # faithfulness -> Wilcoxon; format/refusal (binary) -> McNemar


def _percentile(sorted_vals: list[float], q: float) -> float:
    """Linear-interpolation percentile (q in [0, 1]) over an already-sorted list."""
    if not sorted_vals:
        raise ValueError("percentile of empty sequence")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q * (len(sorted_vals) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_vals[lo]
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def paired_bootstrap_ci(
    base: list[float],
    ft: list[float],
    *,
    n_resamples: int = 10_000,
    ci: float = 0.95,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile bootstrap 95% CI on the mean paired delta (ft - base). Deterministic via seed."""
    if len(base) != len(ft):
        raise ValueError("paired_bootstrap_ci: base and ft must be the same length")
    n = len(base)
    if n == 0:
        raise ValueError("paired_bootstrap_ci: empty inputs")
    deltas = [ft[i] - base[i] for i in range(n)]
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(n_resamples):
        s = 0.0
        for _ in range(n):
            s += deltas[rng.randrange(n)]
        means.append(s / n)
    means.sort()
    lo_q = (1 - ci) / 2
    hi_q = 1 - lo_q
    return round(_percentile(means, lo_q), 4), round(_percentile(means, hi_q), 4)


def _normal_sf(z: float) -> float:
    """Survival function 1 - Φ(z) via erfc — stdlib only."""
    return 0.5 * math.erfc(z / math.sqrt(2))


def wilcoxon_signed_rank_p(base: list[float], ft: list[float]) -> float:
    """Two-sided Wilcoxon signed-rank p-value (normal approx, continuity + tie correction).

    For the continuous, paired faithfulness metric. Zero differences are dropped (Wilcoxon
    convention). Returns 1.0 when there is no non-zero difference to test.
    """
    if len(base) != len(ft):
        raise ValueError("wilcoxon: base and ft must be the same length")
    diffs = [ft[i] - base[i] for i in range(len(base)) if ft[i] != base[i]]
    n = len(diffs)
    if n == 0:
        return 1.0
    order = sorted(range(n), key=lambda i: abs(diffs[i]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(diffs[order[j + 1]]) == abs(diffs[order[i]]):
            j += 1
        avg_rank = (i + 1 + j + 1) / 2  # average of 1-based ranks in the tie group
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    w_plus = sum(ranks[i] for i in range(n) if diffs[i] > 0)
    w_minus = sum(ranks[i] for i in range(n) if diffs[i] < 0)
    w = min(w_plus, w_minus)
    mean_w = n * (n + 1) / 4
    # tie correction on the variance
    tie_term = 0.0
    absd = sorted(abs(d) for d in diffs)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and absd[j + 1] == absd[i]:
            j += 1
        t = j - i + 1
        if t > 1:
            tie_term += t**3 - t
        i = j + 1
    var_w = n * (n + 1) * (2 * n + 1) / 24 - tie_term / 48
    if var_w <= 0:
        return 1.0
    z = (abs(w - mean_w) - 0.5) / math.sqrt(var_w)  # continuity correction
    return round(min(1.0, 2 * _normal_sf(z)), 4)


def _binom_two_sided_p(k: int, n: int, p: float = 0.5) -> float:
    """Exact two-sided binomial p-value for k successes in n trials (p=0.5 for McNemar)."""
    if n == 0:
        return 1.0

    def pmf(x: int) -> float:
        return math.comb(n, x) * p**x * (1 - p) ** (n - x)

    obs = pmf(k)
    # two-sided: sum probabilities of outcomes no more likely than the observed one
    total = sum(pmf(x) for x in range(n + 1) if pmf(x) <= obs + 1e-12)
    return round(min(1.0, total), 4)


def mcnemar_p(base_bin: list[float], ft_bin: list[float]) -> float:
    """Two-sided McNemar exact p-value on paired binary outcomes (0/1).

    Only the discordant pairs matter: b = base-correct & ft-wrong, c = base-wrong & ft-correct.
    Returns 1.0 when there are no discordant pairs.
    """
    if len(base_bin) != len(ft_bin):
        raise ValueError("mcnemar: base and ft must be the same length")
    b = sum(1 for i in range(len(base_bin)) if base_bin[i] >= 0.5 and ft_bin[i] < 0.5)
    c = sum(1 for i in range(len(base_bin)) if base_bin[i] < 0.5 and ft_bin[i] >= 0.5)
    if b + c == 0:
        return 1.0
    return _binom_two_sided_p(min(b, c), b + c, 0.5)


def paired_stats(
    base: list[float],
    ft: list[float],
    *,
    kind: str,
    n_resamples: int = 10_000,
    seed: int = 0,
) -> dict:
    """Per-metric report-only stats: bootstrap CI on the delta + a paired significance test.

    ``kind='continuous'`` -> Wilcoxon signed-rank (faithfulness);
    ``kind='binary'``     -> McNemar exact (format-validity / refusal-correctness).
    ``significant`` is reported as *the 95% CI excludes 0* (the honest small-N signal).
    """
    lo, hi = paired_bootstrap_ci(base, ft, n_resamples=n_resamples, seed=seed)
    if kind == "continuous":
        test, p = "wilcoxon", wilcoxon_signed_rank_p(base, ft)
    elif kind == "binary":
        test, p = "mcnemar", mcnemar_p(base, ft)
    else:
        raise ValueError(f"unknown kind: {kind!r} (expected 'continuous' or 'binary')")
    return {
        "ci95_delta": [lo, hi],
        "p_value": p,
        "significant": not (lo <= 0.0 <= hi),
        "test": test,
    }


def summarize_delta(base: list[float], ft: list[float]) -> float:
    """Mean paired delta (ft - base), for parity with the median-based p50 reporting elsewhere."""
    n = len(base)
    return round(sum(ft[i] - base[i] for i in range(n)) / n, 4) if n else 0.0


def p50_p95(latencies_ms: list[float]) -> tuple[float, float]:
    """(p50, p95) latency over a per-request latency list, rounded to 1 dp."""
    if not latencies_ms:
        return 0.0, 0.0
    s = sorted(latencies_ms)
    return round(median(s), 1), round(_percentile(s, 0.95), 1)
