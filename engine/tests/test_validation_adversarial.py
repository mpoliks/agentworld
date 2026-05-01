"""Pin tests for the adversarial scenario search (A3).

Two scopes:

1. The search itself runs deterministically and has the right shape.
2. The persisted artifact at outputs/validation/adversarial_search.json
   matches the conclusion the brief now states: a counter-example exists
   under productive folding. The numerical thresholds are wide so a
   refactor that perturbs the trajectory by 5-10% does not break the
   test, but a result that *flips the verdict* will.

Note: the small-scale runtime used by the search has lower coasean_paradise
welfare than the canonical scale, so the threshold the search beats is the
same-scale paradise. This is honest about what the counter-example claims:
"there exist parameters where the model produces high EBI and welfare
above paradise *at the same runtime budget*." Lifting that to "high EBI
coexists with high welfare in general" requires the priors sweep (A2).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from engine.scenarios import get_scenario
from engine.validation.adversarial import (
    SEARCH_BOUNDS,
    AdversarialResult,
    adversarial_search,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_adversarial_search_runs_and_returns_well_formed_result():
    res = adversarial_search(n_evals=10, seed=0, n_steps=12, progress=False)
    assert isinstance(res, AdversarialResult)
    assert res.n_evals == 10
    assert res.seed == 0
    # Bounds round-trip.
    assert len(res.bounds) == len(SEARCH_BOUNDS)
    # Best point covers every search dimension.
    assert set(res.best_point.keys()) == {b[0] for b in SEARCH_BOUNDS}
    # All values inside their declared bounds.
    for name, lo, hi in SEARCH_BOUNDS:
        assert lo <= res.best_point[name] <= hi, name
    # Score trajectory exists and isn't NaN.
    assert len(res.score_trajectory) == res.n_evals
    for s in res.score_trajectory:
        assert math.isfinite(s)


def test_persisted_search_artifact_records_a_counter_example():
    """The canonical search at seed=0 / n_evals=200 finds a region where
    EBI > 10 and welfare > coasean_paradise's terminal welfare."""
    p = REPO_ROOT / "outputs" / "validation" / "adversarial_search.json"
    if not p.exists():
        pytest.skip(f"Run `agentworld validate adversarial` to produce {p}")
    d = json.loads(p.read_text())
    assert d["found_counter_example"] is True
    assert d["best_ebi"] > d["ebi_target"]
    assert d["best_welfare"] > d["paradise_welfare"]
    # The search budget the artifact was produced at.
    assert d["n_evals"] >= 100, "canonical artifact is supposed to be at least 100 evals"


def test_baroque_with_high_welfare_scenario_reproduces_counter_example():
    """Running the registered scenario reproduces the counter-example
    qualitatively. We check the verdict, not exact numbers — engine
    tweaks may shift welfare a few percent."""
    from engine.core.world import World
    from engine.validation.adversarial import _RunSpec, _measure_paradise_welfare

    spec = _RunSpec(
        n_steps=30, n_human_prototypes=600, n_agent_prototypes=6_000,
        pairs_per_step=20_000,
    )
    paradise = _measure_paradise_welfare(spec, seed=0)

    w = World.build(get_scenario("baroque_with_high_welfare"))
    w.run(progress=False)
    last = w.metrics.history.steps[-1]
    assert last.exo_baroque_index > 10.0
    assert last.real_per_capita_welfare > paradise
