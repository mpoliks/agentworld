// Surface — high-subdivision icosphere with always-visible grid,
// per-vertex altitude heightmap, and sector partition.
//
// The sphere is a high-subdivision icosahedron; the whole grid is
// rendered every frame via a barycentric-coordinate edge term in the
// fragment shader. Per-vertex altitude is a smoothed signed fraction
// of the base radius; the vertex shader displaces each vertex
// radially by (1 + (altitude + uGlobalAltitude) * uAltitudeScale).
// scene.js drives bumpAltitude() on trade/reject events and feeds
// EBI / fold_max_depth into the global modulation uniforms.
//
// The substrate also carries a 12-region sector partition (Voronoi
// over Fibonacci anchors); each face is tagged at startup and the
// hover path soft-outlines the hovered sector's boundary in-shader.
//
// Pass 26: the per-face wealth-Δ activation channel (carryover from
// the Pass-15 cells-on-sphere paradigm — flashed sector-tinted
// triangles at hashed per-agent home faces) was removed. The
// altitude bumps already carry wealth-Δ honestly and track the
// caterpillar's actual position, which the hashed activations did
// not. The per-vertex `color` attribute is now static at baseColor.

import * as THREE from 'three';

const DEFAULT_RADIUS = 700;
const DEFAULT_SUBDIVISIONS = 280;    // 20 × 281² ≈ 1,579,220 triangles.
                                     // 4× the original (140) build,
                                     // 2× the prior (198) build.
                                     // Cast doubled in lockstep so
                                     // per-face caterpillar density
                                     // stays put.

// Per-vertex `altitude` is a smoothed per-unique-vertex signed
// fraction of the base radius. The shader displaces each vertex
// radially by (1 + (altitude + uGlobalAltitude) * uAltitudeScale).
// Adjacent faces sharing a vertex agree on its altitude, so the
// mesh stays continuous instead of leaving cliffs.
//
// Very light shading is done per-vertex: the brightness multiplier
// vShade = 1 + altitude * uTiltShade is interpolated across each
// face. A flat patch (all 3 corners at same altitude) renders at
// constant shade; a tilted face (corners at different altitudes)
// shows a gradient from one corner to another — which reads as
// face angle. No screen-space derivatives, no extensions, GLSL1.
// Pass 19b: per-vertex altitude drives radial displacement. A second
// uniform additive offset (uGlobalAltitude) lets system-wide signals
// (EBI, reject fraction) bulge or contract the whole sphere on top
// of zonal bumps. uTiltShade folds altitude into a per-vertex
// brightness multiplier — peaks brighten, pits darken, tilted faces
// gradient between corners (very light, max ±8% at altitude=±0.20).
// Both global modulations are CLAMPED tightly on the JS side so the
// displacement formula can't reach the grid-killing extremes we hit
// earlier.
const VERTEX_SHADER = /* glsl */ `
  attribute vec3 color;
  attribute vec3 barycentric;
  attribute float altitude;
  attribute float sectorIdx;
  attribute vec3 sectorBoundary;
  uniform float uAltitudeScale;
  uniform float uGlobalAltitude;
  uniform float uTiltShade;
  // Pass 28: high-EBI chaos warp. Multi-frequency sinusoidal
  // displacement turns the sphere into a lumpy hyperspherical
  // shape as EBI ratchets up. Driven by uChaos in [0, 1].
  uniform float uChaos;
  uniform float uChaosAmplitude;
  varying vec3 vColor;
  varying vec3 vBary;
  varying float vShade;
  varying float vSector;
  varying vec3 vSectorBoundary;
  varying vec3 vSectorOverlayRGB;
  varying float vSectorOverlayAlpha;
  // Plan §B.1 — per-sector welfare overlay. Tints and alphas are
  // refreshed once per tick on the JS side and read here per-vertex
  // (sectorIdx is constant across a face's three corners). 12 sectors
  // ⇒ uniform arrays of length 12, indexed by int(sectorIdx + 0.5).
  uniform vec3 uSectorOverlayRGB[12];
  uniform float uSectorOverlayAlpha[12];

  vec3 chaosOffset(vec3 n) {
    // Three orthogonal sinusoidal trios so the lobes are 3D and
    // not planar. Frequencies are coprime-ish to avoid tiling.
    float a = sin(n.x * 3.7 + n.y * 5.1) * cos(n.z * 4.3);
    float b = sin(n.y * 7.2 + n.z * 3.9) * cos(n.x * 6.5);
    float c = sin(n.z * 5.8 + n.x * 4.1) * cos(n.y * 8.3);
    float d = sin(n.x * 11.0 + n.z * 13.0) * 0.4;
    float e = cos(n.y * 9.0 + n.x * 12.0) * 0.4;
    float f = sin(n.z * 10.5 + n.y * 14.0) * 0.4;
    return vec3(a + d, b + e, c + f);
  }

  void main() {
    vColor = color;
    vBary = barycentric;
    vSector = sectorIdx;
    vSectorBoundary = sectorBoundary;
    // Pin sector index → lookup once in the vertex stage and pass
    // through. GLSL ES 1.0 doesn't allow dynamic indexing in the
    // fragment stage, but a constant array index sourced from a
    // varying-but-flat attribute is fine in the vertex stage.
    int s = int(sectorIdx + 0.5);
    if (s < 0) s = 0; else if (s > 11) s = 11;
    vSectorOverlayRGB = uSectorOverlayRGB[s];
    vSectorOverlayAlpha = uSectorOverlayAlpha[s];
    float a = altitude + uGlobalAltitude;
    vec3 displaced = position * (1.0 + a * uAltitudeScale);
    if (uChaos > 0.0) {
      vec3 n = normalize(position);
      displaced += chaosOffset(n) * uChaos * uChaosAmplitude;
    }
    vShade = max(0.55, 1.0 + altitude * uTiltShade);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(displaced, 1.0);
  }
`;

