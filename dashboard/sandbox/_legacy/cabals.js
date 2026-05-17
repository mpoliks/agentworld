// Cabals (Pass 6) — emergent group structures detected from bonds.
//
// A cabal is a connected component in the bond graph above a strength
// threshold. We rebuild the component map each snapshot via union-find
// over the live bonds (cheap: O(E α(N))), then visualise every cabal
// of size ≥ 3 by drawing the chord graph between all its members.
//
// Cabals get a stable id by carrying the maximum bond strength of
// their representative forward; the chord-line color hashes that id
// so two cabals on the same arc of the sphere can be told apart.

import * as THREE from 'three';

const MIN_BOND_STRENGTH = 0.30;   // bond strength to count toward cabal
const MIN_CABAL_SIZE = 3;
const MAX_CHORD_LINES = 16384;
const MAX_HALO_POINTS = 8192;
const HALO_SIZE = 48.0;           // halo pixel size — small enough to keep
                                  // cabals compact, large enough to ring
                                  // the cabal cell clearly
const NORMAL_COLOR = [1.0, 0.74, 0.36];   // amber by default

// Chord shader. aT in {0, 1} marks which end of the segment the
// vertex sits on; aPhase is a per-line phase offset. The fragment
// shader runs a sinusoidal pulse along the segment so the X-shapes
// have visible "data flow" rather than reading as inert line graphs.
const VERTEX_SHADER = /* glsl */ `
  attribute vec3 aColor;
  attribute float aGlow;
  attribute float aT;
  attribute float aPhase;

  varying vec3 vColor;
  varying float vGlow;
  varying float vT;
  varying float vPhase;

  void main() {
    vColor = aColor;
    vGlow = aGlow;
    vT = aT;
    vPhase = aPhase;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const FRAGMENT_SHADER = /* glsl */ `
  precision highp float;

  uniform float uTime;

  varying vec3 vColor;
  varying float vGlow;
  varying float vT;
  varying float vPhase;

  void main() {
    // Travelling pulse along the segment. vT runs 0 → 1 between the
    // segment's two endpoints; uTime ticks; vPhase is a per-line
    // randomization. The sinusoid is offset by vT so the bright
    // spot slides along the line rather than blinking uniformly.
    float wave = sin(uTime * 1.8 + vPhase * 6.28318 + vT * 6.28318 * 1.4);
    float pulse = 0.45 + 0.55 * (0.5 + 0.5 * wave);

    float alpha = clamp(vGlow * pulse, 0.0, 1.0);
    if (alpha <= 0.0) discard;
    gl_FragColor = vec4(vColor * alpha, alpha);
  }
