"""Plan §5.1 stretch — live network rewire.

`network_model` and `network_p_local` were structural levers (built
into the adjacency matrix at population synthesize and never
revisited mid-run). Phase-5.1 wires them live:

  - `network_p_local` is read per-tick by the partner sampler
    (engine/core/transactions.py:363) and needs no rebuild —
    writing the new value via _apply_overrides takes effect on
    the next step automatically.
  - `network_model` triggers a one-off `world.rewire_network()`
    call between ticks. The engine rebuilds `population.adjacency`
    and `population.degree_centrality`; the next sampler call
    picks up the new structure.

These tests exercise the engine side; the dashboard's lever flip
from structural to live is covered by test_lever_inventory_contract.
"""
from __future__ import annotations

import numpy as np
import pytest

from engine.core.world import World, WorldConfig
from engine.core.population import PopulationConfig
from engine.core.topology import TopologyConfig
from engine.serve import _apply_overrides


def _build_world(network_model: str = "sbm") -> World:
    cfg = WorldConfig(
        population=PopulationConfig(
            n_human_prototypes=60,
            n_agent_prototypes=540,
            seed=7,
            network_model=network_model,
            network_p_local=0.6,
        ),
        topology=TopologyConfig(alpha=0.5),
        n_steps=2,
        pairs_per_step=2_000,
        cast_size=64,
        seed=7,
    )
    return World.build(cfg)


def test_rewire_to_well_mixed_drops_adjacency():
    """`network_model = "well_mixed"` is the no-adjacency path.
    Rewire after construction should null the adjacency."""
    w = _build_world(network_model="sbm")
    assert w.population.adjacency is not None
    w.cfg.population.network_model = "well_mixed"
    w.rewire_network()
    assert w.population.adjacency is None


def test_rewire_to_scale_free_changes_structure():
    """Rewire from sbm to scale_free should produce a different
    adjacency. We compare degree-centrality distributions — sbm
    has a tight degree spread around mean_degree; scale_free has
    a power-law tail with a few hubs."""
    w = _build_world(network_model="sbm")
    deg_sbm = w.population.degree_centrality.copy()
    w.cfg.population.network_model = "scale_free"
    w.rewire_network()
    deg_scale = w.population.degree_centrality.copy()
    # The two distributions should differ on the tail.
    assert deg_sbm.max() != deg_scale.max() or deg_sbm.std() != deg_scale.std()


def test_rewire_preserves_step_loop():
    """After a rewire, the World can step without raising."""
    w = _build_world(network_model="sbm")
    w.step()
    w.cfg.population.network_model = "scale_free"
    w.rewire_network()
    w.step()
    w.step()
    # No exception is the test.


def test_apply_overrides_accepts_network_keys():
    """Both network_model (string) and network_p_local (float)
    round-trip through _apply_overrides without raising."""
    w = _build_world(network_model="sbm")
    _apply_overrides(w.cfg, {
        "network_model": "scale_free",
        "network_p_local": 0.3,
    }, extend_bounds=True)
    assert w.cfg.population.network_model == "scale_free"
    assert w.cfg.population.network_p_local == pytest.approx(0.3)


def test_live_tunable_includes_network_keys():
    """`network_model` and `network_p_local` must be on
    `_LIVE_TUNABLE` — otherwise POST /update will 400 silently."""
    import re
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "serve.py").read_text()
    m = re.search(r"_LIVE_TUNABLE\s*=\s*\{(.*?)\n\s*\}", src, re.DOTALL)
    body = m.group(1)
    keys = set(re.findall(r'"([^"]+)"', body))
    assert "network_model" in keys
    assert "network_p_local" in keys
