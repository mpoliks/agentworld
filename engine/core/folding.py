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
    # Productive vs parasitic split (zero unless `base_variance_absorption > 0`).
    # `real_added_productive` is the welfare-creating contribution of the
    # fold cascade — derivatives-as-productive-tool. The total real
    # welfare contribution of folding is `real_added_productive
    # − real_subtracted`, which can be positive at moderate depth and
    # capability and negative at high depth or low capability.
    # `productive_welfare_yield` is a welfare yield: the fraction of fold
    # nominal that ended up as bounded real welfare; in [0, 1].
    real_added_productive: float = 0.0
    productive_welfare_yield: float = 0.0
    # Per-depth nominal contribution (index 0 = depth 1). Empty list when
    # folding is disabled or the propensity gates the cascade off. Used by
    # the live fold-tree visualisation (B4); does not influence engine
    # math.
    per_depth_contribution: list = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.per_depth_contribution is None:
            self.per_depth_contribution = []


def _productive_share_at_depth(
    cap_intermediating: float, depth: int, topo: Topology
) -> float:
    """Sigmoid-gated capability quality at this fold depth.

    `productive_share_d = sigmoid(cap, midpoint, slope)`.
    Capability above `cap_midpoint` folds productively; below, parasitically.
    Depth decay is applied separately in `_variance_absorbed_factor`.
    """
    cfg = topo.cfg
    if cfg.base_variance_absorption <= 0.0:
        return 0.0
    intermediation_quality = cap_intermediating
    # Keep the sigmoid argument depth-invariant so the mid-point is a
    # capability threshold; depth rides on `_variance_absorbed_factor`.
    z = (intermediation_quality - cfg.cap_midpoint) * cfg.cap_slope
    # Vanilla logistic. Avoid overflow at large |z|.
    if z >= 0:
        return 1.0 / (1.0 + np.exp(-z))
    ez = np.exp(z)
    return ez / (1.0 + ez)


def _variance_absorbed_factor(depth: int, topo: Topology) -> float:
    """Per-layer variance-absorption decay.

    Without an explicit per-pair variance accounting layer, we model the
    welfare contribution as a function of depth and a constant. Deep
    layers absorb less because they're already operating on stabilized
    risks: at depth 1, productive folding adds `base_variance_absorption`
    of its nominal as real; at depth d it adds
    `base_variance_absorption * productive_decay^(d-1)`.
    """
    cfg = topo.cfg
    return cfg.base_variance_absorption * (cfg.productive_decay ** (depth - 1))


def _cap_productive_real_added(raw_added: float, base_real_surplus: float, topo: Topology) -> float:
    """Bound productive folding by variance in the underlying real economy."""
    cap = max(0.0, base_real_surplus) * max(0.0, topo.cfg.max_productive_real_share)
    return float(min(raw_added, cap))


def fold_surplus(
    base_real_surplus: float,
    base_nominal_volume: float,
    topo: Topology,
    rng: np.random.Generator,
    current_max_depth: int = 0,
    cap_intermediating: float = 0.0,
    realized_alpha: float | None = None,
    fold_pressure: float | None = None,
    dt: float = 1.0,
) -> FoldingResult:
    """
    Apply the folding operator to this step's surplus.

    Returns the *additional* nominal volume created by folding and the *additional*
    real welfare consumed by it (a friction loss). The base values are unchanged.

    `cap_intermediating` is the weighted-mean capability of intermediating
    agents — used for the productive-vs-parasitic split. Until per-mode
    intermediation lands, callers pass the population-mean agent
    capability.

    `fold_pressure` is the running cumulative-fold-nominal / cumulative-real
    ratio supplied by the World; when `folding_pressure_feedback` is enabled,
    propensity rises with this signal so EBI becomes a trajectory, not a
    steady-state ratio.

    `dt` rescales the cascade *firing* probability via the discrete-time
    analog applied inside `Topology.folding_propensity`. Cascade contents
    (branching, Hawkes self-excitation) remain intra-cascade and so
    invariant of `dt`; see `docs/concepts/time_discretization.md`.
    """
    cfg = topo.cfg
    propensity = topo.folding_propensity(realized_alpha, fold_pressure, dt=dt)

    if propensity <= 0 or base_real_surplus <= 0 or current_max_depth >= cfg.folding_max_depth:
        return FoldingResult(0.0, 0.0, 0.0, current_max_depth, per_depth_contribution=[])

    if cfg.folding_model == "hawkes":
        return _fold_surplus_hawkes(
            base_real_surplus, base_nominal_volume, topo, rng,
            current_max_depth, cap_intermediating, realized_alpha, fold_pressure,
            dt=dt,
        )
    return _fold_surplus_geometric(
        base_real_surplus, base_nominal_volume, topo,
        current_max_depth, cap_intermediating, realized_alpha, fold_pressure,
        dt=dt,
    )


