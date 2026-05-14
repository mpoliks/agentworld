// Spatial-sandbox three.js scene. Module #1 (Week 2) — boots the
// renderer, holds a black scene, and wires the SSE stream so subsequent
// modules (agents.js, edges.js, folds.js, force.js) can layer on top.
//
// No geometry renders yet. The status pill in the corner is the only
// visible UI; the per-event traffic goes to the browser console.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { startStream } from './stream.js';

// Hardcoded lever state for Week 2. Defaults per spatial-sandbox.md §3
// (the three-panel lever inventory). UI controls land in Week 3.
//
// `spatial_sandbox` is the single engine scenario the sandbox runs.
// Every optional subsystem is on with the §3 lever defaults; the
// dashboard's lever panels will eventually patch this via
// `RunRequest.overrides`. cast_size matches the plan's visible-agent
// target (5,000); pair_sample_k feeds the trade-edge graph.
const LEVERS = {
  scenario: 'spatial_sandbox',
  scale: 'small',
  seed: 24601,
  cast_size: 5000,
  pair_sample_k: 1500,
};

const statusEl = document.getElementById('status');
const counters = { step: 0, cast: 0, edges: 0, folds: 0 };

let renderer, scene, camera, controls;
let summaryTimer = null;
let stream = null;

function initScene() {
  const canvas = document.getElementById('scene');

  renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight, false);

  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x060810);

  camera = new THREE.PerspectiveCamera(
    50,
    window.innerWidth / window.innerHeight,
    0.1,
    5000,
  );
  camera.position.set(0, 0, 800);

  controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;

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
  renderer.render(scene, camera);
}

function setStatus(text, kind = '') {
  statusEl.textContent = text;
  statusEl.dataset.kind = kind;
}

function logSummary() {
  console.log(
    `[stream] tick=${counters.step}  ` +
    `cast=${counters.cast}  ` +
    `edges=${counters.edges}  ` +
    `folds=${counters.folds}`,
  );
}

function onHello(meta) {
  setStatus(`live · ${meta.run_id} · ${meta.scenario}`, 'live');
  console.log('[hello]', meta);
  summaryTimer = setInterval(logSummary, 1000);
}

function onStep(step) {
  counters.step += 1;
  const alpha = (step.alpha ?? 0).toFixed(2);
  const ebi = (step.exo_baroque_index ?? 0).toFixed(2);
  setStatus(`tick ${step.step} · α ${alpha} · EBI ${ebi}`, 'live');
}

function onCastSnapshot(ev) {
  counters.cast += 1;
  if (counters.cast === 1) {
    console.log('[cast_snapshot_v2] first sample:', ev.snapshot[0]);
    console.log(`[cast_snapshot_v2] cast size = ${ev.snapshot.length}`);
  }
}

function onEdges(ev) {
  counters.edges += 1;
  if (counters.edges === 1) {
    console.log('[edges_v2] first sample:', ev.edges[0]);
    console.log(`[edges_v2] edge count per tick ≈ ${ev.edges.length}`);
  }
}

function onFolds(ev) {
  counters.folds += 1;
  if (counters.folds === 1) {
    console.log('[folds_v2] first sample:', ev);
  }
}

function onTerminal(kind, payload) {
  if (summaryTimer) {
    clearInterval(summaryTimer);
    summaryTimer = null;
  }
  const steps = payload?.n_steps ?? counters.step;
  setStatus(`${kind} · ${steps} ticks`, kind);
  console.log(`[${kind}]`, payload);
}

function onConnectError() {
  if (summaryTimer) {
    clearInterval(summaryTimer);
    summaryTimer = null;
  }
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
      onEdges,
      onFolds,
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

main();
