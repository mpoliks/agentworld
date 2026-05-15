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
const counters = { step: 0, cast: 0 };

let renderer, scene, camera, controls;
let surface = null;
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
  });

  window.addEventListener('resize', onResize);
}

function onResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight, false);
}

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  surface?.tick();
  renderer.render(scene, camera);

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
  const diag = surface?.diagnostics?.() ?? {};
  console.log(
    `[stream] tick=${counters.step}  cast=${counters.cast}  fps=${fps.toFixed(1)}  ` +
    `faces=${diag.faceCount}  active=${diag.activeFaces}`,
  );
}

function onHello(meta) {
  setStatus(`live · ${theme.name} · ${meta.scenario}`, 'live');
  summaryTimer = setInterval(logSummary, 1000);
}

function onStep(step) {
  counters.step += 1;
  setStatus(`${theme.name} · tick ${step.step}`, 'live');
}

function onCastSnapshot(ev) {
  counters.cast += 1;
  surface?.handleCastSnapshot(ev.snapshot);
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
  initScene();
  animate();
  try {
    stream = await startStream(LEVERS, {
      onHello,
      onStep,
      onCastSnapshot,
      onEdges: () => {},
      onFolds: () => {},
      onTerminal,
      onConnectError,
    });
  } catch (err) {
    setStatus(`error · ${err.message}`, 'error');
    console.error(err);
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
  counters: () => ({ ...counters }),
  theme: () => theme,
};

main();
