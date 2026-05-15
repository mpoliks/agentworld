// Surface — sphere as a high-subdivision tessellation.
//
// Replaces the cells-on-a-sphere paradigm. The sphere itself is the
// thing the eye sees, divided into thousands of tiny triangles. Each
// trade event activates the triangle that contains the relevant
// agent's home position; activity decays per frame. Themes vary the
// triangulation density, base + activation colors, fade rate, and
// whether activations use a single colour or the sector palette.
//
// Light mode: scene background is light, base face colour is a faint
// tint of the activation hue, activation colour is the high-contrast
// foreground. Activity reads as ink-on-paper marks blooming and
// fading on the sphere.

import * as THREE from 'three';

import { sectorPalette } from './palette.js';

const DEFAULT_RADIUS = 600;          // physically bigger than the cell-era sphere — gives "very tiny" feel
const DEFAULT_SUBDIVISIONS = 5;      // 20 * 4^5 = 20,480 faces
const DEFAULT_FADE_RATE = 0.90;
const ACTIVATION_FLOOR = 0.012;      // below this, snap to base

const VERTEX_SHADER = /* glsl */ `
  attribute vec3 color;
  varying vec3 vColor;
  void main() {
    vColor = color;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

// Flat-shaded fragment — no lighting math, just the per-face color
// the JS layer wrote into the vertex color buffer. We keep this
// shader minimal so the only thing affecting the look is the
// per-triangle colour math the activity loop drives.
const FRAGMENT_SHADER = /* glsl */ `
  precision highp float;
  varying vec3 vColor;
  void main() {
    gl_FragColor = vec4(vColor, 1.0);
  }
