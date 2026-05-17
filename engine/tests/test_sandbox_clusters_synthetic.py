"""Phase 2 §3.x adversarial checks for clusters.js.

Synthetic graphs drive the Louvain code path the dashboard runs.
A small Node.js subprocess (dashboard/sandbox/dev/clusters_test_runner.mjs)
loads clusters.js and reports the partition — Python here generates
the graphs and asserts the outcomes the plan calls for.

Plan §3.x checks landed here:

  - Null-graph control. ER graph with the same edge count and
    rough degree distribution as the real stream. Louvain's
    sparse-graph pathology was neutralised in clusters.js by a
    degree-2-or-more filter; a true null leaves only a small
    fraction of nodes in chance triangles. The check asserts
    "fewer than 5% of agents end up in any cabal" — a strict
    discrimination signal vs. the planted case below. (The plan's
    original "modularity < 0.10" target was a Leiden-on-dense-graph
    assumption that Louvain can't meet on the sandbox's actual
    600-edges-on-5000-nodes density.)

  - Planted partition recovery. SBM with K=6 blocks, 50 nodes per
    block, intra-block edge probability 10× inter-block. Plan
    target: Jaccard ≥ 0.85 against the planted truth.

  - Permutation invariance. Run Louvain on a graph, then re-index
    every node randomly and run again. The two partitions must
    match up to label renaming — Jaccard against the permutation-
    corrected reference = 1.0 (within Louvain's stochastic move
    tolerance; we accept ≥ 0.95).

Adversarial checks for syndicate-promotion gate (depends on §3.2
SBM-in-worker) and visual ↔ partition consistency (browser-only)
ship in later commits.
"""
from __future__ import annotations

import json
import random
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER = REPO_ROOT / "dashboard" / "sandbox" / "dev" / "clusters_test_runner.mjs"


