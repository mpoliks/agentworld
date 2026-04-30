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

The §0 panel reads `docs/concepts/epistemic_status.md` for provenance and
a calibrated/stipulated/speculative summary so the reader sees the rules
of the artifact at the top of the page.
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.scenarios import SCENARIO_DESCRIPTIONS

SCENARIO_ORDER = [
    "coasean_paradise",
    "universal_advocate",
    "public_defender",
    "smoothing_cascade",
    "equilibrium_drift",
    "compute_famine",
    "hemispherical_schism",
    "matryoshka_collapse",
    "nimby_cascade",
    "synthetic_consumers",
    "recursive_simulation",
    "fold_avalanche",
    "slop_market",
    "baroque_cathedral",
    "exo_baroque_singularity",
    "coasean_paradise_networked",
    "baroque_cathedral_networked",
]

SCENARIO_LABELS = {
    "coasean_paradise": "Coasean Paradise",
    "universal_advocate": "Universal Advocate",
    "public_defender": "Public Defender",
    "smoothing_cascade": "Smoothing Cascade",
    "equilibrium_drift": "Equilibrium Drift",
    "compute_famine": "Compute Famine",
    "hemispherical_schism": "Hemispherical Schism",
    "matryoshka_collapse": "Matryoshka Collapse",
    "nimby_cascade": "NIMBY Cascade",
    "synthetic_consumers": "Synthetic Consumers",
    "recursive_simulation": "Recursive Simulation",
    "fold_avalanche": "Fold Avalanche",
    "slop_market": "Slop Market",
    "baroque_cathedral": "Baroque Cathedral",
    "exo_baroque_singularity": "Exo-Baroque Singularity",
    "coasean_paradise_networked": "Coasean Paradise (Networked)",
    "baroque_cathedral_networked": "Baroque Cathedral (Networked)",
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


def build_html(
    runs: dict,
    sensitivity: dict | None = None,
    ensembles: dict | None = None,
    sobol_alpha: dict | None = None,
    sobol_exo: dict | None = None,
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
    }
    payload_json = json.dumps(payload)

    html = HTML_TEMPLATE.replace("__PAYLOAD__", payload_json)
    return html


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Agentworld – A computational atlas of the smooth-striated continuum</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<meta name="googlebot" content="noindex, nofollow">
<meta name="referrer" content="no-referrer-when-downgrade">
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
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
.scn-card .alpha { font-family: var(--mono); font-size: 11px; color: var(--text-3); display: flex; gap: 12px; }
.scn-card .alpha b { color: var(--accent); font-weight: 500; }
.scn-card .desc { font-size: 12px; color: var(--text-2); line-height: 1.4; }

.detail-pane { display: grid; grid-template-columns: 280px 1fr; gap: 24px; align-items: start; }
@media (max-width: 900px) { .detail-pane { grid-template-columns: 1fr; } }

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
}
</style>
</head>
<body>

<header>
  <div class="wrap">
    <div class="super">Antikythera × Disintegrator · companion artifact</div>
    <h1>Agentworld<br><em>An atlas of the smooth-striated continuum</em></h1>
    <p class="lead">A computational sandbox for the planetary economy when society is composed of <b>8 billion humans</b> and <b>800 billion to 1 trillion AI agents</b>. We look at one variable through fifteen scenarios that range from agents <em>dissolving</em> economic intermediation (e.g. removing transaction barriers) or <em>fractally multiplying</em> it (introducing new, recursive transaction barriers)? Both are stable equilibria of the same underlying technology, and which one materializes is an open question. What we offer here is a few distributions of possible scenarios.</p>
    <div class="meta">
      <span>15 scenarios</span>
      <span>8 × 10⁹ humans + 8 × 10¹¹ agents · 6.6M importance-weighted prototypes</span>
      <span>60 steps · 20M pair-interactions per step</span>
    </div>
  </div>
</header>

