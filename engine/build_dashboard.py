"""
Build a single self-contained HTML dashboard from the run outputs.

The output is `dashboard/index.html`. Open it in any browser; no server needed.

The dashboard pulls four kinds of inputs:

    1. Per-scenario run JSON in `outputs/runs/`        (required)
    2. Per-scenario ensemble bands JSON in `outputs/ensembles/{name}.bands.json`
       (optional; when present, plots show median + 5/95 bands and the
        scenario card shows the ensemble seed count)
    3. Phase-space sweep JSON in `outputs/sensitivity/phase_space.json`
       (optional; renders the §6 basin map)
    4. Sobol indices JSON in `outputs/sensitivity/sobol_indices.json` and
       `outputs/sensitivity/exo_sobol_indices.json`
       (optional; renders the §7 global-sensitivity panel)

The §1 introduction is a working-paper exposition of the model — the
question, the trade pipeline, the folding operator, and the diagnostic
ledgers (EBI, real welfare, fold depth, human legibility) — with
KaTeX-rendered equations and three SVG figures.
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.scenarios import SCENARIO_DESCRIPTIONS

SCENARIO_ORDER = [
    "coasean_paradise",
    "universal_advocate",
    "public_defender",
    "civic_renaissance",
    "synthetic_consumers_v2",
    "smoothing_cascade",
    "equilibrium_drift",
    "matryoshka_collapse",
    "hemispherical_schism",
    "compute_famine",
    "derivatives_revolution",
    "legal_collapse",
    "regulatory_capture",
    "endogenous_baroque",
    "pigouvian_heavy",
    "pigouvian_friction",
    "full_emergence",
    "recursive_simulation",
    "fold_avalanche",
    "slop_market",
    "productive_baroque",
    "baroque_with_high_welfare",
    "baroque_cathedral",
    "baroque_cathedral_networked",
    "exo_baroque_singularity",
]

SCENARIO_LABELS = {
    "coasean_paradise": "Coasean Paradise",
    "universal_advocate": "Universal Advocate",
    "public_defender": "Public Defender",
    "civic_renaissance": "Civic Renaissance",
    "synthetic_consumers": "Synthetic Demand",
    "synthetic_consumers_v2": "Synthetic Customers",
    "smoothing_cascade": "Smoothing Cascade",
    "equilibrium_drift": "Equilibrium Drift",
    "matryoshka_collapse": "Matryoshka Collapse",
    "hemispherical_schism": "Hemispherical Schism",
    "compute_famine": "Compute Famine",
    "derivatives_revolution": "Derivatives Revolution",
    "legal_collapse": "Legal Collapse",
    "regulatory_capture": "Regulatory Capture",
    "endogenous_baroque": "Endogenous Baroque",
    "pigouvian_heavy": "Pigouvian Heavy",
    "pigouvian_friction": "Pigouvian Friction",
    "full_emergence": "Full Emergence",
    "recursive_simulation": "Recursive Simulation",
    "fold_avalanche": "Fold Avalanche",
    "slop_market": "Slop Market",
    "productive_baroque": "Productive Baroque",
    "baroque_with_high_welfare": "Baroque (High Welfare)",
    "baroque_cathedral": "Baroque Cathedral",
    "baroque_cathedral_networked": "Productive Cathedral",
    "exo_baroque_singularity": "Exo-Baroque Singularity",
}


def _load_runs(runs_dir: Path) -> dict:
    out = {}
    for name in SCENARIO_ORDER:
        path = runs_dir / f"{name}.json"
        if not path.exists():
            continue
        with open(path) as f:
            out[name] = json.load(f)
    return out


def _load_sensitivity(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def _load_ensembles(ensembles_dir: Path) -> dict:
    """Load per-scenario `*.bands.json` files; key by scenario name."""
    out: dict[str, dict] = {}
    if not ensembles_dir.exists():
        return out
    for name in SCENARIO_ORDER:
        bands_path = ensembles_dir / f"{name}.bands.json"
        if not bands_path.exists():
            continue
        try:
            out[name] = json.loads(bands_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
    return out


def _load_sobol(path: Path) -> dict | None:
    """Load a Sobol indices JSON. Returns None when missing or malformed."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _load_provenance() -> list[dict]:
    """Return the empirical-anchor provenance list for the About panel."""
    try:
        from engine.data.empirical_anchors import provenance_dict

        return provenance_dict()
    except Exception:  # pragma: no cover
        return []


def _load_convergence_stability(outputs_dir: Path) -> dict:
    """Read the convergence + stability summary JSONs and derive per-scenario
    scale-stability and trajectory-convergence flags for the §3 panel.

    Returns {scenario_name: {...}} where each entry may carry:

        scale_status         : "stable" | "fragile" | None
        scale_small_ebi      : terminal-EBI mean at small scale
        scale_medium_ebi_*   : terminal-EBI mean / lo / hi at medium scale
        traj_status          : "steady" | "transient" | None
        traj_drift_pct       : |EBI(last) − EBI(prev)| / EBI(prev) × 100
        traj_n_steps_*       : n_steps for the last two budgets
        traj_ebi_*           : terminal EBI at those two budgets

    Missing inputs are silently skipped — the dashboard panel renders
    "no data" for scenarios without sweep coverage.
    """
    conv_path = outputs_dir / "convergence" / "_summary.json"
    stab_path = outputs_dir / "stability" / "_summary.json"
    conv = json.loads(conv_path.read_text()) if conv_path.exists() else {}
    stab = json.loads(stab_path.read_text()) if stab_path.exists() else {}

    out: dict[str, dict] = {}
    for name in set(conv.keys()) | set(stab.keys()):
        entry: dict = {}
        c = conv.get(name, {})
        if "small" in c and "medium" in c:
            sm = c["small"].get("exo_baroque_index", {}) or {}
            md = c["medium"].get("exo_baroque_index", {}) or {}
            if sm and md:
                small_mean = float(sm.get("mean", 0.0))
                med_mean = float(md.get("mean", 0.0))
                med_lo = float(md.get("lo", 0.0))
                med_hi = float(md.get("hi", 0.0))
                # Stable when small mean lies inside the medium CI plus a
                # 25% slack on either side; fragile otherwise.
                span = max(med_hi - med_lo, 0.05 * max(abs(med_mean), 1.0))
                lo, hi = med_lo - 0.25 * span, med_hi + 0.25 * span
                entry["scale_status"] = "stable" if lo <= small_mean <= hi else "fragile"
                entry["scale_small_ebi"] = small_mean
                entry["scale_medium_ebi_mean"] = med_mean
                entry["scale_medium_ebi_lo"] = med_lo
                entry["scale_medium_ebi_hi"] = med_hi

        s = stab.get(name, {})
        if s:
            budgets = sorted(int(k) for k in s.keys())
            if len(budgets) >= 2:
                prev_n, last_n = budgets[-2], budgets[-1]
                prev_mean = float(
                    (s[str(prev_n)].get("exo_baroque_index", {}) or {}).get("mean", 0.0)
                )
                last_mean = float(
                    (s[str(last_n)].get("exo_baroque_index", {}) or {}).get("mean", 0.0)
                )
                if abs(prev_mean) > 1e-9:
                    drift_pct = abs(last_mean - prev_mean) / abs(prev_mean) * 100.0
                else:
                    drift_pct = 0.0
                entry["traj_status"] = "steady" if drift_pct < 1.0 else "transient"
                entry["traj_drift_pct"] = drift_pct
                entry["traj_n_steps_prev"] = prev_n
                entry["traj_n_steps_last"] = last_n
                entry["traj_ebi_prev"] = prev_mean
                entry["traj_ebi_last"] = last_mean

        if entry:
            out[name] = entry
    return out


def build_html(
    runs: dict,
    sensitivity: dict | None = None,
    ensembles: dict | None = None,
    sobol_alpha: dict | None = None,
    sobol_exo: dict | None = None,
    convergence_stability: dict | None = None,
) -> str:
    payload = {
        "scenarios": {
            name: {
                "label": SCENARIO_LABELS.get(name, name),
                "description": SCENARIO_DESCRIPTIONS.get(name, ""),
                "final_alpha": run["final_alpha"],
                "final_label": run["final_label"],
                "history": run["history"],
                "population_summary": run["population_summary"],
                "config": run["config"],
            }
            for name, run in runs.items()
        },
        "scenario_order": [n for n in SCENARIO_ORDER if n in runs],
        "sensitivity": sensitivity,
        "ensembles": ensembles or {},
        "sobol_alpha": sobol_alpha,
        "sobol_exo": sobol_exo,
        "provenance": _load_provenance(),
        "convergence_stability": convergence_stability or {},
    }
    payload_json = json.dumps(payload)

    html = HTML_TEMPLATE.replace("__PAYLOAD__", payload_json)
    return html


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Agentworld – An atlas of agentic macroeconomics</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<meta name="googlebot" content="noindex, nofollow">
<meta name="referrer" content="no-referrer-when-downgrade">
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js" onload="renderMathInElement(document.body, {
  delimiters: [
    {left: '$$', right: '$$', display: true},
    {left: '\\[', right: '\\]', display: true},
    {left: '$',  right: '$',  display: false},
    {left: '\\(', right: '\\)', display: false}
  ],
  throwOnError: false
});"></script>
<style>
:root {
  --bg: #0c0d10;
  --panel: #14161a;
  --panel-2: #1a1d22;
  --border: #2a2d33;
  --text: #e7e8ea;
  --text-2: #9ea2a8;
  --text-3: #6a6d72;
  --accent: #b89a55;
  --green: #5fa572;
  --red: #c25a5a;
  --blue: #5b8ec4;
  --purple: #9077c2;
  --serif: 'Iowan Old Style', 'Georgia', 'Times New Roman', serif;
  --sans: 'Inter', 'Helvetica Neue', 'Helvetica', system-ui, sans-serif;
  --mono: 'JetBrains Mono', 'SF Mono', 'Menlo', monospace;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: var(--bg); color: var(--text); font-family: var(--sans); -webkit-font-smoothing: antialiased; }
a { color: var(--accent); text-decoration: none; border-bottom: 1px solid rgba(184,154,85,0.3); }
a:hover { border-bottom-color: var(--accent); }
.wrap { max-width: 1280px; margin: 0 auto; padding: 0 24px; }

header {
  padding: 64px 0 40px;
  border-bottom: 1px solid var(--border);
}
header .super { font-size: 11px; letter-spacing: 0.18em; text-transform: uppercase; color: var(--text-3); margin-bottom: 18px; }
header h1 { font-family: var(--serif); font-weight: 400; font-size: 56px; line-height: 1.05; margin: 0 0 18px; letter-spacing: -0.02em; }
header h1 em { font-style: italic; color: var(--accent); }
header .lead { font-family: var(--serif); font-size: 19px; line-height: 1.55; color: var(--text); margin-bottom: 18px; }
header .meta { font-size: 13px; color: var(--text-3); display: flex; gap: 16px; margin-top: 24px; flex-wrap: wrap; }
header .meta span { padding: 4px 10px; background: var(--panel); border: 1px solid var(--border); border-radius: 3px; }

section { padding: 56px 0; border-bottom: 1px solid var(--border); }
section h2 { font-family: var(--serif); font-weight: 400; font-size: 32px; margin: 0 0 12px; letter-spacing: -0.01em; }
section h2 .marker { color: var(--accent); margin-right: 12px; font-size: 18px; vertical-align: middle; font-family: var(--mono); }
section .sub { font-family: var(--serif); font-size: 16px; color: var(--text-2); line-height: 1.55; margin-bottom: 28px; }

.panel { background: var(--panel); border: 1px solid var(--border); border-radius: 4px; padding: 20px; }

.atlas-grid { display: grid; grid-template-columns: 1fr; gap: 24px; }

.scenario-strip {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}
.scn-card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 14px 16px;
  cursor: pointer;
  transition: all 0.12s;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.scn-card:hover { border-color: var(--accent); background: var(--panel-2); }
.scn-card.active { border-color: var(--accent); background: var(--panel-2); }
.scn-card .name { font-family: var(--serif); font-size: 17px; font-weight: 400; color: var(--text); }
.scn-card .alpha { font-family: var(--mono); font-size: 11px; color: var(--text-3); display: flex; gap: 10px; white-space: nowrap; }
.scn-card .alpha b { color: var(--accent); font-weight: 500; }
.scn-card .desc { font-size: 12px; color: var(--text-2); line-height: 1.45; }
.scn-card .cs-badges { display: flex; gap: 6px; margin-top: 2px; }
.cs-badge {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.04em;
  padding: 2px 6px;
  border-radius: 3px;
  border: 1px solid;
  text-transform: uppercase;
}
.cs-badge.stable, .cs-badge.steady   { color: var(--green);   border-color: var(--green);   background: rgba(95,165,114,0.10); }
.cs-badge.drifting                   { color: #b89a55;        border-color: #b89a55;        background: rgba(184,154,85,0.10); }
.cs-badge.fragile, .cs-badge.transient { color: #c25a5a;     border-color: #c25a5a;        background: rgba(194,90,90,0.10); }
.cs-badge.unknown                    { color: var(--text-3); border-color: var(--border); background: var(--panel-2); }

.cs-panel {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 18px 22px;
  margin-bottom: 22px;
}
.cs-panel-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 10px; }
.cs-panel-head h3 { margin: 0; font-family: var(--serif); font-weight: 400; font-size: 18px; color: var(--text); }
.cs-panel-head .cs-meta { font-family: var(--mono); font-size: 11px; color: var(--text-3); }
.cs-panel-sub { font-size: 13px; color: var(--text-2); line-height: 1.55; margin: 0 0 12px; }
.cs-table { width: 100%; border-collapse: collapse; font-size: 12px; font-family: var(--mono); }
.cs-table th { text-align: left; color: var(--text-3); font-weight: 400; padding: 6px 8px; border-bottom: 1px solid var(--border); }
.cs-table td { padding: 6px 8px; border-bottom: 1px solid rgba(42,45,51,0.4); color: var(--text-2); }
.cs-table td.scen { color: var(--text); }
.cs-table td.num { text-align: right; }
.cs-empty { color: var(--text-3); font-size: 12px; padding: 12px 0; font-family: var(--mono); }

.phase-pane { display: grid; grid-template-columns: 1fr 320px; gap: 16px; align-items: stretch; margin-bottom: 24px; }
.phase-pane .phase-map-box { display: flex; flex-direction: column; min-height: 0; }
.phase-pane .phase-map-box > div[id="phase-map"] { flex: 1; }
.phase-side { display: flex; flex-direction: column; gap: 12px; }
.phase-section-label { font-size: 10px; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.10em; margin-bottom: 12px; }
.phase-controls { padding: 16px 18px; }
.phase-slider-row { margin-bottom: 18px; }
.phase-slider-row:last-child { margin-bottom: 0; }
.phase-slider-label { font-family: var(--serif); font-size: 13px; color: var(--text-2); margin-bottom: 4px; display: flex; justify-content: space-between; align-items: baseline; }
.phase-slider-help { font-size: 11px; color: var(--text-3); font-style: italic; }
.phase-slider-readout { font-family: var(--mono); font-size: 22px; color: var(--accent); margin-bottom: 4px; }
.phase-controls input[type="range"] { width: 100%; accent-color: var(--accent); }
.phase-slider-axis { display: flex; justify-content: space-between; font-family: var(--mono); font-size: 10px; color: var(--text-3); margin-top: 2px; }
.phase-readout { padding: 16px 18px; }
.phase-readout-row { display: flex; justify-content: space-between; align-items: baseline; padding: 6px 0; border-bottom: 1px solid var(--border); }
.phase-readout-row:last-of-type { border-bottom: 0; }
.phase-readout-key { font-family: var(--serif); font-size: 12.5px; color: var(--text-3); }
.phase-readout-val { font-family: var(--mono); font-size: 13px; color: var(--text); }
.phase-readout-foot { margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--border); font-family: var(--serif); font-size: 12px; color: var(--text-3); line-height: 1.4; min-height: 30px; }
.phase-legend { padding: 14px 18px; }
.phase-legend-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 14px; }
.phase-legend-item { display: flex; align-items: center; gap: 8px; font-family: var(--serif); font-size: 12px; color: var(--text-2); }
.phase-legend-glyph { font-family: var(--mono); font-size: 14px; width: 14px; text-align: center; }
@media (max-width: 900px) { .phase-pane { grid-template-columns: 1fr; } }
.detail-pane { display: grid; grid-template-columns: 280px 1fr; gap: 24px; align-items: stretch; margin-bottom: 24px; }
.detail-pane > .chart-box { display: flex; flex-direction: column; min-height: 0; }
.detail-pane > .chart-box > #anim-container { flex: 1; min-height: 360px; }
@media (max-width: 900px) { .detail-pane { grid-template-columns: 1fr; } .detail-pane > .chart-box > #anim-container { aspect-ratio: 9 / 5; flex: none; } }

.detail-meta { display: flex; flex-direction: column; gap: 16px; }
.detail-meta .stat { background: var(--panel); border: 1px solid var(--border); border-radius: 4px; padding: 14px 16px; }
.detail-meta .stat .label { font-size: 11px; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.08em; }
.detail-meta .stat .value { font-family: var(--mono); font-size: 22px; color: var(--text); margin-top: 4px; }
.detail-meta .stat .value.tinted { color: var(--accent); }
.detail-meta .stat .sub { font-size: 11px; color: var(--text-3); margin-top: 4px; }
.detail-meta .desc { font-family: var(--serif); font-size: 14px; line-height: 1.5; color: var(--text-2); padding: 8px 4px; }

.charts-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 800px) { .charts-grid { grid-template-columns: 1fr; } }
.chart-box { background: var(--panel); border: 1px solid var(--border); border-radius: 4px; padding: 8px; }
.chart-title { font-size: 11px; color: var(--text-3); padding: 8px 12px 0; text-transform: uppercase; letter-spacing: 0.08em; }
.chart-caption { font-family: var(--serif); font-size: 13px; line-height: 1.5; color: var(--text-2); padding: 6px 12px 4px; }
.chart-caption b { color: var(--text); font-weight: 500; }
.chart-caption i { color: var(--accent); font-style: italic; }

.compare-bar { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 8px; }
.compare-help { font-size: 12px; color: var(--text-3); margin-bottom: 12px; font-family: var(--sans); }
.compare-help kbd { font-family: var(--mono); font-size: 11px; background: var(--panel-2); border: 1px solid var(--border); border-radius: 2px; padding: 1px 5px; color: var(--text-2); }
.chip { background: var(--panel); border: 1px solid var(--border); border-radius: 3px; padding: 4px 10px; font-size: 12px; color: var(--text-2); cursor: pointer; user-select: none; }
.chip:hover { border-color: var(--accent); }
.chip.active { background: var(--panel-2); border-color: var(--accent); color: var(--text); }
.chip.action { background: transparent; border: 1px dashed var(--text-3); color: var(--text-3); font-family: var(--mono); font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; padding: 4px 12px; }
.chip.action:hover { color: var(--text); border-color: var(--text); border-style: solid; }
.chip-sep { width: 1px; align-self: stretch; background: var(--border); margin: 0 6px; }

footer { padding: 56px 0 80px; color: var(--text-3); font-size: 12px; }
footer p { max-width: 720px; line-height: 1.6; }
.legend { display: inline-flex; gap: 16px; align-items: center; font-size: 11px; color: var(--text-3); margin-top: 8px; }
.legend i { display: inline-block; width: 11px; height: 11px; border-radius: 2px; vertical-align: middle; margin-right: 6px; }
.callout { font-family: var(--serif); font-size: 16px; line-height: 1.55; padding: 18px 22px; border-left: 3px solid var(--accent); background: var(--panel); margin: 24px 0; color: var(--text); }
.callout em { color: var(--text-2); }

/* Essay layout for the introduction. The §1 primer was previously a grid of
   tile-cards which forced the reader to assemble the argument themselves;
   here we present the same material as continuous prose with embedded
   figures and equation displays, in the manner of a working paper. */
.essay { max-width: none; margin: 0; font-family: var(--serif); font-size: 16.5px; line-height: 1.65; color: var(--text); }
.essay > p { margin: 0 0 18px; }
.essay > p:first-of-type::first-letter {
  font-family: var(--serif);
  float: left;
  font-size: 56px;
  line-height: 0.9;
  padding: 6px 10px 0 0;
  color: var(--accent);
  font-style: italic;
}
.essay h3 {
  font-family: var(--serif);
  font-weight: 400;
  font-size: 22px;
  letter-spacing: -0.005em;
  margin: 40px 0 14px;
  color: var(--text);
}
.essay h3 .num {
  font-family: var(--mono);
  font-size: 13px;
  color: var(--accent);
  margin-right: 10px;
  vertical-align: 2px;
}
.essay b { color: var(--text); font-weight: 500; }
.essay i, .essay em { color: var(--text); font-style: italic; }
.essay code { font-family: var(--mono); font-size: 14px; color: var(--accent); background: rgba(184,154,85,0.06); padding: 1px 5px; border-radius: 2px; }
.essay ul { padding-left: 22px; margin: 0 0 18px; }
.essay ul li { margin-bottom: 8px; color: var(--text); }
.essay blockquote {
  margin: 22px 0;
  padding: 4px 0 4px 20px;
  border-left: 2px solid var(--accent);
  color: var(--text-2);
  font-style: italic;
  font-size: 15.5px;
}

