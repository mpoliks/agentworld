// Fold-spawn rings (Phase 1.3). Each `folds_v2` event reports
// nominal contribution per depth and a total `n_sub_markets_added`
// count for the tick. We allocate that many small rings, distribute
// them across depths proportional to `per_depth`, and place each at
// a random cast member's current face centroid (offset radially by
// 1.5% of R). Each ring snaps in fast, briefly holds, then fades.
//
// Visual idiom: thin torus rings — hollow centres so they overlap
// without occluding the substrate beneath, and the eye can count
// concurrent events. Ring radius scales with depth so deeper folds
// (rare, costly) read as larger; depth-1 stays small.
//
// The engine emits fold contributions as economy-wide aggregates,
// not per-agent — so the agent attribution here is a proxy
// (placement is on random cast members weighted by trade activity).
//
// Color by depth: depth 1 = neutral grey, deepest depth = magenta
// rgb(140, 102, 191) (matches the matryoshka flow row). Color stays
// saturated across the lifetime; alpha carries the fade.

import * as THREE from 'three';

const FADE_IN = 8;
const HOLD = 20;
const FADE_OUT = 32;
const TOTAL_LIFE = FADE_IN + HOLD + FADE_OUT;

const MAX_INSTANCES_DEFAULT = 4000;   // unbounded pool — set high enough
                                       // for ~10 ticks of 5000-fold backlog
const RADIAL_OFFSET = 0.015;          // 1.5% of R radially outward
const RING_BASE_FRAC = 0.010;         // depth-1 ring radius = 1.0% of R
const RING_DEPTH_FRAC = 0.012;        // each extra depth adds 1.2% of R
const RING_TUBE_FRAC = 0.20;          // tube thickness = 20% of ring radius
const RING_OPACITY = 0.85;

// Color endpoints. Match the matryoshka flow row palette.
const COLOR_SHALLOW = [0.55, 0.55, 0.55];     // grey
const COLOR_DEEP = [140 / 255, 102 / 255, 191 / 255]; // magenta

// Per-depth color cache. Computed from fold_max_depth on every
// event so a lever change that raises max-depth updates the
// gradient.
function depthColor(depth, maxDepth, out) {
  if (maxDepth <= 1) {
    out[0] = COLOR_DEEP[0]; out[1] = COLOR_DEEP[1]; out[2] = COLOR_DEEP[2];
    return;
  }
  const t = Math.max(0, Math.min(1, (depth - 1) / (maxDepth - 1)));
  out[0] = COLOR_SHALLOW[0] * (1 - t) + COLOR_DEEP[0] * t;
  out[1] = COLOR_SHALLOW[1] * (1 - t) + COLOR_DEEP[1] * t;
  out[2] = COLOR_SHALLOW[2] * (1 - t) + COLOR_DEEP[2] * t;
}