def _fold_surplus_geometric(
    base_real_surplus: float,
    base_nominal_volume: float,
    topo: Topology,
    current_max_depth: int,
    cap_intermediating: float,
    realized_alpha: float | None = None,
    fold_pressure: float | None = None,
    dt: float = 1.0,
) -> FoldingResult:
    """Original closed-form cascade. Deterministic in the noise dimension."""
    cfg = topo.cfg
    propensity = topo.folding_propensity(realized_alpha, fold_pressure, dt=dt)
    alpha = cfg.alpha if realized_alpha is None else realized_alpha

    nominal_added = 0.0
    real_lost = 0.0
    n_subs = 0.0
    cur_nominal = base_nominal_volume
    new_depth = current_max_depth
    productive_real_added = 0.0
    per_depth: list[float] = []

    for d in range(1, cfg.folding_max_depth + 1):
        depth_prop = propensity * (0.85 ** (d - 1))
        if depth_prop < 0.01:
            break

        branch = cfg.folding_branching * (0.6 + 0.4 * alpha)
        cur_nominal = cur_nominal * branch * cfg.fold_nominal_multiplier * depth_prop

        real_lost_at_depth = (
            base_real_surplus * (1.0 - (cfg.fold_real_efficiency ** d)) * depth_prop
        )
        nominal_added += cur_nominal
        real_lost = max(real_lost, real_lost_at_depth)
        n_subs += branch * depth_prop * (10.0 ** d)
        new_depth = d
        per_depth.append(float(cur_nominal))

        # Productive-vs-parasitic split: zero contribution unless
        # `base_variance_absorption > 0` (the back-compat default).
        if cfg.base_variance_absorption > 0.0:
            p_share = _productive_share_at_depth(cap_intermediating, d, topo)
            v_factor = _variance_absorbed_factor(d, topo)
            real_added_d = cur_nominal * p_share * v_factor
            productive_real_added += real_added_d

        if cur_nominal < base_nominal_volume * 1e-3:
            break

    real_lost = min(real_lost, base_real_surplus * 0.95)
    productive_real_added = _cap_productive_real_added(
        productive_real_added, base_real_surplus, topo
    )
    if nominal_added > 0:
        productive_welfare_yield = float(
            min(1.0, max(0.0, productive_real_added / nominal_added))
        )
    else:
        productive_welfare_yield = 0.0
    return FoldingResult(
        nominal_added=nominal_added,
        real_subtracted=real_lost,
        n_sub_markets_added=n_subs,
        new_max_depth=new_depth,
        real_added_productive=productive_real_added,
        productive_welfare_yield=productive_welfare_yield,
        per_depth_contribution=per_depth,
    )


def _fold_surplus_hawkes(
    base_real_surplus: float,
    base_nominal_volume: float,
    topo: Topology,
    rng: np.random.Generator,
    current_max_depth: int,
    cap_intermediating: float,
    realized_alpha: float | None = None,
    fold_pressure: float | None = None,
    dt: float = 1.0,
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
    propensity = topo.folding_propensity(realized_alpha, fold_pressure, dt=dt)
    alpha = cfg.alpha if realized_alpha is None else realized_alpha
    n_eff = float(np.clip(cfg.hawkes_branching_ratio, 0.0, 0.95))
    # Gamma shape parameter — k=hawkes_decay so larger decay = lighter tail.
    k = max(0.5, float(cfg.hawkes_decay))

    nominal_added = 0.0
    real_lost = 0.0
    n_subs = 0.0
    cur_nominal_mean = base_nominal_volume
    new_depth = current_max_depth
    prev_factor = 1.0  # depth-1 has no parent to inherit excitation from
    productive_real_added = 0.0
    per_depth: list[float] = []

    for d in range(1, cfg.folding_max_depth + 1):
        depth_prop = propensity * (0.85 ** (d - 1))
        if depth_prop < 0.01:
            break

        branch = cfg.folding_branching * (0.6 + 0.4 * alpha)
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
        per_depth.append(float(contribution))

        # Productive split — uses the realized contribution at this depth,
        # not the mean. Self-exciting overshoots therefore generate
        # over-mean productive welfare *and* over-mean parasitic
        # accounting at the same time (the Hawkes property carries through
        # to both halves of the split).
        if cfg.base_variance_absorption > 0.0:
            p_share = _productive_share_at_depth(cap_intermediating, d, topo)
            v_factor = _variance_absorbed_factor(d, topo)
            real_added_d = contribution * p_share * v_factor
            productive_real_added += real_added_d

        # Propagate the deviation-from-mean factor forward so that
        # over/undershoots cluster across generations (the Hawkes property).
        prev_factor = cur_factor / max(excitation, 1e-9)

        if cur_nominal_mean < base_nominal_volume * 1e-3:
            break

    real_lost = min(real_lost, base_real_surplus * 0.95)
    productive_real_added = _cap_productive_real_added(
        productive_real_added, base_real_surplus, topo
    )
    if nominal_added > 0:
        productive_welfare_yield = float(
            min(1.0, max(0.0, productive_real_added / nominal_added))
        )
    else:
        productive_welfare_yield = 0.0
    return FoldingResult(
        nominal_added=nominal_added,
        real_subtracted=real_lost,
        n_sub_markets_added=n_subs,
        new_max_depth=new_depth,
        real_added_productive=productive_real_added,
        productive_welfare_yield=productive_welfare_yield,
        per_depth_contribution=per_depth,
    )
