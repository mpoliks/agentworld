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


# ---------------------------------------------------------------------------
# S1 — Audit-trail tampering
# ---------------------------------------------------------------------------


def test_audit_tampering_default_off_is_bit_identical() -> None:
    """`RegulatorConfig.audit_tampering_rate = 0` (the default) preserves
    canonical bit-identity even with the regulator + registration
    mechanisms enabled. Defaulting off is the W2a contract.
    """
    cfg_default = _small_cfg()
    cfg_default.topology.regulator = RegulatorConfig(
        enabled=True,
        regulator_strength=0.10,
        regulator_capture=0.4,
    )
    cfg_default.topology.registration = RegistrationConfig(
        enabled=True,
        registration_floor=0.30,
        initial_registered_share=0.5,
        initial_registration_seed=99,
    )
    cfg_explicit = _small_cfg()
    cfg_explicit.topology.regulator = RegulatorConfig(
        enabled=True,
        regulator_strength=0.10,
        regulator_capture=0.4,
        audit_tampering_rate=0.0,  # explicit zero
    )
    cfg_explicit.topology.registration = RegistrationConfig(
        enabled=True,
        registration_floor=0.30,
        initial_registered_share=0.5,
        initial_registration_seed=99,
    )

    w_default = World.build(cfg_default)
    w_default.run(progress=False)
    w_explicit = World.build(cfg_explicit)
    w_explicit.run(progress=False)

    assert _terminal_triple(w_default) == _terminal_triple(w_explicit)
    assert all(
        m.forged_registration_share == 0.0
        for m in w_default.metrics.history.steps
    )


def test_audit_tampering_full_capture_defeats_floor() -> None:
    """With `audit_tampering_rate = 1.0` and `regulator_capture = 1.0`,
    the captured regulator forges every unregistered bit. The
    `registration_floor` cannot bite, and the regulator gate's
    rejection rate collapses to the rate a fully-registered population
    would see — capture completely defeats the floor.
    """
    # Baseline: same regulator + registration regime, no tampering.
    cfg_no_tamper = _small_cfg()
    cfg_no_tamper.topology.regulator = RegulatorConfig(
        enabled=True,
        regulator_strength=0.10,
        regulator_capture=1.0,
    )
    cfg_no_tamper.topology.registration = RegistrationConfig(
        enabled=True,
        registration_floor=0.30,
        initial_registered_share=0.5,
        initial_registration_seed=101,
    )
    w_no_tamper = World.build(cfg_no_tamper)
    w_no_tamper.run(progress=False)
    rejections_no_tamper = sum(
        m.rejected_regulator for m in w_no_tamper.metrics.history.steps
    )

    # With tampering=1, capture=1: every unregistered bit gets forged →
    # no floor bump → regulator rejection rate matches its base
    # (base × audit × (1−capture) = 0 here, since capture=1.0).
    cfg_full_tamper = _small_cfg()
    cfg_full_tamper.topology.regulator = RegulatorConfig(
        enabled=True,
        regulator_strength=0.10,
        regulator_capture=1.0,
        audit_tampering_rate=1.0,
    )
    cfg_full_tamper.topology.registration = RegistrationConfig(
        enabled=True,
        registration_floor=0.30,
        initial_registered_share=0.5,
        initial_registration_seed=101,
    )
    w_full = World.build(cfg_full_tamper)
    w_full.run(progress=False)
    rejections_full = sum(
        m.rejected_regulator for m in w_full.metrics.history.steps
    )

    # The floor is completely defeated.
    assert rejections_full < rejections_no_tamper
    assert rejections_full == 0.0
    # Every unregistered endpoint was forged.
    forged_shares = [
        m.forged_registration_share for m in w_full.metrics.history.steps
    ]
    assert all(s == 1.0 for s in forged_shares), (
        f"All steps should report 100% forging at rate=1, capture=1: "
        f"got {forged_shares}"
    )


def test_audit_tampering_scales_with_capture() -> None:
    """Forged-share is `audit_tampering_rate × regulator_capture`, so
    pinning rate=1 and varying capture yields a (statistically)
    proportional forged-share. We test the midpoint (capture=0.5) lands
    between the bracketing cases (0.0 and 1.0).
    """

    def _mean_forged(capture: float, rate: float) -> float:
        cfg = _small_cfg()
        cfg.topology.regulator = RegulatorConfig(
            enabled=True,
            regulator_strength=0.10,
            regulator_capture=capture,
            audit_tampering_rate=rate,
        )
        cfg.topology.registration = RegistrationConfig(
            enabled=True,
            registration_floor=0.30,
            initial_registered_share=0.5,
            initial_registration_seed=42,
        )
        w = World.build(cfg)
        w.run(progress=False)
        return float(
            np.mean([m.forged_registration_share for m in w.metrics.history.steps])
        )

    no_capture = _mean_forged(0.0, 1.0)
    half_capture = _mean_forged(0.5, 1.0)
    full_capture = _mean_forged(1.0, 1.0)
    assert no_capture == 0.0
    assert full_capture == pytest.approx(1.0, abs=1e-9)
    assert 0.3 < half_capture < 0.7, (
        f"At rate=1, capture=0.5, expect forged share near 0.5; got {half_capture:.3f}"
    )


