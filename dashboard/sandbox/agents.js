// Caterpillar agents (Pass 17c) — graph-walking, grid-shaped bodies.
//
// Each agent occupies one icosphere face. Each step moves it to an
// edge-adjacent face. The agent's body is the trail of recently-
// occupied faces; each body segment is rendered as the actual three
// vertices of the grid face it sits on, scaled toward the centroid
// by segmentScale (so gridlines stay visible around it) and lifted
// radially by the agent's stack altitude.
//
// This way a caterpillar looks like a chain of literally-adjacent
// grid triangles, alternating orientation in the natural ▲▼▲▼
// pattern of the icosphere tessellation.
//
// Engine signal bindings (Pass 17c):
//   wealth (level)        → visible body length (log2 bucket)
//   capability            → step rate (steps/sec; min..max)
//   is_human              → body-length multiplier (more segments,
//                           same triangle size)
//   stack                 → vertical lift = sphereRadius + stack · stackLift
//   firm_id               → strong force-following toward firm centroid
//   recent_partners       → weak force-following toward partner centroid
//   autonomy              → probability of pure random walk per step;
//                           (1.0 = wanderer, 0.0 = strict follower)

import * as THREE from 'three';

const MAX_TRAIL = 24;
const MAX_CAST = 5000;
const MAX_VERTS = MAX_CAST * MAX_TRAIL * 3;          // worst-case vertex count

