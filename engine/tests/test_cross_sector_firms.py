"""Cross-sector firm formation — gated by `InstitutionConfig.cross_sector_firms`.

Default-off path preserves the (sector, stack) binning rule. Flag-on
path lets firms span sectors within a hemispherical stack; the cast
snapshot exposes the resulting sector composition under
`cast_snapshot[*].firm_sectors`.
"""
from __future__ import annotations

import numpy as np

from engine.core.institutions import formation_step
from engine.core.population import Population, PopulationConfig
from engine.core.topology import InstitutionConfig, TopologyConfig
from engine.core.world import World, WorldConfig


def _populate(seed: int = 1, n_human: int = 30, n_agent: int = 270) -> Population:
    return Population.synthesize(
        PopulationConfig(
            n_human_prototypes=n_human,
            n_agent_prototypes=n_agent,
            seed=seed,
        )
    )


def test_default_keeps_firms_single_sector() -> None:
    pop = _populate()
    cfg = InstitutionConfig(
        enabled=True,
        max_firms=200,
        formation_surplus_threshold=-1.0,
        max_firm_size=10,
    )
    rng = np.random.default_rng(7)
    formed = formation_step(
        pop, cfg, rng,
        surplus_per_proto=np.ones(pop.n, dtype=np.float32),
    )
    assert formed > 0
    for fid in np.unique(pop.firm_id[pop.firm_id >= 0]):
        sectors = np.unique(pop.sector[pop.firm_id == fid])
        assert sectors.size == 1, (
            f"firm {fid} spans sectors {sectors.tolist()} with flag off"
        )


def test_flag_on_produces_cross_sector_firms() -> None:
    pop = _populate()
    cfg = InstitutionConfig(
        enabled=True,
        max_firms=200,
        formation_surplus_threshold=-1.0,
        max_firm_size=10,
        cross_sector_firms=True,
    )
    rng = np.random.default_rng(7)
    formed = formation_step(
        pop, cfg, rng,
        surplus_per_proto=np.ones(pop.n, dtype=np.float32),
    )
    assert formed > 0
    multi_sector = 0
    for fid in np.unique(pop.firm_id[pop.firm_id >= 0]):
        if np.unique(pop.sector[pop.firm_id == fid]).size > 1:
            multi_sector += 1
    assert multi_sector > 0, (
        "expected at least one cross-sector firm with the flag on"
    )


def test_firm_sectors_snapshot_matches_members() -> None:
    cfg = WorldConfig(
        population=PopulationConfig(
            n_human_prototypes=30, n_agent_prototypes=270, seed=11,
        ),
        topology=TopologyConfig(
            alpha=0.4,
            institutions=InstitutionConfig(
                enabled=True,
                max_firms=200,
                formation_surplus_threshold=0.0,
                max_firm_size=10,
                formation_check_every_k=1,
                cross_sector_firms=True,
            ),
        ),
        cast_size=8,
        n_steps=4,
        pairs_per_step=4_000,
        seed=11,
    )
    world = World.build(cfg)
    last = None
    for _ in range(cfg.n_steps):
        last = world.step()
    snap = (last.cast_snapshot if last is not None else None) or []
    pop = world.population
    assert snap, "expected a non-empty cast snapshot"
    for entry in snap:
        fid = entry["firm_id"]
        if fid < 0:
            assert entry["firm_sectors"] == []
            continue
        expected = [int(s) for s in np.unique(pop.sector[pop.firm_id == fid])]
        assert entry["firm_sectors"] == expected, (
            f"agent {entry['idx']} firm {fid}: snapshot "
            f"{entry['firm_sectors']} vs members {expected}"
        )