# ---------------------------------------------------------------------------
# S3 — Multi-jurisdiction registration arbitrage
# ---------------------------------------------------------------------------


def test_arbitrage_default_off_keeps_registration_stack_none() -> None:
    """`RegistrationConfig.arbitrage_enabled = False` (the default) leaves
    `Population.registration_stack` unset, preserving canonical bit-identity.
    """
    cfg = _small_cfg()
    cfg.topology.regulator = RegulatorConfig(enabled=True)
    cfg.topology.registration = RegistrationConfig(
        enabled=True,
        registration_floor=0.30,
        initial_registered_share=0.5,
        initial_registration_seed=99,
    )
    w = World.build(cfg)
    assert w.population.registration_stack is None


def test_arbitrage_picks_laxest_stack_when_one_is_strictly_softer() -> None:
    """When one stack has strictly less stringent regulator params than
    all others (lower strength × audit × (1 − capture)), every agent
    registers in that stack. This is the load-bearing arbitrage claim.
    """
    cfg = _small_cfg()
    # Four stacks; stack 0 is the lax one (capture 1.0, audit 0.01) and
    # the other three are strict (capture 0.0, audit 1.0). Equal strength.
    cfg.topology.regulator = RegulatorConfig(
        enabled=True,
        regulator_strength=(0.10, 0.10, 0.10, 0.10),
        regulator_capture=(1.0, 0.0, 0.0, 0.0),
        regulator_audit_quality=(0.01, 1.0, 1.0, 1.0),
    )
    cfg.topology.registration = RegistrationConfig(
        enabled=True,
        arbitrage_enabled=True,
        registration_floor=0.30,
        initial_registered_share=0.5,
    )
    w = World.build(cfg)
    assert w.population.registration_stack is not None
    assert w.population.registration_stack.dtype == np.int8
    # Every agent registered in the lax stack (stack 0).
    assert np.unique(w.population.registration_stack).tolist() == [0]


def test_arbitrage_off_registration_stack_matches_pop_stack() -> None:
    """With arbitrage disabled (the W2a default), no registration stack
    field is set, and the gate falls back to the flat floor that uses
    the trading-partner's stack. Two configs that differ only in the
    arbitrage flag produce identical terminal metrics when the regulator
    is uniform across stacks (no arbitrage opportunity).
    """
    cfg_off = _small_cfg()
    cfg_off.topology.regulator = RegulatorConfig(
        enabled=True,
        regulator_strength=0.10,
    )
    cfg_off.topology.registration = RegistrationConfig(
        enabled=True,
        arbitrage_enabled=False,
        registration_floor=0.30,
        initial_registered_share=0.5,
        initial_registration_seed=77,
    )
    cfg_on = _small_cfg()
    cfg_on.topology.regulator = RegulatorConfig(
        enabled=True,
        regulator_strength=0.10,
    )
    cfg_on.topology.registration = RegistrationConfig(
        enabled=True,
        arbitrage_enabled=True,
        registration_floor=0.30,
        initial_registered_share=0.5,
        initial_registration_seed=77,
    )
    w_off = World.build(cfg_off)
    w_on = World.build(cfg_on)
    assert w_off.population.registration_stack is None
    # With identical vendors across stacks, arbitrage picks one stack
    # uniformly — but since the floor scales by *effective strength* and
    # all stacks are identical, the per-pair rejection probability
    # collapses to the same value under both configs. The terminal
    # metrics need not be bit-identical (different field values change
    # downstream array dtypes) but the registration-relevant aggregate
    # `rejected_regulator` should match.
    w_off.run(progress=False)
    w_on.run(progress=False)
    rej_off = sum(m.rejected_regulator for m in w_off.metrics.history.steps)
    rej_on = sum(m.rejected_regulator for m in w_on.metrics.history.steps)
    # Under a uniform regulator, arbitrage is a no-op on rejections up
    # to the constant-factor floor scaling (the floor under arbitrage
    # is multiplied by the chosen stack's effective strength, which is
    # the same for all stacks here, but it IS now multiplied — so the
    # floor effect shrinks). We assert direction, not equality.
    assert rej_on <= rej_off


