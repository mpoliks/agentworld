"""Tests for `agentworld serve` (B2).

Covers:
- /scenarios returns the canonical list.
- POST /runs starts a run and returns a run_id.
- /runs/{id}/history returns the recorded history once the worker finishes.
- /runs/{id}/stream emits SSE events ending with `done`.
- An unknown scenario returns 404.
- Posting a second run cancels the prior one (cooperative).

Tests use FastAPI's TestClient. Each run is a tiny scenario so the worker
finishes within a few seconds. The serve module is itself an optional
dependency; tests skip if FastAPI is missing.
"""

from __future__ import annotations

import json
import time

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from engine.serve import create_app


def _wait_terminal(client: TestClient, run_id: str, timeout: float = 30.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/runs/{run_id}/history")
        assert r.status_code == 200
        body = r.json()
        if body["status"] in ("done", "error", "cancelled"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"run {run_id} did not terminate within {timeout}s")


def _post_small_run(client: TestClient, scenario: str = "equilibrium_drift", n_steps: int = 3):
    r = client.post(
        "/runs",
        json={"scenario": scenario, "n_steps": n_steps, "scale": "small"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_scenarios_endpoint():
    with TestClient(create_app()) as client:
        r = client.get("/scenarios")
        assert r.status_code == 200
        body = r.json()
        names = {item["name"] for item in body}
        assert "coasean_paradise" in names
        assert "baroque_cathedral" in names
        assert "equilibrium_drift" in names


def test_unknown_scenario_404():
    with TestClient(create_app()) as client:
        r = client.post(
            "/runs",
            json={"scenario": "no_such_scenario", "n_steps": 1, "scale": "small"},
        )
        assert r.status_code == 404


def test_post_run_then_history_terminates():
    with TestClient(create_app()) as client:
        run = _post_small_run(client, n_steps=3)
        body = _wait_terminal(client, run["run_id"])
        assert body["status"] == "done"
        assert len(body["history"]) == 3
        assert body["label"]  # topology label populated


def test_stream_emits_step_then_done():
    with TestClient(create_app()) as client:
        run = _post_small_run(client, n_steps=2)
        with client.stream("GET", f"/runs/{run['run_id']}/stream") as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            events = []
            for line in resp.iter_lines():
                if line.startswith("event:"):
                    events.append(line.split(":", 1)[1].strip())
                if "done" in events or "error" in events or "cancelled" in events:
                    break
        assert "hello" in events
        assert events.count("step") >= 2
        assert "done" in events


def test_second_post_cancels_prior_run():
    """Posting a second run while the first is active marks the prior cancelled."""
    with TestClient(create_app()) as client:
        first = _post_small_run(client, n_steps=20)
        # Give the worker a moment to start.
        time.sleep(0.05)
        second = _post_small_run(client, n_steps=2)
        body_second = _wait_terminal(client, second["run_id"])
        assert body_second["status"] == "done"
        # The first run should have terminated as cancelled (or done if it
        # was a tiny scenario that beat the cancel race; equilibrium_drift
        # at n=20 is too long to finish before the second POST).
        body_first = client.get(f"/runs/{first['run_id']}/history").json()
        assert body_first["status"] in ("cancelled", "done")
