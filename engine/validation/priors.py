"""Priors over speculative parameters (A2).

The α-engine and exo-engine carry a small inventory of parameters that are
*permanently uncalibrated* — load-bearing knobs whose values have no
historical analog at the 800B-agent scale. Declaring a prior over each is
the precondition for any "X is likely under this artifact" statement.

The priors here are *honest about ignorance*: wide uniform/log-uniform
distributions over the bound the brief argues are plausible, with a
one-line justification per parameter. The point is not to fit; the point
is to expose every claim to a documented uncertainty.

The accompanying sweep (`posterior_sweep.py`) draws Sobol-quasi-random
samples (we want coverage, not Sobol *indices*) from this inventory and
runs the engine at each sample to produce an outcome distribution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


PriorFamily = Literal["uniform", "loguniform"]


@dataclass(frozen=True)
class Prior:
    """A 1D prior over one parameter."""

    name: str
    family: PriorFamily
    low: float
    high: float
    engine: Literal["alpha", "exo"]
    target: str  # dotted path of where the value lands (TopologyConfig.alpha, etc.)
    justification: str

    def map_unit(self, u: float) -> float:
        """Map u ∈ [0, 1] from a Sobol draw to a sample in [low, high]."""
        u = float(min(1.0, max(0.0, u)))
        if self.family == "uniform":
            return self.low + (self.high - self.low) * u
        # log-uniform: assumes low > 0.
        import math
        log_low = math.log(self.low)
        log_high = math.log(self.high)
        return float(math.exp(log_low + (log_high - log_low) * u))


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

# Eleven parameters. Seven on the α-engine, four on the exo. The α-engine
# subset drives the canonical posterior sweep at outputs/validation/
# posterior_sweep.parquet; the exo subset is declared here so that a
# parallel exo sweep (out of scope for A2) inherits the same priors-as-
# documentation contract.

INVENTORY: tuple[Prior, ...] = (
    # ---- alpha-engine speculative knobs ------------------------------------
    Prior(
        name="folding_propensity",
        family="uniform", low=0.10, high=0.85,
        engine="alpha", target="topology.folding_propensity",
        justification=(
            "Top-of-cascade fold rate. No empirical analog. Brief argues "
            "values >0.85 produce uninterpretable runaway; <0.10 mutes the "
            "mechanism entirely."
        ),
    ),
    Prior(
        name="fold_real_efficiency",
        family="uniform", low=0.40, high=0.96,
        engine="alpha", target="topology.fold_real_efficiency",
        justification=(
            "Per-layer real-surplus retention. 0.40 is aggressive value "
            "loss, 0.96 is near-frictionless compounding."
        ),
    ),
    Prior(
        name="fold_nominal_multiplier",
        family="uniform", low=1.0, high=3.0,
        engine="alpha", target="topology.fold_nominal_multiplier",
        justification=(
            "Per-layer nominal multiplication. 1.0 is no GDP inflation; "
            "3.0 saturates the cascade quickly."
        ),
    ),
    Prior(
        name="base_variance_absorption",
        family="uniform", low=0.0, high=0.60,
        engine="alpha", target="topology.base_variance_absorption",
        justification=(
            "Productive folding strength at depth 1. 0.0 is parasitic-only; "
            "0.60 is aggressively productive at maximum capability."
        ),
    ),
    Prior(
        name="productive_decay",
        family="uniform", low=0.40, high=0.95,
        engine="alpha", target="topology.productive_decay",
        justification=(
            "Per-layer decay of productive welfare share. Lower is faster "
            "decay; higher pushes welfare creation deeper into the cascade."
        ),
    ),
    Prior(
        name="max_productive_real_share",
        family="uniform", low=0.30, high=0.90,
        engine="alpha", target="topology.max_productive_real_share",
        justification=(
            "Cap on productive welfare from folding as a share of base "
            "real surplus. Safeguard against free welfare from nominal "
            "recursion."
        ),
    ),
    Prior(
        name="cap_slope",
        family="uniform", low=2.0, high=6.0,
        engine="alpha", target="topology.cap_slope",
        justification=(
            "Sigmoid slope at the productive-fold capability midpoint. "
            "2.0 is gentle; 6.0 is near-step-function bimodal."
        ),
    ),
    # ---- exo-engine speculative knobs --------------------------------------
    Prior(
        name="drag_target_intensity",
        family="uniform", low=0.10, high=0.55,
        engine="exo", target="drag.target_intensity",
        justification=(
            "Equilibrium drag intensity (manual labor of legibility). "
            "0.10 ≈ minimal coordination overhead; 0.55 saturates labor."
        ),
    ),
    Prior(
        name="stack_base_lift_propensity",
        family="uniform", low=0.20, high=0.65,
        engine="exo", target="stack.base_lift_propensity",
        justification=(
            "Base capital-lift rate per layer. The exo-engine's "
            "load-bearing speculative parameter for the stack."
        ),
    ),
    Prior(
        name="suppression_strength",
        family="uniform", low=0.05, high=0.55,
        engine="exo", target="differential.suppression_strength",
        justification=(
            "Differential-suppression intensity. 0.05 is permissive; "
            "0.55 is universal-state-grade."
        ),
    ),
    Prior(
        name="suppression_cost_exp",
        family="uniform", low=1.2, high=3.5,
        engine="exo", target="differential.suppression_cost_exp",
        justification=(
            "Convexity of suppression cost. >2 means doubling suppression "
            "more than quadruples its welfare cost."
        ),
    ),
)


def alpha_priors() -> tuple[Prior, ...]:
    """The α-engine subset of the prior inventory."""
    return tuple(p for p in INVENTORY if p.engine == "alpha")


def exo_priors() -> tuple[Prior, ...]:
    """The exo-engine subset."""
    return tuple(p for p in INVENTORY if p.engine == "exo")


def all_names() -> list[str]:
    return [p.name for p in INVENTORY]
