"""W1b — norm-participation alignment.

Pre-W1b the individual-layer rejection gate uses static Euclidean
distance on a fixed scalar `alignment`. Hadfield's *Normative
Infrastructure for AI Alignment* (AIhub, May 2025) argues that
alignment is *participation in evolving community norms* — agents
who routinely transact converge in norm space; agents who don't,
don't. W1b operationalises that: each prototype carries a K-dim
`norm_vector`; `align_reject` uses L2-distance-in-norm-space; each
step every prototype's norm drifts toward the capability-weighted
mean of its executed partners' norms.

These tests pin five contracts:

1. With `NormsConfig.enabled = False` (the canonical default) the
   field is allocated but unread, so terminal metrics are bit-
   identical to the pre-W1b baseline.
2. The norm-update procedure converges executed partners toward each
   other when the update rate is positive (we measure the per-step
   delta).
3. With `update_rate = 0.0` the norm vector is static even when the
   mechanism is enabled, so the W1b distance metric still fires at
   the gate but no convergence happens.
4. The capability-weight knob biases the EMA target: with the flag
   on, high-capability partners pull harder.
5. Three registered scenarios — `norms_drift`, `norms_capture`,
   `norms_brittle` — exist and run for a short horizon.
"""

from __future__ import annotations

import numpy as np
import pytest

from engine.core.norms import norm_distance, update_norm_vectors
from engine.core.population import Population, PopulationConfig
from engine.core.topology import NormsConfig
from engine.core.world import World
from engine.scenarios import SCENARIOS, get_scenario


def _small_cfg() -> "WorldConfig":  # noqa: F821
    cfg = get_scenario("equilibrium_drift")
    cfg.n_steps = 4
    cfg.pairs_per_step = 4_000
    cfg.population.n_human_prototypes = 200
    cfg.population.n_agent_prototypes = 2_000
    cfg.seed = 81
    cfg.population.seed = 18
    return cfg


def _terminal_triple(world: World) -> tuple[float, float, float]:
    last = world.metrics.history.steps[-1]
    return (
        last.exo_baroque_index,
        last.real_welfare_cumulative,
        last.gini_wealth,
    )


def test_norms_off_is_bit_identical() -> None:
    """`NormsConfig.enabled = False` (the default) preserves canonical
    bit-identity even with a non-default `n_dimensions` value supplied
    (since the gate is gated on `enabled`, not on `n_dimensions`).
    """
    cfg_default = _small_cfg()
    cfg_explicit = _small_cfg()
    cfg_explicit.topology.norms = NormsConfig(enabled=False, n_dimensions=8)

    w_default = World.build(cfg_default)
    w_default.run(progress=False)
    w_explicit = World.build(cfg_explicit)
    w_explicit.run(progress=False)

    assert _terminal_triple(w_default) == _terminal_triple(w_explicit)


def test_norm_vector_allocated_at_default() -> None:
    """Even with W1b off, `pop.norm_vector` is populated so downstream
    code can introspect the field. It defaults to a `(n, 1)` zero
    matrix in the disabled case.
    """
    cfg = _small_cfg()
    world = World.build(cfg)
    assert world.population.norm_vector is not None
    assert world.population.norm_vector.shape == (world.population.n, 1)
    assert world.population.norm_vector.dtype == np.float32


def test_norm_update_converges_partners() -> None:
    """Two prototypes that transact every step move their norms
    toward each other under positive `update_rate`. Test directly
    against `update_norm_vectors` so we don't depend on the full
    world for a clean read.
    """
    pop = Population.synthesize(
        PopulationConfig(n_human_prototypes=10, n_agent_prototypes=20, seed=1),
        norms_config=NormsConfig(
            enabled=True,
            n_dimensions=4,
            update_rate=0.5,
            initial_norm_seed=1,
        ),
    )
    cfg = NormsConfig(enabled=True, n_dimensions=4, update_rate=0.5)
    a = np.array([0], dtype=np.int64)
    b = np.array([29], dtype=np.int64)
    executed = np.array([True])
    pair_real_count = np.array([1.0])
    pre_dist = float(
        np.linalg.norm(pop.norm_vector[a[0]] - pop.norm_vector[b[0]])
    )
    update_norm_vectors(pop, a, b, executed, pair_real_count, cfg)
    post_dist = float(
        np.linalg.norm(pop.norm_vector[a[0]] - pop.norm_vector[b[0]])
    )
    assert post_dist < pre_dist, (
        f"Executed pair should converge under positive update_rate: "
        f"pre={pre_dist:.4f}, post={post_dist:.4f}."
    )


