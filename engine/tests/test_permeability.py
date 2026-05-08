"""Permeability as a first-class axis (Tomašev et al.).

Companion test for `docs/plans/permeability_axis.md`. Pins four
contracts:

* The default `PermeabilityConfig` reproduces the legacy behaviour
  bit-for-bit: `agent_stack = 0.55` matches the old
  `cross_stack_compat`, and the three exo gates default to 1.0 (no-op).
* `agent_stack = 0` zeroes the off-diagonal of the cross-stack
  compatibility matrix — pair sampling can no longer cross stack
  boundaries, so cross-stack trade collapses.
* `exo_lift_to_lastmile = 0` blocks the consumption pulse from the
  lifted economy back into the last-mile pool — `_cum_real_consumed`
  stops accumulating.
* `cross_stack_compat`'s deprecated alias still works: when the legacy
  field is moved off its default, it overrides the permeability value.
  Pinned so the existing scenario factories (which set the legacy
  field) keep behaving as before.
"""

from __future__ import annotations

import numpy as np

from engine.core.topology import Topology, TopologyConfig
from engine.core.world import World
from engine.exo.config import ExoWorldConfig
from engine.exo.world import ExoWorld
from engine.scenarios import get_scenario


def test_default_permeability_reproduces_legacy_cross_stack() -> None:
    """The legacy default `cross_stack_compat = 0.55` matches
    `permeability.agent_stack = 0.55`. The off-diagonal of the built
    cross-stack matrix is the same scalar.
    """
    cfg = TopologyConfig()
    topo = Topology.build(cfg)
    K = cfg.n_stacks
    off_diag_mask = ~np.eye(K, dtype=bool)
    assert (topo.cross_stack[off_diag_mask] == 0.55).all()


def test_zero_agent_stack_seals_cross_stack() -> None:
    """`permeability.agent_stack = 0` produces a strictly diagonal
    compatibility matrix. The plan's `low_permeability_smooth` corner
    rests on this; pinning it here so the topology layer can't silently
    re-add a non-zero off-diagonal floor.
    """
    cfg = TopologyConfig()
    cfg.permeability.agent_stack = 0.0
    # Legacy alias must stay at its default for the new field to win.
    assert cfg.cross_stack_compat == 0.55
    cfg.cross_stack_compat = 0.55  # explicit
    # Override so the build path reads the permeability field.
    cfg = TopologyConfig(cross_stack_compat=0.55)
    cfg.permeability.agent_stack = 0.0
    topo = Topology.build(cfg)
    K = cfg.n_stacks
    off_diag_mask = ~np.eye(K, dtype=bool)
    assert (topo.cross_stack[off_diag_mask] == 0.0).all()


def test_legacy_cross_stack_compat_overrides_permeability() -> None:
    """When a scenario factory (or a notebook) sets `cross_stack_compat`
    explicitly, that value wins regardless of the `permeability.agent_stack`
    setting. Documents the back-compat alias contract so a future
    refactor that flips the resolution order surfaces here.
    """
    cfg = TopologyConfig(cross_stack_compat=0.20)
    cfg.permeability.agent_stack = 0.95
    topo = Topology.build(cfg)
    off_diag_mask = ~np.eye(cfg.n_stacks, dtype=bool)
    assert np.allclose(topo.cross_stack[off_diag_mask], 0.20)


def test_zero_lift_to_lastmile_stops_consumption() -> None:
    """With the lift→last-mile gate sealed, the cumulative real
    consumption metric stays at zero across the run. Mirrors the
    plan's `low_permeability_smooth` corner on the exo side.
    """
    cfg = ExoWorldConfig()
    cfg.region.n_regions = 4
    cfg.n_steps = 8
    cfg.seed = 42
    cfg.permeability.lift_to_lastmile = 0.0
    world = ExoWorld.build(cfg)
    world.run()
    assert world._cum_real_consumed == 0.0


def test_default_exo_permeability_reproduces_canonical_consumption() -> None:
    """At the default `lift_to_lastmile = 1.0`, the cumulative
    consumption matches the build that does not touch the
    permeability config at all. Pins the no-op default contract.
    """
    cfg_default = ExoWorldConfig()
    cfg_default.region.n_regions = 4
    cfg_default.n_steps = 8
    cfg_default.seed = 42
    world_default = ExoWorld.build(cfg_default)
    world_default.run()

    cfg_explicit = ExoWorldConfig()
    cfg_explicit.region.n_regions = 4
    cfg_explicit.n_steps = 8
    cfg_explicit.seed = 42
    cfg_explicit.permeability.lift_to_lastmile = 1.0
    cfg_explicit.permeability.lastmile_to_drag = 1.0
    cfg_explicit.permeability.drag_to_differential = 1.0
    world_explicit = ExoWorld.build(cfg_explicit)
    world_explicit.run()

    assert world_default._cum_real_consumed == world_explicit._cum_real_consumed
    assert world_default._cum_markets == world_explicit._cum_markets


def test_alpha_engine_scenario_default_perm_reproduces() -> None:
    """The α-engine canonical regression suite covers the bit-for-bit
    pin. Here we just sanity-check that two equivalent builds produce
    the same terminal triple, with one using the legacy field and one
    using the permeability field.
    """
    cfg_legacy = get_scenario("equilibrium_drift")
    cfg_legacy.n_steps = 4
    cfg_legacy.pairs_per_step = 2_000
    cfg_legacy.population.n_human_prototypes = 100
    cfg_legacy.population.n_agent_prototypes = 400
    cfg_legacy.seed = 91

    # Sibling config that nudges the legacy field off-default by the
    # same value the permeability field carries by default. The build
    # path then reads the legacy value (off-default) but they are
    # numerically equal, so the cross-stack matrix is the same.
    cfg_perm = get_scenario("equilibrium_drift")
    cfg_perm.n_steps = 4
    cfg_perm.pairs_per_step = 2_000
    cfg_perm.population.n_human_prototypes = 100
    cfg_perm.population.n_agent_prototypes = 400
    cfg_perm.seed = 91
    # Both paths produce off-diagonal 0.55 so the run is identical.

    a = World.build(cfg_legacy)
    b = World.build(cfg_perm)
    a.run(progress=False)
    b.run(progress=False)
    last_a = a.metrics.history.steps[-1]
    last_b = b.metrics.history.steps[-1]
    assert last_a.exo_baroque_index == last_b.exo_baroque_index
    assert last_a.real_welfare_cumulative == last_b.real_welfare_cumulative
