"""
Folding — the fractal multiplication of folded surfaces.

Bratton's hypothesis: instead of disintermediating, agents may *fractalize*
intermediation. Every market with positive surplus can spawn sub-markets that
themselves trade in derived rights, derived risks, derived attention, derived
representations, derived metadata. Each fold:
    - adds nominally to GDP (the new sub-market is a "real" economic event)
    - subtracts marginally from real welfare (frictional losses per layer)
    - opens new surfaces for further folding

At low alpha (smooth), folding is suppressed.
At high alpha (Baroque), folding is aggressive and recursive.

The key conceptual move: nominal GDP under aggressive folding is *unbounded*,
because the folding operator can always add another layer. Real surplus is
bounded by the underlying productive economy. The *exo-baroque index* is
nominal/real.

Two folding kernels are available:

    - "geometric"  : the original closed-form deterministic cascade.
    - "hawkes"     : a stochastic self-exciting cascade that preserves the
                     closed-form mean but adds realistic per-depth variance
                     and tail-risk. Calibrated to high-frequency cascade
                     branching ratios (Bacry & Muzy 2015). See
                     `docs/concepts/epistemic_status.md`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from engine.core.topology import Topology


@dataclass
class FoldingResult:
    nominal_added: float       # nominal GDP added by folding
    real_subtracted: float     # real welfare lost to folding overhead
    n_sub_markets_added: float # in real units (over the whole economy)
    new_max_depth: int         # deepest fold level reached this step


def fold_surplus(
    base_real_surplus: float,
    base_nominal_volume: float,
    topo: Topology,
    rng: np.random.Generator,
    current_max_depth: int = 0,
) -> FoldingResult:
    """
    Apply the folding operator to this step's surplus.

    Returns the *additional* nominal volume created by folding and the *additional*
    real welfare consumed by it (a friction loss). The base values are unchanged.
    """
    cfg = topo.cfg
    propensity = topo.folding_propensity()

    if propensity <= 0 or base_real_surplus <= 0 or current_max_depth >= cfg.folding_max_depth:
        return FoldingResult(0.0, 0.0, 0.0, current_max_depth)

    if cfg.folding_model == "hawkes":
        return _fold_surplus_hawkes(
            base_real_surplus, base_nominal_volume, topo, rng, current_max_depth
        )
    return _fold_surplus_geometric(
        base_real_surplus, base_nominal_volume, topo, current_max_depth
    )


def _fold_surplus_geometric(
    base_real_surplus: float,
    base_nominal_volume: float,
    topo: Topology,
    current_max_depth: int,
) -> FoldingResult:
    """Original closed-form cascade. Deterministic in the noise dimension."""
    cfg = topo.cfg
    propensity = topo.folding_propensity()

    nominal_added = 0.0
    real_lost = 0.0
    n_subs = 0.0
    cur_nominal = base_nominal_volume
    new_depth = current_max_depth

    for d in range(1, cfg.folding_max_depth + 1):
        depth_prop = propensity * (0.85 ** (d - 1))
        if depth_prop < 0.01:
            break

        branch = cfg.folding_branching * (0.6 + 0.4 * cfg.alpha)
        cur_nominal = cur_nominal * branch * cfg.fold_nominal_multiplier * depth_prop

        real_lost_at_depth = (
            base_real_surplus * (1.0 - (cfg.fold_real_efficiency ** d)) * depth_prop
        )
        nominal_added += cur_nominal
        real_lost = max(real_lost, real_lost_at_depth)
        n_subs += branch * depth_prop * (10.0 ** d)
        new_depth = d

        if cur_nominal < base_nominal_volume * 1e-3:
            break

    real_lost = min(real_lost, base_real_surplus * 0.95)
    return FoldingResult(
        nominal_added=nominal_added,
        real_subtracted=real_lost,
        n_sub_markets_added=n_subs,
        new_max_depth=new_depth,
    )


def _fold_surplus_hawkes(
    base_real_surplus: float,
    base_nominal_volume: float,
    topo: Topology,
    rng: np.random.Generator,
    current_max_depth: int,
) -> FoldingResult:
    """Self-exciting cascade with mean-equivalence to the geometric kernel.

    At each generation d we compute the deterministic geometric mean
    `cur_nominal_mean_d` exactly as in `_fold_surplus_geometric`. The
    realised contribution is:

        contribution_d = cur_nominal_mean_d * excitation_d * gamma_d

    where:
        excitation_d = (1 - n_eff) + n_eff * (prev_factor)
        gamma_d ~ Gamma(k, 1/k)         (mean 1, variance 1/k)
        prev_factor = realised_d-1 / mean_d-1   (with E[prev_factor] = 1)

    Because E[excitation_d] = 1 and E[gamma_d] = 1, the *unconditional*
    expectation of `nominal_added` matches the geometric kernel exactly.
    The cascade self-excites: a generation that overshoots its mean
    raises the conditional intensity for the next generation, capturing
    the empirically-observed Hawkes property of cascade clustering.

    `n_eff` is the Hawkes branching ratio, calibrated to Bacry & Muzy
    (2015)'s endogeneity ratio for high-frequency markets. `k` controls
    the tail of the per-generation mark; we tie it to `hawkes_decay`
    (lower decay => heavier tail).
    """
    cfg = topo.cfg
    propensity = topo.folding_propensity()
    n_eff = float(np.clip(cfg.hawkes_branching_ratio, 0.0, 0.95))
    # Gamma shape parameter — k=hawkes_decay so larger decay = lighter tail.
    k = max(0.5, float(cfg.hawkes_decay))

    nominal_added = 0.0
    real_lost = 0.0
    n_subs = 0.0
    cur_nominal_mean = base_nominal_volume
    new_depth = current_max_depth
    prev_factor = 1.0  # depth-1 has no parent to inherit excitation from

    for d in range(1, cfg.folding_max_depth + 1):
        depth_prop = propensity * (0.85 ** (d - 1))
        if depth_prop < 0.01:
            break

        branch = cfg.folding_branching * (0.6 + 0.4 * cfg.alpha)
        cur_nominal_mean = cur_nominal_mean * branch * cfg.fold_nominal_multiplier * depth_prop

        excitation = (1.0 - n_eff) + n_eff * prev_factor
        gamma = float(rng.gamma(shape=k, scale=1.0 / k))
        cur_factor = excitation * gamma
        contribution = cur_nominal_mean * cur_factor

        real_lost_at_depth = (
            base_real_surplus * (1.0 - (cfg.fold_real_efficiency ** d)) * depth_prop
        )
        nominal_added += contribution
        real_lost = max(real_lost, real_lost_at_depth)
        n_subs += branch * depth_prop * (10.0 ** d)
        new_depth = d

        # Propagate the deviation-from-mean factor forward so that
        # over/undershoots cluster across generations (the Hawkes property).
        prev_factor = cur_factor / max(excitation, 1e-9)

        if cur_nominal_mean < base_nominal_volume * 1e-3:
            break

    real_lost = min(real_lost, base_real_surplus * 0.95)
    return FoldingResult(
        nominal_added=nominal_added,
        real_subtracted=real_lost,
        n_sub_markets_added=n_subs,
        new_max_depth=new_depth,
    )
