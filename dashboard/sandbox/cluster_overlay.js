// Cabal overlay (Phase 2 §3.3 of spatial-sandbox-completeness.md).
//
// One translucent triangle-fan patch per active cabal, sized to the
// member set's spherical convex hull. The patch follows the
// displaced substrate (members project to face-centroid positions
// the substrate shader uses), and rebuilds whenever clusters.tick
// produces a new partition.
//
// Algorithm per cabal:
//   1. Collect member face centroids, displaced by substrate
//      altitude (same shader-uniform read as edges.js / firms.js
//      / folds.js — patches stay seated on terrain).
//   2. Compute the mean direction. All hull math happens in the
//      tangent plane at this centroid.
//   3. Project each member to local (u, v) coords. Compute 2-D
//      convex hull via Andrew's monotone chain.
//   4. Triangulate as a fan from the centroid. Lift each hull
//      vertex back to the sphere (project along the centroid's
//      radial direction, with radius matching the displaced
//      substrate at that direction).
//
// Cluster ID hue: golden-ratio hash on cabalId. Cabal opacity
// 0.10 (plan spec). The hue is stable across ticks because
// clusters.js carries cabalIds forward by warm-start — a true
// Jaccard-stability hue (§3.2 SBM in worker) is a follow-on.
//
// renderOrder = 1 — above the substrate (0), below firm spokes
// (5). Patches stay legible under trade arcs (10) and fold
// icospheres (8).

import * as THREE from 'three';

// Plan §C.2 — lowered from 3 to 2. The Fortunato-Barthélemy
// resolution-limit floor (~√(2E) ≈ 45 at 1000 edges/tick) caps
// cabal size from below, not from above; rendering 2-member
// transient communities is honest about what Louvain actually
// produces vs. what the resolution limit forbids.
const MIN_CABAL_RENDER_SIZE = 2;
const HUE_STEPS = 96;
const HCL_C = 0.62;
const HCL_L = 0.50;
const PATCH_LIFT = 1.006;             // hover just above substrate
const OUTLINE_LIFT = 1.008;           // outline + dot sit a hair
                                       // above the fill so they don't
                                       // z-fight the patch surface
const CABAL_OPACITY = 0.10;
const SYNDICATE_OPACITY = 0.22;       // plan §3.3 — promoted clusters
                                       // render bolder so the eye
                                       // distinguishes lasting groups
                                       // from transient ones
const OUTLINE_OPACITY_CABAL = 0.65;
const OUTLINE_OPACITY_SYNDICATE = 0.90;
const OUTLINE_WIDTH_CABAL = 1;
const OUTLINE_WIDTH_SYNDICATE = 2;
const SYNDICATE_DOT_FRAC = 0.012;     // centroid marker for promoted
                                       // clusters only — 1.2% of R

// HSL → RGB (matches firms.js helper). HCL distinctness is close
// enough at low opacity that HSL works.
function hueToRgb(h, c, l, out) {
  const s = c;
  const ll = l;
  const r1 = ll < 0.5 ? ll * (1 + s) : ll + s - ll * s;
  const r2 = 2 * ll - r1;
  const k = (n) => {
    let t = h + n / 3;
    if (t < 0) t += 1;
    if (t > 1) t -= 1;
    if (t < 1 / 6) return r2 + (r1 - r2) * 6 * t;
    if (t < 1 / 2) return r1;
    if (t < 2 / 3) return r2 + (r1 - r2) * (2 / 3 - t) * 6;
    return r2;
  };
  out[0] = k(1);
  out[1] = k(0);
  out[2] = k(-1);
}

function buildHuePalette() {
  const palette = new Float32Array(HUE_STEPS * 3);
  const tmp = [0, 0, 0];
  const phi = 0.6180339887;
  let h = 0.23;                       // offset from firm palette
  for (let i = 0; i < HUE_STEPS; i += 1) {
    hueToRgb(h, HCL_C, HCL_L, tmp);
    palette[i * 3 + 0] = tmp[0];
    palette[i * 3 + 1] = tmp[1];
    palette[i * 3 + 2] = tmp[2];
    h = (h + phi) % 1.0;
  }
  return palette;
}

// 2D convex hull via Andrew's monotone chain. Input: array of
// [x, y] pairs. Output: hull points in CCW order. Handles
// collinear / duplicate points by skipping.
function convexHull2d(points) {
  if (points.length < 3) return points.slice();
  const pts = points.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  function cross(o, a, b) {
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  }
  const lower = [];
  for (const p of pts) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) {
      lower.pop();
    }
    lower.push(p);
  }
  const upper = [];
  for (let i = pts.length - 1; i >= 0; i -= 1) {
    const p = pts[i];
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) {
      upper.pop();
    }
    upper.push(p);
  }
  lower.pop();
  upper.pop();
  return lower.concat(upper);
}

