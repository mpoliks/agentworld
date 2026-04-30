"""
Differential creation — endogenous market spawning from ontological variance.

The exo claim: any sufficiently capable substrate will keep finding new
abstractions to price. New markets emerge wherever ontological difference
exists, unless something actively suppresses it. Suppression is not free;
its cost rises convexly toward the universal-suppression limit (the
"Combine state").

State per region:
    ontological_variance : a stylised measure of internal differentiation
    market_saturation    : 0..1, fraction of available differentials priced
    suppression_state    : realised suppression strength
    spawn_history        : cumulative markets spawned

Per step, a region produces:
    new markets    ~ Poisson(λ_r) with λ_r ∝ variance * (1 - saturation)
                                              * (1 - σ_r)
    welfare drawn for suppression: cost ∝ (σ_r ** suppression_cost_exp)

Variance itself is endogenous: it falls as suppression rises and rises as
new markets create new ontological niches. We model this with a simple
update equation per step.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from engine.exo.config import DifferentialConfig


@dataclass
class DifferentialState:
    """Per-region state for the differential operator."""

    ontological_variance: np.ndarray  # (n_regions,)
    market_saturation: np.ndarray  # (n_regions,) in [0, 1]
    suppression_realised: np.ndarray  # (n_regions,)
    spawn_total: np.ndarray  # (n_regions,) cumulative markets spawned
    suppression_welfare_drawn: np.ndarray  # (n_regions,)

    @classmethod
    def empty(
        cls, n_regions: int, initial_variance: np.ndarray | float = 1.0
    ) -> "DifferentialState":
        var = (
            np.full(n_regions, float(initial_variance), dtype=np.float64)
            if np.isscalar(initial_variance)
            else np.asarray(initial_variance, dtype=np.float64).copy()
        )
        return cls(
            ontological_variance=var,
            market_saturation=np.zeros(n_regions, dtype=np.float64),
            suppression_realised=np.zeros(n_regions, dtype=np.float64),
            spawn_total=np.zeros(n_regions, dtype=np.float64),
            suppression_welfare_drawn=np.zeros(n_regions, dtype=np.float64),
        )


def differential_step(
    cfg: DifferentialConfig,
    state: DifferentialState,
    target_suppression: np.ndarray,
    real_per_region: np.ndarray,
    rng: np.random.Generator,
) -> dict:
    """Run one differential step.

    Returns:
        dict with
            new_markets_per_region    : float
            suppression_cost_per_region : real welfare drawn for suppression
            variance_after            : updated ontological variance
    """
    n_regions = state.ontological_variance.shape[0]

    # Smooth toward target suppression with mild noise.
    new_supp = 0.85 * state.suppression_realised + 0.15 * target_suppression
    new_supp += 0.01 * rng.standard_normal(n_regions)
    new_supp = np.clip(new_supp, 0.0, 1.0)
    state.suppression_realised = new_supp

    # Expected new markets per region.
    rate = (
        cfg.base_market_creation_rate
        + cfg.variance_to_market_rate * state.ontological_variance
    ) * (1.0 - state.market_saturation) * np.clip(1.0 - new_supp, 0.05, 1.0)
    rate = np.clip(rate, 0.0, None)
    new_markets = rng.poisson(np.clip(rate * 6.0, 0.0, 200.0))
    state.spawn_total += new_markets

    # Saturation moves toward the asymptote set by `market_saturation_layers`.
    state.market_saturation = np.clip(
        state.market_saturation + new_markets / cfg.market_saturation_layers,
        0.0,
        0.98,
    )

    # Suppression cost in real welfare. Convex in suppression strength.
    supp_cost = (
        cfg.suppression_welfare_cost
        * (new_supp ** cfg.suppression_cost_exp)
        * np.sqrt(np.maximum(real_per_region, 0.0) + 1.0)
    )
    supp_cost = np.minimum(supp_cost, np.maximum(real_per_region, 0.0))
    state.suppression_welfare_drawn += supp_cost

    # Variance update: rises with new markets (each market opens new niches),
    # falls with realised suppression. Soft-saturates at 2.0.
    variance_delta = 0.04 * new_markets - 0.05 * new_supp * state.ontological_variance
    state.ontological_variance = np.clip(
        state.ontological_variance + variance_delta + 0.005 * rng.standard_normal(n_regions),
        0.05,
        2.0,
    )

    return {
        "new_markets_per_region": new_markets.astype(np.float64),
        "suppression_cost_per_region": supp_cost,
        "variance_after": state.ontological_variance.copy(),
        "suppression_realised": state.suppression_realised.copy(),
    }
