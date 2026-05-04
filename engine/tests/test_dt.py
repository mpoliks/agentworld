"""Explicit-dt scaling tests.

The default `WorldConfig.dt = 1.0` reproduces canonical baselines bit-for-bit
(the regression suite covers this). Beyond that, the rate-like sub-processes
(`_advance_law_state`, `capability_update`, `wealth_depreciation`) must
scale linearly (or for depreciation, exactly) with `dt`. These tests pin
that contract at the unit level.

Discrete-event sub-processes (Coasean pair sampling, fold cascade, entry/
exit, institutions) are intentionally *not* rescaled — see
`docs/concepts/time_discretization.md`.
"""

from __future__ import annotations

import numpy as np

from engine.core.dynamics import capability_update, wealth_depreciation
from engine.core.population import Population, PopulationConfig
from engine.core.topology import LawConfig, PopulationDynamicsConfig
from engine.core.world import World, WorldConfig
from engine.scenarios import get_scenario


def _build_minimal_pop() -> Population:
    pop_cfg = PopulationConfig(
        n_human_prototypes=200, n_agent_prototypes=400, seed=42,
    )
    return Population.synthesize(pop_cfg)


def test_capability_update_scales_linearly_with_dt() -> None:
    cfg = PopulationDynamicsConfig(
        enabled=True,
        capability_learning_rate=0.01,
        capability_decay_rate=0.002,
    )
    pop_a = _build_minimal_pop()
    pop_b = _build_minimal_pop()
    rng = np.random.default_rng(7)
    wealth_delta = rng.normal(0.0, 1.0, size=pop_a.n).astype(np.float32)

    cap_before = pop_a.capability.copy()
    capability_update(pop_a, wealth_delta, cfg, dt=1.0)
    delta_at_1 = pop_a.capability - cap_before

    pop_b.capability[:] = cap_before
    capability_update(pop_b, wealth_delta, cfg, dt=2.0)
    delta_at_2 = pop_b.capability - cap_before

    # Linear scaling is only exact in the un-clipped regime; restrict the
    # check to prototypes that didn't hit the [0.01, 0.99] floor/ceiling.
    safe = (
        (cap_before > 0.05) & (cap_before < 0.95)
        & (pop_a.capability > 0.011) & (pop_a.capability < 0.989)
        & (pop_b.capability > 0.011) & (pop_b.capability < 0.989)
    )
    assert safe.sum() > 50, "test setup degenerate — too many clipped"
    np.testing.assert_allclose(
        delta_at_2[safe], 2.0 * delta_at_1[safe], rtol=1e-4, atol=1e-6,
    )


def test_wealth_depreciation_uses_exact_continuous_time_relation() -> None:
    cfg = PopulationDynamicsConfig(enabled=True, wealth_depreciation=0.05)
    pop_a = _build_minimal_pop()
    pop_b = _build_minimal_pop()

    w_before = pop_a.wealth.copy()
    wealth_depreciation(pop_a, cfg, dt=2.0)
    expected = w_before * np.float32((1.0 - 0.05) ** 2.0)
    np.testing.assert_allclose(pop_a.wealth, expected, rtol=1e-5)

    # dt=0.0 is a no-op (factor = 1).
    wealth_depreciation(pop_b, cfg, dt=0.0)
    np.testing.assert_array_equal(pop_b.wealth, w_before)


def test_law_state_advance_scales_linearly_with_dt() -> None:
    cfg = get_scenario("legal_collapse")  # opts into law dynamics
    cfg.n_steps = 2
    cfg.track_ledger = False  # we only need the law state diagnostic

    cfg.dt = 1.0
    world_a = World.build(cfg)
    s0_strength = world_a.law_strength
    s0_capture = world_a.law_capture
    world_a.step()
    delta_s_at_1 = world_a.law_strength - s0_strength
    delta_c_at_1 = world_a.law_capture - s0_capture

    cfg2 = get_scenario("legal_collapse")
    cfg2.n_steps = 2
    cfg2.track_ledger = False
    cfg2.dt = 2.0
    world_b = World.build(cfg2)
    world_b.step()
    delta_s_at_2 = world_b.law_strength - s0_strength
    delta_c_at_2 = world_b.law_capture - s0_capture

    # Linear in dt up to the [0,1] clip and modulo wealth-share feedback
    # (which has a tiny same-seed variation in the first step). Tolerance
    # is loose: the assertion is that doubling dt roughly doubles the
    # per-step evolution.
    if abs(delta_s_at_1) > 1e-6:
        ratio = delta_s_at_2 / delta_s_at_1
        assert 1.7 < ratio < 2.3, f"law_strength dt scaling ratio = {ratio:.3f}"
    if abs(delta_c_at_1) > 1e-6:
        ratio = delta_c_at_2 / delta_c_at_1
        assert 1.7 < ratio < 2.3, f"law_capture dt scaling ratio = {ratio:.3f}"


def test_default_dt_is_bit_identical() -> None:
    """The default `dt = 1.0` produces identical canonical EBI."""
    cfg_a = get_scenario("baroque_cathedral")
    cfg_a.n_steps = 15
    world_a = World.build(cfg_a)
    world_a.run(progress=False)

    cfg_b = get_scenario("baroque_cathedral")
    cfg_b.n_steps = 15
    cfg_b.dt = 1.0  # explicit
    world_b = World.build(cfg_b)
    world_b.run(progress=False)

    a = world_a.metrics.history.steps[-1].exo_baroque_index
    b = world_b.metrics.history.steps[-1].exo_baroque_index
    assert a == b, f"explicit dt=1.0 perturbs EBI: {a} != {b}"


def test_folding_propensity_scales_with_dt_via_discrete_time_analog() -> None:
    """Per-step propensity at dt=k is `1 - (1 - p)^k`."""
    cfg = get_scenario("baroque_cathedral")
    world = World.build(cfg)
    p1 = world.topology.folding_propensity(dt=1.0)
    p2 = world.topology.folding_propensity(dt=2.0)
    p_half = world.topology.folding_propensity(dt=0.5)

    assert 0.0 < p1 < 1.0, f"baroque_cathedral propensity at dt=1 should be in (0,1): {p1}"

    expected_2 = 1.0 - (1.0 - p1) ** 2.0
    expected_half = 1.0 - (1.0 - p1) ** 0.5
    assert abs(p2 - expected_2) < 1e-9, f"dt=2 propensity mismatch: {p2} vs {expected_2}"
    assert abs(p_half - expected_half) < 1e-9, f"dt=0.5 propensity mismatch: {p_half} vs {expected_half}"

    # Order-preserving: p_half < p1 < p2 < 1.
    assert p_half < p1 < p2 < 1.0


def test_folding_dt_is_no_op_when_base_propensity_zero() -> None:
    """When base propensity is zero, dt scaling is a no-op."""
    cfg = get_scenario("coasean_paradise")
    cfg.topology.folding_propensity = 0.0  # force-zero
    world = World.build(cfg)
    assert world.topology.folding_propensity(dt=1.0) == 0.0
    assert world.topology.folding_propensity(dt=4.0) == 0.0
    assert world.topology.folding_propensity(dt=0.25) == 0.0
