"""Phase 6 §7.1 — inspector card contract.

inspector_agent.js opens a per-agent card sourced from the most
recent cast snapshot. The card lists identity, state, norm
distance, cluster membership, and a K-axis norm radar. Plan §7.x
includes runtime adversarial checks for inspector identity and
sector match — those need Playwright. The static contracts here:

  - The card markup exists in sandbox.html with the three element
    ids the JS reads (header, close, body).
  - inspector_agent.js sources every load-bearing field from the
    cast-entry shape the engine actually emits — every key
    referenced as `e.<name>` must exist on cast snapshot rows.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
INSPECTOR_JS = REPO_ROOT / "dashboard" / "sandbox" / "inspector_agent.js"
SANDBOX_HTML = REPO_ROOT / "dashboard" / "sandbox.html"
WORLD_PY = REPO_ROOT / "engine" / "core" / "world.py"


def test_card_markup_present():
    """Phase 6 §7.1 follow-on: cards are now built dynamically into
    an #inspector-stack container so the dashboard can show
    multiple at once (shift-click). The static card-id check from
    the initial commit is gone with the static container."""
    text = SANDBOX_HTML.read_text()
    assert 'id="inspector-stack"' in text


def test_inspector_supports_multi_card_stack():
    """Inspector module exposes the stack API and respects MAX_CARDS."""
    js = INSPECTOR_JS.read_text()
    assert "MAX_CARDS" in js, "MAX_CARDS constant missing"
    m = re.search(r"MAX_CARDS\s*=\s*(\d+)", js)
    assert m and 2 <= int(m.group(1)) <= 8, "MAX_CARDS outside sensible range"
    # The card stack lives in `cards`, replaceUnpinned, addCard.
    assert "function addCard" in js
    assert "function replaceUnpinned" in js


def test_pin_and_watch_buttons_present():
    js = INSPECTOR_JS.read_text()
    assert "pinBtn" in js, "Pin button wiring missing"
    assert "watchBtn" in js, "Watch button wiring missing"
    assert "WATCH_CHURN_THRESHOLD" in js, "Watch threshold constant missing"


def test_cluster_card_kind_supported():
    js = INSPECTOR_JS.read_text()
    assert "renderClusterCard" in js
    assert "drawSectorPie" in js
    assert "drawJaccardSpark" in js


def test_card_field_reads_match_cast_snapshot_keys():
    """Every `e.<key>` reference in inspector_agent.js must
    correspond to a key emitted by `_assemble_cast_snapshot_v2`
    in engine/core/world.py."""
    js = INSPECTOR_JS.read_text()
    js_keys = set(re.findall(r"\be\.([a-z_]+)", js))

    # Pull every quoted key written into a snapshot entry in
    # world.py. The function builds `entry["..."] = ...` and
    # creates the dict with quoted keys in one assignment.
    py = WORLD_PY.read_text()
    py_keys = set(re.findall(r'"([a-z_]+)":', py))
    py_keys |= set(re.findall(r'entry\["([a-z_]+)"\]', py))

    missing = js_keys - py_keys
    assert not missing, (
        f"inspector_agent.js reads cast fields the engine does not emit: "
        f"{sorted(missing)}"
    )


def test_inspector_uses_drag_threshold_under_five_pixels():
    """Click-not-drag detection: plan §7.1 spec says drag < 4 px
    counts as a click. Anything looser and rotation drags open
    the card unintentionally."""
    js = INSPECTOR_JS.read_text()
    m = re.search(r"DRAG_PX_THRESHOLD\s*=\s*(\d+)", js)
    assert m
    assert int(m.group(1)) <= 5, (
        f"DRAG_PX_THRESHOLD = {m.group(1)} — too loose, drag rotates "
        "the camera and opens the inspector unintentionally"
    )


def test_norm_radar_axis_count_matches_cast_field():
    """The cast snapshot's `norm_vector` carries K components where
    K = WorldConfig.norms_n_dimensions. The radar polygon walks
    K vertices around the circle — inspector_agent.js reads
    `nv.length`. Pin the JS variable name so a refactor that
    hardcodes 8 (instead of nv.length) gets caught."""
    js = INSPECTOR_JS.read_text()
    assert "const K = nv.length" in js, (
        "radar must size off nv.length, not a hardcoded K"
    )
