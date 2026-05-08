"""Persistent agent registration — coverage, identity, audit accumulation.

Companion test for `docs/plans/registration_regime.md`. Pins four
contracts:

* `registration_coverage = 0.0` (the back-compat default) leaves audit
  counters at zero and `registered_active_share` at exactly 0.0 forever.
  Existing canonical pins reproduce because no audit-trail update is
  triggered (`prototype_id` is uniformly -1 and the per-step scatter-add
  is a noop).
* `registration_coverage = 1.0` registers every agent prototype but
  never a human. Plan 4's regulator depends on this invariant — it must
  not be able to audit a human.
* Audit counters increment monotonically. Plan 4's defect score is
  `rejections / (rejections + acceptances)` and would diverge if the
  counters could decrement.
* `registered_active_share` rises with coverage. The dashboard surfaces
  this as a header chip on registration-on scenarios.
"""

from __future__ import annotations

import numpy as np

from engine.core.population import Population, PopulationConfig
from engine.core.world import World
from engine.scenarios import get_scenario


def _small_cfg(coverage: float, seed: int = 11) -> "WorldConfig":
    cfg = get_scenario("equilibrium_drift")
    cfg.n_steps = 4
    cfg.pairs_per_step = 4_000
    cfg.population.n_human_prototypes = 200
    cfg.population.n_agent_prototypes = 1_000
    cfg.population.registration_coverage = coverage
    cfg.population.seed = seed
    cfg.seed = seed + 1
    return cfg


def test_coverage_zero_leaves_audit_at_zero() -> None:
    cfg = _small_cfg(coverage=0.0)
    world = World.build(cfg)
    pop = world.population
    assert (pop.prototype_id == -1).all()
    world.run(progress=False)
    # No registered prototypes => no audit trail movement, regardless of
    # how many trades were rejected or executed.
    assert pop.audit_acceptances.sum() == 0
    assert pop.audit_rejections.sum() == 0
    for m in world.metrics.history.steps:
        assert m.registered_active_share == 0.0


def test_coverage_one_registers_every_agent_only() -> None:
    cfg = _small_cfg(coverage=1.0)
    world = World.build(cfg)
    pop = world.population
    # Every agent gets a non-negative compact id; humans stay at -1.
    assert (pop.prototype_id[pop.is_human] == -1).all()
    assert (pop.prototype_id[~pop.is_human] >= 0).all()
    # Compact assignment in [0, n_agents).
    assigned = pop.prototype_id[~pop.is_human]
    assert assigned.min() == 0
    assert assigned.max() == assigned.size - 1


def test_audit_counters_only_grow() -> None:
    cfg = _small_cfg(coverage=0.5)
    world = World.build(cfg)
    pop = world.population
    accept_prev = pop.audit_acceptances.copy()
    reject_prev = pop.audit_rejections.copy()
    for _ in range(cfg.n_steps):
        world.step()
        assert (pop.audit_acceptances >= accept_prev).all()
        assert (pop.audit_rejections >= reject_prev).all()
        accept_prev = pop.audit_acceptances.copy()
        reject_prev = pop.audit_rejections.copy()


def test_registered_active_share_rises_with_coverage() -> None:
    """Coverage is monotonic in the share of executed flow that is
    audit-eligible. Not bit-exact (the seed sequence differs) but the
    direction is contractual.
    """
    shares: list[float] = []
    for cov in (0.0, 0.3, 1.0):
        cfg = _small_cfg(coverage=cov)
        world = World.build(cfg)
        world.run(progress=False)
        # Average over the last two steps so a one-step outlier doesn't
        # flip the comparison on small-population test scaffolding.
        last_two = world.metrics.history.steps[-2:]
        shares.append(float(np.mean([m.registered_active_share for m in last_two])))
    assert shares[0] == 0.0
    assert shares[1] > shares[0]
    assert shares[2] > shares[1]


def test_synthesize_keeps_humans_unregistered() -> None:
    """Independent of `coverage`, the synthesizer must never assign a
    non-negative id to a human row. Plan 4's regulator's correctness
    rests on this. Pinned at coverage=1.0 because that's the worst-case
    branch for any logic bug that mistakenly registers humans.
    """
    pop = Population.synthesize(
        PopulationConfig(
            n_human_prototypes=64,
            n_agent_prototypes=64,
            registration_coverage=1.0,
            seed=7,
        )
    )
    assert (pop.prototype_id[pop.is_human] == -1).all()
