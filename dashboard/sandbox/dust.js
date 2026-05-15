// Dust — background population density on the sphere surface.
//
// Pure decoration. ~50k static points spread evenly across the
// inner shell (radius 395) so the sphere reads as populated even
// where the engine-driven cast members are sparse. Engine state
// doesn't drive these — they're a visual texture that makes the
// sphere look like a populated globe rather than a thin ring of
// dots.
//
// Each dust mote inherits a sector palette color so the whole shell
// has the same 12-band hue rotation as the cast layer. Dots are
// tiny (~1.5 px) and fairly dim so cabal halos and agent cells
// continue to dominate the eye, but the sphere never reads as empty.

import * as THREE from 'three';

import { sectorPalette } from './palette.js';

const DUST_COUNT = 50000;
const DUST_RADIUS = 395;
const DUST_BASE_SIZE = 1.4;
const DUST_BRIGHTNESS = 0.55;

const VERTEX_SHADER = /* glsl */ `
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
`;

const FRAGMENT_SHADER = /* glsl */ `
  precision highp float;
  uniform float uBrightness;
  varying vec3 vColor;
  void main() {
    vec2 uv = gl_PointCoord - 0.5;
    float d = length(uv);
    if (d > 0.5) discard;
    float coverage = 1.0 - smoothstep(0.35, 0.50, d);
    gl_FragColor = vec4(vColor * uBrightness * coverage, coverage);
  }
`;

export function createDust(scene, opts = {}) {
  const count = opts.count ?? DUST_COUNT;
  const radius = opts.radius ?? DUST_RADIUS;
  const palette = sectorPalette();

  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);

  // Fibonacci sphere distribution gives even coverage without pole
  // bias; same trick the cast layer uses. Color hashes by latitude
  // band so the sector palette reads on the dust too.
  const phi = Math.PI * (3.0 - Math.sqrt(5.0));
  for (let i = 0; i < count; i += 1) {
    const y = 1.0 - (i / (count - 1)) * 2.0;
    const r = Math.sqrt(Math.max(0, 1.0 - y * y));
    const theta = phi * i;
    positions[i * 3 + 0] = Math.cos(theta) * r * radius;
    positions[i * 3 + 1] = y * radius;
    positions[i * 3 + 2] = Math.sin(theta) * r * radius;

    // Map latitude band (-1..1) to sector palette so dust matches
    // the cast layer's hue rotation.
    const lat = (y + 1) * 0.5;                  // 0 → south, 1 → north
    const palIdx = Math.min(palette.length - 1, Math.floor(lat * palette.length));
    const rgb = palette[palIdx];
    // Small per-mote color jitter so the bands aren't perfectly flat.
    const jitter = 0.8 + Math.random() * 0.4;
    colors[i * 3 + 0] = rgb[0] * jitter;
    colors[i * 3 + 1] = rgb[1] * jitter;
    colors[i * 3 + 2] = rgb[2] * jitter;
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('aColor', new THREE.BufferAttribute(colors, 3));

  const material = new THREE.ShaderMaterial({
    vertexShader: VERTEX_SHADER,
    fragmentShader: FRAGMENT_SHADER,
    uniforms: {
      uPixelRatio: { value: Math.min(window.devicePixelRatio, 2) },
      uSize: { value: DUST_BASE_SIZE },
      uBrightness: { value: DUST_BRIGHTNESS },
    },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });

  const points = new THREE.Points(geometry, material);
  points.frustumCulled = false;
  scene.add(points);

  function setVisible(visible) {
    points.visible = !!visible;
  }
  function dispose() {
    scene.remove(points);
    geometry.dispose();
    material.dispose();
  }
  return { points, setVisible, dispose };
}
