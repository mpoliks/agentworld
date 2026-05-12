"""W2a — Hadfield-style persistent agent identity + registration regime.

The Hadfield argument (*Legal Infrastructure for Transformative AI
Governance*, arXiv:2602.01474) is that without a stable identifier the
regulator can read and without a registered-bit a regulator can update,
every higher-level governance design runs on infrastructure that does
not exist. W2a adds the smallest credible version of that
infrastructure to the alpha-engine.

These tests pin five contracts:

1. With `RegistrationConfig.enabled = False` (the canonical default)
   the new `agent_id` and `registered` fields exist on `Population`
   but no engine code reads them, so terminal metrics are bit-identical
   to the pre-W2a baseline.
2. `agent_id` is a stable monotonic int64; consecutive steps see the
   same id on the same prototype slot when entry/exit doesn't fire.
3. Enabling the registration mechanism with a `registration_cost`
   deducts wealth from registered agents (and humans are exempt).
4. With the W1a regulator gate also enabled, `registration_floor`
   raises the regulator gate's per-pair rejection probability on
   pairs that include an unregistered agent endpoint. The gate
   doesn't fire when `RegulatorConfig.enabled = False`, so
   registration alone (without a regulator to read it) does no work
   at the rejection layer.
5. Entry/exit re-issues fresh agent ids on prototype recycle.
"""

from __future__ import annotations

import numpy as np
import pytest

from engine.core.population import Population, PopulationConfig
from engine.core.topology import (
    PopulationDynamicsConfig,
    RegistrationConfig,
    RegulatorConfig,
)
from engine.core.world import World, WorldConfig
from engine.scenarios import get_scenario


def _small_cfg() -> WorldConfig:
    cfg = get_scenario("equilibrium_drift")
    cfg.n_steps = 4
    cfg.pairs_per_step = 4_000
    cfg.population.n_human_prototypes = 200
    cfg.population.n_agent_prototypes = 2_000
    cfg.seed = 23
    cfg.population.seed = 32
    return cfg


def _terminal_triple(world: World) -> tuple[float, float, float]:
    last = world.metrics.history.steps[-1]
    return (
        last.exo_baroque_index,
        last.real_welfare_cumulative,
        last.gini_wealth,
    )


def test_registration_off_is_bit_identical() -> None:
    """With `RegistrationConfig.enabled = False`, terminal metrics match
    a configuration that doesn't touch the registration config block.
    """
    cfg_default = _small_cfg()
    cfg_explicit = _small_cfg()
    cfg_explicit.topology.registration = RegistrationConfig(enabled=False)

    w_default = World.build(cfg_default)
    w_default.run(progress=False)
    w_explicit = World.build(cfg_explicit)
    w_explicit.run(progress=False)

    assert _terminal_triple(w_default) == _terminal_triple(w_explicit)


def test_agent_id_and_registered_fields_exist_at_default() -> None:
    """Even with the mechanism disabled, the new fields are populated
    so downstream code can introspect them; the *behavioural* default
    must be no-op.
    """
    cfg = _small_cfg()
    world = World.build(cfg)
    pop = world.population
    # Stable int64 identity, monotonic from 0.
    assert pop.agent_id is not None
    assert pop.agent_id.dtype == np.int64
    assert pop.agent_id[0] == 0
    assert pop.agent_id[-1] == pop.n - 1
    assert pop.agent_next_id == pop.n
    # `registered` defaults to all-True (the canonical implicit
    # assumption: everyone is treated as registered).
    assert pop.registered is not None
    assert pop.registered.dtype == bool
    assert bool(pop.registered.all())


def test_initial_share_below_one_uses_dedicated_seed() -> None:
    """`initial_registration_seed` is a dedicated stream so toggling
    the registration mechanism does not perturb any other population
    draw. Two populations with identical configs except the
    registration seed should have identical `wealth`, `capability`,
    `sector`, etc. — only `registered` differs.
    """
    base = Population.synthesize(
        PopulationConfig(n_human_prototypes=50, n_agent_prototypes=200, seed=7),
        registration_config=RegistrationConfig(
            enabled=True,
            initial_registered_share=0.5,
            initial_registration_seed=0,
        ),
    )
    other = Population.synthesize(
        PopulationConfig(n_human_prototypes=50, n_agent_prototypes=200, seed=7),
        registration_config=RegistrationConfig(
            enabled=True,
            initial_registered_share=0.5,
            initial_registration_seed=1,  # different seed
        ),
    )
    # All non-registration arrays identical.
    np.testing.assert_array_equal(base.capability, other.capability)
    np.testing.assert_array_equal(base.wealth, other.wealth)
    np.testing.assert_array_equal(base.sector, other.sector)
    np.testing.assert_array_equal(base.alignment, other.alignment)
    # Registration mask differs (with extremely high probability at n=200).
    assert not np.array_equal(base.registered, other.registered)
    # Humans always registered regardless of seed.
    assert bool(base.registered[base.is_human].all())
    assert bool(other.registered[other.is_human].all())


