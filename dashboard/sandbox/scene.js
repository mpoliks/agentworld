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
const STOCK_SEGMENTS = [
  { key: 'humans', label: 'humans', color: 'rgb(217, 166, 77)',  source: (s) => s.human_wealth_share ?? 0 },
  { key: 'ai',     label: 'ai',     color: 'rgb(110, 130, 155)', source: (s) => Math.max(0, 1 - (s.human_wealth_share ?? 0)) },
];
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
const hudEbiEl = document.getElementById('hud-ebi');
const hudWelfareStepEl = document.getElementById('hud-welfare-step');
const hudGiniEl = document.getElementById('hud-gini');
const hudTpsEl = document.getElementById('hud-tps');
// Live levers panel (right side under the HUD). One slider per
// engine parameter that's whitelisted by _LIVE_TUNABLE in
// engine/serve.py and pushed via POST /runs/{id}/update. α was
// dropped — it's an outcome of governance/tax/capability conditions,
// not a knob a regulator actually has (the path-dependence test in
// Pass 26 confirmed turning α down doesn't unwind fold accumulation).
// HUD α row stays as a read-only readout.
const leverMarketTaxEl = document.getElementById('lever-market-tax');
const leverMarketTaxValueEl = document.getElementById('lever-market-tax-value');
// Slider value 0..100 maps log-scale to agentsPerHuman 1..1000.
// At slider=67, value ≈ 100 (real-population default of 1 human : 100 agents).
function sliderToAgentsPerHuman(s) {
  return Math.max(1, Math.round(Math.pow(10, (Number(s) / 100) * 3)));
}
const tradeCounterEl = document.getElementById('trade-counter-value');
const welfareTotalEl = document.getElementById('welfare-total-value');
const welfareStockEl = document.getElementById('welfare-stock');
const welfareFlowEl = document.getElementById('welfare-flow');
let sectorsEnabled = toggleSectorsEl?.checked ?? true;
// Dashboard-side pause. The engine keeps running; we skip processing
// new step / cast / edge events so the visual freezes. Toggling off
// resumes from the next event (no catch-up backlog — we just drop
// what arrived during the pause).
let paused = false;
const togglePauseEl = document.getElementById('toggle-pause');
let _counterFrame = 0;
let cumulativeTrades = 0;       // monotonic — increments per snapshot
let cumulativeWealth = 0;       // real_welfare_cumulative from engine

