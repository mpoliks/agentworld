// Spatial-sandbox scene (Pass 13) — tessellated-surface rendering.
//
// The cells-on-a-sphere paradigm is gone. The sphere itself is a
// high-subdivision icosahedron; engine events fill in and fade out
// individual triangles on its surface. All themes are light mode.
//
// Modules: only surface.js renders. agents/bonds/cabals/dust/trails
// from the prior paradigm are no longer wired in.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

import { createSurface } from './surface.js';
import { createAgents } from './agents.js';
import { createEdges } from './edges.js';
import { createFirms } from './firms.js';
import { createFolds } from './folds.js';
import { createClusters } from './clusters.js';
import { createClusterLabels } from './cluster_labels.js';
import { createClusterOverlay } from './cluster_overlay.js';
import { createInspectorAgent } from './inspector_agent.js';
import { OUTCOME_PALETTE } from './edges.js';
// Plan §8.3 — dev/checks runs in-browser invariants when the URL
// carries `?dev=1`. Imported lazily so production loads don't pay
// the parse cost.
let _devChecks = null;
import { loadAlphaWeights, mapAlpha } from './alpha_map.js';
import { predictEbi, CURVE_DOMAIN } from './alpha_ebi_curve.js';
import { startStream } from './stream.js';
import { THEME } from './themes.js';

const LEVERS = {
  scenario: 'spatial_sandbox',
  scale: 'small',
  seed: 24601,
  // 4× scale-up: dashboard requests 20K cast members. Bumped from
  // 5000; corresponding RunRequest pydantic cap also raised in
  // engine/serve.py.
  cast_size: 20000,
  pair_sample_k: 3000,
  // Run indefinitely — the counter should keep climbing while the
  // dashboard is open.
  continuous: true,
};

// Wealth meter splits into two sections so the percentages stay
// honest — stock fractions (humans + ai) sum to 100% by
// construction, per-tick flow rates (matryoshka / legal / recycling)
// are independent rates on their own scale.
// matryoshka: parasitic nominal value-add per tick as a fraction of
// nominal GDP. Sourced from (nominal_step − real_step) / nominal_step
// — not from governance_overhead_fraction, which the engine defines
// as gate-rejection rate (law + market + regulator + align), not
// fold overhead. Alpha moves this number directly because more folds
// = bigger per-tick nominal-real gap.
const FLOW_SEGMENTS = [
  { key: 'matryoshka', label: 'matryoshka',    color: 'rgb(140, 102, 191)', source: (s) => {
    const n = s.nominal_gdp_step;
    const r = s.real_welfare_step;
    if (!Number.isFinite(n) || n <= 0 || !Number.isFinite(r)) return 0;
    const v = (n - r) / n;
    return v < 0 ? 0 : v > 1 ? 1 : v;
  } },
  { key: 'legal',      label: 'legal capture', color: 'rgb(217, 89, 89)',   source: (s) => s.law_surplus_loss_fraction ?? 0 },
  { key: 'recycling',  label: 'recycling',     color: 'rgb(89, 178, 115)',  source: (s) => s.pigouvian_effective_rate ?? 0 },
];

const statusEl = document.getElementById('status');
const loaderEl = document.getElementById('loader');
const loaderFillEl = document.getElementById('loader-fill');
const loaderLabelEl = document.getElementById('loader-label');
const sectorLabelEl = document.getElementById('sector-label');
const toggleTradesEl = document.getElementById('toggle-trades');  // legacy ref; element removed
const toggleCabalsEl = document.getElementById('toggle-cabals');
const toggleSectorsEl = document.getElementById('toggle-sectors');
const toggleHumansOnlyEl = document.getElementById('toggle-humans-only');
const ratioSliderEl = document.getElementById('ratio-slider');
const ratioValueEl = document.getElementById('ratio-value');
// HUD readout (top-right). Numeric mirror of the engine signals
// that drive the visual — α, EBI, per-tick welfare delta, gini,
// engine ticks/sec.
const hudAlphaEl = document.getElementById('hud-alpha');
const hudAlphaLeverEl = document.getElementById('hud-alpha-lever');
const hudAlphaGapRowEl = document.getElementById('hud-alpha-gap-row');
const hudAlphaGapEl = document.getElementById('hud-alpha-gap');
const hudEbiEl = document.getElementById('hud-ebi');
const hudWelfareStepEl = document.getElementById('hud-welfare-step');
const hudGiniEl = document.getElementById('hud-gini');
const hudTpsEl = document.getElementById('hud-tps');
const hudStreamEl = document.getElementById('hud-stream');
const hudFoldsEl = document.getElementById('hud-folds');
const hudComputeEl = document.getElementById('hud-compute');
const hudRejCostEl = document.getElementById('hud-rej-cost');
const hudRejMarketEl = document.getElementById('hud-rej-market');
const hudRejAlignEl = document.getElementById('hud-rej-align');
const hudRejLawEl = document.getElementById('hud-rej-law');
const hudRejComputeEl = document.getElementById('hud-rej-compute');
const hudRejPermEl = document.getElementById('hud-rej-perm');
const hudRejRegEl = document.getElementById('hud-rej-reg');
const hudRejSumRowEl = document.getElementById('hud-rej-sum-row');
const hudRejSumEl = document.getElementById('hud-rej-sum');
const hudRegimeCaptionEl = document.getElementById('hud-regime-caption');
const hudCabalsEl = document.getElementById('hud-cabals');
const hudSyndicatesEl = document.getElementById('hud-syndicates');
// Top-left density readout. cast count + caterpillars-per-1K-faces;
// face count itself removed from the UI per user feedback. Cheap
// reads from diagnostics, no per-frame allocation.
const densityCastEl = document.getElementById('density-cast');
const densityPer1kEl = document.getElementById('density-per-1k');
// Plan §C.1 — Louvain pipeline diagnostic readouts.
const hudEdgesInEl = document.getElementById('hud-edges-in');
const hudCandidatesEl = document.getElementById('hud-candidates');
const hudRenderFloorEl = document.getElementById('hud-render-floor');
const leversPendingRowEl = document.getElementById('levers-pending-row');
// Plan §G.1 — restart-preview block. Visible only when at least one
// structural lever has a pending edit; projected α and EBI numbers
// summarise what the engine will land at after Restart.
const leversPreviewRowEl = document.getElementById('levers-preview-row');
const leversPreviewAlphaEl = document.getElementById('levers-preview-alpha');
const leversPreviewEbiEl = document.getElementById('levers-preview-ebi');
const sectorCompassEl = document.getElementById('sector-compass');
const arcLegendEl = document.getElementById('arc-legend');
const ebiLegendEl = document.getElementById('ebi-legend');
// Lever panel — Phase 4 of spatial-sandbox-completeness.md §5.
// Levers carry data-key (engine override key) and data-kind
// ("live" → POST /update on every change; "structural" → queued
// until the user clicks Restart). The HTML defines the 20 plan-§3
// rows; this module reads them by attribute rather than by id so
// new levers slot in without scene.js changes.
//
// Per-lever value formatting lives in LEVER_FORMAT below, keyed by
// data-key. Levers not listed default to v.toFixed(2).
const LEVER_FORMAT = {
  // Live numeric levers
  'market_layer_tax':                  (v) => (v * 100).toFixed(1) + '%',
  'pigouvian.tax_rate':                (v) => (v * 100).toFixed(1) + '%',
  'pigouvian.recycling_progressivity': (v) => v.toFixed(1),
  'compute.budget_per_tick':           (v) => v.toFixed(2),
  'compute.power_cost_per_trade':      (v) => v.toFixed(4),
  'cross_stack_permeability':          (v) => (v * 100).toFixed(1) + '%',
  'norms.update_rate':                 (v) => v.toFixed(3),
  'law.transaction_size_cap':          (v) => v.toFixed(2),
  'folding_max_depth':                 (v) => String(Math.round(v)),
  'alpha':                             (v) => v.toFixed(2),
  'folding_propensity':                (v) => v.toFixed(2),
  'fold_nominal_multiplier':           (v) => v.toFixed(2),
  'base_friction':                     (v) => v.toFixed(3),
  // Structural numeric levers
  'agent_capability_mean':             (v) => v.toFixed(2),
  'human_capability_mean':             (v) => v.toFixed(2),
  'agent_autonomy_mean':               (v) => v.toFixed(2),
  'agent_trade_rate_multiplier':       (v) => v.toFixed(1),
  'network_p_local':                   (v) => v.toFixed(2),
  'norms.certified_fraction':          (v) => v.toFixed(2),
  'law.law_strength_initial':          (v) => v.toFixed(2),
};
// Levers that take a string value (selects). Some need translation
// to the engine override shape (e.g. "on"/"off" → true/false).
const LEVER_STRING_TRANSFORM = {
  'regulator.enabled':    (s) => s === 'on',
  'institutions.enabled': (s) => s === 'on',
  'mission.enabled':      (s) => s === 'on',
  // Pass-through values for the categorical levers (engine accepts
  // the string directly).
};

// Scenario presets — each entry is a target lever-state vector keyed
// by data-key. Values are pulled from engine/scenarios/__init__.py so
// every preset reproduces the scenario's attractor exactly. Off-panel
// scenario params (folding_branching, fold_real_efficiency, etc.) are
// left at engine defaults; the panel exposes every knob that
// distinguishes one preset's regime from another.
const PRESETS = {
  coasean_paradise: {
    title: 'COASEAN PARADISE',
    targets: {
      agent_capability_mean: 0.85,
      human_capability_mean: 0.65,
      alpha: 0.08,
      folding_propensity: 0.10,
      base_friction: 0.025,
      market_layer_tax: 0.010,
      cross_stack_permeability: 0.85,
      folding_max_depth: 2,
    },
  },
  universal_advocate: {
    title: 'UNIVERSAL ADVOCATE',
    targets: {
      agent_capability_mean: 0.90,
      human_capability_mean: 0.78,
      alpha: 0.20,
      base_friction: 0.020,
      folding_propensity: 0.25,
    },
  },
  exo_baroque_singularity: {
    title: 'EXO-BAROQUE SINGULARITY',
    targets: {
      alpha: 0.97,
      folding_propensity: 0.78,
      fold_nominal_multiplier: 2.4,
      folding_max_depth: 10,
    },
  },
  baroque_cathedral: {
    title: 'BAROQUE CATHEDRAL',
    targets: {
      agent_capability_mean: 0.78,
      alpha: 0.92,
      folding_propensity: 0.65,
      fold_nominal_multiplier: 2.0,
      base_friction: 0.06,
      market_layer_tax: 0.04,
      cross_stack_permeability: 0.45,
    },
  },
  slop_market: {
    title: 'SLOP MARKET',
    targets: {
      agent_capability_mean: 0.40,
      human_capability_mean: 0.30,
      alpha: 0.85,
      folding_propensity: 0.60,
      fold_nominal_multiplier: 2.2,
    },
  },
  mission_economy: {
    title: 'MISSION ECONOMY',
    targets: {
      agent_capability_mean: 0.70,
      human_capability_mean: 0.50,
      alpha: 0.45,
      folding_propensity: 0.35,
      base_friction: 0.04,
      cross_stack_permeability: 0.65,
      'institutions.enabled': true,
      'mission.enabled':      true,
    },
  },
};

// Active preset state. The title under the sphere reads from
// _activePreset.title; the steady-state line reads from
// _steadyState.triggered.
let _activePreset = null;
let _presetTweenActive = false;

// Steady-state detector. Maintains a rolling ring of the last
// STEADY_WINDOW steps' EBI and real_per_capita_welfare. Once both
// scalars hold a coefficient of variation under STEADY_COV_THRESHOLD
// for STEADY_HOLD consecutive emits AND the run has been going for
// at least STEADY_WARMUP steps, the sub-title flips to STEADY STATE.
// The detector resets on every preset application.
const STEADY_WINDOW = 60;
const STEADY_HOLD = 30;
const STEADY_COV_THRESHOLD = 0.005;  // 0.5% — both EBI and welfare
const STEADY_WARMUP = 30;
const _steadyState = {
  ebiRing: [],
  welfareRing: [],
  consecHits: 0,
  triggered: false,
  stepsSeen: 0,
};

function resetSteadyState() {
  _steadyState.ebiRing.length = 0;
  _steadyState.welfareRing.length = 0;
  _steadyState.consecHits = 0;
  _steadyState.triggered = false;
  _steadyState.stepsSeen = 0;
  setSphereSubtitle('');
}

function _coefficientOfVariation(arr) {
  if (arr.length < 2) return Infinity;
  let sum = 0;
  for (let i = 0; i < arr.length; i += 1) sum += arr[i];
  const mean = sum / arr.length;
  if (!Number.isFinite(mean) || mean === 0) return Infinity;
  let varSum = 0;
  for (let i = 0; i < arr.length; i += 1) {
    const d = arr[i] - mean;
    varSum += d * d;
  }
  const sd = Math.sqrt(varSum / arr.length);
  return Math.abs(sd / mean);
}

function updateSteadyState(step) {
  _steadyState.stepsSeen += 1;
  const nstep = step.nominal_gdp_step;
  const rstep = step.real_welfare_step;
  const ebi = (Number.isFinite(nstep) && Number.isFinite(rstep) && rstep > 0)
    ? nstep / rstep
    : null;
  const welfare = step.real_per_capita_welfare;
  if (ebi !== null) {
    _steadyState.ebiRing.push(ebi);
    if (_steadyState.ebiRing.length > STEADY_WINDOW) _steadyState.ebiRing.shift();
  }
  if (Number.isFinite(welfare)) {
    _steadyState.welfareRing.push(welfare);
    if (_steadyState.welfareRing.length > STEADY_WINDOW) _steadyState.welfareRing.shift();
  }
  if (
    _steadyState.stepsSeen < STEADY_WARMUP ||
    _steadyState.ebiRing.length < STEADY_WINDOW ||
    _steadyState.welfareRing.length < STEADY_WINDOW
  ) return;
  const covE = _coefficientOfVariation(_steadyState.ebiRing);
  const covW = _coefficientOfVariation(_steadyState.welfareRing);
  if (covE < STEADY_COV_THRESHOLD && covW < STEADY_COV_THRESHOLD) {
    _steadyState.consecHits += 1;
  } else {
    _steadyState.consecHits = 0;
    if (_steadyState.triggered) {
      _steadyState.triggered = false;
      setSphereSubtitle('');
    }
  }
  if (!_steadyState.triggered && _steadyState.consecHits >= STEADY_HOLD) {
    _steadyState.triggered = true;
    setSphereSubtitle('STEADY STATE');
  }
}

// Sector-level surface topography. Translates the engine's per-sector
// real-welfare emission into sustained altitude offsets per sector,
// producing 12 continents whose mass varies with the regime. The
// per-event bumps from individual trades layer on top as detail
// texture.
//
// Each tick: EMA-smooth the per-sector welfare share, z-score against
// the population mean, tanh-squash to bounded units, scale into the
// surface's ±SECTOR_BASE_CAP budget. With the 8 %/tick EMA the
// continent map responds to a regime change within ~30 ticks (~15 s
// of engine time) — slow enough to filter per-step noise, fast enough
// to track a preset transition.
const _sectorWelfareEMA = new Float32Array(12);
let _sectorWelfareEMASeeded = false;
const SECTOR_WELFARE_EMA_RATE = 0.08;
const SECTOR_TOPO_GAIN = 0.12;  // scales the tanh'd z-score into the
                                // ±0.18 cap; 0.12 reads as clearly
                                // visible continents without clamping
                                // a typical regime's variance.