.eqn {
  font-size: 15px;
  line-height: 1.6;
  color: var(--text);
  background: var(--panel);
  border: 1px solid var(--border);
  border-left: 2px solid var(--accent);
  border-radius: 3px;
  padding: 18px 22px;
  margin: 22px 0;
  overflow-x: auto;
}
.eqn .katex { color: var(--text); font-size: 1.1em; }
.eqn .katex-display { margin: 0; }
.eqn .katex-display > .katex > .katex-html > .tag { color: var(--text-3); font-size: 0.85em; }
.essay .katex { color: var(--text); }

.fig {
  margin: 28px 0;
  padding: 18px 18px 12px;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 4px;
}
.fig .fig-body { width: 100%; display: block; }
.fig figcaption {
  font-family: var(--serif);
  font-size: 13.5px;
  line-height: 1.55;
  color: var(--text-2);
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
}
.fig figcaption b { color: var(--text); font-weight: 500; }
.fig figcaption .figlabel { font-family: var(--mono); font-size: 11px; color: var(--accent); letter-spacing: 0.08em; text-transform: uppercase; margin-right: 8px; }

.essay-aside {
  font-family: var(--serif);
  font-size: 14px;
  line-height: 1.55;
  color: var(--text-3);
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  padding: 14px 0;
  margin: 24px 0;
}

/* Mobile: the atlas needs more vertical room because the colorbar moves
   under the plot, and the surrounding page chrome should compress so the
   chart isn't squeezed by 24px gutters and 64px section padding. */
@media (max-width: 640px) {
  .wrap { padding: 0 14px; }
  header { padding: 40px 0 28px; }
  header h1 { font-size: 38px; }
  header .lead { font-size: 16px; }
  section { padding: 36px 0; }
  section h2 { font-size: 24px; }
  section .sub { font-size: 14px; }
  .chart-box { padding: 6px; }
  .chart-caption { font-size: 12px; padding: 4px 6px; }
  #atlas { height: 560px; }
  .callout { font-size: 14px; padding: 14px 16px; }
  .detail-pane { gap: 16px; }
  .charts-grid { gap: 10px; }
  .essay { font-size: 15px; }
  .essay > p:first-of-type::first-letter { font-size: 44px; }
  .essay h3 { font-size: 19px; margin-top: 32px; }
  .eqn { font-size: 12px; padding: 12px; }
  .fig { padding: 12px; }
}
</style>
</head>
<body>

