"""Plan §8.3 — dev/checks runtime invariants contract.

`dashboard/sandbox/dev/checks.js` is the in-browser invariant
harness. Default off; opt in with `?dev=1` URL parameter. The
file declares one check function per invariant from the plan
spec; this contract test pins their presence so a refactor
that drops a check is caught.

The runtime behaviour (assertion firing → badge surfaces) needs
a real browser to exercise; that's the deferred Playwright pass.
The static contract here:

  - `dashboard/sandbox/dev/checks.js` exists and exports
    `enableDevChecks` and `devChecksDiagnostics`.
  - The file declares each of the six in-browser invariants the
    plan calls out (HUD numerics, stock-bar sum, folds count,
    rejection-mix completeness, visual ↔ partition consistency,
    inspector identity).
  - scene.js gates the harness import on `URLSearchParams(...)
    .has('dev')`, so production loads don't pay the cost.
  - sandbox.html ships the badge slot with the right id.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKS_JS = REPO_ROOT / "dashboard" / "sandbox" / "dev" / "checks.js"
SCENE_JS = REPO_ROOT / "dashboard" / "sandbox" / "scene.js"
SANDBOX_HTML = REPO_ROOT / "dashboard" / "sandbox.html"


def test_checks_file_present():
    assert CHECKS_JS.exists(), f"missing {CHECKS_JS}"


def test_exports_enable_and_diagnostics():
    text = CHECKS_JS.read_text()
    assert "export function enableDevChecks" in text
    assert "export function devChecksDiagnostics" in text


@pytest.mark.parametrize("name", [
    "checkHudConsistency",
    "checkStockBar",
    "checkFoldsCount",
    "checkRejectionMixCompleteness",
    "checkVisualPartitionConsistency",
    "checkSegmentTintTruthfulness",
    "checkInspectorIdentity",
])
def test_each_invariant_declared(name):
    """Every invariant the plan calls out must have a check
    function in the harness. A refactor that drops a category
    here is what the plan §8.3 framing wants caught."""
    text = CHECKS_JS.read_text()
    assert f"function {name}(" in text, (
        f"{name} not declared in dev/checks.js"
    )


def test_scene_js_gates_on_dev_query_param():
    """Production loads must not pay the parse cost. scene.js
    imports dev/checks.js only when `?dev=1` is in the URL."""
    text = SCENE_JS.read_text()
    # The URLSearchParams gate lives next to the dynamic import.
    assert re.search(
        r"new URLSearchParams\(location\.search\)\.has\('dev'\)",
        text,
    ), "scene.js missing ?dev=1 gate for dev/checks import"
    assert "import('./dev/checks.js')" in text, (
        "dev/checks.js must be a dynamic import"
    )


def test_badge_markup_present():
    text = SANDBOX_HTML.read_text()
    assert 'id="dev-checks-badge"' in text, "dev-checks-badge missing from sandbox.html"


def test_step_forwarding_hook_present():
    """The harness reads `__devChecksOnStep` to get the latest
    StepMetrics. scene.js must publish each step into the global
    hook the harness installs."""
    text = SCENE_JS.read_text()
    assert "window.__devChecksOnStep" in text, (
        "scene.js does not forward steps into the dev/checks harness"
    )


def test_check_period_documented_and_reasonable():
    """CHECK_PERIOD = 30 frames ≈ 0.5 s at 60 fps. Bounds are
    pinned so a future refactor that bumps to per-frame doesn't
    silently torpedo the render budget."""
    text = CHECKS_JS.read_text()
    m = re.search(r"CHECK_PERIOD\s*=\s*(\d+)", text)
    assert m
    period = int(m.group(1))
    assert 10 <= period <= 120, f"CHECK_PERIOD = {period} outside [10, 120]"
