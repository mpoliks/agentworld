"""Smoke tests for the engine. Run with: pytest engine/tests/"""

from __future__ import annotations

import pytest

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