const FRAGMENT_SHADER = /* glsl */ `
  precision highp float;

  uniform vec3 uEdgeColor;
  uniform float uEdgeThreshold;
  uniform vec3 uHoverOutline;
  uniform float uHoverBoundary;
  uniform float uHoverShade;
  uniform float uHoveredSector;

  varying vec3 vColor;
  varying vec3 vBary;
  varying float vShade;
  varying float vSector;
  varying vec3 vSectorBoundary;
  varying vec3 vSectorOverlayRGB;
  varying float vSectorOverlayAlpha;

  void main() {
    float minBary = min(vBary.x, min(vBary.y, vBary.z));
    bool inHovered = uHoveredSector >= 0.0 && abs(vSector - uHoveredSector) < 0.5;
    // Boundary detection: near an edge whose neighbour face is in a
    // different sector. Only painted when this face's sector matches
    // the hovered sector.
    bool nearBoundary = inHovered && (
      (vBary.x < uHoverBoundary && vSectorBoundary.x > 0.5) ||
      (vBary.y < uHoverBoundary && vSectorBoundary.y > 0.5) ||
      (vBary.z < uHoverBoundary && vSectorBoundary.z > 0.5)
    );
    vec3 col;
    if (nearBoundary) {
      col = uHoverOutline;
    } else if (minBary < uEdgeThreshold) {
      col = uEdgeColor;
    } else {
      // Plan §B.1 — mix in the regional welfare tint. Alpha capped
      // at 0.30 on the JS side so the sector-hover edge highlight
      // still survives. Edge and boundary fragments skip the mix so
      // the grid stays legible.
      col = mix(vColor, vSectorOverlayRGB, vSectorOverlayAlpha);
    }
    float hover = inHovered ? uHoverShade : 1.0;
    gl_FragColor = vec4(col * vShade * hover, 1.0);
  }
`;

