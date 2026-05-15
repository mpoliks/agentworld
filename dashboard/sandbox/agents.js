// Cast renderer (Pass 6) — continuous motion + human/agent
// differentiation + activity-driven flash.
//
// Every cast member is one point in a single THREE.Points draw call.
// Three visual states stack:
//
//   1. Continuous orbital motion. Each slot has an angular-momentum
//      axis L assigned at first sight; velocity = L × position, so
//      each agent traces a stable great-circle orbit on the sphere.
//      Magnitudes scale with autonomy (humans slow, agents fast).
//      force.js can layer additional impulses on top.
//
//   2. Activity EMA. Per-snapshot |Δwealth| accumulator decays at
//      0.85/snapshot, so trading cells stay continuously elevated
//      and quiet ones fall back. Drives baseline brightness.
//
//   3. Flash impulse. A sharp pop when |Δwealth/wealth| crosses a
//      relative threshold. Decays over 30 frames on the GPU.
//
// Human/agent differentiation is in the shader: humans render larger,
// brighter, with a soft outer halo (round); agents render smaller,
// crisper (square), more numerous-looking. The aIsHuman attribute
// drives it.

import * as THREE from 'three';

import { SECTOR_NAMES, sectorPalette } from './palette.js';

const FLASH_FRAMES = 30;
const FLASH_REL_THRESHOLD = 0.02;
const FLASH_ABS_FLOOR = 0.05;
const ACTIVITY_FADE = 0.86;
const ACTIVITY_BRIGHT_SCALE = 1.6;
const ACTIVITY_SIZE_SCALE = 4.0;
const FLASH_BRIGHT_GAIN = 0.9;
const FLASH_SIZE_GAIN = 14.0;
const BASE_SIZE_AGENT = 4.0;
const BASE_SIZE_HUMAN = 18.0;
const BASE_BRIGHTNESS = 0.30;

// Continuous-motion magnitudes (radians per frame at radius=400).
// Humans drift slowly, agents fast.
const ORBIT_HUMAN = 0.0030;
const ORBIT_AGENT = 0.014;

const NEVER_FLASHED = -1e9;

const VERTEX_SHADER = /* glsl */ `
  attribute vec3 aColor;
  attribute float aBaseSize;
  attribute float aIsHuman;
  attribute float aActivity;
  attribute float aFlashTime;

  uniform float uPixelRatio;
  uniform float uCurrentFrame;
  uniform float uFlashFrames;
  uniform float uActivitySizeScale;
  uniform float uFlashSizeGain;

  varying vec3 vColor;
  varying float vActivity;
  varying float vFlash;
  varying float vIsHuman;

  void main() {
    float age = uCurrentFrame - aFlashTime;
    float flash = clamp(1.0 - age / uFlashFrames, 0.0, 1.0);
    float activity = clamp(aActivity, 0.0, 1.0);

    vColor = aColor;
    vActivity = activity;
    vFlash = flash;
    vIsHuman = aIsHuman;

    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    float pixelSize = aBaseSize
                    + activity * uActivitySizeScale
                    + flash * uFlashSizeGain;
    gl_PointSize = pixelSize * uPixelRatio * (300.0 / -mvPosition.z);
    gl_Position = projectionMatrix * mvPosition;
  }
`;

// Two cell shapes: humans render round with a soft halo
// (high-autonomy nodes look organic, distinct); agents render square
// and crisp (numerous, mechanical). Both use additive-blended emissive
// color so the later bloom pass lifts them into halos.
const FRAGMENT_SHADER = /* glsl */ `
  precision highp float;

  varying vec3 vColor;
  varying float vActivity;
  varying float vFlash;
  varying float vIsHuman;

  uniform float uBaseBrightness;
  uniform float uActivityBrightScale;
  uniform float uFlashBrightGain;

  void main() {
    vec2 uv = gl_PointCoord - 0.5;

    float coverage;
    vec3 tint;
    if (vIsHuman > 0.5) {
      // Round, soft-edged cell with a wide halo. Humans get a warm
      // gold tint mixed with their sector hue so they read as
      // distinct anchor points across the sphere — eye picks them
      // out instantly against the smaller, cooler agent squares.
      float d = length(uv);
      if (d > 0.5) discard;
      float core = 1.0 - smoothstep(0.18, 0.32, d);
      float halo = 1.0 - smoothstep(0.05, 0.50, d);
      coverage = core + halo * 0.55;
      vec3 gold = vec3(1.0, 0.86, 0.55);
      tint = mix(vColor, gold, 0.55);
    } else {
      // Hard square — Conway cell aesthetic for the agent population.
      float edge = max(abs(uv.x), abs(uv.y));
      if (edge > 0.48) discard;
      coverage = 1.0;
      tint = vColor;
    }

    float bright = uBaseBrightness
                 + vActivity * uActivityBrightScale
                 + vFlash * uFlashBrightGain;
    bright = clamp(bright, 0.0, 1.6);
    // Humans get a brightness boost so their halo lifts above the
    // bond web; agents stay at baseline so they read as a numerous
    // colored field instead of overwhelming the sphere.
    if (vIsHuman > 0.5) bright *= 1.45;
    gl_FragColor = vec4(tint * bright * coverage, coverage);
  }
`;

