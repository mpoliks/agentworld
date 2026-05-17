// Trade edges (Pass 23, surplus-tiered in Pass 28). Each sampled
// pair spawns a great-circle arc between the two agents' head
// faces. The arc PERSISTS for ~4 seconds and re-tracks each
// endpoint every frame to the agent's current head face — so the
// line follows the two caterpillars as they walk.
//
// Three thickness tiers routed by per-arc real_surplus:
//   thin   (linewidth 0.8)  small trades — the per-tick firehose
//   mid    (linewidth 2.0)  moderate trades
//   thick  (linewidth 5.0)  high-surplus standout trades
//
// Each tier is its own LineSegments2 mesh with its own LineMaterial
// (LineMaterial.linewidth is a uniform per-material, so per-arc
// thickness requires distinct materials). All three meshes live in
// a single Group so scene-level transforms (the EBI shape morph in
// scene.js) apply to all of them via group.scale.
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
const MAX_AGE_FRAMES = 240;      // 4 s at 60 fps

// Tier configuration. Per-tier active-arc caps sum to ~800 (the
// pre-tier global cap). Thin gets the largest budget because most
// trades are small; thick gets the smallest because big trades are
// rare and should be visually scarce when they appear.
const TIER_WIDTHS = [0.6, 2.2, 6.0];
const TIER_CAPS = [500, 200, 100];
// Direct base_surplus thresholds, calibrated against the
// distribution observed in spatial_sandbox at defaults
// (p50 ≈ 0.12, p90 ≈ 0.27, max ≈ 0.45). Roughly 60/30/10 split
// at baseline — bigger trades may flip the split as the user
// drives the levers around.
const TIER_THRESHOLDS = [0.10, 0.25];
function surplusToTier(surplus) {
  if (surplus < TIER_THRESHOLDS[0]) return 0;
  if (surplus < TIER_THRESHOLDS[1]) return 1;
  return 2;
}

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
  const tierWidths = opts.tierWidths ?? TIER_WIDTHS;
  const tierCaps = opts.tierCaps ?? TIER_CAPS;

  // Per-tier rendering state. One LineSegments2 + LineMaterial +
  // buffers per thickness bucket. The Group holds all three so
  // scene.js's per-mesh transforms (shape morph scale.y) apply
  // uniformly.
  const group = new THREE.Group();
  group.renderOrder = 10;
  scene.add(group);
  const tiers = tierWidths.map((width, i) => {
    const cap = tierCaps[i];
    const maxSegTotal = cap * ARC_SEGMENTS;
    const positionsArray = new Float32Array(maxSegTotal * 6);
    const colorsArray = new Float32Array(maxSegTotal * 6);
    const geometry = new LineSegmentsGeometry();
    geometry.setPositions(positionsArray);
    geometry.setColors(colorsArray);
    geometry.instanceCount = 0;
    const positionsBuffer = geometry.attributes.instanceStart.data;
    const colorsBuffer = geometry.attributes.instanceColorStart.data;
    const material = new LineMaterial({
      vertexColors: true,
      linewidth: width,
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
    group.add(mesh);
    return {
      positionsArray, colorsArray, geometry, material, mesh,
      positionsBuffer, colorsBuffer,
      cap, maxSegTotal,
      active: [],
    };
  });

  function setResolution(w, h) {
    for (const t of tiers) t.material.resolution.set(w, h);
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

  // Write one arc into the given tier's buffers starting at
  // segIdxStart. Returns the number of segments written (0 if
  // either endpoint is missing).
  function writeArc(tier, edge, segIdxStart, altScale, globalAlt) {
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
    const cr = base[0] * (1 - fade) + FADE_R * fade;
    const cg = base[1] * (1 - fade) + FADE_G * fade;
    const cbl = base[2] * (1 - fade) + FADE_B * fade;

    const positionsArray = tier.positionsArray;
    const colorsArray = tier.colorsArray;

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

  // Called per snapshot — route each new edge to its surplus tier.
  // Both endpoints must be in the cast or the edge is discarded.
  function handleEdges(edges) {
    if (!edges) return;
    for (let i = 0; i < edges.length; i += 1) {
      const e = edges[i];
      if (!e) continue;
      const a = e.proto_a;
      const b = e.proto_b;
      if (typeof a !== 'number' || typeof b !== 'number') continue;
      if (agents.currentFaceForIdx(a) < 0 || agents.currentFaceForIdx(b) < 0) continue;
      // base_surplus (pre-friction "would-be" surplus) is used
      // instead of real_surplus because real_surplus is 0 for
      // rejected pairs by design — and a big rejected trade
      // ("big trade hit the law gate") is exactly the kind of
      // event we want rendered thick.
      const surplus = Number.isFinite(e.base_surplus)
        ? Math.max(0, e.base_surplus)
        : (Number.isFinite(e.real_surplus) ? Math.max(0, e.real_surplus) : 0);
      const ti = surplusToTier(surplus);
      const tier = tiers[ti];
      if (tier.active.length >= tier.cap) tier.active.shift();
      tier.active.push({ a, b, isReject: !!e.reject_reason, age: 0, surplus });
    }
  }

  // Called every animation frame — age, prune, then rebuild the
  // arc buffers from current agent positions, per tier.
  function tick() {
    const altScale = surface.mesh?.material?.uniforms?.uAltitudeScale?.value ?? 1.0;
    const globalAlt = surface.mesh?.material?.uniforms?.uGlobalAltitude?.value ?? 0.0;

    for (const tier of tiers) {
      const active = tier.active;
      for (let i = active.length - 1; i >= 0; i -= 1) {
        active[i].age += 1;
        if (active[i].age >= MAX_AGE_FRAMES) active.splice(i, 1);
      }
      if (active.length === 0) {
        tier.geometry.instanceCount = 0;
        continue;
      }
      let segCount = 0;
      for (let i = 0; i < active.length; i += 1) {
        if (segCount + ARC_SEGMENTS > tier.maxSegTotal) break;
        const wrote = writeArc(tier, active[i], segCount, altScale, globalAlt);
        segCount += wrote;
      }
      tier.geometry.instanceCount = segCount;
      tier.positionsBuffer.needsUpdate = true;
      tier.colorsBuffer.needsUpdate = true;
    }
  }

  function setVisible(b) { group.visible = !!b; }
  function dispose() {
    scene.remove(group);
    for (const tier of tiers) {
      tier.geometry.dispose();
      tier.material.dispose();
    }
  }
  function diagnostics() {
    let active = 0;
    let segments = 0;
    for (const tier of tiers) {
      active += tier.active.length;
      segments += tier.geometry.instanceCount;
    }
    return { active, segments, tierActive: tiers.map((t) => t.active.length) };
  }
  // Restart hook — drop in-flight arcs immediately so the new run
  // doesn't render trade lines anchored to the prior cast's slots.
  function reset() {
    for (const tier of tiers) {
      tier.active.length = 0;
      tier.geometry.instanceCount = 0;
    }
  }

  // `mesh` exposed for backwards-compat with scene.js's transform
  // hooks (applyShape sets edges.mesh.scale.y). The group wraps the
  // per-tier meshes so the scale applies to all three at once.
  return {
    mesh: group, handleEdges, tick, setResolution, setVisible, dispose, diagnostics, reset,
  };
}
