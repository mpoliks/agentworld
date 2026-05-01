"""Tests for the dynamic law layer from `brief/dynamic_mechanisms.md`, §3."""

from __future__ import annotations

import numpy as np
import pytest

from engine.core.population import Population, PopulationConfig
from engine.core.topology import LawConfig, Topology, TopologyConfig
from engine.core.transactions import coasean_step
from engine.core.world import World, WorldConfig


def _small_population(seed: int = 77) -> Population:
    return Population.synthesize(
        PopulationConfig(
            n_human_prototypes=300,
            n_agent_prototypes=3_000,
            seed=seed,
        )
    )


def test_law_strength_enables_transaction_surplus():
    """Weak law suppresses stranger-trade surplus before the cost filter."""
    pop = _small_population()
    topo = Topology.build(
        TopologyConfig(
            alpha=0.35,
            cross_stack_compat=0.45,
            law=LawConfig(enabled=True, upkeep_investment=0.0, natural_decay=0.0),
        )
    )

    strong = coasean_step(
        pop,
        topo,
        np.random.default_rng(1),
        n_pairs=20_000,
        law_strength=1.0,
        law_capture=0.0,
        gini_wealth=0.35,
    )
    weak = coasean_step(
        pop,
        topo,
        np.random.default_rng(1),
        n_pairs=20_000,
        law_strength=0.20,
        law_capture=0.0,
        gini_wealth=0.35,
    )

    assert weak.real_surplus_added < strong.real_surplus_added
    assert weak.n_transactions_real < strong.n_transactions_real
    assert weak.law_weak_surplus_loss > strong.law_weak_surplus_loss


def test_law_capture_penalizes_cross_stack_high_gini_trade():
    """Capture turns concentration and cross-stack incompatibility into surplus loss."""
    pop = _small_population(seed=88)
    topo = Topology.build(
        TopologyConfig(
            alpha=0.35,
            cross_stack_compat=0.20,
            law=LawConfig(enabled=True, upkeep_investment=0.0, natural_decay=0.0),
        )
    )

    neutral = coasean_step(
        pop,
        topo,
        np.random.default_rng(2),
        n_pairs=20_000,
        law_strength=1.0,
        law_capture=0.0,
        gini_wealth=0.75,
    )
    captured = coasean_step(
        pop,
        topo,
        np.random.default_rng(2),
        n_pairs=20_000,
        law_strength=1.0,
        law_capture=1.0,
        gini_wealth=0.75,
    )

    assert captured.real_surplus_added < neutral.real_surplus_added
    assert captured.law_capture_surplus_loss > 0.0
    assert neutral.law_capture_surplus_loss == pytest.approx(0.0)


def test_world_updates_law_state_and_charges_upkeep():
    cfg = WorldConfig(
        population=PopulationConfig(
            n_human_prototypes=300,
            n_agent_prototypes=3_000,
            wealth_pareto_alpha=1.2,
            seed=99,
        ),
        topology=TopologyConfig(
            alpha=0.4,
            law=LawConfig(
                enabled=True,
                law_strength_initial=0.60,
                upkeep_investment=0.10,
                natural_decay=0.005,
                law_capture_initial=0.0,
                civic_pushback_default=0.0,
            ),
        ),
        n_steps=3,
        pairs_per_step=8_000,
        seed=99,
    )
    world = World.build(cfg)
    world.run(progress=False)
    first = world.metrics.history.steps[0]
    last = world.metrics.history.steps[-1]

    assert first.law_strength == pytest.approx(0.60)
    assert last.law_strength > first.law_strength
    assert world.law_capture > first.law_capture
    assert first.law_upkeep_cost_step > 0.0
    assert first.law_surplus_loss_fraction > 0.0


def test_law_disabled_is_behaviorally_inert():
    cfg = WorldConfig(
        population=PopulationConfig(
            n_human_prototypes=300,
            n_agent_prototypes=3_000,
            seed=111,
        ),
        topology=TopologyConfig(
            alpha=0.4,
            law=LawConfig(
                enabled=False,
                law_strength_initial=0.25,
                law_capture_initial=1.0,
                upkeep_investment=0.50,
                natural_decay=0.20,
            ),
        ),
        n_steps=3,
        pairs_per_step=8_000,
        seed=111,
    )
    world = World.build(cfg)
    world.run(progress=False)
    first = world.metrics.history.steps[0]
    last = world.metrics.history.steps[-1]

    assert first.law_strength == pytest.approx(1.0)
    assert first.law_capture == pytest.approx(0.0)
    assert world.law_strength == pytest.approx(1.0)
    assert world.law_capture == pytest.approx(0.0)
    assert last.law_upkeep_cost_step == pytest.approx(0.0)
    assert last.law_weak_surplus_loss_step == pytest.approx(0.0)
    assert last.law_capture_surplus_loss_step == pytest.approx(0.0)