<section style="border-bottom: 1px solid var(--border);">
  <div class="wrap">
    <h2><span class="marker">§0</span> Epistemic status · what these numbers are and aren't</h2>
    <p class="sub">Before any chart, the rules of the game. This artifact is a stochastic-dynamic <i>thought instrument</i>, not a forecast. Some of its building blocks are calibrated to public empirical data; the load-bearing speculative parameters are deliberately not. The full taxonomy lives in <a href="https://github.com" target="_blank" rel="noopener">docs/concepts/epistemic_status.md</a>; below is the short version. Use the dashboard to read <i>conditional</i> patterns ("EBI explodes whenever α &gt; X and fold-real-efficiency &lt; Y"), not unconditional probabilities.</p>
    <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px;">
      <div class="panel" style="border-left: 3px solid var(--green);">
        <h3 style="margin-top:0;font-family:var(--serif);font-weight:400;">Calibrated structure</h3>
        <p style="font-family:var(--serif);font-size:13px;line-height:1.55;color:var(--text-2);">Heavy-tail kurtosis (Cont 2001), BEA 2022 sectoral co-movement, World Bank regional growth correlations, Atalay 2011 production-network degree, Bacry/Muzy 2015 cascade branching ratios. These shape the <i>noise structure</i>, not the macro outputs. Updating the source data should update these numbers.</p>
      </div>
      <div class="panel" style="border-left: 3px solid var(--accent);">
        <h3 style="margin-top:0;font-family:var(--serif);font-weight:400;">Stipulated parameters</h3>
        <p style="font-family:var(--serif);font-size:13px;line-height:1.55;color:var(--text-2);">Capability distributions, sector concentration, friction floor, market/individual taxes, region size distributions. Bounds chosen for face validity, swept in §7 to show conditional sensitivity. We sweep <i>within</i> these bounds; we do not claim the bounds themselves are calibrated.</p>
      </div>
      <div class="panel" style="border-left: 3px solid var(--red);">
        <h3 style="margin-top:0;font-family:var(--serif);font-weight:400;">Speculative load-bearers</h3>
        <p style="font-family:var(--serif);font-size:13px;line-height:1.55;color:var(--text-2);">Folding propensity, fold-real efficiency, lift propensity, suppression cost exponent, drag intensity. These are the parameters that make the model interesting <i>and</i> the parameters with no historical analog at the 800B-agent scale. Permanently un-fitted to past macro data; reported as conditional dependencies, not as estimates.</p>
      </div>
      <div class="panel">
        <h3 style="margin-top:0;font-family:var(--serif);font-weight:400;">Bands and seeds</h3>
        <p style="font-family:var(--serif);font-size:13px;line-height:1.55;color:var(--text-2);">Where ensembles are present, plots show median + 5/95 percentile bands across N seeds. The band is over <i>noise realizations within a fixed parameterization</i>, not a posterior over the world. A band of [22, 81] on EBI is "this artifact's behavior under these parameters can land anywhere in 22-81," not "EBI is 50/50 to be above 47."</p>
      </div>
      <div class="panel">
        <h3 style="margin-top:0;font-family:var(--serif);font-weight:400;">Two engines on purpose</h3>
        <p style="font-family:var(--serif);font-size:13px;line-height:1.55;color:var(--text-2);">The α-engine (this dashboard's main subject) treats EBI = nominal/real as the diagnostic. The exo-engine refuses that frame and tracks lift / drag / last-mile / differential operators. Both are reported. Their disagreement is part of the deliverable. Any "calibration" that converged them onto a single estimated trajectory destroys what is interesting about the artifact.</p>
      </div>
      <div class="panel">
        <h3 style="margin-top:0;font-family:var(--serif);font-weight:400;">What §7 (Sobol) tells you</h3>
        <p style="font-family:var(--serif);font-size:13px;line-height:1.55;color:var(--text-2);">First-order (S1) and total-order (ST) global sensitivity indices. Within the stipulated bounds, S1 is the share of output variance the parameter explains alone; ST includes interactions. Parameters where both are near zero are cosmetic. The indices do <i>not</i> say which parameter is "most likely" to take any value.</p>
      </div>
    </div>
    <div id="provenance-panel" style="margin-top:24px;"></div>
  </div>
</section>

<section>
  <div class="wrap">
    <h2><span class="marker">§1</span> Reader's primer · what every variable means</h2>
    <p class="sub">Read this first, because every chart downstream uses these terms. Units, axes, and reference lines are defined here for §2–§6.</p>
    <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(300px,1fr)); gap: 16px;">

      <div class="panel">
        <h3 style="margin-top:0;font-family:var(--serif);font-weight:400;">α – the control variable</h3>
        <p style="font-family:var(--serif);font-size:14px;line-height:1.55;color:var(--text-2);">A single number on [0, 1] that interpolates between two <b>limit regimes</b> from zero economic mediation (a totally smooth market) to an infinitely complex market. A <i>limit regime</i> is the qualitatively distinct behavior the system collapses to at an extreme value of α: <b>α = 0</b> is the <i>Smooth</i> limit (next panel) and <b>α = 1</b> is the <i>Striated</i> limit (panel after that). Real economies live in the interior of [0, 1] and are usually a sectoral mix of both. Every other quantity in this dashboard is causally downstream of α (sometimes set by a schedule, sometimes responding to the run via feedback). The atlas places each scenario at <i>its</i> terminal α; the §4 detail pane shows α moving over time.</p>
      </div>

      <div class="panel" style="border-left: 3px solid var(--green);">
        <h3 style="margin-top:0;font-family:var(--serif);font-weight:400;">Smooth · α → 0 · Krier limit</h3>
        <p style="font-family:var(--serif);font-size:14px;line-height:1.55;color:var(--text-2);">Near-zero transaction cost and continuous bilateral negotiation between agents. No recursive intermediation – every trade is one trade, not a tower of derivative trades. The state collapses to a contract guarantor; markets are direct exchanges between buyer and seller. Nominal GDP and real welfare stay in lockstep: every measured dollar of economic activity ends up as something a human consumed. <i>Coasean Paradise</i> is the ideal scenario and <i>Universal Advocate</i> is the equity-corrected version, both borrowed from Seb Krier's work.</p>
      </div>

      <div class="panel" style="border-left: 3px solid var(--red);">
        <h3 style="margin-top:0;font-family:var(--serif);font-weight:400;">Striated · α → 1 · Bratton limit</h3>
        <p style="font-family:var(--serif);font-size:14px;line-height:1.55;color:var(--text-2);">Recursive intermediation everywhere. Every transaction passes through Matryoshka layers (see below) and any transaction with positive expected surplus may spawn sub-markets that price derived rights, derived attention, or derived metadata. Each new tier adds nominal accounting volume and consumes some of the underlying surplus as friction. Nominal GDP detaches from real welfare by orders of magnitude. <i>Baroque Cathedral</i>, <i>Slop Market</i>, and <i>Exo-Baroque Singularity</i> are the canonical instances.</p>
      </div>

      <div class="panel">
        <h3 style="margin-top:0;font-family:var(--serif);font-weight:400;">Real welfare · per-capita welfare</h3>
        <p style="font-family:var(--serif);font-size:14px;line-height:1.55;color:var(--text-2);"><b>Real welfare</b> is the surplus that ended up in human hands at last-mile consumption, summed across the run. <b>Per-capita welfare</b> divides cumulative real welfare by 8 × 10⁹ humans. <b>Units are stylized – not dollars</b>, because raw values across 8 billion humans land in the 5 × 10⁻⁵ to 5 × 10⁻⁴ range, which is unreadable at four decimal places. Every number on the dashboard is therefore <b>multiplied by 10⁶ for display</b> so that Coasean Paradise reads as ≈ 513 and Slop Market as ≈ 57. Read the <i>ratios</i>, not the absolute numbers – Coasean Paradise produces roughly 9× more welfare per human than Slop Market, for example.</p>
      </div>

      <div class="panel">
        <h3 style="margin-top:0;font-family:var(--serif);font-weight:400;">Nominal GDP</h3>
        <p style="font-family:var(--serif);font-size:14px;line-height:1.55;color:var(--text-2);">Total measured economic activity, summed across the run, in the same stylized unit as real welfare. Includes both real surplus and the layered accounting volume produced by folding. In a smooth regime nominal ≈ real; in a striated regime nominal can exceed real by a factor of 10⁶ or more.</p>
      </div>

      <div class="panel" style="border-left: 3px solid var(--accent);">
        <h3 style="margin-top:0;font-family:var(--serif);font-weight:400;">EBI – exo-baroque index</h3>
        <p style="font-family:var(--serif);font-size:14px;line-height:1.55;color:var(--text-2);">Nominal GDP ÷ real welfare. The single clearest measure of how much of <i>the economy</i> has folded out of human consumption. <b>EBI = 1</b> is the parity regime (Smoothworld). Anything sustained above 1 is GDP that the human side never received – accounting that lives only in agent-to-agent ledgers.</p>
      </div>

      <div class="panel">
        <h3 style="margin-top:0;font-family:var(--serif);font-weight:400;">Folding · fold depth</h3>
        <p style="font-family:var(--serif);font-size:14px;line-height:1.55;color:var(--text-2);">When a transaction has positive expected surplus, agents may spawn sub-markets that trade in derived rights, derived attention, derived metadata. Each tier is one fold. <b>Fold depth</b> is the height of the tallest such tower observed in any single transaction this step. Smooth regimes hold this at zero; striated regimes climb to integers in the single or low double digits. The exo-engine renames folding <i>lift</i> – the basic operating logic of capital, not a parameter setting.</p>
      </div>

      <div class="panel">
        <h3 style="margin-top:0;font-family:var(--serif);font-weight:400;">Matryoshka layers (after Krier)</h3>
        <p style="font-family:var(--serif);font-size:14px;line-height:1.55;color:var(--text-2);">Every attempted transaction passes through three nested filters before it can clear: <b>law</b> (binary statutory veto), <b>market / platform</b> (probabilistic fee-or-rules filter), and <b>individual alignment</b> (continuous person-level objection). A trade that fails any layer is a rejection. The §4 rejection chart shows which layer is the binding constraint in each regime.</p>
      </div>

      <div class="panel">
        <h3 style="margin-top:0;font-family:var(--serif);font-weight:400;">Human legibility index</h3>
        <p style="font-family:var(--serif);font-size:14px;line-height:1.55;color:var(--text-2);">1 ÷ EBI, capped at 1. The share of nominal economic activity a human could in principle audit at last-mile resolution. 1.0 means the market is fully readable from the outside; values near 0 mean the market is legible only to itself.</p>
      </div>

      <div class="panel">
        <h3 style="margin-top:0;font-family:var(--serif);font-weight:400;">Wealth Gini</h3>
        <p style="font-family:var(--serif);font-size:14px;line-height:1.55;color:var(--text-2);">Standard 0–1 Gini over the joint human + agent wealth distribution at the terminal step. Reported in §4 alongside per-capita welfare so that <i>welfare</i> and <i>distribution of welfare</i> can be read together. <i>Public Defender</i> is a specific example where this variable is compressed.</p>
      </div>

      <div class="panel">
        <h3 style="margin-top:0;font-family:var(--serif);font-weight:400;">Interaction shares · A2A / H2A / H2H</h3>
        <p style="font-family:var(--serif);font-size:14px;line-height:1.55;color:var(--text-2);">Three counters per scenario: <b>A2A</b> agent-to-agent, <b>H2A</b> human-to-agent, <b>H2H</b> human-to-human. Above the smooth limit, A2A dominates by two or three orders of magnitude – the population that produces nearly all transactions is also the population that consumes them. Reported in the §4 detail pane.</p>
      </div>

      <div class="panel">
        <h3 style="margin-top:0;font-family:var(--serif);font-weight:400;">Population</h3>
        <p style="font-family:var(--serif);font-size:14px;line-height:1.55;color:var(--text-2);">~10⁵ prototypes, importance-weighted to 8 × 10⁹ humans and 8 × 10¹¹ agents (a 100:1 agent-to-human ratio). Each prototype carries (capability, sector, hemispherical stack, alignment, autonomy, wealth). Sample size makes the run tractable; weights make the totals correct at planetary scale.</p>
      </div>

    </div>
  </div>
