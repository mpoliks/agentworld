"""Phase 6 §7.3 — wealth meter contract.

The redesigned meter:
  - Single split bar for stock (humans amber / AI blue-grey). The
    two segments compose to 1.0 by construction — there is no gap.
  - Three 60-tick sparklines for the per-tick flow channels:
    matryoshka, legal capture, recycling. EMA smoothing is gone;
    the canvas is repainted strictly per onStep.

Contract here is the static piece: every flow channel reads from a
StepMetrics field the engine actually emits, and the stock split
reads from human_wealth_share. A field rename on either side would
make a row render constant zero — caught here before the user sees
it.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from engine.core.metrics import StepMetrics


REPO_ROOT = Path(__file__).resolve().parents[2]
SCENE_JS = REPO_ROOT / "dashboard" / "sandbox" / "scene.js"
SANDBOX_HTML = REPO_ROOT / "dashboard" / "sandbox.html"


def _stepmetrics_field_names() -> set[str]:
    """Reflect StepMetrics dataclass field names."""
    import dataclasses
    return {f.name for f in dataclasses.fields(StepMetrics)}


def test_stock_split_reads_human_wealth_share():
    """updateWealthStock reads step.human_wealth_share. Pin that
    the field exists on StepMetrics so the bar isn't silently
    fed undefined."""
    fields = _stepmetrics_field_names()
    assert "human_wealth_share" in fields, (
        "human_wealth_share missing from StepMetrics — wealth split bar would render 0/0"
    )
    text = SCENE_JS.read_text()
    assert "step.human_wealth_share" in text, (
        "scene.js no longer reads human_wealth_share for the stock split"
    )


def test_flow_segments_source_existing_step_fields():
    """The three flow sparklines source matryoshka (nominal − real
    over nominal), legal capture (law_surplus_loss_fraction), and
    recycling (pigouvian_effective_rate). Every named StepMetrics
    field must exist."""
    fields = _stepmetrics_field_names()
    text = SCENE_JS.read_text()
    m = re.search(r"FLOW_SEGMENTS\s*=\s*\[(.*?)\];", text, re.DOTALL)
    assert m, "FLOW_SEGMENTS array not found in scene.js"
    body = m.group(1)
    # Each source closure references step fields by name.
    # Confirm the three load-bearing names appear in the body.
    expected = [
        "nominal_gdp_step",
        "real_welfare_step",
        "law_surplus_loss_fraction",
        "pigouvian_effective_rate",
    ]
    for name in expected:
        assert f"s.{name}" in body or f"step.{name}" in body or name in body, (
            f"FLOW_SEGMENTS no longer references {name}"
        )
        assert name in fields, (
            f"{name} missing from StepMetrics — sparkline would render constant 0"
        )


def test_split_bar_html_uses_no_gap_layout():
    """The two segments share a flex parent. The plan calls out
    'no gap (the two compose to 1.0 by construction)' — anything
    else fakes a gap and the bar lies about the split."""
    text = SANDBOX_HTML.read_text()
    # The split-bar div contains two segment divs and a readout
    # div follows it. Scope to the section between the bar opener
    # and the readout opener.
    m = re.search(
        r'id="wealth-stock-bar".*?id="wealth-stock-readout"',
        text,
        re.DOTALL,
    )
    assert m, "wealth-stock-bar block missing from sandbox.html"
    body = m.group(0)
    assert "wealth-stock-humans" in body
    assert "wealth-stock-ai" in body
    # CSS verifies no flex gap.
    css = text
    assert "#wealth-stock-bar" in css
    # Look for the rule body — gap should be absent or 0.
    css_block = re.search(r"#wealth-stock-bar\s*\{(.*?)\}", css, re.DOTALL)
    assert css_block
    css_body = css_block.group(1)
    assert "display: flex" in css_body
    # gap is not declared, so flex children sit edge-to-edge.
    assert "gap:" not in css_body, (
        "wealth-stock-bar declares a flex gap; the split would no longer compose to 1.0"
    )


def test_old_ema_smoothing_removed():
    """Plan §7.3 explicitly drops the per-frame EMA. Keep it that
    way — re-adding it would re-introduce the stale-target bug in
    backgrounded tabs."""
    text = SCENE_JS.read_text()
    assert "METER_EMA_ALPHA" not in text, (
        "METER_EMA_ALPHA reappeared in scene.js — plan §7.3 drops it"
    )
    assert "r.smoothed =" not in text, (
        "EMA smoothed-target path reappeared — plan §7.3 drops it"
    )


def test_sparkline_length_is_sixty_ticks():
    """Plan §7.3 spec: '60-tick sparklines'. Catches a refactor
    that bumps to 120 or shrinks to 30 without coordination."""
    text = SCENE_JS.read_text()
    m = re.search(r"SPARKLINE_LEN\s*=\s*(\d+)", text)
    assert m
    assert int(m.group(1)) == 60, f"SPARKLINE_LEN = {m.group(1)} (want 60)"
