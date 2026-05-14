"""Schoenegger verifiable-semantics layer — `NormsConfig.certified_fraction`.

Default-off (0.0) leaves `pop.certified` as None and reproduces the
canonical baselines bit-identically. With the flag on the alignment
gate scales by `(1 − min(cert_a, cert_b))`; high cert collapses
alignment distance toward 0 and admits more pairs.
"""
from __future__ import annotations

import numpy as np

from engine.core.population import Population, PopulationConfig
from engine.core.topology import NormsConfig, TopologyConfig, InstitutionConfig
from engine.core.world import World, WorldConfig


def _synth(norms_config: NormsConfig | None = None, seed: int = 3) -> Population:
    return Population.synthesize(
        PopulationConfig(n_human_prototypes=40, n_agent_prototypes=360, seed=seed),
        norms_config=norms_config,
    )


def test_default_keeps_certified_none() -> None:
    pop = _synth(NormsConfig(enabled=True))
    assert pop.certified is None


def test_flag_on_draws_beta_certified_array() -> None:
    cfg = NormsConfig(enabled=True, certified_fraction=0.5, certified_fraction_sd=0.15)
    pop = _synth(cfg)
    assert pop.certified is not None
    assert pop.certified.shape == (pop.n,)
    assert pop.certified.dtype == np.float32
    assert pop.certified.min() >= 0.0
    assert pop.certified.max() <= 1.0
    assert abs(float(pop.certified.mean()) - 0.5) < 0.05


def test_certified_draw_reproducible_from_seed() -> None:
    cfg = NormsConfig(
        enabled=True, certified_fraction=0.4,
        certified_fraction_sd=0.2, initial_norm_seed=99,
    )
    pop_a = _synth(cfg, seed=7)
    pop_b = _synth(cfg, seed=7)
    np.testing.assert_array_equal(pop_a.certified, pop_b.certified)


def test_alignment_rejections_drop_with_high_certified_fraction() -> None:
    """High certified-fraction collapses align_dist → lower rejected_align."""
    def _run(cert_fraction: float) -> float:
        cfg = WorldConfig(
            population=PopulationConfig(
                n_human_prototypes=60, n_agent_prototypes=540, seed=13,
            ),
            topology=TopologyConfig(
                alpha=0.5,
                norms=NormsConfig(
                    enabled=True,
                    certified_fraction=cert_fraction,
                    certified_fraction_sd=0.05,  # tight cluster around mean
                    initial_norm_seed=13,
                ),
            ),
            n_steps=6,
            pairs_per_step=8_000,
            seed=13,
        )
        world = World.build(cfg)
        align_rejects = []
        for _ in range(cfg.n_steps):
            m = world.step()
            align_rejects.append(float(m.rejected_align))
        return float(np.mean(align_rejects))

    low_cert_rate = _run(0.05)
    high_cert_rate = _run(0.95)
    assert high_cert_rate < low_cert_rate, (
        f"expected high cert to reduce align_reject_rate; "
        f"got low={low_cert_rate:.4f} high={high_cert_rate:.4f}"
    )


def test_cast_snapshot_surfaces_certified() -> None:
    cfg = WorldConfig(
        population=PopulationConfig(
            n_human_prototypes=30, n_agent_prototypes=270, seed=21,
        ),
        topology=TopologyConfig(
            alpha=0.4,
            norms=NormsConfig(
                enabled=True,
                certified_fraction=0.5,
                certified_fraction_sd=0.15,
                initial_norm_seed=21,
            ),
        ),
        cast_size=8,
        n_steps=3,
        pairs_per_step=4_000,
        seed=21,
    )
    world = World.build(cfg)
    last = None
    for _ in range(cfg.n_steps):
        last = world.step()
    snap = (last.cast_snapshot if last is not None else None) or []
    assert snap
    pop = world.population
    for entry in snap:
        ii = entry["idx"]
        assert "certified" in entry
        assert abs(entry["certified"] - float(pop.certified[ii])) < 1e-6
        assert 0.0 <= entry["certified"] <= 1.0


def test_disabled_norms_keeps_certified_none_even_at_nonzero_fraction() -> None:
    """When norms_cfg.enabled is False, no Beta draw happens regardless of fraction."""
    cfg = NormsConfig(enabled=False, certified_fraction=0.7)
    pop = _synth(cfg)
    assert pop.certified is None
