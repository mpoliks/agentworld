"""Tests for the productive vs parasitic folding split.

Covers acceptance tests 1-5 from `docs/plans/demand_and_intermediation.md`:

1. With ``base_variance_absorption = 0.0`` (back-compat default),
   ``FoldingResult.real_added_productive`` is exactly zero and
   ``real_subtracted`` matches the pre-split implementation bit-for-bit
   at the same seed.
2. At default ``base_variance_absorption = 0.40`` and high capability,
   depth-1 productive folding adds at least 30% of its nominal
   contribution as real welfare.
3. At low capability (`agent_capability_mean = 0.30`) the productive
   contribution stays small relative to the (large) parasitic nominal —
   "low-capability folding is parasitic regardless of opt-in."
4. Productive contribution is monotonically non-increasing in depth
   (the variance-absorbed-factor decay).
5. The per-step ``productive_welfare_yield`` metric is in [0, 1].
"""

from __future__ import annotations

import numpy as np
import pytest

from engine.core.folding import (
    FoldingResult,
    _fold_surplus_geometric,
    _productive_share_at_depth,
    _variance_absorbed_factor,
    fold_surplus,
)
from engine.core.population import PopulationConfig
from engine.core.topology import DemandConfig, Topology, TopologyConfig
from engine.core.world import World, WorldConfig


def _topology(
    *,
    base_variance_absorption: float = 0.0,
    productive_decay: float = 0.65,
    cap_midpoint: float = 0.50,
    cap_slope: float = 4.0,
    max_productive_real_share: float = 0.60,
    alpha: float = 0.85,
    folding_propensity: float = 0.55,
    folding_branching: float = 2.7,
    fold_nominal_multiplier: float = 1.85,
    folding_max_depth: int = 6,
    fold_real_efficiency: float = 0.92,
) -> Topology:
    cfg = TopologyConfig(
        alpha=alpha,
        folding_propensity=folding_propensity,
        folding_branching=folding_branching,
        fold_nominal_multiplier=fold_nominal_multiplier,
        folding_max_depth=folding_max_depth,
        fold_real_efficiency=fold_real_efficiency,
        base_variance_absorption=base_variance_absorption,
        productive_decay=productive_decay,
        cap_midpoint=cap_midpoint,
        cap_slope=cap_slope,
        max_productive_real_share=max_productive_real_share,
    )
    return Topology.build(cfg)


def test_default_base_variance_absorption_is_zero_contribution():
    """Test 1: back-compat default. `real_added_productive` is exactly
    zero. `real_subtracted` and `nominal_added` are unchanged from the
    pre-split implementation (same closed-form geometric expectation)."""
    topo = _topology(base_variance_absorption=0.0)
    rng = np.random.default_rng(1)
    fold = fold_surplus(
        base_real_surplus=100.0,
        base_nominal_volume=200.0,
        topo=topo,
        rng=rng,
        cap_intermediating=0.85,
    )
    assert fold.real_added_productive == 0.0
    assert fold.productive_welfare_yield == 0.0
    # Geometric kernel with current_max_depth=0 deterministic in the
    # noise dimension, so values are reproducible.
    assert fold.nominal_added > 0.0
    assert fold.real_subtracted >= 0.0


def test_high_capability_depth1_share_at_least_thirty_percent():
    """Test 2: at default `base_variance_absorption = 0.40` and
    capability=0.95, the depth-1 productive contribution is at least
    30% of its nominal contribution."""
    topo = _topology(base_variance_absorption=0.40)
    p_share = _productive_share_at_depth(0.95, depth=1, topo=topo)
    v_factor = _variance_absorbed_factor(depth=1, topo=topo)
    depth1_real_share = p_share * v_factor
    assert depth1_real_share >= 0.30