</section>

<section>
  <div class="wrap">
    <h2><span class="marker">§2</span> The atlas</h2>
    <p class="sub">Each point is one scenario at its terminal step. The <b>x-axis</b> is α, the smooth-striated control variable on [0, 1]. The <b>y-axis</b> is the <i>exo-baroque index</i> (EBI) – nominal GDP divided by real welfare, log-scaled. <b>Color</b> encodes per-capita real welfare; greener is better. The dashed line at EBI = 1 is the parity regime: every measured dollar of GDP matches a dollar of human welfare. Anything sustained above that line is GDP that the human side of the economy never receives – accounting that has folded out of last-mile consumption.</p>
    <p class="sub"><b>What to read off the chart.</b> Bottom-left: low α, no folding, accounting tracks welfare. Top-right: high α, recursive folding, accounting separates from welfare by orders of magnitude. A point that sits high on the y-axis <i>and</i> dim in color is the brief's failure case – a regime printing volume without producing anything humans consume. Every point is hover-only; identifying the cluster scenarios by name needs a mouse-over, which keeps the plotting region uncluttered and the y-axis range honest.</p>
    <div class="atlas-grid">
      <div class="chart-box">
        <div class="chart-title">α × exo-baroque index · color = per-capita welfare</div>
        <div class="chart-caption"><b>Dashed horizontal:</b> EBI = 1 – the parity line where welfare equals nominal GDP. <b>Color</b> is per-capita welfare scaled by 10⁶ (model state is unchanged; the scaling exists so values like Coasean Paradise ≈ 513 and Slop Market ≈ 57 are legible at a glance instead of collapsing into "0.0005" and "0.0001"). Hover any point for the scenario label, exact α, EBI, and welfare.</div>
        <div id="atlas" style="height:520px;"></div>
      </div>
      <div class="callout">
        <p style="margin: 0 0 14px;">
          Bratton's hypothesis is that the right-hand limit – <b>Baroqueworld</b> – is at least as plausible as the Krier limit on the left, and that this is where the on-paper GDP gains will come from. Krier's <i>Coasean Paradise</i> sits in the bottom-left. Bratton's <i>Exo-Baroque Singularity</i> sits in the top-right. The economies of the late 2030s are a weighted blend of the two, varying by sector, jurisdiction, and stack. <em>The atlas does not predict where any given regime lands. It clarifies what landing somewhere costs.</em>
        </p>
        <p style="margin: 0 0 14px;">
          <b>What the atlas does not show.</b> These terminal-step snapshots basically compress fifteen trajectories into fifteen dots. Two scenarios can land at the same coordinate by very different routes – a slow drift through the mid-α basin reads identically to a fast climb that overshoots and falls back. §4 unfolds each path as a six-chart panel; §5 stacks any subset of paths on a shared time axis so the route, not just the destination, becomes clear.
        </p>
        <p style="margin: 0;">
          <b>What this means for decisions.</b> There are five main points here based on this simulation. <b>(1)</b> The thing that really moves regimes is α – protocol striation – not capability. Smarter agents raise welfare <i>inside</i> a basin without moving a population across a basin boundary, so a "smarter agents" policy with no α policy still ends in Baroqueworld if α was high. <b>(2)</b> High nominal GDP is not a win condition. Above EBI = 1, the marginal dollar is accounting that the human side never received, so the decision-relevant metric is per-capita real welfare and the diagnostic-relevant metric is EBI itself. Optimizing for nominal GDP under high α funds the Slop Market. <b>(3)</b> The mid-α basin is the default attractor – without active mechanism design, a population drifts toward striation rather than toward the smooth corner. Landing in the bottom-left is a deliberate act, sustained by concrete choices about platform fees, fold ceilings, alignment-layer veto rights, and the friction floor. <b>(4)</b> Smoothworld is not a free lunch. It requires near-zero transaction cost <i>and</i> contract enforcement that scales to 8 × 10⁹ humans plus 8 × 10¹¹ agents – a heavier institutional ask than its "shrunken state" framing suggests. <b>(5)</b> Two scenarios at the same atlas coordinate are not the same policy. <i>Recursive Simulation</i> and <i>Baroque Cathedral</i> can both end at high α and high EBI, but one got there via positive-feedback drift (no one chose it) and the other via deliberate construction. Use §4 and §5 to see the specific routes taken.
        </p>
      </div>
    </div>
  </div>
