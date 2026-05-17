"""Tests for the live-engine extensions to `agentworld serve` (S1).

Covers:
- /scenarios/families returns the seven-family taxonomy.
- /parameter_meta returns the eight live parameter records.
- /sobol_indices returns S1/ST per parameter for the requested metric.
- POST /runs with overrides applies the patch and propagates to StepMetrics.
- POST /runs with overrides rejects unknown keys (400).
- POST /runs with overrides rejects out-of-bounds values (400).
- POST /runs with extend_bounds=True allows out-of-bounds values.
- POST /runs with family validates scenario ↔ family agreement.
- POST /runs with alpha_schedule of the right length is accepted.
- POST /runs with mis-sized alpha_schedule is rejected (400).
- POST /runs with alpha_schedule values outside [0, 1] is rejected (400).
"""

from __future__ import annotations

import time

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from engine.serve import create_app, _apply_overrides, OverrideError
from engine.core.world import WorldConfig


# ---- helpers --------------------------------------------------------------


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


# ---- /scenarios/families --------------------------------------------------


def test_families_endpoint_returns_seven_families():
    with TestClient(create_app()) as client:
        r = client.get("/scenarios/families")
        assert r.status_code == 200
        body = r.json()
        ids = [fam["id"] for fam in body]
        assert ids == [
            "alpha_baseline",
            "demand_intermediation",
            "dynamic_law",
            "pigouvian",
            "emergent_strategy",
            "mission_economy",
            "norms_layer",
        ]


def test_families_endpoint_lists_scenarios_per_family():
    with TestClient(create_app()) as client:
        r = client.get("/scenarios/families")
        assert r.status_code == 200
        by_id = {fam["id"]: fam for fam in r.json()}
        assert "coasean_paradise" in by_id["alpha_baseline"]["scenarios"]
        assert "pigouvian_heavy" in by_id["pigouvian"]["scenarios"]
        assert "norms_drift" in by_id["norms_layer"]["scenarios"]
        # _anchored variants inherit family membership.
        anchored = by_id["alpha_baseline"]["scenarios"]
        assert any(n.endswith("_anchored") for n in anchored)


# ---- /parameter_meta ------------------------------------------------------


def test_parameter_meta_returns_eight_parameters():
    with TestClient(create_app()) as client:
        r = client.get("/parameter_meta")
        assert r.status_code == 200
        body = r.json()
        names = [p["name"] for p in body["parameters"]]
        assert names == [
            "alpha",
            "agent_capability_mean",
            "folding_propensity",
            "base_variance_absorption",
            "folding_branching",
            "base_friction",
            "max_productive_real_share",
            "fold_nominal_multiplier",
        ]


def test_parameter_meta_includes_bounds_and_gloss():
    with TestClient(create_app()) as client:
        r = client.get("/parameter_meta")
        assert r.status_code == 200
        by_name = {p["name"]: p for p in r.json()["parameters"]}
        alpha = by_name["alpha"]
        assert alpha["sobol_min"] == 0.05
        assert alpha["sobol_max"] == 0.95
        assert alpha["tooltip"]
        assert alpha["help"]
        assert alpha["mean_abs_st"] > 0


# ---- /sobol_indices -------------------------------------------------------


def test_sobol_indices_default_metric():
    with TestClient(create_app()) as client:
        r = client.get("/sobol_indices")
        assert r.status_code == 200
        body = r.json()
        assert body["metric"] == "log_exo_baroque_index"
        assert "alpha" in body["parameter_names"]
        assert len(body["S1"]) == len(body["parameter_names"])
        assert len(body["ST"]) == len(body["parameter_names"])


def test_sobol_indices_specific_metric():
    with TestClient(create_app()) as client:
        r = client.get("/sobol_indices", params={"metric": "real_per_capita_welfare"})
        assert r.status_code == 200
        body = r.json()
        assert body["metric"] == "real_per_capita_welfare"


def test_sobol_indices_unknown_metric_404():
    with TestClient(create_app()) as client:
        r = client.get("/sobol_indices", params={"metric": "no_such_metric"})
        assert r.status_code == 404


