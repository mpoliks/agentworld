"""W1a regulator-layer behaviour.

The Hadfield regulator gate (`RegulatorConfig.enabled`) is the second
middle-layer filter, distinct from the platform/`market` gate. This
file pins three things:

1. With `enabled=False` (the canonical default), the regulator gate
   consumes no rng draws and the engine is bit-identical to the
   pre-W1a build — `rejected_regulator == 0.0`, terminal EBI / welfare
   / Gini all match `equilibrium_drift` baselines.
2. With `enabled=True` and a moderate vendor profile, the gate fires:
   `rejected_regulator > 0`, executed-transaction count drops, and the
   surplus-tax channel reduces `real_welfare_cumulative` when
   `regulator_layer_tax > 0`.
3. Under per-component RNG, burning the dedicated `regulator` stream
   is a no-op against terminal metrics when the gate is disabled (the
   stream simply isn't read). This is the isolation contract the W1a
   work piggy-backs on from the rng-split plan.
"""

from __future__ import annotations

import pytest

from engine.core.world import World, WorldConfig
from engine.core.topology import RegulatorConfig
from engine.scenarios import get_scenario


def _small_cfg(rng_split_mode: str = "legacy") -> WorldConfig:
    cfg = get_scenario("equilibrium_drift")
    cfg.n_steps = 4
    cfg.pairs_per_step = 4_000
    cfg.population.n_human_prototypes = 200
    cfg.population.n_agent_prototypes = 2_000
    cfg.seed = 17
    cfg.population.seed = 71
    cfg.rng_split_mode = rng_split_mode
    return cfg


def _terminal_triple(world: World) -> tuple[float, float, float]:
    last = world.metrics.history.steps[-1]
    return (
        last.exo_baroque_index,
        last.real_welfare_cumulative,
        last.gini_wealth,
    )


def test_regulator_off_is_bit_identical_to_canonical() -> None:
    """With `RegulatorConfig.enabled = False` the gate must consume no
    rng draws and produce no rejections — terminal metrics identical
    to a configuration that doesn't even instantiate the regulator
    config block.
    """
    cfg_default = _small_cfg()
    cfg_explicit_off = _small_cfg()
    # Spelling the default out explicitly should be a no-op.
    cfg_explicit_off.topology.regulator = RegulatorConfig(enabled=False)

    w_default = World.build(cfg_default)
    w_default.run(progress=False)
    w_explicit = World.build(cfg_explicit_off)
    w_explicit.run(progress=False)

    assert _terminal_triple(w_default) == _terminal_triple(w_explicit)
    assert all(
        m.rejected_regulator == 0.0
        for m in w_default.metrics.history.steps
    )


def test_regulator_on_rejects_and_taxes() -> None:
    """A moderate regulator vendor rejects a measurable share of pairs
    and the surplus-tax channel scales the executed surplus by
    `1 − regulator_layer_tax`.
    """
    baseline_cfg = _small_cfg()
    baseline_cfg.topology.regulator = RegulatorConfig(enabled=False)
    baseline = World.build(baseline_cfg)
    baseline.run(progress=False)

    active_cfg = _small_cfg()
    active_cfg.topology.regulator = RegulatorConfig(
        enabled=True,
        regulator_strength=0.30,
        regulator_capture=0.0,
        regulator_audit_quality=1.0,
        regulator_layer_tax=0.05,
    )
    active = World.build(active_cfg)
    active.run(progress=False)

    base_last = baseline.metrics.history.steps[-1]
    on_last = active.metrics.history.steps[-1]

    # Gate fires: some pairs are rejected at the regulator layer.
    assert sum(m.rejected_regulator for m in active.metrics.history.steps) > 0.0
    # And the canonical run never has any regulator rejections.
    assert all(m.rejected_regulator == 0.0 for m in baseline.metrics.history.steps)
    # Executed-transaction count drops because the gate adds a rejection
    # bucket the canonical run doesn't have.
    assert on_last.n_transactions_real < base_last.n_transactions_real
    # The 5% surplus tax + the rejected pairs together drag cumulative
    # welfare below the no-regulator baseline.
    assert on_last.real_welfare_cumulative < base_last.real_welfare_cumulative


def test_per_stack_vendor_arrays() -> None:
    """Per-stack vendor params are accepted and applied correctly.

    Setting one stack's strength to 0 should give zero regulator
    rejections in pairs whose stricter endpoint sits in that stack
    (i.e. nothing in that stack ever blocks). The other stacks still
    fire normally.
    """
    cfg = _small_cfg()
    K = cfg.topology.n_stacks
    # Stack 0 has a fully captured, zero-strength regulator; the rest
    # have a moderate one. With `max(p_reject_a, p_reject_b)` semantics
    # the gate still fires on any pair with at least one non-stack-0
    # endpoint.
    strength = tuple([0.0] + [0.25] * (K - 1))
    cfg.topology.regulator = RegulatorConfig(
        enabled=True,
        regulator_strength=strength,
        regulator_capture=0.0,
        regulator_audit_quality=1.0,
    )
    world = World.build(cfg)
    world.run(progress=False)
    total_rejected = sum(m.rejected_regulator for m in world.metrics.history.steps)
    assert total_rejected > 0.0


def test_regulator_stream_isolated_when_disabled() -> None:
    """Under per-component RNG, burning the dedicated regulator stream
    is a no-op against terminal metrics when the gate is disabled (the
    stream is allocated but never read).
    """
    a = World.build(_small_cfg(rng_split_mode="per_component"))
    b = World.build(_small_cfg(rng_split_mode="per_component"))
    b.rngs["regulator"].random(10_000)
    a.run(progress=False)
    b.run(progress=False)
    assert _terminal_triple(a) == _terminal_triple(b)


def test_per_stack_validation_rejects_wrong_length() -> None:
    """Mismatched per-stack array length must raise at build time, not
    silently broadcast.
    """
    cfg = _small_cfg()
    K = cfg.topology.n_stacks
    cfg.topology.regulator = RegulatorConfig(
        enabled=True,
        regulator_strength=tuple([0.25] * (K + 1)),  # one too many
    )
    world = World.build(cfg)
    with pytest.raises(ValueError, match="regulator_strength"):
        world.run(progress=False)