// Build the meter rows. Stock and flow sections are separate DOM
// containers so the percentages don't pretend to compose into one
// pie. meterRows stays a flat list — updateWelfareMeter() doesn't
// care which section a row belongs to.
function buildMeterRow(seg, container) {
  const row = document.createElement('div');
  row.className = 'meter-row';
  const header = document.createElement('div');
  header.className = 'meter-row-header';
  const labelWrap = document.createElement('span');
  labelWrap.className = 'meter-row-label';
  const dot = document.createElement('span');
  dot.className = 'meter-dot';
  dot.style.background = seg.color;
  labelWrap.appendChild(dot);
  labelWrap.appendChild(document.createTextNode(seg.label));
  const valueEl = document.createElement('span');
  valueEl.className = 'meter-row-value';
  valueEl.textContent = '--';
  header.appendChild(labelWrap);
  header.appendChild(valueEl);
  const bar = document.createElement('div');
  bar.className = 'meter-bar';
  const fillEl = document.createElement('div');
  fillEl.className = 'meter-fill';
  fillEl.style.background = seg.color;
  bar.appendChild(fillEl);
  row.appendChild(header);
  row.appendChild(bar);
  container.appendChild(row);
  return {
    key: seg.key,
    source: seg.source,
    target: 0,
    valueEl,
    fillEl,
    smoothed: NaN,
  };
}
function initWelfareMeter() {
  meterRows = [];
  if (welfareStockEl) {
    for (const seg of STOCK_SEGMENTS) meterRows.push(buildMeterRow(seg, welfareStockEl));
  }
  if (welfareFlowEl) {
    for (const seg of FLOW_SEGMENTS) meterRows.push(buildMeterRow(seg, welfareFlowEl));
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

// EMA smoothing on each meter row so per-snapshot sampling noise
// doesn't drown out alpha-driven trends. α=0.08 per frame → ~0.4s
// half-life, fast enough to feel responsive, slow enough to smooth
// the engine's 5 Hz tick-to-tick variance. Earlier cosmetic sine
// jitter was making real signal changes look random — removed.
const METER_EMA_ALPHA = 0.08;
function updateWelfareMeter() {
  if (!meterRows) return;
  for (let i = 0; i < meterRows.length; i += 1) {
    const r = meterRows[i];
    if (!Number.isFinite(r.smoothed)) r.smoothed = r.target;
    r.smoothed = r.smoothed * (1 - METER_EMA_ALPHA) + r.target * METER_EMA_ALPHA;
    let v = r.smoothed;
    if (v < 0) v = 0; else if (v > 1) v = 1;
    r.fillEl.style.width = (v * 100).toFixed(2) + '%';
    r.valueEl.textContent = (v * 100).toFixed(1) + '%';
  }
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

// Yield one animation frame so the browser repaints the loader fill
// before the next synchronous chunk (icosphere build, adjacency, etc.).
function nextFrame() {
  return new Promise(resolve => requestAnimationFrame(() => resolve()));
}

let renderer, scene, camera, controls;
let surface = null;
let agents = null;
let edges = null;
// Wealth-flow meter state. Each entry: { key, target, smoothed, valueEl, fillEl }.
let meterRows = null;
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
  });

  edges = createEdges(scene, surface, agents, {
    sphereRadius: theme.radius ?? 700,
  });

  initWelfareMeter();

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
  togglePauseEl?.addEventListener('change', () => {
    paused = togglePauseEl.checked;
    setStatus(paused ? `${theme.name} · paused` : `${theme.name} · live`, paused ? '' : 'live');
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
  // Live levers — debounced POST /runs/{id}/update so dragging
  // the slider doesn't fire ~60 requests/sec. The readout updates
  // immediately; the request waits LEVER_DEBOUNCE_MS for the drag
  // to settle.
  if (leverMarketTaxEl) {
    leverMarketTaxEl.addEventListener('input', () => {
      const v = parseFloat(leverMarketTaxEl.value);
      if (!Number.isFinite(v)) return;
      if (leverMarketTaxValueEl) leverMarketTaxValueEl.textContent = (v * 100).toFixed(1) + '%';
      scheduleLeverUpdate('market_layer_tax', v);
    });
  }
}

// Debounced live-update POST. Per-key timer so simultaneous sliders
// on different keys don't cancel each other. The engine validates
// against _LIVE_TUNABLE + Sobol bounds; a 400/409 response is logged
// but doesn't unwind the slider — the user can drag back.
const LEVER_DEBOUNCE_MS = 200;
const _leverTimers = new Map();
const _leverPending = new Map();
function scheduleLeverUpdate(key, value) {
  _leverPending.set(key, value);
  const prev = _leverTimers.get(key);
  if (prev !== undefined) clearTimeout(prev);
  _leverTimers.set(key, setTimeout(() => {
    _leverTimers.delete(key);
    flushLeverUpdates();
  }, LEVER_DEBOUNCE_MS));
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
  const o = _raycaster.ray.origin;
  const d = _raycaster.ray.direction;
  const R = surface.radius ?? 700;
  const od = o.x * d.x + o.y * d.y + o.z * d.z;
  const oo = o.x * o.x + o.y * o.y + o.z * o.z;
  const disc = od * od - (oo - R * R);
  if (disc < 0) { setHoveredSector(-1); return; }
  const t = -od - Math.sqrt(disc);
  if (t < 0) { setHoveredSector(-1); return; }
  const px = o.x + t * d.x;
  const py = o.y + t * d.y;
  const pz = o.z + t * d.z;
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
  // Wealth-flow meter bars jitter every frame so the readout has
  // life even when the underlying shares are stable.
  updateWelfareMeter();
  renderer.render(scene, camera);

  // Throttle trade-counter DOM updates to ~10 Hz. Cumulative count
  // since the run started.
  _counterFrame += 1;
  if (_counterFrame >= 6) {
    _counterFrame = 0;
    if (tradeCounterEl) {
      tradeCounterEl.textContent = cumulativeTrades.toLocaleString();
    }
  }

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
  console.log(
    `[stream] tick=${counters.step}  cast=${counters.cast}  fps=${fps.toFixed(1)}  ` +
    `faces=${sd.faceCount}  ` +
    `agents=${ad.castCount}  segments=${ad.segments}  firms=${ad.firmCount}  ` +
    `arcs=${ed.lineCount}`,
  );
}

function onHello(meta) {
  setStatus(`live · ${theme.name} · ${meta.scenario}`, 'live');
  summaryTimer = setInterval(logSummary, 1000);
}

function onStep(step) {
  if (paused) return;
  counters.step += 1;
  setStatus(`${theme.name} · tick ${step.step}`, 'live');

  pushStepArrival(performance.now() * 0.001);
  if (hudAlphaEl && Number.isFinite(step.alpha)) hudAlphaEl.textContent = step.alpha.toFixed(3);
  // Per-tick EBI = nominal_step / real_step. Reads the *current*
  // regime instead of the cumulative ratio, which can only ratchet
  // up. Falls through when real_step is unusable.
  if (hudEbiEl) {
    const nstep = step.nominal_gdp_step;
    const rstep = step.real_welfare_step;
    if (Number.isFinite(nstep) && Number.isFinite(rstep) && rstep > 0) {
      hudEbiEl.textContent = (nstep / rstep).toFixed(3);
    }
  }
  if (hudWelfareStepEl && Number.isFinite(step.real_welfare_step)) {
    const v = step.real_welfare_step;
    const sign = v >= 0 ? '+' : '';
    hudWelfareStepEl.textContent = sign + v.toFixed(1);
  }
  if (hudGiniEl && Number.isFinite(step.gini_wealth)) hudGiniEl.textContent = step.gini_wealth.toFixed(3);
  if (hudTpsEl) hudTpsEl.textContent = ticksPerSec().toFixed(1);

  // Push each meter row's target value from the step payload, plus
  // the running cumulative wealth total at the panel header.
  if (meterRows) {
    for (let i = 0; i < meterRows.length; i += 1) {
      const r = meterRows[i];
      const v = r.source(step);
      r.target = Number.isFinite(v) ? Math.max(0, Math.min(1, v)) : 0;
    }
  }
  if (typeof step.real_welfare_cumulative === 'number') {
    cumulativeWealth = step.real_welfare_cumulative;
    if (welfareTotalEl) welfareTotalEl.textContent = Math.round(cumulativeWealth).toLocaleString();
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
  if (counters.cast === 1) setProgress(1.0, 'live');
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
  // Draw the live trade arcs (blue success, red reject) over the
  // current substrate. Replaces previous snapshot's lines.
  edges?.handleEdges(ev.edges);
  if (ev.edges) cumulativeTrades += ev.edges.length;
}

function onTerminal(kind) {
  if (summaryTimer) { clearInterval(summaryTimer); summaryTimer = null; }
  setStatus(`${kind}`, kind);
}

function onConnectError() {
  if (summaryTimer) { clearInterval(summaryTimer); summaryTimer = null; }
  setStatus('stream closed', 'error');
}

async function main() {
  setProgress(0.05, 'scene init');
  await nextFrame();
  setProgress(0.18, 'icosphere build');
  await nextFrame();
  // Heavy: ~1-2 s for the 398k-face mesh + adjacency hash.
  initScene();
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
      onFolds: () => {},
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
  if (stream) {
    fetch(`/runs/${stream.runId}/cancel`, { method: 'POST' }).catch(() => {});
    stream.close();
  }
});

window.__sandbox = {
  fps: () => fps,
  surface: () => surface?.diagnostics?.(),
  agents: () => agents?.diagnostics?.(),
  edges: () => edges?.diagnostics?.(),
  counters: () => ({ ...counters }),
  theme: () => theme,
  hideAgents: (h = true) => { if (agents) agents.mesh.visible = !h; },
  hideSurface: (h = true) => { if (surface) surface.mesh.visible = !h; },
  hideEdges: (h = true) => { if (edges) edges.mesh.visible = !h; },
  disableTopology: () => { surface?.setAltitudeScale(0); surface?.setGlobalAltitude(0); },
};

main();