# ---- _apply_overrides (pure-function tests) -------------------------------


def test_apply_overrides_writes_to_correct_subconfig():
    cfg = WorldConfig()
    _apply_overrides(cfg, {"alpha": 0.7, "agent_capability_mean": 0.8})
    assert cfg.topology.alpha == 0.7
    assert cfg.population.agent_capability_mean == 0.8


def test_apply_overrides_writes_world_top_level():
    cfg = WorldConfig()
    _apply_overrides(cfg, {"pairs_per_step": 1000})
    assert cfg.pairs_per_step == 1000


def test_apply_overrides_rejects_unknown_key():
    cfg = WorldConfig()
    with pytest.raises(OverrideError):
        _apply_overrides(cfg, {"no_such_field": 1.0})


def test_apply_overrides_rejects_out_of_bounds():
    cfg = WorldConfig()
    with pytest.raises(OverrideError):
        _apply_overrides(cfg, {"alpha": 0.99})  # above sobol_max 0.95
    with pytest.raises(OverrideError):
        _apply_overrides(cfg, {"alpha": 0.01})  # below sobol_min 0.05


def test_apply_overrides_extend_bounds_allows_out_of_box():
    cfg = WorldConfig()
    _apply_overrides(cfg, {"alpha": 0.99}, extend_bounds=True)
    assert cfg.topology.alpha == 0.99


# ---- POST /runs override integration -------------------------------------


