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
const NORMAL_COLOR = [1.0, 0.74, 0.36];   // amber by default

const VERTEX_SHADER = /* glsl */ `
  attribute vec3 aColor;
  attribute float aGlow;
  varying vec3 vColor;
  varying float vGlow;
  void main() {
    vColor = aColor;
    vGlow = aGlow;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const FRAGMENT_SHADER = /* glsl */ `
  precision highp float;
  varying vec3 vColor;
  varying float vGlow;
  void main() {
    float alpha = clamp(vGlow, 0.0, 1.0);
    if (alpha <= 0.0) discard;
    gl_FragColor = vec4(vColor * alpha, alpha);
  }
`;

// Stable hash-to-color: small palette of bright cabal tints so the
// eye picks out distinct clusters at a glance.
const CABAL_COLORS = [
  [1.00, 0.74, 0.36],
  [0.42, 0.83, 0.99],
  [0.99, 0.50, 0.78],
  [0.69, 0.99, 0.62],
  [0.97, 0.97, 0.40],
  [0.65, 0.55, 1.00],
  [1.00, 0.55, 0.40],
  [0.40, 1.00, 0.85],
];

function colorForCabal(rootSlot) {
  return CABAL_COLORS[rootSlot % CABAL_COLORS.length];
}

export function createCabals(scene, opts) {
  if (!opts || !opts.agents) throw new Error('createCabals requires opts.agents');
  if (!opts.bonds) throw new Error('createCabals requires opts.bonds');
  const { agents, bonds } = opts;
  const minBondStrength = opts.minBondStrength ?? MIN_BOND_STRENGTH;
  const minCabalSize = opts.minCabalSize ?? MIN_CABAL_SIZE;

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

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(linePositions, 3));
  geometry.setAttribute('aColor', new THREE.BufferAttribute(lineColors, 3));
  geometry.setAttribute('aGlow', new THREE.BufferAttribute(lineGlows, 1));
  geometry.setDrawRange(0, 0);

  const material = new THREE.ShaderMaterial({
    vertexShader: VERTEX_SHADER,
    fragmentShader: FRAGMENT_SHADER,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });

  const lineSegments = new THREE.LineSegments(geometry, material);
  lineSegments.frustumCulled = false;
  scene.add(lineSegments);

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
  }

  function tick() {
    let slot = 0;
    for (const [root, slots] of members) {
      if (slots.length < minCabalSize) continue;
      const col = colorForCabal(root);
      // Render chord graph: every pair within the cabal becomes one
      // line. N=3→3 lines, N=4→6, N=8→28. Strong cabals look like
      // dense lattices.
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

          // Bigger cabals dim slightly so a 12-clique doesn't blow
          // out brighter than a 3-clique — keep the structure
          // legible across sizes. Floor at 0.55 so even big cabals
          // read clearly against the dimmed bond layer.
          const g = Math.max(0.55, 0.95 / Math.max(1, Math.log2(slots.length)));
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
  }

  function setVisible(visible) {
    lineSegments.visible = !!visible;
  }

  function dispose() {
    scene.remove(lineSegments);
    geometry.dispose();
    material.dispose();
    members.clear();
  }

  function diagnostics() {
    return { cabalCount, members: members.size };
  }

  return { lineSegments, tick, handleCastSnapshot, setVisible, dispose, diagnostics };
}
