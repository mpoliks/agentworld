"""Tests for the CI-aware Sobol comparison harness.

Two contracts:

1. The four-way classifier maps `(s1, conf, s1', conf')` to the right
   transition class. We test the four corners explicitly so the
   `|S1| > S1_conf` rule cannot drift.
2. `compare_sobol_outputs` aligns metrics + parameters across summaries
   by *name* (not index), so a reordered summary stays consistent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _stub_summary(params: list[str], s1: list[float], conf: list[float]) -> dict:
    return {
        "problem": {"num_vars": len(params), "names": params, "bounds": []},
        "n_base_samples": 32,
        "n_simulations": 32 * (len(params) + 2),
        "n_steps": 4,
        "pairs_per_step": 100,
        "n_human_prototypes": 10,
        "n_agent_prototypes": 100,
        "parameter_bounds": [],
        "indices": [
            {
                "metric": "log_exo_baroque_index",
                "parameter_names": params,
                "S1": s1,
                "S1_conf": conf,
                "ST": s1,
                "ST_conf": conf,
            },
        ],
    }


def test_classifier_corners():
    from engine.sensitivity_compare import _classify, _transition

    assert _classify(0.10, 0.05) == "signal"   # |s1| > conf
    assert _classify(0.02, 0.05) == "noise"    # |s1| < conf
    assert _classify(-0.10, 0.05) == "signal"  # magnitude, not sign

    assert _transition(0.10, 0.05, 0.10, 0.05) == "signal_to_signal"
    assert _transition(0.10, 0.05, 0.02, 0.05) == "signal_to_noise"
    assert _transition(0.02, 0.05, 0.10, 0.05) == "noise_to_signal"
    assert _transition(0.02, 0.05, 0.02, 0.05) == "noise_to_noise"


def test_compare_two_counts_match_corners(tmp_path):
    from engine.sensitivity_compare import compare_two

    a = _stub_summary(
        params=["p1", "p2", "p3", "p4"],
        s1=[0.10, 0.10, 0.02, 0.02],
        conf=[0.05, 0.05, 0.05, 0.05],
    )
    b = _stub_summary(
        params=["p1", "p2", "p3", "p4"],
        s1=[0.10, 0.02, 0.10, 0.02],
        conf=[0.05, 0.05, 0.05, 0.05],
    )
    result = compare_two(a, b, label_a="A", label_b="B")
    assert result.counts == {
        "signal_to_signal": 1,
        "signal_to_noise": 1,
        "noise_to_signal": 1,
        "noise_to_noise": 1,
    }


def test_compare_two_aligns_by_param_name_not_index():
    from engine.sensitivity_compare import compare_two

    a = _stub_summary(
        params=["p1", "p2"],
        s1=[0.10, 0.02],
        conf=[0.05, 0.05],
    )
    # Same params, opposite order.
    b = _stub_summary(
        params=["p2", "p1"],
        s1=[0.02, 0.10],
        conf=[0.05, 0.05],
    )
    result = compare_two(a, b, label_a="A", label_b="B")
    # p1 is signal-to-signal, p2 is noise-to-noise — *regardless* of
    # the ordering in summary b.
    assert result.counts == {
        "signal_to_signal": 1,
        "signal_to_noise": 0,
        "noise_to_signal": 0,
        "noise_to_noise": 1,
    }


def test_compare_sobol_outputs_writes_pairwise_report(tmp_path):
    from engine.sensitivity_compare import (
        compare_sobol_outputs, write_comparison_report,
    )

    a = _stub_summary(["p1"], [0.10], [0.05])
    b = _stub_summary(["p1"], [0.10], [0.05])
    c = _stub_summary(["p1"], [0.02], [0.05])
    path_a = tmp_path / "a.json"
    path_b = tmp_path / "b.json"
    path_c = tmp_path / "c.json"
    path_a.write_text(json.dumps(a))
    path_b.write_text(json.dumps(b))
    path_c.write_text(json.dumps(c))

    report = compare_sobol_outputs([
        ("A", path_a),
        ("B", path_b),
        ("C", path_c),
    ])
    assert len(report.comparisons) == 2
    assert report.comparisons[0].label_a == "A"
    assert report.comparisons[0].label_b == "B"
    assert report.comparisons[1].label_a == "B"
    assert report.comparisons[1].label_b == "C"
    # B → C drops the signal.
    assert report.comparisons[1].counts["signal_to_noise"] == 1

    out = tmp_path / "report.json"
    write_comparison_report(report, out)
    reloaded = json.loads(out.read_text())
    assert len(reloaded["sources"]) == 3
    assert len(reloaded["comparisons"]) == 2


def test_real_legacy_to_percomp_comparison_runs():
    """Smoke test against the existing pinned legacy + percomp summaries.

    Skipped when either file is absent (e.g. a fresh checkout that
    hasn't run the Sobol round yet).
    """
    from engine.sensitivity_compare import compare_sobol_outputs

    legacy = REPO_ROOT / "outputs" / "sensitivity" / "sobol_indices.n2048.json"
    percomp = (
        REPO_ROOT / "outputs" / "sensitivity"
        / "sobol_indices.per_component.n2048.json"
    )
    if not legacy.exists() or not percomp.exists():
        pytest.skip("legacy or percomp n2048 Sobol artifact not present")

    report = compare_sobol_outputs([
        ("legacy_n2048", legacy),
        ("percomp_n2048", percomp),
    ])
    counts = report.comparisons[0].counts
    # Sanity: every (metric, param) is in exactly one of the four classes.
    assert sum(counts.values()) > 0
    for k in (
        "noise_to_noise", "signal_to_noise",
        "noise_to_signal", "signal_to_signal",
    ):
        assert k in counts