</section>

<section>
  <div class="wrap">
    <h2><span class="marker">§3</span> The scenarios</h2>
    <p class="sub">Click a card to load its detail pane below. Cards are ordered along α – <i>Coasean Paradise</i> on the far left, <i>Exo-Baroque Singularity</i> on the far right. Each card prints the scenario's terminal α, exo-baroque index, and per-capita welfare. The fifteen scenarios fix different levers – alignment-layer rejection rate, agent autonomy, friction floor, capability variance, fold ceiling, the rate at which α responds to its own EBI – so that the rest of the system can be read as a response to that lever.</p>
    <div class="scenario-strip" id="scn-strip"></div>
  </div>
</section>

<section>
  <div class="wrap">
    <h2><span class="marker">§4</span> Scenario detail · <span id="active-name" style="color:var(--accent);"></span></h2>
    <p class="sub" id="active-desc"></p>
    <p class="sub" id="ensemble-status" style="color:var(--text-3); font-size:13px;"></p>
    <div class="detail-pane">
      <div class="detail-meta" id="active-meta"></div>
      <div>
        <div class="charts-grid">
          <div class="chart-box">
            <div class="chart-title">α (smooth ↔ striated) over time</div>
            <div class="chart-caption">The control schedule. A flat line means α was held constant; a ramp or decay means α was scheduled to move; a jagged trace means α responded to the run itself – <i>Recursive Simulation</i> is the canonical example, where α climbs whenever EBI climbs.</div>
            <div id="d-alpha" style="height:240px;"></div>
          </div>
          <div class="chart-box">
            <div class="chart-title">cumulative real welfare vs nominal GDP</div>
            <div class="chart-caption">Two cumulative curves on a log y-axis. They start together. The vertical gap between them <i>is</i> the exo-baroque index – the wider it opens, the more measured economic activity has folded into accounting that no human ever consumes.</div>
            <div id="d-realnom" style="height:240px;"></div>
          </div>
          <div class="chart-box">
            <div class="chart-title">exo-baroque index over time (log scale)</div>
            <div class="chart-caption">The same gap, expressed as a single ratio. The dashed reference at EBI = 1 is the parity line. Anything sustained above it is GDP that the human side of the economy did not receive – folded surplus that exists only in agent-to-agent ledgers.</div>
            <div id="d-ebi" style="height:240px;"></div>
          </div>
          <div class="chart-box">
            <div class="chart-title">max fold depth this step</div>
            <div class="chart-caption">The tallest tower of recursive sub-markets observed in any single transaction this step. Step shape because depth is integer-valued. A flat zero means the scenario refuses to fold; a staircase climb is folding take-off – each new tier reflects the pricing of a derived right, derived attention, or derived metadata.</div>
            <div id="d-fold" style="height:240px;"></div>
          </div>
          <div class="chart-box">
            <div class="chart-title">per-capita welfare · ×10⁶ stylized units</div>
            <div class="chart-caption">Real welfare divided across 8 × 10⁹ humans, step by step. The actual material outcome on the human side. Multiplied by 10⁶ for legibility – these are not dollars. Coasean Paradise tops out near 500; Slop Market near 60. Use this trace to compare scenarios on welfare alone, with α and EBI deliberately set aside.</div>
            <div id="d-pc" style="height:240px;"></div>
          </div>
          <div class="chart-box">
            <div class="chart-title">rejection share by Matryoshka layer</div>
            <div class="chart-caption">Of the trades that did not clear, which Matryoshka layer killed them. <span style="color:#c25a5a;">law</span> = a binary statutory veto. <span style="color:#5b8ec4;">market</span> = a probabilistic platform / fee filter. <span style="color:#5fa572;">alignment</span> = an individual-level objection. <span style="color:#b89a55;">cost</span> = the friction floor. The dominant color names the binding constraint at each step.</div>
            <div id="d-rej" style="height:240px;"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>

