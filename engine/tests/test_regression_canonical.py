"""Regression test against saved canonical baselines.

Re-runs each baseline scenario, compares terminal metrics to the JSON files
in outputs/runs/. The bar is tight (|ΔEBI| < 5%) because all three new
mechanisms are flag-gated and the canonical scenarios opt none of them in.
A failure here means a change to the engine has silently shifted what the
default code path computes — investigate before merging.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.core.world import World
from engine.scenarios import get_scenario


CANONICAL_SCENARIOS = (
    "coasean_paradise",
    "baroque_cathedral",
    "equilibrium_drift",
    "smoothing_cascade",
    "fold_avalanche",
    "hemispherical_schism",
    "compute_famine",
    "universal_advocate",
    "synthetic_consumers",
    "nimby_cascade",
    "slop_market",
    "public_defender",
    "matryoshka_collapse",
    "recursive_simulation",
    "exo_baroque_singularity",
)

BASELINE_DIR = Path(__file__).resolve().parents[2] / "outputs" / "runs"


@pytest.mark.parametrize("name", CANONICAL_SCENARIOS)
def test_canonical_scenario_matches_saved_baseline(name: str) -> None:
    baseline_path = BASELINE_DIR / f"{name}.json"
    if not baseline_path.exists():
        pytest.skip(f"missing canonical baseline {baseline_path}")

    baseline = json.loads(baseline_path.read_text())
    cfg = get_scenario(name)
    world = World.build(cfg)
    world.run(progress=False)
    terminal = world.metrics.history.steps[-1]

    old_ebi = baseline["history"]["exo_baroque_index"][-1]
    new_ebi = terminal.exo_baroque_index
    assert abs(new_ebi - old_ebi) / old_ebi < 0.05
    assert world.topology.label() == baseline["final_label"]


def _terminal_relative_drift(ebi_series, k: int = 10) -> float:
    """Per-step relative EBI drift over the last `k` steps.

    Returns 0.0 if the series is shorter than `k + 1` or terminal value is
    near zero.
    """
    if len(ebi_series) < k + 1:
        return 0.0
    end = float(ebi_series[-1])
    start = float(ebi_series[-k - 1])
    if abs(start) < 1e-9:
        return 0.0
    return (end - start) / (k * abs(start))


@pytest.mark.parametrize("name", CANONICAL_SCENARIOS)
def test_canonical_trajectory_terminal_drift_matches_baseline(name: str) -> None:
    """Pin the *trajectory shape* near the terminal step, not just the
    point estimate.

    For each canonical scenario we compute the per-step relative drift of
    EBI over the last 10 steps, both for the saved baseline and for a
    fresh re-run. A code change that silently accelerates or arrests the
    trajectory near the terminal step shows up as a drift mismatch even
    if the terminal point estimate happens to land within the 5%
    baseline tolerance. This is what tells the brief whether a quoted
    terminal number is *steady-state* or *transient*: the empirical
    sweep at `agentworld stability --steps 100 200 400` lives downstream
    of this check, but the regression here is the frozen version.
    """
    baseline_path = BASELINE_DIR / f"{name}.json"
    if not baseline_path.exists():
        pytest.skip(f"missing canonical baseline {baseline_path}")

    baseline = json.loads(baseline_path.read_text())
    cfg = get_scenario(name)
    world = World.build(cfg)
    world.run(progress=False)

    baseline_series = baseline["history"]["exo_baroque_index"]
    current_series = [s.exo_baroque_index for s in world.metrics.history.steps]

    base_drift = _terminal_relative_drift(baseline_series, k=10)
    curr_drift = _terminal_relative_drift(current_series, k=10)

    # Tolerance: the absolute drift is small even for transient scenarios
    # (~0.5–1% per step), so we allow the *change* in drift to be up to
    # 0.5pp per step in either direction. That is generous enough that
    # the tx/fold/law machinery can wiggle without false alarms but tight
    # enough that a real shape change (steady → transient or vice versa)
    # will trip.
    delta = abs(curr_drift - base_drift)
    assert delta < 5e-3, (
        f"{name}: terminal trajectory drift changed from "
        f"{base_drift:+.4f} per step (baseline) to {curr_drift:+.4f} per "
        f"step (current); |delta|={delta:.4f} > 0.005. Investigate before "
        f"merging — a flat scenario may have started drifting, or a "
        f"transient scenario may have arrested."
    )