/**
 * Build the cast renderer.
 *
 * @param {THREE.Scene} scene
 * @param {{
 *   maxAgents?: number,
 *   layoutRadius?: number,
 * }} opts
 */
export function createAgents(scene, opts = {}) {
  const maxAgents = opts.maxAgents ?? 5000;
  const radius = opts.layoutRadius ?? 400;

  const palette = sectorPalette();

  const positions = new Float32Array(maxAgents * 3);
  const colors = new Float32Array(maxAgents * 3);
  const baseSizes = new Float32Array(maxAgents);
  const isHumanBuf = new Float32Array(maxAgents);
  const activities = new Float32Array(maxAgents);
  const flashTimes = new Float32Array(maxAgents);
  flashTimes.fill(NEVER_FLASHED);

  // Angular-momentum axes (one per slot). Velocity per frame is
  // omega × position, where omega is this axis times the per-slot
  // orbit magnitude. force.js can write into this buffer to perturb.
  const omega = new Float32Array(maxAgents * 3);

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('aColor', new THREE.BufferAttribute(colors, 3));
  geometry.setAttribute('aBaseSize', new THREE.BufferAttribute(baseSizes, 1));
  geometry.setAttribute('aIsHuman', new THREE.BufferAttribute(isHumanBuf, 1));
  geometry.setAttribute('aActivity', new THREE.BufferAttribute(activities, 1));
  geometry.setAttribute('aFlashTime', new THREE.BufferAttribute(flashTimes, 1));
  geometry.setDrawRange(0, 0);

  const material = new THREE.ShaderMaterial({
    vertexShader: VERTEX_SHADER,
    fragmentShader: FRAGMENT_SHADER,
    uniforms: {
      uPixelRatio: { value: Math.min(window.devicePixelRatio, 2) },
      uCurrentFrame: { value: 0 },
      uFlashFrames: { value: FLASH_FRAMES },
      uActivitySizeScale: { value: ACTIVITY_SIZE_SCALE },
      uFlashSizeGain: { value: FLASH_SIZE_GAIN },
      uBaseBrightness: { value: BASE_BRIGHTNESS },
      uActivityBrightScale: { value: ACTIVITY_BRIGHT_SCALE },
      uFlashBrightGain: { value: FLASH_BRIGHT_GAIN },
    },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });

  const points = new THREE.Points(geometry, material);
  points.frustumCulled = false;
  scene.add(points);

  const slotByIdx = new Map();
  const lastWealth = new Float32Array(maxAgents);
  lastWealth.fill(NaN);

  let initialized = false;
  let castCount = 0;
  let currentFrame = 0;

  function fibonacci(slot, total, out) {
    if (total <= 1) {
      out[0] = 0; out[1] = 0; out[2] = radius;
      return;
    }
    const phi = Math.PI * (3.0 - Math.sqrt(5.0));
    const y = 1.0 - (slot / (total - 1)) * 2.0;
    const r = Math.sqrt(Math.max(0, 1.0 - y * y));
    const theta = phi * slot;
    out[0] = Math.cos(theta) * r * radius;
    out[1] = y * radius;
    out[2] = Math.sin(theta) * r * radius;
  }

  // Random unit vector — used as the angular-momentum axis for each
  // slot's orbital motion. Box-Muller style via two uniform draws to
  // avoid the pole bias of naive rejection sampling.
  function randomUnit(out) {
    let x, y, z, l2;
    do {
      x = Math.random() * 2 - 1;
      y = Math.random() * 2 - 1;
      z = Math.random() * 2 - 1;
      l2 = x * x + y * y + z * z;
    } while (l2 === 0 || l2 > 1);
    const l = Math.sqrt(l2);
    out[0] = x / l; out[1] = y / l; out[2] = z / l;
  }

  function initialLayout(snapshot) {
    const sorted = snapshot.slice().sort((a, b) => {
      if (a.sector !== b.sector) return a.sector - b.sector;
      return a.idx - b.idx;
    });
    castCount = Math.min(sorted.length, maxAgents);

    const tmp = [0, 0, 0];
    const axis = [0, 0, 0];
    for (let slot = 0; slot < castCount; slot += 1) {
      const entry = sorted[slot];
      slotByIdx.set(entry.idx, slot);

      fibonacci(slot, castCount, tmp);
      positions[slot * 3 + 0] = tmp[0];
      positions[slot * 3 + 1] = tmp[1];
      positions[slot * 3 + 2] = tmp[2];

      const human = !!entry.is_human;
      isHumanBuf[slot] = human ? 1.0 : 0.0;
      baseSizes[slot] = human ? BASE_SIZE_HUMAN : BASE_SIZE_AGENT;

      // Pick an angular-momentum axis. The magnitude (orbit speed) is
      // baked in: omega = axis × magnitude. Each slot orbits around
      // its own great-circle.
      randomUnit(axis);
      const mag = human ? ORBIT_HUMAN : ORBIT_AGENT;
      omega[slot * 3 + 0] = axis[0] * mag;
      omega[slot * 3 + 1] = axis[1] * mag;
      omega[slot * 3 + 2] = axis[2] * mag;
    }
    geometry.attributes.position.needsUpdate = true;
    geometry.attributes.aBaseSize.needsUpdate = true;
    geometry.attributes.aIsHuman.needsUpdate = true;
    geometry.setDrawRange(0, castCount);
    initialized = true;
  }

  function handleCastSnapshot(snapshot) {
    if (!snapshot || snapshot.length === 0) return;
    if (!initialized) initialLayout(snapshot);

    for (let i = 0; i < castCount; i += 1) {
      activities[i] *= ACTIVITY_FADE;
    }

    for (let i = 0; i < snapshot.length; i += 1) {
      const entry = snapshot[i];
      const slot = slotByIdx.get(entry.idx);
      if (slot === undefined) continue;

      const palIdx = ((entry.sector % palette.length) + palette.length) % palette.length;
      const rgb = palette[palIdx];
      colors[slot * 3 + 0] = rgb[0];
      colors[slot * 3 + 1] = rgb[1];
      colors[slot * 3 + 2] = rgb[2];

      const w = entry.wealth ?? 0;
      const prev = lastWealth[slot];
      lastWealth[slot] = w;
      if (Number.isNaN(prev)) continue;

      const delta = w - prev;
      const adelta = Math.abs(delta);
      activities[slot] += adelta * 1.4;

      const wRef = Math.max(prev, 1e-3);
      const rel = adelta / wRef;
      if (rel > FLASH_REL_THRESHOLD || adelta > FLASH_ABS_FLOOR) {
        flashTimes[slot] = currentFrame;
      }
    }

    geometry.attributes.aColor.needsUpdate = true;
    geometry.attributes.aActivity.needsUpdate = true;
    geometry.attributes.aFlashTime.needsUpdate = true;
  }

  // Per-frame integration step. Each slot's velocity is omega × position
  // (always tangent to the sphere). Integrate, then reproject to the
  // layoutRadius sphere to clean up float drift.
  function tick() {
    currentFrame += 1;
    material.uniforms.uCurrentFrame.value = currentFrame;

    if (!initialized || castCount === 0) return;

    for (let i = 0; i < castCount; i += 1) {
      const px = positions[i * 3 + 0];
      const py = positions[i * 3 + 1];
      const pz = positions[i * 3 + 2];
      const ox = omega[i * 3 + 0];
      const oy = omega[i * 3 + 1];
      const oz = omega[i * 3 + 2];

      // velocity = omega × position (tangent to sphere by construction).
      const vx = oy * pz - oz * py;
      const vy = oz * px - ox * pz;
      const vz = ox * py - oy * px;

      let nx = px + vx;
      let ny = py + vy;
      let nz = pz + vz;

      // Reproject to layoutRadius sphere.
      const r = Math.sqrt(nx * nx + ny * ny + nz * nz) || 1;
      const s = radius / r;
      positions[i * 3 + 0] = nx * s;
      positions[i * 3 + 1] = ny * s;
      positions[i * 3 + 2] = nz * s;
    }

    geometry.attributes.position.needsUpdate = true;
  }

  function getPosition(idx, out) {
    const slot = slotByIdx.get(idx);
    if (slot === undefined) return null;
    const base = slot * 3;
    const dst = out ?? [0, 0, 0];
    dst[0] = positions[base + 0];
    dst[1] = positions[base + 1];
    dst[2] = positions[base + 2];
    return dst;
  }

  function slotForIdx(idx) {
    const slot = slotByIdx.get(idx);
    return slot === undefined ? -1 : slot;
  }

  function slotCount() {
    return castCount;
  }

  function invalidatePositions() {
    geometry.attributes.position.needsUpdate = true;
  }

  function setVisible(visible) {
    points.visible = !!visible;
  }

  function dispose() {
    scene.remove(points);
    geometry.dispose();
    material.dispose();
    slotByIdx.clear();
  }

  function diagnostics() {
    return { castCount, currentFrame, initialized };
  }

  return {
    points,
    handleCastSnapshot,
    tick,
    getPosition,
    setVisible,
    dispose,
    diagnostics,
    positions,
    slotForIdx,
    slotCount,
    invalidatePositions,
    layoutRadius: radius,
    _slotByIdx: slotByIdx,
  };
}

export { SECTOR_NAMES };