`;

// Stable hash-to-color: small palette of bright cabal tints so the
// eye picks out distinct clusters at a glance. Themes can override
// via opts.palette.
const DEFAULT_CABAL_COLORS = [
  [1.00, 0.74, 0.36],
  [0.42, 0.83, 0.99],
  [0.99, 0.50, 0.78],
  [0.69, 0.99, 0.62],
  [0.97, 0.97, 0.40],
  [0.65, 0.55, 1.00],
  [1.00, 0.55, 0.40],
  [0.40, 1.00, 0.85],
];

export function createCabals(scene, opts) {
  if (!opts || !opts.agents) throw new Error('createCabals requires opts.agents');
  if (!opts.bonds) throw new Error('createCabals requires opts.bonds');
  const { agents, bonds } = opts;
  const minBondStrength = opts.minBondStrength ?? MIN_BOND_STRENGTH;
  const minCabalSize = opts.minCabalSize ?? MIN_CABAL_SIZE;
  const cabalColors =
    Array.isArray(opts.palette) && opts.palette.length > 0
      ? opts.palette
      : DEFAULT_CABAL_COLORS;
  const colorForCabal = (rootSlot) => cabalColors[rootSlot % cabalColors.length];

  const positions = agents.positions;
  const maxAgents = positions.length / 3;

  // Union-find arrays. Sized for maxAgents so reuse is cheap.
  const parent = new Int32Array(maxAgents);
  const rank = new Uint8Array(maxAgents);

  function ufReset() {
    for (let i = 0; i < maxAgents; i += 1) {
      parent[i] = i;
      rank[i] = 0;
    }
  }

  function ufFind(x) {
    let root = x;
    while (parent[root] !== root) root = parent[root];
    // Path compression.
    let cur = x;
    while (parent[cur] !== root) {
      const next = parent[cur];
      parent[cur] = root;
      cur = next;
    }
    return root;
  }

  function ufUnion(a, b) {
    const ra = ufFind(a);
    const rb = ufFind(b);
    if (ra === rb) return;
    if (rank[ra] < rank[rb]) parent[ra] = rb;
    else if (rank[ra] > rank[rb]) parent[rb] = ra;
    else { parent[rb] = ra; rank[ra] += 1; }
  }

  // Chord-graph render buffers. Two vertices per chord line.
  const linePositions = new Float32Array(MAX_CHORD_LINES * 2 * 3);
  const lineColors = new Float32Array(MAX_CHORD_LINES * 2 * 3);
  const lineGlows = new Float32Array(MAX_CHORD_LINES * 2);
  // aT: 0 for the first vertex of the segment, 1 for the second.
  // Used by the fragment shader to interpolate the pulse position
  // along the segment.
  const lineTs = new Float32Array(MAX_CHORD_LINES * 2);
  for (let i = 0; i < MAX_CHORD_LINES; i += 1) {
    lineTs[i * 2 + 0] = 0.0;
    lineTs[i * 2 + 1] = 1.0;
  }
  // Per-line phase offset, replicated to both vertices. Stable for
  // the lifetime of the geometry so individual chords pulse out of
  // sync — gives the cabal lattice complex visual rhythm.
  const linePhases = new Float32Array(MAX_CHORD_LINES * 2);
  for (let i = 0; i < MAX_CHORD_LINES; i += 1) {
    const ph = Math.random();
    linePhases[i * 2 + 0] = ph;
    linePhases[i * 2 + 1] = ph;
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(linePositions, 3));
  geometry.setAttribute('aColor', new THREE.BufferAttribute(lineColors, 3));
  geometry.setAttribute('aGlow', new THREE.BufferAttribute(lineGlows, 1));
  geometry.setAttribute('aT', new THREE.BufferAttribute(lineTs, 1));
  geometry.setAttribute('aPhase', new THREE.BufferAttribute(linePhases, 1));
  geometry.setDrawRange(0, 0);

  const material = new THREE.ShaderMaterial({
    vertexShader: VERTEX_SHADER,
    fragmentShader: FRAGMENT_SHADER,
    uniforms: {
      uTime: { value: 0 },
    },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });

  const lineSegments = new THREE.LineSegments(geometry, material);
  lineSegments.frustumCulled = false;
  scene.add(lineSegments);

  // Per-cabal-member halo layer. Each cabal member gets a large soft
  // disc behind it so cabal membership reads at a glance even when
  // chord lines tangle. Rendered as additive points so they pile up
  // into a glow at dense cabal centroids.
  const haloPositions = new Float32Array(MAX_HALO_POINTS * 3);
  const haloColors = new Float32Array(MAX_HALO_POINTS * 3);

  const haloGeometry = new THREE.BufferGeometry();
  haloGeometry.setAttribute('position', new THREE.BufferAttribute(haloPositions, 3));
  haloGeometry.setAttribute('aColor', new THREE.BufferAttribute(haloColors, 3));
  haloGeometry.setDrawRange(0, 0);

  const haloMaterial = new THREE.ShaderMaterial({
    vertexShader: /* glsl */ `
      attribute vec3 aColor;
      uniform float uPixelRatio;
      uniform float uSize;
      varying vec3 vColor;
      void main() {
        vColor = aColor;
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        gl_PointSize = uSize * uPixelRatio * (300.0 / -mv.z);
        gl_Position = projectionMatrix * mv;
      }
    `,
    fragmentShader: /* glsl */ `
      precision highp float;
      varying vec3 vColor;
      void main() {
        vec2 uv = gl_PointCoord - 0.5;
        float d = length(uv);
        if (d > 0.5) discard;
        // Soft annulus around the cell: peaks at d=0.32, fading both
        // toward the cell (d→0.18) and outward (d→0.50). Bright
        // enough to read clearly against the cell beneath it; thick
        // enough that the eye reads it as "this cell belongs to a
        // colored group" rather than "this cell is yellow."
        float ring = exp(-pow((d - 0.32) / 0.14, 2.0));
        float alpha = ring * 1.10;
        if (alpha < 0.005) discard;
        gl_FragColor = vec4(vColor * alpha * 1.6, alpha);
      }
    `,
    uniforms: {
      uPixelRatio: { value: Math.min(window.devicePixelRatio, 2) },
      uSize: { value: HALO_SIZE },
    },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });

  const haloPoints = new THREE.Points(haloGeometry, haloMaterial);
  haloPoints.frustumCulled = false;
  scene.add(haloPoints);

  // Members per cabal root. Rebuilt on snapshot (via handleCastSnapshot)
  // and reused every frame, since bond topology only changes on
  // snapshots; only the positions inside members move per frame.
  const members = new Map();
  let cabalCount = 0;
  // Per-cabal capped member roster for chord rendering. Chord cost is
  // N² so we cap members per cabal at MAX_CABAL_MEMBERS.
  const MAX_CABAL_MEMBERS = 16;

  function rebuildCabals() {
    ufReset();
    for (const { a, b, strength } of bonds.iterBonds()) {
      if (strength < minBondStrength) continue;
      ufUnion(a, b);
    }
    // Members per root. Use a Set during construction to keep O(1)
    // dedup, then materialise to an Array (truncated to
    // MAX_CABAL_MEMBERS) for fast iteration in the frame-time chord
    // repack.
    const sets = new Map();
    for (const { a, b, strength } of bonds.iterBonds()) {
      if (strength < minBondStrength) continue;
      const r = ufFind(a);
      let s = sets.get(r);
      if (!s) { s = new Set(); sets.set(r, s); }
      s.add(a); s.add(b);
    }
    members.clear();
    cabalCount = 0;
    for (const [root, set] of sets) {
      if (set.size < minCabalSize) continue;
      const arr = Array.from(set).slice(0, MAX_CABAL_MEMBERS);
      members.set(root, arr);
      cabalCount += 1;
    }
  }

  function handleCastSnapshot(_snapshot) {
    // bonds is updated by scene.js before this is called. Re-derive
    // cabals once per snapshot, not per frame.
    rebuildCabals();

    // Push per-slot altitude back to agents. Non-members sit on the
    // base shell; cabal members rise into a higher band whose radius
    // grows logarithmically with cabal size. Lift is modest so the
    // cabals read as compact local structures, not dramatic columns.
    if (typeof agents.resetTargetRadii === 'function') {
      agents.resetTargetRadii();
      const baseR = agents.layoutRadius;
      for (const slots of members.values()) {
        if (slots.length < minCabalSize) continue;
        const lift = 22 + 7 * Math.log2(slots.length);
        const r = baseR + lift;
        for (let i = 0; i < slots.length; i += 1) {
          agents.setSlotRadius(slots[i], r);
        }
      }
    }
  }

  function tick() {
    material.uniforms.uTime.value = performance.now() / 1000;

    let slot = 0;
    let haloSlot = 0;
    for (const [root, slots] of members) {
      if (slots.length < minCabalSize) continue;
      const col = colorForCabal(root);

      // 1. Per-member halo: every cabal member gets a wide additive
      //    disc in the cabal's color, drawn behind the cell. Cabal
      //    membership reads at a glance even when chord lines
      //    overlap with bonds.
      for (let i = 0; i < slots.length && haloSlot < MAX_HALO_POINTS; i += 1) {
        const m = slots[i];
        haloPositions[haloSlot * 3 + 0] = positions[m * 3 + 0];
        haloPositions[haloSlot * 3 + 1] = positions[m * 3 + 1];
        haloPositions[haloSlot * 3 + 2] = positions[m * 3 + 2];
        haloColors[haloSlot * 3 + 0] = col[0];
        haloColors[haloSlot * 3 + 1] = col[1];
        haloColors[haloSlot * 3 + 2] = col[2];
        haloSlot += 1;
      }

      // 2. Chord graph between every pair of members. N=3→3 lines,
      //    N=4→6, N=8→28. Bright per-cabal hue. Big cabals dim
      //    slightly so a 12-clique doesn't blow out brighter than
      //    a 3-clique.
      for (let i = 0; i < slots.length && slot < MAX_CHORD_LINES; i += 1) {
        for (let j = i + 1; j < slots.length && slot < MAX_CHORD_LINES; j += 1) {
          const a = slots[i];
          const b = slots[j];
          const vBase = slot * 6;
          linePositions[vBase + 0] = positions[a * 3 + 0];
          linePositions[vBase + 1] = positions[a * 3 + 1];
          linePositions[vBase + 2] = positions[a * 3 + 2];
          linePositions[vBase + 3] = positions[b * 3 + 0];
          linePositions[vBase + 4] = positions[b * 3 + 1];
          linePositions[vBase + 5] = positions[b * 3 + 2];

          const cBase = slot * 6;
          lineColors[cBase + 0] = col[0];
          lineColors[cBase + 1] = col[1];
          lineColors[cBase + 2] = col[2];
          lineColors[cBase + 3] = col[0];
          lineColors[cBase + 4] = col[1];
          lineColors[cBase + 5] = col[2];

          const g = Math.max(0.85, 1.4 / Math.max(1, Math.log2(slots.length)));
          lineGlows[slot * 2 + 0] = g;
          lineGlows[slot * 2 + 1] = g;

          slot += 1;
        }
      }
    }
    geometry.attributes.position.needsUpdate = true;
    geometry.attributes.aColor.needsUpdate = true;
    geometry.attributes.aGlow.needsUpdate = true;
    geometry.setDrawRange(0, slot * 2);

    haloGeometry.attributes.position.needsUpdate = true;
    haloGeometry.attributes.aColor.needsUpdate = true;
    haloGeometry.setDrawRange(0, haloSlot);
  }

  function setVisible(visible) {
    lineSegments.visible = !!visible;
  }

  function dispose() {
    scene.remove(lineSegments);
    scene.remove(haloPoints);
    geometry.dispose();
    material.dispose();
    haloGeometry.dispose();
    haloMaterial.dispose();
    members.clear();
  }

  function diagnostics() {
    return { cabalCount, members: members.size };
  }

  return { lineSegments, tick, handleCastSnapshot, setVisible, dispose, diagnostics };
}
