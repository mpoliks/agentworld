// Firm-membership spokes (Phase 1.2). Each cast member with a
// non-negative firm_id gets a thin low-opacity line from its
// current face centroid to the firm's centroid, both displaced by
// substrate altitude so spokes hug the deformed terrain. Color is
// a stable 64-step HCL palette indexed by firm_id, so the same
// firm keeps its hue across ticks.
//
// Render order is 5 — under the trade arcs (10) so executed trades
// stay legible on top of firm structure, but above the substrate
// (default 0) so spokes don't get z-fought out of view.
//
// The cast snapshot drives membership; the per-frame tick reads
// each member's CURRENT face from agents.currentFaceForIdx() so
// spokes follow caterpillars as they walk. No buffer reallocation
// per frame — positions overwrite in place.

import * as THREE from 'three';

const MAX_SPOKES_DEFAULT = 5000;     // covers ~25 firms × 200 members
const HUE_STEPS = 64;
const HCL_C = 0.55;
const HCL_L = 0.58;

// HCL → RGB. h in [0,1], c in [0,1], l in [0,1]. Approximate
// (HSL is close enough for distinct colour bands at our opacity).
function hclToRgb(h, c, l, out) {
  // HSL with hue rotation. Saturation := c, lightness := l.
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

// Stable hue from firm_id. firm_id % HUE_STEPS picks a slot in a
// fixed palette; the palette is generated once with golden-ratio
// hue spacing so adjacent firms don't end up adjacent in hue.
function buildPalette() {
  const palette = new Float32Array(HUE_STEPS * 3);
  const tmp = [0, 0, 0];
  const phi = 0.6180339887;
  let h = 0.0;
  for (let i = 0; i < HUE_STEPS; i += 1) {
    hclToRgb(h, HCL_C, HCL_L, tmp);
    palette[i * 3 + 0] = tmp[0];
    palette[i * 3 + 1] = tmp[1];
    palette[i * 3 + 2] = tmp[2];
    h = (h + phi) % 1.0;
  }
  return palette;
}

export function createFirms(scene, surface, agents, opts = {}) {
  const { faceCentroids, vertAltitudes, vertIds, radius } = surface;
  const sphereRadius = opts.sphereRadius ?? radius ?? 700;
  const maxSpokes = opts.maxSpokes ?? MAX_SPOKES_DEFAULT;
  const opacity = opts.opacity ?? 0.08;
  const spokeLift = opts.spokeLift ?? 1.003;

  const palette = buildPalette();

  // Each spoke is one line segment = 2 vertices = 6 floats.
  const positions = new Float32Array(maxSpokes * 6);
  const colors = new Float32Array(maxSpokes * 6);
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  geometry.setDrawRange(0, 0);

  const material = new THREE.LineBasicMaterial({
    vertexColors: true,
    transparent: true,
    opacity,
    depthTest: true,
    depthWrite: false,
  });
  const mesh = new THREE.LineSegments(geometry, material);
  mesh.renderOrder = 5;
  mesh.frustumCulled = false;
  scene.add(mesh);

  // Cast-snapshot bookkeeping. membersByFirm[fid] = array of agent
  // idx values from the most recent snapshot. Used to compute
  // centroids and to know which spokes to draw.
  let castIdxByFirm = new Map();       // firmId → idx[]
  let firmIdsActive = [];              // sorted list of active firmIds
  let memberStats = {                  // for diagnostics + checks
    n_firms: 0,
    n_members: 0,
    n_cross_sector: 0,
    n_members_with_spoke: 0,
  };
  // Cast-side sector lookup for the cross-sector check.
  let sectorByIdx = new Map();

  function handleCastSnapshot(snapshot) {
    if (!snapshot || snapshot.length === 0) return;
    castIdxByFirm = new Map();
    sectorByIdx = new Map();
    const sectorsByFirm = new Map();   // firmId → Set<sector_id>
    for (let i = 0; i < snapshot.length; i += 1) {
      const e = snapshot[i];
      const fid = typeof e.firm_id === 'number' ? e.firm_id : -1;
      if (fid < 0) continue;
      let arr = castIdxByFirm.get(fid);
      if (!arr) { arr = []; castIdxByFirm.set(fid, arr); }
      arr.push(e.idx);
      sectorByIdx.set(e.idx, typeof e.sector === 'number' ? e.sector : -1);
      let set = sectorsByFirm.get(fid);
      if (!set) { set = new Set(); sectorsByFirm.set(fid, set); }
      if (typeof e.sector === 'number') set.add(e.sector);
    }
    firmIdsActive = Array.from(castIdxByFirm.keys()).sort((a, b) => a - b);

    let nCross = 0;
    let nMembers = 0;
    for (const [fid, arr] of castIdxByFirm) {
      nMembers += arr.length;
      const sset = sectorsByFirm.get(fid);
      if (sset && sset.size >= 2) nCross += 1;
    }
    memberStats = {
      n_firms: firmIdsActive.length,
      n_members: nMembers,
      n_cross_sector: nCross,
      n_members_with_spoke: 0,
    };
  }

  // Displaced face centroid: faceCentroids[f] * (1 + alt * altScale).
  const _pa = [0, 0, 0];
  const _cen = [0, 0, 0];
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
    const k = 1 + (avgAlt + globalAlt) * altScale;
    out[0] = cx * k;
    out[1] = cy * k;
    out[2] = cz * k;
  }

  function tick() {
    // Match edges.js: read the same shader-uniform values the
    // substrate uses so spokes hug the same displaced surface as
    // the trade arcs. Default to (1, 0) before the first uniform
    // write.
    const altScale = surface.mesh?.material?.uniforms?.uAltitudeScale?.value ?? 1.0;
    const globalAlt = surface.mesh?.material?.uniforms?.uGlobalAltitude?.value ?? 0.0;
    let seg = 0;
    let nWithSpoke = 0;
    for (let f = 0; f < firmIdsActive.length; f += 1) {
      const fid = firmIdsActive[f];
      const members = castIdxByFirm.get(fid);
      if (!members || members.length < 2) continue;

      // Centroid = mean of member face positions (displaced).
      let cx = 0, cy = 0, cz = 0, n = 0;
      for (let m = 0; m < members.length; m += 1) {
        const fa = agents.currentFaceForIdx(members[m]);
        if (fa < 0) continue;
        faceDisplacedCentroid(fa, altScale, globalAlt, _pa);
        cx += _pa[0]; cy += _pa[1]; cz += _pa[2];
        n += 1;
      }
      if (n < 2) continue;
      _cen[0] = (cx / n) * spokeLift;
      _cen[1] = (cy / n) * spokeLift;
      _cen[2] = (cz / n) * spokeLift;

      // Palette colour for this firm.
      const slot = ((fid % HUE_STEPS) + HUE_STEPS) % HUE_STEPS;
      const cr = palette[slot * 3 + 0];
      const cg = palette[slot * 3 + 1];
      const cb = palette[slot * 3 + 2];

      // One spoke per member from member position → centroid.
      for (let m = 0; m < members.length; m += 1) {
        if (seg >= maxSpokes) break;
        const fa = agents.currentFaceForIdx(members[m]);
        if (fa < 0) continue;
        faceDisplacedCentroid(fa, altScale, globalAlt, _pa);
        const off = seg * 6;
        positions[off + 0] = _pa[0] * spokeLift;
        positions[off + 1] = _pa[1] * spokeLift;
        positions[off + 2] = _pa[2] * spokeLift;
        positions[off + 3] = _cen[0];
        positions[off + 4] = _cen[1];
        positions[off + 5] = _cen[2];
        colors[off + 0] = cr;
        colors[off + 1] = cg;
        colors[off + 2] = cb;
        colors[off + 3] = cr;
        colors[off + 4] = cg;
        colors[off + 5] = cb;
        seg += 1;
        nWithSpoke += 1;
      }
      if (seg >= maxSpokes) break;
    }
    geometry.attributes.position.needsUpdate = true;
    geometry.attributes.color.needsUpdate = true;
    geometry.setDrawRange(0, seg * 2);
    memberStats.n_members_with_spoke = nWithSpoke;
  }

  function setVisible(v) { mesh.visible = !!v; }
  function reset() {
    castIdxByFirm = new Map();
    firmIdsActive = [];
    sectorByIdx = new Map();
    memberStats = { n_firms: 0, n_members: 0, n_cross_sector: 0, n_members_with_spoke: 0 };
    geometry.setDrawRange(0, 0);
  }
  function dispose() {
    scene.remove(mesh);
    geometry.dispose();
    material.dispose();
  }

  function diagnostics() {
    return { ...memberStats };
  }

  // Adversarial check support: full mapping of firm_id → member idx
  // list so a console-side check can verify spoke ↔ membership match.
  function membersByFirm() {
    const out = {};
    for (const [fid, arr] of castIdxByFirm) {
      out[fid] = arr.slice();
    }
    return out;
  }

  return {
    mesh,
    handleCastSnapshot,
    tick,
    setVisible,
    reset,
    dispose,
    diagnostics,
    membersByFirm,
  };
}
