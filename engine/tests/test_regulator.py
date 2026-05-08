"""Hadfield-style licensed-regulator audit gate.

Companion test for `docs/plans/regulator_market_split.md`. Pins the
contract that distinguishes Krier's platform/deployer compatibility
gate (always on) from Hadfield's licensed-regulator audit (opt-in,
keyed off the registration audit trail):

* `RegulatorConfig.enabled = False` — the regulator slice of the
  market-layer rejection share is exactly 0.0, and the platform slice
  matches the legacy `rejected_market` share. Ensures the canonical
  pinned baselines see no movement.
* `regulator.coverage` is bounded above by
  `PopulationConfig.registration_coverage`. A regulator cannot audit a
  prototype it cannot identify. Pinned at the runtime configuration
  level rather than warning-only because Hadfield's argument is that
  the bound is structural, not a sanity check.
* High `audit_quality` blocks high-defect prototypes preferentially.
  Construct a population where every registered prototype has a high
  rejection history; with `audit_quality=1.0, coverage=1.0`, the
  regulator share should rise above the legacy market share.
* The regulator layer cannot affect unregistered prototypes — their
  defect score is zero by construction, so the rejection probability
  collapses to `base_reject_rate`.
"""

from __future__ import annotations

import numpy as np

from engine.core.world import World
from engine.scenarios import get_scenario


def _cfg(
    *,
    coverage: float,
    audit_quality: float,
    enabled: bool = True,
    registration_coverage: float = 0.7,
    seed: int = 23,
) -> "WorldConfig":
    cfg = get_scenario("equilibrium_drift")
    cfg.n_steps = 5
    cfg.pairs_per_step = 4_000
    cfg.population.n_human_prototypes = 200
    cfg.population.n_agent_prototypes = 1_000
    cfg.population.registration_coverage = registration_coverage
    cfg.topology.regulator.enabled = enabled
    cfg.topology.regulator.coverage = coverage
    cfg.topology.regulator.audit_quality = audit_quality
    cfg.population.seed = seed
    cfg.seed = seed + 1
    return cfg


def test_regulator_disabled_zeros_regulator_share() -> None:
    """With the regulator gate off, only the platform share moves —
    `regulator_reject_share` is exactly zero across the run."""
    cfg = _cfg(coverage=0.5, audit_quality=0.5, enabled=False)
    world = World.build(cfg)
    world.run(progress=False)
    for m in world.metrics.history.steps:
        assert m.regulator_reject_share == 0.0


def test_platform_share_matches_legacy_market_when_regulator_off() -> None:
    """`platform_reject_share + regulator_reject_share` collapses to
    `rejected_market / total_attempts` (within float noise) when the
    regulator gate is off, because the platform slice is the only
    market-layer rejection in that mode.
    """
    cfg = _cfg(coverage=0.0, audit_quality=0.0, enabled=False)
    world = World.build(cfg)
    world.run(progress=False)
    for m in world.metrics.history.steps:
        attempts = (
            m.n_transactions_real + m.rejected_law + m.rejected_market
            + m.rejected_align + m.rejected_cost
        )
        if attempts <= 0:
            continue
        expected_market_share = m.rejected_market / attempts
        # Platform-only at this config; regulator share is zero.
        assert abs(
            (m.platform_reject_share + m.regulator_reject_share)
            - expected_market_share
        ) < 1e-9


def test_regulator_coverage_bounded_by_registration_coverage() -> None:
    """`regulator.coverage = 0.9` with `registration_coverage = 0.2`
    must not behave like full coverage. The regulator share at the
    capped-coverage config should be approximately equal to (rather
    than exceed) the share at `registration=0.2, coverage=0.2`.
    """
    cfg_capped = _cfg(
        coverage=0.9, audit_quality=0.5, registration_coverage=0.2,
    )
    world_capped = World.build(cfg_capped)
    world_capped.run(progress=False)

    cfg_matched = _cfg(
        coverage=0.2, audit_quality=0.5, registration_coverage=0.2,
    )
    world_matched = World.build(cfg_matched)
    world_matched.run(progress=False)

    capped_avg = float(np.mean(
        [m.regulator_reject_share for m in world_capped.metrics.history.steps]
    ))
    matched_avg = float(np.mean(
        [m.regulator_reject_share for m in world_matched.metrics.history.steps]
    ))
    # Capped should not exceed matched by more than noise.
    assert capped_avg <= matched_avg + 0.02


def test_regulator_blocks_high_defect_prototypes() -> None:
    """With every registered prototype synthetically marked as a
    rejection-heavy defector, raising `audit_quality` raises the
    regulator share. Pins the direction of the audit_quality lever.
    """
    cfg = _cfg(coverage=1.0, audit_quality=0.0, registration_coverage=1.0)
    world_low = World.build(cfg)
    # Pre-load defect history: every registered prototype has 9 prior
    # rejections and 1 acceptance. Defect score = 0.9 across the board.
    pop = world_low.population
    pop.audit_acceptances[~pop.is_human] = 1
    pop.audit_rejections[~pop.is_human] = 9
    world_low.run(progress=False)
    low_share = float(np.mean(
        [m.regulator_reject_share for m in world_low.metrics.history.steps]
    ))

    cfg2 = _cfg(coverage=1.0, audit_quality=0.9, registration_coverage=1.0)
    world_high = World.build(cfg2)
    pop2 = world_high.population
    pop2.audit_acceptances[~pop2.is_human] = 1
    pop2.audit_rejections[~pop2.is_human] = 9
    world_high.run(progress=False)
    high_share = float(np.mean(
        [m.regulator_reject_share for m in world_high.metrics.history.steps]
    ))

    assert high_share > low_share


def test_regulator_layer_does_not_affect_unregistered() -> None:
    """At `registration_coverage = 0`, the regulator gate sees only
    `defect_score = 0` everywhere, so its marginal contribution
    collapses to `base_reject_rate * coverage` — small and bounded.
    Pins the requirement that audit cannot reach the anonymous fraction
    of the population.
    """
    cfg = _cfg(
        coverage=1.0, audit_quality=1.0, registration_coverage=0.0,
    )
    world = World.build(cfg)
    world.run(progress=False)
    avg_reg = float(np.mean(
        [m.regulator_reject_share for m in world.metrics.history.steps]
    ))
    # Effective coverage clamped to 0 => regulator gate is a no-op.
    assert avg_reg == 0.0