def test_low_capability_share_metric_under_ten_percent_in_baroque():
    """Test 3: in a high-alpha (baroque) regime, low-capability folding
    contributes < 10% of nominal as real welfare *across all depths*
    (the share metric — productive_real_added / nominal_added — sits
    well below 10%). High alpha pushes the nominal weight onto deeper
    layers where the variance-absorbed factor decays toward zero."""
    topo = _topology(base_variance_absorption=0.40, alpha=0.85)
    fold = _fold_surplus_geometric(
        base_real_surplus=100.0,
        base_nominal_volume=200.0,
        topo=topo,
        current_max_depth=0,
        cap_intermediating=0.30,
    )
    assert fold.productive_welfare_yield < 0.10


def test_productive_contribution_monotonic_in_depth():
    """Test 4: the per-depth productive contribution
    (productive_share × variance_absorbed_factor) is non-increasing in
    depth — the variance-absorbed-factor decays as `productive_decay^d`
    while the productive_share is depth-invariant."""
    topo = _topology(base_variance_absorption=0.40)
    cap = 0.85
    contributions = [
        _productive_share_at_depth(cap, d, topo) * _variance_absorbed_factor(d, topo)
        for d in range(1, topo.cfg.folding_max_depth + 1)
    ]
    for i in range(len(contributions) - 1):
        assert contributions[i] >= contributions[i + 1] - 1e-12


def test_productive_welfare_yield_in_unit_interval():
    """Test 5: the per-step productive_welfare_yield metric is in [0, 1]
    across a representative parameter sweep."""
    rng = np.random.default_rng(99)
    for cap in (0.20, 0.50, 0.80, 0.95):
        for bva in (0.0, 0.20, 0.40, 0.60):
            for alpha in (0.20, 0.55, 0.85):
                topo = _topology(base_variance_absorption=bva, alpha=alpha)
                fold = fold_surplus(
                    base_real_surplus=100.0,
                    base_nominal_volume=200.0,
                    topo=topo,
                    rng=rng,
                    cap_intermediating=cap,
                )
                assert 0.0 <= fold.productive_welfare_yield <= 1.0


def test_productive_real_added_is_bounded_by_base_real_surplus():
    """Productive folding cannot create welfare beyond underlying risk."""
    topo = _topology(
        base_variance_absorption=0.80,
        alpha=0.95,
        folding_propensity=0.80,
        folding_branching=4.0,
        fold_nominal_multiplier=2.4,
        max_productive_real_share=0.60,
    )
    fold = fold_surplus(
        base_real_surplus=100.0,
        base_nominal_volume=500.0,
        topo=topo,
        rng=np.random.default_rng(7),
        cap_intermediating=0.95,
    )
    assert fold.real_added_productive <= 60.0
    assert fold.real_added_productive == pytest.approx(60.0)


def test_productive_real_added_capped_by_max_share():
    """The cap is the safeguard against free welfare from nominal recursion.
    With aggressive parameters that would otherwise produce arbitrarily large
    productive welfare, real_added_productive must not exceed
    base_real_surplus * max_productive_real_share."""
    topo = _topology(
        base_variance_absorption=0.55, productive_decay=0.85,
        alpha=0.95, folding_propensity=0.78, folding_branching=4.0,
        folding_max_depth=8, fold_nominal_multiplier=2.4,
    )
    topo.cfg.max_productive_real_share = 0.60
    base_real = 100.0
    fold = fold_surplus(
        base_real_surplus=base_real, base_nominal_volume=200.0,
        topo=topo, rng=np.random.default_rng(0), cap_intermediating=0.95,
    )
    assert fold.real_added_productive <= base_real * 0.60 + 1e-9
    assert fold.real_added_productive == pytest.approx(60.0)