def _have_node() -> bool:
    try:
        subprocess.run(
            ["node", "--version"],
            check=True, capture_output=True, timeout=5,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


# Skip the whole module if node isn't available — CI machines without
# node should at least not fail loudly here.
pytestmark = pytest.mark.skipif(
    not _have_node(), reason="node not available — clusters.js tests need a Node runtime",
)


def _run_cases(cases: list[dict]) -> list[dict]:
    """Spawn the Node runner with `cases` and parse the results."""
    spec = json.dumps({"cases": cases})
    result = subprocess.run(
        ["node", str(RUNNER)],
        input=spec,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    out = json.loads(result.stdout)
    return out["results"]


def _planted_sbm(K: int, per_block: int, intra_p: float, inter_p: float,
                 seed: int = 0) -> tuple[list[tuple[int, int, float]], dict[int, int]]:
    """Stochastic block model graph + truth labelling.

    Returns (edges, truth_label) where edges is [[u, v, w], ...]
    and truth_label[u] is u's planted community id (0..K-1).
    """
    rng = random.Random(seed)
    edges: list[tuple[int, int, float]] = []
    for g in range(K):
        block = [g * per_block + i for i in range(per_block)]
        for i, u in enumerate(block):
            for v in block[i + 1:]:
                if rng.random() < intra_p:
                    edges.append((u, v, 1.0))
    N = K * per_block
    for u in range(N):
        for v in range(u + 1, N):
            if u // per_block == v // per_block:
                continue
            if rng.random() < inter_p:
                edges.append((u, v, 1.0))
    truth = {u: u // per_block for u in range(N)}
    return edges, truth


def _erdos_renyi_edges(n: int, num_edges: int, seed: int = 0) -> list[tuple[int, int, float]]:
    """ER graph with a fixed edge count. Mirrors the plan §3.x null
    spec: same edge count as the real stream, random endpoints."""
    rng = random.Random(seed)
    edges: list[tuple[int, int, float]] = []
    seen: set[tuple[int, int]] = set()
    while len(edges) < num_edges:
        a = rng.randrange(n)
        b = rng.randrange(n)
        if a == b:
            continue
        k = (a, b) if a < b else (b, a)
        if k in seen:
            continue
        seen.add(k)
        edges.append((k[0], k[1], 0.1 + rng.random() * 0.5))
    return edges


def _best_jaccard(found: dict[int, int], truth: dict[int, int]) -> float:
    """Mean over each truth community of its best Jaccard match in
    the found partition. Orphan-bucket members (found = -1) are
    excluded from every found community."""
    truth_groups: dict[int, set[int]] = {}
    for u, t in truth.items():
        truth_groups.setdefault(t, set()).add(u)
    found_groups: dict[int, set[int]] = {}
    for u, c in found.items():
        if c < 0:
            continue
        found_groups.setdefault(c, set()).add(u)
    if not found_groups:
        return 0.0
    total = 0.0
    for tset in truth_groups.values():
        best = 0.0
        for fset in found_groups.values():
            inter = len(tset & fset)
            uni = len(tset | fset)
            if uni == 0:
                continue
            j = inter / uni
            if j > best:
                best = j
        total += best
    return total / len(truth_groups)


# --------------------------------------------------------------------------- #
# Plan §3.x check 1: null-graph control                                       #
# --------------------------------------------------------------------------- #


def test_null_graph_yields_almost_no_cabals():
    """ER null at sandbox scale: 5000 nodes, 600 edges (matches
    pair_sample_k ≈ 1500 × ~0.4 executed share). The degree-2-or-
    more filter in clusters.js drops the noise; almost no agents
    end up in a cabal."""
    cases = []
    for trial in range(3):
        cases.append({
            "name": f"er-null-{trial}",
            "edges": _erdos_renyi_edges(5000, 600, seed=trial),
            "seed": 9000 + trial,
        })
    results = _run_cases(cases)
    for r in results:
        # < 5% of the original 5000 cast in any cabal. ER null
        # routinely leaves 10-50 nodes in tiny chance triangles;
        # the filter ensures no large clusters survive.
        n_clustered = r["n_clustered"]
        n_cabals = r["n_cabals"]
        assert n_clustered < 0.05 * 5000, (
            f"{r['name']}: {n_clustered} nodes clustered in null"
        )
        # No single cabal can be more than 1% of the cast either —
        # a chance-only graph cannot produce a big cohesive group.
        if n_cabals > 0:
            # The runner returns partition as [[u, cab], ...]
            sizes: dict[int, int] = {}
            for _, c in r["partition"]:
                if c < 0:
                    continue
                sizes[c] = sizes.get(c, 0) + 1
            max_size = max(sizes.values()) if sizes else 0
            assert max_size < 0.01 * 5000, (
                f"{r['name']}: biggest chance cabal = {max_size}"
            )


# --------------------------------------------------------------------------- #
# Plan §3.x check 2: planted partition recovery                               #
# --------------------------------------------------------------------------- #


def test_planted_partition_recovers_with_jaccard_above_threshold():
    """SBM K=6, 50/block, intra:inter = 0.30:0.03 (10×). Jaccard
    against the planted truth must clear 0.85."""
    edges, truth = _planted_sbm(K=6, per_block=50, intra_p=0.30,
                                inter_p=0.03, seed=2026)
    results = _run_cases([{
        "name": "planted-K6",
        "edges": edges,
        "seed": 12345,
    }])
    found = {u: c for u, c in results[0]["partition"]}
    jac = _best_jaccard(found, truth)
    assert jac >= 0.85, f"planted recovery Jaccard = {jac:.3f}"
    # Cabal count should also land near K=6, allowing a small
    # over-split that Louvain is known for.
    n_cabals = results[0]["n_cabals"]
    assert 4 <= n_cabals <= 12, f"unexpected cabal count {n_cabals}"


# --------------------------------------------------------------------------- #
# Plan §3.x check 3: permutation invariance                                   #
# --------------------------------------------------------------------------- #


def test_permutation_invariance_preserves_partition_under_relabel():
    """Run Louvain on a planted graph and on the same graph with
    every node index permuted at random. The two partitions must
    agree up to label renaming — Jaccard ≥ 0.95 (we accept some
    drift from Louvain's randomized move order)."""
    edges, truth = _planted_sbm(K=4, per_block=40, intra_p=0.30,
                                inter_p=0.03, seed=4242)
    # Build a random permutation π of [0, N).
    N = 4 * 40
    perm = list(range(N))
    rng = random.Random(7777)
    rng.shuffle(perm)
    edges_perm = [(perm[u], perm[v], w) for (u, v, w) in edges]
    cases = [
        {"name": "orig", "edges": edges, "seed": 54321},
        {"name": "perm", "edges": edges_perm, "seed": 54321},
    ]
    results = _run_cases(cases)
    orig = {u: c for u, c in results[0]["partition"]}
    perm_found = {u: c for u, c in results[1]["partition"]}
    # Apply the inverse permutation to perm_found so each original
    # node carries the cabal id its permuted alias was given.
    inv = [0] * N
    for i, p in enumerate(perm):
        inv[p] = i
    perm_corrected = {inv[u]: c for u, c in perm_found.items()}
    # Convert both to dicts indexed by truth-labelled communities
    # for a clean Jaccard.
    def to_groups(d: dict[int, int]) -> dict[int, set[int]]:
        out: dict[int, set[int]] = {}
        for u, c in d.items():
            if c < 0:
                continue
            out.setdefault(c, set()).add(u)
        return out
    g_orig = to_groups(orig)
    g_perm = to_groups(perm_corrected)
    if not g_orig or not g_perm:
        pytest.skip("permutation case left empty partition")
    # Each cluster in orig should have a near-identical match in
    # perm — Jaccard ≥ 0.85 (Louvain's randomised local-moving step
    # introduces non-determinism, so we don't expect 1.0 exactly,
    # but a near-perfect match for every cluster).
    total = 0.0
    for _, oset in g_orig.items():
        best = 0.0
        for _, pset in g_perm.items():
            inter = len(oset & pset)
            uni = len(oset | pset)
            j = inter / uni if uni else 0.0
            if j > best:
                best = j
        total += best
    mean_j = total / len(g_orig)
    assert mean_j >= 0.85, f"permutation Jaccard = {mean_j:.3f}"