def test_registration_cost_deducts_from_registered_agents_only() -> None:
    """The per-step compliance cost only debits registered agents;
    humans and unregistered agents see no wealth deduction from this
    channel.
    """
    cfg = _small_cfg()
    cfg.topology.registration = RegistrationConfig(
        enabled=True,
        registration_cost=0.05,
        initial_registered_share=0.5,
        initial_registration_seed=42,
    )

    world = World.build(cfg)
    pop = world.population
    pre_wealth = pop.wealth.copy()
    pre_registered = pop.registered.copy()

    # One step. With pop_dynamics disabled, no entry/exit fires, so
    # the only wealth-changing channels are transactions and the new
    # compliance debit. We compare pre vs post on humans (should be
    # unaffected by the compliance debit) and on unregistered agents
    # (also unaffected by the compliance debit).
    world.step()

    human_mask = pop.is_human
    unreg_agent_mask = (~pop.is_human) & (~pre_registered)
    reg_agent_mask = (~pop.is_human) & pre_registered

    # Humans never paid the compliance cost — so the delta on them is
    # whatever transactions did, with no extra deduction. We can't
    # assert exact equality (transactions move wealth too), but we can
    # check that the *signed* wealth change on registered agents is
    # strictly more negative than on unregistered ones, since the
    # compliance debit only fires on the former.
    if reg_agent_mask.any() and unreg_agent_mask.any():
        delta_reg = (pop.wealth[reg_agent_mask] - pre_wealth[reg_agent_mask]).mean()
        delta_unreg = (pop.wealth[unreg_agent_mask] - pre_wealth[unreg_agent_mask]).mean()
        assert delta_reg < delta_unreg, (
            f"Registered agents should net pay more (mean delta {delta_reg:.4f}) "
            f"than unregistered ({delta_unreg:.4f}) due to the compliance debit."
        )


def test_registration_floor_raises_regulator_rejection() -> None:
    """With both W1a regulator and W2a registration enabled, a non-zero
    `registration_floor` raises the regulator gate's rejection rate
    relative to the same regulator config without the floor.
    """
    # Baseline: regulator on, registration off.
    cfg_no_floor = _small_cfg()
    cfg_no_floor.topology.regulator = RegulatorConfig(
        enabled=True,
        regulator_strength=0.10,
    )
    cfg_no_floor.topology.registration = RegistrationConfig(enabled=False)
    w_no_floor = World.build(cfg_no_floor)
    w_no_floor.run(progress=False)
    base_rejected = sum(
        m.rejected_regulator for m in w_no_floor.metrics.history.steps
    )

    # Active: regulator on, registration on with floor and a share that
    # leaves a chunk of agents unregistered.
    cfg_floor = _small_cfg()
    cfg_floor.topology.regulator = RegulatorConfig(
        enabled=True,
        regulator_strength=0.10,
    )
    cfg_floor.topology.registration = RegistrationConfig(
        enabled=True,
        registration_floor=0.30,
        initial_registered_share=0.5,
        initial_registration_seed=99,
    )
    w_floor = World.build(cfg_floor)
    w_floor.run(progress=False)
    active_rejected = sum(
        m.rejected_regulator for m in w_floor.metrics.history.steps
    )

    assert active_rejected > base_rejected, (
        f"registration_floor should raise regulator rejections: "
        f"baseline total {base_rejected:.1f}, with-floor total {active_rejected:.1f}."
    )


def test_registration_alone_does_nothing_at_gate() -> None:
    """With the W1a regulator gate *disabled*, enabling the registration
    mechanism cannot change rejection behaviour (registration only does
    work through the regulator). Terminal-metric bit-identity is too
    strict because the compliance-cost channel still runs; we check
    instead that `rejected_regulator == 0` in both configurations.
    """
    cfg_off = _small_cfg()
    cfg_off.topology.registration = RegistrationConfig(enabled=False)
    w_off = World.build(cfg_off)
    w_off.run(progress=False)

    cfg_on = _small_cfg()
    cfg_on.topology.registration = RegistrationConfig(
        enabled=True,
        registration_floor=0.30,
        registration_cost=0.0,  # isolate to gate behaviour
        initial_registered_share=0.5,
    )
    # `cfg.topology.regulator.enabled` stays at the default (False) —
    # the gate doesn't fire, so the floor cannot bite.
    w_on = World.build(cfg_on)
    w_on.run(progress=False)

    assert all(m.rejected_regulator == 0.0 for m in w_off.metrics.history.steps)
    assert all(m.rejected_regulator == 0.0 for m in w_on.metrics.history.steps)


def test_entry_exit_reissues_agent_ids() -> None:
    """Recycled prototypes get fresh `agent_id` values when the
    registration mechanism is enabled (Hadfield's contract: a
    re-entrant is a *new* actor, not the same one with reset state).
    With the mechanism disabled the id stays put.
    """
    cfg = _small_cfg()
    cfg.topology.pop_dynamics = PopulationDynamicsConfig(
        enabled=True,
        # Set thresholds so most agents fail and recycle each step.
        exit_wealth_threshold=1e9,
        wealth_depreciation=0.0,
        capability_learning_rate=0.0,
        capability_decay_rate=0.0,
    )

    # Disabled: agent_id stays untouched across recycling.
    cfg.topology.registration = RegistrationConfig(enabled=False)
    w_off = World.build(cfg)
    id_pre_off = w_off.population.agent_id.copy()
    w_off.step()
    assert np.array_equal(w_off.population.agent_id, id_pre_off)

    # Enabled: every recycled slot gets a fresh monotonic id.
    cfg.topology.registration = RegistrationConfig(enabled=True)
    w_on = World.build(cfg)
    id_pre_on = w_on.population.agent_id.copy()
    next_id_pre = w_on.population.agent_next_id
    w_on.step()
    # Every prototype recycled in this step has a new id; counter has advanced.
    changed = w_on.population.agent_id != id_pre_on
    assert changed.any(), "exit_threshold should have forced recyclings."
    assert w_on.population.agent_next_id == next_id_pre + int(changed.sum())
    # New ids are strictly above any pre-existing id.
    assert w_on.population.agent_id[changed].min() >= next_id_pre
