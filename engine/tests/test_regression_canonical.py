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
