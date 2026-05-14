"""Spatial-sandbox scenario factory.

The factory in `engine/scenarios/__init__.py` is the canonical
zero-lever-touch config the spatial-sandbox dashboard runs against.
Every optional subsystem is on with the defaults from
`docs/plans/spatial-sandbox.md` §3, and `cast_size` / `pair_sample_k`
are large enough that the PR #5 sub-events populate every tick.

Tests:

- the factory returns a fully-formed `WorldConfig` with every subsystem
  enabled;
- a short run emits a non-empty cast snapshot and pair-sample list, so
  `_v2_subpayloads` produces `cast_snapshot_v2` and `edges_v2` every
  tick a v2 subscriber actually needs them;
- the snapshot carries the PR #1/#2/#6 enrichments
  (`firm_sectors`, `certified`, `norm_vector`, `degree_centrality`).
"""
from __future__ import annotations

from engine.core.world import World
from engine.scenarios import get_scenario
from engine.serve import _step_metrics_to_dict, _v2_subpayloads


def test_factory_turns_every_subsystem_on():
    cfg = get_scenario("spatial_sandbox")
    t = cfg.topology
    assert t.norms.enabled
    assert t.norms.n_dimensions == 8
    assert t.norms.certified_fraction == 0.5
    assert t.demand.enabled
    assert t.pigouvian.enabled
    assert t.registration.enabled
    assert t.institutions.enabled
    assert t.institutions.cross_sector_firms
    assert t.pop_dynamics.enabled
    assert t.mission.enabled
    assert t.strategy.enabled
    assert t.law.enabled
    assert t.regulator.enabled
    assert t.compute.enabled
    assert cfg.cast_size == 5000
    assert cfg.pair_sample_k == 1500


def test_short_run_emits_cast_and_edges_v2():
    cfg = get_scenario("spatial_sandbox")
    # SMALL-scale population is heavy for a unit test; shrink it but
    # keep every subsystem on. Cast size is clamped to population size
    # by the cast builder so 200 is safe.
    cfg.population.n_human_prototypes = 60
    cfg.population.n_agent_prototypes = 540
    cfg.cast_size = 200
    cfg.pair_sample_k = 64
    cfg.pairs_per_step = 2_000
    cfg.n_steps = 3

    world = World.build(cfg)
    last_metrics = None
    for _ in range(cfg.n_steps):
        last_metrics = world.step()

    payload = _step_metrics_to_dict(last_metrics)
    sub = dict(_v2_subpayloads(payload))

    assert "cast_snapshot_v2" in sub
    assert "edges_v2" in sub

    snap = sub["cast_snapshot_v2"]["snapshot"]
    assert len(snap) > 0
    entry = snap[0]
    # PR #1 (cross-sector firms): firm_sectors list present.
    assert "firm_sectors" in entry
    assert isinstance(entry["firm_sectors"], list)
    # PR #2 (certified_fraction): per-agent certified scalar present.
    assert "certified" in entry
    # PR #6 (snapshot enrichments): full norm vector + degree centrality.
    assert "norm_vector" in entry
    assert len(entry["norm_vector"]) == cfg.topology.norms.n_dimensions
    assert "degree_centrality" in entry
    assert entry["degree_centrality"] >= 0  # SBM network has adjacency


def test_factory_is_idempotent():
    """Two calls return equivalent (but independent) WorldConfigs."""
    a = get_scenario("spatial_sandbox")
    b = get_scenario("spatial_sandbox")
    assert a is not b
    assert a.seed == b.seed
    assert a.cast_size == b.cast_size
    assert a.topology.norms.n_dimensions == b.topology.norms.n_dimensions