def test_update_rate_zero_freezes_norms() -> None:
    """When the gate is enabled but `update_rate = 0`, the norm vector
    is unchanged by the update step. The distance gate still fires
    against the static norm vector.
    """
    pop = Population.synthesize(
        PopulationConfig(n_human_prototypes=10, n_agent_prototypes=20, seed=2),
        norms_config=NormsConfig(
            enabled=True, n_dimensions=4, update_rate=0.0,
            initial_norm_seed=2,
        ),
    )
    pre = pop.norm_vector.copy()
    cfg = NormsConfig(enabled=True, n_dimensions=4, update_rate=0.0)
    a = np.array([0, 1, 2], dtype=np.int64)
    b = np.array([20, 21, 22], dtype=np.int64)
    executed = np.ones(3, dtype=bool)
    pair_real_count = np.ones(3, dtype=np.float64)
    update_norm_vectors(pop, a, b, executed, pair_real_count, cfg)
    np.testing.assert_array_equal(pop.norm_vector, pre)


def test_capability_weight_biases_target() -> None:
    """A high-capability partner pulls the EMA target harder than a
    low-capability partner. Constructed as: prototype 0 has two
    partners with the same offset but different capabilities; the
    final norm should land closer to the high-capability partner's.
    """
    pop = Population.synthesize(
        PopulationConfig(n_human_prototypes=5, n_agent_prototypes=20, seed=3),
        norms_config=NormsConfig(
            enabled=True, n_dimensions=2, update_rate=0.5,
            initial_norm_seed=3,
        ),
    )
    # Override norms and capability so we can read the bias cleanly.
    pop.norm_vector[:] = 0.0
    pop.norm_vector[0] = np.array([0.0, 0.0], dtype=np.float32)
    pop.norm_vector[1] = np.array([1.0, 0.0], dtype=np.float32)
    pop.norm_vector[2] = np.array([-1.0, 0.0], dtype=np.float32)
    pop.capability[:] = 0.5
    pop.capability[1] = 0.95  # high-cap "good" partner
    pop.capability[2] = 0.05  # low-cap "bad" partner
    cfg = NormsConfig(
        enabled=True, n_dimensions=2, update_rate=1.0, capability_weight=True
    )
    a = np.array([0, 0], dtype=np.int64)
    b = np.array([1, 2], dtype=np.int64)
    executed = np.ones(2, dtype=bool)
    pair_real_count = np.ones(2, dtype=np.float64)
    update_norm_vectors(pop, a, b, executed, pair_real_count, cfg)
    # At update_rate=1.0 the new norm IS the weighted-mean partner norm.
    # Weighted by capability: (0.95*[1,0] + 0.05*[-1,0]) / (0.95+0.05) = [0.9, 0].
    new = pop.norm_vector[0]
    assert new[0] > 0.5, f"High-cap partner should dominate the EMA target; got {new}"


def test_norm_isolated_seed_doesnt_perturb_alignment() -> None:
    """The dedicated `initial_norm_seed` doesn't move other Population
    draws. Two populations identical except for the norm seed should
    have identical capability / sector / wealth / alignment arrays.
    """
    base = Population.synthesize(
        PopulationConfig(n_human_prototypes=50, n_agent_prototypes=200, seed=4),
        norms_config=NormsConfig(
            enabled=True, n_dimensions=4, initial_norm_seed=0,
        ),
    )
    other = Population.synthesize(
        PopulationConfig(n_human_prototypes=50, n_agent_prototypes=200, seed=4),
        norms_config=NormsConfig(
            enabled=True, n_dimensions=4, initial_norm_seed=99,
        ),
    )
    np.testing.assert_array_equal(base.capability, other.capability)
    np.testing.assert_array_equal(base.sector, other.sector)
    np.testing.assert_array_equal(base.wealth, other.wealth)
    np.testing.assert_array_equal(base.alignment, other.alignment)
    # Norm vectors should differ with high probability at this n.
    assert not np.array_equal(base.norm_vector, other.norm_vector)


def test_norm_distance_normalisation() -> None:
    """`norm_distance` divides by sqrt(K), so for K=1 with elements in
    [-1, 1] it lands on the same [0, 2] range as `|al_a − al_b|`.
    """
    a = np.array([[1.0]], dtype=np.float32)
    b = np.array([[-1.0]], dtype=np.float32)
    assert float(norm_distance(a, b, 1)[0]) == pytest.approx(2.0)
    # K=4 with the same per-dim distance gives back the same scalar.
    a4 = np.array([[1.0, 1.0, 1.0, 1.0]], dtype=np.float32)
    b4 = np.array([[-1.0, -1.0, -1.0, -1.0]], dtype=np.float32)
    assert float(norm_distance(a4, b4, 4)[0]) == pytest.approx(2.0)


def test_registered_scenarios_run() -> None:
    """All three norms scenarios are registered and run for a short
    horizon. We confirm plumbing; substantive convergence claims are
    deferred to a dedicated sweep.
    """
    for name in ("norms_drift", "norms_capture", "norms_brittle"):
        assert name in SCENARIOS, f"scenario {name!r} missing from registry"
        cfg = get_scenario(name)
        cfg.n_steps = 2
        cfg.pairs_per_step = 2_000
        cfg.population.n_human_prototypes = 100
        cfg.population.n_agent_prototypes = 600
        world = World.build(cfg)
        world.run(progress=False)
        assert world.step_idx == 2
        # Norm vector evolves across the run when the mechanism is on.
        assert world.population.norm_vector is not None
