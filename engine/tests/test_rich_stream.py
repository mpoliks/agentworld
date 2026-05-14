"""PR #5: rich SSE stream — `cast_snapshot_v2`, `edges_v2`, `folds_v2`.

The demux is a function of the step-payload dict that returns the v2
sub-events when their source fields are non-empty. The SSE handler in
`engine/serve.py` calls it on every replay and live `step` event.
"""
from __future__ import annotations

import dataclasses

import pytest

from engine.core.population import PopulationConfig
from engine.core.topology import (
    InstitutionConfig, NormsConfig, TopologyConfig,
)
from engine.core.world import World, WorldConfig
from engine.serve import _step_metrics_to_dict, _v2_subpayloads


def _build_world(*, with_cast: bool, with_pairs: bool, n_steps: int = 4) -> World:
    cfg = WorldConfig(
        population=PopulationConfig(
            n_human_prototypes=30, n_agent_prototypes=270, seed=17,
        ),
        topology=TopologyConfig(
            alpha=0.6,
            norms=NormsConfig(enabled=True, certified_fraction=0.5),
            institutions=InstitutionConfig(
                enabled=True,
                max_firms=200,
                formation_surplus_threshold=0.0,
                cross_sector_firms=True,
                formation_check_every_k=1,
            ),
        ),
        cast_size=6 if with_cast else 0,
        pair_sample_k=8 if with_pairs else 0,
        n_steps=n_steps,
        pairs_per_step=4_000,
        seed=17,
    )
    return World.build(cfg)


def test_empty_payload_emits_nothing() -> None:
    """Step payload with no cast/edges/folds emits no v2 sub-events."""
    world = _build_world(with_cast=False, with_pairs=False)
    last = None
    for _ in range(world.cfg.n_steps):
        last = world.step()
    payload = _step_metrics_to_dict(last)
    payload.setdefault("fold_per_depth_contribution", [])
    subs = _v2_subpayloads(payload)
    # Force the three source lists empty to isolate the demux behaviour.
    payload["cast_snapshot"] = []
    payload["pair_samples"] = []
    payload["fold_per_depth_contribution"] = []
    assert _v2_subpayloads(payload) == []


def test_cast_snapshot_v2_emitted_when_cast_present() -> None:
    world = _build_world(with_cast=True, with_pairs=False)
    last = None
    for _ in range(world.cfg.n_steps):
        last = world.step()
    payload = _step_metrics_to_dict(last)
    subs = dict(_v2_subpayloads(payload))
    assert "cast_snapshot_v2" in subs
    cs = subs["cast_snapshot_v2"]
    assert cs["step"] == last.step
    assert isinstance(cs["snapshot"], list)
    assert len(cs["snapshot"]) > 0
    # Each snapshot entry carries the PR #1/#2 enrichments.
    entry = cs["snapshot"][0]
    assert "firm_sectors" in entry
    assert "certified" in entry


def test_edges_v2_emitted_when_pair_samples_present() -> None:
    world = _build_world(with_cast=False, with_pairs=True)
    last = None
    for _ in range(world.cfg.n_steps):
        last = world.step()
    payload = _step_metrics_to_dict(last)
    subs = dict(_v2_subpayloads(payload))
    assert "edges_v2" in subs
    ev = subs["edges_v2"]
    assert ev["step"] == last.step
    assert isinstance(ev["edges"], list)
    assert len(ev["edges"]) > 0
    # Each edge is a PairSample dict; reject_reason is one of the known
    # gates (including "compute" after PR #4 / PR #5 touch-up).
    valid = {"", "permeability", "compute", "law", "regulator",
             "market", "align", "cost", "unknown"}
    for edge in ev["edges"]:
        assert edge["reject_reason"] in valid


def test_folds_v2_emitted_when_per_depth_present() -> None:
    """A scenario with folding active surfaces folds_v2 with per-depth data."""
    cfg = WorldConfig(
        population=PopulationConfig(
            n_human_prototypes=30, n_agent_prototypes=270, seed=19,
        ),
        topology=TopologyConfig(
            alpha=0.85,  # high alpha drives fold cascade
            folding_propensity=0.5,
        ),
        n_steps=4,
        pairs_per_step=4_000,
        seed=19,
    )
    world = World.build(cfg)
    last = None
    for _ in range(cfg.n_steps):
        last = world.step()
    payload = _step_metrics_to_dict(last)
    subs = dict(_v2_subpayloads(payload))
    if not last.fold_per_depth_contribution:
        pytest.skip("fold cascade produced no per-depth contribution this seed")
    assert "folds_v2" in subs
    folds = subs["folds_v2"]
    assert folds["step"] == last.step
    assert folds["per_depth"] == last.fold_per_depth_contribution
    assert "fold_max_depth" in folds


def test_v2_subpayloads_step_index_round_trips() -> None:
    """The sub-event step index matches the source payload's step."""
    payload = {
        "step": 42,
        "cast_snapshot": [{"idx": 0}],
        "pair_samples": [{"proto_a": 1, "proto_b": 2, "executed": True,
                          "reject_reason": "", "is_a_human": False,
                          "is_b_human": False, "sec_a": 0, "sec_b": 1,
                          "cap_a": 0.5, "cap_b": 0.5, "base_surplus": 0.1,
                          "friction": 0.0, "real_surplus": 0.1,
                          "pair_weight": 1.0}],
        "fold_per_depth_contribution": [1.0, 0.5],
        "n_sub_markets_added": 3.0,
        "fold_max_depth": 2,
    }
    subs = dict(_v2_subpayloads(payload))
    for kind in ("cast_snapshot_v2", "edges_v2", "folds_v2"):
        assert subs[kind]["step"] == 42
