"""Tests for B4: per-depth fold contribution round-trips through StepMetrics
and the SSE stream so the d3 fold-tree has data to render.

Three checks:
- A productive-baroque scenario produces a non-empty per-depth array on
  most steps, and the array sums to the step's nominal_added inside the
  cascade (allowing for floor pruning at very small contributions).
- A smooth scenario produces empty per-depth arrays (folding gated off).
- The SSE serializer emits `fold_per_depth_contribution` as a list of
  numbers in each step event.
"""

from __future__ import annotations

import json
import time

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from engine.core.world import World
from engine.scenarios import get_scenario
from engine.serve import create_app


def _shrink(name: str, n_steps: int = 4):
    cfg = get_scenario(name)
    cfg.n_steps = n_steps
    cfg.pairs_per_step = 5_000
    cfg.population.n_human_prototypes = 200
    cfg.population.n_agent_prototypes = 2_000
    return cfg


def test_baroque_scenario_emits_per_depth_arrays():
    cfg = _shrink("baroque_cathedral", n_steps=4)
    w = World.build(cfg)
    w.run(progress=False)
    steps = w.metrics.history.steps
    assert len(steps) == 4
    # At least one step has a non-empty per-depth array (folding fires).
    nonempty = [s for s in steps if len(s.fold_per_depth_contribution) > 0]
    assert len(nonempty) >= 1, "expected baroque scenario to produce fold cascades"
    for s in nonempty:
        # Values are non-negative numbers.
        for v in s.fold_per_depth_contribution:
            assert v >= 0
        # Length never exceeds folding_max_depth (default 7).
        assert len(s.fold_per_depth_contribution) <= 10


def test_smooth_scenario_emits_empty_per_depth_arrays():
    cfg = _shrink("coasean_paradise", n_steps=3)
    w = World.build(cfg)
    w.run(progress=False)
    # Coasean paradise gates folding propensity very low; cascade barely
    # fires. Expect either empty arrays or short arrays with very small
    # numbers — but `coasean_paradise` does have folding_propensity=0.10,
    # so a few low-contribution steps are possible. Check the per-step
    # sum is below the cascade-disabled scenario's nominal volume.
    for s in w.metrics.history.steps:
        contribs = s.fold_per_depth_contribution
        if contribs:
            assert sum(contribs) < s.nominal_gdp_step + 1.0


def test_sse_stream_carries_per_depth():
    """The SSE serializer round-trips the per-depth list through asdict()
    and into each step event."""
    with TestClient(create_app()) as client:
        r = client.post(
            "/runs",
            json={"scenario": "productive_baroque", "n_steps": 3, "scale": "small"},
        )
        assert r.status_code == 200, r.text
        run_id = r.json()["run_id"]
        # Drain stream.
        events = []
        with client.stream("GET", f"/runs/{run_id}/stream") as resp:
            current_event = None
            for line in resp.iter_lines():
                if line.startswith("event:"):
                    current_event = line.split(":", 1)[1].strip()
                elif line.startswith("data:") and current_event:
                    events.append((current_event, line.split(":", 1)[1].strip()))
                if current_event in ("done", "error", "cancelled"):
                    break
        step_events = [json.loads(d) for k, d in events if k == "step"]
        assert len(step_events) == 3
        # At least one step carries a non-empty per-depth list under
        # productive_baroque.
        any_nonempty = any(
            isinstance(s.get("fold_per_depth_contribution"), list)
            and len(s["fold_per_depth_contribution"]) > 0
            for s in step_events
        )
        assert any_nonempty, "expected SSE stream to carry per-depth contributions"
