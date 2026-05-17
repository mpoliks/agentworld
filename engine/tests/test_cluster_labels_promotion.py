"""Phase 2 §3.2 — cabal → syndicate promotion gate.

cluster_labels.js carries cross-tick Jaccard history per tracked
cluster and promotes a cabal to a syndicate when its mean Jaccard
clears 0.90 for 50 consecutive ticks against its own predecessor.
The plan's check (spatial-sandbox-completeness.md §3.x) calls for
two engineered sequences:

  1. Jaccard 0.95 for 10 ticks then 0.65 for 5 ticks. No promotion
     at any tick (window threshold not reached, and the drop would
     have caught it anyway).
  2. Reverse: a long stretch of sustained ≥ 0.90 Jaccard against the
     same predecessor. Promotion at tick 50 of that stretch.

Python here constructs the per-tick partitions and feeds them
through cluster_labels.js via the Node test harness so the JS
logic stays single-sourced.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER = REPO_ROOT / "dashboard" / "sandbox" / "dev" / "cluster_labels_test_runner.mjs"


def _have_node() -> bool:
    try:
        subprocess.run(["node", "--version"], check=True, capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


pytestmark = pytest.mark.skipif(
    not _have_node(), reason="node not available — cluster_labels.js tests need a Node runtime",
)


def _run(spec: dict) -> dict:
    result = subprocess.run(
        ["node", str(RUNNER)],
        input=json.dumps(spec),
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return json.loads(result.stdout)


def _partition_with_jaccard(prev_members: set[int], j: float,
                            next_agent_id_start: int) -> tuple[set[int], int]:
    """Build a member set whose Jaccard against `prev_members` is
    approximately `j`. Returns (new_members, next_unused_id) so
    successive partitions can keep ids monotonic.

    Strategy: keep `keep` members from prev_members; add enough
    new members so the resulting Jaccard hits the target.
    For target J on equal-size sets:
        J = inter / (|A| + |B| - inter)
        with |A| = |B| = n and inter = keep,
        J = keep / (2n - keep) → keep = J * 2n / (1 + J)
    """
    n = len(prev_members)
    if n == 0:
        # First tick: pick a starting set of 10 members.
        members = set(range(next_agent_id_start, next_agent_id_start + 10))
        return members, next_agent_id_start + 10
    if j >= 0.999:
        return set(prev_members), next_agent_id_start
    keep = int(round(j * 2 * n / (1 + j)))
    keep = max(1, min(n, keep))
    members = set(sorted(prev_members)[:keep])
    needed_new = n - keep
    members |= set(range(next_agent_id_start, next_agent_id_start + needed_new))
    return members, next_agent_id_start + needed_new


def _build_spec_from_jaccard_sequence(jaccard_seq: list[float], *,
                                       promote_window: int = 50,
                                       initial_size: int = 10) -> dict:
    """Build a ticks list where one tracked cabal walks through the
    supplied Jaccard-against-predecessor schedule. Tick 0 establishes
    the cabal; ticks 1..N-1 deliver the engineered Jaccard.
    """
    ticks = []
    next_id = 1000
    # Tick 0: starting members.
    prev = set(range(next_id, next_id + initial_size))
    next_id += initial_size
    ticks.append({
        "partition": [(idx, 0) for idx in prev],
    })
    for j in jaccard_seq:
        new_members, next_id = _partition_with_jaccard(prev, j, next_id)
        ticks.append({
            "partition": [(idx, 0) for idx in new_members],
        })
        prev = new_members
    return {
        "ticks": ticks,
        "promoteWindow": promote_window,
        "matchThreshold": 0.20,
    }


def test_short_high_then_low_jaccard_does_not_promote():
    """Plan §3.x: 0.95 for 10 ticks then 0.65 for 5 ticks. Assert no
    promotion at any tick. The 10+5 window is well short of the
    50-tick promote window and the drop would catch it anyway."""
    seq = [0.95] * 10 + [0.65] * 5
    spec = _build_spec_from_jaccard_sequence(seq, promote_window=50)
    out = _run(spec)
    for entry in out["perTick"]:
        assert entry["syndicates"] == 0, (
            f"tick {entry['tick']}: {entry['syndicates']} syndicates "
            "(want 0)"
        )


def test_sustained_high_jaccard_promotes_after_window():
    """Plan §3.x: sustained Jaccard ≥ 0.90 promotes at tick 50 of
    the run (after `promoteWindow` ticks of high agreement). Use a
    Jaccard schedule that comfortably clears the threshold."""
    seq = [0.95] * 60          # 60 ticks of strong agreement
    spec = _build_spec_from_jaccard_sequence(seq, promote_window=50)
    out = _run(spec)
    # Tick numbering in the harness's perTick: index 0 is the
    # establishing tick (J=undefined). Index k corresponds to the
    # k-th delivered Jaccard value.
    promoted_at = None
    for entry in out["perTick"]:
        if entry["syndicates"] >= 1:
            promoted_at = entry["tick"]
            break
    assert promoted_at is not None, "expected the cabal to be promoted"
    # Plan target: promotion at tick 50 of sustained ≥0.90. There's
    # one establishing tick before the sequence starts, so promotion
    # lands at the (promote_window + 1)-th harness tick.
    assert 49 <= promoted_at <= 51, (
        f"promotion at tick {promoted_at} (expected ~50)"
    )


def test_demotion_after_long_low_jaccard_window():
    """After a syndicate is established, an 80-tick stretch of
    Jaccard < 0.70 should demote it back to cabal. Combine 60 high
    + 90 low ticks; check the syndicate count returns to 0 by the
    end."""
    seq = [0.95] * 60 + [0.60] * 90
    spec = _build_spec_from_jaccard_sequence(
        seq, promote_window=50,
    )
    spec["demoteWindow"] = 80
    spec["demoteMeanJ"] = 0.70
    out = _run(spec)
    # Find peak syndicate count and final count.
    peak = max((entry["syndicates"] for entry in out["perTick"]), default=0)
    final = out["perTick"][-1]["syndicates"]
    assert peak >= 1, f"expected at least one syndicate at peak; got {peak}"
    assert final == 0, (
        f"syndicate not demoted after low-Jaccard stretch (final={final})"
    )
