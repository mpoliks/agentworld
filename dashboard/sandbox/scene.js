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
import { loadAlphaWeights, mapAlpha } from './alpha_map.js';
import { startStream } from './stream.js';
import { THEME } from './themes.js';

const LEVERS = {
  scenario: 'spatial_sandbox',
  scale: 'small',
  seed: 24601,
  cast_size: 5000,
  pair_sample_k: 1500,
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
const toggleTradesEl = document.getElementById('toggle-trades');
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
const leversPendingRowEl = document.getElementById('levers-pending-row');
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
  'law.transaction_size_cap':          (v) => (v >= 10 ? '∞' : v.toFixed(2)),
  'folding_max_depth':                 (v) => String(Math.round(v)),
  // Structural numeric levers
  'agent_capability_mean':             (v) => v.toFixed(2),
  'agent_autonomy_mean':               (v) => v.toFixed(2),
  'agent_trade_rate_multiplier':       (v) => v.toFixed(1),
  'network_p_local':                   (v) => v.toFixed(2),
  'norms.certified_fraction':          (v) => v.toFixed(2),
  'law.law_strength_initial':          (v) => v.toFixed(2),
};
// Levers that take a string value (selects). Some need translation
// to the engine override shape (e.g. "on"/"off" → true/false).
const LEVER_STRING_TRANSFORM = {
  'regulator.enabled':  (s) => s === 'on',
  // Pass-through values for the categorical levers (engine accepts
  // the string directly).
};
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
const btnRestartEl = document.getElementById('btn-restart');
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
let _shapeFlatten = 0;
let _shapeChaos = 0;
const SHAPE_FLATTEN_MAX = 0.85;        // 85% squash at EBI≈0.5 (extreme smooth)
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

// Phase 6 §7.4 — trade-arc outcome legend. Builds 8 rows
// (executed + 7 reject reasons) from OUTCOME_PALETTE in edges.js
// so the legend RGB matches the rendered arc RGB pixel-exact.
const ARC_LEGEND_ROWS = [
  ['executed',        'executed'],
  ['reject_cost',     'cost reject'],
  ['reject_market',   'market reject'],
  ['reject_align',    'align reject'],
  ['reject_law',      'law reject'],
  ['reject_compute',  'compute reject'],
  ['reject_perm',     'perm reject'],
  ['reject_reg',      'reg reject'],
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
  // Map the six regime bands onto the three glyphs:
  //   ebi < 1.5  → disc       (flat real economy + low baroque)
  //   1.5 ≤ ebi < 2.5 → sphere (calibrated reference)
  //   ebi ≥ 2.5  → lobes      (reflexivity / exo-baroque / untethered)
  let band;
  if (ebi < 1.5) band = 'disc';
  else if (ebi < 2.5) band = 'sphere';
  else band = 'lobes';
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
    r.valueEl.textContent = (sample * 100).toFixed(1) + '%';
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
    const w = canvas.width;
    const h = canvas.height;
    const n = r.history.length;
    ctx.lineWidth = 1.5 * dpr;
    ctx.strokeStyle = r.color;
    ctx.beginPath();
    for (let k = 0; k < n; k += 1) {
      const x = (k / (SPARKLINE_LEN - 1)) * w;
      const sample = r.history[k].v;
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
  camera.position.set(0, 0, 1700);

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
    cardEl: document.getElementById('inspector-card'),
    cardCloseEl: document.getElementById('inspector-card-close'),
    cardBodyEl: document.getElementById('inspector-card-body'),
  });
  inspector.attach();

  initWelfareMeter();
  initSectorCompass();
  initArcLegend();
  initEbiLegend();

  window.addEventListener('resize', onResize);
  renderer.domElement.addEventListener('mousemove', onPointerMove);
  renderer.domElement.addEventListener('mouseleave', onPointerLeave);

  toggleTradesEl?.addEventListener('change', () => {
    edges?.setVisible(toggleTradesEl.checked);
  });
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
  btnRestartEl?.addEventListener('click', () => { restartRun(); });
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

