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
  const {
    faceCentroids, faceAdjacency, faceCount, facePositions,
    faceAltitudes, vertAltitudes, vertIds, radius,
  } = surface;
  const sphereRadius = opts.sphereRadius ?? radius ?? 700;
  // Per-step inward altitude pull, scaled by the agent's Matryoshka
  // stack. Stack-0 agents leave no mark; stack-N agents (sub-market
  // participants) carve the local face slightly inward each step, so
  // their cumulative activity etches pits into the substrate.
  const stackInwardScale = opts.stackInwardScale ?? 0.00012;
  const maxStepsPerSec = opts.maxStepsPerSec ?? 24;
  const minStepsPerSec = opts.minStepsPerSec ?? 8;
  const partnerAttract = opts.partnerAttract ?? 1.0;
  const firmAttract = opts.firmAttract ?? 3.0;
  const segmentScale = opts.segmentScale ?? 0.75;     // shrink each body triangle toward its face's centroid
  const humanLengthFactor = opts.humanLengthFactor ?? 1.6;  // humans get longer caterpillars
  const segmentColor = opts.segmentColor ?? [0.10, 0.08, 0.07];
  // Pass 18a: wealth-delta drives a radial altitude bump on the
  // agent's current face. log1p() so a runaway wealthy agent doesn't
  // create a single dominant peak; threshold filters out the
  // population-level noise that's always present.
  const altitudeBumpScale = opts.altitudeBumpScale ?? 0.012;
  const altitudeBumpThreshold = opts.altitudeBumpThreshold ?? 0.02;
  // Asymmetric scaling: positive wealth deltas push outward 2x
  // harder than negative deltas push inward. Counterweights the
  // omnipresent inward forces (stack carving + rejects) so wealth
  // peaks remain legible against the inward-drifting baseline.
  const positiveBumpFactor = opts.positiveBumpFactor ?? 2.0;

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
    // Segments and substrate vertices are at the same radius now
    // that the stack lift is gone — without an offset they
    // z-fight at coplanar pixels and the substrate's grid render
    // loses across the whole sphere. polygonOffset pulls agents
    // slightly toward camera in depth space only (no physical
    // displacement) so substrate grid stays visible everywhere
    // except where an agent actually covers.
    polygonOffset: true,
    polygonOffsetFactor: -1,
    polygonOffsetUnits: -1,
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
  let lastWealth = null;        // Float32Array[castCount] — for wealth-delta bumps
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
    lastWealth = new Float32Array(castCount);
    lastWealth.fill(NaN);

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

      // Wealth-delta → altitude bump on the agent's current face.
      // log1p() so windfalls don't dominate; sign carried so losses
      // dig craters and gains raise peaks. Positive deltas get a
      // positiveBumpFactor multiplier (Pass 19) so wealth peaks
      // remain visible against the omnipresent inward pressure from
      // stack carving and rejects.
      const prevW = lastWealth[slot];
      lastWealth[slot] = w;
      if (Number.isFinite(prevW)) {
        const deltaSigned = w - prevW;
        const deltaMag = Math.abs(deltaSigned);
        if (deltaMag >= altitudeBumpThreshold) {
          const cur = trail[slot * MAX_TRAIL + trailHead[slot]];
          const baseBump = altitudeBumpScale * Math.log1p(deltaMag);
          const signed = deltaSigned >= 0 ? baseBump * positiveBumpFactor : -baseBump;
          surface.bumpAltitude(cur, signed);
        }
      }

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
        // Sub-market carving: stack-N agents pull the face they
        // stepped onto inward by a fixed per-step amount, scaled by
        // stack depth. Accumulates into pits over many steps.
        const s = stack[i];
        if (s > 0) surface.bumpAltitude(next, -s * stackInwardScale);
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

      const altScale = surface.mesh?.material?.uniforms?.uAltitudeScale?.value ?? 1.0;
      const globalAlt = surface.mesh?.material?.uniforms?.uGlobalAltitude?.value ?? 0.0;
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

        // Per-vertex lift to match the substrate's actual displaced
        // face plane. Each agent vertex inherits its corresponding
        // face vertex's altitude (plus the global offset) — same
        // formula as the substrate shader so the agent triangle sits
        // exactly on the substrate face's plane.
        const a0 = vertAltitudes ? vertAltitudes[vertIds[f * 3 + 0]] : 0;
        const a1 = vertAltitudes ? vertAltitudes[vertIds[f * 3 + 1]] : 0;
        const a2 = vertAltitudes ? vertAltitudes[vertIds[f * 3 + 2]] : 0;
        const lift0 = 1 + (a0 + globalAlt) * altScale;
        const lift1 = 1 + (a1 + globalAlt) * altScale;
        const lift2 = 1 + (a2 + globalAlt) * altScale;

        const dv0x = v0x * lift0;
        const dv0y = v0y * lift0;
        const dv0z = v0z * lift0;
        const dv1x = v1x * lift1;
        const dv1y = v1y * lift1;
        const dv1z = v1z * lift1;
        const dv2x = v2x * lift2;
        const dv2y = v2y * lift2;
        const dv2z = v2z * lift2;

        const dcx = (dv0x + dv1x + dv2x) / 3;
        const dcy = (dv0y + dv1y + dv2y) / 3;
        const dcz = (dv0z + dv1z + dv2z) / 3;

        const w = vert * 3;
        positionArr[w + 0] = dcx + (dv0x - dcx) * segmentScale;
        positionArr[w + 1] = dcy + (dv0y - dcy) * segmentScale;
        positionArr[w + 2] = dcz + (dv0z - dcz) * segmentScale;
        positionArr[w + 3] = dcx + (dv1x - dcx) * segmentScale;
        positionArr[w + 4] = dcy + (dv1y - dcy) * segmentScale;
        positionArr[w + 5] = dcz + (dv1z - dcz) * segmentScale;
        positionArr[w + 6] = dcx + (dv2x - dcx) * segmentScale;
        positionArr[w + 7] = dcy + (dv2y - dcy) * segmentScale;
        positionArr[w + 8] = dcz + (dv2z - dcz) * segmentScale;
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

  // For scene.js's reject-handler: look up the face an agent
  // currently occupies. Returns -1 if the idx isn't in the cast.
  function currentFaceForIdx(idx) {
    const slot = slotByIdx.get(idx);
    if (slot === undefined) return -1;
    return trail[slot * MAX_TRAIL + trailHead[slot]];
  }

  return {
    mesh, handleCastSnapshot, tick, setVisible, dispose, diagnostics,
    currentFaceForIdx,
  };
}