function updateSectorTopography(step) {
  const arr = step.real_welfare_per_sector_step;
  if (!Array.isArray(arr) || arr.length !== 12) return;
  // EMA-smooth on raw values so a single noisy tick doesn't reshape
  // the continents. First valid emit seeds the EMA so the first
  // post-restart tick already reads the engine's level instead of
  // ramping from zero.
  if (!_sectorWelfareEMASeeded) {
    for (let i = 0; i < 12; i += 1) {
      const v = Number(arr[i]);
      _sectorWelfareEMA[i] = Number.isFinite(v) ? v : 0;
    }
    _sectorWelfareEMASeeded = true;
  } else {
    for (let i = 0; i < 12; i += 1) {
      const v = Number(arr[i]);
      if (!Number.isFinite(v)) continue;
      _sectorWelfareEMA[i] =
        _sectorWelfareEMA[i] * (1 - SECTOR_WELFARE_EMA_RATE) +
        v * SECTOR_WELFARE_EMA_RATE;
    }
  }
  // Compute mean + std of the smoothed values. Division by std turns
  // the signal into z-scores so the visual deformation is comparable
  // across regimes that print very different absolute welfare numbers
  // (coasean's mean welfare/step is two orders larger than slop's).
  let mean = 0;
  for (let i = 0; i < 12; i += 1) mean += _sectorWelfareEMA[i];
  mean /= 12;
  let varSum = 0;
  for (let i = 0; i < 12; i += 1) {
    const d = _sectorWelfareEMA[i] - mean;
    varSum += d * d;
  }
  const std = Math.sqrt(varSum / 12);
  if (std < 1e-9) return;  // all sectors equal — nothing to differentiate
  const deltas = new Float32Array(12);
  for (let i = 0; i < 12; i += 1) {
    const z = (_sectorWelfareEMA[i] - mean) / std;
    // tanh squashes the tails so a single dominant sector doesn't
    // monopolise the altitude budget while the other 11 read as flat.
    const squashed = Math.tanh(z);
    deltas[i] = squashed * SECTOR_TOPO_GAIN;
  }
  surface?.setSectorAltitudeTargets?.(deltas);
}

function resetSectorTopography() {
  _sectorWelfareEMA.fill(0);
  _sectorWelfareEMASeeded = false;
  // The surface API gets cleared via resetHeightmap on restartRun.
}

function setSphereTitle(text) {
  const el = document.getElementById('sphere-title-main');
  if (el) el.textContent = text || '';
}

function setSphereSubtitle(text) {
  const el = document.getElementById('sphere-title-sub');
  if (!el) return;
  el.textContent = text || '';
  if (text) el.classList.add('visible');
  else el.classList.remove('visible');
}
// Slider value 0..100 maps log-scale to agentsPerHuman 1..1000.
// At slider=67, value ≈ 100 (real-population default of 1 human : 100 agents).
function sliderToAgentsPerHuman(s) {
  return Math.max(1, Math.round(Math.pow(10, (Number(s) / 100) * 3)));
}
const tradeCounterEl = document.getElementById('trade-counter-value');
const welfareTotalEl = document.getElementById('welfare-total-value');
const cumulativeBarFillEl = document.getElementById('cumulative-bar-fill');
const welfareFlowEl = document.getElementById('welfare-flow');
// Phase 6 §7.3 — split stock bar.
const wealthStockHumansEl = document.getElementById('wealth-stock-humans');
const wealthStockAiEl = document.getElementById('wealth-stock-ai');
const wealthStockHumansPctEl = document.getElementById('wealth-stock-humans-pct');
const wealthStockAiPctEl = document.getElementById('wealth-stock-ai-pct');
let sectorsEnabled = toggleSectorsEl?.checked ?? true;
// Dashboard-side pause. The engine keeps running; we skip processing
// new step / cast / edge events so the visual freezes. Toggling off
// resumes from the next event (no catch-up backlog — we just drop
// what arrived during the pause).
let paused = false;
const btnPauseEl = document.getElementById('btn-pause');
// Two recycle buttons:
//   btn-reset   — re-runs the engine in-place with current lever
//                 values. JS state stays alive; only the engine run
//                 and the substrate get torn down + rebuilt.
//   btn-restart — full page reload via location.reload(). Use when
//                 the dashboard JS itself looks wedged or you want
//                 to pick up new code.
const btnResetEl = document.getElementById('btn-reset');
const btnRestartEl = document.getElementById('btn-restart');
const btnStartEl = document.getElementById('btn-start');
const presetSelectEl = document.getElementById('preset-select');
let cumulativeTrades = 0;       // monotonic — increments per snapshot
let cumulativeWealth = 0;       // real_welfare_cumulative from engine
// EMA of per-tick EBI. Drives the world-shape morph. α=0.06 per
// step (~5 Hz tick rate) → ~3 s half-life — fast enough to react
// to lever changes, slow enough to filter per-snapshot sampling
// noise. Initialised at the neutral midpoint so the first few
// frames don't snap to disc/chaos before the engine produces a
// meaningful EBI.
let _ebiSmoothed = 2.0;
// Stream-staleness tracking. The dashboard expects an edges_v2
// burst on every engine tick (~5 Hz). If the gap grows beyond
// STREAM_STALE_MS the HUD's "stream" row flips from "live" to
// "Xs ago" so the user can tell engine-stop vs browser-throttle.
// document.visibilityState makes the throttle case explicit:
// backgrounded tabs prefix the readout with "bg".
let _lastEdgeT = 0;
const STREAM_STALE_MS = 2000;
// Two morph axes, mutually exclusive by EBI regime:
//   EBI <= 2.0  →  flatten toward disc       (smooth/clean economy)
//   EBI ~= 2.0  →  clean sphere, just pockmarks from trade bumps
//   EBI  > 2.0  →  chaos warp (lumpy hyperspherical lobes)
// Target values updated from EBI on each engine tick. The
// RENDERED values smoothly approach the targets every animation
// frame, decoupling the visible morph from the engine cadence
// (which would otherwise show up as a "tick — jump — sit"
// rhythm). A small breathing oscillation is folded in on top of
// the rendered flatten so the shape never sits at a perfectly
// fixed value between events.
let _shapeFlattenTarget = 0;
let _shapeChaosTarget = 0;
let _shapeFlatten = 0;
let _shapeChaos = 0;
const SHAPE_SMOOTH_RATE = 0.04;        // per-frame ease-toward-target
const SHAPE_BREATH_AMP_FLATTEN = 0.018; // ±1.8% on flatten
const SHAPE_BREATH_AMP_CHAOS = 0.025;   // ±2.5% on chaos amplitude
const SHAPE_FLATTEN_MAX = 0.0;         // Disc morph disabled — the squash
                                       // read poorly and broke the sphere
                                       // identity. Hyperspherical chaos
                                       // on the high-EBI side stays.
const SHAPE_FLATTEN_EBI_HIGH = 2.0;    // above this → no flatten
const SHAPE_FLATTEN_EBI_LOW = 0.5;     // at or below this → full flatten
const SHAPE_CHAOS_EBI_LOW = 2.0;       // at or below this → no chaos
const SHAPE_CHAOS_EBI_HIGH = 5.0;      // at or above this → full chaos
const CUM_WEALTH_BAR_CAP = 1e8; // 100M real welfare → full bar. Linear scale,
                                // saturates past the cap. The number text below
                                // keeps climbing past the bar's ceiling.

// Phase 3 §4.2 — sector compass. Twelve swatches rendered from the
// theme's sectorPalette; clicking a swatch isolates that sector
// (other agents fade to 0.18 RGB for 5 s) and the visual answer to
// "where do the manufacturing agents end up under this configuration"
// is one click away. Hovering a swatch shows the sector name.
let _isolateTimer = null;
function initSectorCompass() {
  if (!sectorCompassEl) return;
  const palette = theme.sectorPalette;
  if (!Array.isArray(palette)) return;
  // Idempotent: rebuild on every init in case the panel was wiped
  // (e.g. restartRun resets DOM-level state).
  sectorCompassEl.innerHTML = '';
  for (let i = 0; i < palette.length; i += 1) {
    const swatch = document.createElement('div');
    swatch.className = 'sector-compass-swatch';
    swatch.dataset.sector = String(i);
    const c = palette[i];
    swatch.style.background = `rgb(${Math.round(c[0] * 255)}, ${Math.round(c[1] * 255)}, ${Math.round(c[2] * 255)})`;
    swatch.title = SECTOR_NAMES[i] ?? `sector ${i}`;
    swatch.addEventListener('click', () => onSectorCompassClick(i, swatch));
    sectorCompassEl.appendChild(swatch);
  }
}
function onSectorCompassClick(sector, swatchEl) {
  if (!agents) return;
  const current = agents.isolatedSectorOf?.() ?? -1;
  if (_isolateTimer !== null) {
    clearTimeout(_isolateTimer);
    _isolateTimer = null;
  }
  if (current === sector) {
    // Click on the active swatch clears isolation.
    agents.setIsolatedSector(-1);
    for (const el of sectorCompassEl.querySelectorAll('.sector-compass-swatch')) {
      el.classList.remove('isolated');
    }
    return;
  }
  agents.setIsolatedSector(sector);
  for (const el of sectorCompassEl.querySelectorAll('.sector-compass-swatch')) {
    el.classList.toggle('isolated', el === swatchEl);
  }
  // Plan §4.2: isolate for 5 s, then revert.
  _isolateTimer = setTimeout(() => {
    agents.setIsolatedSector(-1);
    for (const el of sectorCompassEl.querySelectorAll('.sector-compass-swatch')) {
      el.classList.remove('isolated');
    }
    _isolateTimer = null;
  }, 5000);
}

// Trade-arc legend. The on-substrate palette is binary
// (executed-blue vs rejected-red); per-reason breakdown lives in
// the HUD rej-mix rows instead of competing for hue space here.
// `reject_cost` is the representative palette key for the
// rejected colour — every reject_* key in OUTCOME_COLORS now
// points at the same RGB.
const ARC_LEGEND_ROWS = [
  ['executed',    'executed'],
  ['reject_cost', 'rejected'],
];
function initArcLegend() {
  if (!arcLegendEl) return;
  arcLegendEl.innerHTML = '';
  for (const [key, label] of ARC_LEGEND_ROWS) {
    const c = OUTCOME_PALETTE[key];
    if (!c) continue;
    const row = document.createElement('div');
    row.className = 'arc-legend-row';
    const dot = document.createElement('div');
    dot.className = 'arc-legend-dot';
    dot.style.background = `rgb(${Math.round(c[0] * 255)}, ${Math.round(c[1] * 255)}, ${Math.round(c[2] * 255)})`;
    const name = document.createElement('div');
    name.className = 'arc-legend-name';
    name.textContent = label;
    row.appendChild(dot);
    row.appendChild(name);
    arcLegendEl.appendChild(row);
  }
}

// Phase 6 §7.4 — EBI shape-morph legend. Three glyphs that mirror
// the substrate shape morph: disc / sphere / lobes. The active
// glyph highlights based on the current EBI band (driven by
// updateEbiLegend on each onStep).
function initEbiLegend() {
  if (!ebiLegendEl) return;
  // The glyphs are pre-rendered in the HTML; this hook is here so
  // a future "click to pin band" interaction has a place to land.
  for (const el of ebiLegendEl.querySelectorAll('.ebi-glyph')) {
    el.classList.remove('active');
  }
}
function updateEbiLegend(ebi) {
  if (!ebiLegendEl || !Number.isFinite(ebi)) return;
  // Two reachable shape bands now that the disc flatten is
  // disabled (SHAPE_FLATTEN_MAX = 0):
  //   ebi < 2.5  → sphere (calibrated reference + low baroque)
  //   ebi ≥ 2.5  → lobes  (reflexivity / exo-baroque / untethered)
  const band = ebi >= 2.5 ? 'lobes' : 'sphere';
  for (const el of ebiLegendEl.querySelectorAll('.ebi-glyph')) {
    el.classList.toggle('active', el.dataset.band === band);
  }
}

// Phase 6 §7.3 — the welfare meter redesigns around two new shapes:
// a single split bar for stock (humans + AI compose to 1.0), and
// three 60-tick sparklines for the per-tick flow channels. The
// per-frame EMA smoothing the old meter used is dropped — it was
// hiding real signal changes and producing stale targets in
// backgrounded tabs.
const SPARKLINE_LEN = 60;
let sparklineRows = null;

function buildSparklineRow(seg, container) {
  const row = document.createElement('div');
  row.className = 'sparkline-row';
  const header = document.createElement('div');
  header.className = 'sparkline-row-header';
  const labelWrap = document.createElement('span');
  labelWrap.className = 'sparkline-row-label';
  const dot = document.createElement('span');
  dot.className = 'meter-dot';
  dot.style.background = seg.color;
  labelWrap.appendChild(dot);
  labelWrap.appendChild(document.createTextNode(seg.label));
  const valueEl = document.createElement('span');
  valueEl.className = 'sparkline-row-value';
  valueEl.textContent = '--';
  header.appendChild(labelWrap);
  header.appendChild(valueEl);
  const canvas = document.createElement('canvas');
  canvas.className = 'sparkline-canvas';
  // Width is finalised at first draw using clientWidth so the
  // canvas hits its CSS-laid-out size 1:1. Height is fixed by CSS.
  canvas.width = 1;
  canvas.height = 1;
  row.appendChild(header);
  row.appendChild(canvas);
  container.appendChild(row);
  return {
    key: seg.key,
    source: seg.source,
    color: seg.color,
    valueEl,
    canvas,
    // Ring buffer of (step, value) pairs. step is the integer
    // engine step index so the x-axis reads as real time.
    history: [],
    lastDrawnStep: -1,
  };
}

function initWelfareMeter() {
  // Stock side has no per-frame bar anymore; the split bar updates
  // directly off the latest snapshot. Sparklines own the flow side.
  sparklineRows = [];
  if (welfareFlowEl) {
    welfareFlowEl.innerHTML = '';
    for (const seg of FLOW_SEGMENTS) {
      sparklineRows.push(buildSparklineRow(seg, welfareFlowEl));
    }
  }
}

// Phase 6 §7.3 — paint the stock split bar from the latest stock
// shares. Called from onStep.
function updateWealthStock(step) {
  const hShare = Number.isFinite(step.human_wealth_share)
    ? Math.max(0, Math.min(1, step.human_wealth_share))
    : null;
  if (hShare === null) return;
  const aShare = 1 - hShare;
  if (wealthStockHumansEl) wealthStockHumansEl.style.width = (hShare * 100).toFixed(2) + '%';
  if (wealthStockAiEl) wealthStockAiEl.style.width = (aShare * 100).toFixed(2) + '%';
  if (wealthStockHumansPctEl) wealthStockHumansPctEl.textContent = (hShare * 100).toFixed(1) + '%';
  if (wealthStockAiPctEl) wealthStockAiPctEl.textContent = (aShare * 100).toFixed(1) + '%';
}

