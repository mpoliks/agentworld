// Spatial-sandbox three.js scene (Pass 6).
//
// Render stack (back-to-front):
//   1. trails.js   — fading sector-coloured streak behind every agent.
//   2. agents.js   — cells: humans round + haloed, agents square + hard.
//                    Continuous orbital motion driven inside agents.tick.
//   3. bonds.js    — bright lines between repeat-trader pairs.
//   4. cabals.js   — chord graph between members of every bond-cluster
//                    of size ≥ 3 (the visible "structures").
//
// Bloom postprocess runs on the composed scene.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';

import { createAgents } from './agents.js';
import { createBonds } from './bonds.js';
import { createCabals } from './cabals.js';
import { createTrails } from './trails.js';
import { startStream } from './stream.js';

const LEVERS = {
  scenario: 'spatial_sandbox',
  scale: 'small',
  seed: 24601,
  cast_size: 5000,
  pair_sample_k: 1500,
};

const statusEl = document.getElementById('status');
const counters = { step: 0, cast: 0 };

let renderer, scene, camera, controls, composer, bloomPass;
let agents = null;
let bonds = null;
let cabals = null;
let trails = null;
let summaryTimer = null;
let stream = null;
let frameCount = 0;
let lastFpsT = performance.now();
let fps = 0;

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
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;

  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x04060c);

  camera = new THREE.PerspectiveCamera(
    50,
    window.innerWidth / window.innerHeight,
    0.1,
    5000,
  );
  camera.position.set(0, 0, 950);

  controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.autoRotate = true;
  controls.autoRotateSpeed = 0.25;

  agents = createAgents(scene, { maxAgents: LEVERS.cast_size });
  trails = createTrails(scene, { agents });
  bonds = createBonds(scene, { agents });
  cabals = createCabals(scene, { agents, bonds });

  composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  // UnrealBloomPass internally downsamples — sizing this Vector2 at
  // half-res cuts bloom GPU cost without making the bloom obviously
  // blocky on top of the additive-blended cells.
  const bloomSize = new THREE.Vector2(
    Math.floor(window.innerWidth / 2),
    Math.floor(window.innerHeight / 2),
  );
  bloomPass = new UnrealBloomPass(bloomSize, 1.4, 0.7, 0.04);
  composer.addPass(bloomPass);

  window.addEventListener('resize', onResize);
}

function onResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight, false);
  composer.setSize(window.innerWidth, window.innerHeight);
}

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  agents?.tick();
  trails?.tick();
  bonds?.tick();
  cabals?.tick();
  composer.render();

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
  console.log(
    `[stream] tick=${counters.step}  cast=${counters.cast}  fps=${fps.toFixed(1)}  ` +
    `bonds=${bonds?.bondCount() ?? 0}  cabals=${cabals?.diagnostics().cabalCount ?? 0}`,
  );
}

function onHello(meta) {
  setStatus(`live · ${meta.run_id} · ${meta.scenario}`, 'live');
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
  agents?.handleCastSnapshot(ev.snapshot);
  bonds?.handleCastSnapshot(ev.snapshot);
  cabals?.handleCastSnapshot(ev.snapshot);
}

function onTerminal(kind, payload) {
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
  agents: () => agents?.diagnostics?.(),
  bonds: () => ({ count: bonds?.bondCount() ?? 0 }),
  cabals: () => cabals?.diagnostics?.(),
  counters: () => ({ ...counters }),
  samplePositions: (n = 4) => {
    if (!agents) return null;
    const out = [];
    for (let i = 0; i < n; i += 1) {
      out.push([
        Math.round(agents.positions[i * 3 + 0] * 100) / 100,
        Math.round(agents.positions[i * 3 + 1] * 100) / 100,
        Math.round(agents.positions[i * 3 + 2] * 100) / 100,
      ]);
    }
    return out;
  },
  // Bond strength distribution for the verifier.
  bondHist: () => {
    if (!bonds) return null;
    const buckets = [0, 0, 0, 0, 0];
    for (const { strength } of bonds.iterBonds()) {
      const b = Math.min(4, Math.floor(strength));
      buckets[b] += 1;
    }
    return { '0-1': buckets[0], '1-2': buckets[1], '2-3': buckets[2], '3-4': buckets[3], '4+': buckets[4] };
  },
};

main();
