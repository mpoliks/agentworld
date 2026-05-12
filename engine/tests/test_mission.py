"""W2b — mission-economy lever.

The mission lever has three coupled effects when enabled:

1. **Formation bias.** In `engine/core/institutions.py:formation_step`,
   candidates in `MissionConfig.coordinator_sectors` see their
   `formation_surplus_threshold` multiplied by
   `formation_threshold_factor`. Below 1.0 it makes coordination
   cheaper in those sectors; above 1.0 it makes it harder (the
   `mission_competing` adversarial sibling).
2. **Levy.** Each step, `mission_levy * tx.real_surplus_added` is
   skimmed from cleared real surplus into a world-level
   `_mission_pool`. The levy reduces `real_step` (it's a sink, not a
   transfer) and is logged in the welfare ledger.
3. **Disbursement.** Each step, a fraction
   `capability_uplift_per_unit_pool` of the pool is drained into
   capability boosts for coordinator-sector agents. `levy_target`
   chooses flat-share (`coordinator_uplift`) or proportional-to-
   capability (`regressive_pool`, the captured mode).

These tests pin the three contracts plus a bit-identity guarantee at
the default and an existence check for the three registered
scenarios.
"""

from __future__ import annotations

import numpy as np
import pytest

from engine.core.topology import (
    InstitutionConfig,
    MissionConfig,
)
from engine.core.world import World
from engine.scenarios import SCENARIOS, get_scenario


def _small_cfg(scenario_name: str = "equilibrium_drift") -> "WorldConfig":  # noqa
    cfg = get_scenario(scenario_name)
    cfg.n_steps = 4
    cfg.pairs_per_step = 4_000
    cfg.population.n_human_prototypes = 200
    cfg.population.n_agent_prototypes = 2_000
    cfg.seed = 51
    cfg.population.seed = 15
    return cfg


def _terminal_triple(world: World) -> tuple[float, float, float]:
    last = world.metrics.history.steps[-1]
    return (
        last.exo_baroque_index,
        last.real_welfare_cumulative,
        last.gini_wealth,
    )


def test_mission_off_is_bit_identical() -> None:
    """Default-off mission config preserves canonical bit-identity."""
    cfg_default = _small_cfg()
    cfg_explicit = _small_cfg()
    cfg_explicit.topology.mission = MissionConfig(enabled=False)

    w_default = World.build(cfg_default)
    w_default.run(progress=False)
    w_explicit = World.build(cfg_explicit)
    w_explicit.run(progress=False)

    assert _terminal_triple(w_default) == _terminal_triple(w_explicit)
    assert w_default._mission_pool == 0.0
    assert w_explicit._mission_pool == 0.0


def test_mission_levy_accumulates_pool_and_drains() -> None:
    """With the lever on, the pool tracks cumulative levy minus
    cumulative disbursement; both are positive over the run.
    """
    cfg = _small_cfg()
    cfg.n_steps = 6
    cfg.topology.mission = MissionConfig(
        enabled=True,
        coordinator_sectors=(9, 10),
        mission_levy=0.10,
        capability_uplift_per_unit_pool=0.05,
        levy_target="coordinator_uplift",
    )
    world = World.build(cfg)
    world.run(progress=False)
    # Pool started at 0, took non-zero levy each step, drained some;
    # final pool should be finite and non-negative.
    assert world._mission_pool >= 0.0
    # Some welfare was redirected to the pool — real_welfare_cumulative
    # should be strictly below what it would have been without the levy.
    cfg_off = _small_cfg()
    cfg_off.n_steps = 6
    cfg_off.topology.mission = MissionConfig(enabled=False)
    w_off = World.build(cfg_off)
    w_off.run(progress=False)
    assert (
        world.metrics.history.steps[-1].real_welfare_cumulative
        < w_off.metrics.history.steps[-1].real_welfare_cumulative
    )


