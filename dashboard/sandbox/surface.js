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
  // Inequality pinch. uPinchAxis is a unit vector; uPinchStrength
  // is signed: > 0 elongates the sphere along the axis (prolate),
  // < 0 flattens it (oblate). |strength| ≤ ~0.18 so the silhouette
  // still reads as a sphere with an axial bulge or squash. Driven
  // from a Gini-derived signal in scene.js; default 0 = no pinch.
  uniform vec3  uPinchAxis;
  uniform float uPinchStrength;
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
    // Inequality pinch: pull each vertex along uPinchAxis by an
    // amount proportional to its projection onto the axis. Positive
    // strength = prolate (stretched along axis); negative = oblate
    // (compressed along axis). Independent of altitude and chaos, so
    // a calm regime with very high Gini still bulges visibly.
    if (uPinchStrength != 0.0) {
      float proj = dot(position, uPinchAxis);
      displaced += uPinchAxis * proj * uPinchStrength;
    }
    // Asymmetric tilt shade: valleys darken at full gain (trenches
    // and basins still read as shadow against the base gray), but
    // peaks brighten on a heavily attenuated curve so the dominant
    // sector's elevated continent stays close to the substrate's
    // base gray instead of bleaching to white. A hard ceiling at
    // 1.10 caps the brightest face at ~10 % above base, which
    // reads as a subtle ridge rather than a bright plateau.
    float tiltRaw = altitude * uTiltShade;
    if (tiltRaw > 0.0) tiltRaw *= 0.25;
    vShade = clamp(1.0 + tiltRaw, 0.55, 1.10);
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
  // vertDisplayAlt is allocated AFTER uniqueVertCount is computed —
  // see below, near the vertAltitudes allocation block.

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
      // Pinch defaults: no pinch, axis along Y (irrelevant when
      // strength=0). scene.js picks a stable random axis at session
      // start and pushes a Gini-derived strength in [-0.18, +0.18].
      uPinchAxis: { value: new THREE.Vector3(0, 1, 0) },
      uPinchStrength: { value: 0.0 },
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
  // Per-unique-vertex DISPLAY altitude — the same value the substrate
  // shader receives via the `altitude` attribute. External consumers
  // (agents.js, firms.js, cluster_overlay.js, edges.js, folds.js)
  // must read this when lifting their geometry onto the substrate;
  // vertAltitudes alone is the bump-driven layer and excludes the
  // per-sector continent (vertSectorBase) and border-trench
  // (vertBoundaryTrench) contributions.
  const vertDisplayAlt = new Float32Array(uniqueVertCount);
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
  // Snapshot of the static Fibonacci anchors. resetHeightmap()
  // restores them so a Restart returns to the canonical partition
  // even after a session of anchor drift. faceSectorInitial is
  // populated below once the static partition is computed.
  const sectorAnchorsInitial = new Float32Array(sectorAnchors);
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
  // Frozen copy of the canonical partition for reset.
  const faceSectorInitial = new Int8Array(faceSector);

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
  // Both attributes mutate at runtime — sectorIdx changes when a
  // boundary face migrates to a different sector; sectorBoundary
  // changes whenever any face flips, since neighbour-side flags are
  // sector-dependent. Mark them dynamic and keep handles so the
  // Voronoi reassignment loop can flag needsUpdate.
  const sectorIdxAttr = new THREE.BufferAttribute(sectorArr, 1);
  const sectorBoundaryAttr = new THREE.BufferAttribute(sectorBoundaryArr, 3);
  sectorIdxAttr.setUsage(THREE.DynamicDrawUsage);
  sectorBoundaryAttr.setUsage(THREE.DynamicDrawUsage);
  geometry.setAttribute('sectorIdx', sectorIdxAttr);
  geometry.setAttribute('sectorBoundary', sectorBoundaryAttr);

  let frameCounter = 0;

  // Per-vertex sector mix. Stored as raw incidence COUNTS so that
  // when face f migrates from s_old → s_new we can update three
  // vertices in O(1) by decrementing/incrementing their counters. The
  // normalised weight Σ_s vertSectorWeights[u·12 + s] = 1 is derived
  // from counts / vertIncidence and rebuilt lazily when a face has
  // migrated.
  //
  // Counts are signed (Int16) because the Voronoi reassignment writes
  // a +1 / -1 delta per migration; capacity 2¹⁵ is far above any
  // physical incidence (6 for an interior vertex, 5 for the 12
  // icosahedron poles).
  const vertSectorCounts = new Int16Array(uniqueVertCount * 12);
  const vertIncidence = new Int16Array(uniqueVertCount);
  const vertSectorWeights = new Float32Array(uniqueVertCount * 12);
  // Per-vertex dirty bit. Migration sets it; _refreshVertWeights()
  // drains it before _recomputeVertSectorBase runs.
  const vertWeightsDirty = new Uint8Array(uniqueVertCount);
  for (let f = 0; f < faceCount; f += 1) {
    const s = faceSector[f];
    const u0 = vertIds[f * 3 + 0];
    const u1 = vertIds[f * 3 + 1];
    const u2 = vertIds[f * 3 + 2];
    vertSectorCounts[u0 * 12 + s] += 1;
    vertSectorCounts[u1 * 12 + s] += 1;
    vertSectorCounts[u2 * 12 + s] += 1;
    vertIncidence[u0] += 1; vertIncidence[u1] += 1; vertIncidence[u2] += 1;
  }
  for (let u = 0; u < uniqueVertCount; u += 1) {
    const c = vertIncidence[u] || 1;
    const inv = 1 / c;
    for (let s = 0; s < 12; s += 1) {
      vertSectorWeights[u * 12 + s] = vertSectorCounts[u * 12 + s] * inv;
    }
  }
  function _refreshVertWeights() {
    let any = false;
    for (let u = 0; u < uniqueVertCount; u += 1) {
      if (!vertWeightsDirty[u]) continue;
      const c = vertIncidence[u] || 1;
      const inv = 1 / c;
      const o = u * 12;
      for (let s = 0; s < 12; s += 1) {
        vertSectorWeights[o + s] = vertSectorCounts[o + s] * inv;
      }
      vertWeightsDirty[u] = 0;
      any = true;
    }
    return any;
  }

  // Vertex 1-ring adjacency. Built once from faces: two vertices are
  // neighbours iff they share at least one face. Stored as a flat
  // CSR-style table (offsets[u]..offsets[u+1] indexes into the
  // neighbours array) so the Laplacian smoothing passes below can
  // iterate without indirection. Memory: roughly uniqueVertCount × 6
  // ints — under 6 MB at the current resolution.
  let vertNeighborOffsets;
  let vertNeighbors;
  {
    const tmpSets = new Array(uniqueVertCount);
    for (let u = 0; u < uniqueVertCount; u += 1) tmpSets[u] = new Set();
    for (let f = 0; f < faceCount; f += 1) {
      const a = vertIds[f * 3 + 0];
      const b = vertIds[f * 3 + 1];
      const c = vertIds[f * 3 + 2];
      tmpSets[a].add(b); tmpSets[a].add(c);
      tmpSets[b].add(a); tmpSets[b].add(c);
      tmpSets[c].add(a); tmpSets[c].add(b);
    }
    vertNeighborOffsets = new Int32Array(uniqueVertCount + 1);
    let total = 0;
    for (let u = 0; u < uniqueVertCount; u += 1) {
      vertNeighborOffsets[u] = total;
      total += tmpSets[u].size;
    }
    vertNeighborOffsets[uniqueVertCount] = total;
    vertNeighbors = new Int32Array(total);
    let idx = 0;
    for (let u = 0; u < uniqueVertCount; u += 1) {
      for (const n of tmpSets[u]) { vertNeighbors[idx] = n; idx += 1; }
      tmpSets[u] = null;   // release per-vertex set asap
    }
  }
  // Scratch buffer for in-place Laplacian smoothing. Allocated once
  // and reused across passes so the per-tick cost is zero-alloc.
  const _smoothScratch = new Float32Array(uniqueVertCount);

  // -------------------------------------------------------------
  // Live sector geometry: activity-weighted Voronoi + anchor drift.
  // -------------------------------------------------------------
  //
  // Each sector carries an externally-driven activity weight (scene.js
  // pushes EMA-smoothed real-welfare share). Two effects flow from it:
  //
  // 1. Weighted Voronoi reassignment of contested faces. Boundary
  //    faces (faces with at least one cross-sector neighbour) are
  //    re-evaluated each tick using a small per-tick budget. The
  //    distance metric is `(1 − dot(faceNormal, anchor)) − weight·k`,
  //    so a sector with a higher weight pulls contested faces toward
  //    its anchor — its region grows, neighbours shrink. The reassign-
  //    ment refreshes faceSector, the per-vertex sectorIdx attribute,
  //    the per-face sectorBoundary flags, and the vertSectorCounts.
  //
  // 2. Anchor drift. Each anchor eases per frame toward the centroid
  //    of its currently-assigned faces, so a sector that loses ground
  //    on one side re-centres in what remains. Continents jostle
  //    instead of just expanding/contracting around a fixed pole.
  //
  // Defaults preserve the prior behaviour: with all activity weights
  // equal, the weighted-Voronoi term cancels and no boundary face
  // migrates. setSectorActivityWeights({s → wₛ}) is the entry point.
  const sectorActivityWeightTarget = new Float32Array(sectorCount);
  const sectorActivityWeight       = new Float32Array(sectorCount);
  const SECTOR_WEIGHT_LERP = 0.04;
  // Strength of the weighted-Voronoi tiebreak. With weights in roughly
  // [−1, +1] (z-scores tanh'd before being pushed in), 0.06 lets a
  // dominant sector annex a band of faces roughly one anchor-radius
  // wide while a quiet sector keeps its core.
  const VORONOI_WEIGHT_SCALE = 0.06;
  // Per-tick budget for boundary reassignment. The Set has O(few-k)
  // members at typical sector counts; reassigning ~6 % per tick gives
  // a ~3 s settle time for a regime change. Bounded by both ratio and
  // an absolute floor/ceiling so a giant or tiny boundary still
  // produces motion.
  const VORONOI_REASSIGN_FRAC = 0.06;
  const VORONOI_REASSIGN_MIN = 32;
  const VORONOI_REASSIGN_MAX = 1024;
  // Anchor drift toward member centroid, normalised per tick.
  const ANCHOR_DRIFT_LERP = 0.012;

  // The boundary-face working set. Built initially from the static
  // partition; mutated by reassignment.
  const boundaryFaces = new Set();
  for (let f = 0; f < faceCount; f += 1) {
    const sf = faceSector[f];
    const n0 = faceAdjacency[f * 3 + 0];
    const n1 = faceAdjacency[f * 3 + 1];
    const n2 = faceAdjacency[f * 3 + 2];
    if ((n0 >= 0 && faceSector[n0] !== sf)
     || (n1 >= 0 && faceSector[n1] !== sf)
     || (n2 >= 0 && faceSector[n2] !== sf)) {
      boundaryFaces.add(f);
    }
  }
  // Cursor for round-robin reassignment so we don't always hit the
  // same prefix of the boundary set.
  let _boundaryCursor = 0;

  // Cached unit normals (face centroid / |centroid|) for the Voronoi
  // distance evaluation. Built once; doesn't change when faces
  // reassign (only the sector label moves, not the geometry).
  const faceUnit = new Float32Array(faceCount * 3);
  // Per-sector running sums of member faceUnits. Maintained
  // incrementally on reassignment so anchor drift can read the
  // current centroid in O(K) instead of O(F·K).
  const sectorCentroidSumX = new Float32Array(sectorCount);
  const sectorCentroidSumY = new Float32Array(sectorCount);
  const sectorCentroidSumZ = new Float32Array(sectorCount);
  const sectorFaceCount    = new Int32Array(sectorCount);
  for (let f = 0; f < faceCount; f += 1) {
    const cx = faceCentroids[f * 3 + 0];
    const cy = faceCentroids[f * 3 + 1];
    const cz = faceCentroids[f * 3 + 2];
    const cn = Math.sqrt(cx * cx + cy * cy + cz * cz) || 1;
    const ux = cx / cn, uy = cy / cn, uz = cz / cn;
    faceUnit[f * 3 + 0] = ux;
    faceUnit[f * 3 + 1] = uy;
    faceUnit[f * 3 + 2] = uz;
    const s = faceSector[f];
    sectorCentroidSumX[s] += ux;
    sectorCentroidSumY[s] += uy;
    sectorCentroidSumZ[s] += uz;
    sectorFaceCount[s]    += 1;
  }

  function setSectorActivityWeights(weights) {
    if (!weights || weights.length !== sectorCount) return;
    for (let s = 0; s < sectorCount; s += 1) {
      let v = Number(weights[s]);
      if (!Number.isFinite(v)) v = 0;
      // Clamp the target so a runaway signal can't drive the Voronoi
      // term past one anchor-radius — at |w·k| ~= 0.12 the term is
      // dominant; beyond that every contested face flips and the
      // surface starts thrashing.
      if (v > 1.5) v = 1.5;
      else if (v < -1.5) v = -1.5;
      sectorActivityWeightTarget[s] = v;
    }
  }

  // Reassign one face: returns true if its sector changed. Updates
  // faceSector, the per-vertex sectorIdx attribute, the per-face
  // sectorBoundary flags (on this face AND on its three neighbours,
  // whose flags depend on this face's sector), and the per-vertex
  // sector counts.
  function _reassignFace(f) {
    const ux = faceUnit[f * 3 + 0];
    const uy = faceUnit[f * 3 + 1];
    const uz = faceUnit[f * 3 + 2];
    let best = faceSector[f];
    let bestScore = -Infinity;
    for (let k = 0; k < sectorCount; k += 1) {
      const ax = sectorAnchors[k * 3 + 0];
      const ay = sectorAnchors[k * 3 + 1];
      const az = sectorAnchors[k * 3 + 2];
      // Score = dot − (1 − weight·k)·0 … written as
      // dot + weight·SCALE so higher is better. A high weight
      // amplifies the sector's pull; a low (negative) weight makes
      // its anchors register as further away.
      const score = (ux * ax + uy * ay + uz * az)
                  + sectorActivityWeight[k] * VORONOI_WEIGHT_SCALE;
      if (score > bestScore) { bestScore = score; best = k; }
    }
    const old = faceSector[f];
    if (best === old) return false;
    const u0 = vertIds[f * 3 + 0];
    const u1 = vertIds[f * 3 + 1];
    const u2 = vertIds[f * 3 + 2];
    faceSector[f] = best;
    // Incremental centroid-sum + count update so the per-tick anchor
    // drift stays O(K) instead of O(F·K).
    sectorCentroidSumX[old]  -= ux;
    sectorCentroidSumY[old]  -= uy;
    sectorCentroidSumZ[old]  -= uz;
    sectorFaceCount[old]     -= 1;
    sectorCentroidSumX[best] += ux;
    sectorCentroidSumY[best] += uy;
    sectorCentroidSumZ[best] += uz;
    sectorFaceCount[best]    += 1;
    vertSectorCounts[u0 * 12 + old]  -= 1;
    vertSectorCounts[u1 * 12 + old]  -= 1;
    vertSectorCounts[u2 * 12 + old]  -= 1;
    vertSectorCounts[u0 * 12 + best] += 1;
    vertSectorCounts[u1 * 12 + best] += 1;
    vertSectorCounts[u2 * 12 + best] += 1;
    vertWeightsDirty[u0] = 1;
    vertWeightsDirty[u1] = 1;
    vertWeightsDirty[u2] = 1;
    // Per-vertex sectorIdx attribute. The render path reads the
    // overlay-RGB array per-vertex; getting the index wrong tints the
    // vertex with the wrong sector's welfare colour even if the face
    // sector flag is right.
    const fb = f * 3;
    sectorArr[fb + 0] = best;
    sectorArr[fb + 1] = best;
    sectorArr[fb + 2] = best;
    sectorIdxAttr.needsUpdate = true;
    // Refresh the sectorBoundary attribute for this face AND its
    // three neighbours (their boundary flags reference this face's
    // sector). The flag on neighbour n is set per-edge against the
    // edge that n shares with f.
    _refreshSectorBoundaryFor(f);
    const n0 = faceAdjacency[f * 3 + 0];
    const n1 = faceAdjacency[f * 3 + 1];
    const n2 = faceAdjacency[f * 3 + 2];
    if (n0 >= 0) _refreshSectorBoundaryFor(n0);
    if (n1 >= 0) _refreshSectorBoundaryFor(n1);
    if (n2 >= 0) _refreshSectorBoundaryFor(n2);
    sectorBoundaryAttr.needsUpdate = true;
    // Boundary-set membership for f and its 3 neighbours may have
    // flipped — recompute.
    _refreshBoundarySetFor(f);
    if (n0 >= 0) _refreshBoundarySetFor(n0);
    if (n1 >= 0) _refreshBoundarySetFor(n1);
    if (n2 >= 0) _refreshBoundarySetFor(n2);
    return true;
  }

  function _refreshSectorBoundaryFor(f) {
    const sf = faceSector[f];
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

  function _refreshBoundarySetFor(f) {
    const sf = faceSector[f];
    const n0 = faceAdjacency[f * 3 + 0];
    const n1 = faceAdjacency[f * 3 + 1];
    const n2 = faceAdjacency[f * 3 + 2];
    const isBoundary =
         (n0 >= 0 && faceSector[n0] !== sf)
      || (n1 >= 0 && faceSector[n1] !== sf)
      || (n2 >= 0 && faceSector[n2] !== sf);
    if (isBoundary) boundaryFaces.add(f);
    else boundaryFaces.delete(f);
  }

  function _stepVoronoiReassignment() {
    // Ease activity weights toward target.
    for (let s = 0; s < sectorCount; s += 1) {
      const t = sectorActivityWeightTarget[s];
      const c = sectorActivityWeight[s];
      if (c !== t) sectorActivityWeight[s] = c + (t - c) * SECTOR_WEIGHT_LERP;
    }
    if (boundaryFaces.size === 0) return;
    // Anchor drift. Read each sector's running centroid sum (kept
    // current by _reassignFace) → normalised mean direction → ease
    // the anchor toward it. O(K), not O(F).
    for (let k = 0; k < sectorCount; k += 1) {
      const cnt = sectorFaceCount[k];
      if (cnt === 0) continue;
      const inv = 1 / cnt;
      let mx = sectorCentroidSumX[k] * inv;
      let my = sectorCentroidSumY[k] * inv;
      let mz = sectorCentroidSumZ[k] * inv;
      const mn = Math.sqrt(mx * mx + my * my + mz * mz) || 1;
      mx /= mn; my /= mn; mz /= mn;
      const ax = sectorAnchors[k * 3 + 0];
      const ay = sectorAnchors[k * 3 + 1];
      const az = sectorAnchors[k * 3 + 2];
      let nx = ax + (mx - ax) * ANCHOR_DRIFT_LERP;
      let ny = ay + (my - ay) * ANCHOR_DRIFT_LERP;
      let nz = az + (mz - az) * ANCHOR_DRIFT_LERP;
      const nn = Math.sqrt(nx * nx + ny * ny + nz * nz) || 1;
      sectorAnchors[k * 3 + 0] = nx / nn;
      sectorAnchors[k * 3 + 1] = ny / nn;
      sectorAnchors[k * 3 + 2] = nz / nn;
    }
    // Round-robin a slice of the boundary set. Iterating a Set in
    // insertion order is fine; we cap the slice size + bail when
    // we've walked the whole set in one pass.
    let budget = Math.floor(boundaryFaces.size * VORONOI_REASSIGN_FRAC);
    if (budget < VORONOI_REASSIGN_MIN) budget = VORONOI_REASSIGN_MIN;
    if (budget > VORONOI_REASSIGN_MAX) budget = VORONOI_REASSIGN_MAX;
    if (budget > boundaryFaces.size) budget = boundaryFaces.size;
    const snapshot = Array.from(boundaryFaces);
    const total = snapshot.length;
    let i = _boundaryCursor % total;
    for (let n = 0; n < budget; n += 1) {
      _reassignFace(snapshot[i]);
      i = (i + 1) % total;
    }
    _boundaryCursor = i;
  }

  // -------------------------------------------------------------
  // Cross-sector trade rifts: pre-compute the per-pair boundary face
  // list once. Each entry maps an ordered key i·sectorCount + j
  // (with i<j) → an array of face indices that touch sectors i and j.
  // The rift driver picks faces at random from the hot pair's list
  // each tick and dumps an altitude bump on them via the existing
  // bumpAltitude pipeline, so rifts inherit decay + concentration
  // and don't need their own state machine.
  // -------------------------------------------------------------
  const pairBoundaryFaces = new Map();   // key → number[]
  function _pairKey(i, j) {
    return i < j ? i * sectorCount + j : j * sectorCount + i;
  }
  for (let f = 0; f < faceCount; f += 1) {
    const sf = faceSector[f];
    for (let e = 0; e < 3; e += 1) {
      const nb = faceAdjacency[f * 3 + e];
      if (nb < 0) continue;
      const sn = faceSector[nb];
      if (sn === sf) continue;
      const k = _pairKey(sf, sn);
      let arr = pairBoundaryFaces.get(k);
      if (!arr) { arr = []; pairBoundaryFaces.set(k, arr); }
      arr.push(f);
    }
  }
  // Per-pair flow EMA (sectorCount × sectorCount, symmetric). The
  // index used is i·sectorCount + j with i<j; setSectorPairFlows()
  // accepts a 144-element flat array (or any subset) where each cell
  // is normalised flow magnitude in roughly [0, 1].
  const sectorPairFlow = new Float32Array(sectorCount * sectorCount);
  // Per-pair rift sign — +1 ridge, −1 trench. Picked once per pair at
  // first activation from the parity of the pair key, so the same pair
  // always rifts the same direction across a session.
  const sectorPairSign = new Int8Array(sectorCount * sectorCount);
  // Maximum bump magnitude carved into a rift face per tick at flow=1.
  // Slightly bigger than the per-event amplified cap so a saturated
  // rift can outpace per-trade noise.
  const RIFT_BUMP_MAX = 0.09;
  // Faces touched per pair per tick at flow=1. We don't write every
  // boundary face every tick — that would consume the bump budget —
  // just a slice so the ridge/trench grows over a couple of seconds.
  const RIFT_FACES_PER_PAIR_AT_MAX = 16;

  function setSectorPairFlows(flat) {
    if (!flat || flat.length !== sectorCount * sectorCount) return;
    for (let i = 0; i < sectorCount; i += 1) {
      for (let j = i + 1; j < sectorCount; j += 1) {
        let v = Number(flat[i * sectorCount + j]);
        if (!Number.isFinite(v) || v < 0) v = 0;
        if (v > 1) v = 1;
        sectorPairFlow[i * sectorCount + j] = v;
      }
    }
  }

  function _stepRifts() {
    for (const [key, faces] of pairBoundaryFaces) {
      const flow = sectorPairFlow[key];
      if (flow <= 0.05) continue;
      // Lock sign on first activation.
      if (sectorPairSign[key] === 0) {
        sectorPairSign[key] = (key & 1) ? -1 : 1;
      }
      const sign = sectorPairSign[key];
      const mag  = flow * RIFT_BUMP_MAX * sign;
      const k    = Math.max(
        2,
        Math.floor(flow * RIFT_FACES_PER_PAIR_AT_MAX),
      );
      const n = faces.length;
      if (n === 0) continue;
      // Sample k random faces. Cheap; we don't need draw-without-
      // replacement at this k. Force-flat so the rift can seed on
      // initially flat terrain — without the bypass, 95 % of the
      // first batch of bumps would fizzle.
      for (let t = 0; t < k; t += 1) {
        const f = faces[Math.floor(Math.random() * n)];
        bumpAltitude(f, mag, { forceFlat: true });
      }
    }
  }

  // -------------------------------------------------------------
  // Basin reversal: when a sector is severely suppressed (its activity
  // weight is far below the maximum), its faces are allowed to dip
  // below the standard altitudeMaxNeg floor. The per-vertex effective
  // floor is a blend over vertSectorWeights of each sector's basin
  // depth, recomputed when activity weights or sector membership
  // change.
  // -------------------------------------------------------------
  const sectorBasinFloor = new Float32Array(sectorCount);
  const vertBasinFloor   = new Float32Array(uniqueVertCount);
  // Maximum allowed extra basin depth on top of altitudeMaxNeg.
  const BASIN_EXTRA_MAX = 0.20;
  let basinDirty = true;

  // -------------------------------------------------------------
  // Topologically-instrumented sector border. Every vertex that
  // sits on a sector-boundary face gets a small negative altitude
  // offset (a "river"), so the border itself reads as a continuous
  // valley between continents instead of as an abrupt step where
  // adjacent continent altitudes happen to differ.
  //
  // Depth is modulated per-vertex by the activity-weight
  // differential of the sectors that vertex touches. A vertex
  // sitting between two evenly-activity-matched sectors gets a
  // shallow channel; a vertex on the front line between a
  // dominant sector and a suppressed one gets a deep gorge. The
  // border thereby *measures* the pressure across it: where
  // sectors are fighting, the river runs deep.
  //
  // Recomputed on the Voronoi step (10 Hz) since both inputs —
  // which faces are on a boundary, and what the activity-weight
  // differentials are — only change on that cadence.
  // -------------------------------------------------------------
  const vertBoundaryTrench = new Float32Array(uniqueVertCount);
  // Trench depth is currently zero — the carved-river border
  // treatment read as too literal a feature on the substrate. The
  // smoothing of vertSectorBase already kills the geometric-cliff
  // problem; the borders are now implied by the continent slope
  // rather than carved as physical channels. Channel is kept wired
  // so a future treatment (subtle hover-only or activity-gated)
  // can re-enable it by raising these constants.
  const BORDER_TRENCH_BASE = 0.0;
  const BORDER_TRENCH_GAP_SCALE = 0.0;

  function _refreshBoundaryTrench() {
    vertBoundaryTrench.fill(0);
    // For each boundary face, compute the activity-weight gap
    // across each cross-sector edge. Apply max-of-incident-gap to
    // each of the face's three vertices. Using max (not sum) so a
    // vertex shared by multiple boundary faces with different gaps
    // takes its hottest edge.
    for (const f of boundaryFaces) {
      const sf = faceSector[f];
      const wf = sectorActivityWeight[sf];
      const n0 = faceAdjacency[f * 3 + 0];
      const n1 = faceAdjacency[f * 3 + 1];
      const n2 = faceAdjacency[f * 3 + 2];
      let maxGap = 0;
      if (n0 >= 0) {
        const sn = faceSector[n0];
        if (sn !== sf) {
          const g = Math.abs(wf - sectorActivityWeight[sn]);
          if (g > maxGap) maxGap = g;
        }
      }
      if (n1 >= 0) {
        const sn = faceSector[n1];
        if (sn !== sf) {
          const g = Math.abs(wf - sectorActivityWeight[sn]);
          if (g > maxGap) maxGap = g;
        }
      }
      if (n2 >= 0) {
        const sn = faceSector[n2];
        if (sn !== sf) {
          const g = Math.abs(wf - sectorActivityWeight[sn]);
          if (g > maxGap) maxGap = g;
        }
      }
      const depth = -(BORDER_TRENCH_BASE + BORDER_TRENCH_GAP_SCALE * maxGap);
      const u0 = vertIds[f * 3 + 0];
      const u1 = vertIds[f * 3 + 1];
      const u2 = vertIds[f * 3 + 2];
      if (depth < vertBoundaryTrench[u0]) vertBoundaryTrench[u0] = depth;
      if (depth < vertBoundaryTrench[u1]) vertBoundaryTrench[u1] = depth;
      if (depth < vertBoundaryTrench[u2]) vertBoundaryTrench[u2] = depth;
    }
    // Diffuse the trench by one Laplacian pass so the channel
    // tapers smoothly into the surrounding terrain instead of
    // having its own micro-cliff at the trench shoulder.
    for (let u = 0; u < uniqueVertCount; u += 1) {
      const start = vertNeighborOffsets[u];
      const end   = vertNeighborOffsets[u + 1];
      let sum = 0;
      for (let i = start; i < end; i += 1) sum += vertBoundaryTrench[vertNeighbors[i]];
      const cnt = end - start;
      const avg = cnt > 0 ? sum / cnt : vertBoundaryTrench[u];
      _smoothScratch[u] = vertBoundaryTrench[u] * 0.5 + avg * 0.5;
    }
    vertBoundaryTrench.set(_smoothScratch);
  }

  function _recomputeBasinFloors() {
    let maxW = -Infinity;
    for (let s = 0; s < sectorCount; s += 1) {
      if (sectorActivityWeight[s] > maxW) maxW = sectorActivityWeight[s];
    }
    // Only reverse basins once *some* sector is meaningfully ahead.
    // At maxW < 0.4 the regime hasn't concentrated enough to warrant
    // pulling other sectors below zero.
    const concentration = Math.max(0, (maxW - 0.4) / 0.8);
    const cclamp = Math.min(1, concentration);
    for (let s = 0; s < sectorCount; s += 1) {
      const lag = maxW - sectorActivityWeight[s];
      const lagN = Math.max(0, Math.min(1, lag / 1.5));
      sectorBasinFloor[s] = -altitudeMaxNeg - BASIN_EXTRA_MAX * lagN * cclamp;
    }
    for (let u = 0; u < uniqueVertCount; u += 1) {
      const o = u * 12;
      let floor = 0;
      for (let s = 0; s < sectorCount; s += 1) {
        floor += vertSectorWeights[o + s] * sectorBasinFloor[s];
      }
      vertBasinFloor[u] = floor;
    }
  }
  _recomputeBasinFloors();

  // Sustained per-sector altitude offsets — the "continents" layer.
  // The bump-driven `vertAltitudes` decays back to zero on a fast clock
  // (~38 s half-life); this layer holds its value so regime-level
  // signals like real_welfare_per_sector_step can paint long-lived
  // topography. Target is set externally; current eases toward target
  // each tick to avoid pop-on-update.
  const sectorBaseTarget  = new Float32Array(12);
  const sectorBaseCurrent = new Float32Array(12);
  const vertSectorBase    = new Float32Array(uniqueVertCount);
  // Hard cap on each per-sector offset. ±0.18 lets a sector rise or
  // sink visibly without monopolising the altitude budget — the
  // per-event bump cap is 0.012, so 0.18 reads as ~15 trade events of
  // sustained baseline elevation.
  const SECTOR_BASE_CAP = 0.18;
  // Ease toward target at 4 %/frame — at 60 fps a step of 0.10 settles
  // in ~0.5 s. Slow enough to feel like landmass shifting; fast enough
  // that a new preset's continent map shows up well within the
  // ~5 s tween of the lever transition.
  const SECTOR_BASE_LERP = 0.04;
  let sectorBaseDirty = true;

  function setSectorAltitudeTargets(deltas) {
    if (!deltas || deltas.length !== 12) return;
    for (let s = 0; s < 12; s += 1) {
      let v = Number(deltas[s]);
      if (!Number.isFinite(v)) v = 0;
      if (v >  SECTOR_BASE_CAP) v =  SECTOR_BASE_CAP;
      else if (v < -SECTOR_BASE_CAP) v = -SECTOR_BASE_CAP;
      sectorBaseTarget[s] = v;
    }
    sectorBaseDirty = true;
  }

  // Number of Laplacian passes applied to vertSectorBase after the
  // raw per-vertex weighted sum is computed. With 0 passes, sector
  // boundaries appear as one-face-wide cliffs (sectorBaseCurrent[A]
  // − sectorBaseCurrent[B] in a single edge); 2 passes at λ=0.5
  // diffuses the step over ~6–10 face-widths so the continent
  // transitions read as slopes rather than geometric edges. Cost is
  // ~O(2 · uniqueVertCount · meanDegree) ≈ 3 M ops at 10 Hz — well
  // under the per-frame budget.
  const SECTOR_BASE_SMOOTH_PASSES = 2;
  const SECTOR_BASE_SMOOTH_LAMBDA = 0.5;

  function _recomputeVertSectorBase() {
    for (let u = 0; u < uniqueVertCount; u += 1) {
      const o = u * 12;
      let sum = 0;
      for (let s = 0; s < 12; s += 1) {
        sum += vertSectorWeights[o + s] * sectorBaseCurrent[s];
      }
      vertSectorBase[u] = sum;
    }
    // Laplacian smoothing in place. Each pass replaces v[u] with
    // (1 − λ)·v[u] + λ·mean(neighbours(u)). At λ=0.5 the spread
    // doubles per pass, so 2 passes ~ 4 face-widths of diffusion;
    // combined with the natural mesh density that turns a
    // cliff-edge transition into a smooth slope.
    for (let p = 0; p < SECTOR_BASE_SMOOTH_PASSES; p += 1) {
      for (let u = 0; u < uniqueVertCount; u += 1) {
        const start = vertNeighborOffsets[u];
        const end   = vertNeighborOffsets[u + 1];
        let sum = 0;
        for (let i = start; i < end; i += 1) sum += vertSectorBase[vertNeighbors[i]];
        const cnt = end - start;
        const avg = cnt > 0 ? sum / cnt : vertSectorBase[u];
        _smoothScratch[u] = vertSectorBase[u] * (1 - SECTOR_BASE_SMOOTH_LAMBDA)
                          + avg * SECTOR_BASE_SMOOTH_LAMBDA;
      }
      vertSectorBase.set(_smoothScratch);
    }
  }

  // Per-sector welfare accumulator. EMA: bumpAltitude(faceIdx, m)
  // deposits m into sectorTotals[faceSector[faceIdx]]; tick() decays
  // the totals at SECTOR_DECAY each frame (~3 s half-life). Pure
  // continuous evolution — no ring buffer cycle to produce a visible
  // pulse at the cycle frequency.
  const sectorTotals = new Float32Array(12);
  // Palette: cream for welfare-positive, faint copper for negative.
  // Subdued so the substrate's existing sector-hover blue still
  // wins the visual fight when the user hovers a region.
  // Positive-welfare tint matched to the neutral substrate baseColor
  // so the overlay no longer bleaches the dominant sector. A faintly
  // cooler-than-base gray keeps a hint of "this sector is doing well"
  // without flipping the continent to white. Negative tint stays as
  // faint copper since the warm-vs-cool axis is what differentiates.
  const TINT_POSITIVE = new THREE.Vector3(0.80, 0.81, 0.83);  // cool neutral
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
  function setPinchAxis(x, y, z) {
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) return;
    const n = Math.sqrt(x * x + y * y + z * z);
    if (n < 1e-6) return;
    material.uniforms.uPinchAxis.value.set(x / n, y / n, z / n);
  }
  function setPinchStrength(s) {
    if (!Number.isFinite(s)) return;
    if (s >  0.18) s =  0.18;
    else if (s < -0.18) s = -0.18;
    material.uniforms.uPinchStrength.value = s;
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
  function bumpAltitude(faceIdx, magnitude, opts) {
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
    //
    // The rift driver bypasses the filter via {forceFlat:true}: rifts
    // are deliberately seeded on flat boundary territory and need
    // every bump to land so the ridge/trench can take shape.
    const FLAT_THRESHOLD = 0.012;
    const FLAT_SURVIVAL = 0.05;
    const force = opts && opts.forceFlat === true;
    if (!force && Math.abs(baseAlt) < FLAT_THRESHOLD && Math.random() > FLAT_SURVIVAL) {
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

  // How often to step the live-geometry layer (Voronoi reassignment,
  // anchor drift, rifts). Stepping every frame would burn budget on
  // a layer that only needs to evolve on a multi-second timescale —
  // every 6 frames ≈ 10 Hz, matching the engine tick rate without
  // overshooting it.
  const GEOMETRY_STEP_INTERVAL = 6;

  function tick() {
    frameCounter += 1;

    // Live sector-geometry layer: weighted-Voronoi face reassignment,
    // anchor drift, cross-sector rift bumps. Every 6th frame so the
    // anchor drift sums to roughly the intended ~0.7 %/sec rate and
    // the per-pair rift budget doesn't saturate the bump pipeline.
    if (frameCounter % GEOMETRY_STEP_INTERVAL === 0) {
      _stepVoronoiReassignment();
      _stepRifts();
      if (_refreshVertWeights()) {
        // Per-vertex sector weights changed — the continent altitude
        // blend depends on them, so trigger a rebuild.
        sectorBaseDirty = true;
      }
      // Activity weights ease toward target every geometry step, so
      // basin floors always need a refresh on this cadence.
      basinDirty = true;
      // Both boundary membership and the activity-weight gaps that
      // drive trench depth change at the geometry-step rate.
      _refreshBoundaryTrench();
    }

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
      else if (a < vertBasinFloor[u]) a = vertBasinFloor[u];
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
    // Ease the per-sector base layer toward target. The bump-driven
    // vertAltitudes above decays on a ~38 s clock; this layer carries
    // sustained signals (per-sector real welfare) and only moves when
    // the target changes. When stable, this is a no-op after settling.
    let sectorMoved = false;
    for (let s = 0; s < 12; s += 1) {
      const tgt = sectorBaseTarget[s];
      const cur = sectorBaseCurrent[s];
      if (cur === tgt) continue;
      const next = cur + (tgt - cur) * SECTOR_BASE_LERP;
      if (Math.abs(next - tgt) < 1e-5) sectorBaseCurrent[s] = tgt;
      else sectorBaseCurrent[s] = next;
      sectorMoved = true;
    }
    if (sectorMoved || sectorBaseDirty) {
      _recomputeVertSectorBase();
      sectorBaseDirty = false;
    }
    if (basinDirty) {
      _recomputeBasinFloors();
      basinDirty = false;
    }
    // Compute the combined per-unique-vertex display altitude ONCE,
    // then replicate to the GPU attribute (per non-indexed vertex)
    // and to the per-face average. The display altitude is the sum
    // of (a) the bump-driven dynamic layer, (b) the sustained
    // per-sector continent layer, and (c) the border-trench channel,
    // clamped by a per-vertex floor that opens up extra depth for
    // sectors suppressed under a dominant regime (basin reversal).
    // External consumers (agents.js, firms.js, cluster_overlay.js)
    // read vertDisplayAlt to lift their geometry — without it they
    // would sit on the un-swollen base sphere and get buried inside
    // the dominant continent.
    for (let u = 0; u < uniqueVertCount; u += 1) {
      let a = vertAltitudes[u] + vertSectorBase[u] + vertBoundaryTrench[u];
      if (a > altitudeMaxPos) a = altitudeMaxPos;
      else if (a < vertBasinFloor[u]) a = vertBasinFloor[u];
      vertDisplayAlt[u] = a;
    }
    for (let v = 0; v < vertexCount; v += 1) {
      altitudeArr[v] = vertDisplayAlt[vertIds[v]];
    }
    for (let f = 0; f < faceCount; f += 1) {
      const b = f * 3;
      faceAltitudes[f] = (
        vertDisplayAlt[vertIds[b + 0]] +
        vertDisplayAlt[vertIds[b + 1]] +
        vertDisplayAlt[vertIds[b + 2]]
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
    // Sustained per-sector continent layer: drop targets + current
    // so a Restart erases the prior regime's topography.
    sectorBaseTarget.fill(0);
    sectorBaseCurrent.fill(0);
    vertSectorBase.fill(0);
    sectorBaseDirty = true;
    // Restore the canonical Fibonacci anchors + face partition,
    // zero the activity weights, drop the per-pair flow EMA, and
    // rebuild the per-vertex sector counts from the frozen partition
    // so weighted Voronoi / basin floors start clean.
    sectorAnchors.set(sectorAnchorsInitial);
    faceSector.set(faceSectorInitial);
    sectorActivityWeight.fill(0);
    sectorActivityWeightTarget.fill(0);
    sectorPairFlow.fill(0);
    sectorPairSign.fill(0);
    vertSectorCounts.fill(0);
    sectorCentroidSumX.fill(0);
    sectorCentroidSumY.fill(0);
    sectorCentroidSumZ.fill(0);
    sectorFaceCount.fill(0);
    for (let f = 0; f < faceCount; f += 1) {
      const s = faceSector[f];
      vertSectorCounts[vertIds[f * 3 + 0] * 12 + s] += 1;
      vertSectorCounts[vertIds[f * 3 + 1] * 12 + s] += 1;
      vertSectorCounts[vertIds[f * 3 + 2] * 12 + s] += 1;
      sectorCentroidSumX[s] += faceUnit[f * 3 + 0];
      sectorCentroidSumY[s] += faceUnit[f * 3 + 1];
      sectorCentroidSumZ[s] += faceUnit[f * 3 + 2];
      sectorFaceCount[s]    += 1;
    }
    vertWeightsDirty.fill(1);
    _refreshVertWeights();
    // Rebuild per-vertex sectorIdx + per-face sectorBoundary attrs
    // and the boundaryFaces set from the canonical partition.
    boundaryFaces.clear();
    for (let f = 0; f < faceCount; f += 1) {
      const sf = faceSector[f];
      sectorArr[f * 3 + 0] = sf;
      sectorArr[f * 3 + 1] = sf;
      sectorArr[f * 3 + 2] = sf;
      _refreshSectorBoundaryFor(f);
      _refreshBoundarySetFor(f);
    }
    sectorIdxAttr.needsUpdate = true;
    sectorBoundaryAttr.needsUpdate = true;
    _recomputeBasinFloors();
    vertBoundaryTrench.fill(0);
    // Reset pinch.
    material.uniforms.uPinchStrength.value = 0.0;
  }

  function dispose() {
    scene.remove(mesh);
    geometry.dispose();
    material.dispose();
  }

  function diagnostics() {
    // Surface a face-count histogram over sectors so the Voronoi
    // reassignment can be inspected from the console — at startup
    // every sector holds ~faceCount/12 = 66 k faces; a dominant
    // sector should visibly grow this past 80 k while a suppressed
    // one shrinks below 50 k.
    const faceCountBySector = new Int32Array(sectorCount);
    for (let f = 0; f < faceCount; f += 1) faceCountBySector[faceSector[f]] += 1;
    // Active rift count = pairs with flow above the rift threshold.
    let activeRifts = 0;
    for (let i = 0; i < sectorCount; i += 1) {
      for (let j = i + 1; j < sectorCount; j += 1) {
        if (sectorPairFlow[i * sectorCount + j] > 0.05) activeRifts += 1;
      }
    }
    return {
      faceCount,
      frame: frameCounter,
      sectorTotals: Array.from(sectorTotals),
      sectorOverlayAlpha: Array.from(sectorOverlayAlphaArr),
      sectorBaseTarget: Array.from(sectorBaseTarget),
      sectorBaseCurrent: Array.from(sectorBaseCurrent),
      altitudeScale: material.uniforms.uAltitudeScale.value,
      perEventBumpCap: PER_EVENT_BUMP_CAP_AMPLIFIED,
      sectorActivityWeight: Array.from(sectorActivityWeight),
      sectorBasinFloor: Array.from(sectorBasinFloor),
      faceCountBySector: Array.from(faceCountBySector),
      boundaryFaceCount: boundaryFaces.size,
      activeRifts,
      pinchStrength: material.uniforms.uPinchStrength.value,
      // Border-trench statistics: max depth + mean over boundary
      // vertices. At rest with all weights equal the depth is just
      // BORDER_TRENCH_BASE; under a high-pressure regime the max
      // depth climbs as the gap term kicks in.
      trenchStats: (() => {
        let mx = 0, sum = 0, n = 0;
        for (let u = 0; u < uniqueVertCount; u += 1) {
          const v = vertBoundaryTrench[u];
          if (v < 0) {
            if (v < mx) mx = v;
            sum += v; n += 1;
          }
        }
        return {
          deepest: +mx.toFixed(4),
          mean: n > 0 ? +(sum / n).toFixed(4) : 0,
          boundaryVerts: n,
        };
      })(),
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
    // vertAltitudes is the BUMP-DRIVEN dynamic layer alone (decays
    // toward zero). External consumers that need to sit ON TOP of
    // the substrate's actual displaced surface must read vertDisplayAlt
    // instead, which is the bump + continent + trench sum clamped by
    // basin floor — i.e. the same value the substrate shader receives.
    // Reading vertAltitudes alone buries the geometry inside a swollen
    // continent.
    vertAltitudes,
    vertDisplayAlt,
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
    setSectorAltitudeTargets,
    // Live-geometry layer driven from scene.js. Activity weights
    // reshape sector regions (weighted Voronoi + anchor drift) and
    // open up extra basin depth for suppressed sectors. Pair flows
    // carve ridges/trenches along cross-sector boundaries. Pinch
    // displaces the whole sphere along an axis (driven from Gini).
    setSectorActivityWeights,
    setSectorPairFlows,
    setPinchAxis,
    setPinchStrength,
  };
}
