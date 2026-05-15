// Surface — high-subdivision icosphere with always-visible grid and
// magnitude-driven activation persistence.
//
// The sphere is a high-subdivision icosahedron; the whole grid is
// rendered every frame via a barycentric-coordinate edge term in the
// fragment shader. Engine trade events activate individual triangles
// in greyscale; the activation persistence (how long the triangle
// stays visible) is proportional to the magnitude of the wealth
// change that fired it, and the brightness decays linearly toward
// the base across that lifetime.
//
// Semantics:
//   • Intensity (current brightness) ↔ recency. Just-fired triangles
//     read at full active colour; older ones blend back toward base.
//   • Lifetime (total visible duration) ↔ event magnitude. A
//     near-threshold wealth move keeps the triangle visible for ~1s;
//     a windfall persists 10+ seconds.
//
// Activations are also staggered: each cell's triggered fire-frame is
// scheduled at currentFrame + random(0, STAGGER_FRAMES) so the
// ~3,000 simultaneous SSE-snapshot triggers spread across the
// inter-snapshot interval instead of pulsing in lockstep.

import * as THREE from 'three';

const DEFAULT_RADIUS = 700;
const DEFAULT_SUBDIVISIONS = 140;    // 20 × 141² ≈ 397,620 triangles
const STAGGER_FRAMES = 12;           // matches SSE snapshot rate

// Lifetime curve. log1p(delta) saturates around log1p(MAGNITUDE_REF),
// so events at MAGNITUDE_REF and above use MAX_PERSIST frames and
// tiny events sit near MIN_PERSIST.
const MIN_PERSIST_FRAMES = 60;       // 1.0s at 60fps
const MAX_PERSIST_FRAMES = 720;      // 12s at 60fps
const MAGNITUDE_REF = 10.0;          // wealth-delta saturation point

const VERTEX_SHADER = /* glsl */ `
  attribute vec3 color;
  attribute vec3 barycentric;
  varying vec3 vColor;
  varying vec3 vBary;
  void main() {
    vColor = color;
    vBary = barycentric;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

// Per-triangle flat fill, switched to the edge colour inside the
// barycentric edge band so the grid renders on every fragment near
// a triangle boundary. No GLSL extensions required.
const FRAGMENT_SHADER = /* glsl */ `
  precision highp float;

  uniform vec3 uEdgeColor;
  uniform float uEdgeThreshold;

  varying vec3 vColor;
  varying vec3 vBary;

  void main() {
    float minBary = min(vBary.x, min(vBary.y, vBary.z));
    vec3 col = minBary < uEdgeThreshold ? uEdgeColor : vColor;
    gl_FragColor = vec4(col, 1.0);
  }
