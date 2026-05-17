"""Phase 1.1 — α-mapping contract.

The dashboard owns its own lever→α mapping at
`dashboard/sandbox/alpha_weights.json`. The mapping is hand-pinned
(static-knob α in the engine makes a Sobol regression degenerate;
see the JSON's rationale field). These tests are the CI tripwire
that catches accidental edits that break the spatial-sandbox
adversarial checks in §2.1 of `docs/plans/spatial-sandbox-completeness.md`:

  - Range coverage: best-corner α ≥ 0.85, worst-corner α ≤ 0.15.
  - Monotonicity: each non-zero-weight lever's sign matches the
    research-doc sign vector, swept across 8 steps with all other
    levers held at default.
  - Defaults reachability: α at every-lever-default sits inside
    [0.10, 0.90] (the mapping is bounded).
  - Forward compat: every plan-§3 lever has an entry, even if
    weight = 0 (Phase 4 controls slot in here).

These tests do not touch the engine. They replicate the same math
the JS-side `alpha_map.js` runs, against the same JSON file the
browser fetches.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


WEIGHTS_PATH = (
    Path(__file__).resolve().parents[2]
    / "dashboard"
    / "sandbox"
    / "alpha_weights.json"
)


def _load():
    with WEIGHTS_PATH.open() as f:
        return json.load(f)


def _map_alpha(state: dict, weights: dict) -> float:
    """Mirror of alpha_map.js `mapAlpha()`."""
    s = weights.get("baseline", 0.5)
    for key, cfg in weights["levers"].items():
        v = state.get(key)
        if not isinstance(v, (int, float)):
            continue
        rng = cfg["max"] - cfg["min"]
        if rng <= 0:
            continue
        norm = 2 * (v - cfg["min"]) / rng - 1
        s += cfg["sign"] * cfg["weight"] * norm
    for key, cfg in weights.get("categorical_levers", {}).items():
        v = state.get(key)
        if not isinstance(v, str):
            continue
        off = cfg.get("offsets", {}).get(v)
        if isinstance(off, (int, float)):
            s += off
    return max(0.0, min(1.0, s))


def test_range_coverage_best_and_worst_corners():
    """Range coverage: best-corner ≥ 0.85, worst-corner ≤ 0.15."""
    w = _load()
    best, worst = {}, {}
    for k, c in w["levers"].items():
        best[k]  = c["max"] if c["sign"] > 0 else c["min"]
        worst[k] = c["min"] if c["sign"] > 0 else c["max"]
    max_a = _map_alpha(best, w)
    min_a = _map_alpha(worst, w)
    assert max_a >= 0.85, f"best-corner α only reaches {max_a:.3f}"
    assert min_a <= 0.15, f"worst-corner α only reaches {min_a:.3f}"


def test_monotonicity_sign_vector_holds_per_lever():
    """Each non-zero-weight lever must move α in its declared direction
    across an 8-step sweep, with all other levers held at default.
    Tolerance: ≥7 of 8 transitions match the sign (clamping at the
    [0, 1] boundary takes the 8th)."""
    w = _load()
    defaults = {k: c["default"] for k, c in w["levers"].items()}
    failures = []
    for key, c in w["levers"].items():
        if c["weight"] == 0.0:
            continue
        state = dict(defaults)
        prev = _map_alpha(state, w)
        sign_correct = 0
        for i in range(1, 9):
            state[key] = c["min"] + (i / 8.0) * (c["max"] - c["min"])
            cur = _map_alpha(state, w)
            da = cur - prev
            if da == 0 or (da > 0) == (c["sign"] > 0):
                sign_correct += 1
            prev = cur
        if sign_correct < 7:
            failures.append((key, sign_correct, c["sign"]))
    assert not failures, (
        f"monotonicity violations: {failures}"
    )


def test_defaults_yield_interior_alpha():
    """α at every-lever-default must sit inside [0.10, 0.90]. A
    default that lands at a corner means the mapping is one
    slider-twitch away from clamping, which makes the gap diagnostic
    misleading."""
    w = _load()
    state = {k: c["default"] for k, c in w["levers"].items()}
    a = _map_alpha(state, w)
    assert 0.10 <= a <= 0.90, f"α at defaults = {a:.3f} (outside [0.10, 0.90])"


def test_forward_compat_full_lever_inventory():
    """Every plan-§3 lever from spatial-sandbox-completeness.md §5
    must appear with an entry (weight may be 0). When Phase 4 lands
    the missing UI controls, the JSON already knows the lever's sign
    and range."""
    w = _load()
    levers = set(w["levers"].keys()) | set(w.get("categorical_levers", {}).keys())
    expected = {
        # 6 implemented today
        "market_layer_tax",
        "pigouvian.tax_rate",
        "pigouvian.recycling_progressivity",
        "compute.budget_per_tick",
        "compute.power_cost_per_trade",
        "cross_stack_permeability",
        # 7 agentic (plan §5)
        "agent_capability_mean",
        "norms.certified_fraction",
        "network_model",
        "network_p_local",
        "agent_autonomy_mean",
        "norms.update_rate",
        "agent_trade_rate_multiplier",
        # 5 legal
        "law.strength",
        "folding.max_depth",
        "law.transaction_size_cap",
        "regulator.enabled",
        "pigouvian.recycling",
        # 2 environmental
        "compute.distribution",
        "scale_preset",
    }
    missing = expected - levers
    assert not missing, f"missing lever entries: {sorted(missing)}"


def test_clamp_bounds_at_extremes():
    """Beyond-range slider values clamp to [0, 1]."""
    w = _load()
    # Hand a value 10× the max for every lever — should still clamp
    # at 1.0, not overflow.
    state = {k: c["max"] * 10 for k, c in w["levers"].items() if c["max"] > 0}
    a = _map_alpha(state, w)
    assert 0.0 <= a <= 1.0


def test_signs_match_research_doc_intent():
    """A pinned-sign check: each implemented lever has the sign the
    research docs assign. Catches accidental sign flips when the JSON
    is hand-edited."""
    w = _load()
    expected_signs = {
        "market_layer_tax":                  -1,
        "pigouvian.tax_rate":                -1,
        "pigouvian.recycling_progressivity": -1,
        "compute.budget_per_tick":            1,
        "compute.power_cost_per_trade":      -1,
        "cross_stack_permeability":           1,
        "agent_capability_mean":             -1,
        "norms.certified_fraction":          -1,
        "law.strength":                      -1,
        "folding.max_depth":                  1,
        "law.transaction_size_cap":          -1,
        "regulator.enabled":                 -1,
    }
    for k, want in expected_signs.items():
        got = w["levers"][k]["sign"]
        assert got == want, f"{k}: sign={got} (want {want})"