export function createFolds(scene, surface, agents, opts = {}) {
  const { faceCentroids, vertDisplayAlt, vertIds, radius } = surface;
  const sphereRadius = opts.sphereRadius ?? radius ?? 700;
  const maxInstances = opts.maxInstances ?? MAX_INSTANCES_DEFAULT;
  // Unit-radius torus (major=1, minor=tube/R). At draw time the
  // per-instance scale matrix sizes the ring by depth, so a single
  // geometry serves every depth bucket.
  const geometry = new THREE.TorusGeometry(1, RING_TUBE_FRAC, 6, 28);
  const material = new THREE.MeshBasicMaterial({
    transparent: true,
    opacity: RING_OPACITY,
    depthTest: true,
    depthWrite: false,
    side: THREE.DoubleSide,
  });
  const mesh = new THREE.InstancedMesh(geometry, material, maxInstances);
  mesh.renderOrder = 8;                // above substrate (0), below arcs (10)
  mesh.frustumCulled = false;
  mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  // Per-instance color attribute.
  const colorBuf = new Float32Array(maxInstances * 3);
  mesh.instanceColor = new THREE.InstancedBufferAttribute(colorBuf, 3);
  mesh.instanceColor.setUsage(THREE.DynamicDrawUsage);

  function ringRadiusFor(depth) {
    return sphereRadius * (RING_BASE_FRAC + RING_DEPTH_FRAC * Math.max(0, depth - 1));
  }
  // Track each instance's life — frame counter, depth, base color,
  // anchor agent idx, anchor face index. Hidden instances get
  // matrix = zero-scale.
  const instances = new Array(maxInstances);
  for (let i = 0; i < maxInstances; i += 1) {
    instances[i] = {
      active: false,
      frame: 0,
      depth: 0,
      baseColor: [0, 0, 0],
      agentIdx: -1,
      face: -1,
    };
  }
  // Free-list of indices for O(1) allocation. Pop from the tail.
  const free = [];
  for (let i = maxInstances - 1; i >= 0; i -= 1) free.push(i);

  // Zero out every matrix so unused instances are invisible.
  const zeroMatrix = new THREE.Matrix4().makeScale(0, 0, 0);
  for (let i = 0; i < maxInstances; i += 1) mesh.setMatrixAt(i, zeroMatrix);
  mesh.instanceMatrix.needsUpdate = true;

  scene.add(mesh);

  // Most-recent active cast indices (filled by handleCastSnapshot).
  // We sample these as placement anchors for the proxy attribution.
  let castIdxList = [];

  const _scratch = new THREE.Matrix4();
  const _pos = new THREE.Vector3();
  const _scaleVec = new THREE.Vector3();
  const _quat = new THREE.Quaternion();
  // Torus default normal points along +Z; orientForOutward rotates
  // it to align with the radial direction at the placement so the
  // ring lies flat on the sphere surface.
  const _zAxis = new THREE.Vector3(0, 0, 1);
  const _outward = new THREE.Vector3();
  function orientForOutward(pos, outQuat) {
    _outward.copy(pos).normalize();
    outQuat.setFromUnitVectors(_zAxis, _outward);
  }

  // Displaced face centroid, matching edges.js / firms.js.
  function faceDisplacedCentroid(f, altScale, globalAlt, out) {
    const cx = faceCentroids[f * 3 + 0];
    const cy = faceCentroids[f * 3 + 1];
    const cz = faceCentroids[f * 3 + 2];
    // Read DISPLAY altitude (bump + continent + trench, clamped) so
    // fold icospheres ride on the actual deformed substrate instead
    // of the un-swollen base sphere — without this, a fold spawned
    // inside a swollen sector continent sits buried in the bulge.
    let avgAlt = 0;
    if (vertDisplayAlt && vertIds) {
      const b = f * 3;
      avgAlt = (vertDisplayAlt[vertIds[b + 0]]
              + vertDisplayAlt[vertIds[b + 1]]
              + vertDisplayAlt[vertIds[b + 2]]) / 3;
    }
    const k = (1 + (avgAlt + globalAlt) * altScale) * (1 + RADIAL_OFFSET);
    out[0] = cx * k;
    out[1] = cy * k;
    out[2] = cz * k;
  }

  function handleCastSnapshot(snapshot) {
    if (!snapshot || snapshot.length === 0) return;
    // Cache the idx list once per snapshot so handleFolds() can
    // sample from it cheaply.
    castIdxList = snapshot.map((e) => e.idx).filter((i) => i >= 0);
  }

  // The engine's `folds_v2` event:
  //   { step, per_depth: number[], n_sub_markets_added: number,
  //     fold_max_depth: number }
  // Distribute `n_sub_markets_added` icospheres across depths
  // proportional to per_depth, clamped to a sane per-tick cap so
  // a single high-depth tick can't flood the pool.
  const PER_TICK_CAP = 200;
  const _color = [0, 0, 0];
  const _tmpVec = [0, 0, 0];
  function handleFolds(ev) {
    if (!ev || !Array.isArray(ev.per_depth) || ev.per_depth.length === 0) return;
    if (castIdxList.length === 0) return;
    const total = ev.per_depth.reduce((a, b) => a + Math.max(0, b), 0);
    if (total <= 0) return;
    const maxDepth = ev.fold_max_depth || ev.per_depth.length;
    // Number to spawn this tick. n_sub_markets_added is small
    // (~37 per tick at default levers) — clamp to the cap so a
    // user-cranked tick can't exhaust the pool in one frame.
    const want = Math.min(
      PER_TICK_CAP,
      Math.max(1, Math.round(ev.n_sub_markets_added || ev.per_depth.length)),
    );
    // Per-depth share of the spawn budget.
    const perDepthCount = ev.per_depth.map((c) =>
      Math.max(0, Math.round(want * (c / total))),
    );

    const altScale = surface.mesh?.material?.uniforms?.uAltitudeScale?.value ?? 1.0;
    const globalAlt = surface.mesh?.material?.uniforms?.uGlobalAltitude?.value ?? 0.0;

    for (let d = 0; d < perDepthCount.length; d += 1) {
      const depth = d + 1;             // 1-indexed
      depthColor(depth, maxDepth, _color);
      for (let k = 0; k < perDepthCount[d]; k += 1) {
        if (free.length === 0) break;
        const slot = free.pop();
        const inst = instances[slot];
        const idx = castIdxList[Math.floor(Math.random() * castIdxList.length)];
        const face = agents.currentFaceForIdx(idx);
        if (face < 0) {
          free.push(slot);             // try again later
          continue;
        }
        inst.active = true;
        inst.frame = 0;
        inst.depth = depth;
        inst.baseColor[0] = _color[0];
        inst.baseColor[1] = _color[1];
        inst.baseColor[2] = _color[2];
        inst.agentIdx = idx;
        inst.face = face;
        // Initial placement at scale 0 — the first tick() pass will
        // grow it. Orient so the ring lies tangent to the sphere.
        faceDisplacedCentroid(face, altScale, globalAlt, _tmpVec);
        _pos.set(_tmpVec[0], _tmpVec[1], _tmpVec[2]);
        orientForOutward(_pos, _quat);
        _scaleVec.set(0, 0, 0);
        _scratch.compose(_pos, _quat, _scaleVec);
        mesh.setMatrixAt(slot, _scratch);
        colorBuf[slot * 3 + 0] = _color[0];
        colorBuf[slot * 3 + 1] = _color[1];
        colorBuf[slot * 3 + 2] = _color[2];
      }
    }
    mesh.instanceMatrix.needsUpdate = true;
    mesh.instanceColor.needsUpdate = true;
  }

  // Per-frame: advance life timers, refresh position (so folds
  // follow their anchor agent's walk), scale by fade curve.
  function tick() {
    const altScale = surface.mesh?.material?.uniforms?.uAltitudeScale?.value ?? 1.0;
    const globalAlt = surface.mesh?.material?.uniforms?.uGlobalAltitude?.value ?? 0.0;
    let anyChange = false;
    let anyColorChange = false;
    for (let s = 0; s < maxInstances; s += 1) {
      const inst = instances[s];
      if (!inst.active) continue;
      inst.frame += 1;
      if (inst.frame > TOTAL_LIFE) {
        inst.active = false;
        free.push(s);
        mesh.setMatrixAt(s, zeroMatrix);
        anyChange = true;
        continue;
      }
      // Fade curve. Fast pop-in, brief hold, slower shrink-out.
      // Ease-out on fade-in so the ring snaps to size, then linear
      // shrink on fade-out so events read as discrete pulses.
      let scale01;
      if (inst.frame < FADE_IN) {
        const t = inst.frame / FADE_IN;
        scale01 = 1 - (1 - t) * (1 - t);    // ease-out quad
      } else if (inst.frame < FADE_IN + HOLD) {
        scale01 = 1.0;
      } else {
        const f = inst.frame - (FADE_IN + HOLD);
        scale01 = 1.0 - f / FADE_OUT;
      }
      if (scale01 < 0) scale01 = 0;

      // Re-anchor to the agent's current face so the ring tracks
      // the caterpillar as it walks.
      const f = agents.currentFaceForIdx(inst.agentIdx);
      if (f >= 0) inst.face = f;
      faceDisplacedCentroid(inst.face, altScale, globalAlt, _tmpVec);
      _pos.set(_tmpVec[0], _tmpVec[1], _tmpVec[2]);
      orientForOutward(_pos, _quat);
      const r = ringRadiusFor(inst.depth) * scale01;
      _scaleVec.set(r, r, r);
      _scratch.compose(_pos, _quat, _scaleVec);
      mesh.setMatrixAt(s, _scratch);

      // Keep depth hue solid across the lifetime — the shrink curve
      // already does the alpha-like fade.
      colorBuf[s * 3 + 0] = inst.baseColor[0];
      colorBuf[s * 3 + 1] = inst.baseColor[1];
      colorBuf[s * 3 + 2] = inst.baseColor[2];
      anyChange = true;
      anyColorChange = true;
    }
    if (anyChange) mesh.instanceMatrix.needsUpdate = true;
    if (anyColorChange) mesh.instanceColor.needsUpdate = true;
  }

  function activeCount() {
    return maxInstances - free.length;
  }

  function setVisible(v) { mesh.visible = !!v; }
  function reset() {
    for (let s = 0; s < maxInstances; s += 1) {
      if (instances[s].active) {
        instances[s].active = false;
        mesh.setMatrixAt(s, zeroMatrix);
      }
    }
    free.length = 0;
    for (let i = maxInstances - 1; i >= 0; i -= 1) free.push(i);
    castIdxList = [];
    mesh.instanceMatrix.needsUpdate = true;
  }
  function dispose() {
    scene.remove(mesh);
    geometry.dispose();
    material.dispose();
  }

  function diagnostics() {
    let active = 0;
    let perDepth = {};
    for (let s = 0; s < maxInstances; s += 1) {
      if (!instances[s].active) continue;
      active += 1;
      perDepth[instances[s].depth] = (perDepth[instances[s].depth] || 0) + 1;
    }
    return { activeCount: active, perDepth };
  }

  // Adversarial check 2.3 support: depth → list of currently-active
  // base color values. A console-side test can verify color
  // saturation increases monotonically with depth.
  function depthColors() {
    const out = {};
    for (let s = 0; s < maxInstances; s += 1) {
      const inst = instances[s];
      if (!inst.active) continue;
      if (!out[inst.depth]) out[inst.depth] = [];
      out[inst.depth].push(inst.baseColor.slice());
    }
    return out;
  }

  return {
    mesh,
    handleCastSnapshot,
    handleFolds,
    tick,
    setVisible,
    reset,
    dispose,
    diagnostics,
    activeCount,
    depthColors,
  };
}