`;

/**
 * Build the tessellated-surface renderer.
 *
 * @param {THREE.Scene} scene
 * @param {{
 *   radius?: number,
 *   subdivisions?: number,
 *   fadeRate?: number,
 *   baseColor?: [number, number, number],
 *   activeColor?: [number, number, number],
 *   useSectorPalette?: boolean,
 *   wireframe?: boolean,
 *   wireframeColor?: [number, number, number],
 *   wireframeOpacity?: number,
 *   activationThreshold?: number,
 * }} opts
 */
export function createSurface(scene, opts = {}) {
  const radius = opts.radius ?? DEFAULT_RADIUS;
  const subdivisions = opts.subdivisions ?? DEFAULT_SUBDIVISIONS;
  const fadeRate = opts.fadeRate ?? DEFAULT_FADE_RATE;
  const baseColor = opts.baseColor ?? [0.93, 0.93, 0.93];
  const activeColor = opts.activeColor ?? [0.05, 0.05, 0.05];
  const useSectorPalette = !!opts.useSectorPalette;
  const activationThreshold = opts.activationThreshold ?? 0.01;
  const palette = sectorPalette();

  // IcosahedronGeometry at subdivisions > 0 returns a non-indexed
  // BufferGeometry with each triangle's three vertices independent —
  // exactly the structure we want for per-face flat colors via vertex
  // attributes.
  const geometry = new THREE.IcosahedronGeometry(radius, subdivisions);
  const positionAttr = geometry.getAttribute('position');
  const vertexCount = positionAttr.count;
  const faceCount = vertexCount / 3;

  // Per-vertex color — initialised to baseColor for every vertex so
  // the sphere starts as a quiet shell. The activation loop writes
  // the same colour to all three vertices of an activated triangle.
  const colors = new Float32Array(vertexCount * 3);
  for (let v = 0; v < vertexCount; v += 1) {
    colors[v * 3 + 0] = baseColor[0];
    colors[v * 3 + 1] = baseColor[1];
    colors[v * 3 + 2] = baseColor[2];
  }
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

  // Per-face activity in [0, 1] + the activation color (sector hue or
  // theme's single colour). Splitting these lets a theme rotate the
  // activation hue per cell while sharing the same fade curve.
  const activities = new Float32Array(faceCount);
  const activeColors = new Float32Array(faceCount * 3);
  for (let f = 0; f < faceCount; f += 1) {
    activeColors[f * 3 + 0] = activeColor[0];
    activeColors[f * 3 + 1] = activeColor[1];
    activeColors[f * 3 + 2] = activeColor[2];
  }

  // Precompute face centroids — used once per cast member to pin
  // each slot to its closest face on first snapshot.
  const centroids = new Float32Array(faceCount * 3);
  {
    const p = positionAttr.array;
    for (let f = 0; f < faceCount; f += 1) {
      const base = f * 9;
      centroids[f * 3 + 0] = (p[base + 0] + p[base + 3] + p[base + 6]) / 3;
      centroids[f * 3 + 1] = (p[base + 1] + p[base + 4] + p[base + 7]) / 3;
      centroids[f * 3 + 2] = (p[base + 2] + p[base + 5] + p[base + 8]) / 3;
    }
  }

  const material = new THREE.ShaderMaterial({
    vertexShader: VERTEX_SHADER,
    fragmentShader: FRAGMENT_SHADER,
    side: THREE.FrontSide,
    transparent: false,
    depthWrite: true,
  });

  const mesh = new THREE.Mesh(geometry, material);
  mesh.frustumCulled = false;
  scene.add(mesh);

  // Optional wireframe overlay — same geometry, wireframe material,
  // additive opacity. Themes can enable this to draw faint triangle
  // edges over the flat fills.
  let wireMesh = null;
  if (opts.wireframe) {
    const wireMat = new THREE.LineBasicMaterial({
      color: new THREE.Color().fromArray(opts.wireframeColor ?? [0, 0, 0]),
      transparent: true,
      opacity: opts.wireframeOpacity ?? 0.18,
      depthTest: true,
      depthWrite: false,
    });
    const wireGeo = new THREE.WireframeGeometry(geometry);
    wireMesh = new THREE.LineSegments(wireGeo, wireMat);
    scene.add(wireMesh);
  }

  // idx → face. Filled on first snapshot when we know cast count.
  const slotByIdx = new Map();
  const slotToFace = new Int32Array(0);  // re-allocated on first snapshot
  let slotToFaceArr = null;
  const lastWealth = new Float32Array(0);
  let lastWealthArr = null;

  let castCount = 0;
  let initialized = false;

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

  // Find face whose centroid is angularly nearest to a given point on
  // the sphere. Both are radius-R, so smallest squared distance ⇔
  // largest cosine ⇔ smallest angle. O(faceCount) per call; only
  // called once per cast member at init.
  function findFaceForPoint(x, y, z) {
    let bestF = 0;
    let bestD2 = Infinity;
    for (let f = 0; f < faceCount; f += 1) {
      const dx = centroids[f * 3 + 0] - x;
      const dy = centroids[f * 3 + 1] - y;
      const dz = centroids[f * 3 + 2] - z;
      const d2 = dx * dx + dy * dy + dz * dz;
      if (d2 < bestD2) { bestD2 = d2; bestF = f; }
    }
    return bestF;
  }

  function initialLayout(snapshot) {
    castCount = snapshot.length;
    slotToFaceArr = new Int32Array(castCount);
    lastWealthArr = new Float32Array(castCount);

    // Randomise the slot → face mapping. With sector-sorted Fibonacci
    // mapping, consecutive slots landed on adjacent faces, producing
    // a regular stripe pattern when many cells activated at once.
    // Scattering the mapping means thousands of simultaneous events
    // sprinkle across the sphere with no visible structure.
    for (let slot = 0; slot < castCount; slot += 1) {
      const entry = snapshot[slot];
      slotByIdx.set(entry.idx, slot);
      // Cheap deterministic hash: each idx hashes to a face index so
      // refreshes are stable, but adjacent idx values land far apart
      // on the sphere.
      const h = mulberry32Hash(entry.idx + 1);
      slotToFaceArr[slot] = h % faceCount;

      if (useSectorPalette) {
        const palIdx = ((entry.sector % palette.length) + palette.length) % palette.length;
        const rgb = palette[palIdx];
        const f = slotToFaceArr[slot];
        activeColors[f * 3 + 0] = rgb[0];
        activeColors[f * 3 + 1] = rgb[1];
        activeColors[f * 3 + 2] = rgb[2];
      }

      lastWealthArr[slot] = NaN;
    }
    initialized = true;
  }

  // 32-bit integer hash that scatters consecutive inputs across the
  // full uint32 range. Used to break up the sector-sorted slot index
  // → face mapping so activations look random.
  function mulberry32Hash(x) {
    x = ((x + 0x6D2B79F5) | 0) >>> 0;
    x = Math.imul(x ^ (x >>> 15), x | 1) >>> 0;
    x ^= x + Math.imul(x ^ (x >>> 7), x | 61);
    return (x ^ (x >>> 14)) >>> 0;
  }

  function handleCastSnapshot(snapshot) {
    if (!snapshot || snapshot.length === 0) return;
    if (!initialized) initialLayout(snapshot);

    for (let i = 0; i < snapshot.length; i += 1) {
      const entry = snapshot[i];
      const slot = slotByIdx.get(entry.idx);
      if (slot === undefined) continue;

      const w = entry.wealth ?? 0;
      const prev = lastWealthArr[slot];
      lastWealthArr[slot] = w;
      if (Number.isNaN(prev)) continue;

      const delta = Math.abs(w - prev);
      if (delta < activationThreshold) continue;

      // Activate this slot's face to a fixed peak intensity. Tiny
      // wealth deltas were producing barely-visible activations
      // before; now any qualifying event paints the triangle at full
      // intensity so the fade animation reads clearly.
      const f = slotToFaceArr[slot];
      activities[f] = 1.0;
    }
  }

  // Per-frame fade + vertex-color rewrite. We only touch faces whose
  // activity is non-zero, so quiet frames cost nothing.
  function tick() {
    let anyDirty = false;
    for (let f = 0; f < faceCount; f += 1) {
      if (activities[f] <= 0) continue;

      activities[f] *= fadeRate;
      let needsReset = false;
      if (activities[f] < ACTIVATION_FLOOR) {
        activities[f] = 0;
        needsReset = true;
      }

      const a = activities[f];
      const ar = activeColors[f * 3 + 0];
      const ag = activeColors[f * 3 + 1];
      const ab = activeColors[f * 3 + 2];

      const r = baseColor[0] + (ar - baseColor[0]) * a;
      const g = baseColor[1] + (ag - baseColor[1]) * a;
      const b = baseColor[2] + (ab - baseColor[2]) * a;

      const base = f * 9;
      colors[base + 0] = r; colors[base + 1] = g; colors[base + 2] = b;
      colors[base + 3] = r; colors[base + 4] = g; colors[base + 5] = b;
      colors[base + 6] = r; colors[base + 7] = g; colors[base + 8] = b;

      anyDirty = true;
      // When activity hits zero we still wrote the base color, so
      // the face naturally rejoins the rest. `needsReset` is just a
      // local marker; no extra work needed.
      void needsReset;
    }
    if (anyDirty) geometry.getAttribute('color').needsUpdate = true;
  }

  function activeFaceCount() {
    let n = 0;
    for (let f = 0; f < faceCount; f += 1) if (activities[f] > 0) n += 1;
    return n;
  }

  function setVisible(visible) {
    mesh.visible = !!visible;
    if (wireMesh) wireMesh.visible = !!visible;
  }

  function dispose() {
    scene.remove(mesh);
    geometry.dispose();
    material.dispose();
    if (wireMesh) {
      scene.remove(wireMesh);
      wireMesh.geometry.dispose();
      wireMesh.material.dispose();
    }
    slotByIdx.clear();
  }

  function diagnostics() {
    return {
      faceCount,
      castCount,
      activeFaces: activeFaceCount(),
    };
  }

  return {
    mesh,
    wireMesh,
    handleCastSnapshot,
    tick,
    setVisible,
    dispose,
    diagnostics,
  };
}
