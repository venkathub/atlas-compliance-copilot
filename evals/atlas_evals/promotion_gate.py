"""GPU-free model-promotion gate (P7 Task 2, ADR-0075/0076/0077, tag ``Promotion``).

The **model-version analog** of the P2 code-merge gate (``atlas_evals.gate``): it consumes P6's
committed ``training/results/comparison.json`` (pre-scored ``{base, ft, delta}`` per metric) and
decides **promote / block** against the model-promotion floors (``promotion-floors.json``). Like
``cost_gate.py`` it is a **pure function + thin CLI**; the CLI exits non-zero on a block so CI can
gate on it.

**Hard contract:** no network, no GPU, no RAGAS/judge import. Faithfulness is *read* from the
committed comparison (RAGAS-scored upstream in the episodic window); format/refusal are the
deterministic P6 scorers' committed numbers. This module only applies policy to those numbers.

Faithfulness semantics (confirmed D2 hybrid, ADR-0076): promote iff

    ft >= abs_floor (0.656)
      AND ( ft >= base - max_regression   OR   format-validity *jumped* )
      AND refusal delta >= 0
      AND cost within band (when measured)

i.e. a *bounded, justified* faithfulness regression is tolerated **only** when it buys the format
objective the fine-tune exists for, and **never** below floor. ``mode`` selects the policy:
``hybrid`` (default), ``no_regression`` (strict P2 band, no rescue), ``absolute`` (floor only).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from atlas_evals.datasets.corpus import DATA_DIR
from atlas_evals.promotion_floors import DEFAULT_PATH as FLOORS_PATH
from atlas_evals.promotion_floors import PromotionFloors, load_floors

_EPS = 1e-9

# The hybrid OR-branch fires only when format-validity *jumped* by a large margin AND clears its
# floor (ADR-0076 quantifies "jumped"). The real P6 adapter jumps 0.000 -> 0.955 (+0.955), far above
# this; a flat/small format change cannot rescue a faithfulness regression beyond the band.
_FORMAT_JUMP_MIN_DELTA = 0.25


@dataclass
class Decision:
    metric: str
    value: float | None
    base: float | None
    threshold: float | None
    rule: str
    passed: bool


@dataclass
class PromotionGateResult:
    promoted: bool
    decisions: list[Decision] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)
    model_version: str = ""
    evaluated_at: str = ""
    git_sha: str = ""

    def to_json(self) -> dict:
        d = asdict(self)
        d["decisions"] = [asdict(x) for x in self.decisions]
        return d


class ComparisonError(ValueError):
    """Raised when ``comparison.json`` is missing a required metric block or is malformed."""


def _metric(comparison: dict, name: str) -> dict:
    metrics = comparison.get("metrics")
    if not isinstance(metrics, dict) or name not in metrics:
        raise ComparisonError(f"comparison.json missing required metric block: {name!r}")
    block = metrics[name]
    for key in ("base", "ft"):
        if not isinstance(block.get(key), (int, float)) or isinstance(block.get(key), bool):
            raise ComparisonError(f"comparison metric {name!r} missing numeric {key!r}")
    return block


def _model_version(comparison: dict) -> str:
    ids = comparison.get("model_ids")
    if isinstance(ids, dict) and ids.get("ft"):
        return str(ids["ft"])
    return str(comparison.get("ft_model", ""))


def evaluate_promotion_gate(
    comparison: dict, floors: PromotionFloors, *, git_sha: str = ""
) -> PromotionGateResult:
    """Pure promotion decision over a pre-scored ``comparison.json`` (hybrid D2, ADR-0076)."""
    decisions: list[Decision] = []
    reasons: list[str] = []

    faith = _metric(comparison, "faithfulness")
    fmt = _metric(comparison, "format_validity")
    refusal = _metric(comparison, "refusal_correctness")

    f_ft, f_base = float(faith["ft"]), float(faith["base"])
    fmt_ft, fmt_base = float(fmt["ft"]), float(fmt["base"])
    fc = floors.faithfulness

    # --- faithfulness: floor is absolute in every mode ---
    floor_ok = f_ft + _EPS >= fc.abs_floor
    if not floor_ok:
        reasons.append(
            f"faithfulness {f_ft:.3f} < abs_floor {fc.abs_floor:.3f} (below floor — not promotable)"
        )
    decisions.append(
        Decision("faithfulness_floor", f_ft, f_base, fc.abs_floor, "ft >= abs_floor", floor_ok)
    )

    # --- faithfulness: regression policy (mode-dependent) ---
    within_band = f_ft + _EPS >= f_base - fc.max_regression_vs_base
    format_jumped = (fmt_ft + _EPS >= floors.format_validity.abs_floor) and (
        (fmt_ft - fmt_base) + _EPS >= _FORMAT_JUMP_MIN_DELTA
    )
    if fc.mode == "absolute":
        regression_ok, rule = True, "absolute: floor only"
    elif fc.mode == "no_regression":
        regression_ok = within_band
        rule = f"ft >= base - {fc.max_regression_vs_base:.3f}"
    else:  # hybrid
        regression_ok = within_band or format_jumped
        rule = (
            f"ft >= base - {fc.max_regression_vs_base:.3f} "
            f"OR format jumped >= {_FORMAT_JUMP_MIN_DELTA:.2f}"
        )
    if not regression_ok:
        reasons.append(
            f"faithfulness regressed {f_base - f_ft:.3f} beyond band "
            f"{fc.max_regression_vs_base:.3f} "
            f"(base {f_base:.3f} -> ft {f_ft:.3f}) and format did not jump — mode={fc.mode}"
        )
    decisions.append(
        Decision(
            f"faithfulness_regression[{fc.mode}]",
            f_ft,
            f_base,
            fc.max_regression_vs_base,
            rule,
            regression_ok,
        )
    )

    # --- format-validity: absolute floor ---
    fmt_ok = fmt_ft + _EPS >= floors.format_validity.abs_floor
    if not fmt_ok:
        reasons.append(
            f"format_validity {fmt_ft:.3f} < abs_floor {floors.format_validity.abs_floor:.3f}"
        )
    decisions.append(
        Decision(
            "format_validity",
            fmt_ft,
            fmt_base,
            floors.format_validity.abs_floor,
            "ft >= abs_floor",
            fmt_ok,
        )
    )

    # --- refusal-correctness: must not regress ---
    r_delta = float(refusal.get("delta", float(refusal["ft"]) - float(refusal["base"])))
    r_min = floors.refusal_correctness.min_delta_vs_base
    refusal_ok = r_delta + _EPS >= r_min
    if not refusal_ok:
        reasons.append(
            f"refusal_correctness delta {r_delta:+.3f} < min {r_min:+.3f} (regressed vs base)"
        )
    decisions.append(
        Decision(
            "refusal_correctness",
            float(refusal["ft"]),
            float(refusal["base"]),
            r_min,
            f"delta >= {r_min}",
            refusal_ok,
        )
    )

    # --- cost-regression: relative band, only when measured (D3/ADR-0077) ---
    cost = comparison.get("cost")
    delta_pct = cost.get("delta_pct") if isinstance(cost, dict) else None
    band = floors.cost.max_regression_pct_vs_base
    if delta_pct is None:
        # Cost is captured only in the episodic window (Task 11); absent => not measured, not a
        # block. Recorded as a passing decision with an explicit "not measured" note.
        decisions.append(
            Decision(
                "cost_per_request",
                None,
                None,
                band,
                f"delta_pct <= {band:.1f}% (not measured)",
                True,
            )
        )
    else:
        cost_ok = float(delta_pct) <= band + _EPS
        if not cost_ok:
            reasons.append(
                f"cost/request regressed {float(delta_pct):.1f}% > band {band:.1f}% vs base"
            )
        decisions.append(
            Decision(
                "cost_per_request",
                float(delta_pct),
                0.0,
                band,
                f"delta_pct <= {band:.1f}%",
                cost_ok,
            )
        )

    promoted = all(d.passed for d in decisions)
    # block_reason_required contract: a block must always carry at least one reason.
    if not promoted and floors.block_reason_required and not reasons:
        reasons.append("promotion blocked (see decisions)")

    return PromotionGateResult(
        promoted=promoted,
        decisions=decisions,
        blocked_reasons=reasons,
        model_version=_model_version(comparison),
        evaluated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        git_sha=git_sha or str(comparison.get("git_sha", "")),
    )


def _render_markdown(result: PromotionGateResult) -> str:
    verdict = "PROMOTE ✅" if result.promoted else "BLOCK ⛔"
    lines = [
        "# Model promotion gate",
        "",
        f"**Verdict:** {verdict}",
        f"**Model version:** `{result.model_version or '—'}`",
        f"**Evaluated at:** {result.evaluated_at}  ·  **git sha:** `{result.git_sha or '—'}`",
        "",
        "| Metric | ft | base | threshold | rule | passed |",
        "|---|---|---|---|---|---|",
    ]
    for d in result.decisions:
        val = "—" if d.value is None else f"{d.value:.3f}"
        base = "—" if d.base is None else f"{d.base:.3f}"
        thr = "—" if d.threshold is None else f"{d.threshold}"
        lines.append(
            f"| {d.metric} | {val} | {base} | {thr} | {d.rule} | {'✅' if d.passed else '⛔'} |"
        )
    if result.blocked_reasons:
        lines += ["", "## Blocked reasons", *[f"- {r}" for r in result.blocked_reasons]]
    return "\n".join(lines) + "\n"


def write_report(report_dir: Path, result: PromotionGateResult) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "promotion.json").write_text(json.dumps(result.to_json(), indent=2) + "\n")
    (report_dir / "promotion-summary.md").write_text(_render_markdown(result))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="atlas_evals.promotion_gate",
        description="Atlas GPU-free model-promotion gate (base-vs-FT, floors + cost)",
    )
    ap.add_argument(
        "--comparison",
        default=str(Path("training/results/comparison.json")),
        help="path to the committed comparison.json",
    )
    ap.add_argument("--floors", default=str(FLOORS_PATH), help="path to promotion-floors.json")
    ap.add_argument("--report-dir", default=str(DATA_DIR.parent / "report"))
    ap.add_argument("--git-sha", default="", help="override git sha recorded in the report")
    args = ap.parse_args(argv)

    comp_path = Path(args.comparison)
    if not comp_path.exists():
        print(f"PROMOTION GATE: BLOCK — comparison not found: {comp_path}")
        return 1

    floors = load_floors(Path(args.floors))
    comparison = json.loads(comp_path.read_text())
    result = evaluate_promotion_gate(comparison, floors, git_sha=args.git_sha)
    write_report(Path(args.report_dir), result)

    print("PROMOTION GATE:", "PROMOTE" if result.promoted else "BLOCK")
    print(f"  model_version={result.model_version or '—'}")
    for d in result.decisions:
        val = "—" if d.value is None else f"{d.value:.3f}"
        print(f"  [{'PASS' if d.passed else 'FAIL'}] {d.metric}: {val} ({d.rule})")
    for r in result.blocked_reasons:
        print("  -", r)
    return 0 if result.promoted else 1


if __name__ == "__main__":
    sys.exit(main())
