"""Model-promotion floors (P7 Task 1, ADR-0075/0076, tag ``Promotion``).

The **model-promotion bar**, kept deliberately separate from the P2 ``baseline.json`` code-merge bar
(``atlas_evals.baseline``) so the two calibration lifecycles stay independently legible (D1). This
file only *loads and validates* the committed ``promotion-floors.json``; the decision logic lives in
``atlas_evals.promotion_gate`` (Task 2).

Floor semantics (confirmed D2, hybrid — see ``docs/phases/P7_SPEC.md`` §3):
  * faithfulness — ``abs_floor`` **0.656** (references the same P2 floor value, not the P2 gate
    object) + ``max_regression_vs_base`` 0.05; ``mode`` selects how a regression is judged.
  * format_validity — ``abs_floor`` 0.95 (the P6 adapter's 0.955 passes; base 0.000 blocks).
  * refusal_correctness — ``min_delta_vs_base`` 0.0 (must not regress).
  * cost — ``max_regression_pct_vs_base`` 10.0 (relative band on cost-units-per-request, D3).

GPU-free, no RAGAS import (hard contract): pure JSON + dataclasses.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from atlas_evals.datasets.corpus import DATA_DIR

DEFAULT_PATH = DATA_DIR / "promotion-floors.json"

# Faithfulness regression policies (D2). ``hybrid`` allows a bounded regression above floor only
# when the fine-tune's format objective improves; ``no_regression`` mirrors the strict P2 band;
# ``absolute`` gates on the floor alone.
FAITHFULNESS_MODES = ("hybrid", "no_regression", "absolute")


class FloorConfigError(ValueError):
    """Raised when ``promotion-floors.json`` is malformed, unpinned, or out of range."""


def _require_unit(name: str, value: object) -> float:
    """Validate a value is a real number in the closed unit interval [0, 1]."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise FloorConfigError(f"{name}: expected a number, got {value!r}")
    v = float(value)
    if not 0.0 <= v <= 1.0:
        raise FloorConfigError(f"{name}: {v} out of range [0, 1]")
    return v


@dataclass
class FaithfulnessFloor:
    abs_floor: float
    max_regression_vs_base: float
    mode: str = "hybrid"

    def validate(self) -> None:
        _require_unit("faithfulness.abs_floor", self.abs_floor)
        _require_unit("faithfulness.max_regression_vs_base", self.max_regression_vs_base)
        if self.mode not in FAITHFULNESS_MODES:
            raise FloorConfigError(
                f"faithfulness.mode {self.mode!r} not in {FAITHFULNESS_MODES}"
            )


@dataclass
class FormatFloor:
    abs_floor: float

    def validate(self) -> None:
        _require_unit("format_validity.abs_floor", self.abs_floor)


@dataclass
class RefusalFloor:
    min_delta_vs_base: float = 0.0

    def validate(self) -> None:
        if not isinstance(self.min_delta_vs_base, (int, float)) or isinstance(
            self.min_delta_vs_base, bool
        ):
            raise FloorConfigError(
                f"refusal_correctness.min_delta_vs_base: expected a number, "
                f"got {self.min_delta_vs_base!r}"
            )


@dataclass
class CostFloor:
    max_regression_pct_vs_base: float = 10.0

    def validate(self) -> None:
        v = self.max_regression_pct_vs_base
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            raise FloorConfigError(f"cost.max_regression_pct_vs_base: expected a number, got {v!r}")
        if float(v) < 0.0:
            raise FloorConfigError(f"cost.max_regression_pct_vs_base: {v} must be >= 0")


@dataclass
class PromotionFloors:
    faithfulness: FaithfulnessFloor
    format_validity: FormatFloor
    refusal_correctness: RefusalFloor = field(default_factory=RefusalFloor)
    cost: CostFloor = field(default_factory=CostFloor)
    block_reason_required: bool = True

    def validate(self) -> None:
        self.faithfulness.validate()
        self.format_validity.validate()
        self.refusal_correctness.validate()
        self.cost.validate()
        if not isinstance(self.block_reason_required, bool):
            raise FloorConfigError("block_reason_required must be a boolean")

    def to_json(self) -> dict:
        return asdict(self)


_REQUIRED_BLOCKS = ("faithfulness", "format_validity")


def load_floors(path: Path = DEFAULT_PATH) -> PromotionFloors:
    """Load + validate the committed promotion-floors config. Hard-fails on any malformation."""
    try:
        obj = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise FloorConfigError(f"promotion-floors config not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise FloorConfigError(f"promotion-floors config is not valid JSON: {exc}") from exc

    if not isinstance(obj, dict):
        raise FloorConfigError("promotion-floors config must be a JSON object")
    for block in _REQUIRED_BLOCKS:
        if block not in obj:
            raise FloorConfigError(f"promotion-floors config missing required block: {block!r}")

    try:
        floors = PromotionFloors(
            faithfulness=FaithfulnessFloor(**obj["faithfulness"]),
            format_validity=FormatFloor(**obj["format_validity"]),
            refusal_correctness=RefusalFloor(**obj.get("refusal_correctness", {})),
            cost=CostFloor(**obj.get("cost", {})),
            block_reason_required=obj.get("block_reason_required", True),
        )
    except TypeError as exc:  # unexpected/missing keys inside a block
        raise FloorConfigError(f"promotion-floors config has malformed block: {exc}") from exc

    floors.validate()
    return floors