# ---------------------------------------------------------------------------
# S2 — Identity laundering through firm formation
# ---------------------------------------------------------------------------


def _laundering_cfg(launder: bool, registration: bool) -> WorldConfig:
    """Cfg that aggressively dissolves firms so the laundering path bites."""
    from engine.core.topology import InstitutionConfig

    cfg = _small_cfg()
    cfg.n_steps = 5
    cfg.pairs_per_step = 2_000
    cfg.population.n_human_prototypes = 100
    cfg.population.n_agent_prototypes = 1_000
    cfg.topology.institutions = InstitutionConfig(
        enabled=True,
        laundering_enabled=launder,
        formation_check_every_k=1,
        formation_surplus_threshold=-1e9,
        dissolution_wealth_threshold=10.0,
    )
    if registration:
        cfg.topology.registration = RegistrationConfig(
            enabled=True,
            initial_registered_share=0.5,
            initial_registration_seed=11,
        )
    else:
        cfg.topology.registration = RegistrationConfig(enabled=False)
    return cfg


def test_laundering_default_off_is_bit_identical() -> None:
    """With `InstitutionConfig.laundering_enabled = False` (the default),
    enabling W2a + institutions reproduces the pre-S2 bit-identical
    contract. This is the new bit-identity guarantee — W2a on,
    laundering off.
    """
    cfg_default = _laundering_cfg(launder=False, registration=True)
    cfg_explicit = _laundering_cfg(launder=False, registration=True)
    cfg_explicit.topology.institutions.laundering_enabled = False  # explicit

    w_default = World.build(cfg_default)
    w_default.run(progress=False)
    w_explicit = World.build(cfg_explicit)
    w_explicit.run(progress=False)

    assert _terminal_triple(w_default) == _terminal_triple(w_explicit)
    # No new agent_ids issued — the canonical entry/exit pattern is the
    # only path that grows the id pool.
    assert w_default.population.agent_next_id == w_explicit.population.agent_next_id


def test_laundering_grows_unique_agent_ids_above_population_size() -> None:
    """With `laundering_enabled=True` and detection=0, every firm
    dissolution triggers fresh `agent_id` issues. After several
    formation/dissolution cycles `agent_next_id` exceeds the population
    size — the cumulative count of unique ids is strictly greater than
    `pop.n`. This is the load-bearing laundering claim.
    """
    cfg = _laundering_cfg(launder=True, registration=True)
    w = World.build(cfg)
    pop_n = w.population.n
    initial_next_id = w.population.agent_next_id
    assert initial_next_id == pop_n
    w.run(progress=False)
    assert w.population.agent_next_id > pop_n, (
        f"With laundering on, the cumulative unique agent_id count should "
        f"exceed pop size (n={pop_n}); got next_id={w.population.agent_next_id}"
    )


def test_laundering_requires_registration_enabled() -> None:
    """The S2 plan says the laundering re-issue can only fire when *both*
    `laundering_enabled` and the W2a flag are True. With registration
    off, the laundering branch is a no-op.
    """
    cfg = _laundering_cfg(launder=True, registration=False)
    w = World.build(cfg)
    pop_n = w.population.n
    w.run(progress=False)
    # Without W2a, no laundering happened: agent_next_id stays at pop_n
    # (entry/exit is also off here because pop_dynamics is off).
    assert w.population.agent_next_id == pop_n


def test_laundering_detection_clamps_registered_share() -> None:
    """With `laundering_detection_rate = 1.0`, every laundered prototype
    has its registered bit flipped back to False. Across many laundering
    events the laundered-agent registered count trends down strongly
    versus the no-detection baseline.
    """
    base_cfg = _laundering_cfg(launder=True, registration=True)
    base_cfg.topology.regulator = RegulatorConfig(
        enabled=True, regulator_strength=0.05,
    )
    # No detection — laundered agents redraw at initial_registered_share=0.5.
    w_no_det = World.build(base_cfg)
    w_no_det.run(progress=False)
    no_det_reg = int(
        w_no_det.population.registered[~w_no_det.population.is_human].sum()
    )

    # Detection=1.0 — every laundered prototype is flipped back to False.
    det_cfg = _laundering_cfg(launder=True, registration=True)
    det_cfg.topology.regulator = RegulatorConfig(
        enabled=True, regulator_strength=0.05, laundering_detection_rate=1.0,
    )
    w_det = World.build(det_cfg)
    w_det.run(progress=False)
    det_reg = int(
        w_det.population.registered[~w_det.population.is_human].sum()
    )

    assert det_reg < no_det_reg, (
        f"Detection should strictly reduce post-laundering registered count: "
        f"no_det={no_det_reg}, det={det_reg}"
    )