export function createAgents(scene, surface, opts = {}) {
  const { faceCentroids, faceAdjacency, faceCount, facePositions, radius } = surface;
  const sphereRadius = opts.sphereRadius ?? radius ?? 700;
  const stackLift = opts.stackLift ?? 28;
  const maxStepsPerSec = opts.maxStepsPerSec ?? 24;
  const minStepsPerSec = opts.minStepsPerSec ?? 8;
  const partnerAttract = opts.partnerAttract ?? 1.0;
  const firmAttract = opts.firmAttract ?? 3.0;
  const segmentScale = opts.segmentScale ?? 0.75;     // shrink each body triangle toward its face's centroid
  const humanLengthFactor = opts.humanLengthFactor ?? 1.6;  // humans get longer caterpillars
  const segmentColor = opts.segmentColor ?? [0.10, 0.08, 0.07];

  // Single mesh, single big position buffer. Per frame we rewrite the
  // live vertex range; setDrawRange() caps the GPU at the live count.
  const positionArr = new Float32Array(MAX_VERTS * 3);
  const geometry = new THREE.BufferGeometry();
  const posAttr = new THREE.BufferAttribute(positionArr, 3);
  posAttr.setUsage(THREE.DynamicDrawUsage);
  geometry.setAttribute('position', posAttr);
  geometry.setDrawRange(0, 0);

  const material = new THREE.MeshBasicMaterial({
    color: new THREE.Color(segmentColor[0], segmentColor[1], segmentColor[2]),
    side: THREE.DoubleSide,
    transparent: false,
  });

  const mesh = new THREE.Mesh(geometry, material);
  mesh.frustumCulled = false;
  scene.add(mesh);

  const slotByIdx = new Map();
  let castCount = 0;
  let trail = null;             // Int32Array[castCount · MAX_TRAIL] of face indices
  let trailHead = null;         // Int32Array[castCount] ring-buffer head
  let trailLen = null;          // Int8Array[castCount] number of valid entries
  let stepCooldown = null;      // Float32Array[castCount] frames until next step
  let bucket = null;            // Int8Array[castCount] base body length from wealth
  let capability = null;        // Float32Array[castCount]
  let autonomy = null;          // Float32Array[castCount]
  let isHuman = null;           // Uint8Array[castCount]
  let stack = null;             // Int8Array[castCount]
  let firmId = null;            // Int32Array[castCount]
  let recentPartners = null;    // Array<Array<number>>[castCount]
  let initialized = false;

  // Firm centroids in 3D position space, rebuilt each snapshot.
  const firmCentroids = new Map();

  function initialLayout(snapshot) {
    castCount = snapshot.length;
    trail = new Int32Array(castCount * MAX_TRAIL);
    trailHead = new Int32Array(castCount);
    trailLen = new Int8Array(castCount);
    stepCooldown = new Float32Array(castCount);
    bucket = new Int8Array(castCount);
    capability = new Float32Array(castCount);
    autonomy = new Float32Array(castCount);
    isHuman = new Uint8Array(castCount);
    stack = new Int8Array(castCount);
    firmId = new Int32Array(castCount);
    recentPartners = new Array(castCount);

    for (let i = 0; i < castCount; i += 1) {
      const e = snapshot[i];
      slotByIdx.set(e.idx, i);
      const f = Math.floor(Math.random() * faceCount);
      // Seed trail with spawn face so the agent is visible from the
      // first frame (1 segment showing at the spawn cell).
      for (let t = 0; t < MAX_TRAIL; t += 1) trail[i * MAX_TRAIL + t] = f;
      trailHead[i] = 0;
      trailLen[i] = 1;
      stepCooldown[i] = Math.random() * 20;
      recentPartners[i] = [];
      bucket[i] = 1;
    }
    initialized = true;
  }

  function handleCastSnapshot(snapshot) {
    if (!snapshot || snapshot.length === 0) return;
    if (!initialized) initialLayout(snapshot);

    const firmAccum = new Map();

    for (let i = 0; i < snapshot.length; i += 1) {
      const e = snapshot[i];
      const slot = slotByIdx.get(e.idx);
      if (slot === undefined) continue;

      capability[slot] = typeof e.capability === 'number' ? e.capability : 0.5;
      autonomy[slot] = typeof e.autonomy === 'number' ? e.autonomy : 0.5;
      isHuman[slot] = e.is_human ? 1 : 0;
      stack[slot] = typeof e.stack === 'number' ? e.stack : 0;
      firmId[slot] = typeof e.firm_id === 'number' ? e.firm_id : -1;

      const w = Math.max(0, e.wealth ?? 0);
      let b = Math.floor(Math.log2(w + 1)) + 2;
      if (b < 1) b = 1;
      if (b > MAX_TRAIL) b = MAX_TRAIL;
      bucket[slot] = b;

      recentPartners[slot] = Array.isArray(e.recent_partners) ? e.recent_partners : [];

      const fid = firmId[slot];
      if (fid >= 0) {
        const cf = trail[slot * MAX_TRAIL + trailHead[slot]];
        let a = firmAccum.get(fid);
        if (!a) { a = [0, 0, 0, 0]; firmAccum.set(fid, a); }
        a[0] += faceCentroids[cf * 3 + 0];
        a[1] += faceCentroids[cf * 3 + 1];
        a[2] += faceCentroids[cf * 3 + 2];
        a[3] += 1;
      }
    }

    firmCentroids.clear();
    for (const [fid, a] of firmAccum) {
      const n = a[3];
      firmCentroids.set(fid, [a[0] / n, a[1] / n, a[2] / n]);
    }
  }

  // Pick the next face. With probability = autonomy, pick a random
  // non-backtracking neighbour. Otherwise, pick the neighbour whose
  // direction from the current face best aligns with the pull vector
  // (partner centroid + firm centroid). Unit-free: no mixing of
  // brownian noise with force-magnitude scoring.
  function chooseNeighbour(slot) {
    const head = trailHead[slot];
    const cur = trail[slot * MAX_TRAIL + head];
    const prev = trailLen[slot] >= 2
      ? trail[slot * MAX_TRAIL + ((head - 1 + MAX_TRAIL) % MAX_TRAIL)]
      : -1;

    const n0 = faceAdjacency[cur * 3 + 0];
    const n1 = faceAdjacency[cur * 3 + 1];
    const n2 = faceAdjacency[cur * 3 + 2];

    // Filter out the immediate previous face. Keep at least one
    // candidate even if all three are the prev (shouldn't happen on a
    // closed manifold, but defensive).
    const cands = [];
    if (n0 >= 0 && n0 !== prev) cands.push(n0);
    if (n1 >= 0 && n1 !== prev) cands.push(n1);
    if (n2 >= 0 && n2 !== prev) cands.push(n2);
    if (cands.length === 0) {
      return n0 >= 0 ? n0 : n1 >= 0 ? n1 : n2;
    }

    if (Math.random() < autonomy[slot]) {
      return cands[Math.floor(Math.random() * cands.length)];
    }

    // Force-following: score by direction-alignment with pull vector.
    const cx = faceCentroids[cur * 3 + 0];
    const cy = faceCentroids[cur * 3 + 1];
    const cz = faceCentroids[cur * 3 + 2];

    let fx = 0, fy = 0, fz = 0;

    const partners = recentPartners[slot];
    if (partners.length > 0) {
      let pcx = 0, pcy = 0, pcz = 0, n = 0;
      for (let k = 0; k < partners.length; k += 1) {
        const ps = slotByIdx.get(partners[k]);
        if (ps === undefined) continue;
        const pf = trail[ps * MAX_TRAIL + trailHead[ps]];
        pcx += faceCentroids[pf * 3 + 0];
        pcy += faceCentroids[pf * 3 + 1];
        pcz += faceCentroids[pf * 3 + 2];
        n += 1;
      }
      if (n > 0) {
        const inv = 1 / n;
        fx += (pcx * inv - cx) * partnerAttract;
        fy += (pcy * inv - cy) * partnerAttract;
        fz += (pcz * inv - cz) * partnerAttract;
      }
    }

    const fid = firmId[slot];
    if (fid >= 0) {
      const c = firmCentroids.get(fid);
      if (c !== undefined) {
        fx += (c[0] - cx) * firmAttract;
        fy += (c[1] - cy) * firmAttract;
        fz += (c[2] - cz) * firmAttract;
      }
    }

    // No pull at all (no firm, no partners) → random walk fallback.
    if (fx === 0 && fy === 0 && fz === 0) {
      return cands[Math.floor(Math.random() * cands.length)];
    }

    let bestN = cands[0], bestScore = -Infinity;
    for (let k = 0; k < cands.length; k += 1) {
      const n = cands[k];
      const dx = faceCentroids[n * 3 + 0] - cx;
      const dy = faceCentroids[n * 3 + 1] - cy;
      const dz = faceCentroids[n * 3 + 2] - cz;
      const score = dx * fx + dy * fy + dz * fz;
      if (score > bestScore) { bestScore = score; bestN = n; }
    }
    return bestN;
  }

  function tick() {
    if (!initialized) return;

    // 1) Step decisions per agent.
    for (let i = 0; i < castCount; i += 1) {
      stepCooldown[i] -= 1;
      if (stepCooldown[i] <= 0) {
        const next = chooseNeighbour(i);
        trailHead[i] = (trailHead[i] + 1) % MAX_TRAIL;
        trail[i * MAX_TRAIL + trailHead[i]] = next;
        if (trailLen[i] < MAX_TRAIL) trailLen[i] += 1;
        const stepsPerSec = minStepsPerSec + (maxStepsPerSec - minStepsPerSec) * capability[i];
        stepCooldown[i] = 60 / Math.max(0.001, stepsPerSec);
      }
    }

    // 2) Write live vertex data. Each visible segment is a 0.75-
    //    scaled copy of the grid face it occupies, lifted radially
    //    by the agent's stack altitude.
    let vert = 0;
    for (let i = 0; i < castCount; i += 1) {
      let visible = bucket[i];
      if (isHuman[i]) visible = Math.floor(visible * humanLengthFactor);
      if (visible > trailLen[i]) visible = trailLen[i];
      if (visible <= 0) continue;
      if (visible > MAX_TRAIL) visible = MAX_TRAIL;

      const altitude = sphereRadius + stack[i] * stackLift;
      const lift = altitude / sphereRadius;
      const head = trailHead[i];
      const tBase = i * MAX_TRAIL;

      for (let s = 0; s < visible; s += 1) {
        const ti = (head - s + MAX_TRAIL) % MAX_TRAIL;
        const f = trail[tBase + ti];
        if (f < 0 || f >= faceCount) continue;

        const fb = f * 9;
        const v0x = facePositions[fb + 0];
        const v0y = facePositions[fb + 1];
        const v0z = facePositions[fb + 2];
        const v1x = facePositions[fb + 3];
        const v1y = facePositions[fb + 4];
        const v1z = facePositions[fb + 5];
        const v2x = facePositions[fb + 6];
        const v2y = facePositions[fb + 7];
        const v2z = facePositions[fb + 8];

        const cx = (v0x + v1x + v2x) / 3;
        const cy = (v0y + v1y + v2y) / 3;
        const cz = (v0z + v1z + v2z) / 3;

        // Shrink toward centroid, then lift radially.
        const w = vert * 3;
        positionArr[w + 0] = (cx + (v0x - cx) * segmentScale) * lift;
        positionArr[w + 1] = (cy + (v0y - cy) * segmentScale) * lift;
        positionArr[w + 2] = (cz + (v0z - cz) * segmentScale) * lift;
        positionArr[w + 3] = (cx + (v1x - cx) * segmentScale) * lift;
        positionArr[w + 4] = (cy + (v1y - cy) * segmentScale) * lift;
        positionArr[w + 5] = (cz + (v1z - cz) * segmentScale) * lift;
        positionArr[w + 6] = (cx + (v2x - cx) * segmentScale) * lift;
        positionArr[w + 7] = (cy + (v2y - cy) * segmentScale) * lift;
        positionArr[w + 8] = (cz + (v2z - cz) * segmentScale) * lift;
        vert += 3;
      }
    }
    geometry.setDrawRange(0, vert);
    posAttr.needsUpdate = true;
  }

  function setVisible(v) { mesh.visible = !!v; }

  function dispose() {
    scene.remove(mesh);
    geometry.dispose();
    material.dispose();
  }

  function diagnostics() {
    return {
      castCount,
      segments: geometry.drawRange.count / 3,
      firmCount: firmCentroids.size,
    };
  }

  return { mesh, handleCastSnapshot, tick, setVisible, dispose, diagnostics };
}
