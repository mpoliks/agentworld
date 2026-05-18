"""Phase 3 §4.x — sector overlay contracts.

The plan's adversarial checks for the emergent-sector overlay
break into runtime browser tests (tint truthfulness, no phantom
binding, permeability-driven Moran's I dispersion) and static
contracts. The static ones are the cheap CI tripwires that catch
the most common drift:

  - Compass ↔ palette match. Each of the 12 sector compass
    swatches in sandbox.html must render the exact RGB from
    themes.js sectorPalette. A typo or off-by-one would render
    the wrong color and silently mislead the user about which
    sector they isolated.

  - SECTOR_NAMES alignment. scene.js and engine/core/population.py
    both list the 12 sector names. They must agree exactly —
    a rename or reorder on either side flips the labels.

  - N_SECTORS = 12. The palette assumes 12 entries; if the engine
    ever grows another sector the palette needs to grow in lock-step.

The runtime adversarial tests (segment-tint truthfulness, no
phantom binding, Moran's I dispersion under cross-stack
permeability) need Playwright + a live engine and ship in a
follow-on pass.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from engine.core.population import N_SECTORS, SECTOR_NAMES


REPO_ROOT = Path(__file__).resolve().parents[2]
THEMES_JS = REPO_ROOT / "dashboard" / "sandbox" / "themes.js"
SCENE_JS = REPO_ROOT / "dashboard" / "sandbox" / "scene.js"


def _parse_theme_sector_palette() -> list[tuple[float, float, float]]:
    """Pull the sectorPalette block out of themes.js. Each entry is
    `[r, g, b],  // n  label`. Returns the list in declaration order."""
    text = THEMES_JS.read_text()
    m = re.search(r"sectorPalette\s*:\s*\[(.*?)\],\s*sectorTintWeight", text, re.DOTALL)
    assert m, "sectorPalette block not found in themes.js"
    body = m.group(1)
    rows = re.findall(r"\[\s*([\d.+-eE]+)\s*,\s*([\d.+-eE]+)\s*,\s*([\d.+-eE]+)\s*\]", body)
    return [(float(r), float(g), float(b)) for (r, g, b) in rows]


def _parse_scene_sector_names() -> list[str]:
    text = SCENE_JS.read_text()
    m = re.search(r"const SECTOR_NAMES\s*=\s*\[(.*?)\];", text, re.DOTALL)
    assert m, "SECTOR_NAMES not found in scene.js"
    return re.findall(r"'([^']+)'", m.group(1))


def test_palette_has_n_sectors_entries():
    palette = _parse_theme_sector_palette()
    assert len(palette) == N_SECTORS, (
        f"sectorPalette has {len(palette)} entries, engine has {N_SECTORS} sectors"
    )


def test_palette_rgb_components_in_unit_range():
    """Every channel must be in [0, 1]. agents.js applies the mix
    `base * (1-w) + paletteEntry * w`; a channel outside [0, 1]
    would produce an invalid color or silently clip on GPU upload."""
    for i, (r, g, b) in enumerate(_parse_theme_sector_palette()):
        for ch, name in ((r, "R"), (g, "G"), (b, "B")):
            assert 0.0 <= ch <= 1.0, f"sector {i} {name}={ch} outside [0, 1]"


def test_sector_names_match_engine():
    """scene.js SECTOR_NAMES must equal engine population.SECTOR_NAMES."""
    js_names = _parse_scene_sector_names()
    assert js_names == SECTOR_NAMES, (
        f"sector name list mismatch:\n  js: {js_names}\n  py: {SECTOR_NAMES}"
    )


def test_compass_uses_full_palette_in_order():
    """sandbox.html's compass is built dynamically from the same
    palette, so the contract here is on the JS init code: there's
    exactly one swatch built per palette entry, indexed in order.
    Scrape initSectorCompass to confirm — a refactor that reverses
    the loop or skips entries would surface here."""
    text = SCENE_JS.read_text()
    init = re.search(
        r"function initSectorCompass\(\)\s*\{(.*?)\n\}",
        text,
        re.DOTALL,
    )
    assert init, "initSectorCompass not found in scene.js"
    body = init.group(1)
    # The function reads palette.length and walks 0..length-1.
    assert "palette.length" in body, (
        "initSectorCompass must iterate the full palette"
    )
    # Each swatch must carry data-sector = String(i) — used by the
    # adversarial click-to-isolate test (Playwright) to address
    # individual swatches.
    assert "swatch.dataset.sector = String(i)" in body, (
        "compass swatches must carry data-sector"
    )
    # Each swatch must read its color from the palette entry — not
    # a different palette or a constant.
    assert "palette[i]" in body, (
        "compass swatches must source RGB from sectorPalette[i]"
    )


def test_segment_tint_mix_formula_documented_in_agents():
    """agents.js performs `base * (1-w) + palette[s] * w`. Surface
    the formula by source-grep so a refactor that drops the mix
    (e.g. flips to pure palette[s]) is caught by CI rather than
    silently changing every caterpillar's color."""
    agents_js = (REPO_ROOT / "dashboard" / "sandbox" / "agents.js").read_text()
    # The compute uses _baseR / _baseG / _baseB and the tint weight.
    assert "_baseR * (1 - w) + p[0] * w" in agents_js
    assert "_baseG * (1 - w) + p[1] * w" in agents_js
    assert "_baseB * (1 - w) + p[2] * w" in agents_js


def test_engine_n_sectors_is_twelve():
    """The dashboard palette + compass UI are 12-keyed. Engine grows
    its sector inventory → the dashboard needs to grow too. Pin to
    catch drift."""
    assert N_SECTORS == 12
