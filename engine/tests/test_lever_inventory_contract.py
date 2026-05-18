"""Phase 4 — lever inventory contract.

The dashboard panel lists 20 plan-§3 levers in sandbox.html. Each
carries `data-key="<engine override key>"` and
`data-kind="live"|"structural"`. The live ones go through POST
/runs/{id}/update against the engine's `_LIVE_TUNABLE` allowlist;
the structural ones ride RunRequest.overrides on the next restart.
Both paths land in `engine.serve._apply_overrides`, which writes
through to a WorldConfig.

These tests are the CI tripwire that catches:

  - a dashboard lever whose `data-key` doesn't match an engine
    config field (the engine would reject the override silently
    in the live path or noisily on restart);
  - a live-flagged lever that isn't on `_LIVE_TUNABLE` (POST /update
    would 400);
  - a structural-flagged lever that IS on `_LIVE_TUNABLE` (the dot
    in the UI would mislead the user);
  - a dropped lever — the HTML reorg accidentally loses a row.

The expected inventory is pinned here in Python so an out-of-sync
edit on either side fails fast.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from engine.scenarios import get_scenario
from engine.serve import _apply_overrides


SANDBOX_HTML = (
    Path(__file__).resolve().parents[2]
    / "dashboard"
    / "sandbox.html"
)


# Pinned inventory. Tuples are (engine_key, kind). `scale` is the
# RunRequest top-level field; the rest are override keys.
EXPECTED_LEVERS: tuple[tuple[str, str], ...] = (
    # Agentic
    ("agent_capability_mean",             "structural"),
    ("agent_autonomy_mean",               "structural"),
    ("agent_trade_rate_multiplier",       "structural"),
    # Plan §5.1 stretch landed: network_model + network_p_local
    # are now live. network_model triggers a rewire between ticks
    # (~50-200 ms at the sandbox's 88k-prototype scale);
    # network_p_local is read per-tick by the sampler with no
    # rebuild required.
    ("network_p_local",                   "live"),
    ("norms.certified_fraction",          "structural"),
    ("norms.update_rate",                 "live"),
    ("network_model",                     "live"),
    # Legal
    ("market_layer_tax",                  "live"),
    ("pigouvian.tax_rate",                "live"),
    ("pigouvian.recycling_progressivity", "live"),
    ("law.law_strength_initial",          "structural"),
    ("law.transaction_size_cap",          "live"),
    ("folding_max_depth",                 "live"),
    ("regulator.enabled",                 "structural"),
    ("cross_stack_permeability",          "live"),
    ("pigouvian.recycling",               "structural"),
    # Environmental
    ("compute.budget_per_tick",           "live"),
    ("compute.power_cost_per_trade",      "live"),
    ("compute.distribution",              "structural"),
    ("scale",                             "structural"),
)


def _parse_html_levers():
    """Extract every (data-key, data-kind) pair from the lever panel
    in sandbox.html. The dashboard owns the structure; this scraping
    proves the engine knows about the same keys."""
    text = SANDBOX_HTML.read_text()
    # Strip everything outside #levers-panel so we only catch levers,
    # not e.g. another panel reusing the attribute name.
    panel_re = re.search(
        r'<div id="levers-panel"[\s\S]*?</div>\s*</div>',
        text,
    )
    assert panel_re, "could not locate #levers-panel in sandbox.html"
    panel = panel_re.group(0)
    pairs = re.findall(
        r'data-key="([^"]+)"[^>]*data-kind="([^"]+)"',
        panel,
    )
    return tuple(pairs)


def test_html_inventory_matches_pinned():
    html_levers = _parse_html_levers()
    pinned = set(EXPECTED_LEVERS)
    found = set(html_levers)
    missing_in_html = pinned - found
    extra_in_html = found - pinned
    assert not missing_in_html, (
        f"dashboard panel missing pinned levers: {sorted(missing_in_html)}"
    )
    assert not extra_in_html, (
        f"dashboard panel has unpinned levers: {sorted(extra_in_html)}"
    )


def test_live_levers_are_on_engine_allowlist():
    """Every lever marked data-kind='live' must be on the
    `_LIVE_TUNABLE` set in engine/serve.py — otherwise POST /update
    will 400 silently and the slider will appear broken.

    `_LIVE_TUNABLE` is closed over inside `create_app()` and not
    importable directly, so we grep the source. The set is short and
    stable; this is the cheapest source of truth check."""
    src = (Path(__file__).resolve().parents[1] / "serve.py").read_text()
    m = re.search(r"_LIVE_TUNABLE\s*=\s*\{(.*?)\n\s*\}", src, re.DOTALL)
    assert m, "couldn't extract _LIVE_TUNABLE from serve.py"
    body = m.group(1)
    keys = set(re.findall(r'"([^"]+)"', body))
    for key, kind in EXPECTED_LEVERS:
        if kind != "live":
            continue
        if key == "scale":
            continue  # RunRequest top-level field, not an override
        assert key in keys, (
            f"live lever {key!r} not on _LIVE_TUNABLE allowlist"
        )


def test_structural_levers_are_not_on_live_allowlist():
    """Conversely, structural-flagged levers must NOT be on the live
    allowlist. If they are, the UI dot is lying about the lever's
    behaviour — a structural lever marked as live would silently
    accept POST /update writes that don't take effect until restart."""
    src = (Path(__file__).resolve().parents[1] / "serve.py").read_text()
    m = re.search(r"_LIVE_TUNABLE\s*=\s*\{(.*?)\n\s*\}", src, re.DOTALL)
    body = m.group(1)
    keys = set(re.findall(r'"([^"]+)"', body))
    for key, kind in EXPECTED_LEVERS:
        if kind != "structural":
            continue
        if key == "scale":
            continue  # not an override key
        assert key not in keys, (
            f"structural lever {key!r} appears on _LIVE_TUNABLE"
        )


