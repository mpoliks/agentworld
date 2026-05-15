// Surface — high-subdivision icosphere with a per-fragment wireframe.
//
// The sphere itself IS the visualisation: thousands of tiny triangles
// cover its surface, the grid is rendered always-on via a barycentric
// edge term in the fragment shader, and engine events fill in
// individual triangles in greyscale. Light mode throughout.
//
// Why barycentric edges instead of a separate WireframeGeometry:
//   • Same draw call as the fills.
//   • Constant 1-pixel-wide edges that anti-alias correctly at any
//     zoom (fwidth-driven).
//   • No second buffer the size of the geometry to upload.

import * as THREE from 'three';

const DEFAULT_RADIUS = 700;
const DEFAULT_SUBDIVISIONS = 100;    // 20 × 101² ≈ 204,020 faces
const DEFAULT_FADE_RATE = 0.90;
const ACTIVATION_FLOOR = 0.012;

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

// Fragment: writes the face fill color, but if the fragment is close
// to a triangle edge (min barycentric below an fwidth-derived
// threshold), it blends toward the edge colour instead. Result is a
// consistent grid line drawn through every triangle's boundary.
const FRAGMENT_SHADER = /* glsl */ `
  #extension GL_OES_standard_derivatives : enable
  precision highp float;

  uniform vec3 uEdgeColor;
  uniform float uEdgeWidthPx;

  varying vec3 vColor;
  varying vec3 vBary;

  void main() {
    float minBary = min(vBary.x, min(vBary.y, vBary.z));
    // fwidth of the min-barycentric tells us the screen-space rate of
    // change. Multiplying by the desired pixel width gives the band
    // we need to smoothly fade between edge and fill colours.
    float w = fwidth(minBary) * uEdgeWidthPx;
    float edge = smoothstep(0.0, w, minBary);
    vec3 col = mix(uEdgeColor, vColor, edge);
    gl_FragColor = vec4(col, 1.0);
  }
`;

/**
 * Build the tessellated-surface renderer.
 */
export function createSurface(scene, opts = {}) {
  const radius = opts.radius ?? DEFAULT_RADIUS;
  const subdivisions = opts.subdivisions ?? DEFAULT_SUBDIVISIONS;
  const fadeRate = opts.fadeRate ?? DEFAULT_FADE_RATE;
  const baseColor = opts.baseColor ?? [0.93, 0.93, 0.93];
  const activeColor = opts.activeColor ?? [0.08, 0.08, 0.08];
  const edgeColor = opts.edgeColor ?? [0.55, 0.55, 0.55];
  const edgeWidthPx = opts.edgeWidthPx ?? 1.0;
  const activationThreshold = opts.activationThreshold ?? 0.01;

  // High-subdivision icosphere. Three.js's PolyhedronGeometry uses
  // linear edge subdivision: faces = 20 * (subdivisions + 1)².
  const geometry = new THREE.IcosahedronGeometry(radius, subdivisions);
  const positionAttr = geometry.getAttribute('position');
  const vertexCount = positionAttr.count;
  const faceCount = vertexCount / 3;

  // Per-vertex color, initialised to baseColor.
  const colors = new Float32Array(vertexCount * 3);
  for (let v = 0; v < vertexCount; v += 1) {
    colors[v * 3 + 0] = baseColor[0];
    colors[v * 3 + 1] = baseColor[1];
    colors[v * 3 + 2] = baseColor[2];
  }
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

  // Barycentric attribute — every triangle gets (1,0,0), (0,1,0),
  // (0,0,1) on its three vertices so the fragment shader can derive
  // distance to nearest edge.
  const bary = new Float32Array(vertexCount * 3);
  for (let f = 0; f < faceCount; f += 1) {
    const base = f * 9;
    bary[base + 0] = 1; bary[base + 1] = 0; bary[base + 2] = 0;
    bary[base + 3] = 0; bary[base + 4] = 1; bary[base + 5] = 0;
    bary[base + 6] = 0; bary[base + 7] = 0; bary[base + 8] = 1;
  }
  geometry.setAttribute('barycentric', new THREE.BufferAttribute(bary, 3));

  const activities = new Float32Array(faceCount);
  const activeColors = new Float32Array(faceCount * 3);
  for (let f = 0; f < faceCount; f += 1) {
    activeColors[f * 3 + 0] = activeColor[0];
    activeColors[f * 3 + 1] = activeColor[1];
    activeColors[f * 3 + 2] = activeColor[2];
  }

  const material = new THREE.ShaderMaterial({
    vertexShader: VERTEX_SHADER,
    fragmentShader: FRAGMENT_SHADER,
    uniforms: {
      uEdgeColor: { value: new THREE.Color().fromArray(edgeColor) },
      uEdgeWidthPx: { value: edgeWidthPx },
    },
    side: THREE.FrontSide,
    transparent: false,
    depthWrite: true,
    extensions: {
      derivatives: true,
    },
  });

  const mesh = new THREE.Mesh(geometry, material);
  mesh.frustumCulled = false;
  scene.add(mesh);

  const slotByIdx = new Map();
  let slotToFaceArr = null;
  let lastWealthArr = null;
  let castCount = 0;
  let initialized = false;

  // mulberry32-style hash to scatter consecutive idx values across the
  // full face index space, so adjacent slots don't end up on adjacent
  // triangles.
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

      if (Math.abs(w - prev) < activationThreshold) continue;
      activities[slotToFaceArr[slot]] = 1.0;
    }
  }

  function tick() {
    let anyDirty = false;
    for (let f = 0; f < faceCount; f += 1) {
      if (activities[f] <= 0) continue;

      activities[f] *= fadeRate;
      if (activities[f] < ACTIVATION_FLOOR) activities[f] = 0;

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
    }
    if (anyDirty) geometry.getAttribute('color').needsUpdate = true;
  }

  function activeFaceCount() {
    let n = 0;
    for (let f = 0; f < faceCount; f += 1) if (activities[f] > 0) n += 1;
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
    return { faceCount, castCount, activeFaces: activeFaceCount() };
  }

  return { mesh, handleCastSnapshot, tick, setVisible, dispose, diagnostics };
}
