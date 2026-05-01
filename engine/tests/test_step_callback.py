"""Guardrail for the streaming hook (B1 of validation_lift_plus_live_viz).

`World.run` and `ExoWorld.run` accept an optional `step_callback`. The
contract is: when no callback is provided, behavior is bit-identical to the
historical no-callback path; when a callback is provided, the metrics
history at the end of the run is bit-identical to the same scenario run
without a callback. The callback observes; it does not perturb.
"""

from __future__ import annotations

from dataclasses import asdict

import numpy as np

from engine.core.world import World
from engine.exo.scenarios import get_scenario as get_exo_scenario
from engine.exo.world import ExoWorld
from engine.scenarios import get_scenario


def _shrink_alpha(name: str, n_steps: int = 3):
    cfg = get_scenario(name)
    cfg.n_steps = n_steps
    cfg.pairs_per_step = 5_000
    cfg.population.n_human_prototypes = 200
    cfg.population.n_agent_prototypes = 2_000
    return cfg


def _shrink_exo(name: str, n_steps: int = 4, n_regions: int = 4):
    cfg = get_exo_scenario(name)
    cfg.n_steps = n_steps
    cfg.region.n_regions = n_regions
    return cfg


def _history_dict(metrics) -> dict:
    return metrics.history.to_dict()


def _equal_history(a: dict, b: dict) -> bool:
    if set(a.keys()) != set(b.keys()):
        return False
    for k in a:
        va, vb = np.asarray(a[k]), np.asarray(b[k])
        if va.shape != vb.shape:
            return False
        if not np.array_equal(va, vb):
            return False
    return True


def test_alpha_step_callback_is_bit_identical_when_noop():
    cfg_a = _shrink_alpha("equilibrium_drift")
    cfg_b = _shrink_alpha("equilibrium_drift")
    a = World.build(cfg_a)
    b = World.build(cfg_b)
    a.run(progress=False)
    seen = []
    b.run(progress=False, step_callback=lambda m: seen.append(m.step))
    assert _equal_history(_history_dict(a.metrics), _history_dict(b.metrics))
    assert seen == list(range(cfg_b.n_steps))


def test_alpha_step_callback_runs_when_none():
    cfg = _shrink_alpha("equilibrium_drift")
    w = World.build(cfg)
    w.run(progress=False, step_callback=None)
    assert len(w.metrics.history.steps) == cfg.n_steps


def test_exo_step_callback_is_bit_identical_when_noop():
    cfg_a = _shrink_exo("fold_cathedral")
    cfg_b = _shrink_exo("fold_cathedral")
    a = ExoWorld.build(cfg_a)
    b = ExoWorld.build(cfg_b)
    a.run(progress=False)
    seen = []
    b.run(progress=False, step_callback=lambda m: seen.append(m.step))
    assert _equal_history(a.history.to_dict(), b.history.to_dict())
    assert seen == list(range(cfg_b.n_steps))


def test_callback_receives_step_metrics_with_expected_fields():
    cfg = _shrink_alpha("equilibrium_drift")
    w = World.build(cfg)
    received = []
    w.run(progress=False, step_callback=lambda m: received.append(m))
    assert len(received) == cfg.n_steps
    m0 = received[0]
    d = asdict(m0)
    for required in ("step", "alpha", "real_welfare_step", "exo_baroque_index"):
        assert required in d