export function createClusterOverlay(scene, surface, agents, opts = {}) {
  const { faceCentroids, vertAltitudes, vertIds, radius } = surface;
  const sphereRadius = opts.sphereRadius ?? radius ?? 700;
  const cabalOpacity = opts.cabalOpacity ?? CABAL_OPACITY;
  const syndicateOpacity = opts.syndicateOpacity ?? SYNDICATE_OPACITY;
  const palette = buildHuePalette();

  // One mesh per cabal, kept in a pool keyed by cabalId. Rebuilt
  // each clusters tick. The pool is cleared every snapshot so a
  // shrinking partition doesn't leak stale meshes.
  const meshByCabal = new Map();
  const group = new THREE.Group();
  group.renderOrder = 1;
  scene.add(group);

  function faceDisplacedCentroid(f, altScale, globalAlt, out) {
    const cx = faceCentroids[f * 3 + 0];
    const cy = faceCentroids[f * 3 + 1];
    const cz = faceCentroids[f * 3 + 2];
    let avgAlt = 0;
    if (vertAltitudes && vertIds) {
      const b = f * 3;
      avgAlt = (vertAltitudes[vertIds[b + 0]]
              + vertAltitudes[vertIds[b + 1]]
              + vertAltitudes[vertIds[b + 2]]) / 3;
    }
    const k = (1 + (avgAlt + globalAlt) * altScale) * PATCH_LIFT;
    out[0] = cx * k;
    out[1] = cy * k;
    out[2] = cz * k;
  }

  function makeMesh(cabalId) {
    // Geometry allocated per cabal; arrays sized at first build.
    const geometry = new THREE.BufferGeometry();
    const material = new THREE.MeshBasicMaterial({
      transparent: true,
      opacity: cabalOpacity,
      side: THREE.DoubleSide,
      depthTest: true,
      depthWrite: false,
      vertexColors: false,
    });
    const slot = ((cabalId % HUE_STEPS) + HUE_STEPS) % HUE_STEPS;
    const r = palette[slot * 3 + 0];
    const g = palette[slot * 3 + 1];
    const b = palette[slot * 3 + 2];
    material.color.setRGB(r, g, b);
    const mesh = new THREE.Mesh(geometry, material);
    mesh.renderOrder = 1;
    mesh.frustumCulled = false;

    // Hull-boundary outline. LineLoop over the same hull vertices
    // as the fill, lifted slightly so it crisply rims the patch.
    // Width is approximate (most GPUs clamp LineBasicMaterial width
    // to 1px) but opacity carries the cabal/syndicate distinction.
    const outlineGeom = new THREE.BufferGeometry();
    const outlineMat = new THREE.LineBasicMaterial({
      color: new THREE.Color(r, g, b),
      transparent: true,
      opacity: OUTLINE_OPACITY_CABAL,
      linewidth: OUTLINE_WIDTH_CABAL,
      depthTest: true,
      depthWrite: false,
    });
    const outline = new THREE.LineLoop(outlineGeom, outlineMat);
    outline.renderOrder = 2;
    outline.frustumCulled = false;
    mesh.add(outline);
    mesh.userData.outline = outline;

    // Centroid dot. Only visible for syndicates; cabals keep the
    // soft-fill-only treatment so transient groups don't visually
    // compete with promoted ones.
    const dotGeom = new THREE.SphereGeometry(1, 10, 8);
    const dotMat = new THREE.MeshBasicMaterial({
      color: new THREE.Color(r, g, b),
      transparent: true,
      opacity: 0.0,
      depthTest: true,
      depthWrite: false,
    });
    const dot = new THREE.Mesh(dotGeom, dotMat);
    dot.renderOrder = 3;
    dot.frustumCulled = false;
    dot.visible = false;
    mesh.add(dot);
    mesh.userData.dot = dot;

    return mesh;
  }

  function setMeshStatus(mesh, status) {
    const isSyndicate = status === 'syndicate';
    mesh.material.opacity = isSyndicate ? syndicateOpacity : cabalOpacity;
    const outline = mesh.userData.outline;
    if (outline) {
      outline.material.opacity = isSyndicate
        ? OUTLINE_OPACITY_SYNDICATE
        : OUTLINE_OPACITY_CABAL;
      outline.material.linewidth = isSyndicate
        ? OUTLINE_WIDTH_SYNDICATE
        : OUTLINE_WIDTH_CABAL;
    }
    const dot = mesh.userData.dot;
    if (dot) {
      dot.visible = isSyndicate;
      dot.material.opacity = isSyndicate ? 1.0 : 0.0;
    }
  }

  function rebuildPatchGeometry(mesh, members) {
    // members: array of {x, y, z} positions on the displaced sphere.
    if (members.length < MIN_CABAL_RENDER_SIZE) {
      mesh.visible = false;
      return;
    }
    // Compute centroid direction. Mean of unit vectors.
    let cx = 0, cy = 0, cz = 0;
    for (const m of members) {
      const r = Math.sqrt(m.x * m.x + m.y * m.y + m.z * m.z) || 1;
      cx += m.x / r; cy += m.y / r; cz += m.z / r;
    }
    const cn = Math.sqrt(cx * cx + cy * cy + cz * cz) || 1;
    cx /= cn; cy /= cn; cz /= cn;

    // Build tangent basis (e1, e2) orthonormal to the centroid
    // direction. Pick the up-vector that's least aligned with the
    // centroid so the cross product is well-conditioned.
    let upX = 0, upY = 1, upZ = 0;
    if (Math.abs(cy) > 0.9) { upX = 1; upY = 0; upZ = 0; }
    let e1x = upY * cz - upZ * cy;
    let e1y = upZ * cx - upX * cz;
    let e1z = upX * cy - upY * cx;
    const e1n = Math.sqrt(e1x * e1x + e1y * e1y + e1z * e1z) || 1;
    e1x /= e1n; e1y /= e1n; e1z /= e1n;
    const e2x = cy * e1z - cz * e1y;
    const e2y = cz * e1x - cx * e1z;
    const e2z = cx * e1y - cy * e1x;

    // Project each member to tangent (u, v) and also remember
    // its sphere radius so the back-projection picks up the
    // substrate's altitude at that direction.
    const proj = [];
    let meanR = 0;
    for (let i = 0; i < members.length; i += 1) {
      const m = members[i];
      const u = m.x * e1x + m.y * e1y + m.z * e1z;
      const v = m.x * e2x + m.y * e2y + m.z * e2z;
      const r = Math.sqrt(m.x * m.x + m.y * m.y + m.z * m.z);
      proj.push([u, v, r]);
      meanR += r;
    }
    meanR /= members.length;

    // 2-D convex hull on the (u, v) projection.
    const hull2 = convexHull2d(proj.map((p) => [p[0], p[1]]));
    if (hull2.length < 3) {
      mesh.visible = false;
      return;
    }
    // Triangle fan from the centroid (u=0, v=0). The centroid sits
    // at sphere radius meanR so the patch hugs the same altitude
    // as the members.
    const triCount = hull2.length;
    const positions = new Float32Array((1 + hull2.length) * 3);
    positions[0] = cx * meanR;
    positions[1] = cy * meanR;
    positions[2] = cz * meanR;
    for (let i = 0; i < hull2.length; i += 1) {
      const [u, v] = hull2[i];
      const px = cx * meanR + u * e1x + v * e2x;
      const py = cy * meanR + u * e1y + v * e2y;
      const pz = cz * meanR + u * e1z + v * e2z;
      // Re-normalize to the sphere surface so the patch sits on
      // the substrate even when (u, v) push out into 3D.
      const len = Math.sqrt(px * px + py * py + pz * pz) || 1;
      const s = meanR / len;
      positions[(1 + i) * 3 + 0] = px * s;
      positions[(1 + i) * 3 + 1] = py * s;
      positions[(1 + i) * 3 + 2] = pz * s;
    }
    const indices = new Uint32Array(triCount * 3);
    for (let i = 0; i < triCount; i += 1) {
      indices[i * 3 + 0] = 0;
      indices[i * 3 + 1] = 1 + i;
      indices[i * 3 + 2] = 1 + ((i + 1) % triCount);
    }
    // Recycle the existing geometry buffers when sizes match to
    // avoid a per-tick alloc.
    const geom = mesh.geometry;
    const oldPos = geom.getAttribute('position');
    if (oldPos && oldPos.array.length === positions.length) {
      oldPos.array.set(positions);
      oldPos.needsUpdate = true;
    } else {
      geom.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    }
    if (geom.index && geom.index.array.length === indices.length) {
      geom.index.array.set(indices);
      geom.index.needsUpdate = true;
    } else {
      geom.setIndex(new THREE.BufferAttribute(indices, 1));
    }
    mesh.visible = true;

    // Build the outline. Same hull vertices as the patch, but lifted
    // by OUTLINE_LIFT/PATCH_LIFT so the line crisply rims the fill
    // instead of co-planar z-fighting it.
    const outline = mesh.userData.outline;
    if (outline) {
      const liftBoost = OUTLINE_LIFT / PATCH_LIFT;
      const outPos = new Float32Array(hull2.length * 3);
      for (let i = 0; i < hull2.length; i += 1) {
        outPos[i * 3 + 0] = positions[(1 + i) * 3 + 0] * liftBoost;
        outPos[i * 3 + 1] = positions[(1 + i) * 3 + 1] * liftBoost;
        outPos[i * 3 + 2] = positions[(1 + i) * 3 + 2] * liftBoost;
      }
      const og = outline.geometry;
      const oldOut = og.getAttribute('position');
      if (oldOut && oldOut.array.length === outPos.length) {
        oldOut.array.set(outPos);
        oldOut.needsUpdate = true;
      } else {
        og.setAttribute('position', new THREE.BufferAttribute(outPos, 3));
      }
    }

    // Position the centroid dot (visible only for syndicates). Sized
    // here too so a sphere-radius shift in PATCH_LIFT carries over.
    const dot = mesh.userData.dot;
    if (dot) {
      const liftBoost = OUTLINE_LIFT / PATCH_LIFT;
      dot.position.set(
        positions[0] * liftBoost,
        positions[1] * liftBoost,
        positions[2] * liftBoost,
      );
      const dotR = sphereRadius * SYNDICATE_DOT_FRAC;
      dot.scale.set(dotR, dotR, dotR);
    }
  }

  // Called each cluster tick. `partition` is a Map<agentIdx, stableId>
  // (or raw cabalId pre-§3.2). `labels` is the optional cluster_labels
  // accessor so the overlay can read each cluster's status and tint
  // the patch accordingly (cabal 0.10 opacity, syndicate 0.22).
  function update(partition, labels = null) {
    if (!partition) return;
    const altScale = surface.mesh?.material?.uniforms?.uAltitudeScale?.value ?? 1.0;
    const globalAlt = surface.mesh?.material?.uniforms?.uGlobalAltitude?.value ?? 0.0;

    // Group members by cluster id, looking up each agent's current
    // face.
    const byCluster = new Map();
    const tmp = [0, 0, 0];
    for (const [agentIdx, clusterId] of partition) {
      if (clusterId < 0) continue;
      const f = agents.currentFaceForIdx(agentIdx);
      if (f < 0) continue;
      faceDisplacedCentroid(f, altScale, globalAlt, tmp);
      let arr = byCluster.get(clusterId);
      if (!arr) { arr = []; byCluster.set(clusterId, arr); }
      arr.push({ x: tmp[0], y: tmp[1], z: tmp[2] });
    }

    // Build / refresh meshes for every cluster in the partition.
    const seen = new Set();
    for (const [clusterId, members] of byCluster) {
      seen.add(clusterId);
      let mesh = meshByCabal.get(clusterId);
      if (!mesh) {
        mesh = makeMesh(clusterId);
        meshByCabal.set(clusterId, mesh);
        group.add(mesh);
      }
      rebuildPatchGeometry(mesh, members);
      if (labels) {
        setMeshStatus(mesh, labels.statusOf(clusterId));
      }
    }
    // Drop meshes for clusters no longer in the partition.
    for (const [clusterId, mesh] of meshByCabal) {
      if (!seen.has(clusterId)) {
        group.remove(mesh);
        mesh.geometry.dispose();
        mesh.material.dispose();
        const outline = mesh.userData.outline;
        if (outline) { outline.geometry.dispose(); outline.material.dispose(); }
        const dot = mesh.userData.dot;
        if (dot) { dot.geometry.dispose(); dot.material.dispose(); }
        meshByCabal.delete(clusterId);
      }
    }
  }

  function setVisible(v) { group.visible = !!v; }
  function reset() {
    for (const [, mesh] of meshByCabal) {
      group.remove(mesh);
      mesh.geometry.dispose();
      mesh.material.dispose();
    }
    meshByCabal.clear();
  }
  function dispose() {
    reset();
    scene.remove(group);
  }
  function diagnostics() {
    let visible = 0;
    for (const [, m] of meshByCabal) if (m.visible) visible += 1;
    return {
      meshes: meshByCabal.size,
      visible,
      // Plan §C.1 — exposed so the HUD can show RENDER FLOOR.
      minCabalRenderSize: MIN_CABAL_RENDER_SIZE,
    };
  }

  return {
    group,
    update,
    setVisible,
    reset,
    dispose,
    diagnostics,
  };
}