// Phase 6 §7.3 — push the per-step value into each sparkline's ring
// buffer and re-draw. Called from onStep so the canvas is at most
// one engine tick behind the rendered state.
function pushSparklineSamples(step) {
  if (!sparklineRows) return;
  const stepIdx = Number.isFinite(step.step) ? step.step : 0;
  for (let i = 0; i < sparklineRows.length; i += 1) {
    const r = sparklineRows[i];
    const v = r.source(step);
    const sample = Number.isFinite(v) ? Math.max(0, Math.min(1, v)) : 0;
    r.history.push({ s: stepIdx, v: sample });
    if (r.history.length > SPARKLINE_LEN) r.history.shift();
    // Smoothing target for the rightmost line vertex. drawSparklines
    // eases r.rendered toward this each frame so the right edge of
    // the sparkline glides continuously instead of jumping at
    // engine-tick boundaries (the previous behaviour produced the
    // ~0.75 Hz visible pulse).
    r.target = sample;
    if (r.rendered === undefined) r.rendered = sample;
  }
}

function drawSparklines() {
  if (!sparklineRows) return;
  for (let i = 0; i < sparklineRows.length; i += 1) {
    const r = sparklineRows[i];
    const canvas = r.canvas;
    if (canvas.clientWidth === 0 || canvas.clientHeight === 0) continue;
    // Match canvas backing to displayed size (devicePixelRatio
    // factor so the line stays sharp on hi-dpi).
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const targetW = Math.floor(canvas.clientWidth * dpr);
    const targetH = Math.floor(canvas.clientHeight * dpr);
    if (canvas.width !== targetW) canvas.width = targetW;
    if (canvas.height !== targetH) canvas.height = targetH;
    const ctx = canvas.getContext('2d');
    if (!ctx) continue;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (r.history.length < 2) continue;
    // Ease the rendered head value toward the per-tick target so
    // the rightmost vertex moves smoothly across frames.
    if (r.target !== undefined) {
      r.rendered += (r.target - r.rendered) * 0.10;
    }
    if (r.valueEl) r.valueEl.textContent = (r.rendered * 100).toFixed(1) + '%';
    const w = canvas.width;
    const h = canvas.height;
    const n = r.history.length;
    ctx.lineWidth = 1.5 * dpr;
    ctx.strokeStyle = r.color;
    ctx.beginPath();
    for (let k = 0; k < n; k += 1) {
      const x = (k / (SPARKLINE_LEN - 1)) * w;
      // Replace the rightmost sample with the per-frame eased
      // value; the rest of the history stays at the discrete tick
      // values it landed at.
      const sample = (k === n - 1 && r.rendered !== undefined)
        ? r.rendered
        : r.history[k].v;
      const y = h - sample * h;
      if (k === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }
}

// HUD ticks/sec — ring buffer of recent step arrival timestamps.
// Engine cadence is distinct from render FPS (the scene animates at
// the browser's rAF rate while step events arrive ~5 Hz).
const HUD_TPS_WINDOW = 10;
const _stepArrivalT = new Float32Array(HUD_TPS_WINDOW);
let _stepArrivalI = 0;
let _stepArrivalCount = 0;
function pushStepArrival(tSec) {
  _stepArrivalT[_stepArrivalI] = tSec;
  _stepArrivalI = (_stepArrivalI + 1) % HUD_TPS_WINDOW;
  if (_stepArrivalCount < HUD_TPS_WINDOW) _stepArrivalCount += 1;
}
function ticksPerSec() {
  if (_stepArrivalCount < 2) return 0;
  const newestI = (_stepArrivalI - 1 + HUD_TPS_WINDOW) % HUD_TPS_WINDOW;
  const oldestI = _stepArrivalCount < HUD_TPS_WINDOW
    ? 0
    : _stepArrivalI;
  const newest = _stepArrivalT[newestI];
  const oldest = _stepArrivalT[oldestI];
  const span = newest - oldest;
  if (span <= 0) return 0;
  return (_stepArrivalCount - 1) / span;
}

// Phase 6 §7.3 drops the per-frame EMA — the sparkline already
// gives the user a continuous read on the underlying signal and
// the EMA's only purpose was masking sampling noise at frame rate.
// In backgrounded tabs the EMA never converged because rAF was
// throttled; the new path updates strictly per onStep so it's
// immune to background throttling.
function updateWelfareMeter() {
  drawSparklines();
}
const counters = { step: 0, cast: 0 };

// Canonical sector names from engine/core/population.py.
const SECTOR_NAMES = [
  'agriculture', 'extraction', 'manufacturing', 'energy',
  'logistics', 'construction', 'retail', 'finance',
  'information', 'health', 'education', 'leisure',
];

function setProgress(fraction, label) {
  if (loaderFillEl) loaderFillEl.style.width = `${Math.min(100, Math.max(0, fraction * 100))}%`;
  if (label && loaderLabelEl) loaderLabelEl.textContent = label;
  if (fraction >= 1 && loaderEl) {
    setTimeout(() => loaderEl.setAttribute('data-done', '1'), 250);
  }
}

// Yield to the event loop so the browser can repaint the loader fill
// before the next synchronous chunk (icosphere build, adjacency, etc.).
// MessageChannel.postMessage is not throttled in background tabs, so
// initial load completes whether the user has the tab focused or not
// — unlike rAF, which Chrome throttles to ~1Hz (or stalls entirely)
// for backgrounded tabs and would leave main() hung at "scene init".
function nextFrame() {
  return new Promise((resolve) => {
    const channel = new MessageChannel();
    channel.port1.onmessage = () => resolve();
    channel.port2.postMessage(null);
  });
}

let renderer, scene, camera, controls;
let surface = null;
let agents = null;
let edges = null;
let firms = null;
let folds = null;
let clusters = null;
let clusterLabels = null;
let clusterOverlay = null;
let clusterWorker = null;
let _workerJobId = 0;
let _workerInflight = false;
let _workerLastMs = 0;
let _workerTicksUntilNext = 0;
const CLUSTER_WORKER_PERIOD = 10;     // worker pass cadence (ticks)
let inspector = null;
// Phase 6 §7.1 — the inspector reads from the most-recent cast
// snapshot to populate the agent card. scene.js owns the canonical
// snapshot map so multiple subsystems (firms, folds, inspector)
// can look up by idx without each maintaining its own copy.
const _castByIdx = new Map();
let summaryTimer = null;
let stream = null;
let frameCount = 0;
let lastFpsT = performance.now();
let fps = 0;

// Single locked theme — themes.THEME.
const theme = THEME;

function initScene() {
  const canvas = document.getElementById('scene');

  renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: false,
    powerPreference: 'high-performance',
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight, false);
  // Linear tonemap — light-mode themes need predictable colours, not
  // the warm rolloff ACES gives.
  renderer.toneMapping = THREE.NoToneMapping;

  scene = new THREE.Scene();
  scene.background = new THREE.Color(theme.background ?? 0xffffff);

  // Camera sits far enough back that the radius=600 sphere fills a
  // generous portion of the viewport with margin for the activations
  // at the silhouette.
  camera = new THREE.PerspectiveCamera(
    42,
    window.innerWidth / window.innerHeight,
    1,
    8000,
  );
  camera.position.set(0, 0, 2400);   // start zoomed out a bit so
                                     // the sphere fits with margin
                                     // for substrate altitude peaks
                                     // and arc bows.

  controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.06;
  controls.minDistance = 700;
  controls.maxDistance = 4000;

  surface = createSurface(scene, {
    radius: theme.radius,
    subdivisions: theme.subdivisions,
    baseColor: theme.baseColor,
    edgeColor: theme.edgeColor,
    edgeThreshold: theme.edgeThreshold,
    // Map the substrate-build phases into the [0.18, 0.60] band of
    // the overall loader so the bar moves during the 5–7 sec block
    // at 2×/4× scaling instead of sitting frozen at "icosphere
    // build". Callback fires synchronously between phases — Three's
    // IcosahedronGeometry constructor itself is still one
    // uninterruptible call inside the build.
    onProgress: (frac, label) => {
      const overall = 0.18 + frac * (0.60 - 0.18);
      setProgress(overall, label);
    },
  });

  agents = createAgents(scene, surface, {
    sphereRadius: theme.radius ?? 700,
    stackInwardScale: theme.stackInwardScale,
    maxStepsPerSec: theme.maxStepsPerSec,
    minStepsPerSec: theme.minStepsPerSec,
    partnerAttract: theme.partnerAttract,
    firmAttract: theme.firmAttract,
    segmentScale: theme.segmentScale,
    humanLengthFactor: theme.humanLengthFactor,
    segmentColor: theme.segmentColor,
    sectorPalette: theme.sectorPalette,
    sectorTintWeight: 0.85,
  });

  edges = createEdges(scene, surface, agents, {
    sphereRadius: theme.radius ?? 700,
  });

  firms = createFirms(scene, surface, agents, {
    sphereRadius: theme.radius ?? 700,
  });

  folds = createFolds(scene, surface, agents, {
    sphereRadius: theme.radius ?? 700,
  });

  clusters = createClusters();
  clusterLabels = createClusterLabels();
  // Phase 2 §3.2 follow-on: secondary clusterer in a Web Worker.
  // The worker runs Louvain on the buffer snapshot every 10
  // ticks; the reply feeds cluster_labels.updateWithSecondary
  // for stability cross-validation. Worker module is loaded via
  // import URL relative to the dashboard root.
  try {
    clusterWorker = new Worker(
      new URL('./clusters_sbm.js', import.meta.url),
      { type: 'module' },
    );
    clusterWorker.addEventListener('message', onClusterWorkerMessage);
    clusterWorker.addEventListener('error', (e) => {
      console.warn('[cluster-worker] error:', e.message);
      clusterWorker = null;
    });
  } catch (err) {
    console.warn('[cluster-worker] init failed:', err);
    clusterWorker = null;
  }
  clusterOverlay = createClusterOverlay(scene, surface, agents, {
    sphereRadius: theme.radius ?? 700,
  });

  inspector = createInspectorAgent({
    canvas,
    camera,
    agents,
    surface,
    sectorNames: SECTOR_NAMES,
    sectorPalette: theme.sectorPalette,
    getCastEntry: _castByIdx,
    getClusterId: (idx) => {
      const part = clusterLabels?.partition();
      if (!part) return -1;
      return part.get(idx) ?? -1;
    },
    getClusterStatus: (cid) => clusterLabels?.statusOf?.(cid) ?? 'cabal',
    getClusterTrack: (cid) => clusterLabels?.trackOf?.(cid) ?? null,
    getClusterMembers: (cid) => {
      const t = clusterLabels?.trackOf?.(cid);
      return t ? t.members : [];
    },
    stackEl: document.getElementById('inspector-stack'),
  });
  inspector.attach();

  initWelfareMeter();
  initSectorCompass();
  initArcLegend();
  initEbiLegend();

  window.addEventListener('resize', onResize);
  renderer.domElement.addEventListener('mousemove', onPointerMove);
  renderer.domElement.addEventListener('mousemove', onPointerMoveForFirmHover);
  renderer.domElement.addEventListener('mouseleave', onPointerLeave);

  // Trade arcs are now always hidden; the visualization moved to
  // the trades panel and the toggle was retired in favour of
  // show-cabals below.
  if (edges) edges.setVisible(false);
  toggleCabalsEl?.addEventListener('change', () => {
    clusterOverlay?.setVisible(toggleCabalsEl.checked);
  });
  if (toggleCabalsEl && clusterOverlay) {
    clusterOverlay.setVisible(toggleCabalsEl.checked);
  }
  toggleSectorsEl?.addEventListener('change', () => {
    sectorsEnabled = toggleSectorsEl.checked;
    if (!sectorsEnabled) {
      surface?.setHoveredSector(-1);
      if (sectorLabelEl) sectorLabelEl.style.display = 'none';
      _lastHoveredSector = -1;
    }
  });
  toggleHumansOnlyEl?.addEventListener('change', () => {
    agents?.setHumansOnly(toggleHumansOnlyEl.checked);
  });
  btnPauseEl?.addEventListener('click', () => {
    paused = !paused;
    btnPauseEl.classList.toggle('toggled', paused);
    btnPauseEl.textContent = paused ? 'resume' : 'pause';
    setStatus(paused ? `${theme.name} · paused` : `${theme.name} · live`, paused ? '' : 'live');
  });
  btnResetEl?.addEventListener('click', () => { restartRun(); });
  btnRestartEl?.addEventListener('click', () => {
    if (typeof window !== 'undefined') window.location.reload();
  });
  presetSelectEl?.addEventListener('change', () => {
    const v = presetSelectEl.value;
    if (btnStartEl) btnStartEl.disabled = !v || !PRESETS[v];
  });
  btnStartEl?.addEventListener('click', () => {
    const name = presetSelectEl?.value;
    if (!name || !PRESETS[name]) return;
    applyPreset(name);
  });
  if (ratioSliderEl) {
    const applyRatio = () => {
      const n = sliderToAgentsPerHuman(ratioSliderEl.value);
      if (ratioValueEl) ratioValueEl.textContent = String(n);
      agents?.setAgentsPerHuman(n);
    };
    applyRatio();
    ratioSliderEl.addEventListener('input', applyRatio);
  }
  // Generic lever wiring. Every control inside #levers-panel that
  // carries data-key gets one listener. data-kind="live" pushes to
  // the engine immediately (debounced); "structural" queues for the
  // next Restart and surfaces the pending banner.
  initLeverControls();
}

// Phase 2 §3.2 follow-on — worker dispatch. Posts a buffer
// snapshot every CLUSTER_WORKER_PERIOD ticks if the previous job
// has returned. _workerInflight gates the post so a slow worker
// can't queue multiple jobs.
function dispatchClusterWorker() {
  if (!clusterWorker || !clusters) return;
  if (_workerInflight) return;
  _workerTicksUntilNext -= 1;
  if (_workerTicksUntilNext > 0) return;
  _workerTicksUntilNext = CLUSTER_WORKER_PERIOD;
  const edges = clusters.bufferSnapshot();
  if (edges.length === 0) return;
  _workerInflight = true;
  _workerJobId += 1;
  clusterWorker.postMessage({
    type: 'run',
    jobId: _workerJobId,
    edges,
  });
}

function onClusterWorkerMessage(ev) {
  const { type, jobId, partition, ms } = ev.data ?? {};
  if (type !== 'partition') return;
  _workerInflight = false;
  _workerLastMs = ms ?? 0;
  // Ignore replies for jobs the dashboard restart already
  // invalidated.
  if (jobId !== _workerJobId) return;
  if (!Array.isArray(partition)) return;
  const map = new Map();
  for (const [idx, c] of partition) map.set(idx, c);
  clusterLabels?.updateWithSecondary(map);
}

function initLeverControls() {
  const panel = document.getElementById('levers-panel');
  if (!panel) return;
  const controls = panel.querySelectorAll('[data-key]');
  for (const el of controls) {
    const key = el.dataset.key;
    const kind = el.dataset.kind || 'live';
    const valueEl = document.getElementById(`${el.id}-value`);
    const tag = el.tagName.toLowerCase();
    if (tag === 'select') {
      // Initial display already correct from selected option.
      el.addEventListener('change', () => {
        const raw = el.value;
        if (valueEl) valueEl.textContent = raw;
        const transform = LEVER_STRING_TRANSFORM[key];
        const value = transform ? transform(raw) : raw;
        applyLeverChange(key, value, kind);
      });
    } else {
      // input[type="range"] or other numeric
      const fmt = LEVER_FORMAT[key] ?? ((v) => v.toFixed(2));
      el.addEventListener('input', () => {
        const v = parseFloat(el.value);
        if (!Number.isFinite(v)) return;
        if (valueEl) valueEl.textContent = fmt(v);
        applyLeverChange(key, v, kind);
      });
    }
  }
}

function applyLeverChange(key, value, kind) {
  // Live: write through to engine. _leverState carries numeric
  // values for the α-mapper, so don't pollute it with strings.
  if (kind === 'live') {
    if (typeof value === 'number') _leverState[key] = value;
    scheduleLeverUpdate(key, value);
    return;
  }
  // Structural: queue for restart. The structural-pending map is
  // separate from the live debounce queue so they don't fight.
  _structuralPending.set(key, value);
  if (typeof value === 'number') _leverState[key] = value;
  updateAlphaHud();
  if (leversPendingRowEl) leversPendingRowEl.style.display = '';
  // Plan §G.1 — refresh the restart preview every time a structural
  // lever queues. The projected α reads the post-restart lever state
  // (live levers + pending structural levers) through mapAlpha; EBI
  // est is the cached α→EBI curve interpolated at that α.
  updateRestartPreview();
}

// Debounced live-update POST. Per-key timer so simultaneous sliders
// on different keys don't cancel each other. The engine validates
// against _LIVE_TUNABLE + Sobol bounds; a 400/409 response is logged
// but doesn't unwind the slider — the user can drag back.
const LEVER_DEBOUNCE_MS = 200;
const _leverTimers = new Map();
const _leverPending = new Map();
// Live lever state — every scheduleLeverUpdate writes here so the
// dashboard-side α mapper can read the current configuration even
// when the engine update POST is debounced. Initial values are
// seeded from the slider DOM at main() startup.
const _leverState = {};
// Pending structural-lever changes. Drained into the Restart
// overrides payload. Cleared after the restart completes.
const _structuralPending = new Map();
let _lastEngineAlpha = NaN;
// Plan §G.1 — tracked alongside _lastEngineAlpha so the restart-
// preview row can show ΔEBI against the live reading. Refreshed in
// onStep from the same EBI-EMA path the shape morph reads.
let _lastEngineEbi = NaN;

// Read every data-key control's current value into _leverState.
// Called once in main() so the lever-α mapping has the right
// baseline before the user touches anything.
function seedLeverStateFromDom() {
  const panel = document.getElementById('levers-panel');
  if (!panel) return;
  for (const el of panel.querySelectorAll('[data-key]')) {
    const key = el.dataset.key;
    if (el.tagName.toLowerCase() === 'select') {
      // Strings don't feed the α-mapper, skip.
      continue;
    }
    const v = parseFloat(el.value);
    if (Number.isFinite(v)) _leverState[key] = v;
  }
}
// Plan §D.2 — walk the lever-panel rows and append a hollow-square
// mark to any whose data-key maps to an alpha_weights entry with
// `implemented: false`. The mark sits AFTER the label so it doesn't
// fight the live/structural dot that sits BEFORE; tooltip explains
// the meaning. Idempotent — re-running it (e.g. after a weights
// reload) won't double up.
function markUnimplementedLevers(weights) {
  if (!weights) return;
  const panel = document.getElementById('levers-panel');
  if (!panel) return;
  const unimplemented = new Set();
  for (const [k, c] of Object.entries(weights.levers || {})) {
    if (c.implemented === false) unimplemented.add(k);
  }
  for (const [k, c] of Object.entries(weights.categorical_levers || {})) {
    if (c.implemented === false) unimplemented.add(k);
  }
  for (const el of panel.querySelectorAll('[data-key]')) {
    const key = el.dataset.key;
    if (!unimplemented.has(key)) continue;
    const header = el.closest('.lever-row')?.querySelector('.lever-header');
    if (!header) continue;
    if (header.querySelector('.lever-mark-unimpl')) continue;
    const label = header.querySelector('.lever-label');
    if (!label) continue;
    const mark = document.createElement('span');
    mark.className = 'lever-mark-unimpl';
    mark.title =
      'structural — weight applied to lever-α only; engine reads on restart.';
    label.insertAdjacentElement('afterend', mark);
  }
}

// Plan §E.1/§E.2 — per-snapshot population stats. Sorted vectors
// power both the unicode-block histograms (rendered into #pop-hist-*)
// and the inspector card's percentile readout. Re-built once per
// cast snapshot — the agentic levers don't change values across
// per-tick events, only across snapshots.
const POP_STATS = {
  capability: { sorted: null, mu: 0, sigma: 0 },
  autonomy:   { sorted: null, mu: 0, sigma: 0 },
  trade_rate: { sorted: null, mu: 0, sigma: 0 },
};
const HIST_BAR_CHARS = ['▁', '▂', '▃', '▄', '▅', '▆', '▇', '█'];
const HIST_BUCKETS = 10;

function _renderHistRow(field, range, barsEl, statsEl) {
  const stats = POP_STATS[field];
  if (!stats || !stats.sorted || stats.sorted.length === 0) {
    if (barsEl) barsEl.textContent = '--';
    if (statsEl) statsEl.textContent = '--';
    return;
  }
  const [min, max] = range;
  const span = Math.max(1e-9, max - min);
  const counts = new Array(HIST_BUCKETS).fill(0);
  for (let i = 0; i < stats.sorted.length; i += 1) {
    let b = Math.floor(((stats.sorted[i] - min) / span) * HIST_BUCKETS);
    if (b < 0) b = 0;
    else if (b >= HIST_BUCKETS) b = HIST_BUCKETS - 1;
    counts[b] += 1;
  }
  const peak = Math.max(1, ...counts);
  let bars = '';
  for (let i = 0; i < HIST_BUCKETS; i += 1) {
    const norm = counts[i] / peak;
    const ci = Math.min(
      HIST_BAR_CHARS.length - 1,
      Math.floor(norm * HIST_BAR_CHARS.length),
    );
    bars += HIST_BAR_CHARS[ci];
  }
  if (barsEl) barsEl.textContent = bars;
  if (statsEl) {
    statsEl.textContent = `μ=${stats.mu.toFixed(2)} σ=${stats.sigma.toFixed(2)}`;
  }
}

function _statsFromArr(values) {
  if (values.length === 0) return { sorted: null, mu: 0, sigma: 0 };
  const sorted = values.slice().sort((a, b) => a - b);
  let sum = 0;
  for (let i = 0; i < sorted.length; i += 1) sum += sorted[i];
  const mu = sum / sorted.length;
  let varSum = 0;
  for (let i = 0; i < sorted.length; i += 1) {
    const d = sorted[i] - mu;
    varSum += d * d;
  }
  return { sorted, mu, sigma: Math.sqrt(varSum / sorted.length) };
}

function rebuildPopulationStats(snapshot) {
  if (!Array.isArray(snapshot) || snapshot.length === 0) return;
  const capVals = [];
  const autVals = [];
  const trmVals = [];
  // trade_rate is population-uniform in the engine — the lever sets a
  // single multiplier per cohort. Stamp every cast member with the
  // current lever value so the histogram bar shows a single spike
  // at the value the slider is set to, and σ stays at 0.
  const trmFromLever = _leverState['agent_trade_rate_multiplier'];
  for (const e of snapshot) {
    if (e && Number.isFinite(e.capability)) capVals.push(e.capability);
    if (e && Number.isFinite(e.autonomy))   autVals.push(e.autonomy);
    if (Number.isFinite(trmFromLever)) trmVals.push(trmFromLever);
  }
  POP_STATS.capability = _statsFromArr(capVals);
  POP_STATS.autonomy   = _statsFromArr(autVals);
  POP_STATS.trade_rate = _statsFromArr(trmVals);
  // Render into the toggles panel.
  _renderHistRow(
    'capability', [0.0, 1.0],
    document.getElementById('pop-hist-cap'),
    document.getElementById('pop-hist-cap-stats'),
  );
  _renderHistRow(
    'autonomy', [0.0, 1.0],
    document.getElementById('pop-hist-aut'),
    document.getElementById('pop-hist-aut-stats'),
  );
  _renderHistRow(
    'trade_rate', [0.5, 5.0],
    document.getElementById('pop-hist-trm'),
    document.getElementById('pop-hist-trm-stats'),
  );
}

// Plan §E.2 — percentile lookup against the latest snapshot's
// distribution. Returns an integer 0..100. Used by the inspector
// card to render "0.378 / p23" so the user reads the agent against
// the population the histograms describe. Returns -1 if the field
// hasn't been seen yet or the value isn't finite.
function populationPercentile(field, value) {
  if (!Number.isFinite(value)) return -1;
  const stats = POP_STATS[field];
  if (!stats || !stats.sorted || stats.sorted.length === 0) return -1;
  const a = stats.sorted;
  // Binary search for first element ≥ value; rank = that index.
  let lo = 0, hi = a.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (a[mid] < value) lo = mid + 1;
    else hi = mid;
  }
  const p = Math.round((lo / a.length) * 100);
  return p < 0 ? 0 : (p > 100 ? 100 : p);
}

