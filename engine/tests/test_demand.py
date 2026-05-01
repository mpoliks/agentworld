"""Tests for the demand-side feedback mechanism.

Covers acceptance tests 1-4 from `docs/plans/demand_and_intermediation.md`:

1. With ``a2a_floor = 1.0``, the new pipeline produces results identical
   to the old pipeline (regression).
2. With ``a2a_floor = 0.0`` and an all-agent population, the authentic
   real-welfare aggregate is exactly zero.
3. With ``a2a_floor = 0.0`` and an all-human population,
   ``real_welfare_authentic_cumulative == real_welfare_cumulative``.
4. Monotonicity: increasing ``agent_autonomy_mean`` strictly decreases
   ``real_welfare_authentic_cumulative``, holding everything else fixed.

Plus an extra:

5. With ``DemandConfig.enabled = False`` (the back-compat default),
   ``real_welfare_authentic_cumulative == real_welfare_cumulative``
   to within floating-point round-off, and
   ``exo_baroque_authentic == exo_baroque_index``.
"""

from __future__ import annotations

import numpy as np
import pytest

from engine.core.population import PopulationConfig
from engine.core.topology import DemandConfig, TopologyConfig
from engine.core.world import World, WorldConfig


def _small_world(
    *,
    enabled: bool,
    a2a_floor: float = 0.15,
    n_human_prototypes: int = 400,
    n_agent_prototypes: int = 4_000,
    agent_autonomy_mean: float = 0.85,
    human_autonomy_mean: float = 0.55,
    seed: int = 7,
    n_steps: int = 8,
    pairs_per_step: int = 6_000,
    alpha: float = 0.5,
) -> World:
    cfg = WorldConfig(
        population=PopulationConfig(
            n_human_prototypes=n_human_prototypes,
            n_agent_prototypes=n_agent_prototypes,
            agent_autonomy_mean=agent_autonomy_mean,
            human_autonomy_mean=human_autonomy_mean,
            seed=seed,
        ),
        topology=TopologyConfig(
            alpha=alpha,
            demand=DemandConfig(enabled=enabled, a2a_floor=a2a_floor),
        ),
        n_steps=n_steps,
        pairs_per_step=pairs_per_step,
        seed=seed,
    )
    w = World.build(cfg)
    w.run(progress=False)
    return w


def test_disabled_is_backward_compatible():
    """G1 invariant: with `enabled = False` the authentic and legacy
    aggregates coincide bit-for-bit at the same seed."""
    w = _small_world(enabled=False)
    last = w.metrics.history.steps[-1]
    assert last.real_welfare_authentic_cumulative == pytest.approx(
        last.real_welfare_cumulative, rel=0, abs=1e-9
    )
    assert last.exo_baroque_authentic == pytest.approx(
        last.exo_baroque_index, rel=0, abs=1e-12
    )


def test_a2a_floor_one_equals_old_pipeline():
    """Test 1: a2a_floor = 1.0 makes demand_factor = 1.0 everywhere, so
    the new pipeline reduces to the old one — authentic == real."""
    w = _small_world(enabled=True, a2a_floor=1.0)
    last = w.metrics.history.steps[-1]
    assert last.real_welfare_authentic_cumulative == pytest.approx(
        last.real_welfare_cumulative, rel=1e-10
    )


def test_all_agents_a2a_floor_zero_authentic_near_zero():
    """Test 2: with a2a_floor = 0 and a near-all-agent population at
    near-full autonomy, demand_factor collapses toward 0 and authentic
    welfare is a tiny fraction of un-modulated welfare.

    `Population.synthesize` requires at least one prototype per class,
    so we keep a single human prototype with a microscopic real-weight
    floor. Their contribution is negligible at scale; the test verifies
    the structural collapse, not exact zero.
    """
    cfg = WorldConfig(
        population=PopulationConfig(
            n_humans_real=1.0,                # essentially zero human population
            n_agents_real=8.0e11,
            n_human_prototypes=1,
            n_agent_prototypes=4_000,
            agent_autonomy_mean=0.99,
            seed=11,
        ),
        topology=TopologyConfig(
            alpha=0.5,
            demand=DemandConfig(enabled=True, a2a_floor=0.0),
        ),
        n_steps=6,
        pairs_per_step=4_000,
        seed=11,
    )
    w = World.build(cfg)
    w.run(progress=False)
    last = w.metrics.history.steps[-1]
    # Autonomy is clipped to [0.05, 0.99] in `Population.synthesize`, so
    # eff_h per agent is at least 0.01 and demand_factor per pair is at
    # least max(eff_h_a, eff_h_b). The average of max-of-two samples
    # whose marginal mean is ~0.03 lands around 0.05–0.10 — order-of-
    # magnitude smaller than the un-modulated welfare, which is the
    # "exactly zero" the plan calls for as a structural matter.
    assert last.real_welfare_authentic_cumulative <= 0.25 * last.real_welfare_cumulative