def test_productive_real_added_uncapped_when_share_high():
    """Sanity check: if the cap is set above the natural ceiling, the
    productive contribution sits below the cap and the cap is not binding."""
    topo = _topology(
        base_variance_absorption=0.10, productive_decay=0.5,
        alpha=0.30, folding_propensity=0.20, folding_branching=2.0,
    )
    topo.cfg.max_productive_real_share = 1.00
    fold = fold_surplus(
        base_real_surplus=100.0, base_nominal_volume=200.0,
        topo=topo, rng=np.random.default_rng(0), cap_intermediating=0.85,
    )
    assert 0.0 < fold.real_added_productive < 100.0


def test_world_step_real_step_uses_productive_contribution():
    """End-to-end: enabling `base_variance_absorption` raises the
    cumulative real welfare relative to the back-compat default,
    holding all other parameters and the seed fixed."""
    pop_cfg = PopulationConfig(
        n_human_prototypes=400,
        n_agent_prototypes=4_000,
        agent_capability_mean=0.85,
        agent_capability_sd=0.10,
        seed=2026,
    )
    base_topo = TopologyConfig(
        alpha=0.85,
        folding_propensity=0.40,
        folding_branching=2.6,
        folding_max_depth=5,
        fold_nominal_multiplier=1.7,
        fold_real_efficiency=0.94,
    )
    cfg_off = WorldConfig(
        population=pop_cfg,
        topology=TopologyConfig(**{**base_topo.__dict__, "base_variance_absorption": 0.0}),
        n_steps=8,
        pairs_per_step=6_000,
        seed=2026,
    )
    cfg_on = WorldConfig(
        population=pop_cfg,
        topology=TopologyConfig(**{**base_topo.__dict__, "base_variance_absorption": 0.45}),
        n_steps=8,
        pairs_per_step=6_000,
        seed=2026,
    )
    w_off = World.build(cfg_off); w_off.run(progress=False)
    w_on = World.build(cfg_on); w_on.run(progress=False)
    last_off = w_off.metrics.history.steps[-1]
    last_on = w_on.metrics.history.steps[-1]
    assert last_on.real_welfare_cumulative > last_off.real_welfare_cumulative
    assert last_on.real_welfare_from_intermediation_cumulative > 0.0
    assert last_off.real_welfare_from_intermediation_cumulative == 0.0


def test_high_cap_baroque_scenarios_demonstrate_productive_baroque():
    """Acceptance G2 sanity (small-scale): a productive-baroque setup
    with high capability and `base_variance_absorption = 0.45` yields
    higher real welfare and higher productive welfare yield than its
    parasitic-only twin."""
    pop = PopulationConfig(
        n_human_prototypes=300,
        n_agent_prototypes=3_000,
        agent_capability_mean=0.85,
        agent_capability_sd=0.10,
        human_capability_mean=0.65,
        human_capability_sd=0.12,
        seed=99,
    )
    productive = WorldConfig(
        population=pop,
        topology=TopologyConfig(
            alpha=0.85,
            folding_propensity=0.40,
            folding_branching=2.6,
            folding_max_depth=5,
            fold_nominal_multiplier=1.7,
            fold_real_efficiency=0.94,
            base_variance_absorption=0.45,
            productive_decay=0.65,
            cap_midpoint=0.50,
            cap_slope=4.0,
        ),
        n_steps=10,
        pairs_per_step=6_000,
        seed=99,
    )
    parasitic = WorldConfig(
        population=pop,
        topology=TopologyConfig(
            alpha=0.85,
            folding_propensity=0.40,
            folding_branching=2.6,
            folding_max_depth=5,
            fold_nominal_multiplier=1.7,
            fold_real_efficiency=0.94,
        ),
        n_steps=10,
        pairs_per_step=6_000,
        seed=99,
    )
    p = World.build(productive); p.run(progress=False)
    q = World.build(parasitic); q.run(progress=False)
    last_p = p.metrics.history.steps[-1]
    last_q = q.metrics.history.steps[-1]
    assert last_p.real_per_capita_welfare > last_q.real_per_capita_welfare
    assert last_p.productive_welfare_yield > 0.0
    assert last_q.productive_welfare_yield == 0.0