@pytest.mark.parametrize("key,kind", [
    (k, v) for k, v in EXPECTED_LEVERS if k != "scale"
])
def test_every_lever_applies_via_apply_overrides(key, kind):
    """Every override key the dashboard ships must round-trip
    through _apply_overrides without raising. The function walks
    nested configs by dotted-key; a typo on either side surfaces
    here."""
    cfg = get_scenario("spatial_sandbox")
    # Pick a per-lever value that is in range but not the default.
    # Categorical levers get a concrete string; bools toggle; numerics
    # get a small delta from default.
    VALUES = {
        "agent_capability_mean":             0.45,
        "agent_autonomy_mean":               0.60,
        "agent_trade_rate_multiplier":       1.5,
        "network_p_local":                   0.40,
        "norms.certified_fraction":          0.35,
        "norms.update_rate":                 0.07,
        "network_model":                     "scale_free",
        "market_layer_tax":                  0.05,
        "pigouvian.tax_rate":                0.20,
        "pigouvian.recycling_progressivity": 1.5,
        "law.law_strength_initial":          0.65,
        "law.transaction_size_cap":          5.0,
        "folding_max_depth":                 4,
        "regulator.enabled":                 False,
        "cross_stack_permeability":          0.6,
        "pigouvian.recycling":               "friction_subsidy",
        "compute.budget_per_tick":           0.5,
        "compute.power_cost_per_trade":      0.0002,
        "compute.distribution":              "wealth_weighted",
    }
    v = VALUES[key]
    # extend_bounds=True keeps the Sobol-bounds check from rejecting
    # values inside the dashboard's slider range but outside the
    # Sobol design (the dashboard's bounds are the truth here).
    _apply_overrides(cfg, {key: v}, extend_bounds=True)
    # Confirm the override actually wrote through by reading back
    # the config field the engine consumes.
    if "." in key:
        head, _, tail = key.partition(".")
        nested = getattr(cfg.topology, head)
        assert getattr(nested, tail) == v
    elif hasattr(cfg, key):
        assert getattr(cfg, key) == v
    elif hasattr(cfg.topology, key):
        assert getattr(cfg.topology, key) == v
    elif hasattr(cfg.population, key):
        assert getattr(cfg.population, key) == v
    else:
        pytest.fail(f"override key {key!r} did not land on any config")
