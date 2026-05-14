"""PR #6 — per-agent enrichments in `cast_snapshot`.

Three new keys per entry: `norm_vector` (full K-dim), `degree_centrality`
(from `pop.adjacency`), `recent_partners` (last 5 executed partner IDs
sourced from `pair_samples`).
"""
from __future__ import annotations

import numpy as np

from engine.core.population import Population, PopulationConfig
from engine.core.topology import NormsConfig, TopologyConfig
from engine.core.world import World, WorldConfig


def test_population_degree_centrality_set_for_scale_free() -> None:
    """`pop.degree_centrality` is populated when the network model builds an adjacency."""
    pop = Population.synthesize(
        PopulationConfig(
            n_human_prototypes=30, n_agent_prototypes=270, seed=33,
            network_model="scale_free", network_mean_degree=6,
        ),
    )
    assert pop.adjacency is not None
    assert pop.degree_centrality is not None
    assert pop.degree_centrality.shape == (pop.n,)
    assert pop.degree_centrality.min() >= 0
    assert int(pop.degree_centrality.sum()) > 0


def test_population_degree_centrality_none_for_well_mixed() -> None:
    pop = Population.synthesize(
        PopulationConfig(
            n_human_prototypes=30, n_agent_prototypes=270, seed=33,
            network_model="well_mixed",
        ),
    )
    assert pop.adjacency is None
    assert pop.degree_centrality is None


def test_snapshot_carries_norm_vector_when_norms_enabled() -> None:
    cfg = WorldConfig(
        population=PopulationConfig(
            n_human_prototypes=30, n_agent_prototypes=270, seed=43,
        ),
        topology=TopologyConfig(
            alpha=0.4,
            norms=NormsConfig(enabled=True, n_dimensions=4),
        ),
        cast_size=6,
        n_steps=2,
        pairs_per_step=2_000,
        seed=43,
    )
    world = World.build(cfg)
    last = None
    for _ in range(cfg.n_steps):
        last = world.step()
    assert last.cast_snapshot
    for entry in last.cast_snapshot:
        assert "norm_vector" in entry
        assert len(entry["norm_vector"]) == 4


def test_snapshot_recent_partners_populates_with_pair_sampling() -> None:
    """With pair sampling on, cast members accumulate recent_partners."""
    cfg = WorldConfig(
        population=PopulationConfig(
            n_human_prototypes=30, n_agent_prototypes=270, seed=47,
        ),
        topology=TopologyConfig(alpha=0.4),
        cast_size=6,
        pair_sample_k=64,  # plenty of samples to populate cast members
        n_steps=15,
        pairs_per_step=4_000,
        seed=47,
    )
    world = World.build(cfg)
    last = None
    for _ in range(cfg.n_steps):
        last = world.step()
    assert last.cast_snapshot
    populated = [e for e in last.cast_snapshot if e["recent_partners"]]
    assert populated, "expected at least one cast member with recent_partners"
    for e in last.cast_snapshot:
        assert "recent_partners" in e
        assert isinstance(e["recent_partners"], list)
        assert len(e["recent_partners"]) <= 5
        for pid in e["recent_partners"]:
            assert isinstance(pid, int)
            assert 0 <= pid < world.population.n


def test_snapshot_degree_centrality_surfaces_in_entry() -> None:
    cfg = WorldConfig(
        population=PopulationConfig(
            n_human_prototypes=30, n_agent_prototypes=270, seed=51,
            network_model="scale_free", network_mean_degree=6,
        ),
        topology=TopologyConfig(alpha=0.4),
        cast_size=6,
        n_steps=2,
        pairs_per_step=2_000,
        seed=51,
    )
    world = World.build(cfg)
    last = None
    for _ in range(cfg.n_steps):
        last = world.step()
    assert last.cast_snapshot
    degrees = [e["degree_centrality"] for e in last.cast_snapshot]
    assert all(isinstance(d, int) for d in degrees)
    assert any(d > 0 for d in degrees), "scale_free network should give some non-zero degrees"


def test_snapshot_well_mixed_reports_minus_one_degree() -> None:
    """Well-mixed network has no adjacency → degree_centrality = -1 in entries."""
    cfg = WorldConfig(
        population=PopulationConfig(
            n_human_prototypes=30, n_agent_prototypes=270, seed=53,
            network_model="well_mixed",
        ),
        topology=TopologyConfig(alpha=0.4),
        cast_size=6,
        n_steps=2,
        pairs_per_step=2_000,
        seed=53,
    )
    world = World.build(cfg)
    last = None
    for _ in range(cfg.n_steps):
        last = world.step()
    assert last.cast_snapshot
    for e in last.cast_snapshot:
        assert e["degree_centrality"] == -1
