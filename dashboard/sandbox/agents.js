// Cast renderer — every visible agent is one point in a single
// THREE.Points draw call. cast_snapshot_v2 events update color (sector),
// size (log wealth), and glow (autonomy²) in place.
//
// Position assignment is a stable Fibonacci-sphere layout keyed by
// cast-slot. force.js (later module) overwrites the position attribute
// with the simulated layout; until then the sphere keeps the agents
// visible and evenly distributed so the per-agent colour and size
// signal is legible.

import * as THREE from 'three';

import { SECTOR_NAMES, sectorPalette } from './palette.js';

const VERTEX_SHADER = /* glsl */ `
  attribute vec3 aColor;
  attribute float aSize;
  attribute float aGlow;

  varying vec3 vColor;
  varying float vGlow;

  uniform float uPixelRatio;
  uniform float uSizeScale;

  void main() {
    vColor = aColor;
    vGlow = aGlow;

    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    // Point size scales with pixel ratio (so 1pt looks the same on
    // retina) and falls off with depth (perspective size attenuation).
    gl_PointSize = aSize * uSizeScale * uPixelRatio * (300.0 / -mvPosition.z);
    gl_Position = projectionMatrix * mvPosition;
  }
`;

const FRAGMENT_SHADER = /* glsl */ `
  precision highp float;

  varying vec3 vColor;
  varying float vGlow;

  void main() {
    // Soft disk: 1.0 at centre, 0.0 at edge of the point sprite.
    vec2 uv = gl_PointCoord - 0.5;
    float d = length(uv);
    float disk = 1.0 - smoothstep(0.35, 0.5, d);
    if (disk <= 0.0) discard;

    // Inner halo for high-autonomy agents — the glow term lifts the
    // centre and gives the bloom pass something to grab when it lands
    // in a later module.
    float halo = 1.0 - smoothstep(0.0, 0.5, d);
    vec3 rgb = vColor + vColor * vGlow * halo * 1.2;

    gl_FragColor = vec4(rgb, disk);
  }
`;

/**
 * Build the cast renderer.
 *
 * @param {THREE.Scene} scene
 * @param {{ maxAgents?: number, sizeScale?: number }} opts
 * @returns {{
 *   points: THREE.Points,
 *   handleCastSnapshot: (snapshot: Array) => void,
 *   setVisible: (visible: boolean) => void,
 *   dispose: () => void,
 * }}
 */
export function createAgents(scene, opts = {}) {
  const maxAgents = opts.maxAgents ?? 5000;
  const sizeScale = opts.sizeScale ?? 1.0;
  const radius = opts.layoutRadius ?? 400;

  const palette = sectorPalette();  // [12][3] of float rgb in [0,1]

  const positions = new Float32Array(maxAgents * 3);
  const colors = new Float32Array(maxAgents * 3);
  const sizes = new Float32Array(maxAgents);
  const glows = new Float32Array(maxAgents);

  // Fibonacci sphere — stable, evenly distributed, idx-independent.
  // force.js will overwrite these positions per tick once it lands.
  const phi = Math.PI * (3.0 - Math.sqrt(5.0));
  for (let i = 0; i < maxAgents; i += 1) {
    const y = 1.0 - (i / (maxAgents - 1)) * 2.0;
    const r = Math.sqrt(1.0 - y * y);
    const theta = phi * i;
    positions[i * 3 + 0] = Math.cos(theta) * r * radius;
    positions[i * 3 + 1] = y * radius;
    positions[i * 3 + 2] = Math.sin(theta) * r * radius;
    // Slots start hidden (size 0); handleCastSnapshot fills them in
    // as cast entries arrive.
    sizes[i] = 0.0;
    glows[i] = 0.0;
    colors[i * 3 + 0] = 0.0;
    colors[i * 3 + 1] = 0.0;
    colors[i * 3 + 2] = 0.0;
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('aColor', new THREE.BufferAttribute(colors, 3));
  geometry.setAttribute('aSize', new THREE.BufferAttribute(sizes, 1));
  geometry.setAttribute('aGlow', new THREE.BufferAttribute(glows, 1));
  // drawRange caps the GPU at the number of live agents; grows as the
  // cast snapshot fills slots.
  geometry.setDrawRange(0, 0);

  const material = new THREE.ShaderMaterial({
    vertexShader: VERTEX_SHADER,
    fragmentShader: FRAGMENT_SHADER,
    uniforms: {
      uPixelRatio: { value: Math.min(window.devicePixelRatio, 2) },
      uSizeScale: { value: sizeScale },
    },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });

  const points = new THREE.Points(geometry, material);
  points.frustumCulled = false;  // a single draw call; let the GPU clip
  scene.add(points);

  // idx (cast prototype id) → slot in the buffers. Stable across ticks
  // because cast indices don't churn — see PR #6 commit notes.
  const slotByIdx = new Map();
  let nextSlot = 0;

  function slotFor(idx) {
    let slot = slotByIdx.get(idx);
    if (slot === undefined) {
      if (nextSlot >= maxAgents) return -1;
      slot = nextSlot++;
      slotByIdx.set(idx, slot);
    }
    return slot;
  }

  function handleCastSnapshot(snapshot) {
    if (!snapshot || snapshot.length === 0) return;

    for (let i = 0; i < snapshot.length; i += 1) {
      const entry = snapshot[i];
      const slot = slotFor(entry.idx);
      if (slot < 0) continue;

      const palIdx = ((entry.sector % palette.length) + palette.length) % palette.length;
      const rgb = palette[palIdx];
      colors[slot * 3 + 0] = rgb[0];
      colors[slot * 3 + 1] = rgb[1];
      colors[slot * 3 + 2] = rgb[2];

      // Wealth → size. log1p compresses the long tail; floor keeps
      // zero-wealth agents visible.
      const wealth = Math.max(0, entry.wealth ?? 0);
      sizes[slot] = 2.0 + Math.log1p(wealth) * 0.9;

      // Autonomy² → glow strength. Humans (low autonomy) stay flat;
      // agents (high autonomy) get the halo.
      const autonomy = Math.min(1, Math.max(0, entry.autonomy ?? 0));
      glows[slot] = autonomy * autonomy;
    }

    geometry.attributes.aColor.needsUpdate = true;
    geometry.attributes.aSize.needsUpdate = true;
    geometry.attributes.aGlow.needsUpdate = true;
    geometry.setDrawRange(0, nextSlot);
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

  return {
    points,
    handleCastSnapshot,
    setVisible,
    dispose,
    // Exposed for the (later) inspector raycaster.
    _slotByIdx: slotByIdx,
  };
}

export { SECTOR_NAMES };
