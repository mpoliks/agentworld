"""Phase 6 §7.2 — trade-arc outcome palette contract.

edges.js maps every engine reject_reason (plus executed) to a
distinct RGB on the trade arcs. The trade-arc legend in
sandbox.html (built in scene.js initArcLegend) reads from the
same OUTCOME_PALETTE export. Contract here: every engine
reject_reason has a palette entry, and the dashboard label set
covers all 8 outcomes from plan §7.2.

Adversarial check from plan §7.x:

  "Arc legend palette match. Each legend dot's RGB must equal the
  rendered arc color for that outcome. Pixel-exact."

The runtime pixel-match check needs Playwright. The static check
here ensures both ends share a single source of truth — a
typo on either side fails fast.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
EDGES_JS = REPO_ROOT / "dashboard" / "sandbox" / "edges.js"
SCENE_JS = REPO_ROOT / "dashboard" / "sandbox" / "scene.js"
TXN_PY = REPO_ROOT / "engine" / "core" / "transactions.py"


# Engine reject_reason strings — pulled from transactions.py's
# _REJECT_REASONS tuple. Re-pinned here so a rename on the engine
# side flags this test.
EXPECTED_ENGINE_REASONS = (
    "permeability",
    "compute",
    "law",
    "regulator",
    "market",
    "align",
    "cost",
)


def _engine_reasons() -> tuple[str, ...]:
    """Pull `_REJECT_REASONS` from transactions.py."""
    text = TXN_PY.read_text()
    m = re.search(r"_REJECT_REASONS:.*?=\s*\((.*?)\)", text, re.DOTALL)
    assert m, "could not parse _REJECT_REASONS from transactions.py"
    return tuple(re.findall(r'"([^"]+)"', m.group(1)))


def test_engine_reject_reasons_match_pinned_inventory():
    """If the engine adds a new reject_reason, the dashboard
    palette needs an entry for it. Fail loudly here so we update
    in lockstep."""
    found = _engine_reasons()
    assert set(found) == set(EXPECTED_ENGINE_REASONS), (
        f"engine reject reasons changed:\n"
        f"  engine: {found}\n"
        f"  pinned: {EXPECTED_ENGINE_REASONS}"
    )


def _outcome_palette() -> dict[str, tuple[float, float, float]]:
    """Parse the OUTCOME_COLORS object from edges.js."""
    text = EDGES_JS.read_text()
    m = re.search(r"const OUTCOME_COLORS\s*=\s*\{(.*?)\n\};", text, re.DOTALL)
    assert m, "OUTCOME_COLORS not found in edges.js"
    body = m.group(1)
    out = {}
    for row in re.finditer(
        r"(\w+):\s*\[\s*([\d.+-eE]+)\s*,\s*([\d.+-eE]+)\s*,\s*([\d.+-eE]+)\s*\]",
        body,
    ):
        out[row.group(1)] = (float(row.group(2)), float(row.group(3)), float(row.group(4)))
    return out


def _reason_to_palette() -> dict[str, str]:
    text = EDGES_JS.read_text()
    m = re.search(r"const REASON_TO_PALETTE\s*=\s*\{(.*?)\n\};", text, re.DOTALL)
    assert m
    body = m.group(1)
    out = {}
    for row in re.finditer(r"'([^']*)':\s*'([^']+)'", body):
        out[row.group(1)] = row.group(2)
    return out


def test_palette_covers_executed_plus_every_engine_reason():
    palette = _outcome_palette()
    expected_keys = {"executed"} | {f"reject_{_short(r)}" for r in EXPECTED_ENGINE_REASONS}
    missing = expected_keys - set(palette.keys())
    extras = set(palette.keys()) - expected_keys
    assert not missing, f"palette missing entries: {sorted(missing)}"
    assert not extras, f"palette has unexpected entries: {sorted(extras)}"
    # RGB in unit range.
    for key, (r, g, b) in palette.items():
        for v, ch in ((r, "R"), (g, "G"), (b, "B")):
            assert 0 <= v <= 1, f"{key} {ch}={v} outside [0, 1]"


def test_reason_to_palette_maps_every_engine_string():
    mapping = _reason_to_palette()
    # Empty string → executed; every engine reason → its palette key.
    assert mapping.get("") == "executed"
    for reason in EXPECTED_ENGINE_REASONS:
        key = mapping.get(reason)
        expected = f"reject_{_short(reason)}"
        assert key == expected, (
            f"reason {reason!r} → palette {key!r} (expected {expected!r})"
        )


def test_arc_legend_rows_cover_full_palette():
    """initArcLegend in scene.js walks an ARC_LEGEND_ROWS table.
    Every legend row's palette key must EXIST in the palette so
    each rendered dot has a real RGB to draw — but the legend may
    cover fewer rows than the palette has keys when multiple
    palette entries deliberately share the same RGB (current
    design collapses all reject_* to one rejected-red, so the
    legend shows 'executed' + 'rejected' even though the palette
    still has 8 keys for the per-reason HUD/contract path)."""
    text = SCENE_JS.read_text()
    m = re.search(r"ARC_LEGEND_ROWS\s*=\s*\[(.*?)\];", text, re.DOTALL)
    assert m
    keys = re.findall(r"\['(\w+)',", m.group(1))
    palette = _outcome_palette()
    assert set(keys).issubset(palette.keys()), (
        f"legend rows reference palette keys that don't exist:\n"
        f"  legend: {sorted(keys)}\n"
        f"  palette: {sorted(palette.keys())}"
    )
    # Sanity: every distinct RGB in the palette is covered by at
    # least one legend row.
    palette_rgbs = {tuple(palette[k]) for k in palette}
    legend_rgbs = {tuple(palette[k]) for k in keys}
    assert palette_rgbs == legend_rgbs, (
        f"legend does not cover every distinct palette colour:\n"
        f"  palette colours: {sorted(palette_rgbs)}\n"
        f"  legend colours:  {sorted(legend_rgbs)}"
    )


def _short(reason: str) -> str:
    """Mirror the abbreviation edges.js uses (permeability → perm,
    regulator → reg, everything else verbatim)."""
    if reason == "permeability":
        return "perm"
    if reason == "regulator":
        return "reg"
    return reason