<header>
  <div class="wrap">
    <div class="super">Antikythera × Disintegrator · companion artifact</div>
    <h1>Agentworld<br><em>An atlas of agentic macroeconomics</em></h1>
    <p class="lead">A Monte Carlo sandbox for a planetary economy composed of <b>8 billion humans</b> and <b>800 billion AI agents</b> (it's worth 100xing that latter figure in future work). This atlas primarily isolates one variable through twenty-five scenarios: at one limit, agents <em>dissolve</em> economic intermediation (transaction barriers fall and middle layers thin out), and at the other, agents <em>fractally multiply</em> economic intermediation — every trade spawns sub-trades on top of itself. Both limits are stable equilibria of the same underlying technology, and which one materializes in reality is an open question. What this dashboard offers is a sample of distributions across the variable space between them.</p>
    <div class="meta">
      <span>25 scenarios</span>
      <span>66K importance-weighted prototypes per scenario</span>
      <span>200 steps · 200K prototype pairs sampled per step</span>
      <span>1 step ≈ 1 quarter · e.g. 2026 → 2076</span>
    </div>
  </div>
</header>

<section>
  <div class="wrap">
    <h2><span class="marker">§1</span> Introduction</h2>
    <p class="sub">A working-paper exposition of what this dashboard is and what is being computed. Every chart from §2 onward presupposes the definitions developed here.</p>

    <div class="essay">

      <p><b>What does the planetary economy do when the population of economic actors expands, within a few years, from roughly eight billion humans to roughly eight billion humans plus eight hundred billion AI agents?</b> If anything, eight hundred billion is an underestimation: the inference cost of a capable agent is now within an order of magnitude of the cost of the electricity that runs it, and the rails for high-frequency, sub-cent, autonomous payments are being laid as this is written — but it's a nice starting point. The real question is what regime of <em>intermediation</em> a hundred-to-one ratio of agents to humans selects for. Two regimes are equally consistent with the underlying technology. In the first, agents act as a kind of economic solvent: they evaporate transaction costs, dissolve middle-layer firms whose entire value-add was coordination, and flatten the economy into a continuous bilateral surface. In the second, agents act according to exocapitalist principles: every existing market spawns sub-markets, every sub-market spawns sub-sub-markets, and a single delivery to a human's door eventually involves thousands of priced micro-transactions that no human ever sees. We do not know, in 2026, which of these will materialize, in what proportion, in what sectors. The artifact you are reading is an attempt to clarify what each regime would cost, and what diagnostics one would need to tell which regime one is in before it is too late to intervene (good luck).</p>

      <p>The work is pretty modest. It runs a vectorized agent-economy simulator across twenty-five named scenarios that bracket the variable space, and reports a small set of summary statistics in a way that is pretty honest about the speculative load each parameter carries. It's best to think of this as less of a forecast and more of a controlled exercise in <em>what would have to be true</em> for this metric to behave that way under that regime. The hope is that a reader can sit with the atlas in §2, scrub through the scenarios in §3, and develop intuitions about a parameter space that is otherwise too large and too unfamiliar to reason about by hand.</p>

      <h3><span class="num">1.1</span> The question we are asking the simulator</h3>

      <p>The single dial we turn, across the twenty-five scenarios, is a scalar $\alpha \in [0, 1]$. $\alpha$ is a proxy for the degree to which trades in the economy are allowed to spawn further trades on top of themselves. At $\alpha = 0$ every exchange is one direct exchange — a buyer and a seller meet, agree, and the value moves; nothing intermediates. At $\alpha = 1$ every base exchange routes through layers of derivative sub-trades, fees, repackaged rights, attention markets, and metadata markets, each one adding overhead and each one (potentially) priced as a "real" economic event by national-accounts standards. Our current economic world sits somewhere in the middle, varying by sector and jurisdiction.</p>

      <figure class="fig">
        <svg class="fig-body" viewBox="0 0 720 130" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="The smooth-striated continuum from alpha = 0 (Smoothworld) to alpha = 1 (Baroqueworld)">
          <defs>
            <linearGradient id="alphaGrad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stop-color="#5fa572"/>
              <stop offset="50%" stop-color="#b89a55"/>
              <stop offset="100%" stop-color="#c25a5a"/>
            </linearGradient>
          </defs>
          <rect x="40" y="36" width="640" height="22" rx="3" fill="url(#alphaGrad)" opacity="0.85"/>
          <line x1="40" y1="58" x2="40" y2="68" stroke="#9ea2a8" stroke-width="1"/>
          <line x1="200" y1="58" x2="200" y2="64" stroke="#9ea2a8" stroke-width="1"/>
          <line x1="360" y1="58" x2="360" y2="68" stroke="#9ea2a8" stroke-width="1"/>
          <line x1="520" y1="58" x2="520" y2="64" stroke="#9ea2a8" stroke-width="1"/>
          <line x1="680" y1="58" x2="680" y2="68" stroke="#9ea2a8" stroke-width="1"/>
          <text x="40"  y="84" fill="#9ea2a8" font-family="JetBrains Mono, monospace" font-size="11" text-anchor="middle">α = 0.00</text>
          <text x="360" y="84" fill="#9ea2a8" font-family="JetBrains Mono, monospace" font-size="11" text-anchor="middle">0.50</text>
          <text x="680" y="84" fill="#9ea2a8" font-family="JetBrains Mono, monospace" font-size="11" text-anchor="middle">1.00</text>
          <text x="40"  y="22" fill="#5fa572" font-family="Iowan Old Style, Georgia, serif" font-size="14" font-style="italic">Smoothworld</text>
          <text x="680" y="22" fill="#c25a5a" font-family="Iowan Old Style, Georgia, serif" font-size="14" font-style="italic" text-anchor="end">Baroqueworld</text>
          <text x="40"  y="112" fill="#e7e8ea" font-family="Iowan Old Style, Georgia, serif" font-size="13">direct trade · no folding</text>
          <text x="680" y="112" fill="#e7e8ea" font-family="Iowan Old Style, Georgia, serif" font-size="13" text-anchor="end">recursive sub-markets · deep folding</text>
        </svg>
        <figcaption><span class="figlabel">Figure 1</span><b>The smooth-striated continuum.</b> The single parameter $\alpha$ is a proxy for the depth and rate at which a base trade is allowed to spawn derivative sub-trades. $\alpha$ enters the engine in two places: it raises the per-trade transaction cost by a small additive term (so highly striated economies are also slightly more expensive per base trade), and it raises folding propensity as $\alpha^{1.4}$, so the cascade depth grows super-linearly as $\alpha \to 1$.</figcaption>
      </figure>

      <h3><span class="num">1.2</span> What the simulator is</h3>

      <p>We are modeling off of a population of $H = 8 \times 10^{9}$ humans and $A = 8 \times 10^{11}$ AI agents, represented through importance-weighted prototypes ($\approx 6.6\text{M}$ sampled prototypes carry the full population's mass). At every step of a two-hundred-step run, the engine draws on the order of $2 \times 10^{5}$ random pairs of trading partners. For each pair it asks four questions in sequence: would this trade create surplus; what would it cost; would any of the three governance filters block it; and, if it does execute, does it spawn a folding cascade of sub-trades on top of itself. Surviving trades transfer wealth between the parties and accumulate into the run-level aggregates that the rest of this dashboard plots.</p>

      <p>Human and agentic activities are processed through the same trade engine — the matching, the surplus computation, the filters, and the fold rules are type-blind once a pair has been drawn. <em>Type</em> matters only at three points: which prototypes get drawn into pairs (population mass and the trade-rate multiplier discussed below), how the prototypes are seeded (capability, autonomy, alignment, wealth all sample from different distributions), and how their resulting surplus maps to welfare downstream (per-capita welfare divides by humans only, and a "demand-modulation" mode in some scenarios further discounts pure agent-to-agent surplus). That being said, agents and humans do not behave the same (further work can be done here to turn this work into its own set of modulable variables):</p>

      <ul>
        <li><b>Population mass.</b> $A / H = 100$ agents per human at the demographic level. Most random pairings are A2A.</li>
        <li><b>Trade speed.</b> An AI agent can attempt thousands of trades in the time a human attempts one. In the fractal-trade scenarios we model this with a trade-rate multiplier $\rho_{\text{agent}} = 100$ on top of the demographic ratio, so humans appear in roughly $1$ in $10{,}000$ executed trades. In smooth-limit scenarios $\rho_{\text{agent}} = 1$ — which proposes a counterfactual world in which agents trade at human speed.</li>
        <li><b>Wealth.</b> Human wealth is lognormal with $\bar{w}_H \approx 100$ per prototype; agent wealth is Pareto-tailed with $\bar{w}_A \approx 5$. Agents are individually poorer but collectively far wealthier.</li>
        <li><b>Capability.</b> Agent capability $c_A \sim \mathcal{N}(0.72,\, 0.20^{2})$; human capability $c_H \sim \mathcal{N}(0.45,\, 0.18^{2})$. Agents on average bring better matching, pricing, and execution to any trade they enter.</li>
        <li><b>Autonomy and alignment.</b> Agents act independently $\approx 85\%$ of the time on average, humans $\approx 55\%$; human alignment values are spread wider ($\sigma_{H} \approx 0.45$) than agent values ($\sigma_{A} \approx 0.25$), so a human-touching pair is more likely to fail the alignment filter than a pure agent-agent pair.</li>
      </ul>

      <h3><span class="num">1.3</span> How a single trade resolves</h3>

      <p>The decision a pair $(a, b)$ faces, on every step, is whether the surplus it could generate exceeds the cost of generating it, and then whether the three Matryoshka governance filters — law, market, individual alignment — let it through. Let $c_a, c_b \in [0,1]$ denote the parties' capabilities, $s_{ab} \in [0,1]$ the cosine compatibility of their sectoral profiles, and $v$ the base match volume. Surplus is a capability-weighted match score with an additive noise term:</p>

      <div class="eqn">$$
S_{ab} \;=\; v \cdot \Bigl(\, 0.05 \;+\; 0.5\, c_a\, c_b\, s_{ab} \;+\; \varepsilon \,\Bigr),
\qquad \varepsilon \sim \mathcal{N}(0,\, 0.05^{2}) \tag{1}
$$</div>

      <p>where $\varepsilon$ is Gaussian by default; an opt-in Student-$t$ copula calibrated to BEA 2022 input-output correlations is available in the calibrated-noise scenarios. Cost is the sum of a hard friction floor $\varphi_0$, a Coasean term controlled by an exponent $\kappa$ that rewards the better-matched pair, an $\alpha$-dependent striation term, and a cross-stack penalty in the compatibility $\sigma_{ab} \in [0,1]$:</p>

      <div class="eqn">$$
C_{ab} \;=\; \varphi_{0}
\;+\; \varphi_{1}\,\bigl( 1 - \min(c_a, c_b) \bigr)^{\kappa}
\;+\; 0.020\, \alpha \,\bigl( 1 + 0.3\,(1 - \sigma_{ab}) \bigr)
\;+\; 0.015\,(1 - \sigma_{ab}) \tag{2}
$$</div>

      <p>The trade clears iff $S_{ab} \geq C_{ab}$ <em>and</em> none of the three filters reject it. Each filter invokes a Bernoulli with probability that scales with relevant disagreement, like cross-stack incompatibility for the law layer, sector mismatch and alignment distance for the market layer, or alignment distance attenuated by autonomy for the individual layer. We use $\Delta_{ab}$ for the alignment distance and $u_{ab}$ for the mean autonomy of the pair:</p>

      <div class="eqn">$$
\begin{aligned}
\Pr(\text{law reject})    \;&=\; 0.01 \;+\; 0.04\,(1 - \sigma_{ab}) \\
\Pr(\text{market reject}) \;&=\; 0.02 \;+\; 0.06\,(1 - s_{ab}) \;+\; 0.04\, |\Delta_{ab}| \\
\Pr(\text{align reject})  \;&=\; 0.03 \;+\; 0.20\, |\Delta_{ab}|\,\bigl( 1 - 0.5\, u_{ab} \bigr)
\end{aligned} \tag{3}
$$</div>

      <p>A trade rejected by any one of the three contributes nothing to either nominal GDP or real welfare; a trade that clears contributes $S_{ab}$ to the real-welfare ledger and $S_{ab} + C_{ab}$ to the nominal-GDP ledger, and is then handed to the folding operator.</p>

      <figure class="fig">
        <svg class="fig-body" viewBox="0 0 760 240" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Schematic of the per-step trade pipeline">
          <defs>
            <marker id="arrowhead" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 z" fill="#6a6d72"/>
            </marker>
          </defs>
          <rect x="18" y="86" width="118" height="52" rx="4" fill="#1a1d22" stroke="#2a2d33"/>
          <text x="77" y="108" fill="#e7e8ea" font-family="Iowan Old Style, Georgia, serif" font-size="12.5" text-anchor="middle">draw pair</text>
          <text x="77" y="124" fill="#9ea2a8" font-family="JetBrains Mono, monospace" font-size="10" text-anchor="middle">~2×10⁵ / step</text>
          <line x1="136" y1="112" x2="166" y2="112" stroke="#6a6d72" stroke-width="1" marker-end="url(#arrowhead)"/>

          <rect x="170" y="86" width="118" height="52" rx="4" fill="#1a1d22" stroke="#2a2d33"/>
          <text x="229" y="108" fill="#e7e8ea" font-family="Iowan Old Style, Georgia, serif" font-size="12.5" text-anchor="middle">surplus ≥ cost ?</text>
          <text x="229" y="124" fill="#9ea2a8" font-family="JetBrains Mono, monospace" font-size="10" text-anchor="middle">S vs C  (1, 2)</text>
          <line x1="288" y1="112" x2="318" y2="112" stroke="#6a6d72" stroke-width="1" marker-end="url(#arrowhead)"/>

          <rect x="322" y="40" width="118" height="44" rx="4" fill="#1a1d22" stroke="#2a2d33"/>
          <text x="381" y="58" fill="#e7e8ea" font-family="Iowan Old Style, Georgia, serif" font-size="12" text-anchor="middle">law filter</text>
          <text x="381" y="73" fill="#9ea2a8" font-family="JetBrains Mono, monospace" font-size="10" text-anchor="middle">cross-stack</text>

          <rect x="322" y="92" width="118" height="44" rx="4" fill="#1a1d22" stroke="#2a2d33"/>
          <text x="381" y="110" fill="#e7e8ea" font-family="Iowan Old Style, Georgia, serif" font-size="12" text-anchor="middle">market filter</text>
          <text x="381" y="125" fill="#9ea2a8" font-family="JetBrains Mono, monospace" font-size="10" text-anchor="middle">sector + align</text>

          <rect x="322" y="144" width="118" height="44" rx="4" fill="#1a1d22" stroke="#2a2d33"/>
          <text x="381" y="162" fill="#e7e8ea" font-family="Iowan Old Style, Georgia, serif" font-size="12" text-anchor="middle">alignment</text>
          <text x="381" y="177" fill="#9ea2a8" font-family="JetBrains Mono, monospace" font-size="10" text-anchor="middle">|Δalign| · (1−auto)</text>

          <line x1="440" y1="62"  x2="468" y2="100" stroke="#6a6d72" stroke-width="1"/>
          <line x1="440" y1="114" x2="468" y2="114" stroke="#6a6d72" stroke-width="1" marker-end="url(#arrowhead)"/>
          <line x1="440" y1="166" x2="468" y2="128" stroke="#6a6d72" stroke-width="1"/>

          <rect x="470" y="86" width="118" height="52" rx="4" fill="#14161a" stroke="#b89a55"/>
          <text x="529" y="108" fill="#e7e8ea" font-family="Iowan Old Style, Georgia, serif" font-size="12.5" text-anchor="middle">trade executes</text>
          <text x="529" y="124" fill="#b89a55" font-family="JetBrains Mono, monospace" font-size="10" text-anchor="middle">+ wealth transfer</text>

          <line x1="588" y1="100" x2="618" y2="60" stroke="#6a6d72" stroke-width="1" marker-end="url(#arrowhead)"/>
          <line x1="588" y1="124" x2="618" y2="180" stroke="#6a6d72" stroke-width="1" marker-end="url(#arrowhead)"/>

          <rect x="622" y="34" width="124" height="52" rx="4" fill="#1a1d22" stroke="#5fa572"/>
          <text x="684" y="56" fill="#5fa572" font-family="Iowan Old Style, Georgia, serif" font-size="12.5" text-anchor="middle">real welfare</text>
          <text x="684" y="72" fill="#9ea2a8" font-family="JetBrains Mono, monospace" font-size="10" text-anchor="middle">+= surplus</text>

          <rect x="622" y="156" width="124" height="68" rx="4" fill="#1a1d22" stroke="#c25a5a"/>
          <text x="684" y="178" fill="#c25a5a" font-family="Iowan Old Style, Georgia, serif" font-size="12.5" text-anchor="middle">folding cascade</text>
          <text x="684" y="194" fill="#9ea2a8" font-family="JetBrains Mono, monospace" font-size="10" text-anchor="middle">+= surplus + cost</text>
          <text x="684" y="210" fill="#9ea2a8" font-family="JetBrains Mono, monospace" font-size="10" text-anchor="middle">+ Σ nominal_d</text>

          <text x="684" y="20" fill="#9ea2a8" font-family="JetBrains Mono, monospace" font-size="10" text-anchor="middle">→ welfare ledger</text>
          <text x="684" y="240" fill="#9ea2a8" font-family="JetBrains Mono, monospace" font-size="10" text-anchor="middle">→ nominal-GDP ledger</text>
        </svg>
        <figcaption><span class="figlabel">Figure 2</span><b>The per-step trade pipeline.</b> We pick a pair, compare surplus against cost (eqs.&nbsp;1–2), push through three independent governance filters in sequence (eq.&nbsp;3), and the surviving trade contributes simultaneously to two ledgers — the welfare ledger ($S_{ab}$ only) and the nominal-GDP ledger ($S_{ab} + C_{ab}$, plus everything the folding cascade adds).</figcaption>
      </figure>

      <h3><span class="num">1.4</span> The folding operator</h3>

      <p>Folding is the mechanism that lets the nominal ledger run away from the welfare ledger. When a base trade clears, the engine considers whether to spawn derivative sub-trades on top of it — a derivative on the trade, then a derivative on the derivative, and so on, up to a per-scenario maximum depth $D$. Let $p_{0}$ denote the scenario's base folding propensity. The propensity to fold at depth $d$ depends on $\alpha$ and decays geometrically:</p>

      <div class="eqn">$$
p_{d} \;=\; p_{0}\;\cdot\;\alpha^{1.4}\;\cdot\;0.85^{\,d - 1},
\qquad d = 1, 2, \ldots, D \tag{4}
$$</div>

      <p>At each depth, the cascade branches by a factor $\beta(\alpha) = \beta_{0}\,(0.6 + 0.4\,\alpha)$ that itself rises with $\alpha$ (deeper economies are also wider economies), each layer is amplified by a nominal multiplier $m$, and each layer adds to the nominal ledger while shaving a small fraction off the real ledger. The default kernel is geometric and deterministic at the layer level; we use an opt-in Hawkes self-exciting kernel to preserve the same mean but inject realistic per-depth variance and self-excitation calibrated to the Bacry &amp; Muzy 2015 endogeneity ratio. Writing $N_{d}$ for the nominal contribution and $R$ for the base real surplus of the trade, with $\eta = $ <code>fold_real_efficiency</code> $&lt; 1$, the per-depth bookkeeping is:</p>

      <div class="eqn">$$
\begin{aligned}
N_{d}      \;&=\; N_{d-1}\;\cdot\;\beta(\alpha)\;\cdot\;m\;\cdot\;p_{d}, \\
L_{d}      \;&=\; R\;\cdot\;\bigl( 1 - \eta^{\,d} \bigr)\;\cdot\;p_{d}, \\
\Delta\text{Nominal} \;&=\; \sum_{d=1}^{D} N_{d}, \qquad
\Delta\text{Real} \;=\; -\,\max_{d}\, L_{d}.
\end{aligned} \tag{5}
$$</div>

      <figure class="fig">
        <svg class="fig-body" viewBox="0 0 720 240" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="A folding cascade — the base trade spawns sub-trades over six depths, with nominal GDP accumulating multiplicatively and real welfare leaking at each layer">
          <text x="40" y="30"  fill="#6a6d72" font-family="JetBrains Mono, monospace" font-size="10">depth 0</text>
          <text x="40" y="68"  fill="#6a6d72" font-family="JetBrains Mono, monospace" font-size="10">depth 1</text>
          <text x="40" y="108" fill="#6a6d72" font-family="JetBrains Mono, monospace" font-size="10">depth 2</text>
          <text x="40" y="148" fill="#6a6d72" font-family="JetBrains Mono, monospace" font-size="10">depth 3</text>
          <text x="40" y="188" fill="#6a6d72" font-family="JetBrains Mono, monospace" font-size="10">…</text>

          <line x1="360" y1="30" x2="270" y2="60" stroke="#6a6d72" stroke-width="0.7"/>
          <line x1="360" y1="30" x2="450" y2="60" stroke="#6a6d72" stroke-width="0.7"/>
          <circle cx="360" cy="26" r="7" fill="#b89a55"/>

          <circle cx="270" cy="64" r="5.5" fill="#9077c2"/>
          <circle cx="450" cy="64" r="5.5" fill="#9077c2"/>
          <line x1="270" y1="64" x2="220" y2="100" stroke="#6a6d72" stroke-width="0.6"/>
          <line x1="270" y1="64" x2="320" y2="100" stroke="#6a6d72" stroke-width="0.6"/>
          <line x1="450" y1="64" x2="400" y2="100" stroke="#6a6d72" stroke-width="0.6"/>
          <line x1="450" y1="64" x2="500" y2="100" stroke="#6a6d72" stroke-width="0.6"/>

          <circle cx="220" cy="104" r="4.5" fill="#5b8ec4"/>
          <circle cx="320" cy="104" r="4.5" fill="#5b8ec4"/>
          <circle cx="400" cy="104" r="4.5" fill="#5b8ec4"/>
          <circle cx="500" cy="104" r="4.5" fill="#5b8ec4"/>
          <g stroke="#6a6d72" stroke-width="0.5">
            <line x1="220" y1="104" x2="195" y2="140"/><line x1="220" y1="104" x2="245" y2="140"/>
            <line x1="320" y1="104" x2="295" y2="140"/><line x1="320" y1="104" x2="345" y2="140"/>
            <line x1="400" y1="104" x2="375" y2="140"/><line x1="400" y1="104" x2="425" y2="140"/>
            <line x1="500" y1="104" x2="475" y2="140"/><line x1="500" y1="104" x2="525" y2="140"/>
          </g>

          <g fill="#5fa572" opacity="0.9">
            <circle cx="195" cy="144" r="3.5"/><circle cx="245" cy="144" r="3.5"/>
            <circle cx="295" cy="144" r="3.5"/><circle cx="345" cy="144" r="3.5"/>
            <circle cx="375" cy="144" r="3.5"/><circle cx="425" cy="144" r="3.5"/>
            <circle cx="475" cy="144" r="3.5"/><circle cx="525" cy="144" r="3.5"/>
          </g>

          <g fill="#6a6d72" opacity="0.5">
            <circle cx="180" cy="180" r="2"/><circle cx="200" cy="180" r="2"/><circle cx="240" cy="180" r="2"/><circle cx="260" cy="180" r="2"/>
            <circle cx="290" cy="180" r="2"/><circle cx="310" cy="180" r="2"/><circle cx="340" cy="180" r="2"/><circle cx="360" cy="180" r="2"/>
            <circle cx="380" cy="180" r="2"/><circle cx="400" cy="180" r="2"/><circle cx="430" cy="180" r="2"/><circle cx="450" cy="180" r="2"/>
            <circle cx="470" cy="180" r="2"/><circle cx="490" cy="180" r="2"/><circle cx="520" cy="180" r="2"/><circle cx="540" cy="180" r="2"/>
          </g>

          <line x1="600" y1="26"  x2="620" y2="26"  stroke="#c25a5a" stroke-width="1"/>
          <line x1="600" y1="64"  x2="624" y2="64"  stroke="#c25a5a" stroke-width="1"/>
          <line x1="600" y1="104" x2="630" y2="104" stroke="#c25a5a" stroke-width="1"/>
          <line x1="600" y1="144" x2="640" y2="144" stroke="#c25a5a" stroke-width="1"/>
          <line x1="600" y1="180" x2="660" y2="180" stroke="#c25a5a" stroke-width="1"/>
          <text x="668" y="30"  fill="#c25a5a" font-family="JetBrains Mono, monospace" font-size="9.5">+N₀</text>
          <text x="668" y="68"  fill="#c25a5a" font-family="JetBrains Mono, monospace" font-size="9.5">+N₁</text>
          <text x="668" y="108" fill="#c25a5a" font-family="JetBrains Mono, monospace" font-size="9.5">+N₂</text>
          <text x="668" y="148" fill="#c25a5a" font-family="JetBrains Mono, monospace" font-size="9.5">+N₃</text>
          <text x="668" y="184" fill="#c25a5a" font-family="JetBrains Mono, monospace" font-size="9.5">…</text>

          <text x="100" y="26"  fill="#5fa572" font-family="JetBrains Mono, monospace" font-size="9.5">welfare = R</text>
          <text x="100" y="68"  fill="#5fa572" font-family="JetBrains Mono, monospace" font-size="9.5">R · η</text>
          <text x="100" y="108" fill="#5fa572" font-family="JetBrains Mono, monospace" font-size="9.5">R · η²</text>
          <text x="100" y="148" fill="#5fa572" font-family="JetBrains Mono, monospace" font-size="9.5">R · η³</text>
          <text x="100" y="184" fill="#5fa572" font-family="JetBrains Mono, monospace" font-size="9.5">→ 0</text>

          <text x="360" y="222" fill="#9ea2a8" font-family="Iowan Old Style, Georgia, serif" font-size="12" text-anchor="middle" font-style="italic">nominal: Σ N_d grows multiplicatively  ·  real: bounded by R and leaks per layer</text>
        </svg>
        <figcaption><span class="figlabel">Figure 3</span><b>A folding cascade.</b> A base trade (gold, depth $0$) spawns sub-trades that themselves spawn sub-trades, governed by $\alpha$ and the per-depth branching factor $\beta(\alpha)$. The right margin tracks the additive contributions $N_{d}$ to the nominal-GDP ledger; the left margin tracks the real-welfare ledger, which is bounded by the base surplus $R$ and erodes by a factor $\eta &lt; 1$ at each layer. In a low-$\alpha$ scenario the cascade rarely makes it past depth $0$ or $1$ and the two ledgers track each other. In a high-$\alpha$ scenario the cascade sustains itself across many layers and the nominal ledger separates from the real ledger by orders of magnitude.</figcaption>
      </figure>

      <h3><span class="num">1.5</span> The diagnostics that follow from the model</h3>

      <p>The whole point of carrying both ledgers is to take their ratio. Let $\mathcal{T}_{t}$ denote the set of trades that cleared at step $t$. Real welfare and nominal GDP accumulate as</p>

      <div class="eqn">$$
W \;=\; \sum_{t}\,\sum_{(a,b)\in\mathcal{T}_{t}} S_{ab},
\qquad
G \;=\; \sum_{t}\,\sum_{(a,b)\in\mathcal{T}_{t}} \bigl( S_{ab} + C_{ab} + \Delta\text{Nominal}_{ab}\bigr).
\tag{6}
$$</div>

      <p>The dashboard's central diagnostic is the <b>exo-baroque index</b> (exo from exocapitalism, baroque from Deleuze, basically just meaning how insane of a meta-meta-meta-deriviative stack exists on top of any given trade). It's defined as the ratio of these two ledgers:</p>

      <div class="eqn">$$
\mathrm{EBI} \;=\; \frac{G}{W} \;=\; \frac{\sum_{t} \text{nominal\_GDP}_{t}}{\sum_{t} \text{real\_welfare}_{t}}. \tag{7}
$$</div>

      <p>$\mathrm{EBI} = 1$ is the parity level (no ficticious capital), meaning that every unit of measured economic activity reached a human as actual consumption. $\mathrm{EBI} = 100$ means $99\%$ of measured activity was trades-of-trades that never delivered anything to a human. $\mathrm{EBI}$ in the low millions, which a few of the high-$\alpha$ scenarios do reach, means the on-paper economy and the consumed economy live on different planets. $\mathrm{EBI}$ is plotted on a log scale because it ranges over six orders of magnitude across the scenario set. Because it is a ratio, $\mathrm{EBI}$ is dimensionless and scenario-comparable; absolute values of the underlying ledgers are not.</p>

      <p>A subtlety worth flagging here, because one of the conclusions in §2 turns on it: $\mathrm{EBI}$ and absolute per-capita welfare are not the same diagnostic and can move in different directions. A regime with $\mathrm{EBI} = 10^{6}$ — most of the on-paper economy is parasitic accounting that no human consumed — can still produce substantial per-capita welfare, because the on-paper economy being printed is enormous and even a tiny share of it reaching humans is a sizeable absolute amount. <i>Productive Cathedral</i> in the scenario set carries both attributes: high $\mathrm{EBI}$ (parasitic share dominant) and high per-capita welfare (the small productive share is large in absolute terms). Two readers asking different questions of the same economy — <em>are people materially better off?</em> and <em>is the economy connected to anything humans experience?</em> — can come to opposite conclusions and both be right. $\mathrm{EBI}$ is the diagnostic for the second question; per-capita welfare is the diagnostic for the first; neither subsumes the other.</p>

      <p>The other quantities the dashboard plots are downstream of the same ledgers, and are introduced briefly here so that the charts in §4–§7 read without reference back. <b>Real welfare</b> $W$ is the sum, across the run, of the surplus that survived the filters; <b>per-capita welfare</b> divides that by $H = 8 \times 10^{9}$ humans only, since agent surplus that never benefits a human does not count as welfare on this dashboard:</p>

      <div class="eqn">$$
w \;=\; \frac{W}{H} \;\cdot\; 10^{3} \qquad \text{(unitless; scaled for legibility)}. \tag{8}
$$</div>

      <p><em>Compare scenarios by ratios, not absolute values.</em> <b>Nominal GDP</b> $G$ is the sum of cleared $(S + C)$ plus everything the folding cascade contributed. <b>Fold depth</b> is the height of the tallest derivative tower seen in any single base trade in a step — depth $0$ means no sub-trades happened, depth $7$ means a base trade had a seven-layer stack of derivatives wrapped around it. <b>Human legibility</b> $\ell$ is the share of executed trades in which at least one party is a human, equivalent to one minus the agent-to-agent share:</p>

      <div class="eqn">$$
\ell \;=\; \pi_{\text{H2H}} + \pi_{\text{H2A}} \;=\; 1 - \pi_{\text{A2A}}. \tag{9}
$$</div>

      <p>$\ell$ is a measure of how much of the economy a human can in principle observe, contest, or audit at last-mile resolution; it sits around $\ell \in [10^{-3},\,3 \times 10^{-2}]$ in smooth scenarios and falls to $\ell \in [10^{-5},\,10^{-4}]$ in fractal scenarios with the $\rho_{\text{agent}} = 100$ multiplier on. <b>Wealth Gini</b> is the standard $[0, 1]$ inequality measure across the combined human-and-agent population. The <b>three filters</b> — law, market, alignment (eq.&nbsp;3) — are reported in §4 as rejection-rate decompositions, so the reader can see which institutional layer is doing the most blocking under each scenario.</p>

      <p>Every chart from §2 onward is drawn as a <em>solid line</em> at the median across $N = 64$ random seeds with a <em>shaded band</em> covering the $[P_{5},\, P_{95}]$ envelope. The band shows how much randomness within a fixed scenario configuration could shift the result. A wide band means the scenario is sensitive to noise; a tight band means the outcome is robust under fixed assumptions. <em>The band is not a probability that the world will land in this range</em> — it is just a sensitivity reading on the simulation under fixed parameters.</p>

      <h3><span class="num">1.6</span> What we are trying to settle</h3>

      <p>Our goal is pretty narrow and specific: to produce a usable atlas of the parameter space inside which the next decade of mechanism-design choices about the agent economy will be made. We are not arguing that any one of the twenty-five scenarios is the world that will arrive, but we are arguing that the <em>shape</em> of the trade-off — that high $\alpha$ produces high nominal GDP and low welfare, that the middle of the $\alpha$ range is the default landing spot in the absence of active mechanism design, that $\mathrm{EBI}$ is the diagnostic that distinguishes "the economy got bigger" from "the economy got more legible to itself and less to us" — is robust across plausible parameterizations of the model, and is therefore worth taking seriously as a frame for policy thinking.</p>

      <p>A note on the substrate. Twenty-one of the twenty-five scenarios on this dashboard run on the empirical substrate by default — sector-block trading network calibrated to Atalay et al. 2011, t-copula correlated noise calibrated to the BEA 2022 input-output matrix, and a self-exciting Hawkes folding kernel calibrated to the Bacry &amp; Muzy 2015 endogeneity ratio. The four exclusions are the productive-folding scenarios (<i>Productive Cathedral</i>, <i>Productive Baroque</i>, <i>Derivatives Revolution</i>) and one adversarial-search variant (<i>Baroque (High Welfare)</i>) whose hand-tuned parameters do not survive the substrate switch. This means that when you compare <i>Slop Market</i> to <i>Productive Cathedral</i> across the high-$\alpha$ band, the only meaningful difference is productive folding — not the substrate stack. When you compare <i>Coasean Paradise</i> to <i>Baroque Cathedral</i>, both are on the same substrate. Welfare numbers on this dashboard are systematically higher than they would be on a well-mixed default — by roughly 60% across the board — because realistic trading networks pre-match compatible pairs, raising matching efficiency. Empirical anchoring changes the welfare height the basins can support, but not which basin the scenario is in. The conclusions in §2 are about the basins themselves.</p>

      <p>The six conclusions the simulator keeps surfacing, across scenarios and seeds, are developed in the callout in §2 once the atlas is in front of you. In short: <em>(i)</em> the direct-trade regime is unstable on its own — staying there is an active engineering task, not a passive default; <em>(ii)</em> productive sub-markets raise welfare in absolute terms but do not move the share of measured activity that reaches humans, so $\mathrm{EBI}$ and welfare can both come out high in the same regime; <em>(iii)</em> a targeted tax on agent-to-agent transaction volume is the one corrective lever the simulator finds, and it is bounded by the share of nominal that would have produced welfare if not deterred; <em>(iv)</em> wealth inequality moves only when bargaining power is equalised before trades happen, not by post-trade redistribution; <em>(v)</em> the share of the economy that any human is party to collapses with $\alpha$ independently of welfare, raising a separate concern about democratic legibility; and <em>(vi)</em> even when agents are free to learn their own preferred $\alpha$, they settle at upper-mid $\alpha$ rather than at either extreme. The atlas in §2 makes (i) and (ii) visible at a glance. The detail panes in §4, the §5 Sankey, and the §6 overlays make the rest legible.</p>

      <div class="essay-aside">Again, this is not a forecast — the numbers are stylized and the parameters are explicitly bracketed in the form of scenarios. This also isn't a normative argument; both poles are plausible and the artifact tries to be agnostic about them. This is also not complete; the twenty-five scenarios are samples from an obviously infinite set, and the model itself privileges last-mile material consumption as the welfare denominator in a way that the companion exo-engine deliberately rejects. For the rules of what is and is not claimed — which parameters are calibrated to public empirical data, which are stipulated for face validity, and which are deliberately speculative — the epistemic-status panel in <code>docs/concepts/epistemic_status.md</code> and the empirical-anchor table at the foot of this page are better authoritative references.</div>

    </div>
  </div>
</section>

<section>
  <div class="wrap">
    <h2><span class="marker">§2</span> The atlas</h2>
    <p class="sub">Each point is one scenario at its terminal step. The <b>x-axis</b> is α — how complicated trades are allowed to get, on [0, 1]. The <b>y-axis</b> is the exo-baroque index (EBI) — nominal GDP divided by real welfare, log-scaled. <b>Color</b> encodes per-capita real welfare; greener is better. The dashed line at EBI = 1 represents parity where every unit of measured economic activity matched a unit of human welfare. Anything sustained above that line is measured activity the human side of the economy never received — accounting that lives only in agent-to-agent ledgers.</p>
    <p class="sub"><b>What to read off the chart.</b> Bottom-left: low α, no folding, accounting tracks welfare. Top-right: high α, recursive folding, accounting separates from welfare by orders of magnitude. A point that sits high on the y-axis <i>and</i> dim in color is a kind of failure case as far as human experience goes – a regime printing volume without producing anything humans consume.</p>
    <div class="atlas-grid">
      <div class="chart-box">
        <div class="chart-title">α × exo-baroque index · color = per-capita welfare</div>
        <div class="chart-caption"><b>Dashed horizontal:</b> EBI = 1 – the parity line where welfare equals nominal GDP. <b>Color</b> is per-capita welfare scaled by 10³ (model state is unchanged; the scaling exists so values like Coasean Paradise ≈ 279 and Slop Market ≈ 25 are legible at a glance instead of collapsing into the raw per-capita figures around 0.28 and 0.025). Hover any point for the scenario label, exact α, EBI, and welfare.</div>
        <div id="atlas" style="height:520px;"></div>
      </div>
      <div class="callout">
        <p style="margin: 0 0 14px;">
          The right-hand limit — the <b>fractal-trade economy</b>, where every base trade spawns layers of derivative sub-trades — is at least as plausible as the left-hand limit, and is where the on-paper GDP gains in the late 2020s and 2030s will plausibly come from. <i>Coasean Paradise</i> sits in the bottom-left (everything is a direct trade). <i>Exo-Baroque Singularity</i> sits in the top-right (everything is folded into towers of sub-trades). Real economies are a weighted blend of the two, varying by sector and jurisdiction. <em>The atlas does not predict where any given regime lands. It clarifies what landing somewhere costs.</em>
        </p>
        <p style="margin: 0 0 14px;">
          <b>What the atlas does not show.</b> These terminal-step snapshots compress twenty-five trajectories into twenty-five dots. Two scenarios can land at the same coordinate by very different routes – a slow drift through the mid-α basin reads identically to a fast climb that overshoots and falls back. §4 unfolds each path as a six-chart panel; §5 stacks any subset of paths on a shared time axis so the route, not just the destination, becomes clear.
        </p>
        <p style="margin: 0;">
          <b>What this means for decisions.</b> Six conclusions fall out of the scenario set, in order of how load-bearing they are.</p>
        <p style="margin: 0 0 14px;">
          <b>(1) The direct-trade regime is unstable on its own.</b> The economy's direct-trade regime — where every transaction is a single observable exchange between two parties, with no derivatives or sub-markets stacked on top — does not hold itself in place. Whenever we let agents themselves decide how much to spawn sub-trades on the back of an existing trade, and we make that decision responsive to what they observe in the rest of the economy, the system collapses out of direct trade in roughly twenty steps (about five years on this clock). Two scenarios on the dashboard, <i>Recursive Simulation</i> and <i>Endogenous Baroque</i>, set this up explicitly: agents become more willing to spawn sub-markets the more sub-markets they see around them. Both slide into the layered, hard-to-audit regime quickly, regardless of where they start. The implication is that staying in the direct-trade regime requires active engineering, not just choosing not to intervene. Concretely: caps on how many derivative layers can stack on top of any base trade; a price floor on every transaction so the cheapest sub-trades can't exist; the right of individuals to veto trades on values grounds even when those trades would be profitable; a targeted tax on agent-to-agent transaction volume; <em>and</em> a contract-enforcement layer that can handle eight billion humans plus eight hundred billion agents at once. The popular reading of the direct-trade regime as a "shrunken state" — a libertarian default — has the institutional difficulty backwards. Direct trade is the harder thing to engineer, not the easier one.
        </p>
        <p style="margin: 0 0 14px;">
          <b>(2) Making the sub-markets useful raises welfare in absolute terms but doesn't restore the human share of measured activity.</b> When sub-markets layered on top of a base trade do real economic work — a derivative that's a genuine risk-pooling mechanism, a sub-market that's a genuine price-discovery mechanism, a layered trade that's a genuine liquidity transfer between parties who both benefit — the dashboard calls this <i>productive folding</i>. When sub-markets are pure overhead — fees stacked on fees, attention markets feeding metadata markets feeding rights markets, with nothing being delivered to a person at the end — the dashboard calls this <i>parasitic folding</i>. Real economies have both, in some proportion, and one of the things the simulator tries to clarify is what happens when you tilt that mix toward productive. The finding is more split than first impression suggests: productive folding <em>does</em> raise welfare, meaningfully. <i>Productive Cathedral</i> — high-α with the productive setting turned all the way up, on a realistic trading network with calibrated noise from US input-output data and self-exciting cascade dynamics drawn from financial-market data — produces the highest per-capita welfare in the entire high-α band of the atlas. The on-paper economy it prints is enormous; even a tiny share of it reaching humans is a substantial absolute amount of welfare. So if the question you bring to the simulator is <em>are people materially better off?</em> — productive folding helps, even at high α. What it does not do is move the share of measured activity that reaches humans. Roughly 99.99% of nominal GDP in <i>Productive Cathedral</i> still goes to agent-to-agent ledgers that no human consumes (the §5 Sankey shows this directly). EBI stays in the high band. So if the question you bring is <em>is the economy connected to anything humans experience?</em> — productive folding doesn't fix that. The absolute volume reaching humans grows because the volume <em>being printed</em> is enormous; the <em>fraction</em> that reaches them stays microscopic. The deeper implication is that EBI and welfare are partially decoupled diagnostics. A regime can score well on welfare and poorly on EBI at the same time, because absolute welfare scales with the size of the on-paper economy while the share-of-GDP reaching humans is a separate quantity that depends on the cascade structure. Two readers asking different questions of the same economy — <em>are people better off?</em> vs <em>can the population see the economy that nominally runs on its behalf?</em> — can come to opposite conclusions about <i>Productive Cathedral</i> and both be right. That isn't a defect of either diagnostic. It's a real feature of high-α-plus-productive-folding regimes that a single headline metric would paper over.
        </p>
        <p style="margin: 0 0 14px;">
          <b>(3) A targeted tax on agent-to-agent volume is the one corrective lever the simulator finds, and it's bounded by its own tax base.</b> A <i>Pigouvian tax</i> is a tax aimed at an activity that imposes a cost the rest of the economy pays for, but which doesn't show up in the activity's own price — the textbook example is a carbon tax. Here, the cost being paid is parasitic accounting: agent-to-agent transaction volume that no human ever consumes but which the rest of the economy's measurement systems treat as economic activity. Two scenarios run different versions of this lever. <i>Pigouvian Heavy</i> taxes 35% of all agent-to-agent transaction volume — both base trades and the volume the cascade spawns on top of them — and recycles the revenue back to humans, weighted toward the lower deciles. The result, at α≈0.6, is that EBI lands 25–30% below what it would be in the same configuration with no tax. Welfare doesn't crash. <i>Pigouvian Friction</i> is the same idea routed differently: a 15% tax recycled as a subsidy on the friction cost of any human-touching trade, which brings humans back into the economy through the supply side rather than as a cash transfer. The constraint that bounds them is sneaky and worth understanding directly. The tax is collected on volume, but its corrective effect — the part that lowers EBI rather than just transferring money around — depends on the share of that volume that <em>would have</em> become real surplus if the tax hadn't deterred it. In deep baroque regimes most of the activity being taxed wasn't going to produce welfare anyway, so the deterrence has nothing to grab onto. The parasitic ribbon dominates, the surplus-bearing share is small, and you can't compensate for that with a higher rate — past a certain point, raising the rate just stops the part of the activity that <em>would have</em> been productive, leaving the parasitic ribbon to fill the space. The §5 Sankey is the place to read this off: the ribbon labeled "recycled (Pigouvian)" can only get as thick as the surplus-bearing slice of the nominal flow, no matter how aggressively the rate is set.
        </p>
        <p style="margin: 0 0 14px;">
          <b>(4) Wealth inequality moves at the source, not after the fact.</b> The wealth Gini — the standard 0-to-1 inequality measure (0 = perfectly equal, 1 = one party owns everything) — moves in this simulator only when the asymmetry that produced the inequality in the first place is removed before the trades happen. <i>Universal Advocate</i>, the only scenario in the set that meaningfully compresses the Gini, raises agent capability across the entire population: every household, regardless of starting wealth, gets the same level of representation in any trade negotiation. The wealth distribution flattens because the bargaining-power gap that previously compounded across deciles has been closed at the source. The two contrast scenarios fill in the picture. <i>Public Defender</i> runs a more politically tractable version of the same idea: capability uplift targeted only to the lower deciles, leaving the upper deciles where they were. The Gini compresses, but less than under universal access — targeted access doesn't reach the asymmetry that produces inequality in high-skill matchups. <i>Pigouvian Heavy</i> runs the opposite intervention: leave bargaining power where it was before any trades happened, and instead tax agent-to-agent volume after the fact, recycling the revenue to humans with progressivity baked into the recycling. The EBI moves. The Gini doesn't. Distributional outcomes in this model are determined by who has bargaining power <em>before</em> the trade engine runs, not by transfers <em>after</em> it has run. The implication for policy is the unfashionable one: post-trade redistribution can move how much money is in whose hands, but it does not move the shape of the distribution that comes out of the trade engine itself. Gini compression has to happen upstream.
        </p>
        <p style="margin: 0 0 14px;">
          <b>(5) Even when welfare is high, the share of the economy any human is party to collapses with α.</b> The dashboard tracks a third diagnostic alongside EBI and welfare, called <i>human legibility</i>: the share of executed trades in which at least one party is a human. In direct-trade scenarios this sits between 0.1% and 3% — already small, because there are a hundred agents for every human just by counting. In fractal scenarios with realistic agent trade speed (one human-paced step for every hundred agent-paced trades), it falls another two orders of magnitude, to between one in a hundred thousand and one in ten thousand executed trades. Welfare and EBI tell you <em>whether</em> the economy is reaching humans. Legibility tells you whether humans can <em>see</em> the economy at all — whether there is any single trade that a specific person was party to and could in principle audit, contest, or remember happening. This number falls with α regardless of whether the cascade is productive or parasitic, and regardless of where welfare lands. <i>Productive Cathedral</i>, the scenario from conclusion 2 with high welfare and high EBI, has very low legibility — the high welfare reaches humans through statistical aggregates, not through trades that any specific person was on either side of. The implication for democratic accountability is direct: in the high-α scenarios, the economy is observable to itself — agents can audit agents, sub-markets can audit sub-markets — but it is no longer observable to the population on whose behalf it nominally runs. The legibility axis is what tells you whether the people supposedly being represented by the economic system can see the system that represents them.
        </p>
        <p style="margin: 0;">
          <b>(6) When agents are free to choose how complicated trades get, they settle at upper-mid α — not at the extremes.</b> There is one scenario in the set, <i>Endogenous Baroque</i>, that gives every prototype a learning algorithm — a contextual bandit — on its own preferred α. Each agent can learn over the run what level of fractal trade it wants to participate in, given what it observes around it. The population's average α drifts to wherever this learning takes it. The empirical answer is robustly the upper-mid range — α settles somewhere around 0.7. Not the cathedral (α near 1). Not the direct-trade corner (α near 0). This says two things. First, the cathedral regime — α near 1, fold cascade everywhere, EBI in the millions — does not arise from agent preferences alone. Sustaining it takes external scaffolding: low platform fees, no ceiling on how deep the cascade can go, weak alignment vetoes, no friction floor. Without those institutional conditions in place, the cathedral evaporates back toward the upper-mid attractor. Second, and equally important, the direct-trade corner doesn't arise from agent preferences either. Agents free to choose any α don't choose direct trade. The gravitational pull of the population's own learning is mid-fractal, which reinforces the first conclusion — that staying in the direct-trade corner is an active engineering task, not a passive default. The simulator finds that even before any institutional pressure is applied, agents that can learn settle at α ≈ 0.7 because that's where their own incentives land.
        </p>
      </div>
    </div>
  </div>
</section>

<section>
  <div class="wrap">
    <h2><span class="marker">§3</span> The scenarios</h2>
    <p class="sub">Click a card to load its detail pane below. Cards are ordered along α – <i>Coasean Paradise</i> on the far left, <i>Exo-Baroque Singularity</i> on the far right. Each card prints the scenario's terminal α, exo-baroque index, and per-capita welfare. The twenty-five scenarios fix different levers – alignment-layer rejection rate, agent autonomy, friction floor, capability variance, fold ceiling, the rate at which α responds to its own EBI, demand-side feedback, productive folding, and opt-in time-varying law schedules – so that the rest of the system can be read as a response to that lever.</p>
    <div class="scenario-strip" id="scn-strip"></div>
    <div class="cs-panel" id="cs-panel">
      <div class="cs-panel-head">
        <h3>Scale stability &amp; trajectory convergence at the 50-year horizon</h3>
        <span class="cs-meta">via <code>agentworld convergence</code> / <code>agentworld stability</code></span>
      </div>
      <p class="cs-panel-sub" style="border-left: 2px solid var(--accent); padding-left: 12px; color: var(--text);"><b>Reading the panel.</b> The numbers everywhere else on this dashboard are <b>50-year-horizon values</b> — one step is one quarter, so <code>n_steps=200</code> ≈ the brief's 2026→2076 frame. This <b>drift column</b> shows how much each scenario's terminal EBI moves if you double the horizon to <code>n_steps=400</code> (year 100): a continuous quantity, not a pass/fail. Low drift (&lt;1%) means the trajectory has effectively saturated within the brief's window — what you see is the answer. High drift means EBI is still climbing past year 50. Steady-state values would require multi-century extrapolation past the point where the speculative load-bearing parameters really make sense for a simulation of this size, so the dashboard quotes the 50-year value alongside that drift marker, not in place of it.</p>
      <p class="cs-panel-sub">One diagnostic per scenario: <b>(drift)</b> what is the percentage shift in terminal EBI between <code>n_steps=200</code> and <code>n_steps=400</code>? The earlier scale-stability flag (small-vs-medium-population EBI consistency) is currently small-only because the empirical SBM substrate exceeds the network-node ceiling at medium scale and would fall back to well-mixed sampling, contaminating the comparison. The drift column comes from a 4-seed stability sweep on the substrate at the small population. See <a href="https://github.com/mpoliks/agentworld/blob/main/docs/concepts/convergence.md">convergence.md</a> and <a href="https://github.com/mpoliks/agentworld/blob/main/docs/concepts/time_discretization.md">time_discretization.md</a> for method and the dt anchor.</p>
      <div id="cs-table-host"></div>
    </div>
  </div>
</section>

<section>
  <div class="wrap">
    <h2><span class="marker">§4</span> Scenario detail · <span id="active-name" style="color:var(--accent);"></span></h2>
    <p class="sub" id="active-desc"></p>
    <p class="sub" id="ensemble-status" style="color:var(--text-3); font-size:13px;"></p>
    <div class="detail-pane">
      <div class="detail-meta" id="active-meta"></div>
      <div class="chart-box">
        <div class="chart-title">transaction space — live animation</div>
        <div class="chart-caption">
          A 500-prototype sample of the economy. <b><span style="color:#5b8ec4;">Blue dots</span></b> are humans (50 of 500 — visually inflated from the actual ~1% mass share so they're visible). <b><span style="color:#d49e5c;">Amber dots</span></b> are agents (450 of 500). Each <b>flash</b> is a sample of executed trades: <span style="color:#d49e5c;"><b>amber</b></span> = agent-to-agent, <span style="color:#5b8ec4;"><b>teal</b></span> = human-to-agent, <span style="color:#5fa572;"><b>green</b></span> = human-to-human. Flash density tracks <code>n_transactions_real</code>; the type-mix tracks <code>a2a_share / h2a_share / h2h_share</code>. <b>Fractal fans</b> branching off an a2a flash represent the fold cascade — each curved sub-branch is a sub-trade in a derivative market; sub-branches fork further to represent derivatives-of-derivatives. Fan density and depth are driven by the <code>n_sub_markets_added / n_transactions_real</code> ratio at each step, so smooth scenarios show plain flashes and baroque scenarios fill the canvas with dense recursive trees. <b>Welfare particles</b> emerge from each flash: with probability ≈ 1/EBI they fly to a human dot and land as a green pulse (welfare delivered); otherwise they dissipate in the agent layer. Counters update step by step.
        </div>
        <div id="anim-container" style="position:relative; background:#0f1012; border-radius:6px; overflow:hidden;">
          <canvas id="anim-canvas" style="display:block; width:100%; height:100%;"></canvas>
            <div id="anim-stats" style="position:absolute; top:12px; right:12px; background:rgba(15,16,18,0.78); border:1px solid rgba(255,255,255,0.10); border-radius:5px; padding:10px 14px; font-family:var(--mono); font-size:11px; color:var(--text-2); pointer-events:none; min-width:180px;">
              <div style="font-size:10px; color:var(--text-3); letter-spacing:0.08em; text-transform:uppercase; margin-bottom:6px;">live</div>
              <div>step <span id="a-step" style="color:var(--accent);">0</span> / <span id="a-nsteps">200</span></div>
              <div>real welfare (cum) <span id="a-real" style="color:#5fa572;">0</span></div>
              <div>nominal GDP (cum) <span id="a-nom" style="color:#d49e5c;">0</span></div>
              <div>EBI <span id="a-ebi" style="color:#fff;">1.00</span></div>
              <div>sub-markets/step <span id="a-fold" style="color:#fff;">0</span></div>
              <div>a2a share <span id="a-a2a" style="color:#fff;">0%</span></div>
            </div>
            <div id="anim-controls" style="position:absolute; bottom:12px; left:12px; right:12px; display:flex; align-items:center; gap:12px; background:rgba(15,16,18,0.78); border:1px solid rgba(255,255,255,0.10); border-radius:5px; padding:8px 12px;">
              <button id="anim-play" style="background:var(--accent); color:#0f1012; border:0; border-radius:3px; padding:4px 10px; font-family:var(--mono); font-size:12px; cursor:pointer;">▶ play</button>
              <button id="anim-restart" style="background:transparent; color:var(--text-2); border:1px solid var(--border); border-radius:3px; padding:4px 10px; font-family:var(--mono); font-size:11px; cursor:pointer;">↺ restart</button>
              <input id="anim-scrub" type="range" min="0" max="59" value="0" style="flex:1; accent-color:var(--accent);">
          <select id="anim-speed" style="background:transparent; color:var(--text-2); border:1px solid var(--border); border-radius:3px; padding:3px 6px; font-family:var(--mono); font-size:11px;">
            <option value="200">0.35×</option>
            <option value="120">0.6×</option>
            <option value="70" selected>1×</option>
            <option value="40">1.75×</option>
            <option value="20">3.5×</option>
          </select>
        </div>
      </div>
    </div>
    <!-- /detail-pane -->
    </div>

    <div class="charts-grid">
      <div class="chart-box">
        <div class="chart-title">α (smooth ↔ striated) over time</div>
        <div class="chart-caption">The control schedule. A flat line means α was held constant; a ramp or decay means α was scheduled to move; a jagged trace means α responded to the run itself – <i>Recursive Simulation</i> is the easiest example, where α climbs whenever EBI climbs.</div>
        <div id="d-alpha" style="height:240px;"></div>
      </div>
      <div class="chart-box">
        <div class="chart-title">cumulative real welfare vs nominal GDP</div>
        <div class="chart-caption">Two cumulative curves on a log y-axis. They start together. Watch the vertical gap between them (that <i>is</i> the exo-baroque index) – the wider it opens, the more measured economic activity has folded into accounting that no human ever consumes.</div>
        <div id="d-realnom" style="height:240px;"></div>
      </div>
      <div class="chart-box">
        <div class="chart-title">exo-baroque index over time (log scale)</div>
        <div class="chart-caption">The same gap, expressed as a single ratio. The dashed reference at EBI = 1 is the parity line. Anything sustained above it is GDP that the human side of the economy did not receive.</div>
        <div id="d-ebi" style="height:240px;"></div>
      </div>
      <div class="chart-box">
        <div class="chart-title">sub-markets created per step (log)</div>
        <div class="chart-caption">How many derivative / sub-trade markets were spawned by the fold cascade each step, in real units across the whole economy. Log y-axis because values span ~7 orders of magnitude across scenarios. A flat zero means the scenario refuses to fold; rising values mean fractal multiplication is intensifying. This replaces the older "max fold depth" panel — depth saturated at the cap in most scenarios and carried almost no information beyond "is folding on or off"; the sub-market count actually varies meaningfully both within a run and across scenarios.</div>
        <div id="d-fold" style="height:240px;"></div>
      </div>
      <div class="chart-box">
        <div class="chart-title">per-capita welfare · ×10³ stylized units</div>
        <div class="chart-caption">Real welfare divided across 8 × 10⁹ humans, step by step. The actual material outcome on the human side. These are not dollars, these are stylized units for comparison! Coasean Paradise tops out near 280; Slop Market near 25. Productive Cathedral (the high-α scenario with productive folding turned on) is the welfare leader at ≈ 620. Use this trace to compare scenarios on welfare alone, with α and EBI deliberately set aside.</div>
        <div id="d-pc" style="height:240px;"></div>
      </div>
      <div class="chart-box">
        <div class="chart-title">why trades got rejected — by filter</div>
        <div class="chart-caption">Of the trades that did not complete, which filter killed them. <span style="color:#c25a5a;">law</span> = the trade was illegal. <span style="color:#5b8ec4;">market</span> = the platform blocked it or its fees made it uneconomic. <span style="color:#5fa572;">alignment</span> = one of the parties objected on values grounds. <span style="color:#b89a55;">cost</span> = the trade's underlying friction was higher than its surplus, so it wasn't worth doing.</div>
        <div id="d-rej" style="height:240px;"></div>
      </div>
      <div class="chart-box">
        <div class="chart-title">authentic vs un-modulated real welfare (cumulative, log)</div>
        <div class="chart-caption"><b>Authentic</b> real welfare is the share that reaches a human consumer (or a human-controlled agent acting on a principal's behalf). The <b>un-modulated</b> trace is the legacy aggregate. The two coincide when <code>DemandConfig.enabled = False</code> (the default) — one curve is drawn on top of the other. When demand-side feedback is on, the gap between the curves is the surplus that A2A activity printed but no person consumed.</div>
        <div id="d-authentic" style="height:240px;"></div>
      </div>
      <div class="chart-box">
        <div class="chart-title">productive welfare yield over time</div>
        <div class="chart-caption">Per-step productive yield of the fold cascade. <b>Welfare yield</b> is bounded real welfare created per fold-nominal dollar (risk transfer, hedging, price discovery). <b>Nominal residual</b> is the remaining fold nominal. Yield is zero when <code>base_variance_absorption = 0.0</code> (the back-compat default).</div>
        <div id="d-pfs" style="height:240px;"></div>
      </div>
    </div>
  </div>
</section>

<section>
  <div class="wrap">
    <h2><span class="marker">§5</span> Where did the welfare go? · <span id="welfare-scn-label" style="color:var(--accent);">—</span></h2>
    <p class="sub">Same scenario as §4 above. Every unit of measured economic activity (nominal GDP) ends up in one of five places: directly consumed by humans, captured by agents (and never reaching humans), lost to the law system as overhead or capture, recycled via Pigouvian transfer (when that lever is on), or sitting as <i>parasitic accounting</i> — nominal volume that the fold cascade printed without producing any consumable welfare. The Sankey below traces those flows for whichever scenario you picked in §3, so you can see <b>why</b> the scenario landed where it did, not just that it did.</p>
    <div class="phase-pane">
      <div class="chart-box phase-map-box">
        <div class="chart-title">nominal GDP flow</div>
        <div id="welfare-sankey" style="height:520px;"></div>
      </div>
      <div class="phase-side">
        <div class="panel phase-readout">
          <div class="phase-section-label">breakdown</div>
          <div class="phase-readout-row"><span class="phase-readout-key">total nominal GDP</span><span class="phase-readout-val" id="w-r-total">—</span></div>
          <div class="phase-readout-row"><span class="phase-readout-key" style="color:#5fa572;">→ to humans</span><span class="phase-readout-val" id="w-r-humans">—</span></div>
          <div class="phase-readout-row"><span class="phase-readout-key" style="color:#d49e5c;">→ to agents</span><span class="phase-readout-val" id="w-r-agents">—</span></div>
          <div class="phase-readout-row"><span class="phase-readout-key" style="color:#c25a5a;">→ lost to law</span><span class="phase-readout-val" id="w-r-law">—</span></div>
          <div class="phase-readout-row"><span class="phase-readout-key" style="color:#5b8ec4;">→ recycled (Pigouvian)</span><span class="phase-readout-val" id="w-r-pig">—</span></div>
          <div class="phase-readout-row"><span class="phase-readout-key" style="color:#7a7d82;">→ parasitic accounting</span><span class="phase-readout-val" id="w-r-paras">—</span></div>
          <div class="phase-readout-foot" id="w-r-foot"></div>
        </div>
        <div class="panel phase-legend">
          <div class="phase-section-label">how to read it</div>
          <div style="font-family:var(--serif); font-size:12.5px; line-height:1.55; color:var(--text-2);">
            Each ribbon's <b>thickness</b> is the absolute share of nominal GDP flowing to that destination. A thick green ribbon means most measured activity reached a human; a thick gray ribbon means most was just folded accounting that no one consumed. <b>Pigouvian recycling is bounded by the slice of nominal that actually became surplus</b> — in baroque scenarios the parasitic ribbon dominates and the tax base is small even at high tax rates.
          </div>
        </div>
      </div>
    </div>
    <div class="callout" id="welfare-note"></div>
  </div>
</section>

<section>
  <div class="wrap">
    <h2><span class="marker">§6</span> Compare scenarios</h2>
    <p class="sub">Pick any subset of scenarios and overlay them on a shared time axis. Useful for questions like:<i>what do the Slop Market and the Baroque Cathedral share, and where do they diverge?</i> Both end at high α; only one converts that α into welfare. Stacking the EBI and per-capita-welfare curves makes the divergence step visible.</p>
    <div class="compare-help">
      Click a chip to toggle it in or out of the overlay. <kbd>⌥ alt-click</kbd> a chip to <b>solo</b> it – keep just that one and clear the rest. The buttons at the right of the strip act on the whole set: <b>All</b> turns every scenario on, <b>Clear</b> removes everything, <b>Reset</b> restores the four corner-defining scenarios.
    </div>
    <div class="compare-bar" id="compare-bar"></div>
    <div class="charts-grid">
      <div class="chart-box">
        <div class="chart-title">exo-baroque index (log)</div>
        <div class="chart-caption">How fast each scenario's accounting separates from welfare over time. Curves that hug 1 are smooth regimes; curves that climb are folding regimes; curves that climb and then stall have hit a fold ceiling.</div>
        <div id="c-ebi" style="height:280px;"></div>
      </div>
      <div class="chart-box">
        <div class="chart-title">per-capita welfare · ×10³ stylized units</div>
        <div class="chart-caption">What households actually got at each step. Shape distinguishes cumulative growth from stagnation; height ranks the selected scenarios on welfare alone, regardless of how much GDP each printed. Y-axis is scaled by 10³ for legibility – model state is identical to the §1 definition.</div>
        <div id="c-pc" style="height:280px;"></div>
      </div>
      <div class="chart-box">
        <div class="chart-title">cumulative nominal GDP (symlog)</div>
        <div class="chart-caption">Total measured economic activity. The symlog y-axis carries both <i>Coasean Paradise</i> (≈ unity) and <i>Exo-Baroque Singularity</i> (≈ 10⁶ +) on the same chart without one flattening the other.</div>
        <div id="c-nom" style="height:280px;"></div>
      </div>
      <div class="chart-box">
        <div class="chart-title">human legibility index</div>
        <div class="chart-caption">Bounded 0–1: the share of nominal GDP a human could in principle audit. 1.0 means the market is fully readable from the outside; values near 0 mean the market is legible only to itself.</div>
        <div id="c-leg" style="height:280px;"></div>
      </div>
    </div>
  </div>
</section>

<section>
  <div class="wrap">
    <h2><span class="marker">§7</span> Global sensitivity · which knobs actually move what</h2>
    <p class="sub">Saltelli/Sobol decomposition at N=2048 base samples (34,816 simulations, 15-parameter problem). <b>S1</b> is the share of output variance the parameter explains on its own; <b>ST</b> includes interactions with the other parameters. A bar where <b>ST &gt;&gt; S1</b> means the parameter mostly matters through interactions with other parameters. Parameters where both are near zero are cosmetic within the bounds we swept. Bounds for each parameter are listed alongside the chart — the indices are conditional on those bounds, so they tell you the variance structure inside the explored space, not outside it.</p>
    <p class="sub">Two metrics are shown in transformed form so the Saltelli estimator stays inside its assumptions: <b>log(EBI)</b> instead of raw EBI (raw EBI's right tail is unbounded — real → 0 in baroque regimes pushes EBI → ∞, which breaks variance decomposition), and <b>gini of |Δwealth|</b> instead of terminal gini (terminal gini is ~100% determined by initial population synthesis; corr(gini₀, gini_T) = 1.0000 across the parameter space, so Sobol on it would attribute population-seed noise to topology parameters). Both transformed metrics preserve rank ordering of the originals and produce well-bounded indices (max ST ≤ 0.85, all sum(S1) ≤ 1.0). Raw EBI and gini_wealth time series are still on the dashboard above.</p>
    <div class="charts-grid" style="grid-template-columns: 1fr 1fr;">
      <div class="chart-box">
        <div class="chart-title">α-engine · Sobol indices for log(EBI)</div>
        <div class="chart-caption">First-order S1 (filled) and total-order ST (outlined) for the log-transformed exo-baroque index. Tall S1 + short ST gap = the parameter acts independently. Tall ST with low S1 = the parameter only matters through interactions with others. Log transform tames the unbounded right tail of raw EBI so the variance decomposition stays valid.</div>
        <div id="sobol-alpha-ebi" style="height:340px;"></div>
      </div>
      <div class="chart-box">
        <div class="chart-title">α-engine · Sobol indices for terminal welfare</div>
        <div class="chart-caption">Same decomposition, target = real per-capita welfare. Compare to the EBI panel: knobs that dominate EBI may not dominate welfare, and vice versa.</div>
        <div id="sobol-alpha-welfare" style="height:340px;"></div>
      </div>
      <div class="chart-box">
        <div class="chart-title">α-engine · Sobol indices for wealth-change inequality</div>
        <div class="chart-caption">Sensitivity for gini of |wealth_t − wealth_0| — captures topology-driven wealth churn rather than the initial-population baseline (terminal gini was ~100% determined by population synthesis, so was unusable for Sobol). Top driver is typically agent capability: more capable agents extract more surplus and shift the distribution further.</div>
        <div id="sobol-alpha-gini" style="height:340px;"></div>
      </div>
      <div class="chart-box">
        <div class="chart-title">α-engine · Sobol indices for productive welfare yield</div>
        <div class="chart-caption">Per-step share of fold-nominal volume that becomes real welfare. Distinguishes productive folding (real intermediation) from parasitic folding (markup-only). Top driver is the productive-vs-parasitic split parameter (base_variance_absorption); alpha and folding_propensity follow.</div>
        <div id="sobol-alpha-prod" style="height:340px;"></div>
      </div>
      <div class="chart-box">
        <div class="chart-title">exo-engine · Sobol indices for circulation index</div>
        <div class="chart-caption">Same decomposition for the exo-engine target (exo_circulation_index). This chart says which exo-side knobs impact exo-side diagnostics.</div>
        <div id="sobol-exo-circ" style="height:340px;"></div>
      </div>
      <div class="chart-box">
        <div class="chart-title">exo-engine · Sobol indices for imperial extraction share</div>
        <div class="chart-caption">Sensitivity of the imperial extraction-share metric. Useful for the question "is the extraction rate parameter the only thing that controls extraction share?" (Spoiler: it usually is, and that is itself maybe an indictment of the engine.)</div>
        <div id="sobol-exo-extraction" style="height:340px;"></div>
      </div>
    </div>
    <div class="callout" id="sobol-note">No Sobol indices found. Run <code>agentworld sobol</code> and <code>agentworld exo sobol</code> to populate.</div>
  </div>
</section>


<footer>
  <div class="wrap">
    <p>Agentworld is a tool for thinking about a near-term variable space. The immediate conceptual neighbors are Sébastien Krier's <i>Coasean Bargaining at Scale</i> (Sept 2025) and Tomašev et al's <i>Virtual Agent Economy</i> (Sept 2025); the alternative ontology supplied by the exo-engine is Poliks &amp; Trillo, <i>Exocapitalism</i> (2025).</p>
  </div>
</footer>

<script>
const PAYLOAD = __PAYLOAD__;
const SCN = PAYLOAD.scenarios;
const ORDER = PAYLOAD.scenario_order;
const SENS = PAYLOAD.sensitivity;
const ENSEMBLES = PAYLOAD.ensembles || {};
const SOBOL_ALPHA = PAYLOAD.sobol_alpha || null;
const SOBOL_EXO = PAYLOAD.sobol_exo || null;
const PROVENANCE = PAYLOAD.provenance || [];

// ---------- welfare display scaling ----------
// Real per-capita welfare lives in ~2.5e-2 to ~6.2e-1 (stylized units divided
// across 8e9 humans). At that magnitude .toFixed(4) collapses the whole range
// into the unscaled per-step values (~0.025 to ~0.62) and cross-scenario ranking is hard to read. Scale
// by 10^6 for display only – model state is unchanged. Coasean Paradise reads
// as ~279, Slop Market as ~25. Apply consistently everywhere welfare appears.
const WELFARE_SCALE = 1e3;
const WELFARE_LABEL_LONG  = 'welfare per capita · ×10³ stylized units';
const WELFARE_LABEL_SHORT = 'w/cap (×10³)';
const fmtW = (v) => (v * WELFARE_SCALE).toFixed(1);
// Compact welfare formatter for the scenario cards – the full ×10³ figure
// like "173891.4" wraps at the card's 220px min-width, so card readouts use
// k/M suffixes instead. The detail panes and chart axes still use fmtW.
const fmtWcompact = (v) => {
  const n = v * WELFARE_SCALE;
  if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(2) + 'M';
  if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + 'k';
  return n.toFixed(1);
};

// ---------- viewport helper ----------
// Single mobile breakpoint at 640px. Used by the atlas to swap colorbar
// orientation and tighten margins; not a global breakpoint, the rest of the
// dashboard handles narrow viewports through CSS grid alone.
const MOBILE_BREAKPOINT = 640;
const isMobile = () => window.matchMedia('(max-width: ' + MOBILE_BREAKPOINT + 'px)').matches;

// ---------- atlas chart ----------
// All scenario labels live in hover only – there are too many in the smooth-mid
// cluster (α ≈ 0.3–0.6, EBI ≈ 1–10) for inline labels to land cleanly, and the
// leader lines also distort plotly's autorange on the y-axis. The dashed
// EBI = 1 line is the only in-plot reference; everything else is in the chart
// caption HTML directly above the atlas.
//
// Mobile layout (≤640px): the colorbar moves to a horizontal strip under the
// plot so it doesn't eat the plotting width; margins shrink; markers grow for
// thumb-tap targets. Touch already triggers Plotly hover on tap, so tooltips
// still work.
function renderAtlas() {
  const mobile = isMobile();
  const xs = [], ys = [], texts = [], colors = [];
  ORDER.forEach(name => {
    const s = SCN[name];
    const h = s.history;
    xs.push(s.final_alpha);
    ys.push(h.exo_baroque_index[h.exo_baroque_index.length - 1]);
    texts.push(s.label);
    colors.push(h.real_per_capita_welfare[h.real_per_capita_welfare.length - 1] * WELFARE_SCALE);
  });

  const colorbar = mobile
    ? {
        orientation: 'h',
        title: { text: 'welfare per capita · ×10³', font: { color: '#9ea2a8', size: 10 } },
        tickfont: { color: '#6a6d72', size: 9 },
        thickness: 10, len: 0.9,
        x: 0.5, xanchor: 'center',
        y: -0.28, yanchor: 'top',
      }
    : {
        title: { text: WELFARE_LABEL_LONG, font: { color: '#9ea2a8', size: 11 } },
        tickfont: { color: '#6a6d72', size: 10 },
      };

  const trace = {
    x: xs, y: ys,
    text: texts,
    mode: 'markers',
    type: 'scatter',
    marker: {
      size: mobile ? 22 : 18,
      color: colors,
      colorscale: [[0, '#4a3a82'], [0.5, '#b89a55'], [1, '#5fa572']],
      colorbar,
      line: { color: '#0c0d10', width: 1 },
    },
    hovertemplate:
      '<b>%{text}</b>' +
      '<br>α = %{x:.3f}' +
      '<br>EBI = %{y:.3g}' +
      '<br>' + WELFARE_LABEL_SHORT + ' = %{marker.color:.1f}' +
      '<extra></extra>',
  };

  const layout = {
    paper_bgcolor: '#14161a', plot_bgcolor: '#14161a',
    font: { color: '#9ea2a8', family: 'Inter, sans-serif', size: mobile ? 10 : 12 },
    xaxis: {
      title: { text: 'α (smooth → striated)', font: { size: mobile ? 11 : 13 } },
      tickfont: { size: mobile ? 9 : 11 },
      gridcolor: '#2a2d33', zerolinecolor: '#2a2d33',
      range: [-0.02, 1.04], autorange: false,
    },
    yaxis: {
      title: { text: 'exo-baroque index (log)', font: { size: mobile ? 11 : 13 } },
      tickfont: { size: mobile ? 9 : 11 },
      type: 'log', gridcolor: '#2a2d33', zerolinecolor: '#2a2d33',
      // Explicit log range. Without this, Plotly's autorange interacts badly
      // with the mobile horizontal colorbar at y=-0.28 over a 7-decade EBI
      // span and throws "Something went wrong with axis scaling".
      range: [-0.1, 7.7], autorange: false,
    },
    margin: mobile
      ? { l: 46, r: 14, t: 14, b: 110 }
      : { l: 70, r: 40, t: 30, b: 60 },
    shapes: [
      { type: 'line', x0: -0.02, x1: 1.04, y0: 1, y1: 1, line: { color: '#666', dash: 'dash', width: 1 } },
    ],
    annotations: [],
  };
  Plotly.newPlot('atlas', [trace], layout, { displayModeBar: false, responsive: true });
}

// Re-render the atlas only when the viewport actually crosses the mobile
// breakpoint. Plotly's responsive:true handles intra-breakpoint resizes by
// itself; this listener exists purely to swap the colorbar/margin/font preset.
let _atlasIsMobile = isMobile();
let _atlasResizeTimer = null;
window.addEventListener('resize', () => {
  clearTimeout(_atlasResizeTimer);
  _atlasResizeTimer = setTimeout(() => {
    const nowMobile = isMobile();
    if (nowMobile !== _atlasIsMobile) {
      _atlasIsMobile = nowMobile;
      renderAtlas();
    }
  }, 180);
});

// ---------- convergence/stability badges (per-scenario) ----------
function _csBadgeHtml(name) {
  const cs = (PAYLOAD.convergence_stability || {})[name];
  if (!cs) return '';
  const parts = [];
  if (cs.scale_status) {
    const cls = cs.scale_status;
    const t = cs.scale_status === 'stable' ? 'S✓' : 'S✗';
    const tip = `Scale ${cs.scale_status}: small EBI ${cs.scale_small_ebi?.toFixed(2)} vs medium [${cs.scale_medium_ebi_lo?.toFixed(2)}, ${cs.scale_medium_ebi_hi?.toFixed(2)}]`;
    parts.push(`<span class="cs-badge ${cls}" title="${tip}">${t}</span>`);
  }
  if (cs.traj_drift_pct != null) {
    const drift = cs.traj_drift_pct;
    const sign = drift >= 0 ? '+' : '';
    const absD = Math.abs(drift);
    // Tier purely cosmetic — actual quantity is the magnitude in the badge text.
    const cls = absD < 1 ? 'steady' : (absD < 5 ? 'drifting' : 'transient');
    const tip = `EBI drift over n_steps=${cs.traj_n_steps_prev}→${cs.traj_n_steps_last}: ${cs.traj_ebi_prev?.toFixed(2)} → ${cs.traj_ebi_last?.toFixed(2)} (${sign}${drift.toFixed(2)}%)`;
    parts.push(`<span class="cs-badge ${cls}" title="${tip}">drift ${sign}${drift.toFixed(1)}%</span>`);
  }
  return parts.length ? `<div class="cs-badges">${parts.join('')}</div>` : '';
}

function renderConvergenceStability() {
  const host = document.getElementById('cs-table-host');
  if (!host) return;
  const cs = PAYLOAD.convergence_stability || {};
  const rows = ORDER.map(name => {
    const e = cs[name] || {};
    return {name, label: SCN[name].label, ...e};
  }).filter(r => r.scale_status || r.traj_drift_pct != null);
  if (rows.length === 0) {
    host.innerHTML = '<div class="cs-empty">No convergence/stability sweeps committed yet. Run <code>agentworld convergence</code> and <code>agentworld stability</code> to populate this panel.</div>';
    return;
  }
  // Under the empirical substrate switch, scale-stability comparison is
  // small-only (SBM exceeds MAX_NETWORK_NODES at medium population), so we
  // drop the scale columns and surface drift alone. Scale data is still
  // loaded via PAYLOAD if/when present (e.g., for diagnostic review), but
  // the visible table is drift-focused.
  const haveScaleData = rows.some(r => r.scale_status);
  const nSettled = rows.filter(r => r.traj_drift_pct != null && Math.abs(r.traj_drift_pct) < 1).length;
  const nDrifting = rows.filter(r => r.traj_drift_pct != null && Math.abs(r.traj_drift_pct) >= 1 && Math.abs(r.traj_drift_pct) < 5).length;
  const nTransient = rows.filter(r => r.traj_drift_pct != null && Math.abs(r.traj_drift_pct) >= 5).length;
  const summary = `<div class="cs-panel-sub" style="color:var(--text-3); font-family:var(--mono); font-size:11px; margin-bottom:6px;">scope: ${rows.length} scenarios · 50→100y drift: <span style="color:var(--green);">${nSettled} &lt;1%</span>, <span style="color:#b89a55;">${nDrifting} 1–5%</span>, <span style="color:#c25a5a;">${nTransient} ≥5%</span>${haveScaleData ? '' : ' · scale comparison unavailable (SBM at medium scale exceeds memory ceiling)'}</div>`;
  const fmtN = (x) => (x == null ? '—' : (Math.abs(x) < 100 ? x.toFixed(2) : x.toExponential(1)));
  const fmtPct = (x) => {
    if (x == null) return '—';
    const sign = x >= 0 ? '+' : '';
    return `${sign}${x.toFixed(2)}%`;
  };
  const driftColor = (d) => {
    if (d == null) return 'var(--text-3)';
    const a = Math.abs(d);
    if (a < 1) return 'var(--green)';
    if (a < 5) return '#b89a55';
    return '#c25a5a';
  };
  const tr = rows.map(r => `
    <tr>
      <td class="scen">${r.label}</td>
      <td class="num">${fmtN(r.traj_ebi_prev)}</td>
      <td class="num">${fmtN(r.traj_ebi_last)}</td>
      <td class="num" style="color:${driftColor(r.traj_drift_pct)}; font-weight:500;">${fmtPct(r.traj_drift_pct)}</td>
    </tr>`).join('');
  host.innerHTML = summary + `
    <table class="cs-table">
      <thead>
        <tr>
          <th>scenario</th>
          <th class="num">EBI(200 steps · year 50)</th>
          <th class="num">EBI(400 steps · year 100)</th>
          <th class="num">drift 50→100y</th>
        </tr>
      </thead>
      <tbody>${tr}</tbody>
    </table>`;
}

// ---------- scenario strip ----------
function renderStrip(active) {
  const el = document.getElementById('scn-strip');
  el.innerHTML = '';
  ORDER.forEach(name => {
    const s = SCN[name];
    const h = s.history;
    const ebi = h.exo_baroque_index[h.exo_baroque_index.length - 1];
    const pc = h.real_per_capita_welfare[h.real_per_capita_welfare.length - 1];
    const card = document.createElement('div');
    card.className = 'scn-card' + (name === active ? ' active' : '');
    card.innerHTML = `
      <div class="name">${s.label}</div>
      <div class="alpha"><span>α=<b>${s.final_alpha.toFixed(2)}</b></span><span>EBI=<b>${ebi < 100 ? ebi.toFixed(2) : ebi.toExponential(1)}</b></span><span>w=<b>${fmtWcompact(pc)}</b></span></div>
      ${_csBadgeHtml(name)}
      <div class="desc">${s.description}</div>`;
    card.addEventListener('click', () => loadDetail(name));
    el.appendChild(card);
  });
}

// ---------- ensemble band helpers ----------
// When `outputs/ensembles/{name}.bands.json` is present, the per-scenario
// charts overlay the ensemble's median + 5/95 percentile band. The single
// run still plots on top so the original look is preserved; the band is a
// translucent envelope behind it. The §1 primer's "Bands on the charts"
// panel explains what these bands mean (and don't).
function _bandTraces(name, key, color, scale) {
  const bands = ENSEMBLES[name]?.bands?.[key];
  if (!bands) return [];
  const n = bands.median.length;
  const x = Array.from({length: n}, (_, i) => i);
  const apply = (arr) => scale ? arr.map(v => v * scale) : arr;
  // Lower bound is plotted invisibly; upper bound fills down to it.
  return [
    { x, y: apply(bands.p05), mode: 'lines', line: { width: 0 }, hoverinfo: 'skip', showlegend: false },
    { x, y: apply(bands.p95), mode: 'lines', line: { width: 0 }, fill: 'tonexty',
      fillcolor: color, hoverinfo: 'skip', showlegend: false, name: 'p05/p95 band' },
    { x, y: apply(bands.median), mode: 'lines', line: { color: color.replace('0.2', '0.7'), width: 1.4, dash: 'dot' },
      name: 'ensemble median', hoverinfo: 'skip', showlegend: false },
  ];
}

// ---------- transaction-space animation ----------
// Visualizes the executed-trade stream behind the per-step aggregates.
// 500 dots represent prototypes (50 humans + 450 agents — the visual
// human share is inflated from the ~1% mass share so humans stay visible
// at panel resolution; the legend documents this). Per-step flashes are
// drawn proportional to n_transactions_real, with type mix following
// a2a_share / h2a_share / h2h_share. Concentric rings around an a2a
// flash visualise fold_max_depth at that step.
const ANIM = {
  scenarioName: null,
  step: 0,
  playing: false,
  speed: 70,           // ms per simulation step — fast enough to read change
  intervalId: null,
  canvas: null,
  ctx: null,
  dpr: 1,
  width: 0,
  height: 0,
  dotsH: [],
  dotsA: [],
  flashes: [],
  history: null,
  cumReal: 0,
  cumNom: 0,
  sectorEdges: null,
};

function _animMulberry32(a) {
  return function() {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function _animSeed(s) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}
function _animFmtBig(v) {
  if (!isFinite(v) || v === 0) return '0';
  const abs = Math.abs(v);
  if (abs >= 1e12) return (v / 1e12).toFixed(2) + 'T';
  if (abs >= 1e9)  return (v / 1e9).toFixed(2) + 'B';
  if (abs >= 1e6)  return (v / 1e6).toFixed(2) + 'M';
  if (abs >= 1e3)  return (v / 1e3).toFixed(2) + 'K';
  return v.toFixed(2);
}

function _animResize() {
  const c = ANIM.canvas;
  if (!c) return;
  const rect = c.getBoundingClientRect();
  ANIM.dpr = window.devicePixelRatio || 1;
  ANIM.width = rect.width;
  ANIM.height = rect.height;
  c.width = Math.floor(rect.width * ANIM.dpr);
  c.height = Math.floor(rect.height * ANIM.dpr);
  ANIM.ctx.setTransform(ANIM.dpr, 0, 0, ANIM.dpr, 0, 0);
}

function _animLayoutDots() {
  const rng = _animMulberry32(_animSeed(ANIM.scenarioName || 'x'));
  const padX = 24, padY = 28;
  const W = Math.max(ANIM.width - padX * 2, 100);
  // Reserve ~36px at bottom for the welfare bar + label.
  const H = Math.max(ANIM.height - padY * 2 - 36, 100);

  // 10 sectors. Per-scenario weights are drawn from a Dirichlet-like
  // distribution seeded by the scenario name, so different scenarios
  // produce visibly different sector-band silhouettes (some scenarios
  // are dominated by one sector, others are well-distributed). This is
  // a *visualisation* approximation — the actual engine sectors come from
  // a Dirichlet draw over a fixed seed; here we just want the static
  // layout to vary across scenarios.
  const sectorWeights = [];
  let sw_sum = 0;
  for (let i = 0; i < 10; i++) {
    // Exponential, mildly heavy-tailed so concentrations show up.
    const w = -Math.log(Math.max(rng(), 1e-4));
    sectorWeights.push(w);
    sw_sum += w;
  }
  for (let i = 0; i < 10; i++) sectorWeights[i] /= sw_sum;
  const sectorEdges = [0];
  for (let i = 0; i < 10; i++) sectorEdges.push(sectorEdges[i] + sectorWeights[i]);
  ANIM.sectorEdges = sectorEdges;

  function placeDot() {
    // Pick a sector weighted by mass; pick x-position inside the sector
    // band; pick y-position freely (no type/capability stratification).
    const u = rng();
    let sIdx = 9;
    for (let i = 0; i < 10; i++) {
      if (u >= sectorEdges[i] && u < sectorEdges[i + 1]) { sIdx = i; break; }
    }
    const xLo = sectorEdges[sIdx];
    const xHi = sectorEdges[sIdx + 1];
    const xFrac = xLo + (xHi - xLo) * rng();
    const yFrac = rng();  // free vertical scatter — humans and agents mixed
    const x = padX + xFrac * W;
    const y = padY + yFrac * H;
    return { x, y, bx: x, by: y, vx: 0, vy: 0, sector: sIdx, activity: 0 };
  }

  ANIM.dotsH = [];
  ANIM.dotsA = [];
  for (let i = 0; i < 50; i++) {
    ANIM.dotsH.push({ ...placeDot(), type: 'h', baseR: 3.5, r: 3.5, winner: false });
  }
  for (let i = 0; i < 450; i++) {
    ANIM.dotsA.push({ ...placeDot(), type: 'a', baseR: 1.8, r: 1.8, winner: false });
  }

  // Designate winners and assign each to one of several "wealth attractor"
  // points scattered around the canvas. As Gini × time rises, winners
  // migrate toward their assigned attractor (not a single corner), so the
  // pattern reads as multiple emerging concentration zones rather than a
  // single pile-up.
  const h = ANIM.history;
  if (h) {
    const giniEnd = h.gini_wealth[h.gini_wealth.length - 1] || 0.4;
    const nWinners = Math.round(8 + 60 * Math.max(0, giniEnd - 0.3));
    // Place 4-6 attractor points using the scenario rng so positions vary
    // across scenarios.
    const nAttractors = 4 + Math.floor(rng() * 3);
    const attractors = [];
    for (let i = 0; i < nAttractors; i++) {
      attractors.push({
        x: padX + (0.10 + 0.80 * rng()) * W,
        y: padY + (0.10 + 0.80 * rng()) * H,
      });
    }
    // Pick winners: random subset of agents, each assigned to a random attractor.
    const idxs = new Set();
    while (idxs.size < Math.min(nWinners, ANIM.dotsA.length)) {
      idxs.add(Math.floor(rng() * ANIM.dotsA.length));
    }
    for (const idx of idxs) {
      const d = ANIM.dotsA[idx];
      d.winner = true;
      const a = attractors[Math.floor(rng() * attractors.length)];
      d.targetX = a.x;
      d.targetY = a.y;
    }
  }
}

// Welfare-particle system. Every flash spawns a particle from the flash
// midpoint. With probability 1/EBI (the share of measured activity that
// actually reaches a human at last-mile), the particle homes in on the
// nearest human dot and lands as a green pulse — visible welfare delivery.
// With probability 1 - 1/EBI it dissipates in the agent layer. Coasean
// scenarios fountain particles into human dots; baroque scenarios show
// almost no particles reaching humans even though flashes are dense.
const _PARTICLES = [];

function _spawnParticleFromFlash(midX, midY, ebi) {
  const successProb = 1 / Math.max(ebi || 1, 1);
  const success = Math.random() < successProb;
  let tx, ty;
  if (success && ANIM.dotsH.length) {
    // Pick the closest few humans, then random among them — keeps particles
    // from homing on a single human dot every time.
    let candidates = [];
    let bestD2 = Infinity;
    for (const h of ANIM.dotsH) {
      const dx = h.x - midX, dy = h.y - midY;
      const d2 = dx * dx + dy * dy;
      candidates.push([d2, h]);
      if (d2 < bestD2) bestD2 = d2;
    }
    candidates.sort((a, b) => a[0] - b[0]);
    const target = candidates[Math.floor(Math.random() * Math.min(5, candidates.length))][1];
    tx = target.x; ty = target.y;
  } else {
    // Dies in the agent layer — wander off and fade.
    tx = midX + (Math.random() - 0.5) * 80;
    ty = midY + (Math.random() - 0.5) * 80;
  }
  const dx = tx - midX, dy = ty - midY;
  const d = Math.sqrt(dx * dx + dy * dy) || 1;
  const speed = success ? 3.6 : 2.0;
  _PARTICLES.push({
    x: midX, y: midY,
    vx: (dx / d) * speed, vy: (dy / d) * speed,
    tx, ty, age: 0, success,
    arrived: false, arrivedFlash: 0,
  });
}

function _drawParticles() {
  const ctx = ANIM.ctx;
  const remaining = [];
  for (const p of _PARTICLES) {
    p.age += 1;
    const maxAge = p.success ? 35 : 22;
    if (p.age >= maxAge) continue;
    if (!p.arrived) {
      p.x += p.vx;
      p.y += p.vy;
      const ddx = p.tx - p.x, ddy = p.ty - p.y;
      if (ddx * ddx + ddy * ddy < 9) {
        p.arrived = true;
        p.arrivedFlash = 0;
      }
    }
    const op = Math.max(0, 1 - p.age / maxAge);
    if (p.arrived && p.success) {
      // Bright green pulse on a human — welfare delivered.
      const flashSize = 6 - p.arrivedFlash;
      ctx.fillStyle = `rgba(150, 240, 170, ${op * 0.85})`;
      ctx.beginPath();
      ctx.arc(p.tx, p.ty, Math.max(2, flashSize), 0, Math.PI * 2);
      ctx.fill();
      p.arrivedFlash += 0.4;
    } else if (p.success) {
      ctx.fillStyle = `rgba(150, 230, 170, ${op * 0.85})`;
      ctx.beginPath();
      ctx.arc(p.x, p.y, 1.7, 0, Math.PI * 2);
      ctx.fill();
    } else {
      // Dissipating in the agent layer — small amber dot fading.
      ctx.fillStyle = `rgba(212, 158, 92, ${op * 0.40})`;
      ctx.beginPath();
      ctx.arc(p.x, p.y, 1.1, 0, Math.PI * 2);
      ctx.fill();
    }
    remaining.push(p);
  }
  _PARTICLES.length = 0;
  for (const p of remaining) _PARTICLES.push(p);
}

// Recursive fold-cascade spawner — produces fractal-looking fans of
// child flashes around an a2a base trade. Each child is a curved branch
// (quadratic Bezier; control point offset perpendicular to the from→to
// axis) that itself forks into 2-4 grandchildren at smaller angles, all
// tapering in length and width per generation. Terminal branches at max
// depth get a small "leaf" dot for visual closure. The branching factor,
// angle distribution, and per-depth attenuation approximate the engine's
// geometric kernel while producing the dense self-similar look.
function _spawnFoldChildren(parentFlash, depth, maxDepth) {
  if (depth >= maxDepth) return;
  // Higher base fork probability so dense fans actually appear; the depth
  // recursion + length attenuation keeps the canvas manageable.
  const forkProb = Math.pow(0.92, depth);
  if (Math.random() > forkProb) return;
  // 2-4 children per fork (more than before — fractal fans need enough
  // branches per generation to look organic rather than line-like).
  const branches = 2 + Math.floor(Math.random() * 3);
  const fx = parentFlash.from.x, fy = parentFlash.from.y;
  const tx = parentFlash.to.x,   ty = parentFlash.to.y;
  // Child origin: depth-0 children start at the parent's midpoint;
  // depth>0 children start at the parent's TO endpoint (the tip of the
  // previous branch), so successive generations propagate outward like
  // a tree growing rather than all radiating from one point.
  let ox, oy;
  if (depth === 0) {
    ox = (fx + tx) / 2; oy = (fy + ty) / 2;
  } else {
    ox = tx; oy = ty;
  }
  const dx = tx - fx, dy = ty - fy;
  const plen = Math.sqrt(dx * dx + dy * dy) || 1;
  const ux = dx / plen, uy = dy / plen;
  const px = -uy, py = ux;
  for (let i = 0; i < branches; i++) {
    // Length tapers ~50% per generation; randomness keeps siblings unequal.
    const childLen = plen * (0.42 + Math.random() * 0.28);
    // Branch angle: tighter as you go deeper so the tree doesn't fan
    // back across itself. Symmetric around 0 with random sign.
    const baseAngle = (Math.PI / 9) + Math.random() * (Math.PI / 5);
    const sign = (i % 2 === 0 ? 1 : -1) * (Math.random() < 0.5 ? -1 : 1);
    const a = baseAngle * (1 - depth * 0.15);
    const cdx = ux * Math.cos(a) + px * sign * Math.sin(a);
    const cdy = uy * Math.cos(a) + py * sign * Math.sin(a);
    const ex = ox + cdx * childLen;
    const ey = oy + cdy * childLen;
    // Quadratic-Bezier control point: offset perpendicular to the
    // from→to chord, with sign biased so the curve bends away from the
    // parent. Magnitude scales with branch length so it feels organic.
    const mx = (ox + ex) / 2, my = (oy + ey) / 2;
    const curveMag = childLen * (0.18 + Math.random() * 0.18) * (sign);
    // Perpendicular to child's own direction (not parent's).
    const cux = ex - ox, cuy = ey - oy;
    const cpLen = Math.sqrt(cux * cux + cuy * cuy) || 1;
    const cnx = -cuy / cpLen, cny = cux / cpLen;
    const cpx = mx + cnx * curveMag;
    const cpy = my + cny * curveMag;
    const child = {
      from: { x: ox, y: oy },
      to:   { x: ex, y: ey },
      cpx, cpy,                  // Bezier control point
      type: 'a2a',
      depth: depth + 1,
      isFold: true,              // marks this for curve-rendering
      isLeaf: (depth + 1) === maxDepth,
      age: 0,
    };
    ANIM.flashes.push(child);
    _spawnFoldChildren(child, depth + 1, maxDepth);
  }
}

// Per-frame motion: gentle random wander + anchor pull. Velocity
// accumulates from flash-based nudges (applied during flash spawn), so
// dots that trade frequently drift toward each other organically. Damped
// each frame so motion stays bounded.
function _stepDotMotion() {
  const all = [...ANIM.dotsH, ...ANIM.dotsA];
  for (const d of all) {
    if (d.vx === undefined) { d.vx = 0; d.vy = 0; }
    // Random wander — keeps the system alive even when nothing is flashing.
    d.vx += (Math.random() - 0.5) * 0.18;
    d.vy += (Math.random() - 0.5) * 0.18;
    // Soft anchor pull (back toward base position).
    d.vx += (d.bx - d.x) * 0.025;
    d.vy += (d.by - d.y) * 0.025;
    // Damping.
    d.vx *= 0.78;
    d.vy *= 0.78;
    // Integrate.
    d.x += d.vx;
    d.y += d.vy;
  }
}

function _animDraw() {
  const ctx = ANIM.ctx;
  if (!ctx) return;
  const h = ANIM.history;
  const i = Math.max(0, Math.min((h ? h.step.length - 1 : 0), ANIM.step - 1));

  // Solid dark background — no EBI tinting; the EBI signal is conveyed by
  // the welfare-particle flow (or its absence).
  ctx.fillStyle = '#0f1012';
  ctx.fillRect(0, 0, ANIM.width, ANIM.height - 18);
  _animDrawWelfareBar(i);

  // Step the motion system every frame so dots feel alive even between
  // simulation steps.
  _stepDotMotion();

  // Active flashes — short lifespan so each step's burst is its own visual event.
  // Depth-0 flashes are base trades (between actual prototypes), drawn as
  // straight lines. Depth-1+ flashes are sub-market events from the fold
  // cascade, rendered as quadratic Bezier curves (organic feel) with
  // tapered widths and terminal leaves at the cascade tips.
  const remaining = [];
  for (const f of ANIM.flashes) {
    f.age += 1;
    const lifespan = 5;
    if (f.age >= lifespan) continue;
    const op = 1 - (f.age / lifespan);
    const depth = f.depth || 0;
    // Per-generation attenuation matches the engine's depth-prop decay
    // and gives the cascade its tapered, "fading into the substrate" look.
    const depthOp = Math.pow(0.78, depth);
    const depthW = Math.pow(0.72, depth);
    let color, lw;
    if (f.type === 'a2a') { color = `rgba(212, 158, 92, ${op * 0.55 * depthOp})`; lw = 0.9 * depthW; }
    else if (f.type === 'h2a') { color = `rgba(91, 178, 220, ${op * 0.95})`; lw = 1.6; }
    else { color = `rgba(110, 220, 130, ${op * 1.0})`; lw = 3.0; }
    ctx.strokeStyle = color;
    ctx.lineWidth = Math.max(lw, 0.25);
    ctx.beginPath();
    ctx.moveTo(f.from.x, f.from.y);
    if (f.isFold && f.cpx !== undefined) {
      // Bezier curve for fold children — bends organically away from parent.
      ctx.quadraticCurveTo(f.cpx, f.cpy, f.to.x, f.to.y);
    } else {
      ctx.lineTo(f.to.x, f.to.y);
    }
    ctx.stroke();
    // Terminal leaves at cascade tips — a small filled dot at the very
    // ends of the deepest branches, so the fractal has visible terminals
    // rather than just trailing into nothing. Small enough not to clutter
    // shallow scenarios.
    if (f.isLeaf) {
      ctx.fillStyle = `rgba(212, 158, 92, ${op * 0.45 * depthOp})`;
      ctx.beginPath();
      ctx.arc(f.to.x, f.to.y, Math.max(0.8, 1.6 * depthW), 0, Math.PI * 2);
      ctx.fill();
    }
    remaining.push(f);
  }
  ANIM.flashes = remaining;

  // Welfare particles drawn after flashes, before dots (so dots sit on top).
  _drawParticles();

  // Dots — agents first (back), humans on top.
  for (const d of ANIM.dotsA) {
    ctx.fillStyle = d.winner ? '#f4b878' : '#d49e5c';
    ctx.beginPath();
    ctx.arc(d.x, d.y, d.r, 0, Math.PI * 2);
    ctx.fill();
  }
  for (const d of ANIM.dotsH) {
    ctx.fillStyle = '#5b8ec4';
    ctx.beginPath();
    ctx.arc(d.x, d.y, d.r, 0, Math.PI * 2);
    ctx.fill();
  }
}

// Bottom strip: cumulative real welfare as a fraction of cumulative nominal,
// rendered as a green bar against an amber background. In a smooth scenario
// the green fills the strip; in a baroque scenario it's a thin sliver and
// the amber dominates. Visually carries the EBI story without numbers.
function _animDrawWelfareBar(i) {
  const ctx = ANIM.ctx;
  const h = ANIM.history;
  if (!ctx) return;
  const y = ANIM.height - 14;
  const barH = 10;
  const x0 = 14;
  const x1 = ANIM.width - 14;
  const w = x1 - x0;
  // Background (the unrealised-nominal portion).
  ctx.fillStyle = 'rgba(212, 158, 92, 0.30)';
  ctx.fillRect(x0, y, w, barH);
  // Real welfare share (cumulative real / cumulative nominal).
  if (h) {
    const r = h.real_welfare_cumulative[i] || 0;
    const n = h.nominal_gdp_cumulative[i] || 0;
    const frac = n > 0 ? Math.max(0, Math.min(1, r / n)) : 0;
    ctx.fillStyle = 'rgba(95, 220, 130, 0.85)';
    ctx.fillRect(x0, y, w * frac, barH);
    // Tick marks at 1%, 10%, 100% to give the eye a reference.
    ctx.fillStyle = 'rgba(255, 255, 255, 0.18)';
    for (const f of [0.001, 0.01, 0.1, 0.5]) {
      ctx.fillRect(x0 + w * f, y - 2, 1, barH + 4);
    }
    // Percent label (left-anchored)
    ctx.fillStyle = 'rgba(255, 255, 255, 0.65)';
    ctx.font = '10px ui-monospace, monospace';
    const pct = (frac * 100);
    const label = pct >= 1 ? pct.toFixed(0) + '% real' : pct.toFixed(2) + '% real';
    ctx.fillText(label, x0 + 4, y - 3);
  }
}

function _animSpawnFlashesForStep(stepIdx) {
  const h = ANIM.history;
  if (!h) return;
  if (stepIdx < 0 || stepIdx >= h.step.length) return;

  // Concentration signal: Gini × time-fraction. Drives winner migration
  // toward each winner's personal attractor (set at layout time, scattered
  // across the canvas) and winner-dot size growth.
  const gini = h.gini_wealth[stepIdx] || 0.4;
  const tFrac = stepIdx / Math.max(h.step.length - 1, 1);
  const concentration = Math.max(0, gini - 0.3) * tFrac;  // 0..~0.7
  const winnerR = 2.0 + 7 * concentration;
  for (const d of ANIM.dotsA) {
    if (!d.winner) continue;
    // Each winner has its own (targetX, targetY) from layout — they migrate
    // toward different attractor points around the canvas, not a single corner.
    if (d.targetX !== undefined) {
      d.bx = d.bx + (d.targetX - d.bx) * 0.045;
      d.by = d.by + (d.targetY - d.by) * 0.045;
    }
    d.r = winnerR;
  }

  // Flash density tracks per-step transaction throughput.
  const ntx = h.n_transactions_real[stepIdx] || 0;
  const ntxMax = Math.max.apply(null, h.n_transactions_real) || 1;
  const nFlashes = Math.max(4, Math.round(80 * (ntx / Math.max(ntxMax, 1))));
  const a2a = h.a2a_share[stepIdx];
  const h2a = h.h2a_share[stepIdx];
  const ebi = h.exo_baroque_index[stepIdx] || 1;
  // Sub-markets-per-base-trade ratio drives fan probability and fan depth.
  // This varies across ~7 orders of magnitude between scenarios while
  // fold_max_depth is binary, so it's the right signal for the cascade
  // visualisation. Log-scaled when applied below.
  const nsub = h.n_sub_markets_added[stepIdx] || 0;
  const subRatio = nsub / Math.max(ntx, 1);

  for (let i = 0; i < nFlashes; i++) {
    const r = Math.random();
    let from, to, type;
    if (r < a2a) {
      type = 'a2a';
      from = ANIM.dotsA[Math.floor(Math.random() * ANIM.dotsA.length)];
      to = ANIM.dotsA[Math.floor(Math.random() * ANIM.dotsA.length)];
    } else if (r < a2a + h2a) {
      type = 'h2a';
      from = ANIM.dotsH[Math.floor(Math.random() * ANIM.dotsH.length)];
      to = ANIM.dotsA[Math.floor(Math.random() * ANIM.dotsA.length)];
    } else {
      type = 'h2h';
      from = ANIM.dotsH[Math.floor(Math.random() * ANIM.dotsH.length)];
      to = ANIM.dotsH[Math.floor(Math.random() * ANIM.dotsH.length)];
    }
    if (!from || !to || from === to) continue;
    // Flash-based attraction: nudge both endpoints toward each other so
    // dots that frequently trade drift together.
    const dx = (to.x - from.x);
    const dy = (to.y - from.y);
    const k = 0.012;
    from.vx = (from.vx || 0) + dx * k;
    from.vy = (from.vy || 0) + dy * k;
    to.vx = (to.vx || 0) - dx * k;
    to.vy = (to.vy || 0) - dy * k;
    // Bump activity (later: drives subtle dot-size growth for non-winners).
    from.activity = (from.activity || 0) + 1;
    to.activity = (to.activity || 0) + 1;
    // Store dot references on the flash so render uses post-motion positions.
    const baseFlash = { from, to, type, depth: 0, age: 0 };
    ANIM.flashes.push(baseFlash);
    // Welfare particle from flash midpoint — represents this trade's
    // contribution toward (or failure to deliver) human consumption.
    _spawnParticleFromFlash((from.x + to.x) / 2, (from.y + to.y) / 2, ebi);
    // Fold cascade: drive fan probability and fan depth off the actual
    // sub-markets-per-trade ratio computed by the engine each step,
    // not off `fold_max_depth` (which saturates trivially at the cap and
    // therefore carries almost no scenario information). Log-scaled so
    // ratios spanning ~7 orders of magnitude across scenarios all map
    // into legible fan density.
    if (type === 'a2a' && subRatio > 0) {
      // probability ∈ [0, 1]: 0 at ratio≈0, 0.5 around ratio≈0.1, 1 above ratio≈1
      const p = Math.min(1, Math.log10(1 + subRatio * 100) / 2);
      if (Math.random() < p) {
        // depth ∈ [2, 5]: shallow fans at low ratio, dense recursion at high
        const fanDepth = Math.min(5, Math.max(2, Math.floor(2 + Math.log10(1 + subRatio * 100))));
        _spawnFoldChildren(baseFlash, 0, fanDepth);
      }
    }
  }
}

function _animUpdateStats() {
  const h = ANIM.history;
  if (!h) return;
  const i = ANIM.step;
  document.getElementById('a-step').textContent = i;
  document.getElementById('a-real').textContent = _animFmtBig(h.real_welfare_cumulative[i] || 0);
  document.getElementById('a-nom').textContent = _animFmtBig(h.nominal_gdp_cumulative[i] || 0);
  const ebi = h.exo_baroque_index[i] || 1;
  document.getElementById('a-ebi').textContent = ebi < 100 ? ebi.toFixed(2) : ebi.toExponential(2);
  document.getElementById('a-fold').textContent = _animFmtBig(h.n_sub_markets_added[i] || 0);
  document.getElementById('a-a2a').textContent = ((h.a2a_share[i] || 0) * 100).toFixed(2) + '%';
  document.getElementById('anim-scrub').value = i;
}

function _animTick() {
  const h = ANIM.history;
  if (!h) return;
  if (ANIM.step >= h.step.length) {
    _animPause();
    return;
  }
  _animSpawnFlashesForStep(ANIM.step);
  _animDraw();
  _animUpdateStats();
  ANIM.step += 1;
}

function _animPlay() {
  if (ANIM.playing) return;
  ANIM.playing = true;
  document.getElementById('anim-play').textContent = '❚❚ pause';
  if (ANIM.step >= (ANIM.history?.step?.length || 60)) ANIM.step = 0;
  ANIM.intervalId = setInterval(_animTick, ANIM.speed);
}
function _animPause() {
  if (!ANIM.playing) return;
  ANIM.playing = false;
  document.getElementById('anim-play').textContent = '▶ play';
  if (ANIM.intervalId) { clearInterval(ANIM.intervalId); ANIM.intervalId = null; }
}
function _animTogglePlay() { ANIM.playing ? _animPause() : _animPlay(); }
function _animRestart() {
  _animPause();
  ANIM.step = 0;
  ANIM.flashes = [];
  // Hard clear (no fade)
  ANIM.ctx.fillStyle = '#0f1012';
  ANIM.ctx.fillRect(0, 0, ANIM.width, ANIM.height);
  _animLayoutDots();
  _animDraw();
  _animUpdateStats();
}
function _animScrubTo(idx) {
  _animPause();
  ANIM.step = idx;
  ANIM.flashes = [];
  ANIM.ctx.fillStyle = '#0f1012';
  ANIM.ctx.fillRect(0, 0, ANIM.width, ANIM.height);
  _animLayoutDots();
  // Spawn just this step's flashes for context
  _animSpawnFlashesForStep(idx);
  _animDraw();
  _animUpdateStats();
}

function initAnimation(scenarioName) {
  _animPause();
  ANIM.scenarioName = scenarioName;
  ANIM.history = SCN[scenarioName]?.history || null;
  ANIM.step = 0;
  ANIM.flashes = [];

  const c = document.getElementById('anim-canvas');
  if (!c) return;
  ANIM.canvas = c;
  ANIM.ctx = c.getContext('2d');
  _animResize();
  _animLayoutDots();

  // Wire controls (rebind each scenario load — cheap and idempotent)
  const playBtn = document.getElementById('anim-play');
  const restartBtn = document.getElementById('anim-restart');
  const scrub = document.getElementById('anim-scrub');
  const speed = document.getElementById('anim-speed');
  if (playBtn) playBtn.onclick = _animTogglePlay;
  if (restartBtn) restartBtn.onclick = _animRestart;
  if (scrub && ANIM.history) {
    scrub.max = ANIM.history.step.length - 1;
    scrub.oninput = (e) => _animScrubTo(parseInt(e.target.value, 10));
  }
  if (speed) speed.onchange = (e) => {
    ANIM.speed = parseInt(e.target.value, 10);
    if (ANIM.playing) { _animPause(); _animPlay(); }
  };

  // n-steps display
  const nstepsEl = document.getElementById('a-nsteps');
  if (nstepsEl && ANIM.history) nstepsEl.textContent = ANIM.history.step.length;

  // Initial frame: hard-clear and render dots.
  ANIM.ctx.fillStyle = '#0f1012';
  ANIM.ctx.fillRect(0, 0, ANIM.width, ANIM.height);
  _animDraw();
  _animUpdateStats();

  // Initial frame is rendered above; wait for the user to click play.
}

// Re-layout on container resize.
window.addEventListener('resize', () => {
  if (!ANIM.canvas) return;
  _animResize();
  _animLayoutDots();
  _animDraw();
});

// ---------- detail pane ----------
function loadDetail(name) {
  renderStrip(name);
  const s = SCN[name];
  document.getElementById('active-name').textContent = s.label;
  document.getElementById('active-desc').textContent = s.description;

  const ens = ENSEMBLES[name];
  const status = document.getElementById('ensemble-status');
  if (ens) {
    status.innerHTML =
      `<b style="color:var(--accent);">Ensemble:</b> ${ens.n_seeds} seeds, ${ens.n_steps} steps. ` +
      'Plots show the single seeded run on top; translucent envelope is the bootstrapped 5/95 percentile band; ' +
      'dotted line is the ensemble median. See the primer for what bands mean and don\'t.';
  } else {
    status.innerHTML =
      '<i style="color:var(--text-3);">No ensemble loaded for this scenario. Run </i>' +
      '<code>agentworld ensemble ' + name + ' --seeds 64</code><i style="color:var(--text-3);"> to populate.</i>';
  }

  const h = s.history;
  const last = (a) => a[a.length - 1];

  const meta = document.getElementById('active-meta');
  meta.innerHTML = `
    <div class="stat"><div class="label">Final α (regime label)</div><div class="value tinted">${s.final_alpha.toFixed(2)} <span style="font-size:13px; color:var(--text-3);">${s.final_label}</span></div></div>
    <div class="stat"><div class="label">Exo-baroque index</div><div class="value">${last(h.exo_baroque_index) < 100 ? last(h.exo_baroque_index).toFixed(2) : last(h.exo_baroque_index).toExponential(2)}</div><div class="sub">nominal / real, log-scale</div></div>
    <div class="stat"><div class="label">Per-capita real welfare</div><div class="value">${fmtW(last(h.real_per_capita_welfare))}</div><div class="sub">cumulative · ×10³ stylized units</div></div>
    <div class="stat"><div class="label">Wealth Gini</div><div class="value">${last(h.gini_wealth).toFixed(3)}</div></div>
    <div class="stat"><div class="label">Sub-markets created (peak)</div><div class="value">${_animFmtBig(Math.max(...h.n_sub_markets_added))}</div><div class="sub">peak step's fold-cascade output</div></div>
    <div class="stat"><div class="label">A2A interaction share</div><div class="value">${(last(h.a2a_share) * 100).toFixed(1)}%</div><div class="sub">vs H2A: ${(last(h.h2a_share) * 100).toFixed(2)}% · H2H: ${(last(h.h2h_share) * 100).toFixed(3)}%</div></div>
    <div class="stat"><div class="label">Governance overhead</div><div class="value">${(last(h.governance_overhead_fraction) * 100).toFixed(1)}%</div><div class="sub">share of attempted trades killed by filters</div></div>
  `;

  const baseLayout = {
    paper_bgcolor: '#14161a', plot_bgcolor: '#14161a',
    font: { color: '#9ea2a8', family: 'Inter, sans-serif', size: 10 },
    margin: { l: 50, r: 16, t: 6, b: 36 },
    xaxis: { title: 'step', gridcolor: '#23262b', zerolinecolor: '#2a2d33' },
    yaxis: { gridcolor: '#23262b', zerolinecolor: '#2a2d33' },
    showlegend: false,
  };

  Plotly.react('d-alpha',
    [{ x: h.step, y: h.alpha, mode: 'lines', line: { color: '#b89a55', width: 2 }, fill: 'tozeroy', fillcolor: 'rgba(184,154,85,0.06)' }],
    { ...baseLayout, yaxis: { ...baseLayout.yaxis, range: [0, 1] } },
    { displayModeBar: false, responsive: true });

  Plotly.react('d-realnom',
    [
      ..._bandTraces(name, 'real_welfare_cumulative', 'rgba(95,165,114,0.2)'),
      ..._bandTraces(name, 'nominal_gdp_cumulative', 'rgba(194,90,90,0.2)'),
      { x: h.step, y: h.real_welfare_cumulative, name: 'real welfare', mode: 'lines', line: { color: '#5fa572', width: 2 } },
      { x: h.step, y: h.nominal_gdp_cumulative, name: 'nominal GDP', mode: 'lines', line: { color: '#c25a5a', width: 2 } },
    ],
    { ...baseLayout, yaxis: { ...baseLayout.yaxis, type: 'log' }, showlegend: true, legend: { orientation: 'h', y: 1.15, font: { size: 9 } } },
    { displayModeBar: false, responsive: true });

  Plotly.react('d-ebi',
    [
      ..._bandTraces(name, 'exo_baroque_index', 'rgba(144,119,194,0.2)'),
      { x: h.step, y: h.exo_baroque_index, mode: 'lines', line: { color: '#9077c2', width: 2 } },
    ],
    { ...baseLayout, yaxis: { ...baseLayout.yaxis, type: 'log' },
      shapes: [{ type: 'line', x0: 0, x1: h.step.length - 1, y0: 1, y1: 1, line: { color: '#666', dash: 'dash', width: 1 } }] },
    { displayModeBar: false, responsive: true });

  Plotly.react('d-fold',
    [
      ..._bandTraces(name, 'n_sub_markets_added', 'rgba(91,142,196,0.2)'),
      { x: h.step, y: h.n_sub_markets_added, mode: 'lines',
        line: { color: '#5b8ec4', width: 2 },
        fill: 'tozeroy', fillcolor: 'rgba(91,142,196,0.08)' },
    ],
    { ...baseLayout, yaxis: { ...baseLayout.yaxis, type: 'log' } },
    { displayModeBar: false, responsive: true });

  Plotly.react('d-pc',
    [
      ..._bandTraces(name, 'real_per_capita_welfare', 'rgba(95,165,114,0.2)', WELFARE_SCALE),
      { x: h.step, y: h.real_per_capita_welfare.map(v => v * WELFARE_SCALE),
        mode: 'lines', line: { color: '#5fa572', width: 2 }, fill: 'tozeroy', fillcolor: 'rgba(95,165,114,0.08)' },
    ],
    baseLayout, { displayModeBar: false, responsive: true });

  // Rejection share, normalized & stacked.
  const rl = h.rejected_law, rm = h.rejected_market, ra = h.rejected_align, rc = h.rejected_cost;
  const tot = rl.map((_, i) => Math.max(rl[i] + rm[i] + ra[i] + rc[i], 1));
  const stack = (arr) => arr.map((v, i) => v / tot[i]);
  Plotly.react('d-rej',
    [
      { x: h.step, y: stack(rl), name: 'law', stackgroup: 'one', mode: 'none', fillcolor: 'rgba(194,90,90,0.7)' },
      { x: h.step, y: stack(rm), name: 'market', stackgroup: 'one', mode: 'none', fillcolor: 'rgba(91,142,196,0.7)' },
      { x: h.step, y: stack(ra), name: 'alignment', stackgroup: 'one', mode: 'none', fillcolor: 'rgba(95,165,114,0.7)' },
      { x: h.step, y: stack(rc), name: 'cost', stackgroup: 'one', mode: 'none', fillcolor: 'rgba(184,154,85,0.7)' },
    ],
    { ...baseLayout, yaxis: { ...baseLayout.yaxis, range: [0, 1] }, showlegend: true, legend: { orientation: 'h', y: 1.15, font: { size: 9 } } },
    { displayModeBar: false, responsive: true });

  // Authentic vs un-modulated real welfare. When DemandConfig is off
  // (the substrate-anchored default for 21 of 25 dashboard scenarios),
  // the two curves are mathematically identical — show an overlay note
  // rather than letting the reader stare at a single line wondering why.
  const demandOn = !!(s.config && s.config.topology && s.config.topology.demand && s.config.topology.demand.enabled);
  const authCum = h.real_welfare_authentic_cumulative || h.real_welfare_cumulative;
  const authAnnotations = demandOn ? [] : [{
    text: 'demand modulation off — the two curves coincide exactly',
    showarrow: false,
    xref: 'paper', yref: 'paper', x: 0.5, y: 0.92,
    font: { color: '#9ea2a8', size: 11, family: 'Iowan Old Style, Georgia, serif' },
    bgcolor: 'rgba(20,22,26,0.85)', bordercolor: 'rgba(154,158,168,0.3)', borderwidth: 1, borderpad: 4,
  }];
  Plotly.react('d-authentic',
    [
      { x: h.step, y: h.real_welfare_cumulative, name: 'real welfare (un-modulated)',
        mode: 'lines', line: { color: '#5fa572', width: 2 } },
      { x: h.step, y: authCum, name: 'authentic (human-consumed)',
        mode: 'lines', line: { color: '#b89a55', width: 2, dash: 'solid' } },
    ],
    { ...baseLayout, yaxis: { ...baseLayout.yaxis, type: 'log' },
      annotations: authAnnotations,
      showlegend: true, legend: { orientation: 'h', y: 1.15, font: { size: 9 } } },
    { displayModeBar: false, responsive: true });

  // Productive folding welfare yield vs nominal residual. When productive
  // folding is off (base_variance_absorption=0, the substrate-anchored
  // default for 21 of 25 scenarios), yield is flat zero and nominal residual
  // is flat 1.0 — show an overlay note explaining why.
  const productiveOn = !!(s.config && s.config.topology && s.config.topology.base_variance_absorption > 0);
  const pfs = h.productive_welfare_yield || h.step.map(() => 0);
  const pas = (h.parasitic_nominal_residual != null)
    ? h.parasitic_nominal_residual
    : pfs.map(v => 1 - v);
  const prodAnnotations = productiveOn ? [] : [{
    text: 'productive folding off (base_variance_absorption = 0) — all fold-cascade volume is parasitic',
    showarrow: false,
    xref: 'paper', yref: 'paper', x: 0.5, y: 0.5,
    font: { color: '#e7e8ea', size: 11, family: 'Iowan Old Style, Georgia, serif' },
    bgcolor: 'rgba(20,22,26,0.85)', bordercolor: 'rgba(154,158,168,0.3)', borderwidth: 1, borderpad: 4,
  }];
  Plotly.react('d-pfs',
    [
      { x: h.step, y: pfs, name: 'welfare yield', stackgroup: 'one', mode: 'none', fillcolor: 'rgba(95,165,114,0.7)' },
      { x: h.step, y: pas, name: 'nominal residual', stackgroup: 'one', mode: 'none', fillcolor: 'rgba(194,90,90,0.7)' },
    ],
    { ...baseLayout, yaxis: { ...baseLayout.yaxis, range: [0, 1] },
      annotations: prodAnnotations,
      showlegend: true, legend: { orientation: 'h', y: 1.15, font: { size: 9 } } },
    { displayModeBar: false, responsive: true });

  // Initialize the transaction-space animation for this scenario.
  initAnimation(name);
  // §5's welfare-flow Sankey inherits the same scenario.
  renderWelfareFlow(name);
}

// ---------- compare ----------
const COMPARE_DEFAULT = ['coasean_paradise', 'baroque_cathedral', 'slop_market', 'universal_advocate'];
let compareSelection = new Set(COMPARE_DEFAULT);

function _mkAction(label, title, onClick) {
  const el = document.createElement('div');
  el.className = 'chip action';
  el.textContent = label;
  el.title = title;
  el.onclick = onClick;
  return el;
}

function renderCompareBar() {
  const bar = document.getElementById('compare-bar');
  bar.innerHTML = '';
  ORDER.forEach(name => {
    const s = SCN[name];
    const chip = document.createElement('div');
    chip.className = 'chip' + (compareSelection.has(name) ? ' active' : '');
    chip.textContent = s.label;
    chip.title = 'Click to toggle. Alt-click to solo (keeps only this scenario).';
    chip.addEventListener('click', (ev) => {
      if (ev.altKey) {
        // Solo: if this is already the only selected scenario, restore defaults.
        // Otherwise, isolate to just this one.
        if (compareSelection.size === 1 && compareSelection.has(name)) {
          compareSelection = new Set(COMPARE_DEFAULT);
        } else {
          compareSelection = new Set([name]);
        }
      } else {
        if (compareSelection.has(name)) compareSelection.delete(name);
        else compareSelection.add(name);
      }
      renderCompareBar();
      renderCompare();
    });
    bar.appendChild(chip);
  });

  const sep = document.createElement('div');
  sep.className = 'chip-sep';
  bar.appendChild(sep);

  bar.appendChild(_mkAction('All', 'Select every scenario',
    () => { compareSelection = new Set(ORDER); renderCompareBar(); renderCompare(); }));
  bar.appendChild(_mkAction('Clear', 'Deselect every scenario',
    () => { compareSelection = new Set(); renderCompareBar(); renderCompare(); }));
  bar.appendChild(_mkAction('Reset', 'Restore the four corner-defining scenarios (' + COMPARE_DEFAULT.join(', ') + ')',
    () => { compareSelection = new Set(COMPARE_DEFAULT); renderCompareBar(); renderCompare(); }));
}

const PALETTE = ['#b89a55','#5fa572','#c25a5a','#5b8ec4','#9077c2','#c2954b','#5fa5a5','#a55f8c','#7ea55f','#5f7ea5','#a55f5f','#a8a85f','#5fa55f','#a55fa5','#5f5fa8'];

function renderCompare() {
  const sel = ORDER.filter(n => compareSelection.has(n));
  const baseLayout = {
    paper_bgcolor: '#14161a', plot_bgcolor: '#14161a',
    font: { color: '#9ea2a8', family: 'Inter, sans-serif', size: 10 },
    margin: { l: 56, r: 16, t: 6, b: 36 },
    xaxis: { title: 'step', gridcolor: '#23262b', zerolinecolor: '#2a2d33' },
    yaxis: { gridcolor: '#23262b', zerolinecolor: '#2a2d33' },
    legend: { orientation: 'h', y: 1.15, font: { size: 9 } },
  };
  const trace = (name, key, idx, scale) => {
    const s = SCN[name];
    const y = scale ? s.history[key].map(v => v * scale) : s.history[key];
    return { x: s.history.step, y: y, name: s.label, mode: 'lines', line: { color: PALETTE[idx % PALETTE.length], width: 1.7 } };
  };
  Plotly.react('c-ebi', sel.map((n, i) => trace(n, 'exo_baroque_index', i)),
    { ...baseLayout, yaxis: { ...baseLayout.yaxis, type: 'log' } },
    { displayModeBar: false, responsive: true });
  Plotly.react('c-pc', sel.map((n, i) => trace(n, 'real_per_capita_welfare', i, WELFARE_SCALE)), baseLayout, { displayModeBar: false, responsive: true });
  Plotly.react('c-nom', sel.map((n, i) => trace(n, 'nominal_gdp_cumulative', i)),
    { ...baseLayout, yaxis: { ...baseLayout.yaxis, type: 'log' } },
    { displayModeBar: false, responsive: true });
  Plotly.react('c-leg', sel.map((n, i) => trace(n, 'human_legibility_index', i)),
    { ...baseLayout, yaxis: { ...baseLayout.yaxis, range: [0, 1] } },
    { displayModeBar: false, responsive: true });
}

// ---------- phase space ----------
// Data is a regular grid (alpha_values × capability_values). A heatmap is the
// structurally honest viz: one cell per grid point, colored by log₁₀(EBI),
// with a basin-label overlay so the basin boundary is legible at a glance.
const BASIN_GLYPH = { smooth: '○', mixed: '·', striated: '◐', baroque: '●', slop: '×' };
const BASIN_COLOR = {
  smooth:   '#5fa572',
  mixed:    '#b89a55',
  striated: '#c2954b',
  baroque:  '#c25a5a',
  slop:     '#9077c2',
};

function renderPhaseSpace() {
  // §6 is now the welfare-flow Sankey rather than the basin map.
  // Renamed entry point preserved for backward compat with renderAll.
  return renderWelfareFlow();
}

function _welfareFlowFor(s) {
  // Compute the cumulative nominal-GDP flow buckets for one scenario.
  // All values are in the same stylized unit as nominal_gdp_cumulative.
  const h = s.history;
  const last = (a) => a[a.length - 1] || 0;
  const sum = (a) => a.reduce((x, y) => x + (y || 0), 0);
  const N = last(h.nominal_gdp_cumulative);
  const R = last(h.real_welfare_cumulative);
  const R_auth = last(h.real_welfare_authentic_cumulative);
  // Agents' share = real welfare that didn't reach humans.
  const toAgents = Math.max(0, R - R_auth);
  const L = sum(h.law_weak_surplus_loss_step) +
            sum(h.law_capture_surplus_loss_step) +
            sum(h.law_upkeep_cost_step);
  const P = last(h.pigouvian_revenue_cumulative);
  // Parasitic accounting = the rest. Floor at 0 in case of rounding.
  const parasitic = Math.max(0, N - R - L - P);
  return { N, R, R_auth, toAgents, L, P, parasitic };
}

function _welfareDescription(f) {
  const N = f.N || 1;
  const pHuman = f.R_auth / N;
  const pAgent = f.toAgents / N;
  const pLaw = f.L / N;
  const pPig = f.P / N;
  const pPar = f.parasitic / N;
  // Identify the dominant destination and frame the one-line story.
  const buckets = [
    ['humans',           pHuman, 'Most measured activity reached a human as actual consumption.'],
    ['agents',           pAgent, 'Welfare circulates within the agent layer rather than reaching humans.'],
    ['law system',       pLaw,   'The law system is the binding constraint — overhead or capture is eating most surplus.'],
    ['Pigouvian',        pPig,   'The Pigouvian tax is recycling a meaningful share back to humans.'],
    ['parasitic accounting', pPar, 'Most measured activity is fold-cascade accounting that no human ever consumed.'],
  ];
  buckets.sort((a, b) => b[1] - a[1]);
  return buckets[0][2];
}

// Track the active scenario across §4 and §5. `loadDetail` updates this.
let _activeWelfareScenario = null;

function renderWelfareFlow(name) {
  // The §3 scenario strip drives §4's detail pane via loadDetail; we reuse
  // that same selection for §5's welfare-flow Sankey rather than maintaining
  // a separate dropdown. Falls back to the last-known active scenario when
  // called without an explicit name (e.g. on initial page load).
  if (name) _activeWelfareScenario = name;
  const activeName = _activeWelfareScenario || Object.keys(SCN)[0];
  const s = SCN[activeName];
  if (!s) return;
  const labelEl = document.getElementById('welfare-scn-label');
  if (labelEl) labelEl.textContent = s.label;
  const f = _welfareFlowFor(s);

  // Build the Sankey. Order: source → real-welfare → humans/agents,
  // and source → law / pigouvian / parasitic.
  // Always include the same node set so node positions stay stable when
  // the user switches scenarios.
  const nodes = {
    label: [
      'Total nominal GDP',           // 0 — source
      'Real welfare delivered',      // 1 — intermediate
      '→ to humans',                 // 2
      '→ to agents',                 // 3
      'Lost to law system',          // 4
      'Recycled (Pigouvian)',        // 5
      'Parasitic accounting',        // 6
    ],
    color: [
      '#6a6d72',  // 0 source — neutral grey
      '#9ea2a8',  // 1 intermediate
      '#5fa572',  // 2 humans — green
      '#d49e5c',  // 3 agents — amber
      '#c25a5a',  // 4 law — red
      '#5b8ec4',  // 5 pigouvian — blue
      '#43464b',  // 6 parasitic — dark grey
    ],
  };
  // Plotly Sankey requires positive link values. Use small epsilons so
  // missing categories still render (the node stays in place but the
  // ribbon is invisible). 1e-6 of N is below visible thickness.
  const eps = Math.max(1, f.N * 1e-9);
  const linkSrc = [0, 0, 0, 0, 1, 1];
  const linkDst = [1, 4, 5, 6, 2, 3];
  const linkVal = [
    Math.max(eps, f.R),               // 0→1 real welfare
    Math.max(eps, f.L),               // 0→4 law
    Math.max(eps, f.P),               // 0→5 pigouvian
    Math.max(eps, f.parasitic),       // 0→6 parasitic
    Math.max(eps, f.R_auth),          // 1→2 humans
    Math.max(eps, f.toAgents),        // 1→3 agents
  ];
  // Per-link color (lower opacity than the node colors).
  const linkColor = [
    'rgba(158, 162, 168, 0.30)',  // → real welfare
    'rgba(194, 90, 90, 0.45)',    // → law
    'rgba(91, 142, 196, 0.45)',   // → pigouvian
    'rgba(67, 70, 75, 0.55)',     // → parasitic
    'rgba(95, 165, 114, 0.55)',   // → humans
    'rgba(212, 158, 92, 0.50)',   // → agents
  ];
  const linkLabel = [
    `${(f.R / Math.max(f.N, 1) * 100).toFixed(2)}%`,
    `${(f.L / Math.max(f.N, 1) * 100).toFixed(2)}%`,
    `${(f.P / Math.max(f.N, 1) * 100).toFixed(2)}%`,
    `${(f.parasitic / Math.max(f.N, 1) * 100).toFixed(2)}%`,
    `${(f.R_auth / Math.max(f.N, 1) * 100).toFixed(2)}%`,
    `${(f.toAgents / Math.max(f.N, 1) * 100).toFixed(2)}%`,
  ];

  Plotly.react('welfare-sankey', [{
    type: 'sankey',
    arrangement: 'snap',
    node: {
      label: nodes.label,
      color: nodes.color,
      pad: 18, thickness: 22,
      line: { color: '#0f1012', width: 0.5 },
    },
    link: {
      source: linkSrc, target: linkDst, value: linkVal,
      color: linkColor, label: linkLabel,
      hovertemplate: '%{source.label} → %{target.label}<br>%{value:.3e}<extra></extra>',
    },
    valueformat: '.3e',
    textfont: { color: '#e7e8ea', family: 'Inter, sans-serif', size: 13 },
  }], {
    paper_bgcolor: '#14161a', plot_bgcolor: '#14161a',
    font: { color: '#9ea2a8', family: 'Inter, sans-serif', size: 12 },
    margin: { l: 10, r: 10, t: 10, b: 10 },
  }, { displayModeBar: false, responsive: true });

  // Update right-side breakdown numbers.
  const pct = (x) => (x / Math.max(f.N, 1) * 100);
  const fmtRow = (val) => `${_animFmtBig(val)} <span style="color:var(--text-3); font-size:11px;">(${pct(val).toFixed(2)}%)</span>`;
  document.getElementById('w-r-total').innerHTML  = _animFmtBig(f.N);
  document.getElementById('w-r-humans').innerHTML = fmtRow(f.R_auth);
  document.getElementById('w-r-agents').innerHTML = fmtRow(f.toAgents);
  document.getElementById('w-r-law').innerHTML    = fmtRow(f.L);
  document.getElementById('w-r-pig').innerHTML    = fmtRow(f.P);
  document.getElementById('w-r-paras').innerHTML  = fmtRow(f.parasitic);
  document.getElementById('w-r-foot').textContent = _welfareDescription(f);

  // Section-level callout — fixed orientation guidance, since the
  // scenario picker now lives upstream in §3.
  const note = document.getElementById('welfare-note');
  if (note) {
    note.innerHTML =
      'Cycle through a few in §3 to see how different the destinations are: ' +
      '<b>Coasean Paradise</b> ≈ 95% humans / 5% parasitic; ' +
      '<b>Baroque Cathedral</b> &lt; 0.05% humans / ≈ 99.96% parasitic; ' +
      '<b>Legal Collapse</b> ≈ 65% lost to the law system; ' +
      '<b>Pigouvian Heavy</b> recycles ≈ 8.3% via the tax (vs 4% in <i>Synthetic Customers</i> with the same demand modulation but no tax). ' +
      'Same engine, same population scale, different destinations.';
  }
}

// ---------- provenance ----------
// Renders the calibrated/stipulated/speculative provenance from
// engine/data/empirical_anchors.py. Pure DOM; no charts.
function renderProvenance() {
  const host = document.getElementById('provenance-panel');
  if (!host) return;
  if (!PROVENANCE.length) {
    host.innerHTML = '';
    return;
  }
  const rows = PROVENANCE.map(p => `
    <tr>
      <td style="padding:8px 12px; font-family:var(--mono); font-size:11px; color:var(--accent);">${p.name}</td>
      <td style="padding:8px 12px; font-family:var(--serif); font-size:13px;">${p.scope}</td>
      <td style="padding:8px 12px; font-family:var(--sans); font-size:12px; color:var(--text-2);">${p.source}</td>
      <td style="padding:8px 12px; font-family:var(--mono); font-size:12px; color:var(--text-3);">${p.vintage}</td>
    </tr>`).join('');
  host.innerHTML = `
    <div class="panel">
      <h3 style="margin-top:0;font-family:var(--serif);font-weight:400;">Empirical anchor provenance</h3>
      <p style="font-family:var(--serif);font-size:13px;line-height:1.55;color:var(--text-2);margin-top:4px;">
        Every constant below is calibrated against a public source. Anchors govern noise structure
        (heavy-tail shape, sectoral / regional co-movement, network degree, cascade branching),
        not load-bearing model behavior. Re-anchor on source updates and rerun the dashboard.
      </p>
      <table style="width:100%; border-collapse:collapse; margin-top:8px;">
        <thead>
          <tr style="border-bottom:1px solid var(--border); font-size:11px; text-transform:uppercase; color:var(--text-3); letter-spacing:0.08em;">
            <th style="padding:6px 12px; text-align:left;">Anchor</th>
            <th style="padding:6px 12px; text-align:left;">Scope</th>
            <th style="padding:6px 12px; text-align:left;">Source</th>
            <th style="padding:6px 12px; text-align:left;">Vintage</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

// ---------- sobol ----------
// Renders S1 (filled) + ST (outlined) bars per parameter for one (engine, metric)
// pair. Sorts by ST descending. Caller passes the SobolSummary, the metric
// to display, and the chart container id.
function _sobolBarFigure(summary, metric, divId, paramBoundsLabel) {
  if (!summary) {
    Plotly.purge(divId);
    return false;
  }
  const idx = summary.indices.find(i => i.metric === metric);
  if (!idx) {
    Plotly.purge(divId);
    return false;
  }
  // Sort parameters by ST descending so the dominant knob lands on top.
  const sortIdx = idx.parameter_names
    .map((_, i) => i)
    .sort((a, b) => idx.ST[b] - idx.ST[a]);
  const names = sortIdx.map(i => idx.parameter_names[i]);
  const s1 = sortIdx.map(i => Math.max(0, idx.S1[i]));
  const st = sortIdx.map(i => Math.max(0, idx.ST[i]));
  const s1c = sortIdx.map(i => idx.S1_conf[i]);
  const stc = sortIdx.map(i => idx.ST_conf[i]);

  const traceS1 = {
    x: s1, y: names, type: 'bar', orientation: 'h',
    name: 'S1 (first-order)',
    marker: { color: 'rgba(184,154,85,0.8)', line: { color: '#b89a55', width: 1 } },
    error_x: { type: 'data', array: s1c, color: '#6a6d72', thickness: 1 },
    hovertemplate: '<b>%{y}</b><br>S1 = %{x:.3f} ± %{error_x.array:.3f}<extra></extra>',
  };
  const traceST = {
    x: st, y: names, type: 'bar', orientation: 'h',
    name: 'ST (total-order)',
    marker: { color: 'rgba(95,165,114,0.0)', line: { color: '#5fa572', width: 2 } },
    error_x: { type: 'data', array: stc, color: '#6a6d72', thickness: 1 },
    hovertemplate: '<b>%{y}</b><br>ST = %{x:.3f} ± %{error_x.array:.3f}<extra></extra>',
  };
  Plotly.react(divId, [traceST, traceS1], {
    paper_bgcolor: '#14161a', plot_bgcolor: '#14161a',
    font: { color: '#9ea2a8', family: 'Inter, sans-serif', size: 10 },
    margin: { l: 170, r: 24, t: 8, b: 36 },
    barmode: 'overlay',
    xaxis: { title: 'variance share', gridcolor: '#23262b', zerolinecolor: '#2a2d33', range: [0, Math.max(1.0, Math.max(...st) + 0.05)] },
    yaxis: { gridcolor: '#23262b', automargin: true },
    showlegend: true,
    legend: { orientation: 'h', y: 1.15, font: { size: 9 } },
  }, { displayModeBar: false, responsive: true });
  return true;
}

function renderSobol() {
  let any = false;
  any = _sobolBarFigure(SOBOL_ALPHA, 'log_exo_baroque_index', 'sobol-alpha-ebi') || any;
  any = _sobolBarFigure(SOBOL_ALPHA, 'real_per_capita_welfare', 'sobol-alpha-welfare') || any;
  any = _sobolBarFigure(SOBOL_ALPHA, 'gini_wealth_change_abs', 'sobol-alpha-gini') || any;
  any = _sobolBarFigure(SOBOL_ALPHA, 'productive_welfare_yield', 'sobol-alpha-prod') || any;
  any = _sobolBarFigure(SOBOL_EXO, 'exo_circulation_index', 'sobol-exo-circ') || any;
  any = _sobolBarFigure(SOBOL_EXO, 'imperial_extraction_share', 'sobol-exo-extraction') || any;

  const note = document.getElementById('sobol-note');
  if (any) {
    const a = SOBOL_ALPHA ? `α-engine: ${SOBOL_ALPHA.n_simulations} sims (${SOBOL_ALPHA.n_base_samples} Saltelli base × ${SOBOL_ALPHA.problem.num_vars + 2})` : 'α-engine: not run';
    const e = SOBOL_EXO ? `exo-engine: ${SOBOL_EXO.n_simulations} sims (${SOBOL_EXO.n_base_samples} Saltelli base × ${SOBOL_EXO.problem.num_vars + 2})` : 'exo-engine: not run';
    note.innerHTML = `<b>Run scope:</b> ${a}; ${e}. Parameter bounds are listed in the sweep JSON. ` +
      'A parameter dominating S1 means its independent variance accounts for most of the output variance ' +
      'within the bounds we swept; outside those bounds the indices may differ.';
  } else {
    note.innerHTML =
      'No Sobol indices found. Run <code>agentworld sobol</code> and <code>agentworld exo sobol</code> ' +
      'to populate the four panels above.';
  }
}

// boot
renderAtlas();
renderConvergenceStability();
renderStrip(ORDER[0]);
loadDetail(ORDER[0]);
renderCompareBar();
renderCompare();
renderPhaseSpace();
renderSobol();
renderProvenance();
</script>
</body>
</html>
"""


def main():
    here = Path(__file__).resolve().parents[1]
    runs_dir = here / "outputs" / "runs"
    sensitivity_path = here / "outputs" / "sensitivity" / "phase_space.json"
    ensembles_dir = here / "outputs" / "ensembles"
    sobol_alpha_path = here / "outputs" / "sensitivity" / "sobol_indices.json"
    sobol_exo_path = here / "outputs" / "sensitivity" / "exo_sobol_indices.json"
    out = here / "dashboard" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)

    runs = _load_runs(runs_dir)
    if not runs:
        raise SystemExit("No run outputs found in outputs/runs – run scenarios first.")
    ensembles = _load_ensembles(ensembles_dir)
    sobol_alpha = _load_sobol(sobol_alpha_path)
    sobol_exo = _load_sobol(sobol_exo_path)
    sensitivity = _load_sensitivity(sensitivity_path)
    convergence_stability = _load_convergence_stability(here / "outputs")

    html = build_html(
        runs,
        sensitivity=sensitivity,
        ensembles=ensembles,
        sobol_alpha=sobol_alpha,
        sobol_exo=sobol_exo,
        convergence_stability=convergence_stability,
    )
    out.write_text(html)
    print(
        f"dashboard written: {out}  ({out.stat().st_size:,} bytes, "
        f"{len(runs)} scenarios, {len(ensembles)} ensembles, "
        f"sobol_alpha={'yes' if sobol_alpha else 'no'}, "
        f"sobol_exo={'yes' if sobol_exo else 'no'}, "
        f"cs_flags={len(convergence_stability)})"
    )


if __name__ == "__main__":
    main()
