"""Smoke tests for the exo-engine."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from engine.exo.config import (
    DragConfig,
    ExoWorldConfig,
    ImperialConfig,
    RegionConfig,
)
from engine.exo.imperial import ImperialState
from engine.exo.scenarios import SCENARIOS, anxiety_dampener, get_scenario
from engine.exo.sweep import (
    basin_counts,
    run_exo_sweep,
    run_imperial_sweep,
)
from engine.exo.world import ExoWorld


def _shrink(cfg, n_steps=4, n_regions=4):
    cfg.n_steps = n_steps
    cfg.region.n_regions = n_regions
    return cfg


@pytest.mark.parametrize("name", list(SCENARIOS.keys()))
def test_exo_scenario_runs(name):
    cfg = _shrink(get_scenario(name))
    world = ExoWorld.build(cfg)
    history = world.run(progress=False)
    assert len(history.steps) == cfg.n_steps
    terminal = history.steps[-1]
    assert terminal.exo_circulation_index >= 0
    assert terminal.real_produced_total >= 0
    assert terminal.cumulative_markets >= 0


def test_pure_lift_dominates_combine_state():
    pl = _shrink(get_scenario("pure_lift"), n_steps=20, n_regions=6)
    cs = _shrink(get_scenario("combine_state"), n_steps=20, n_regions=6)
    pure_world = ExoWorld.build(pl)
    pure_world.run(progress=False)
    comb_world = ExoWorld.build(cs)
    comb_world.run(progress=False)
    pure_t = pure_world.history.steps[-1]
    comb_t = comb_world.history.steps[-1]
    # Pure lift should have higher exo circulation than combine state.
    assert pure_t.exo_circulation_index > comb_t.exo_circulation_index
    # Combine state should pay materially more for suppression.
    assert comb_t.suppression_welfare_cost > pure_t.suppression_welfare_cost


def test_last_mile_revolt_compresses_real_production():
    base_cfg = _shrink(get_scenario("fold_cathedral"), n_steps=20, n_regions=6)
    base = ExoWorld.build(base_cfg)
    base.run(progress=False)
    revolt = ExoWorld.build(_shrink(get_scenario("last_mile_revolt"), n_steps=20, n_regions=6))
    revolt.run(progress=False)
    assert revolt.history.steps[-1].real_produced_total < base.history.steps[-1].real_produced_total


def test_anxiety_dampener_reduces_lift_relative_to_drag_saturation():
    drag_sat = ExoWorld.build(_shrink(get_scenario("drag_saturation"), n_steps=30, n_regions=6))
    drag_sat.run(progress=False)
    dampener = ExoWorld.build(_shrink(get_scenario("anxiety_dampener"), n_steps=30, n_regions=6))
    dampener.run(progress=False)
    # Anxiety dampener should produce less circulation than drag saturation
    # because dampener tokens consume welfare without enabling lift.
    assert dampener.history.steps[-1].exo_circulation_index <= drag_sat.history.steps[-1].exo_circulation_index


def test_exo_phase_space_sweep_smoke():
    summary = run_exo_sweep(
        drag_values=[0.1, 0.85],
        suppression_values=[0.1, 0.9],
        n_steps=4,
        n_regions=4,
    )
    assert len(summary.points) == 4
    assert sum(basin_counts(summary.points).values()) == 4


# ===== Imperial / non-coextension tests =================================


def test_imperial_state_initialises_with_all_tracts_populated():
    cfg = ImperialConfig(n_tracts=4)
    rng = np.random.default_rng(42)
    state = ImperialState.initialize(cfg, n_regions=12, rng=rng)
    assert state.n_tracts == 4
    assert (state.tract_polity_count > 0).all()
    assert state.resource_endowment.shape == (4,)
    assert state.attractor_strength.shape == (4,)
    assert (state.violence_floor >= cfg.historical_violence_floor * 0.4).all()


def test_imperial_extraction_drains_polity_welfare_and_pools_capital():
    cfg = get_scenario("imperial_inheritance")
    cfg.n_steps = 30
    cfg.region.n_regions = 10
    cfg.imperial = ImperialConfig(
        enabled=True, n_tracts=4, extraction_rate=0.20, seed=cfg.imperial.seed
    )
    world = ExoWorld.build(cfg)
    world.run(progress=False)
    s = world.history.steps[-1]
    assert s.imperial_extraction_total > 0.0
    assert s.imperial_capital_pooled_total > 0.0
    assert s.imperial_capital_concentration > 0.0


def test_imperial_disabled_runs_zero_extraction():
    cfg = get_scenario("fold_cathedral")
    cfg.n_steps = 10
    cfg.region.n_regions = 6
    cfg.imperial = ImperialConfig(enabled=False)
    world = ExoWorld.build(cfg)
    world.run(progress=False)
    s = world.history.steps[-1]
    assert s.imperial_extraction_total == 0.0
    assert s.imperial_capital_pooled_total == 0.0
    assert s.imperial_capital_concentration == 0.0
    assert world.imperial_state is None


def test_imperial_pool_layers_redistribute_independent_of_compat():
    """High pooling with low cross-region compat should still concentrate
    capital at the tract level: empire is non-coextensive with polity ties.
    """
    cfg = ExoWorldConfig(
        region=RegionConfig(n_regions=12, cross_region_compat=0.05),
        imperial=ImperialConfig(
            enabled=True,
            n_tracts=3,
            tract_attractor_dirichlet=0.5,
            capital_pooling_strength=0.45,
            pool_layers=4,
            extraction_rate=0.10,
            seed=8888,
        ),
        n_steps=25,
        seed=2222,
    )
    world = ExoWorld.build(cfg)
    world.run(progress=False)
    s = world.history.steps[-1]
    assert s.imperial_capital_concentration > 0.4


# ===== Adaptive Coasean dampener tests ==================================


def test_adaptive_dampener_responds_to_welfare_drop():
    """When welfare per polity is far below target, the dampener should
    rise toward its cap. When welfare is above target, dampener should
    stay near the static floor.
    """
    # Low-welfare configuration → adaptive dampener should fire.
    cfg_low = anxiety_dampener()
    cfg_low.n_steps = 30
    w_low = ExoWorld.build(cfg_low)
    w_low.run(progress=False)
    high_dampener = w_low.history.steps[-1].coasean_dampener_max

    # High-welfare counterfactual: lower target, no extraction.
    cfg_high = anxiety_dampener()
    cfg_high.n_steps = 30
    cfg_high = replace(
        cfg_high,
        drag=replace(cfg_high.drag, adaptive_welfare_target=0.001),
        imperial=ImperialConfig(enabled=False),
    )
    w_high = ExoWorld.build(cfg_high)
    w_high.run(progress=False)
    low_dampener = w_high.history.steps[-1].coasean_dampener_max

    assert high_dampener > low_dampener


def test_adaptive_dampener_does_not_exceed_cap():
    cfg = anxiety_dampener()
    cfg.n_steps = 50
    w = ExoWorld.build(cfg)
    w.run(progress=False)
    cap = cfg.drag.adaptive_dampener_max
    for s in w.history.steps:
        assert s.coasean_dampener_max <= cap + 1e-9
        assert s.coasean_dampener_mean <= cap + 1e-9


def test_imperial_phase_space_sweep_smoke():
    summary = run_imperial_sweep(
        extraction_values=[0.0, 0.20],
        pooling_values=[0.0, 0.40],
        n_steps=6,
        n_regions=6,
        n_tracts=3,
    )
    assert len(summary.points) == 4
    assert sum(basin_counts(summary.points).values()) == 4


def test_tract_realignment_runs_and_records_attractor_changes():
    cfg = get_scenario("tract_realignment")
    cfg.n_steps = 60
    cfg.region.n_regions = 10
    world = ExoWorld.build(cfg)
    pre_attractor = world.imperial_state.attractor_strength.copy()
    world.run(progress=False)
    post_attractor = world.imperial_state.attractor_strength.copy()
    # The schedule should have shifted attractor strengths over time.
    assert not np.allclose(pre_attractor, post_attractor)
