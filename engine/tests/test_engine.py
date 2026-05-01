"""Smoke tests for the engine. Run with: pytest engine/tests/"""

from __future__ import annotations

import pytest
import numpy as np

from engine.core.world import World
from engine.scenarios import SCENARIOS, get_scenario


def test_population_synthesis():
    from engine.core.population import Population, PopulationConfig
    cfg = PopulationConfig(n_human_prototypes=200, n_agent_prototypes=2000, seed=0)
    pop = Population.synthesize(cfg)
    assert pop.n == 2200
    assert pop.is_human.sum() == 200
    assert (~pop.is_human).sum() == 2000
    s = pop.summary()
    assert s["human_to_agent_ratio"] == pytest.approx(100.0, rel=1e-3)


def test_world_runs_two_steps():
    cfg = get_scenario("equilibrium_drift")
    cfg.n_steps = 2
    cfg.pairs_per_step = 5000
    cfg.population.n_human_prototypes = 200
    cfg.population.n_agent_prototypes = 2000
    world = World.build(cfg)
    world.run(progress=False)
    assert world.step_idx == 2
    assert len(world.metrics.history.steps) == 2


@pytest.mark.parametrize("name", list(SCENARIOS.keys()))
def test_scenario_runs(name):
    cfg = get_scenario(name)
    cfg.n_steps = 3
    cfg.pairs_per_step = 5000
    cfg.population.n_human_prototypes = 200
    cfg.population.n_agent_prototypes = 2000
    world = World.build(cfg)
    metrics = world.run(progress=False)
    h = metrics.history.to_dict()
    assert len(h["step"]) == 3
    # EBI is always >= 1 (or very close, because nominal volume ≥ real surplus by design).
    assert all(e >= 0.99 for e in h["exo_baroque_index"])
    # Real welfare cumulative is monotonically non-decreasing.
    rwc = h["real_welfare_cumulative"]
    assert all(rwc[i + 1] >= rwc[i] for i in range(len(rwc) - 1))


def test_smooth_vs_baroque_ebi_separation():
    # The Coasean Paradise should have EBI close to 1, the Baroque Cathedral much higher.
    csc = get_scenario("coasean_paradise"); csc.n_steps = 12; csc.pairs_per_step = 30_000
    bsc = get_scenario("baroque_cathedral"); bsc.n_steps = 12; bsc.pairs_per_step = 30_000
    csc.population.n_human_prototypes = 1000; csc.population.n_agent_prototypes = 6000
    bsc.population.n_human_prototypes = 1000; bsc.population.n_agent_prototypes = 6000
    smooth = World.build(csc); smooth.run()
    baroque = World.build(bsc); baroque.run()
    s_ebi = smooth.metrics.history.steps[-1].exo_baroque_index
    b_ebi = baroque.metrics.history.steps[-1].exo_baroque_index
    assert s_ebi < 5.0
    assert b_ebi > 50.0
    assert b_ebi > s_ebi * 10


def test_phase_space_sweep_smoke():
    from engine.sensitivity import basin_counts, run_phase_space_sweep

    summary = run_phase_space_sweep(
        alpha_values=[0.05, 0.95],
        capability_values=[0.45, 0.85],
        n_steps=3,
        pairs_per_step=4_000,
        n_human_prototypes=200,
        n_agent_prototypes=2_000,
    )
    assert len(summary.points) == 4
    assert sum(basin_counts(summary.points).values()) == 4
    assert max(point.ebi for point in summary.points) > min(point.ebi for point in summary.points)


def test_strategy_disabled_is_bitidentical():
    cfg_a = get_scenario("equilibrium_drift")
    cfg_b = get_scenario("equilibrium_drift")
    for cfg in (cfg_a, cfg_b):
        cfg.n_steps = 3
        cfg.pairs_per_step = 5000
        cfg.population.n_human_prototypes = 200
        cfg.population.n_agent_prototypes = 2000
        cfg.seed = 123
        cfg.population.seed = 456
    cfg_b.topology.strategy.enabled = False

    world_a = World.build(cfg_a)
    world_b = World.build(cfg_b)
    world_a.run(progress=False)
    world_b.run(progress=False)

    a = world_a.metrics.history.steps[-1]
    b = world_b.metrics.history.steps[-1]
    assert a.exo_baroque_index == b.exo_baroque_index
    assert a.real_welfare_cumulative == b.real_welfare_cumulative
    assert a.gini_wealth == b.gini_wealth


def test_bandit_converges_to_profitable_action():
    from engine.core.strategy import apply_actions, select_actions, update_rewards

    rng = np.random.default_rng(0)
    n = 2000
    rewards = np.zeros((n, 3), dtype=np.float32)
    counts = np.ones((n, 3), dtype=np.int32)
    pref = np.full(n, 0.5, dtype=np.float32)

    for _ in range(30):
        actions = select_actions(rewards, counts, epsilon=0.02, rng=rng)
        apply_actions(pref, actions, delta=0.05)
        realized = np.where(actions == 0, 1.0, 0.0).astype(np.float32)
        update_rewards(rewards, counts, actions, realized, learning_rate=0.3)

    assert float(pref.mean()) < 0.2
    assert float((np.argmax(rewards, axis=1) == 0).mean()) > 0.95