def test_post_run_with_overrides_round_trips():
    with TestClient(create_app()) as client:
        r = client.post(
            "/runs",
            json={
                "scenario": "equilibrium_drift",
                "n_steps": 2,
                "scale": "small",
                "overrides": {"alpha": 0.8, "folding_propensity": 0.4},
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["overrides"]["alpha"] == 0.8
        body = _wait_terminal(client, body["run_id"])
        assert body["status"] == "done"
        # The patched alpha shows up in the per-step metrics.
        last = body["history"][-1]
        assert abs(last["alpha"] - 0.8) < 1e-9


def test_post_run_with_unknown_override_400():
    with TestClient(create_app()) as client:
        r = client.post(
            "/runs",
            json={
                "scenario": "equilibrium_drift",
                "n_steps": 2,
                "scale": "small",
                "overrides": {"no_such_field": 1.0},
            },
        )
        assert r.status_code == 400
        assert "no_such_field" in r.json()["detail"]


def test_post_run_with_out_of_bounds_override_400():
    with TestClient(create_app()) as client:
        r = client.post(
            "/runs",
            json={
                "scenario": "equilibrium_drift",
                "n_steps": 2,
                "scale": "small",
                "overrides": {"alpha": 0.99},
            },
        )
        assert r.status_code == 400
        assert "Sobol bounds" in r.json()["detail"]


def test_post_run_with_extend_bounds_allows_out_of_box():
    with TestClient(create_app()) as client:
        r = client.post(
            "/runs",
            json={
                "scenario": "equilibrium_drift",
                "n_steps": 2,
                "scale": "small",
                "overrides": {"alpha": 0.99},
                "extend_bounds": True,
            },
        )
        assert r.status_code == 200, r.text


# ---- family validation ---------------------------------------------------


def test_post_run_with_matching_family_accepted():
    with TestClient(create_app()) as client:
        r = client.post(
            "/runs",
            json={
                "scenario": "coasean_paradise",
                "n_steps": 2,
                "scale": "small",
                "family": "alpha_baseline",
            },
        )
        assert r.status_code == 200, r.text


def test_post_run_with_mismatched_family_400():
    with TestClient(create_app()) as client:
        r = client.post(
            "/runs",
            json={
                "scenario": "coasean_paradise",
                "n_steps": 2,
                "scale": "small",
                "family": "pigouvian",
            },
        )
        assert r.status_code == 400
        assert "alpha_baseline" in r.json()["detail"]


def test_post_run_with_unknown_family_400():
    with TestClient(create_app()) as client:
        r = client.post(
            "/runs",
            json={
                "scenario": "coasean_paradise",
                "n_steps": 2,
                "scale": "small",
                "family": "no_such_family",
            },
        )
        assert r.status_code == 400


# ---- alpha_schedule -------------------------------------------------------


def test_post_run_with_alpha_schedule_round_trips():
    n_steps = 3
    schedule = [0.2, 0.5, 0.8]
    with TestClient(create_app()) as client:
        r = client.post(
            "/runs",
            json={
                "scenario": "equilibrium_drift",
                "n_steps": n_steps,
                "scale": "small",
                "alpha_schedule": schedule,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["alpha_schedule_len"] == n_steps
        body = _wait_terminal(client, body["run_id"])
        assert body["status"] == "done"
        alphas = [h["alpha"] for h in body["history"]]
        # World.run applies alpha_schedule[i] at step i; check the
        # final-step alpha matches the schedule's final value.
        assert abs(alphas[-1] - schedule[-1]) < 1e-9


def test_post_run_with_wrong_length_alpha_schedule_400():
    with TestClient(create_app()) as client:
        r = client.post(
            "/runs",
            json={
                "scenario": "equilibrium_drift",
                "n_steps": 3,
                "scale": "small",
                "alpha_schedule": [0.2, 0.5],
            },
        )
        assert r.status_code == 400
        assert "length" in r.json()["detail"]


def test_post_run_with_out_of_range_alpha_schedule_400():
    with TestClient(create_app()) as client:
        r = client.post(
            "/runs",
            json={
                "scenario": "equilibrium_drift",
                "n_steps": 2,
                "scale": "small",
                "alpha_schedule": [0.5, 1.2],
            },
        )
        assert r.status_code == 400


# ---- V2 pair sampling round-trip -----------------------------------------


def test_post_run_with_pair_sample_k_round_trips():
    """`pair_sample_k = K` POSTs the value through to the worker and
    PairSample records show up in StepMetrics history."""
    with TestClient(create_app()) as client:
        r = client.post(
            "/runs",
            json={
                "scenario": "equilibrium_drift",
                "n_steps": 2,
                "scale": "small",
                "pair_sample_k": 25,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["pair_sample_k"] == 25
        body = _wait_terminal(client, body["run_id"])
        assert body["status"] == "done"
        # Each StepMetrics carries K pair_samples records.
        for step in body["history"]:
            assert len(step["pair_samples"]) == 25
            rec = step["pair_samples"][0]
            assert "proto_a" in rec
            assert "executed" in rec
            assert "reject_reason" in rec


def test_post_run_pair_sample_k_zero_emits_empty_lists():
    with TestClient(create_app()) as client:
        r = client.post(
            "/runs",
            json={
                "scenario": "equilibrium_drift",
                "n_steps": 2,
                "scale": "small",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["pair_sample_k"] == 0
        body = _wait_terminal(client, body["run_id"])
        for step in body["history"]:
            assert step["pair_samples"] == []


# ---- dotted-key overrides for nested configs ------------------------------


def test_apply_overrides_dotted_key_reaches_nested_config():
    cfg = WorldConfig()
    _apply_overrides(cfg, {"pigouvian.tax_rate": 0.42}, extend_bounds=True)
    assert cfg.topology.pigouvian.tax_rate == 0.42


def test_apply_overrides_dotted_key_recycling_progressivity():
    cfg = WorldConfig()
    _apply_overrides(cfg, {"pigouvian.recycling_progressivity": 2.5}, extend_bounds=True)
    assert cfg.topology.pigouvian.recycling_progressivity == 2.5


def test_apply_overrides_dotted_key_unknown_head_rejected():
    cfg = WorldConfig()
    with pytest.raises(OverrideError, match="not a nested config"):
        _apply_overrides(cfg, {"nope.something": 1.0}, extend_bounds=True)


def test_apply_overrides_dotted_key_unknown_tail_rejected():
    cfg = WorldConfig()
    with pytest.raises(OverrideError, match="not a field"):
        _apply_overrides(cfg, {"pigouvian.does_not_exist": 1.0}, extend_bounds=True)


def test_apply_overrides_dotted_key_deeper_nesting_rejected():
    cfg = WorldConfig()
    with pytest.raises(OverrideError, match="only one level"):
        _apply_overrides(cfg, {"pigouvian.something.deeper": 1.0}, extend_bounds=True)


def test_update_endpoint_accepts_pigouvian_tax_rate():
    with TestClient(create_app()) as client:
        r = client.post(
            "/runs",
            json={"scenario": "spatial_sandbox", "n_steps": 0, "scale": "small", "cast_size": 50, "pair_sample_k": 50},
        )
        assert r.status_code == 200, r.text
        run_id = r.json()["run_id"]
        u = client.post(
            f"/runs/{run_id}/update",
            json={"overrides": {"pigouvian.tax_rate": 0.30}},
        )
        assert u.status_code == 200, u.text
        client.post(f"/runs/{run_id}/cancel")


def test_update_endpoint_rejects_unwhitelisted_nested_key():
    with TestClient(create_app()) as client:
        r = client.post(
            "/runs",
            json={"scenario": "spatial_sandbox", "n_steps": 0, "scale": "small", "cast_size": 50, "pair_sample_k": 50},
        )
        assert r.status_code == 200
        run_id = r.json()["run_id"]
        u = client.post(
            f"/runs/{run_id}/update",
            json={"overrides": {"pigouvian.enabled": False}},
        )
        assert u.status_code == 400
        assert "not live-tunable" in u.json()["detail"]
        client.post(f"/runs/{run_id}/cancel")


# ---- additional live-tunable knobs ----------------------------------------


def test_update_endpoint_accepts_cross_stack_permeability():
    with TestClient(create_app()) as client:
        r = client.post(
            "/runs",
            json={"scenario": "spatial_sandbox", "n_steps": 0, "scale": "small", "cast_size": 50, "pair_sample_k": 50},
        )
        assert r.status_code == 200
        run_id = r.json()["run_id"]
        u = client.post(
            f"/runs/{run_id}/update",
            json={"overrides": {"cross_stack_permeability": 0.7}},
        )
        assert u.status_code == 200, u.text
        client.post(f"/runs/{run_id}/cancel")


def test_update_endpoint_accepts_compute_budget_per_tick():
    with TestClient(create_app()) as client:
        r = client.post(
            "/runs",
            json={"scenario": "spatial_sandbox", "n_steps": 0, "scale": "small", "cast_size": 50, "pair_sample_k": 50},
        )
        assert r.status_code == 200
        run_id = r.json()["run_id"]
        u = client.post(
            f"/runs/{run_id}/update",
            json={"overrides": {"compute.budget_per_tick": 2.5}},
        )
        assert u.status_code == 200, u.text
        client.post(f"/runs/{run_id}/cancel")


def test_update_endpoint_accepts_compute_power_cost_per_trade():
    with TestClient(create_app()) as client:
        r = client.post(
            "/runs",
            json={"scenario": "spatial_sandbox", "n_steps": 0, "scale": "small", "cast_size": 50, "pair_sample_k": 50},
        )
        assert r.status_code == 200
        run_id = r.json()["run_id"]
        u = client.post(
            f"/runs/{run_id}/update",
            json={"overrides": {"compute.power_cost_per_trade": 0.0005}},
        )
        assert u.status_code == 200, u.text
        client.post(f"/runs/{run_id}/cancel")


def test_apply_overrides_compute_dotted_key():
    cfg = WorldConfig()
    _apply_overrides(cfg, {"compute.budget_per_tick": 2.5}, extend_bounds=True)
    assert cfg.topology.compute.budget_per_tick == 2.5
    _apply_overrides(cfg, {"compute.power_cost_per_trade": 0.0005}, extend_bounds=True)
    assert cfg.topology.compute.power_cost_per_trade == 0.0005