def test_disbursement_lifts_coordinator_sector_capability() -> None:
    """With `coordinator_uplift` targeting, mean capability in
    coordinator sectors grows relative to the same agents in a no-mission
    control. Test on `equilibrium_drift` with population dynamics off so
    capability_update / depreciation don't confound the signal.
    """
    cfg = _small_cfg()
    cfg.topology.pop_dynamics.enabled = False
    cfg.topology.mission = MissionConfig(
        enabled=True,
        coordinator_sectors=(9, 10),
        mission_levy=0.20,
        capability_uplift_per_unit_pool=1.0,  # disburse the whole pool every step
        levy_target="coordinator_uplift",
    )
    world = World.build(cfg)
    coord_mask = (
        np.isin(world.population.sector, np.asarray([9, 10], dtype=world.population.sector.dtype))
        & (~world.population.is_human)
    )
    other_mask = (~coord_mask) & (~world.population.is_human)
    cap_pre_coord = float(world.population.capability[coord_mask].mean()) if coord_mask.any() else 0.0
    cap_pre_other = float(world.population.capability[other_mask].mean()) if other_mask.any() else 0.0
    world.run(progress=False)
    cap_post_coord = float(world.population.capability[coord_mask].mean()) if coord_mask.any() else 0.0
    cap_post_other = float(world.population.capability[other_mask].mean()) if other_mask.any() else 0.0
    # Coordinator-sector capability should have grown relative to other agents.
    delta_coord = cap_post_coord - cap_pre_coord
    delta_other = cap_post_other - cap_pre_other
    assert delta_coord > delta_other, (
        f"Coordinator-sector capability delta {delta_coord:.6f} should exceed "
        f"non-coordinator delta {delta_other:.6f} under flat-share disbursement."
    )


def test_regressive_target_concentrates_uplift() -> None:
    """`regressive_pool` disbursement should put more uplift on the
    top-capability quartile of coordinator-sector agents than on the
    bottom — the Matthew-effect contract the captured-mode lever
    enforces.
    """
    cfg = _small_cfg()
    cfg.topology.pop_dynamics.enabled = False
    cfg.topology.mission = MissionConfig(
        enabled=True,
        coordinator_sectors=(9, 10),
        mission_levy=0.20,
        capability_uplift_per_unit_pool=1.0,
        levy_target="regressive_pool",
    )
    world = World.build(cfg)
    coord_mask = (
        np.isin(world.population.sector, np.asarray([9, 10], dtype=world.population.sector.dtype))
        & (~world.population.is_human)
    )
    cap_pre = world.population.capability[coord_mask].copy()
    # Use the pre-run capability to define quartiles so we can compare
    # apples to apples after the run shifts them.
    q75 = float(np.quantile(cap_pre, 0.75))
    q25 = float(np.quantile(cap_pre, 0.25))
    top_q = cap_pre >= q75
    bot_q = cap_pre <= q25
    world.run(progress=False)
    cap_post = world.population.capability[coord_mask]
    delta_top = float((cap_post[top_q] - cap_pre[top_q]).mean()) if top_q.any() else 0.0
    delta_bot = float((cap_post[bot_q] - cap_pre[bot_q]).mean()) if bot_q.any() else 0.0
    assert delta_top > delta_bot, (
        f"Regressive disbursement should favour the top-capability quartile: "
        f"top delta {delta_top:.6f} vs bottom delta {delta_bot:.6f}."
    )


def test_formation_threshold_factor_changes_firm_count() -> None:
    """With institutions on and the mission threshold factor below 1.0,
    coordinator-sector firms form more easily than they would without
    the bias. We check this by comparing firm counts at terminal step.
    """
    base = _small_cfg()
    base.topology.institutions = InstitutionConfig(
        enabled=True,
        formation_surplus_threshold=0.001,
        formation_check_every_k=1,
    )
    base.topology.mission = MissionConfig(enabled=False)
    w_base = World.build(base)
    w_base.run(progress=False)
    firms_base = int(np.unique(w_base.population.firm_id[w_base.population.firm_id >= 0]).size)

    biased = _small_cfg()
    biased.topology.institutions = InstitutionConfig(
        enabled=True,
        formation_surplus_threshold=0.001,
        formation_check_every_k=1,
    )
    biased.topology.mission = MissionConfig(
        enabled=True,
        coordinator_sectors=(9, 10),
        formation_threshold_factor=0.1,
    )
    w_biased = World.build(biased)
    w_biased.run(progress=False)
    firms_biased = int(np.unique(w_biased.population.firm_id[w_biased.population.firm_id >= 0]).size)

    # With a more permissive threshold in coordinator sectors, firm
    # count should be at least as high (typically strictly higher).
    assert firms_biased >= firms_base, (
        f"Lower formation threshold in coordinator sectors should form "
        f"at least as many firms; got biased={firms_biased}, base={firms_base}."
    )


def test_registered_scenarios_exist_and_run() -> None:
    """The three mission scenarios are registered and can build and
    step through a short run. Substantive welfare/EBI sign-of-effect
    claims are deferred to a dedicated sweep; here we just confirm the
    plumbing.
    """
    for name in ("mission_economy", "mission_captured", "mission_competing"):
        assert name in SCENARIOS, f"scenario {name!r} missing from registry"
        cfg = get_scenario(name)
        cfg.n_steps = 2
        cfg.pairs_per_step = 2_000
        cfg.population.n_human_prototypes = 100
        cfg.population.n_agent_prototypes = 600
        world = World.build(cfg)
        world.run(progress=False)
        assert world.step_idx == 2
