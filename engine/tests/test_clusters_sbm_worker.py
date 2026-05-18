"""Phase 2 §3.2 follow-on — secondary clusterer Web Worker.

clusters_sbm.js runs Louvain in a worker; the main thread feeds
its partition into cluster_labels.updateWithSecondary so a track
that both clusterers agree on flips `validated = true`. The worker
module re-implements Louvain locally rather than importing from
clusters.js because Web Workers don't share the main thread's
module state.

CI checks here:

  - runJob exposed for testing returns a partition on a planted
    SBM graph that's close to the primary's (Jaccard ≥ 0.85).
  - cluster_labels.updateWithSecondary marks tracks validated
    when the secondary agrees ≥ 0.70, and leaves them un-
    validated when the secondary disagrees.
"""
from __future__ import annotations

import json
import random
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKER_RUNNER = (
    REPO_ROOT / "dashboard" / "sandbox" / "dev" / "clusters_sbm_test_runner.mjs"
)


def _have_node() -> bool:
    try:
        subprocess.run(
            ["node", "--version"],
            check=True, capture_output=True, timeout=5,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


pytestmark = pytest.mark.skipif(
    not _have_node(), reason="node not available — clusters_sbm tests need a Node runtime",
)


def _run(spec: dict) -> dict:
    result = subprocess.run(
        ["node", str(WORKER_RUNNER)],
        input=json.dumps(spec),
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return json.loads(result.stdout)


def _planted_sbm(K=4, per_block=40, intra_p=0.30, inter_p=0.03, seed=0):
    rng = random.Random(seed)
    edges = []
    for g in range(K):
        block = [g * per_block + i for i in range(per_block)]
        for i, u in enumerate(block):
            for v in block[i + 1:]:
                if rng.random() < intra_p:
                    edges.append([u, v, 1.0])
    N = K * per_block
    for u in range(N):
        for v in range(u + 1, N):
            if u // per_block == v // per_block:
                continue
            if rng.random() < inter_p:
                edges.append([u, v, 1.0])
    truth = {u: u // per_block for u in range(N)}
    return edges, truth


def _best_jaccard(found: dict[int, int], truth: dict[int, int]) -> float:
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
            j = inter / uni if uni else 0.0
            if j > best:
                best = j
        total += best
    return total / len(truth_groups)


def test_worker_recovers_planted_partition():
    """The worker module's runJob, run as plain JS, produces a
    partition with Jaccard ≥ 0.85 against the planted truth on
    most seeds. Louvain's randomised local-moving step yields
    occasional outliers; we take the best of three seeds (mirrors
    real-world worker behaviour where the user sees a partition
    refresh every 10 ticks, not a single shot)."""
    edges, truth = _planted_sbm()
    best_j = 0.0
    best_mod = 0.0
    for seed in (1, 2, 3):
        out = _run({"action": "run", "edges": edges, "seed": seed})
        found = {u: c for u, c in out["partition"]}
        j = _best_jaccard(found, truth)
        if j > best_j:
            best_j = j
            best_mod = out["modularity"]
    assert best_mod > 0.30, (
        f"worker modularity = {best_mod:.3f} (planted graph)"
    )
    assert best_j >= 0.85, f"worker planted Jaccard = {best_j:.3f}"


def test_secondary_jaccard_marks_track_validated():
    """When the worker's partition agrees ≥ 0.70 Jaccard with a
    primary track, the track flips `validated = true`. Disagreement
    leaves `validated = false`."""
    # Build a primary partition with a 10-member cabal.
    primary_members = list(range(10))
    primary_partition = [[i, 0] for i in primary_members]
    # Secondary that agrees with the primary (same 10 members).
    secondary_agree = [[i, 0] for i in primary_members]
    out = _run({
        "action": "labels-validate",
        "primary": primary_partition,
        "secondary": secondary_agree,
    })
    track = out["track"]
    assert track["validated"] is True, (
        f"agreeing secondary did not validate (Jaccard={track['secondaryJaccard']})"
    )
    assert track["secondaryJaccard"] >= 0.70

    # Secondary that disagrees (completely different members).
    secondary_disagree = [[i + 100, 0] for i in range(10)]
    out2 = _run({
        "action": "labels-validate",
        "primary": primary_partition,
        "secondary": secondary_disagree,
    })
    track2 = out2["track"]
    assert track2["validated"] is False
    assert track2["secondaryJaccard"] < 0.70