// Plan §G.1 — restart-preview row. Computes:
//   α (lever)  — current displayed value (mapAlpha over _leverState)
//   α (after)  — projected, with pending structural overrides applied
//                (we already write structural changes into _leverState
//                synchronously in scheduleLeverUpdate's structural
//                branch, so the "after" is just mapAlpha over the
//                full state).
//   EBI est    — predictEbi(after) from the cached α→EBI curve.
// Hides when no structural changes are queued, or when the projected
// α leaves the curve's domain (so the estimate is honest about the
// bound).
function updateRestartPreview() {
  if (!leversPreviewRowEl) return;
  if (_structuralPending.size === 0) {
    leversPreviewRowEl.style.display = 'none';
    return;
  }
  const aAfter = mapAlpha(_leverState);
  let aText = '--';
  let aDelta = '';
  if (Number.isFinite(aAfter)) {
    aText = aAfter.toFixed(3);
    // Δ vs the current engine α.
    if (Number.isFinite(_lastEngineAlpha)) {
      const dAlpha = aAfter - _lastEngineAlpha;
      const sign = dAlpha >= 0 ? '+' : '';
      aDelta = ` (${sign}${dAlpha.toFixed(3)})`;
    }
  }
  if (leversPreviewAlphaEl) leversPreviewAlphaEl.textContent = aText + aDelta;
  let eText = '--';
  if (Number.isFinite(aAfter)) {
    const eAfter = predictEbi(aAfter);
    if (eAfter === null) {
      eText = `out of range [${CURVE_DOMAIN.min}, ${CURVE_DOMAIN.max}]`;
    } else {
      eText = eAfter.toFixed(eAfter >= 100 ? 0 : (eAfter >= 10 ? 1 : 2));
      if (Number.isFinite(_lastEngineEbi)) {
        const dE = eAfter - _lastEngineEbi;
        const sign = dE >= 0 ? '+' : '';
        eText += ` (${sign}${Math.abs(dE) >= 100 ? dE.toFixed(0)
                       : (Math.abs(dE) >= 10 ? dE.toFixed(1) : dE.toFixed(2))})`;
      }
    }
  }
  if (leversPreviewEbiEl) leversPreviewEbiEl.textContent = eText;
  leversPreviewRowEl.style.display = '';
}

function scheduleLeverUpdate(key, value) {
  _leverPending.set(key, value);
  _leverState[key] = value;
  updateAlphaHud();
  const prev = _leverTimers.get(key);
  if (prev !== undefined) clearTimeout(prev);
  _leverTimers.set(key, setTimeout(() => {
    _leverTimers.delete(key);
    flushLeverUpdates();
  }, LEVER_DEBOUNCE_MS));
}

// Refresh the α (lever) / α (engine) / Δ rows. Called on every
// lever change AND every onStep. Both inputs are independent: the
// engine value updates per tick from `step.alpha`; the lever value
// updates per drag.
function updateAlphaHud() {
  const lever = mapAlpha(_leverState);
  const engine = _lastEngineAlpha;
  if (hudAlphaLeverEl) {
    hudAlphaLeverEl.textContent = Number.isFinite(lever) ? lever.toFixed(3) : '--';
  }
  if (hudAlphaEl) {
    hudAlphaEl.textContent = Number.isFinite(engine) ? engine.toFixed(3) : '--';
  }
  if (hudAlphaGapRowEl && hudAlphaGapEl) {
    if (Number.isFinite(lever) && Number.isFinite(engine)) {
      const d = engine - lever;
      const showGap = Math.abs(d) > 0.05;
      hudAlphaGapRowEl.style.display = showGap ? '' : 'none';
      if (showGap) {
        const sign = d >= 0 ? '+' : '';
        hudAlphaGapEl.textContent = `${sign}${d.toFixed(2)}`;
      }
    } else {
      hudAlphaGapRowEl.style.display = 'none';
    }
  }
}

