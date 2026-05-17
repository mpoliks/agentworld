// Trade edges (Pass 23). Each sampled pair spawns a great-circle
// arc between the two agents' head faces. The arc PERSISTS for ~4
// seconds and re-tracks each endpoint every frame to the agent's
// current head face — so the line follows the two caterpillars as
// they walk.
//
// LineSegments2 + LineMaterial gives screen-space-thick lines
// (LineBasicMaterial is capped at 1px on most WebGL drivers).
// Colour fades toward the cream background over the lifetime so
// the line softly dissolves rather than popping out.

import * as THREE from 'three';
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';
import { LineSegmentsGeometry } from 'three/addons/lines/LineSegmentsGeometry.js';
import { LineSegments2 } from 'three/addons/lines/LineSegments2.js';

const ARC_SEGMENTS = 60;         // arc samples per pair — higher = smoother
const MAX_ACTIVE = 800;          // hard cap on simultaneously-drawn arcs
const MAX_AGE_FRAMES = 240;      // 4 s at 60 fps
const MAX_SEG_TOTAL = MAX_ACTIVE * ARC_SEGMENTS;

// Lines fade toward the cream paper colour as they age.
const FADE_R = 0.94;
const FADE_G = 0.93;
const FADE_B = 0.90;

export function createEdges(scene, surface, agents, opts = {}) {
  const { faceCentroids, vertAltitudes, vertIds, radius } = surface;
  const sphereRadius = opts.sphereRadius ?? radius ?? 700;
  const successColor = opts.successColor ?? [0.10, 0.35, 0.95];
  const rejectColor = opts.rejectColor ?? [0.95, 0.15, 0.15];
  const arcLift = opts.arcLift ?? 1.005;
  // archHeight is the additive radial bulge at the arc midpoint as
  // a fraction of the endpoint radius. sin(πt) profile — clean
  // parabolic arch anchored to both endpoints.
  const archHeight = opts.archHeight ?? 0.28;
  const lineWidth = opts.lineWidth ?? 2.0;

  // Active edge list. Each entry: { a, b, isReject, age }.
  const active = [];

  const positionsArray = new Float32Array(MAX_SEG_TOTAL * 6);
  const colorsArray = new Float32Array(MAX_SEG_TOTAL * 6);

  const geometry = new LineSegmentsGeometry();
  geometry.setPositions(positionsArray);
  geometry.setColors(colorsArray);
  geometry.instanceCount = 0;
  // Cached refs to the underlying interleaved buffers so we can
  // mark them needsUpdate without re-calling setPositions / setColors
  // (which would allocate new buffers each frame).
  const positionsBuffer = geometry.attributes.instanceStart.data;
  const colorsBuffer = geometry.attributes.instanceColorStart.data;

  const material = new LineMaterial({
    vertexColors: true,
    linewidth: lineWidth,
    transparent: true,
    opacity: 1.0,
    depthTest: false,
    depthWrite: false,
    worldUnits: false,
  });
  material.resolution.set(window.innerWidth, window.innerHeight);

  const mesh = new LineSegments2(geometry, material);
  mesh.renderOrder = 10;
  mesh.frustumCulled = false;
  scene.add(mesh);

  function setResolution(w, h) {
    material.resolution.set(w, h);
  }

  // Face's effective displaced centroid: faceCentroids[f] * (1 + altF * altScale).
  function faceDisplacedCentroid(f, altScale, globalAlt, out) {
    const cx = faceCentroids[f * 3 + 0];
    const cy = faceCentroids[f * 3 + 1];
    const cz = faceCentroids[f * 3 + 2];
    let avgAlt = 0;
    if (vertAltitudes && vertIds) {
      const b = f * 3;
      avgAlt = (vertAltitudes[vertIds[b + 0]] + vertAltitudes[vertIds[b + 1]] + vertAltitudes[vertIds[b + 2]]) / 3;
    }
    const k = 1 + (avgAlt + globalAlt) * altScale;
    out[0] = cx * k;
    out[1] = cy * k;
    out[2] = cz * k;
  }

  const _pa = [0, 0, 0];
  const _pb = [0, 0, 0];

  // Write one arc into the buffers starting at segIdxStart. Returns
  // the number of segments written (0 if either endpoint is missing).
  function writeArc(edge, segIdxStart, altScale, globalAlt) {
    const fa = agents.currentFaceForIdx(edge.a);
    const fb = agents.currentFaceForIdx(edge.b);
    if (fa < 0 || fb < 0 || fa === fb) return 0;

    faceDisplacedCentroid(fa, altScale, globalAlt, _pa);
    faceDisplacedCentroid(fb, altScale, globalAlt, _pb);

    const ra = Math.sqrt(_pa[0] * _pa[0] + _pa[1] * _pa[1] + _pa[2] * _pa[2]);
    const rb = Math.sqrt(_pb[0] * _pb[0] + _pb[1] * _pb[1] + _pb[2] * _pb[2]);
    if (ra < 1e-3 || rb < 1e-3) return 0;

    const ax = _pa[0] / ra, ay = _pa[1] / ra, az = _pa[2] / ra;
    const bx = _pb[0] / rb, by = _pb[1] / rb, bz = _pb[2] / rb;
    let dot = ax * bx + ay * by + az * bz;
    if (dot > 1) dot = 1; else if (dot < -1) dot = -1;
    const angle = Math.acos(dot);
    const sinA = Math.sin(angle);

    const fade = edge.age / MAX_AGE_FRAMES;       // 0..1
    const base = edge.isReject ? rejectColor : successColor;
    // Surplus weight: low-surplus trades fade toward the background
    // cream so the big trades pop out of the 1,500-arc-per-tick
    // firehose. sqrt curve so the long-tail of tiny surpluses
    // doesn't all crowd at 0. Floor at 0.15 so micro-trades are
    // still faintly visible — they tell the user a trade happened
    // even if it wasn't meaningful.
    const surplusFrac = Math.min(1, Math.sqrt(edge.surplus) / 6);
    const w = 0.15 + 0.85 * surplusFrac;
    const cr = (base[0] * (1 - fade) + FADE_R * fade) * w + FADE_R * (1 - w);
    const cg = (base[1] * (1 - fade) + FADE_G * fade) * w + FADE_G * (1 - w);
    const cbl = (base[2] * (1 - fade) + FADE_B * fade) * w + FADE_B * (1 - w);

    let prevX = ax * ra * arcLift;
    let prevY = ay * ra * arcLift;
    let prevZ = az * ra * arcLift;

    for (let s = 1; s <= ARC_SEGMENTS; s += 1) {
      const t = s / ARC_SEGMENTS;
      let ux, uy, uz;
      if (sinA < 1e-4) {
        ux = ax * (1 - t) + bx * t;
        uy = ay * (1 - t) + by * t;
        uz = az * (1 - t) + bz * t;
        const ul = Math.sqrt(ux * ux + uy * uy + uz * uz) || 1;
        ux /= ul; uy /= ul; uz /= ul;
      } else {
        const s0 = Math.sin((1 - t) * angle) / sinA;
        const s1 = Math.sin(t * angle) / sinA;
        ux = ax * s0 + bx * s1;
        uy = ay * s0 + by * s1;
        uz = az * s0 + bz * s1;
      }
      const baseR = ra * (1 - t) + rb * t;
      // sin(πt) parabolic arch — zero at endpoints, peak at t=0.5.
      const archMul = 1.0 + archHeight * Math.sin(t * Math.PI);
      const rt = baseR * arcLift * archMul;
      const nx = ux * rt, ny = uy * rt, nz = uz * rt;

      const segIdx = segIdxStart + (s - 1);
      const off = segIdx * 6;
      positionsArray[off + 0] = prevX;
      positionsArray[off + 1] = prevY;
      positionsArray[off + 2] = prevZ;
      positionsArray[off + 3] = nx;
      positionsArray[off + 4] = ny;
      positionsArray[off + 5] = nz;
      colorsArray[off + 0] = cr;
      colorsArray[off + 1] = cg;
      colorsArray[off + 2] = cbl;
      colorsArray[off + 3] = cr;
      colorsArray[off + 4] = cg;
      colorsArray[off + 5] = cbl;

      prevX = nx; prevY = ny; prevZ = nz;
    }
    return ARC_SEGMENTS;
  }

  // Called per snapshot — append new edges to the active list. Both
  // endpoints must be in the cast or the edge is discarded.
  function handleEdges(edges) {
    if (!edges) return;
    for (let i = 0; i < edges.length; i += 1) {
      const e = edges[i];
      if (!e) continue;
      const a = e.proto_a;
      const b = e.proto_b;
      if (typeof a !== 'number' || typeof b !== 'number') continue;
      if (agents.currentFaceForIdx(a) < 0 || agents.currentFaceForIdx(b) < 0) continue;
      if (active.length >= MAX_ACTIVE) active.shift();
      // surplus drives a per-arc visibility weight in writeArc so
      // big-surplus trades stand out from the per-tick firehose
      // (~1,500 sampled pairs every snapshot). Rejected pairs use
      // their would-have-been surplus the same way.
      const surplus = Number.isFinite(e.real_surplus)
        ? Math.max(0, e.real_surplus)
        : (Number.isFinite(e.base_surplus) ? Math.max(0, e.base_surplus) : 0);
      active.push({
        a, b,
        isReject: !!e.reject_reason,
        age: 0,
        surplus,
      });
    }
  }

  // Called every animation frame — age, prune, then rebuild the
  // arc buffers from current agent positions.
  function tick() {
    // Age + prune in-place (back-to-front for splice efficiency).
    for (let i = active.length - 1; i >= 0; i -= 1) {
      active[i].age += 1;
      if (active[i].age >= MAX_AGE_FRAMES) active.splice(i, 1);
    }
    if (active.length === 0) {
      geometry.instanceCount = 0;
      return;
    }
    const altScale = surface.mesh?.material?.uniforms?.uAltitudeScale?.value ?? 1.0;
    const globalAlt = surface.mesh?.material?.uniforms?.uGlobalAltitude?.value ?? 0.0;

    let segCount = 0;
    for (let i = 0; i < active.length; i += 1) {
      if (segCount + ARC_SEGMENTS > MAX_SEG_TOTAL) break;
      const wrote = writeArc(active[i], segCount, altScale, globalAlt);
      segCount += wrote;
    }
    geometry.instanceCount = segCount;
    positionsBuffer.needsUpdate = true;
    colorsBuffer.needsUpdate = true;
  }

  function setVisible(b) { mesh.visible = !!b; }
  function dispose() {
    scene.remove(mesh);
    geometry.dispose();
    material.dispose();
  }
  function diagnostics() {
    return { active: active.length, segments: geometry.instanceCount };
  }
  // Restart hook — drop in-flight arcs immediately so the new run
  // doesn't render trade lines anchored to the prior cast's slots.
  function reset() {
    active.length = 0;
    geometry.instanceCount = 0;
  }

  return {
    mesh, handleEdges, tick, setResolution, setVisible, dispose, diagnostics, reset,
  };
}