`;

export function createSurface(scene, opts = {}) {
  const radius = opts.radius ?? DEFAULT_RADIUS;
  const subdivisions = opts.subdivisions ?? DEFAULT_SUBDIVISIONS;
  const baseColor = opts.baseColor ?? [0.90, 0.89, 0.85];
  const activeColor = opts.activeColor ?? [0.08, 0.08, 0.10];
  const edgeColor = opts.edgeColor ?? [0.62, 0.60, 0.55];
  const edgeThreshold = opts.edgeThreshold ?? 0.03;
  const activationThreshold = opts.activationThreshold ?? 0.02;
  const minPersistFrames = opts.minPersistFrames ?? MIN_PERSIST_FRAMES;
  const maxPersistFrames = opts.maxPersistFrames ?? MAX_PERSIST_FRAMES;
  const magnitudeRef = opts.magnitudeRef ?? MAGNITUDE_REF;

  // High-subdivision icosphere. Face count = 20 * (subdivisions+1)².
  const geometry = new THREE.IcosahedronGeometry(radius, subdivisions);
  const positionAttr = geometry.getAttribute('position');
  const vertexCount = positionAttr.count;
  const faceCount = vertexCount / 3;

  // Initial per-vertex colour = baseColor on every face.
  const colors = new Float32Array(vertexCount * 3);
  for (let v = 0; v < vertexCount; v += 1) {
    colors[v * 3 + 0] = baseColor[0];
    colors[v * 3 + 1] = baseColor[1];
    colors[v * 3 + 2] = baseColor[2];
  }
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

  // Barycentric attribute — every triangle gets (1,0,0), (0,1,0),
  // (0,0,1) on its three vertices. The fragment shader uses these to
  // derive distance-to-nearest-edge for the grid render.
  const bary = new Float32Array(vertexCount * 3);
  for (let f = 0; f < faceCount; f += 1) {
    const base = f * 9;
    bary[base + 0] = 1; bary[base + 1] = 0; bary[base + 2] = 0;
    bary[base + 3] = 0; bary[base + 4] = 1; bary[base + 5] = 0;
    bary[base + 6] = 0; bary[base + 7] = 0; bary[base + 8] = 1;
  }
  geometry.setAttribute('barycentric', new THREE.BufferAttribute(bary, 3));

  // Per-face activation state. startFrame = -1 when the face has no
  // live activation. persistFrames = total lifetime in frames when
  // activated, used to compute the linear brightness decay.
  const startFrameArr = new Float32Array(faceCount);
  startFrameArr.fill(-1);
  const persistFramesArr = new Float32Array(faceCount);

  const material = new THREE.ShaderMaterial({
    vertexShader: VERTEX_SHADER,
    fragmentShader: FRAGMENT_SHADER,
    uniforms: {
      uEdgeColor: { value: new THREE.Color().fromArray(edgeColor) },
      uEdgeThreshold: { value: edgeThreshold },
    },
    side: THREE.FrontSide,
    transparent: false,
    depthWrite: true,
  });

  const mesh = new THREE.Mesh(geometry, material);
  mesh.frustumCulled = false;
  scene.add(mesh);

  // Per-slot bookkeeping: idx → slot, last-seen wealth (for delta
  // detection), scheduled fire frame, scheduled magnitude.
  const slotByIdx = new Map();
  let slotToFaceArr = null;
  let lastWealthArr = null;
  let fireAtFrameArr = null;
  let fireMagnitudeArr = null;
  let castCount = 0;
  let initialized = false;
  let frameCounter = 0;

  // 32-bit hash to scatter consecutive idx values across the full
  // face index space, so adjacent slots land on far-apart triangles.
  function hashIdx(x) {
    x = ((x + 0x6D2B79F5) | 0) >>> 0;
    x = Math.imul(x ^ (x >>> 15), x | 1) >>> 0;
    x ^= x + Math.imul(x ^ (x >>> 7), x | 61);
    return (x ^ (x >>> 14)) >>> 0;
  }

  function initialLayout(snapshot) {
    castCount = snapshot.length;
    slotToFaceArr = new Int32Array(castCount);
    lastWealthArr = new Float32Array(castCount);
    fireAtFrameArr = new Float32Array(castCount);
    fireAtFrameArr.fill(-1);
    fireMagnitudeArr = new Float32Array(castCount);
    for (let slot = 0; slot < castCount; slot += 1) {
      const entry = snapshot[slot];
      slotByIdx.set(entry.idx, slot);
      slotToFaceArr[slot] = hashIdx(entry.idx + 1) % faceCount;
      lastWealthArr[slot] = NaN;
    }
    initialized = true;
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

      fireAtFrameArr[slot] = frameCounter + Math.random() * STAGGER_FRAMES;
      fireMagnitudeArr[slot] = delta;
    }
  }

  // Mapping wealth-delta magnitude → lifetime in frames.
  //   log1p(delta) / log1p(magnitudeRef) clamped to [0,1] scales
  //   linearly between min and max persist windows. Small events
  //   sit near MIN_PERSIST; large ones (delta ≥ magnitudeRef)
  //   pin at MAX_PERSIST.
  const _logRef = Math.log1p(magnitudeRef);
  function persistenceForMagnitude(delta) {
    let f = Math.log1p(Math.max(0, delta)) / _logRef;
    if (f > 1) f = 1;
    if (f < 0) f = 0;
    return minPersistFrames + (maxPersistFrames - minPersistFrames) * f;
  }

  function tick() {
    frameCounter += 1;

    // 1) Release any scheduled activations whose stagger window has
    //    arrived. Sets startFrame + persistFrames on the target face,
    //    overwriting any prior live activation (re-fires reset the
    //    triangle to full intensity).
    if (fireAtFrameArr !== null) {
      for (let slot = 0; slot < castCount; slot += 1) {
        const fr = fireAtFrameArr[slot];
        if (fr < 0) continue;
        if (frameCounter < fr) continue;

        const f = slotToFaceArr[slot];
        startFrameArr[f] = frameCounter;
        persistFramesArr[f] = persistenceForMagnitude(fireMagnitudeArr[slot]);
        fireAtFrameArr[slot] = -1;
      }
    }

    // 2) Per-face decay. Each live face linearly fades from
    //    activeColor at startFrame to baseColor at startFrame+persist.
    let anyDirty = false;
    for (let f = 0; f < faceCount; f += 1) {
      const start = startFrameArr[f];
      if (start < 0) continue;

      const age = frameCounter - start;
      const persist = persistFramesArr[f];

      let activity;
      if (age >= persist) {
        // Expired — write baseColor and clear.
        activity = 0;
        startFrameArr[f] = -1;
      } else {
        activity = 1 - age / persist;
      }

      const r = baseColor[0] + (activeColor[0] - baseColor[0]) * activity;
      const g = baseColor[1] + (activeColor[1] - baseColor[1]) * activity;
      const b = baseColor[2] + (activeColor[2] - baseColor[2]) * activity;

      const base = f * 9;
      colors[base + 0] = r; colors[base + 1] = g; colors[base + 2] = b;
      colors[base + 3] = r; colors[base + 4] = g; colors[base + 5] = b;
      colors[base + 6] = r; colors[base + 7] = g; colors[base + 8] = b;
      anyDirty = true;
    }
    if (anyDirty) geometry.getAttribute('color').needsUpdate = true;
  }

  function activeFaceCount() {
    let n = 0;
    for (let f = 0; f < faceCount; f += 1) {
      if (startFrameArr[f] >= 0) n += 1;
    }
    return n;
  }

  function setVisible(visible) { mesh.visible = !!visible; }

  function dispose() {
    scene.remove(mesh);
    geometry.dispose();
    material.dispose();
    slotByIdx.clear();
  }

  function diagnostics() {
    return { faceCount, castCount, activeFaces: activeFaceCount(), frame: frameCounter };
  }

  return { mesh, handleCastSnapshot, tick, setVisible, dispose, diagnostics };
}
