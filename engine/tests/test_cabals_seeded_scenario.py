"""Plan §C.3/§C.4 — contract test for the cabals_seeded scenario.

The dashboard's cluster pipeline runs in browser JS (clusters.js, then
cluster_labels.js, then cluster_overlay.js). When the live engine
reports CABALS = 0 across every regime, the reviewer cannot
distinguish three different failure modes:

  1. The engine produces no community structure to detect.
  2. Louvain detects communities but the MIN_CABAL_SIZE / orphan
     filter drops them below the render floor.
  3. The detector wires up but the overlay never reads from it.

This test isolates failure mode (1). The `cabals_seeded` scenario
pushes ``network_intra_sector_share`` to 0.99 and the mean degree to
30 so the 12 sectors function as 12 near-clique blocks with almost
zero cross-block adjacency. If executed-trade pairs from this
scenario do not group into at least three dense sector-blocks within
60 ticks, the engine itself isn't producing structure — the
dashboard's flat-line CABALS reading is honest. If they do, the
absence of cabals on ``spatial_sandbox`` is a true engine result and
not a plumbing bug.

The Python side here only asserts (1): edges executed in this
scenario over 60 ticks must concentrate inside ≥ 3 sectors at the
edge-density Louvain needs to merge them into communities. We
sidestep running Louvain in Python — the JS-side
test_sandbox_clusters_synthetic test already covers the Louvain code
path with planted SBM graphs; here we only check that the engine
delivers those edges to the dashboard.
"""
from __future__ import annotations

from collections import Counter

import pytest

from engine.core.world import World
from engine.scenarios import get_scenario


@pytest.fixture(scope="module")
def seeded_pair_buffer():
    """Run the cabals_seeded scenario for 60 ticks and return the
    accumulated executed-pair (sec_a, sec_b) tuples — i.e. the
    sector-of-side-a and sector-of-side-b for every cleared trade.
    """
    cfg = get_scenario("cabals_seeded")
    # Shrink the test footprint: 60 ticks is the plan target, but the
    # canonical 5000-cast / 88k-prototype scale is heavy for a unit
    # test. The sector-block structure is independent of scale, so
    # use a smaller cast with the same SBM density knobs.
    cfg.population.n_human_prototypes = 60
    cfg.population.n_agent_prototypes = 540
    cfg.cast_size = 600
    cfg.pair_sample_k = 300
    cfg.pairs_per_step = 6_000
    cfg.n_steps = 60

    world = World.build(cfg)
    # PairSample carries the per-pair (sec_a, sec_b) directly — no
    # population-side sector lookup needed.
    sector_pairs: list[tuple[int, int]] = []
    for _ in range(cfg.n_steps):
        m = world.step()
        pairs = getattr(m, "pair_samples", None)
        if not pairs:
            continue
        for p in pairs:
            if not getattr(p, "executed", False):
                continue
            sector_pairs.append((int(p.sec_a), int(p.sec_b)))
    return sector_pairs


def test_cabals_seeded_concentrates_edges_inside_sectors(seeded_pair_buffer):
    """≥ 3 sector blocks accumulate ≥ 20 intra-sector executed edges
    over 60 ticks. The exact threshold is calibrated to ~5% of the
    expected per-block edge count under SBM with the seeded density;
    failures here mean the SBM constructor is not producing the
    intra-share the config asked for or the partner sampler isn't
    drawing local neighbours.
    """
    intra_per_sector = Counter()
    for sa, sb in seeded_pair_buffer:
        if sa == sb:
            intra_per_sector[sa] += 1
    big_sectors = [s for s, c in intra_per_sector.items() if c >= 20]
    assert len(big_sectors) >= 3, (
        f"cabals_seeded: only {len(big_sectors)} sectors accumulated "
        f"≥ 20 intra-sector executed edges over 60 ticks "
        f"(per-sector counts: {dict(intra_per_sector)})"
    )


def test_cabals_seeded_intra_share_dominates(seeded_pair_buffer):
    """The SBM density knobs were pushed to 99% intra-share; the
    executed-trade pair stream should reflect that with ≥ 70% of
    cleared pairs landing inside a single sector. (Not 99% because
    the trade-selection layer also draws partners from other
    channels — well-mixed background, registered-firm hub picks —
    that wash out the pure-SBM signal somewhat.)
    """
    if not seeded_pair_buffer:
        pytest.skip("no executed pairs collected (engine pair sampler returned none)")
    intra = sum(1 for sa, sb in seeded_pair_buffer if sa == sb)
    share = intra / len(seeded_pair_buffer)
    assert share >= 0.70, (
        f"intra-sector share of executed pairs = {share:.2f}; "
        f"expected ≥ 0.70 under cabals_seeded SBM density"
    )