<section>
  <div class="wrap">
    <h2><span class="marker">§5</span> Compare scenarios</h2>
    <p class="sub">Pick any subset of scenarios and overlay them on a shared time axis. Useful for the question: <i>what do the Slop Market and the Baroque Cathedral share, and where do they diverge?</i> Both end at high α; only one converts that α into welfare. Stacking the EBI and per-capita-welfare curves makes the divergence step visible.</p>
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
        <div class="chart-title">per-capita welfare · ×10⁶ stylized units</div>
        <div class="chart-caption">What households actually got at each step. Shape distinguishes cumulative growth from stagnation; height ranks the selected scenarios on welfare alone, regardless of how much GDP each printed. Y-axis is scaled by 10⁶ for legibility – model state is identical to the §1 definition.</div>
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
    <h2><span class="marker">§6</span> Phase-space sweep</h2>
    <p class="sub">The sweeps provide a regular grid across α (x-axis) and agent capability (y-axis), with each cell classified into one of five basins: <i>smooth</i>, <i>mixed</i>, <i>striated</i>, <i>baroque</i>, <i>slop</i>. Cell color encodes log₁₀(EBI).</p>
    <p class="sub"><b>How to read the grid.</b> Walk any row from left-to-right and watch the glyph change – that change is a basin transition, and the α column where it happens is the tipping point for that level of capability. Then climb a column instead: the glyph holds. Capability raises welfare <i>inside</i> a basin without moving it across a boundary. The full population can be made wildly more capable and still sit in the same regime.</p>
    <div class="detail-pane">
      <div class="detail-meta" id="phase-meta"></div>
      <div class="chart-box"><div class="chart-title">α × capability basin map · color = log₁₀(EBI) · glyph = basin</div><div id="phase-map" style="height:460px;"></div></div>
    </div>
    <div class="callout" id="phase-note"></div>
  </div>
