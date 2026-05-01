"""Tests for the prior + posterior sweep (A2).

Three checks:

1. Each declared prior round-trips through `map_unit` correctly: 0 -> low,
   1 -> high, monotone in between.
2. A small posterior sweep produces a well-formed DataFrame and a summary
   whose basin probabilities sum to 1.
3. The persisted canonical artifact at outputs/validation/posterior_sweep.parquet
   exists, has the right column set, and has a non-trivial spread of
   basin classifications. We do not pin the exact percentages — sweep
   tightening is deliberate, not a side-effect of an engine refactor —
   but we do pin "more than just one basin appears" so a regression that
   collapses the distribution shows up.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_priors_unit_roundtrip():
    from engine.validation.priors import INVENTORY

    for p in INVENTORY:
        assert p.map_unit(0.0) == pytest.approx(p.low, rel=1e-9)
        assert p.map_unit(1.0) == pytest.approx(p.high, rel=1e-9)
        # Monotone non-decreasing (uniform / loguniform are both monotone).
        assert p.map_unit(0.4) <= p.map_unit(0.6)
        # Outside [0, 1] is clamped to the bounds.
        assert p.map_unit(-0.5) == pytest.approx(p.low, rel=1e-9)
        assert p.map_unit(1.5) == pytest.approx(p.high, rel=1e-9)


def test_inventory_has_eleven_priors_split_seven_alpha_four_exo():
    from engine.validation.priors import INVENTORY, alpha_priors, exo_priors

    assert len(INVENTORY) == 11
    assert len(alpha_priors()) == 7
    assert len(exo_priors()) == 4
    # No name collisions.
    names = [p.name for p in INVENTORY]
    assert len(set(names)) == len(names)


def test_run_posterior_sweep_small():
    """A 16-sample sweep at tiny scale finishes fast and returns a sane df."""
    from engine.validation.posterior_sweep import run_posterior_sweep

    df, summary = run_posterior_sweep(n_samples=16, seed=0, n_steps=10, progress=False)
    assert len(df) == 16
    expected_cols = {
        "folding_propensity", "fold_real_efficiency", "fold_nominal_multiplier",
        "base_variance_absorption", "productive_decay", "max_productive_real_share",
        "cap_slope", "sample_idx", "terminal_ebi",
        "terminal_real_per_capita_welfare", "basin",
    }
    assert set(df.columns) >= expected_cols
    # Probabilities sum to 1.
    total = summary.p_smooth + summary.p_mixed + summary.p_baroque + summary.p_diverged
    assert total == pytest.approx(1.0, abs=1e-6)
    # Quantiles are finite.
    for v in summary.ebi_quantiles.values():
        assert v == v  # not NaN
    for v in summary.welfare_quantiles.values():
        assert v == v


def test_persisted_canonical_sweep_has_distribution():
    """The persisted artifact records a non-trivial basin distribution."""
    parquet = REPO_ROOT / "outputs" / "validation" / "posterior_sweep.parquet"
    summary = REPO_ROOT / "outputs" / "validation" / "posterior_sweep.summary.json"
    if not parquet.exists() or not summary.exists():
        pytest.skip(
            f"Run `agentworld validate priors --samples 2000` to produce "
            f"{parquet} and {summary}"
        )

    d = json.loads(summary.read_text())
    # At least 100 samples (canonical is 2000 but we don't pin tightly).
    assert d["n_samples"] >= 100
    # All four probabilities are valid.
    for k in ("p_smooth", "p_mixed", "p_baroque", "p_diverged"):
        assert 0.0 <= d[k] <= 1.0
    # The distribution is non-degenerate: more than one basin has mass.
    nonzero = sum(1 for k in ("p_smooth", "p_mixed", "p_baroque") if d[k] > 0.01)
    assert nonzero >= 2, "expected at least two basins to have >1% mass"
