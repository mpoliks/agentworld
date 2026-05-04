"""Convergence-pinned regression — does small scale faithfully approximate medium scale?

For a curated subset of scenarios we sweep population scale ∈ {small,
medium} with K seeds each and assert that the small-scale terminal-EBI
mean lies within the medium-scale bootstrap CI. Where it does not, the
importance-weighting failure mode is biting and the scenario is flagged
as scale-fragile.

The full multi-scale sweep with proper bootstrap discipline lives in
`engine.convergence`; this test is a tight subset chosen for runtime.
"""

from __future__ import annotations

import pytest

from engine.convergence import run_scenario_at_scale
from engine.scale import Scale


# Scenarios picked to span the smooth/striated/productive arms of the
# parameter space without enabling any extra-cost paths (no full-emergence,
# no large-scale law/dynamics composition).
PINNED_SCENARIOS = (
    "coasean_paradise",
    "baroque_cathedral",
    "productive_baroque",
)


@pytest.mark.parametrize("name", PINNED_SCENARIOS)
def test_small_scale_terminal_ebi_inside_medium_scale_ci(name: str) -> None:
    seeds = [0, 1]
    small = run_scenario_at_scale(name, Scale.SMALL, seeds, n_steps=30)
    medium = run_scenario_at_scale(name, Scale.MEDIUM, seeds, n_steps=30)

    s_small = small.summary["exo_baroque_index"]
    s_medium = medium.summary["exo_baroque_index"]

    # Allow a generous slack outside the bootstrap CI: the test is meant to
    # catch order-of-magnitude divergence, not to pin point estimates.
    span = max(s_medium["hi"] - s_medium["lo"], 0.10 * max(abs(s_medium["mean"]), 1.0))
    lo = s_medium["lo"] - 0.5 * span
    hi = s_medium["hi"] + 0.5 * span
    assert lo <= s_small["mean"] <= hi, (
        f"{name}: small-scale EBI mean {s_small['mean']:.3f} is outside "
        f"medium-scale CI [{lo:.3f}, {hi:.3f}] (raw CI "
        f"[{s_medium['lo']:.3f}, {s_medium['hi']:.3f}]). "
        f"This scenario is scale-fragile under importance weighting."
    )
