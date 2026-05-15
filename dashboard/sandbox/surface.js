// Surface — high-subdivision icosphere with always-visible grid and
// magnitude-driven activation persistence.
//
// The sphere is a high-subdivision icosahedron; the whole grid is
// rendered every frame via a barycentric-coordinate edge term in the
// fragment shader. Engine trade events activate individual triangles;
// the activation persistence (how long the triangle stays visible) is
// proportional to the magnitude of the wealth change that fired it,
// and the brightness decays linearly toward the base across that
// lifetime.
//
// Semantics (engine-tied axes only):
//   • Intensity (current brightness) ↔ recency. Just-fired triangles
//     read at full active colour; older ones blend back toward base.
//   • Lifetime (total visible duration) ↔ event magnitude. A
//     near-threshold wealth move keeps the triangle visible for ~1s;
//     a windfall persists 10+ seconds.
//   • Active-colour hue ↔ agent sector. Each fire mixes a low-chroma
//     sector tint into the dark active colour at sectorTintWeight.
//   • Persistence multiplier ↔ degree_centrality. High-degree agents
//     leave longer traces, normalised against the running max.
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
  // Sector tint table and mix weight. Empty palette / weight 0
  // disables the hue axis and falls back to pure activeColor.
  const sectorPalette = opts.sectorPalette ?? [];
  const sectorTintWeight = opts.sectorTintWeight ?? 0.0;
  // Top end of the persistFrames multiplier when an agent's
  // degree_centrality matches the running max. 1.0 disables the axis.
  const degreePersistBoost = opts.degreePersistBoost ?? 1.0;

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
  // Per-face active-colour target, baked at fire time from the
  // agent's sector tint. Decay loop lerps from baseColor to this
  // instead of the global activeColor.
  const faceActiveColorArr = new Float32Array(faceCount * 3);

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

  // Face centroids and 3-neighbour adjacency, precomputed once.
  // The agent module reads these to walk the icosphere as a graph
  // (each face has exactly 3 edge-sharing neighbours on a closed
  // triangulation). Build cost is O(F) with integer-key dedup of the
  // shared vertex positions.
  const positions = positionAttr.array;
  const faceCentroids = new Float32Array(faceCount * 3);
  for (let f = 0; f < faceCount; f += 1) {
    const v0 = f * 9;
    faceCentroids[f * 3 + 0] = (positions[v0 + 0] + positions[v0 + 3] + positions[v0 + 6]) / 3;
    faceCentroids[f * 3 + 1] = (positions[v0 + 1] + positions[v0 + 4] + positions[v0 + 7]) / 3;
    faceCentroids[f * 3 + 2] = (positions[v0 + 2] + positions[v0 + 5] + positions[v0 + 8]) / 3;
  }

  // Vertex dedup: positions are reproducible to within 0.1 unit on an
  // icosphere of this resolution, so rounding to 0.1 is safe.
  // Packed key encoding stays under 2^53 for radius ≤ 700.
  function pkey(x, y, z) {
    const xi = Math.round(x * 10) + 7000;
    const yi = Math.round(y * 10) + 7000;
    const zi = Math.round(z * 10) + 7000;
    return (xi * 16384 + yi) * 16384 + zi;
  }
  const vertMap = new Map();
  let nextVid = 0;
  const vertIds = new Int32Array(vertexCount);
  for (let v = 0; v < vertexCount; v += 1) {
    const k = pkey(positions[v * 3 + 0], positions[v * 3 + 1], positions[v * 3 + 2]);
    let id = vertMap.get(k);
    if (id === undefined) {
      id = nextVid;
      nextVid += 1;
      vertMap.set(k, id);
    }
    vertIds[v] = id;
  }

  // Edge → [face_a, face_b]. Pack (lo, hi) vertex IDs into a number.
  function ekey(a, b) {
    return a < b ? a * 1000000 + b : b * 1000000 + a;
  }
  const edgeMap = new Map();
  for (let f = 0; f < faceCount; f += 1) {
    const v0 = vertIds[f * 3 + 0];
    const v1 = vertIds[f * 3 + 1];
    const v2 = vertIds[f * 3 + 2];
    const e0 = ekey(v0, v1), e1 = ekey(v1, v2), e2 = ekey(v2, v0);
    let r = edgeMap.get(e0); if (!r) { r = [-1, -1]; edgeMap.set(e0, r); }
    if (r[0] === -1) r[0] = f; else if (r[1] === -1) r[1] = f;
    r = edgeMap.get(e1); if (!r) { r = [-1, -1]; edgeMap.set(e1, r); }
    if (r[0] === -1) r[0] = f; else if (r[1] === -1) r[1] = f;
    r = edgeMap.get(e2); if (!r) { r = [-1, -1]; edgeMap.set(e2, r); }
    if (r[0] === -1) r[0] = f; else if (r[1] === -1) r[1] = f;
  }
  const faceAdjacency = new Int32Array(faceCount * 3);
  faceAdjacency.fill(-1);
  for (let f = 0; f < faceCount; f += 1) {
    const v0 = vertIds[f * 3 + 0];
    const v1 = vertIds[f * 3 + 1];
    const v2 = vertIds[f * 3 + 2];
    const r0 = edgeMap.get(ekey(v0, v1));
    const r1 = edgeMap.get(ekey(v1, v2));
    const r2 = edgeMap.get(ekey(v2, v0));
    faceAdjacency[f * 3 + 0] = r0[0] === f ? r0[1] : r0[0];
    faceAdjacency[f * 3 + 1] = r1[0] === f ? r1[1] : r1[0];
    faceAdjacency[f * 3 + 2] = r2[0] === f ? r2[1] : r2[0];
  }
  // Map metadata is no longer needed; let GC reclaim it.
  vertMap.clear();
  edgeMap.clear();

  // Per-slot bookkeeping: idx → slot, last-seen wealth (for delta
  // detection), scheduled fire frame, scheduled magnitude, plus the
  // most-recent sector and degree_centrality for the agent in that
  // slot. Sector/degree are read at fire-release time so staggered
  // activations use the snapshot that scheduled them.
  const slotByIdx = new Map();
  let slotToFaceArr = null;
  let lastWealthArr = null;
  let fireAtFrameArr = null;
  let fireMagnitudeArr = null;
  let slotSectorArr = null;
  let slotDegreeArr = null;
  let castCount = 0;
  let initialized = false;
  let frameCounter = 0;
  // Running max degree_centrality. Used to normalise the persistence
  // multiplier without re-scanning all slots each tick.
  let maxDegreeSeen = 0;

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
    slotSectorArr = new Int8Array(castCount);
    slotSectorArr.fill(-1);
    slotDegreeArr = new Int32Array(castCount);
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

      // Latch the latest sector / degree before any fire scheduling
      // so the release path reads current values.
      const sec = entry.sector;
      if (typeof sec === 'number' && sec >= 0) {
        slotSectorArr[slot] = sec;
      }
      const deg = entry.degree_centrality;
      if (typeof deg === 'number' && deg > 0) {
        slotDegreeArr[slot] = deg;
        if (deg > maxDegreeSeen) maxDegreeSeen = deg;
      }

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

  // Resolve the per-face active colour at fire time: the dark
  // activeColor blended with the agent's sector tint at the configured
  // weight. A negative sector (no sector data yet) or empty palette
  // falls through to the unmixed activeColor.
  function activeColorForSector(sector, out, outBase) {
    let tr = activeColor[0];
    let tg = activeColor[1];
    let tb = activeColor[2];
    if (
      sectorTintWeight > 0 &&
      sector >= 0 &&
      sector < sectorPalette.length
    ) {
      const tint = sectorPalette[sector];
      const w = sectorTintWeight;
      tr = activeColor[0] * (1 - w) + tint[0] * w;
      tg = activeColor[1] * (1 - w) + tint[1] * w;
      tb = activeColor[2] * (1 - w) + tint[2] * w;
    }
    out[outBase + 0] = tr;
    out[outBase + 1] = tg;
    out[outBase + 2] = tb;
  }

  // Scale persistFrames by the slot's degree_centrality, normalised
  // against the running max. degree=0 (or maxDegreeSeen=0) leaves the
  // base lifetime untouched; the top-degree agent gets the full boost.
  function persistMultiplierForDegree(degree) {
    if (degreePersistBoost <= 1.0 || maxDegreeSeen <= 0 || degree <= 0) {
      return 1.0;
    }
    const t = degree / maxDegreeSeen;
    return 1.0 + (degreePersistBoost - 1.0) * (t > 1 ? 1 : t);
  }

  function tick() {
    frameCounter += 1;

    // 1) Release any scheduled activations whose stagger window has
    //    arrived. Sets startFrame + persistFrames on the target face,
    //    overwriting any prior live activation (re-fires reset the
    //    triangle to full intensity). The per-face active colour is
    //    baked from the agent's sector tint here, and the lifetime is
    //    scaled by the agent's normalised degree_centrality.
    if (fireAtFrameArr !== null) {
      for (let slot = 0; slot < castCount; slot += 1) {
        const fr = fireAtFrameArr[slot];
        if (fr < 0) continue;
        if (frameCounter < fr) continue;

        const f = slotToFaceArr[slot];
        startFrameArr[f] = frameCounter;
        const base = persistenceForMagnitude(fireMagnitudeArr[slot]);
        const mult = persistMultiplierForDegree(slotDegreeArr[slot]);
        persistFramesArr[f] = base * mult;
        activeColorForSector(slotSectorArr[slot], faceActiveColorArr, f * 3);
        fireAtFrameArr[slot] = -1;
      }
    }

    // 2) Per-face decay. Each live face linearly fades from its
    //    sector-tinted active colour at startFrame to baseColor at
    //    startFrame+persist.
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

      const ac = f * 3;
      const r = baseColor[0] + (faceActiveColorArr[ac + 0] - baseColor[0]) * activity;
      const g = baseColor[1] + (faceActiveColorArr[ac + 1] - baseColor[1]) * activity;
      const b = baseColor[2] + (faceActiveColorArr[ac + 2] - baseColor[2]) * activity;

      const cbase = f * 9;
      colors[cbase + 0] = r; colors[cbase + 1] = g; colors[cbase + 2] = b;
      colors[cbase + 3] = r; colors[cbase + 4] = g; colors[cbase + 5] = b;
      colors[cbase + 6] = r; colors[cbase + 7] = g; colors[cbase + 8] = b;
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
    return {
      faceCount,
      castCount,
      activeFaces: activeFaceCount(),
      frame: frameCounter,
      maxDegreeSeen,
    };
  }

  return {
    mesh,
    handleCastSnapshot,
    tick,
    setVisible,
    dispose,
    diagnostics,
    faceCount,
    faceCentroids,
    faceAdjacency,
    // The non-indexed positions array. Each face occupies 9
    // consecutive floats: v0(xyz), v1(xyz), v2(xyz). Read-only as
    // far as agents.js is concerned.
    facePositions: positions,
    radius,
  };
}
