"""Norm-evolution alignment-layer rejection.

Companion test for `docs/plans/norm_evolution_alignment.md`. Pins the
contract that turns "static distance" into "tracked moving target":

* `enabled = False` (default) reproduces the canonical pre-Round-1
  alignment gate bit-for-bit. Plan 1's `test_regression_canonical.py`
  is the system-level pin; this file pins the per-step path.
* `enabled = True, eta = 0` keeps the norm pinned at `initial_norm`. The
  binding becomes a constant offset rather than a pairwise distance, so
  metrics differ from the legacy run — but they reproduce themselves
  bit-identically across two builds, which is the regression we care
  about for the eta=0 corner.
* The norm tracks the alignment-weighted mean of *executed* trades over
  the lag window. Convergence direction is the contract; the exact rate
  is implementation detail.
* Translation invariance breaks. The plan-stated failure mode of the
  static-distance gate is that shifting every prototype's alignment by a
  constant doesn't change the rejection rate. Under norm evolution the
  shift moves the whole population away from the (still-stale)
  `initial_norm`, so rejections rise until the norm catches up.
* With `registration_coverage=0`, observations carry no weight (no
  registered participants), the norm stays pinned at `initial_norm`
  forever, and `community_norm_drift` is exactly zero across the run.
"""

from __future__ import annotations

import numpy as np

from engine.core.world import World
from engine.scenarios import get_scenario


def _small_cfg(
    *,
    enabled: bool,
    eta: float = 0.05,
    initial_norm: float = 0.0,
    coverage: float = 0.5,
    seed: int = 17,
) -> "WorldConfig":
    cfg = get_scenario("equilibrium_drift")
    cfg.n_steps = 8
    cfg.pairs_per_step = 4_000
    cfg.population.n_human_prototypes = 200
    cfg.population.n_agent_prototypes = 1_000
    cfg.population.registration_coverage = coverage
    cfg.population.norm.enabled = enabled
    cfg.population.norm.norm_update_eta = eta
    cfg.population.norm.norm_lag_steps = 2
    cfg.population.norm.initial_norm = initial_norm
    cfg.population.seed = seed
    cfg.seed = seed + 1
    return cfg


def _terminal_metric(world: World, name: str) -> float:
    return float(getattr(world.metrics.history.steps[-1], name))


def test_norm_disabled_reproduces_canonical() -> None:
    """Default config (norm.enabled=False) is the bit-for-bit canonical
    path. Two builds with the same seed produce identical terminal
    triples. Cross-checked at the system level by
    `test_regression_canonical.py`; this test is a focused per-step
    sanity check that the norm-disabled branch never reads any norm-side
    state.
    """
    a = World.build(_small_cfg(enabled=False, coverage=0.0))
    b = World.build(_small_cfg(enabled=False, coverage=0.0))
    a.run(progress=False)
    b.run(progress=False)
    for ma, mb in zip(a.metrics.history.steps, b.metrics.history.steps):
        assert ma.exo_baroque_index == mb.exo_baroque_index
        assert ma.community_norm_drift == 0.0
        assert ma.align_reject_share_under_norm == 0.0


def test_eta_zero_keeps_norm_pinned() -> None:
    """`enabled=True, eta=0` is the pinned-norm regime. The binding is
    a constant deviation `|al - initial_norm|`; the norm itself never
    moves, so `community_norm_drift` stays at zero and the per-build
    determinism still holds.
    """
    a = World.build(_small_cfg(enabled=True, eta=0.0, initial_norm=0.0))
    b = World.build(_small_cfg(enabled=True, eta=0.0, initial_norm=0.0))
    a.run(progress=False)
    b.run(progress=False)
    for ma, mb in zip(a.metrics.history.steps, b.metrics.history.steps):
        assert ma.exo_baroque_index == mb.exo_baroque_index
        assert ma.community_norm_drift == 0.0


def test_norm_drifts_under_positive_eta() -> None:
    """With eta > 0, the community norm walks away from `initial_norm`
    in the direction of the alignment-weighted observed mean. The
    direction depends on the population's actual alignment distribution;
    this test only asserts that *some* drift accumulates (the magnitude
    is implementation detail).
    """
    cfg = _small_cfg(enabled=True, eta=0.20, initial_norm=0.5, coverage=1.0)
    world = World.build(cfg)
    world.run(progress=False)
    drifts = [m.community_norm_drift for m in world.metrics.history.steps]
    # Final drift should be strictly larger than the first non-zero
    # observation step's drift — the lag buffer pre-loads with
    # `initial_norm`, so step 0 reports 0 while step 1 starts to move.
    assert drifts[-1] > 0.0
    assert drifts[-1] >= drifts[1]


def test_translation_breaks_static_invariance() -> None:
    """The static-distance gate is translation invariant: shift every
    prototype's alignment by +0.5 and `align_dist` is unchanged. The
    norm-evolution gate is not — the shift moves the population away
    from the (initial) norm, so the alignment-rejection share rises
    until the norm catches up. This pins the *direction* of the
    Hadfield-aligned correction.

    The check is on alignment-rejection share averaged over the run, to
    average out per-step noise on small populations.
    """
    cfg_static = _small_cfg(enabled=False, coverage=1.0)
    static_world = World.build(cfg_static)
    # Apply the shift after build, before run.
    static_world.population.alignment = np.clip(
        static_world.population.alignment + np.float32(0.5),
        np.float32(-1.0),
        np.float32(1.0),
    )
    static_world.run(progress=False)

    cfg_norm = _small_cfg(enabled=True, eta=0.05, coverage=1.0)
    norm_world = World.build(cfg_norm)
    norm_world.population.alignment = np.clip(
        norm_world.population.alignment + np.float32(0.5),
        np.float32(-1.0),
        np.float32(1.0),
    )
    norm_world.run(progress=False)

    static_align = float(np.mean(
        [m.rejected_align for m in static_world.metrics.history.steps]
    ))
    norm_align = float(np.mean(
        [m.rejected_align for m in norm_world.metrics.history.steps]
    ))
    assert norm_align > static_align


def test_zero_coverage_freezes_norm() -> None:
    """With registration_coverage=0, no observations are weighted in,
    so `community_norm` stays at `initial_norm` across the run. Pins
    plan 3's stated requirement that norm evolution depends on plan 2's
    registration regime to do real work.
    """
    cfg = _small_cfg(enabled=True, eta=0.30, initial_norm=0.25, coverage=0.0)
    world = World.build(cfg)
    world.run(progress=False)
    drifts = [m.community_norm_drift for m in world.metrics.history.steps]
    assert max(drifts) == 0.0
