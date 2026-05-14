"""ComputeConfig — compute / power admission filter.

Default-off (ComputeConfig.enabled = False or power_cost_per_trade = 0)
reproduces canonical baselines bit-identically. With the filter on,
pairs are admitted in descending `admit_score` order until the per-tick
budget runs out; remaining pairs land in `rejected_compute`.
"""
from __future__ import annotations

import numpy as np
import pytest

from engine.core.compute import admit_pairs, step_pool
from engine.core.population import Population, PopulationConfig
from engine.core.topology import ComputeConfig, TopologyConfig
from engine.core.world import World, WorldConfig


def _synth(seed: int = 5) -> Population:
    return Population.synthesize(
        PopulationConfig(n_human_prototypes=40, n_agent_prototypes=360, seed=seed)
    )


def test_admit_pairs_zero_cost_admits_all() -> None:
    pop = _synth()
    rng = np.random.default_rng(0)
    n = 100
    a = rng.integers(0, pop.n, size=n)
    b = rng.integers(0, pop.n, size=n)
    cfg = ComputeConfig(enabled=True, power_cost_per_trade=0.0)
    reject, debited = admit_pairs(
        cfg=cfg, pop=pop, a=a, b=b, rng=rng, available=10.0,
    )
    assert not reject.any()
    assert debited == 0.0


def test_admit_pairs_budget_caps_admissions() -> None:
    pop = _synth()
    rng = np.random.default_rng(1)
    n = 100
    a = rng.integers(0, pop.n, size=n)
    b = rng.integers(0, pop.n, size=n)
    cfg = ComputeConfig(
        enabled=True, power_cost_per_trade=0.01, distribution="uniform",
    )
    # budget of 0.305 → 30 admissions, 70 rejected (avoids 0.30/0.01
    # floor-division floating-point artifact landing at 29).
    reject, debited = admit_pairs(
        cfg=cfg, pop=pop, a=a, b=b, rng=rng, available=0.305,
    )
    n_admitted = int((~reject).sum())
    assert n_admitted == 30
    assert debited == pytest.approx(0.30, abs=1e-9)


@pytest.mark.parametrize(
    "distribution,attr",
    [
        ("wealth_weighted", "wealth"),
        ("capability_weighted", "capability"),
        ("autonomy_weighted", "autonomy"),
    ],
)
def test_admit_pairs_attribute_weighted_picks_high_score_pairs(
    distribution: str, attr: str,
) -> None:
    pop = _synth(seed=11)
    rng = np.random.default_rng(7)
    n = 200
    a = rng.integers(0, pop.n, size=n)
    b = rng.integers(0, pop.n, size=n)
    cfg = ComputeConfig(
        enabled=True, power_cost_per_trade=0.01, distribution=distribution,
    )
    # admit half
    reject, _ = admit_pairs(
        cfg=cfg, pop=pop, a=a, b=b, rng=rng, available=1.0,
    )
    attr_arr = getattr(pop, attr)
    scores = np.maximum(attr_arr[a], attr_arr[b]).astype(np.float64)
    median_admitted = np.median(scores[~reject])
    median_rejected = np.median(scores[reject])
    assert median_admitted >= median_rejected, (
        f"admitted should skew toward high {attr}; got "
        f"admit median={median_admitted} reject median={median_rejected}"
    )


def test_admit_pairs_unknown_distribution_raises() -> None:
    pop = _synth()
    rng = np.random.default_rng(0)
    a = np.array([0, 1, 2])
    b = np.array([3, 4, 5])
    cfg = ComputeConfig(
        enabled=True, power_cost_per_trade=0.01, distribution="popularity_contest",
    )
    with pytest.raises(ValueError, match="ComputeConfig.distribution"):
        admit_pairs(cfg=cfg, pop=pop, a=a, b=b, rng=rng, available=1.0)


def test_step_pool_carryover_is_pool_recovery_times_residual() -> None:
    cfg = ComputeConfig(
        enabled=True, budget_per_tick=1.0,
        power_cost_per_trade=0.01, pool_recovery=0.5,
    )
    # debit 0.4 from 1.0 budget → residual 0.6 → carryover 0.3
    available, residual, pool_after = step_pool(
        cfg=cfg, pool_before=0.0, debited=0.4,
    )
    assert available == pytest.approx(1.0)
    assert residual == pytest.approx(0.6)
    assert pool_after == pytest.approx(0.3)


def test_step_pool_scarcity_floor_clamps_available() -> None:
    cfg = ComputeConfig(
        enabled=True, budget_per_tick=0.1, scarcity_floor=0.5,
        power_cost_per_trade=0.01, pool_recovery=0.0,
    )
    available, _, pool_after = step_pool(
        cfg=cfg, pool_before=0.0, debited=0.0,
    )
    assert available == pytest.approx(0.5)
    # zero pool_recovery → next-tick pool is 0
    assert pool_after == 0.0


def test_step_pool_zero_recovery_drops_carryover() -> None:
    cfg = ComputeConfig(
        enabled=True, budget_per_tick=1.0,
        power_cost_per_trade=0.01, pool_recovery=0.0,
    )
    _, _, pool_after = step_pool(cfg=cfg, pool_before=0.0, debited=0.0)
    assert pool_after == 0.0


def test_world_default_off_surfaces_zero_compute_metrics() -> None:
    """With ComputeConfig.enabled=False the cascade is bit-identical."""
    cfg = WorldConfig(
        population=PopulationConfig(
            n_human_prototypes=30, n_agent_prototypes=270, seed=23,
        ),
        topology=TopologyConfig(alpha=0.5),
        n_steps=3,
        pairs_per_step=4_000,
        seed=23,
    )
    w = World.build(cfg)
    metrics = [w.step() for _ in range(cfg.n_steps)]
    for m in metrics:
        assert m.rejected_compute == 0.0
        assert m.compute_budget_remaining == 0.0


def test_world_on_produces_compute_rejections_and_pool_carryover() -> None:
    """Enable ComputeConfig with a tight budget; expect compute rejects + pool state."""
    cfg = WorldConfig(
        population=PopulationConfig(
            n_human_prototypes=30, n_agent_prototypes=270, seed=29,
        ),
        topology=TopologyConfig(
            alpha=0.5,
            compute=ComputeConfig(
                enabled=True,
                budget_per_tick=1.0,
                power_cost_per_trade=0.001,
                distribution="uniform",
                pool_recovery=0.5,
            ),
        ),
        n_steps=3,
        pairs_per_step=4_000,
        seed=29,
    )
    w = World.build(cfg)
    metrics = [w.step() for _ in range(cfg.n_steps)]
    total_compute_rejects = sum(m.rejected_compute for m in metrics)
    assert total_compute_rejects > 0.0, "expected compute rejections with budget=1.0 cost=0.001"
    # Pool carryover should be positive after at least one step (budget
    # is 1.0, cost is 0.001 × n_admitted < 1.0, residual > 0, recovery 0.5).
    assert any(m.compute_budget_remaining > 0.0 for m in metrics)