// Apply the world-shape morph to every mesh whose vertices live in
// scene-space — substrate, caterpillars, indicator dots, tethers,
// trade arcs. mesh.scale.y is the cheapest way to do this; no
// shader changes, no per-vertex JS rewrites. Sector hover (which
// does its own analytic ray-vs-sphere) inverse-transforms the ray
// in onPointerMove so hit detection still resolves on the original
// sphere geometry.
function applyShape() {
  const sy = 1 - _shapeFlatten;
  if (surface) {
    surface.mesh.scale.y = sy;
    surface.setChaos(_shapeChaos);
  }
  if (agents) {
    agents.mesh.scale.y = sy;
    if (agents.indicatorMesh) agents.indicatorMesh.scale.y = sy;
    if (agents.tetherMesh) agents.tetherMesh.scale.y = sy;
  }
  if (edges) edges.mesh.scale.y = sy;
  if (firms) firms.mesh.scale.y = sy;
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
      // Flatten ramp on the low side: EBI < 2.0 starts compressing
      // toward disc; at EBI 0.5 (or below) the sphere is fully flat.
      const flatT = (SHAPE_FLATTEN_EBI_HIGH - _ebiSmoothed)
        / (SHAPE_FLATTEN_EBI_HIGH - SHAPE_FLATTEN_EBI_LOW);
      _shapeFlatten = Math.max(0, Math.min(SHAPE_FLATTEN_MAX, flatT * SHAPE_FLATTEN_MAX));
      // Chaos ramp on the high side: EBI > 2.0 starts adding lobes;
      // saturates at EBI 5.0.
      const chaosT = (_ebiSmoothed - SHAPE_CHAOS_EBI_LOW)
        / (SHAPE_CHAOS_EBI_HIGH - SHAPE_CHAOS_EBI_LOW);
      _shapeChaos = Math.max(0, Math.min(1, chaosT));
      applyShape();
    }
  }
  if (hudWelfareStepEl && Number.isFinite(step.real_welfare_step)) {
    const v = step.real_welfare_step;
    const sign = v >= 0 ? '+' : '';
    hudWelfareStepEl.textContent = sign + v.toFixed(1);
  }
  if (hudGiniEl && Number.isFinite(step.gini_wealth)) hudGiniEl.textContent = step.gini_wealth.toFixed(3);
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
      // 1.0..1.10 effective range (clamped on the setter side).
      surface.setAltitudeScale(1.0 + Math.max(0, ebi - 1.0) * 0.10);
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
function onEdges(ev) {
  if (paused) return;
  if (!surface || !agents || !ev.edges) return;
  for (let i = 0; i < ev.edges.length; i += 1) {
    const e = ev.edges[i];
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
  if (btnRestartEl) btnRestartEl.disabled = true;
  setStatus(`${theme.name} · restarting…`, '');

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

  counters.step = 0;
  counters.cast = 0;
  cumulativeWealth = 0;
  cumulativeTrades = 0;
  _stepArrivalCount = 0;
  _stepArrivalI = 0;
  _ebiSmoothed = 2.0;
  _shapeFlatten = 0;
  _shapeChaos = 0;
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
  // Phase 6 §7.1 — inspector clears: card hides on next refresh
  // because _castByIdx is empty.
  _castByIdx.clear();
  inspector?.refresh();
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
    if (btnRestartEl) btnRestartEl.disabled = false;
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
  loadAlphaWeights('./alpha_weights.json').then(() => updateAlphaHud());
  setProgress(0.62, 'topology ready');
  await nextFrame();
  animate();
  setProgress(0.78, 'stream connect');
  await nextFrame();
  try {
    stream = await startStream(LEVERS, {
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
  inspectorOpenIdx: () => inspector?.openIdxOf?.() ?? -1,
  castEntry: (idx) => _castByIdx.get(idx) ?? null,
  leverState: () => ({ ..._leverState }),
  alphaLever: () => mapAlpha(_leverState),
  alphaEngine: () => _lastEngineAlpha,
  regimeLabel: (ebi) => regimeLabel(ebi),
  counters: () => ({ ...counters }),
  theme: () => theme,
  hideAgents: (h = true) => { if (agents) agents.mesh.visible = !h; },
  hideSurface: (h = true) => { if (surface) surface.mesh.visible = !h; },
  hideEdges: (h = true) => { if (edges) edges.mesh.visible = !h; },
  hideFirms: (h = true) => { if (firms) firms.mesh.visible = !h; },
  hideFolds: (h = true) => { if (folds) folds.mesh.visible = !h; },
  disableTopology: () => { surface?.setAltitudeScale(0); surface?.setGlobalAltitude(0); },
};

main();