// Phase 5 §6.1 helpers. Both read the most recent step payload and
// repaint a small group of HUD rows. Kept in one place so the
// adversarial-check tests can call them with a stub step.
function updateRejectionMix(step) {
  // The engine's StepMetrics splits rejections into seven gates.
  // total_attempted in engine/core/metrics.py:606 does NOT include
  // rejected_compute (the field was added later in the compute
  // admission PR). Use the same six gates for the denominator the
  // engine uses so the "sum" diagnostic stays apples-to-apples, but
  // still display the compute share so the user sees the compute
  // gate's contribution.
  const cost   = Number.isFinite(step.rejected_cost)         ? step.rejected_cost         : 0;
  const market = Number.isFinite(step.rejected_market)       ? step.rejected_market       : 0;
  const align  = Number.isFinite(step.rejected_align)        ? step.rejected_align        : 0;
  const law    = Number.isFinite(step.rejected_law)          ? step.rejected_law          : 0;
  const comp   = Number.isFinite(step.rejected_compute)      ? step.rejected_compute      : 0;
  const perm   = Number.isFinite(step.rejected_permeability) ? step.rejected_permeability : 0;
  const reg    = Number.isFinite(step.rejected_regulator)    ? step.rejected_regulator    : 0;
  const real   = Number.isFinite(step.n_transactions_real)   ? step.n_transactions_real   : 0;
  const denom = real + cost + market + align + law + perm + reg;
  if (denom <= 0) {
    for (const el of [hudRejCostEl, hudRejMarketEl, hudRejAlignEl, hudRejLawEl,
                       hudRejComputeEl, hudRejPermEl, hudRejRegEl]) {
      if (el) el.textContent = '0.00';
    }
    if (hudRejSumRowEl) hudRejSumRowEl.style.display = 'none';
    return;
  }
  const fCost   = cost   / denom;
  const fMarket = market / denom;
  const fAlign  = align  / denom;
  const fLaw    = law    / denom;
  const fComp   = comp   / denom;
  const fPerm   = perm   / denom;
  const fReg    = reg    / denom;
  if (hudRejCostEl)   hudRejCostEl.textContent   = fCost.toFixed(2);
  if (hudRejMarketEl) hudRejMarketEl.textContent = fMarket.toFixed(2);
  if (hudRejAlignEl)  hudRejAlignEl.textContent  = fAlign.toFixed(2);
  if (hudRejLawEl)    hudRejLawEl.textContent    = fLaw.toFixed(2);
  if (hudRejComputeEl)hudRejComputeEl.textContent= fComp.toFixed(2);
  if (hudRejPermEl)   hudRejPermEl.textContent   = fPerm.toFixed(2);
  if (hudRejRegEl)    hudRejRegEl.textContent    = fReg.toFixed(2);
  // Adversarial check 6.x rejection-mix completeness — the six
  // engine-counted gates should sum to the engine's reported
  // total_rejected_fraction. Compute the actual sum and compare to
  // the implied value (1 − real / denom). Show a red ‼ row only
  // when the discrepancy exceeds 1e-6 — the gates rounding to two
  // decimal places means we compare the unrounded floats.
  const totalRejFraction = 1 - real / denom;
  const gateSum = fCost + fMarket + fAlign + fLaw + fPerm + fReg;
  const drift = Math.abs(gateSum - totalRejFraction);
  if (hudRejSumRowEl && hudRejSumEl) {
    if (drift > 1e-6) {
      hudRejSumRowEl.style.display = '';
      hudRejSumEl.textContent = drift.toExponential(1);
    } else {
      hudRejSumRowEl.style.display = 'none';
    }
  }
}

// Phase 5 §6.2 — EBI regime band labels. The bands match the
// spec table in spatial-sandbox-completeness.md §6.2 line for
// line; the adversarial check 6.x asserts the caption is the
// correct label for the current EBI.
const REGIME_BANDS = [
  // [upper-exclusive, label]
  [0.7, 'flat real economy'],
  [1.5, 'low baroque'],
  [2.5, 'calibrated reference'],
  [4.0, 'pricing reflexivity dominant'],
  [6.0, 'exo-baroque'],
  [Infinity, 'untethered'],
];
function regimeLabel(ebi) {
  if (!Number.isFinite(ebi)) return '--';
  for (const [upper, label] of REGIME_BANDS) {
    if (ebi < upper) return label;
  }
  return 'untethered';
}
function updateRegimeCaption(ebi) {
  if (!hudRegimeCaptionEl) return;
  hudRegimeCaptionEl.textContent = regimeLabel(ebi);
}

function flushLeverUpdates() {
  if (!stream?.runId || _leverPending.size === 0) return;
  const overrides = Object.fromEntries(_leverPending);
  _leverPending.clear();
  fetch(`/runs/${stream.runId}/update`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ overrides }),
  }).then((res) => {
    if (!res.ok) {
      res.text().then((t) => console.warn(`[lever] ${res.status}: ${t}`));
    }
  }).catch((err) => {
    console.warn(`[lever] network: ${err.message}`);
  });
}

// Sector hover detection. Cheap analytic ray-vs-sphere intersection
// followed by an O(K) nearest-anchor lookup — no full mesh raycast.
const _raycaster = new THREE.Raycaster();
const _ndcMouse = new THREE.Vector2();
let _lastHoveredSector = -1;

function onPointerMove(event) {
  if (!surface || !sectorsEnabled) return;
  const rect = renderer.domElement.getBoundingClientRect();
  _ndcMouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  _ndcMouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  _raycaster.setFromCamera(_ndcMouse, camera);
  // Inverse-apply the world-shape morph so the ray runs against the
  // original (unflattened) sphere. The morph is a Y-axis scale, so
  // dividing oy/dy by (1 - flatten) puts the ray in the substrate's
  // pre-morph frame. Direction must be re-normalised since scaling
  // a unit vector breaks the |d|=1 assumption baked into the
  // ray-vs-sphere formula below.
  const sy = 1 - _shapeFlatten;
  const ox = _raycaster.ray.origin.x;
  const oy = _raycaster.ray.origin.y / sy;
  const oz = _raycaster.ray.origin.z;
  let dx = _raycaster.ray.direction.x;
  let dy = _raycaster.ray.direction.y / sy;
  let dz = _raycaster.ray.direction.z;
  const dlen = Math.sqrt(dx * dx + dy * dy + dz * dz) || 1;
  dx /= dlen; dy /= dlen; dz /= dlen;
  const R = surface.radius ?? 700;
  const od = ox * dx + oy * dy + oz * dz;
  const oo = ox * ox + oy * oy + oz * oz;
  const disc = od * od - (oo - R * R);
  if (disc < 0) { setHoveredSector(-1); return; }
  const t = -od - Math.sqrt(disc);
  if (t < 0) { setHoveredSector(-1); return; }
  const px = ox + t * dx;
  const py = oy + t * dy;
  const pz = oz + t * dz;
  const n = Math.sqrt(px * px + py * py + pz * pz) || 1;
  const ux = px / n, uy = py / n, uz = pz / n;
  const anchors = surface.sectorAnchors;
  const K = surface.sectorCount ?? 12;
  let best = -1, bestDot = -Infinity;
  for (let k = 0; k < K; k += 1) {
    const a = ux * anchors[k * 3 + 0] + uy * anchors[k * 3 + 1] + uz * anchors[k * 3 + 2];
    if (a > bestDot) { bestDot = a; best = k; }
  }
  setHoveredSector(best, event.clientX, event.clientY);
}

function onPointerLeave() {
  setHoveredSector(-1);
  // Plan §F.2 — clear the firm hover state when the cursor exits
  // the canvas; otherwise the dimmed-other-firms render state
  // sticks around indefinitely.
  firms?.setHoveredFirm(-1);
}

// Plan §F.2 — firm-hover detection. The inspector card's pickAt
// helper does an O(cast) sweep against the substrate ray to find
// the nearest agent under the cursor; we throttle that to ≤ 10 Hz
// so a fast-moving cursor doesn't burn CPU on a 5000-agent O(n)
// loop every mouse frame. When the hovered agent has a non-
// negative firm_id, firms.js boosts that firm's spokes to the cap.
let _firmHoverPending = false;
let _firmHoverLastClientX = -1;
let _firmHoverLastClientY = -1;
const FIRM_HOVER_THROTTLE_MS = 100;
function onPointerMoveForFirmHover(ev) {
  _firmHoverLastClientX = ev.clientX;
  _firmHoverLastClientY = ev.clientY;
  if (_firmHoverPending) return;
  _firmHoverPending = true;
  setTimeout(() => {
    _firmHoverPending = false;
    if (!inspector || !firms) return;
    const pick = inspector.pickFromEvent?.({
      clientX: _firmHoverLastClientX,
      clientY: _firmHoverLastClientY,
    });
    if (!pick || pick.kind !== 'agent') {
      firms.setHoveredFirm(-1);
      return;
    }
    const e = _castByIdx.get(pick.id);
    const fid = (e && Number.isInteger(e.firm_id) && e.firm_id >= 0)
      ? e.firm_id : -1;
    firms.setHoveredFirm(fid);
  }, FIRM_HOVER_THROTTLE_MS);
}

function setHoveredSector(idx, mouseX = 0, mouseY = 0) {
  if (idx !== _lastHoveredSector) {
    surface?.setHoveredSector(idx);
    _lastHoveredSector = idx;
  }
  if (idx >= 0 && sectorLabelEl) {
    sectorLabelEl.style.display = 'block';
    sectorLabelEl.style.left = (mouseX + 14) + 'px';
    sectorLabelEl.style.top = (mouseY + 14) + 'px';
    sectorLabelEl.textContent = SECTOR_NAMES[idx] ?? `sector ${idx}`;
  } else if (sectorLabelEl) {
    sectorLabelEl.style.display = 'none';
  }
}

function onResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight, false);
  edges?.setResolution(window.innerWidth, window.innerHeight);
}

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  // Pause = halt all simulation activity. The camera (controls,
  // renderer) keeps running so the user can still orbit the frozen
  // scene, but the per-frame tickers — substrate altitude decay,
  // caterpillar steps, trade-arc tweens, firm-spoke and fold
  // re-anchoring, welfare meter — all sit out the frame. Engine
  // event handlers (onStep, onEdges, onCastSnapshot, onFolds) also
  // early-return on the paused flag, so the engine's continued
  // event stream doesn't mutate visible state either.
  if (!paused) {
    drainBumpQueue();
    tickShape();
    tickEasedHud();
    tickTradeStats();
    tickSparkle();
    surface?.tick();
    agents?.tick();
    edges?.tick();
    // Firms render after agents tick — spokes read each member's
    // current face from agents.currentFaceForIdx() so they must follow.
    firms?.tick();
    // Folds re-anchor to their agent's current face each frame, so
    // icospheres follow the caterpillar over their 150-frame life.
    folds?.tick();
    // Wealth-flow meter bars jitter every frame so the readout has
    // life even when the underlying shares are stable.
    updateWelfareMeter();
    // Top-left density readout. Updates each unpaused frame.
    updateDensityPanel();
  }
  renderer.render(scene, camera);

  // Trade counter updates moved to onEdges (event-driven) so the
  // readout works even when animate() is rAF-throttled in
  // backgrounded tabs.

  frameCount += 1;
  const now = performance.now();
  if (now - lastFpsT >= 1000) {
    fps = (frameCount * 1000) / (now - lastFpsT);
    frameCount = 0;
    lastFpsT = now;
  }
}

function setStatus(text, kind = '') {
  statusEl.textContent = text;
  statusEl.dataset.kind = kind;
}

// ─── HUD value smoother ─────────────────────────────────────────
// Maps a DOM element id to an eased value. onStep callers stash
// targets via easeHudValue(); tickEasedHud() runs every frame in
// animate() and writes the rendered value through the formatter.
// Kills the per-tick "jerk" that was making float readouts pulse
// at the engine cadence.
const _easedHud = new Map(); // id → { target, rendered, fmt, smooth }
const HUD_EASE_DEFAULT = 0.08;
function easeHudValue(id, target, fmt, smooth = HUD_EASE_DEFAULT) {
  let f = _easedHud.get(id);
  if (!f) {
    f = { target, rendered: target, fmt, smooth };
    _easedHud.set(id, f);
  } else {
    f.target = target;
    f.fmt = fmt;
    f.smooth = smooth;
  }
}
function tickEasedHud() {
  for (const [id, f] of _easedHud) {
    f.rendered += (f.target - f.rendered) * f.smooth;
    const el = document.getElementById(id);
    if (el) el.textContent = f.fmt(f.rendered);
  }
}

// ─── Trade stats panel ──────────────────────────────────────────
// Live per-tick rejection mix smoothed via a slow EMA so percentages
// roll over ~10 seconds instead of jerking with every engine tick.
// The sparkle canvas underneath shows individual pair outcomes as
// fading green/red dots, giving the panel a continuous activity feel
// without committing to the spatial-arc visualization the user
// pulled out.
const tsTarget   = { success: 0, cost: 0, market: 0, align: 0,
                     law: 0, compute: 0, perm: 0, reg: 0 };
const tsRendered = { success: 0, cost: 0, market: 0, align: 0,
                     law: 0, compute: 0, perm: 0, reg: 0 };
const TS_SMOOTH = 0.0046;   // ~2.5 s half-life at 60 fps → ~10 s tail
let _tsSeeded = false;
const tsEls = {
  success:      document.getElementById('ts-success'),
  fail:         document.getElementById('ts-fail'),
  cost:         document.getElementById('ts-cost'),
  market:       document.getElementById('ts-market'),
  align:        document.getElementById('ts-align'),
  law:          document.getElementById('ts-law'),
  compute:      document.getElementById('ts-compute'),
  perm:         document.getElementById('ts-perm'),
  reg:          document.getElementById('ts-reg'),
  cumulative:   document.getElementById('trade-stats-total-value'),
  splitSuccess: document.getElementById('ts-split-success'),
  splitFail:    document.getElementById('ts-split-fail'),
};

// Cumulative executed-trade counter, mirrors the wealth panel's
// cumulative-total readout. Counts every executed pair the engine
// reports per step.
let _tsCumulative = 0;

// Per-step success/fail rate sparkline histories. Drawn in the
// trades panel below the per-reason breakdown.
const TS_SPARK_LEN = 60;
const tsSparkHistory = { success: [], fail: [] };
const tsSparkRendered = { success: 0, fail: 0 };
const tsSparkCanvases = {
  success: document.getElementById('ts-spark-success'),
  fail:    document.getElementById('ts-spark-fail'),
};
const tsSparkValueEls = {
  success: document.getElementById('ts-spark-success-val'),
  fail:    document.getElementById('ts-spark-fail-val'),
};
const tsSparkColors = {
  success: 'rgb(64, 166, 82)',
  fail:    'rgb(199, 82, 82)',
};

function updateTradeStatsFromStep(step) {
  if (!step) return;
  const cost    = +step.rejected_cost         || 0;
  const market  = +step.rejected_market       || 0;
  const align   = +step.rejected_align        || 0;
  const law     = +step.rejected_law          || 0;
  const compute = +step.rejected_compute      || 0;
  const perm    = +step.rejected_permeability || 0;
  const reg     = +step.rejected_regulator    || 0;
  const real    = +step.n_transactions_real   || 0;
  const total = cost + market + align + law + compute + perm + reg + real;
  if (total <= 0) return;
  tsTarget.success = real    / total;
  tsTarget.cost    = cost    / total;
  tsTarget.market  = market  / total;
  tsTarget.align   = align   / total;
  tsTarget.law     = law     / total;
  tsTarget.compute = compute / total;
  tsTarget.perm    = perm    / total;
  tsTarget.reg     = reg     / total;
  if (!_tsSeeded) {
    Object.assign(tsRendered, tsTarget);
    _tsSeeded = true;
  }
  // Cumulative executed counter — wealth-panel-style headline.
  // step.n_transactions_real is a weighted prototype-pair count
  // (each prototype-pair stands for `pair_weight` real events),
  // so the running sum is naturally fractional. We round on
  // display so the headline reads as an integer count instead of
  // showing the engine's internal accounting precision.
  _tsCumulative += real;
  if (tsEls.cumulative) {
    tsEls.cumulative.textContent = Math.round(_tsCumulative).toLocaleString();
  }
}

