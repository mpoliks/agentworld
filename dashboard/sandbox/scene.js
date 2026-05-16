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
};

const statusEl = document.getElementById('status');
const loaderEl = document.getElementById('loader');
const loaderFillEl = document.getElementById('loader-fill');
const loaderLabelEl = document.getElementById('loader-label');
const sectorLabelEl = document.getElementById('sector-label');
const toggleTradesEl = document.getElementById('toggle-trades');
const toggleSectorsEl = document.getElementById('toggle-sectors');
const tradeCounterEl = document.getElementById('trade-counter-value');
let sectorsEnabled = toggleSectorsEl?.checked ?? true;
let _counterFrame = 0;
let cumulativeTrades = 0;       // monotonic — increments per snapshot
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
    activeColor: theme.activeColor,
    edgeColor: theme.edgeColor,
    edgeThreshold: theme.edgeThreshold,
    activationThreshold: theme.activationThreshold,
    minPersistFrames: theme.minPersistFrames,
    maxPersistFrames: theme.maxPersistFrames,
    magnitudeRef: theme.magnitudeRef,
    sectorPalette: theme.sectorPalette,
    sectorTintWeight: theme.sectorTintWeight,
    degreePersistBoost: theme.degreePersistBoost,
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
    `faces=${sd.faceCount}  active=${sd.activeFaces}  ` +
    `agents=${ad.castCount}  segments=${ad.segments}  firms=${ad.firmCount}  ` +
    `arcs=${ed.lineCount}`,
  );
}

function onHello(meta) {
  setStatus(`live · ${theme.name} · ${meta.scenario}`, 'live');
  summaryTimer = setInterval(logSummary, 1000);
}

function onStep(step) {
  counters.step += 1;
  setStatus(`${theme.name} · tick ${step.step}`, 'live');
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
  counters.cast += 1;
  surface?.handleCastSnapshot(ev.snapshot);
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
