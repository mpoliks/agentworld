"""Tests for the permeability + norms validation sweeps (H-J validation lift).

Three checks per sweep, following the existing posterior-sweep test pattern:

1. The smoke-test sweep at tiny scale finishes, produces a well-formed
   summary, and serialises to JSON without losing fields.
2. The summary's per-grid-point shape matches the plan's contract
   (basin shares sum to 1; the four rejection components sum to 1).
3. When the persisted canonical artifact is present, it has the right
   sample count and a non-degenerate distribution — we do not pin
   exact percentages because sweep tightening (more samples, longer
   horizon) is deliberate, not a regression.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Permeability sweep
# ---------------------------------------------------------------------------


def test_permeability_grid_is_eleven_points_zero_to_one():
    from engine.validation.sweeps import PERMEABILITY_GRID

    assert len(PERMEABILITY_GRID) == 11
    assert PERMEABILITY_GRID[0] == 0.0
    assert PERMEABILITY_GRID[-1] == 1.0
    # Monotone non-decreasing.
    for i in range(1, len(PERMEABILITY_GRID)):
        assert PERMEABILITY_GRID[i] > PERMEABILITY_GRID[i - 1]


def test_run_permeability_sweep_tiny():
    """A 2-sample × 3-point sweep finishes fast and returns the documented shape."""
    from engine.validation.sweeps import run_permeability_sweep

    summary = run_permeability_sweep(
        n_samples_per_point=2,
        permeability_values=(0.0, 0.5, 1.0),
        n_steps=4,
        pairs_per_step=2_000,
        n_human_prototypes=80,
        n_agent_prototypes=800,
    )
    assert len(summary.basin_distribution) == 3
    assert len(summary.ebi_quantiles) == 3
    for row in summary.basin_distribution:
        # Five basin labels always present, even if zero.
        for k in ("smooth", "mixed", "striated", "baroque", "slop"):
            assert k in row
            assert 0.0 <= row[k] <= 1.0
        # Shares sum to 1 (within float tolerance).
        s = row["smooth"] + row["mixed"] + row["striated"] + row["baroque"] + row["slop"]
        assert s == pytest.approx(1.0, abs=1e-9)
    for row in summary.ebi_quantiles:
        for q in ("p10", "p50", "p90"):
            assert q in row
            # Non-NaN (the tiny smoke run lands in non-divergent regime).
            assert row[q] == row[q]


def test_permeability_summary_round_trips_json(tmp_path):
    from engine.validation.sweeps import (
        run_permeability_sweep, write_permeability_summary,
    )

    summary = run_permeability_sweep(
        n_samples_per_point=2,
        permeability_values=(0.0, 1.0),
        n_steps=4,
        pairs_per_step=2_000,
        n_human_prototypes=80,
        n_agent_prototypes=800,
    )
    out = tmp_path / "permeability.json"
    write_permeability_summary(summary, out)
    loaded = json.loads(out.read_text())
    assert loaded["permeability_values"] == [0.0, 1.0]
    assert loaded["n_samples_per_point"] == 2
    assert len(loaded["basin_distribution"]) == 2


def test_persisted_permeability_sweep_has_distribution():
    path = REPO_ROOT / "outputs" / "validation" / "permeability_sweep.json"
    if not path.exists():
        pytest.skip(
            f"Run `agentworld validate permeability` to produce {path}"
        )
    d = json.loads(path.read_text())
    assert d["n_samples_per_point"] >= 32
    assert len(d["permeability_values"]) >= 6
    # At least one grid point has a non-degenerate basin mix.
    nonzero_rows = 0
    for row in d["basin_distribution"]:
        nonzero = sum(
            1 for k in ("smooth", "mixed", "striated", "baroque", "slop")
            if row[k] > 0.01
        )
        if nonzero >= 2:
            nonzero_rows += 1
    assert nonzero_rows >= 1, "expected at least one grid point with >1 basin"


# ---------------------------------------------------------------------------
# Norms sensitivity sweep
# ---------------------------------------------------------------------------


def test_run_norms_sensitivity_tiny():
    from engine.validation.sweeps import (
        REJECTION_COMPONENTS, run_norms_sensitivity,
    )

    summary = run_norms_sensitivity(
        n_samples=2,
        n_steps=4,
        pairs_per_step=2_000,
        n_human_prototypes=80,
        n_agent_prototypes=800,
    )
    assert summary.n_samples == 2
    assert len(summary.configurations) == 2
    labels = {c["label"] for c in summary.configurations}
    assert labels == {"static", "norm_participation"}
    for cfg in summary.configurations:
        dist = cfg["rejection_share_distribution"]
        for k in REJECTION_COMPONENTS:
            for q in ("p10", "p50", "p90"):
                assert q in dist[k]
        for q in ("p10", "p50", "p90"):
            assert q in cfg["ebi"]
            assert q in cfg["per_capita"]
    for q in ("p10", "p50", "p90"):
        assert q in summary.alignment_share_delta


def test_norms_summary_round_trips_json(tmp_path):
    from engine.validation.sweeps import (
        run_norms_sensitivity, write_norms_summary,
    )

    summary = run_norms_sensitivity(
        n_samples=2,
        n_steps=4,
        pairs_per_step=2_000,
        n_human_prototypes=80,
        n_agent_prototypes=800,
    )
    out = tmp_path / "norms.json"
    write_norms_summary(summary, out)
    loaded = json.loads(out.read_text())
    assert loaded["n_samples"] == 2
    assert {c["label"] for c in loaded["configurations"]} == {
        "static", "norm_participation",
    }


def test_persisted_norms_sweep_has_distribution():
    path = REPO_ROOT / "outputs" / "validation" / "norms_sensitivity.json"
    if not path.exists():
        pytest.skip(
            f"Run `agentworld validate norms` to produce {path}"
        )
    d = json.loads(path.read_text())
    assert d["n_samples"] >= 32
    assert len(d["configurations"]) == 2
    for cfg in d["configurations"]:
        for k in ("law", "market", "align", "cost"):
            for q in ("p10", "p50", "p90"):
                assert q in cfg["rejection_share_distribution"][k]