export function createSurface(scene, opts = {}) {
  const radius = opts.radius ?? DEFAULT_RADIUS;
  const subdivisions = opts.subdivisions ?? DEFAULT_SUBDIVISIONS;
  const baseColor = opts.baseColor ?? [0.90, 0.89, 0.85];
  const edgeColor = opts.edgeColor ?? [0.62, 0.60, 0.55];
  const edgeThreshold = opts.edgeThreshold ?? 0.03;
  // Progress hook. scene.js wires this into the loader bar so the
  // user sees substrate-build progress during the ~5–7 sec
  // post-Three-geometry work at 2×/4× scaling. Three's
  // IcosahedronGeometry is one blocking call we can't interrupt;
  // the subsequent dedup + adjacency + sector partition is broken
  // into chunks here so the bar can move.
  const onProgress = typeof opts.onProgress === 'function'
    ? opts.onProgress : () => {};
  // Pass 18a heightmap parameters. altitudeMax caps |face altitude|
  // so runaway accumulation can't push the mesh inside-out.
  // altitudeDecay is per-frame multiplicative relaxation back toward
  // zero. altitudeBaseScale is the uniform multiplier in the shader
  // (modulated upward by EBI at runtime).
  // Asymmetric caps: positive (peaks) and negative (pits) clamp at
  // different magnitudes so the four inward forces (losses + stack
  // carve + rejects + decay) can't drown out the single positive
  // source. Pits floor early, peaks have headroom.
  const altitudeMaxPos = opts.altitudeMaxPos ?? 0.40;
  const altitudeMaxNeg = opts.altitudeMaxNeg ?? 0.12;
  // Slower decay (was 0.9991) so existing features persist longer —
  // combined with the concentration bias in bumpAltitude this lets
  // trenches and peaks accumulate rather than blurring back to flat.
  const altitudeDecay = opts.altitudeDecay ?? 0.9997;
  const altitudeBaseScale = opts.altitudeBaseScale ?? 1.0;

  onProgress(0.0, 'icosphere mesh');
  // High-subdivision icosphere. Face count = 20 * (subdivisions+1)².
  const geometry = new THREE.IcosahedronGeometry(radius, subdivisions);
  const positionAttr = geometry.getAttribute('position');
  const vertexCount = positionAttr.count;
  const faceCount = vertexCount / 3;
  onProgress(0.15, `${(faceCount / 1000).toFixed(0)}k faces`);

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

  // Per-unique-vertex altitude (Pass 18a). The icosphere geometry
  // is non-indexed so each face has its own three vertex copies; the
  // vertIds map (built below during adjacency) tells us which copies
  // share a physical position. Storing altitude per unique vertex
  // and replicating into the non-indexed attribute each tick gives
  // smooth continuity across face boundaries — each face becomes a
  // flat triangle whose three corners ramp into neighbours, instead
  // of a rigid radial block with cliffs at every edge.
  let vertAltitudes = null;      // Float32Array[uniqueVertCount], filled after vertIds is built
  const altitudeArr = new Float32Array(vertexCount);
  const altitudeAttr = new THREE.BufferAttribute(altitudeArr, 1);
  altitudeAttr.setUsage(THREE.DynamicDrawUsage);
  geometry.setAttribute('altitude', altitudeAttr);
  // Per-face altitude is derived (average of the face's three unique
  // vertex altitudes) and refreshed each tick. agents.js reads it
  // for the caterpillar segment lift.
  const faceAltitudes = new Float32Array(faceCount);

  // Plan §B.1 — pre-allocate the 12 sector overlay uniform slots.
  // RGB is the lerp target (cream for welfare-positive, copper-red
  // for welfare-negative). Alpha is the per-sector mix factor in
  // [0, 0.30] driven from the 30-tick wealth-Δ window.
  const sectorOverlayRGBArr = [];
  const sectorOverlayAlphaArr = new Float32Array(12);
  for (let k = 0; k < 12; k += 1) sectorOverlayRGBArr.push(new THREE.Vector3(0, 0, 0));

  const material = new THREE.ShaderMaterial({
    vertexShader: VERTEX_SHADER,
    fragmentShader: FRAGMENT_SHADER,
    uniforms: {
      uEdgeColor: { value: new THREE.Color().fromArray(edgeColor) },
      uEdgeThreshold: { value: edgeThreshold },
      uAltitudeScale: { value: altitudeBaseScale },
      uGlobalAltitude: { value: 0.0 },
      uTiltShade: { value: 1.8 },
      // Sector hover (Pass 22). uHoveredSector = -1 means no hover.
      // uHoverBoundary thickens the boundary edge band (~0.10 ≈ 30%
      // of face width). uHoverShade brightens the hovered sector
      // very lightly. uHoverOutline is a soft sandy blue.
      uHoveredSector: { value: -1.0 },
      uHoverBoundary: { value: 0.10 },
      uHoverShade: { value: 1.06 },
      uHoverOutline: { value: new THREE.Color(0.40, 0.55, 0.78) },
      uChaos: { value: 0.0 },
      // 18% of radius at max chaos — visible lobes without
      // breaking the silhouette so badly the sphere reads as garbage.
      uChaosAmplitude: { value: radius * 0.18 },
      uSectorOverlayRGB:  { value: sectorOverlayRGBArr },
      uSectorOverlayAlpha:{ value: sectorOverlayAlphaArr },
    },
    side: THREE.FrontSide,
    transparent: false,
    depthWrite: true,
  });

  const mesh = new THREE.Mesh(geometry, material);
  mesh.frustumCulled = false;
  scene.add(mesh);
  onProgress(0.30, 'face centroids');

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

  onProgress(0.45, 'vertex dedup');
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

  onProgress(0.65, 'edge adjacency');
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
  // Now that the unique-vertex count is known, allocate per-vertex
  // altitudes. vertIds maps each non-indexed vertex into this array.
  const uniqueVertCount = nextVid;
  vertAltitudes = new Float32Array(uniqueVertCount);
  // Pending-altitude pool. bumpAltitude() deposits the (already-
  // clamped) magnitude here instead of straight onto vertAltitudes;
  // tick() drains a fixed fraction per frame so the displacement
  // ramps smoothly across the rAF cycle instead of jumping once
  // per engine tick. Time constant ≈ 10 frames at PENDING_DRAIN_RATE
  // = 0.10 — about 170 ms at 60 fps, which is shorter than the
  // engine's ~250 ms tick interval so successive ticks blend.
  const pendingAltitudes = new Float32Array(uniqueVertCount);
  // 0.04 per frame ≈ 1.6 s effective time constant — longer than
  // the engine's ~0.5–1 s tick interval, so the prior batch's
  // ramp is still drifting in when the next batch lands. This is
  // what kills the half-second pulse the user reported.
  const PENDING_DRAIN_RATE = 0.04;
  // Per-vertex hard cap on pending magnitude so a runaway burst on
  // a single face can't accumulate an unboundedly tall residual.
  const PENDING_CAP = 0.30;

  onProgress(0.85, 'sector partition');
  // Sector partition (Pass 22). 12 Fibonacci-distributed anchor
  // points on the unit sphere; each face is tagged with the sector
  // whose anchor is closest to its centroid. The K=12 engine sector
  // enum maps 1:1 onto these regions — agent walks are filtered to
  // same-sector neighbours, so each economic sector visibly occupies
  // its own contiguous patch of the substrate.
  const sectorCount = opts.sectorCount ?? 12;
  const sectorAnchors = new Float32Array(sectorCount * 3);
  {
    const golden = Math.PI * (3 - Math.sqrt(5));
    for (let k = 0; k < sectorCount; k += 1) {
      const y = sectorCount === 1 ? 0 : 1 - (k / (sectorCount - 1)) * 2;
      const rxz = Math.sqrt(Math.max(0, 1 - y * y));
      const theta = golden * k;
      sectorAnchors[k * 3 + 0] = Math.cos(theta) * rxz;
      sectorAnchors[k * 3 + 1] = y;
      sectorAnchors[k * 3 + 2] = Math.sin(theta) * rxz;
    }
  }
  const faceSector = new Int8Array(faceCount);
  const facesBySector = new Array(sectorCount);
  for (let k = 0; k < sectorCount; k += 1) facesBySector[k] = [];
  for (let f = 0; f < faceCount; f += 1) {
    const cx = faceCentroids[f * 3 + 0];
    const cy = faceCentroids[f * 3 + 1];
    const cz = faceCentroids[f * 3 + 2];
    const cn = Math.sqrt(cx * cx + cy * cy + cz * cz) || 1;
    const ux = cx / cn, uy = cy / cn, uz = cz / cn;
    let best = 0, bestDot = -Infinity;
    for (let k = 0; k < sectorCount; k += 1) {
      const ax = sectorAnchors[k * 3 + 0];
      const ay = sectorAnchors[k * 3 + 1];
      const az = sectorAnchors[k * 3 + 2];
      const d = ux * ax + uy * ay + uz * az;
      if (d > bestDot) { bestDot = d; best = k; }
    }
    faceSector[f] = best;
    facesBySector[best].push(f);
  }

  // Per-vertex sector + boundary attributes for the hover render
  // path. sectorIdx is the face's sector replicated to its 3
  // vertices; sectorBoundary is a vec3 flag triple where each
  // component is 1.0 if the edge OPPOSITE that vertex is a sector
  // boundary (neighbour face has a different sector).
  const sectorArr = new Float32Array(vertexCount);
  const sectorBoundaryArr = new Float32Array(vertexCount * 3);
  for (let f = 0; f < faceCount; f += 1) {
    const sf = faceSector[f];
    sectorArr[f * 3 + 0] = sf;
    sectorArr[f * 3 + 1] = sf;
    sectorArr[f * 3 + 2] = sf;
    // faceAdjacency[f*3 + e] = neighbour across edge e:
    //   e=0: edge (v0,v1) — opposite v2
    //   e=1: edge (v1,v2) — opposite v0
    //   e=2: edge (v2,v0) — opposite v1
    const n01 = faceAdjacency[f * 3 + 0];
    const n12 = faceAdjacency[f * 3 + 1];
    const n20 = faceAdjacency[f * 3 + 2];
    const b0 = (n12 >= 0 && faceSector[n12] !== sf) ? 1 : 0;   // opp v0
    const b1 = (n20 >= 0 && faceSector[n20] !== sf) ? 1 : 0;   // opp v1
    const b2 = (n01 >= 0 && faceSector[n01] !== sf) ? 1 : 0;   // opp v2
    const fb = f * 9;
    sectorBoundaryArr[fb + 0] = b0; sectorBoundaryArr[fb + 1] = b1; sectorBoundaryArr[fb + 2] = b2;
    sectorBoundaryArr[fb + 3] = b0; sectorBoundaryArr[fb + 4] = b1; sectorBoundaryArr[fb + 5] = b2;
    sectorBoundaryArr[fb + 6] = b0; sectorBoundaryArr[fb + 7] = b1; sectorBoundaryArr[fb + 8] = b2;
  }
  geometry.setAttribute('sectorIdx', new THREE.BufferAttribute(sectorArr, 1));
  geometry.setAttribute('sectorBoundary', new THREE.BufferAttribute(sectorBoundaryArr, 3));

  let frameCounter = 0;

  // Per-sector welfare accumulator. EMA: bumpAltitude(faceIdx, m)
  // deposits m into sectorTotals[faceSector[faceIdx]]; tick() decays
  // the totals at SECTOR_DECAY each frame (~3 s half-life). Pure
  // continuous evolution — no ring buffer cycle to produce a visible
  // pulse at the cycle frequency.
  const sectorTotals = new Float32Array(12);
  // Palette: cream for welfare-positive, faint copper for negative.
  // Subdued so the substrate's existing sector-hover blue still
  // wins the visual fight when the user hovers a region.
  const TINT_POSITIVE = new THREE.Vector3(0.96, 0.92, 0.80);  // light cream
  const TINT_NEGATIVE = new THREE.Vector3(0.76, 0.51, 0.41);  // faint copper
  const TINT_ZERO = new THREE.Vector3(0.0, 0.0, 0.0);
  // The denominator above which |sectorTotal| reads as alpha cap.
  // 30 ticks × 5,000 bumps/tick × 0.06 per-event cap = 9,000 ceiling;
  // hitting ~60 of those bumps in a single sector saturates the tint.
  // Max alpha dropped from 0.30 (plan default) to 0.15 — at 0.30 the
  // cream tint washes the substrate enough that the sector-tinted
  // caterpillars lose contrast against it. 0.15 keeps the regional
  // signal legible while leaving the caterpillars' colour as the
  // dominant feature.
  const SECTOR_TINT_DENOM = 3.0;
  const SECTOR_TINT_MAX_ALPHA = 0.15;

  // Pass 18a heightmap state. foldCascadeMultiplier is set per step
  // from fold_max_depth, so deep cascades amplify the radial impact
  // of subsequent wealth-delta bumps. altitudeScale is mutated per
  // step from EBI so high-baroque economies get dramatic terrain.
  let foldCascadeMultiplier = 1.0;
  function setFoldCascadeMultiplier(m) {
    if (Number.isFinite(m)) foldCascadeMultiplier = m;
  }
  // Both setters clamp tightly. Earlier (Pass 19) loose ranges drove
  // the displacement into regimes where the grid edges vanished from
  // the substrate render; these clamps cap how far the global
  // modulation can stretch the geometry while still letting EBI and
  // reject fraction nudge it visibly.
  // Plan §B.2 widens this clamp so the EBI-driven altitude scale can
  // ride the smoothstep(2.0, 4.0) curve from 0.6 (calibrated band)
  // up to 2.0 (lobed band). The original [0.9, 1.10] range was set
  // when EBI only modulated by ±0.10 — too tight to carry the lobed-
  // regime amplification this phase introduces.
  function setAltitudeScale(s) {
    if (!Number.isFinite(s)) return;
    if (s < 0.5) s = 0.5;
    else if (s > 2.1) s = 2.1;
    material.uniforms.uAltitudeScale.value = s;
  }
  function setGlobalAltitude(g) {
    if (!Number.isFinite(g)) return;
    if (g < -0.03) g = -0.03;
    else if (g > 0.03) g = 0.03;
    material.uniforms.uGlobalAltitude.value = g;
  }
  function setHoveredSector(idx) {
    material.uniforms.uHoveredSector.value =
      Number.isFinite(idx) && idx >= 0 ? idx : -1.0;
  }
  function setChaos(t) {
    if (!Number.isFinite(t)) return;
    if (t < 0) t = 0; else if (t > 1) t = 1;
    material.uniforms.uChaos.value = t;
  }
  // Two per-event bump caps. Random walks across "empty" faces
  // hit the tight cap (deformations barely register out of
  // nowhere); bumps that align with an existing feature get the
  // loose cap (peaks/pits accumulate where they already started).
  // The gap between the two caps is what produces concentration —
  // without it, both kinds of bumps would saturate identically.
  const PER_EVENT_BUMP_CAP_PLAIN     = 0.012;
  const PER_EVENT_BUMP_CAP_AMPLIFIED = 0.08;
  // Concentration bias: bumps applied on faces that already have
  // same-sign altitude get amplified (positive feedback: peaks
  // attract more positive bumps, pits attract more negative ones);
  // bumps opposing the local altitude get attenuated. This is what
  // turns the previously-uniform "everywhere a little" deformation
  // into discrete concentrated trenches and peaks.
  const CONCENTRATION_GAIN = 6.0;        // amplification ramp per unit |alt|
  const CONCENTRATION_OPPOSE = 0.30;     // factor for opposing-sign bumps
  function bumpAltitude(faceIdx, magnitude) {
    if (faceIdx < 0 || faceIdx >= faceCount) return;
    let m = magnitude * foldCascadeMultiplier;
    if (m === 0) return;
    // Concentration bias from a neighbor-averaged altitude — not
    // just the bumped face. This lets features grow RADIALLY:
    // a bump on a face adjacent to an existing peak gets amplified
    // even if the face itself was flat. Without this, features
    // only thickened in place and stayed point-sized; with it,
    // peaks and trenches spread to cover groups of faces.
    const adjOffset = faceIdx * 3;
    const n0 = faceAdjacency[adjOffset + 0];
    const n1 = faceAdjacency[adjOffset + 1];
    const n2 = faceAdjacency[adjOffset + 2];
    const selfAlt = faceAltitudes[faceIdx];
    // Weighted mean: self counts triple so the bumped face still
    // dominates the local read, but neighbour influence is enough
    // for a fresh face near a feature to inherit the amplification.
    const baseAlt = (
      selfAlt * 3
      + (n0 >= 0 ? faceAltitudes[n0] : 0)
      + (n1 >= 0 ? faceAltitudes[n1] : 0)
      + (n2 >= 0 ? faceAltitudes[n2] : 0)
    ) / 6;
    // Probabilistic skip on truly-flat faces. A bump landing where
    // there's no existing altitude (and no neighbouring altitude)
    // only survives ~5 % of the time. The rest fizzle. This kills
    // the uniform pockmarking that comes from agents walking
    // randomly across the sphere and dumping bumps everywhere —
    // most random bumps disappear, the few that survive seed
    // features, and the concentration bias above grows those
    // features into mountains and trenches. Without the skip, the
    // bias only sharpens an underlying uniform pattern.
    const FLAT_THRESHOLD = 0.012;
    const FLAT_SURVIVAL = 0.05;
    if (Math.abs(baseAlt) < FLAT_THRESHOLD && Math.random() > FLAT_SURVIVAL) {
      return;
    }
    let amplified = false;
    if (baseAlt !== 0) {
      const sameSign = (baseAlt > 0 && m > 0) || (baseAlt < 0 && m < 0);
      if (sameSign) {
        const mult = 1 + Math.min(3.0, Math.abs(baseAlt) * CONCENTRATION_GAIN);
        m *= mult;
        amplified = true;
      } else {
        m *= CONCENTRATION_OPPOSE;
      }
    }
    const cap = amplified ? PER_EVENT_BUMP_CAP_AMPLIFIED : PER_EVENT_BUMP_CAP_PLAIN;
    if (m >  cap) m =  cap;
    else if (m < -cap) m = -cap;
    if (m === 0) return;
    const base = faceIdx * 3;
    const u0 = vertIds[base + 0];
    const u1 = vertIds[base + 1];
    const u2 = vertIds[base + 2];
    // Deposit into the pending pool instead of applying immediately.
    // tick() drains 10%/frame into vertAltitudes, so the displacement
    // ramps smoothly across the rAF cycle instead of stepping once
    // per engine tick.
    let p;
    p = pendingAltitudes[u0] + m;
    if (p >  PENDING_CAP) p =  PENDING_CAP;
    else if (p < -PENDING_CAP) p = -PENDING_CAP;
    pendingAltitudes[u0] = p;
    p = pendingAltitudes[u1] + m;
    if (p >  PENDING_CAP) p =  PENDING_CAP;
    else if (p < -PENDING_CAP) p = -PENDING_CAP;
    pendingAltitudes[u1] = p;
    p = pendingAltitudes[u2] + m;
    if (p >  PENDING_CAP) p =  PENDING_CAP;
    else if (p < -PENDING_CAP) p = -PENDING_CAP;
    pendingAltitudes[u2] = p;
    // Record the signed magnitude into the per-sector EMA totals
    // for the welfare overlay. Reads the clamped value so the tint
    // matches what the substrate displaces.
    const sec = faceSector[faceIdx];
    sectorTotals[sec] += m;
  }

  function tick() {
    frameCounter += 1;

    // Drain the pending-altitude pool into vertAltitudes. Each frame
    // transfers PENDING_DRAIN_RATE of the residual; this turns the
    // bursty engine-tick deposits into a smooth ramp instead of a
    // single-frame jump. Then the normal decay runs.
    for (let u = 0; u < uniqueVertCount; u += 1) {
      const p = pendingAltitudes[u];
      if (p === 0) continue;
      const delta = p * PENDING_DRAIN_RATE;
      pendingAltitudes[u] = p - delta;
      if (Math.abs(pendingAltitudes[u]) < 1e-5) pendingAltitudes[u] = 0;
      let a = vertAltitudes[u] + delta;
      if (a > altitudeMaxPos) a = altitudeMaxPos;
      else if (a < -altitudeMaxNeg) a = -altitudeMaxNeg;
      vertAltitudes[u] = a;
    }

    // Altitude decay on the unique-vertex store, then replicate to
    // the non-indexed attribute and to the per-face average (which
    // agents.js reads for caterpillar lift). Per-vertex storage means
    // adjacent faces sharing a vertex agree on its height, so the
    // displaced mesh stays continuous instead of cliffed.
    let anyNonZero = false;
    for (let u = 0; u < uniqueVertCount; u += 1) {
      let a = vertAltitudes[u];
      if (a === 0) continue;
      a *= altitudeDecay;
      if (a < 1e-5 && a > -1e-5) a = 0;
      vertAltitudes[u] = a;
      if (a !== 0) anyNonZero = true;
    }
    // Always refresh — agents.js depends on faceAltitudes for the
    // caterpillar segment lift even on frames where everything
    // decays to zero (so segments settle back to base radius).
    for (let v = 0; v < vertexCount; v += 1) {
      altitudeArr[v] = vertAltitudes[vertIds[v]];
    }
    for (let f = 0; f < faceCount; f += 1) {
      const b = f * 3;
      faceAltitudes[f] = (
        vertAltitudes[vertIds[b + 0]] +
        vertAltitudes[vertIds[b + 1]] +
        vertAltitudes[vertIds[b + 2]]
      ) / 3;
    }
    altitudeAttr.needsUpdate = true;
    void anyNonZero;  // reserved for future dirty-skip optimisation

    // EMA-based sector accumulator. Replaces the prior 30-slot ring
    // buffer, which cycled every 0.5 s and produced a perceptible
    // pulse whenever a sector's bumps clumped into a couple of slots
    // that then got zeroed on cycle-out. The EMA decays continuously
    // every frame (~3 s half-life), so the tint evolves smoothly
    // regardless of the engine tick cadence. bumpAltitude deposits
    // straight into sectorTotals; this loop just decays.
    const SECTOR_DECAY = 0.9962;   // ≈ 3 s half-life at 60 fps
    for (let k = 0; k < 12; k += 1) {
      sectorTotals[k] *= SECTOR_DECAY;
      if (Math.abs(sectorTotals[k]) < 1e-5) sectorTotals[k] = 0;
    }
    // Push to uniforms. Lerp toward TINT_POSITIVE or TINT_NEGATIVE
    // depending on sign; alpha is |total| / SECTOR_TINT_DENOM
    // saturated at SECTOR_TINT_MAX_ALPHA.
    for (let k = 0; k < 12; k += 1) {
      const v = sectorTotals[k];
      const mag = Math.abs(v);
      let alpha = mag / SECTOR_TINT_DENOM;
      if (alpha > SECTOR_TINT_MAX_ALPHA) alpha = SECTOR_TINT_MAX_ALPHA;
      sectorOverlayAlphaArr[k] = alpha;
      const tint = v > 0 ? TINT_POSITIVE : (v < 0 ? TINT_NEGATIVE : TINT_ZERO);
      sectorOverlayRGBArr[k].copy(tint);
    }
  }

  function setVisible(visible) { mesh.visible = !!visible; }

  // Restart hook — zero the heightmap so the substrate snaps back
  // to base radius instead of slow-decaying over ~115s at the
  // 0.9991/frame relaxation rate.
  function resetHeightmap() {
    if (vertAltitudes) vertAltitudes.fill(0);
    if (pendingAltitudes) pendingAltitudes.fill(0);
    faceAltitudes.fill(0);
    altitudeArr.fill(0);
    altitudeAttr.needsUpdate = true;
    // Clear the per-sector EMA so a Restart snaps the overlay back
    // to neutral instead of fading over its half-life.
    sectorTotals.fill(0);
    for (let k = 0; k < 12; k += 1) {
      sectorOverlayAlphaArr[k] = 0;
      sectorOverlayRGBArr[k].copy(TINT_ZERO);
    }
  }

  function dispose() {
    scene.remove(mesh);
    geometry.dispose();
    material.dispose();
  }

  function diagnostics() {
    return {
      faceCount,
      frame: frameCounter,
      sectorTotals: Array.from(sectorTotals),
      sectorOverlayAlpha: Array.from(sectorOverlayAlphaArr),
      altitudeScale: material.uniforms.uAltitudeScale.value,
      perEventBumpCap: PER_EVENT_BUMP_CAP_AMPLIFIED,
    };
  }

  return {
    mesh,
    tick,
    setVisible,
    resetHeightmap,
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
    // Heightmap (Pass 18a). agents.js reads faceAltitudes to lift
    // caterpillar segments onto the deformed terrain, and calls
    // bumpAltitude() on wealth-delta events to write into it.
    // scene.js drives setFoldCascadeMultiplier / setAltitudeScale
    // from per-step engine metrics.
    faceAltitudes,
    // Per-unique-vertex altitudes + the non-indexed → unique map.
    // agents.js reads these to lift each segment vertex by its
    // matching face-vertex altitude, so segments stay on the
    // substrate's tilted plane instead of riding the face average.
    vertAltitudes,
    vertIds,
    // Sector partition (Pass 22). faceSector[f] in [0, sectorCount-1];
    // facesBySector[k] is the list of face indices in sector k.
    faceSector,
    facesBySector,
    sectorCount,
    sectorAnchors,
    bumpAltitude,
    setFoldCascadeMultiplier,
    setAltitudeScale,
    setGlobalAltitude,
    setHoveredSector,
    setChaos,
  };
}