def test_strategy_world_moves_toward_low_alpha_when_decrease_is_default_best():
    cfg = get_scenario("endogenous_paradise")
    cfg.n_steps = 8
    cfg.pairs_per_step = 3000
    cfg.population.n_human_prototypes = 200
    cfg.population.n_agent_prototypes = 1000
    cfg.topology.strategy.epsilon = 0.0
    cfg.topology.strategy.initial_pref = 0.5
    cfg.topology.strategy.initial_pref_sd = 0.0
    world = World.build(cfg)
    world.run(progress=False)

    terminal = world.metrics.history.steps[-1]
    assert terminal.endogenous_alpha < 0.2
    assert terminal.pref_smooth_share > 0.95


def test_chunked_realized_alpha_preserves_pair_alpha():
    from engine.core.population import Population, PopulationConfig
    from engine.core.topology import StrategyConfig, Topology, TopologyConfig
    from engine.core.transactions import coasean_step

    pop = Population.synthesize(
        PopulationConfig(n_human_prototypes=50, n_agent_prototypes=200, seed=4),
        strategy_config=StrategyConfig(enabled=True, initial_pref=0.37, initial_pref_sd=0.0),
    )
    topo = Topology.build(
        TopologyConfig(
            alpha=0.5,
            strategy=StrategyConfig(enabled=True, local_alpha_noise_sd=0.0),
        )
    )
    result = coasean_step(
        pop,
        topo,
        np.random.default_rng(5),
        n_pairs=1000,
        chunk_size=125,
        local_alpha=pop.intermediation_pref,
    )
    assert result.realized_alpha == pytest.approx(0.37)


def test_executed_interaction_shares_use_executed_weighted_pairs():
    from engine.core.transactions import executed_interaction_shares

    h_a = np.array([True, True, False, False, False])
    h_b = np.array([True, False, False, True, False])
    executed = np.array([True, True, True, False, True])
    pair_real_count = np.array([2.0, 3.0, 5.0, 100.0, 10.0])

    a2a, h2a, h2h = executed_interaction_shares(
        h_a, h_b, executed, pair_real_count,
    )

    assert a2a == pytest.approx(15.0 / 20.0)
    assert h2a == pytest.approx(3.0 / 20.0)
    assert h2h == pytest.approx(2.0 / 20.0)
    assert a2a + h2a + h2h == pytest.approx(1.0)


def test_firms_form_and_dissolve():
    from engine.core.institutions import dissolution_step, formation_step
    from engine.core.population import Population, PopulationConfig
    from engine.core.topology import InstitutionConfig

    rng = np.random.default_rng(1)
    pop = Population.synthesize(
        PopulationConfig(n_human_prototypes=20, n_agent_prototypes=80, seed=1)
    )
    cfg = InstitutionConfig(
        enabled=True,
        max_firms=10,
        formation_surplus_threshold=-1.0,
        max_firm_size=10,
    )
    formed = formation_step(pop, cfg, rng, surplus_per_proto=np.ones(pop.n, dtype=np.float32))
    assert formed > 0
    assert np.any(pop.firm_id >= 0)

    pop.wealth[pop.firm_id >= 0] = 0.0
    dissolved = dissolution_step(pop, cfg)
    assert dissolved > 0
    assert np.all(pop.firm_id == -1)


def test_capability_grows_with_surplus():
    from engine.core.dynamics import capability_update
    from engine.core.population import Population, PopulationConfig
    from engine.core.topology import PopulationDynamicsConfig

    pop = Population.synthesize(
        PopulationConfig(n_human_prototypes=20, n_agent_prototypes=80, seed=2)
    )
    before = pop.capability.copy()
    wealth_delta = np.ones(pop.n, dtype=np.float32) * float(pop.wealth.mean())
    cfg = PopulationDynamicsConfig(
        enabled=True,
        capability_learning_rate=0.01,
        capability_decay_rate=0.0,
    )
    capability_update(pop, wealth_delta, cfg)
    assert float(pop.capability.mean()) > float(before.mean())


def test_population_dynamics_savings_rate_controls_wealth_accumulation():
    cfg = get_scenario("equilibrium_drift")
    cfg.n_steps = 1
    cfg.pairs_per_step = 4000
    cfg.population.n_human_prototypes = 200
    cfg.population.n_agent_prototypes = 1000
    cfg.topology.pop_dynamics.enabled = True
    cfg.topology.pop_dynamics.savings_rate = 0.0
    cfg.topology.pop_dynamics.wealth_depreciation = 0.0
    cfg.topology.pop_dynamics.capability_learning_rate = 0.0
    cfg.topology.pop_dynamics.capability_decay_rate = 0.0
    cfg.topology.pop_dynamics.exit_wealth_threshold = -1.0

    world = World.build(cfg)
    wealth_before = world.population.wealth.copy()
    world.step()
    np.testing.assert_allclose(world.population.wealth, wealth_before)