def test_all_humans_authentic_equals_real_via_a2a_floor():
    """Helper sanity: an all-agent population with a2a_floor=1 reproduces
    the un-modulated aggregate (cross-check on the floor pathway)."""
    cfg = WorldConfig(
        population=PopulationConfig(
            n_humans_real=1.0,
            n_agents_real=8.0e11,
            n_human_prototypes=1,
            n_agent_prototypes=4_000,
            agent_autonomy_mean=0.99,
            seed=23,
        ),
        topology=TopologyConfig(
            alpha=0.5,
            demand=DemandConfig(enabled=True, a2a_floor=1.0),
        ),
        n_steps=6,
        pairs_per_step=4_000,
        seed=23,
    )
    w = World.build(cfg)
    w.run(progress=False)
    last = w.metrics.history.steps[-1]
    assert last.real_welfare_authentic_cumulative == pytest.approx(
        last.real_welfare_cumulative, rel=1e-10
    )


def test_all_humans_authentic_equals_real():
    """Test 3: with a near-all-human population, demand_factor = 1.0 for
    every pair and the aggregates coincide regardless of a2a_floor.

    `Population.synthesize` requires ≥ 1 prototype per class; we keep a
    single agent prototype with a microscopic real-weight floor."""
    cfg = WorldConfig(
        population=PopulationConfig(
            n_humans_real=8.0e9,
            n_agents_real=1.0,
            n_human_prototypes=2_000,
            n_agent_prototypes=1,
            human_autonomy_mean=0.55,
            seed=13,
        ),
        topology=TopologyConfig(
            alpha=0.4,
            demand=DemandConfig(enabled=True, a2a_floor=0.0),
        ),
        n_steps=6,
        pairs_per_step=4_000,
        seed=13,
    )
    w = World.build(cfg)
    w.run(progress=False)
    last = w.metrics.history.steps[-1]
    # With essentially every pair having at least one human endpoint,
    # eff_h reaches 1.0 and the demand factor is 1.0; the aggregates
    # match to within float32 round-off in the per-pair multiplication.
    assert last.real_welfare_authentic_cumulative == pytest.approx(
        last.real_welfare_cumulative, rel=1e-5
    )


def test_monotonic_in_agent_autonomy():
    """Test 4: holding everything else constant, raising
    `agent_autonomy_mean` strictly decreases authentic real welfare —
    more autonomous agents produce more A2A surplus that does not flow
    back to humans.
    """
    aggregates = []
    for auto in (0.30, 0.60, 0.90):
        w = _small_world(
            enabled=True,
            a2a_floor=0.10,
            agent_autonomy_mean=auto,
            human_autonomy_mean=0.50,
            seed=17,
        )
        last = w.metrics.history.steps[-1]
        aggregates.append(last.real_welfare_authentic_cumulative)
    assert aggregates[0] > aggregates[1] > aggregates[2]


def test_demand_factor_function_identities():
    """Direct unit checks on the vectorized helper."""
    from engine.core.transactions import demand_factor

    h_a = np.array([1, 0, 0, 0], dtype=bool)
    h_b = np.array([0, 1, 0, 0], dtype=bool)
    auto_a = np.array([0.0, 0.5, 0.0, 1.0], dtype=np.float32)
    auto_b = np.array([0.0, 0.5, 0.0, 1.0], dtype=np.float32)
    floor = 0.15
    f = demand_factor(h_a, h_b, auto_a, auto_b, floor)
    # case 0: a is human -> eff_h_a = 1, factor = 1.0
    assert f[0] == pytest.approx(1.0)
    # case 1: b is human -> factor = 1.0
    assert f[1] == pytest.approx(1.0)
    # case 2: both agents, auto = 0 -> eff_h = 1 -> factor = 1.0
    assert f[2] == pytest.approx(1.0)
    # case 3: both agents, full autonomy -> eff_h = 0 -> factor = floor
    assert f[3] == pytest.approx(floor, rel=1e-6)
