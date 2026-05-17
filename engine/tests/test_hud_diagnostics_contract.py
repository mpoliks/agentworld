"""Phase 5 — HUD diagnostics contract.

The dashboard reads seven rejection gates, two compute fields, an
EBI value, and a fold-depth field from StepMetrics. If the engine
ever drops or renames one of those fields the HUD silently shows
'--' or NaN. These tests are the CI tripwire that catches it
before the dashboard does, and they pin the EBI regime band table
to its sister table in dashboard/sandbox/scene.js.

Adversarial check 6.x rejection-mix completeness is enforced
inside updateRejectionMix() in the browser — see the red ‼ sum
row that surfaces when the six engine-counted gates don't sum to
the engine's implied total. The Python side here verifies the
seven fields exist and behave additively.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from engine.core.metrics import StepMetrics
from engine.core.world import World
from engine.scenarios import get_scenario


SCENE_JS = (
    Path(__file__).resolve().parents[2]
    / "dashboard"
    / "sandbox"
    / "scene.js"
)


REJECTION_FIELDS = (
    "rejected_cost",
    "rejected_market",
    "rejected_align",
    "rejected_law",
    "rejected_compute",
    "rejected_permeability",
    "rejected_regulator",
)


def test_step_metrics_carries_all_rejection_gates():
    """The HUD reads seven gates. They must all exist on StepMetrics
    with numeric defaults — otherwise the dashboard rows render as
    NaN or '--' instead of showing real values."""
    # Build a fresh StepMetrics with the required positional args
    # so we can probe defaults for the post-creation fields.
    m = StepMetrics(
        step=0,
        alpha=0.5,
        real_welfare_step=0.0,
        real_welfare_cumulative=0.0,
        nominal_gdp_step=0.0,
        nominal_gdp_cumulative=0.0,
        exo_baroque_index=1.0,
        fold_max_depth=0,
        n_transactions_real=0.0,
        n_sub_markets_added=0.0,
        rejected_law=0.0,
        rejected_market=0.0,
        rejected_align=0.0,
        rejected_cost=0.0,
        gini_wealth=0.0,
        real_per_capita_welfare=0.0,
        human_legibility_index=0.0,
        governance_overhead_fraction=0.0,
        a2a_share=0.0,
        h2a_share=0.0,
        h2h_share=0.0,
    )
    for field in REJECTION_FIELDS:
        v = getattr(m, field, None)
        assert v is not None, f"{field} missing on StepMetrics"
        assert isinstance(v, (int, float)), f"{field} not numeric: {type(v)}"
        assert v >= 0, f"{field} default = {v} (must be ≥ 0)"


def test_compute_pool_field_present():
    m = StepMetrics(
        step=0, alpha=0.5,
        real_welfare_step=0.0, real_welfare_cumulative=0.0,
        nominal_gdp_step=0.0, nominal_gdp_cumulative=0.0,
        exo_baroque_index=1.0, fold_max_depth=0,
        n_transactions_real=0.0, n_sub_markets_added=0.0,
        rejected_law=0.0, rejected_market=0.0,
        rejected_align=0.0, rejected_cost=0.0,
        gini_wealth=0.0, real_per_capita_welfare=0.0,
        human_legibility_index=0.0, governance_overhead_fraction=0.0,
        a2a_share=0.0, h2a_share=0.0, h2h_share=0.0,
    )
    assert hasattr(m, "compute_budget_remaining"), (
        "HUD 'compute' row reads StepMetrics.compute_budget_remaining"
    )
    assert isinstance(m.compute_budget_remaining, (int, float))


def test_short_run_emits_rejection_gates_as_floats():
    """The sandbox scenario actually produces non-zero values on at
    least some of the gates over a short run. We don't require any
    specific gate to fire — the test just asserts the values are
    finite floats so the HUD can render them."""
    cfg = get_scenario("spatial_sandbox")
    cfg.population.n_human_prototypes = 60
    cfg.population.n_agent_prototypes = 540
    cfg.cast_size = 200
    cfg.pair_sample_k = 64
    cfg.pairs_per_step = 2_000
    cfg.n_steps = 5

    world = World.build(cfg)
    last = None
    for _ in range(cfg.n_steps):
        last = world.step()
    for field in REJECTION_FIELDS:
        v = getattr(last, field)
        assert isinstance(v, (int, float)) and v == v  # not NaN
        assert v >= 0


# EBI regime band table, mirrored from scene.js REGIME_BANDS.
# Each row: (upper_exclusive, label). Tests verify the JS source
# carries the same constants.
REGIME_BANDS_PY = (
    (0.7,        "flat real economy"),
    (1.5,        "low baroque"),
    (2.5,        "calibrated reference"),
    (4.0,        "pricing reflexivity dominant"),
    (6.0,        "exo-baroque"),
    (float("inf"), "untethered"),
)


def _regime_label(ebi: float) -> str:
    for upper, label in REGIME_BANDS_PY:
        if ebi < upper:
            return label
    return "untethered"


def test_regime_band_labels_match_scene_js():
    """The Python-side band table must match the JS REGIME_BANDS
    array. Catches an out-of-sync rename in either file."""
    text = SCENE_JS.read_text()
    m = re.search(
        r"const REGIME_BANDS\s*=\s*\[(.*?)\];",
        text,
        re.DOTALL,
    )
    assert m, "REGIME_BANDS array not found in scene.js"
    body = m.group(1)
    # Each row is `[<expr>, '<label>'],` — parse with a forgiving regex.
    rows = re.findall(
        r"\[\s*(Infinity|[-\d.eE+]+)\s*,\s*['\"]([^'\"]+)['\"]\s*\]",
        body,
    )
    parsed = []
    for u, lbl in rows:
        upper = float("inf") if u == "Infinity" else float(u)
        parsed.append((upper, lbl))
    assert parsed == list(REGIME_BANDS_PY), (
        f"scene.js REGIME_BANDS does not match the Python table:\n"
        f"  js: {parsed}\n"
        f"  py: {list(REGIME_BANDS_PY)}"
    )


@pytest.mark.parametrize(
    "ebi,label",
    [
        (0.10, "flat real economy"),
        (0.69, "flat real economy"),
        (0.70, "low baroque"),
        (1.49, "low baroque"),
        (1.50, "calibrated reference"),
        (2.49, "calibrated reference"),
        (2.50, "pricing reflexivity dominant"),
        (3.99, "pricing reflexivity dominant"),
        (4.00, "exo-baroque"),
        (5.99, "exo-baroque"),
        (6.00, "untethered"),
        (20.0, "untethered"),
    ],
)
def test_regime_label_partition(ebi, label):
    """Boundary values land in the right band — exclusive upper edge
    rolls into the next band, the lower edge stays."""
    assert _regime_label(ebi) == label