</section>

<section>
  <div class="wrap">
    <h2><span class="marker">§7</span> Global sensitivity · which knobs actually move what</h2>
    <p class="sub">Saltelli/Sobol decomposition. <b>S1</b> is the share of output variance the parameter explains on its own; <b>ST</b> includes interactions with the other parameters. A bar where <b>ST &gt;&gt; S1</b> means the parameter mostly matters through interactions. Parameters where both are near zero are cosmetic <i>within the stipulated bounds</i> (see §0). Bounds for each parameter are listed alongside the chart, because the indices are conditional on them — they tell you the variance structure inside the explored space, not outside it.</p>
    <div class="charts-grid" style="grid-template-columns: 1fr 1fr;">
      <div class="chart-box">
        <div class="chart-title">α-engine · Sobol indices for terminal EBI</div>
        <div class="chart-caption">First-order S1 (filled) and total-order ST (outlined) for terminal exo-baroque index. Tall S1 + short ST gap = the parameter acts independently. Tall ST with low S1 = the parameter only matters through interactions with others.</div>
        <div id="sobol-alpha-ebi" style="height:340px;"></div>
      </div>
      <div class="chart-box">
        <div class="chart-title">α-engine · Sobol indices for terminal welfare</div>
        <div class="chart-caption">Same decomposition, target = real per-capita welfare. Compare to the EBI panel: knobs that dominate EBI may not dominate welfare, and vice versa.</div>
        <div id="sobol-alpha-welfare" style="height:340px;"></div>
      </div>
      <div class="chart-box">
        <div class="chart-title">exo-engine · Sobol indices for circulation index</div>
        <div class="chart-caption">Same decomposition for the exo-engine target (exo_circulation_index). The exo-engine refuses EBI as a load-bearing diagnostic; this chart says which exo-side knobs move the exo-side diagnostic.</div>
        <div id="sobol-exo-circ" style="height:340px;"></div>
      </div>
      <div class="chart-box">
        <div class="chart-title">exo-engine · Sobol indices for imperial extraction share</div>
        <div class="chart-caption">Sensitivity of the imperial extraction-share metric. Useful for the question "is the extraction rate parameter the only thing that controls extraction share?" (Spoiler: it usually is, and that is itself a useful sanity check on the engine.)</div>
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
// Real per-capita welfare lives in ~5.7e-5 to ~5.1e-4 (stylized units divided
// across 8e9 humans). At that magnitude .toFixed(4) collapses the whole range
// into "0.0001" or "0.0005" and cross-scenario ranking is invisible. Scale
// by 10^6 for display only – model state is unchanged. Coasean Paradise reads
// as ~513, Slop Market as ~57. Apply consistently everywhere welfare appears.
const WELFARE_SCALE = 1e6;
const WELFARE_LABEL_LONG  = 'welfare per capita · ×10⁶ stylized units';
const WELFARE_LABEL_SHORT = 'w/cap (×10⁶)';
const fmtW = (v) => (v * WELFARE_SCALE).toFixed(1);

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
        title: { text: 'welfare per capita · ×10⁶', font: { color: '#9ea2a8', size: 10 } },
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
      <div class="alpha"><span>α=<b>${s.final_alpha.toFixed(2)}</b></span><span>EBI=<b>${ebi < 100 ? ebi.toFixed(2) : ebi.toExponential(1)}</b></span><span>${WELFARE_LABEL_SHORT}=<b>${fmtW(pc)}</b></span></div>
      <div class="desc">${s.description}</div>`;
    card.addEventListener('click', () => loadDetail(name));
    el.appendChild(card);
  });
}

// ---------- ensemble band helpers ----------
// When `outputs/ensembles/{name}.bands.json` is present, the per-scenario
// charts overlay the ensemble's median + 5/95 percentile band. The single
// run still plots on top so the original look is preserved; the band is a
// translucent envelope behind it. The §0 epistemic-status panel explains
// what these bands mean (and don't).
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
      'dotted line is the ensemble median. See §0 for what bands mean and don\'t.';
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
    <div class="stat"><div class="label">Per-capita real welfare</div><div class="value">${fmtW(last(h.real_per_capita_welfare))}</div><div class="sub">cumulative · ×10⁶ stylized units</div></div>
    <div class="stat"><div class="label">Wealth Gini</div><div class="value">${last(h.gini_wealth).toFixed(3)}</div></div>
    <div class="stat"><div class="label">Max fold depth reached</div><div class="value">${Math.max(...h.fold_max_depth)}</div></div>
    <div class="stat"><div class="label">A2A interaction share</div><div class="value">${(last(h.a2a_share) * 100).toFixed(1)}%</div><div class="sub">vs H2A: ${(last(h.h2a_share) * 100).toFixed(2)}% · H2H: ${(last(h.h2h_share) * 100).toFixed(3)}%</div></div>
    <div class="stat"><div class="label">Governance overhead</div><div class="value">${(last(h.governance_overhead_fraction) * 100).toFixed(1)}%</div><div class="sub">trades killed in Matryoshka layers</div></div>
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
    [{ x: h.step, y: h.fold_max_depth, mode: 'lines', line: { color: '#5b8ec4', width: 2, shape: 'hv' } }],
    baseLayout, { displayModeBar: false, responsive: true });

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
  if (!SENS || !SENS.points || SENS.points.length === 0) {
    document.getElementById('phase-note').textContent =
      'No phase-space sweep found. Run agentworld sweep to generate outputs/sensitivity/phase_space.json.';
    return;
  }
  const pts = SENS.points;
  const counts = {};
  pts.forEach(p => { counts[p.basin] = (counts[p.basin] || 0) + 1; });
  const order = ['smooth', 'mixed', 'striated', 'baroque', 'slop'];

  const meta = document.getElementById('phase-meta');
  meta.innerHTML = `
    <div class="stat"><div class="label">Grid points</div><div class="value tinted">${pts.length}</div>
      <div class="sub">${SENS.alpha_values.length} α values × ${SENS.capability_values.length} capability values</div></div>
    ${order.map(k => `
      <div class="stat" style="border-left:3px solid ${BASIN_COLOR[k]};">
        <div class="label">${k} basin <span style="color:${BASIN_COLOR[k]};font-family:var(--mono);">${BASIN_GLYPH[k]}</span></div>
        <div class="value">${counts[k] || 0}</div>
      </div>`).join('')}
  `;

  const alphas = SENS.alpha_values;
  const caps   = SENS.capability_values;
  const idx = (a, c) => pts.find(p => p.alpha === a && p.agent_capability_mean === c);

  // z[j][i] indexed [capability_row][alpha_col] for Plotly heatmap.
  const z = caps.map(c => alphas.map(a => {
    const p = idx(a, c);
    return p ? Math.log10(Math.max(p.ebi, 1)) : null;
  }));
  const hover = caps.map(c => alphas.map(a => {
    const p = idx(a, c);
    if (!p) return '';
    return `basin: <b>${p.basin}</b><br>α=${p.alpha} · cap=${p.agent_capability_mean}<br>` +
           `EBI=${p.ebi < 100 ? p.ebi.toFixed(2) : p.ebi.toExponential(1)}<br>` +
           `${WELFARE_LABEL_SHORT}=${fmtW(p.real_per_capita_welfare)}<br>` +
           `legibility=${p.human_legibility_index.toFixed(3)}`;
  }));
  const basinGlyph = caps.map(c => alphas.map(a => {
    const p = idx(a, c);
    return p ? BASIN_GLYPH[p.basin] : '';
  }));

  const heatmap = {
    type: 'heatmap',
    x: alphas, y: caps, z,
    text: hover, hoverinfo: 'text',
    colorscale: [[0, '#2c4633'], [0.25, '#5fa572'], [0.5, '#b89a55'],
                 [0.75, '#c25a5a'], [1, '#7a4f9c']],
    colorbar: {
      title: { text: 'log₁₀(EBI)', font: { color: '#9ea2a8', size: 11 } },
      tickfont: { color: '#6a6d72', size: 10 },
      thickness: 12, len: 0.85,
    },
    xgap: 2, ygap: 2,
  };

  // Basin glyph overlay – one annotation per cell, very small.
  const annotations = [];
  caps.forEach((c, j) => alphas.forEach((a, i) => {
    if (basinGlyph[j][i]) {
      annotations.push({
        x: a, y: c, xref: 'x', yref: 'y',
        text: basinGlyph[j][i], showarrow: false,
        font: { color: '#e7e8ea', size: 14, family: 'JetBrains Mono, monospace' },
      });
    }
  }));

  Plotly.newPlot('phase-map', [heatmap], {
    paper_bgcolor: '#14161a', plot_bgcolor: '#14161a',
    font: { color: '#9ea2a8', family: 'Inter, sans-serif' },
    xaxis: { title: 'α (smooth → striated)', gridcolor: '#2a2d33', zerolinecolor: '#2a2d33',
             tickmode: 'array', tickvals: alphas, tickformat: '.2f' },
    yaxis: { title: 'agent capability mean', gridcolor: '#2a2d33', zerolinecolor: '#2a2d33',
             tickmode: 'array', tickvals: caps, tickformat: '.2f' },
    margin: { l: 80, r: 30, t: 20, b: 60 },
    annotations,
  }, { displayModeBar: false, responsive: true });

  document.getElementById('phase-note').innerHTML =
    'The boundary that matters here most is α, not capability. Capability does increase welfare inside ' +
    'a regime, but it does not move a point across a basin line. Whether the same population sits in ' +
    '<i>smooth</i>, <i>mixed</i>, or <i>baroque</i> is instead decided by protocol striation. ' +
    "It's worth noting that the on-paper gains visible at the right edge of the grid are not gains in " +
    'welfare but are gains in the number of priced surfaces.';
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
        not load-bearing dynamics. Re-anchor on source updates and rerun the dashboard.
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
  any = _sobolBarFigure(SOBOL_ALPHA, 'exo_baroque_index', 'sobol-alpha-ebi') || any;
  any = _sobolBarFigure(SOBOL_ALPHA, 'real_per_capita_welfare', 'sobol-alpha-welfare') || any;
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

    html = build_html(
        runs,
        sensitivity=sensitivity,
        ensembles=ensembles,
        sobol_alpha=sobol_alpha,
        sobol_exo=sobol_exo,
    )
    out.write_text(html)
    print(
        f"dashboard written: {out}  ({out.stat().st_size:,} bytes, "
        f"{len(runs)} scenarios, {len(ensembles)} ensembles, "
        f"sobol_alpha={'yes' if sobol_alpha else 'no'}, "
        f"sobol_exo={'yes' if sobol_exo else 'no'})"
    )


if __name__ == "__main__":
    main()