function _drawTsSpark(name) {
  const canvas = tsSparkCanvases[name];
  if (!canvas) return;
  if (canvas.clientWidth === 0 || canvas.clientHeight === 0) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const targetW = Math.floor(canvas.clientWidth * dpr);
  const targetH = Math.floor(canvas.clientHeight * dpr);
  if (canvas.width !== targetW) canvas.width = targetW;
  if (canvas.height !== targetH) canvas.height = targetH;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const hist = tsSparkHistory[name];
  if (hist.length < 2) return;
  // Ease the rendered right-edge toward the latest sample so the
  // line glides continuously between engine ticks.
  const target = hist[hist.length - 1];
  tsSparkRendered[name] += (target - tsSparkRendered[name]) * 0.10;
  if (tsSparkValueEls[name]) {
    tsSparkValueEls[name].textContent =
      (tsSparkRendered[name] * 100).toFixed(1) + '%';
  }
  const w = canvas.width;
  const h = canvas.height;
  const n = hist.length;
  ctx.lineWidth = 1.5 * dpr;
  ctx.strokeStyle = tsSparkColors[name];
  ctx.beginPath();
  for (let k = 0; k < n; k += 1) {
    const x = (k / (TS_SPARK_LEN - 1)) * w;
    const sample = (k === n - 1) ? tsSparkRendered[name] : hist[k];
    const y = h - sample * h;
    if (k === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();
}

const _tsKeys = ['success', 'cost', 'market', 'align',
                 'law', 'compute', 'perm', 'reg'];
function _fmtPct(v) {
  if (!Number.isFinite(v)) return '--';
  const p = v * 100;
  return (p >= 10 ? p.toFixed(1) : p.toFixed(2)) + '%';
}
function tickTradeStats() {
  for (const k of _tsKeys) {
    tsRendered[k] += (tsTarget[k] - tsRendered[k]) * TS_SMOOTH;
  }
  if (tsEls.success) tsEls.success.textContent = _fmtPct(tsRendered.success);
  if (tsEls.fail)    tsEls.fail.textContent    = _fmtPct(1 - tsRendered.success);
  for (const k of ['cost', 'market', 'align', 'law', 'compute', 'perm', 'reg']) {
    if (tsEls[k]) tsEls[k].textContent = _fmtPct(tsRendered[k]);
  }
  // Drive the success/fail split bar widths from the same eased
  // values so the bar glides instead of stepping each tick.
  if (tsEls.splitSuccess) {
    tsEls.splitSuccess.style.width = (tsRendered.success * 100).toFixed(2) + '%';
  }
  if (tsEls.splitFail) {
    tsEls.splitFail.style.width = ((1 - tsRendered.success) * 100).toFixed(2) + '%';
  }
}

// ─── Sparkle ────────────────────────────────────────────────────
const sparkleCanvas = document.getElementById('trade-sparkle');
const sparkleCtx = sparkleCanvas ? sparkleCanvas.getContext('2d') : null;
const sparkleParticles = [];      // [{x, y, vy, age, ar, ag, ab}]
const SPARKLE_MAX = 320;
const SPARKLE_AGE_MAX = 180;      // ~3 s at 60 fps — long enough to
                                  // drift across the taller canvas

// Queue of pending spawn requests so a 3000-edge tick batch
// doesn't burst-spawn 40 particles in one frame (which produced
// the audible-feeling rhythm of "tick! 40 dots, silence, tick! 40
// dots"). Pushed-into here from onEdges; tickSparkle drains a
// fraction each frame so particles continually appear.
const sparkleSpawnQueue = [];   // each entry: bool rejected
const SPARKLE_SPAWN_FRACTION = 1 / 18;
const SPARKLE_SPAWN_MIN = 2;

function spawnSparkles(edges) {
  if (!sparkleCanvas || !edges || edges.length === 0) return;
  // Subsample so a large batch doesn't backlog the queue.
  const stride = Math.max(1, Math.ceil(edges.length / 60));
  for (let i = 0; i < edges.length; i += stride) {
    const e = edges[i];
    if (!e) continue;
    sparkleSpawnQueue.push(!!e.reject_reason);
  }
  // Hard cap so the queue can't accumulate beyond what we can
  // visually render anyway.
  if (sparkleSpawnQueue.length > 600) {
    sparkleSpawnQueue.splice(0, sparkleSpawnQueue.length - 600);
  }
}

function _spawnOne(rejected) {
  if (!sparkleCanvas) return;
  if (sparkleParticles.length >= SPARKLE_MAX) return;
  const w = sparkleCanvas.width;
  const h = sparkleCanvas.height;
  sparkleParticles.push({
    x: Math.random() * w,
    y: h - 1,
    // Vertical velocity tuned so a typical particle takes
    // ~SPARKLE_AGE_MAX frames to drift from h-1 to ~0 across the
    // (now taller) canvas.
    vy: -(0.6 + Math.random() * 0.6),
    age: 0,
    rejected,
  });
}

function tickSparkle() {
  if (!sparkleCtx || !sparkleCanvas) return;
  // Drain a slice of the spawn queue so particles trickle in at
  // frame rate instead of bursting once per tick.
  if (sparkleSpawnQueue.length > 0) {
    const target = Math.max(
      SPARKLE_SPAWN_MIN,
      Math.ceil(sparkleSpawnQueue.length * SPARKLE_SPAWN_FRACTION),
    );
    const n = Math.min(target, sparkleSpawnQueue.length);
    for (let k = 0; k < n; k += 1) {
      _spawnOne(sparkleSpawnQueue[k]);
    }
    sparkleSpawnQueue.splice(0, n);
  }
  const w = sparkleCanvas.width;
  const h = sparkleCanvas.height;
  sparkleCtx.clearRect(0, 0, w, h);
  for (let i = sparkleParticles.length - 1; i >= 0; i -= 1) {
    const p = sparkleParticles[i];
    p.y += p.vy;
    p.age += 1;
    if (p.age >= SPARKLE_AGE_MAX || p.y < -1) {
      sparkleParticles.splice(i, 1);
      continue;
    }
    const alpha = 1 - (p.age / SPARKLE_AGE_MAX);
    if (p.rejected) {
      // Failed trades render as small black X marks. Shape alone
      // distinguishes success/fail (colour-blind friendly); black
      // also reads well against the cream substrate of the panel.
      sparkleCtx.strokeStyle = `rgba(26,20,18,${alpha.toFixed(3)})`;
      sparkleCtx.lineWidth = 1.2;
      sparkleCtx.beginPath();
      sparkleCtx.moveTo(p.x - 2.2, p.y - 2.2);
      sparkleCtx.lineTo(p.x + 2.2, p.y + 2.2);
      sparkleCtx.moveTo(p.x + 2.2, p.y - 2.2);
      sparkleCtx.lineTo(p.x - 2.2, p.y + 2.2);
      sparkleCtx.stroke();
    } else {
      sparkleCtx.fillStyle = `rgba(64,166,82,${alpha.toFixed(3)})`;
      sparkleCtx.beginPath();
      sparkleCtx.arc(p.x, p.y, 1.8, 0, Math.PI * 2);
      sparkleCtx.fill();
    }
  }
}

// Drain a slice of the substrate-bump queue each frame. Spreads
// engine-batched deposits across ~30 rAF frames so a 3000-edge tick
// doesn't fire 3000 bumps in a single frame; combined with the
// pending-pool drain in surface.js, the visible deformation stays
// continuous instead of pulsing at the engine tick rate.
function drainBumpQueue() {
  if (paused || _bumpQueue.length === 0 || !surface || !agents) return;
  const target = Math.max(
    BUMP_QUEUE_DRAIN_MIN,
    Math.ceil(_bumpQueue.length * BUMP_QUEUE_DRAIN_FRACTION),
  );
  const n = Math.min(target, _bumpQueue.length);
  for (let i = 0; i < n; i += 1) {
    const e = _bumpQueue[i];
    if (!e) continue;
    const a = e.proto_a ?? -1;
    const b = e.proto_b ?? -1;
    if (e.reject_reason) {
      if (a >= 0) {
        const f = agents.currentFaceForIdx(a);
        if (f >= 0) surface.bumpAltitude(f, -REJECT_BUMP);
      }
      if (b >= 0) {
        const f = agents.currentFaceForIdx(b);
        if (f >= 0) surface.bumpAltitude(f, -REJECT_BUMP);
      }
    } else if (e.executed) {
      const surplus = Math.max(0, e.real_surplus ?? 0);
      const bump = TRADE_BUMP_BASE * (1.0 + Math.sqrt(surplus));
      if (a >= 0) {
        const f = agents.currentFaceForIdx(a);
        if (f >= 0) surface.bumpAltitude(f, bump);
      }
      if (b >= 0) {
        const f = agents.currentFaceForIdx(b);
        if (f >= 0) surface.bumpAltitude(f, bump);
      }
    }
  }
  _bumpQueue.splice(0, n);
}

// Top-left density readout. Surfaces the substrate face count, the
// live cast count, and caterpillar-per-1,000-faces ratio — the
// scaling knob the prior conversation flagged as the cause of "more
// agents but same density" perception.
function updateDensityPanel() {
  if (!densityCastEl && !densityPer1kEl) return;
  const sd = surface?.diagnostics?.();
  const ad = agents?.diagnostics?.();
  const faces = sd?.faceCount ?? 0;
  const cast = ad?.castCount ?? 0;
  if (densityCastEl) {
    densityCastEl.textContent = cast > 0
      ? cast.toLocaleString()
      : '--';
  }
  if (densityPer1kEl) {
    if (faces > 0 && cast > 0) {
      const ratio = (cast / faces) * 1000;
      densityPer1kEl.textContent = ratio >= 10
        ? ratio.toFixed(1)
        : ratio.toFixed(2);
    } else {
      densityPer1kEl.textContent = '--';
    }
  }
}

function logSummary() {
  const sd = surface?.diagnostics?.() ?? {};
  const ad = agents?.diagnostics?.() ?? {};
  const ed = edges?.diagnostics?.() ?? {};
  const fd = firms?.diagnostics?.() ?? {};
  const fold = folds?.diagnostics?.() ?? {};
  console.log(
    `[stream] tick=${counters.step}  cast=${counters.cast}  fps=${fps.toFixed(1)}  ` +
    `faces=${sd.faceCount}  ` +
    `agents=${ad.castCount}  segments=${ad.segments}  firms=${ad.firmCount}  ` +
    `firmsCast=${fd.n_firms}/${fd.n_members}m/${fd.n_cross_sector}cs  ` +
    `folds=${fold.activeCount}  ` +
    `arcs=${ed.lineCount}`,
  );
}

// Per-frame shape-morph driver. Smoothly eases the rendered
// _shapeFlatten/_shapeChaos toward the per-tick targets, then
// overlays a slow multi-frequency breathing modulation so the
// shape never sits at a perfectly fixed value between engine
// ticks. Both together eliminate the "tick-jump-sit" rhythm the
// engine cadence would otherwise impose on the visual.
function tickShape() {
  _shapeFlatten += (_shapeFlattenTarget - _shapeFlatten) * SHAPE_SMOOTH_RATE;
  _shapeChaos   += (_shapeChaosTarget   - _shapeChaos)   * SHAPE_SMOOTH_RATE;
  applyShape();
}

// Apply the world-shape morph to every mesh whose vertices live in
// scene-space — substrate, caterpillars, indicator dots, tethers,
// trade arcs. mesh.scale.y is the cheapest way to do this; no
// shader changes, no per-vertex JS rewrites. Sector hover (which
// does its own analytic ray-vs-sphere) inverse-transforms the ray
// in onPointerMove so hit detection still resolves on the original
// sphere geometry.
function applyShape() {
  // Slow multi-frequency breathing overlay — coprime-ish periods so
  // the wave never quite repeats. Amplitudes are small (~2%) so the
  // overlay reads as life, not as a separate animation layer.
  const t = performance.now() * 0.001;
  const breath = (
    Math.sin(t * 0.41) * 0.55 +
    Math.sin(t * 0.73 + 1.2) * 0.30 +
    Math.sin(t * 1.19 + 2.7) * 0.15
  );
  const flatBreath = breath * SHAPE_BREATH_AMP_FLATTEN;
  const chaosBreath = breath * SHAPE_BREATH_AMP_CHAOS;
  let renderedFlatten = _shapeFlatten + flatBreath;
  if (renderedFlatten < 0) renderedFlatten = 0;
  else if (renderedFlatten > SHAPE_FLATTEN_MAX) renderedFlatten = SHAPE_FLATTEN_MAX;
  let renderedChaos = _shapeChaos + chaosBreath;
  if (renderedChaos < 0) renderedChaos = 0;
  else if (renderedChaos > 1) renderedChaos = 1;
  const sy = 1 - renderedFlatten;
  if (surface) {
    surface.mesh.scale.y = sy;
    surface.setChaos(renderedChaos);
  }
  if (agents) {
    agents.mesh.scale.y = sy;
    if (agents.indicatorMesh) agents.indicatorMesh.scale.y = sy;
    if (agents.tetherMesh) agents.tetherMesh.scale.y = sy;
  }
  if (edges) edges.mesh.scale.y = sy;
  if (firms) firms.mesh.scale.y = sy;
  if (firms?.markerMesh) firms.markerMesh.scale.y = sy;
  if (folds) folds.mesh.scale.y = sy;
  if (clusterOverlay) clusterOverlay.group.scale.y = sy;
}

// Stream-age refresher. setInterval is also background-throttled,
// but only to ~1 Hz (not stalled like rAF), so this still updates
// the HUD readout often enough to tell live vs throttled at a
// glance. Started in onHello, cleared in onTerminal/onConnectError.
let streamAgeTimer = null;
const STREAM_STALL_MS = 5000;
function updateStreamAge() {
  if (!hudStreamEl) return;
  const hidden = typeof document !== 'undefined' && document.hidden;
  if (_lastEdgeT === 0) {
    hudStreamEl.textContent = hidden ? 'bg · --' : '--';
    hudStreamEl.title = hidden
      ? 'tab is backgrounded — render rate reduced; engine and stream are unaffected.'
      : 'awaiting first edge event from the engine.';
    return;
  }
  const ageMs = performance.now() - _lastEdgeT;
  // Phase 6 §7.5: distinguish three states.
  //   live       — fresh edges arriving
  //   bg · live  — same, but the browser is throttling rAF
  //   STALL      — no edges for ≥ 5 s; engine may have stopped
  let text;
  let title;
  if (ageMs >= STREAM_STALL_MS) {
    text = 'STALL';
    title = 'no edge events for 5+ seconds — engine may have stopped.';
  } else if (hidden) {
    text = ageMs < STREAM_STALE_MS
      ? 'bg · live'
      : 'bg · ' + (ageMs / 1000).toFixed(1) + 's';
    title = 'tab is backgrounded — render rate reduced; engine and stream are unaffected.';
  } else if (ageMs < STREAM_STALE_MS) {
    text = 'live';
    title = 'edges arriving from the live engine.';
  } else {
    text = (ageMs / 1000).toFixed(1) + 's';
    title = `${(ageMs / 1000).toFixed(1)} s since the last edge event — connection may be slow.`;
  }
  hudStreamEl.textContent = text;
  hudStreamEl.title = title;
}

function onHello(meta) {
  setStatus(`live · ${theme.name} · ${meta.scenario}`, 'live');
  summaryTimer = setInterval(logSummary, 1000);
  if (streamAgeTimer === null) streamAgeTimer = setInterval(updateStreamAge, 500);
}

function onStep(step) {
  if (paused) return;
  counters.step += 1;
  // Plan §8.3 — forward to dev/checks if it's running. The hook
  // is a global function published by enableDevChecks.
  if (typeof window !== 'undefined' && window.__devChecksOnStep) {
    window.__devChecksOnStep(step);
  }
  updateSteadyState(step);
  updateSectorTopography(step);
  // Update the trade-stats panel targets. tickTradeStats() in
  // animate() eases the rendered values toward these with a slow
  // EMA so the percentages roll over ~10 s instead of jerking
  // every tick.
  updateTradeStatsFromStep(step);
  setStatus(`${theme.name} · tick ${step.step}`, 'live');

  pushStepArrival(performance.now() * 0.001);
  if (Number.isFinite(step.alpha)) {
    _lastEngineAlpha = step.alpha;
    updateAlphaHud();
  }
  // Per-tick EBI = nominal_step / real_step. Reads the *current*
  // regime instead of the cumulative ratio, which can only ratchet
  // up. Falls through when real_step is unusable.
  if (hudEbiEl) {
    const nstep = step.nominal_gdp_step;
    const rstep = step.real_welfare_step;
    if (Number.isFinite(nstep) && Number.isFinite(rstep) && rstep > 0) {
      const ebi = nstep / rstep;
      hudEbiEl.textContent = ebi.toFixed(3);
      _ebiSmoothed = _ebiSmoothed * 0.94 + ebi * 0.06;
      // Plan §G.1 — track engine EBI so the restart-preview row can
      // show ΔEBI against the live reading. Uses the same per-step
      // nominal/real ratio the HUD displays so the two numbers line
      // up exactly.
      _lastEngineEbi = ebi;
      // Flatten ramp on the low side: EBI < 2.0 starts compressing
      // toward disc; at EBI 0.5 (or below) the sphere is fully flat.
      // Smoothstep eases the linear ramp into an S-curve so the
      // shape doesn't ride a perfectly flat slope across the band.
      const flatT0 = (SHAPE_FLATTEN_EBI_HIGH - _ebiSmoothed)
        / (SHAPE_FLATTEN_EBI_HIGH - SHAPE_FLATTEN_EBI_LOW);
      const flatT = Math.max(0, Math.min(1, flatT0));
      const flatEased = flatT * flatT * (3 - 2 * flatT);
      _shapeFlattenTarget = flatEased * SHAPE_FLATTEN_MAX;
      // Chaos ramp on the high side: EBI > 2.0 starts adding lobes;
      // saturates at EBI 5.0.
      const chaosT0 = (_ebiSmoothed - SHAPE_CHAOS_EBI_LOW)
        / (SHAPE_CHAOS_EBI_HIGH - SHAPE_CHAOS_EBI_LOW);
      const chaosT = Math.max(0, Math.min(1, chaosT0));
      _shapeChaosTarget = chaosT * chaosT * (3 - 2 * chaosT);
      // Note: applyShape() is no longer called here. tickShape() in
      // animate() interpolates _shapeFlatten/_shapeChaos toward the
      // targets each frame so the morph rides continuously instead
      // of jumping at engine-tick boundaries.
    }
  }
  if (Number.isFinite(step.real_welfare_step)) {
    // EMA-smooth the welfare-step value so it glides instead of
    // jerking once per engine tick. The eased value is rendered by
    // tickEasedHud() in animate().
    easeHudValue('hud-welfare-step', step.real_welfare_step,
      (v) => (v >= 0 ? '+' : '') + v.toFixed(1));
  }
  if (Number.isFinite(step.gini_wealth)) {
    easeHudValue('hud-gini', step.gini_wealth, (v) => v.toFixed(3));
  }
  if (hudTpsEl) hudTpsEl.textContent = ticksPerSec().toFixed(1);

  // Phase 5 §6.1 — folds and compute. FOLDS is the active mesh
  // count from the folds module (adversarial check 6.x folds-count
  // requires it to equal __sandbox.folds().activeCount). COMPUTE
  // reads compute_budget_remaining as a fraction of nominal budget;
  // the engine emits the absolute carryover, which is ∈ [0, ~budget]
  // — we display the raw value for accuracy.
  if (hudFoldsEl) {
    const af = folds?.activeCount?.() ?? 0;
    hudFoldsEl.textContent = String(af);
  }
  if (hudComputeEl && Number.isFinite(step.compute_budget_remaining)) {
    hudComputeEl.textContent = step.compute_budget_remaining.toFixed(2);
  }

  // Phase 5 §6.1 — rejection mix. The engine emits each `rejected_*`
  // as the per-tick weight that the gate filtered out (not a
  // fraction). Sum + n_tx_real is the total attempted pair-weight
  // for the tick. We display each gate as a fraction of total.
  // Adversarial check 6.x rejection-mix completeness asserts the
  // displayed shares sum to within 1e-6 of the total fraction.
  updateRejectionMix(step);

  // Phase 5 §6.2 — EBI regime caption. One of six bands sourced
  // from the band table in spatial-sandbox-completeness.md §6.2.
  updateRegimeCaption(step.exo_baroque_index);
  // Phase 6 §7.4 — EBI shape-morph legend glyph.
  updateEbiLegend(step.exo_baroque_index);

  // Phase 2 §3.1: run Louvain over the rolling edge buffer. Decays
  // are applied inside tick() so call once per engine step (not per
  // animation frame).
  clusters?.tick();
  // Phase 2 §3.2 follow-on: dispatch a worker-side Louvain every
  // CLUSTER_WORKER_PERIOD ticks, but only when the prior job has
  // returned. _workerInflight gates the post so we don't queue
  // multiple jobs if the worker is slow.
  dispatchClusterWorker();
  // Phase 2 §3.2: feed the fresh partition through the cross-tick
  // identity tracker. cluster_labels.js matches each raw cabal to
  // its best Jaccard predecessor, assigns stable ids, and runs the
  // promotion gates. The overlay and HUD read from clusterLabels
  // so cabal hue + opacity track stable identity, not the raw
  // Louvain id (which can re-label between passes).
  if (clusters && clusterLabels) {
    clusterLabels.update(clusters.partition());
  }
  if (hudCabalsEl || hudSyndicatesEl) {
    const d = clusterLabels?.diagnostics?.() ?? { cabals: 0, syndicates: 0 };
    if (hudCabalsEl) hudCabalsEl.textContent = String(d.cabals);
    if (hudSyndicatesEl) hudSyndicatesEl.textContent = String(d.syndicates);
  }
  // Plan §C.1 — Louvain pipeline diagnostic readouts. Reads from
  // clusters.diagnostics() (primary partition source) and
  // clusterOverlay.diagnostics() (renderer floor). Splits the "0/0"
  // cliff that the reviewer cannot distinguish into three failure
  // modes: engine produces no structure / detector below floor /
  // overlay never wires up.
  if (hudEdgesInEl || hudCandidatesEl || hudRenderFloorEl) {
    const cd = clusters?.diagnostics?.() ?? { edgesIn: 0, candidates: 0 };
    const od = clusterOverlay?.diagnostics?.() ?? { minCabalRenderSize: 0 };
    if (hudEdgesInEl) hudEdgesInEl.textContent = String(cd.edgesIn ?? 0);
    if (hudCandidatesEl) hudCandidatesEl.textContent = String(cd.candidates ?? 0);
    if (hudRenderFloorEl) {
      hudRenderFloorEl.textContent =
        `${od.minCabalRenderSize ?? 0} / ${cd.candidates ?? 0}`;
    }
  }
  // Phase 2 §3.3: rebuild the cabal-hull overlay from the stable-id
  // partition. The overlay reads each cluster's status (cabal vs
  // syndicate) and tints accordingly.
  if (clusterLabels && clusterOverlay) {
    clusterOverlay.update(clusterLabels.partition(), clusterLabels);
  }

  // Phase 6 §7.3 — split stock bar + 60-tick flow sparklines fed
  // strictly per onStep. Independent of the per-frame render loop
  // so background-throttled tabs still see correct state on resume.
  updateWealthStock(step);
  pushSparklineSamples(step);
  if (typeof step.real_welfare_cumulative === 'number') {
    cumulativeWealth = step.real_welfare_cumulative;
    if (welfareTotalEl) welfareTotalEl.textContent = Math.round(cumulativeWealth).toLocaleString();
    if (cumulativeBarFillEl) {
      const frac = Math.max(0, Math.min(1,
        Math.max(0, cumulativeWealth) / CUM_WEALTH_BAR_CAP));
      cumulativeBarFillEl.style.width = (frac * 100).toFixed(2) + '%';
    }
  }
  // Pass 19b: per-step modulation re-enabled with much smaller
  // coefficients than Pass 19. The setters also clamp on the surface
  // side as a second line of defence.
  if (surface) {
    const ebi = step.exo_baroque_index;
    if (Number.isFinite(ebi)) {
      // Plan §B.2 — EBI-driven altitude scale via the existing
      // _ebiSmoothed EMA (same one the shape-morph reads), so per-
      // tick jitter doesn't whiplash the substrate's amplitude.
      // Formula:
      //   uAltitudeScale = 0.6 + 1.4 * smoothstep(2.0, 4.0, ebiSmoothed)
      // At EBI≈1.5 (disc band): bumps barely visible.
      // At EBI≈3.5 (lobed band): bumps register as lobe-surface texture.
      // The smoothstep is computed against _ebiSmoothed which is
      // updated below in the shape-morph block.
      const t = (_ebiSmoothed - 2.0) / 2.0;
      const u = t < 0 ? 0 : (t > 1 ? 1 : t);
      const ss = u * u * (3 - 2 * u);
      surface.setAltitudeScale(0.6 + 1.4 * ss);
    }
    const depth = step.fold_max_depth;
    if (Number.isFinite(depth)) {
      surface.setFoldCascadeMultiplier(1.0 + depth * 0.25);
    }
    const rejectFrac = (
      (step.rejected_law ?? 0) +
      (step.rejected_market ?? 0) +
      (step.rejected_align ?? 0) +
      (step.rejected_cost ?? 0) +
      (step.rejected_compute ?? 0) +
      (step.rejected_permeability ?? 0) +
      (step.rejected_regulator ?? 0)
    );
    const ebiBulge = Number.isFinite(ebi) ? Math.max(0, ebi - 1.0) * 0.02 : 0;
    const rejectContract = rejectFrac * 0.03;
    surface.setGlobalAltitude(ebiBulge - rejectContract);
  }
}

function onCastSnapshot(ev) {
  if (paused) return;
  counters.cast += 1;
  agents?.handleCastSnapshot(ev.snapshot);
  firms?.handleCastSnapshot(ev.snapshot);
  folds?.handleCastSnapshot(ev.snapshot);
  clusters?.ingestSnapshot(ev.snapshot);
  // Phase 6 §7.1 — keep a flat idx → entry index so the inspector
  // and other consumers can read agent state without re-walking
  // the snapshot array.
  if (Array.isArray(ev.snapshot)) {
    _castByIdx.clear();
    for (const e of ev.snapshot) {
      if (e && Number.isInteger(e.idx)) _castByIdx.set(e.idx, e);
    }
    // Plan §E.1/§E.2 — rebuild the per-snapshot population stats
    // so the histograms and inspector percentile read from the
    // distribution the user actually sees on this tick.
    rebuildPopulationStats(ev.snapshot);
  }
  inspector?.refresh();
  if (counters.cast === 1) setProgress(1.0, 'live');
}

function onFolds(ev) {
  if (paused) return;
  folds?.handleFolds(ev);
}

// Trade-driven altitude bumps. Successful pairs push both partners'
// faces outward (scaled by real_surplus); rejected pairs ding them
// inward. Both directions get their per-event signal from the live
// pair stream, which has hundreds of events per tick — much denser
// than the snapshot-to-snapshot wealth-delta channel that was
// driving positive growth before.
const REJECT_BUMP = 0.0015;
const TRADE_BUMP_BASE = 0.009;
// Spread substrate-bump processing across ~30 frames so the
// engine's batched tick doesn't dump 3000 deposits in a single
// frame and then go quiet for 0.5 s. Cluster ingest and arc
// creation still happen at batch boundaries; only the substrate-
// deformation deposits are deferred.
const _bumpQueue = [];
const BUMP_QUEUE_DRAIN_FRACTION = 1 / 30;
const BUMP_QUEUE_DRAIN_MIN = 8;

function onEdges(ev) {
  if (paused) return;
  if (!surface || !agents || !ev.edges) return;
  // Feed the sparkle canvas in the trade-stats panel — each pair
  // outcome spawns one green/red dot that drifts up and fades.
  spawnSparkles(ev.edges);
  // Push every edge into the bump queue. animate() drains a slice
  // of this each frame so deformation deposits trickle in
  // continuously instead of arriving all at once.
  for (let i = 0; i < ev.edges.length; i += 1) {
    if (ev.edges[i]) _bumpQueue.push(ev.edges[i]);
  }
  // Phase 2 §3.1: feed pair samples into the rolling cluster
  // detector. Reject pairs and weight-0 pairs are filtered inside
  // ingestEdges; here we hand the whole batch.
  clusters?.ingestEdges(ev.edges);
  // Draw the live trade arcs (blue success, red reject) over the
  // current substrate. Replaces previous snapshot's lines.
  edges?.handleEdges(ev.edges);
  if (ev.edges) {
    cumulativeTrades += ev.edges.length;
    // Update the counter DOM here instead of in animate() — animate
    // is rAF-throttled when the tab is in the background, but SSE
    // events keep landing, so a counter-from-rAF reads "0" forever
    // for backgrounded users.
    if (tradeCounterEl) tradeCounterEl.textContent = cumulativeTrades.toLocaleString();
    _lastEdgeT = performance.now();
  }
}

function onTerminal(kind) {
  if (summaryTimer) { clearInterval(summaryTimer); summaryTimer = null; }
  if (streamAgeTimer) { clearInterval(streamAgeTimer); streamAgeTimer = null; }
  setStatus(`${kind}`, kind);
}

function onConnectError() {
  if (summaryTimer) { clearInterval(summaryTimer); summaryTimer = null; }
  if (streamAgeTimer) { clearInterval(streamAgeTimer); streamAgeTimer = null; }
  setStatus('stream closed', 'error');
}

// Apply a scenario preset. The preset's `targets` dict maps lever
// data-key → target value. The flow:
//
//   1. Sort targets into structural (kind="structural") and live
//      (kind="live") by reading the matching DOM control's
//      data-kind attribute.
//   2. If any structural target differs from the current control
//      value, snap the structural controls to their targets, queue
//      them in _structuralPending, and call restartRun(). The
//      restart picks up the structural overrides on the new engine
//      run; live controls stay at their current values during the
//      restart (the engine resets them to scenario defaults too,
//      but we tween them up after).
//   3. Tween live controls from their post-restart values to the
//      preset targets over PRESET_TWEEN_MS. Each frame dispatches
//      an `input` event on the slider, which fires the regular
//      lever listener — formatting + debounced POST /update both
//      get the synthetic edit just like a manual drag.
//   4. The title under the sphere flips to the preset name on
//      click; the steady-state detector resets so a prior STEADY
//      STATE line doesn't carry into the new run.
const PRESET_TWEEN_MS = 5000;

async function applyPreset(name) {
  const preset = PRESETS[name];
  if (!preset || _presetTweenActive) return;
  _activePreset = { name, title: preset.title };
  setSphereTitle(preset.title);
  resetSteadyState();
  if (btnStartEl) btnStartEl.disabled = true;
  if (presetSelectEl) presetSelectEl.disabled = true;
  _presetTweenActive = true;
  try {
    const panel = document.getElementById('levers-panel');
    if (!panel) return;
    const structuralChanges = [];
    const liveChanges = [];
    for (const [key, target] of Object.entries(preset.targets)) {
      const el = panel.querySelector(`[data-key="${key}"]`);
      if (!el) continue;
      const kind = el.dataset.kind || 'live';
      if (el.tagName.toLowerCase() === 'select') {
        // Selects are always structural in the current panel; snap
        // immediately and route through the queue. Boolean targets
        // are represented as "on"/"off" strings in the DOM.
        const raw = typeof target === 'boolean' ? (target ? 'on' : 'off') : String(target);
        structuralChanges.push({ el, key, raw });
      } else {
        const numeric = Number(target);
        if (!Number.isFinite(numeric)) continue;
        if (kind === 'structural') {
          structuralChanges.push({ el, key, value: numeric });
        } else {
          liveChanges.push({ el, key, value: numeric });
        }
      }
    }
    if (structuralChanges.length > 0) {
      for (const c of structuralChanges) {
        if (c.el.tagName.toLowerCase() === 'select') {
          c.el.value = c.raw;
          c.el.dispatchEvent(new Event('change', { bubbles: true }));
        } else {
          c.el.value = String(c.value);
          c.el.dispatchEvent(new Event('input', { bubbles: true }));
        }
      }
      await restartRun();
    }
    if (liveChanges.length > 0) {
      const starts = liveChanges.map((c) => parseFloat(c.el.value));
      const t0 = performance.now();
      await new Promise((resolve) => {
        function step() {
          const now = performance.now();
          const t = Math.min(1, (now - t0) / PRESET_TWEEN_MS);
          // Smoothstep for a less mechanical animation.
          const eased = t * t * (3 - 2 * t);
          for (let i = 0; i < liveChanges.length; i += 1) {
            const c = liveChanges[i];
            const v = starts[i] + (c.value - starts[i]) * eased;
            c.el.value = String(v);
            c.el.dispatchEvent(new Event('input', { bubbles: true }));
          }
          if (t >= 1) resolve();
          else requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
      });
    }
  } finally {
    _presetTweenActive = false;
    if (btnStartEl) btnStartEl.disabled = false;
    if (presetSelectEl) presetSelectEl.disabled = false;
  }
}

// Cancel the live run, reset dashboard state, and start a fresh
// run with the current slider values applied as overrides. This is
// the only way to clear path-dependent state (accumulated folds,
// wealth gini, etc.) so the user can see the steady-state effect
// of a lever set rather than fighting whatever the prior trajectory
// dragged the world into.
let _restarting = false;
async function restartRun() {
  if (_restarting) return;
  _restarting = true;
  // Disable the in-place reset button while the run is being torn
  // down + rebuilt. btn-restart (hard page reload) stays clickable
  // as an escape hatch in case the in-place reset wedges.
  if (btnResetEl) btnResetEl.disabled = true;
  setStatus(`${theme.name} · resetting…`, '');

  // Restart override payload is the union of:
  //   - every live numeric lever's current value (so the new run
  //     starts at the same point the user has on screen);
  //   - every queued structural lever change (drained here).
  // `scale` is a RunRequest top-level field, not an override key —
  // separated out so RunRequest carries it as a sibling of overrides.
  const overrides = {};
  let scaleOverride = null;
  const panel = document.getElementById('levers-panel');
  if (panel) {
    for (const el of panel.querySelectorAll('[data-key]')) {
      const key = el.dataset.key;
      if (key === 'scale') {
        scaleOverride = el.value;
        continue;
      }
      if (el.tagName.toLowerCase() === 'select') {
        const raw = el.value;
        const transform = LEVER_STRING_TRANSFORM[key];
        overrides[key] = transform ? transform(raw) : raw;
      } else {
        const v = parseFloat(el.value);
        if (Number.isFinite(v)) overrides[key] = v;
      }
    }
  }
  // Structural pending takes precedence (the user's most recent
  // edits should win over the seeded DOM values).
  for (const [k, v] of _structuralPending) overrides[k] = v;
  _structuralPending.clear();
  if (leversPendingRowEl) leversPendingRowEl.style.display = 'none';
  if (leversPreviewRowEl) leversPreviewRowEl.style.display = 'none';

  if (stream) {
    stream.cancel();
    stream = null;
  }

  agents?.reset();
  surface?.resetHeightmap();
  edges?.reset();
  firms?.reset();
  folds?.reset();
  clusters?.reset();
  clusterLabels?.reset();
  clusterOverlay?.reset();
  // Invalidate in-flight worker jobs so a stale reply doesn't
  // bleed secondary Jaccard from the prior run into the new one.
  _workerInflight = false;
  _workerJobId += 1;
  _workerTicksUntilNext = 0;

  counters.step = 0;
  counters.cast = 0;
  cumulativeWealth = 0;
  cumulativeTrades = 0;
  resetSteadyState();
  resetSectorTopography();
  // Reset the trades-panel state so the cumulative counter and
  // success/fail sparklines start fresh on Reset.
  _tsCumulative = 0;
  _tsSeeded = false;
  if (tsEls.cumulative) tsEls.cumulative.textContent = '0';
  if (tsEls.splitSuccess) tsEls.splitSuccess.style.width = '0%';
  if (tsEls.splitFail)    tsEls.splitFail.style.width    = '0%';
  _stepArrivalCount = 0;
  _stepArrivalI = 0;
  _ebiSmoothed = 2.0;
  _shapeFlatten = 0;
  _shapeChaos = 0;
  _shapeFlattenTarget = 0;
  _shapeChaosTarget = 0;
  _lastEdgeT = 0;
  applyShape();
  if (hudStreamEl) hudStreamEl.textContent = '--';
  if (welfareTotalEl) welfareTotalEl.textContent = '0';
  if (cumulativeBarFillEl) cumulativeBarFillEl.style.width = '0%';
  if (tradeCounterEl) tradeCounterEl.textContent = '0';
  for (const id of [
    'hud-alpha', 'hud-alpha-lever', 'hud-alpha-gap', 'hud-ebi',
    'hud-welfare-step', 'hud-gini', 'hud-tps',
    'hud-folds', 'hud-compute',
    'hud-rej-cost', 'hud-rej-market', 'hud-rej-align', 'hud-rej-law',
    'hud-rej-compute', 'hud-rej-perm', 'hud-rej-reg', 'hud-rej-sum',
    'hud-regime-caption', 'hud-cabals', 'hud-syndicates',
  ]) {
    const el = document.getElementById(id);
    if (el) el.textContent = '--';
  }
  if (hudAlphaGapRowEl) hudAlphaGapRowEl.style.display = 'none';
  if (hudRejSumRowEl) hudRejSumRowEl.style.display = 'none';
  _lastEngineAlpha = NaN;
  // Phase 6 §7.3 — restart resets sparkline history and the
  // stock-bar widths so the new run reads from zero.
  if (sparklineRows) {
    for (const r of sparklineRows) {
      r.history.length = 0;
      r.lastDrawnStep = -1;
      r.valueEl.textContent = '--';
      const ctx = r.canvas.getContext('2d');
      if (ctx) ctx.clearRect(0, 0, r.canvas.width, r.canvas.height);
    }
  }
  if (wealthStockHumansEl) wealthStockHumansEl.style.width = '0%';
  if (wealthStockAiEl) wealthStockAiEl.style.width = '0%';
  if (wealthStockHumansPctEl) wealthStockHumansPctEl.textContent = '--%';
  if (wealthStockAiPctEl) wealthStockAiPctEl.textContent = '--%';
  // Phase 6 §7.1 — inspector clears: card stack drops every card
  // because the cast snapshot is gone.
  _castByIdx.clear();
  inspector?.reset();
  if (paused) {
    paused = false;
    if (btnPauseEl) {
      btnPauseEl.classList.remove('toggled');
      btnPauseEl.textContent = 'pause';
    }
  }

  try {
    const req = { ...LEVERS, overrides };
    if (scaleOverride) req.scale = scaleOverride;
    stream = await startStream(req, {
      onHello, onStep, onCastSnapshot, onEdges,
      onFolds,
      onTerminal, onConnectError,
    });
  } catch (err) {
    setStatus(`error · ${err.message}`, 'error');
    console.error(err);
  } finally {
    _restarting = false;
    if (btnResetEl) btnResetEl.disabled = false;
  }
}

async function main() {
  setProgress(0.05, 'scene init');
  await nextFrame();
  setProgress(0.18, 'icosphere build');
  await nextFrame();
  // Heavy: ~1-2 s for the 398k-face mesh + adjacency hash.
  initScene();
  // Seed _leverState from current DOM slider positions, so the
  // dashboard-side α mapping shows the right value before the first
  // user interaction.
  seedLeverStateFromDom();
  // Fetch weights in parallel with topology build — the JSON is
  // tiny and not on the render critical path.
  // Plan §A.1 — call without a URL so the loader uses its module-
  // relative DEFAULT_URL. Avoids the document.baseURI 404 trap.
  loadAlphaWeights().then((w) => {
    updateAlphaHud();
    // Plan §D.2 — append a hollow-square marker to each lever whose
    // engine field isn't implemented yet (and so contributes to the
    // lever-α target but doesn't move the engine until Restart).
    markUnimplementedLevers(w);
  });
  // Plan §8.3 — opt in to runtime invariants via ?dev=1 URL.
  if (typeof location !== 'undefined'
      && new URLSearchParams(location.search).has('dev')) {
    import('./dev/checks.js').then((m) => {
      _devChecks = m;
      m.enableDevChecks();
    }).catch((err) => {
      console.warn('[dev/checks] failed to load:', err);
    });
  }
  setProgress(0.62, 'topology ready');
  await nextFrame();
  animate();
  setProgress(0.78, 'stream connect');
  await nextFrame();
  try {
    // Ship the current slider state as overrides on the FIRST run
    // so the calm-preset HTML defaults actually reach the engine
    // without the user having to click Reset. Subsequent restartRun
    // calls already do this; previously the first run alone used
    // raw scenario defaults.
    const initialOverrides = {};
    for (const [k, v] of Object.entries(_leverState)) {
      if (v !== undefined && v !== null) initialOverrides[k] = v;
    }
    stream = await startStream({ ...LEVERS, overrides: initialOverrides }, {
      onHello,
      onStep,
      onCastSnapshot,
      onEdges,
      onFolds,
      onTerminal,
      onConnectError,
    });
    setProgress(0.92, 'awaiting first frame');
  } catch (err) {
    setStatus(`error · ${err.message}`, 'error');
    console.error(err);
    if (loaderEl) loaderEl.setAttribute('data-done', '1');
  }
}

window.addEventListener('beforeunload', () => {
  if (stream) stream.cancel();
});

window.__sandbox = {
  fps: () => fps,
  surface: () => surface?.diagnostics?.(),
  agents: () => agents?.diagnostics?.(),
  edges: () => edges?.diagnostics?.(),
  firms: () => firms?.diagnostics?.(),
  firmMembers: () => firms?.membersByFirm?.() ?? {},
  folds: () => folds?.diagnostics?.(),
  foldDepthColors: () => folds?.depthColors?.() ?? {},
  clusters: () => clusters?.diagnostics?.(),
  clusterPartition: () => clusters?.partition?.() ?? new Map(),
  clusterCabalSizes: () => clusters?.cabalSizes?.() ?? new Map(),
  clusterLabels: () => clusterLabels?.diagnostics?.(),
  clusterTracks: () => clusterLabels?.allTracks?.() ?? [],
  clusterStablePartition: () => clusterLabels?.partition?.() ?? new Map(),
  clusterTrack: (id) => clusterLabels?.trackOf?.(id) ?? null,
  clusterOverlay: () => clusterOverlay?.diagnostics?.(),
  hideClusterOverlay: (h = true) => clusterOverlay?.setVisible?.(!h),
  isolateSector: (idx) => agents?.setIsolatedSector?.(idx),
  isolatedSector: () => agents?.isolatedSectorOf?.() ?? -1,
  sectorPalette: () => theme.sectorPalette,
  sectorNames: () => SECTOR_NAMES.slice(),
  inspector: () => inspector?.diagnostics?.() ?? { cards: [] },
  inspectorOpen: (kind, id, shift = false) => inspector?.openCard?.(kind, id, shift),
  inspectorReset: () => inspector?.reset?.(),
  castEntry: (idx) => _castByIdx.get(idx) ?? null,
  leverState: () => ({ ..._leverState }),
  alphaLever: () => mapAlpha(_leverState),
  alphaEngine: () => _lastEngineAlpha,
  // Plan §A.3 — exposed so dev/checks.js can probe the loader cold-
  // start. Returns the live mapAlpha symbol from alpha_map.js.
  alphaMap: { mapAlpha },
  // Plan §E.2 — percentile lookup against the per-snapshot
  // population distribution. Used by inspector_agent.js to stamp
  // capability/autonomy rows with their rank in the cast.
  populationPercentile,
  populationStats: () => ({
    capability: { mu: POP_STATS.capability.mu, sigma: POP_STATS.capability.sigma,
                  n: POP_STATS.capability.sorted?.length ?? 0 },
    autonomy:   { mu: POP_STATS.autonomy.mu,   sigma: POP_STATS.autonomy.sigma,
                  n: POP_STATS.autonomy.sorted?.length ?? 0 },
    trade_rate: { mu: POP_STATS.trade_rate.mu, sigma: POP_STATS.trade_rate.sigma,
                  n: POP_STATS.trade_rate.sorted?.length ?? 0 },
  }),
  regimeLabel: (ebi) => regimeLabel(ebi),
  counters: () => ({ ...counters }),
  theme: () => theme,
  hideAgents: (h = true) => { if (agents) agents.mesh.visible = !h; },
  hideSurface: (h = true) => { if (surface) surface.mesh.visible = !h; },
  hideEdges: (h = true) => { if (edges) edges.mesh.visible = !h; },
  hideFirms: (h = true) => {
    if (firms) firms.mesh.visible = !h;
    if (firms?.markerMesh) firms.markerMesh.visible = !h;
  },
  hideFolds: (h = true) => { if (folds) folds.mesh.visible = !h; },
  disableTopology: () => { surface?.setAltitudeScale(0); surface?.setGlobalAltitude(0); },
};

main();
