// Bonds (Pass 6) — persistent pairwise structure on top of the cast.
//
// Each cast_snapshot the engine reports recent_partners per cast member.
// We treat every (slot, in-cast partner) sighting as a bond increment;
// all bonds decay multiplicatively per snapshot. The strength map is an
// EMA over recent trade activity.
//
// Bonds are bright lines so they read clearly against the additive-
// blended cast. They also drive the cabal-detection union-find in
// cabals.js, which renders triangle/clique chord graphs on top of the
// raw bond layer.

import * as THREE from 'three';

const FADE_RATE = 0.94;
const INC_PER_SIGHTING = 1.0;
const MIN_STRENGTH = 0.10;       // tracking threshold (still used for force)
const RENDER_MIN_STRENGTH = 1.5; // only render bonds at least this strong
const MAX_STRENGTH = 8.0;
const RENDER_MAX = 4096;
const KEY_STRIDE = 8192;

const VERTEX_SHADER = /* glsl */ `
  attribute float aStrength;
  uniform float uStrengthScale;
  varying float vStrength;
  void main() {
    vStrength = clamp(aStrength * uStrengthScale, 0.0, 1.0);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const FRAGMENT_SHADER = /* glsl */ `
  precision highp float;
  uniform vec3 uColor;
  varying float vStrength;
  void main() {
    if (vStrength <= 0.0) discard;
    // Quad-knee with low ceiling: bonds are connective tissue, not
    // the main visual. Cabal chord lines and cells should dominate.
    float alpha = vStrength * vStrength * 0.45;
    gl_FragColor = vec4(uColor * alpha, alpha);
  }
`;

export function createBonds(scene, opts) {
  if (!opts || !opts.agents) throw new Error('createBonds requires opts.agents');
  const { agents } = opts;
  const fadeRate = opts.fadeRate ?? FADE_RATE;
  const minStrength = opts.minStrength ?? MIN_STRENGTH;
  const maxStrength = opts.maxStrength ?? MAX_STRENGTH;
  const color = opts.color ?? [0.96, 0.97, 1.0];

  const positions = agents.positions;
  const strengths = new Map();

  const linePositions = new Float32Array(RENDER_MAX * 2 * 3);
  const lineStrengths = new Float32Array(RENDER_MAX * 2);

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(linePositions, 3));
  geometry.setAttribute('aStrength', new THREE.BufferAttribute(lineStrengths, 1));
  geometry.setDrawRange(0, 0);

  const material = new THREE.ShaderMaterial({
    vertexShader: VERTEX_SHADER,
    fragmentShader: FRAGMENT_SHADER,
    uniforms: {
      uStrengthScale: { value: 1.0 / maxStrength },
      uColor: { value: new THREE.Color().fromArray(color) },
    },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });

  const lineSegments = new THREE.LineSegments(geometry, material);
  lineSegments.frustumCulled = false;
  scene.add(lineSegments);

  function pairKey(a, b) {
    return a < b ? a * KEY_STRIDE + b : b * KEY_STRIDE + a;
  }
  function decodePair(key) {
    const a = Math.floor(key / KEY_STRIDE);
    return [a, key - a * KEY_STRIDE];
  }

  function handleCastSnapshot(snapshot) {
    if (!snapshot || snapshot.length === 0) return;

    for (const [key, s] of strengths) {
      const next = s * fadeRate;
      if (next < minStrength) strengths.delete(key);
      else strengths.set(key, next);
    }

    for (let i = 0; i < snapshot.length; i += 1) {
      const entry = snapshot[i];
      const slotA = agents.slotForIdx(entry.idx);
      if (slotA < 0) continue;
      const partners = entry.recent_partners;
      if (!partners) continue;

      for (let p = 0; p < partners.length; p += 1) {
        const slotB = agents.slotForIdx(partners[p]);
        if (slotB < 0 || slotB === slotA) continue;
        const key = pairKey(slotA, slotB);
        const next = (strengths.get(key) ?? 0) + INC_PER_SIGHTING;
        strengths.set(key, next > maxStrength ? maxStrength : next);
      }
    }
  }

  function tick() {
    let slot = 0;
    for (const [key, strength] of strengths) {
      if (slot >= RENDER_MAX) break;
      if (strength < RENDER_MIN_STRENGTH) continue;
      const [a, b] = decodePair(key);
      const aBase = a * 3;
      const bBase = b * 3;
      const vBase = slot * 6;
      linePositions[vBase + 0] = positions[aBase + 0];
      linePositions[vBase + 1] = positions[aBase + 1];
      linePositions[vBase + 2] = positions[aBase + 2];
      linePositions[vBase + 3] = positions[bBase + 0];
      linePositions[vBase + 4] = positions[bBase + 1];
      linePositions[vBase + 5] = positions[bBase + 2];
      lineStrengths[slot * 2 + 0] = strength;
      lineStrengths[slot * 2 + 1] = strength;
      slot += 1;
    }
    geometry.attributes.position.needsUpdate = true;
    geometry.attributes.aStrength.needsUpdate = true;
    geometry.setDrawRange(0, slot * 2);
  }

  function* iterBonds() {
    for (const [key, strength] of strengths) {
      const [a, b] = decodePair(key);
      yield { a, b, strength };
    }
  }

  function bondCount() {
    return strengths.size;
  }

  function setVisible(visible) {
    lineSegments.visible = !!visible;
  }

  function dispose() {
    scene.remove(lineSegments);
    geometry.dispose();
    material.dispose();
    strengths.clear();
  }

  return {
    lineSegments,
    handleCastSnapshot,
    tick,
    iterBonds,
    bondCount,
    setVisible,
    dispose,
  };
}
