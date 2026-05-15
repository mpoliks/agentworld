// Trails (Pass 6) — per-agent fading position history.
//
// Each cast member has a ring buffer of its last TRAIL_LENGTH positions.
// Every frame we record current positions and render TRAIL_LENGTH-1
// line segments per cast member (sequential pairs from the ring),
// alpha-decaying from head (bright, just-recorded) to tail (faint,
// oldest).
//
// Memory at maxAgents=5000 and TRAIL_LENGTH=18: ~5MB for positions +
// ~1.7MB for alpha. Renders in a single THREE.LineSegments draw call.

import * as THREE from 'three';

const TRAIL_LENGTH = 8;             // ring depth; segments rendered = LEN-1
const REPACK_EVERY_N_FRAMES = 2;    // repack render buffer every Nth tick;
                                    // the ring still pushes every frame
                                    // (cheap), only the GPU repack throttles

const VERTEX_SHADER = /* glsl */ `
  attribute vec3 aColor;
  attribute float aAge;
  uniform float uTrailLength;
  varying vec3 vColor;
  varying float vAge;
  void main() {
    vColor = aColor;
    vAge = aAge;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const FRAGMENT_SHADER = /* glsl */ `
  precision highp float;
  uniform float uTrailLength;
  varying vec3 vColor;
  varying float vAge;
  void main() {
    // Age 0 = newest segment, age TRAIL_LENGTH-1 = oldest.
    float alpha = 1.0 - vAge / uTrailLength;
    alpha = clamp(alpha, 0.0, 1.0);
    alpha = alpha * alpha * 0.55;
    if (alpha <= 0.001) discard;
    gl_FragColor = vec4(vColor * alpha, alpha);
  }
`;

export function createTrails(scene, opts) {
  if (!opts || !opts.agents) throw new Error('createTrails requires opts.agents');
  const { agents } = opts;
  const positions = agents.positions;
  const maxAgents = positions.length / 3;
  const trailLength = opts.trailLength ?? TRAIL_LENGTH;
  const segmentsPerAgent = trailLength - 1;

  // History buffer: TRAIL_LENGTH positions per agent, as a ring.
  // history[(slot * trailLength + ring) * 3 + xyz].
  const history = new Float32Array(maxAgents * trailLength * 3);
  // Per-slot ring head index.
  const heads = new Uint16Array(maxAgents);
  // True once a slot has been written to TRAIL_LENGTH times so all
  // segments are populated. Until then, we render only the segments
  // that exist.
  const fillCount = new Uint16Array(maxAgents);

  // Render buffers: 2 vertices per segment per agent.
  const totalSegments = maxAgents * segmentsPerAgent;
  const linePositions = new Float32Array(totalSegments * 2 * 3);
  const lineColors = new Float32Array(totalSegments * 2 * 3);
  const lineAges = new Float32Array(totalSegments * 2);

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(linePositions, 3));
  geometry.setAttribute('aColor', new THREE.BufferAttribute(lineColors, 3));
  geometry.setAttribute('aAge', new THREE.BufferAttribute(lineAges, 1));
  geometry.setDrawRange(0, 0);

  const material = new THREE.ShaderMaterial({
    vertexShader: VERTEX_SHADER,
    fragmentShader: FRAGMENT_SHADER,
    uniforms: {
      uTrailLength: { value: trailLength },
    },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });

  const lineSegments = new THREE.LineSegments(geometry, material);
  lineSegments.frustumCulled = false;
  scene.add(lineSegments);

  // Pull current sector colors from the cast renderer's aColor buffer
  // so each trail matches its head's hue exactly. We grab it via the
  // exposed geometry attribute.
  const sourceColors = agents.points.geometry.getAttribute('aColor').array;

  let frameCounter = 0;

  function tick() {
    const slotN = agents.slotCount();
    if (slotN === 0) return;

    // 1) Push current positions into each slot's ring (every frame —
    //    cheap, just a few hundred kilobytes of writes to a JS array).
    for (let i = 0; i < slotN; i += 1) {
      const head = heads[i];
      const base = (i * trailLength + head) * 3;
      history[base + 0] = positions[i * 3 + 0];
      history[base + 1] = positions[i * 3 + 1];
      history[base + 2] = positions[i * 3 + 2];
      heads[i] = (head + 1) % trailLength;
      if (fillCount[i] < trailLength) fillCount[i] += 1;
    }

    // Throttle the expensive GPU repack to every Nth frame so the
    // main thread has room to breathe (lets CDP eval, audio,
    // event handlers run).
    frameCounter += 1;
    if (frameCounter % REPACK_EVERY_N_FRAMES !== 0) return;

    // 2) Repack render buffers. For each slot, emit segments from
    //    most-recent to oldest, pairing consecutive ring entries.
    let outSeg = 0;
    for (let i = 0; i < slotN; i += 1) {
      const fill = fillCount[i];
      if (fill < 2) continue;
      const head = heads[i];
      const cr = sourceColors[i * 3 + 0];
      const cg = sourceColors[i * 3 + 1];
      const cb = sourceColors[i * 3 + 2];

      const maxSegs = Math.min(segmentsPerAgent, fill - 1);
      for (let s = 0; s < maxSegs; s += 1) {
        // Pair (head-1-s, head-2-s) mod trailLength.
        const r1 = (head - 1 - s + trailLength) % trailLength;
        const r2 = (head - 2 - s + trailLength) % trailLength;
        const p1 = (i * trailLength + r1) * 3;
        const p2 = (i * trailLength + r2) * 3;
        const vBase = outSeg * 6;
        linePositions[vBase + 0] = history[p1 + 0];
        linePositions[vBase + 1] = history[p1 + 1];
        linePositions[vBase + 2] = history[p1 + 2];
        linePositions[vBase + 3] = history[p2 + 0];
        linePositions[vBase + 4] = history[p2 + 1];
        linePositions[vBase + 5] = history[p2 + 2];

        const cBase = outSeg * 6;
        lineColors[cBase + 0] = cr;
        lineColors[cBase + 1] = cg;
        lineColors[cBase + 2] = cb;
        lineColors[cBase + 3] = cr;
        lineColors[cBase + 4] = cg;
        lineColors[cBase + 5] = cb;

        lineAges[outSeg * 2 + 0] = s;
        lineAges[outSeg * 2 + 1] = s + 1;
        outSeg += 1;
      }
    }

    geometry.attributes.position.needsUpdate = true;
    geometry.attributes.aColor.needsUpdate = true;
    geometry.attributes.aAge.needsUpdate = true;
    geometry.setDrawRange(0, outSeg * 2);
  }

  function setVisible(visible) {
    lineSegments.visible = !!visible;
  }

  function dispose() {
    scene.remove(lineSegments);
    geometry.dispose();
    material.dispose();
  }

  return { lineSegments, tick, setVisible, dispose };
}
